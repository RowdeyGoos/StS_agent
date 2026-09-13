"""Persistent game state; no candidate, observation or artifact-manifest fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from game.headless.cards.base import Card
from game.headless.core.rng import GameRandomService


class RunPhase(str, Enum):
    ROUTE = "route"
    COMBAT = "combat"
    REWARD = "reward"
    ROOM = "room"
    VICTORY = "victory"
    DEFEAT = "defeat"


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
    visited_nodes: list[str] = field(default_factory=list)
    # Pending gameplay data contains values, never callback closures or wire DTOs.
    pending: dict | None = None

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
        if type(self.max_hp) is not int or self.max_hp <= 0 or type(self.hp) is not int or not 0 <= self.hp <= self.max_hp:
            raise ValueError("Invalid run HP.")
        if type(self.gold) is not int or self.gold < 0:
            raise ValueError("Invalid run gold.")
        ids = [card.instance_id for card in self.deck]
        if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("Persistent card identities must be present and unique.")
        for card in self.deck:
            card.definition.spec_at(card.upgrade_level)
        if type(self.next_card_id) is not int or self.next_card_id < 0 or type(self.combats_completed) is not int or self.combats_completed < 0:
            raise ValueError("Invalid run counters.")
        if (self.hp == 0) != (self.phase is RunPhase.DEFEAT):
            raise ValueError("Run HP and defeat phase disagree.")
        if not isinstance(self.phase, RunPhase):
            raise ValueError("Invalid run phase.")
