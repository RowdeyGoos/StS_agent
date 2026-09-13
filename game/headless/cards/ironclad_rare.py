"""The restricted first boss reward pool, including each native upgrade."""

from dataclasses import replace
from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.effects import GainBlock, LoseHp, GainEnergy, DrawCards, ExhaustHandAttack

IMPERVIOUS = CardDefinition("impervious", (
    CardSpec("Impervious", 2, "skill", block_gain=30, exhausts=True, uses_target=False),
    CardSpec("Impervious+", 2, "skill", block_gain=40, exhausts=True, uses_target=False),
), (GainBlock(),))
OFFERING = CardDefinition("offering", (
    CardSpec("Offering", 0, "skill", draw_count=3, exhausts=True, uses_target=False),
    CardSpec("Offering+", 0, "skill", draw_count=5, exhausts=True, uses_target=False),
), (LoseHp(6), GainEnergy(2), DrawCards()))
FIEND_FIRE = CardDefinition("fiend_fire", (
    CardSpec("Fiend Fire", 2, "attack", base_damage=7, exhausts=True),
    CardSpec("Fiend Fire+", 2, "attack", base_damage=10, exhausts=True),
), (ExhaustHandAttack(),))
IMPERVIOUS = replace(IMPERVIOUS, pool="ironclad", rarity="rare", strike=False)
OFFERING = replace(OFFERING, pool="ironclad", rarity="rare", strike=False)
FIEND_FIRE = replace(FIEND_FIRE, pool="ironclad", rarity="rare", strike=False)

DEFINITIONS = (IMPERVIOUS, OFFERING, FIEND_FIRE)

