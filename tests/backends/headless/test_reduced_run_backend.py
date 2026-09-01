"""End-to-end structural-fixture tests for the H3 reduced-run composer."""

from __future__ import annotations

from copy import deepcopy
from multiprocessing import get_context
import pickle
from typing import Any

import pytest

import game.backends.headless.reduced_run_backend as reduced_module
from game.backends.headless.reduced_run_backend import (
    BACKEND_FINGERPRINT,
    BACKEND_ID,
    BACKEND_VERSION,
    RULES_FINGERPRINT,
    RULES_VERSION,
    HeadlessRunConfig,
    ReducedRunBackend,
    ReducedRunBackendError,
    create_reduced_run_backend,
)
from game.content.reduced_v0 import CONTENT_FINGERPRINT, CONTENT_VERSION
from game.contracts.headless_v0 import (
    ActionRequest,
    CandidateKind,
    DecisionPhase,
    DecisionStatus,
    EvidenceLabel,
    HeadlessBinding,
    PolicyView,
    PublicEventKind,
    TransitionReason,
    TransitionResult,
)
from game.data.headless_trajectory import TrajectoryRecorder
from game.engine.headless_state import WorldState
from game.runtime.episode_runner import EpisodeStopReason, run_episode


def _config(**settings: Any) -> HeadlessRunConfig:
    return HeadlessRunConfig(
        scenario_id="simple__starter",
        content_fingerprint=CONTENT_FINGERPRINT,
        game_seed=7,
        backend_settings=settings,
    )


def _request(decision, candidate) -> ActionRequest:
    return ActionRequest(HeadlessBinding.for_candidate(decision, candidate.candidate_id))


def _candidate(decision, kind: CandidateKind):
    return next(item for item in decision.candidates if item.kind is kind)


def _apply_kind(backend: ReducedRunBackend, decision, kind: CandidateKind):
    transition = backend.apply(_request(decision, _candidate(decision, kind)))
    assert transition.result is TransitionResult.ACCEPTED
    assert transition.public_events == transition.next_decision.public_events
    assert tuple(event.sequence for event in transition.public_events) == tuple(
        range(len(transition.public_events))
    )
    return transition.next_decision


def _combat_choice(decision):
    plays = [
        item for item in decision.candidates
        if item.kind is CandidateKind.COMBAT_PLAY_CARD
    ]
    damaging_refs = {
        card["card_ref"]
        for card in decision.observation.data["hand"]
        if card["card_definition_id"] in {"bash", "body_slam", "iron_wave", "strike"}
    }
    damaging = [item for item in plays if item.card_ref in damaging_refs]
    return (
        damaging[0]
        if damaging
        else plays[0]
        if plays
        else _candidate(decision, CandidateKind.COMBAT_END_TURN)
    )


def _finish_combat(backend: ReducedRunBackend, decision):
    for _ in range(100):
        if decision.phase is not DecisionPhase.COMBAT:
            return decision
        transition = backend.apply(_request(decision, _combat_choice(decision)))
        assert transition.result is TransitionResult.ACCEPTED
        assert transition.public_events == transition.next_decision.public_events
        decision = transition.next_decision
    raise AssertionError("combat did not finish within the bounded fixture budget")


def _finish_reward(backend: ReducedRunBackend, decision):
    assert decision.phase is DecisionPhase.REWARD
    if any(item.kind is CandidateKind.REWARD_CLAIM_GOLD for item in decision.candidates):
        decision = _apply_kind(backend, decision, CandidateKind.REWARD_CLAIM_GOLD)
    if any(item.kind is CandidateKind.REWARD_OPEN_CARD_REWARD for item in decision.candidates):
        decision = _apply_kind(backend, decision, CandidateKind.REWARD_OPEN_CARD_REWARD)
    if any(item.kind is CandidateKind.REWARD_CHOOSE_CARD for item in decision.candidates):
        decision = _apply_kind(backend, decision, CandidateKind.REWARD_CHOOSE_CARD)
    if any(item.kind is CandidateKind.REWARD_SKIP_CARD for item in decision.candidates):
        decision = _apply_kind(backend, decision, CandidateKind.REWARD_SKIP_CARD)
    return _apply_kind(backend, decision, CandidateKind.REWARD_PROCEED)


