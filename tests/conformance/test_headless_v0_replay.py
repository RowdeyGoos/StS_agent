"""Replay, snapshot, runner, and trajectory conformance for headless_v0."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

import pytest

from game.backends.headless.combat_v0_backend import CombatV0Backend
from game.backends.headless.fixture_backend import FixtureBackend
from game.backends.headless.reduced_run_backend import (
    HeadlessRunConfig,
    ReducedRunBackend,
    create_reduced_run_backend,
)
from game.backends.headless.scenarios import scenario_from_id
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import (
    ActionRequest,
    CandidateKind,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    HeadlessBinding,
    PolicyView,
    TransitionResult,
)
from game.data.headless_trajectory import (
    StreamRole,
    TrajectoryCompletion,
    TrajectoryRecorder,
    decode_hindsight_targets,
    decode_policy_replay,
    decode_synthetic_audit,
    policy_view_for,
    validate_trajectory,
)
from game.runtime.episode_runner import EpisodeStopReason, run_episode


_ATTACKS = frozenset({"bash", "body_slam", "iron_wave", "pommel_strike", "strike"})


def _config(**settings: Any) -> HeadlessRunConfig:
    return HeadlessRunConfig(
        scenario_id="simple__starter",
        content_fingerprint=CONTENT_FINGERPRINT,
        game_seed=17,
        backend_settings=settings,
    )


def _request(decision: DecisionState, candidate_id: str) -> ActionRequest:
    return ActionRequest(HeadlessBinding.for_candidate(decision, candidate_id))


def _choose(view: PolicyView, *, room: str = "rest") -> str:
    if view.phase is DecisionPhase.COMBAT:
        definitions = {
            card["card_ref"]: card["card_definition_id"]
            for card in view.observation.data["hand"]
        }
        attacks = [
            item
            for item in view.candidates
            if item.kind is CandidateKind.COMBAT_PLAY_CARD
            and definitions[item.card_ref] in _ATTACKS
        ]
        if attacks:
            return attacks[0].candidate_id
        return next(
            item.candidate_id
            for item in view.candidates
            if item.kind is CandidateKind.COMBAT_END_TURN
        )
    if view.phase is DecisionPhase.REWARD:
        for kind in (
            CandidateKind.REWARD_CLAIM_GOLD,
            CandidateKind.REWARD_OPEN_CARD_REWARD,
            CandidateKind.REWARD_CHOOSE_CARD,
            CandidateKind.REWARD_SKIP_CARD,
            CandidateKind.REWARD_PROCEED,
        ):
            matching = [item for item in view.candidates if item.kind is kind]
            if matching:
                return matching[0].candidate_id
    if view.phase is DecisionPhase.MAP:
        node_kinds = {
            node["node_ref"]: node["kind"] for node in view.observation.data["nodes"]
        }
        preferred = [
            item for item in view.candidates if node_kinds[item.node_ref] == room
        ]
        return (preferred[0] if preferred else view.candidates[0]).candidate_id
    for kind in (
        CandidateKind.ROOM_REST_HEAL,
        CandidateKind.ROOM_EVENT_OPTION,
        CandidateKind.ROOM_PROCEED,
    ):
        matching = [item for item in view.candidates if item.kind is kind]
        if matching:
            return matching[0].candidate_id
    raise AssertionError("chooser received an unsupported actionable boundary")


def _trace(backend: object, configuration: object, *, room: str = "rest") -> tuple[str, ...]:
    decision = backend.reset(configuration)  # type: ignore[attr-defined]
    trace = [decision.to_json()]
    for _ in range(100):
        if decision.status is not DecisionStatus.ACTIONABLE:
            return tuple(trace)
        candidate_id = _choose(decision.policy_view(), room=room)
        transition = backend.apply(_request(decision, candidate_id))  # type: ignore[attr-defined]
        assert transition.result is TransitionResult.ACCEPTED
        trace.append(transition.to_json())
        decision = transition.next_decision
    raise AssertionError("episode exceeded bounded replay budget")


@pytest.mark.parametrize(
    "fixture_id", ("combat", "reward", "map", "rest", "event", "unsupported")
)
def test_fixture_playback_reset_and_replay_are_byte_deterministic(fixture_id: str) -> None:
    first = _trace(FixtureBackend(), fixture_id)
    second = _trace(FixtureBackend(), {"fixture_id": fixture_id})
    assert first == second


def test_combat_and_reduced_reset_replay_are_byte_deterministic() -> None:
    scenario = scenario_from_id("simple__starter", seed=23, enemy_max_hp=12)
    assert _trace(CombatV0Backend(), scenario) == _trace(CombatV0Backend(), scenario)

    config = _config(initial_hp=60, combat_settings={"enemy_max_hp": 6})
    assert _trace(ReducedRunBackend(), config) == _trace(ReducedRunBackend(), config)
    assert _trace(ReducedRunBackend(), config, room="event") == _trace(
        ReducedRunBackend(), config, room="event"
    )


def test_fixture_snapshots_restore_every_recorded_cursor_exactly() -> None:
    for fixture_id in ("combat", "reward", "map", "rest", "event", "unsupported"):
        backend = FixtureBackend()
        decision = backend.reset(fixture_id)
        boundaries: list[tuple[object, DecisionState, str]] = []
        while decision.status is DecisionStatus.ACTIONABLE:
            candidate_id = decision.candidates[0].candidate_id
            boundaries.append((backend.snapshot(), decision, candidate_id))
            decision = backend.apply(_request(decision, candidate_id)).next_decision

        for snapshot, expected, candidate_id in boundaries:
            assert backend.restore(snapshot) == expected
            first = backend.apply(_request(expected, candidate_id)).to_json()
            assert backend.restore(snapshot) == expected
            second = backend.apply(_request(expected, candidate_id)).to_json()
            assert first == second


def _snapshot_suffix(snapshot: dict[str, Any], *, room: str) -> tuple[str, ...]:
    backend = ReducedRunBackend()
    decision = backend.restore(deepcopy(snapshot))
    suffix = [decision.to_json()]
    for _ in range(100):
        if decision.status is not DecisionStatus.ACTIONABLE:
            return tuple(suffix)
        candidate_id = _choose(decision.policy_view(), room=room)
        transition = backend.apply(_request(decision, candidate_id))
        assert transition.result is TransitionResult.ACCEPTED
        suffix.append(transition.to_json())
        decision = transition.next_decision
    raise AssertionError("restored suffix exceeded bounded replay budget")


@pytest.mark.parametrize("room", ("rest", "event"))
def test_reduced_snapshot_restore_at_every_decision_replays_exact_suffix(room: str) -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(
        _config(initial_hp=60, combat_settings={"enemy_max_hp": 6})
    )
    snapshots: list[dict[str, Any]] = []
    for _ in range(100):
        snapshots.append(deepcopy(backend.snapshot()))
        if decision.status is not DecisionStatus.ACTIONABLE:
            break
        candidate_id = _choose(decision.policy_view(), room=room)
        decision = backend.apply(_request(decision, candidate_id)).next_decision
    else:
        raise AssertionError("route exceeded bounded snapshot budget")

    phases = {snapshot["phase"] for snapshot in snapshots}
    assert {"combat", "reward", "map", "room", "terminal"} <= phases
    for snapshot in snapshots:
        assert _snapshot_suffix(snapshot, room=room) == _snapshot_suffix(snapshot, room=room)


def test_combat_snapshot_restore_at_arbitrary_boundaries_replays_exact_suffix() -> None:
    backend = CombatV0Backend()
    decision = backend.reset(
        scenario_from_id("simple__starter", seed=29, enemy_max_hp=18)
    )
    snapshots: list[dict[str, Any]] = []
    for _ in range(40):
        snapshots.append(deepcopy(backend.snapshot()))
        if decision.status is not DecisionStatus.ACTIONABLE:
            break
        candidate_id = _choose(decision.policy_view())
        decision = backend.apply(_request(decision, candidate_id)).next_decision
    else:
        raise AssertionError("combat exceeded bounded snapshot budget")

    for snapshot in snapshots:
        first = CombatV0Backend()
        second = CombatV0Backend()
        first_decision = first.restore(deepcopy(snapshot))
        second_decision = second.restore(deepcopy(snapshot))
        assert first_decision == second_decision
        if first_decision.status is DecisionStatus.ACTIONABLE:
            candidate_id = _choose(first_decision.policy_view())
            assert first.apply(_request(first_decision, candidate_id)) == second.apply(
                _request(second_decision, candidate_id)
            )


def test_generic_runner_and_public_factory_replay_without_seed_coupling() -> None:
    config = _config(initial_hp=60, combat_settings={"enemy_max_hp": 6})
    seen: list[PolicyView] = []

    def chooser(view: PolicyView) -> str:
        assert type(view) is PolicyView
        assert not hasattr(view, "run_id")
        assert not hasattr(view, "decision_hash")
        seen.append(view)
        return _choose(view)

    first = run_episode(create_reduced_run_backend(), config, chooser, transition_budget=100)
    second = run_episode(create_reduced_run_backend(), config, _choose, transition_budget=100)
    assert first.stop_reason is second.stop_reason is EpisodeStopReason.TERMINAL
    assert first.transition_count == second.transition_count
    assert first.final_decision.to_json() == second.final_decision.to_json()
    assert seen


def test_trajectory_replay_is_policy_target_audit_separated_and_manifest_bound() -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(
        _config(initial_hp=60, combat_settings={"enemy_max_hp": 6})
    )
    recorder = TrajectoryRecorder("trajectory.conformance.reduced", backend.manifest())

    for _ in range(100):
        candidate_id = (
            None
            if decision.status is not DecisionStatus.ACTIONABLE
            else _choose(decision.policy_view())
        )
        record = recorder.record_boundary(decision, candidate_id)
        assert policy_view_for(record) == decision.policy_view()
        if candidate_id is None:
            break
        transition = backend.apply(_request(decision, candidate_id))
        recorder.record_transition(transition)
        decision = transition.next_decision
    else:
        raise AssertionError("trajectory exceeded bounded recording budget")

    finalized = recorder.finalize()
    assert finalized.manifest.completion is TrajectoryCompletion.TERMINAL
    assert finalized.manifest.evidence == backend.manifest().evidence
    assert finalized.manifest.descriptor(StreamRole.POLICY_REPLAY).record_count > 1
    policy = decode_policy_replay(finalized.policy_replay_jsonl)
    targets = decode_hindsight_targets(finalized.hindsight_target_jsonl)
    audits = decode_synthetic_audit(finalized.synthetic_audit_jsonl)
    assert len(policy) == len(audits)
    assert len(targets) == 1
    assert targets[0].label_timing == "hindsight"
    assert b'"run_id"' not in finalized.policy_replay_jsonl
    assert b'"decision_hash"' not in finalized.policy_replay_jsonl
    assert b'"receipt"' not in finalized.policy_replay_jsonl
    assert b'"run_id"' in finalized.synthetic_audit_jsonl
    assert b'"label_timing":"hindsight"' in finalized.hindsight_target_jsonl

    validated = validate_trajectory(
        finalized.manifest_json,
        finalized.policy_replay_jsonl,
        finalized.hindsight_target_jsonl,
        finalized.synthetic_audit_jsonl,
        expected_manifest_sha256=finalized.manifest_sha256,
    )
    assert validated == finalized


@pytest.mark.parametrize(
    ("backend", "configuration", "trajectory_id"),
    (
        (FixtureBackend(), "combat", "trajectory.conformance.fixture"),
        (
            CombatV0Backend(),
            scenario_from_id("simple__starter", seed=31, enemy_max_hp=6),
            "trajectory.conformance.combat",
        ),
    ),
    ids=("fixture", "combat_v0"),
)
def test_fixture_and_combat_manifests_bind_replay_records_without_claim_promotion(
    backend: object, configuration: object, trajectory_id: str
) -> None:
    decision = backend.reset(configuration)  # type: ignore[attr-defined]
    recorder = TrajectoryRecorder(trajectory_id, backend.manifest())  # type: ignore[attr-defined]
    for _ in range(60):
        candidate_id = (
            None
            if decision.status is not DecisionStatus.ACTIONABLE
            else (
                decision.candidates[0].candidate_id
                if isinstance(backend, FixtureBackend)
                else _choose(decision.policy_view())
            )
        )
        recorder.record_boundary(decision, candidate_id)
        if candidate_id is None:
            break
        transition = backend.apply(_request(decision, candidate_id))  # type: ignore[attr-defined]
        recorder.record_transition(transition)
        decision = transition.next_decision
    else:
        raise AssertionError("bounded backend trajectory did not terminate")

    finalized = recorder.finalize()
    assert finalized.manifest.evidence == backend.manifest().evidence  # type: ignore[attr-defined]
    assert all(
        item.label.value in {"combat_v0", "structural_fixture"}
        for item in finalized.manifest.evidence
    )
    assert b'"run_id"' not in finalized.policy_replay_jsonl


def test_snapshot_serialization_tamper_fails_closed_without_mutating_backend() -> None:
    """Isolated adversarial mutation of the public serialized-snapshot boundary."""

    backend = ReducedRunBackend()
    original = backend.reset(_config(combat_settings={"enemy_max_hp": 6}))
    snapshot = deepcopy(backend.snapshot())
    tampered = deepcopy(snapshot)
    tampered["private_world_snapshot"]["payload"]["rng"]["seed"] += 1

    with pytest.raises(ValueError):
        backend.restore(tampered)
    assert backend.observe() == original
    assert backend.snapshot() == snapshot
