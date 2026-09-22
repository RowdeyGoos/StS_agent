"""Pinned Defect inventory, cross-card behavior and resumable solo execution."""

import json
from pathlib import Path
import pytest
from game.headless.cards.catalog import DEFAULT_CARDS, IRONCLAD_CARDS, DEFECT_CARDS
from game.headless.cards.defect import ORDINARY_IDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection, EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.powers.ironclad import apply_power
from game.headless.core.resolution import drain


def saved(c):
    return json.loads(json.dumps(c.snapshot()))


def clone(c):
    other = CombatEngine(cards=DEFECT_CARDS)
    other.restore(saved(c))
    return other


def fight(*hand, draw=(), discard=(), exhaust=(), level=0, hp=1000, enemies=1):
    ids = (*hand, *draw, *discard, *exhaust)
    c = CombatEngine(cards=DEFECT_CARDS, cards_per_turn=0,
        deck_factory=lambda: [DEFECT_CARDS.create(n, upgrade_level=level if i == 0 else 0, instance_id=f'card.{i}') for i, n in enumerate(ids)],
        encounter_factory=lambda _: [SimpleEnemy(max_hp=hp) for _ in range(enemies)])
    c.reset()
    d = c.player.deck
    cards = {x.instance_id:x for x in d.all_cards()}
    d.draw_pile.clear()
    d.hand.clear()
    offset = 0
    for names, pile in ((hand,d.hand),(draw,d.draw_pile),(discard,d.discard_pile),(exhaust,d.exhaust_pile)):
        pile.extend(cards[f'card.{i}'] for i in range(offset, offset+len(names)))
        offset += len(names)
    c.player.energy = 20
    c.player.rules.stars = 20
    return c


def play(c, name, slot=0):
    card = next(x for x in c.player.hand if x.definition.definition_id == name)
    return c.apply(PlayCard(card.instance_id, slot if card.spec.uses_target else None))


def select(c, *names):
    if c.player.rules.selection is None:
        return
    for name in names:
        card = next(x for x in c.player.hand if x.definition.definition_id == name)
        c.apply(ChooseCombatCard(card.instance_id))
    c.apply(ConfirmCombatSelection())


def settle(c):
    for _ in range(100):
        if c.player.pending_play is None and c.player.rules.selection is None:
            return
        other = clone(c)
        actions = c.legal_actions()
        s=c.player.rules.selection
        action = ConfirmCombatSelection() if ConfirmCombatSelection() in actions else next(a for a in actions if s is None or a.instance_id not in s["selected"])
        c.apply(action); other.apply(action)
        assert saved(c) == saved(other)
    pytest.fail('Choices did not terminate')


ROWS = json.loads((Path(__file__).parents[1]/'fixtures/headless_native_defect_vectors.json').read_text())['rows']


def test_complete_native_family_is_explicit_and_enabled_in_default_catalog():
    assert len(ORDINARY_IDS) == 80
    assert set(ORDINARY_IDS) == {r['id'] for r in ROWS if r['rarity'] in ('Common','Uncommon','Rare')}
    assert set(ORDINARY_IDS) <= {d.definition_id for d in DEFAULT_CARDS.definitions}
    assert not set(ORDINARY_IDS) & {d.definition_id for d in IRONCLAD_CARDS.definitions}


@pytest.mark.parametrize('row', [r for r in ROWS if r['rarity'] != 'Ancient'], ids=lambda r:r['id'])
def test_native_values_and_keywords_at_both_upgrade_levels(row):
    d = DEFECT_CARDS.definition(row['id'])
    assert (d.rarity, d.pool, d.generate_in_combat) == (row['rarity'].lower(), 'token' if row['rarity']=='Token' else 'defect', row['generate'])
    for level, expected in enumerate(row['levels']):
        spec = d.levels[level]
        assert (spec.kind,spec.cost,spec.x_cost,spec.uses_target) == (row['kind'].lower(),expected['cost'],expected['x'],row['target']=='AnyEnemy')
        for field, keyword in [('exhausts','Exhaust'),('retain','Retain'),('innate','Innate'),('sly','Sly'),('ethereal','Ethereal')]:
            assert getattr(spec,field) == (keyword in expected['keywords'])
        assert (spec.star_cost,spec.star_x)==(expected['star'],expected['starX'])
        v=expected['vars']
        if 'OstyDamage' in v: assert spec.base_damage==v['OstyDamage']
        if 'Damage' in v: assert spec.base_damage==v['Damage']
        if 'CalculatedDamage' in v: assert spec.base_damage==v['CalculationBase']
        if 'Block' in v: assert spec.block_gain==v['Block']


