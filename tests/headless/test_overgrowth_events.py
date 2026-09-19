"""Native repeated upgrades, composite transformations and conditional events."""
from copy import deepcopy
import json

import pytest

from game.cli.headless_play import choose_demo_action
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.events.catalog import EVENTS
from game.headless.events.progression import EventProgression
from game.headless.events.eligibility import entry_conditions
from game.headless.run import events
from game.headless.run.actions import ChooseEventOption, ChooseEventCard, LeaveEvent
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase


def saved(run):
    return json.loads(json.dumps(run.snapshot(), sort_keys=True))


def step(run, action):
    clone = RunEngine(); clone.restore(saved(run))
    assert clone.legal_actions() == run.legal_actions()
    clone.apply(action); run.apply(action)
    assert saved(run) == saved(clone)


def start(event, **kwargs):
    run = RunEngine(**kwargs)
    events.begin(run.state, event)
    return run


def option(run, name):
    return ChooseEventOption(run.state.pending['event_instance_id'], name)


@pytest.mark.parametrize('hp,expected', [(80,80),(79,80),(1,21)])
def test_tablet_smash_heals_twenty_and_finishes(hp,expected):
    run = start('tablet_of_truth', hp=hp)
    step(run, option(run,'smash'))
    assert run.state.hp == expected
    assert run.state.max_hp == 80
    assert all(c.upgrade_level == 0 for c in run.state.deck)
    assert run.state.rng.request_count('event.tablet_upgrade') == 0
    step(run, LeaveEvent(run.state.pending['event_instance_id']))


def test_tablet_all_five_steps_upgrade_random_cards_then_all_remaining_and_enter_combat():
    run = start('tablet_of_truth', seed=4, hp=35)
    for count,maximum in enumerate((77,71,59,35,1),1):
        action = option(run,f'decipher_{count}')
        step(run, action)
        assert run.state.max_hp == maximum
        assert run.state.hp == min(35,maximum)
        assert sum(c.upgrade_level for c in run.state.deck) == (count if count < 5 else 10)
        assert run.state.rng.request_count('event.tablet_upgrade') == min(count,4)
        before = saved(run)
        with pytest.raises(ValueError): run.apply(action)
        assert saved(run) == before
    assert run.legal_actions() == (LeaveEvent(0),)
    step(run, LeaveEvent(0))
    run.start_combat(encounter_id='overgrowth_nibbit')
    assert run.combat.player.max_hp == run.combat.player.hp == 1
    clone = RunEngine(); clone.restore(saved(run))
    assert saved(run) == saved(clone)


@pytest.mark.parametrize('count', range(1,5))
def test_tablet_give_up_keeps_paid_cost_and_completed_upgrades(count):
    run = start('tablet_of_truth')
    for i in range(count): step(run, option(run,f'decipher_{i+1}'))
    before_hp = run.state.hp
    step(run, option(run,'give_up'))
    assert run.state.hp == before_hp
    assert sum(c.upgrade_level for c in run.state.deck) == count
    assert run.legal_actions() == (LeaveEvent(0),)


@pytest.mark.parametrize('maximum,count',[(1,1),(3,1),(9,2),(21,3),(45,4)])
def test_lethal_decipher_keeps_one_max_hp_and_kills_without_upgrade(maximum,count):
    run = start('tablet_of_truth',max_hp=maximum)
    for i in range(count): step(run, option(run,f'decipher_{i+1}'))
    assert run.state.phase is RunPhase.DEFEAT
    assert run.state.hp == 0 and run.state.max_hp == 1
    assert sum(c.upgrade_level for c in run.state.deck) == count-1
    assert run.state.rng.request_count('event.tablet_upgrade') == count-1
    assert not run.legal_actions()
    clone=RunEngine();clone.restore(saved(run))
    assert saved(run)==saved(clone)


@pytest.mark.parametrize('cards', [[],['strike']])
def test_empty_or_fully_upgraded_deck_still_pays_cost_without_random_draw(cards):
    run = RunEngine(card_ids=cards)
    for card in run.state.deck:card.upgrade()
    events.begin(run.state,'tablet_of_truth')
    for i in range(5):step(run,option(run,f'decipher_{i+1}'))
    assert run.state.hp == run.state.max_hp == 1
    assert run.state.rng.request_count('event.tablet_upgrade') == 0


def test_morphic_loner_gains_five_maximum_and_current_hp_without_spending_gold():
    run=start('morphic_grove',gold=163,hp=40)
    step(run,option(run,'loner'))
    assert (run.state.hp,run.state.max_hp,run.state.gold)==(45,85,163)
    step(run,LeaveEvent(0))
    run.start_combat(encounter_id='overgrowth_nibbit')
    assert (run.combat.player.hp,run.combat.player.max_hp)==(45,85)


def test_morphic_pays_all_gold_then_collects_two_originals_before_revealing_transforms():
    run=start('morphic_grove',gold=237,seed=4)
    originals=[c.instance_id for c in run.state.deck]
    step(run,option(run,'group'))
    assert run.state.gold==0
    step(run,ChooseEventCard(0,originals[3]))
    assert [c.instance_id for c in run.state.deck]==originals
    assert run.state.rng.request_count('event.morphic_transform')==0
    assert ChooseEventCard(0,originals[3]) not in run.legal_actions()
    assert LeaveEvent(0) not in run.legal_actions()
    step(run,ChooseEventCard(0,originals[0]))
    assert run.state.rng.request_count('event.morphic_transform')==2
    current=[c.instance_id for c in run.state.deck]
    assert current[3] not in originals and current[0] not in originals
    assert all(current[i]==originals[i] for i in range(10) if i not in (0,3))
    assert run.state.pending['data']['selected']==[originals[3],originals[0]]
    assert all(c.upgrade_level==0 for c in run.state.deck)
    step(run,LeaveEvent(0))
    run.start_combat(encounter_id='overgrowth_nibbit')
    clone=RunEngine();clone.restore(saved(run))
    assert saved(run)==saved(clone)


