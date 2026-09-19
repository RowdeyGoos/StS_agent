"""All twenty native Hive encounters; generated Act 2 travel is separate."""
from functools import partial
from types import MappingProxyType
from game.headless.encounters.base import EncounterDefinition
from game.headless.encounters.randomness import create
from game.headless.monsters.hive_normal import (
    BowlbugEgg, BowlbugNectar, BowlbugRock, BowlbugSilk, Chomper, Exoskeleton,
    HunterKiller, LouseProgenitor, Myte, SlumberingBeetle, SpinyToad, Tunneler,
)
from game.headless.monsters.hive_summons import Ovicopter, TheObscura
from game.headless.monsters.hive_elites import (
    DecimillipedeSegmentFront, DecimillipedeSegmentMiddle, DecimillipedeSegmentBack,
    Entomancer, InfestedPrism,
)
from game.headless.monsters.hive_bosses import Crusher, Rocket, KnowledgeDemon, TheInsatiable
from game.headless.monsters.hive_hopper import ThievingHopper


def group(kinds, rng):
    return [create(kind, rng) for kind in kinds]


def bowlbugs(rng, *, weak=False):
    workers = [BowlbugEgg, BowlbugNectar] if weak else [BowlbugEgg, BowlbugSilk, BowlbugNectar]
    kinds = [BowlbugRock]
    for _ in range(1 if weak else 2):
        kind = rng.choice(workers)
        workers.remove(kind)
        kinds.append(kind)
    return group(kinds, rng)


def chompers(rng):
    return [create(Chomper, rng), create(Chomper, rng, scream_first=True)]


def exoskeletons(count, rng):
    return [create(Exoskeleton, rng, opening=i) for i in range(count)]


def segments(rng):
    opening = rng.randrange(3)
    return [create(kind, rng, opening=(opening + i) % 3) for i, kind in enumerate(
        (DecimillipedeSegmentFront, DecimillipedeSegmentMiddle, DecimillipedeSegmentBack))]


def mytes(rng):
    return [create(Myte, rng, opening=i) for i in (0, 2)]


def encounter(factory, room='combat'):
    return EncounterDefinition(factory, room, (35, 45) if room == 'elite' else (100, 100) if room == 'boss' else (10, 20), room == 'elite', act=2)


def members(*kinds, room='combat'):
    return encounter(partial(group, kinds), room)


ENCOUNTERS = MappingProxyType({
    'hive_bowlbugs': encounter(bowlbugs),
    'hive_bowlbugs_weak': encounter(partial(bowlbugs, weak=True)),
    'hive_chompers': encounter(chompers),
    'hive_decimillipede': encounter(segments, 'elite'),
    'hive_entomancer': members(Entomancer, room='elite'),
    'hive_exoskeletons': encounter(partial(exoskeletons, 4)),
    'hive_exoskeletons_weak': encounter(partial(exoskeletons, 3)),
    'hive_hunter_killer': members(HunterKiller),
    'hive_kaiser_crab': members(Crusher, Rocket, room='boss'),
    'hive_infested_prism': members(InfestedPrism, room='elite'),
    'hive_knowledge_demon': members(KnowledgeDemon, room='boss'),
    'hive_louse_progenitor': members(LouseProgenitor),
    'hive_mytes': encounter(mytes),
    'hive_ovicopter': members(Ovicopter),
    'hive_slumbering_beetle': members(BowlbugRock, BowlbugSilk, SlumberingBeetle),
    'hive_spiny_toad': members(SpinyToad),
    'hive_the_insatiable': members(TheInsatiable, room='boss'),
    'hive_the_obscura': members(TheObscura),
    'hive_thieving_hopper': members(ThievingHopper),
    'hive_tunneler': members(Tunneler),
})
NATIVE_HIVE_ENCOUNTERS = MappingProxyType(dict(zip((
    'BowlbugsNormal', 'BowlbugsWeak', 'ChompersNormal', 'DecimillipedeElite', 'EntomancerElite',
    'ExoskeletonsNormal', 'ExoskeletonsWeak', 'HunterKillerNormal', 'KaiserCrabBoss',
    'InfestedPrismsElite', 'KnowledgeDemonBoss', 'LouseProgenitorNormal', 'MytesNormal',
    'OvicopterNormal', 'SlumberingBeetleNormal', 'SpinyToadNormal', 'TheInsatiableBoss',
    'TheObscuraNormal', 'ThievingHopperWeak', 'TunnelerWeak',
), ENCOUNTERS)))
