"""Sapphire Seed and owned Sown state across cards, choices and combats."""
from copy import deepcopy
import json

import pytest

from game.headless.cards.base import Card,CardDefinition,CardSpec
from game.headless.core.actions import PlayCard,EndTurn,ChooseCombatCard
from game.headless.enchantments.base import enchant,can_enchant
from game.headless.run.engine import RunEngine
from game.headless.run import events
from game.headless.run.actions import ChooseEventOption,ChooseEventCard,LeaveEvent


def saved(run):return json.loads(json.dumps(run.snapshot()))
def step(run,action):
    clone=RunEngine();clone.restore(saved(run))
    assert clone.legal_actions()==run.legal_actions()
    run.apply(action);clone.apply(action);assert saved(run)==saved(clone)
def start(**kwargs):
    run=RunEngine(**kwargs);events.begin(run.state,'sapphire_seed');return run

def test_eat_heals_before_choice_then_upgrades_exact_card_and_preserves_sown():
    run=RunEngine(card_ids=['strike','defend'],hp=40)
    enchant(run.state.deck[0]);events.begin(run.state,'sapphire_seed')
    first,second=[c.instance_id for c in run.state.deck]
    step(run,ChooseEventOption(0,'eat'));assert run.state.hp==49
    assert run.legal_actions()==(ChooseEventCard(0,first),ChooseEventCard(0,second))
    before=saved(run)
    with pytest.raises(ValueError):run.apply(LeaveEvent(0))
    assert saved(run)==before
    step(run,ChooseEventCard(0,first))
    assert run.state.deck[0].upgrade_level==1 and run.state.deck[0].enchantment.definition_id=='sown'
    step(run,LeaveEvent(0))


@pytest.mark.parametrize('cards',['empty','curse','single','upgraded'])
def test_eat_empty_single_and_no_upgrade_cases_still_heal(cards):
    ids=[] if cards=='empty' else ['guilty'] if cards=='curse' else ['strike']
    run=RunEngine(card_ids=ids,hp=79)
    if cards=='upgraded':run.state.deck[0].upgrade()
    events.begin(run.state,'sapphire_seed');step(run,ChooseEventOption(0,'eat'))
    assert run.state.hp==80 and run.legal_actions()==(LeaveEvent(0),)
    if cards=='single':assert run.state.deck[0].upgrade_level==1


def test_plant_excludes_status_curse_unplayable_and_already_enchanted_cards():
    run=RunEngine(card_ids=['slimed','guilty','clumsy','strike','defend'])
    enchant(run.state.deck[-1]);events.begin(run.state,'sapphire_seed')
    identity=run.state.deck[-2].instance_id
    step(run,ChooseEventOption(0,'plant'))
    assert run.legal_actions()==(LeaveEvent(0),)
    assert run.state.deck[-2].enchantment.definition_id=='sown'
    assert run.state.deck[-2].instance_id==identity
    assert all(c.enchantment is None for c in run.state.deck[:3])
    step(run,LeaveEvent(0));events.begin(run.state,'sapphire_seed')
    step(run,ChooseEventOption(1,'plant'));assert run.legal_actions()==(LeaveEvent(1),)
    assert run.state.deck[-2].enchantment.amount==1


def test_ethereal_playable_card_can_be_enchanted_but_unplayable_skill_cannot():
    ethereal=Card(CardDefinition('temporary',(CardSpec('Temporary',1,'skill',ethereal=True),),()))
    blocked=Card(CardDefinition('blocked',(CardSpec('Blocked',-1,'skill'),),()))
    assert can_enchant(ethereal) and not can_enchant(blocked)
    enchant(ethereal)
    with pytest.raises(ValueError):enchant(blocked)


def test_plant_selection_has_no_heal_and_preserves_original_upgrade():
    run=RunEngine(card_ids=['strike','defend'],hp=40)
    run.state.deck[1].upgrade();events.begin(run.state,'sapphire_seed')
    step(run,ChooseEventOption(0,'plant'));assert run.state.hp==40
    identity=run.state.deck[1].instance_id
    step(run,ChooseEventCard(0,identity))
    assert run.state.deck[0].enchantment is None
    assert run.state.deck[1].enchantment.amount==1 and run.state.deck[1].upgrade_level==1


