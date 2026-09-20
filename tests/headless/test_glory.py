"""Pinned Glory construction and source-backed combat/continuation regressions."""
from copy import deepcopy
import json
from pathlib import Path
import re
import pytest
from game.headless.core.actions import EndTurn, PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.native_service import NativeRandomService
from game.headless.encounters.glory import ENCOUNTERS, NATIVE_GLORY_ENCOUNTERS
from game.headless.encounters.randomness import EncounterRandom
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.state import RunPhase
from game.headless.run.actions import LeaveRewards

VECTORS = json.loads((Path(__file__).parents[1] / 'fixtures/headless_native_glory_vectors.json').read_text())


def saved(run): return json.loads(json.dumps(run.snapshot()))


def clone(run):
    result = RunEngine()
    result.restore(saved(run))
    assert result.legal_actions() == run.legal_actions()
    assert saved(result) == saved(run)
    return result


def step(run, action):
    other = clone(run)
    run.apply(action); other.apply(action)
    assert saved(run) == saved(other)
    clone(run)


def start(name, cards=(), *, hp=10000, draw=None, seed=7, profile='native'):
    run = RunEngine(seed=seed, max_hp=hp, config=RunConfig(), card_ids=cards, rng_profile=profile)
    run.start_combat(encounter_id='glory_' + name, cards_per_turn=min(10, len(cards)) if draw is None else draw, energy_per_turn=30)
    return run


def play(run, name, slot=0):
    card = next(c for c in run.combat.player.hand if c.definition.definition_id == name)
    step(run, PlayCard(card.instance_id, slot if card.spec.uses_target else None))


def kill(run, enemy):
    previous = enemy.hp
    enemy.hp = 0
    enemy._after_damage(previous, False)
    run.combat.resolve_external_effect()


@pytest.mark.parametrize('row', VECTORS['rows'], ids=lambda r:f"{r['seed']}-{r['floor']}-{r['encounter']}")
def test_native_construction_and_rng_suffixes(row):
    rng = NativeRandomService(row['seed'])
    context = EncounterRandom(rng.root_seed, row['floor'], row['id'].upper(), rng.stream('monster_ai'), rng.stream('niche'))
    enemies = ENCOUNTERS[NATIVE_GLORY_ENCOUNTERS[row['encounter']]](context)
    assert [type(e).__name__ for e in enemies] == [e['type'] for e in row['monsters']]
    assert [e.hp for e in enemies] == [e['hp'] for e in row['monsters']]
    def normalize(name): return re.sub('[^a-z0-9]', '', name.replace('_MOVE', '').lower())
    assert [normalize(e.intent.move_name) for e in enemies] == [normalize(e['move']) for e in row['monsters']]
    for stream, count, suffix in ((context.composition, 'compositionCounter', 'compositionSuffix'),
            (rng.stream('niche'), 'hpCounter', 'hpSuffix'), (rng.stream('monster_ai'), 'aiCounter', 'aiSuffix')):
        assert stream.counter == row[count]
        assert stream.next_double() == row[suffix]


@pytest.mark.parametrize('name', ENCOUNTERS)
@pytest.mark.parametrize('profile', ['native', 'fixture'])
def test_all_encounters_continue_through_ten_turns_and_reward_exit(name, profile):
    run = start(name.removeprefix('glory_'), profile=profile)
    for _ in range(10): step(run, EndTurn())
    for _ in range(8):
        for enemy in tuple(run.combat.enemies):
            if enemy.is_alive: kill(run, enemy)
        if run.combat.done: break
        step(run, EndTurn())
    assert run.combat.done and run.combat.winner == 'player'
    run.finish_combat()
    step(run, LeaveRewards())
    if ENCOUNTERS[name].room_kind == 'boss':
        assert run.state.phase is RunPhase.ACT_COMPLETE and run.state.act_completion.act == 3
    else: assert run.state.phase is RunPhase.ROUTE


def test_native_roster_is_complete():
    assert len(ENCOUNTERS) == 18
    assert {r['encounter'] for r in VECTORS['rows']} == set(NATIVE_GLORY_ENCOUNTERS)
    assert [sum(e.room_kind == k for e in ENCOUNTERS.values()) for k in ('combat','elite','boss')] == [12,3,3]


