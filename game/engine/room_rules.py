"""Reduced structural rules for supported rest sites and safe events.

This module owns only room-local progression over the accepted private
``WorldState`` kernel.  It is intentionally not a backend: decision bindings,
map traversal, snapshots, and terminal composition remain the responsibility of
their respective owners.  The sole public surface is made from the frozen
``headless_v0`` observation, candidate, and event records.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, TypeVar

from game.content.reduced_v0 import REST_HEAL_PARAMETERS, SAFE_EVENT_DEFINITIONS
from game.contracts.headless_v0 import (
    DecisionPhase,
    MAX_PUBLIC_COUNTER,
    PublicEvent,
    PublicEventKind,
    PublicObservation,
    PublicReferenceKind,
    PublicScope,
    RoomEffectKind,
    RoomEventOptionCandidate,
    RoomKind,
    RoomOptionKind,
    RoomProceedCandidate,
    RoomRestHealCandidate,
    TypedCandidate,
    room_option_reference,
)
from game.engine.headless_state import PendingDecision, StateValidationError, WorldState


ROOM_RULES_VERSION = "reduced_room_rules_v0"
ROOM_RULES_EVIDENCE = "structural_fixture"
ROOM_DECISION_KIND = "room_action"
ROOM_RULES_ACTION_TRUST_BOUNDARY = "internal_after_headless_binding_authentication_v1"

_CONTEXT_FIELDS = frozenset(
    {
        "event_id",
        "opening_baseline",
        "public_scope",
        "resolved_receipt",
        "room_kind",
        "state",
    }
)
_OPENING_BASELINE_FIELDS = frozenset(
    {"current_hp", "gold", "max_hp", "public_scope", "sequence"}
)
_RESOLVED_RECEIPT_FIELDS = frozenset({"amount", "effect"})
_READY = "ready"
_RESOLVED = "resolved"
_RULES_DESCRIPTOR = {
    "version": ROOM_RULES_VERSION,
    "decision_binding": "exact_pending_public_scope_and_sequence_v1",
    "action_trust_boundary": ROOM_RULES_ACTION_TRUST_BOUNDARY,
    "initial_boundary_validation": "observation_and_candidates_before_commit_v1",
    "maximum_open_sequence": MAX_PUBLIC_COUNTER - 1,
    "next_boundary_validation": "event_and_observation_before_commit_v1",
    "private_state_invariant": "opening_baseline_plus_exact_resolved_effect_receipt_v1",
    "rest": {"heal_amount": REST_HEAL_PARAMETERS.heal_amount, "one_use": True},
    "resolved_proceed_sequence": "increment_one",
    "safe_events": [item.to_dict() for item in SAFE_EVENT_DEFINITIONS],
    "stochastic_effects": [],
}
ROOM_RULES_FINGERPRINT = sha256(
    json.dumps(_RULES_DESCRIPTOR, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


class RoomRuleError(ValueError):
    """Raised when a room operation is invalid for the current private state."""


class UnsupportedRoomContentError(RoomRuleError):
    """Raised for room content outside the closed reduced structural fixture."""


@dataclass(frozen=True, slots=True)
class RoomTransition:
    """The result of one accepted room candidate application."""

    completed: bool
    public_events: tuple[PublicEvent, ...]


_SAFE_EVENTS_BY_ID = {item.event_id: item for item in SAFE_EVENT_DEFINITIONS}
T = TypeVar("T")


def open_room(
    world: WorldState,
    room_kind: RoomKind | str,
    *,
    decision_sequence: int,
    public_scope: PublicScope,
    event_id: str | None = None,
) -> None:
    """Open one supported room at an already-entered ``ROOM`` boundary.

    ``event_id`` is private room configuration.  Safe event identity is not
    exposed in the public room observation, which contains only its declared
    option effect and amount.
    """

    _require_world(world)
    try:
        kind = RoomKind(room_kind)
    except (TypeError, ValueError) as error:
        raise UnsupportedRoomContentError("Unsupported room kind.") from error
    if world.phase is not DecisionPhase.ROOM:
        raise RoomRuleError("Rooms can only open from the room phase.")
    if world.pending_decision is not None:
        raise RoomRuleError("A room decision is already pending.")
    if not isinstance(decision_sequence, int) or isinstance(decision_sequence, bool) or decision_sequence < 0:
        raise RoomRuleError("decision_sequence must be a nonnegative integer.")
    if not isinstance(public_scope, PublicScope):
        raise TypeError("public_scope must be a PublicScope.")
    if public_scope.decision_ordinal != decision_sequence:
        raise RoomRuleError("Room public scope does not bind to decision_sequence.")
    if decision_sequence >= MAX_PUBLIC_COUNTER:
        raise RoomRuleError("Room decision sequence cannot advance to a proceed boundary.")

    if kind is RoomKind.REST:
        if event_id is not None:
            raise UnsupportedRoomContentError("Rest rooms cannot name an event.")
    else:
        if not isinstance(event_id, str) or event_id not in _SAFE_EVENTS_BY_ID:
            raise UnsupportedRoomContentError("Event is not in the safe-event allowlist.")
        _validate_event_effect_available(world, _SAFE_EVENTS_BY_ID[event_id])

    _mutate_atomically(
        world,
        lambda: _open_and_validate_room(
            world,
            decision_sequence,
            kind.value,
            event_id,
            _READY,
            public_scope,
        ),
    )


def room_public_observation(world: WorldState, public_scope: PublicScope) -> PublicObservation:
    """Project exactly the room data permitted to a chooser or future model."""

    context = _room_context(world)
    if not isinstance(public_scope, PublicScope):
        raise TypeError("public_scope must be a PublicScope.")
    _require_bound_scope(context, public_scope)
    room_kind = RoomKind(context["room_kind"])
    state = context["state"]
    options = _public_options(world, room_kind, context, public_scope, state)
    return PublicObservation(
        phase=DecisionPhase.ROOM,
        public_scope=public_scope,
        data={
            "room_kind": room_kind.value,
            "player": _public_player(world),
            "options": options,
            "can_proceed": state == _RESOLVED or (room_kind is RoomKind.REST and not options),
        },
    )


def room_candidates(
    world: WorldState,
    public_scope: PublicScope,
) -> tuple[RoomRestHealCandidate | RoomEventOptionCandidate | RoomProceedCandidate, ...]:
    """Return all and only currently legal room actions in canonical ID order."""

    observation = room_public_observation(world, public_scope)
    candidates: list[
        RoomRestHealCandidate | RoomEventOptionCandidate | RoomProceedCandidate
    ] = []
    for option in observation.data["options"]:
        if not option["enabled"]:
            continue
        if option["kind"] == RoomOptionKind.REST_HEAL.value:
            candidates.append(
                RoomRestHealCandidate(
                    observation.public_scope.decision_scope,
                    option["option_ref"],
                    option["amount"],
                )
            )
        else:
            candidates.append(
                RoomEventOptionCandidate(
                    observation.public_scope.decision_scope,
                    option["option_ref"],
                )
            )
    if observation.data["can_proceed"]:
        candidates.append(RoomProceedCandidate(observation.public_scope.decision_scope))
    return tuple(sorted(candidates, key=lambda item: item.candidate_id))


def apply_room_candidate(
    world: WorldState,
    public_scope: PublicScope,
    candidate: TypedCandidate,
) -> RoomTransition:
    """Apply one advertised candidate at the internal room-component seam.

    This helper checks exact candidate membership and the persisted public scope,
    but a ``TypedCandidate`` intentionally carries no run ID or decision hash.
    The composing ``HeadlessBackend`` must authenticate the complete
    ``ActionRequest``/``HeadlessBinding`` before invoking this function.  This
    helper is not itself an authenticated backend operation.
    """

    if type(candidate) not in (
        RoomRestHealCandidate,
        RoomEventOptionCandidate,
        RoomProceedCandidate,
    ):
        raise RoomRuleError("Candidate is not a room candidate.")
    context = _room_context(world)
    legal = room_candidates(world, public_scope)
    if candidate not in legal:
        raise RoomRuleError("Candidate is not currently legal for this room decision.")

    room_kind = RoomKind(context["room_kind"])
    if isinstance(candidate, RoomProceedCandidate):
        # Room completion is the local handoff boundary.  The composer decides
        # which map decision follows; it receives a normal MAP phase with no
        # lingering private room configuration.
        return _mutate_atomically(
            world,
            lambda: _apply_proceed_transition(world),
        )

    if isinstance(candidate, RoomRestHealCandidate):
        if room_kind is not RoomKind.REST:
            raise RoomRuleError("Rest healing is unavailable in this room.")
        applied = min(candidate.heal_amount, world.max_hp - world.current_hp)
        if applied <= 0:
            raise RoomRuleError("Rest healing is unavailable at full HP.")
        # The candidate was validated against the declared content amount.  The
        # emitted amount records the capped persistent delta instead.
        return _mutate_atomically(
            world,
            lambda: _apply_rest_heal_transition(world, context, applied),
        )

    if room_kind is not RoomKind.EVENT:
        raise RoomRuleError("Event options are unavailable in this room.")
    event = _event_from_context(context)
    effect = RoomEffectKind(event.effect_kind)
    amount = event.amount
    return _mutate_atomically(
        world,
        lambda: _apply_event_option_transition(world, context, effect, amount),
    )


def _require_world(world: WorldState) -> None:
    if not isinstance(world, WorldState):
        raise TypeError("world must be a WorldState.")
    try:
        world.validate()
    except StateValidationError as error:
        raise RoomRuleError("World state is invalid.") from error


def _room_context(world: WorldState) -> dict[str, Any]:
    _require_world(world)
    if world.phase is not DecisionPhase.ROOM:
        raise RoomRuleError("World is not at a room decision boundary.")
    pending = world.pending_decision
    if pending is None or pending.decision_kind != ROOM_DECISION_KIND:
        raise RoomRuleError("No room decision is pending.")
    context = dict(pending.private_context)
    if set(context) != _CONTEXT_FIELDS:
        raise RoomRuleError("Room decision context has an incompatible schema.")
    if context["state"] not in {_READY, _RESOLVED}:
        raise RoomRuleError("Room decision has an invalid state.")
    try:
        room_kind = RoomKind(context["room_kind"])
    except (TypeError, ValueError) as error:
        raise RoomRuleError("Room decision names an unsupported room kind.") from error
    event_id = context["event_id"]
    try:
        stored_scope = PublicScope.from_dict(context["public_scope"])
    except Exception as error:
        raise RoomRuleError("Room decision has an invalid public scope binding.") from error
    if stored_scope.decision_ordinal != pending.sequence:
        raise RoomRuleError("Persisted public scope does not bind to pending sequence.")
    if room_kind is RoomKind.REST and event_id is not None:
        raise RoomRuleError("Rest decision contains an event identifier.")
    if room_kind is RoomKind.EVENT and (
        not isinstance(event_id, str) or event_id not in _SAFE_EVENTS_BY_ID
    ):
        raise UnsupportedRoomContentError("Room decision names unsupported event content.")
    baseline = _opening_baseline_from_context(context)
    opening_scope = PublicScope.from_dict(baseline["public_scope"])
    if opening_scope.decision_ordinal != baseline["sequence"]:
        raise RoomRuleError("Opening public scope does not bind to opening sequence.")
    if context["state"] == _READY:
        if pending.sequence != baseline["sequence"] or stored_scope != opening_scope:
            raise RoomRuleError("Ready room decision does not match its opening identity.")
        if context["resolved_receipt"] is not None:
            raise RoomRuleError("Ready room decision cannot contain an effect receipt.")
        _require_exact_player_baseline(world, baseline)
    else:
        expected_scope = _next_public_scope(opening_scope)
        if pending.sequence != baseline["sequence"] + 1 or stored_scope != expected_scope:
            raise RoomRuleError("Resolved room decision does not follow its opening identity.")
        _validate_resolved_effect(world, room_kind, event_id, baseline, context)
    return context


def _opening_baseline_from_context(context: Mapping[str, Any]) -> dict[str, Any]:
    baseline = context["opening_baseline"]
    if not isinstance(baseline, Mapping) or set(baseline) != _OPENING_BASELINE_FIELDS:
        raise RoomRuleError("Room opening baseline has an incompatible schema.")
    current_hp = _require_nonnegative_private_int(
        baseline["current_hp"], "opening_baseline.current_hp"
    )
    max_hp = _require_nonnegative_private_int(
        baseline["max_hp"], "opening_baseline.max_hp"
    )
    gold = _require_nonnegative_private_int(
        baseline["gold"], "opening_baseline.gold"
    )
    sequence = _require_nonnegative_private_int(
        baseline["sequence"], "opening_baseline.sequence"
    )
    if max_hp <= 0 or current_hp > max_hp:
        raise RoomRuleError("Room opening baseline has invalid HP.")
    if sequence >= MAX_PUBLIC_COUNTER:
        raise RoomRuleError("Room opening baseline cannot advance to proceed.")
    public_scope = baseline["public_scope"]
    if not isinstance(public_scope, Mapping):
        raise RoomRuleError("Room opening baseline public scope must be an object.")
    try:
        normalized_scope = PublicScope.from_dict(public_scope)
    except Exception as error:
        raise RoomRuleError("Room opening baseline has an invalid public scope.") from error
    return {
        "current_hp": current_hp,
        "gold": gold,
        "max_hp": max_hp,
        "public_scope": normalized_scope.to_dict(),
        "sequence": sequence,
    }


def _require_nonnegative_private_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RoomRuleError(f"{path} must be a nonnegative integer.")
    return value


def _require_exact_player_baseline(
    world: WorldState,
    baseline: Mapping[str, Any],
) -> None:
    if (
        world.current_hp != baseline["current_hp"]
        or world.max_hp != baseline["max_hp"]
        or world.gold != baseline["gold"]
    ):
        raise RoomRuleError("Ready room state differs from its opening baseline.")


def _validate_resolved_effect(
    world: WorldState,
    room_kind: RoomKind,
    event_id: str | None,
    baseline: Mapping[str, Any],
    context: Mapping[str, Any],
) -> None:
    receipt = context["resolved_receipt"]
    if not isinstance(receipt, Mapping) or set(receipt) != _RESOLVED_RECEIPT_FIELDS:
        raise RoomRuleError("Resolved room decision requires an exact effect receipt.")
    try:
        receipt_effect = RoomEffectKind(receipt["effect"])
    except (TypeError, ValueError) as error:
        raise RoomRuleError("Resolved room receipt names an invalid effect.") from error
    receipt_amount = _require_nonnegative_private_int(
        receipt["amount"], "resolved_receipt.amount"
    )
    expected_effect, expected_amount, expected_hp, expected_gold = (
        _expected_resolved_effect(room_kind, event_id, baseline)
    )
    if receipt_effect is not expected_effect or receipt_amount != expected_amount:
        raise RoomRuleError("Resolved room receipt does not match its allowlisted effect.")
    if (
        world.current_hp != expected_hp
        or world.max_hp != baseline["max_hp"]
        or world.gold != expected_gold
    ):
        raise RoomRuleError("Resolved room state does not match its effect receipt.")


def _expected_resolved_effect(
    room_kind: RoomKind,
    event_id: str | None,
    baseline: Mapping[str, Any],
) -> tuple[RoomEffectKind, int, int, int]:
    opening_hp = baseline["current_hp"]
    max_hp = baseline["max_hp"]
    opening_gold = baseline["gold"]
    if room_kind is RoomKind.REST:
        effect = RoomEffectKind.HEAL
        declared_amount = REST_HEAL_PARAMETERS.heal_amount
    else:
        event = _SAFE_EVENTS_BY_ID[event_id]
        effect = RoomEffectKind(event.effect_kind)
        declared_amount = event.amount

    expected_hp = opening_hp
    expected_gold = opening_gold
    if effect is RoomEffectKind.HEAL:
        applied = min(declared_amount, max_hp - opening_hp)
        expected_hp += applied
    elif effect is RoomEffectKind.GAIN_GOLD:
        applied = declared_amount
        expected_gold += applied
    elif effect is RoomEffectKind.LOSE_HP:
        applied = min(declared_amount, opening_hp)
        expected_hp -= applied
    else:
        raise UnsupportedRoomContentError("Safe event names an unsupported effect.")
    if applied <= 0:
        raise RoomRuleError("Resolved room effect must produce a positive delta.")
    return effect, applied, expected_hp, expected_gold


def _next_public_scope(public_scope: PublicScope) -> PublicScope:
    return PublicScope(
        history_ordinal=public_scope.history_ordinal,
        decision_ordinal=public_scope.decision_ordinal + 1,
        reveal_ordinals=public_scope.reveal_ordinals,
    )


def _require_bound_scope(context: Mapping[str, Any], public_scope: PublicScope) -> None:
    expected = PublicScope.from_dict(context["public_scope"])
    if public_scope != expected:
        raise RoomRuleError("Public scope does not bind to the pending room decision.")


def _set_pending_room_decision(
    world: WorldState,
    sequence: int,
    room_kind: str,
    event_id: str | None,
    state: str,
    public_scope: PublicScope,
    opening_baseline: Mapping[str, Any],
    resolved_receipt: Mapping[str, Any] | None,
) -> None:
    world.pending_decision = PendingDecision(
        ROOM_DECISION_KIND,
        sequence,
        {
            "room_kind": room_kind,
            "event_id": event_id,
            "opening_baseline": opening_baseline,
            "state": state,
            "public_scope": public_scope.to_dict(),
            "resolved_receipt": resolved_receipt,
        },
    )


def _open_and_validate_room(
    world: WorldState,
    sequence: int,
    room_kind: str,
    event_id: str | None,
    state: str,
    public_scope: PublicScope,
) -> None:
    opening_baseline = {
        "current_hp": world.current_hp,
        "gold": world.gold,
        "max_hp": world.max_hp,
        "public_scope": public_scope.to_dict(),
        "sequence": sequence,
    }
    _set_pending_room_decision(
        world,
        sequence,
        room_kind,
        event_id,
        state,
        public_scope,
        opening_baseline,
        None,
    )
    room_candidates(world, public_scope)


def _complete_room(world: WorldState) -> None:
    world.pending_decision = None
    world.phase = DecisionPhase.MAP


def _apply_proceed_transition(world: WorldState) -> RoomTransition:
    _complete_room(world)
    return RoomTransition(
        completed=True,
        public_events=(
            PublicEvent(0, PublicEventKind.ROOM_PROCEEDED, DecisionPhase.ROOM, {}),
        ),
    )


def _apply_rest_heal_transition(
    world: WorldState,
    context: Mapping[str, Any],
    applied: int,
) -> RoomTransition:
    world.current_hp += applied
    _mark_resolved(world, context, RoomEffectKind.HEAL, applied)
    transition = RoomTransition(
        completed=False,
        public_events=(
            PublicEvent(
                0,
                PublicEventKind.ROOM_REST_HEALED,
                DecisionPhase.ROOM,
                {"amount": applied},
            ),
        ),
    )
    _validate_next_room_boundary(world)
    return transition


def _apply_event_option_transition(
    world: WorldState,
    context: Mapping[str, Any],
    effect: RoomEffectKind,
    amount: int,
) -> RoomTransition:
    applied = _apply_event_effect(world, effect, amount)
    _mark_resolved(world, context, effect, applied)
    transition = RoomTransition(
        completed=False,
        public_events=(
            PublicEvent(
                0,
                PublicEventKind.ROOM_EVENT_OPTION_CHOSEN,
                DecisionPhase.ROOM,
                {"effect": effect.value, "amount": applied},
            ),
        ),
    )
    _validate_next_room_boundary(world)
    return transition


def _validate_next_room_boundary(world: WorldState) -> None:
    """Construct the next public decision before committing an option effect."""

    context = _room_context(world)
    next_scope = PublicScope.from_dict(context["public_scope"])
    room_candidates(world, next_scope)


def _public_player(world: WorldState) -> dict[str, int]:
    return {
        "deck_size": len(world.master_deck),
        "gold": world.gold,
        "hp": world.current_hp,
        "max_hp": world.max_hp,
    }


def _public_options(
    world: WorldState,
    room_kind: RoomKind,
    context: Mapping[str, Any],
    scope: PublicScope,
    state: str,
) -> list[dict[str, Any]]:
    if state == _RESOLVED:
        return []
    if room_kind is RoomKind.REST:
        if world.current_hp >= world.max_hp:
            return []
        return [
            {
                "option_ref": room_option_reference(
                    scope, room_kind, RoomOptionKind.REST_HEAL, 0
                ),
                "kind": RoomOptionKind.REST_HEAL.value,
                "effect": RoomEffectKind.HEAL.value,
                "amount": REST_HEAL_PARAMETERS.heal_amount,
                "enabled": True,
            }
        ]
    event = _event_from_context(context)
    _validate_event_effect_available(world, event)
    return [
        {
            "option_ref": room_option_reference(
                scope, room_kind, RoomOptionKind.EVENT_OPTION, 0
            ),
            "kind": RoomOptionKind.EVENT_OPTION.value,
            "effect": event.effect_kind,
            "amount": event.amount,
            "enabled": True,
        }
    ]


def _event_from_context(context: Mapping[str, Any]):
    event_id = context["event_id"]
    try:
        return _SAFE_EVENTS_BY_ID[event_id]
    except KeyError as error:
        raise UnsupportedRoomContentError("Room decision names unsupported event content.") from error


def _validate_event_effect_available(world: WorldState, event: Any) -> None:
    """Reject declared effects that cannot produce a public-valid transition."""

    try:
        effect = RoomEffectKind(event.effect_kind)
    except (AttributeError, TypeError, ValueError) as error:
        raise UnsupportedRoomContentError("Safe event names an unsupported effect.") from error
    amount = event.amount
    if effect is RoomEffectKind.HEAL:
        if min(amount, world.max_hp - world.current_hp) <= 0:
            raise RoomRuleError("Healing event has no contract-valid effect at full HP.")
        return
    if effect is RoomEffectKind.GAIN_GOLD:
        if world.gold > MAX_PUBLIC_COUNTER - amount:
            raise RoomRuleError("Gold event would exceed the public counter bound.")
        return
    if effect is RoomEffectKind.LOSE_HP:
        if min(amount, world.current_hp) <= 0:
            raise RoomRuleError("HP-loss event has no contract-valid effect at zero HP.")
        return
    raise UnsupportedRoomContentError("Safe event names an unsupported effect.")


def _mark_resolved(
    world: WorldState,
    context: Mapping[str, Any],
    effect: RoomEffectKind,
    applied: int,
) -> None:
    pending = world.pending_decision
    assert pending is not None  # established by _room_context before mutation
    current_scope = PublicScope.from_dict(context["public_scope"])
    next_sequence = pending.sequence + 1
    next_scope = _next_public_scope(current_scope)
    _set_pending_room_decision(
        world,
        next_sequence,
        context["room_kind"],
        context["event_id"],
        _RESOLVED,
        next_scope,
        context["opening_baseline"],
        {"effect": effect.value, "amount": applied},
    )


def _mutate_atomically(world: WorldState, operation: Callable[[], T]) -> T:
    """Run a room mutation or restore the exact private world on any failure."""

    before = world.to_private_dict()
    try:
        result = operation()
        world.validate()
        return result
    except Exception:
        _restore_world(world, before)
        raise


def _restore_world(world: WorldState, payload: Mapping[str, Any]) -> None:
    restored = WorldState.from_private_dict(payload)
    for field in fields(WorldState):
        setattr(world, field.name, getattr(restored, field.name))


def _apply_event_effect(world: WorldState, effect: RoomEffectKind, amount: int) -> int:
    """Apply a declared deterministic effect.

    The current closed content has no stochastic event.  If a future approved
    structural event adds one, its effect resolution must consume only the
    named ``event_effect`` stream in the content-declared option/effect order.
    """

    if effect is RoomEffectKind.HEAL:
        applied = min(amount, world.max_hp - world.current_hp)
        world.current_hp += applied
        return applied
    if effect is RoomEffectKind.GAIN_GOLD:
        world.gold += amount
        return amount
    if effect is RoomEffectKind.LOSE_HP:
        applied = min(amount, world.current_hp)
        world.current_hp -= applied
        return applied
    raise UnsupportedRoomContentError("Safe event names an unsupported effect.")
