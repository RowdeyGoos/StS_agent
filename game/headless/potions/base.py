"""Supported unpowered potion effects, independent of cards and transport."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class PotionDefinition:
    definition_id: str
    damage: int = 0
    block: int = 0

    @property
    def targeted(self) -> bool:
        return self.damage > 0

    def use(self, combat, target_slot: int | None) -> None:
        if self.targeted:
            combat.enemies[target_slot].take_damage(self.damage, is_attack=False)
        else:
            combat.player.gain_block(self.block)


@dataclass(frozen=True, slots=True)
class PotionInstance:
    definition_id: str
    instance_id: str


POTIONS = MappingProxyType({
    "potion_shaped_rock": PotionDefinition("potion_shaped_rock", damage=15),
    "fire_potion": PotionDefinition("fire_potion", damage=20),
    "block_potion": PotionDefinition("block_potion", block=12),
})
