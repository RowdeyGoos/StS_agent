"""Tests for bounded, condition-carrying local rollout measurements."""

from __future__ import annotations

from game.backends.headless.reduced_run_backend import HeadlessRunConfig
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.training.headless_benchmark import (
    HeadlessBenchmarkConfig,
    benchmark_headless_rollouts,
)
from game.training.headless_rollout import HeadlessBatchConfig, HeadlessRolloutConfig


def test_tiny_benchmark_reports_its_actual_local_conditions_and_rates() -> None:
    episode = HeadlessRolloutConfig(
        "benchmark-000",
        HeadlessRunConfig("simple__starter", CONTENT_FINGERPRINT, 7, {}),
        transition_budget=2,
    )
    conditions = HeadlessBenchmarkConfig(HeadlessBatchConfig((episode,)), repetitions=1)

    result = benchmark_headless_rollouts(conditions)

    assert result.conditions == conditions
    assert result.episode_count == 1
    assert result.transition_count == 2
    assert result.elapsed_seconds >= 0.0
    assert result.episodes_per_second >= 0.0
    assert result.transitions_per_second >= 0.0
