"""Pinned Necrobinder inventory, cross-card behavior and resumable solo execution."""

import json
from pathlib import Path
import pytest
from game.headless.cards.catalog import DEFAULT_CARDS, IRONCLAD_CARDS, NECROBINDER_CARDS
from game.headless.cards.necrobinder import ORDINARY_IDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection, EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.powers.ironclad import apply_power
from game.headless.core.resolution import drain


def saved(c):
    return json.loads(json.dumps(c.snapshot()))


def clone(c):
    other = CombatEngine(cards=NECROBINDER_CARDS)
    other.restore(saved(c))
    return other


def fight(*hand, draw=(), discard=(), exhaust=(), level=0, hp=1000, enemies=1):
    ids = (*hand, *draw, *discard, *exhaust)
    c = CombatEngine(cards=NECROBINDER_CARDS, cards_per_turn=0,
        deck_factory=lambda: [NECROBINDER_CARDS.create(n, upgrade_level=level if i == 0 else 0, instance_id=f'card.{i}') for i, n in enumerate(ids)],
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


ROWS = json.loads((Path(__file__).parents[1]/'fixtures/headless_native_necrobinder_vectors.json').read_text())['rows']


def test_complete_native_family_is_explicit_and_enabled_in_default_catalog():
    assert len(ORDINARY_IDS) == 80
    assert set(ORDINARY_IDS) == {r['id'] for r in ROWS if r['rarity'] in ('Common','Uncommon','Rare')}
    assert set(ORDINARY_IDS) <= {d.definition_id for d in DEFAULT_CARDS.definitions}
    assert not set(ORDINARY_IDS) & {d.definition_id for d in IRONCLAD_CARDS.definitions}


@pytest.mark.parametrize('row', [r for r in ROWS if r['rarity'] != 'Ancient'], ids=lambda r:r['id'])
def test_native_values_and_keywords_at_both_upgrade_levels(row):
    d = NECROBINDER_CARDS.definition(row['id'])
    assert (d.rarity, d.pool, d.generate_in_combat) == (row['rarity'].lower(), 'token' if row['rarity']=='Token' else 'necrobinder', row['generate'])
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
def test_every_necrobinder_card_resumes_choices_and_three_turns(identity,level):
    c = fight(identity,'deflect','tactician', draw=('strike','defend','reflex','prepared'), discard=('slice','defend'), exhaust=('shiv',),level=level)
    from game.headless.core.osty import summon
    summon(c.player, 10)
    play(c,identity);settle(c)
    assert not c.player.deck.in_play
    other=clone(c)
    assert saved(other)==saved(c)
    for _ in range(3):
        if c.done:break
        c.apply(EndTurn());settle(c)
        assert saved(clone(c))==saved(c)





def test_summon_is_owned_and_revival_reuses_pet_without_rng():
    from game.headless.core.osty import summon, lose_hp
    c=fight('bodyguard','spur'); p=c.player
    before=[rng.getstate() for rng in (p.deck.rng,p.deck.niche_rng,p.deck.target_rng)]
    assert p.rules.osty is None
    play(c,'bodyguard')
    pet=p.rules.osty
    assert pet == {'hp':5,'max_hp':5}
    lose_hp(p,3); summon(p,2)
    assert pet == {'hp':4,'max_hp':7}
    lose_hp(p,20); summon(p,3)
    assert p.rules.osty is pet and pet == {'hp':3,'max_hp':3}
    assert before == [rng.getstate() for rng in (p.deck.rng,p.deck.niche_rng,p.deck.target_rng)]
    assert clone(c).player.rules.osty == pet


def test_osty_receives_unblocked_attack_then_owner_spillover_only():
    from game.headless.core.osty import summon
    c=fight('strike'); p=c.player; summon(p,5)
    p.block=3
    p.take_damage(6,source=c.enemies[0]); drain(p)
    assert (p.block,p.rules.osty['hp'],p.hp)==(0,2,80)
    p.take_damage(7,source=c.enemies[0]);drain(p)
    assert (p.rules.osty['hp'],p.hp)==(0,75)
    summon(p,9)
    p.take_damage(4,is_attack=False);p.lose_hp(2);drain(p)
    assert (p.rules.osty['hp'],p.hp)==(9,69)


def test_pet_ignores_owner_strength_weak_and_vigor_but_uses_calcify():
    from game.headless.core.osty import summon
    c=fight('poke','strike');p=c.player; summon(p,5)
    p.strength=10;p.apply_status('weak',2);apply_power(p,'vigor',8);apply_power(p,'calcify',4)
    play(c,'poke')
    assert c.enemies[0].hp==990
    assert p.rules.powers['vigor']==8
    play(c,'strike')
    assert c.enemies[0].hp==972


def test_missing_osty_guards_are_card_specific():
    c=fight('high_five','poke','snap','sic_em','strike')
    high=next(x for x in c.player.hand if x.definition.definition_id=='high_five')
    assert PlayCard(high.instance_id,None) not in c.legal_actions()
    play(c,'poke');assert c.enemies[0].hp==1000
    play(c,'sic_em');assert c.enemies[0].statuses.get('sic_em')==3
    play(c,'snap');assert c.player.rules.selection is not None
    select(c,'strike');assert next(x for x in c.player.hand if x.definition.definition_id=='strike').spec.retain


def test_doom_waits_until_enemy_turn_end_and_ignores_block():
    c=fight('scourge',hp=13)
    c.enemies[0].block=99
    play(c,'scourge')
    assert not c.done and c.enemies[0].hp==13
    c.apply(EndTurn())
    assert c.done and c.winner=='player' and c.player.hp<80


def test_end_of_days_kills_immediately_and_slippery_does_not_save_target():
    c=fight('end_of_days',hp=29,enemies=2)
    for e in c.enemies:e.block=99;e.statuses.add('slippery',5)
    play(c,'end_of_days')
    assert c.done and c.player.hp==80


def test_self_doom_and_artifact_and_intangible_do_not_confuse_direct_kill():
    c=fight('neurosurge');p=c.player
    play(c,'neurosurge');p.hp=3
    c.apply(EndTurn())
    # Enemy may kill a low-HP owner before the next turn; directly exercise boundary.
    d=fight('strike');d.player.statuses.add('doom',80);apply_power(d.player,'intangible',1)
    d.apply(EndTurn());assert d.done and d.winner=='enemy'
    e=fight('neurosurge');play(e,'neurosurge');e.player.statuses.add('artifact',1)
    e.apply(EndTurn());assert not e.player.statuses.get('doom') and not e.player.statuses.get('artifact')


def test_doom_application_shroud_and_deaths_door_per_target():
    c=fight('negative_pulse','deaths_door',enemies=2);apply_power(c.player,'shroud',2)
    play(c,'negative_pulse');assert c.player.block==9
    play(c,'deaths_door');assert c.player.block==27
    c=fight('deaths_door');play(c,'deaths_door');assert c.player.block==6


def test_no_escape_threshold_and_oblivion_captured_before_play():
    c=fight('oblivion','scourge','no_escape');p=c.player
    play(c,'oblivion');assert not c.enemies[0].statuses.get('doom')
    play(c,'scourge');assert c.enemies[0].statuses.get('doom')==16
    play(c,'no_escape');assert c.enemies[0].statuses.get('doom')==34
    c.apply(EndTurn());assert not c.enemies[0].statuses.get('oblivion')


def test_blight_and_reaper_form_include_block_in_damage_result():
    c=fight('blight_strike');p=c.player;apply_power(p,'reaper_form',1)
    c.enemies[0].block=20
    play(c,'blight_strike')
    assert c.enemies[0].hp==1000 and c.enemies[0].block==12
    assert c.enemies[0].statuses.get('doom')==16


def test_debilitate_doubles_weak_and_vulnerable_effects():
    c=fight('debilitate','strike');e=c.enemies[0]
    play(c,'debilitate');e.statuses.add('vulnerable',2)
    play(c,'strike');assert e.hp==978
    from game.headless.powers.status import modify_attack_damage_for_statuses
    e.statuses.add('weak',2)
    assert modify_attack_damage_for_statuses(12,c.player.statuses,e.statuses)==6


def test_soul_draw_and_exhaust_and_storm_scaling():
    c=fight('soul','soul_storm',draw=('strike','defend'));p=c.player
    play(c,'soul');assert len(p.hand)==3 and p.deck.exhaust_pile[0].definition.definition_id=='soul'
    play(c,'soul_storm');assert c.enemies[0].hp==989


def test_soul_hooks_summon_and_haunt_without_block_damage():
    c=fight('soul',draw=('strike','defend'));p=c.player
    apply_power(p,'devour_life',2);apply_power(p,'haunt',6);c.enemies[0].block=99
    play(c,'soul')
    assert p.rules.osty=={'hp':2,'max_hp':2}
    assert c.enemies[0].hp==994 and c.enemies[0].block==99


def test_soul_random_insertion_consumes_shuffle_only_and_restores():
    from game.headless.core.native_rng import NativeRng
    c=fight('capture_spirit',draw=('strike','defend'));p=c.player
    p.deck.rng=NativeRng(42);p.deck.niche_rng=NativeRng(90)
    play(c,'capture_spirit')
    assert p.deck.rng.counter==3 and p.deck.niche_rng.counter==0
    assert sum(x.definition.definition_id=='soul' for x in p.deck.draw_pile)==3
    assert saved(clone(c))==saved(c)


def test_dirge_x_summons_then_inserts_upgraded_souls():
    c=fight('dirge',level=1);c.player.energy=3
    play(c,'dirge')
    assert c.player.rules.osty=={'hp':12,'max_hp':12}
    assert len(c.player.deck.draw_pile)==3 and all(x.upgraded for x in c.player.deck.draw_pile)


def test_ethereal_play_counters_and_death_march_ignore_hand_draw():
    c=fight('parse','banshees_cry','pull_from_below','death_march',draw=('strike','defend','defile'))
    play(c,'parse');p=c.player
    assert p.rules.ethereal_plays==1 and p.rules.drawn_turn==3
    assert p.card_cost(next(x for x in p.hand if x.definition.definition_id=='banshees_cry'))==7
    play(c,'pull_from_below');assert c.enemies[0].hp==995
    play(c,'death_march');assert c.enemies[0].hp==975


def test_pagestorm_and_spirit_of_ash_and_veilpiercer():
    c=fight('veilpiercer','parse',draw=('strike','defile'));p=c.player
    apply_power(p,'spirit_of_ash',4);apply_power(p,'pagestorm',1)
    play(c,'veilpiercer')
    assert p.card_cost(next(x for x in p.hand if x.definition.definition_id=='parse'))==0
    play(c,'parse')
    assert p.block==4 and not p.rules.powers['veilpiercer'] and len(p.hand)==3
    assert p.rules.drawn_turn==3


def test_eidolon_exhausts_captured_hand_and_grants_intangible():
    c=fight('eidolon',*(['strike']*9));p=c.player
    play(c,'eidolon');assert len(p.deck.exhaust_pile)==9
    p.take_damage(20);p.lose_hp(7);assert p.hp==78
    c.apply(EndTurn());assert p.rules.powers['intangible']==0


def test_fetch_counts_physical_cards_and_rattle_counts_attack_commands():
    from game.headless.core.osty import summon
    c=fight('fetch','fetch','rattle',draw=('strike','defend','strike'));p=c.player;summon(p,5)
    first=p.hand[0];first.combat_state.replay_count=1
    play(c,'fetch')
    assert p.rules.drawn_turn==1 and p.rules.osty_attacks_turn==2
    play(c,'fetch');assert p.rules.drawn_turn==2 and p.rules.osty_attacks_turn==3
    before=c.enemies[0].hp;play(c,'rattle')
    assert before-c.enemies[0].hp==28 and p.rules.osty_attacks_turn==4


def test_necro_mastery_sacrifice_and_sic_em():
    from game.headless.core.osty import summon
    c=fight('sic_em','poke','sacrifice',enemies=2);p=c.player;summon(p,5)
    apply_power(p,'necro_mastery',1)
    play(c,'sic_em');play(c,'poke')
    assert p.rules.osty['max_hp']==8
    play(c,'sacrifice')
    assert p.block==16 and p.rules.osty['hp']==0
    assert [e.hp for e in c.enemies]==[981,992]


def test_hang_doubles_its_multiplier_after_each_play():
    c=fight('hang','hang','hang')
    play(c,'hang');play(c,'hang');play(c,'hang')
    assert c.enemies[0].hp==930 and c.enemies[0].statuses.get('hang')==8


def test_scythe_growth_is_permanent_and_restores_with_run():
    from game.headless.run.engine import RunEngine
    run=RunEngine(cards=NECROBINDER_CARDS,card_ids=['the_scythe','transfigure','strike'],seed=2)
    c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000),cards_per_turn=3)
    play(c,'the_scythe');run.sync_combat_loot()
    persistent=next(x for x in run.state.deck if x.definition.definition_id=='the_scythe')
    assert persistent.permanent_damage==4 and persistent.spec.base_damage==17
    restored=RunEngine(cards=NECROBINDER_CARDS,card_ids=[]);restored.restore(json.loads(json.dumps(run.snapshot())))
    assert restored.state.deck[0].permanent_damage==4


