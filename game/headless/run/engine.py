"""Persistent run ownership and combat handoff, independent of external interfaces."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.combat import CombatEngine
from game.headless.core.rng import GameRandomService
from game.headless.map.graph import MapGraph
from game.headless.run.deck import add_card, find_card, upgrade_card
from game.headless.run.state import RunPhase, RunState
from game.headless.run.config import RunConfig
from game.headless.run.inventory import add_relic
from game.headless.potions.base import POTIONS
from game.headless.relics.base import RELICS
from game.headless.encounters.catalog import ENCOUNTERS


class RunEngine:
    def __init__(self, *, seed: int = 0, card_ids=None, max_hp: int = 80, hp: int | None = None,
                 gold: int = 0, cards=DEFAULT_CARDS, graph: MapGraph | None = None,
                 config: RunConfig | None = None, rng_profile="fixture") -> None:
        self.cards = cards
        self.graph = graph
        from game.headless.core.native_service import NativeRandomService
        if rng_profile not in ("fixture", "native"):
            raise ValueError("Unsupported randomness profile.")
        rng = NativeRandomService(seed) if rng_profile == "native" else GameRandomService(seed)
        self.state = RunState(seed, max_hp, max_hp if hp is None else hp, gold, [], rng)
        if rng_profile == "native":
            from game.headless.generation.odds import initial
            self.state.generation_odds = initial()
            from game.headless.generation.relics import populate
            self.state.relic_bags = populate(rng)
        self.state.config = config
        if config is not None and config.ascension >= 4:
            self.state.potion_capacity = 2
            self.state.potions = [None] * 2
        if config is not None:
            for card_id in (*config.reward_cards, *config.boss_reward_cards):
                cards.definition(card_id)
            if any(r not in RELICS or r == "burning_blood" or RELICS[r].stackable for r in config.reward_relics):
                raise ValueError("Unsupported relic reward pool.")
            if any(p not in POTIONS for p in config.reward_potions):
                raise ValueError("Unsupported potion reward pool.")
        if self.state.hp == 0:
            self.state.phase = RunPhase.DEFEAT
        self.combat: CombatEngine | None = None
        if card_ids is None:
            card_ids = ("strike",) * 5 + ("defend",) * 4 + ("bash",)
        for definition_id in card_ids:
            add_card(self.state, cards.definition(definition_id))
        if config is not None and config.ascension >= 5:
            add_card(self.state, cards.definition("ascenders_bane"))
        self.state.validate()

    @classmethod
    def ironclad_slice(cls, *, seed: int = 0, ascension: int = 0, route: str = "first-slice", boss=None, elite=None, hallway=None):
        """Native starter inventory on a named, restricted authored route."""
        from game.headless.run.scenarios import ROUTES
        if route not in ROUTES:
            raise ValueError("Unsupported authored route.")
        config = RunConfig(ascension=ascension)
        overrides = {name: value for name, value in (("boss", boss), ("elite", elite), ("hallway", hallway)) if value is not None}
        if overrides and route != "overgrowth-act1":
            raise ValueError("Encounter overrides require the authored Act 1 route.")
        engine = cls(seed=seed, max_hp=80, hp=64 if ascension >= 2 else 80, gold=99, config=config,
                     graph=ROUTES[route](**overrides))
        add_relic(engine.state, "burning_blood")
        return engine

    @classmethod
    def ironclad_act1(cls, *, seed=0, act="overgrowth", ascension=0, discovery="all_seen", map_profile=None, ancient_profile=None, rng_profile="native", cards=DEFAULT_CARDS):
        """Generate a full-length A0 map with declared restricted content pools."""
        from game.headless.map.act1 import generate_act1_map, profile_for, PRUNED_PROFILES
        map_profile = map_profile or profile_for(act)
        from game.headless.encounters.progression import EncounterProgression
        from game.headless.run.unknown_rooms import UnknownRooms
        from game.headless.events.progression import EventProgression
        from game.headless.run import ancient
        if ancient_profile not in (None, ancient.PROFILE, ancient.RESTRICTED_PROFILE):
            raise ValueError("Unsupported Ancient start profile.")
        from game.headless.potions.pools import ORDINARY_POTIONS
        from game.headless.relics.pools import ORDINARY_RELICS, SHOP_RELICS
        config = RunConfig(act=act, ascension=ascension, relic_fallback="circlet", reward_relics=ORDINARY_RELICS, shop_relics=SHOP_RELICS, reward_potions=ORDINARY_POTIONS)
        if act == "overgrowth" and map_profile in PRUNED_PROFILES:
            config = replace(config, event_pool=(*config.event_pool, "morphic_grove", "tablet_of_truth",
                                                     "whispering_hollow", "wellspring", "slippery_bridge", "sunken_statue", "dense_vegetation", "sapphire_seed", "byrdonis_nest"))
        if act == 'underdocks':
            from game.headless.generation.room_pools import ACT1_POOLS, SHARED_EVENTS, ACT1_INELIGIBLE_EVENTS
            config = replace(config, event_pool=(*ACT1_POOLS[act][3], *(e for e in SHARED_EVENTS if e not in ACT1_INELIGIBLE_EVENTS)))
        engine = cls(seed=seed, gold=99, config=config, rng_profile=rng_profile, cards=cards)
        if getattr(engine.state.rng, "native", False):
            if discovery != "all_seen":
                raise ValueError("Only declared all-seen Act 1 discovery is supported.")
            from game.headless.generation.initialization import generate
            from game.headless.encounters.progression import native_ids
            ids = native_ids(act)
            engine.state.initialization = generate(engine.state.rng, act=act, ascension=ascension)
            initial = engine.state.initialization["acts"][0]
            engine.state.encounter_progression = EncounterProgression(
                [ids[n] for n in initial["normal"]], [ids[n] for n in initial["elites"]], ids[initial["boss"]], act=act)
        else:
            engine.state.encounter_progression = EncounterProgression.generate(engine.state.rng, discovery=discovery, act=act)
        if act == "overgrowth" and map_profile in PRUNED_PROFILES:
            from game.headless.events.act1_content import DEFINITIONS as remaining_events
            config = replace(config, event_pool=(*config.event_pool, *(d.definition_id for d in remaining_events)))
            engine.state.config = config
        engine.graph = generate_act1_map(engine.state.rng, event_pool=config.event_pool, act=act, profile=map_profile, ascension=ascension)
        if engine.graph.generation in PRUNED_PROFILES:
            engine.state.unknown_rooms = UnknownRooms()
            if engine.state.initialization is not None:
                from game.headless.events.progression import NATIVE_PROFILE
                engine.state.event_progression = EventProgression(list(initial["events"]), profile=NATIVE_PROFILE)
            else:
                engine.state.event_progression = EventProgression.generate(engine.state.rng, config.event_pool)
        add_relic(engine.state, "burning_blood")
        if ancient_profile is None:
            from game.headless.core.ascension import ancient_heal
            ancient_heal(engine.state, neow=True)
        if ancient_profile is not None:
            ancient.begin(engine.state, profile=ancient_profile, cards=engine.cards)
        return engine

    @classmethod
    def ironclad_run(cls, *, seed=0, first_act="overgrowth", last_act="glory", ancient_profile=None, rng_profile="native", cards=DEFAULT_CARDS, ascension=0):
        """Play through Glory and the Architect; optionally stop after Hive."""
        if last_act not in ("hive", "glory"):
            raise ValueError("Unsupported campaign endpoint.")
        engine = cls.ironclad_act1(seed=seed, act=first_act, ancient_profile=ancient_profile,
                                   rng_profile=rng_profile, cards=cards, ascension=ascension)
        engine.state.config = replace(engine.state.config, campaign=(first_act, 'hive', 'glory') if last_act == 'glory' else (first_act, 'hive'))
        return engine

    def advance_act(self):
        from game.headless.run.campaign import advance
        return advance(self)

    def legal_actions(self) -> tuple:
        from game.headless.run.flow import legal_actions
        return legal_actions(self)

    def apply(self, action):
        from game.headless.run.flow import apply
        result = apply(self, action)
        from game.headless.relics.neow import drain
        drain(self.state, self.cards)
        from game.headless.run.shop import resume_parasol
        resume_parasol(self.state, self.cards)
        from game.headless.events.steps import drain as resume_event
        resume_event(self.state, self.cards)
        if self.combat is not None:
            self.sync_combat_loot()
        from game.headless.relics.ancient_map import update
        update(self)
        from game.headless.events.checkpoint import refresh
        refresh(self.state)
        return result

    def obtain_relic(self, definition_id, *, card_pool=None):
        self.state.require_between_rooms()
        before, graph = deepcopy(self.state), self.graph
        try:
            result = add_relic(self.state, definition_id, cards=self.cards, card_pool=card_pool)
            from game.headless.relics.ancient_map import update
            update(self)
            return result
        except Exception:
            self.state, self.graph = before, graph
            raise

    def preview_upgrade(self, instance_id: str):
        self.state.require_between_rooms()
        return find_card(self.state, instance_id).preview_upgrade()

    def upgrade_card(self, instance_id: str):
        self.state.require_between_rooms()
        return upgrade_card(self.state, instance_id)

    def start_combat(self, *, encounter_id: str | None = None, encounter_factory=None, enemy_factory=None, energy_per_turn=3, cards_per_turn=5) -> CombatEngine:
        if encounter_id is None and encounter_factory is not None:
            registered = next((name for name, definition in ENCOUNTERS.items() if definition is encounter_factory or definition.factory is encounter_factory), None)
            if registered is not None:
                encounter_id, encounter_factory = registered, None
        room_kind = "combat"
        if encounter_id is not None:
            if encounter_id not in ENCOUNTERS or encounter_factory is not None or enemy_factory is not None:
                raise ValueError("Unsupported or ambiguous encounter.")
            encounter_factory = ENCOUNTERS[encounter_id]
            if encounter_factory.event_id is not None:
                raise ValueError("Event encounters require their event combat transition.")
            room_kind = encounter_factory.room_kind
            if encounter_factory.gives_relic:
                from game.headless.run.rewards import eligible_relics
                if self.state.config is None or not eligible_relics(self.state):
                    raise ValueError("The restricted elite relic pool has no available reward.")
        self.state.require_room_entry(room_kind)
        if self.state.pending is None:
            from game.headless.relics.run_rules import entered_room
            entered_room(self.state, room_kind)
        if self.state.pending is not None and self.graph is not None:
            from game.headless.encounters.progression import encounter_at
            from game.headless.run.unknown_rooms import room_node
            selected_id = encounter_at(self.state, room_node(self.state, self.graph, self.state.current_node_id))
            if selected_id is not None and selected_id != encounter_id:
                raise ValueError("Combat must match the selected encounter.")
        rng, combat = self._prepare_combat(encounter_factory=encounter_factory, enemy_factory=enemy_factory,
                                           energy_per_turn=energy_per_turn, cards_per_turn=cards_per_turn)
        if self.state.encounter_progression is not None:
            if self.graph is None or self.state.pending is None or self.state.current_node_id in self.state.encounter_progression.assignments:
                raise ValueError("Generated encounters require a new selected map room.")
            self.state.encounter_progression.assignments[self.state.current_node_id] = encounter_id
        self.state.rng = rng
        self.state.pending = None
        self.state.phase = RunPhase.COMBAT
        self.state.active_encounter_id = encounter_id
        if encounter_id is not None:
            self.state.act_index = ENCOUNTERS[encounter_id].act - 1
        self.combat = combat
        self.sync_combat_loot()
        if combat.done:
            self.finish_combat()
        return combat

    def _prepare_combat(self, *, encounter_factory=None, enemy_factory=None, energy_per_turn=3, cards_per_turn=5):
        # Build against an independent stream snapshot, committing only on success.
        from game.headless.core.rng import from_snapshot
        rng = from_snapshot(self.state.rng.snapshot())
        seed = 0 if getattr(rng, "native", False) else rng.randint("combat_launch", 0, (1 << 63) - 1)
        deck = deepcopy(self.state.deck)
        combat = CombatEngine(seed=seed, deck_factory=lambda: deepcopy(deck),
                              encounter_factory=encounter_factory, enemy_factory=enemy_factory,
                              player_max_hp=self.state.max_hp, energy_per_turn=energy_per_turn,
                              cards_per_turn=cards_per_turn, cards=self.cards, ascension=self.state.config.ascension if self.state.config else 0)
        if getattr(rng, "native", False):
            from game.headless.core.native_service import COMBAT_STREAMS
            combat.native_streams = {name:rng.stream(name) for name in COMBAT_STREAMS}
            combat.rng = combat.native_streams["monster_ai"]
            from game.headless.encounters.catalog import NATIVE_OVERGROWTH_ENCOUNTERS, NATIVE_UNDERDOCKS_ENCOUNTERS, NATIVE_HIVE_ENCOUNTERS, NATIVE_GLORY_ENCOUNTERS
            import re
            from game.headless.encounters.randomness import EncounterRandom
            native_type = next((key for key, value in {**NATIVE_OVERGROWTH_ENCOUNTERS, **NATIVE_UNDERDOCKS_ENCOUNTERS, **NATIVE_HIVE_ENCOUNTERS, **NATIVE_GLORY_ENCOUNTERS}.items()
                                if ENCOUNTERS[value] is encounter_factory), None)
            if getattr(encounter_factory, "event_id", None) == "dense_vegetation":
                native_type = "DenseVegetationEventEncounter"
            from game.headless.encounters.extended_events import NATIVE_IDS
            native_type = native_type or next((n for key,n in NATIVE_IDS.items() if ENCOUNTERS[key] is encounter_factory), None)
            if native_type is not None:
                # Generated maps start after Ancient, including when its optional
                # choice was skipped. Native history counts that root as floor 1.
                ancient_floor = int(self.state.initialization is not None or self.state.ancient_start is not None)
                combat.encounter_rng = EncounterRandom(
                    rng.root_seed, self.state.visited_room_count + ancient_floor,
                    re.sub(r"(?<!^)(?=[A-Z])", "_", native_type).upper(),
                    combat.rng, combat.native_streams["niche"], ascension=combat.ascension,
                )
        room_kind = getattr(encounter_factory, "room_kind", "combat")
        from game.headless.relics.ancient_map import coat_active
        combat.fur_coat_active = coat_active(self)
        combat.reset(relics=self.state.relics, initial_hp=self.state.hp, room_kind=room_kind,
                     potion_capacity=len(self.state.potions), potion_slots=self.state.potions.count(None), potions=self.state.potions,
                     gold=self.state.gold, potion_pool=self.state.config.reward_potions if self.state.config else None)
        return rng, combat

    def sync_combat_loot(self):
        from game.headless.run.inventory import add_potion
        from game.headless.encounters.theft import synchronize as sync_theft
        sync_theft(self.state, self.combat.player)
        r = self.combat.player.rules
        from game.headless.relics.ancient_state import sync_cards
        sync_cards(self.state, self.combat.player)
        for card in self.state.deck:
            if card.definition.definition_id == 'the_scythe':
                card.permanent_damage += r.scythe_gains.get(card.instance_id, 0)
        r.scythe_gains.clear()
        for card in self.state.deck:
            if card.definition.definition_id == 'genetic_algorithm':
                card.permanent_block += r.genetic_gains.get(card.instance_id, 0)
        r.genetic_gains.clear()
        from game.headless.relics.combat import synchronize
        from game.headless.relics.damage import potions_changed
        synchronize(self.state, self.combat.player)
        self.state.gold += r.gold_gained - r.gold_lost
        r.gold_gained = r.gold_lost = 0
        r.gold_available = self.state.gold
        from game.headless.potions.base import PotionInstance
        self.state.potions = [None if item is None else PotionInstance(**item) for item in r.potions]
        for potion in r.potions_generated:
            add_potion(self.state, potion)
        from dataclasses import asdict
        r.potions = [None if item is None else asdict(item) for item in self.state.potions]
        r.potions_generated.clear()
        r.potion_slots = self.state.potions.count(None)
        potions_changed(self.combat.player)

    def finish_combat(self) -> None:
        if self.state.phase is not RunPhase.COMBAT or self.combat is None or not self.combat.done:
            raise ValueError("The owned combat is not finished.")
        self.sync_combat_loot()
        encounter_id = self.state.active_encounter_id
        self.state.active_encounter_id = None
        self.state.max_hp = self.combat.player.max_hp
        self.state.hp = self.combat.player.hp
        self.state.combats_completed += 1
        self.state.phase = RunPhase.ROUTE if self.combat.winner == "player" else RunPhase.DEFEAT
        from game.headless.relics.combat import owned, memory
        lamp = owned(self.combat.player, "lava_lamp")
        undamaged = lamp is not None and not memory(self.combat.player, lamp).get("damaged", False)
        extra_cards = self.combat.player.rules.extra_card_rewards
        royalties = self.combat.player.rules.powers.get("royalties", 0)
        from game.headless.encounters.loot import capture as capture_loot
        encounter_loot = capture_loot(encounter_id, self.combat.enemies)
        from game.headless.encounters.theft import finish as finish_theft
        finish_theft(self.state, encounter_loot)
        improvement = self.combat.player.rules.powers.get("improvement", 0)
        selection_rng = self.combat.player.deck.selection_rng
        if self.state.event_combats and self.state.event_combats[-1].outcome is None:
            self.state.event_combats[-1].timed_out = any(getattr(e, "timed_out", False) for e in self.combat.enemies)
        self.combat = None
        from game.headless.run.event_combat import finish
        finish(self.state, encounter_id, won=self.state.phase is RunPhase.ROUTE)
        from game.headless.run.lifecycle import after_combat
        after_combat(self.state, won=self.state.phase is RunPhase.ROUTE,
                     elite=encounter_id is not None and ENCOUNTERS[encounter_id].room_kind == "elite",
                     cards=self.cards, improvement=improvement, selection_rng=selection_rng,
                     room_kind=ENCOUNTERS[encounter_id].room_kind if encounter_id is not None else "combat")
        if self.state.phase is RunPhase.ROUTE:
            if encounter_id and encounter_id.startswith("battleworn_dummy_"):
                from game.headless.run.event_combat import resume
                resume(self.state, self.cards)
            elif self.state.config is not None:
                from game.headless.run.rewards import begin_combat_rewards
                begin_combat_rewards(self.state, self.cards, encounter_id=encounter_id, undamaged=undamaged, extra_cards=extra_cards, royalties=royalties, encounter_loot=encounter_loot)

    def available_nodes(self) -> tuple[str, ...]:
        self.state.require_between_rooms()
        from game.headless.run.map_travel import available
        return () if self.graph is None else available(self.state, self.graph)

    def choose_node(self, node_id: str):
        if node_id not in self.available_nodes():
            raise ValueError("Map node is unavailable.")
        node = self.graph.node(node_id)
        if node.kind == "unknown":
            from game.headless.run.unknown_rooms import prepare_unknown
            rng, unknown, progression, node = prepare_unknown(self.state, self.graph, node)
            self.state.rng, self.state.unknown_rooms = rng, unknown
            self.state.event_progression = progression
        from game.headless.relics.run_rules import entered_room
        if node.row != 0:
            entered_room(self.state, node.kind, unknown=self.graph.node(node_id).kind == "unknown")
        from game.headless.run.map_travel import entered
        entered(self.state, self.graph, self.state.current_node_id, node_id)
        self.state.current_node_id = node_id
        self.state.visited_nodes.append(node_id)
        self.state.pending = {"kind": "node", "node_id": node_id, "room_kind": node.kind}
        if node.kind == "terminal":
            self.state.pending = None
            self.state.phase = RunPhase.VICTORY
        elif node.kind == "slice_end":
            self.state.pending = None
            self.state.phase = RunPhase.SLICE_COMPLETE
        return node

    def snapshot(self) -> dict:
        from game.headless.run.snapshots import capture_run
        return capture_run(self)

    def restore(self, snapshot: dict) -> None:
        from game.headless.run.snapshots import restore_run
        restored = restore_run(snapshot, cards=self.cards)
        self.state, self.combat, self.graph = restored.state, restored.combat, restored.graph
