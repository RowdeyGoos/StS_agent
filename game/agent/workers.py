"""Small, bounded spawn workers with cooperative cancellation and forced cleanup."""
from dataclasses import dataclass, replace
from contextlib import contextmanager
import multiprocessing
import signal
import threading
import time
import uuid

from game.agent.runner import RunCancelled, RunFailure, prepare_directories, run_episode


@dataclass(frozen=True, slots=True)
class BatchResult:
    episodes: tuple
    elapsed_seconds: float


@contextmanager
def _defer_start_signals():
    """Let Process.start attach its OS handle before delivering an interruption.

    CPython can spawn a child before assigning Process._popen. An exception in
    that interval otherwise leaves a real child invisible to parent cleanup.
    Non-main threads do not receive Python signal-handler interruptions.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    pending = []
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for sig in previous:
            signal.signal(sig, lambda signum, frame: pending.append((signum, frame)))
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        for sig, frame in pending:
            handler = previous[sig]
            if callable(handler):
                handler(sig, frame)
            elif handler == signal.SIG_DFL:
                raise KeyboardInterrupt


def _worker(config, output, audit, episode_id, stopped, sender, checkpoint=None):
    # Ctrl-C is handled once by the parent, which requests an orderly stop.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        kwargs = {}
        if checkpoint is not None:
            import torch
            from game.agent.training.checkpoint import load_policy
            from game.agent.provenance import implementation
            torch.set_num_threads(1)
            task = checkpoint[2]
            learned = load_policy(checkpoint[0], expected_sha256=checkpoint[1], task=task)
            kwargs = ({'policy':learned, 'policy_identity':learned.identity} if task == 'full_run' else
                      {'combat_policy': learned,
                       'policy_identity': 'hybrid_v1:' + checkpoint[1] + ':' + implementation().policy})
        result = run_episode(config, output_dir=output, audit_dir=audit,
                             episode_id=episode_id, cancel=stopped, **kwargs)
        sender.send(('complete', result))
    except RunCancelled:
        sender.send(('cancelled', None))
    except BaseException as error:
        # Exception text can contain private game data. Public operational
        # summaries contain only the bounded error category/type.
        sender.send(('failed', type(error).__name__))
    finally:
        sender.close()


def _cleanup(active, stopped):
    stopped.set()
    deadline = time.monotonic() + 3.0
    for process, receiver, _ in active.values():
        if process.pid is not None:
            process.join(max(0.0, deadline - time.monotonic()))
    for process, _, _ in active.values():
        if process.is_alive():
            process.terminate()
    deadline = time.monotonic() + 1.0
    for process, _, _ in active.values():
        if process.pid is not None:
            process.join(max(0.0, deadline - time.monotonic()))
        if process.is_alive():
            process.kill()
    for process, receiver, _ in active.values():
        if process.pid is not None:
            process.join(1.0)
        receiver.close()
        if process.is_alive():
            raise RunFailure('Worker cleanup failed')
        process.close()


def run_batch(config, *, output_dir, audit_dir, episodes=1, workers=1, cancel=None, combat_checkpoint=None, run_checkpoint=None):
    """Run seeds base+i in fresh processes; result order is independent of scheduling.

    Each job has its own engine, policy state, RNG, files, and opaque episode ID.
    A failed job stops the batch without retries. Completed artifacts are retained;
    interrupted files remain .partial. The parent enforces a hard deadline five
    seconds beyond each configured episode budget, including process startup.
    """
    config.validate()
    if type(episodes) is not int or not 1 <= episodes <= 10000:
        raise ValueError('episodes must be between 1 and 10000')
    if type(workers) is not int or not 1 <= workers <= 32:
        raise ValueError('workers must be between 1 and 32')
    checkpoint = None
    if combat_checkpoint is not None and run_checkpoint is not None:
        raise ValueError('Choose either a full-run policy or a combat hybrid')
    if combat_checkpoint is not None or run_checkpoint is not None:
        from pathlib import Path
        from game.agent.training.checkpoint import load_policy
        task = 'full_run' if run_checkpoint is not None else 'combat'
        path = str(Path(run_checkpoint if run_checkpoint is not None else combat_checkpoint).resolve())
        frozen = load_policy(path, task=task)
        checkpoint = (path, frozen.identity.split(':')[-1], task)
    output, audit = prepare_directories(output_dir, audit_dir)
    context = multiprocessing.get_context('spawn')
    stopped = context.Event()
    active, results = {}, {}
    scheduled = 0
    started = time.monotonic()
    try:
        while len(results) < episodes:
            if cancel is not None and cancel.is_set():
                raise RunCancelled('Batch cancelled; unfinished recordings remain partial')
            while scheduled < episodes and len(active) < workers:
                if cancel is not None and cancel.is_set():
                    raise RunCancelled('Batch cancelled before starting its next worker')
                receiver, sender = context.Pipe(duplex=False)
                args = (
                    replace(config, seed=config.seed + scheduled), str(output), str(audit),
                    uuid.uuid4().hex, stopped, sender)
                if checkpoint is not None:
                    args += (checkpoint,)
                process = context.Process(target=_worker, args=args, name='sts-agent-worker')
                # Register before start so interruption cannot orphan a child
                # between successful spawn and registration in the parent.
                active[scheduled] = (process, receiver, time.monotonic())
                try:
                    with _defer_start_signals():
                        process.start()
                finally:
                    sender.close()
                scheduled += 1
            for index, (process, receiver, launched) in list(active.items()):
                if receiver.poll():
                    try:
                        status, value = receiver.recv()
                    except EOFError as error:
                        raise RunFailure('Worker exited without a result') from error
                    if status != 'complete':
                        raise RunFailure('Worker stopped: ' + (value if status == 'failed' else status))
                    process.join(1.0)
                    if process.is_alive() or process.exitcode != 0:
                        raise RunFailure('Worker did not close cleanly')
                    results[index] = value
                    del active[index]
                    receiver.close()
                    process.close()
                elif not process.is_alive():
                    raise RunFailure('Worker exited without a result')
                elif time.monotonic() - launched > config.time_limit_seconds + 5.0:
                    raise RunFailure('Worker exceeded its hard deadline')
            if active:
                time.sleep(0.01)
    finally:
        _cleanup(active, stopped)
    return BatchResult(tuple(results[index] for index in range(episodes)), time.monotonic() - started)
