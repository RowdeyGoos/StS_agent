"""All 20 native Underdocks encounters; encounter RNG owns opening roles."""
from functools import partial
from types import MappingProxyType
from game.headless.encounters.base import EncounterDefinition
from game.headless.encounters.randomness import create
from game.headless.monsters.underdocks_normal import (
    CorpseSlug, CalcifiedCultist, DampCultist, FossilStalker, HauntedShip,
    Seapunk, SewerClam, SludgeSpinner, Toadpole,
)
from game.headless.monsters.underdocks_summons import GremlinMerc, LivingFog, TwoTailedRat
from game.headless.monsters.underdocks_elites import PhantasmalGardener, SkulkingColony, TerrorEel
from game.headless.monsters.underdocks_bosses import LagavulinMatriarch, SoulFysh, WaterfallGiant
from game.headless.monsters.event_monsters import PunchConstruct


def group(kinds, rng):
    return [create(kind, rng) for kind in kinds]


def slugs(count, rng):
    opening = rng.randrange(3)
    return [create(CorpseSlug, rng, opening=(opening + i) % 3) for i in range(count)]


def rats(rng):
    opening = rng.randrange(3)
    return [create(TwoTailedRat, rng, opening=(opening + i) % 3, position=i + 2) for i in range(3)]


def toadpoles(rng):
    return [create(Toadpole, rng, front=True), create(Toadpole, rng)]


def gardeners(rng):
    return [create(PhantasmalGardener, rng, opening=i) for i in (2, 0, 1, 3)]


def encounter(*kinds, room_kind='combat'):
    return EncounterDefinition(partial(group, kinds), room_kind,
                               (35, 45) if room_kind == 'elite' else (100, 100) if room_kind == 'boss' else (10, 20),
                               room_kind == 'elite')


ENCOUNTERS = MappingProxyType({
    'underdocks_corpse_slugs': EncounterDefinition(partial(slugs, 3)),
    'underdocks_corpse_slugs_weak': EncounterDefinition(partial(slugs, 2)),
    'underdocks_cultists': encounter(CalcifiedCultist, DampCultist),
    'underdocks_fossil_stalker': encounter(FossilStalker),
    'underdocks_gremlin_merc': encounter(GremlinMerc),
    'underdocks_haunted_ship': encounter(HauntedShip),
    'underdocks_lagavulin_matriarch': encounter(LagavulinMatriarch, room_kind='boss'),
    'underdocks_living_fog': encounter(LivingFog),
    'underdocks_phantasmal_gardeners': EncounterDefinition(gardeners, 'elite', (35, 45), True),
    'underdocks_punch_construct': encounter(PunchConstruct),
    'underdocks_seapunk': encounter(CalcifiedCultist, Seapunk),
    'underdocks_seapunk_weak': encounter(Seapunk),
    'underdocks_sewer_clam': encounter(SewerClam),
    'underdocks_skulking_colony': encounter(SkulkingColony, room_kind='elite'),
    'underdocks_sludge_spinner': encounter(SludgeSpinner),
    'underdocks_soul_fysh': encounter(SoulFysh, room_kind='boss'),
    'underdocks_terror_eel': encounter(TerrorEel, room_kind='elite'),
    'underdocks_toadpoles': EncounterDefinition(toadpoles),
    'underdocks_two_tailed_rats': EncounterDefinition(rats),
    'underdocks_waterfall_giant': encounter(WaterfallGiant, room_kind='boss'),
})
NATIVE_UNDERDOCKS_ENCOUNTERS = MappingProxyType(dict(zip((
    'CorpseSlugsNormal', 'CorpseSlugsWeak', 'CultistsNormal', 'FossilStalkerNormal',
    'GremlinMercNormal', 'HauntedShipNormal', 'LagavulinMatriarchBoss', 'LivingFogNormal',
    'PhantasmalGardenersElite', 'PunchConstructNormal', 'SeapunkNormal', 'SeapunkWeak',
    'SewerClamNormal', 'SkulkingColonyElite', 'SludgeSpinnerWeak', 'SoulFyshBoss',
    'TerrorEelElite', 'ToadpolesWeak', 'TwoTailedRatsNormal', 'WaterfallGiantBoss',
), ENCOUNTERS)))
