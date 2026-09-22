"""Actual native ending entry, final rewards, recorded victory and disposal."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game.headless.core.native_service import NativeRandomService
from game.headless.relics.base import RelicInstance
from game.headless.run import rewards
from game.headless.run.actions import ContinueAct, ChooseEventOption
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase
from tests.headless.test_act2_run import complete_act, clone, saved, step

RECORD = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_campaign_ending_2026_09_20.json').read_text())


@pytest.fixture(scope='module', params=['0','2','42'])
def final_boss(request):
    run = RunEngine.ironclad_run(seed=int(request.param), rng_profile='native', last_act='glory')
    run.state.max_hp = run.state.hp = 10000
    for act in range(3):
        complete_act(run)
        if act < 2:
            run.apply(ContinueAct())
    return saved(run)


@pytest.mark.parametrize('loadout',['plain','maw_bank','wongo','both'])
def test_native_ending_and_terminal_snapshot(final_boss, loadout):
    run = RunEngine()
    run.restore(final_boss)
    row = next(r for r in RECORD['result']['rows'] if r['seed'] == str(run.state.seed) and r['loadout'] == loadout)
    # Completed Python path above is synthetic setup, not native combat evidence.
    # Match the native fixture's authored final-boundary inventory and RNG.
    run.state.hp = 31
    run.state.gold = row['goldBefore']
    names = ['burning_blood'] + (['maw_bank'] if loadout in ('maw_bank','both') else []) + (['wongos_mystery_ticket'] if loadout in ('wongo','both') else [])
    run.state.relics = [RelicInstance(name, run.state.allocate_item_id(), counter=5 if name=='wongos_mystery_ticket' else 0) for name in names]
    run.state.rng._streams['niche'] = NativeRandomService(run.state.seed).stream('niche')
    old_floor = len(run.state.visited_nodes)
    step(run, ContinueAct())
    state = run.state
    assert state.pending['definition_id'] == 'the_architect'
    assert state.hp == row['entryHp'] == 31
    assert state.gold == row['goldAfter']
    assert len(state.visited_nodes) == old_floor
    assert row['floorBefore'] == row['floorAfter']
    assert row['room'] == 'Event' and row['isVictoryRoom']
    for stream, prefix in [('niche','niche'),('event:THE_ARCHITECT','event')]:
        rng = state.rng.stream(stream)
        assert rng.counter == row[prefix+'Counter']
        assert deepcopy(rng).next_double() == row[prefix+'Suffix']
    step(run, ChooseEventOption(state.pending['event_instance_id'], 'proceed'))
    # The public winning state corresponds to native serialization before cleanup.
    assert run.state.phase is RunPhase.VICTORY
    assert run.state.hp == row['savedHp'] == 31 and row['disposedHp'] == 0
    assert row['recorded'] and row['uploadsDisabled'] and row['savingDisabled']
    assert run.state.pending is None and not run.legal_actions()
    clone(run)
    before = saved(run)
    with pytest.raises(ValueError):
        run.apply(ContinueAct())
    assert saved(run) == before


@pytest.mark.parametrize('row',RECORD['result']['rows'],ids=lambda r:f'{r["seed"]}-{r["loadout"]}')
def test_final_boss_base_rewards_suppressed_but_ticket_still_fires(row):
    from game.headless.run.config import RunConfig
    run = RunEngine(seed=int(row['seed']), rng_profile='native', config=RunConfig(act='glory'))
    run.state.act_index = 2
    if row['loadout'] in ('wongo','both'):
        run.state.relics = [RelicInstance('wongos_mystery_ticket',run.state.allocate_item_id(),counter=5)]
    rewards.begin_combat_rewards(run.state,run.cards,encounter_id='glory_test_subject')
    pending = run.state.pending
    assert pending['gold'] == 0 and pending['offers'] == [] and pending['potion'] is None
    assert len(pending['extra_rewards']) == len(row['rewardRows'])
    assert all(r['kind']=='RelicReward' for r in row['rewardRows'])
    assert [r['offers'][0].upper() for r in pending['extra_rewards']] == [r['relic'] for r in row['rewardRows']]
    if run.state.relics:
        assert run.state.relics[0].counter == 6


def test_pre_ending_rng_schema_is_rejected():
    run = RunEngine()
    before = saved(run)
    old = deepcopy(before)
    old['schema'] = 'headless_run_state_v53'
    with pytest.raises(ValueError):
        run.restore(old)
    assert saved(run) == before