@pytest.mark.parametrize('identity', ORDINARY_IDS)
@pytest.mark.parametrize('level', [0,1])
def test_every_defect_card_resumes_choices_and_three_turns(identity,level):
    c = fight(identity,'deflect','tactician', draw=('strike','defend','reflex','prepared'), discard=('slice','defend'), exhaust=('shiv',),level=level)
    play(c,identity);settle(c)
    assert not c.player.deck.in_play
    other=clone(c)
    assert saved(other)==saved(c)
    for _ in range(3):
        if c.done:break
        c.apply(EndTurn());settle(c)
        assert saved(clone(c))==saved(c)







def channel(c, *kinds):
    from game.headless.core.resolution import push
    push(c.player, *[['orb_channel', kind] for kind in kinds])
    drain(c.player)


def orb_values(c):
    r = c.player.rules
    return [r.orbs[i] for i in r.orb_order]


def test_ironclad_first_channel_grants_one_slot_and_overflow_evokes_first():
    c = fight('zap', 'cold_snap')
    assert c.player.rules.orb_slots == 0
    play(c, 'zap')
    assert c.player.rules.orb_slots == 1
    play(c, 'cold_snap')
    assert c.enemies[0].hp == 986  # 6 attack, 8 evoked lightning.
    assert orb_values(c) == [{'kind':'frost', 'value':0}]
    assert saved(clone(c)) == saved(c)


@pytest.mark.parametrize('kind,passive,evoke', [('lightning',5,10),('frost',4,7),('plasma',1,2),('dark',8,6),('glass',6,12)])
def test_orb_base_and_focus_values(kind, passive, evoke):
    from game.headless.core.orbs import value
    c = fight('defend'); channel(c, kind); apply_power(c.player, 'focus', 2)
    orb = orb_values(c)[0]
    assert (value(c.player, orb, 'passive'), value(c.player, orb, 'evoke')) == (passive, evoke)


def test_dark_stores_growth_and_targets_first_lowest_hp_without_rng():
    from game.headless.core.resolution import push
    c = fight('darkness', 'dualcast', enemies=2);p=c.player
    apply_power(p,'focus',2);play(c,'darkness')
    assert orb_values(c)[0]['value'] == 14
    apply_power(p,'focus',-4)
    c.enemies[0].hp=c.enemies[1].hp=50
    state=p.deck.target_rng.getstate()
    play(c,'dualcast')
    assert [e.hp for e in c.enemies]==[22,50]
    assert p.deck.target_rng.getstate()==state
    assert not p.rules.orb_order


def test_glass_decays_raw_value_but_focus_remains_effective():
    from game.headless.core.resolution import push
    c=fight('defend',enemies=2);p=c.player;channel(c,'glass');apply_power(p,'focus',2)
    identity=p.rules.orb_order[0]
    for _ in range(6):push(p,['orb_trigger',identity,'passive',None]);drain(p)
    assert [e.hp for e in c.enemies]==[978,978]  # 6+5+4+3+2+2
    assert orb_values(c)[0]['value']==0
    assert saved(clone(c))==saved(c)


