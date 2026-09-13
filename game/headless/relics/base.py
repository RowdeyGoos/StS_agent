"""Owned relic instances and the first supported lifecycle effect."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class RelicDefinition:
    definition_id: str
    victory_heal: int = 0
    pickup_max_hp: int = 0

    def after_obtained(self, state) -> None:
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


RELICS = MappingProxyType({
    "burning_blood": RelicDefinition("burning_blood", victory_heal=6),
    "strawberry": RelicDefinition("strawberry", pickup_max_hp=7),
    "pear": RelicDefinition("pear", pickup_max_hp=10),
    "mango": RelicDefinition("mango", pickup_max_hp=14),
})
