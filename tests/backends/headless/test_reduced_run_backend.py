"""End-to-end structural-fixture tests for the H3 reduced-run composer."""

from __future__ import annotations

from copy import deepcopy
from multiprocessing import get_context
import pickle
from typing import Any

import pytest

import game.backends.headless.combat_v0_backend as combat_module
import game.backends.headless.reduced_run_backend as reduced_module
from game.backends.headless.combat_v0_backend import CombatV0Backend
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
    DecisionState,
    DecisionStatus,
    EvidenceLabel,
    HeadlessBinding,
    MAX_PUBLIC_COUNTER,
    PolicyView,
    PublicEvent,
    PublicEventKind,
    TransitionReason,
    TransitionResult,
)
from game.data.headless_trajectory import TrajectoryRecorder
from game.engine.headless_state import CombatLaunchSpec, WorldState
from game.engine.random_service import GameRandomService
from game.engine.room_rules import RoomRuleError
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
        reduced_module._SNAPSHOT_DESCRIPTOR_DOMAIN, descriptor
    )


def _rehash_world_snapshot(snapshot: dict[str, Any]) -> None:
    private = snapshot["private_world_snapshot"]
    world = WorldState.from_private_dict(private["payload"])
    private["semantic_key"] = world.semantic_key()
    _rehash_snapshot(snapshot)


def _rehash_combat_snapshot(snapshot: dict[str, Any]) -> None:
    descriptor = {key: value for key, value in snapshot.items() if key != "descriptor_hash"}
    snapshot["descriptor_hash"] = combat_module._fingerprint(
        "combat_v0_backend.snapshot_descriptor.v1", descriptor
    )


def _map_node_instance(snapshot: dict[str, Any], definition_id: str) -> str:
    return next(
        node["instance_id"]
        for node in snapshot["private_world_snapshot"]["payload"]["map_nodes"]
        if node["definition_id"] == definition_id
    )


def _replace_snapshot_events(
    snapshot: dict[str, Any],
    decision: DecisionState,
    events: tuple[PublicEvent, ...],
) -> None:
    forged = DecisionState.create(
        backend_id=decision.backend_id,
        backend_version=decision.backend_version,
        backend_fingerprint=decision.backend_fingerprint,
        content_version=decision.content_version,
        content_fingerprint=decision.content_fingerprint,
        rules_version=decision.rules_version,
        rules_fingerprint=decision.rules_fingerprint,
        run_id=decision.run_id,
        decision_sequence=decision.decision_sequence,
        status=decision.status,
        phase=decision.phase,
        observation=decision.observation,
        candidates=decision.candidates,
        public_events=events,
    )
    snapshot["last_public_events"] = [event.to_dict() for event in events]
    snapshot["current_decision_hash"] = forged.decision_hash
    _rehash_snapshot(snapshot)


def _replace_snapshot_combat_boundary(
    snapshot: dict[str, Any],
    outer: DecisionState,
    child: DecisionState,
) -> None:
    forged = DecisionState.create(
        backend_id=outer.backend_id,
        backend_version=outer.backend_version,
        backend_fingerprint=outer.backend_fingerprint,
        content_version=outer.content_version,
        content_fingerprint=outer.content_fingerprint,
        rules_version=outer.rules_version,
        rules_fingerprint=outer.rules_fingerprint,
        run_id=outer.run_id,
        decision_sequence=outer.decision_sequence,
        status=child.status,
        phase=child.phase,
        observation=child.observation,
        candidates=child.candidates,
        public_events=child.public_events,
    )
    snapshot["current_decision_hash"] = forged.decision_hash
    snapshot["last_public_events"] = [
        event.to_dict() for event in child.public_events
    ]
    snapshot["public_scope"] = child.observation.public_scope.to_dict()
    _rehash_snapshot(snapshot)


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


@pytest.mark.parametrize(
    "settings",
    (
        {"initial_gold": MAX_PUBLIC_COUNTER, "combat_settings": {"enemy_max_hp": 1}},
        {
            "initial_gold": MAX_PUBLIC_COUNTER - 25,
            "event_id": "cool_spring",
            "combat_settings": {"enemy_max_hp": 1},
        },
        {
            "initial_gold": MAX_PUBLIC_COUNTER - 50,
            "event_id": "quiet_cache",
            "combat_settings": {"enemy_max_hp": 1},
        },
    ),
)
def test_configuration_preflight_rejects_deterministic_gold_deadlocks(settings) -> None:
    with pytest.raises(ReducedRunBackendError, match="gold bound"):
        _config(**settings)


