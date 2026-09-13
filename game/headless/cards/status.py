"""Implemented generated status cards."""

from game.headless.cards.base import Card, CardDefinition, CardSpec

SLIMED = CardDefinition("slimed", (
    CardSpec("Slimed", 1, "status", exhausts=True, uses_target=False),
), ())
DEFINITIONS = (SLIMED,)


class SlimedCard(Card):
    def __init__(self) -> None:
        super().__init__(SLIMED)
