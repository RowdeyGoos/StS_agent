"""Solo Ancient inventory, observable rules and saved continuations."""
import json
from dataclasses import replace
import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard, EndTurn, ChooseCombatCard, ConfirmCombatSelection
from game.headless.run.actions import (ChooseRelicCard, ChooseRelicReward, ConfirmRelicSelection,
    UseRestRelic, ChooseCookCard, ConfirmCook, RerollCardReward, SacrificeCardReward,
    ChooseShopRemoval, ChooseNode)
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.inventory import add_relic, add_potion
from game.headless.relics.base import RelicInstance
from game.headless.relics.ancient_content import ANCIENT_ADDITIONS
from game.headless.monsters.overgrowth import SimpleEnemy


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def roundtrip(run):
    clone = RunEngine(cards=run.cards)
    clone.restore(saved(run))
    assert saved(clone) == saved(run)
    assert clone.legal_actions() == run.legal_actions()
    return clone


def settle(run):
    for _ in range(100):
        if run.state.relic_work:
            work = run.state.relic_work[0]
            actions = run.legal_actions()
            action = next((a for a in actions if isinstance(a, ConfirmRelicSelection)), None)
            if action is None:
                action = next(a for a in actions if isinstance(a, ChooseRelicCard) and a.instance_id not in work['selected']) if work['kind'] == 'select' else ChooseRelicReward(None)
        elif run.combat and (run.combat.player.rules.selection is not None or run.combat.player.pending_play is not None):
            actions = run.legal_actions()
            action = ConfirmCombatSelection() if ConfirmCombatSelection() in actions else actions[0]
        else:
            return
        clone = roundtrip(run)
        run.apply(action)
        clone.apply(action)
        assert saved(run) == saved(clone)
    pytest.fail('Ancient continuation did not finish.')


def setup(*relics, cards=('strike','strike','defend','defend','bash'), draw=10, energy=3):
    run = RunEngine(card_ids=cards, config=RunConfig())
    for name in relics:
        run.obtain_relic(name)
        settle(run)
    c = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=1000), cards_per_turn=draw, energy_per_turn=energy)
    settle(run)
    return run, c.player


def play(run, name):
    c = next(c for c in run.combat.player.hand if c.definition.definition_id == name)
    run.apply(PlayCard(c.instance_id, 0 if c.spec.uses_target else None))
    return c


@pytest.mark.parametrize('name', ANCIENT_ADDITIONS)
def test_every_ancient_pickup_roundtrips(name):
    run = RunEngine.ironclad_act1(seed=13)
    from game.headless.run.state import RunPhase
    run.state.ancient_start = None
    run.state.pending = None
    run.state.phase = RunPhase.ROUTE
    run.obtain_relic(name)
    settle(run)
    roundtrip(run)


@pytest.mark.parametrize('name', ANCIENT_ADDITIONS)
def test_every_ancient_combat_turns_roundtrip(name):
    # Combat-only fixture deliberately bypasses pickup choices; acquisition is
    # exercised separately above. Preserve native persistent defaults.
    run = RunEngine(card_ids=('inflame','inflame','strike','defend','bash'), config=RunConfig())
    run.state.relics.append(RelicInstance(name, run.state.allocate_item_id(), counter=5 if name == 'pumpkin_candle' else 0))
    c = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    settle(run)
    for _ in range(3):
        clone = roundtrip(run)
        run.apply(EndTurn()); clone.apply(EndTurn())
        assert saved(run) == saved(clone)
        settle(run)


@pytest.mark.parametrize('name', ('blessed_antler','blood_soaked_rose','ectoplasm','philosophers_stone','prismatic_gem','sozu','spiked_gauntlets','velvet_choker','whispering_earring','pumpkin_candle'))
def test_energy_ancients(name):
    run,p = setup(name, cards=('dazed',)*6)
    assert p.energy == 4


@pytest.mark.parametrize('name,extra', [('fiddle',2),('snecko_eye',2),('paels_blood',1)])
def test_ancient_hand_draw(name,extra):
    run,p = setup(name,cards=('strike',)*15,draw=5)
    assert len(p.hand) == 5+extra


def test_fiddle_blocks_card_draw_but_not_next_hand():
    run,p = setup('fiddle',cards=('shrug_it_off',)*15,draw=5)
    play(run,'shrug_it_off')
    assert len(p.hand) == 6
    run.apply(EndTurn())
    assert len(p.hand) == 7


