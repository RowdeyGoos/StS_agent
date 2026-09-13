"""Owned relic instances and the first supported lifecycle effect."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class RelicDefinition:
    definition_id: str
    victory_heal: int = 0
    pickup_max_hp: int = 0
    stackable: bool = False
    pickup_gold: int = 0
    combat_strength: int = 0
    evolve_after_elites: int = 0
    evolves_into: str | None = None
    allow_duplicates: bool = False

    def after_obtained(self, state) -> None:
        state.gold += self.pickup_gold
        state.max_hp += self.pickup_max_hp
        state.hp = min(state.max_hp, state.hp + self.pickup_max_hp)

    def after_combat_victory(self, state) -> int:
        if state.hp <= 0:
            return 0
        amount = min(self.victory_heal, state.max_hp - state.hp)
        state.hp += amount
        return amount


@dataclass(frozen=True, slots=True)
class RelicInstance:
    definition_id: str
    instance_id: str
    counter: int = 0


RELICS = MappingProxyType({
    "sword_of_stone": RelicDefinition("sword_of_stone", evolve_after_elites=5, evolves_into="sword_of_jade", allow_duplicates=True),
    "sword_of_jade": RelicDefinition("sword_of_jade", combat_strength=3, allow_duplicates=True),
    "golden_pearl": RelicDefinition("golden_pearl", pickup_gold=150),
    "nutritious_oyster": RelicDefinition("nutritious_oyster", pickup_max_hp=11),
    "circlet": RelicDefinition("circlet", stackable=True),
    "burning_blood": RelicDefinition("burning_blood", victory_heal=6),
    "strawberry": RelicDefinition("strawberry", pickup_max_hp=7),
    "pear": RelicDefinition("pear", pickup_max_hp=10),
    "mango": RelicDefinition("mango", pickup_max_hp=14),
})
