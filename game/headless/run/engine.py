"""Persistent run ownership and combat handoff, independent of external interfaces."""

from __future__ import annotations

from copy import deepcopy

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


class RunEngine:
    def __init__(self, *, seed: int = 0, card_ids=None, max_hp: int = 80, hp: int | None = None,
                 gold: int = 0, cards=DEFAULT_CARDS, graph: MapGraph | None = None,
                 config: RunConfig | None = None) -> None:
        self.cards = cards
        self.graph = graph
        self.state = RunState(seed, max_hp, max_hp if hp is None else hp, gold, [], GameRandomService(seed))
        self.state.config = config
        if config is not None:
            for card_id in config.reward_cards:
                cards.definition(card_id)
            if any(p not in POTIONS for p in config.reward_potions):
                raise ValueError("Unsupported potion reward pool.")
        if self.state.hp == 0:
            self.state.phase = RunPhase.DEFEAT
        self.combat: CombatEngine | None = None
        if card_ids is None:
            card_ids = ("strike",) * 5 + ("defend",) * 4 + ("bash",)
        for definition_id in card_ids:
            add_card(self.state, cards.definition(definition_id))
        self.state.validate()

    @classmethod
    def ironclad_slice(cls, *, seed: int = 0, ascension: int = 0):
        """Native starter inventory on a restricted authored two-combat route."""
        from game.headless.run.scenarios import first_slice_map
        engine = cls(seed=seed, max_hp=80, gold=99, config=RunConfig(ascension=ascension),
                     graph=first_slice_map())
        add_relic(engine.state, "burning_blood")
        return engine

    def legal_actions(self) -> tuple:
        from game.headless.run.flow import legal_actions
        return legal_actions(self)

    def apply(self, action):
        from game.headless.run.flow import apply
        return apply(self, action)

    def preview_upgrade(self, instance_id: str):
        self.state.require_between_rooms()
        return find_card(self.state, instance_id).preview_upgrade()

    def upgrade_card(self, instance_id: str):
        self.state.require_between_rooms()
        return upgrade_card(self.state, instance_id)

    def start_combat(self, *, encounter_factory=None, enemy_factory=None, energy_per_turn=3, cards_per_turn=5) -> CombatEngine:
        self.state.require_room_entry("combat")
        # Build against an independent stream snapshot, committing only on success.
        rng = GameRandomService(self.state.seed)
        rng.restore(self.state.rng.snapshot())
        seed = rng.randint("combat_launch", 0, (1 << 63) - 1)
        deck = deepcopy(self.state.deck)
        combat = CombatEngine(seed=seed, deck_factory=lambda: deepcopy(deck),
                              encounter_factory=encounter_factory, enemy_factory=enemy_factory,
                              player_max_hp=self.state.max_hp, energy_per_turn=energy_per_turn,
                              cards_per_turn=cards_per_turn)
        combat.reset()
        combat.player.hp = self.state.hp
        self.state.rng = rng
        self.state.pending = None
        self.state.phase = RunPhase.COMBAT
        self.combat = combat
        return combat

    def finish_combat(self) -> None:
        if self.state.phase is not RunPhase.COMBAT or self.combat is None or not self.combat.done:
            raise ValueError("The owned combat is not finished.")
        self.state.hp = self.combat.player.hp
        self.state.combats_completed += 1
        self.state.phase = RunPhase.ROUTE if self.combat.winner == "player" else RunPhase.DEFEAT
        self.combat = None
        if self.state.phase is RunPhase.ROUTE:
            for relic in self.state.relics:
                RELICS[relic.definition_id].after_combat_victory(self.state)
            if self.state.config is not None:
                from game.headless.run.rewards import begin_combat_rewards
                begin_combat_rewards(self.state, self.cards)

    def available_nodes(self) -> tuple[str, ...]:
        self.state.require_between_rooms()
        return () if self.graph is None else self.graph.available_nodes(self.state.current_node_id)

    def choose_node(self, node_id: str):
        if node_id not in self.available_nodes():
            raise ValueError("Map node is unavailable.")
        node = self.graph.node(node_id)
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
