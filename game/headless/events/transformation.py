"""Explicit restricted transformation pools and source validation."""

from game.headless.cards.pools import REWARD_CARDS, ANCIENT_CARDS, COLORLESS_CARDS

TRANSFORM_POOL = REWARD_CARDS

CURSE_POOL = ("guilty", "clumsy")
COLORLESS_POOL = COLORLESS_CARDS
COLORLESS_SOURCES = (*COLORLESS_POOL, "byrdonis_egg", "byrd_swoop", "giant_rock")


def replacement_pool(source, pool):
    return CURSE_POOL if source in CURSE_POOL else COLORLESS_POOL if source in COLORLESS_SOURCES else pool


def transform(state, cards, identity, pool, *, stream):
    from game.headless.run.deck import find_card, transform_card
    source = find_card(state, identity).definition.definition_id
    return transform_card(state, cards, identity, replacement_pool(source, pool), stream=stream)


def check_content(state, cards, pool):
    sources = (*pool, *ANCIENT_CARDS, "strike", "defend", "bash", *CURSE_POOL, *COLORLESS_SOURCES)
    if any(c.definition.definition_id not in sources for c in state.deck):
        raise ValueError("Transformation requires a supported source card and replacement pool.")
    for name in pool:
        cards.definition(name)
    if any(c.definition.definition_id in COLORLESS_SOURCES for c in state.deck):
        for name in COLORLESS_POOL:
            cards.definition(name)
    if any(c.definition.definition_id in CURSE_POOL for c in state.deck):
        for name in CURSE_POOL:
            cards.definition(name)
