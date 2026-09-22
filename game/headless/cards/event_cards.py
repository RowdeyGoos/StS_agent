"""Cards acquired through events and their permanent effects."""

from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.effects import DealDamage

BYRDONIS_EGG = CardDefinition("byrdonis_egg", (CardSpec("Byrdonis Egg", -1, "quest", uses_target=False),), (), rarity="quest", pool="event", generate_in_combat=False)
BYRD_SWOOP = CardDefinition("byrd_swoop", (
    CardSpec("Byrd Swoop", 0, "attack", base_damage=14),
    CardSpec("Byrd Swoop+", 0, "attack", base_damage=18),
), (DealDamage(),), rarity="event", pool="event", generate_in_combat=False)
from game.headless.cards.operations import Attack, CardOperation
NEOWS_FURY = CardDefinition("neows_fury", (
    CardSpec("Neow's Fury", 1, "attack", base_damage=10, exhausts=True),
    CardSpec("Neow's Fury+", 1, "attack", base_damage=14, exhausts=True),
), (Attack(), CardOperation("random_discard_to_hand", 2, 3)), rarity="ancient", pool="colorless", generate_in_combat=False)
from game.headless.cards.event_effects import ToricBlock
PECK = CardDefinition("peck", (
    CardSpec("Peck", 1, "attack", base_damage=2),
    CardSpec("Peck+", 1, "attack", base_damage=2),
), (Attack(hits=3, upgraded_hits=4),), rarity="event", pool="event", generate_in_combat=False)
TORIC_TOUGHNESS = CardDefinition("toric_toughness", (
    CardSpec("Toric Toughness", 2, "skill", block_gain=5, uses_target=False),
    CardSpec("Toric Toughness+", 2, "skill", block_gain=7, uses_target=False),
), (ToricBlock(),), rarity="event", pool="event", generate_in_combat=False)
SPOILS_MAP = CardDefinition("spoils_map", (CardSpec("Spoils Map", -1, "quest", uses_target=False),), (),
                            rarity="quest", pool="event", generate_in_combat=False)
DEFINITIONS = (BYRDONIS_EGG, BYRD_SWOOP, NEOWS_FURY, PECK, TORIC_TOUGHNESS, SPOILS_MAP)
