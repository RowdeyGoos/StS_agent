"""Shared restricted Ironclad transformation pool and source validation."""

TRANSFORM_POOL = (
    "pommel_strike", "shrug_it_off", "iron_wave", "body_slam", "armaments", "true_grit",
    "uppercut", "shockwave", "sword_boomerang", "impervious", "offering", "fiend_fire",
)


def check_content(state, cards, pool):
    sources = (*pool, "strike", "defend", "bash")
    if any(c.definition.definition_id not in sources for c in state.deck):
        raise ValueError("Transformation currently supports only the implemented Ironclad deck cards.")
    for name in pool:
        cards.definition(name)
