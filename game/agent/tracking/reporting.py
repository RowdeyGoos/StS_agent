"""Shared opt-in reporting boundary for trainers and evaluators."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import time
import sys
import warnings


@dataclass(frozen=True)
class TrackingConfig:
    directory: str
    experiment: str = 'StS experiments'
    name: str | None = None
    inspector_url: str | None = None


_session = ContextVar('sts_tracking_session', default=None)


@contextmanager
def tracking_session(config: TrackingConfig | None):
    """Scope a writer to the caller; spawn workers inherit no mutable writer."""
    if config is None:
        yield
        return
    from .store import TrackingStore
    with TrackingStore(config.directory, experiment=config.experiment, name=config.name,
                       inspector_url=config.inspector_url) as store:
        token = _session.set(store)
        try:
            yield store
        finally:
            _session.reset(token)


def report_progress(path, report):
    """Tracking failure never turns a successful game/update into a failed one.

    Canonical report/checkpoint publication is owned by the trainer. A failed
    dashboard write is visible as a warning and recoverable with `track import`.
    """
    store = _session.get()
    if store is None:
        return
    # Imitation updates can take milliseconds. Flush periodically and at every
    # terminal report, retaining every intervening metric in the report snapshot.
    now = time.monotonic()
    previous = getattr(store, '_last_flush', {})
    key = str(path)
    if report.get('status') == 'running' and now-previous.get(key, -float('inf')) < 5:
        return
    previous[key] = now
    store._last_flush = previous
    try:
        store.import_report(path, report)
    except Exception as error:
        message = ('Experiment tracking failed ('+type(error).__name__+'): '+str(error)+
                   '. Canonical outputs are retained; retry with sts-agent-track import.')
        try:
            warnings.warn(message, RuntimeWarning)
        except Exception:
            # Warning-as-error settings or a closed logging stream must not
            # escape into the training/game exception boundary either.
            try:
                print(message, file=sys.stderr)
            except Exception:
                pass
