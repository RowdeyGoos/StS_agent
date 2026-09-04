"""Maintained twelve-case serial/spawn panel; synthetic consistency only."""

from collections import Counter
from multiprocessing import active_children
import random
import signal

import pytest

from game.backends.headless.reduced_run_backend import HeadlessRunConfig
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import DecisionState, DecisionStatus
from game.data.headless_trajectory import (
    decode_hindsight_targets,
    decode_policy_replay,
    decode_synthetic_audit,
    validate_trajectory,
)
from game.training.headless_rollout import (
    ChooserKind,
    CollectorWorkerConfig,
    HeadlessBatchConfig,
    HeadlessRolloutConfig,
    RolloutStopReason,
    run_headless_batch,
)


def _panel() -> tuple[HeadlessRolloutConfig, ...]:
    """Keep both scenarios, all choosers, multiple seeds and four controls."""
    episodes = []
    for scenario in ("simple__starter", "nibbit__starter"):
        for chooser, policy_seed in zip(ChooserKind, (5, 11, 19)):
            episodes.append(HeadlessRolloutConfig(
                f"matched-{scenario}-{chooser.value}",
                HeadlessRunConfig(scenario, CONTENT_FINGERPRINT, 7, {}),
                300, chooser, policy_seed,
            ))
        episodes.append(HeadlessRolloutConfig(
            f"matched-{scenario}-seed-8",
            HeadlessRunConfig(scenario, CONTENT_FINGERPRINT, 8, {}),
            300, ChooserKind.STRUCTURAL_HEURISTIC, 11,
        ))
    for name, budget, settings, chooser, policy_seed in (
        ("zero", 0, {}, ChooserKind.STRUCTURAL_HEURISTIC, 11),
        ("one", 1, {}, ChooserKind.STRUCTURAL_HEURISTIC, 11),
        ("defeat", 300, {"initial_hp": 1}, ChooserKind.STRUCTURAL_HEURISTIC, 11),
        ("unsupported", 300, {
            "event_id": "cool_spring", "combat_settings": {"enemy_max_hp": 1},
        }, ChooserKind.SEEDED_RANDOM, 5),
    ):
        episodes.append(HeadlessRolloutConfig(
            f"matched-{name}",
            HeadlessRunConfig("simple__starter", CONTENT_FINGERPRINT, 7, settings),
            budget, chooser, policy_seed,
        ))
    assert len(episodes) == 12
    return tuple(episodes)


def test_twelve_complete_results_match_across_modes_and_collector_seeds() -> None:
    panel = _panel()
    global_rng = random.getstate()
    sigint_handler = signal.getsignal(signal.SIGINT)
    prior_children = {child.pid for child in active_children()}
    baseline = None
    # Full factorial: mode and scheduling seed change independently.
    for process_safe in (False, True):
        for collector_seed in (17, 999):
            batch = run_headless_batch(
                HeadlessBatchConfig(panel, CollectorWorkerConfig(2, collector_seed)),
                process_safe=process_safe,
            )
            assert batch.process_safe is process_safe
            assert batch.worker == CollectorWorkerConfig(2, collector_seed)
            assert not batch.interrupted
            assert batch.pending_trajectory_ids == ()
            assert tuple(result.config for result in batch.results) == panel
            assert {child.pid for child in active_children()} == prior_children
            assert random.getstate() == global_rng
            assert signal.getsignal(signal.SIGINT) == sigint_handler
            if baseline is None:
                baseline = batch.results
            for expected, actual in zip(baseline, batch.results):
                # Dataclass equality includes every result field, the complete
                # manifest, and all three byte streams. No timing exclusions.
                if actual != expected:
                    pytest.fail(
                        f"{actual.config.trajectory_id}: complete result differs; "
                        f"spawn={process_safe}, collector_seed={collector_seed}",
                        pytrace=False,
                    )
                assert actual.failure is None
                assert actual.transition_count <= actual.config.transition_budget <= 300
                assert actual.initial_snapshot_sha256 is not None
                assert actual.final_snapshot_sha256 is not None
                trajectory = actual.trajectory
                assert trajectory is not None
                validated = validate_trajectory(
                    trajectory.manifest_json,
                    trajectory.policy_replay_jsonl,
                    trajectory.hindsight_target_jsonl,
                    trajectory.synthetic_audit_jsonl,
                    expected_manifest_sha256=trajectory.manifest_sha256,
                )
                assert validated == trajectory
                policy = decode_policy_replay(trajectory.policy_replay_jsonl)
                targets = decode_hindsight_targets(trajectory.hindsight_target_jsonl)
                audit = decode_synthetic_audit(trajectory.synthetic_audit_jsonl)
                assert len(policy) == len(audit) == actual.transition_count + 1
                assert len(targets) == 1
                assert sum(record.chosen_action is not None for record in policy) == actual.transition_count
                assert all(
                    record.chosen_action is None or record.chosen_action in record.candidates
                    for record in policy
                )
                assert {item.label.value for item in actual.evidence} == {
                    "combat_v0", "structural_fixture",
                }
                final = DecisionState.from_json(actual.final_decision_json)
                if actual.stop_reason in {RolloutStopReason.ROUTE_COMPLETE, RolloutStopReason.DEFEAT}:
                    assert final.status is DecisionStatus.TERMINAL
                    assert final.candidates == policy[-1].candidates == ()
                elif actual.stop_reason is RolloutStopReason.UNSUPPORTED:
                    assert final.status is DecisionStatus.UNSUPPORTED
                    assert final.candidates == policy[-1].candidates == ()
                else:
                    assert final.status is DecisionStatus.ACTIONABLE
                if actual.stop_reason in {RolloutStopReason.BUDGET_EXHAUSTED, RolloutStopReason.UNSUPPORTED}:
                    assert targets[0].terminal_outcome is None
            assert Counter(result.stop_reason for result in batch.results) == {
                RolloutStopReason.ROUTE_COMPLETE: 8,
                RolloutStopReason.BUDGET_EXHAUSTED: 2,
                RolloutStopReason.DEFEAT: 1,
                RolloutStopReason.UNSUPPORTED: 1,
            }
            controls = {result.config.trajectory_id: result for result in batch.results}
            assert controls["matched-zero"].transition_count == 0
            assert controls["matched-one"].transition_count == 1
            zero = controls["matched-zero"]
            assert zero.initial_snapshot_sha256 == zero.final_snapshot_sha256
