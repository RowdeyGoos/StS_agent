"""Seeded encounter construction, separate from monster behavior."""

from game.headless.encounters.randomness import create

from random import Random
from typing import Callable
from game.headless.monsters.base import Enemy, EncounterFactory
from game.headless.monsters.overgrowth import (SimpleEnemy, Nibbit, ShrinkerBeetle, FuzzyWurmCrawler, Mawler, LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium)


def build_overgrowth_easy_encounter(rng: Random) -> list[Enemy]:
    """Sample one encounter uniformly from the Overgrowth first-three-fight pool."""
    encounter_builders: tuple[EncounterFactory, ...] = (
        lambda inner_rng: [create(Nibbit, inner_rng)],
        build_overgrowth_slimes_encounter,
        lambda inner_rng: [create(ShrinkerBeetle, inner_rng)],
        lambda inner_rng: [create(FuzzyWurmCrawler, inner_rng)],
    )
    encounter_builder = rng.choice(encounter_builders)
    return list(encounter_builder(rng))


def sample_overgrowth_first_three_encounter_builders(
    rng: Random,
) -> tuple[EncounterFactory, ...]:
    """Sample three unique encounter builders from the Overgrowth easy pool."""
    encounter_builders: list[EncounterFactory] = [
        lambda inner_rng: [create(Nibbit, inner_rng)],
        build_overgrowth_slimes_encounter,
        lambda inner_rng: [create(ShrinkerBeetle, inner_rng)],
        lambda inner_rng: [create(FuzzyWurmCrawler, inner_rng)],
    ]
    rng.shuffle(encounter_builders)
    return tuple(encounter_builders[:3])


def build_overgrowth_slimes_encounter(rng: Random) -> list[Enemy]:
    """Build the Overgrowth easy Slimes encounter."""
    small_types = [LeafSlimeSmall, TwigSlimeSmall]
    first_small = rng.choice(small_types)
    small_types.remove(first_small)
    last_small = rng.choice(small_types)
    medium_type = rng.choice((LeafSlimeMedium, TwigSlimeMedium))
    return [create(first_small, rng), create(medium_type, rng), create(last_small, rng)]


def build_overgrowth_fuzzy_encounter(rng: Random) -> list[Enemy]:
    """Native FuzzyWurmCrawlerWeak composition."""
    return [create(FuzzyWurmCrawler, rng)]


def build_overgrowth_mawler_encounter(rng: Random) -> list[Enemy]:
    """Build the fixed solo Mawler encounter."""
    return [create(Mawler, rng)]


def build_overgrowth_nibbits_encounter(rng: Random) -> list[Enemy]:
    """Build the fixed two-Nibbit encounter."""
    return [create(Nibbit, rng, role="front"), create(Nibbit, rng, role="back")]


def build_overgrowth_shrinker_fuzzy_encounter(rng: Random) -> list[Enemy]:
    """Build the fixed Shrinker Beetle plus Fuzzy Wurm Crawler encounter."""
    return [create(ShrinkerBeetle, rng), create(FuzzyWurmCrawler, rng)]


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


def build_overgrowth_normal_slimes(rng):
    leaf_first = rng.choice((False, True))
    from game.headless.encounters.randomness import EncounterRandom
    if isinstance(rng, EncounterRandom):
        leaf_first = not leaf_first
    small = (LeafSlimeSmall, TwigSlimeSmall) if leaf_first else (TwigSlimeSmall, LeafSlimeSmall)
    return [create(TwigSlimeMedium, rng), create(LeafSlimeMedium, rng), *(create(kind, rng) for kind in small)]


def build_overgrowth_flyconid(rng):
    from game.headless.monsters.overgrowth_normal import Flyconid
    medium = rng.choice((LeafSlimeMedium, TwigSlimeMedium))
    return [create(medium, rng), create(Flyconid, rng)]


def build_overgrowth_inklets(rng):
    from game.headless.monsters.overgrowth_normal import Inklet
    return [create(Inklet, rng), create(Inklet, rng, middle=True), create(Inklet, rng)]


def build_overgrowth_ruby_raiders(rng):
    from game.headless.monsters.ruby_raiders import (
        AxeRubyRaider, AssassinRubyRaider, BruteRubyRaider, CrossbowRubyRaider, TrackerRubyRaider,
    )
    candidates = [AxeRubyRaider, AssassinRubyRaider, BruteRubyRaider, CrossbowRubyRaider, TrackerRubyRaider]
    selected = []
    for _ in range(3):
        kind = rng.choice(candidates)
        candidates.remove(kind)
        selected.append(kind)
    return [create(kind, rng) for kind in selected]


def build_overgrowth_strangler(rng):
    from game.headless.monsters.overgrowth_normal import SlitheringStrangler, SnappingJaxfruit
    variant = rng.randrange(3)
    if variant == 0:
        kinds = [SnappingJaxfruit]
    elif variant == 1:
        kinds = [rng.choice((LeafSlimeMedium, TwigSlimeMedium))]
    else:
        kinds = [rng.choice((LeafSlimeSmall, TwigSlimeSmall)) for _ in range(2)]
    return [*(create(kind, rng) for kind in kinds), create(SlitheringStrangler, rng)]


def build_overgrowth_jaxfruit(rng):
    from game.headless.monsters.overgrowth_normal import SnappingJaxfruit, Flyconid
    return [create(SnappingJaxfruit, rng), create(Flyconid, rng)]


def build_overgrowth_kin(rng):
    from game.headless.monsters.kin import KinFollower, KinPriest
    return [create(KinFollower, rng, starts_with_dance=True), create(KinFollower, rng), create(KinPriest, rng)]
