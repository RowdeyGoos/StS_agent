"""Private run continuation using plain state records and explicit content catalogs."""

from copy import deepcopy
from dataclasses import asdict

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.combat import CombatEngine
from game.headless.core.rng import GameRandomService
from game.headless.core.snapshots import card_record, restore_card
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.state import RunPhase, RunState
from game.headless.run.config import RunConfig
from game.headless.potions.base import POTIONS, PotionInstance
from game.headless.relics.base import RELICS, RelicInstance
from game.headless.encounters.catalog import ENCOUNTERS

SCHEMA = "headless_run_state_v2"


def _item_definitions():
    return {"relics": [asdict(v) for v in RELICS.values()],
            "potions": [asdict(v) for v in POTIONS.values()]}


def capture_run(engine) -> dict:
    state = engine.state
    state.validate()
    return {
        "schema": SCHEMA, "cards": engine.cards.snapshot_fingerprint(), "items": _item_definitions(),
        "state": {"seed": state.seed, "max_hp": state.max_hp, "hp": state.hp,
                  "gold": state.gold, "deck": [card_record(c) for c in state.deck],
                  "rng": state.rng.snapshot(), "phase": state.phase.value,
                  "next_card_id": state.next_card_id, "combats_completed": state.combats_completed,
                  "current_node_id": state.current_node_id, "visited_nodes": list(state.visited_nodes),
                  "pending": deepcopy(state.pending),
                  "config": None if state.config is None else asdict(state.config),
                  "relics": [asdict(r) for r in state.relics],
                  "potions": [None if p is None else asdict(p) for p in state.potions],
                  "next_item_id": state.next_item_id, "potion_drop_chance": state.potion_drop_chance},
        "graph": None if engine.graph is None else asdict(engine.graph),
        "combat": None if engine.combat is None else engine.combat.snapshot(cards=engine.cards),
    }


def restore_run(snapshot, *, cards=DEFAULT_CARDS):
    from game.headless.run.engine import RunEngine
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA:
        raise ValueError("Incompatible run snapshot.")
    if snapshot.get("cards") != cards.snapshot_fingerprint():
        raise ValueError("Run snapshot card definitions are incompatible.")
    if snapshot.get("items") != _item_definitions():
        raise ValueError("Run snapshot item definitions are incompatible.")
    try:
        payload = snapshot["state"]
        config = None if payload["config"] is None else RunConfig(**payload["config"])
        if config is not None:
            for card_id in config.reward_cards:
                cards.definition(card_id)
            if any(p not in POTIONS for p in config.reward_potions):
                raise ValueError("Unsupported potion pool.")
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
            config=config, relics=[RelicInstance(**r) for r in payload["relics"]],
            potions=[None if p is None else PotionInstance(**p) for p in payload["potions"]],
            next_item_id=payload["next_item_id"], potion_drop_chance=payload["potion_drop_chance"],
        )
        state.validate()
        graph = snapshot["graph"]
        if graph is not None:
            graph = MapGraph(tuple(MapNode(n["node_id"], n["kind"], tuple(n["next_node_ids"]), n["encounter_id"]) for n in graph["nodes"]), graph["start_id"])
            if any(n.encounter_id is not None and (n.kind != "combat" or n.encounter_id not in ENCOUNTERS) for n in graph.nodes):
                raise ValueError("Unsupported map encounter.")
            previous = None
            for node_id in state.visited_nodes:
                if node_id not in graph.available_nodes(previous):
                    raise ValueError("Invalid map history.")
                previous = node_id
            if previous != state.current_node_id:
                raise ValueError("Map cursor does not match its history.")
        elif state.current_node_id is not None or state.visited_nodes:
            raise ValueError("Map history has no map.")
        if state.phase is RunPhase.SLICE_COMPLETE and (graph is None or state.current_node_id is None or graph.node(state.current_node_id).kind != "slice_end"):
            raise ValueError("Slice completion requires its authored ending.")
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
        if set(pending) != {"kind", "node_id", "room_kind"}:
            raise ValueError("Invalid map decision fields.")
        if state.phase is not RunPhase.ROUTE or graph is None or pending["node_id"] != state.current_node_id or pending["room_kind"] != graph.node(state.current_node_id).kind:
            raise ValueError("Invalid pending map node.")
    elif kind == "reward":
        expected = {"kind", "gold", "gold_claimed", "offers", "card_resolved"}
        if "combat_reward" in pending:
            expected |= {"combat_reward", "potion", "potion_claimed"}
        if set(pending) != expected:
            raise ValueError("Invalid reward state fields.")
        if state.phase is not RunPhase.REWARD or type(pending["gold"]) is not int or pending["gold"] < 0:
            raise ValueError("Invalid pending reward.")
        if type(pending["gold_claimed"]) is not bool or type(pending["card_resolved"]) is not bool:
            raise ValueError("Invalid reward resolution flags.")
        for definition_id in pending["offers"]:
            cards.definition(definition_id)
        if not isinstance(pending["offers"], list) or not pending["offers"] or len(set(pending["offers"])) != len(pending["offers"]):
            raise ValueError("Invalid reward offers.")
        if "combat_reward" in pending:
            if (pending["combat_reward"] is not True or state.config is None
                    or type(pending["potion_claimed"]) is not bool
                    or not 10 <= pending["gold"] <= 20
                    or len(pending["offers"]) != 3
                    or not set(pending["offers"]) <= set(state.config.reward_cards)
                    or (pending["potion"] is not None and pending["potion"] not in state.config.reward_potions)
                    or (pending["potion"] is None and pending["potion_claimed"])):
                raise ValueError("Invalid combat reward bundle.")
    elif kind == "rest_site":
        if state.phase is not RunPhase.ROOM or pending["stage"] not in ("options", "smith", "resolved"):
            raise ValueError("Invalid rest-site phase.")
        if pending["stage"] == "smith":
            from game.headless.run.rest_site import eligible_upgrades
            if not pending["eligible"] or pending["eligible"] != list(eligible_upgrades(state)):
                raise ValueError("Invalid smith selection.")
            expected = {"kind", "stage", "eligible"}
        else:
            expected = {"kind", "stage"}
        if set(pending) != expected:
            raise ValueError("Invalid rest-site state fields.")
    elif kind in ("rest", "event"):
        if state.phase not in (RunPhase.ROOM, RunPhase.DEFEAT) or type(pending["resolved"]) is not bool:
            raise ValueError("Invalid pending room.")
        for option, (effect, amount) in pending["options"].items():
            if not isinstance(option, str) or effect not in ("heal", "gain_gold", "lose_hp") or type(amount) is not int or amount <= 0:
                raise ValueError("Invalid room effect.")
    else:
        raise ValueError("Unsupported pending gameplay state.")