def test_sown_refunds_once_across_reshuffle_turns_and_resets_next_combat():
    run=RunEngine(card_ids=['strike'],max_hp=200)
    enchant(run.state.deck[0]);identity=run.state.deck[0].instance_id
    for fight in range(2):
        run.start_combat(encounter_id='overgrowth_nibbit')
        step(run,PlayCard(identity,0));assert run.combat.player.energy==3
        assert not run.state.deck[0].enchantment.triggered
        step(run,EndTurn());step(run,PlayCard(identity,0));assert run.combat.player.energy==2
        run.combat.enemies[0].take_damage(10000,is_attack=False)
        run.combat.resolve_external_effect();run.finish_combat()


def test_sown_waits_for_armaments_selection_and_fires_once_after_restore():
    run=RunEngine(card_ids=['armaments','strike','defend'])
    enchant(run.state.deck[0]);run.start_combat(encounter_id='overgrowth_nibbit')
    arm=next(c for c in run.combat.player.hand if c.definition.definition_id=='armaments')
    step(run,PlayCard(arm.instance_id))
    assert run.combat.player.energy==2 and not arm.enchantment.triggered
    assert run.combat.player.pending_play is not None
    step(run,run.legal_actions()[0]);assert run.combat.player.energy==3 and arm.enchantment.triggered
    assert not run.state.deck[0].enchantment.triggered


def test_sown_does_not_make_unaffordable_card_legal_and_failed_play_does_not_trigger():
    run=RunEngine(card_ids=['bash']);enchant(run.state.deck[0])
    run.start_combat(encounter_id='overgrowth_nibbit');run.combat.player.energy=1
    card=run.combat.player.hand[0];before=saved(run)
    with pytest.raises(ValueError):run.apply(PlayCard(card.instance_id,0))
    assert saved(run)==before and not card.enchantment.triggered


def test_terminal_enemy_kill_consumes_sown_without_energy_and_player_death_skips_it():
    from game.headless.core.combat import CombatEngine
    from game.headless.monsters.overgrowth import SimpleEnemy
    from game.headless.cards.catalog import DEFAULT_CARDS
    for name,hp,target_hp,expected_trigger in [('strike',80,1,True),('offering',1,100,False)]:
        card=DEFAULT_CARDS.create(name);enchant(card)
        combat=CombatEngine(deck_factory=lambda:[deepcopy(card)],enemy_factory=lambda:SimpleEnemy(max_hp=target_hp),player_max_hp=hp)
        combat.reset();played=combat.player.hand[0]
        combat.apply(PlayCard(played.instance_id,0 if name=='strike' else None))
        assert combat.done and played.enchantment.triggered==expected_trigger
        assert combat.player.energy==(2 if name=='strike' else 3)


@pytest.mark.parametrize('event,choice',[('aroma_of_chaos','let_go'),('morphic_grove','group'),('whispering_hollow','hug')])
def test_transform_removes_enchantment_and_cannot_restore_an_invented_replacement(event,choice):
    run=RunEngine(card_ids=['strike'],gold=150)
    enchant(run.state.deck[0]);events.begin(run.state,event)
    step(run,ChooseEventOption(0,choice))
    assert run.state.deck[0].enchantment is None
    before=saved(run);bad=deepcopy(before)
    bad['state']['deck'][0]['enchantment']={'definition_id':'sown','amount':1,'triggered':False}
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


@pytest.mark.parametrize('field,value',[('definition_id','unknown'),('amount',0),('amount',True),('triggered',1),('triggered',True)])
def test_invalid_permanent_enchantment_restore_is_atomic(field,value):
    run=RunEngine(card_ids=['strike']);enchant(run.state.deck[0])
    before=saved(run);bad=deepcopy(before);bad['state']['deck'][0]['enchantment'][field]=value
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


def test_event_result_restore_preserves_the_exact_enchantment_and_original_cards():
    run=start(card_ids=['strike','defend']);run.apply(ChooseEventOption(0,'plant'))
    run.apply(ChooseEventCard(0,run.state.deck[1].instance_id))
    before=saved(run)
    for index in (0,1):
        bad=deepcopy(before)
        bad['state']['deck'][index]['enchantment']={'definition_id':'sown','amount':2,'triggered':False}
        with pytest.raises(ValueError):run.restore(bad)
        assert saved(run)==before
