"""Cumulative pinned 0.107.1 difficulty rules; no process-global difficulty."""
from enum import IntEnum


class Ascension(IntEnum):
    SWARMING_ELITES = 1
    WEARY_TRAVELER = 2
    POVERTY = 3
    TIGHT_BELT = 4
    ASCENDERS_BANE = 5
    INFLATION = 6
    SCARCITY = 7
    TOUGH_ENEMIES = 8
    DEADLY_ENEMIES = 9
    DOUBLE_BOSS = 10


def validate(level):
    if type(level) is not int or not 0 <= level <= 10:
        raise ValueError("Ascension must be an integer from 0 through 10.")
    return level


def level(state):
    return state.config.ascension if state.config is not None else 0


def gold_range(state, bounds):
    return tuple(n * 3 // 4 for n in bounds) if level(state) >= Ascension.POVERTY else bounds


def ancient_heal(state, *, neow=False):
    from game.headless.relics.run_rules import heal
    if neow:
        state.hp = state.max_hp * 4 // 5 if level(state) >= Ascension.WEARY_TRAVELER else state.max_hp
        return
    missing = state.max_hp - state.hp
    heal(state, missing * 4 // 5 if level(state) >= Ascension.WEARY_TRAVELER else missing)