@pytest.mark.parametrize('field,value',[('osty',{'hp':6,'max_hp':5}),('osty',{'hp':False,'max_hp':5}),('doom_applied_turn',1),('ethereal_plays',-1),('fetch_plays',['missing']),('scythe_gains',{'missing':4})])
def test_rejects_invalid_owned_necrobinder_state(field,value):
    c=fight('bodyguard');snapshot=saved(c);snapshot['player']['rules'][field]=value
    with pytest.raises(ValueError):CombatEngine(cards=NECROBINDER_CARDS).restore(snapshot)


def test_selection_rejects_different_effect_and_foreign_candidate():
    c=fight('sculpting_strike','strike','defend');play(c,'sculpting_strike')
    for mutate in (lambda s:s.update(operation='nec_transfigure'),lambda s:s.update(candidates=['missing'])):
        snapshot=saved(c);mutate(snapshot['player']['rules']['selection'])
        with pytest.raises(ValueError):CombatEngine(cards=NECROBINDER_CARDS).restore(snapshot)


@pytest.mark.parametrize('first,expected',[('envenom',{'poison':0,'doom':6}),('reaper_form',{'poison':1,'doom':0})])
def test_reaper_form_obeys_existing_power_order_with_artifact(first,expected):
    c=fight('strike');p=c.player
    for name in (first, 'reaper_form' if first=='envenom' else 'envenom'):apply_power(p,name,1)
    c.enemies[0].statuses.add('artifact',1);play(c,'strike')
    assert {k:c.enemies[0].statuses.get(k) for k in expected}==expected


