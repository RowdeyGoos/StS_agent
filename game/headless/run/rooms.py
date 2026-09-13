"""Small explicit room transitions; future room mechanics belong in this layer."""

from game.headless.events.safe import apply_effect
from game.headless.run.state import RunPhase


def begin_room(state, *, kind: str, options: dict) -> None:
    state.require_room_entry(kind)
    if kind not in ("rest", "event") or not options:
        raise ValueError("Unsupported room.")
    copied = {}
    for key, (effect, amount) in options.items():
        if not isinstance(key, str) or not key or effect not in ("heal", "gain_gold", "lose_hp") or type(amount) is not int or amount <= 0:
            raise ValueError("Invalid room option.")
        copied[key] = [effect, amount]
    state.pending = {"kind": kind, "options": copied, "resolved": False}
    state.phase = RunPhase.ROOM


def choose_option(state, option_id: str) -> int:
    room = _room(state)
    if room["resolved"] or option_id not in room["options"]:
        raise ValueError("Room option is unavailable.")
    applied = apply_effect(state, *room["options"][option_id])
    room["resolved"] = True
    if state.hp == 0:
        state.phase = RunPhase.DEFEAT
    return applied


def finish_room(state) -> None:
    if not _room(state)["resolved"]:
        raise ValueError("Resolve the room before proceeding.")
    state.pending = None
    state.phase = RunPhase.ROUTE


def _room(state):
    if state.phase is not RunPhase.ROOM or not state.pending or state.pending.get("kind") not in ("rest", "event"):
        raise ValueError("No room is active.")
    return state.pending
