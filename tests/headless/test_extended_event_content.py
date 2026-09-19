"""Observable rules for event-only cards, relics and reward interactions."""
from copy import deepcopy
import json
import pytest
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.cards.extended_events import DEFINITIONS, RIDERS
from game.headless.relics.event_content import NAMES
from game.headless.core.actions import PlayCard, EndTurn, ChooseCombatCard, ConfirmCombatSelection
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.actions import ChooseExtraReward, LeaveRewards, ChooseEventOption
from game.headless.run.inventory import add_relic
from game.headless.run import events
from game.headless.monsters.overgrowth import SimpleEnemy


def snapshot(run): return json.loads(json.dumps(run.snapshot()))


def restore(run):
    result=RunEngine();result.restore(snapshot(run));assert result.legal_actions()==run.legal_actions()
    return result


def apply(run,action):
    clone=restore(run);run.apply(action);clone.apply(action)
    assert snapshot(run)==snapshot(clone);restore(run)


def setup(names=('strike','bash','defend'),relics=(),*,upgraded=False,event_data=None):
    run=RunEngine(card_ids=names,config=RunConfig(),hp=70)
    for card in run.state.deck:
        if upgraded and len(card.definition.levels)>1: card.upgrade()
        if card.definition.definition_id=='mad_science': card.event_data=deepcopy(event_data or {'kind':'attack','rider':'sapping'})
    for name in relics: add_relic(run.state,name)
    run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000),cards_per_turn=10,energy_per_turn=20)
    restore(run)
    return run


def play(run,name):
    c=next(c for c in run.combat.player.hand if c.definition.definition_id==name)
    apply(run,PlayCard(c.instance_id,0 if c.spec.uses_target else None))
    return c


def settle(run):
    for _ in range(10):
        if not run.combat.player.rules.selection:return
        actions=run.legal_actions();confirm=ConfirmCombatSelection()
        apply(run,confirm if confirm in actions else actions[0])
    pytest.fail('Unresolved selection.')


@pytest.mark.parametrize('name',[d.definition_id for d in DEFINITIONS if d.definition_id!='lantern_key'])
@pytest.mark.parametrize('upgraded',[False,True])
def test_every_event_card_plays_restores_and_advances_turn(name,upgraded):
    names=(name,'strike','bash') if name=='clash' else (name,'strike','bash','defend')
    run=setup(names,upgraded=upgraded)
    play(run,name);settle(run);apply(run,EndTurn());settle(run)


@pytest.mark.parametrize('kind,rider',[(kind,rider) for kind,options in RIDERS.items() for rider in options])
def test_mad_science_riders_have_owned_persistent_configuration(kind,rider):
    run=setup(('mad_science','strike','defend'),event_data={'kind':kind,'rider':rider})
    p=run.combat.player;enemy=run.combat.enemies[0]
    play(run,'mad_science')
    if kind=='attack':
        assert enemy.hp==1000-(36 if rider=='violence' else 12)
        if rider=='sapping': assert enemy.statuses.get('weak')==enemy.statuses.get('vulnerable')==2
    elif kind=='skill':
        assert p.block==8
        if rider=='energized': assert p.energy==21
    else:
        assert p.rules.powers.get(rider,0)==1 if rider!='expertise' else p.strength==2 and p.rules.powers['dexterity']==2
    apply(run,EndTurn())


def test_history_course_replay_disappears_and_does_not_replay_itself():
    run=setup(relics=('history_course',));p=run.combat.player
    count=len(p.deck.all_cards());play(run,'strike');hp=run.combat.enemies[0].hp
    apply(run,EndTurn())
    assert run.combat.enemies[0].hp==hp-6
    assert len(p.deck.all_cards())==count
    assert not any(c.combat_state.is_dupe for c in p.deck.all_cards())
    hp=run.combat.enemies[0].hp;apply(run,EndTurn())
    assert run.combat.enemies[0].hp==hp


def test_big_mushroom_max_hp_and_first_draw_penalty():
    run=RunEngine(config=RunConfig());add_relic(run.state,'big_mushroom')
    assert run.state.max_hp==100 and run.state.hp==100
    run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000))
    assert len(run.combat.player.hand)==3
    apply(run,EndTurn());assert len(run.combat.player.hand)==5