def test_liveness_preflight_allows_exact_single_reward_bound() -> None:
    config = _config(
        initial_gold=MAX_PUBLIC_COUNTER - 25,
        map_template_id="short_rest_path",
        combat_settings={"enemy_max_hp": 1},
    )
    decision = ReducedRunBackend().reset(config)
    assert decision.status is DecisionStatus.ACTIONABLE


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


def test_restore_reconstructs_active_generation_without_rewinding_lifetime_epoch() -> None:
    backend = ReducedRunBackend()
    generation_zero = backend.reset(_config())
    snapshot_zero = deepcopy(backend.snapshot())
    generation_one = backend.reset(_config())
    request_one = _request(
        generation_one,
        _candidate(generation_one, CandidateKind.COMBAT_END_TURN),
    )

    restored_zero = backend.restore(snapshot_zero)
    assert restored_zero.run_id == generation_zero.run_id
    assert backend.snapshot()["reset_generation"] == 0
    generation_two = backend.reset(_config())
    assert backend.snapshot()["reset_generation"] == 2
    assert generation_two.run_id not in {generation_zero.run_id, generation_one.run_id}
    assert generation_two.decision_hash != generation_one.decision_hash
    assert backend.apply(request_one).result is TransitionResult.STALE

    fresh = ReducedRunBackend()
    fresh.restore(deepcopy(backend.snapshot()))
    assert fresh.reset(_config()).run_id != generation_two.run_id
    assert fresh.snapshot()["reset_generation"] == 3


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


def _progress_combat_snapshot(outer_snapshot: dict[str, Any]) -> CombatV0Backend:
    child = CombatV0Backend()
    decision = child.restore(deepcopy(outer_snapshot["combat_snapshot"]))
    transition = child.apply(_request(decision, _combat_choice(decision)))
    assert transition.result is TransitionResult.ACCEPTED
    return child


def test_restore_rejects_terminal_combat_child_under_active_combat_world() -> None:
    source = ReducedRunBackend()
    source.reset(_config(combat_settings={"enemy_max_hp": 1}))
    snapshot = deepcopy(source.snapshot())
    child = _progress_combat_snapshot(snapshot)
    assert child.get_resolution() is not None
    snapshot["combat_snapshot"] = child.snapshot()
    _rehash_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


@pytest.mark.parametrize("combat_number", (1, 2))
def test_restore_rejects_child_progress_spliced_ahead_of_outer_sequence(
    combat_number: int,
) -> None:
    source = ReducedRunBackend()
    source.reset(_config())
    if combat_number == 2:
        pre_combat_two = _to_pre_combat_two(source)
        _choose_map_kind(source, pre_combat_two, "combat")
    snapshot = deepcopy(source.snapshot())
    child = _progress_combat_snapshot(snapshot)
    assert child.get_resolution() is None
    snapshot["combat_snapshot"] = child.snapshot()
    _rehash_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


@pytest.mark.parametrize("splice", ("seed", "scenario", "settings"))
def test_restore_binds_active_launch_to_world_rng_and_exact_config(splice: str) -> None:
    source = ReducedRunBackend()
    source.reset(_config())
    snapshot = deepcopy(source.snapshot())
    combat_snapshot = snapshot["combat_snapshot"]
    launch_payload = combat_snapshot["launch"]
    if splice == "seed":
        launch_payload["combat_seed"] += 1
    elif splice == "scenario":
        launch_payload["scenario_id"] = "nibbit__starter"
    else:
        launch_payload["combat_settings"] = {"cards_per_turn": 4}
    launch = CombatLaunchSpec.from_dict(launch_payload)
    _rehash_combat_snapshot(combat_snapshot)
    snapshot["private_world_snapshot"]["payload"]["active_combat_launch_key"] = (
        launch.semantic_key()
    )
    _rehash_world_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError):
        ReducedRunBackend().restore(snapshot)


