"""Implemented generated status cards."""

from game.headless.cards.base import Card, CardDefinition, CardSpec
from game.headless.cards.effects import DrawCards

SLIMED = CardDefinition("slimed", (
    CardSpec("Slimed", 1, "status", draw_count=1, exhausts=True, uses_target=False),
), (DrawCards(),), rarity="status", pool="status")
WOUND = CardDefinition("wound", (CardSpec("Wound", -1, "status", uses_target=False),), (), rarity="status", pool="status")
DAZED = CardDefinition("dazed", (CardSpec("Dazed", -1, "status", uses_target=False, ethereal=True),), (), rarity="status", pool="status")
INFECTION = CardDefinition("infection", (CardSpec("Infection", -1, "status", uses_target=False, end_turn_damage=3),), (), rarity="status", pool="status")
BECKON = CardDefinition("beckon", (CardSpec("Beckon", 1, "status", uses_target=False, end_turn_hp_loss=6),), (), rarity="status", pool="status")
BURN = CardDefinition("burn", (CardSpec("Burn", -1, "status", uses_target=False, end_turn_damage=2),), (), rarity="status", pool="status")
DEBRIS = CardDefinition("debris", (CardSpec("Debris", 1, "status", uses_target=False, exhausts=True),), (), rarity="status", pool="status")
WITHER = CardDefinition("wither", (CardSpec("Wither", -1, "status", uses_target=False, end_turn_damage=3),), (), rarity="status", pool="status")
TOXIC = CardDefinition("toxic", (CardSpec("Toxic", 1, "status", uses_target=False, exhausts=True, end_turn_damage=5),), (), rarity="status", pool="status")
VOID = CardDefinition("void", (CardSpec("Void", -1, "status", uses_target=False, ethereal=True),), (), rarity="status", pool="status")
GUILTY = CardDefinition("guilty", (CardSpec("Guilty", -1, "curse", uses_target=False),), (), combat_lifetime=5, rarity="curse", pool="curse")
CLUMSY = CardDefinition("clumsy", (CardSpec("Clumsy", -1, "curse", uses_target=False, ethereal=True),), (), rarity="curse", pool="curse")
INJURY = CardDefinition("injury", (CardSpec("Injury", -1, "curse", uses_target=False),), (), rarity="curse", pool="curse")
GREED = CardDefinition("greed", (CardSpec("Greed", -1, "curse", uses_target=False, eternal=True),), (), rarity="curse", pool="curse")
SPORE_MIND = CardDefinition("spore_mind", (CardSpec("Spore Mind", 1, "curse", uses_target=False, exhausts=True),), (), rarity="curse", pool="curse")
POOR_SLEEP = CardDefinition("poor_sleep", (CardSpec("Poor Sleep", -1, "curse", uses_target=False, retain=True),), (), rarity="curse", pool="curse")
DEFINITIONS = (SLIMED, WOUND, DAZED, INFECTION, GUILTY, CLUMSY, INJURY, GREED, SPORE_MIND, POOR_SLEEP,
               BECKON, BURN, DEBRIS, WITHER, TOXIC, VOID)


class SlimedCard(Card):
    def __init__(self) -> None:
        super().__init__(SLIMED)
