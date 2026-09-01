"""Structural-fixture tests for reduced rest and safe-event room rules."""

from __future__ import annotations

from copy import deepcopy

import pytest

from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import (
    MAX_PUBLIC_COUNTER,
    ContractValidationError,
    DecisionPhase,
    NodeKind,
    PublicReferenceKind,
    PublicScope,
    RoomEventOptionCandidate,
    RoomKind,
    RoomProceedCandidate,
    RoomRestHealCandidate,
)
from game.engine.headless_state import PendingDecision, WorldState
from game.engine.room_rules import (
    ROOM_RULES_ACTION_TRUST_BOUNDARY,
    ROOM_RULES_EVIDENCE,
    ROOM_RULES_FINGERPRINT,
    ROOM_RULES_VERSION,
    RoomRuleError,
    UnsupportedRoomContentError,
    apply_room_candidate,
    open_room,
    room_candidates,
    room_public_observation,
)
from game.engine.snapshots import WorldSnapshotCodec


def _world(*, hp: int = 68, gold: int = 99, seed: int = 71) -> WorldState:
    return WorldState.create(
        seed=seed,
        current_hp=hp,
        max_hp=80,
        gold=gold,
        deck_definition_ids=("strike", "defend"),
        map_node_definitions=(("rest_1", NodeKind.REST), ("event_1", NodeKind.EVENT)),
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_fingerprint=ROOM_RULES_FINGERPRINT,
        phase=DecisionPhase.ROOM,
    )


def _scope(decision: int = 4, option: int = 0) -> PublicScope:
    reveals = {kind.value: 0 for kind in PublicReferenceKind}
    reveals[PublicReferenceKind.OPTION.value] = option
    return PublicScope(history_ordinal=2, decision_ordinal=decision, reveal_ordinals=reveals)


def _open_rest(world: WorldState) -> None:
    open_room(world, RoomKind.REST, decision_sequence=4, public_scope=_scope())


def _open_event(world: WorldState, event_id: str = "quiet_cache") -> None:
    open_room(
        world,
        RoomKind.EVENT,
        event_id=event_id,
        decision_sequence=4,
        public_scope=_scope(),
    )


def test_rest_candidates_are_complete_heal_is_capped_and_then_only_proceed() -> None:
    world = _world(hp=72)
    _open_rest(world)

    observation = room_public_observation(world, _scope())
    candidates = room_candidates(world, _scope())

    assert ROOM_RULES_VERSION == "reduced_room_rules_v0"
    assert ROOM_RULES_EVIDENCE == "structural_fixture"
    assert ROOM_RULES_ACTION_TRUST_BOUNDARY == (
        "internal_after_headless_binding_authentication_v1"
    )
    assert observation.data == {
        "room_kind": "rest",
        "player": {"deck_size": 2, "gold": 99, "hp": 72, "max_hp": 80},
        "options": ({
            "option_ref": observation.data["options"][0]["option_ref"],
            "kind": "rest_heal", "effect": "heal", "amount": 15, "enabled": True,
        },),
        "can_proceed": False,
    }
    assert len(candidates) == 1 and isinstance(candidates[0], RoomRestHealCandidate)
    assert candidates[0].heal_amount == 15

    result = apply_room_candidate(world, _scope(), candidates[0])
    assert world.current_hp == 80
    assert result.completed is False
    assert result.public_events[0].to_dict() == {
        "sequence": 0, "event_type": "room.rest_healed", "phase": "room", "data": {"amount": 8},
    }
    assert room_public_observation(world, _scope(decision=5)).data["options"] == ()
    afterwards = room_candidates(world, _scope(decision=5))
    assert len(afterwards) == 1 and isinstance(afterwards[0], RoomProceedCandidate)

    completed = apply_room_candidate(world, _scope(decision=5), afterwards[0])
    assert completed.completed is True
    assert world.phase is DecisionPhase.MAP and world.pending_decision is None
    assert completed.public_events[0].event_type.value == "room.proceeded"


@pytest.mark.parametrize(
    ("event_id", "initial_hp", "initial_gold", "expected_hp", "expected_gold", "effect", "amount"),
    [
        ("quiet_cache", 68, 99, 68, 119, "gain_gold", 20),
        ("cool_spring", 76, 99, 80, 99, "heal", 4),
    ],
)
def test_whitelisted_safe_event_option_then_proceed(
    event_id: str,
    initial_hp: int,
    initial_gold: int,
    expected_hp: int,
    expected_gold: int,
    effect: str,
    amount: int,
) -> None:
    world = _world(hp=initial_hp, gold=initial_gold)
    _open_event(world, event_id)

    observation = room_public_observation(world, _scope())
    candidates = room_candidates(world, _scope())
    assert observation.data["room_kind"] == "event"
    assert "event_id" not in observation.data
    assert len(candidates) == 1 and isinstance(candidates[0], RoomEventOptionCandidate)
    assert observation.data["options"][0]["effect"] == effect

    result = apply_room_candidate(world, _scope(), candidates[0])
    assert world.current_hp == expected_hp and world.gold == expected_gold
    assert result.public_events[0].data == {"effect": effect, "amount": amount}
    proceed = room_candidates(world, _scope(decision=5))
    assert len(proceed) == 1 and isinstance(proceed[0], RoomProceedCandidate)
    assert apply_room_candidate(world, _scope(decision=5), proceed[0]).completed is True


