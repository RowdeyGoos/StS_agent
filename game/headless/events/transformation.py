"""Owned source-family transformation pools and content validation."""

from game.headless.cards.pools import REWARD_CARDS, ANCIENT_CARDS, COLORLESS_CARDS

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.generation.foreign import ORDINARY

FOREIGN_SOURCES = tuple(d.definition_id for d in DEFAULT_CARDS.definitions
                        if d.pool in ORDINARY and d.rarity in ('basic', 'common', 'uncommon', 'rare'))
TRANSFORM_POOL = REWARD_CARDS

from game.headless.cards.curses import ALL_CURSES, SPECIAL_CURSES
CURSE_POOL = ALL_CURSES
CURSE_SOURCES = CURSE_POOL
ETERNAL_SOURCES = ("greed", *SPECIAL_CURSES)
COLORLESS_POOL = COLORLESS_CARDS
COLORLESS_SOURCES = (*COLORLESS_POOL, "byrdonis_egg", "byrd_swoop", "giant_rock", "neows_fury", "peck", "toric_toughness", "spoils_map", *(d.definition_id for d in DEFAULT_CARDS.definitions if d.pool == "event"))


def replacement_pool(source, pool):
    if source in FOREIGN_SOURCES:
        return ORDINARY[DEFAULT_CARDS.definition(source).pool]
    return CURSE_POOL if source in CURSE_SOURCES else COLORLESS_POOL if source in COLORLESS_SOURCES else pool


def transform(state, cards, identity, pool, *, stream):
    from game.headless.run.deck import find_card, transform_card
    source = find_card(state, identity).definition.definition_id
    return transform_card(state, cards, identity, replacement_pool(source, pool), stream=stream)


def check_content(state, cards, pool):
    sources = (*pool, *ANCIENT_CARDS, "strike", "defend", "bash", *CURSE_SOURCES, *ETERNAL_SOURCES, *COLORLESS_SOURCES, *FOREIGN_SOURCES)
    if any(c.definition.definition_id not in sources for c in state.deck):
        raise ValueError("Transformation requires a supported source card and replacement pool.")
    for name in pool:
        cards.definition(name)
    if any(c.definition.definition_id in COLORLESS_SOURCES for c in state.deck):
        for name in COLORLESS_POOL:
            cards.definition(name)
    if any(c.definition.definition_id in CURSE_SOURCES for c in state.deck):
        for name in CURSE_POOL:
            cards.definition(name)
    for family in {c.definition.pool for c in state.deck if c.definition.definition_id in FOREIGN_SOURCES}:
        for name in ORDINARY[family]:
            cards.definition(name)
