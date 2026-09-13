"""Seeded encounter construction, separate from monster behavior."""

from random import Random
from typing import Callable
from game.headless.monsters.base import Enemy, EncounterFactory
from game.headless.monsters.overgrowth import (SimpleEnemy, Nibbit, ShrinkerBeetle, FuzzyWurmCrawler, Mawler, LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium)


def build_overgrowth_easy_encounter(rng: Random) -> list[Enemy]:
    """Sample one encounter uniformly from the Overgrowth first-three-fight pool."""
    encounter_builders: tuple[EncounterFactory, ...] = (
        lambda inner_rng: [Nibbit(inner_rng)],
        build_overgrowth_slimes_encounter,
        lambda inner_rng: [ShrinkerBeetle(inner_rng)],
        lambda inner_rng: [FuzzyWurmCrawler(inner_rng)],
    )
    encounter_builder = rng.choice(encounter_builders)
    return list(encounter_builder(rng))


def sample_overgrowth_first_three_encounter_builders(
    rng: Random,
) -> tuple[EncounterFactory, ...]:
    """Sample three unique encounter builders from the Overgrowth easy pool."""
    encounter_builders: list[EncounterFactory] = [
        lambda inner_rng: [Nibbit(inner_rng)],
        build_overgrowth_slimes_encounter,
        lambda inner_rng: [ShrinkerBeetle(inner_rng)],
        lambda inner_rng: [FuzzyWurmCrawler(inner_rng)],
    ]
    rng.shuffle(encounter_builders)
    return tuple(encounter_builders[:3])


def build_overgrowth_slimes_encounter(rng: Random) -> list[Enemy]:
    """Build the Overgrowth easy Slimes encounter."""
    medium_enemy = rng.choice((LeafSlimeMedium, TwigSlimeMedium))(rng)
    small_enemies: list[Enemy] = [LeafSlimeSmall(rng), TwigSlimeSmall(rng)]
    rng.shuffle(small_enemies)
    return [medium_enemy, *small_enemies]


def build_overgrowth_mawler_encounter(rng: Random) -> list[Enemy]:
    """Build the fixed solo Mawler encounter."""
    return [Mawler(rng)]


def build_overgrowth_nibbits_encounter(rng: Random) -> list[Enemy]:
    """Build the fixed two-Nibbit encounter."""
    return [Nibbit(rng), Nibbit(rng)]


def build_overgrowth_shrinker_fuzzy_encounter(rng: Random) -> list[Enemy]:
    """Build the fixed Shrinker Beetle plus Fuzzy Wurm Crawler encounter."""
    return [ShrinkerBeetle(rng), FuzzyWurmCrawler(rng)]


def build_overgrowth_hard_v1_encounter(rng: Random) -> list[Enemy]:
    """Sample one encounter from the deliberately partial hard-v1 pool."""
    encounter_builder = rng.choice(
        (
            build_overgrowth_mawler_encounter,
            build_overgrowth_nibbits_encounter,
            build_overgrowth_shrinker_fuzzy_encounter,
        )
    )
    return list(encounter_builder(rng))
