"""Owned relic instances and the first supported lifecycle effect."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class RelicDefinition:
    definition_id: str
    victory_heal: int

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


RELICS = MappingProxyType({"burning_blood": RelicDefinition("burning_blood", victory_heal=6)})
