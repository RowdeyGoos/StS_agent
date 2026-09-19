"""Pinned native factories plus acquired-card play and adversarial restoration."""

import json
from copy import deepcopy
from pathlib import Path
import pytest
from game.headless.cards.catalog import DEFAULT_CARDS, IRONCLAD_CARDS, CardCatalog
from game.headless.cards.pools import REWARD_CARDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection, EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.core.native_rng import single
from game.headless.generation.foreign import ORDINARY, FAMILIES, splash_pool, complete
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.actions import ChooseRelicReward
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic

VECTORS=json.loads((Path(__file__).parents[1]/'fixtures/headless_native_foreign_vectors.json').read_text())
MODES={'plain':(), 'wing_charm':('wing_charm',), 'silver_crucible':('silver_crucible',),
    'silken_tress':('silken_tress',), 'eggs':('molten_egg','toxic_egg','frozen_egg'),
    'combined':('wing_charm','silver_crucible','silken_tress','molten_egg')}


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other=RunEngine(cards=run.cards);other.restore(saved(run));return other


def acquisition(row):
    run=RunEngine(seed=row['seed'],rng_profile='native',card_ids=[])
    for name in MODES[row['mode']]:add_relic(run.state,name,cards=run.cards)
    add_relic(run.state,'kaleidoscope',cards=run.cards)
    return run


def settle(run):
    for _ in range(100):
        p=run.combat.player
        if p.pending_play is None and p.rules.selection is None:return
        actions=run.legal_actions()
        action=ConfirmCombatSelection() if ConfirmCombatSelection() in actions else actions[0]
        other=clone(run);run.apply(action);other.apply(action)
        assert saved(run)==saved(other)
    pytest.fail('Acquired-card choice did not finish')


def test_complete_default_catalog_keeps_ordinary_rewards_ironclad():
    assert complete(DEFAULT_CARDS) and not complete(IRONCLAD_CARDS)
    assert tuple(VECTORS['families'])==FAMILIES
    assert sum(map(len,ORDINARY.values()))==320
    assert all(DEFAULT_CARDS.definition(n).pool=='ironclad' for n in REWARD_CARDS)
    assert all(DEFAULT_CARDS.definition(n).rarity in ('common','uncommon','rare') for names in ORDINARY.values() for n in names)


@pytest.mark.parametrize('row',VECTORS['rows'],ids=lambda r:r['seed']+'-'+r['mode'])
def test_kaleidoscope_matches_native_groups_modifiers_and_rng(row):
    run=acquisition(row);state=run.state
    actual=[[dict(id=o['definition_id'],pool=run.cards.definition(o['definition_id']).pool,
        upgrade=o['upgrade_level'],enchantment=None if o['enchantment'] is None else o['enchantment']['definition_id'])
        for o in work['offers']] for work in state.relic_work]
    assert actual==row['sets']
    assert state.generation_odds['card_offset']==single(row['offset'])
    assert saved(clone(run))==saved(run)
    for stream in ('niche','rewards'):
        assert state.rng.request_count(stream)==row[stream+'Counter']
        assert state.rng.double(stream)==row[stream+'Suffix']
    counters={r.definition_id:r.counter for r in state.relics}
    if 'silver_crucible' in counters:assert counters['silver_crucible']==2
    if 'silken_tress' in counters:assert counters['silken_tress']==1


@pytest.mark.parametrize('row',VECTORS['rows'],ids=lambda r:r['seed']+'-'+r['mode'])
def test_every_native_offered_option_can_be_acquired_played_and_restored(row):
    original=acquisition(row)
    for index in range(3):
        run=clone(original)
        run.apply(ChooseRelicReward(index));assert saved(clone(run))==saved(run)
        run.apply(ChooseRelicReward(index));assert len(run.state.deck)==2
        c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=10000),cards_per_turn=2)
        p=c.player;p.energy=100;p.rules.stars=100
        for card in tuple(p.hand):
            if card not in p.hand:continue
            action=PlayCard(card.instance_id,0 if card.spec.uses_target else None)
            assert action in run.legal_actions(),card.definition.definition_id
            run.apply(action);settle(run)
        assert saved(clone(run))==saved(run)


