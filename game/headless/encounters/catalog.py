"""Explicit encounter definitions used by authored run routes."""

from game.headless.encounters.randomness import create

from types import MappingProxyType
from functools import partial
from game.headless.encounters.events import dense_vegetation
from game.headless.encounters.base import EncounterDefinition
from game.headless.monsters.byrdonis import Byrdonis
from game.headless.monsters.vantom import Vantom
from game.headless.encounters.overgrowth import (
    build_overgrowth_slimes_encounter, build_overgrowth_fuzzy_encounter,
    build_overgrowth_mawler_encounter, build_overgrowth_nibbits_encounter,
)
from game.headless.monsters.overgrowth import Nibbit, ShrinkerBeetle
from game.headless.monsters.bygone_effigy import BygoneEffigy
from game.headless.monsters.ceremonial_beast import CeremonialBeast
from game.headless.monsters.phrog_parasite import PhrogParasite
from game.headless.monsters.fogmog import Fogmog
from game.headless.monsters.overgrowth_normal import CubexConstruct, VineShambler
from game.headless.encounters.overgrowth import (
    build_overgrowth_normal_slimes, build_overgrowth_flyconid, build_overgrowth_inklets,
    build_overgrowth_ruby_raiders, build_overgrowth_strangler, build_overgrowth_jaxfruit,
    build_overgrowth_kin, build_overgrowth_shrinker_fuzzy_encounter,
)


def solo(kind, rng):
    return [create(kind, rng)]


def nibbit_encounter(rng):
    return [create(Nibbit, rng)]


def byrdonis_encounter(rng):
    return [create(Byrdonis, rng)]


def vantom_encounter(rng):
    return [create(Vantom, rng)]


from game.headless.encounters.extended_events import ENCOUNTERS as EXTENDED_EVENTS

from game.headless.encounters.underdocks import ENCOUNTERS as UNDERDOCKS, NATIVE_UNDERDOCKS_ENCOUNTERS

ENCOUNTERS = MappingProxyType({
    **UNDERDOCKS,
    **EXTENDED_EVENTS,
    "dense_vegetation_event": EncounterDefinition(dense_vegetation, event_id="dense_vegetation"),
    "overgrowth_shrinker": EncounterDefinition(partial(solo, ShrinkerBeetle)),
    "overgrowth_crawlers": EncounterDefinition(build_overgrowth_shrinker_fuzzy_encounter),
    "overgrowth_cubex": EncounterDefinition(partial(solo, CubexConstruct)),
    "overgrowth_flyconid": EncounterDefinition(build_overgrowth_flyconid),
    "overgrowth_fogmog": EncounterDefinition(partial(solo, Fogmog)),
    "overgrowth_inklets": EncounterDefinition(build_overgrowth_inklets),
    "overgrowth_ruby_raiders": EncounterDefinition(build_overgrowth_ruby_raiders),
    "overgrowth_slimes_normal": EncounterDefinition(build_overgrowth_normal_slimes),
    "overgrowth_strangler": EncounterDefinition(build_overgrowth_strangler),
    "overgrowth_jaxfruit": EncounterDefinition(build_overgrowth_jaxfruit),
    "overgrowth_vine_shambler": EncounterDefinition(partial(solo, VineShambler)),
    "overgrowth_bygone_effigy": EncounterDefinition(partial(solo, BygoneEffigy), "elite", (35, 45), True),
    "overgrowth_phrog_parasite": EncounterDefinition(partial(solo, PhrogParasite), "elite", (35, 45), True),
    "overgrowth_ceremonial_beast": EncounterDefinition(partial(solo, CeremonialBeast), "boss", (100, 100)),
    "overgrowth_the_kin": EncounterDefinition(build_overgrowth_kin, "boss", (100, 100)),
    "overgrowth_vantom": EncounterDefinition(vantom_encounter, "boss", (100, 100)),
    "overgrowth_nibbit": EncounterDefinition(nibbit_encounter),
    "overgrowth_slimes": EncounterDefinition(build_overgrowth_slimes_encounter),
    "overgrowth_fuzzy": EncounterDefinition(build_overgrowth_fuzzy_encounter),
    "overgrowth_mawler": EncounterDefinition(build_overgrowth_mawler_encounter),
    "overgrowth_nibbits": EncounterDefinition(build_overgrowth_nibbits_encounter),
    "overgrowth_byrdonis": EncounterDefinition(byrdonis_encounter, "elite", (35, 45), True),
})


# Native Overgrowth.GenerateAllEncounters (100694198); no inferred spawn weights.
NATIVE_OVERGROWTH_ENCOUNTERS = MappingProxyType({
    "BygoneEffigyElite": "overgrowth_bygone_effigy", "ByrdonisElite": "overgrowth_byrdonis",
    "CeremonialBeastBoss": "overgrowth_ceremonial_beast", "CubexConstructNormal": "overgrowth_cubex",
    "FlyconidNormal": "overgrowth_flyconid", "FogmogNormal": "overgrowth_fogmog",
    "FuzzyWurmCrawlerWeak": "overgrowth_fuzzy", "InkletsNormal": "overgrowth_inklets",
    "MawlerNormal": "overgrowth_mawler", "NibbitsNormal": "overgrowth_nibbits",
    "NibbitsWeak": "overgrowth_nibbit", "OvergrowthCrawlers": "overgrowth_crawlers",
    "PhrogParasiteElite": "overgrowth_phrog_parasite", "RubyRaidersNormal": "overgrowth_ruby_raiders",
    "ShrinkerBeetleWeak": "overgrowth_shrinker", "SlimesNormal": "overgrowth_slimes_normal",
    "SlimesWeak": "overgrowth_slimes", "SlitheringStranglerNormal": "overgrowth_strangler",
    "SnappingJaxfruitNormal": "overgrowth_jaxfruit", "TheKinBoss": "overgrowth_the_kin",
    "VantomBoss": "overgrowth_vantom", "VineShamblerNormal": "overgrowth_vine_shambler",
})
