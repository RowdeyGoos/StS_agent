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
    small_types = [LeafSlimeSmall, TwigSlimeSmall]
    first_small = rng.choice(small_types)
    small_types.remove(first_small)
    last_small = rng.choice(small_types)
    medium_type = rng.choice((LeafSlimeMedium, TwigSlimeMedium))
    return [first_small(rng), medium_type(rng), last_small(rng)]


def build_overgrowth_fuzzy_encounter(rng: Random) -> list[Enemy]:
    """Native FuzzyWurmCrawlerWeak composition."""
    return [FuzzyWurmCrawler(rng)]


def build_overgrowth_mawler_encounter(rng: Random) -> list[Enemy]:
    """Build the fixed solo Mawler encounter."""
    return [Mawler(rng)]


def build_overgrowth_nibbits_encounter(rng: Random) -> list[Enemy]:
    """Build the fixed two-Nibbit encounter."""
    return [Nibbit(rng, role="front"), Nibbit(rng, role="back")]


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


def build_overgrowth_normal_slimes(rng):
    small = (LeafSlimeSmall, TwigSlimeSmall) if rng.choice((False, True)) else (TwigSlimeSmall, LeafSlimeSmall)
    return [TwigSlimeMedium(rng), LeafSlimeMedium(rng), *(kind(rng) for kind in small)]


def build_overgrowth_flyconid(rng):
    from game.headless.monsters.overgrowth_normal import Flyconid
    medium = rng.choice((LeafSlimeMedium, TwigSlimeMedium))
    return [medium(rng), Flyconid(rng)]


def build_overgrowth_inklets(rng):
    from game.headless.monsters.overgrowth_normal import Inklet
    return [Inklet(rng), Inklet(rng, middle=True), Inklet(rng)]


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
    return [kind(rng) for kind in selected]


def build_overgrowth_strangler(rng):
    from game.headless.monsters.overgrowth_normal import SlitheringStrangler, SnappingJaxfruit
    variant = rng.randrange(3)
    if variant == 0:
        kinds = [SnappingJaxfruit]
    elif variant == 1:
        kinds = [rng.choice((LeafSlimeMedium, TwigSlimeMedium))]
    else:
        kinds = [rng.choice((LeafSlimeSmall, TwigSlimeSmall)) for _ in range(2)]
    return [*(kind(rng) for kind in kinds), SlitheringStrangler(rng)]


def build_overgrowth_jaxfruit(rng):
    from game.headless.monsters.overgrowth_normal import SnappingJaxfruit, Flyconid
    return [SnappingJaxfruit(rng), Flyconid(rng)]


def build_overgrowth_kin(rng):
    from game.headless.monsters.kin import KinFollower, KinPriest
    return [KinFollower(rng, starts_with_dance=True), KinFollower(rng), KinPriest(rng)]