def settle(run):
    for _ in range(20):
        if run.combat.player.rules.selection is None: return
        legal = run.legal_actions()
        action = next((a for a in legal if isinstance(a, ConfirmCombatSelection)), None)
        step(run, action or next(a for a in legal if isinstance(a, ChooseCombatCard)))
    pytest.fail('Selection failed to settle')


def count(p, name): return sum(c.definition.definition_id == name for c in p.deck.all_cards())


def test_axebot_replacements_have_new_slots_rng_hp_and_clean_powers():
    run = start('axebots')
    p = run.combat.player
    first = run.combat.enemies[0]
    first.strength = 25; first.statuses.add('weak', 3)
    for life, stock in enumerate((1, 0), 1):
        old = run.combat.enemies[-1]
        kill(run, old)
        new = run.combat.enemies[-1]
        assert len(run.combat.enemies) == life + 1 and old.replaced
        assert new.stock == stock and new.strength == 0 and not new.statuses.get('weak')
        assert 70 <= new.hp <= 78 and new.intent.move_name == 'Boot Up'
        clone(run)
        step(run, EndTurn())
        assert new.block == 10 and new.strength == life * 3
    kill(run, run.combat.enemies[-1])
    assert run.combat.done and len(p.combat_enemies) == 3


def test_fabricator_summons_wait_for_next_turn_but_get_side_end_and_reuse_positions():
    from game.headless.monsters.glory_summons import Bot, Zapbot
    run = start('fabricator')
    p, boss = run.combat.player, run.combat.enemies[0]
    boss._intent_index = 0
    hp = p.hp
    step(run, EndTurn())
    assert p.hp == hp and len(run.combat.enemies) == 3
    assert [e.position for e in run.combat.enemies[1:]] == [0, 1]
    for e in run.combat.enemies[1:]:
        if isinstance(e, Zapbot): assert e.strength == 2
    boss._intent_index = 0
    step(run, EndTurn())
    assert p.hp < hp and boss.intent.move_name == 'Disintegrate'
    assert [e.position for e in run.combat.enemies[1:]] == [0, 1, 3, 4]
    old = run.combat.enemies[1]
    kill(run, old)
    boss._intent_index = 1
    step(run, EndTurn())
    assert run.combat.enemies[1] is old and not old.is_alive
    assert run.combat.enemies[-1].position == 0
    assert sum(isinstance(e, Bot) and e.is_alive for e in run.combat.enemies) == 4


def test_ritual_skips_application_turn_and_plating_decays_after_first_turn():
    run = start('devoted_sculptor')
    e = run.combat.enemies[0]
    step(run, EndTurn()); assert e.strength == 0
    hp = run.combat.player.hp
    step(run, EndTurn()); assert e.strength == 9 and run.combat.player.hp == hp - 12
    run = start('frog_knight')
    e = run.combat.enemies[0]
    assert e.block == 15
    for block in (15, 14, 13):
        step(run, EndTurn()); assert e.block == block
    e.hp = 94
    for _ in range(3): step(run, EndTurn())
    assert e.intent.move_name == 'Beetle Charge'
    step(run, EndTurn()); assert e.charged
    for _ in range(6):
        assert e.intent.move_name != 'Beetle Charge'
        step(run, EndTurn())


@pytest.mark.parametrize('block,pet,loss', [(0,0,4),(5,0,2),(10,0,0),(0,10,0)])
def test_paper_cuts_per_unblocked_hit_excludes_pet(block, pet, loss):
    from game.headless.core.osty import summon
    run = start('scrolls_of_biting_weak')
    p = run.combat.player
    e = run.combat.enemies[0]; e._intent_index = 1
    p.block = block
    if pet: summon(p, pet)
    maximum = p.max_hp
    e.execute_intent(p)
    assert p.max_hp == maximum - loss


def test_paper_cuts_maximum_hp_loss_can_kill_after_surviving_hit():
    run = start('scrolls_of_biting_weak', hp=2)
    p, e = run.combat.player, run.combat.enemies[0]
    p.block = 13; e._intent_index = 0
    e.execute_intent(p)
    assert p.hp == 0 and p.max_hp == 1


def test_soar_halves_powered_attack_after_vulnerable_and_leaves_unpowered_damage():
    run = start('owl_magistrate')
    p, e = run.combat.player, run.combat.enemies[0]
    e.soaring = True; e.statuses.add('vulnerable', 1)
    hp = e.hp
    e.take_damage(7, attacker_statuses=p.statuses)
    assert e.hp == hp - 5  # floor(7 * 1.5 * .5)
    e.take_damage(7, is_attack=False)
    assert e.hp == hp - 12
    clone(run)


