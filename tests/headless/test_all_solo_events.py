"""Pinned all-act solo events: commands, continuations and content effects."""
from copy import deepcopy
import json
import pytest
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run import events
from game.headless.run.actions import ChooseEventOption, ChooseEventCard, LeaveEvent, LeaveRewards
from game.headless.run.state import RunPhase
from game.headless.run.inventory import add_potion, add_relic
from game.headless.events.roster import DEFINITIONS


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def restored(run):
    clone=RunEngine();clone.restore(saved(run))
    assert clone.legal_actions()==run.legal_actions()
    return clone


def step(run,action):
    clone=restored(run)
    run.apply(action);clone.apply(action)
    assert saved(run)==saved(clone)
    restored(run)


def choose(run,option):
    step(run,ChooseEventOption(run.state.pending['event_instance_id'],option))


def start(name,**kwargs):
    run=RunEngine(config=RunConfig(),gold=1000,**kwargs)
    run.state.act_index=1
    add_potion(run.state,'foul_potion')
    events.begin(run.state,name,cards=run.cards)
    return run


def win(run):
    for enemy in tuple(run.combat.enemies):
        enemy.take_damage(10000,is_attack=False)
    run.combat.resolve_external_effect()
    run.finish_combat()


def finish(run):
    for _ in range(80):
        restored(run)
        if run.state.phase in (RunPhase.DEFEAT,RunPhase.VICTORY,RunPhase.ROUTE): return
        if run.combat:
            clone=restored(run);win(run);win(clone);assert saved(run)==saved(clone)
            continue
        actions=run.legal_actions()
        if any(isinstance(a,LeaveEvent) for a in actions):
            step(run,next(a for a in actions if isinstance(a,LeaveEvent)));return
        if any(isinstance(a,LeaveRewards) for a in actions):
            step(run,LeaveRewards());continue
        from game.headless.run.actions import ConfirmRelicSelection, ChooseRelicCard
        confirmations=[a for a in actions if isinstance(a,ConfirmRelicSelection)]
        if confirmations:
            step(run,confirmations[0]);continue
        if run.state.relic_work and run.state.relic_work[0]['kind']=='select':
            selected=run.state.relic_work[0]['selected']
            actions=tuple(a for a in actions if not isinstance(a,ChooseRelicCard) or a.instance_id not in selected)
        names=('exit_baths','extract_instead','leave','accept','proceed','skip')
        preferred=[a for a in actions if isinstance(a,ChooseEventOption) and a.option_id in names]
        step(run,(preferred or list(actions))[0])
    pytest.fail('Event failed to reach a terminal page within 80 commands.')


@pytest.mark.parametrize('name',[d.definition_id for d in DEFINITIONS])
@pytest.mark.parametrize('profile',['fixture','native'])
def test_every_initial_branch_round_trips_and_finishes(name,profile):
    run=start(name,seed=7,rng_profile=profile)
    for action in list(events.legal_actions(run.state)):
        trial=restored(run)
        step(trial,action)
        finish(trial)


@pytest.mark.parametrize("setting", [1, 2, 3])
def test_dummy_three_turn_timeout_is_not_a_kill_reward(setting):
    from game.headless.core.actions import EndTurn
    run=start('battleworn_dummy')
    choose(run,f'setting_{setting}')
    for _ in range(3): step(run,EndTurn())
    assert run.combat is None and run.state.event_combats[-1].timed_out
    before=list(run.state.relics)
    assert run.state.pending['stage']=='resolved'
    assert run.state.relics==before


@pytest.mark.parametrize('name,option',[('doll_room','take_some_time'),('abyssal_baths','immerse')])
def test_lethal_page_transition_restores_terminal(name,option):
    run=start(name,hp=1)
    choose(run,option)
    assert run.state.phase is RunPhase.DEFEAT and not run.legal_actions()


def test_failed_event_combat_is_atomic(monkeypatch):
    run=start('battleworn_dummy');before=saved(run)
    def fail(**kwargs): raise ValueError('injected construction failure')
    monkeypatch.setattr(run,'_prepare_combat',fail)
    with pytest.raises(ValueError):run.apply(ChooseEventOption(0,'setting_1'))
    assert saved(run)==before


@pytest.mark.parametrize('name',['ranwid_the_elder','stone_of_all_time'])
def test_trade_locks_potion_inventory(name):
    from game.headless.run.actions import UsePotion,DiscardPotion
    run=start(name)
    assert not any(isinstance(a,(UsePotion,DiscardPotion)) for a in run.legal_actions())


def test_mad_science_deck_card_keeps_configuration_through_bing_bong():
    from game.headless.events.operations import execute
    run=RunEngine()
    add_relic(run.state,'bing_bong')
    execute(run.state,run.cards,('mad_science','power','improvement'))
    assert [c.event_data for c in run.state.deck[-2:]]==[{'kind':'power','rider':'improvement'}]*2
    restored(run)