def _choose_map_kind(backend: ReducedRunBackend, decision, node_kind: str):
    kind_by_reference = {
        node["node_ref"]: node["kind"] for node in decision.observation.data["nodes"]
    }
    selected = next(
        item for item in decision.candidates
        if kind_by_reference[item.node_ref] == node_kind
    )
    transition = backend.apply(_request(decision, selected))
    assert transition.result is TransitionResult.ACCEPTED
    return transition.next_decision


def _to_pre_combat_two(backend: ReducedRunBackend):
    decision = _finish_combat(backend, backend.observe())
    decision = _finish_reward(backend, decision)
    decision = _choose_map_kind(backend, decision, "rest")
    if any(item.kind is CandidateKind.ROOM_REST_HEAL for item in decision.candidates):
        decision = _apply_kind(backend, decision, CandidateKind.ROOM_REST_HEAL)
    decision = _apply_kind(backend, decision, CandidateKind.ROOM_PROCEED)
    assert decision.phase is DecisionPhase.MAP
    return decision


def _finish_route(backend: ReducedRunBackend, decision):
    if decision.phase is DecisionPhase.MAP:
        decision = _choose_map_kind(backend, decision, "combat")
    decision = _finish_combat(backend, decision)
    decision = _finish_reward(backend, decision)
    return _choose_map_kind(backend, decision, "terminal")


def _spawn_factory_probe(queue) -> None:
    factory = pickle.loads(pickle.dumps(create_reduced_run_backend))
    config = pickle.loads(pickle.dumps(_config()))
    backend = factory()
    decision = backend.reset(config)
    queue.put((type(backend).__name__, decision.phase.value, decision.decision_sequence))


def _rehash_snapshot(snapshot: dict[str, Any]) -> None:
    descriptor = {key: value for key, value in snapshot.items() if key != "descriptor_hash"}
    snapshot["descriptor_hash"] = reduced_module._canonical_hash(
        "reduced_headless.snapshot_descriptor.v0", descriptor
    )


def test_manifest_is_exact_component_addressable_and_truthful() -> None:
    manifest = ReducedRunBackend().manifest()

    assert manifest.backend_id == BACKEND_ID
    assert manifest.backend_version == BACKEND_VERSION
    assert manifest.backend_fingerprint == BACKEND_FINGERPRINT
    assert manifest.content_version == CONTENT_VERSION
    assert manifest.content_fingerprint == CONTENT_FINGERPRINT
    assert manifest.rules_version == RULES_VERSION
    assert manifest.rules_fingerprint == RULES_FINGERPRINT
    assert manifest.supported_phases == (
        DecisionPhase.COMBAT,
        DecisionPhase.MAP,
        DecisionPhase.REWARD,
        DecisionPhase.ROOM,
    )
    assert manifest.unsupported_phases == ()
    assert manifest.capabilities.deterministic_reset is True
    assert manifest.capabilities.counterfactual_stepping is True
    assert manifest.capabilities.snapshot_restore is True
    assert manifest.capabilities.fixture_playback is False
    assert manifest.capabilities.live_truth is False
    assert manifest.capabilities.legacy_shaped_reward_diagnostics is False

    evidence = {item.component: item.label for item in manifest.evidence}
    assert tuple(evidence) == tuple(sorted(evidence))
    assert evidence == {
        "combat_backend": EvidenceLabel.COMBAT_V0,
        "combat_projection": EvidenceLabel.COMBAT_V0,
        "combat_rules": EvidenceLabel.COMBAT_V0,
        "composer": EvidenceLabel.STRUCTURAL_FIXTURE,
        "content": EvidenceLabel.STRUCTURAL_FIXTURE,
        "map": EvidenceLabel.STRUCTURAL_FIXTURE,
        "reward": EvidenceLabel.STRUCTURAL_FIXTURE,
        "room": EvidenceLabel.STRUCTURAL_FIXTURE,
        "snapshot": EvidenceLabel.STRUCTURAL_FIXTURE,
        "state": EvidenceLabel.STRUCTURAL_FIXTURE,
    }


def test_config_is_strict_json_pickle_safe_and_factory_spawns() -> None:
    config = _config(
        combat_settings={"incoming_damage_shaping_scale_ratio": [0, 1]},
        event_id="cool_spring",
    )
    assert pickle.loads(pickle.dumps(config)) == config
    assert HeadlessRunConfig.from_dict(config.to_dict()) == config
    assert set(config.to_dict()) == {
        "scenario_id", "content_fingerprint", "game_seed", "backend_settings"
    }

    context = get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_spawn_factory_probe, args=(queue,))
    process.start()
    process.join(15)
    assert process.exitcode == 0
    assert queue.get(timeout=2) == ("ReducedRunBackend", "combat", 0)


