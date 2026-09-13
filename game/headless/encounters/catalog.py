"""Explicit encounter definitions used by authored run routes."""

from types import MappingProxyType
from game.headless.encounters.overgrowth import build_overgrowth_slimes_encounter
from game.headless.monsters.overgrowth import Nibbit


def nibbit_encounter(rng):
    return [Nibbit(rng)]


ENCOUNTERS = MappingProxyType({
    "overgrowth_nibbit": nibbit_encounter,
    "overgrowth_slimes": build_overgrowth_slimes_encounter,
})