@pytest.mark.parametrize('row',VECTORS['splash'],ids=lambda r:r['seed']+str(r['upgraded']))
def test_splash_matches_native_pool_offers_upgrades_and_rng(row):
    run=RunEngine(seed=row['seed'],rng_profile='native',card_ids=['splash'])
    if row['upgraded']:run.state.deck[0].upgrade()
    c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=10000),cards_per_turn=1)
    run.apply(PlayCard(c.player.hand[0].instance_id))
    assert [d.definition_id for d in splash_pool(run.cards)]==row['eligible']
    assert [c.definition.definition_id for c in run.combat.player.deck.offered]==row['selected']
    assert [c.upgrade_level for c in run.combat.player.deck.offered]==row['levels']
    rng=c.player.deck.generation_rng
    assert rng.counter==row['counter']
    assert deepcopy(rng).next_double()==row['suffix']
    for index in (None,0,1,2):
        branch=clone(run);p=branch.combat.player
        if index is not None:branch.apply(ChooseCombatCard(p.deck.offered[index].instance_id))
        branch.apply(ConfirmCombatSelection())
        if index is not None:
            card=p.hand[0]
            assert p.card_cost(card)==(p.energy if card.spec.x_cost else 0) and p.star_cost(card)==(p.rules.stars if card.spec.star_x else 0)
            action=PlayCard(card.instance_id,0 if card.spec.uses_target else None)
            assert action in branch.legal_actions()
            branch.apply(action);settle(branch)
        else:assert not p.hand
        assert not p.deck.offered and saved(clone(branch))==saved(branch)


def test_splash_free_energy_expires_on_play_but_stars_last_until_turn_end(monkeypatch):
    from game.headless.cards import colorless_effects
    monkeypatch.setattr(colorless_effects,'select_cards',lambda *a,**kw:[DEFAULT_CARDS.definition('solar_strike'),DEFAULT_CARDS.definition('crescent_spear'),DEFAULT_CARDS.definition('comet')])
    run=RunEngine(card_ids=['splash']);c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=10000),cards_per_turn=1)
    run.apply(PlayCard(c.player.hand[0].instance_id));run.apply(ChooseCombatCard(c.player.deck.offered[2].instance_id));run.apply(ConfirmCombatSelection())
    card=c.player.hand[0];assert c.player.star_cost(card)==0 and c.player.card_cost(card)==0
    run.apply(PlayCard(card.instance_id,0));assert c.player.star_cost(card)==0
    assert card.combat_state.turn_cost_override is None
    run.apply(EndTurn());assert c.player.star_cost(card)==card.spec.star_cost
    assert saved(clone(run))==saved(run)


@pytest.mark.parametrize('mutation',['duplicate_family','owner_card','extra_group','too_few'])
def test_forged_kaleidoscope_groups_reject_atomically(mutation):
    run=acquisition(VECTORS['rows'][0]);baseline=saved(run);bad=deepcopy(baseline);work=bad['state']['relic_work']
    if mutation=='duplicate_family':work[0]['offers'][1]=deepcopy(work[0]['offers'][0])
    elif mutation=='owner_card':work[0]['offers'][0]['definition_id']='anger'
    elif mutation=='extra_group':work.append(deepcopy(work[0]))
    else:work[0]['offers'].pop()
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==baseline


def test_partial_family_catalog_does_not_unlock_kaleidoscope():
    from dataclasses import replace
    additions=[replace(IRONCLAD_CARDS.definition('anger'),definition_id=f'{f}_example',pool=f) for f in FAMILIES]
    cards=CardCatalog((*IRONCLAD_CARDS.definitions,*additions));run=RunEngine(cards=cards);before=saved(run)
    with pytest.raises(ValueError,match='card pools'):run.obtain_relic('kaleidoscope')
    assert saved(run)==before


def test_both_kaleidoscope_groups_can_be_skipped_without_extra_rng():
    run=acquisition(VECTORS['rows'][0]);before=run.state.rng.snapshot()
    for _ in range(2):run.apply(ChooseRelicReward(None));assert saved(clone(run))==saved(run)
    assert not run.state.deck and not run.state.relic_work and run.state.rng.snapshot()==before


