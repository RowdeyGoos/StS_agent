"""Native potion/relic combinations: complete power amounts at each boundary."""
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import hashlib
from itertools import product
import gzip
import json
import re

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard, EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import NativeRandomService, COMBAT_STREAMS
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.monsters.hive_normal import Chomper
from game.headless.potions.base import PotionInstance
from game.headless.potions import use as potion_use
from game.headless.relics.base import RelicInstance
from game.headless.relics.combat import memory

ROOT = Path(__file__).parents[2]
RECORD = json.loads(gzip.decompress((ROOT / 'docs/evidence/native_item_status_2026_09_20.json.gz').read_bytes()))
CURRENT_RECORD = json.loads(gzip.decompress((ROOT / 'docs/evidence/native_conditional_relic_stats_2026_09_20.json.gz').read_bytes()))


def slug(name):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def saved(combat):
    return json.loads(json.dumps(combat.snapshot()))


def prepare(row):
    service = NativeRandomService(int(row['seed']))
    streams = {key: service.stream(key) for key in COMBAT_STREAMS}
    initial_shuffle = streams['shuffle'].getstate()
    construction = MonsterConstruction(streams['monster_ai'], streams['niche'], ascension=row['ascension'])
    engine = CombatEngine(cards=DEFAULT_CARDS, cards_per_turn=0, ascension=row['ascension'],
        deck_factory=lambda: [DEFAULT_CARDS.create(k) for k in ['strike'] * 3 + ['defend'] * 11],
        encounter_factory=lambda _: [Chomper(construction)])
    engine.native_streams, engine.rng = streams, streams['monster_ai']
    potions = [PotionInstance(slug(k), f'potion.{i}') for i, k in enumerate(row['potionNames'])]
    engine.reset(relics=[RelicInstance(slug(k), f'relic.{i}') for i, k in enumerate(row['relicNames'])],
                 initial_hp=row['before']['hp'], potions=potions, potion_slots=0)
    engine.cards_per_turn = 5
    p, enemy = engine.player, engine.enemies[0]
    cards = sorted(p.deck.all_cards(), key=lambda c: int(c.instance_id.rsplit('.', 1)[1]))
    p.hand[:] = cards[:4]
    p.deck.draw_pile = list(reversed(cards[4:]))
    p.deck.discard_pile.clear()
    p.deck.rng.setstate(initial_shuffle)
    p.hp, p.block, p.energy = row['before']['hp'], row['before']['block'], 10
    enemy.hp = enemy.max_hp = 1000
    enemy.statuses._counts.clear()  # Authored native fixture omits AfterAddedToRoom.
    if row['variant']:
        p.statuses._counts['artifact'] = 1
        enemy.statuses._counts['artifact'] = 1
    if row['scenario'] == 'speed':
        p.statuses._counts['frail'] = 2
    identities = {c.instance_id: f'card.{i}' for i, c in enumerate(cards)}
    return engine, identities


def power_map(engine, *, enemy=False):
    p = engine.player
    owner = engine.enemies[0] if enemy else p
    result = {k.upper() + '_POWER': v for k, v in owner.statuses._counts.items() if v}
    strength = owner.strength
    if enemy:
        shackles = result.pop('DARK_SHACKLES_POWER', 0)
        if shackles:
            result['SHACKLING_POTION_POWER'] = shackles
            strength -= shackles
    else:
        aliases = {'temporary_strength': 'FLEX_POTION_POWER', 'temporary_dexterity': 'SPEED_POTION_POWER'}
        for key, value in p.rules.powers.items():
            if value:
                result[aliases.get(key, key.upper() + '_POWER')] = value
    if strength:
        result['STRENGTH_POWER'] = strength
    return result


def boundary(engine, identities):
    p, enemy = engine.player, engine.enemies[0]
    def pile(cards):
        return [identities[c.instance_id] for c in cards]
    relics = []
    for r in p.rules.relics:
        name = r['definition_id']
        state = bool(memory(p, r).get('dexterity_applied')) if name == 'belt_buckle' else bool(r['counter']) if name == 'lizard_tail' else None
        relics.append(dict(id=name.upper(), state=state))
    return dict(hp=p.hp, maxHp=p.max_hp, block=p.block, energy=p.energy, turn=engine.turn,
        powers=power_map(engine), enemy=dict(hp=enemy.hp, block=enemy.block, powers=power_map(engine, enemy=True),
            move={'Clamp': 'CLAMP_MOVE', 'Screech': 'SCREECH_MOVE'}[enemy.intent.move_name]),
        potions=[None if item is None else item['definition_id'].upper() for item in p.rules.potions],
        relics=relics, hand=pile(p.hand), draw=pile(reversed(p.deck.draw_pile)),
        discard=pile(p.deck.discard_pile), exhaust=pile(p.deck.exhaust_pile))


