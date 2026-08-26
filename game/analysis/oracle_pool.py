"""Process helpers for independent brute-force continuation searches."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import get_context

from ..simulation.actions import CombatAction
from .bruteforce import clone_combat_env
from ..simulation.core import CombatEnv


@dataclass(frozen=True, slots=True)
class OracleSearchTask:
    """One process-safe committed-action continuation request."""

    env: CombatEnv
    action: CombatAction
    max_steps: int
    max_nodes: int
    time_limit_seconds: float | None


def create_oracle_process_pool(workers: int) -> ProcessPoolExecutor:
    """Create a macOS-safe spawned pool for coarse oracle searches."""
    if workers <= 1:
        raise ValueError("Oracle process pools require at least two workers.")
    return ProcessPoolExecutor(
        max_workers=workers,
        mp_context=get_context("spawn"),
    )


def prepare_env_for_oracle_process(env: CombatEnv) -> CombatEnv:
    """Clone an active episode while removing unused unpickleable factories."""
    prepared_env = clone_combat_env(env)
    # Search never calls reset(), so episode factories are irrelevant. Lambdas
    # are common here and cannot be serialized by the spawn start method.
    prepared_env.deck_factory = None  # type: ignore[assignment]
    prepared_env.enemy_factory = None  # type: ignore[assignment]
    prepared_env.encounter_factory = None
    return prepared_env


def run_oracle_search_task(task: OracleSearchTask):
    """Run one task in a worker without importing analysis code at module load."""
    from .oracle import evaluate_committed_action

    return evaluate_committed_action(
        task.env,
        task.action,
        max_steps=task.max_steps,
        max_nodes=task.max_nodes,
        time_limit_seconds=task.time_limit_seconds,
    )
