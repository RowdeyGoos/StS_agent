"""Tests for bounded, condition-carrying local rollout measurements."""

from __future__ import annotations

from game.backends.headless.reduced_run_backend import HeadlessRunConfig
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.training.headless_benchmark import (
    HeadlessBenchmarkConfig,
    benchmark_headless_rollouts,
)
from game.training.headless_rollout import HeadlessBatchConfig, HeadlessRolloutConfig
import game.training.headless_rollout as rollout_module


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


def test_benchmark_stops_repetitions_after_a_collector_interruption(monkeypatch) -> None:
    original_entry = rollout_module._run_batch_entry
    calls = []

    def interrupt_second_episode(config):
        calls.append(config.trajectory_id)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return original_entry(config)

    monkeypatch.setattr(rollout_module, "_run_batch_entry", interrupt_second_episode)
    episodes = tuple(
        HeadlessRolloutConfig(
            f"benchmark-partial-{index}",
            HeadlessRunConfig("simple__starter", CONTENT_FINGERPRINT, index, {}),
            transition_budget=1,
        )
        for index in range(2)
    )
    conditions = HeadlessBenchmarkConfig(HeadlessBatchConfig(episodes), repetitions=3)
    result = benchmark_headless_rollouts(conditions)

    assert len(calls) == 2
    assert result.conditions == conditions
    assert len(result.batches) == 1
    assert result.batches[0].interrupted is True
    assert result.episode_count == 1
    assert result.transition_count == 1
    assert result.interrupted is True
    assert result.attempted_repetitions == 1
    assert result.completed_repetitions == 0
    assert result.unstarted_repetitions == 2