def test_pyramid_keeps_cards_but_exhausts_ethereal():
    run,p = setup('runic_pyramid',cards=('strike','dazed'),draw=2)
    strike = next(c for c in p.hand if c.definition.definition_id == 'strike')
    run.apply(EndTurn())
    assert strike in p.hand
    assert [c.definition.definition_id for c in p.deck.exhaust_pile] == ['dazed']


def test_eye_skips_enemy_side_once_and_exhausts_hand():
    run,p = setup('paels_eye',cards=('strike',)*5)
    hp=p.hp
    run.apply(EndTurn())
    assert p.hp == hp and len(p.deck.exhaust_pile) == 5 and run.combat.turn == 2
    run.apply(EndTurn())
    assert p.hp < hp


def test_throwing_axe_replays_only_first_card():
    run,p = setup('throwing_axe',cards=('strike',)*5,energy=10)
    play(run,'strike')
    assert run.combat.enemies[0].hp == 988
    play(run,'strike')
    assert run.combat.enemies[0].hp == 982


def test_choker_stops_manual_and_auto_after_six():
    run,p = setup('velvet_choker',cards=('anger',)*9,energy=10)
    for _ in range(6): play(run,'anger')
    assert not any(isinstance(a,PlayCard) for a in run.legal_actions())
    from game.headless.core.resolution import start_play,drain
    start_play(p,p.hand[0],auto=True);drain(p)
    assert p.cards_played_this_turn == 6


def test_scarf_fifth_manual_card_is_free_and_not_sixth():
    run,p = setup('brilliant_scarf',cards=('anger',)*4+('bash','strike'),energy=10)
    for _ in range(4): play(run,'anger')
    bash=next(c for c in p.hand if c.definition.definition_id=='bash')
    assert p.card_cost(bash)==0
    before=p.energy;play(run,'bash');assert p.energy==before
    strike=next(c for c in p.hand if c.definition.definition_id=='strike')
    assert p.card_cost(strike)==1


def test_music_box_copy_is_ethereal_and_only_first_attack():
    run,p=setup('music_box',cards=('strike','strike'),energy=10)
    play(run,'strike')
    assert len(p.hand)==2 and sum(c.spec.ethereal for c in p.hand)==1
    play(run,'strike')
    assert len(p.hand)==1


def test_goopy_grows_persistently_and_exhausts():
    run,p=setup('paels_claw',cards=('defend',))
    card=play(run,'defend')
    assert p.block==5 and card in p.deck.exhaust_pile
    assert run.state.deck[0].enchantment.amount==2
    roundtrip(run)


def test_soup_zero_cost_eternal_strikes_gain_three_damage():
    run,p=setup('nutritious_soup',cards=('strike',))
    card=play(run,'strike')
    assert card.cost==0 and card.spec.eternal and run.combat.enemies[0].hp==991


def test_imbed_autoplays_before_earring_and_earring_pays_resources():
    run,p=setup('electric_shrymp','whispering_earring',cards=('defend','strike','strike','strike','strike'),draw=5)
    assert p.energy==0 and p.block==5 and p.cards_played_this_turn==5
    assert not p.hand
    roundtrip(run)


def test_whistle_stuns_then_restores_the_planned_move():
    run,p=setup('tanxs_whistle',cards=('defend',),draw=10)
    enemy=run.combat.enemies[0]
    intent=enemy.intent
    play(run,'whistle')
    assert enemy.intent.kind=='stun'
    hp=p.hp;run.apply(EndTurn())
    assert p.hp==hp and enemy.intent==intent
    roundtrip(run)


def test_brightest_flame_max_hp_loss_persists_and_roundtrips():
    run,p=setup('storybook',cards=('strike',)*5)
    play(run,'brightest_flame')
    assert p.max_hp==79
    roundtrip(run)


def test_meat_cleaver_cancel_and_confirm():
    from game.headless.run import rest_site
    run=RunEngine();run.obtain_relic('meat_cleaver');rest_site.begin_rest_site(run.state)
    run.apply(UseRestRelic('cook'));roundtrip(run)
    run.apply(ChooseCookCard(run.state.deck[0].instance_id));run.apply(ChooseCookCard(None))
    assert len(run.state.deck)==10 and run.state.max_hp==80
    run.apply(UseRestRelic('cook'))
    for c in run.state.deck[:2]:run.apply(ChooseCookCard(c.instance_id))
    run.apply(ConfirmCook())
    assert len(run.state.deck)==8 and run.state.max_hp==89
    roundtrip(run)


