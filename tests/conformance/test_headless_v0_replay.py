"""Replay, snapshot, runner, and trajectory conformance for headless_v0."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

import pytest

from game.backends.headless.combat_v0_backend import CombatV0Backend
from game.backends.headless.fixture_backend import FixtureBackend
from game.backends.headless.reduced_run_backend import (
    HeadlessRunConfig,
    ReducedRunBackend,
    ReducedRunBackendError,
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
    PublicEvent,
    PublicEventKind,
    TransitionResult,
    canonical_json,
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
from game.engine.headless_state import WorldState
from game.engine.random_service import GameRandomService


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
    source_decisions: list[str] = []
    source_transitions: list[str] = []
    for _ in range(100):
        snapshots.append(deepcopy(backend.snapshot()))
        source_decisions.append(decision.to_json())
        if decision.status is not DecisionStatus.ACTIONABLE:
            break
        candidate_id = _choose(decision.policy_view(), room=room)
        transition = backend.apply(_request(decision, candidate_id))
        source_transitions.append(transition.to_json())
        decision = transition.next_decision
    else:
        raise AssertionError("route exceeded bounded snapshot budget")

    phases = {snapshot["phase"] for snapshot in snapshots}
    assert {"combat", "reward", "map", "room", "terminal"} <= phases
    for index, snapshot in enumerate(snapshots):
        expected = (source_decisions[index], *source_transitions[index:])
        restored = _snapshot_suffix(snapshot, room=room)
        assert restored == expected


def test_reduced_runtime_unsupported_snapshot_matches_original_boundary() -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(
        _config(event_id="cool_spring", combat_settings={"enemy_max_hp": 1})
    )
    for _ in range(80):
        if decision.status is not DecisionStatus.ACTIONABLE:
            break
        candidate_id = _choose(decision.policy_view(), room="event")
        decision = backend.apply(_request(decision, candidate_id)).next_decision
    else:
        raise AssertionError("runtime-unsupported route exceeded bounded budget")
    assert decision.status is DecisionStatus.UNSUPPORTED
    snapshot = deepcopy(backend.snapshot())

    restored = ReducedRunBackend()
    restored_decision = restored.restore(deepcopy(snapshot))
    assert restored_decision.to_json() == decision.to_json()
    assert restored.snapshot() == snapshot
    assert _snapshot_suffix(snapshot, room="event") == (decision.to_json(),)


def _combat_snapshot_suffix(snapshot: dict[str, Any]) -> tuple[str, ...]:
    backend = CombatV0Backend()
    decision = backend.restore(deepcopy(snapshot))
    suffix = [decision.to_json()]
    for _ in range(40):
        if decision.status is not DecisionStatus.ACTIONABLE:
            return tuple(suffix)
        candidate_id = _choose(decision.policy_view())
        transition = backend.apply(_request(decision, candidate_id))
        assert transition.result is TransitionResult.ACCEPTED
        suffix.append(transition.to_json())
        decision = transition.next_decision
    raise AssertionError("restored combat suffix exceeded bounded budget")


def test_combat_snapshot_restore_at_arbitrary_boundaries_replays_exact_suffix() -> None:
    backend = CombatV0Backend()
    decision = backend.reset(
        scenario_from_id("simple__starter", seed=29, enemy_max_hp=18)
    )
    snapshots: list[dict[str, Any]] = []
    source_decisions: list[str] = []
    source_transitions: list[str] = []
    for _ in range(40):
        snapshots.append(deepcopy(backend.snapshot()))
        source_decisions.append(decision.to_json())
        if decision.status is not DecisionStatus.ACTIONABLE:
            break
        candidate_id = _choose(decision.policy_view())
        transition = backend.apply(_request(decision, candidate_id))
        source_transitions.append(transition.to_json())
        decision = transition.next_decision
    else:
        raise AssertionError("combat exceeded bounded snapshot budget")

    for index, snapshot in enumerate(snapshots):
        expected = (source_decisions[index], *source_transitions[index:])
        assert _combat_snapshot_suffix(snapshot) == expected


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


class _RecordingChooser:
    def __init__(self, *, room: str = "rest", end_turn_only: bool = False) -> None:
        self.room = room
        self.end_turn_only = end_turn_only
        self.views: list[PolicyView] = []

    def __call__(self, view: PolicyView) -> str:
        assert view.status is DecisionStatus.ACTIONABLE
        self.views.append(view)
        if self.end_turn_only and view.phase is DecisionPhase.COMBAT:
            return next(
                item.candidate_id
                for item in view.candidates
                if item.kind is CandidateKind.COMBAT_END_TURN
            )
        return _choose(view, room=self.room)


def _assert_chooser_stopped_at_boundary(
    backend: ReducedRunBackend,
    chooser: _RecordingChooser,
    transition_count: int,
) -> None:
    assert len(chooser.views) == transition_count
    calls_at_stop = len(chooser.views)
    backend.observe()
    assert len(chooser.views) == calls_at_stop


def test_reduced_runner_reports_structural_route_completion_not_full_game_win() -> None:
    backend = ReducedRunBackend()
    chooser = _RecordingChooser(room="rest")
    result = run_episode(
        backend,
        _config(initial_hp=60, combat_settings={"enemy_max_hp": 1}),
        chooser,
        transition_budget=100,
    )

    assert result.stop_reason is EpisodeStopReason.TERMINAL
    assert result.final_decision.status is DecisionStatus.TERMINAL
    assert result.final_decision.phase is DecisionPhase.TERMINAL
    assert result.final_decision.observation.data["outcome"] == "victory"
    assert result.final_decision.candidates == ()
    assert backend.terminal_reason == "route_complete"
    assert backend.unsupported_reason is None
    _assert_chooser_stopped_at_boundary(backend, chooser, result.transition_count)


def test_reduced_runner_reports_defeat_with_exact_nonpolicy_reason() -> None:
    backend = ReducedRunBackend()
    chooser = _RecordingChooser(end_turn_only=True)
    result = run_episode(
        backend,
        _config(initial_hp=1),
        chooser,
        transition_budget=100,
    )

    assert result.stop_reason is EpisodeStopReason.TERMINAL
    assert result.final_decision.status is DecisionStatus.TERMINAL
    assert result.final_decision.phase is DecisionPhase.TERMINAL
    assert result.final_decision.observation.data["outcome"] == "defeat"
    assert result.final_decision.candidates == ()
    assert backend.terminal_reason == "defeat"
    assert backend.unsupported_reason is None
    _assert_chooser_stopped_at_boundary(backend, chooser, result.transition_count)


def test_reduced_runner_reports_runtime_unsupported_with_exact_nonpolicy_reason() -> None:
    backend = ReducedRunBackend()
    chooser = _RecordingChooser(room="event")
    result = run_episode(
        backend,
        _config(event_id="cool_spring", combat_settings={"enemy_max_hp": 1}),
        chooser,
        transition_budget=100,
    )

    assert result.stop_reason is EpisodeStopReason.UNSUPPORTED
    assert result.final_decision.status is DecisionStatus.UNSUPPORTED
    assert result.final_decision.phase is DecisionPhase.UNSUPPORTED
    assert dict(result.final_decision.observation.data) == {
        "reason_code": "unsupported_content"
    }
    assert result.final_decision.candidates == ()
    assert backend.terminal_reason is None
    assert backend.unsupported_reason == "room_unavailable"
    _assert_chooser_stopped_at_boundary(backend, chooser, result.transition_count)


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


def _reduced_descriptor_hash(snapshot: dict[str, Any]) -> str:
    descriptor = {
        key: value for key, value in snapshot.items() if key != "descriptor_hash"
    }
    return sha256(
        b"reduced_headless.snapshot_descriptor.v3\0"
        + canonical_json(descriptor).encode("utf-8")
    ).hexdigest()


def _rehash_reduced_snapshot(snapshot: dict[str, Any]) -> None:
    snapshot["descriptor_hash"] = _reduced_descriptor_hash(snapshot)


def _rehash_world_and_reduced_snapshot(snapshot: dict[str, Any]) -> None:
    private_snapshot = snapshot["private_world_snapshot"]
    world = WorldState.from_private_dict(private_snapshot["payload"])
    private_snapshot["semantic_key"] = world.semantic_key()
    _rehash_reduced_snapshot(snapshot)


def _replace_snapshot_public_events(
    snapshot: dict[str, Any],
    source: DecisionState,
    events: tuple[PublicEvent, ...],
) -> None:
    forged = DecisionState.create(
        backend_id=source.backend_id,
        backend_version=source.backend_version,
        backend_fingerprint=source.backend_fingerprint,
        content_version=source.content_version,
        content_fingerprint=source.content_fingerprint,
        rules_version=source.rules_version,
        rules_fingerprint=source.rules_fingerprint,
        run_id=source.run_id,
        decision_sequence=source.decision_sequence,
        status=source.status,
        phase=source.phase,
        observation=source.observation,
        candidates=source.candidates,
        public_events=events,
    )
    snapshot["last_public_events"] = [event.to_dict() for event in events]
    snapshot["current_decision_hash"] = forged.decision_hash
    _rehash_reduced_snapshot(snapshot)


def _terminal_source() -> tuple[DecisionState, dict[str, Any]]:
    backend = ReducedRunBackend()
    result = run_episode(
        backend,
        _config(initial_hp=60, combat_settings={"enemy_max_hp": 1}),
        _RecordingChooser(room="rest"),
        transition_budget=100,
    )
    assert result.stop_reason is EpisodeStopReason.TERMINAL
    assert backend.terminal_reason == "route_complete"
    return result.final_decision, deepcopy(backend.snapshot())


def _assert_semantic_snapshot_rejection_is_atomic(snapshot: dict[str, Any]) -> None:
    assert snapshot["descriptor_hash"] == _reduced_descriptor_hash(snapshot)
    target = ReducedRunBackend()
    target.reset(_config(combat_settings={"enemy_max_hp": 6}))
    before = deepcopy(target.snapshot())

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        target.restore(deepcopy(snapshot))

    assert target.snapshot() == before


@pytest.mark.parametrize(
    "tamper",
    (
        "outer_action_history",
        "child_state",
        "public_event_payload",
        "rng_stream",
        "closed_map_history",
        "combat_entry_chronology",
    ),
)
def test_coordinated_semantic_snapshot_tampering_reaches_replay_validation_and_is_atomic(
    tamper: str,
) -> None:
    if tamper == "outer_action_history":
        source = ReducedRunBackend()
        decision = source.reset(_config(combat_settings={"enemy_max_hp": 20}))
        candidate_id = _choose(decision.policy_view())
        transition = source.apply(_request(decision, candidate_id))
        assert transition.result is TransitionResult.ACCEPTED
        forged = deepcopy(source.snapshot())
        assert forged["accepted_outer_candidate_ids"]
        forged["accepted_outer_candidate_ids"] = forged[
            "accepted_outer_candidate_ids"
        ][:-1]
        _rehash_reduced_snapshot(forged)
    elif tamper == "child_state":
        source = ReducedRunBackend()
        source.reset(_config(combat_settings={"enemy_max_hp": 40}))
        forged = deepcopy(source.snapshot())
        child = CombatV0Backend()
        child_decision = child.restore(deepcopy(forged["combat_snapshot"]))
        child_transition = child.apply(
            _request(child_decision, _choose(child_decision.policy_view()))
        )
        assert child_transition.result is TransitionResult.ACCEPTED
        assert child_transition.next_decision.status is DecisionStatus.ACTIONABLE
        forged["combat_snapshot"] = child.snapshot()
        _rehash_reduced_snapshot(forged)
    elif tamper == "public_event_payload":
        terminal, forged = _terminal_source()
        assert [event.event_type for event in terminal.public_events] == [
            PublicEventKind.MAP_NODE_CHOSEN,
            PublicEventKind.RUN_TERMINATED,
        ]
        events = (
            PublicEvent(
                0,
                PublicEventKind.MAP_NODE_CHOSEN,
                DecisionPhase.MAP,
                {"node_kind": "rest"},
            ),
            terminal.public_events[1],
        )
        _replace_snapshot_public_events(forged, terminal, events)
    elif tamper == "rng_stream":
        source = ReducedRunBackend()
        source.reset(_config())
        forged = deepcopy(source.snapshot())
        payload = forged["private_world_snapshot"]["payload"]
        rng = GameRandomService(0)
        rng.restore(payload["rng"])
        rng.randint("event_effect", 0, 10)
        payload["rng"] = rng.snapshot()
        _rehash_world_and_reduced_snapshot(forged)
    elif tamper == "closed_map_history":
        _terminal, forged = _terminal_source()
        payload = forged["private_world_snapshot"]["payload"]
        payload["node_history"] = payload["node_history"][:-1]
        payload["current_node_id"] = payload["node_history"][-1]
        _rehash_world_and_reduced_snapshot(forged)
    else:
        source = ReducedRunBackend()
        decision = source.reset(
            _config(initial_hp=60, combat_settings={"enemy_max_hp": 1})
        )
        for _ in range(80):
            if source.combat_launch_count == 2 and decision.phase is DecisionPhase.COMBAT:
                break
            candidate_id = _choose(decision.policy_view(), room="rest")
            decision = source.apply(_request(decision, candidate_id)).next_decision
        else:
            raise AssertionError("second combat entry was not reached")
        forged = deepcopy(source.snapshot())
        assert forged["combat_entry_sequence"] > 0
        forged["combat_entry_sequence"] -= 1
        _rehash_reduced_snapshot(forged)

    _assert_semantic_snapshot_rejection_is_atomic(forged)


def test_snapshot_serialization_tamper_fails_closed_without_mutating_backend() -> None:
    """Outer checksum rejection remains separate from semantic replay checks."""

    backend = ReducedRunBackend()
    original = backend.reset(_config(combat_settings={"enemy_max_hp": 6}))
    snapshot = deepcopy(backend.snapshot())
    tampered = deepcopy(snapshot)
    tampered["private_world_snapshot"]["payload"]["rng"]["seed"] += 1

    with pytest.raises(ValueError):
        backend.restore(tampered)
    assert backend.observe() == original
    assert backend.snapshot() == snapshot
