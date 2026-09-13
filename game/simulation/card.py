"""Legacy combat names and metadata; game rules live in game.headless.cards.

The eight-name research vocabulary is deliberately fixed. Adding game content
never requires extending this legacy representation.
"""

from game.headless.cards.base import Card, CardSpec
from game.headless.cards.ironclad import (
    StrikeCard, DefendCard, BashCard, PommelStrikeCard, ShrugItOffCard, IronWaveCard,
    BodySlamCard, create_starter_deck, create_ironclad_sequencing_deck,
    STRIKE, DEFEND, BASH, POMMEL_STRIKE, SHRUG_IT_OFF, IRON_WAVE, BODY_SLAM,
)
from game.headless.cards.status import SlimedCard, SLIMED

# Explicitly retain the old vocabulary even when the game catalog grows.
CARD_SPECS = {
    definition.levels[0].name: definition.levels[0]
    for definition in (STRIKE, DEFEND, BASH, POMMEL_STRIKE, SHRUG_IT_OFF, IRON_WAVE, BODY_SLAM, SLIMED)
}


def get_card_spec(card_name: str) -> CardSpec:
    try:
        return CARD_SPECS[card_name]
    except KeyError as exc:
        raise ValueError(f"Unknown card name for metadata lookup: {card_name!r}") from exc
