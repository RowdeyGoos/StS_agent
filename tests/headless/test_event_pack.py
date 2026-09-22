"""Four events, reward inventories and persistent card/relic progression."""
from copy import deepcopy
import json

import pytest

from game.cli.headless_play import choose_demo_action
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.events.catalog import EVENTS
from game.headless.events.progression import EventProgression
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run import events
from game.headless.run.actions import ChooseEventOption, ChooseEventCard, LeaveEvent, DiscardPotion, UsePotion, LeaveRewards
from game.headless.run.deck import add_card
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion, add_relic, remove_relic
from game.headless.run.state import RunPhase


def saved(run):return json.loads(json.dumps(run.snapshot(),sort_keys=True))


def step(run, action):
    clone=RunEngine();clone.restore(saved(run))
    assert clone.legal_actions()==run.legal_actions()
    clone.apply(action);run.apply(action)
    assert saved(clone)==saved(run)


def start(name,**kwargs):
    run=RunEngine(**kwargs);events.begin(run.state,name);return run


def opt(run,name):return ChooseEventOption(run.state.pending['event_instance_id'],name)


def finish(run):step(run,LeaveEvent(run.state.pending['event_instance_id']))


def win(run):
    for _ in range(10):
        for enemy in tuple(run.combat.enemies):
            if enemy.is_alive:enemy.take_damage(10000,is_attack=False)
    run.combat.resolve_external_effect();run.finish_combat()


@pytest.mark.parametrize('event,choice,count',[('whispering_hollow','gold',2),('wellspring','bottle',1)])
def test_potion_bundle_full_inventory_claim_discard_skip_and_restore(event,choice,count):
    run=RunEngine(gold=150)
    for _ in range(3):add_potion(run.state,'fire_potion')
    events.begin(run.state,event)
    step(run,opt(run,choice))
    before=saved(run)
    assert not any(isinstance(a,ChooseEventOption) and a.option_id.startswith('claim_potion_') for a in run.legal_actions())
    with pytest.raises(ValueError):run.apply(opt(run,'claim_potion_0'))
    assert saved(run)==before
    step(run,DiscardPotion(run.state.potions[0].instance_id))
    step(run,opt(run,'claim_potion_0'))
    claimed=run.state.pending['data']['rewards'][0]['claimed_id']
    assert any(p and p.instance_id==claimed for p in run.state.potions)
    step(run,DiscardPotion(claimed))
    assert opt(run,'claim_potion_0') not in run.legal_actions()
    assert len(run.state.pending['data']['rewards'])==count
    step(run,opt(run,'finish_rewards'));finish(run)


def test_whisper_price_is_fixed_and_payment_happens_once():
    prices=set()
    for seed in range(60):
        run=start('whispering_hollow',seed=seed,gold=44)
        price=run.state.pending['data']['price'];prices.add(price)
        before=run.state.rng.snapshot()
        run.legal_actions();assert run.state.rng.snapshot()==before
        step(run,opt(run,'gold'))
        assert run.state.gold==44-price
        assert run.state.rng.request_count('rewards')==4
        assert run.state.rng.request_count('event.potions')==0
    assert min(prices)>=26 and max(prices)<=44 and len(prices)>10


@pytest.mark.parametrize('hp,count',[(20,3),(9,3),(1,1),(20,0)])
def test_hug_transforms_before_damage_and_handles_empty_or_lethal_choice(hp,count):
    run=start('whispering_hollow',hp=hp,card_ids=['strike']*count)
    original=[c.instance_id for c in run.state.deck]
    step(run,opt(run,'hug'))
    if count>1:step(run,ChooseEventCard(0,original[1]))
    assert run.state.hp==max(0,hp-9)
    assert len(run.state.deck)==count
    assert len(set(c.instance_id for c in run.state.deck)-set(original))==(1 if count else 0)
    assert run.state.phase is (RunPhase.DEFEAT if hp<=9 else RunPhase.ROOM)
    if hp<=9:assert not run.legal_actions()


@pytest.mark.parametrize('count',range(4))
def test_bathe_removes_one_then_grants_fresh_guilty(count):
    run=start('wellspring',card_ids=['strike']*count)
    original=[c.instance_id for c in run.state.deck]
    step(run,opt(run,'bathe'))
    if count>1:step(run,ChooseEventCard(0,original[-1]))
    assert len(run.state.deck)==max(0,count-1)+1
    guilty=run.state.deck[-1]
    assert guilty.definition.definition_id=='guilty' and guilty.instance_id not in original
    assert guilty.combats_seen==0
    assert sum(c.instance_id in original for c in run.state.deck)==max(0,count-1)
    finish(run)


