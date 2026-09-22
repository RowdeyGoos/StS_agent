"""Composed native combat end hooks, cancellation and room reward generation."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard
from game.headless.core.native_rng import single
from game.headless.core.native_service import NativeRandomService
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.monsters.phrog_parasite import PhrogParasite
from game.headless.potions.pools import ORDINARY_POTIONS
from game.headless.powers.ironclad import apply_power
from game.headless.relics.base import RelicInstance
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase

RECORD=json.loads((Path(__file__).parents[2]/'docs/evidence/native_end_boundary_2026_09_20.json').read_text())


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other=RunEngine()
    other.restore(saved(run))
    assert saved(other)==saved(run)
    return other


def prepare(row):
    run=RunEngine(seed=int(row['seed']), rng_profile='native', hp=row['hpBefore'],
                  config=RunConfig(reward_potions=ORDINARY_POTIONS),
                  card_ids=['guilty']+(['strike','defend','bash'] if row['loadout']=='fishing' else []))
    # Explicit fixture setup mirrors native authored inventory, not pickups.
    run.state.deck[0].combats_seen=4
    names=['the_abacus','gremlin_horn','burning_blood','meat_on_the_bone','pumpkin_candle']
    if row['loadout']=='wax_after':names+=['toy_box']
    if row['loadout'] in ('cheese','wax_before','wax_after'):names+=['chosen_cheese']
    if row['loadout']=='wax_before':names+=['toy_box']
    if row['loadout']=='fishing':names+=['fishing_rod']
    run.state.relics=[RelicInstance(n,f'run.item.{i}',counter=2 if n in ('pumpkin_candle','toy_box','fishing_rod') else 0,
                         data={'_wax':True} if n=='chosen_cheese' and row['loadout'].startswith('wax_') else {})
                      for i,n in enumerate(names)]
    run.state.next_item_id=len(names)
    # Construction and combat share the owned native streams.
    run.state.rng=NativeRandomService(int(row['seed']))
    niche=run.state.rng.stream('niche')
    combat=run.start_combat(
        encounter_factory=lambda ai:[PhrogParasite(MonsterConstruction(ai,niche))],
        cards_per_turn=0)
    combat.player.deck.niche_rng.setstate(niche.getstate())
    p=combat.player
    p.deck.exhaust_pile=p.deck.draw_pile
    p.deck.draw_pile=[]
    for name in ['defend']*3+['sword_boomerang']:
        card=DEFAULT_CARDS.create(name)
        p.deck._ensure_identity(card)
        (p.hand if name=='sword_boomerang' else p.deck.discard_pile).append(card)
    p.energy=1
    p.block=7
    p.deck.rng.setstate(NativeRandomService(int(row['seed'])).stream('shuffle').getstate())
    p.strength=100
    apply_power(p,'duplication',1)
    if row['scenario']!='victory':apply_power(p,'stratagem',1)
    combat.enemies[0].hp=1
    return run


def play_to_boundary(run,scenario):
    p=run.combat.player
    if scenario=='defeat':
        # Native uses CreatureCmd.Kill; this is an explicit lethal external effect.
        p.hp=0
        run.combat.resolve_external_effect()
    else:
        card=next(c for c in p.hand if c.definition.definition_id=='sword_boomerang')
        run.combat.apply(PlayCard(card.instance_id))
    assert run.combat.done
    assert not p.rules.tasks and not p.rules.deferred_hooks and not p.rules.selection
    terminal=clone(run)
    run.finish_combat()
    terminal.finish_combat()
    assert saved(terminal)==saved(run)


@pytest.mark.parametrize('row',RECORD['result']['rows'],ids=lambda r:f'{r["seed"]}-{r["scenario"]}-{r["loadout"]}-{r["hpBefore"]}')
def test_native_end_hooks_and_room_rewards(row):
    run=prepare(row)
    other=clone(run)
    for engine in (run,other):play_to_boundary(engine,row['scenario'])
    assert saved(other)==saved(run)
    state=run.state
    assert (state.hp,state.max_hp)==(row['hpAfter'],row['maxHp'])
    relics={r.definition_id:r for r in state.relics}
    assert relics['pumpkin_candle'].counter==row['candle']
    if 'toy_box' in relics:
        assert relics['toy_box'].counter==row['toyCounter']
        assert bool(relics['chosen_cheese'].data.get('_melted'))==row['cheeseMelted']
    if 'fishing_rod' in relics:assert relics['fishing_rod'].counter==row['rodCounter']%3
    names={'strike':'STRIKE_IRONCLAD','defend':'DEFEND_IRONCLAD'}
    assert [dict(id=names.get(c.definition.definition_id,c.definition.definition_id.upper()),upgrade=c.upgrade_level) for c in state.deck]==row['deck']
    if row['scenario']=='defeat':
        assert state.phase is RunPhase.DEFEAT and state.pending is None
        assert state.deck[0].combats_seen==row['guiltyCount']==4
    else:
        assert state.phase is RunPhase.REWARD
        reward=state.pending
        native={r['kind']:r['value'] for r in row['rewards']}
        assert reward['gold']==native['gold']
        assert reward['potion']==(native['potion'].lower() if 'potion' in native else None)
        assert [dict(id=n.upper(),upgrade=m.get('upgrade_level',0)) for n,m in zip(reward['offers'],reward['card_modifiers'])]==native['cards']
    assert state.generation_odds==dict(card_offset=single(row['cardOdds']),potion_chance=single(row['potionOdds']))
    for stream,prefix in [('rewards','rewards'),('niche','niche')]:
        rng=state.rng.stream(stream)
        assert rng.counter==row[prefix+'Counter']
        assert deepcopy(rng).next_double()==row[prefix+'Suffix']
    clone(run)
    before=saved(run)
    with pytest.raises(ValueError):run.finish_combat()
    assert saved(run)==before


def test_native_fixture_exercises_real_end_cleanup_and_loss_dispatch():
    rows=RECORD['result']['rows']
    assert len(rows)==180
    for row in rows:
        win=row['scenario']!='defeat'
        assert row['events']==(['won','ended'] if win else ['ended'])
        assert row['preFinished']==win and not row['inProgress']
        assert row['pendingBefore']==int(row['scenario']=='pending')
        assert row['pendingAfter']==row['pendingBefore']  # Native hook registry retains canceled references.
        assert row['hookStates']==(['Canceled'] if row['scenario']=='pending' else [])
        assert row['powers']==0
        if not win:assert row['rewards']==[]
        if win:
            assert row['block']==0 and row['pileCards']==0
            assert row['guiltyCount']==5
        assert row['mockSaveCalls']==(2 if win else 1)


def test_previous_run_semantics_rejected_atomically():
    run=prepare(RECORD['result']['rows'][0])
    before=saved(run)
    old=deepcopy(before)
    old['schema']='headless_run_state_v51'
    with pytest.raises(ValueError):run.restore(old)
    assert saved(run)==before


@pytest.mark.parametrize('seed',['0','2','42'])
def test_reward_claims_and_room_exit_continue_from_json(seed):
    # Headless command continuation, distinct from native reward generation.
    from game.headless.run.actions import ClaimGold, ChooseRewardCard, LeaveRewards
    row=next(r for r in RECORD['result']['rows'] if r['seed']==seed and r['scenario']=='pending')
    run=prepare(row)
    play_to_boundary(run,row['scenario'])
    reward=deepcopy(run.state.pending)
    rng=run.state.rng.snapshot()
    for action in (ClaimGold(),ChooseRewardCard(reward['offers'][0]),LeaveRewards()):
        other=clone(run)
        run.apply(action)
        other.apply(action)
        assert saved(run)==saved(other)
    assert run.state.phase is RunPhase.ROUTE and run.state.pending is None
    assert run.state.gold==reward['gold']
    assert run.state.deck[-1].definition.definition_id==reward['offers'][0]
    assert run.state.rng.snapshot()==rng


@pytest.mark.parametrize('won',[False,True])
def test_melted_sword_does_not_evolve_during_fresh_victory_pass(won):
    from game.headless.run.lifecycle import after_combat
    run=RunEngine(card_ids=['strike'])
    run.state.relics=[RelicInstance('sword_of_stone','run.item.0',4,{'_wax':True}),
                      RelicInstance('toy_box','run.item.1',2)]
    run.state.next_item_id=2
    after_combat(run.state,won=won,elite=True,cards=run.cards)
    assert run.state.relics[0].definition_id=='sword_of_stone'
    assert run.state.relics[0].counter==4
    assert bool(run.state.relics[0].data.get('_melted'))==won


def test_toy_box_melted_healing_relic_is_excluded_from_victory_pass():
    from game.headless.run.lifecycle import after_combat
    run=RunEngine(hp=30)
    run.state.relics=[RelicInstance('burning_blood','run.item.0',0,{'_wax':True}),
                      RelicInstance('toy_box','run.item.1',2)]
    after_combat(run.state,won=True,elite=False,cards=run.cards)
    assert run.state.hp==30


def test_already_captured_pumpkin_callback_runs_after_toy_box_melts_it():
    from game.headless.run.lifecycle import after_combat
    run=RunEngine()
    run.state.relics=[RelicInstance('toy_box','run.item.0',2),
                      RelicInstance('pumpkin_candle','run.item.1',2,{'_wax':True})]
    after_combat(run.state,won=True,elite=False,cards=run.cards)
    assert run.state.relics[1].counter==1
    assert run.state.relics[1].data['_melted']
