"""Cards acquired through events and their permanent effects."""

from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.effects import DealDamage

BYRDONIS_EGG = CardDefinition("byrdonis_egg", (CardSpec("Byrdonis Egg", -1, "quest", uses_target=False),), ())
BYRD_SWOOP = CardDefinition("byrd_swoop", (
    CardSpec("Byrd Swoop", 0, "attack", base_damage=14),
    CardSpec("Byrd Swoop+", 0, "attack", base_damage=18),
), (DealDamage(),))
from game.headless.cards.operations import Attack, CardOperation
NEOWS_FURY = CardDefinition("neows_fury", (
    CardSpec("Neow's Fury", 1, "attack", base_damage=10, exhausts=True),
    CardSpec("Neow's Fury+", 1, "attack", base_damage=14, exhausts=True),
), (Attack(), CardOperation("random_discard_to_hand", 2, 3)), rarity="ancient", pool="colorless", generate_in_combat=False)
DEFINITIONS = (BYRDONIS_EGG, BYRD_SWOOP, NEOWS_FURY)