def test_restore_rejects_second_combat_progress_reassigned_to_entry_slot() -> None:
    source = ReducedRunBackend()
    source.reset(_config())
    pre_combat_two = _to_pre_combat_two(source)
    entry = _choose_map_kind(source, pre_combat_two, "combat")
    snapshot = deepcopy(source.snapshot())
    assert snapshot["combat_entry_sequence"] == snapshot["decision_sequence"]

    child = _progress_combat_snapshot(snapshot)
    progressed = child.observe()
    assert child.get_resolution() is None
    snapshot["combat_snapshot"] = child.snapshot()
    snapshot["combat_entry_sequence"] -= 1
    _replace_snapshot_combat_boundary(snapshot, entry, progressed)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_restore_binds_config_seed_and_named_combat_rng_history() -> None:
    source = ReducedRunBackend()
    source.reset(_config())

    config_splice = deepcopy(source.snapshot())
    config_splice["config"]["game_seed"] = 8
    spliced_config = HeadlessRunConfig.from_dict(config_splice["config"])
    config_splice["outer_run_id"] = reduced_module._outer_run_id(
        spliced_config, config_splice["reset_generation"]
    )
    _rehash_snapshot(config_splice)
    with pytest.raises(ReducedRunBackendError):
        ReducedRunBackend().restore(config_splice)

    history_splice = deepcopy(source.snapshot())
    history_splice["private_world_snapshot"]["payload"]["rng"]["streams"][
        "combat_launch"
    ]["request_count"] += 1
    _rehash_world_snapshot(history_splice)
    with pytest.raises(ReducedRunBackendError):
        ReducedRunBackend().restore(history_splice)


def test_restore_rejects_pristine_rng_spliced_under_active_first_combat() -> None:
    source = ReducedRunBackend()
    source.reset(_config())
    snapshot = deepcopy(source.snapshot())
    snapshot["private_world_snapshot"]["payload"]["rng"] = GameRandomService(7).snapshot()
    _rehash_world_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError):
        ReducedRunBackend().restore(snapshot)


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


def test_injected_room_rule_error_under_same_public_conditions_rolls_back(
    monkeypatch,
) -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(
        _config(event_id="cool_spring", combat_settings={"enemy_max_hp": 1})
    )
    decision = _finish_combat(backend, decision)
    decision = _finish_reward(backend, decision)
    kind_by_reference = {
        node["node_ref"]: node["kind"] for node in decision.observation.data["nodes"]
    }
    event_candidate = next(
        item for item in decision.candidates
        if kind_by_reference[item.node_ref] == "event"
    )
    before = backend.snapshot()

    def injected_failure(*args, **kwargs):
        raise RoomRuleError("injected room failure")

    monkeypatch.setattr(reduced_module, "open_room", injected_failure)
    transition = backend.apply(_request(decision, event_candidate))
    assert transition.result is TransitionResult.REJECTED
    assert transition.reason is TransitionReason.REJECTED_BY_RULES
    assert transition.next_decision.to_json() == decision.to_json()
    assert backend.snapshot() == before


def test_restore_rejects_stop_reason_on_actionable_boundary() -> None:
    backend = ReducedRunBackend()
    backend.reset(_config())
    snapshot = deepcopy(backend.snapshot())
    snapshot["terminal_reason"] = "defeat"
    _rehash_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