def test_pumpkin_kindling_and_combat_expiry():
    from game.headless.run import rest_site
    from game.headless.relics.ancient_state import after_combat
    run=RunEngine();run.obtain_relic('pumpkin_candle')
    after_combat(run.state,run.cards)
    assert run.state.relics[0].counter==4
    rest_site.begin_rest_site(run.state);run.apply(UseRestRelic('kindle'))
    assert run.state.relics[0].counter==9


def test_wing_sacrifice_is_separate_from_skip_and_reroll_once():
    from game.headless.run.rewards import begin_reward, finish_reward
    from game.headless.cards.pools import REWARD_CARDS
    from game.headless.run.actions import ChooseRewardCard,ClaimGold
    run=RunEngine();run.obtain_relic('paels_wing');run.obtain_relic('driftwood')
    for _ in range(2):
        begin_reward(run.state,run.cards,gold=0,card_ids=REWARD_CARDS)
        run.apply(RerollCardReward())
        assert RerollCardReward() not in run.legal_actions()
        roundtrip(run)
        run.apply(SacrificeCardReward());settle(run)
        from game.headless.run.rewards import claim_gold
        claim_gold(run.state);finish_reward(run.state)
    assert len(run.state.relics)==3


def test_toy_box_melts_first_wax_without_reenabling_pool_entry():
    from game.headless.relics.ancient_state import after_combat
    run=RunEngine();run.obtain_relic('toy_box')
    while run.state.relic_work:
        run.apply(ChooseRelicReward(0));settle(run)
    wax=next(r for r in run.state.relics if r.data.get('_wax'))
    for _ in range(3):after_combat(run.state,run.cards)
    assert wax.data['_melted'] is True and wax in run.state.relics
    roundtrip(run)


@pytest.mark.parametrize('name,delta', [('empty_cage',-2),('biiig_hug',-4),('preserved_fog',-2),('distinguished_cape',3),('paels_horn',2),('sere_talon',5),('jewelry_box',1),('blood_soaked_rose',1),('storybook',1),('tanxs_whistle',1)])
def test_pickup_deck_changes(name,delta):
    run=RunEngine();run.obtain_relic(name);settle(run)
    assert len(run.state.deck)==10+delta


@pytest.mark.parametrize('name,count', [('yummy_cookie',4),('sand_castle',6)])
def test_pickup_upgrade_counts(name,count):
    run=RunEngine();run.obtain_relic(name);settle(run)
    assert sum(c.upgraded for c in run.state.deck)==count


def test_astrolabe_transforms_selected_cards_then_upgrades():
    run=RunEngine();original=[c.instance_id for c in run.state.deck[:3]]
    run.obtain_relic('astrolabe')
    for identity in original:run.apply(ChooseRelicCard(identity))
    run.apply(ConfirmRelicSelection())
    assert sum(c.upgraded for c in run.state.deck)==3
    assert not set(original)&{c.instance_id for c in run.state.deck}
    assert all(c.definition.rarity in ('common','uncommon','rare') for c in run.state.deck[:3])


def test_claws_preserves_upgrade_and_enchantment():
    from game.headless.enchantments.base import enchant
    run=RunEngine(card_ids=('strike','defend'))
    run.state.deck[0].upgrade();enchant(run.state.deck[0],'sharp',3)
    run.obtain_relic('claws');run.apply(ChooseRelicCard(run.state.deck[0].instance_id));run.apply(ConfirmRelicSelection())
    card=run.state.deck[0]
    assert card.definition.definition_id=='maul' and card.upgraded and card.enchantment.definition_id=='sharp'


@pytest.mark.parametrize('starter,replacement', [('bash','break'),('neutralize','suppress'),('unleash','protector'),('falling_star','meteor_shower'),('dualcast','quadcast')])
def test_archaic_tooth_all_acquired_starter_families(starter,replacement):
    run=RunEngine(card_ids=(starter,));run.state.deck[0].upgrade();run.obtain_relic('archaic_tooth')
    assert run.state.deck[0].definition.definition_id==replacement and run.state.deck[0].upgraded
    roundtrip(run)