@pytest.mark.parametrize(
    "payload",
    (
        {"scenario_id": "slimes__starter", "content_fingerprint": CONTENT_FINGERPRINT, "game_seed": 1, "backend_settings": {}},
        {"scenario_id": "simple__starter", "content_fingerprint": "0" * 64, "game_seed": 1, "backend_settings": {}},
        {"scenario_id": "simple__starter", "content_fingerprint": CONTENT_FINGERPRINT, "game_seed": True, "backend_settings": {}},
        {"scenario_id": "simple__starter", "content_fingerprint": CONTENT_FINGERPRINT, "game_seed": 1, "backend_settings": {"policy_seed": 2}},
        {"scenario_id": "simple__starter", "content_fingerprint": CONTENT_FINGERPRINT, "game_seed": 1, "backend_settings": {"worker_seed": 2}},
        {"scenario_id": "simple__starter", "content_fingerprint": CONTENT_FINGERPRINT, "game_seed": 1, "backend_settings": {"event_id": "arbitrary"}},
        {"scenario_id": "simple__starter", "content_fingerprint": CONTENT_FINGERPRINT, "game_seed": 1, "backend_settings": {"value": 1.25}},
        {"scenario_id": "simple__starter", "content_fingerprint": CONTENT_FINGERPRINT, "game_seed": 1, "backend_settings": {"value": lambda: None}},
        {"scenario_id": "simple__starter", "content_fingerprint": CONTENT_FINGERPRINT, "game_seed": 1, "backend_settings": {}, "extra": 1},
    ),
)
def test_invalid_configuration_rejects_before_backend_mutation(payload) -> None:
    backend = ReducedRunBackend()
    original = backend.reset(_config()).to_json()
    original_snapshot = backend.snapshot()

    with pytest.raises(ReducedRunBackendError):
        backend.reset(payload)

    assert backend.observe().to_json() == original
    assert backend.snapshot() == original_snapshot


def test_fresh_determinism_repeated_reset_identity_and_stale_old_binding() -> None:
    first, second = ReducedRunBackend(), ReducedRunBackend()
    first_decision, second_decision = first.reset(_config()), second.reset(_config())
    assert first_decision.to_json() == second_decision.to_json()
    assert first.snapshot() == second.snapshot()

    old_request = _request(
        first_decision,
        _candidate(first_decision, CandidateKind.COMBAT_END_TURN),
    )
    reset_decision = first.reset(_config())
    assert reset_decision.decision_sequence == 0
    assert reset_decision.run_id != first_decision.run_id
    before = first.snapshot()
    stale = first.apply(old_request)
    assert stale.result is TransitionResult.STALE
    assert stale.reason is TransitionReason.STALE_BINDING
    assert stale.next_decision.to_json() == reset_decision.to_json()
    assert first.snapshot() == before


@pytest.mark.parametrize("room_kind", ("rest", "event"))
def test_seeded_two_combat_route_has_persistent_handoff_and_no_waiting(room_kind: str) -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(_config())
    opening_snapshot = backend.snapshot()
    opening_deck = opening_snapshot["private_world_snapshot"]["payload"]["master_deck"]
    observed_statuses = []

    decision = _finish_combat(backend, decision)
    observed_statuses.append(decision.status)
    first_combat_hp = decision.observation.data["player"]["hp"]
    decision = _finish_reward(backend, decision)
    observed_statuses.append(decision.status)
    decision = _choose_map_kind(backend, decision, room_kind)
    observed_statuses.append(decision.status)
    room_ready = decision.observation.data["player"]
    option_kind = (
        CandidateKind.ROOM_REST_HEAL
        if room_kind == "rest"
        else CandidateKind.ROOM_EVENT_OPTION
    )
    if any(item.kind is option_kind for item in decision.candidates):
        decision = _apply_kind(backend, decision, option_kind)
        observed_statuses.append(decision.status)
    decision = _apply_kind(backend, decision, CandidateKind.ROOM_PROCEED)
    observed_statuses.append(decision.status)
    decision = _choose_map_kind(backend, decision, "combat")
    observed_statuses.append(decision.status)

    combat_two_snapshot = backend.snapshot()
    launch = combat_two_snapshot["combat_snapshot"]["launch"]
    persistent_deck = combat_two_snapshot["private_world_snapshot"]["payload"]["master_deck"]
    assert launch["ordered_deck"] == persistent_deck
    assert len(persistent_deck) == len(opening_deck) + 1
    assert not any(card["definition_id"] == "slimed" for card in persistent_deck)
    assert launch["current_hp"] == decision.observation.data["player"]["hp"]
    assert launch["current_hp"] >= first_combat_hp
    assert room_ready["gold"] == 25
    assert backend.combat_launch_count == 2
    assert DecisionStatus.WAITING not in observed_statuses

    decision = _finish_route(backend, decision)
    assert decision.status is DecisionStatus.TERMINAL
    assert decision.observation.data["outcome"] == "victory"
    assert backend.terminal_reason == "route_complete"
    assert [event.event_type for event in decision.public_events] == [
        PublicEventKind.MAP_NODE_CHOSEN,
        PublicEventKind.RUN_TERMINATED,
    ]
    assert backend.combat_launch_count == 2


