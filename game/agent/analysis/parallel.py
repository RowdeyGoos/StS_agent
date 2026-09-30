"""Bounded episode export workers; the parent alone publishes the report."""
import multiprocessing
import queue
import signal
import threading

from game.agent.workers import _cleanup, _defer_start_signals


def _worker(function, stopped, connection):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        while not stopped.is_set():
            if not connection.poll(.05):
                continue
            job = connection.recv()
            try:
                result = function(job)
                connection.send(('complete', result))
                del job, result
            except Exception as error:
                # Only public artifact processing occurs here. Retain actionable
                # validation errors without transporting arbitrary exceptions.
                connection.send(('invalid' if isinstance(error, ValueError) else 'failed',
                                 f'{type(error).__name__}: {error}'))
                return
    finally:
        connection.close()


def _exchange(index, connection, inbox, outbox):
    # Large overlays/results must not block the parent's interruption handling.
    while True:
        job = inbox.get()
        if job is None:
            return
        try:
            connection.send(job)
            result = connection.recv()
        except (EOFError, OSError):
            outbox.put((index, ('failed', 'Analysis worker exited without a result')))
            return
        outbox.put((index, result))
        del job, result


def map_episodes(function, jobs, workers):
    """Yield indexed results as ready, with at most one pending job per worker.

    Callers must close this generator on failure or cancellation. No failed job
    is retried. Reuse the runner's spawn/interrupt/forced-cleanup lifecycle.
    """
    context = multiprocessing.get_context('spawn')
    stopped = context.Event()
    active, channels, assigned = {}, {}, {}
    outbox = queue.Queue()
    remaining = iter(enumerate(jobs))
    try:
        for worker in range(min(workers, len(jobs))):
            parent, child = context.Pipe()
            process = context.Process(target=_worker, args=(function, stopped, child), name='sts-analysis-worker')
            active[worker] = (process, parent, None)
            try:
                with _defer_start_signals():
                    process.start()
            finally:
                child.close()
            inbox = queue.Queue()
            thread = threading.Thread(target=_exchange, args=(worker, parent, inbox, outbox),
                                      name='sts-analysis-transfer', daemon=True)
            channels[worker] = (inbox, thread)
            with _defer_start_signals():
                thread.start()
            index, job = next(remaining)
            assigned[worker] = index
            inbox.put(job)
        while assigned:
            try:
                worker, (status, result) = outbox.get(timeout=.05)
            except queue.Empty:
                if any(not process.is_alive() for process, _, _ in active.values()):
                    raise RuntimeError('Analysis worker exited without a result')
                continue
            if status != 'complete':
                raise (ValueError if status == 'invalid' else RuntimeError)(result)
            index = assigned.pop(worker)
            yield index, result
            next_job = next(remaining, None)
            if next_job is not None:
                assigned[worker] = next_job[0]
                channels[worker][0].put(next_job[1])
    finally:
        stopped.set()
        for inbox, _ in channels.values():
            inbox.put(None)
        try:
            _cleanup(active, stopped)
        finally:
            for _, thread in channels.values():
                if thread.ident is not None:
                    thread.join(1.)
        if any(thread.is_alive() for _, thread in channels.values()):
            raise RuntimeError('Analysis transfer cleanup failed')
