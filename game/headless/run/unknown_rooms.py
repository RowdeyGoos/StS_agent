"""Owned native base unknown-room odds and restricted event outcomes."""

from copy import deepcopy
from dataclasses import dataclass, field, replace
from struct import pack, unpack
from types import MappingProxyType

from game.headless.core.rng import GameRandomService


def _single(value):
    return unpack("f", pack("f", value))[0]


BASE_ODDS = MappingProxyType({"combat": _single(.10), "elite": -1.0,
                              "treasure": _single(.02), "shop": _single(.03)})


def _advance(odds, result, blocked):
    for kind, base in BASE_ODDS.items():
        if kind == result:
            odds[kind] = base
        elif kind not in blocked:
            odds[kind] = _single(odds[kind] + base)


def roll_room(odds, rng, *, blocked=()):
    """Native cumulative roll, with no renormalization of blocked room odds."""
    roll = _single(rng.random("act1.unknown"))
    cumulative = 0.0
    result = "event"
    for kind in BASE_ODDS:
        chance = odds[kind]
        if kind in blocked or chance < 0:
            continue
        cumulative = _single(cumulative + chance)
        if roll <= cumulative:
            result = kind
            break
    _advance(odds, result, blocked)
    return result


@dataclass(frozen=True)
class RoomOutcome:
    kind: str
    event_id: str | None = None
    blocked_by: str | None = None


@dataclass
class UnknownRooms:
    odds: dict[str, float] = field(default_factory=lambda: dict(BASE_ODDS))
    outcomes: dict[str, RoomOutcome] = field(default_factory=dict)

    def validate(self, state, graph):
        expected_nodes = [n for n in state.visited_nodes if graph.node(n).kind == "unknown"]
        if not isinstance(self.outcomes, dict) or set(self.outcomes) != set(expected_nodes):
            raise ValueError("Unknown outcomes differ from visited unknown points.")
        expected_odds = dict(BASE_ODDS)
        previous = None
        for node_id in state.visited_nodes:
            node = graph.node(node_id)
            if node.kind == "unknown":
                result = self.outcomes[node_id]
                blocked = blocked_types(graph, node, previous)
                if result.blocked_by is not None:
                    identity = result.blocked_by
                    if not isinstance(identity, str) or not identity.startswith("run.item.") or not identity.removeprefix("run.item.").isdigit() or int(identity.removeprefix("run.item.")) >= state.next_item_id:
                        raise ValueError("Invalid unknown-room relic source.")
                    current = next((r for r in state.relics if r.instance_id == identity), None)
                    if current is not None and current.definition_id != "juzu_bracelet":
                        raise ValueError("Unknown-room blocker is not Juzu Bracelet.")
                    blocked = (*blocked, "combat")
                if (not isinstance(result, RoomOutcome) or result.kind not in ("combat", "treasure", "shop", "event")
                        or result.kind in blocked
                        or result.kind == "event" and result.event_id not in state.config.event_pool
                        or result.kind != "event" and result.event_id is not None):
                    raise ValueError("Invalid unknown-room outcome.")
                _advance(expected_odds, result.kind, blocked)
                previous = result.kind
            else:
                previous = node.kind
        if (not isinstance(self.odds, dict) or set(self.odds) != set(BASE_ODDS)
                or any(type(v) is not float for v in self.odds.values()) or self.odds != expected_odds):
            raise ValueError("Unknown-room odds differ from their owned outcome history.")


def blocked_types(graph, node, previous_kind):
    children = [graph.node(n) for n in node.next_node_ids]
    return ("shop",) if previous_kind == "shop" or children and all(n.kind == "shop" for n in children) else ()


def room_node(state, graph, node_id):
    """Resolve visited room identity without altering the immutable map marker."""
    node = graph.node(node_id)
    if node.kind == "unknown" and state.unknown_rooms is not None:
        outcome = state.unknown_rooms.outcomes.get(node_id)
        if outcome is not None:
            return replace(node, kind=outcome.kind, event_id=outcome.event_id)
    return node


def prepare_unknown(state, graph, node):
    """Build an outcome on independent state; the caller commits at room entry."""
    if state.unknown_rooms is None or state.config is None or node.node_id in state.unknown_rooms.outcomes:
        raise ValueError("Unknown room requires an unresolved owned point.")
    from game.headless.core.rng import from_snapshot
    rng = from_snapshot(state.rng.snapshot())
    unknown = deepcopy(state.unknown_rooms)
    previous = room_node(state, graph, state.current_node_id).kind if state.current_node_id is not None else None
    from game.headless.relics.run_rules import owned
    bracelet = owned(state, "juzu_bracelet")
    blocked = blocked_types(graph, node, previous) + (("combat",) if bracelet is not None else ())
    kind = roll_room(unknown.odds, rng, blocked=blocked)
    if state.event_progression is None:
        raise ValueError("Unknown room requires an owned event queue.")
    progression = deepcopy(state.event_progression)
    from game.headless.events.eligibility import entry_conditions
    event_id = progression.pull(node.node_id, conditions=entry_conditions(state)) if kind == "event" else None
    unknown.outcomes[node.node_id] = RoomOutcome(kind, event_id, None if bracelet is None else bracelet.instance_id)
    return rng, unknown, progression, replace(node, kind=kind, event_id=event_id)