@pytest.mark.parametrize('status',['doom','debilitate','hang','oblivion','sic_em','enfeebling_touch'])
def test_rend_counts_necrobinder_debuffs_and_effective_negative_strength(status):
    c=fight('rend');c.enemies[0].statuses.add(status,1)
    play(c,'rend');assert c.enemies[0].hp==980


def test_seance_records_transformation_history_without_generation_power_hooks():
    c=fight('seance','supermassive',draw=('strike',));p=c.player
    apply_power(p,'arsenal',1);apply_power(p,'pillar_of_creation',3)
    play(c,'seance')
    assert p.rules.generated_combat==1 and p.strength==0 and p.block==0
    play(c,'supermassive');assert c.enemies[0].hp==992


@pytest.mark.parametrize('task',[['nec_summon',999,'card.0',None],['nec_enemy_loss',0,999,True,'card.0'],['nec_doom_kill',0,'enemy_end']])
def test_injected_necrobinder_continuations_require_actual_producer(task):
    c=fight('snap','strike','defend');play(c,'snap');s=saved(c)
    s['player']['rules']['tasks'].insert(0,task)
    with pytest.raises(ValueError):CombatEngine(cards=NECROBINDER_CARDS).restore(s)


def test_pending_scythe_gains_cannot_forge_persistent_progress():
    from game.headless.run.engine import RunEngine
    run=RunEngine(cards=NECROBINDER_CARDS,card_ids=['the_scythe'])
    run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000))
    snapshot=json.loads(json.dumps(run.snapshot()))
    snapshot['combat']['player']['rules']['scythe_gains'][run.state.deck[0].instance_id]=999
    with pytest.raises(ValueError):RunEngine(cards=NECROBINDER_CARDS,card_ids=[]).restore(snapshot)


