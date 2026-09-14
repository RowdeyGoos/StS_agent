"""Scripted event lifecycle; individual choices and effects belong to content."""

from game.headless.run.unknown_rooms import room_node

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.rng import GameRandomService
from game.headless.events.catalog import EVENTS
from game.headless.run.actions import ChooseEventOption, ChooseEventCard, LeaveEvent
from game.headless.run.state import RunPhase


def begin(state, definition_id, *, cards=DEFAULT_CARDS):
    state.require_room_entry("event")
    if definition_id not in EVENTS:
        raise ValueError("Unsupported event.")
    rng = GameRandomService(state.seed)
    rng.restore(state.rng.snapshot())
    pending = {"kind": "scripted_event", "definition_id": definition_id,
               "event_instance_id": state.next_event_id, "stage": "options",
               "data": EVENTS[definition_id].generate(rng, state=state, cards=cards)}
    from game.headless.events.resources import capture
    resource_context = capture(state)
    if resource_context is not None:
        pending["resources"] = resource_context
    EVENTS[definition_id].validate(pending, state=state, cards=cards)
    state.rng = rng
    state.next_event_id += 1
    state.pending, state.phase = pending, RunPhase.ROOM


def _pending(state):
    if state.phase is not RunPhase.ROOM or not state.pending or state.pending.get("kind") != "scripted_event":
        raise ValueError("No scripted event is active.")
    return state.pending


def legal_actions(state):
    pending = _pending(state)
    instance_id = pending["event_instance_id"]
    if pending["stage"] == "select_card":
        return tuple(ChooseEventCard(instance_id, card_id) for card_id in pending["data"]["eligible"])
    if pending["stage"] == "resolved":
        return (LeaveEvent(instance_id),)
    options = EVENTS[pending["definition_id"]].options(pending)
    if pending["stage"] == "potion_rewards" and None not in state.potions:
        options = tuple(o for o in options if not o.startswith("claim_potion_"))
    return tuple(ChooseEventOption(instance_id, option) for option in options)


def choose(state, instance_id, option_id, *, cards=DEFAULT_CARDS):
    pending = _pending(state)
    definition = EVENTS[pending["definition_id"]]
    if (type(instance_id) is not int or instance_id != pending["event_instance_id"]
            or option_id not in definition.options(pending)):
        raise ValueError("Stale or unavailable event choice.")
    from dataclasses import asdict
    before = [None if p is None else asdict(p) for p in state.potions]
    result = definition.choose(state, pending, option_id, cards=cards)
    if option_id.startswith("claim_potion_"):
        from game.headless.events.potion_context import record
        record(state, before)
    if state.hp == 0:
        state.phase = RunPhase.DEFEAT
    return result


def select_card(state, event_instance_id, card_instance_id, *, cards=DEFAULT_CARDS):
    pending = _pending(state)
    if (type(event_instance_id) is not int or event_instance_id != pending["event_instance_id"]
            or pending["stage"] != "select_card"):
        raise ValueError("Stale or unavailable event card choice.")
    EVENTS[pending["definition_id"]].select_card(state, pending, card_instance_id, cards=cards)
    if state.hp == 0:
        state.phase = RunPhase.DEFEAT


def leave(state, instance_id):
    pending = _pending(state)
    if type(instance_id) is not int or instance_id != pending["event_instance_id"] or pending["stage"] != "resolved":
        raise ValueError("Event cannot be left before resolution.")
    state.pending, state.phase = None, RunPhase.ROUTE


def validate_event(state, graph, *, cards=DEFAULT_CARDS):
    pending = state.pending
    if set(pending) - {"resources", "potion_changes"} != {"kind", "definition_id", "event_instance_id", "stage", "data"}:
        raise ValueError("Invalid event state fields.")
    if pending["definition_id"] not in EVENTS or state.phase not in (RunPhase.ROOM, RunPhase.DEFEAT):
        raise ValueError("Invalid event definition or phase.")
    if (type(pending["event_instance_id"]) is not int or pending["event_instance_id"] < 0
            or pending["event_instance_id"] != state.next_event_id - 1):
        raise ValueError("Invalid owned event identity.")
    if graph is not None:
        node = None if state.current_node_id is None else room_node(state, graph, state.current_node_id)
        if node is None or node.kind != "event" or node.event_id != pending["definition_id"]:
            raise ValueError("Event differs from its room.")
    from game.headless.events.resources import capture, expected
    if (capture(state) is not None) != ("resources" in pending):
        raise ValueError("Event resource context is missing or unexpected.")
    if "resources" in pending and not getattr(EVENTS[pending["definition_id"]], "uses_steps", False):
        initial = expected(state, pending, potion_changes=False)
        from game.headless.events.potion_context import apply_at
        apply_at(initial, state, pending, -1)
    EVENTS[pending["definition_id"]].validate(pending, state=state, cards=cards, defeated=state.phase is RunPhase.DEFEAT)