def test_remove_slots_drops_trailing_orbs_without_evoke_and_can_rechannel():
    from game.headless.core.orbs import add_slots
    c=fight('bulk_up','bulk_up','zap');p=c.player;add_slots(p,2);channel(c,'lightning','plasma')
    energy=p.energy;play(c,'bulk_up')
    assert p.energy==energy-2 and [o['kind'] for o in orb_values(c)]==['lightning']
    play(c,'bulk_up');assert p.rules.orb_slots==0 and c.enemies[0].hp==1000
    play(c,'zap');assert p.rules.orb_slots==1


def test_slots_cap_at_ten():
    from game.headless.core.orbs import add_slots
    c=fight('capacitor',level=1);add_slots(c.player,9);play(c,'capacitor')
    assert c.player.rules.orb_slots==10


def test_temp_focus_applies_to_end_passive_then_expires():
    c=fight('hotfix','zap');p=c.player;play(c,'hotfix');play(c,'zap');c.apply(EndTurn())
    assert c.enemies[0].hp==995
    assert p.rules.powers.get('focus',0)==0 and 'hotfix' not in p.rules.powers


@pytest.mark.parametrize('temporary_first,expected',[(True,992),(False,990)])
def test_consuming_shadow_observes_temp_focus_expiration_order(temporary_first,expected):
    c=fight('defend');p=c.player;channel(c,'lightning')
    order=('hotfix','consuming_shadow') if temporary_first else ('consuming_shadow','hotfix')
    for key in order:apply_power(p,key,2 if key=='hotfix' else 1)
    c.apply(EndTurn())
    assert c.enemies[0].hp==expected-5  # passive5 precedes both ordered end hooks.


def test_plasma_only_naturally_triggers_at_start_after_reset():
    c=fight('fusion');p=c.player;play(c,'fusion');before=p.energy;c.apply(EndTurn())
    assert p.energy==4 and before==19


def test_loop_adds_extra_passive_and_lightning_rod_channels_before_draw():
    c=fight('lightning_rod','loop');p=c.player;play(c,'lightning_rod');play(c,'loop');c.apply(EndTurn())
    assert c.enemies[0].hp==997
    assert p.rules.powers['lightning_rod']==1
    assert len(p.rules.orb_order)==1


def test_hailstorm_kills_before_lightning_passive_consumes_target_rng():
    from game.headless.core.orbs import add_slots
    c=fight('defend');p=c.player;add_slots(p,2);channel(c,'frost','lightning');apply_power(p,'hailstorm',6);c.enemies[0].hp=5
    before=p.deck.target_rng.getstate();c.apply(EndTurn())
    assert c.done and p.deck.target_rng.getstate()==before


def test_echo_form_counts_series_and_feral_returns_only_once_per_series():
    c=fight('claw','claw');p=c.player;apply_power(p,'echo_form',1);apply_power(p,'feral',1)
    first=p.hand[0].instance_id;play(c,'claw')
    assert c.enemies[0].hp==992 and p.rules.series_turn==1 and p.rules.zero_attacks_turn==2
    assert p.rules.auxiliaries['feral']==1
    assert any(x.instance_id==first for x in p.hand)
    play(c,'claw');assert len(p.hand)==1
    assert saved(clone(c))==saved(c)


def test_midturn_echo_and_feral_see_earlier_play_history():
    c=fight('claw','feral','echo_form','strike');p=c.player
    play(c,'claw');play(c,'feral');assert p.rules.auxiliaries['feral']==1
    play(c,'echo_form');hp=c.enemies[0].hp;play(c,'strike');assert hp-c.enemies[0].hp==6


def test_signal_boost_repeats_power_but_storm_does_not_trigger_itself():
    c=fight('storm','signal_boost','capacitor');p=c.player
    play(c,'storm');assert not p.rules.orb_order
    play(c,'signal_boost');play(c,'capacitor')
    assert p.rules.orb_slots==4 and len(p.rules.orb_order)==2
    assert p.rules.powers['signal_boost']==0


def test_helix_drill_uses_energy_spent_and_excludes_own_modified_cost():
    c=fight('defend','helix_drill');p=c.player;play(c,'defend')
    p.hand[0].combat_state.combat_cost_change=2
    play(c,'helix_drill');assert c.enemies[0].hp==997 and p.rules.energy_spent_turn==3


