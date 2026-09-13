"""Implemented generated status cards."""

from game.headless.cards.base import Card, CardDefinition, CardSpec
from game.headless.cards.effects import DrawCards

SLIMED = CardDefinition("slimed", (
    CardSpec("Slimed", 1, "status", draw_count=1, exhausts=True, uses_target=False),
), (DrawCards(),))
WOUND = CardDefinition("wound", (CardSpec("Wound", -1, "status", uses_target=False),), ())
DEFINITIONS = (SLIMED, WOUND)


class SlimedCard(Card):
    def __init__(self) -> None:
        super().__init__(SLIMED)
