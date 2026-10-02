"""CPU-aware command defaults from the local worker and learner benchmarks.

Keep this module free of optional training dependencies. Library callers retain
their explicit settings; command owners resolve these defaults before dispatch.
"""
import os

GAME_WORKER_LIMIT = 16
ARTIFACT_WORKER_LIMIT = 8


def available_cpus():
    """Respect process CPU availability when Python exposes it; always allow one."""
    detect = getattr(os, 'process_cpu_count', os.cpu_count)
    try:
        return max(1, detect() or 1)
    except (OSError, NotImplementedError):
        return 1


def game_workers():
    return min(GAME_WORKER_LIMIT, available_cpus())


def artifact_workers():
    return min(ARTIFACT_WORKER_LIMIT, available_cpus())


def ppo_update_threads():
    cpus = available_cpus()
    return 4 if cpus >= 4 else 2 if cpus >= 2 else 1
