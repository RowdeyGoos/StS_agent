"""All eighteen pinned Glory encounters, with Act 3 reward context."""
from functools import partial
from types import MappingProxyType
from game.headless.encounters.base import EncounterDefinition
from game.headless.encounters.randomness import create
from game.headless.monsters.event_monsters import PunchConstruct
from game.headless.monsters.overgrowth_normal import CubexConstruct
from game.headless.monsters.glory_normal import (DevotedSculptor, FrogKnight, GlobeHead, OwlMagistrate,
    ScrollOfBiting, SlimedBerserker, TheLost, TheForgotten, LivingShield, TurretOperator)
from game.headless.monsters.glory_summons import Axebot, Fabricator
from game.headless.monsters.glory_elites import FlailKnight, SpectralKnight, MagiKnight, MechaKnight, SoulNexus
from game.headless.monsters.glory_bosses import Aeonglass, Queen, TorchHeadAmalgam, TestSubject


def group(kinds, rng): return [create(kind, rng) for kind in kinds]


def scrolls(rng, *, weak=False):
    opening = rng.randrange(3)
    indices = [(opening + i) % 3 for i in range(3)] + ([] if weak else [2])
    return [create(ScrollOfBiting, rng, opening=i) for i in indices]


def encounter(factory, room='combat'):
    return EncounterDefinition(factory, room, (35, 45) if room == 'elite' else (100, 100) if room == 'boss' else (10, 20), room == 'elite', act=3)


def members(*kinds, room='combat'): return encounter(partial(group, kinds), room)


ENCOUNTERS = MappingProxyType({
    'glory_axebots': members(Axebot),
    'glory_construct_menagerie': members(PunchConstruct, CubexConstruct, CubexConstruct),
    'glory_devoted_sculptor': members(DevotedSculptor),
    'glory_aeonglass': members(Aeonglass, room='boss'),
    'glory_fabricator': members(Fabricator),
    'glory_frog_knight': members(FrogKnight),
    'glory_globe_head': members(GlobeHead),
    'glory_knights': members(FlailKnight, SpectralKnight, MagiKnight, room='elite'),
    'glory_mecha_knight': members(MechaKnight, room='elite'),
    'glory_owl_magistrate': members(OwlMagistrate),
    'glory_queen': members(TorchHeadAmalgam, Queen, room='boss'),
    'glory_scrolls_of_biting': encounter(scrolls),
    'glory_scrolls_of_biting_weak': encounter(partial(scrolls, weak=True)),
    'glory_slimed_berserker': members(SlimedBerserker),
    'glory_soul_nexus': members(SoulNexus, room='elite'),
    'glory_test_subject': members(TestSubject, room='boss'),
    'glory_the_lost_and_forgotten': members(TheLost, TheForgotten),
    'glory_turret_operator': members(LivingShield, TurretOperator),
})
NATIVE_GLORY_ENCOUNTERS = MappingProxyType(dict(zip((
    'AxebotsNormal', 'ConstructMenagerieNormal', 'DevotedSculptorWeak', 'AeonglassBoss', 'FabricatorNormal',
    'FrogKnightNormal', 'GlobeHeadNormal', 'KnightsElite', 'MechaKnightElite', 'OwlMagistrateNormal', 'QueenBoss',
    'ScrollsOfBitingNormal', 'ScrollsOfBitingWeak', 'SlimedBerserkerNormal', 'SoulNexusElite', 'TestSubjectBoss',
    'TheLostAndForgottenNormal', 'TurretOperatorWeak',
), ENCOUNTERS)))