def test_full_hp_rest_exposes_only_proceed() -> None:
    world = _world(hp=80)
    _open_rest(world)

    observation = room_public_observation(world, _scope())
    candidates = room_candidates(world, _scope())
    assert observation.data["options"] == ()
    assert observation.data["can_proceed"] is True
    assert len(candidates) == 1 and isinstance(candidates[0], RoomProceedCandidate)


def test_invalid_or_stale_candidate_is_atomic_and_does_not_advance_rng() -> None:
    world = _world(hp=70)
    _open_rest(world)
    before = deepcopy(world.to_private_dict())
    stale = room_candidates(world, _scope())[0]

    with pytest.raises(RoomRuleError, match="does not bind"):
        apply_room_candidate(world, _scope(decision=5), stale)
    with pytest.raises(RoomRuleError, match="not a room candidate"):
        apply_room_candidate(world, _scope(), object())  # type: ignore[arg-type]

    assert world.to_private_dict() == before
    assert world.rng_stream_counters() == {"combat_launch": 0, "event_effect": 0, "reward_offer": 0}


def test_unsupported_content_and_malformed_private_context_fail_closed_without_mutation() -> None:
    world = _world()
    before = deepcopy(world.to_private_dict())
    with pytest.raises(UnsupportedRoomContentError, match="allowlist"):
        _open_event(world, "dangerous_custom")
    assert world.to_private_dict() == before

    _open_event(world)
    before = deepcopy(world.to_private_dict())
    pending = world.pending_decision
    assert pending is not None
    world.pending_decision = PendingDecision(
        pending.decision_kind,
        pending.sequence,
        {
            "room_kind": "event",
            "event_id": "unknown",
            "state": "ready",
            "public_scope": _scope().to_dict(),
        },
    )
    with pytest.raises(UnsupportedRoomContentError, match="unsupported event"):
        room_public_observation(world, _scope())
    assert world.current_hp == before["current_hp"]
    assert world.gold == before["gold"]


def test_snapshot_restore_continues_room_and_preserves_exact_event_stream_counter() -> None:
    world = _world(seed=83)
    _open_event(world, "quiet_cache")
    # Simulate an earlier approved structural stochastic event; the room rules
    # must preserve it and must not consume any additional named stream request
    # for the current deterministic safe events.
    world.rng.randint("event_effect", 0, 99)
    codec = WorldSnapshotCodec(CONTENT_FINGERPRINT, ROOM_RULES_FINGERPRINT)
    snapshot = codec.capture(world)
    candidate = room_candidates(world, _scope())[0]
    direct = apply_room_candidate(world, _scope(), candidate)
    direct_state = world.to_private_dict()

    restored = codec.restore(snapshot)
    restored_candidate = room_candidates(restored, _scope())[0]
    replayed = apply_room_candidate(restored, _scope(), restored_candidate)
    assert replayed == direct
    assert restored.to_private_dict() == direct_state
    assert restored.rng_stream_counters()["event_effect"] == 1


def test_public_projection_excludes_private_event_identity_pending_state_and_rng() -> None:
    world = _world()
    _open_event(world, "quiet_cache")
    world.rng.randint("event_effect", 0, 9)
    public = room_public_observation(world, _scope()).to_dict()
    rendered = repr(public)

    assert "quiet_cache" not in rendered
    assert "event_id" not in rendered
    assert "pending_decision" not in rendered
    assert "rng" not in rendered
    assert "seed" not in rendered


def test_room_actions_do_not_perturb_other_named_streams() -> None:
    world = _world()
    world.rng.randint("combat_launch", 0, 9)
    world.rng.randint("reward_offer", 0, 9)
    before = world.rng_stream_counters()
    _open_event(world, "cool_spring")
    event = room_candidates(world, _scope())[0]
    apply_room_candidate(world, _scope(), event)

    assert world.rng_stream_counters() == before


def test_public_scope_and_candidate_bind_to_the_pending_sequence() -> None:
    world = _world(hp=70)
    _open_rest(world)
    before = deepcopy(world.to_private_dict())
    current_scope = _scope()
    candidate = room_candidates(world, current_scope)[0]

    with pytest.raises(RoomRuleError, match="does not bind"):
        room_candidates(world, _scope(decision=5))
    with pytest.raises(RoomRuleError, match="does not bind"):
        open_room(
            _world(),
            RoomKind.REST,
            decision_sequence=4,
            public_scope=_scope(decision=5),
        )
    forged = RoomRestHealCandidate(
        _scope(decision=5).decision_scope,
        candidate.option_ref,
        candidate.heal_amount,
    )
    with pytest.raises(RoomRuleError, match="not currently legal"):
        apply_room_candidate(world, current_scope, forged)
    assert world.to_private_dict() == before

    apply_room_candidate(world, current_scope, candidate)
    pending = world.pending_decision
    assert pending is not None
    assert pending.sequence == 5
    assert PublicScope.from_dict(pending.private_context["public_scope"]) == _scope(decision=5)
    assert len(room_candidates(world, _scope(decision=5))) == 1