def test_galvanized_applies_to_existing_and_generated_powers_and_uses_block():
    from game.headless.powers.hive import generate
    run = start('globe_head', ('inflame',))
    p = run.combat.player
    assert p.hand[0].combat_state.galvanized
    generate(p, 'inflame', 'hand', 1)
    assert p.hand[-1].combat_state.galvanized
    p.block = 4; hp = p.hp
    play(run, 'inflame')
    assert p.hp == hp - 2 and p.block == 0
    clone(run)


@pytest.mark.parametrize('artifact', [0,1])
def test_stolen_stats_return_only_actual_loss_and_forgotten_uses_dexterity(artifact):
    run = start('the_lost_and_forgotten')
    p = run.combat.player; p.statuses.add('artifact', artifact)
    lost, forgotten = run.combat.enemies
    step(run, EndTurn())
    assert p.strength == (0 if artifact else -2)
    assert forgotten.block == 8 and forgotten.dexterity == 2
    step(run, EndTurn()); step(run, EndTurn())
    assert forgotten.block == 10 and forgotten.dexterity == 4
    kill(run, lost)
    assert p.strength == 0
    kill(run, forgotten)
    # Native PowerCmd suppresses the refund once the last enemy dies.
    assert p.rules.powers['dexterity'] == -4
    clone(run)


def test_rampart_does_not_grant_block_during_extra_player_turn():
    from game.headless.run.inventory import add_relic
    run = RunEngine(seed=7, max_hp=1000, config=RunConfig(), card_ids=())
    add_relic(run.state, 'paels_eye', cards=run.cards)
    run.start_combat(encounter_id='glory_turret_operator', cards_per_turn=0)
    turret = run.combat.enemies[1]
    assert turret.block == 25
    step(run, EndTurn())
    assert run.combat.turn == 2 and turret.block == 25 and turret._intent_index == 0


def test_hex_and_dampen_are_owned_and_restore_upgrades_after_caster_death():
    from game.headless.powers.hive import generate
    run = start('knights', ('strike', 'defend'))
    p = run.combat.player
    strike = next(c for c in p.hand if c.definition.definition_id == 'strike')
    strike.upgrade()
    flail, spectral, magi = run.combat.enemies
    step(run, EndTurn())
    assert all(c.combat_state.hexed and c.spec.ethereal for c in p.deck.all_cards())
    step(run, EndTurn())
    assert strike.upgrade_level == 0 and strike.combat_state.dampened_levels == 1
    generate(p, 'bash', 'hand', 1)
    generated = p.hand[-1]; generated.upgrade()
    assert generated.combat_state.hexed and generated.combat_state.dampened_levels == 0
    kill(run, spectral)
    assert all(not c.combat_state.hexed for c in p.deck.all_cards())
    kill(run, magi)
    assert strike.upgrade_level == 1 and strike.combat_state.dampened_levels == 0
    assert generated.upgrade_level == 1
    clone(run)


def test_queen_binding_includes_unplayable_draws_and_blocks_end_autoplay():
    run = start('queen', ('wound', 'strike', 'strike', 'strike'), draw=4)
    p = run.combat.player; queen = run.combat.enemies[1]
    step(run, EndTurn())
    assert queen.binding and queen.bound_draws == 3
    assert sum(c.combat_state.bound for c in p.hand) == 3
    bound = next(c for c in p.hand if c.combat_state.bound and c.spec.kind == 'attack')
    bound.combat_state.replay_count = 1
    hp = run.combat.enemies[0].hp
    step(run, PlayCard(bound.instance_id, 0))
    assert run.combat.enemies[0].hp == hp - 12 and queen.bound_played
    assert all(not next(c for c in p.hand if c.instance_id == a.instance_id).combat_state.bound for a in run.legal_actions() if isinstance(a, PlayCard))
    # Leave only the blocked attack in hand, so Stampede cannot choose a different card.
    for c in tuple(p.hand):
        if not(c.combat_state.bound and c.spec.kind == 'attack'):
            p.hand.remove(c); p.deck.discard_pile.append(c)
    p.rules.powers['stampede'] = 1
    hp = run.combat.enemies[0].hp
    step(run, EndTurn())
    assert run.combat.enemies[0].hp == hp and not queen.bound_played


