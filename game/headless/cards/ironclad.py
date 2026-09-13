"""Implemented Ironclad cards. Add each verified card family in this layer."""

from game.headless.cards.base import Card, CardDefinition, CardSpec
from game.headless.cards.effects import ApplyTargetStatus, DealDamage, DrawCards, GainBlock, SelectHandCard, ApplyDebuffs
from game.headless.powers.status import VULNERABLE, WEAK

STRIKE = CardDefinition("strike", (
    CardSpec("Strike", 1, "attack", base_damage=6),
    CardSpec("Strike+", 1, "attack", base_damage=9),
), (DealDamage(),))
DEFEND = CardDefinition("defend", (
    CardSpec("Defend", 1, "block", block_gain=5, uses_target=False),
    CardSpec("Defend+", 1, "block", block_gain=8, uses_target=False),
), (GainBlock(),))
BASH = CardDefinition("bash", (
    CardSpec("Bash", 2, "attack", base_damage=8,
             applies_status_name=VULNERABLE, applies_status_stacks=2),
    CardSpec("Bash+", 2, "attack", base_damage=10,
             applies_status_name=VULNERABLE, applies_status_stacks=3),
), (DealDamage(), ApplyTargetStatus()))
POMMEL_STRIKE = CardDefinition("pommel_strike", (
    CardSpec("Pommel Strike", 1, "attack", base_damage=9, draw_count=1),
    CardSpec("Pommel Strike+", 1, "attack", base_damage=10, draw_count=2),
), (DealDamage(), DrawCards()))
SHRUG_IT_OFF = CardDefinition("shrug_it_off", (
    CardSpec("Shrug It Off", 1, "block", block_gain=8, draw_count=1, uses_target=False),
    CardSpec("Shrug It Off+", 1, "block", block_gain=11, draw_count=1, uses_target=False),
), (GainBlock(), DrawCards()))
IRON_WAVE = CardDefinition("iron_wave", (
    CardSpec("Iron Wave", 1, "attack", base_damage=5, block_gain=5),
    CardSpec("Iron Wave+", 1, "attack", base_damage=7, block_gain=7),
), (GainBlock(), DealDamage()))
BODY_SLAM = CardDefinition("body_slam", (
    CardSpec("Body Slam", 1, "attack", damage_equals_player_block=True),
    CardSpec("Body Slam+", 0, "attack", damage_equals_player_block=True),
), (DealDamage(),))

ARMAMENTS = CardDefinition("armaments", (
    CardSpec("Armaments", 1, "skill", block_gain=5, uses_target=False),
    CardSpec("Armaments+", 1, "skill", block_gain=5, uses_target=False),
), (GainBlock(), SelectHandCard("upgrade", upgraded_mode="all")))
TRUE_GRIT = CardDefinition("true_grit", (
    CardSpec("True Grit", 1, "skill", block_gain=7, uses_target=False),
    CardSpec("True Grit+", 1, "skill", block_gain=9, uses_target=False),
), (GainBlock(), SelectHandCard("exhaust", mode="random")))

UPPERCUT = CardDefinition("uppercut", (
    CardSpec("Uppercut", 2, "attack", base_damage=13, applies_status_stacks=1),
    CardSpec("Uppercut+", 2, "attack", base_damage=13, applies_status_stacks=2),
), (DealDamage(), ApplyDebuffs((WEAK, VULNERABLE))))
SHOCKWAVE = CardDefinition("shockwave", (
    CardSpec("Shockwave", 2, "skill", applies_status_stacks=3, exhausts=True, uses_target=False),
    CardSpec("Shockwave+", 2, "skill", applies_status_stacks=5, exhausts=True, uses_target=False),
), (ApplyDebuffs((WEAK, VULNERABLE), all_enemies=True),))

DEFINITIONS = (STRIKE, DEFEND, BASH, POMMEL_STRIKE, SHRUG_IT_OFF, IRON_WAVE,
               BODY_SLAM, ARMAMENTS, TRUE_GRIT, UPPERCUT, SHOCKWAVE)

# Existing constructor names are retained for callers and old experiment configs.
class StrikeCard(Card):
    def __init__(self, *, upgraded: bool = False) -> None:
        if not isinstance(upgraded, bool):
            raise ValueError("upgraded must be a boolean.")
        super().__init__(STRIKE, upgrade_level=int(upgraded))


class DefendCard(Card):
    def __init__(self) -> None:
        super().__init__(DEFEND)


class BashCard(Card):
    def __init__(self) -> None:
        super().__init__(BASH)


class PommelStrikeCard(Card):
    def __init__(self) -> None:
        super().__init__(POMMEL_STRIKE)


class ShrugItOffCard(Card):
    def __init__(self) -> None:
        super().__init__(SHRUG_IT_OFF)


class IronWaveCard(Card):
    def __init__(self) -> None:
        super().__init__(IRON_WAVE)


class BodySlamCard(Card):
    def __init__(self) -> None:
        super().__init__(BODY_SLAM)


def create_starter_deck() -> list[Card]:
    return [StrikeCard() for _ in range(5)] + [DefendCard() for _ in range(4)] + [BashCard()]


def create_ironclad_sequencing_deck() -> list[Card]:
    return ([StrikeCard() for _ in range(2)] + [DefendCard() for _ in range(3)] +
            [BashCard(), PommelStrikeCard(), ShrugItOffCard(), IronWaveCard(), BodySlamCard()])
