"""Private run continuation using plain state records and explicit content catalogs."""

import json
from copy import deepcopy
from dataclasses import asdict

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.combat import CombatEngine
from game.headless.core.rng import GameRandomService
from game.headless.core.snapshots import card_record, restore_card
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.state import RunPhase, RunState, ActCompletion
from game.headless.run.config import RunConfig
from game.headless.potions.base import POTIONS, PotionInstance
from game.headless.relics.base import RELICS, RelicInstance
from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.shops.catalog import fingerprint as shop_fingerprint
from game.headless.treasure.catalog import fingerprint as treasure_fingerprint
from game.headless.events.catalog import EVENTS, fingerprint as event_fingerprint
from game.headless.encounters.progression import EncounterProgression, encounter_at
from game.headless.run.unknown_rooms import UnknownRooms, RoomOutcome, room_node

from game.headless.events.progression import EventProgression
from game.headless.run.ancient import AncientStart

from game.headless.events.combat import EventCombatRecord
from game.headless.run import event_combat

SCHEMA = "headless_run_state_v61"


def _restore_graph(record):
    return MapGraph(tuple(MapNode(**{**n, 'next_node_ids': tuple(n['next_node_ids'])}) for n in record['nodes']),
                    record['start_id'], tuple(record['entry_node_ids']), record['generation'], record['replaced_generation'])


def _restore_completed_act(record):
    from game.headless.run.campaign import CompletedAct
    if not isinstance(record, dict) or set(record) != {'act', 'graph', 'visited_nodes', 'encounter_progression', 'event_progression', 'unknown_rooms', 'event_pool', 'spoils_map'}:
        raise ValueError('Invalid completed act fields.')
    unknown = record['unknown_rooms']
    if not isinstance(unknown, dict) or set(unknown) != {'odds', 'outcomes'}:
        raise ValueError('Invalid archived unknown-room fields.')
    return CompletedAct(record['act'], _restore_graph(record['graph']), deepcopy(record['visited_nodes']),
        EncounterProgression(**deepcopy(record['encounter_progression'])),
        EventProgression(**deepcopy(record['event_progression'])),
        UnknownRooms(deepcopy(unknown['odds']), {n: RoomOutcome(**r) for n, r in unknown['outcomes'].items()}), tuple(record['event_pool']), deepcopy(record['spoils_map']))


def _restore_event_combat(record):
    if not isinstance(record, dict) or set(record) != {"event_instance_id", "definition_id", "node_id", "encounter_id", "combat_number", "outcome", "rewards_left", "continuation", "timed_out", "resumed"}:
        raise ValueError("Invalid event combat state fields.")
    return EventCombatRecord(**record)


def _restore_relic(record):
    if not isinstance(record, dict) or set(record) != {"definition_id", "instance_id", "counter", "data"}:
        raise ValueError("Invalid relic state fields.")
    return RelicInstance(**record)


def _item_definitions():
    return json.loads(json.dumps({"relics": [asdict(v) for v in RELICS.values()],
                                  "potions": [asdict(v) for v in POTIONS.values()]}))