def test_post_mutation_validation_failure_restores_the_exact_world(monkeypatch: pytest.MonkeyPatch) -> None:
    world = _world(hp=70)
    _open_rest(world)
    before = deepcopy(world.to_private_dict())
    candidate = room_candidates(world, _scope())[0]
    original_validate = WorldState.validate

    def reject_resolved_state(self: WorldState) -> None:
        original_validate(self)
        pending = self.pending_decision
        if (
            self.current_hp == 80
            and pending is not None
            and pending.private_context["state"] == "resolved"
        ):
            raise RuntimeError("forced post-mutation validation failure")

    monkeypatch.setattr(WorldState, "validate", reject_resolved_state)
    with pytest.raises(RuntimeError, match="forced post-mutation"):
        apply_room_candidate(world, _scope(), candidate)
    monkeypatch.setattr(WorldState, "validate", original_validate)

    assert world.to_private_dict() == before


def test_persisted_scope_ordinal_must_match_pending_sequence() -> None:
    world = _world()
    _open_event(world)
    pending = world.pending_decision
    assert pending is not None
    world.pending_decision = PendingDecision(
        pending.decision_kind,
        99,
        dict(pending.private_context),
    )
    before = deepcopy(world.to_private_dict())

    with pytest.raises(RoomRuleError, match="Persisted public scope does not bind"):
        room_public_observation(world, _scope())

    assert world.to_private_dict() == before


def test_room_opening_rejects_exhausted_public_ordinal_before_advertising() -> None:
    world = _world(hp=70)
    before = deepcopy(world.to_private_dict())
    exhausted_scope = _scope(decision=MAX_PUBLIC_COUNTER)

    with pytest.raises(RoomRuleError, match="cannot advance"):
        open_room(
            world,
            RoomKind.REST,
            decision_sequence=MAX_PUBLIC_COUNTER,
            public_scope=exhausted_scope,
        )

    assert world.to_private_dict() == before

    last_advance = _world(hp=70)
    penultimate_scope = _scope(decision=MAX_PUBLIC_COUNTER - 1)
    open_room(
        last_advance,
        RoomKind.REST,
        decision_sequence=MAX_PUBLIC_COUNTER - 1,
        public_scope=penultimate_scope,
    )
    heal = room_candidates(last_advance, penultimate_scope)[0]
    apply_room_candidate(last_advance, penultimate_scope, heal)
    pending = last_advance.pending_decision
    assert pending is not None and pending.sequence == MAX_PUBLIC_COUNTER
    final_scope = _scope(decision=MAX_PUBLIC_COUNTER)
    proceed = room_candidates(last_advance, final_scope)
    assert len(proceed) == 1 and isinstance(proceed[0], RoomProceedCandidate)


def test_gold_event_overflow_fails_before_candidate_advertisement() -> None:
    world = _world(gold=MAX_PUBLIC_COUNTER - 10)
    before = deepcopy(world.to_private_dict())

    with pytest.raises(RoomRuleError, match="public counter bound"):
        _open_event(world, "quiet_cache")

    assert world.to_private_dict() == before
    assert world.pending_decision is None
    with pytest.raises(RoomRuleError, match="No room decision"):
        room_candidates(world, _scope())


def test_gold_event_at_exact_public_bound_remains_sound() -> None:
    world = _world(gold=MAX_PUBLIC_COUNTER - 20)
    _open_event(world, "quiet_cache")
    candidate = room_candidates(world, _scope())[0]

    transition = apply_room_candidate(world, _scope(), candidate)

    assert world.gold == MAX_PUBLIC_COUNTER
    assert transition.public_events[0].data == {"effect": "gain_gold", "amount": 20}
    assert len(room_candidates(world, _scope(decision=5))) == 1


def test_full_hp_healing_event_fails_closed_before_candidate_advertisement() -> None:
    world = _world(hp=80)
    before = deepcopy(world.to_private_dict())

    with pytest.raises(RoomRuleError, match="no contract-valid effect"):
        _open_event(world, "cool_spring")

    assert world.to_private_dict() == before
    assert world.pending_decision is None


def test_open_room_rolls_back_when_initial_public_boundary_is_unprojectable() -> None:
    world = _world(gold=MAX_PUBLIC_COUNTER + 1)
    before = deepcopy(world.to_private_dict())

    with pytest.raises(ContractValidationError, match="public_observation.data.player.gold"):
        _open_rest(world)

    assert world.to_private_dict() == before
    assert world.pending_decision is None
