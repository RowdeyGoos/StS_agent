"""Implemented generated status cards."""

from game.headless.cards.base import Card, CardDefinition, CardSpec
from game.headless.cards.effects import DrawCards

SLIMED = CardDefinition("slimed", (
    CardSpec("Slimed", 1, "status", draw_count=1, exhausts=True, uses_target=False),
), (DrawCards(),))
WOUND = CardDefinition("wound", (CardSpec("Wound", -1, "status", uses_target=False),), ())
DAZED = CardDefinition("dazed", (CardSpec("Dazed", -1, "status", uses_target=False, ethereal=True),), ())
INFECTION = CardDefinition("infection", (CardSpec("Infection", -1, "status", uses_target=False, end_turn_damage=3),), ())
GUILTY = CardDefinition("guilty", (CardSpec("Guilty", -1, "curse", uses_target=False),), (), combat_lifetime=5)
CLUMSY = CardDefinition("clumsy", (CardSpec("Clumsy", -1, "curse", uses_target=False, ethereal=True),), ())
INJURY = CardDefinition("injury", (CardSpec("Injury", -1, "curse", uses_target=False),), (), rarity="curse", pool="curse")
GREED = CardDefinition("greed", (CardSpec("Greed", -1, "curse", uses_target=False, eternal=True),), (), rarity="curse", pool="curse", generate_in_combat=False)
DEFINITIONS = (SLIMED, WOUND, DAZED, INFECTION, GUILTY, CLUMSY, INJURY, GREED)


class SlimedCard(Card):
    def __init__(self) -> None:
        super().__init__(SLIMED)