def test_soup_rejects_removal_and_pandora_keeps_eternal_strikes():
    run=RunEngine();run.obtain_relic('nutritious_soup');run.obtain_relic('pandoras_box')
    assert sum(c.definition.definition_id=='strike' for c in run.state.deck)==5
    assert not any(c.definition.definition_id=='defend' for c in run.state.deck)


def test_paels_tooth_returns_upgraded_stored_cards_one_per_combat():
    from game.headless.relics.ancient_state import after_combat
    run=RunEngine(rng_profile='native');run.obtain_relic('paels_tooth');settle(run)
    assert len(run.state.deck)==5
    for n in range(5):
        clone=roundtrip(run)
        after_combat(run.state,run.cards);after_combat(clone.state,clone.cards)
        assert saved(run)==saved(clone) and len(run.state.deck)==6+n
    assert sum(c.upgraded for c in run.state.deck)==5


def test_signet_ectoplasm_and_sozu_block_acquisition():
    from game.headless.relics.run_rules import gain_gold
    run=RunEngine();run.obtain_relic('ectoplasm');run.obtain_relic('signet_ring');gain_gold(run.state,100)
    assert run.state.gold==0
    run.obtain_relic('sozu');before=run.state.next_item_id
    assert add_potion(run.state,'fire_potion') is None
    assert run.state.next_item_id==before and run.state.potions==[None]*3


def test_coffer_fills_added_slots_and_frond_fills_open_slots():
    run=RunEngine();run.obtain_relic('alchemical_coffer')
    assert run.state.potions[:3]==[None]*3 and all(run.state.potions[3:])
    run.obtain_relic('delicate_frond');run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    assert all(run.state.potions)


def test_black_blood_replaces_starter_in_place_and_heals_twelve():
    from game.headless.relics.base import RELICS
    run=RunEngine(hp=40);run.obtain_relic('burning_blood');run.obtain_relic('vajra');run.obtain_relic('touch_of_orobas')
    assert [r.definition_id for r in run.state.relics]==['black_blood','vajra','touch_of_orobas']
    RELICS['black_blood'].after_combat_victory(run.state)
    assert run.state.hp==52


def test_sea_glass_foreign_pool_selection_and_no_prismatic_extension():
    run=RunEngine(rng_profile='native');run.obtain_relic('prismatic_gem');run.obtain_relic('sea_glass',card_pool='silent')
    work=run.state.relic_work[0]
    assert len(work['offers'])==15 and all(run.cards.definition(o['definition_id']).pool=='silent' for o in work['offers'])
    run.apply(ChooseRelicReward(0));run.apply(ChooseRelicReward(6));roundtrip(run)
    run.apply(ConfirmRelicSelection())
    assert sum(c.definition.pool=='silent' for c in run.state.deck)==2


def test_glitter_late_enchantment_and_prismatic_reward_pools():
    from game.headless.relics.rewards import decorate,extend_pool
    from game.headless.cards.pools import REWARD_CARDS
    run=RunEngine(rng_profile='native');run.obtain_relic('prismatic_gem');run.obtain_relic('glitter');run.obtain_relic('wing_charm')
    pool=extend_pool(run.state,run.cards,REWARD_CARDS)
    assert {run.cards.definition(n).pool for n in pool}=={'ironclad','silent','regent','necrobinder','defect'}
    mods=decorate(run.state,run.cards,['anger','pommel_strike','inflame'])
    assert sorted(m['enchantment']['definition_id'] for m in mods.values())==['glam','glam','swift']


def test_legion_doubles_block_then_cools_for_two_turns():
    run,p=setup('paels_legion',cards=('defend',)*5,energy=10)
    play(run,'defend');assert p.block==10
    play(run,'defend');assert p.block==15
    run.apply(EndTurn());play(run,'defend');assert p.block==5
    run.apply(EndTurn());play(run,'defend');assert p.block==10


def test_tears_flesh_sai_and_seal_resources():
    run,p=setup('paels_tears','paels_flesh','sai',cards=('strike',)*8)
    assert p.energy==3 and p.block==7
    run.apply(EndTurn());assert p.energy==5 and p.block==7
    run.apply(EndTurn());assert p.energy==6
    run=RunEngine(gold=9);run.obtain_relic('seal_of_gold');run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000))
    assert run.state.gold==4 and run.combat.player.energy==4
    run.apply(EndTurn());assert run.state.gold==4 and run.combat.player.energy==3