def test_scythe_grows_on_lethal_attack_and_keeps_growth_next_combat():
    from game.headless.run.engine import RunEngine
    run=RunEngine(cards=NECROBINDER_CARDS,card_ids=['the_scythe'])
    c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=13))
    run.apply(PlayCard(c.player.hand[0].instance_id,0))
    assert run.state.deck[0].permanent_damage==4
    c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=50))
    assert c.player.hand[0].spec.base_damage==17
    play(c,'the_scythe');assert c.enemies[0].hp==33


def test_confirmed_player_death_kills_pet():
    from game.headless.core.osty import summon
    c=fight('strike');summon(c.player,5);c.player.lose_hp(80);c.resolve_external_effect()
    assert c.done and c.player.rules.osty['hp']==0
    assert saved(clone(c))==saved(c)


def test_flatten_stays_free_after_play_then_resets_at_turn_end():
    from game.headless.core.osty import summon
    c=fight('poke','flatten');p=c.player;summon(p,9)
    play(c,'poke');flatten=next(x for x in p.hand if x.definition.definition_id=='flatten')
    assert p.card_cost(flatten)==0
    play(c,'flatten');assert p.card_cost(flatten)==0
    assert saved(clone(c))==saved(c)
    c.apply(EndTurn());assert p.card_cost(flatten)==2