def test_splash_star_x_still_spends_available_stars(monkeypatch):
    from game.headless.cards import colorless_effects
    monkeypatch.setattr(colorless_effects,'select_cards',lambda *a,**kw:[DEFAULT_CARDS.definition(n) for n in ('stardust','solar_strike','crescent_spear')])
    run=RunEngine(card_ids=['splash']);c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=10000),cards_per_turn=1)
    c.player.rules.stars=5
    run.apply(PlayCard(c.player.hand[0].instance_id));run.apply(ChooseCombatCard(c.player.deck.offered[0].instance_id));run.apply(ConfirmCombatSelection())
    card=c.player.hand[0];assert c.player.star_cost(card)==5 and card.combat_state.star_free_this_turn
    run.apply(PlayCard(card.instance_id));assert c.player.rules.stars==0
    assert saved(clone(run))==saved(run)


@pytest.mark.parametrize('event,option',[('aroma_of_chaos','let_go'),('aroma_of_chaos','maintain_control'),('morphic_grove','group'),('whispering_hollow','hug'),('new_leaf',None)])
@pytest.mark.parametrize('seed',['0','1','2','42','ABC123'])
def test_acquired_foreign_cards_continue_through_transformation_sources(event,option,seed):
    from game.headless.run import events
    from game.headless.run.actions import ChooseEventOption,ChooseEventCard,ChooseRelicCard,ConfirmRelicSelection
    row=next(r for r in VECTORS['rows'] if r['seed']==seed and r['mode']=='plain')
    run=acquisition(row)
    run.apply(ChooseRelicReward(0));run.apply(ChooseRelicReward(0));run.state.gold=200
    original_ids=[c.instance_id for c in run.state.deck];families=[c.definition.pool for c in run.state.deck]
    if event=='new_leaf':
        run.obtain_relic(event);assert saved(clone(run))==saved(run)
        run.apply(ChooseRelicCard(original_ids[0]));run.apply(ConfirmRelicSelection())
    else:
        events.begin(run.state,event,cards=run.cards);assert saved(clone(run))==saved(run)
        run.apply(ChooseEventOption(run.state.pending['event_instance_id'],option));assert saved(clone(run))==saved(run)
        while run.state.pending['stage']=='select_card':
            run.apply(next(a for a in run.legal_actions() if isinstance(a,ChooseEventCard)))
            assert saved(clone(run))==saved(run)
    assert [c.definition.pool for c in run.state.deck]==families
    if option!='maintain_control':assert [c.instance_id for c in run.state.deck]!=original_ids
    assert saved(clone(run))==saved(run)


@pytest.mark.parametrize('row',VECTORS['transforms'],ids=lambda r:r['original']+str(r['inCombat']))
def test_foreign_transformation_order_and_replacements_match_native(row):
    from game.headless.core.native_rng import NativeRng
    from game.headless.generation.transforms import combat_options
    from game.headless.events.transformation import replacement_pool,TRANSFORM_POOL
    from game.headless.run.deck import transform_card
    original=DEFAULT_CARDS.create(row['original'])
    if row['inCombat']:
        options=[d.definition_id for d in combat_options(DEFAULT_CARDS,original)]
    else:
        options=[n for n in replacement_pool(row['original'],TRANSFORM_POOL) if n!=row['original']]
    assert options==row['options']
    for sample in row['samples']:
        rng=NativeRng(sample['seed'])
        assert rng.choice(options)==sample['selected']
        assert rng.counter==sample['counter'] and rng.next_double()==sample['suffix']
        if not row['inCombat']:
            run=RunEngine(seed=sample['seed'],rng_profile='native',card_ids=[row['original']])
            expected=deepcopy(run.state.rng.stream('niche'))
            selected=expected.choice(options)
            card=transform_card(run.state,run.cards,run.state.deck[0].instance_id,replacement_pool(row['original'],TRANSFORM_POOL),stream='niche')
            assert card.definition.definition_id==selected
            assert run.state.rng.request_count('niche')==expected.counter
            assert run.state.rng.double('niche')==expected.next_double()
            assert saved(clone(run))==saved(run)


@pytest.mark.parametrize('mutation',['owner_card','duplicate','upgrade'])
def test_forged_splash_offers_reject_atomically(mutation):
    run=RunEngine(card_ids=['splash']);c=run.start_combat()
    run.apply(PlayCard(c.player.hand[0].instance_id))
    baseline=saved(run);bad=deepcopy(baseline)
    offers=bad['combat']['deck']['piles']['offered']
    if mutation=='owner_card':offers[0]['definition_id']='anger'
    elif mutation=='duplicate':offers[1]['definition_id']=offers[0]['definition_id']
    else:offers[0]['upgrade_level']=1
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==baseline