def test_complete_solo_event_census_including_neow():
    from pathlib import Path
    from game.headless.events.catalog import EVENTS
    census=json.loads((Path(__file__).parents[1]/'fixtures/headless_solo_event_scope.json').read_text())
    assert len(census['solo_events'])==66
    assert set(EVENTS)|{'neow'}==set(census['solo_events'])


def test_event_combat_continuation_cannot_be_changed_or_dropped():
    run=start('battleworn_dummy');choose(run,'setting_2');before=saved(run)
    for value in (None,{},dict(run.state.event_combats[-1].continuation,definition_id='punch_off')):
        bad=deepcopy(before);bad['state']['event_combats'][-1]['continuation']=value
        with pytest.raises(ValueError):run.restore(bad)
        assert saved(run)==before


def test_crystal_sphere_rejects_cleared_cells_without_spending_a_turn():
    run=start('crystal_sphere');choose(run,'payment_plan')
    options={a.option_id for a in run.legal_actions() if isinstance(a,ChooseEventOption)}
    assert 'big_0_0' not in options and 'small_0_0' not in options
    before=saved(run)
    with pytest.raises(ValueError):run.apply(ChooseEventOption(0,'big_0_0'))
    assert saved(run)==before
    choose(run,'big_5_5')
    assert run.state.pending['data']['pages'][-1]['context']['remaining']==5
    assert ChooseEventOption(0,'small_5_5') not in run.legal_actions()


def test_custom_rewards_generate_before_claims_and_survive_reward_alternatives():
    from game.headless.events.reward_batch import prepare
    from game.headless.run.actions import RerollCardReward,SacrificeCardReward
    run=RunEngine(rng_profile='native');add_relic(run.state,'driftwood');add_relic(run.state,'paels_wing')
    events.begin(run.state,'colorful_philosophers')
    choose(run,run.state.pending['data']['options'][0])
    assert len(run.state.pending['data']['active']['rewards'])==3
    rng=run.state.rng.snapshot();choose(run,'skip_2');assert run.state.rng.snapshot()==rng
    step(run,RerollCardReward(0));step(run,SacrificeCardReward(1))
    assert run.state.pending['data']['active']['rewards'][0]['rerolled']
    choose(run,'skip_0');finish(run)


def test_lantern_key_overrides_unknown_room_and_event_queue_in_act_three():
    from game.headless.map.graph import MapGraph,MapNode
    from game.headless.run.unknown_rooms import UnknownRooms,prepare_unknown
    from game.headless.events.progression import EventProgression
    from game.headless.run.deck import add_card
    run=RunEngine(config=RunConfig());run.state.act_index=2
    add_card(run.state,run.cards.definition('lantern_key'))
    graph=MapGraph((MapNode('q','unknown',()),),'q')
    run.state.unknown_rooms=UnknownRooms();run.state.event_progression=EventProgression.generate(run.state.rng,run.state.config.event_pool)
    rng,unknown,progression,node=prepare_unknown(run.state,graph,graph.node('q'))
    assert node.kind=='event' and node.event_id=='war_historian_repy'
    assert unknown.outcomes['q'].forced_by==run.state.deck[-1].instance_id
    assert progression.assignments['q']=='war_historian_repy'


def test_completed_dummy_cannot_restore_an_unconsumed_continuation():
    run=start('battleworn_dummy');choose(run,'setting_2');win(run);finish(run)
    before=saved(run);bad=deepcopy(before);bad['state']['event_combats'][-1]['resumed']=False
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


def test_last_batch_reward_can_suspend_for_a_relic_pickup(monkeypatch):
    from game.headless.events import operations
    from game.headless.run.actions import ChooseRelicCard
    from itertools import cycle
    pulls=cycle(('anchor','dollys_mirror'))
    monkeypatch.setattr(operations,'pull_relic',lambda *a,**kw:next(pulls))
    run=start('war_historian_repy');choose(run,'unlock_chest')
    choose(run,'skip_0');choose(run,'skip_1');choose(run,'skip_2')
    choose(run,'reward_3_0')
    assert run.state.pending['stage']=='relic_work'
    assert any(isinstance(a,ChooseRelicCard) for a in run.legal_actions())
    finish(run)


def test_zen_weaver_fallback_clamps_gold_loss():
    run = RunEngine(gold=12)
    events.begin(run.state, 'zen_weaver', cards=run.cards)
    choose(run, 'breathing_techniques')
    assert run.state.gold == 0
    assert [c.definition.definition_id for c in run.state.deck[-2:]] == ['enlightenment'] * 2


def test_crystal_retry_retains_items_and_native_reveal_subscriptions(monkeypatch):
    from game.headless.events import minigames
    from game.headless.core.rng import GameRandomService
    monkeypatch.setattr(minigames, 'ITEMS', (('gold_small', 1, 1), ('relic', 20, 20)))
    board = minigames.crystal_board(GameRandomService(7))
    assert len(board['items']) == 20
    assert not board['items'][1]['cells']
    x, y = board['items'][0]['cells'][0]
    result, revealed = minigames.cleared({'board': board}, f'small_{x}_{y}')
    assert result['revealed'] == [0] * 10
    assert revealed == ['gold_small']