def test_defeat_terminates_immediately_with_resolution_and_run_event() -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(_config(initial_hp=1))
    while decision.phase is DecisionPhase.COMBAT:
        decision = _apply_kind(
            backend,
            decision,
            CandidateKind.COMBAT_END_TURN,
        )

    assert decision.status is DecisionStatus.TERMINAL
    assert decision.observation.data["outcome"] == "defeat"
    assert backend.terminal_reason == "defeat"
    assert [event.event_type for event in decision.public_events][-2:] == [
        PublicEventKind.COMBAT_RESOLVED,
        PublicEventKind.RUN_TERMINATED,
    ]
    private = backend.snapshot()["private_world_snapshot"]["payload"]
    assert private["automatic_queue"] == []
    assert private["pending_decision"] is None
    assert private["rng"]["streams"].keys() == {"combat_launch"}


def test_full_outer_authentication_and_reused_combat_candidate_are_atomic() -> None:
    backend = ReducedRunBackend()
    first = backend.reset(_config())
    end_turn = _candidate(first, CandidateKind.COMBAT_END_TURN)
    old_request = _request(first, end_turn)

    invalid = ActionRequest(
        HeadlessBinding(
            first.run_id,
            first.decision_sequence,
            first.decision_hash,
            "cand." + "0" * 64,
        )
    )
    before = backend.snapshot()
    rejected = backend.apply(invalid)
    assert rejected.result is TransitionResult.REJECTED
    assert rejected.reason is TransitionReason.INVALID_CANDIDATE
    assert backend.snapshot() == before

    tampered = ActionRequest(
        HeadlessBinding(
            first.run_id,
            first.decision_sequence,
            "0" * 64,
            end_turn.candidate_id,
        )
    )
    stale = backend.apply(tampered)
    assert stale.result is TransitionResult.STALE
    assert backend.snapshot() == before

    pre_combat_two = _to_pre_combat_two(backend)
    combat_two = _choose_map_kind(backend, pre_combat_two, "combat")
    repeated = _candidate(combat_two, CandidateKind.COMBAT_END_TURN)
    assert repeated.candidate_id == end_turn.candidate_id
    current = backend.snapshot()
    stale = backend.apply(old_request)
    assert stale.result is TransitionResult.STALE
    assert backend.snapshot() == current


def test_combat_launch_counter_advances_only_on_actual_combat_entry() -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(_config())
    assert backend.combat_launch_count == 1

    decision = _finish_combat(backend, decision)
    decision = _apply_kind(backend, decision, CandidateKind.REWARD_CLAIM_GOLD)
    assert backend.combat_launch_count == 1
    decision = _apply_kind(backend, decision, CandidateKind.REWARD_OPEN_CARD_REWARD)
    assert backend.combat_launch_count == 1
    decision = _apply_kind(backend, decision, CandidateKind.REWARD_SKIP_CARD)
    decision = _apply_kind(backend, decision, CandidateKind.REWARD_PROCEED)
    decision = _choose_map_kind(backend, decision, "event")
    decision = _apply_kind(backend, decision, CandidateKind.ROOM_EVENT_OPTION)
    decision = _apply_kind(backend, decision, CandidateKind.ROOM_PROCEED)
    assert backend.combat_launch_count == 1

    _choose_map_kind(backend, decision, "combat")
    assert backend.combat_launch_count == 2


