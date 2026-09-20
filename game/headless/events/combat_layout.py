"""Owned construction RNG for enemies visible before an event choice.

Native combat-layout events construct creatures on entry and reuse them when
combat starts. Save the HP constructor input, not an executable factory or a
second live RNG stream. AI initialization still belongs to combat startup.
"""
from copy import deepcopy

ENCOUNTERS = {'punch_off': 'punch_off_event', 'the_lantern_key': 'mysterious_knight_event'}


def prepare(state, name):
    if name not in ENCOUNTERS or not getattr(state.rng, 'native', False):
        return None
    from game.headless.encounters.randomness import EncounterRandom
    from game.headless.encounters.extended_events import ENCOUNTERS as definitions, NATIVE_IDS
    import re
    encounter = ENCOUNTERS[name]
    hp = state.rng.stream('niche')
    saved = hp.getstate()
    floor = state.visited_room_count + int(state.initialization is not None or state.ancient_start is not None)
    construction = EncounterRandom(state.rng.root_seed, floor,
        re.sub(r'(?<!^)(?=[A-Z])', '_', NATIVE_IDS[encounter]).upper(),
        deepcopy(state.rng.stream('monster_ai')), hp,
        ascension=state.config.ascension if state.config else 0)
    definitions[encounter](construction)
    return saved


def restore(data):
    from game.headless.core.native_rng import NativeRng
    rng = NativeRng()
    rng.setstate(data)
    return rng


def validate(state, name, data):
    if name not in ENCOUNTERS:
        return
    saved = data['pages'][0]['context'].get('enemy_hp_rng')
    if not getattr(state.rng, 'native', False):
        if saved is not None:
            raise ValueError('Fixture event cannot own native construction RNG.')
        return
    before = restore(saved)
    current = state.rng.stream('niche')
    if before.seed != current.seed or before.counter + (2 if name == 'punch_off' else 1) > current.counter:
        raise ValueError('Event enemy construction differs from its owned HP stream.')
