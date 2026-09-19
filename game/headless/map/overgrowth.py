"""Overgrowth entry point; Act 1 topology is shared in :mod:`map.act1`."""
from game.headless.map.act1 import BASE_PROFILE, PROFILE, generate_act1_map, validate_generated_map


def generate_overgrowth_map(rng, *, event_pool, profile=PROFILE):
    return generate_act1_map(rng, event_pool=event_pool, act='overgrowth', profile=profile)