def capture_run(engine) -> dict:
    state = engine.state
    state.validate()
    _validate_progression(state, engine.graph, engine.cards)
    return {
        "schema": SCHEMA, "cards": engine.cards.snapshot_fingerprint(), "items": _item_definitions(), "shops": shop_fingerprint(), "treasure": treasure_fingerprint(), "events": event_fingerprint(),
        "state": {"seed": state.seed, "max_hp": state.max_hp, "hp": state.hp,
                  "gold": state.gold, "deck": [card_record(c) for c in state.deck],
                  "stolen_cards": [card_record(c) for c in state.stolen_cards],
                  "completed_acts": [asdict(a) for a in state.completed_acts],
                  "spoils_map": deepcopy(state.spoils_map), "epilogue_event_id": state.epilogue_event_id,
                  "rng": state.rng.snapshot(), "phase": state.phase.value,
                  "next_card_id": state.next_card_id, "combats_completed": state.combats_completed,
                  "current_node_id": state.current_node_id,
                  "act_completion": None if state.act_completion is None else asdict(state.act_completion),
                  "event_combats": [asdict(record) for record in state.event_combats],
                  "active_encounter_id": state.active_encounter_id, "visited_nodes": list(state.visited_nodes),
                  "pending": deepcopy(state.pending),
                  "config": None if state.config is None else asdict(state.config),
                  "encounter_progression": None if state.encounter_progression is None else asdict(state.encounter_progression),
                  "ancient_start": None if state.ancient_start is None else asdict(state.ancient_start),
                  "event_progression": None if state.event_progression is None else asdict(state.event_progression),
                  "unknown_rooms": None if state.unknown_rooms is None else asdict(state.unknown_rooms),
                  "relics": [asdict(r) for r in state.relics],
                  "relic_work": deepcopy(state.relic_work),
                  "free_travels": deepcopy(state.free_travels),
                  "potion_capacity": state.potion_capacity,
                  "potions": [None if p is None else asdict(p) for p in state.potions],
                  "next_item_id": state.next_item_id, "potion_drop_chance": state.potion_drop_chance, "generation_odds": deepcopy(state.generation_odds), "initialization": deepcopy(state.initialization), "relic_bags": deepcopy(state.relic_bags),
                  "next_shop_id": state.next_shop_id, "shop_removals_used": state.shop_removals_used,
                  "act_index": state.act_index, "wongo_points": state.wongo_points, "freed_repy": state.freed_repy, "next_event_id": state.next_event_id, "next_treasure_id": state.next_treasure_id, "treasure_relics_drawn": list(state.treasure_relics_drawn)},
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
    if snapshot.get("shops") != shop_fingerprint():
        raise ValueError("Run snapshot shop definitions are incompatible.")
    if snapshot.get("treasure") != treasure_fingerprint():
        raise ValueError("Run snapshot treasure definitions are incompatible.")
    if snapshot.get("events") != event_fingerprint():
        raise ValueError("Run snapshot event definitions are incompatible.")
    try:
        payload = snapshot["state"]
        if payload['config'] is not None and not {'act', 'campaign'} <= set(payload['config']):
            raise ValueError('Missing declared act.')
        if payload['encounter_progression'] is not None and 'act' not in payload['encounter_progression']:
            raise ValueError('Missing encounter act owner.')
        config = None if payload["config"] is None else RunConfig(**payload["config"])
        if config is not None:
            for card_id in (*config.reward_cards, *config.boss_reward_cards):
                cards.definition(card_id)
            if any(r not in RELICS or r == "burning_blood" or RELICS[r].stackable for r in config.reward_relics):
                raise ValueError("Unsupported relic pool.")
            if any(p not in POTIONS for p in config.reward_potions):
                raise ValueError("Unsupported potion pool.")
        from game.headless.core.rng import from_snapshot
        rng = from_snapshot(payload["rng"])
        if rng.seed != payload["seed"]:
            raise ValueError("Run RNG seed mismatch.")
        state = RunState(
            seed=payload["seed"], max_hp=payload["max_hp"], hp=payload["hp"], gold=payload["gold"],
            deck=[restore_card(record, cards) for record in payload["deck"]], rng=rng,
            stolen_cards=[restore_card(record, cards) for record in payload["stolen_cards"]],
            completed_acts=[_restore_completed_act(r) for r in payload["completed_acts"]],
            spoils_map=deepcopy(payload["spoils_map"]), epilogue_event_id=payload["epilogue_event_id"],
            phase=RunPhase(payload["phase"]), next_card_id=payload["next_card_id"],
            combats_completed=payload["combats_completed"], current_node_id=payload["current_node_id"],
            active_encounter_id=payload["active_encounter_id"],
            event_combats=[_restore_event_combat(record) for record in payload["event_combats"]],
            act_completion=None if payload["act_completion"] is None else ActCompletion(**payload["act_completion"]),
            visited_nodes=list(payload["visited_nodes"]), pending=deepcopy(payload["pending"]),
            ancient_start=None if payload["ancient_start"] is None else AncientStart(**deepcopy(payload["ancient_start"])),
            event_progression=None if payload["event_progression"] is None else EventProgression(**deepcopy(payload["event_progression"])),
            config=config, relics=[_restore_relic(r) for r in payload["relics"]],
            relic_work=deepcopy(payload["relic_work"]),
            free_travels=deepcopy(payload["free_travels"]),
            potion_capacity=payload["potion_capacity"],
            encounter_progression=None if payload["encounter_progression"] is None else EncounterProgression(**deepcopy(payload["encounter_progression"])),
            potions=[None if p is None else PotionInstance(**p) for p in payload["potions"]],
            next_item_id=payload["next_item_id"], potion_drop_chance=payload["potion_drop_chance"], generation_odds=deepcopy(payload["generation_odds"]), initialization=deepcopy(payload["initialization"]), relic_bags=deepcopy(payload["relic_bags"]),
            next_shop_id=payload["next_shop_id"], shop_removals_used=payload["shop_removals_used"],
            act_index=payload["act_index"], wongo_points=payload["wongo_points"], freed_repy=payload["freed_repy"], next_event_id=payload["next_event_id"], next_treasure_id=payload["next_treasure_id"], treasure_relics_drawn=deepcopy(payload["treasure_relics_drawn"]),
        )
        unknown = payload["unknown_rooms"]
        if unknown is not None:
            if set(unknown) != {"odds", "outcomes"}:
                raise ValueError("Invalid unknown room fields.")
            state.unknown_rooms = UnknownRooms(deepcopy(unknown["odds"]),
                {node_id: RoomOutcome(**record) for node_id, record in unknown["outcomes"].items()})
        state.validate()
        from game.headless.relics.pickup import validate as validate_relic_work
        validate_relic_work(state, cards)
        if state.active_encounter_id is not None and state.active_encounter_id not in ENCOUNTERS:
            raise ValueError("Unknown active encounter.")
        if state.active_encounter_id is not None and ENCOUNTERS[state.active_encounter_id].gives_relic:
            from game.headless.run.rewards import eligible_relics
            if state.config is None or not eligible_relics(state):
                raise ValueError("Active elite requires an available relic reward pool.")
        if state.act_completion is not None:
            completed = ENCOUNTERS.get(state.act_completion.boss_encounter_id)
            if completed is None or completed.room_kind != "boss" or completed.act != state.act_completion.act:
                raise ValueError("Act completion requires a supported boss.")
        graph = snapshot["graph"]
        if graph is not None:
            graph = _restore_graph(graph)
            _validate_progression(state, graph, cards)
            if any(n.encounter_id is not None and (n.encounter_id not in ENCOUNTERS or n.kind != ENCOUNTERS[n.encounter_id].room_kind) for n in graph.nodes):
                raise ValueError("Unsupported map encounter.")
            if any(n.event_id is not None and n.event_id not in EVENTS for n in graph.nodes):
                raise ValueError("Unsupported map event.")
            if state.act_completion is not None and (state.current_node_id is None or
                    encounter_at(state, room_node(state, graph, state.current_node_id)) != state.act_completion.boss_encounter_id):
                raise ValueError("Completed boss differs from its room.")
            from game.headless.run.map_travel import validate as validate_travel
            validate_travel(state, graph)
            if state.phase is RunPhase.COMBAT and state.current_node_id is not None:
                node = room_node(state, graph, state.current_node_id)
                selected = event_combat.encounter_at_current_room(state) or encounter_at(state, node)
                if selected is not None and selected != state.active_encounter_id:
                    raise ValueError("Active encounter differs from its selected room.")
            if (state.visited_nodes[-1] if state.visited_nodes else None) != state.current_node_id:
                raise ValueError("Map cursor does not match its history.")
        elif state.spoils_map is not None or state.completed_acts or state.current_node_id is not None or state.visited_nodes or state.free_travels or state.encounter_progression is not None or state.unknown_rooms is not None or state.event_progression is not None or state.ancient_start is not None:
            raise ValueError("Map history has no map.")
        if state.phase is RunPhase.SLICE_COMPLETE and (graph is None or state.current_node_id is None or room_node(state, graph, state.current_node_id).kind != "slice_end"):
            raise ValueError("Slice completion requires its authored ending.")
        combat = None
        if snapshot["combat"] is not None:
            if state.phase is not RunPhase.COMBAT:
                raise ValueError("Active combat requires the combat phase.")
            combat = CombatEngine()
            combat.restore(snapshot["combat"], cards=cards)
            if combat.ascension != (state.config.ascension if state.config else 0):
                raise ValueError("Combat ascension differs from its run.")
            if getattr(state.rng, "native", False):
                from game.headless.core.native_service import bind_combat
                bind_combat(state.rng, combat)
            rules = combat.player.rules
            if rules.genetic_gains:
                raise ValueError("Combat Genetic Algorithm gains were not synchronized.")
            if rules.scythe_gains:
                raise ValueError('Combat Scythe gains were not synchronized with the owning run.')
            expected_pool = list(state.config.reward_potions) if state.config is not None else ["fire_potion", "block_potion"]
            if rules.relics != [asdict(r) for r in state.relics]:
                raise ValueError("Combat relic inventory differs from run ownership.")
            if (rules.potion_capacity != len(state.potions) or rules.potion_slots != state.potions.count(None) or rules.potion_pool != expected_pool
                    or rules.potions_generated or rules.gold_gained or rules.gold_lost or rules.gold_available != state.gold
                    or rules.potions != [None if p is None else asdict(p) for p in state.potions]):
                raise ValueError("Combat loot differs from its owning run inventory.")
            for identity in rules.potion_uses:
                suffix = identity.removeprefix('run.item.')
                if (not suffix.isdecimal() or identity != f'run.item.{int(suffix)}'
                        or int(suffix) >= state.next_item_id or any(r.instance_id == identity for r in state.relics)):
                    raise ValueError('Active potion use has no run-owned identity.')
            if combat.player.max_hp != state.max_hp + combat.player.rules.max_hp_gained:
                raise ValueError("Combat maximum HP differs from the run.")
        elif state.phase is RunPhase.COMBAT:
            raise ValueError("Combat phase requires its owned combat.")
        from game.headless.encounters.theft import validate_run
        validate_run(state, combat)
        event_combat.validate(state, graph, cards=cards)
        _validate_pending(state, cards, graph)
        if (getattr(state.rng,"native",False) and state.pending and state.pending.get("kind")=="scripted_event"
                and state.rng.active_event!=state.pending["definition_id"]):
            raise ValueError("Event RNG owner differs from pending event.")
        result = RunEngine.__new__(RunEngine)
        result.cards, result.graph, result.state, result.combat = cards, graph, state, combat
        return result
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid run snapshot.") from error


def _validate_progression(state, graph, cards):
    event_combat.validate(state, graph, cards=cards)
    from game.headless.run.spoils_map import validate as validate_spoils
    validate_spoils(state, graph)
    from game.headless.map.standard import PRUNED_PROFILES, SPOILS_PROFILE, profile_for
    if state.ancient_start is not None:
        if not isinstance(state.ancient_start, AncientStart):
            raise ValueError("Invalid Ancient start ownership.")
        state.ancient_start.validate(state, graph, cards)
    if state.pending is not None and state.pending.get("kind") == "ancient" and state.ancient_start is None:
        raise ValueError("Ancient choice has no owner.")
    from game.headless.map.golden_path import PROFILE as GOLDEN
    from game.headless.relics.ancient_map import validate as validate_ancient_map
    validate_ancient_map(state, graph)
    has_unknowns = graph is not None and graph.generation in (*PRUNED_PROFILES, GOLDEN)
    if has_unknowns != (state.unknown_rooms is not None):
        raise ValueError("Unknown room state requires its generated map profile.")
    if has_unknowns != (state.event_progression is not None):
        raise ValueError("Event progression requires its generated map profile.")
    if has_unknowns:
        if not isinstance(state.unknown_rooms, UnknownRooms) or state.config is None:
            raise ValueError("Invalid unknown room ownership.")
        state.unknown_rooms.validate(state, graph)
        if not isinstance(state.event_progression, EventProgression):
            raise ValueError("Invalid event progression ownership.")
        state.event_progression.validate(state, graph)
    generated = graph is not None and graph.generation is not None
    if generated != (state.encounter_progression is not None):
        raise ValueError("Generated map and encounter progression must be owned together.")
    if generated:
        if not isinstance(state.encounter_progression, EncounterProgression) or state.config is None:
            raise ValueError("Invalid generated run configuration.")
        if state.config.campaign and state.act_index:
            root = graph.node(f'act{state.act_index + 1}.ancient')
            from game.headless.map.standard import ancients_for
            if root.row != 0 or root.kind != 'event' or root.event_id not in ancients_for(state.config.act):
                raise ValueError('Campaign act is missing its Ancient entrance.')
            if state.initialization is not None and root.event_id != state.initialization['acts'][state.act_index]['ancient']:
                raise ValueError('Ancient entrance differs from native initialization.')
        if bool(state.encounter_progression.second_boss) != (state.config.act == "glory" and state.config.ascension >= 10):
            raise ValueError("Second boss differs from ascension.")
        if state.act_completion is not None and state.encounter_progression.second_boss and graph.generation != GOLDEN and state.act_completion.boss_encounter_id != state.encounter_progression.second_boss:
            raise ValueError("Second boss must be defeated before completing the act.")
        if state.encounter_progression.act != state.config.act:
            raise ValueError('Encounter progression differs from declared act.')
        if graph.generation not in (GOLDEN, profile_for(state.config.act), profile_for(state.config.act, base=True), *((SPOILS_PROFILE,) if state.config.act == "hive" else ())):
            raise ValueError('Generated map differs from declared act.')
        if getattr(state.rng, "native", False) and state.initialization is None:
            raise ValueError("Generated native run requires its initialization record.")
        if state.phase is RunPhase.SLICE_COMPLETE or state.phase is RunPhase.VICTORY and state.epilogue_event_id is None:
            raise ValueError("Generated Act 1 success requires boss act completion.")
        if state.current_node_id is not None and room_node(state, graph, state.current_node_id).kind == "boss":
            selecting = state.phase is RunPhase.ROUTE and state.pending is not None and state.pending.get("kind") == "node"
            between_bosses = (state.phase is RunPhase.ROUTE and state.pending is None
                and state.encounter_progression.second_boss is not None and graph.node(state.current_node_id).next_node_ids
                and state.encounter_progression.assignments.get(state.current_node_id) == state.encounter_progression.boss)
            if not selecting and not between_bosses and state.epilogue_event_id is None and state.phase not in (RunPhase.COMBAT, RunPhase.REWARD, RunPhase.ACT_COMPLETE, RunPhase.DEFEAT):
                raise ValueError("Generated boss cannot return to between-room navigation.")
        if any(n.kind == "event" and n.row != 0 and n.event_id not in state.config.event_pool for n in graph.nodes):
            raise ValueError("Generated event differs from its declared pool.")
        state.encounter_progression.validate(graph, state.visited_nodes,
            pending_node=state.pending is not None and state.pending.get("kind") == "node",
            room_kinds={node_id: room_node(state, graph, node_id).kind for node_id in state.visited_nodes})
        if sum(len(a.encounter_progression.assignments) for a in state.completed_acts) + len(state.encounter_progression.assignments) + len(state.event_combats) != state.combats_completed + (state.phase is RunPhase.COMBAT):
            raise ValueError("Encounter history differs from completed/active combats.")


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
        if state.phase is not RunPhase.ROUTE or graph is None or pending["node_id"] != state.current_node_id or pending["room_kind"] != room_node(state, graph, state.current_node_id).kind:
            raise ValueError("Invalid pending map node.")
    elif kind == "reward":
        expected = {"kind", "gold", "gold_claimed", "offers", "card_resolved", "card_modifiers"}
        if "combat_reward" in pending:
            expected |= {"combat_reward", "encounter_id", "potion", "potion_claimed", "relic", "relic_claimed", "relic_instance_id", "extra_rewards", "hunt_rewards_earned", "royalties_earned", "gold_bonus_sources"}
        from game.headless.relics.reward_alternatives import validate_marker
        validate_marker(state, pending)
        if pending.get('encounter_id') in ('underdocks_gremlin_merc', 'hive_thieving_hopper'):
            expected.add('encounter_loot')
        if set(pending) - {"rerolled"} != expected:
            raise ValueError("Invalid reward state fields.")
        if state.phase is not RunPhase.REWARD or type(pending["gold"]) is not int or pending["gold"] < 0:
            raise ValueError("Invalid pending reward.")
        if type(pending["gold_claimed"]) is not bool or type(pending["card_resolved"]) is not bool:
            raise ValueError("Invalid reward resolution flags.")
        for definition_id in pending["offers"]:
            cards.definition(definition_id)
        final_boss = pending.get('combat_reward') and pending.get('encounter_id') in ENCOUNTERS and ENCOUNTERS[pending['encounter_id']].room_kind == 'boss' and ENCOUNTERS[pending['encounter_id']].act == 3
        if not isinstance(pending["offers"], list) or not pending["offers"] and not final_boss:
            raise ValueError("Invalid reward offers.")
        from game.headless.relics.rewards import validate_modifiers, validate_extra, validate_combat_offers
        validate_combat_offers(state, cards, pending["offers"])
        validate_modifiers(cards, pending["offers"], pending["card_modifiers"], indexed=True)
        if "combat_reward" in pending:
            from game.headless.encounters import loot
            loot.validate(pending['encounter_id'], pending.get('encounter_loot'), cards)
            validate_extra(state, cards, pending["extra_rewards"], hunt_rewards_earned=pending["hunt_rewards_earned"], royalties_earned=pending["royalties_earned"])
            encounter_id = pending["encounter_id"]
            if encounter_id is not None and encounter_id not in ENCOUNTERS:
                raise ValueError("Unknown reward encounter.")
            encounter = None if encounter_id is None else ENCOUNTERS[encounter_id]
            low, high = (10, 20) if encounter is None else encounter.gold_range
            from game.headless.core.ascension import gold_range
            low, high = gold_range(state, (low, high)) if encounter is None or encounter.ascension_gold else (low, high)
            low, high = loot.gold_range(low, high, pending.get("encounter_loot"))
            if graph is not None and state.current_node_id is not None:
                selected = event_combat.encounter_at_current_room(state) or encounter_at(state, room_node(state, graph, state.current_node_id))
                if selected != encounter_id:
                    raise ValueError("Reward encounter differs from its room.")
            pool = state.config.boss_reward_cards if state.config is not None and encounter is not None and encounter.room_kind == "boss" else (() if state.config is None else state.config.reward_cards)
            from game.headless.relics.run_rules import has, owned
            from game.headless.relics.rewards import extend_pool
            pool = extend_pool(state, cards, pool)
            sources = pending["gold_bonus_sources"]
            owners = {r.instance_id: r.definition_id for r in state.relics}
            if (not isinstance(sources, list) or any(not isinstance(i, str) for i in sources)
                    or len(set(sources)) != len(sources)
                    or any(owners.get(i) != "amethyst_aubergine" for i in sources)):
                raise ValueError("Invalid generated gold bonus ownership.")
            # Later pickups cannot change a previously generated reward amount.
            bonus = 15 * len(sources)
            low, high = low + bonus, high + bonus
            if final_boss:
                low = high = 0
                owners = {r.instance_id: (r.definition_id, r.counter) for r in state.relics}
                if (sources or not pending['gold_claimed'] or not pending['card_resolved'] or pending['offers']
                        or pending['potion'] is not None or pending['hunt_rewards_earned'] or pending['royalties_earned']
                        or any(owners.get(r['source']) != ('wongos_mystery_ticket', 6) for r in pending['extra_rewards'])):
                    raise ValueError('Final boss cannot offer ordinary combat rewards.')
            from game.headless.relics.rewards import active_power_options
            extra_power = active_power_options(state)
            if (pending["combat_reward"] is not True or state.config is None
                    or type(pending["potion_claimed"]) is not bool
                    or not low <= pending["gold"] <= high
                    or len(pending["offers"]) not in ((0,) if final_boss else range(3, 4 + extra_power))
                    or not set(pending["offers"]) <= set(pool)
                    or (pending["potion"] is not None and pending["potion"] not in state.config.reward_potions)
                    or (pending["potion"] is None and pending["potion_claimed"])):
                raise ValueError("Invalid combat reward bundle.")
            relic = pending["relic"]
            if type(pending["relic_claimed"]) is not bool:
                raise ValueError("Invalid relic claim flag.")
            expects_relic = encounter is not None and encounter.gives_relic
            if expects_relic != (relic is not None) or (relic is None and pending["relic_claimed"]):
                raise ValueError("Relic reward does not match encounter kind.")
            if relic is not None:
                claimed = next((r for r in state.relics if r.instance_id == pending["relic_instance_id"]), None)
                if (relic not in (*state.config.reward_relics, state.config.relic_fallback)
                        or pending["relic_claimed"] != (claimed is not None)
                        or claimed is not None and claimed.definition_id != relic
                        or not pending["relic_claimed"] and pending["relic_instance_id"] is not None
                        or not RELICS[relic].stackable and any(r.definition_id == relic for r in state.relics) != pending["relic_claimed"]):
                    raise ValueError("Invalid relic offer or ownership.")
                if relic == state.config.relic_fallback and not all(any(r.definition_id == name for r in state.relics) for name in state.config.reward_relics):
                    raise ValueError("Fallback requires an exhausted restricted relic pool.")
            elif pending["relic_instance_id"] is not None:
                raise ValueError("Missing relic has a claimed instance.")
    elif kind == "ancient":
        if state.ancient_start is None:
            raise ValueError("Ancient choice has no owner.")
        state.ancient_start.validate(state, graph, cards)
    elif kind == "scripted_event":
        from game.headless.run.events import validate_event
        validate_event(state, graph, cards=cards)
    elif kind == "treasure":
        from game.headless.run.treasure_validation import validate_treasure
        validate_treasure(state, graph)
    elif kind == "shop":
        from game.headless.run.shop_validation import validate_shop
        validate_shop(state, cards, graph)
    elif kind == "rest_site":
        if state.phase is not RunPhase.ROOM or pending["stage"] not in ("options", "smith", "resolved", "hatched", "cook"):
            raise ValueError("Invalid rest-site phase.")
        used = pending.get("used")
        if not isinstance(used, list) or len(used) != len(set(used)) or any(v not in ("rest", "smith", "hatch", "lift", "dig", "cook", "clone", "kindle") for v in used):
            raise ValueError("Invalid rest actions history.")
        if pending["stage"] == "cook":
            from game.headless.run.rest_site import validate_cook
            validate_cook(state)
            return
        if pending["stage"] == "hatched":
            from game.headless.run.hatching import validate
            validate(state, cards)
            return
        if pending["stage"] == "smith":
            from game.headless.run.rest_site import eligible_upgrades
            if not pending["eligible"] or pending["eligible"] != list(eligible_upgrades(state)):
                raise ValueError("Invalid smith selection.")
            expected = {"kind", "stage", "eligible", "used"}
        else:
            expected = {"kind", "stage", "used"}
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
