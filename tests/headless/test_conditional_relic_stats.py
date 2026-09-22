"""Native conditional stat changes, Artifact and exact JSON continuation."""

from copy import deepcopy
from dataclasses import asdict
from itertools import product

import pytest

from game.headless.core.combat import CombatEngine
from game.headless.monsters.hive_normal import Chomper
from game.headless.potions.base import PotionInstance
from game.headless.relics.base import RelicInstance
from game.headless.relics.combat import heal, memory, owned
from game.headless.relics.damage import hp_changed, potions_changed
from tests.headless.test_native_item_status import CURRENT_RECORD, power_map, saved, slug

ROWS = [row for row in CURRENT_RECORD['result']['rows'] if row['scenario'].startswith('conditional_')]


def prepare(row):
    engine = CombatEngine(seed=int(row['seed']), ascension=row['ascension'],
                          cards_per_turn=0, encounter_factory=lambda construction: [Chomper(construction)])
    engine.reset(initial_hp=41, potion_slots=2,
                 potions=[PotionInstance('foul_potion', 'potion.0'), None, None],
                 relics=[RelicInstance(slug(name), f'relic.{i}') for i, name in enumerate(row['relicNames'])])
    engine.enemies[0].hp = engine.enemies[0].max_hp = 1000
    if row['variant']:
        engine.player.apply_status('artifact', 1)
    return engine


def boundary(engine, row):
    p = engine.player
    buckle = 'buckle' in row['scenario']
    relic = owned(p, 'belt_buckle' if buckle else 'red_skull')
    helmet = owned(p, 'ruined_helmet')
    return dict(hp=p.hp, maxHp=p.max_hp, ending=p.combat_is_ending,
                powers=power_map(engine),
                active=memory(p, relic).get('dexterity_applied' if buckle else 'strength_applied', False),
                helmetUsed=memory(p, helmet).get('used', False) if helmet else None,
                potionCount=sum(item is not None for item in p.rules.potions))


def expected(state):
    state = deepcopy(state)
    assert len({p['id'] for p in state['powers']}) == len(state['powers'])
    state['powers'] = {p['id']: p['amount'] for p in state['powers']}
    return state


def apply(engine, row, kind):
    p = engine.player
    if kind == 'ending':
        engine.enemies[0].hp = 0
        # Match the native fixture's authored ending boundary, without running
        # complete combat cleanup in either model.
        engine._check_terminal()
    elif 'buckle' in row['scenario']:
        active = kind == 'activate'
        p.rules.potions = ([None] if active else [asdict(PotionInstance('foul_potion', 'potion.0'))]) + [None, None]
        p.rules.potion_slots = 3 if active else 2
        potions_changed(p)
    else:
        p.hp = 40 if kind == 'activate' else 41
        hp_changed(p)


@pytest.mark.parametrize('row', ROWS, ids=lambda r: f"{r['scenario']}-{r['seed']}-a{r['ascension']}-artifact{r['variant']}")
def test_native_conditional_stats_and_json_continuation(row):
    engine = prepare(row)
    assert boundary(engine, row) == expected(row['before'])
    for step in row['steps']:
        snapshot = saved(engine)
        restored = CombatEngine()
        restored.restore(snapshot)
        assert saved(restored) == snapshot
        assert restored.legal_actions() == engine.legal_actions()
        apply(engine, row, step['kind'])
        apply(restored, row, step['kind'])
        assert saved(restored) == saved(engine)
        assert boundary(engine, row) == expected(step['state'])


def test_native_conditional_case_census():
    scenarios = {f'conditional_{name}{ending}' for name in ('skull', 'skull_helmet', 'buckle')
                 for ending in ('', '_ending')}
    keys = [(r['scenario'], r['seed'], r['ascension'], r['variant']) for r in ROWS]
    assert len(keys) == len(set(keys)) == 72
    assert set(keys) == set(product(scenarios, ('0', '2', '42'), (0, 10), (False, True)))


def test_skull_hp_dispatch_and_protected_bonus_survive_run_restore():
    from tests.headless.test_relic_combat import setup, saved as save_run
    from game.headless.run.engine import RunEngine
    run, engine = setup('red_skull', 'ruined_helmet', hp=41)
    p = engine.player
    p.lose_hp(1)
    engine.resolve_external_effect()
    assert p.hp == 40 and p.strength == 6
    p.apply_status('artifact', 1)
    heal(p, 1)
    assert p.strength == 6 and p.statuses.get('artifact') == 0
    restored = RunEngine()
    restored.restore(save_run(run))
    for current in (run, restored):
        current.combat.player.lose_hp(1)
        current.combat.resolve_external_effect()
        assert current.combat.player.strength == 9
        heal(current.combat.player, 1)
        assert current.combat.player.strength == 6
    assert save_run(restored) == save_run(run)


def test_buckle_procurement_and_discard_preserve_protected_bonus():
    from tests.headless.test_potions_complete import setup, clone
    from game.headless.run.actions import DiscardPotion
    run, item = setup('foul_potion', relics=['belt_buckle'])
    run.apply(DiscardPotion(item.instance_id))
    p = run.combat.player
    assert p.rules.powers['dexterity'] == 2
    p.apply_status('artifact', 1)
    p.rules.potions_generated.append('foul_potion')
    run.sync_combat_loot()
    assert p.rules.powers['dexterity'] == 2 and p.statuses.get('artifact') == 0
    restored = clone(run)
    action = DiscardPotion(next(item.instance_id for item in run.state.potions if item))
    run.apply(action)
    restored.apply(action)
    assert run.combat.player.rules.powers['dexterity'] == 4
    assert run.snapshot() == restored.snapshot()


@pytest.mark.parametrize('scenario,stat,bonus', [('conditional_skull', 'strength', 3),
                                              ('conditional_buckle', 'dexterity', 2)])
@pytest.mark.parametrize('initial', [-5, 5])
def test_artifact_blocks_removal_independently_of_existing_stat(scenario, stat, bonus, initial):
    row = next(r for r in ROWS if r['scenario'] == scenario and r['variant'])
    engine = prepare(row)
    p = engine.player
    if stat == 'strength':
        p.strength = initial
    else:
        p.rules.powers[stat] = initial
    apply(engine, row, 'activate')
    apply(engine, row, 'deactivate')
    assert (p.strength if stat == 'strength' else p.rules.powers[stat]) == initial + bonus
    assert p.statuses.get('artifact') == 0


def test_lethal_hp_change_records_skull_condition_without_granting_strength():
    row = next(r for r in ROWS if r['scenario'] == 'conditional_skull_helmet')
    engine = prepare(row)
    p = engine.player
    p.lose_hp(p.hp)
    engine.resolve_external_effect()
    assert not p.is_alive and p.strength == 0
    assert memory(p, owned(p, 'red_skull'))['strength_applied']
    assert not memory(p, owned(p, 'ruined_helmet')).get('used', False)
    restored = CombatEngine()
    restored.restore(saved(engine))
    assert saved(restored) == saved(engine)