@pytest.mark.parametrize("boundary", ("unsupported", "terminal"))
def test_restore_rejects_hidden_pending_decision_on_closed_boundary(boundary: str) -> None:
    if boundary == "unsupported":
        backend = ReducedRunBackend()
        decision = backend.reset(
            _config(event_id="cool_spring", combat_settings={"enemy_max_hp": 1})
        )
        decision = _finish_combat(backend, decision)
        decision = _finish_reward(backend, decision)
        valid_pending = deepcopy(
            backend.snapshot()["private_world_snapshot"]["payload"]["pending_decision"]
        )
        _choose_map_kind(backend, decision, "event")
    else:
        backend = ReducedRunBackend()
        backend.reset(_config())
        decision = _to_pre_combat_two(backend)
        decision = _choose_map_kind(backend, decision, "combat")
        decision = _finish_combat(backend, decision)
        decision = _finish_reward(backend, decision)
        valid_pending = deepcopy(
            backend.snapshot()["private_world_snapshot"]["payload"]["pending_decision"]
        )
        _choose_map_kind(backend, decision, "terminal")
    snapshot = deepcopy(backend.snapshot())
    snapshot["private_world_snapshot"]["payload"]["pending_decision"] = valid_pending
    _rehash_world_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_restore_rejects_route_terminal_history_without_terminal_tail() -> None:
    backend = ReducedRunBackend()
    backend.reset(_config(combat_settings={"enemy_max_hp": 1}))
    terminal = _finish_route(backend, _to_pre_combat_two(backend))
    assert terminal.status is DecisionStatus.TERMINAL
    snapshot = deepcopy(backend.snapshot())
    payload = snapshot["private_world_snapshot"]["payload"]
    payload["node_history"] = payload["node_history"][:-1]
    payload["current_node_id"] = _map_node_instance(snapshot, "combat_2")
    _rehash_world_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_restore_rejects_runtime_unsupported_moved_to_rest_node() -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(
        _config(event_id="cool_spring", combat_settings={"enemy_max_hp": 1})
    )
    decision = _finish_combat(backend, decision)
    decision = _finish_reward(backend, decision)
    decision = _choose_map_kind(backend, decision, "event")
    assert decision.status is DecisionStatus.UNSUPPORTED
    snapshot = deepcopy(backend.snapshot())
    payload = snapshot["private_world_snapshot"]["payload"]
    payload["node_history"][-1] = _map_node_instance(snapshot, "rest_1")
    payload["current_node_id"] = payload["node_history"][-1]
    _rehash_world_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_restore_rejects_defeat_history_after_noncombat_room() -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(_config(initial_hp=1))
    while decision.phase is DecisionPhase.COMBAT:
        decision = _apply_kind(backend, decision, CandidateKind.COMBAT_END_TURN)
    assert decision.status is DecisionStatus.TERMINAL
    restored = ReducedRunBackend().restore(deepcopy(backend.snapshot()))
    assert restored.to_json() == decision.to_json()

    snapshot = deepcopy(backend.snapshot())
    payload = snapshot["private_world_snapshot"]["payload"]
    payload["node_history"].append(_map_node_instance(snapshot, "rest_1"))
    payload["current_node_id"] = payload["node_history"][-1]
    _rehash_world_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_restore_rejects_terminal_map_event_forged_as_rest() -> None:
    backend = ReducedRunBackend()
    backend.reset(_config(combat_settings={"enemy_max_hp": 1}))
    terminal = _finish_route(backend, _to_pre_combat_two(backend))
    snapshot = deepcopy(backend.snapshot())
    events = (
        PublicEvent(
            0,
            PublicEventKind.MAP_NODE_CHOSEN,
            DecisionPhase.MAP,
            {"node_kind": "rest"},
        ),
        terminal.public_events[1],
    )
    _replace_snapshot_events(snapshot, terminal, events)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_restore_rejects_map_return_event_from_wrong_producer() -> None:
    backend = ReducedRunBackend()
    decision = _finish_combat(
        backend,
        backend.reset(_config(combat_settings={"enemy_max_hp": 1})),
    )
    decision = _finish_reward(backend, decision)
    assert decision.phase is DecisionPhase.MAP
    snapshot = deepcopy(backend.snapshot())
    events = (
        PublicEvent(
            0,
            PublicEventKind.ROOM_PROCEEDED,
            DecisionPhase.ROOM,
            {},
        ),
    )
    _replace_snapshot_events(snapshot, decision, events)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_restore_rejects_forged_victory_card_event_payload() -> None:
    backend = ReducedRunBackend()
    decision = _finish_combat(
        backend,
        backend.reset(_config(combat_settings={"enemy_max_hp": 1})),
    )
    assert decision.phase is DecisionPhase.REWARD
    assert decision.public_events[0].event_type is PublicEventKind.COMBAT_CARD_PLAYED
    snapshot = deepcopy(backend.snapshot())
    events = (
        PublicEvent(
            0,
            PublicEventKind.COMBAT_CARD_PLAYED,
            DecisionPhase.COMBAT,
            {
                "card_definition_id": "forged_card",
                "target_enemy_definition_id": None,
            },
        ),
        decision.public_events[1],
    )
    _replace_snapshot_events(snapshot, decision, events)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_restore_rejects_forged_defeat_terminal_action_event() -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(_config(initial_hp=1))
    while decision.phase is DecisionPhase.COMBAT:
        decision = _apply_kind(backend, decision, CandidateKind.COMBAT_END_TURN)
    assert decision.public_events[0].event_type is PublicEventKind.COMBAT_TURN_ENDED
    snapshot = deepcopy(backend.snapshot())
    events = (
        PublicEvent(
            0,
            PublicEventKind.COMBAT_CARD_PLAYED,
            DecisionPhase.COMBAT,
            {
                "card_definition_id": "forged_card",
                "target_enemy_definition_id": None,
            },
        ),
        *decision.public_events[1:],
    )
    _replace_snapshot_events(snapshot, decision, events)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