def test_momentum_and_adaptive_clones_keep_zero_combat_cost():
    c=fight('momentum_strike','adaptive_strike');p=c.player
    play(c,'momentum_strike');play(c,'adaptive_strike')
    clones=[x for x in p.deck.discard_pile if x.definition.definition_id=='adaptive_strike']
    assert len(clones)==2 and sorted(p.card_cost(x) for x in clones)==[0,2]
    assert p.rules.generated_combat==1
    assert p.card_cost(next(x for x in p.deck.discard_pile if x.definition.definition_id=='momentum_strike'))==0


def test_compact_transforms_statuses_to_fuel_without_generation_hooks():
    c=fight('compact','wound','dazed',level=1);p=c.player;apply_power(p,'smokestack',7);apply_power(p,'trash_to_treasure',1)
    play(c,'compact')
    assert [x.definition.definition_id for x in p.hand]==['fuel','fuel']
    assert all(x.upgraded for x in p.hand) and c.enemies[0].hp==1000
    assert not p.rules.orb_order and p.rules.generated_combat==2


def test_generated_status_triggers_owner_hooks_and_rocket_until_played():
    c=fight('boost_away','rocket_punch');p=c.player;apply_power(p,'smokestack',5);apply_power(p,'trash_to_treasure',1)
    play(c,'boost_away');assert c.enemies[0].hp==995 and len(p.rules.orb_order)==1
    rocket=p.hand[0];assert p.card_cost(rocket)==0
    c.apply(EndTurn());assert p.card_cost(rocket)==0
    # Explicit non-hand card lookup still sees the card-local persistent modifier.
    assert rocket.combat_state.played_cost_override == 0


def test_enemy_created_status_does_not_trigger_owner_generation_hooks():
    c=fight('rocket_punch');p=c.player;apply_power(p,'smokestack',5);apply_power(p,'trash_to_treasure',1)
    p.add_card_to_discard(DEFECT_CARDS.create('wound'));drain(p)
    assert c.enemies[0].hp==1000 and not p.rules.orb_order and p.card_cost(p.hand[0])==2


def test_scrape_discards_only_its_draws_and_resolves_sly():
    c=fight('scrape',draw=('defend','deflect','tactician','prepared'));p=c.player
    play(c,'scrape');settle(c)
    assert any(x.definition.definition_id=='deflect' for x in p.hand)
    assert not any(x.definition.definition_id=='defend' for x in p.hand)
    assert p.rules.discarded_turn>=1
    assert saved(clone(c))==saved(c)


def test_iteration_triggers_once_per_turn_including_hand_draws():
    c=fight('skim',draw=('strike','wound','dazed'));p=c.player;apply_power(p,'defect_iteration',2)
    play(c,'skim');assert p.rules.status_draws_turn==2 and len(p.hand)==3
    assert p.rules.drawn_combat==3


def test_flak_cannon_exhausts_statuses_across_piles_before_random_hits():
    c=fight('flak_cannon','wound',draw=('burn',),discard=('dazed',),exhaust=('void',));p=c.player
    play(c,'flak_cannon');assert c.enemies[0].hp==976
    assert len(p.deck.exhaust_pile)==4


def test_sunder_consumes_vigor_and_grants_energy_on_kill():
    c=fight('sunder',enemies=2);p=c.player;c.enemies[0].hp=30;apply_power(p,'vigor',6)
    play(c,'sunder');assert c.enemies[0].hp==0 and p.energy==20 and not p.rules.powers.get('vigor')