def test_guilty_is_unplayable_not_ethereal_and_expires_after_five_completed_fights():
    run=start('wellspring',card_ids=['strike'])
    run.apply(opt(run,'bathe'));finish(run)
    identity=run.state.deck[0].instance_id
    for count in range(1,6):
        run.start_combat(encounter_id='overgrowth_nibbit')
        assert not any(isinstance(a,PlayCard) and a.instance_id==identity for a in run.legal_actions())
        if count==1:
            step(run,EndTurn())
            assert not run.combat.player.deck.exhaust_pile
            assert any(c.instance_id==identity for c in run.combat.player.hand)
        clone=RunEngine();clone.restore(saved(run));win(run);win(clone)
        assert saved(run)==saved(clone)
        if count<5:assert run.state.deck[0].combats_seen==count
        else:assert run.state.deck==[]


@pytest.mark.parametrize('event,option_id',[('aroma_of_chaos','let_go'),('morphic_grove','group'),('whispering_hollow','hug')])
def test_curse_transform_uses_curse_pool_and_resets_lifetime(event,option_id):
    run=start(event,card_ids=['guilty'],gold=150)
    run.state.deck[0].combats_seen=3
    step(run,opt(run,option_id))
    from game.headless.cards.curses import ALL_CURSES
    assert run.state.deck[0].definition.definition_id in set(ALL_CURSES)-{'guilty'}
    assert run.state.deck[0].combats_seen==0
    assert run.state.deck[0].spec.kind=='curse'


def test_bridge_prefers_nonbasic_then_excludes_previous_definition_and_skipped_cards():
    run=start('slippery_bridge',card_ids=['strike','strike','bash','pommel_strike','pommel_strike','shrug_it_off'])
    data=run.state.pending['data'];definitions={c.instance_id:c.definition.definition_id for c in run.state.deck}
    assert definitions[data['offers'][0]] not in ('strike','bash')
    for count in range(3):
        previous=data['offers'][-1]
        step(run,opt(run,f'hold_on_{count}'))
        data=run.state.pending['data']
        assert definitions[data['offers'][-1]]!=definitions[previous]
        assert data['offers'][-1] not in data['offers'][:-1]
    selected=data['offers'][-1]
    step(run,opt(run,'overcome_3'))
    assert all(c.instance_id!=selected for c in run.state.deck)
    assert run.state.hp==80-3-4-5
    finish(run)


def test_bridge_repeated_single_card_fallback_and_lethal_hold_restore():
    run=start('slippery_bridge',card_ids=['strike'],hp=7)
    step(run,opt(run,'hold_on_0'))
    assert run.state.hp==4
    step(run,opt(run,'hold_on_1'))
    assert run.state.phase is RunPhase.DEFEAT and run.state.hp==0
    assert len(run.state.pending['data']['offers'])==3
    assert not run.legal_actions()


def test_bridge_past_loop_page_retains_distinct_decisions():
    run=start('slippery_bridge',card_ids=['strike'],max_hp=200)
    for i in range(9):step(run,opt(run,f'hold_on_{i}'))
    assert run.state.hp==200-sum(range(3,12))
    assert opt(run,'hold_on_9') in run.legal_actions()
    step(run,opt(run,'overcome_9'));assert run.state.deck==[]


@pytest.mark.parametrize('hp',[1,7,20])
def test_statue_grants_gold_before_damage_including_lethal(hp):
    run=start('sunken_statue',hp=hp,gold=99)
    amount=run.state.pending['data']['gold']
    assert 101<=amount<=121
    step(run,opt(run,'dive_into_water'))
    assert run.state.gold==99+amount and run.state.hp==max(0,hp-7)
    assert run.state.phase is (RunPhase.DEFEAT if hp<=7 else RunPhase.ROOM)


def test_sword_tracks_elites_only_evolves_after_five_and_adds_strength_next_fight():
    run=start('sunken_statue')
    step(run,opt(run,'grab_sword'));old_id=run.state.relics[0].instance_id;finish(run)
    # Unconfigured synthetic reward fixture supports arbitrary repeated encounters.
    from game.headless.run.config import RunConfig
    run.state.config=RunConfig(relic_fallback='circlet')
    for relic in run.state.config.reward_relics:add_relic(run.state,relic)
    run.start_combat(encounter_id='overgrowth_nibbit');win(run);run.apply(LeaveRewards())
    assert run.state.relics[0].counter==0
    for count in range(1,6):
        run.start_combat(encounter_id='overgrowth_byrdonis')
        assert run.combat.player.strength==0
        clone=RunEngine();clone.restore(saved(run));win(run);win(clone)
        assert saved(run)==saved(clone)
        run.apply(LeaveRewards())
        if count<5:assert run.state.relics[0].counter==count
    jade=run.state.relics[0]
    assert jade.definition_id=='sword_of_jade' and jade.instance_id!=old_id and jade.counter==0
    run.start_combat(encounter_id='overgrowth_nibbit')
    assert run.combat.player.strength==3
    clone=RunEngine();clone.restore(saved(run));assert clone.combat.player.strength==3


