"""Compatibility entry point for the established Act 1 map API."""
from game.headless.map.standard import (
    BASE_PROFILE, PROFILE, UNDERDOCKS_BASE_PROFILE, UNDERDOCKS_PROFILE,
    BASE_PROFILES, PRUNED_PROFILES, ROWS, WIDTH, profile_for, validate_generated_map,
    generate_map,
)


def generate_act1_map(rng, *, event_pool, act="overgrowth", profile=None, ascension=0):
    if act not in ('overgrowth', 'underdocks'):
        raise ValueError('Unsupported Act 1 location.')
    return generate_map(rng, event_pool=event_pool, act=act, profile=profile, ascension=ascension)
