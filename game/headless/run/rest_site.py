"""Ordinary rest healing and cancelable single-card smithing."""

from game.headless.run.deck import upgrade_card
from game.headless.run.state import RunPhase


def begin_rest_site(state) -> None:
    state.require_room_entry("rest")
    state.pending = {"kind": "rest_site", "stage": "options"}
    state.phase = RunPhase.ROOM


def eligible_upgrades(state) -> tuple[str, ...]:
    return tuple(c.instance_id for c in state.deck if c.upgrade_level + 1 < len(c.definition.levels))


def _pending(state, stage):
    if state.phase is not RunPhase.ROOM or not state.pending or state.pending.get("kind") != "rest_site" or state.pending.get("stage") != stage:
        raise ValueError("Rest-site action is unavailable.")
    return state.pending


def heal_amount(state) -> int:
    return min(state.max_hp * 3 // 10, state.max_hp - state.hp)


def heal(state) -> int:
    pending = _pending(state, "options")
    amount = heal_amount(state)
    state.hp += amount
    pending["stage"] = "resolved"
    return amount


def begin_smith(state) -> None:
    pending = _pending(state, "options")
    choices = eligible_upgrades(state)
    if not choices:
        raise ValueError("No supported card can be upgraded.")
    pending["stage"] = "smith"
    pending["eligible"] = list(choices)


def choose_upgrade(state, instance_id: str | None):
    pending = _pending(state, "smith")
    if instance_id is None:
        state.pending = {"kind": "rest_site", "stage": "options"}
        return None
    if instance_id not in pending["eligible"] or instance_id not in eligible_upgrades(state):
        raise ValueError("Card is not eligible for this upgrade choice.")
    card = upgrade_card(state, instance_id)
    state.pending = {"kind": "rest_site", "stage": "resolved"}
    return card


def leave(state) -> None:
    _pending(state, "resolved")
    state.pending = None
    state.phase = RunPhase.ROUTE