def test_the_boot_and_hand_drill_only_after_block_is_broken():
    run=setup(('exterminate',),relics=('the_boot','hand_drill'))
    enemy=run.combat.enemies[0];enemy.block=4
    play(run,'exterminate')
    assert enemy.block==0 and enemy.statuses.get('vulnerable')==2
    assert enemy.hp==985


def test_bing_bong_copies_reward_enchantment_and_reflections_do_not_reclone():
    from game.headless.run.rewards import acquire_card
    from game.headless.enchantments.base import enchant,record
    from game.headless.events.operations import execute
    run=RunEngine();add_relic(run.state,'bing_bong')
    card=DEFAULT_CARDS.create('strike');enchant(card,'vigorous',8)
    acquire_card(run.state,run.cards,'strike',{'strike':{'upgrade_level':0,'enchantment':record(card)}})
    assert run.state.deck[-1].enchantment==run.state.deck[-2].enchantment
    count=len(run.state.deck);execute(run.state,run.cards,('clone_deck',))
    assert len(run.state.deck)==2*count
    restore(run)


def test_event_combat_extra_rewards_can_be_claimed_before_normal_rewards():
    run=RunEngine(config=RunConfig());events.begin(run.state,'the_lantern_key')
    apply(run,ChooseEventOption(0,'keep_the_key'));apply(run,ChooseEventOption(0,'fight'))
    for enemy in run.combat.enemies:enemy.take_damage(10000,is_attack=False)
    run.combat.resolve_external_effect();run.finish_combat();restore(run)
    apply(run,ChooseExtraReward(0,'lantern_key'))
    assert run.state.deck[-1].definition.definition_id=='lantern_key'
    apply(run,LeaveRewards());assert run.state.pending is None
    # A subsequent ordinary combat cannot resume the old event a second time.
    run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1))
    run.combat.enemies[0].take_damage(5,is_attack=False)
    run.combat.resolve_external_effect();run.finish_combat();apply(run,LeaveRewards())
    assert run.state.pending is None


def test_knight_plating_decrements_by_turn_not_by_hit():
    from game.headless.monsters.event_monsters import MysteriousKnight
    from random import Random
    enemy=MysteriousKnight(Random(1));assert enemy.block==enemy.plating==6
    enemy.take_damage(10);assert enemy.plating==6
    enemy.start_turn();assert enemy.plating==6
    enemy.start_turn();assert enemy.plating==5


def test_tome_card_is_bound_on_offer_without_reroll_on_claim():
    for seed in range(20):
        run=RunEngine(seed=seed,rng_profile='native');events.begin(run.state,'darv')
        c=run.state.pending['data']['pages'][0]['context']
        if 'dusty_tome' in c['options']:break
    before=run.state.rng.request_count('rewards');apply(run,ChooseEventOption(0,'dusty_tome'))
    assert run.state.rng.request_count('rewards')==before
    assert run.state.deck[-1].definition.definition_id==c['tome_card'] and run.state.deck[-1].upgraded


@pytest.mark.parametrize('name',NAMES)
def test_every_event_relic_pickup_combat_and_turn_hooks_restore(name):
    run=setup(relics=(name,))
    play(run,'strike');apply(run,EndTurn())


def test_dream_catcher_adds_a_resumable_real_rest_site_card_reward():
    from game.headless.run import rest_site
    from game.headless.run.actions import Rest,ChooseRelicReward,LeaveRest
    run=RunEngine(config=RunConfig(),hp=40,rng_profile='native');add_relic(run.state,'dream_catcher')
    rest_site.begin_rest_site(run.state);apply(run,Rest())
    assert run.state.relic_work[0]['kind']=='card_reward'
    assert len(run.state.relic_work[0]['offers'])==3
    apply(run,ChooseRelicReward(0));apply(run,LeaveRest())


def test_hand_drill_applies_before_lethal_hit_cleanup():
    run = setup(relics=('hand_drill',))
    enemy = run.combat.enemies[0]
    enemy.hp = 1
    enemy.block = 1
    enemy.apply_status('artifact', 1)
    enemy.take_damage(2, attacker_statuses=run.combat.player.statuses)
    assert enemy.hp == 0
    assert enemy.statuses.get('artifact') == 0