def test_diamond_protects_only_turns_with_two_or_fewer_plays():
    run,p=setup('diamond_diadem',cards=('anger',)*6)
    hp=p.hp;run.apply(EndTurn());half=hp-p.hp
    run.apply(EndTurn())  # The fixture enemy blocks on its second turn.
    for _ in range(3):play(run,'anger')
    hp=p.hp;run.apply(EndTurn())
    assert half == 3 and hp-p.hp == 8


def test_toasty_exhausts_noninnate_before_draw_and_gains_strength_empty():
    run=RunEngine(card_ids=('apotheosis','strike'));run.obtain_relic('toasty_mittens')
    c=run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000))
    assert [c.definition.definition_id for c in c.player.deck.exhaust_pile]==['strike']
    assert c.player.strength==1 and c.player.hand[0].definition.definition_id=='apotheosis'
    run=RunEngine(card_ids=());run.obtain_relic('toasty_mittens');run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000))
    assert run.combat.player.strength==1


def test_jeweled_mask_random_power_is_free_and_not_a_draw():
    run,p=setup('jeweled_mask',cards=('inflame','demon_form','strike'),draw=0)
    assert len(p.hand)==1 and p.hand[0].spec.kind=='power' and p.card_cost(p.hand[0])==0
    assert p.rules.drawn_combat==0


def test_biiig_hug_adds_soot_on_each_shuffle_not_initial_setup():
    from game.headless.core.piles import shuffle
    from game.headless.core.resolution import drain
    run=RunEngine(card_ids=('strike',)*5)
    run.state.relics.append(RelicInstance('biiig_hug',run.state.allocate_item_id()))
    run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=1000));p=run.combat.player
    assert not any(c.definition.definition_id=='soot' for c in p.deck.all_cards())
    shuffle(p,include_hand=True);drain(p)
    assert sum(c.definition.definition_id=='soot' for c in p.deck.all_cards())==1


def test_war_hammer_upgrades_four_after_elite_and_not_normal_combat():
    from game.headless.relics.run_rules import victory
    run=RunEngine();run.obtain_relic('war_hammer');victory(run.state)
    assert not any(c.upgraded for c in run.state.deck)
    victory(run.state,room_kind="elite")
    assert sum(c.upgraded for c in run.state.deck)==4


def test_golden_map_and_fur_coat_marks_roundtrip_and_one_hp_encounter():
    from game.headless.run.state import RunPhase
    run=RunEngine.ironclad_act1(seed=99)
    run.state.pending=None;run.state.ancient_start=None;run.state.phase=RunPhase.ROUTE
    run.obtain_relic('fur_coat');run.obtain_relic('golden_compass')
    from game.headless.map.golden_path import KINDS
    assert tuple(n.kind for n in run.graph.nodes)==KINDS
    coat=next(r for r in run.state.relics if r.definition_id=='fur_coat')
    assert len(coat.data['coordinates'])==5
    roundtrip(run)
    run.apply(ChooseNode(run.graph.start_id))
    assert all(e.hp==1 for e in run.combat.enemies)
    roundtrip(run)


def test_parasol_buys_each_slot_once_with_courier_then_mandatory_free_removal():
    from game.headless.run import shop
    run=RunEngine(config=RunConfig(),gold=0);run.obtain_relic('lords_parasol');run.obtain_relic('the_courier')
    shop.begin(run.state,run.cards);shop.start_parasol(run.state,run.cards)
    settle(run)
    shop.resume_parasol(run.state,run.cards)
    assert run.state.pending['stage']=='remove' and run.state.gold==0
    assert ChooseShopRemoval(None) not in run.legal_actions()
    assert all(o['generation']<=1 for o in run.state.pending['offers'])
    roundtrip(run)
    run.apply(ChooseShopRemoval(run.state.deck[0].instance_id))
    assert run.state.shop_removals_used==1 and run.state.gold==0
    roundtrip(run)


@pytest.mark.parametrize('name', ('glass_eye', 'sea_glass'))
def test_uniform_ancient_offers_do_not_consume_upgrade_rolls(name):
    run = RunEngine.ironclad_act1(seed=7)
    before = run.state.rng.request_count('rewards')
    run.obtain_relic(name)
    assert run.state.rng.request_count('rewards') - before == 15
    roundtrip(run)


