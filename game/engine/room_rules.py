"""Reduced structural rules for supported rest sites and safe events.

This module owns only room-local progression over the accepted private
``WorldState`` kernel.  It is intentionally not a backend: decision bindings,
map traversal, snapshots, and terminal composition remain the responsibility of
their respective owners.  The sole public surface is made from the frozen
``headless_v0`` observation, candidate, and event records.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from game.content.reduced_v0 import REST_HEAL_PARAMETERS, SAFE_EVENT_DEFINITIONS
from game.contracts.headless_v0 import (
    DecisionPhase,
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

_CONTEXT_FIELDS = frozenset({"event_id", "room_kind", "state"})
_READY = "ready"
_RESOLVED = "resolved"
_RULES_DESCRIPTOR = {
    "version": ROOM_RULES_VERSION,
    "rest": {"heal_amount": REST_HEAL_PARAMETERS.heal_amount, "one_use": True},
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


def open_room(
    world: WorldState,
    room_kind: RoomKind | str,
    *,
    decision_sequence: int,
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

    if kind is RoomKind.REST:
        if event_id is not None:
            raise UnsupportedRoomContentError("Rest rooms cannot name an event.")
    else:
        if not isinstance(event_id, str) or event_id not in _SAFE_EVENTS_BY_ID:
            raise UnsupportedRoomContentError("Event is not in the safe-event allowlist.")

    # All validation precedes this one state assignment.
    world.pending_decision = PendingDecision(
        ROOM_DECISION_KIND,
        decision_sequence,
        {"room_kind": kind.value, "event_id": event_id, "state": _READY},
    )
    world.validate()


def room_public_observation(world: WorldState, public_scope: PublicScope) -> PublicObservation:
    """Project exactly the room data permitted to a chooser or future model."""

    context = _room_context(world)
    if not isinstance(public_scope, PublicScope):
        raise TypeError("public_scope must be a PublicScope.")
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
        world.pending_decision = None
        world.phase = DecisionPhase.MAP
        world.validate()
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
        world.current_hp += applied
        _mark_resolved(world, context)
        return RoomTransition(
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

    if room_kind is not RoomKind.EVENT:
        raise RoomRuleError("Event options are unavailable in this room.")
    event = _event_from_context(context)
    effect = RoomEffectKind(event.effect_kind)
    amount = event.amount
    applied = _apply_event_effect(world, effect, amount)
    _mark_resolved(world, context)
    return RoomTransition(
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
    if room_kind is RoomKind.REST and event_id is not None:
        raise RoomRuleError("Rest decision contains an event identifier.")
    if room_kind is RoomKind.EVENT and (
        not isinstance(event_id, str) or event_id not in _SAFE_EVENTS_BY_ID
    ):
        raise UnsupportedRoomContentError("Room decision names unsupported event content.")
    return context


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
    world.pending_decision = PendingDecision(
        ROOM_DECISION_KIND,
        pending.sequence,
        {"room_kind": context["room_kind"], "event_id": context["event_id"], "state": _RESOLVED},
    )
    world.validate()


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