@pytest.mark.parametrize('event',['whispering_hollow','wellspring','slippery_bridge','sunken_statue'])
def test_each_new_event_rejects_malformed_or_stale_state_atomically(event):
    run=start(event,gold=150)
    before=saved(run)
    with pytest.raises(ValueError):run.apply(ChooseEventOption(999,'gold'))
    bad=deepcopy(before);bad['state']['pending']['data']['extra']=True
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


def test_claimed_potion_cannot_be_reclaimed_after_discard_or_bound_to_relic():
    run=start('wellspring');relic=add_relic(run.state,'burning_blood')
    run.apply(opt(run,'bottle'));run.apply(opt(run,'claim_potion_0'))
    before=saved(run);bad=deepcopy(before)
    bad['state']['pending']['data']['rewards'][0]['claimed_id']=relic.instance_id
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


@pytest.mark.parametrize('gold,floor,expected',[(43,6,'tablet_of_truth'),(44,6,'whispering_hollow'),(0,7,'slippery_bridge')])
def test_entry_predicates_skip_ineligible_events(gold,floor,expected):
    progression=EventProgression(['slippery_bridge','whispering_hollow','tablet_of_truth'])
    assert progression.pull('a',conditions={'gold':gold,'transformable_cards':2,'floor':floor})==expected


@pytest.mark.parametrize('seed,path',[(0,'left'),(2,'right'),(4,'left'),(7,'right'),(9,'left')])
def test_expanded_generated_routes_restore_every_decision(seed,path):
    run=RunEngine.ironclad_act1(seed=seed)
    assert len(run.state.config.event_pool)==21
    for _ in range(500):
        if run.state.phase is RunPhase.ACT_COMPLETE:break
        if run.state.phase is RunPhase.COMBAT:win(run)
        else:step(run,choose_demo_action(run,rest_choice='rest',path=path))
    assert run.state.phase is RunPhase.ACT_COMPLETE


def test_duplicate_swords_have_independent_ids_and_evolve_with_existing_jade():
    from dataclasses import replace
    from game.headless.run.lifecycle import after_combat
    run=start('sunken_statue')
    run.apply(opt(run,'grab_sword'));finish(run)
    events.begin(run.state,'sunken_statue')
    step(run,opt(run,'grab_sword'));finish(run)
    assert len({r.instance_id for r in run.state.relics})==2
    assert all(r.definition_id=='sword_of_stone' for r in run.state.relics)
    add_relic(run.state,'sword_of_jade')
    run.state.relics[0]=replace(run.state.relics[0],counter=4)
    after_combat(run.state,won=True,elite=True)
    assert [r.definition_id for r in run.state.relics]==['sword_of_jade','sword_of_stone','sword_of_jade']
    assert run.state.relics[1].counter==1
    run.restore(saved(run));run.start_combat(encounter_id='overgrowth_nibbit')
    assert run.combat.player.strength==6


@pytest.mark.parametrize('event,choice',[('aroma_of_chaos','let_go'),('morphic_grove','group')])
def test_fresh_transformed_guilty_cannot_restore_with_aged_lifetime(event,choice):
    for seed in range(20):
        run=start(event,card_ids=['clumsy'],gold=150,seed=seed)
        run.apply(opt(run,choice))
        if run.state.deck[0].definition.definition_id == 'guilty':
            break
    else:
        pytest.fail('No Guilty transform sampled.')
    before=saved(run);bad=deepcopy(before)
    assert bad['state']['deck'][0]['definition_id']=='guilty'
    bad['state']['deck'][0]['combats_seen']=4
    if event=='morphic_grove':
        assert run.state.pending['data']['results'][0]['definition_id']=='guilty'
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


@pytest.mark.parametrize('count',[True,-1,5])
def test_invalid_guilty_lifetime_restore_is_atomic(count):
    run=RunEngine(card_ids=['guilty'])
    before=saved(run);bad=deepcopy(before);bad['state']['deck'][0]['combats_seen']=count
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


def test_sword_snapshot_requires_its_progress_counter():
    run=RunEngine();add_relic(run.state,'sword_of_stone')
    before=saved(run);bad=deepcopy(before);del bad['state']['relics'][0]['counter']
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before
