"""Private run continuation using plain state records and explicit content catalogs."""

from copy import deepcopy
from dataclasses import asdict

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.combat import CombatEngine
from game.headless.core.rng import GameRandomService
from game.headless.core.snapshots import card_record, restore_card
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.state import RunPhase, RunState

SCHEMA = "headless_run_state_v1"


def capture_run(engine) -> dict:
    state = engine.state
    state.validate()
    return {
        "schema": SCHEMA, "cards": engine.cards.snapshot_fingerprint(),
        "state": {"seed": state.seed, "max_hp": state.max_hp, "hp": state.hp,
                  "gold": state.gold, "deck": [card_record(c) for c in state.deck],
                  "rng": state.rng.snapshot(), "phase": state.phase.value,
                  "next_card_id": state.next_card_id, "combats_completed": state.combats_completed,
                  "current_node_id": state.current_node_id, "visited_nodes": list(state.visited_nodes),
                  "pending": deepcopy(state.pending)},
        "graph": None if engine.graph is None else asdict(engine.graph),
        "combat": None if engine.combat is None else engine.combat.snapshot(cards=engine.cards),
    }


def restore_run(snapshot, *, cards=DEFAULT_CARDS):
    from game.headless.run.engine import RunEngine
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA:
        raise ValueError("Incompatible run snapshot.")
    if snapshot.get("cards") != cards.snapshot_fingerprint():
        raise ValueError("Run snapshot card definitions are incompatible.")
    try:
        payload = snapshot["state"]
        rng = GameRandomService(payload["seed"])
        rng.restore(payload["rng"])
        if rng.seed != payload["seed"]:
            raise ValueError("Run RNG seed mismatch.")
        state = RunState(
            seed=payload["seed"], max_hp=payload["max_hp"], hp=payload["hp"], gold=payload["gold"],
            deck=[restore_card(record, cards) for record in payload["deck"]], rng=rng,
            phase=RunPhase(payload["phase"]), next_card_id=payload["next_card_id"],
            combats_completed=payload["combats_completed"], current_node_id=payload["current_node_id"],
            visited_nodes=list(payload["visited_nodes"]), pending=deepcopy(payload["pending"]),
        )
        state.validate()
        graph = snapshot["graph"]
        if graph is not None:
            graph = MapGraph(tuple(MapNode(n["node_id"], n["kind"], tuple(n["next_node_ids"])) for n in graph["nodes"]), graph["start_id"])
            previous = None
            for node_id in state.visited_nodes:
                if node_id not in graph.available_nodes(previous):
                    raise ValueError("Invalid map history.")
                previous = node_id
            if previous != state.current_node_id:
                raise ValueError("Map cursor does not match its history.")
        elif state.current_node_id is not None or state.visited_nodes:
            raise ValueError("Map history has no map.")
        combat = None
        if snapshot["combat"] is not None:
            if state.phase is not RunPhase.COMBAT:
                raise ValueError("Active combat requires the combat phase.")
            combat = CombatEngine()
            combat.restore(snapshot["combat"], cards=cards)
            if combat.player.max_hp != state.max_hp:
                raise ValueError("Combat maximum HP differs from the run.")
        elif state.phase is RunPhase.COMBAT:
            raise ValueError("Combat phase requires its owned combat.")
        _validate_pending(state, cards, graph)
        result = RunEngine.__new__(RunEngine)
        result.cards, result.graph, result.state, result.combat = cards, graph, state, combat
        return result
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid run snapshot.") from error


def _validate_pending(state, cards, graph):
    pending = state.pending
    if pending is None:
        if state.phase in (RunPhase.REWARD, RunPhase.ROOM):
            raise ValueError("Pending game state is missing.")
        return
    kind = pending["kind"]
    if kind == "node":
        if state.phase is not RunPhase.ROUTE or graph is None or pending["node_id"] != state.current_node_id or pending["room_kind"] != graph.node(state.current_node_id).kind:
            raise ValueError("Invalid pending map node.")
    elif kind == "reward":
        if state.phase is not RunPhase.REWARD or type(pending["gold"]) is not int or pending["gold"] < 0:
            raise ValueError("Invalid pending reward.")
        if type(pending["gold_claimed"]) is not bool or type(pending["card_resolved"]) is not bool:
            raise ValueError("Invalid reward resolution flags.")
        for definition_id in pending["offers"]:
            cards.definition(definition_id)
    elif kind in ("rest", "event"):
        if state.phase not in (RunPhase.ROOM, RunPhase.DEFEAT) or type(pending["resolved"]) is not bool:
            raise ValueError("Invalid pending room.")
        for option, (effect, amount) in pending["options"].items():
            if not isinstance(option, str) or effect not in ("heal", "gain_gold", "lose_hp") or type(amount) is not int or amount <= 0:
                raise ValueError("Invalid room effect.")
    else:
        raise ValueError("Unsupported pending gameplay state.")
