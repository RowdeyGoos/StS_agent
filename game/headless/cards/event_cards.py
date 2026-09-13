"""Cards acquired through events and their permanent effects."""

from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.effects import DealDamage

BYRDONIS_EGG = CardDefinition("byrdonis_egg", (CardSpec("Byrdonis Egg", -1, "quest", uses_target=False),), ())
BYRD_SWOOP = CardDefinition("byrd_swoop", (
    CardSpec("Byrd Swoop", 0, "attack", base_damage=14),
    CardSpec("Byrd Swoop+", 0, "attack", base_damage=18),
), (DealDamage(),))
DEFINITIONS = (BYRDONIS_EGG, BYRD_SWOOP)