def expected(native):
    result = json.loads(json.dumps(native))
    for owner in (result, result['enemy']):
        powers = owner['powers']
        assert len({p['id'] for p in powers}) == len(powers), 'Duplicate native power requires explicit instance matching'
        owner['powers'] = {p['id']: p['amount'] for p in powers}
    return result


def apply(engine, identities, step):
    if step['kind'] == 'end_turn':
        engine.apply(EndTurn())
    elif step['kind'] == 'play':
        identity = next(k for k, v in identities.items() if v == f"card.{step['index']}")
        engine.apply(PlayCard(identity, None if step['index'] == 3 else 0))
    else:
        # Use the production run-owned potion entry point with an authored owner;
        # the combat snapshot owns every item and any resulting continuation.
        items = [None if r is None else PotionInstance(**r) for r in engine.player.rules.potions]
        owner = SimpleNamespace(state=SimpleNamespace(potions=items), combat=engine)
        item = items[step['index']]
        action = next(a for a in potion_use.actions(owner) if a.instance_id == item.instance_id)
        potion_use.use(owner, action)


@pytest.mark.parametrize('row', RECORD['result']['rows'], ids=lambda r: f"{r['scenario']}-{r['seed']}-a{r['ascension']}-{r['variant']}")
def test_native_potion_relic_powers_and_turn_continuation(row):
    engine, identities = prepare(row)
    assert boundary(engine, identities) == expected(row['before'])
    for index, step in enumerate(row['steps']):
        snapshot = saved(engine)
        other = CombatEngine(cards=DEFAULT_CARDS)
        other.restore(snapshot)
        assert saved(other) == snapshot
        assert other.legal_actions() == engine.legal_actions()
        apply(engine, identities, step)
        apply(other, identities, step)
        assert saved(other) == saved(engine)
        assert boundary(engine, identities) == expected(step['state']), (row['scenario'], index, step['kind'])
    for key, native in (('shuffle', 'shuffle'), ('combat_targets', 'targets'), ('niche', 'niche'), ('monster_ai', 'ai')):
        stream = engine.native_streams[key]
        assert stream.counter == row[native]['counter']
        assert deepcopy(stream).next_double() == row[native]['suffix']


def test_native_capture_identity_and_case_census():
    assert RECORD['userDirectoryRemoved']
    assert RECORD['result']['assemblySha256'] == RECORD['pins']['sts2.dll'] == 'e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18'
    # The extended fixture freshly reruns the original cases without repinning
    # their historical capture. Their parsed results must remain identical.
    assert [r for r in CURRENT_RECORD['result']['rows'] if not r['scenario'].startswith('conditional_')] == RECORD['result']['rows']
    assert CURRENT_RECORD['userDirectoryRemoved'] and CURRENT_RECORD['pins'] == RECORD['pins']
    for name, digest in CURRENT_RECORD['fixtureSources'].items():
        assert hashlib.sha256((ROOT / 'tools/native_combat_oracle/queue_runtime' / name).read_bytes()).hexdigest() == digest
    scenarios = {'flex', 'speed', 'binding', 'shackles', 'ward', 'replay', 'healing', 'duration', 'fairy', 'chaos', 'flex_late', 'speed_late'}
    rows = RECORD['result']['rows']
    keys = [(r['scenario'], r['seed'], r['ascension'], r['variant']) for r in rows]
    assert len(keys) == len(set(keys)) == 144
    assert set(keys) == set(product(scenarios, ('0', '2', '42'), (0, 10), (False, True)))
    states = [state for r in rows for state in [r['before'], *[s['state'] for s in r['steps']]]]
    assert len(states) == 1272
    assert {p['id'] for s in states for owner in (s, s['enemy']) for p in owner['powers']} == {
        name + '_POWER' for name in ('ARTIFACT', 'BLOCK_NEXT_TURN', 'BUFFER', 'DEMISE',
        'DEXTERITY', 'DUPLICATION', 'FLEX_POTION', 'FRAIL', 'GIGANTIFICATION', 'PLATING',
        'RADIANCE', 'REGEN', 'REPTILE_TRINKET', 'RITUAL', 'SHACKLING_POTION', 'SHRINK',
        'SPEED_POTION', 'STRENGTH', 'THORNS', 'VULNERABLE', 'WEAK')}
    # A10 must execute its stronger native Clamp, not just carry an A10 label.
    hp = {r['ascension']: r['steps'][-1]['state']['hp'] for r in rows
          if r['scenario'] == 'flex' and not r['variant'] and r['seed'] == '0'}
    assert hp == {0: 32, 10: 30}


def test_older_temporary_relic_state_rejects_atomically():
    row = next(r for r in RECORD['result']['rows'] if r['scenario'] == 'flex_late' and r['variant'])
    engine, identities = prepare(row)
    apply(engine, identities, row['steps'][0])
    before = saved(engine)
    legacy = deepcopy(before)
    legacy['schema'] = 'headless_combat_state_v42'
    with pytest.raises(ValueError):
        engine.restore(legacy)
    assert saved(engine) == before
