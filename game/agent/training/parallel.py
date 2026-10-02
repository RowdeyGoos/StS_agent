"""Persistent, bounded spawn collectors for one synchronous PPO owner.

Only public rollout features cross back to the learner. Each round starts new
games and local action generators; no environment or RNG is kept in a worker.
"""
import multiprocessing
import queue
import signal
import threading
import time

import torch

from game.agent.runner import RunCancelled, RunFailure, prepare_directories
from game.agent.workers import _cleanup, _defer_start_signals
from game.agent.performance import GAME_WORKER_LIMIT
from .model import ActorCritic
from .rollout import Rollout, advantages, check_cancel, collect, fingerprint
from .scenarios import episode_seed


def collection_settings(workers):
    if type(workers) is not int or not 1 <= workers <= GAME_WORKER_LIMIT:
        raise ValueError(f'PPO workers must be between 1 and {GAME_WORKER_LIMIT}')
    return {'workers': workers, 'schedule': 'serial_v1' if workers == 1 else 'parallel_quota_ranges_v1'}


def allocations(quota, workers, cursor):
    """Reserve at most one episode per decision, without reusing skipped seeds."""
    collection_settings(workers)
    if type(quota) is not int or quota < 1:
        raise ValueError('Invalid parallel collection quota')
    episode_seed('train', cursor)
    # The next checkpoint cursor must also be a valid starting index.
    episode_seed('train', cursor + quota)
    count = min(workers, quota)
    size, extra = divmod(quota, count)
    jobs = []
    for index in range(count):
        decisions = size + (index < extra)
        jobs.append((cursor, decisions))
        cursor += decisions
    return tuple(jobs)


def _worker(vocabulary, architecture, experiment, env_factory, stopped, connection):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    # Avoid multiplying the parent's BLAS/Torch thread count by the pool size.
    torch.set_num_threads(1)
    try:
        model = ActorCritic(vocabulary, architecture,
                           action_policy=experiment.training.action_policy).requires_grad_(False)
        while not stopped.is_set():
            if not connection.poll(.05):
                continue
            job = connection.recv()
            progress = {}
            try:
                model.load_state_dict({k: torch.from_numpy(v) for k, v in job['weights'].items()}, strict=True)
                if fingerprint(model) != job['behavior']:
                    raise ValueError('Worker policy differs from the frozen behavior policy')
                result = collect(model, experiment, torch.Generator().manual_seed(job['seed']),
                    cursor=job['cursor'], iteration=job['iteration'], decisions=job['decisions'],
                    output_dir=job['output_dir'], audit_dir=job['audit_dir'], env_factory=env_factory,
                    cancel=stopped, deadline=job['deadline'], progress=progress,
                    encounter_cursor=job['encounter_cursor'], encounter_stride=job['encounter_stride'])
                connection.send(('complete', result))
                # Do not retain the previous rollout while waiting for work.
                del result, job, progress
            except BaseException as error:
                # Exception messages can contain privileged state. Send only a
                # type and the collector's public progress, never its traceback.
                progress['failure'] = type(error).__name__
                status = 'cancelled' if isinstance(error, (RunCancelled, KeyboardInterrupt)) else 'failed'
                connection.send((status, progress))
                break
    finally:
        connection.close()


def _exchange(index, connection, inbox, outbox):
    """Keep large pipe sends/receives off the cancellation/deadline thread."""
    while True:
        job = inbox.get()
        if job is None:
            return
        try:
            connection.send(job)
            result = connection.recv()
        except BaseException:
            outbox.put((index, ('failed', {'failure': 'WorkerTransportError'})))
            return
        outbox.put((index, result))
        del job, result