@pytest.mark.parametrize("boundary", ("victory", "defeat"))
def test_restore_requires_exact_outer_history_at_closed_combat_boundary(
    boundary: str,
) -> None:
    backend = ReducedRunBackend()
    if boundary == "victory":
        decision = _finish_combat(
            backend,
            backend.reset(_config(combat_settings={"enemy_max_hp": 1})),
        )
        assert decision.phase is DecisionPhase.REWARD
    else:
        decision = backend.reset(_config(initial_hp=1))
        while decision.phase is DecisionPhase.COMBAT:
            decision = _apply_kind(
                backend,
                decision,
                CandidateKind.COMBAT_END_TURN,
            )
        assert decision.status is DecisionStatus.TERMINAL

    snapshot = deepcopy(backend.snapshot())
    assert len(snapshot["accepted_outer_candidate_ids"]) == snapshot["decision_sequence"]
    restored = ReducedRunBackend()
    assert restored.restore(deepcopy(snapshot)).to_json() == decision.to_json()
    assert restored.snapshot() == snapshot

    snapshot["accepted_outer_candidate_ids"] = snapshot[
        "accepted_outer_candidate_ids"
    ][:-1]
    _rehash_snapshot(snapshot)
    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_snapshot_detaches_accepted_outer_history_from_caller_mutation() -> None:
    backend = ReducedRunBackend()
    decision = _finish_combat(
        backend,
        backend.reset(_config(combat_settings={"enemy_max_hp": 1})),
    )
    expected = backend.snapshot()
    detached = backend.snapshot()
    detached["accepted_outer_candidate_ids"].append(
        decision.candidates[0].candidate_id
    )

    assert backend.snapshot() == expected


def test_outer_history_append_rolls_back_exactly(monkeypatch) -> None:
    backend = ReducedRunBackend()
    decision = _finish_combat(
        backend,
        backend.reset(_config(combat_settings={"enemy_max_hp": 1})),
    )
    before = deepcopy(backend.snapshot())

    def fail_projection() -> DecisionState:
        raise RuntimeError("forced post-validation projection failure")

    monkeypatch.setattr(backend, "_project_current", fail_projection)
    transition = backend.apply(
        _request(decision, _candidate(decision, CandidateKind.REWARD_CLAIM_GOLD))
    )

    assert transition.result is TransitionResult.REJECTED
    assert transition.reason is TransitionReason.REJECTED_BY_RULES
    assert transition.next_decision.to_json() == decision.to_json()
    assert backend.snapshot() == before


def test_full_outer_history_replay_runs_only_during_snapshot_parse(
    monkeypatch,
) -> None:
    calls: list[int] = []
    original = ReducedRunBackend._validate_outer_action_history

    def tracked(backend: ReducedRunBackend) -> None:
        calls.append(backend._outer_sequence)
        original(backend)

    monkeypatch.setattr(
        ReducedRunBackend,
        "_validate_outer_action_history",
        tracked,
    )
    backend = ReducedRunBackend()
    decision = backend.reset(_config())
    decision = backend.apply(
        _request(decision, _combat_choice(decision))
    ).next_decision
    assert calls == []

    snapshot = deepcopy(backend.snapshot())
    restored = ReducedRunBackend()
    restored_decision = restored.restore(snapshot)
    assert calls == [1]
    assert restored_decision.to_json() == decision.to_json()


def test_restore_rejects_premature_event_effect_rng_draw() -> None:
    backend = ReducedRunBackend()
    backend.reset(_config())
    snapshot = deepcopy(backend.snapshot())
    payload = snapshot["private_world_snapshot"]["payload"]
    rng = GameRandomService(0)
    rng.restore(payload["rng"])
    rng.randint("event_effect", 0, 10)
    payload["rng"] = rng.snapshot()
    _rehash_world_snapshot(snapshot)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(snapshot)


