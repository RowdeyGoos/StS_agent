"""Event cards and the first supported colorless transformation targets."""

from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.effects import DealDamage, GainBlock, DrawCards

BYRDONIS_EGG = CardDefinition("byrdonis_egg", (CardSpec("Byrdonis Egg", -1, "quest", uses_target=False),), ())
BYRD_SWOOP = CardDefinition("byrd_swoop", (
    CardSpec("Byrd Swoop", 0, "attack", base_damage=14),
    CardSpec("Byrd Swoop+", 0, "attack", base_damage=18),
), (DealDamage(),))
FINESSE = CardDefinition("finesse", (
    CardSpec("Finesse", 0, "skill", block_gain=4, draw_count=1, uses_target=False),
    CardSpec("Finesse+", 0, "skill", block_gain=7, draw_count=1, uses_target=False),
), (GainBlock(), DrawCards()))
FLASH_OF_STEEL = CardDefinition("flash_of_steel", (
    CardSpec("Flash of Steel", 0, "attack", base_damage=5, draw_count=1),
    CardSpec("Flash of Steel+", 0, "attack", base_damage=8, draw_count=1),
), (DealDamage(), DrawCards()))
DEFINITIONS = (BYRDONIS_EGG, BYRD_SWOOP, FINESSE, FLASH_OF_STEEL)