def test_native_coffer_generates_a_distinct_batch():
    run = RunEngine.ironclad_act1(seed=0)
    before = run.state.rng.request_count('combat_potion_generation')
    run.obtain_relic('alchemical_coffer')
    assert len({p.definition_id for p in run.state.potions[-4:]}) == 4
    assert run.state.rng.request_count('combat_potion_generation') - before == 8


@pytest.mark.parametrize('name', ('archaic_tooth', 'claws'))
def test_ancient_transform_keeps_egg_upgrade(name):
    run = RunEngine(card_ids=('bash',))
    run.obtain_relic('molten_egg')
    run.obtain_relic(name)
    if name == 'claws':
        run.apply(ChooseRelicCard(run.state.deck[0].instance_id))
        run.apply(ConfirmRelicSelection())
    assert run.state.deck[0].upgraded


@pytest.mark.parametrize('mutation', ('unallocated', 'live', 'noncanonical'))
def test_tooth_stored_identity_is_owned_and_exclusive(mutation):
    run = RunEngine(); run.obtain_relic('paels_tooth'); settle(run)
    snapshot = saved(run)
    records = next(r for r in snapshot['state']['relics'] if r['definition_id'] == 'paels_tooth')['data']['cards']
    records[0]['instance_id'] = {'unallocated': 'run.card.999999', 'live': run.state.deck[0].instance_id,
                               'noncanonical': 'run.card.00'}[mutation]
    with pytest.raises(ValueError):
        RunEngine().restore(snapshot)


def test_compass_cannot_restore_the_original_graph():
    run = RunEngine.ironclad_act1(seed=7)
    original = saved(run)['graph']
    run.obtain_relic('golden_compass')
    snapshot = saved(run); snapshot['graph'] = original
    with pytest.raises(ValueError):
        RunEngine().restore(snapshot)


def test_kaleidoscope_sacrifice_and_empty_reroll_are_atomic():
    run = RunEngine.ironclad_act1(seed=3)
    run.obtain_relic('driftwood'); run.obtain_relic('paels_wing'); run.obtain_relic('kaleidoscope')
    before = saved(run)
    with pytest.raises(ValueError, match='empty native reroll'):
        run.apply(RerollCardReward())
    assert saved(run) == before
    run.apply(SacrificeCardReward()); roundtrip(run)
    assert len(run.state.relic_work) == 1


@pytest.mark.parametrize('name', ('hefty_tablet', 'lead_paperweight', 'sea_glass'))
def test_nonreward_selectors_do_not_offer_reward_alternatives(name):
    run = RunEngine(); run.obtain_relic('driftwood'); run.obtain_relic('paels_wing'); run.obtain_relic(name)
    assert not any(isinstance(a, (RerollCardReward, SacrificeCardReward)) for a in run.legal_actions())


@pytest.mark.parametrize('name,draws', [('glass_eye', 3), ('orrery', 9)])
def test_relic_reroll_retains_source_flags_and_excludes_candy(name, draws):
    run = RunEngine.ironclad_act1(seed=2)
    run.obtain_relic('driftwood'); run.obtain_relic('lasting_candy'); run.obtain_relic(name)
    before = run.state.rng.request_count('rewards')
    run.apply(RerollCardReward())
    assert len(run.state.relic_work[0]['offers']) == 3
    assert run.state.rng.request_count('rewards') - before == draws
    roundtrip(run)


def test_reroll_factory_failure_restores_rng_and_odds():
    from game.headless.run.rewards import begin_reward
    run = RunEngine.ironclad_act1(seed=3)
    run.state.config = replace(run.state.config, reward_cards=('inflame', 'barricade', 'demon_form'))
    run.obtain_relic('driftwood'); run.obtain_relic('lasting_candy')
    begin_reward(run.state, run.cards, gold=0, card_ids=run.state.config.reward_cards)
    before = saved(run)
    with pytest.raises(ValueError, match='duplicate-power'):
        run.apply(RerollCardReward())
    assert saved(run) == before


@pytest.mark.parametrize('name', ('suppress', 'apotheosis'))
def test_ancient_innate_applies_at_both_upgrade_levels(name):
    assert all(level.innate for level in DEFAULT_CARDS.definition(name).levels)


