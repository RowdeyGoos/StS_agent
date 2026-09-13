"""Explicit encounter definitions used by authored run routes."""

from types import MappingProxyType
from game.headless.encounters.base import EncounterDefinition
from game.headless.monsters.byrdonis import Byrdonis
from game.headless.encounters.overgrowth import (
    build_overgrowth_slimes_encounter, build_overgrowth_fuzzy_encounter,
    build_overgrowth_mawler_encounter, build_overgrowth_nibbits_encounter,
)
from game.headless.monsters.overgrowth import Nibbit


def nibbit_encounter(rng):
    return [Nibbit(rng)]


def byrdonis_encounter(rng):
    return [Byrdonis(rng)]


ENCOUNTERS = MappingProxyType({
    "overgrowth_nibbit": EncounterDefinition(nibbit_encounter),
    "overgrowth_slimes": EncounterDefinition(build_overgrowth_slimes_encounter),
    "overgrowth_fuzzy": EncounterDefinition(build_overgrowth_fuzzy_encounter),
    "overgrowth_mawler": EncounterDefinition(build_overgrowth_mawler_encounter),
    "overgrowth_nibbits": EncounterDefinition(build_overgrowth_nibbits_encounter),
    "overgrowth_byrdonis": EncounterDefinition(byrdonis_encounter, "elite", (35, 45), True),
})
