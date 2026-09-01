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

_CONTEXT_FIELDS = frozenset({"event_id", "public_scope", "room_kind", "state"})
_READY = "ready"
_RESOLVED = "resolved"
_RULES_DESCRIPTOR = {
    "version": ROOM_RULES_VERSION,
    "decision_binding": "exact_pending_public_scope_and_sequence_v1",
    "maximum_open_sequence": MAX_PUBLIC_COUNTER - 1,
    "next_boundary_validation": "event_and_observation_before_commit_v1",
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
        event = _SAFE_EVENTS_BY_ID[event_id]
        if event.effect_kind == RoomEffectKind.HEAL.value and world.current_hp >= world.max_hp:
            raise RoomRuleError("Healing event has no contract-valid effect at full HP.")

    _mutate_atomically(
        world,
        lambda: _set_pending_room_decision(
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
    """Apply one advertised room candidate without partial mutation on rejection."""

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
        _mutate_atomically(world, lambda: _complete_room(world))
        return RoomTransition(
            completed=True,
            public_events=(
                PublicEvent(0, PublicEventKind.ROOM_PROCEEDED, DecisionPhase.ROOM, {}),
            ),
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
    return context


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
) -> None:
    world.pending_decision = PendingDecision(
        ROOM_DECISION_KIND,
        sequence,
        {
            "room_kind": room_kind,
            "event_id": event_id,
            "state": state,
            "public_scope": public_scope.to_dict(),
        },
    )


def _complete_room(world: WorldState) -> None:
    world.pending_decision = None
    world.phase = DecisionPhase.MAP


def _apply_rest_heal_transition(
    world: WorldState,
    context: Mapping[str, Any],
    applied: int,
) -> RoomTransition:
    world.current_hp += applied
    _mark_resolved(world, context)
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
    _mark_resolved(world, context)
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
    if event.effect_kind == RoomEffectKind.HEAL.value and world.current_hp >= world.max_hp:
        raise RoomRuleError("Healing event has no contract-valid effect at full HP.")
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


def _mark_resolved(world: WorldState, context: Mapping[str, Any]) -> None:
    pending = world.pending_decision
    assert pending is not None  # established by _room_context before mutation
    current_scope = PublicScope.from_dict(context["public_scope"])
    next_sequence = pending.sequence + 1
    next_scope = PublicScope(
        history_ordinal=current_scope.history_ordinal,
        decision_ordinal=current_scope.decision_ordinal + 1,
        reveal_ordinals=current_scope.reveal_ordinals,
    )
    _set_pending_room_decision(
        world,
        next_sequence,
        context["room_kind"],
        context["event_id"],
        _RESOLVED,
        next_scope,
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
