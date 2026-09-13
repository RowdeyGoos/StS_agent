"""Shared restricted Ironclad transformation pool and source validation."""

TRANSFORM_POOL = (
    "pommel_strike", "shrug_it_off", "iron_wave", "body_slam", "armaments", "true_grit",
    "uppercut", "shockwave", "sword_boomerang", "impervious", "offering", "fiend_fire",
)


CURSE_POOL = ("guilty", "clumsy")


def replacement_pool(source, pool):
    return CURSE_POOL if source in CURSE_POOL else pool


def transform(state, cards, identity, pool, *, stream):
    from game.headless.run.deck import find_card, transform_card
    source = find_card(state, identity).definition.definition_id
    return transform_card(state, cards, identity, replacement_pool(source, pool), stream=stream)


def check_content(state, cards, pool):
    sources = (*pool, "strike", "defend", "bash", *CURSE_POOL)
    if any(c.definition.definition_id not in sources for c in state.deck):
        raise ValueError("Transformation currently supports only the implemented Ironclad deck cards.")
    for name in pool:
        cards.definition(name)
    if any(c.definition.definition_id in CURSE_POOL for c in state.deck):
        for name in CURSE_POOL:
            cards.definition(name)