def test_apotheosis_upgrades_cards_in_all_owned_combat_piles():
    run,p = setup(cards=('apotheosis','strike','defend'))
    strike = next(c for c in p.hand if c.definition.definition_id == 'strike')
    p.hand.remove(strike); p.deck.exhaust_pile.append(strike)
    apotheosis = play(run, 'apotheosis')
    assert not apotheosis.upgraded and all(c.upgraded for c in p.deck.all_cards() if c is not apotheosis)
    assert not any(c.upgraded for c in run.state.deck)
    roundtrip(run)


def test_maul_increases_both_hits_of_all_mauls():
    run,p = setup(cards=('maul','maul'),energy=10)
    enemy = run.combat.enemies[0]
    play(run, 'maul'); first = 1000-enemy.hp
    play(run, 'maul'); second = 1000-enemy.hp-first
    assert (first, second) == (10,12)
    roundtrip(run)


def test_relax_luminesce_and_apparition_resources():
    run,p = setup(cards=('relax','luminesce','apparition'), energy=5)
    play(run, 'luminesce'); assert p.energy == 7
    play(run, 'relax'); assert p.block == 15 and p.energy == 4
    play(run, 'apparition'); assert p.rules.powers['intangible'] == 1
    run.apply(EndTurn()); assert p.energy == 7
    roundtrip(run)


def test_melted_relics_stop_combat_hooks():
    run = RunEngine(card_ids=('strike',))
    run.obtain_relic('anchor'); run.state.relics[0].data.update(_wax=True, _melted=True)
    c = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    assert c.player.block == 0
    roundtrip(run)


def test_ectoplasm_event_gold_continuation_restores():
    from game.headless.run import events
    from game.headless.run.actions import ChooseEventOption
    run = RunEngine(gold=200); run.obtain_relic('ectoplasm')
    events.begin(run.state, 'this_or_that', cards=run.cards)
    run.apply(ChooseEventOption(run.state.pending['event_instance_id'], 'plain'))
    assert run.state.gold == 200
    roundtrip(run)


def test_growth_clones_once_and_preserves_enchantment():
    from game.headless.run import rest_site
    run = RunEngine(card_ids=('strike', 'defend'))
    run.obtain_relic('paels_growth'); settle(run)
    original = next(c for c in run.state.deck if c.enchantment)
    rest_site.begin_rest_site(run.state); run.apply(UseRestRelic('clone'))
    clones = [c for c in run.state.deck if c.enchantment]
    assert len(clones) == 2 and clones[0].instance_id != clones[1].instance_id
    assert all(c.enchantment == original.enchantment for c in clones)
    roundtrip(run)


def test_earring_resolves_armaments_selection_without_user_input():
    run,p = setup('whispering_earring', cards=('armaments', 'defend', 'strike'), energy=3)
    assert p.pending_play is None and p.rules.selection is None
    assert p.cards_played_this_turn == 3 and any(c.upgraded for c in p.deck.all_cards())
    roundtrip(run)


def test_black_star_adds_one_independent_elite_relic_reward():
    from game.headless.relics.rewards import extra_rewards
    from game.headless.encounters.catalog import ENCOUNTERS
    run = RunEngine(config=RunConfig()); run.obtain_relic('black_star')
    run.state.pending = {'relic': 'anchor'}
    rewards = extra_rewards(run.state, run.cards, next(e for e in ENCOUNTERS.values() if e.room_kind == 'elite'))
    assert len(rewards) == 1 and rewards[0]['kind'] == 'relic' and rewards[0]['offers'] != ['anchor']
    assert not extra_rewards(run.state, run.cards, next(e for e in ENCOUNTERS.values() if e.room_kind == 'combat'))


def test_multiple_imbued_skills_follow_native_pile_order():
    from game.headless.core.combat import CombatEngine
    from game.headless.enchantments.base import enchant
    cards = [DEFAULT_CARDS.create('apotheosis'), DEFAULT_CARDS.create('defend')]
    for card in cards:
        enchant(card, 'imbued')
    # Random(0) leaves this two-card fixture shuffle unchanged; Defend is top.
    c = CombatEngine(seed=0, deck_factory=lambda: cards, cards_per_turn=0,
                     enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    c.reset()
    assert c.player.block == 5  # Defend plays before Apotheosis upgrades it.
    assert next(card for card in c.player.deck.all_cards() if card.definition.definition_id == "defend").upgraded
