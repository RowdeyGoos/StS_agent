"""Pinned Silent inventory, cross-card behavior and resumable solo execution."""

import json
from pathlib import Path
import pytest
from game.headless.cards.catalog import DEFAULT_CARDS, SILENT_CARDS
from game.headless.cards.silent import ORDINARY_IDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection, EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.powers.ironclad import apply_power
from game.headless.core.resolution import drain


def saved(c):
    return json.loads(json.dumps(c.snapshot()))


def clone(c):
    other = CombatEngine(cards=SILENT_CARDS)
    other.restore(saved(c))
    return other


def fight(*hand, draw=(), discard=(), exhaust=(), level=0, hp=1000, enemies=1):
    ids = (*hand, *draw, *discard, *exhaust)
    c = CombatEngine(cards=SILENT_CARDS, cards_per_turn=0,
        deck_factory=lambda: [SILENT_CARDS.create(n, upgrade_level=level if i == 0 else 0, instance_id=f'card.{i}') for i, n in enumerate(ids)],
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


ROWS = json.loads((Path(__file__).parents[1]/'fixtures/headless_native_silent_values.json').read_text())['rows']


def test_complete_native_family_is_explicit_and_default_pool_is_unchanged():
    assert len(ORDINARY_IDS) == 80
    assert set(ORDINARY_IDS) == {r['id'] for r in ROWS if r['rarity'] in ('Common','Uncommon','Rare')}
    assert not set(ORDINARY_IDS) & {d.definition_id for d in DEFAULT_CARDS.definitions}


@pytest.mark.parametrize('row', [r for r in ROWS if r['rarity'] != 'Ancient'], ids=lambda r:r['id'])
def test_native_values_and_keywords_at_both_upgrade_levels(row):
    d = SILENT_CARDS.definition(row['id'])
    assert (d.rarity, d.pool, d.generate_in_combat) == (row['rarity'].lower(), 'token' if row['id']=='shiv' else 'silent', row['generate'])
    for level, expected in enumerate(row['levels']):
        spec = d.levels[level]
        assert (spec.kind,spec.cost,spec.x_cost,spec.uses_target) == (row['kind'].lower(),expected['cost'],expected['x'],row['target']=='AnyEnemy')
        for field, keyword in [('exhausts','Exhaust'),('retain','Retain'),('innate','Innate'),('sly','Sly')]:
            assert getattr(spec,field) == (keyword in expected['keywords'])
        v=expected['vars']
        if 'Damage' in v: assert spec.base_damage==v['Damage']
        if 'CalculatedDamage' in v: assert spec.base_damage==v['CalculationBase']
        if 'Block' in v: assert spec.block_gain==v['Block']


@pytest.mark.parametrize('identity', ORDINARY_IDS)
@pytest.mark.parametrize('level', [0,1])
def test_every_silent_card_resumes_choices_and_three_turns(identity,level):
    c = fight(identity,'deflect','tactician', draw=('strike','defend','reflex','prepared'), discard=('slice','defend'), exhaust=('shiv',),level=level)
    if identity=='grand_finale':
        c.player.deck.discard_pile.extend(c.player.deck.draw_pile);c.player.deck.draw_pile.clear()
    play(c,identity);settle(c)
    assert not c.player.deck.in_play
    other=clone(c)
    assert saved(other)==saved(c)
    for _ in range(3):
        if c.done:break
        c.apply(EndTurn());settle(c)
        assert saved(clone(c))==saved(c)


def test_sly_manual_discard_after_draw_and_no_trigger_at_hand_flush():
    c=fight('calculated_gamble','reflex','tactician',draw=('slice','deflect','strike','defend'))
    play(c,'calculated_gamble')
    assert c.player.rules.discarded_turn==2
    assert c.player.rules.drawn_combat==4
    assert c.player.energy==21
    assert c.player.rules.plays_finished==3
    assert {x.definition.definition_id for x in c.player.hand}=={'slice','deflect','strike','defend'}
    c=fight('reflex','tactician',draw=('slice',))
    c.apply(EndTurn())
    assert c.player.rules.plays_finished==0 and c.player.rules.drawn_combat==0


def test_sly_nested_discard_choice_restores_without_repaying_energy():
    c=fight('acrobatics','prepared','slice',draw=('deflect',))
    c.player.hand[1].combat_state.sly_this_turn=True
    play(c,'acrobatics')
    select(c,'prepared')
    assert c.player.rules.selection['operation']=='discard'
    assert c.player.energy==19
    settle(c)
    assert c.player.rules.discarded_turn==2


def test_sly_survives_a_play_and_is_cleared_only_at_turn_end():
    c=fight('hand_trick','deflect','slice')
    play(c,'hand_trick');select(c,'deflect')
    card=next(x for x in c.player.hand if x.definition.definition_id=='deflect')
    play(c,'deflect');assert card.spec.sly
    c.apply(EndTurn());assert not card.spec.sly


def test_poison_tick_accelerant_block_artifact_and_damage_caps():
    c=fight('deadly_poison','accelerant')
    play(c,'accelerant');play(c,'deadly_poison')
    e=c.enemies[0];e.block=99;e.statuses.add('slippery',1)
    c.apply(EndTurn())
    assert e.hp==995 and e.statuses.get('poison')==3
    c=fight('deadly_poison');c.enemies[0].statuses.add('artifact',1)
    play(c,'deadly_poison')
    assert not c.enemies[0].statuses.get('poison') and not c.enemies[0].statuses.get('artifact')


def test_poison_kills_before_enemy_attack():
    c=fight('deadly_poison',hp=5)
    play(c,'deadly_poison');hp=c.player.hp
    result=c.apply(EndTurn())
    assert c.done and c.winner=='player' and c.player.hp==hp
    assert result.details['enemy_actions']==[]


def test_outbreak_counts_applications_and_is_unpowered_blockable():
    c=fight('outbreak','deadly_poison','deadly_poison','deadly_poison',enemies=2)
    play(c,'outbreak');c.enemies[1].block=5
    for _ in range(3):play(c,'deadly_poison')
    assert [e.hp for e in c.enemies]==[989,994]
    assert c.enemies[0].statuses.get('poison')==15
    assert c.player.rules.auxiliaries['outbreak']==0


def test_shivs_accuracy_phantom_fan_and_inky():
    c=fight('phantom_blades','accuracy','fan_of_knives','blade_of_ink',enemies=2)
    for n in ('phantom_blades','accuracy','fan_of_knives','blade_of_ink'):play(c,n)
    shivs=[x for x in c.player.hand if x.definition.definition_id=='shiv']
    assert len(shivs)==6 and all(x.spec.retain and not x.spec.uses_target for x in shivs)
    inky=next(x for x in shivs if x.enchantment)
    c.apply(PlayCard(inky.instance_id))
    assert [e.hp for e in c.enemies]==[982,982]
    assert all(e.statuses.get('weak')==1 for e in c.enemies)
    play(c,'shiv');assert [e.hp for e in c.enemies]==[974,974]


def test_knife_trap_upgrades_and_stops_when_selected_target_dies():
    c=fight('knife_trap',exhaust=('shiv','shiv'),level=1,enemies=2,hp=6)
    play(c,'knife_trap')
    assert c.enemies[0].hp==0 and c.enemies[1].hp==6
    assert c.player.rules.attacks_finished==1


def test_nightmare_captures_values_and_distinct_ids_before_next_draw():
    c=fight('nightmare','slice','deflect')
    play(c,'nightmare');select(c,'slice')
    original=next(x for x in c.player.hand if x.definition.definition_id=='slice')
    original.upgrade()
    other=clone(c)
    for x in (c,other):x.apply(EndTurn())
    assert saved(c)==saved(other)
    copies=[x for x in c.player.hand if x.definition.definition_id=='slice']
    assert len(copies)==3 and len({x.instance_id for x in copies})==3
    assert not any(x.upgraded for x in copies)


def test_tools_of_trade_draw_then_mandatory_discard_sly():
    c=fight('tools_of_the_trade',draw=('slice','tactician','deflect'))
    play(c,'tools_of_the_trade');c.cards_per_turn=1;c.apply(EndTurn())
    assert len(c.player.hand)==2 and c.player.rules.selection['source']=='tools_of_the_trade'
    other=clone(c)
    for x in (c,other):select(x,'tactician')
    assert saved(c)==saved(other) and c.player.energy==4


def test_well_laid_plans_optional_retention_expires_after_flush():
    c=fight('well_laid_plans','slice','deflect')
    play(c,'well_laid_plans');c.apply(EndTurn())
    other=clone(c)
    for x in (c,other):select(x,'slice')
    assert saved(c)==saved(other)
    assert [x.definition.definition_id for x in c.player.hand]==['slice']
    assert not c.player.hand[0].spec.retain


def test_envenom_only_unblocked_powered_attack_and_poison_reacts_per_hit():
    c=fight('envenom','dagger_spray',enemies=2)
    play(c,'envenom');c.enemies[0].block=4
    play(c,'dagger_spray')
    assert [e.statuses.get('poison') for e in c.enemies]==[1,2]


def test_burst_repeats_whole_skill_but_does_not_consume_twice():
    c=fight('burst','deadly_poison','deflect',level=1)
    play(c,'burst');play(c,'deadly_poison')
    assert c.enemies[0].statuses.get('poison')==10 and c.player.rules.powers['burst']==1
    play(c,'deflect');assert c.player.block==8 and c.player.rules.powers['burst']==0


def test_tracking_strangle_and_afterimage_capture_before_play():
    c=fight('afterimage','strangle','tracking','scare','slice')
    play(c,'afterimage');assert c.player.block==0
    play(c,'strangle');assert c.enemies[0].hp==992
    play(c,'tracking');assert c.enemies[0].hp==990
    play(c,'scare');play(c,'slice')
    assert c.enemies[0].hp==974 and c.player.block==4


def test_shadow_step_delays_double_damage_and_shadowmeld_multiplies_all_block():
    c=fight('shadow_step',draw=('slice',))
    play(c,'shadow_step');c.cards_per_turn=1;c.apply(EndTurn());play(c,'slice')
    assert c.enemies[0].hp==988
    c=fight('shadowmeld','deflect');apply_power(c.player,'afterimage',1)
    play(c,'shadowmeld');assert c.player.block==2
    play(c,'deflect');assert c.player.block==12


def test_poison_draw_powers_have_hand_draw_distinction():
    c=fight('corrosive_wave','speedster','backflip',draw=('slice','deflect'))
    play(c,'corrosive_wave');play(c,'speedster');play(c,'backflip')
    assert c.enemies[0].hp==996 and c.enemies[0].statuses.get('poison')==4


@pytest.mark.parametrize('name,expected', [('finisher',12),('flechettes',10),('memento_mori',17),('murder',4),('precise_cut',9)])
def test_history_and_hand_damage(name,expected):
    c=fight(name,'deflect','deflect')
    c.player.rules.attacks_started=c.player.rules.attacks_finished=2
    c.player.rules.discarded_turn=2;c.player.rules.drawn_combat=3
    play(c,name);assert c.enemies[0].hp==1000-expected


def test_pinpoint_discounts_skills_and_free_skill_does_not_spend_energy():
    c=fight('deflect','pinpoint','pounce','malaise')
    play(c,'deflect');pin=next(x for x in c.player.hand if x.definition.definition_id=='pinpoint')
    assert c.player.card_cost(pin)==2
    play(c,'pounce');energy=c.player.energy;play(c,'malaise')
    assert c.player.energy==energy and c.enemies[0].strength==-energy


def test_echoing_slash_repeats_for_each_kill():
    c=fight('echoing_slash',enemies=3)
    c.enemies[0].hp=c.enemies[1].hp=10
    play(c,'echoing_slash')
    assert [e.hp for e in c.enemies]==[0,0,970]
    assert c.player.rules.attacks_finished==1


def test_hunt_fatal_is_owed_without_rng_draw_and_minions_do_not_pay():
    c=fight('the_hunt',hp=10)
    rng=c.player.deck.generation_rng.getstate();play(c,'the_hunt')
    assert c.player.rules.extra_card_rewards==1
    assert c.player.deck.generation_rng.getstate()==rng
    c=fight('the_hunt',hp=10);c.enemies[0].statuses.add('minion',1);play(c,'the_hunt')
    assert c.player.rules.extra_card_rewards==0


@pytest.mark.parametrize('mutation', ['counter','blueprint','choice','captured','null_capture','task'])
def test_malformed_silent_continuation_rejected_atomically(mutation):
    c=fight('acrobatics','slice','deflect');play(c,'acrobatics');payload=saved(c)
    # Locate the combat rule object without relying on snapshot transport wrappers.
    rules=payload['player']['rules']
    if mutation=='counter':rules['discarded_turn']=-1
    elif mutation=='blueprint':rules['nightmares']=[{'definition_id':'slice'}]
    elif mutation=='choice':rules['selection']['maximum']=2
    elif mutation=='captured':rules['plays']['card.0']['silent_before']['strangle']=[-1]
    elif mutation=='null_capture':rules['plays']['card.0']['silent_before']=None
    else:rules['tasks'].insert(0,['silent_poison_tick',99])
    before=saved(c)
    with pytest.raises((ValueError,KeyError,TypeError)):c.restore(payload)
    assert saved(c)==before


def test_poison_infested_death_horn_choice_and_enemy_side_restore():
    from tests.headless.test_paused_death_hooks import setup, finish_choices, clone as clone_run, saved as save_run
    run,card=setup(cards=SILENT_CARDS,outer='deadly_poison')
    run.apply(PlayCard(card.instance_id,0))
    hp=run.combat.player.hp
    run.apply(EndTurn())
    p=run.combat.player
    assert p.rules.selection['source']=='stratagem'
    assert p.rules.enemy_turn['poison_start'] is True
    assert len(run.combat.enemies)==5
    other=clone_run(run)
    finish_choices(run,other)
    assert save_run(run)==save_run(other)
    assert p.hp==hp  # Spawned children were not in the captured side-start participants.
    assert run.combat.turn==2


def test_hunt_extra_reward_population_and_acquisition_survive_run_restore():
    from game.headless.run.engine import RunEngine
    from game.headless.run.config import RunConfig
    from game.headless.run.rewards import choose_extra
    run=RunEngine(seed=2,rng_profile='native',config=RunConfig(),cards=SILENT_CARDS,card_ids=['the_hunt'])
    run.start_combat(encounter_id='overgrowth_cubex',cards_per_turn=0)
    p=run.combat.player;p.hand[:]=p.deck.draw_pile;p.deck.draw_pile=[]
    run.combat.enemies[0].hp=10
    run.combat.enemies[0].block=0
    run.apply(PlayCard(p.hand[0].instance_id,0))
    assert run.combat is None
    extras=run.state.pending['extra_rewards']
    assert len(extras)==1 and extras[0]['source']=='the_hunt:0' and len(extras[0]['offers'])==3
    other=RunEngine(cards=SILENT_CARDS,card_ids=[]);other.restore(json.loads(json.dumps(run.snapshot())))
    identity=extras[0]['offers'][0]
    for r in (run,other):choose_extra(r.state,r.cards,0,identity)
    assert run.snapshot()==other.snapshot()


def test_silent_combat_transform_family_preserves_pinned_pool_order():
    from game.headless.generation.transforms import combat_options
    from game.headless.core.native_rng import NativeRng
    expected=[r['id'] for r in ROWS if r['rarity'] in ('Common','Uncommon','Rare') and r['generate']]
    for identity in ORDINARY_IDS:
        opts=combat_options(SILENT_CARDS,SILENT_CARDS.create(identity))
        assert [d.definition_id for d in opts]==[n for n in expected if n!=identity]
        rng=NativeRng(42);copy=NativeRng(42)
        assert [rng.choice(opts).definition_id for _ in range(4)]==[copy.choice([n for n in expected if n!=identity]) for _ in range(4)]
        assert rng.getstate()==copy.getstate()


def test_echoing_slash_does_not_count_kills_from_nested_speedster_draws():
    from game.headless.relics.base import RelicInstance
    from game.headless.relics.combat import install
    c=fight('echoing_slash',draw=('slice',),enemies=3)
    install(c.player,[RelicInstance('gremlin_horn','relic.horn')])
    apply_power(c.player,'speedster',10)
    c.enemies[0].hp=1;c.enemies[1].hp=9
    play(c,'echoing_slash')
    assert c.enemies[2].hp==970


def test_pinpoint_discount_waits_for_skill_completion_and_expires_at_cleanup():
    from game.headless.powers.ironclad import end_turn
    c=fight('acrobatics','pinpoint','slice',draw=('deflect',))
    play(c,'acrobatics')
    pinpoint=next(x for x in c.player.hand if x.definition.definition_id=='pinpoint')
    assert c.player.card_cost(pinpoint)==3
    select(c,'slice')
    assert c.player.card_cost(pinpoint)==2
    end_turn(c.player)
    assert c.player.card_cost(pinpoint)==3


def test_nightmare_captures_pinpoint_before_its_own_skill_discount():
    c=fight('nightmare','pinpoint','deflect')
    play(c,'nightmare');select(c,'pinpoint');c.apply(EndTurn())
    assert len(c.player.hand)==3
    assert all(c.player.card_cost(x)==3 for x in c.player.hand)


def test_hunt_reward_restore_rejects_unearned_extra_offer():
    from copy import deepcopy
    from game.headless.run.engine import RunEngine
    from game.headless.run.config import RunConfig
    run=RunEngine(seed=2,rng_profile='native',config=RunConfig(),cards=SILENT_CARDS,card_ids=['the_hunt'])
    run.start_combat(encounter_id='overgrowth_cubex',cards_per_turn=0)
    p=run.combat.player;p.hand[:]=p.deck.draw_pile;p.deck.draw_pile=[]
    run.combat.enemies[0].hp=10;run.combat.enemies[0].block=0
    run.apply(PlayCard(p.hand[0].instance_id,0))
    before=json.loads(json.dumps(run.snapshot()))
    payload=deepcopy(before)
    pending=payload['state']['pending']
    extra=deepcopy(pending['extra_rewards'][0]);extra['source']='the_hunt:1'
    pending['extra_rewards'].append(extra)
    with pytest.raises(ValueError):run.restore(payload)
    assert json.loads(json.dumps(run.snapshot()))==before


def test_nightmare_shivs_receive_powers_applied_after_template_capture():
    c=fight('nightmare','shiv','phantom_blades','fan_of_knives')
    play(c,'nightmare');select(c,'shiv')
    play(c,'phantom_blades');play(c,'fan_of_knives')
    c.apply(EndTurn())
    copies=[x for x in c.player.hand if x.definition.definition_id=='shiv']
    assert len(copies)==8 and all(x.spec.retain and not x.spec.uses_target for x in copies)


def test_shadow_step_does_not_double_opening_hellraiser_autoplay():
    c=fight('shadow_step',draw=('strike',))
    apply_power(c.player,'hellraiser',1);play(c,'shadow_step')
    c.cards_per_turn=1;c.apply(EndTurn())
    assert c.enemies[0].hp==994 and c.player.rules.powers['double_damage']==1


def test_infinite_blades_enters_before_hand_draw_and_nightmare_keeps_power_order():
    c=fight('infinite_blades','nightmare','deflect','slice',draw=('strike',))
    play(c,'infinite_blades');play(c,'nightmare');select(c,'slice')
    c.cards_per_turn=1;c.apply(EndTurn())
    assert [x.definition.definition_id for x in c.player.hand]==['shiv','slice','slice','slice','strike']


def test_side_start_powers_advance_while_tools_discard_is_waiting():
    c=fight('shadow_step',draw=('slice','deflect'))
    apply_power(c.player,'tools_of_the_trade',1)
    apply_power(c.player,'noxious_fumes',2)
    play(c,'shadow_step');c.cards_per_turn=1;c.apply(EndTurn())
    assert c.player.rules.selection['source']=='tools_of_the_trade'
    assert c.player.rules.powers['double_damage']==1
    assert c.enemies[0].statuses.get('poison')==2
    other=clone(c)
    for x in (c,other):select(x,'deflect');play(x,'slice')
    assert saved(c)==saved(other) and c.enemies[0].hp==988


def test_missing_preplay_capture_is_rejected_without_losing_afterimage():
    c=fight('acrobatics','slice','deflect');apply_power(c.player,'afterimage',1)
    play(c,'acrobatics');payload=saved(c)
    del payload['player']['rules']['plays']['card.0']['silent_before']
    with pytest.raises(ValueError):c.restore(payload)
    select(c,'slice');assert c.player.block==1


def test_side_start_horn_draw_refreshes_visible_hand_selector_and_restores():
    from game.headless.relics.base import RelicInstance
    from game.headless.relics.combat import install
    c=fight('deflect',draw=('strike','slice','deflect'),enemies=2)
    install(c.player,[RelicInstance('gremlin_horn','relic.horn')])
    c.enemies[0].hp=1
    for key,amount in [('tools_of_the_trade',1),('noxious_fumes',2),('outbreak',10)]:
        apply_power(c.player,key,amount)
    c.player.rules.auxiliaries['outbreak']=2;c.cards_per_turn=1;c.apply(EndTurn())
    assert c.player.rules.selection['candidates']==[x.instance_id for x in c.player.hand]
    assert len(c.player.hand)==3 and c.player.rules.selection['maximum']==1
    other=clone(c)
    for x in (c,other):select(x,'strike')
    assert saved(c)==saved(other)


def test_side_start_includes_shadow_step_autoplayed_by_tools_discard():
    c=fight('deflect',draw=('shadow_step',))
    apply_power(c.player,'tools_of_the_trade',1)
    c.player.deck.draw_pile[0].combat_state.sly_this_combat=True
    c.apply(EndTurn())
    # Single eligible discard resolves immediately; its Sly play completes
    # before the side-start listeners are enumerated.
    assert c.player.rules.selection is None
    assert c.player.rules.powers['double_damage']==1


def test_lethal_side_start_outbreak_cancels_pending_setup_and_finishes_counter():
    c=fight('tools_of_the_trade','noxious_fumes',draw=('slice','deflect','strike'),hp=10)
    play(c,'tools_of_the_trade');play(c,'noxious_fumes')
    apply_power(c.player,'outbreak',11);c.player.rules.auxiliaries['outbreak']=2
    c.cards_per_turn=1;c.apply(EndTurn())
    assert c.done and c.winner=='player'
    assert c.player.rules.selection is None and not c.player.rules.tasks
    assert c.player.rules.auxiliaries['outbreak']==0
    assert saved(clone(c))==saved(c)
