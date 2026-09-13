"""Explicit encounter definitions used by authored run routes."""

from types import MappingProxyType
from game.headless.encounters.overgrowth import (
    build_overgrowth_slimes_encounter, build_overgrowth_fuzzy_encounter,
    build_overgrowth_mawler_encounter, build_overgrowth_nibbits_encounter,
)
from game.headless.monsters.overgrowth import Nibbit


def nibbit_encounter(rng):
    return [Nibbit(rng)]


ENCOUNTERS = MappingProxyType({
    "overgrowth_nibbit": nibbit_encounter,
    "overgrowth_slimes": build_overgrowth_slimes_encounter,
    "overgrowth_fuzzy": build_overgrowth_fuzzy_encounter,
    "overgrowth_mawler": build_overgrowth_mawler_encounter,
    "overgrowth_nibbits": build_overgrowth_nibbits_encounter,
})