@pytest.mark.parametrize('count',range(3))
def test_morphic_auto_selects_when_not_more_than_two_cards_remain(count):
    # Native exhausted-pool fallback may offer an event despite IsAllowed false.
    run=start('morphic_grove',gold=19,card_ids=['strike']*count)
    step(run,option(run,'group'))
    assert run.state.gold==0 and len(run.state.deck)==count
    assert run.state.rng.request_count('event.morphic_transform')==count
    assert run.legal_actions()==(LeaveEvent(0),)


def test_second_transform_failure_rolls_back_both_replacements_and_rng(monkeypatch):
    from game.headless.events import morphic_grove
    run=start('morphic_grove',gold=160)
    run.apply(option(run,'group'))
    run.apply(run.legal_actions()[0])
    before=saved(run)
    original=morphic_grove.transform_card
    calls=0
    def failing(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:raise ValueError('second transform failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(morphic_grove,'transform_card',failing)
    with pytest.raises(ValueError,match='second transform'):run.apply(run.legal_actions()[0])
    assert saved(run)==before


@pytest.mark.parametrize('event',['morphic_grove','tablet_of_truth'])
@pytest.mark.parametrize('field,value', [('initial_hp',0),('initial_max_hp',False),('choice','bad_choice')])
def test_corrupt_event_restore_is_atomic(event,field,value):
    run=start(event,gold=150)
    before=saved(run);bad=deepcopy(before)
    bad['state']['pending']['data'][field]=value
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


def test_tablet_rejects_forged_upgrade_history_and_morphic_rejects_reused_original():
    for event in ('tablet_of_truth','morphic_grove'):
        run=start(event,gold=150,card_ids=['strike','defend'])
        run.apply(option(run,'decipher_1' if event=='tablet_of_truth' else 'group'))
        before=saved(run);bad=deepcopy(before);data=bad['state']['pending']['data']
        if event=='tablet_of_truth':data['upgrades'][0]=[]
        else:data['results'][0]['instance_id']=data['original_ids'][0]
        with pytest.raises(ValueError):run.restore(bad)
        assert saved(run)==before


@pytest.mark.parametrize('gold,cards,allowed',[(99,2,False),(100,1,False),(100,2,True),(200,10,True)])
def test_morphic_native_entry_conditions(gold,cards,allowed):
    run=RunEngine(gold=gold,card_ids=['strike']*cards)
    assert EVENTS['morphic_grove'].is_allowed(entry_conditions(run.state)) is allowed
    p=EventProgression(['morphic_grove','tablet_of_truth'])
    result=p.pull('node',conditions=entry_conditions(run.state))
    assert result==('morphic_grove' if allowed else 'tablet_of_truth')
    assert p.cursor==(1 if allowed else 2)


def test_native_fallback_can_repeat_or_select_ineligible_after_full_pass():
    p=EventProgression(['morphic_grove'])
    conditions={'gold':0,'transformable_cards':0}
    assert p.pull('a',conditions=conditions)=='morphic_grove'
    assert p.cursor==2
    assert p.pull('b',conditions=conditions)=='morphic_grove'
    assert p.cursor==4
    conditions['gold']=999
    assert p.entry_conditions['a']['gold']==0


@pytest.mark.parametrize('seed,path',[(0,'left'),(2,'right'),(4,'left'),(7,'right')])
def test_generated_expanded_event_pool_completes_and_restores(seed,path):
    run=RunEngine.ironclad_act1(seed=seed)
    assert len(run.state.config.event_pool) == 21
    assert set(run.state.config.event_pool) < set(EVENTS)
    for _ in range(500):
        if run.state.phase is RunPhase.ACT_COMPLETE:break
        if run.state.phase is RunPhase.COMBAT:
            # Explicit synthetic fight outcome for progression coverage.
            for _ in range(10):
                for enemy in tuple(run.combat.enemies):
                    if enemy.is_alive:enemy.take_damage(10000,is_attack=False)
            run.combat.resolve_external_effect();run.finish_combat()
        else:step(run,choose_demo_action(run,rest_choice='rest',path=path))
    assert run.state.phase is RunPhase.ACT_COMPLETE
    before=saved(run)
    p=run.state.event_progression
    assert set(p.entry_conditions)==set(p.assignments)
    if p.entry_conditions:
        bad=deepcopy(before)
        first=next(iter(p.entry_conditions))
        bad['state']['event_progression']['entry_conditions'][first]['gold']=-1
        with pytest.raises(ValueError):run.restore(bad)
        assert saved(run)==before


def test_morphic_restore_rejects_transform_into_its_original_definition():
    run=start('morphic_grove',gold=150,card_ids=['pommel_strike','defend'])
    run.apply(option(run,'group'))
    before=saved(run);bad=deepcopy(before)
    bad['state']['deck'][0]['definition_id']='pommel_strike'
    bad['state']['pending']['data']['results'][0]['definition_id']='pommel_strike'
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before