def test_queen_ally_death_changes_only_buff_phase_immediately_and_buff_excludes_self():
    run = start('queen')
    ally, queen = run.combat.enemies
    step(run, EndTurn()); step(run, EndTurn()); step(run, EndTurn())
    assert ally.strength == 1 and queen.strength == 0 and queen.block == 20
    kill(run, ally)
    assert queen.intent.move_name == 'Enrage'
    step(run, EndTurn()); assert queen.strength == 2
    run = start('queen')
    ally, queen = run.combat.enemies
    kill(run, ally)
    assert queen.intent.move_name == 'Puppet Strings'
    step(run, EndTurn()); step(run, EndTurn())
    assert queen.intent.move_name == 'Off With Your Head' and queen.strength == 0


def test_aeonglass_escalates_all_withers_and_six_card_counter_survives_turns():
    from game.headless.powers.hive import generate
    run = start('aeonglass', ('defend',) * 6)
    p, boss = run.combat.player, run.combat.enemies[0]
    for _ in range(5): play(run, 'defend')
    assert boss.cards_left == 1 and count(p, 'wither') == 0
    step(run, EndTurn())
    play(run, 'defend')
    assert boss.cards_left == 6 and count(p, 'wither') == 1
    step(run, EndTurn()); step(run, EndTurn())
    assert boss.wither_upgrades == 1 and boss.strength == 3
    assert all(c.combat_state.wither_level == 1 and c.spec.end_turn_damage == 6 for c in p.deck.all_cards() if c.definition.definition_id == 'wither')
    generate(p, 'wither', 'hand', 1)
    assert p.hand[-1].combat_state.wither_level == 1
    for _ in range(3): step(run, EndTurn())
    assert boss.strength == 7 and boss.wither_upgrades == 2


def test_test_subject_three_lives_painful_stabs_and_alternating_intangible():
    run = start('test_subject', ('defend',))
    p, boss = run.combat.player, run.combat.enemies[0]
    play(run, 'defend'); assert boss.strength == 2
    kill(run, boss)
    assert not run.combat.done and boss.reviving and boss.strength == 0
    assert all(not isinstance(a, PlayCard) or a.target_slot is None for a in run.legal_actions())
    step(run, EndTurn())
    assert boss.hp == 200 and boss.respawns == 1
    step(run, EndTurn())
    assert count(p, 'wound') == 3 and boss.intent.attack_count == 4
    kill(run, boss); step(run, EndTurn())
    assert boss.hp == 300 and boss.respawns == 2 and boss.nemesis_intangible
    before = boss.hp
    boss.take_damage(99, attacker_statuses=p.statuses)
    boss.take_unblockable_damage(99)
    assert boss.hp == before - 2
    step(run, EndTurn()); assert not boss.nemesis_intangible
    kill(run, boss); assert run.combat.done


def test_painful_stabs_after_attack_survives_reactive_death_and_resumable_draw():
    from game.headless.run.inventory import add_relic
    run = RunEngine(seed=7, max_hp=1000, config=RunConfig(), card_ids=('strike', 'defend'))
    add_relic(run.state, 'centennial_puzzle', cards=run.cards)
    run.start_combat(encounter_id='glory_test_subject', cards_per_turn=0)
    p, boss = run.combat.player, run.combat.enemies[0]
    kill(run, boss); step(run, EndTurn())
    boss.hp = 1
    p.rules.powers.update(thorns=2, stratagem=1)
    p.deck.discard_pile.extend(p.deck.draw_pile); p.deck.draw_pile.clear()
    hp = p.hp
    step(run, EndTurn())
    assert p.rules.selection and boss.move_interrupted and boss.reviving
    assert count(p, 'wound') == 0  # AfterAttack waits for damage reactions.
    before = saved(run)
    for stage in ('effects', 'advance'):
        bad = deepcopy(before)
        bad['combat']['player']['rules']['enemy_turn']['move']['stage'] = stage
        with pytest.raises(ValueError): run.restore(bad)
        assert saved(run) == before
    settle(run)
    assert p.hp == hp - 10 and count(p, 'wound') == 1 and boss.hp == 0
    assert boss.stab_hits == 0 and not boss.move_interrupted
    step(run, EndTurn()); assert boss.hp == 300