def test_genetic_algorithm_growth_syncs_to_owned_run_card_and_next_combat():
    from game.headless.run.engine import RunEngine
    run=RunEngine(cards=DEFECT_CARDS,card_ids=['genetic_algorithm','strike'])
    c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=6))
    genetic=next(x for x in c.player.hand if x.definition.definition_id=='genetic_algorithm')
    run.apply(PlayCard(genetic.instance_id,None))
    assert c.player.block==1 and run.state.deck[0].permanent_block==3
    other=RunEngine(cards=DEFECT_CARDS,card_ids=[]);other.restore(json.loads(json.dumps(run.snapshot())))
    assert other.state.deck[0].spec.block_gain==4
    strike=next(x for x in other.combat.player.hand if x.definition.definition_id=='strike')
    other.apply(PlayCard(strike.instance_id,0))
    c=other.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000));play(c,'genetic_algorithm');assert c.player.block==4


@pytest.mark.parametrize('kind',['bad','lightning'])
def test_orb_snapshot_rejects_invalid_instances_and_duplicate_queue(kind):
    c=fight('defend');channel(c,'lightning');snapshot=saved(c)
    if kind=='bad':snapshot['player']['rules']['orbs']['orb.0']['kind']='bad'
    else:snapshot['player']['rules']['orb_order'].append('orb.0')
    with pytest.raises(ValueError):CombatEngine(cards=DEFECT_CARDS).restore(snapshot)


@pytest.mark.parametrize('task',[['orb_channel','lightning'],['orb_trigger','orb.0','evoke',None],['def_damage',0,999]])
def test_injected_orb_and_defect_tasks_need_pending_event(task):
    c=fight('scavenge','defend','strike');channel(c,'lightning');play(c,'scavenge');snapshot=saved(c)
    snapshot['player']['rules']['tasks'].insert(0,task)
    with pytest.raises(ValueError):CombatEngine(cards=DEFECT_CARDS).restore(snapshot)


def test_native_orb_rng_has_own_stream_and_restores_alias():
    from game.headless.run.engine import RunEngine
    run=RunEngine(seed=2,rng_profile='native',cards=DEFECT_CARDS,card_ids=['chaos'])
    c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000))
    before=c.player.deck.generation_rng.getstate();run.apply(PlayCard(c.player.hand[0].instance_id,None))
    assert c.player.deck.generation_rng.getstate()==before
    assert run.state.rng.request_count('combat_orb_generation')==1
    restored=RunEngine(cards=DEFECT_CARDS,card_ids=[]);restored.restore(json.loads(json.dumps(run.snapshot())))
    assert restored.combat.player.deck.orb_rng is restored.state.rng.stream('combat_orb_generation')


def test_feral_stacking_preserves_used_return_count_after_replay():
    c=fight('claw','feral');p=c.player;apply_power(p,'feral',1)
    claw=p.hand[0];claw.combat_state.replay_count=1
    play(c,'claw');assert p.rules.auxiliaries['feral']==1
    play(c,'feral');assert p.rules.auxiliaries['feral']==1
    play(c,'claw');assert claw in p.hand and p.rules.auxiliaries['feral']==2


def test_restored_combat_owns_orb_rng_and_snapshots_its_state():
    env = CombatEngine(seed=4, deck_factory=lambda: [DEFECT_CARDS.create('chaos')])
    env.reset()
    other = CombatEngine()
    other.restore(env.snapshot())
    before = env.snapshot()
    other.player.deck.orb_rng.random()
    assert env.snapshot() == before
    assert other.snapshot() != before


def test_rocket_discount_is_local_survives_restore_and_resets_after_play():
    from game.headless.powers.ironclad import local_cost
    c=fight('turbo','scrape',draw=('rocket_punch',));p=c.player
    play(c,'turbo');rocket=p.deck.draw_pile[0]
    p.apply_status('tangled',1)
    assert local_cost(rocket)==0 and p.card_cost(rocket)==1
    play(c,'scrape');assert rocket in p.hand
    assert saved(clone(c))==saved(c)
    play(c,'rocket_punch');assert local_cost(rocket)==2 and p.card_cost(rocket)==3


