"""Reject broken native event continuations before exposing unusable actions."""
from copy import deepcopy
import json

import pytest
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run import events
from game.headless.run.actions import ChooseEventOption, ChooseRelicReward


@pytest.mark.parametrize('corruption', ['missing', 'duplicate', 'orphan', 'wrong_card', 'foreign_source'])
def test_hefty_tablet_requires_owned_adjacent_injury(corruption):
    run = RunEngine(rng_profile='native')
    run.obtain_relic('hefty_tablet')
    before = json.loads(json.dumps(run.snapshot()))
    bad = deepcopy(before)
    work = bad['state']['relic_work']
    if corruption == 'missing': work.pop()
    elif corruption == 'duplicate': work.append(deepcopy(work[-1]))
    elif corruption == 'orphan': work.pop(0)
    elif corruption == 'wrong_card': work[-1]['values'] = ['doubt']
    else: work[-1]['source'] = 'foreign'
    with pytest.raises(ValueError): run.restore(bad)
    assert json.loads(json.dumps(run.snapshot())) == before
    restored = RunEngine()
    restored.restore(before)
    restored.apply(ChooseRelicReward(0))
    assert restored.state.deck[-1].definition.definition_id == 'injury'


@pytest.mark.parametrize('event,choices,count', [
    ('punch_off', ('i_can_take_them','fight'), 2),
    ('the_lantern_key', ('keep_the_key','fight'), 1),
])
def test_combat_layout_constructs_hp_once_and_rejects_foreign_source(event, choices, count):
    run = RunEngine(seed=42, rng_profile='native', config=RunConfig())
    events.begin(run.state, event)
    assert run.state.rng.stream('niche').counter == count
    before = json.loads(json.dumps(run.snapshot()))
    for mutation in ('seed', 'counter', 'missing'):
        bad = deepcopy(before)
        context = bad['state']['pending']['data']['pages'][0]['context']
        if mutation == 'missing': context.pop('enemy_hp_rng')
        else: context['enemy_hp_rng'][mutation] += 1
        with pytest.raises(ValueError): run.restore(bad)
        assert json.loads(json.dumps(run.snapshot())) == before
    for choice in choices:
        run.restore(json.loads(json.dumps(run.snapshot())))
        run.apply(ChooseEventOption(0, choice))
    assert run.state.rng.stream('niche').counter == count
    snapshot = json.loads(json.dumps(run.snapshot()))
    other = RunEngine(); other.restore(snapshot)
    assert json.loads(json.dumps(other.snapshot())) == snapshot
    assert [(e.hp,e.max_hp) for e in other.combat.enemies] == [(e.hp,e.max_hp) for e in run.combat.enemies]


def test_content_snapshot_fingerprint_is_exact_and_detached():
    from dataclasses import asdict
    from game.headless.run.snapshots import _item_definitions
    from game.headless.relics.base import RELICS
    from game.headless.potions.base import POTIONS
    expected = json.loads(json.dumps({'relics': [asdict(v) for v in RELICS.values()],
                                     'potions': [asdict(v) for v in POTIONS.values()]}))
    actual = _item_definitions()
    assert actual == expected
    actual['relics'][0]['definition_id'] = 'tampered'
    assert _item_definitions() == expected


def test_previous_run_continuation_schema_is_rejected_atomically():
    run = RunEngine(rng_profile='native')
    before = run.snapshot()
    old = deepcopy(before)
    old['schema'] = 'headless_run_state_v62'
    with pytest.raises(ValueError): run.restore(old)
    assert run.snapshot() == before
