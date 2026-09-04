"""Small honest local throughput measurements for headless rollout collection."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from game.training.headless_rollout import (
    HeadlessBatchConfig,
    HeadlessBatchResult,
    run_headless_batch,
)


@dataclass(frozen=True, slots=True)
class HeadlessBenchmarkConfig:
    """Bounded benchmark conditions; this is a measurement, not a promise."""

    batch: HeadlessBatchConfig
    repetitions: int = 1
    process_safe: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.batch, HeadlessBatchConfig):
            raise TypeError("batch must be a HeadlessBatchConfig.")
        if (
            not isinstance(self.repetitions, int)
            or isinstance(self.repetitions, bool)
            or not 1 <= self.repetitions <= 32
        ):
            raise ValueError("repetitions must be between one and 32.")


@dataclass(frozen=True, slots=True)
class HeadlessBenchmarkResult:
    conditions: HeadlessBenchmarkConfig
    elapsed_seconds: float
    episode_count: int
    transition_count: int
    episodes_per_second: float
    transitions_per_second: float
    batches: tuple[HeadlessBatchResult, ...]

    @property
    def interrupted(self) -> bool:
        return any(batch.interrupted for batch in self.batches)

    @property
    def attempted_repetitions(self) -> int:
        return len(self.batches)

    @property
    def completed_repetitions(self) -> int:
        return sum(not batch.interrupted for batch in self.batches)

    @property
    def unstarted_repetitions(self) -> int:
        return self.conditions.repetitions - self.attempted_repetitions


def benchmark_headless_rollouts(config: HeadlessBenchmarkConfig) -> HeadlessBenchmarkResult:
    """Measure exactly the supplied local workload with a monotonic clock."""

    if not isinstance(config, HeadlessBenchmarkConfig):
        raise TypeError("config must be a HeadlessBenchmarkConfig.")
    started = perf_counter()
    collected = []
    for _ in range(config.repetitions):
        batch = run_headless_batch(config.batch, process_safe=config.process_safe)
        collected.append(batch)
        if batch.interrupted:
            break
    batches = tuple(collected)
    elapsed = perf_counter() - started
    episodes = sum(len(batch.results) for batch in batches)
    transitions = sum(batch.transition_count for batch in batches)
    denominator = max(elapsed, 1e-12)
    return HeadlessBenchmarkResult(
        config, elapsed, episodes, transitions,
        episodes / denominator, transitions / denominator, batches,
    )