def test_rocket_local_setter_order_and_expired_relative_changes():
    from game.headless.core.card_costs import mark_setter, until_played
    from game.headless.powers.ironclad import local_cost
    c=fight('rocket_punch');card=c.player.hand[0];v=card.combat_state
    v.turn_cost_change=2;until_played(card,0)
    assert local_cost(card)==0
    v.turn_cost_override=3;v.override_turn_baseline=2;mark_setter(v,'turn')
    assert local_cost(card)==3
    until_played(card,0);assert local_cost(card)==0
    c.apply(EndTurn());assert local_cost(card)==0
    v.combat_cost_change+=1;assert local_cost(card)==1
    assert saved(clone(c))==saved(c)


@pytest.mark.parametrize('doom_first',[True,False])
def test_doom_and_hailstorm_resolve_in_application_order(doom_first):
    c=fight(hp=5);p=c.player
    channel(c,'frost')
    if doom_first:p.apply_status('doom',p.hp)
    apply_power(p,'hailstorm',6)
    if not doom_first:p.apply_status('doom',p.hp)
    other=clone(c)
    c.apply(EndTurn());other.apply(EndTurn())
    assert saved(c)==saved(other)
    assert p.is_alive is (not doom_first)
    assert c.enemies[0].is_alive is doom_first
    if doom_first:assert p.rules.orb_slots==0 and not p.rules.orb_order


@pytest.mark.parametrize('revive',[False,True])
def test_confirmed_death_clears_orbs_but_revival_keeps_them(revive):
    from game.headless.potions.base import PotionInstance
    from dataclasses import asdict
    c=fight();p=c.player;channel(c,'lightning')
    if revive:
        p.rules.potions=[asdict(PotionInstance('fairy_in_a_bottle','potion.0')),None,None]
        p.rules.potion_slots=2
    p.lose_hp(999)
    c.resolve_external_effect()
    assert p.is_alive is revive
    assert p.rules.orb_slots==int(revive)
    assert bool(p.rules.orb_order) is revive
    assert len(p.rules.orbs)==1
    assert saved(clone(c))==saved(c)


def test_snapshot_rejects_missing_ambiguous_side_end_listener_order():
    c=fight();apply_power(c.player,'hailstorm',6);c.player.apply_status('doom',80)
    data=saved(c)
    def erase(node):
        if isinstance(node,dict):
            if 'before_side_end_order' in node:node['before_side_end_order']=[]
            for v in node.values():erase(v)
        elif isinstance(node,list):
            for v in node:erase(v)
    erase(data)
    with pytest.raises(ValueError,match='listener order'):CombatEngine(cards=DEFECT_CARDS).restore(data)


def test_snapshot_rejects_missing_ambiguous_local_cost_order():
    from game.headless.core.card_costs import until_played,mark_setter
    c=fight('rocket_punch');v=c.player.hand[0].combat_state
    until_played(c.player.hand[0],0);v.turn_cost_override=3;mark_setter(v,'turn')
    data=saved(c)
    def erase(node):
        if isinstance(node,dict):
            if 'cost_override_order' in node:node['cost_override_order']=[]
            for x in node.values():erase(x)
        elif isinstance(node,list):
            for x in node:erase(x)
    erase(data)
    with pytest.raises(ValueError,match='setter order'):CombatEngine(cards=DEFECT_CARDS).restore(data)


def test_glass_damage_resumes_horn_shuffle_choice_with_owned_orbs():
    from dataclasses import asdict
    from game.headless.relics.base import RelicInstance
    from game.headless.core.resolution import push
    c=fight(discard=('defend','strike','defend'),enemies=2);p=c.player
    p.rules.relics=[asdict(RelicInstance('gremlin_horn','probe.relic'))]
    p.rules.relic_data={'probe.relic':{}}
    apply_power(p,'stratagem',1);channel(c,'glass');c.enemies[0].hp=1
    push(p,['orb_trigger',p.rules.orb_order[0],'passive',None]);drain(p)
    assert p.rules.selection is not None and c.enemies[1].hp==996
    other=clone(c);settle(c);settle(other)
    assert saved(c)==saved(other) and not p.rules.pending_events