@pytest.mark.parametrize('field,value', [('cards_left',0),('wither_upgrades',-1),('extra_strength',1)])
def test_invalid_boss_counters_are_rejected_atomically(field, value):
    run = start('aeonglass')
    before = saved(run); bad = deepcopy(before)
    bad['combat']['enemies'][0]['state'][field] = value
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


def test_axebot_stock_follows_horn_and_cannot_be_targeted_by_earlier_autoplay():
    from game.headless.run.inventory import add_relic
    run = RunEngine(seed=2, rng_profile='native', config=RunConfig(), card_ids=['strike', 'strike'])
    add_relic(run.state, 'gremlin_horn', cards=run.cards)
    run.start_combat(encounter_id='glory_axebots', cards_per_turn=0)
    p = run.combat.player
    strike = p.deck.draw_pile.pop(); p.hand.append(strike)
    p.rules.powers['hellraiser'] = 1
    run.combat.enemies[0].hp = 1
    state = p.deck.target_rng.getstate()
    step(run, PlayCard(strike.instance_id, 0))
    assert len(run.combat.enemies) == 2 and p.rules.attacks_finished == 1
    child = run.combat.enemies[1]
    assert child.hp == child.max_hp and p.deck.target_rng.getstate() == state
    before = saved(run); bad = deepcopy(before)
    bad['combat']['enemies'][0]['state']['child_slot'] = 0
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


def test_dampen_recovery_belongs_to_original_card_and_not_clone():
    from game.headless.cards.special import clone_to
    run = start('knights', ('strike',))
    p = run.combat.player; magi = run.combat.enemies[2]
    original = p.hand[0]; original.upgrade()
    magi._intent_index = 1
    magi.after_move(p, magi.intent)
    copied = clone_to(p, original, 'hand')
    assert copied.upgrade_level == 0 and copied.combat_state.dampened_levels == 0
    clone(run)
    kill(run, magi)
    assert original.upgrade_level == 1 and copied.upgrade_level == 0
    clone(run)


def test_fabricator_four_total_creatures_force_disintegrate_without_rng():
    from game.headless.monsters.glory_summons import Zapbot, Stabbot
    run = start('fabricator')
    p, boss = run.combat.player, run.combat.enemies[0]
    for _ in range(3): boss.spawn(p, (Zapbot, Stabbot))
    state = boss.rng.getstate()
    boss.advance_intent()
    assert boss.intent.move_name == 'Disintegrate' and boss.rng.getstate() == state
    clone(run)


def test_test_subject_intangible_caps_the_boot_and_pet_attacks():
    from game.headless.run.inventory import add_relic
    run = RunEngine(seed=7, max_hp=1000, config=RunConfig(), card_ids=())
    add_relic(run.state, 'the_boot', cards=run.cards)
    run.start_combat(encounter_id='glory_test_subject', cards_per_turn=0)
    p, boss = run.combat.player, run.combat.enemies[0]
    for _ in range(2): kill(run, boss); step(run, EndTurn())
    assert boss.nemesis_intangible
    for pet in (False, True):
        before = boss.hp
        boss.take_damage(3, attacker_statuses=p.statuses, pet=pet)
        assert boss.hp == before - 1
    clone(run)


@pytest.mark.parametrize('encounter,card,field,value', [
    ('aeonglass', 'wither', 'wither_level', 999),
    ('queen', 'strike', 'bound', True),
    ('knights', 'strike', 'hexed', True),
    ('knights', 'strike', 'dampened_levels', 1),
])
def test_card_effects_require_source_history(encounter, card, field, value):
    run = start(encounter, (card,), draw=0)
    if encounter == 'queen': step(run, EndTurn())
    before = saved(run); bad = deepcopy(before)
    bad['combat']['deck']['piles']['draw_pile'][0]['combat_state'][field] = value
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


def test_dead_first_form_requires_owned_revival():
    run = start('test_subject')
    before = saved(run); bad = deepcopy(before)
    bad['combat']['enemies'][0]['state']['hp'] = 0
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


@pytest.mark.parametrize('first', ['smog','tainted','galvanized','hexed','bound'])
@pytest.mark.parametrize('second', ['smog','tainted','galvanized','hexed','bound'])
def test_first_card_affliction_cannot_be_overwritten(first, second):
    from game.headless.core.afflictions import afflict, NAMES
    from game.headless.cards.catalog import DEFAULT_CARDS
    card = DEFAULT_CARDS.create('strike')
    assert afflict(card, first)
    assert not afflict(card, second)
    assert [name for name in NAMES if getattr(card.combat_state, name)] == [first]