def test_snapshot_matrix_restores_every_required_boundary_exactly() -> None:
    backend = ReducedRunBackend()
    snapshots: dict[str, dict[str, Any]] = {}
    decision = backend.reset(_config())
    snapshots["reset"] = backend.snapshot()
    transition = backend.apply(_request(decision, _combat_choice(decision)))
    decision = transition.next_decision
    snapshots["mid_combat"] = backend.snapshot()
    decision = _finish_combat(backend, decision)
    snapshots["reward_unopened"] = backend.snapshot()
    decision = _apply_kind(backend, decision, CandidateKind.REWARD_CLAIM_GOLD)
    decision = _apply_kind(backend, decision, CandidateKind.REWARD_OPEN_CARD_REWARD)
    snapshots["reward_opened"] = backend.snapshot()
    decision = _apply_kind(backend, decision, CandidateKind.REWARD_CHOOSE_CARD)
    snapshots["reward_resolved"] = backend.snapshot()
    decision = _apply_kind(backend, decision, CandidateKind.REWARD_PROCEED)
    snapshots["map"] = backend.snapshot()
    decision = _choose_map_kind(backend, decision, "rest")
    snapshots["room_ready"] = backend.snapshot()
    decision = _apply_kind(backend, decision, CandidateKind.ROOM_REST_HEAL)
    snapshots["room_resolved"] = backend.snapshot()
    decision = _apply_kind(backend, decision, CandidateKind.ROOM_PROCEED)
    snapshots["pre_combat_two"] = backend.snapshot()
    decision = _choose_map_kind(backend, decision, "combat")
    snapshots["combat_two"] = backend.snapshot()
    decision = _finish_route(backend, decision)
    snapshots["terminal"] = backend.snapshot()

    unsupported = ReducedRunBackend()
    unsupported_decision = unsupported.reset(
        _config(event_id="cool_spring", combat_settings={"enemy_max_hp": 1})
    )
    unsupported_decision = _finish_combat(unsupported, unsupported_decision)
    unsupported_decision = _finish_reward(unsupported, unsupported_decision)
    unsupported_decision = _choose_map_kind(unsupported, unsupported_decision, "event")
    assert unsupported_decision.status is DecisionStatus.UNSUPPORTED
    snapshots["runtime_unsupported"] = unsupported.snapshot()

    assert set(snapshots) == {
        "reset", "mid_combat", "reward_unopened", "reward_opened",
        "reward_resolved", "map", "room_ready", "room_resolved",
        "pre_combat_two", "combat_two", "terminal", "runtime_unsupported",
    }
    for name, snapshot in snapshots.items():
        restored = ReducedRunBackend()
        decision = restored.restore(deepcopy(snapshot))
        assert decision.decision_hash == snapshot["current_decision_hash"], name
        assert decision.public_events == tuple(
            reduced_module.PublicEvent.from_dict(item)
            for item in snapshot["last_public_events"]
        ), name
        assert restored.snapshot() == snapshot, name


def test_pre_combat_two_restore_reproduces_launch_decision_events_and_rng() -> None:
    original = ReducedRunBackend()
    original.reset(_config())
    pre_combat = _to_pre_combat_two(original)
    snapshot = original.snapshot()
    restored = ReducedRunBackend()
    restored_pre_combat = restored.restore(deepcopy(snapshot))
    assert restored.rng_stream_counters == original.rng_stream_counters

    original_next = _choose_map_kind(original, pre_combat, "combat")
    restored_next = _choose_map_kind(restored, restored_pre_combat, "combat")
    assert restored_next.to_json() == original_next.to_json()
    original_snapshot = original.snapshot()
    restored_snapshot = restored.snapshot()
    assert restored_snapshot["combat_snapshot"]["launch"] == original_snapshot["combat_snapshot"]["launch"]
    assert restored_snapshot["last_public_events"] == original_snapshot["last_public_events"]
    assert restored.rng_stream_counters == original.rng_stream_counters
    assert restored.combat_launch_count == 2


