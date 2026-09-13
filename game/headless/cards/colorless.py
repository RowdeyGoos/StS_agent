"""Implemented colorless cards, separate from character reward pools."""

from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.effects import ApplyDebuffs, DealDamage, GainBlock, DrawCards
from game.headless.powers.status import WEAK, VULNERABLE

SHOCKWAVE = CardDefinition("shockwave", (
    CardSpec("Shockwave", 2, "skill", applies_status_stacks=3, exhausts=True, uses_target=False),
    CardSpec("Shockwave+", 2, "skill", applies_status_stacks=5, exhausts=True, uses_target=False),
), (ApplyDebuffs((WEAK, VULNERABLE), all_enemies=True),))

FINESSE = CardDefinition("finesse", (
    CardSpec("Finesse", 0, "skill", block_gain=4, draw_count=1, uses_target=False),
    CardSpec("Finesse+", 0, "skill", block_gain=7, draw_count=1, uses_target=False),
), (GainBlock(), DrawCards()))
FLASH_OF_STEEL = CardDefinition("flash_of_steel", (
    CardSpec("Flash of Steel", 0, "attack", base_damage=5, draw_count=1),
    CardSpec("Flash of Steel+", 0, "attack", base_damage=8, draw_count=1),
), (DealDamage(), DrawCards()))
DEFINITIONS = (SHOCKWAVE, FINESSE, FLASH_OF_STEEL)