def test_legacy_combat_action_mask_respects_bound_card_restriction():
    from game.simulation.core import CombatEnv
    from game.headless.cards.catalog import DEFAULT_CARDS
    env = CombatEnv(seed=7, encounter_factory=ENCOUNTERS['glory_queen'],
                    deck_factory=lambda: [DEFAULT_CARDS.create('strike') for _ in range(4)],
                    player_max_hp=1000, cards_per_turn=4, max_enemy_count=2)
    env.reset()
    env.step(('end_turn',))
    index = next(i for i,c in enumerate(env.player.hand) if c.combat_state.bound)
    env.step(('play', index, 0))
    legal = env.get_legal_actions()
    assert len(legal) == 3  # One unbound card against two targets, plus end turn.
    assert all(a[0] != 'play' or not env.player.hand[a[1]].combat_state.bound for a in legal)
    mask, features = env.encode_policy_inputs()
    assert sum(mask) == 3 and len(features) == len(mask)


@pytest.mark.parametrize('scroll_hp,max_loss', [(2, 0), (8, 2)])
def test_bronze_scales_precedes_paper_cuts_and_does_not_retaliate_twice(scroll_hp, max_loss):
    from game.headless.run.inventory import add_relic
    run = RunEngine(seed=7, max_hp=80, config=RunConfig(), card_ids=())
    add_relic(run.state, 'bronze_scales')
    run.start_combat(encounter_id='glory_scrolls_of_biting_weak', cards_per_turn=0)
    player, scroll = run.combat.player, run.combat.enemies[0]
    scroll.hp = scroll_hp
    scroll._intent_index = 0
    player.block = 3
    scroll.execute_intent(player)
    assert player.hp == 69  # The in-flight Chomp lands even when Thorns kills its source.
    assert player.max_hp == 80 - max_loss
    assert scroll.hp == max(0, scroll_hp - 3)
    assert player.rules.powers['thorns'] == 3
    clone(run)


def test_fabricator_rolls_after_later_bot_dies_and_clears_pending_on_defeat():
    from game.headless.monsters.glory_summons import Stabbot, Guardbot
    from game.headless.monsters.underdocks_summons import append_child
    for fatal in (False, True):
        run = start('fabricator')
        player, boss = run.combat.player, run.combat.enemies[0]
        append_child(Guardbot, boss, player, position=0)
        append_child(Guardbot, boss, player, position=1)
        later = append_child(Stabbot, boss, player, position=3)
        later.hp = 1
        player.rules.powers['thorns'] = 3
        boss._intent_index = 2
        if fatal:
            # Survive Fabricator's 11, then die to the later bot's 11.
            player.hp = 15
        step(run, EndTurn())
        assert not later.is_alive
        assert not boss.move_roll_pending
        if fatal:
            assert run.state.phase is RunPhase.DEFEAT
        else:
            assert boss.intent.move_name in ('Fabricate', 'Fabricating Strike')
            clone(run)


def test_fabricator_rejects_unowned_deferred_roll():
    run = start('fabricator')
    before = saved(run)
    bad = deepcopy(before)
    bad['combat']['enemies'][0]['state']['move_roll_pending'] = True
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before


def test_fabricator_deferred_roll_survives_paused_later_bot_and_cannot_be_dropped():
    from game.headless.run.inventory import add_relic
    from game.headless.monsters.glory_summons import Stabbot
    from game.headless.monsters.underdocks_summons import append_child
    run = RunEngine(seed=7, max_hp=1000, config=RunConfig(), card_ids=('strike', 'defend'))
    add_relic(run.state, 'centennial_puzzle')
    run.start_combat(encounter_id='glory_fabricator', cards_per_turn=0)
    player, boss = run.combat.player, run.combat.enemies[0]
    append_child(Stabbot, boss, player, position=3)
    boss._intent_index = 0
    player.rules.powers['stratagem'] = 1
    player.deck.discard_pile.extend(player.deck.draw_pile)
    player.deck.draw_pile.clear()
    step(run, EndTurn())
    assert player.rules.selection and boss.move_roll_pending
    before = saved(run)
    bad = deepcopy(before)
    bad['combat']['enemies'][0]['state']['move_roll_pending'] = False
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before
    settle(run)
    assert not boss.move_roll_pending
    clone(run)
