"""Pinned Regent inventory, cross-card behavior and resumable solo execution."""

import json
from pathlib import Path
import pytest
from game.headless.cards.catalog import DEFAULT_CARDS, IRONCLAD_CARDS, REGENT_CARDS
from game.headless.cards.regent import ORDINARY_IDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection, EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.powers.ironclad import apply_power
from game.headless.core.resolution import drain


def saved(c):
    return json.loads(json.dumps(c.snapshot()))


def clone(c):
    other = CombatEngine(cards=REGENT_CARDS)
    other.restore(saved(c))
    return other


def fight(*hand, draw=(), discard=(), exhaust=(), level=0, hp=1000, enemies=1):
    ids = (*hand, *draw, *discard, *exhaust)
    c = CombatEngine(cards=REGENT_CARDS, cards_per_turn=0,
        deck_factory=lambda: [REGENT_CARDS.create(n, upgrade_level=level if i == 0 else 0, instance_id=f'card.{i}') for i, n in enumerate(ids)],
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


ROWS = json.loads((Path(__file__).parents[1]/'fixtures/headless_native_regent_values.json').read_text())['rows']


def test_complete_native_family_is_explicit_and_enabled_in_default_catalog():
    assert len(ORDINARY_IDS) == 80
    assert set(ORDINARY_IDS) == {r['id'] for r in ROWS if r['rarity'] in ('Common','Uncommon','Rare')}
    assert set(ORDINARY_IDS) <= {d.definition_id for d in DEFAULT_CARDS.definitions}
    assert not set(ORDINARY_IDS) & {d.definition_id for d in IRONCLAD_CARDS.definitions}


@pytest.mark.parametrize('row', [r for r in ROWS if r['rarity'] != 'Ancient'], ids=lambda r:r['id'])
def test_native_values_and_keywords_at_both_upgrade_levels(row):
    d = REGENT_CARDS.definition(row['id'])
    assert (d.rarity, d.pool, d.generate_in_combat) == (row['rarity'].lower(), 'token' if row['rarity']=='Token' else 'regent', row['generate'])
    for level, expected in enumerate(row['levels']):
        spec = d.levels[level]
        assert (spec.kind,spec.cost,spec.x_cost,spec.uses_target) == (row['kind'].lower(),expected['cost'],expected['x'],row['target']=='AnyEnemy')
        for field, keyword in [('exhausts','Exhaust'),('retain','Retain'),('innate','Innate'),('sly','Sly'),('ethereal','Ethereal')]:
            assert getattr(spec,field) == (keyword in expected['keywords'])
        assert (spec.star_cost,spec.star_x)==(expected['star'],expected['starX'])
        v=expected['vars']
        if 'Damage' in v: assert spec.base_damage==v['Damage']
        if 'CalculatedDamage' in v: assert spec.base_damage==v['CalculationBase']
        if 'Block' in v: assert spec.block_gain==v['Block']


@pytest.mark.parametrize('identity', ORDINARY_IDS)
@pytest.mark.parametrize('level', [0,1])
def test_every_regent_card_resumes_choices_and_three_turns(identity,level):
    c = fight(identity,'deflect','tactician', draw=('strike','defend','reflex','prepared'), discard=('slice','defend'), exhaust=('shiv',),level=level)
    play(c,identity);settle(c)
    assert not c.player.deck.in_play
    other=clone(c)
    assert saved(other)==saved(c)
    for _ in range(3):
        if c.done:break
        c.apply(EndTurn());settle(c)
        assert saved(clone(c))==saved(c)




def test_stars_legality_payment_persistence_and_no_turn_reset():
    c=fight('cloak_of_stars','devastate','venerate')
    c.player.rules.stars=0
    assert all(not isinstance(a,PlayCard) or a.instance_id=='card.2' for a in c.legal_actions())
    with pytest.raises(ValueError): c.player.play_card(0,None)
    play(c,'venerate');play(c,'cloak_of_stars')
    assert c.player.rules.stars==1 and c.player.block==7
    c.apply(EndTurn())
    assert c.player.rules.stars==1 and saved(clone(c))==saved(c)


def test_child_of_stars_pays_once_before_replayed_card_and_black_hole_after_series():
    c=fight('child_of_the_stars','black_hole','comet',enemies=2)
    play(c,'child_of_the_stars');play(c,'black_hole')
    apply_power(c.player,'duplication',1)
    play(c,'comet')
    assert c.player.rules.stars==15 and c.player.block==10
    assert c.enemies[1].hp==997  # one paid-series Black Hole, not per replay
    assert c.enemies[0].hp==915  # 33 + floor(33*1.5) +3


def test_black_hole_per_gain_event_and_blockable_unpowered():
    c=fight('black_hole','royal_gamble','venerate',enemies=2)
    play(c,'black_hole');c.player.strength=40;c.enemies[1].block=5
    play(c,'royal_gamble')
    assert c.player.rules.stars==24 and [e.hp for e in c.enemies]==[994,999]
    play(c,'venerate');assert [e.hp for e in c.enemies]==[991,996]


def test_autoplay_star_x_captures_without_payment_and_chemical_x_applies():
    from game.headless.core.resolution import start_play
    c=fight('stardust','child_of_the_stars','black_hole',enemies=2)
    play(c,'child_of_the_stars');play(c,'black_hole')
    c.player.rules.stars=2
    c.player.rules.relics.append({'definition_id':'chemical_x','instance_id':'relic.x','counter':0})
    start_play(c.player,c.player.hand[0],auto=True);drain(c.player)
    assert c.player.rules.stars==2 and c.player.block==0
    assert sum(1000-e.hp for e in c.enemies)==20


def test_void_form_ends_turn_only_then_free_first_two_manual_series():
    c=fight('void_form','cloak_of_stars','devastate','stardust','defend',draw=('strike',),level=1)
    apply_power(c.player,'retain_hand',1)
    play(c,'void_form')
    assert c.player.rules.round_number==2
    assert c.player.card_cost(c.player.hand[1])==0
    before=c.player.energy
    play(c,'devastate')
    assert c.player.energy==before and c.player.rules.stars==20
    apply_power(c.player,'duplication',1)
    play(c,'cloak_of_stars')
    assert c.player.rules.stars==20
    assert c.player.card_cost(next(x for x in c.player.hand if x.definition.definition_id=='defend'))==1
    assert saved(clone(c))==saved(c)


def test_forge_improves_all_blades_and_creates_when_all_are_exhausted():
    c=fight('spoils_of_battle',exhaust=('sovereign_blade',))
    old=c.player.deck.exhaust_pile[0]
    play(c,'spoils_of_battle')
    blades=[x for x in c.player.deck.all_cards() if x.definition.definition_id=='sovereign_blade']
    assert len(blades)==2 and all(x.combat_state.extra_damage==5 for x in blades)
    assert old in c.player.deck.exhaust_pile
    assert len({x.instance_id for x in blades})==2
    assert saved(clone(c))==saved(c)


def test_summon_forth_recovers_exhausted_blade_before_forge_without_duplicate():
    c=fight('summon_forth',exhaust=('sovereign_blade',))
    play(c,'summon_forth')
    blades=[x for x in c.player.deck.all_cards() if x.definition.definition_id=='sovereign_blade']
    assert len(blades)==1 and blades[0] in c.player.hand and blades[0].combat_state.extra_damage==8


def test_seeking_edge_sword_sage_parry_and_conqueror():
    c=fight('seeking_edge','sword_sage','parry','conqueror',enemies=2)
    for n in ('seeking_edge','sword_sage','parry','conqueror'):play(c,n)
    blade=next(x for x in c.player.hand if x.definition.definition_id=='sovereign_blade')
    assert c.player.card_cost(blade)==2 and not blade.spec.uses_target
    c.player.rules.powers['dexterity']=2
    play(c,'sovereign_blade')
    assert [e.hp for e in c.enemies]==[920,960]
    assert c.player.block==24
    c.apply(EndTurn());assert not c.enemies[0].statuses.get('conqueror')


@pytest.mark.parametrize('identity,generated', [('begone','minion_strike'),('charge','minion_dive_bomb'),('guards','minion_sacrifice')])
@pytest.mark.parametrize('level',[0,1])
def test_minion_transform_replaces_owned_instance_preserves_pile_and_upgrade(identity,generated,level):
    c=fight(identity,'strike','defend',draw=('strike','defend','anger'),level=level)
    play(c,identity)
    s=c.player.rules.selection
    if identity=='guards':
        c.apply(ChooseCombatCard('card.1'));c.apply(ChooseCombatCard('card.2'))
        c.apply(ConfirmCombatSelection())
    else:settle(c)
    pile=c.player.deck.draw_pile if identity=='charge' else c.player.hand
    created=[x for x in pile if x.definition.definition_id==generated]
    assert len(created)==(1 if identity=='begone' else 2)
    assert all(x.upgrade_level==level for x in created)
    assert c.player.rules.generated_combat == len(created)  # Native transform history.
    assert saved(clone(c))==saved(c)


def test_minion_strike_draws_and_satisfies_strike_tag():
    c=fight('minion_strike',draw=('defend',))
    play(c,'minion_strike');assert c.enemies[0].hp==994 and len(c.player.hand)==1
    assert c.player.deck.exhaust_pile[0].definition.strike


def test_decisions_plays_same_skill_three_times_even_from_exhaust():
    c=fight('decisions_decisions','adrenaline')
    play(c,'decisions_decisions');settle(c)
    assert c.player.rules.plays_finished==4 and c.player.energy==23
    assert sum(x.definition.definition_id=='adrenaline' for x in c.player.deck.exhaust_pile)==1


def test_arsenal_and_heirloom_accept_colorless_tokens_but_not_statuses():
    c=fight('arsenal','heirloom_hammer','minion_dive_bomb','debris')
    play(c,'arsenal');play(c,'heirloom_hammer')
    assert len([x for x in c.player.hand if x.definition.definition_id=='minion_dive_bomb'])==2
    assert c.player.strength==1  # generated clone
    play(c,'debris');assert c.player.strength==1
    play(c,'minion_dive_bomb');assert c.player.strength==1


def test_kingly_cards_trigger_on_draw_not_on_pile_move():
    c=fight('glimmer',draw=('kingly_kick','kingly_punch','defend'))
    play(c,'glimmer');settle(c)
    kick=next(x for x in c.player.deck.all_cards() if x.definition.definition_id=='kingly_kick')
    punch=next(x for x in c.player.deck.all_cards() if x.definition.definition_id=='kingly_punch')
    assert c.player.card_cost(kick)==3 and punch.combat_state.extra_damage==4


def test_glow_draws_now_and_next_turn_guiding_star_draws_now():
    c=fight('glow','guiding_star',draw=('strike','strike','strike','strike'))
    play(c,'glow');assert c.player.rules.drawn_combat==1 and c.player.rules.powers['draw_next_turn']==1
    play(c,'guiding_star');assert c.player.rules.drawn_combat==3
    c.apply(EndTurn());assert c.player.rules.drawn_combat==4


def test_particle_wall_returns_hand_but_corruption_exhausts_it():
    c=fight('particle_wall')
    play(c,'particle_wall');assert len(c.player.hand)==1 and c.player.rules.stars==18
    apply_power(c.player,'corruption',1);play(c,'particle_wall')
    assert not c.player.hand and len(c.player.deck.exhaust_pile)==1


def test_glitterstream_previews_next_block_with_dexterity_frail_and_unmovable():
    c=fight('glitterstream')
    apply_power(c.player,'dexterity',2);apply_power(c.player,'unmovable',1)
    c.player.statuses.add('frail',1)
    play(c,'glitterstream')
    assert c.player.block==19 and c.player.rules.powers['block_next_turn']==10
    c.apply(EndTurn());assert c.player.block==10


def test_furnace_genesis_hidden_cache_and_tyranny_setup_restore():
    c=fight('furnace','genesis','hidden_cache','tyranny',draw=('strike','defend','anger'))
    for n in ('furnace','genesis','hidden_cache','tyranny'):play(c,n)
    c.cards_per_turn=1;c.apply(EndTurn())
    assert c.player.rules.stars==26 and c.player.rules.selection['source']=='tyranny'
    assert any(x.definition.definition_id=='sovereign_blade' for x in c.player.hand)
    settle(c);assert saved(clone(c))==saved(c)


def test_foregone_conclusion_tutors_before_hand_draw_and_refill():
    c=fight('foregone_conclusion',draw=('strike','defend','anger','bash'))
    play(c,'foregone_conclusion');c.cards_per_turn=1;c.apply(EndTurn())
    assert c.player.rules.selection['source']=='foregone_conclusion'
    assert c.player.rules.drawn_combat==0
    settle(c)
    assert len(c.player.hand)==3 and c.player.rules.drawn_combat==1
    assert 'foregone_conclusion' not in c.player.rules.powers


def test_bombardment_autoplays_from_exhaust_in_preplay_every_turn():
    c=fight('bombardment',draw=('defend',))
    play(c,'bombardment')
    for _ in range(2):c.apply(EndTurn())
    assert c.enemies[0].hp==952 and c.player.rules.plays_finished==3


def test_invincible_autoplays_only_at_top_of_draw_pile_in_postplay():
    c=fight(draw=('i_am_invincible',))
    c.apply(EndTurn());assert c.player.rules.plays_finished==1
    assert c.player.hp==80  # ten block absorbs the simple enemy attack
    c=fight(draw=('i_am_invincible','strike'))
    c.apply(EndTurn());assert c.player.rules.plays_finished==0


def test_beating_shape_counts_hits_not_damage_and_excludes_own_hit():
    c=fight('celestial_might','beat_into_shape')
    c.enemies[0].block=100
    play(c,'celestial_might');play(c,'beat_into_shape')
    blade=next(x for x in c.player.hand if x.definition.definition_id=='sovereign_blade')
    assert blade.combat_state.extra_damage==20 and c.enemies[0].hp==1000


def test_radiate_and_crescent_count_real_star_history_and_star_cards():
    c=fight('venerate','radiate','crescent_spear','stardust',enemies=2)
    play(c,'venerate');play(c,'radiate')
    assert [e.hp for e in c.enemies]==[994,994]
    play(c,'crescent_spear');assert c.enemies[0].hp==982


def test_orbit_instances_have_independent_payment_counters():
    c=fight('orbit','defend','orbit','defend','defend','defend','defend')
    play(c,'orbit');play(c,'defend');play(c,'orbit')
    for _ in range(4):play(c,'defend')
    assert sorted(v for k,v in c.player.rules.auxiliaries.items() if k.startswith('orbit:'))==[4,7]
    assert c.player.energy==13
    assert saved(clone(c))==saved(c)


def test_monologue_gains_after_subsequent_plays_then_removes_exact_strength():
    c=fight('monologue','monologue','defend')
    play(c,'monologue');assert c.player.strength==0
    play(c,'monologue');assert c.player.strength==1
    play(c,'defend');assert c.player.strength==3
    c.apply(EndTurn());assert c.player.strength==0


def test_reflect_returns_only_blocked_attack_damage():
    c=fight('reflect')
    play(c,'reflect')
    hp=c.enemies[0].hp
    c.player.take_damage(20,source=c.enemies[0])
    assert c.enemies[0].hp==hp-15 and c.player.hp==75
    c.player.gain_block(10);c.player.take_damage(8,is_attack=False,source=c.enemies[0])
    assert c.enemies[0].hp==hp-15


def test_crush_dying_and_monarch_temporary_strength_respects_artifact():
    c=fight('monarchs_gaze','celestial_might','crush_under','dying_star',enemies=2)
    play(c,'monarchs_gaze');c.enemies[0].statuses.add('artifact',1)
    play(c,'celestial_might')
    assert c.enemies[0].statuses.get('monarchs_gaze_strength_down')==2
    play(c,'crush_under');play(c,'dying_star')
    assert c.enemies[0].statuses.get('crush_under')==1 and c.enemies[0].statuses.get('dying_star')==9
    c.apply(EndTurn())
    assert all(not e.statuses.get('dying_star') for e in c.enemies)


def test_transform_history_counts_for_supermassive_without_pillar_hooks():
    c=fight('pillar_of_creation','quasar','begone','strike','heirloom_hammer','supermassive')
    play(c,'pillar_of_creation');play(c,'quasar')
    assert c.player.rules.generated_combat==0
    c.apply(ConfirmCombatSelection())
    play(c,'begone');settle(c)
    assert c.player.rules.generated_combat==1 and c.player.block==0
    play(c,'heirloom_hammer');settle(c)
    assert c.player.rules.generated_combat==2 and c.player.block==3


@pytest.mark.parametrize('field,value',[('stars',-1),('stars',True),('stars_gained_turn',-1),('generated_combat','3'),('regent_hits',{'90':1}),('regent_end_requested',True)])
def test_rejects_malformed_regent_state(field,value):
    c=fight('begone','strike','defend');play(c,'begone')
    snapshot=saved(c);snapshot['player']['rules'][field]=value
    with pytest.raises(ValueError):clone_from(snapshot)


def clone_from(snapshot):
    c=CombatEngine(cards=REGENT_CARDS);c.restore(snapshot);return c


def test_arsenal_triggers_per_generated_card_not_on_play_or_transform():
    c=fight('arsenal','blade_dance','finesse','begone','defend')
    play(c,'arsenal');play(c,'blade_dance')
    assert c.player.strength==3
    play(c,'finesse');assert c.player.strength==3
    play(c,'begone');settle(c);assert c.player.strength==3


def test_sword_sage_modifies_existing_forged_and_copied_blades_once():
    from game.headless.cards.special import clone_to
    c=fight('sword_sage','sovereign_blade','spoils_of_battle')
    play(c,'sword_sage')
    blade=c.player.hand[0]
    copied=clone_to(c.player,blade,'hand')
    assert copied.combat_state.replay_count==blade.combat_state.replay_count==1
    assert c.player.card_cost(copied)==2
    assert saved(clone(c))==saved(c)


@pytest.mark.parametrize('first',['spectrum_shift','infinite_blades'])
def test_cross_family_before_draw_preserves_power_order_and_hand_overflow(first):
    c=fight(*(['strike']*9));apply_power(c.player,'retain_hand',1)
    second='infinite_blades' if first=='spectrum_shift' else 'spectrum_shift'
    apply_power(c.player,first,1);apply_power(c.player,second,1)
    c.apply(EndTurn())
    final=c.player.hand[-1]
    assert (final.definition.definition_id=='shiv') == (first=='infinite_blades')
    assert saved(clone(c))==saved(c)


def test_rejects_unowned_forge_task():
    c=fight('begone','strike','defend');play(c,'begone')
    state=saved(c);state['player']['rules']['tasks'].insert(0,['regent_forge','card.0',999])
    with pytest.raises(ValueError):clone_from(state)


def test_royalties_creates_separate_optional_reward_and_survives_restore():
    from game.headless.run.engine import RunEngine
    from game.headless.run.config import RunConfig
    from game.headless.run.actions import ChooseExtraReward
    from game.headless.run.rewards import begin_combat_rewards
    r=RunEngine(seed=5,cards=REGENT_CARDS,config=RunConfig())
    begin_combat_rewards(r.state,REGENT_CARDS,royalties=70)
    extra=r.state.pending['extra_rewards']
    assert extra[-1]==dict(source='royalties',kind='gold',offers=['royalties'],modifiers={'gold':70},resolved=False)
    restored=RunEngine(cards=REGENT_CARDS);restored.restore(json.loads(json.dumps(r.snapshot())))
    before=restored.state.gold
    restored.apply(ChooseExtraReward(len(extra)-1,'royalties'))
    assert restored.state.gold==before+70
    assert r.state.gold==before


def test_postplay_invincible_precedes_orichalcum_capture_and_visits_each_card():
    c=fight(draw=('i_am_invincible','i_am_invincible'))
    c.player.rules.relics=[dict(definition_id='orichalcum',instance_id='relic.0',counter=0)]
    c.player.end_turn()
    assert c.player.block==20 and c.player.rules.plays_finished==2
    assert not c.player.rules.relic_data['relic.0'].get('orichalcum_ready')


def test_seeking_edge_does_not_reapply_sword_sage_to_existing_blades():
    c=fight('sword_sage','sovereign_blade','seeking_edge','seeking_edge')
    play(c,'sword_sage');play(c,'seeking_edge');play(c,'seeking_edge')
    blade=c.player.hand[0]
    assert blade.combat_state.replay_count==1 and not blade.spec.uses_target


def test_lunar_make_it_so_and_pale_blue_dot_use_completed_play_history():
    c=fight('pale_blue_dot','defend','defend','defend','lunar_blast',exhaust=('make_it_so',),draw=('strike','strike','strike'))
    play(c,'pale_blue_dot')
    for _ in range(3):play(c,'defend')
    assert any(x.definition.definition_id=='make_it_so' for x in c.player.hand)
    play(c,'lunar_blast');assert c.enemies[0].hp==988
    c.apply(EndTurn());assert c.player.rules.drawn_combat==1


def test_heavenly_drill_doubles_hits_at_four_energy_and_star_x_ignores_void_free():
    c=fight('heavenly_drill');c.player.energy=4
    play(c,'heavenly_drill');assert c.player.energy==0 and c.enemies[0].hp==936
    c=fight('stardust');apply_power(c.player,'void_form',2);c.player.rules.auxiliaries['void_form']=0;c.player.rules.stars=3
    play(c,'stardust');assert c.player.rules.stars==0 and c.enemies[0].hp==985


def test_bombardment_waits_for_setup_selection_and_receives_furnace_phase_first():
    c=fight('foregone_conclusion',draw=('strike','defend','anger'),exhaust=('bombardment',))
    play(c,'foregone_conclusion');apply_power(c.player,'furnace',5)
    c.apply(EndTurn())
    assert c.player.rules.selection is not None and c.enemies[0].hp==1000
    assert any(x.definition.definition_id=='sovereign_blade' for x in c.player.hand)
    settle(c);assert c.enemies[0].hp==982


def test_regent_native_generation_choice_restores_rng_suffix():
    from game.headless.core.native_rng import NativeRng
    c=fight('quasar');c.player.deck.generation_rng=NativeRng(42)
    play(c,'quasar')
    offered=[x.definition.definition_id for x in c.player.deck.offered]
    assert len(set(offered))==3
    count=c.player.deck.generation_rng.counter
    assert count>0
    restored=clone(c)
    for engine in (c,restored):engine.apply(ConfirmCombatSelection())
    assert saved(c)==saved(restored) and c.player.deck.generation_rng.counter==count


@pytest.mark.parametrize('first',['monarchs_gaze','envenom'])
def test_after_damage_powers_keep_application_order_against_artifact(first):
    c=fight('strike')
    second='envenom' if first=='monarchs_gaze' else 'monarchs_gaze'
    apply_power(c.player,first,1);apply_power(c.player,second,1)
    c.enemies[0].statuses.add('artifact',1)
    play(c,'strike')
    expected='poison' if first=='monarchs_gaze' else 'monarchs_gaze_strength_down'
    assert c.enemies[0].statuses.get(expected)==1
    assert not c.enemies[0].statuses.get('artifact')


@pytest.mark.parametrize('first,damage',[('reflect',5),('flame_barrier',16)])
def test_retaliation_powers_preserve_order_against_slippery(first,damage):
    c=fight('defend')
    for key in (first,'flame_barrier' if first=='reflect' else 'reflect'):
        apply_power(c.player,key,4 if key=='flame_barrier' else 1)
    c.player.block=15;c.enemies[0].statuses.add('slippery',1)
    c.player.take_damage(15,source=c.enemies[0])
    assert c.enemies[0].hp==1000-damage
