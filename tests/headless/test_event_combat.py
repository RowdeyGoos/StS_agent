"""Dense Vegetation's event, combat, rewards and map continuation."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from game.cli.headless_play import choose_demo_action
from game.headless.core.actions import EndTurn
from game.headless.events.combat import EventCombatRequest
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run import events, event_combat
from game.headless.run.actions import (ChooseEventOption, ChooseNode, LeaveEvent,
    LeaveRewards, ClaimGold, ChooseRewardCard, ClaimPotion)
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from game.headless.run.state import RunPhase


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def step(run, action):
    clone = RunEngine()
    clone.restore(saved(run))
    assert clone.legal_actions() == run.legal_actions()
    run.apply(action)
    clone.apply(action)
    assert saved(run) == saved(clone)


def choice(run, name):
    return ChooseEventOption(run.state.pending['event_instance_id'], name)


def start(**kwargs):
    run = RunEngine(config=RunConfig(), **kwargs)
    events.begin(run.state, 'dense_vegetation')
    return run


def win(run):
    for _ in range(10):
        for enemy in tuple(run.combat.enemies):
            if enemy.is_alive: enemy.take_damage(10000, is_attack=False)
    run.combat.resolve_external_effect()
    run.finish_combat()


def win_restored(run):
    clone = RunEngine(); clone.restore(saved(run))
    win(run); win(clone)
    assert saved(run) == saved(clone)


@pytest.mark.parametrize('hp', [1, 8, 9, 80])
def test_trudge_damage_then_gold_including_lethal(hp):
    run = start(hp=hp, gold=99)
    amount = run.state.pending['data']['gold']
    assert 61 <= amount <= 99
    before = saved(run)
    run.legal_actions(); assert saved(run) == before
    step(run, choice(run, 'trudge_on'))
    assert run.state.hp == max(0, hp-8) and run.state.gold == 99+amount
    assert not run.state.event_combats and run.state.combats_completed == 0
    if hp <= 8:
        assert run.state.phase is RunPhase.DEFEAT and not run.legal_actions()
    else:
        step(run, LeaveEvent(0)); assert run.state.phase is RunPhase.ROUTE


@pytest.mark.parametrize('max_hp,hp,expected', [(80,40,64), (83,40,64), (80,79,80), (80,80,80), (2,1,1)])
def test_rest_heal_rounding_cap_and_mandatory_fight(max_hp,hp,expected):
    run = start(max_hp=max_hp, hp=hp)
    step(run, choice(run, 'rest'))
    assert run.state.hp == expected
    assert run.legal_actions() == (ChooseEventOption(0, 'fight'),)
    before = saved(run)
    for action in (ChooseEventOption(0,'rest'), LeaveEvent(0), ChooseEventOption(99,'fight')):
        with pytest.raises(ValueError): run.apply(action)
        assert saved(run) == before
    step(run, choice(run, 'fight'))
    assert run.combat.player.hp == expected and run.state.pending is None
    assert run.state.rng.request_count('combat_launch') == 1


def test_four_active_wrigglers_alternate_without_spawn_stun():
    run = start(hp=80); run.apply(choice(run,'rest')); step(run,choice(run,'fight'))
    assert [e.intent.move_name for e in run.combat.enemies] == ['Bite','Wriggle','Bite','Wriggle']
    assert all(17 <= e.hp <= 21 for e in run.combat.enemies)
    hp = run.combat.player.hp
    step(run,EndTurn())
    assert run.combat.player.hp == hp-12
    assert [e.strength for e in run.combat.enemies] == [0,2,0,2]
    assert [e.intent.move_name for e in run.combat.enemies] == ['Wriggle','Bite','Wriggle','Bite']
    step(run,EndTurn())
    assert run.combat.player.hp == hp-28
    assert [e.strength for e in run.combat.enemies] == [2,2,2,2]


def test_event_victory_uses_ordinary_rewards_then_leaves_parent():
    graph = MapGraph((MapNode('event','event',('next',),event_id='dense_vegetation'),
                      MapNode('next','combat',(),encounter_id='overgrowth_nibbit')), 'event')
    run = RunEngine(seed=2, config=RunConfig(), graph=graph, hp=30, card_ids=['guilty','strike'])
    add_relic(run.state,'burning_blood'); add_relic(run.state,'sword_of_stone')
    step(run,ChooseNode('event')); step(run,choice(run,'rest')); step(run,choice(run,'fight'))
    win_restored(run)
    assert run.state.hp == 60  # 24 rest + 6 Burning Blood.
    assert run.state.deck[0].combats_seen == 1
    assert run.state.relics[1].counter == 0
    reward=run.state.pending
    assert reward['encounter_id']=='dense_vegetation_event' and 10 <= reward['gold'] <= 20
    assert reward['relic'] is None and len(reward['offers']) == 3
    for kind in (ClaimGold,ChooseRewardCard,ClaimPotion):
        actions=[a for a in run.legal_actions() if isinstance(a,kind)]
        if actions: step(run,actions[0])
    step(run,LeaveRewards())
    assert run.state.phase is RunPhase.ROUTE and run.state.pending is None
    assert run.state.event_combats[0].outcome=='victory' and run.state.event_combats[0].rewards_left
    assert run.state.combats_completed==1 and run.state.visited_nodes==['event']
    before=saved(run)
    with pytest.raises(ValueError):run.apply(ChooseEventOption(0,'fight'))
    assert saved(run)==before
    step(run,ChooseNode('next')); win_restored(run); step(run,LeaveRewards())
    assert run.state.combats_completed==2 and len(run.state.event_combats)==1


def test_event_defeat_has_no_rewards_or_parent_resumption():
    run=start(max_hp=2,hp=1); run.apply(choice(run,'rest'));run.apply(choice(run,'fight'))
    step(run,EndTurn())
    assert run.state.phase is RunPhase.DEFEAT and run.state.pending is None
    assert run.state.event_combats[0].outcome=='defeat'
    assert run.state.combats_completed==1 and not run.legal_actions()


def test_failed_fight_construction_preserves_healed_event_and_all_rng(monkeypatch):
    run=start(hp=20);run.apply(choice(run,'rest'));before=saved(run)
    def fail(**kwargs):
        raise ValueError('injected construction failure')
    monkeypatch.setattr(run,'_prepare_combat',fail)
    with pytest.raises(ValueError):run.apply(choice(run,'fight'))
    assert saved(run)==before and run.combat is None


def test_wrong_request_and_direct_launch_reject_without_bypassing_event():
    run=start();before=saved(run)
    with pytest.raises(ValueError):event_combat.start(run,EventCombatRequest('dense_vegetation_event'))
    assert saved(run)==before
    run.apply(choice(run,'rest'));before=saved(run)
    with pytest.raises(ValueError):event_combat.start(run,EventCombatRequest('overgrowth_nibbit'))
    assert saved(run)==before
    plain=RunEngine(config=RunConfig());before=saved(plain)
    with pytest.raises(ValueError):plain.start_combat(encounter_id='dense_vegetation_event')
    assert saved(plain)==before


@pytest.mark.parametrize('field,value', [('event_instance_id',99),('definition_id','wellspring'),
    ('encounter_id','overgrowth_nibbit'),('combat_number',0),('outcome','victory'),
    ('rewards_left',True),('node_id','missing')])
def test_event_combat_corruption_rejects_atomically(field,value):
    run=start();run.apply(choice(run,'rest'));run.apply(choice(run,'fight'))
    before=saved(run);bad=deepcopy(before);bad['state']['event_combats'][0][field]=value
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


def test_missing_or_duplicated_event_history_cannot_restore_active_or_reward_child():
    run=start();run.apply(choice(run,'rest'));run.apply(choice(run,'fight'))
    for completed in (False,True):
        if completed:win_restored(run)
        before=saved(run)
        for records in ([],before['state']['event_combats']*2):
            bad=deepcopy(before);bad['state']['event_combats']=records
            with pytest.raises(ValueError):run.restore(bad)
            assert saved(run)==before


def test_repeat_event_fights_have_distinct_owners_and_reward_skip_is_final():
    run=start()
    for index in range(2):
        if index:events.begin(run.state,'dense_vegetation')
        step(run,choice(run,'rest'));step(run,choice(run,'fight'));win_restored(run)
        gold=run.state.gold;step(run,LeaveRewards());assert run.state.gold==gold
    assert [r.event_instance_id for r in run.state.event_combats]==[0,1]
    assert [r.combat_number for r in run.state.event_combats]==[1,2]


@pytest.mark.parametrize('seed,path',[(0,'left'),(2,'right'),(4,'left')])
def test_generated_event_combat_preserves_normal_queue_and_all_room_continuations(seed,path):
    # Restrict only the declared event pool to exercise this caller repeatedly.
    run=RunEngine.ironclad_act1(seed=seed)
    run.state.config=replace(run.state.config,event_pool=('dense_vegetation',))
    run.state.event_progression.queue=['dense_vegetation']
    observed=0
    for _ in range(500):
        if run.state.phase is RunPhase.ACT_COMPLETE:break
        if run.state.phase is RunPhase.COMBAT:
            win_restored(run)
        else:
            action=choose_demo_action(run,rest_choice='rest',path=path)
            assignments=deepcopy(run.state.encounter_progression.assignments)
            next_normal=run.state.encounter_progression.next_encounter('combat')
            step(run,action)
            if isinstance(action,ChooseEventOption) and action.option_id=='fight':
                observed+=1
                assert run.state.encounter_progression.assignments==assignments
                assert run.state.encounter_progression.next_encounter('combat')==next_normal
    assert run.state.phase is RunPhase.ACT_COMPLETE
    assert len(run.state.visited_nodes)==16
    assert run.state.combats_completed==len(run.state.encounter_progression.assignments)+observed
    if seed==2:assert observed>0


def test_event_combat_restore_requires_reward_configuration():
    run=start();run.apply(choice(run,'rest'));run.apply(choice(run,'fight'))
    before=saved(run);bad=deepcopy(before);bad['state']['config']=None
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


def test_completed_event_combat_cannot_steal_next_event_identity():
    run=start();run.apply(choice(run,'rest'));run.apply(choice(run,'fight'));win(run)
    run.apply(LeaveRewards());events.begin(run.state,'dense_vegetation')
    before=saved(run);bad=deepcopy(before)
    bad['state']['event_combats'][0]['event_instance_id']=bad['state']['pending']['event_instance_id']
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


def test_dense_entry_and_restored_page_require_usable_combat_rewards():
    run=RunEngine();before=saved(run)
    with pytest.raises(ValueError):events.begin(run.state,'dense_vegetation')
    assert saved(run)==before
    run=start()
    for rest in (False,True):
        if rest:run.apply(choice(run,'rest'))
        before=saved(run);bad=deepcopy(before);bad['state']['config']=None
        with pytest.raises(ValueError):run.restore(bad)
        assert saved(run)==before
