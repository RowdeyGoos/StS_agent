"""Persistent game state; no candidate, observation or artifact-manifest fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from game.headless.cards.base import Card
from game.headless.core.rng import GameRandomService
from game.headless.potions.base import POTIONS, PotionInstance
from game.headless.relics.base import RELICS, RelicInstance
from game.headless.run.config import RunConfig
from game.headless.encounters.progression import EncounterProgression
from game.headless.run.unknown_rooms import UnknownRooms
from game.headless.events.progression import EventProgression
from game.headless.run.ancient import AncientStart
from game.headless.events.combat import EventCombatRecord


class RunPhase(str, Enum):
    ROUTE = "route"
    COMBAT = "combat"
    REWARD = "reward"
    ROOM = "room"
    VICTORY = "victory"
    DEFEAT = "defeat"
    SLICE_COMPLETE = "slice_complete"
    ACT_COMPLETE = "act_complete"


@dataclass(frozen=True, slots=True)
class ActCompletion:
    act: int
    boss_encounter_id: str


@dataclass
class RunState:
    seed: int
    max_hp: int
    hp: int
    gold: int
    deck: list[Card]
    rng: GameRandomService
    phase: RunPhase = RunPhase.ROUTE
    next_card_id: int = 0
    combats_completed: int = 0
    current_node_id: str | None = None
    active_encounter_id: str | None = None
    act_completion: ActCompletion | None = None
    visited_nodes: list[str] = field(default_factory=list)
    # Pending gameplay data contains values, never callback closures or wire DTOs.
    pending: dict | None = None
    config: RunConfig | None = None
    relics: list[RelicInstance] = field(default_factory=list)
    potions: list[PotionInstance | None] = field(default_factory=lambda: [None] * 3)
    next_item_id: int = 0
    potion_drop_chance: int = 40
    next_shop_id: int = 0
    shop_removals_used: int = 0
    next_event_id: int = 0
    next_treasure_id: int = 0
    treasure_relics_drawn: list[str] = field(default_factory=list)
    encounter_progression: EncounterProgression | None = None
    unknown_rooms: UnknownRooms | None = None
    event_progression: EventProgression | None = None
    ancient_start: AncientStart | None = None
    event_combats: list[EventCombatRecord] = field(default_factory=list)

    def allocate_item_id(self) -> str:
        result = f"run.item.{self.next_item_id}"
        self.next_item_id += 1
        return result

    def allocate_card_id(self) -> str:
        allocated = {card.instance_id for card in self.deck}
        while f"run.card.{self.next_card_id}" in allocated:
            self.next_card_id += 1
        result = f"run.card.{self.next_card_id}"
        self.next_card_id += 1
        return result

    def require_between_rooms(self) -> None:
        if self.phase is not RunPhase.ROUTE or self.pending is not None or self.hp <= 0:
            raise ValueError("Operation requires a living run between rooms.")

    def require_room_entry(self, kind: str) -> None:
        if self.pending is None:
            self.require_between_rooms()
            return
        if (self.phase is not RunPhase.ROUTE or self.hp <= 0
                or self.pending.get("kind") != "node"
                or self.pending.get("room_kind") != kind):
            raise ValueError("Selected map node requires a different room.")

    def validate(self) -> None:
        if (self.phase is RunPhase.ACT_COMPLETE) != (self.act_completion is not None):
            raise ValueError("Act completion requires its terminal record.")
        if self.act_completion is not None and (not isinstance(self.act_completion, ActCompletion)
                or type(self.act_completion.act) is not int or self.act_completion.act != 1
                or not isinstance(self.act_completion.boss_encounter_id, str)
                or self.combats_completed < 1):
            raise ValueError("Invalid act completion record.")
        if self.active_encounter_id is not None and (not isinstance(self.active_encounter_id, str)
                or not self.active_encounter_id or self.phase is not RunPhase.COMBAT):
            raise ValueError("Encounter identity requires an active combat.")
        if type(self.max_hp) is not int or self.max_hp <= 0 or type(self.hp) is not int or not 0 <= self.hp <= self.max_hp:
            raise ValueError("Invalid run HP.")
        if type(self.gold) is not int or self.gold < 0:
            raise ValueError("Invalid run gold.")
        ids = [card.instance_id for card in self.deck]
        if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("Persistent card identities must be present and unique.")
        for card in self.deck:
            card.definition.spec_at(card.upgrade_level)
            if type(card.combats_seen) is not int or not 0 <= card.combats_seen < max(1, card.definition.combat_lifetime):
                raise ValueError("Invalid persistent card combat lifetime.")
        if type(self.next_card_id) is not int or self.next_card_id < 0 or type(self.combats_completed) is not int or self.combats_completed < 0:
            raise ValueError("Invalid run counters.")
        if (self.hp == 0) != (self.phase is RunPhase.DEFEAT):
            raise ValueError("Run HP and defeat phase disagree.")
        if not isinstance(self.phase, RunPhase):
            raise ValueError("Invalid run phase.")
        if self.config is not None and not isinstance(self.config, RunConfig):
            raise ValueError("Invalid run configuration.")
        if (type(self.next_shop_id) is not int or self.next_shop_id < 0
                or type(self.shop_removals_used) is not int
                or not 0 <= self.shop_removals_used <= self.next_shop_id):
            raise ValueError("Invalid shop counters.")
        if type(self.next_event_id) is not int or self.next_event_id < 0:
            raise ValueError("Invalid event allocator.")
        from game.headless.treasure.catalog import ORDINARY_CHEST
        if (type(self.next_treasure_id) is not int or self.next_treasure_id < 0
                or not isinstance(self.treasure_relics_drawn, list)
                or any(r not in ORDINARY_CHEST.relic_pool for r in self.treasure_relics_drawn)
                or len(set(self.treasure_relics_drawn)) != len(self.treasure_relics_drawn)
                or len(self.treasure_relics_drawn) > self.next_treasure_id):
            raise ValueError("Invalid treasure counters or depleted pool.")
        if type(self.next_item_id) is not int or self.next_item_id < 0:
            raise ValueError("Invalid item allocator.")
        if type(self.potion_drop_chance) is not int or not 0 <= self.potion_drop_chance <= 100 or self.potion_drop_chance % 10:
            raise ValueError("Invalid potion drop chance.")
        if len(self.potions) != 3:
            raise ValueError("The supported inventory has three potion slots.")
        items = [*self.relics, *(p for p in self.potions if p is not None)]
        item_ids = [item.instance_id for item in items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Item identities must be unique.")
        for item in items:
            if not isinstance(item.instance_id, str) or not item.instance_id.startswith("run.item."):
                raise ValueError("Invalid owned item identity.")
            suffix = item.instance_id.removeprefix("run.item.")
            if not suffix.isdecimal() or str(int(suffix)) != suffix or int(suffix) >= self.next_item_id:
                raise ValueError("Item identity exceeds its allocator.")
        if any(not isinstance(r, RelicInstance) or r.definition_id not in RELICS for r in self.relics):
            raise ValueError("Unsupported relic.")
        nonstackable = [r.definition_id for r in self.relics if not RELICS[r.definition_id].stackable and not RELICS[r.definition_id].allow_duplicates]
        if any(type(r.counter) is not int or not 0 <= r.counter < max(1, RELICS[r.definition_id].evolve_after_elites) for r in self.relics):
            raise ValueError("Invalid relic progression counter.")
        if len(set(nonstackable)) != len(nonstackable):
            raise ValueError("Duplicate relic definition.")
        if any(p is not None and (not isinstance(p, PotionInstance) or p.definition_id not in POTIONS) for p in self.potions):
            raise ValueError("Unsupported potion.")
