"""Consumer-level tests for bounded headless rollout collection."""

from __future__ import annotations

from dataclasses import replace

from game.backends.headless.reduced_run_backend import HeadlessRunConfig
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import DecisionStatus
from game.data.headless_trajectory import validate_trajectory
from game.runtime.episode_runner import EpisodeResult, EpisodeStopReason
from game.training.headless_rollout import (
    ChooserKind,
    CollectorWorkerConfig,
    HeadlessBatchConfig,
    HeadlessRolloutConfig,
    RolloutStopReason,
    _stop_reason,
    run_headless_batch,
    run_headless_rollout,
)
from tests.runtime.test_episode_runner import _decision


def _config(
    trajectory_id: str,
    *,
    game_seed: int = 7,
    policy_seed: int = 11,
    transition_budget: int = 300,
    settings: dict | None = None,
) -> HeadlessRolloutConfig:
    return HeadlessRolloutConfig(
        trajectory_id=trajectory_id,
        run_config=HeadlessRunConfig(
            scenario_id="simple__starter",
            content_fingerprint=CONTENT_FINGERPRINT,
            game_seed=game_seed,
            backend_settings={} if settings is None else settings,
        ),
        transition_budget=transition_budget,
        chooser_kind=ChooserKind.STRUCTURAL_HEURISTIC,
        policy_seed=policy_seed,
    )


def test_multiple_seeded_episodes_are_deterministic_and_preserve_evidence() -> None:
    left = run_headless_rollout(_config("rollout-left"))
    right = run_headless_rollout(_config("rollout-right"))

    assert left.stop_reason is RolloutStopReason.ROUTE_COMPLETE
    assert right.stop_reason is RolloutStopReason.ROUTE_COMPLETE
    assert left.transition_count == right.transition_count
    assert left.final_decision_json == right.final_decision_json
    assert left.initial_snapshot_sha256 == right.initial_snapshot_sha256
    assert left.final_snapshot_sha256 == right.final_snapshot_sha256
    assert left.trajectory is not None and right.trajectory is not None
    assert left.trajectory.policy_replay_jsonl == right.trajectory.policy_replay_jsonl
    assert {item.label.value for item in left.evidence} == {
        "combat_v0", "structural_fixture"
    }


def test_replay_and_hindsight_sidecars_are_separate_and_independently_bound(tmp_path) -> None:
    result = run_headless_rollout(_config("rollout-sidecars"))
    assert result.trajectory is not None
    trajectory = result.trajectory
    validated = validate_trajectory(
        trajectory.manifest_json,
        trajectory.policy_replay_jsonl,
        trajectory.hindsight_target_jsonl,
        trajectory.synthetic_audit_jsonl,
        expected_manifest_sha256=trajectory.manifest_sha256,
    )
    assert validated == trajectory
    paths = trajectory.write_to(tmp_path)
    assert paths.policy_replay.exists()
    assert paths.hindsight_target.exists()
    assert paths.policy_replay != paths.hindsight_target
    assert b"terminal_outcome" not in trajectory.policy_replay_jsonl
    assert b"terminal_outcome" in trajectory.hindsight_target_jsonl


def test_game_policy_and_collector_seeds_are_independent_with_fixed_actions() -> None:
    first = _config("rollout-seed-a", policy_seed=1)
    second = replace(first, trajectory_id="rollout-seed-b", policy_seed=999)
    left = run_headless_batch(
        HeadlessBatchConfig((first,), CollectorWorkerConfig(worker_count=1, worker_seed=1))
    ).results[0]
    right = run_headless_batch(
        HeadlessBatchConfig((second,), CollectorWorkerConfig(worker_count=1, worker_seed=999))
    ).results[0]

    assert left.final_decision_json == right.final_decision_json
    assert left.initial_snapshot_sha256 == right.initial_snapshot_sha256
    assert left.final_snapshot_sha256 == right.final_snapshot_sha256
    assert left.trajectory is not None and right.trajectory is not None
    assert left.trajectory.policy_replay_jsonl == right.trajectory.policy_replay_jsonl


def test_spawned_workers_match_sequential_panel_without_seed_coupling() -> None:
    panel = HeadlessBatchConfig(
        (_config("rollout-spawn-a", game_seed=7), _config("rollout-spawn-b", game_seed=8)),
        CollectorWorkerConfig(worker_count=2, worker_seed=17),
    )
    sequential = run_headless_batch(panel)
    spawned = run_headless_batch(panel, process_safe=True)

    assert spawned.process_safe is True
    assert [item.final_decision_json for item in spawned.results] == [
        item.final_decision_json for item in sequential.results
    ]
    assert [item.final_snapshot_sha256 for item in spawned.results] == [
        item.final_snapshot_sha256 for item in sequential.results
    ]


def test_explicit_route_defeat_budget_and_unsupported_stop_reasons() -> None:
    route = run_headless_rollout(_config("rollout-route"))
    defeat = run_headless_rollout(_config("rollout-defeat", settings={"initial_hp": 1}))
    budget = run_headless_rollout(_config("rollout-budget", transition_budget=1))

    assert route.stop_reason is RolloutStopReason.ROUTE_COMPLETE
    assert defeat.stop_reason is RolloutStopReason.DEFEAT
    assert budget.stop_reason is RolloutStopReason.BUDGET_EXHAUSTED
    assert budget.trajectory is not None
    assert budget.trajectory.manifest.completion.value == "interrupted"
    assert _stop_reason(
        EpisodeResult(EpisodeStopReason.UNSUPPORTED, _decision(0, DecisionStatus.UNSUPPORTED), 0),
        object(),
    ) is RolloutStopReason.UNSUPPORTED