@pytest.mark.parametrize(
    "tamper",
    ("provenance", "phase", "queue", "combat_key", "parked_map"),
)
def test_snapshot_tampering_is_rejected_and_leaves_backend_unchanged(tamper: str) -> None:
    source = ReducedRunBackend()
    source.reset(_config())
    snapshot = deepcopy(source.snapshot())
    target = ReducedRunBackend()
    target.reset(_config())
    target_before = target.snapshot()

    if tamper == "provenance":
        snapshot["rules_fingerprint"] = "0" * 64
    elif tamper == "phase":
        snapshot["phase"] = "reward"
    else:
        private = snapshot["private_world_snapshot"]
        payload = private["payload"]
        if tamper == "queue":
            payload["automatic_queue"] = []
        elif tamper == "combat_key":
            payload["active_combat_launch_key"] = "0" * 64
        else:
            parked = payload["automatic_queue"][0]["private_payload"]["pending_decision"]
            parked["private_context"]["public_events"][0]["data"]["node_kind"] = "rest"
        world = WorldState.from_private_dict(payload)
        private["semantic_key"] = world.semantic_key()
    _rehash_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError):
        target.restore(snapshot)
    assert target.snapshot() == target_before


def test_child_rule_exception_restores_complete_transaction_preimage(monkeypatch) -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(_config())
    before = backend.snapshot()

    def fail_after_mutation(child, request):
        child._environment.player.hp = 1
        raise RuntimeError("forced child rule failure")

    monkeypatch.setattr(reduced_module.CombatV0Backend, "apply", fail_after_mutation)
    transition = backend.apply(_request(decision, decision.candidates[0]))
    assert transition.result is TransitionResult.REJECTED
    assert transition.reason is TransitionReason.REJECTED_BY_RULES
    assert transition.next_decision.to_json() == decision.to_json()
    assert backend.snapshot() == before


def test_reset_detaches_caller_owned_config_mapping() -> None:
    config = _config(combat_settings={"cards_per_turn": 5})
    backend = ReducedRunBackend()
    backend.reset(config)
    before = backend.snapshot()

    config.backend_settings["initial_gold"] = 999
    config.backend_settings["combat_settings"]["cards_per_turn"] = 1

    assert backend.snapshot() == before


class _ScriptedChooser:
    def __init__(self) -> None:
        self.views: list[PolicyView] = []

    def __call__(self, view: PolicyView) -> str:
        assert isinstance(view, PolicyView)
        assert not hasattr(view, "run_id")
        assert not hasattr(view, "decision_hash")
        self.views.append(view)
        if view.phase is DecisionPhase.COMBAT:
            plays = [item for item in view.candidates if item.kind is CandidateKind.COMBAT_PLAY_CARD]
            return (plays[0] if plays else _candidate(view, CandidateKind.COMBAT_END_TURN)).candidate_id
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
            kind_by_reference = {
                node["node_ref"]: node["kind"] for node in view.observation.data["nodes"]
            }
            rest = [
                item for item in view.candidates
                if kind_by_reference[item.node_ref] == "rest"
            ]
            return (rest[0] if rest else view.candidates[0]).candidate_id
        return view.candidates[0].candidate_id


def test_generic_episode_runner_and_trajectory_recorder_accept_outer_boundary() -> None:
    backend = ReducedRunBackend()
    chooser = _ScriptedChooser()
    result = run_episode(backend, _config(), chooser, transition_budget=100)
    assert result.stop_reason is EpisodeStopReason.TERMINAL
    assert result.final_decision.status is DecisionStatus.TERMINAL
    assert backend.terminal_reason == "route_complete"
    assert chooser.views and all(isinstance(view, PolicyView) for view in chooser.views)

    fresh = ReducedRunBackend()
    initial = fresh.reset(_config())
    recorder = TrajectoryRecorder("trajectory.h3.reduced", fresh.manifest())
    record = recorder.record_boundary(initial, initial.candidates[0].candidate_id)
    assert initial.decision_sequence == 0
    assert record.chosen_action == initial.candidates[0]


def test_runtime_unavailable_room_is_visible_unsupported_and_snapshot_capable() -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(
        _config(event_id="cool_spring", combat_settings={"enemy_max_hp": 1})
    )
    decision = _finish_combat(backend, decision)
    decision = _finish_reward(backend, decision)
    transition_source = decision
    decision = _choose_map_kind(backend, decision, "event")

    assert decision.status is DecisionStatus.UNSUPPORTED
    assert decision.phase is DecisionPhase.UNSUPPORTED
    assert decision.candidates == ()
    assert decision.observation.data == {"reason_code": "unsupported_content"}
    assert backend.unsupported_reason == "room_unavailable"
    assert decision.decision_sequence == transition_source.decision_sequence + 1
    restored = ReducedRunBackend()
    assert restored.restore(backend.snapshot()).to_json() == decision.to_json()