class ParallelCollector:
    """Idle processes persist; games end before every result is acknowledged."""
    def __init__(self, model, experiment, env_factory, workers):
        self.settings = collection_settings(workers)
        self.vocabulary, self.architecture = model.vocabulary, model.architecture
        self.experiment, self.env_factory = experiment, env_factory
        self.context = multiprocessing.get_context('spawn')
        self.stopped = self.context.Event()
        self.active, self.channels = {}, {}
        self.outbox = queue.Queue()
        self.closed = False

    def _start(self, count, cancel, deadline):
        before = time.perf_counter()
        for index in range(len(self.active), count):
            check_cancel(cancel)
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('PPO collection startup exceeded its time budget')
            parent, child = self.context.Pipe()
            process = self.context.Process(target=_worker, args=(self.vocabulary, self.architecture,
                self.experiment, self.env_factory, self.stopped, child), name='sts-ppo-collector')
            # Register before start, and defer signals until the OS handle is
            # attached. Reuse the episode runner's interruption-safe lifecycle.
            self.active[index] = (process, parent, time.monotonic())
            try:
                with _defer_start_signals():
                    process.start()
            finally:
                child.close()
            inbox = queue.Queue()
            thread = threading.Thread(target=_exchange, args=(index, parent, inbox, self.outbox),
                                      name='sts-ppo-transfer', daemon=True)
            self.channels[index] = (inbox, thread)
            with _defer_start_signals():
                thread.start()
        return time.perf_counter() - before

    def collect(self, model, generator, *, cursor, iteration, decisions=None, output_dir=None,
                audit_dir=None, cancel=None, deadline=None, progress=None):
        if self.closed:
            raise ValueError('Parallel collector is closed')
        quota = self.experiment.ppo.rollout_steps if decisions is None else decisions
        if type(quota) is not int or not 1 <= quota <= self.experiment.ppo.rollout_steps:
            raise ValueError('Invalid bounded collection quota')
        jobs = allocations(quota, self.settings['workers'], cursor)
        progress = {} if progress is None else progress
        parts, results = {}, {}
        progress.update(status='collecting', episodes=[], steps=0, stop_reason=None,
                        components=dict.fromkeys(self.experiment.training.reward.components, 0.),
                        workers=len(jobs), worker_batches=[])
        before = time.perf_counter()
        def refresh():
            ordered = [parts[i] for i in sorted(parts)]
            progress['episodes'] = [e for p in ordered for e in p.get('episodes', [])]
            progress['steps'] = sum(p.get('steps', 0) for p in ordered)
            progress['components'] = {k: sum(p.get('components', {}).get(k, 0.) for p in ordered)
                                      for k in self.experiment.training.reward.components}
            progress['worker_batches'] = [dict(worker=i, quota=jobs[i][1],
                **{k: parts[i][k] for k in ('status', 'steps', 'seconds') if k in parts[i]}) for i in sorted(parts)]
        try:
            check_cancel(cancel)
            if output_dir is not None:
                output_dir, audit_dir = prepare_directories(output_dir, audit_dir)
            behavior = fingerprint(model)
            progress['spawn_seconds'] = self._start(len(jobs), cancel, deadline)
            # NumPy snapshots are ordinary pipe payloads, with no shared Torch
            # storage that an optimizer step could mutate under a worker.
            weights = {k: v.detach().cpu().numpy().copy() for k, v in model.state_dict().items()}
            seeds = torch.randint(0, 2**63-1, (len(jobs),), generator=generator).tolist()
            hard_deadline = (deadline if deadline is not None else time.monotonic() +
                min(3600., max(n for _, n in jobs)*self.experiment.ppo.episode_seconds)) + 5.
            for index, (start, count) in enumerate(jobs):
                self.channels[index][0].put(dict(weights=weights, behavior=behavior, seed=seeds[index],
                    cursor=start, decisions=count, iteration=iteration, output_dir=output_dir,
                    audit_dir=audit_dir, deadline=deadline,
                    encounter_cursor=iteration*len(jobs)+index, encounter_stride=len(jobs)))
            while len(results) < len(jobs):
                check_cancel(cancel)
                if time.monotonic() >= hard_deadline:
                    raise TimeoutError('PPO collector exceeded its hard deadline')
                try:
                    index, (status, value) = self.outbox.get(timeout=.02)
                except queue.Empty:
                    if any(not p.is_alive() for p, _, _ in self.active.values()):
                        raise RunFailure('PPO collector exited without a result')
                    continue
                if status != 'complete':
                    parts[index] = value
                    refresh()
                    raise RunFailure('PPO collector stopped: ' + value.get('failure', status))
                start, count = jobs[index]
                if (index in results or type(value) is not Rollout or value.behavior != behavior or
                        value.iteration != iteration or value.experiment != self.experiment.identity or
                        not start <= value.next_episode <= start+count or len(value.steps) > count or
                        len(value.steps) != value.progress['steps'] or
                        len(value.steps) != count and value.progress['stop_reason'] is None):
                    raise RunFailure('Invalid frozen PPO worker batch')
                results[index], parts[index] = value, value.progress
                refresh()
            if fingerprint(model) != behavior:
                raise ValueError('Policy changed during parallel collection')
            steps = tuple(s for i in range(len(jobs)) for s in results[i].steps)
            if steps:
                advantages(steps, gamma=self.experiment.ppo.gamma, gae_lambda=self.experiment.ppo.gae_lambda)
            progress['stop_reason'] = next((parts[i]['stop_reason'] for i in range(len(jobs))
                                           if parts[i]['stop_reason'] is not None), None)
            progress['status'] = 'complete'
            return Rollout(steps, behavior, iteration, self.experiment.identity, cursor+quota, progress)
        except BaseException as error:
            progress.update(status='cancelled' if isinstance(error, (RunCancelled, KeyboardInterrupt)) else 'failed',
                            failure=type(error).__name__, discarded=True)
            self.close()
            raise
        finally:
            progress['seconds'] = time.perf_counter()-before
            progress['decisions_per_second'] = progress['steps']/progress['seconds']

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stopped.set()
        for inbox, _ in self.channels.values():
            inbox.put(None)
        try:
            _cleanup(self.active, self.stopped)
        finally:
            until = time.monotonic()+1.
            for _, thread in self.channels.values():
                if thread.ident is not None:
                    thread.join(max(0., until-time.monotonic()))
        if any(thread.is_alive() for _, thread in self.channels.values()):
            raise RunFailure('PPO transfer cleanup failed')
        self.active.clear()
        self.channels.clear()
        while not self.outbox.empty():
            self.outbox.get_nowait()