def test_restore_rejects_rewound_reward_offer_and_clean_continuation_counts_two() -> None:
    backend = ReducedRunBackend()
    decision = _finish_combat(
        backend,
        backend.reset(_config(combat_settings={"enemy_max_hp": 1})),
    )
    decision = _finish_reward(backend, decision)
    assert backend.rng_stream_counters["reward_offer"] == 1
    clean = deepcopy(backend.snapshot())
    forged = deepcopy(clean)
    rng_streams = forged["private_world_snapshot"]["payload"]["rng"]["streams"]
    del rng_streams["reward_offer"]
    _rehash_world_snapshot(forged)

    with pytest.raises(ReducedRunBackendError, match="private boundary"):
        ReducedRunBackend().restore(forged)

    restored = ReducedRunBackend()
    decision = restored.restore(clean)
    decision = _choose_map_kind(restored, decision, "rest")
    if any(
        item.kind is CandidateKind.ROOM_REST_HEAL
        for item in decision.candidates
    ):
        decision = _apply_kind(
            restored,
            decision,
            CandidateKind.ROOM_REST_HEAL,
        )
    decision = _apply_kind(restored, decision, CandidateKind.ROOM_PROCEED)
    decision = _choose_map_kind(restored, decision, "combat")
    decision = _finish_combat(restored, decision)
    decision = _apply_kind(
        restored,
        decision,
        CandidateKind.REWARD_OPEN_CARD_REWARD,
    )
    assert restored.rng_stream_counters["reward_offer"] == 2


def test_outer_history_replay_rng_count_matrix_across_route_boundaries() -> None:
    def assert_counts(
        backend: ReducedRunBackend,
        *,
        combat_launch: int,
        reward_offer: int,
    ) -> None:
        assert backend.rng_stream_counters == {
            "combat_launch": combat_launch,
            "event_effect": 0,
            "reward_offer": reward_offer,
        }
        snapshot = backend.snapshot()
        assert len(snapshot["accepted_outer_candidate_ids"]) == snapshot[
            "decision_sequence"
        ]
        expected_streams = {"combat_launch"}
        if reward_offer:
            expected_streams.add("reward_offer")
        assert set(
            snapshot["private_world_snapshot"]["payload"]["rng"]["streams"]
        ) == expected_streams

    backend = ReducedRunBackend()
    decision = backend.reset(_config(combat_settings={"enemy_max_hp": 1}))
    assert_counts(backend, combat_launch=1, reward_offer=0)
    decision = _finish_combat(backend, decision)
    assert decision.phase is DecisionPhase.REWARD
    assert_counts(backend, combat_launch=1, reward_offer=0)
    decision = _apply_kind(
        backend,
        decision,
        CandidateKind.REWARD_OPEN_CARD_REWARD,
    )
    assert_counts(backend, combat_launch=1, reward_offer=1)
    decision = _finish_reward(backend, decision)
    assert decision.phase is DecisionPhase.MAP
    assert_counts(backend, combat_launch=1, reward_offer=1)
    decision = _choose_map_kind(backend, decision, "rest")
    assert_counts(backend, combat_launch=1, reward_offer=1)
    if any(item.kind is CandidateKind.ROOM_REST_HEAL for item in decision.candidates):
        decision = _apply_kind(backend, decision, CandidateKind.ROOM_REST_HEAL)
    decision = _apply_kind(backend, decision, CandidateKind.ROOM_PROCEED)
    decision = _choose_map_kind(backend, decision, "combat")
    assert decision.phase is DecisionPhase.COMBAT
    assert_counts(backend, combat_launch=2, reward_offer=1)
    decision = _finish_combat(backend, decision)
    assert decision.phase is DecisionPhase.REWARD
    assert_counts(backend, combat_launch=2, reward_offer=1)
    decision = _apply_kind(
        backend,
        decision,
        CandidateKind.REWARD_OPEN_CARD_REWARD,
    )
    assert_counts(backend, combat_launch=2, reward_offer=2)
    decision = _finish_reward(backend, decision)
    decision = _choose_map_kind(backend, decision, "terminal")
    assert decision.status is DecisionStatus.TERMINAL
    assert_counts(backend, combat_launch=2, reward_offer=2)

    defeat = ReducedRunBackend()
    decision = defeat.reset(_config(initial_hp=1))
    while decision.phase is DecisionPhase.COMBAT:
        decision = _apply_kind(
            defeat,
            decision,
            CandidateKind.COMBAT_END_TURN,
        )
    assert decision.status is DecisionStatus.TERMINAL
    assert_counts(defeat, combat_launch=1, reward_offer=0)

    unsupported = ReducedRunBackend()
    decision = unsupported.reset(
        _config(event_id="cool_spring", combat_settings={"enemy_max_hp": 1})
    )
    decision = _finish_reward(unsupported, _finish_combat(unsupported, decision))
    decision = _choose_map_kind(unsupported, decision, "event")
    assert decision.status is DecisionStatus.UNSUPPORTED
    assert_counts(unsupported, combat_launch=1, reward_offer=1)
