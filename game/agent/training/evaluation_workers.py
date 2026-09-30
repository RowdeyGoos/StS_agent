"""Persistent evaluation processes with frozen models and per-game ownership."""
from dataclasses import asdict
import multiprocessing
import signal
import time

from game.agent.provenance import implementation
from game.agent.runner import RunCancelled, run_episode
from game.agent.workers import _cleanup, _defer_start_signals
from .checkpoint import load_policy
from .run_demonstrations import describe

STARTUP_SECONDS = 30.
REPORT_GRACE_SECONDS = 30.


def settings(workers):
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError('Evaluation workers must be between 1 and 8')
    return {'workers': workers, 'schedule': 'serial_v1' if workers == 1 else 'parallel_episodes_v1'}


def _worker(checkpoints, policies, source, output, private, stopped, connection):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    index = None
    try:
        import torch
        torch.set_num_threads(1)
        if asdict(implementation()) != source:
            raise ValueError('Evaluation implementation changed after planning')
        choices = {'heuristic': {}}
        for name, (path, digest, task) in checkpoints.items():
            model = load_policy(path, expected_sha256=digest, task=task)
            identity = ('hybrid_v1:'+digest+':'+source['policy'] if name == 'hybrid' else model.identity)
            if identity != policies[name]:
                raise ValueError('Evaluation policy changed after planning')
            choices[name] = {'combat_policy' if name == 'hybrid' else 'policy': model,
                             'policy_identity': identity}
        connection.send(('ready', None, None))
        while not stopped.is_set():
            if not connection.poll(.02):
                continue
            index, config, episode, policy = connection.recv()
            result = run_episode(config, output_dir=output, audit_dir=private,
                                 episode_id=episode, cancel=stopped, **choices[policy])
            # Canonical loading/outcome analysis is part of the worker's job,
            # so replay validation does not serialize all games in the parent.
            row = describe(result, split=config.split, goal=config.goal)
            connection.send(('complete', index, row))
            index = None
            del result, row
    except BaseException as error:
        # Seeds, engine state and exception text never enter public reports.
        status = 'interrupted' if isinstance(error, (RunCancelled, KeyboardInterrupt)) else 'failed'
        try:
            connection.send((status, index, type(error).__name__))
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


def evaluate_parallel(rows, configs, *, checkpoints, policies, source, output, private, workers, cancel=None):
    """Update the preplanned rows in place; keep every case after failure/stop.

    One small config enters each worker and one public description comes back.
    Games and policy objects never cross worker boundaries. No task is retried.
    """
    settings(workers)
    context = multiprocessing.get_context('spawn')
    stopped = context.Event()
    active, phases, assigned, deadlines = {}, {}, {}, {}
    result = {'status': 'complete'}
    scheduled = completed = 0

    def stop(status, reason, worker=None):
        if result['status'] == 'complete':
            result.update(status=status, failure=reason)
        if worker in assigned:
            index = assigned.pop(worker)
            rows[index].update(status=status, failure=reason)
        stopped.set()

    def receive(worker, *, shutting_down=False):
        nonlocal completed
        process, connection, _ = active[worker]
        try:
            status, index, value = connection.recv()
        except (EOFError, OSError):
            if shutting_down and worker in assigned and result['status'] != 'complete':
                stop('interrupted', 'EvaluationStopped', worker)
            elif not shutting_down or worker in assigned:
                stop('failed', 'WorkerExited', worker)
            phases[worker] = 'closed'
            return
        if status == 'ready' and index is None and phases[worker] == 'starting':
            phases[worker] = 'idle'
            return
        if status in ('failed', 'interrupted'):
            stop(status, value if type(value) is str else 'WorkerFailed', worker)
            phases[worker] = 'closed'
            return
        if (status != 'complete' or type(index) is not int or assigned.get(worker) != index
                or type(value) is not dict or value.get('status') not in ('terminated', 'truncated')
                or value.get('trajectory') != rows[index]['episode_id']+'.trajectory.jsonl'):
            stop('failed', 'InvalidWorkerResult', worker)
            return
        rows[index].update(value)
        assigned.pop(worker)
        phases[worker] = 'idle'
        completed += 1

    try:
        for worker in range(min(workers, len(rows))):
            if cancel is not None and cancel.is_set():
                stop('interrupted', 'RunCancelled')
                break
            parent, child = context.Pipe()
            process = context.Process(target=_worker, args=(checkpoints, policies, source,
                str(output), str(private), stopped, child), name='sts-evaluation-worker')
            active[worker] = (process, parent, None)
            phases[worker] = 'starting'
            deadlines[worker] = time.monotonic()+STARTUP_SECONDS
            try:
                with _defer_start_signals():
                    process.start()
            finally:
                child.close()
        while completed < len(rows) and not stopped.is_set():
            if cancel is not None and cancel.is_set():
                stop('interrupted', 'RunCancelled')
                break
            for worker, (process, connection, _) in active.items():
                if connection.poll():
                    receive(worker)
                elif not process.is_alive():
                    stop('failed', 'WorkerExited', worker)
                elif phases[worker] != 'idle' and time.monotonic() >= deadlines[worker]:
                    stop('failed', 'WorkerDeadlineExceeded', worker)
                if stopped.is_set():
                    break
            if stopped.is_set():
                break
            for worker, (_, connection, _) in active.items():
                if phases[worker] != 'idle' or scheduled == len(rows):
                    continue
                if cancel is not None and cancel.is_set():
                    stop('interrupted', 'RunCancelled')
                    break
                index = scheduled
                assigned[worker] = index
                phases[worker] = 'busy'
                # Budget applies to gameplay. Allow a separate bounded margin
                # for canonical replay analysis and OS scheduling afterwards.
                deadlines[worker] = time.monotonic()+2*configs[index].time_limit_seconds+REPORT_GRACE_SECONDS
                connection.send((index, configs[index], rows[index]['episode_id'], rows[index]['policy']))
                scheduled += 1
            if completed < len(rows) and not stopped.is_set():
                time.sleep(.01)
    except (Exception, KeyboardInterrupt) as error:
        stop('interrupted' if isinstance(error, (RunCancelled, KeyboardInterrupt)) else 'failed',
             type(error).__name__)
    finally:
        stopped.set()
        # Drain completed acknowledgements while siblings cooperatively stop.
        # An acknowledged game is retained even if another game failed first.
        until = time.monotonic()+3.
        try:
            while time.monotonic() < until:
                alive = False
                for worker, (process, connection, _) in active.items():
                    if phases[worker] != 'closed' and connection.poll():
                        receive(worker, shutting_down=True)
                    alive |= process.is_alive()
                if not alive:
                    break
                time.sleep(.01)
            for worker, (process, connection, _) in active.items():
                if phases[worker] != 'closed' and connection.poll():
                    receive(worker, shutting_down=True)
                if process.is_alive():
                    if result['status'] == 'complete':
                        stop('failed', 'WorkerCleanupForced', worker)
                    elif worker in assigned:
                        stop('interrupted', 'EvaluationStopped', worker)
                    result['forced_worker_terminations'] = result.get('forced_worker_terminations', 0)+1
                    process.terminate()
                elif process.pid is not None and process.exitcode != 0:
                    stop('failed', 'WorkerExited', worker)
        except (Exception, KeyboardInterrupt) as error:
            stop('interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', type(error).__name__)
        finally:
            try:
                _cleanup(active, stopped)
            except Exception:
                result.update(status='failed', failure='WorkerCleanupFailed')
        for index in assigned.values():
            rows[index].update(status='interrupted', failure='EvaluationStopped')
    return result