def test_misery_copies_temporary_strength_once_and_restores_it_once():
    c=fight('enfeebling_touch','misery',enemies=2)
    c.enemies[0].strength=5
    play(c,'enfeebling_touch');play(c,'misery')
    assert c.enemies[1].strength==5 and c.enemies[1].statuses.get('enfeebling_touch')==8
    assert saved(clone(c))==saved(c)
    c.apply(EndTurn())
    assert c.enemies[1].strength==5 and not c.enemies[1].statuses.get('enfeebling_touch')


def test_necro_mastery_and_melancholy_see_osty_death():
    from game.headless.core.osty import summon
    c=fight('melancholy');p=c.player;summon(p,4);apply_power(p,'necro_mastery',1)
    p.take_damage(4,source=c.enemies[0]);drain(p)
    assert c.enemies[0].hp==996 and p.card_cost(p.hand[0])==2


def test_lethality_applies_only_to_first_attack_iteration_including_osty():
    from game.headless.core.osty import summon
    c=fight('poke','strike');p=c.player;summon(p,5);apply_power(p,'lethality',50)
    p.hand[0].combat_state.replay_count=1
    play(c,'poke');play(c,'strike');assert c.enemies[0].hp==979


def test_danse_uses_captured_x_after_energy_payment():
    c=fight('eradicate');c.player.energy=2;apply_power(c.player,'danse_macabre',4)
    play(c,'eradicate');assert c.player.block==4


def test_transfigure_changes_exact_selected_card_and_restores():
    c=fight('transfigure','strike','defend');play(c,'transfigure');select(c,'strike')
    chosen=next(x for x in c.player.hand if x.definition.definition_id=='strike')
    assert c.player.card_cost(chosen)==2 and chosen.combat_state.replay_count==1
    assert saved(clone(c))==saved(c)
    play(c,'strike');assert c.enemies[0].hp==988


@pytest.mark.parametrize('task', [['nec_summon', 3, 'card.0', 0], ['nec_enemy_loss', 0, 6, True, 'haunt']])
def test_completed_hit_or_untriggered_power_does_not_authorize_queued_effect(task):
    from game.headless.core.osty import summon
    c = fight('snap', 'strike', 'defend')
    summon(c.player, 5)
    c.enemies[0].statuses.add('sic_em', 3)
    apply_power(c.player, 'haunt', 6)
    play(c, 'snap')
    assert c.player.rules.osty['hp'] == 8
    snapshot = saved(c)
    snapshot['player']['rules']['tasks'].insert(0, task)
    with pytest.raises(ValueError):
        CombatEngine(cards=NECROBINDER_CARDS).restore(snapshot)


@pytest.mark.parametrize('gains', [None, [], {'card.0': '4'}])
def test_malformed_scythe_gains_raise_value_error(gains):
    snapshot = saved(fight('the_scythe'))
    snapshot['player']['rules']['scythe_gains'] = gains
    with pytest.raises(ValueError):
        CombatEngine(cards=NECROBINDER_CARDS).restore(snapshot)


def test_pending_mastery_damage_survives_puzzle_stratagem_choice_once():
    from dataclasses import asdict
    from game.headless.core.osty import summon
    from game.headless.relics.base import RelicInstance
    c = fight('strike', discard=('defend', 'strike', 'defend'))
    p = c.player
    p.rules.relics = [asdict(RelicInstance('centennial_puzzle', 'probe.relic'))]
    p.rules.relic_data = {'probe.relic': {}}
    summon(p, 5)
    apply_power(p, 'necro_mastery', 1)
    apply_power(p, 'stratagem', 1)
    p.take_damage(10, source=c.enemies[0])
    drain(p)
    assert p.rules.selection is not None
    assert p.rules.pending_events == [{
        'context': 0, 'task': ['nec_enemy_loss', 0, 5, True, 'necro_mastery'],
    }]
    other = clone(c)
    settle(c)
    settle(other)
    assert saved(c) == saved(other)
    assert c.enemies[0].hp == 995
    assert p.rules.pending_events == []
