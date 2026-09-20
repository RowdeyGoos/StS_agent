"""Pinned A0 Underdocks composition, rules, continuations and reward handoffs."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.state import RunPhase
from game.headless.run.actions import ChooseExtraReward, LeaveRewards
from game.headless.encounters.underdocks import ENCOUNTERS, NATIVE_UNDERDOCKS_ENCOUNTERS
from game.headless.monsters.underdocks_summons import FatGremlin, GasBomb, TwoTailedRat


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    copy = RunEngine()
    copy.restore(saved(run))
    assert copy.legal_actions() == run.legal_actions()
    return copy


def step(run, action):
    copy = clone(run)
    run.apply(action)
    copy.apply(action)
    assert saved(copy) == saved(run)
    clone(run)


def start(name, *, cards=(), hp=10000, gold=99, seed=7, profile='native'):
    run = RunEngine(seed=seed, max_hp=hp, gold=gold, config=RunConfig(), card_ids=cards, rng_profile=profile)
    run.start_combat(encounter_id='underdocks_' + name, cards_per_turn=10 if cards else 0, energy_per_turn=20)
    return run


def play(run, name, slot=0):
    card = next(c for c in run.combat.player.hand if c.definition.definition_id == name)
    step(run, PlayCard(card.instance_id, slot if card.spec.uses_target else None))


def kill(run, enemy):
    # Synthetic native Kill equivalent for lifecycle tests; bypasses HP damage caps.
    previous = enemy.hp
    enemy.hp = 0
    enemy._after_damage(previous, False)
    run.combat.resolve_external_effect()


def finish(run):
    for _ in range(12):
        if run.combat is None:
            return
        for enemy in tuple(run.combat.enemies):
            if enemy.is_alive and not getattr(enemy, 'about_to_blow', False):
                kill(run, enemy)
        if run.combat.done:
            run.finish_combat()
        else:
            step(run, EndTurn())
    pytest.fail('Unfinished encounter.')


def test_independent_pinned_census():
    scope = json.loads((Path(__file__).parents[1] / 'fixtures/headless_underdocks_scope.json').read_text())
    assert set(scope['encounters']) == set(NATIVE_UNDERDOCKS_ENCOUNTERS)
    assert len(ENCOUNTERS) == 20
    assert {kind: sum(e.room_kind == kind for e in ENCOUNTERS.values()) for kind in ('combat', 'elite', 'boss')} == {'combat': 14, 'elite': 3, 'boss': 3}


@pytest.mark.parametrize('name', ENCOUNTERS)
@pytest.mark.parametrize('profile', ('fixture', 'native'))
def test_every_encounter_twelve_turns_and_reward_handoff(name, profile):
    run = start(name.removeprefix('underdocks_'), profile=profile)
    for _ in range(12):
        before = saved(run)
        run.legal_actions(); run.snapshot()
        assert saved(run) == before
        step(run, EndTurn())
    finish(run)
    assert run.state.phase is RunPhase.REWARD
    assert run.state.pending['encounter_id'] == name
    assert bool(run.state.pending['relic']) == (ENCOUNTERS[name].room_kind == 'elite')
    step(run, LeaveRewards())
    assert run.state.phase is (RunPhase.ACT_COMPLETE if ENCOUNTERS[name].room_kind == 'boss' else RunPhase.ROUTE)


@pytest.mark.parametrize('name', ENCOUNTERS)
def test_every_encounter_can_defeat_player(name):
    run = start(name.removeprefix('underdocks_'), hp=1)
    for _ in range(8):
        if run.state.phase is RunPhase.DEFEAT:
            break
        step(run, EndTurn())
    assert run.state.phase is RunPhase.DEFEAT
    assert not run.legal_actions()


def test_composition_and_opening_roles():
    slugs = start('corpse_slugs').combat.enemies
    assert sorted(e._intent_index for e in slugs) == [0, 1, 2]
    assert [e.name for e in start('cultists').combat.enemies] == ['Calcified Cultist', 'Damp Cultist']
    assert [e.intent.move_name for e in start('phantasmal_gardeners').combat.enemies] == ['Flail', 'Bite', 'Lash', 'Enlarge']
    assert [e.intent.move_name for e in start('toadpoles').combat.enemies] == ['Spiken', 'Whirl']
    rats = start('two_tailed_rats').combat.enemies
    assert [e.position for e in rats] == [2, 3, 4]
    assert len({e._intent_index for e in rats}) == 3


def test_slug_death_stuns_survivors_and_preserves_their_next_move():
    run = start('corpse_slugs')
    victim, *survivors = run.combat.enemies
    openings = [e._intent_index for e in survivors]
    kill(run, victim)
    assert all(e.stunned and e.strength == 4 for e in survivors)
    step(run, EndTurn())
    assert [e._intent_index for e in survivors] == openings
    assert not any(e.stunned for e in survivors)


def test_cultist_ritual_skips_incantation_turn():
    run = start('cultists')
    step(run, EndTurn())
    assert [e.strength for e in run.combat.enemies] == [0, 0]
    step(run, EndTurn())
    assert [e.strength for e in run.combat.enemies] == [2, 5]


def test_fossil_suck_counts_each_unblocked_hit_and_limits_repeats():
    run = start('fossil_stalker')
    enemy = run.combat.enemies[0]
    enemy._intent_index = 2
    step(run, EndTurn())
    assert enemy.strength == 6
    history = []
    for _ in range(60):
        history.append(enemy._intent_index)
        step(run, EndTurn())
    assert all(len(set(history[i:i + 3])) != 1 for i in range(len(history) - 2))


def test_toadpole_thorns_apply_per_hit_and_are_removed_before_spitting():
    run = start('toadpoles', cards=('twin_strike',))
    step(run, EndTurn())
    p = run.combat.player
    before = p.hp
    play(run, 'twin_strike')
    assert p.hp == before - 4
    step(run, EndTurn())
    assert run.combat.enemies[0].thorns == 0


@pytest.mark.parametrize('initial_block,expected_block,expected_damage', [(0, 6, 10), (5, 0, 5)])
def test_skittish_after_entire_attack_and_first_hit_result(initial_block, expected_block, expected_damage):
    run = start('phantasmal_gardeners', cards=('twin_strike', 'strike'))
    enemy = run.combat.enemies[0]
    enemy.block = initial_block
    before = enemy.hp
    play(run, 'twin_strike')
    assert enemy.hp == before - expected_damage
    assert enemy.block == expected_block
    play(run, 'strike')
    if not initial_block:
        assert enemy.block == 0  # Only the first attack command earns Skittish block.


def test_hardened_shell_caps_each_side_then_resets():
    run = start('skulking_colony')
    enemy = run.combat.enemies[0]
    assert enemy.take_damage(30) == 20
    assert enemy.take_unblockable_damage(30) == 0
    clone(run)
    step(run, EndTurn())
    assert enemy.take_unblockable_damage(30) == 20


def test_eel_threshold_stun_terror_and_vigor():
    run = start('terror_eel')
    enemy = run.combat.enemies[0]
    step(run, EndTurn()); step(run, EndTurn())
    assert enemy.vigor == 6 and enemy.intent.attack_damage == 22
    enemy.take_damage(70)
    assert enemy.stunned and enemy._intent_index == 2
    step(run, EndTurn())
    assert enemy.intent.move_name == 'Terror'
    step(run, EndTurn())
    assert run.combat.player.statuses.get('vulnerable') == 99
    step(run, EndTurn())
    assert enemy.vigor == 0


def test_smog_locks_other_skills_and_generated_skills_until_turn_end():
    run = start('living_fog', cards=('defend', 'shrug_it_off', 'strike'))
    step(run, EndTurn())
    play(run, 'defend')
    p = run.combat.player
    assert next(c for c in p.hand if c.definition.definition_id == 'shrug_it_off').combat_state.smog
    from game.headless.cards.colorless_effects import create
    generated = create(p, run.cards.definition('defend'))
    assert generated.combat_state.smog
    assert not any(isinstance(a, PlayCard) and a.instance_id == generated.instance_id for a in run.legal_actions())
    step(run, EndTurn())
    assert not any(c.combat_state.smog for c in p.deck.all_cards())
    assert any(isinstance(e, GasBomb) for e in run.combat.enemies)


def test_soul_fysh_beckon_piles_intangible_and_expiry():
    run = start('soul_fysh')
    step(run, EndTurn())
    p = run.combat.player
    assert [c.definition.definition_id for c in p.deck.draw_pile] == ['beckon']
    assert [c.definition.definition_id for c in p.deck.discard_pile] == ['beckon']
    for _ in range(3): step(run, EndTurn())
    enemy = run.combat.enemies[0]
    assert enemy.intangible == 1
    assert enemy.take_damage(30) == 1
    assert enemy.take_unblockable_damage(30) == 1
    step(run, EndTurn())
    assert enemy.intangible == 0


@pytest.mark.parametrize('wake_by_damage', [False, True])
def test_matriarch_sleep_and_plating(wake_by_damage):
    run = start('lagavulin_matriarch')
    enemy = run.combat.enemies[0]
    assert enemy.block == 12
    if wake_by_damage:
        enemy.take_damage(13)
        assert enemy.stunned and enemy.asleep == enemy.plating == 0
        step(run, EndTurn())
    else:
        for _ in range(3): step(run, EndTurn())
        assert enemy.asleep == enemy.plating == 0
    assert enemy.intent.move_name == 'Slash'
    hp = run.combat.player.hp
    step(run, EndTurn())
    assert run.combat.player.hp == hp - 19


def test_giant_lethal_hit_preserves_one_stun_turn_then_explodes():
    run = start('waterfall_giant')
    step(run, EndTurn())
    enemy = run.combat.enemies[0]
    kill(run, enemy)
    assert not run.combat.done and enemy.hp == enemy.max_hp == 999999999
    assert enemy.intent.move_name == 'About to Blow'
    hp = run.combat.player.hp
    step(run, EndTurn())
    assert run.combat.player.hp == hp and enemy.intent.attack_damage == 15
    step(run, EndTurn())
    assert run.state.phase is RunPhase.REWARD and run.state.hp == hp - 15


@pytest.mark.parametrize('escape,initial_gold', [(False, 99), (True, 99), (True, 0)])
def test_merc_stolen_gold_recovery_or_escape(escape, initial_gold):
    run = start('gremlin_merc', gold=initial_gold)
    step(run, EndTurn())
    assert run.state.gold == max(0, initial_gold - 20)
    kill(run, run.combat.enemies[0])
    assert [e.name for e in run.combat.enemies[1:]] == ['Sneaky Gremlin', 'Fat Gremlin']
    fat = run.combat.enemies[2]
    step(run, EndTurn())  # Actual spawned/stun turn.
    if escape:
        step(run, EndTurn())
        assert fat.escaped
    else:
        kill(run, fat)
    kill(run, run.combat.enemies[1])
    run.finish_combat()
    clone(run)
    pending = run.state.pending
    if escape:
        assert not any(r['source'] == 'stolen_gold' for r in pending['extra_rewards'])
        assert pending['gold'] == 0 if initial_gold else 5 <= pending['gold'] <= 10
    else:
        assert run.state.gold == 79
        index = next(i for i, r in enumerate(pending['extra_rewards']) if r['source'] == 'stolen_gold')
        step(run, ChooseExtraReward(index, 'stolen_gold'))
        assert run.state.gold == 99


@pytest.mark.parametrize('power,expected', [('smoggy', 0), ('strength', 0), ('dexterity', 0)])
def test_artifact_blocks_new_debuffs(power, expected):
    from game.headless.powers.underdocks import apply_smoggy, stat_loss
    run = start('living_fog')
    p = run.combat.player
    p.statuses.add('artifact', 1)
    apply_smoggy(p) if power == 'smoggy' else stat_loss(p, power, 2)
    assert p.statuses.get('artifact') == 0
    assert (p.strength if power == 'strength' else p.rules.powers.get(power, 0)) == expected
    clone(run)


def test_toad_thorns_target_pet_uses_shared_block_and_precedes_target_death():
    from game.headless.core.osty import summon
    run = start('toadpoles')
    p, enemy = run.combat.player, run.combat.enemies[0]
    summon(p, 5)
    p.block = 2
    enemy.thorns = 2
    enemy.take_damage(1, pet=True)
    assert p.block == 0 and p.rules.osty['hp'] == 5
    p.rules.powers.update(buffer=1, intangible=1)
    enemy.take_damage(1, pet=True)
    assert p.rules.osty['hp'] == 3 and p.rules.powers['buffer'] == 1
    p.rules.powers.pop('buffer'); p.rules.powers.pop('intangible')
    hp = p.hp
    enemy.take_damage(1, attacker_statuses=p.statuses, powered=False)
    assert p.hp == hp
    enemy.hp = 1
    enemy.take_damage(1, attacker_statuses=p.statuses)
    assert enemy.hp == 0 and p.hp == hp - 2
    clone(run)


@pytest.mark.parametrize('name', ['gremlin_merc', 'waterfall_giant'])
def test_live_monster_cannot_restore_or_execute_death_task(name):
    from game.headless.core.resolution import execute
    run = start(name, cards=('armaments', 'strike', 'defend'))
    play(run, 'armaments')
    assert run.combat.player.pending_play is not None
    snapshot = saved(run)
    snapshot['combat']['player']['rules']['tasks'].append(['monster_death', 0])
    with pytest.raises(ValueError):
        RunEngine().restore(snapshot)
    with pytest.raises(ValueError):
        execute(run.combat.player, ['monster_death', 0])


def test_giant_reactive_death_cannot_skip_about_to_blow():
    run = start('waterfall_giant')
    step(run, EndTurn())
    enemy, p = run.combat.enemies[0], run.combat.player
    enemy.hp = 1
    p.rules.powers['thorns'] = 1
    step(run, EndTurn())
    assert enemy.intent.move_name == 'About to Blow' and enemy.steam == 18
    hp = p.hp
    step(run, EndTurn())
    assert p.hp == hp and enemy.intent.move_name == 'Explode'
    assert enemy.intent.attack_damage == 18
    step(run, EndTurn())
    assert run.state.phase is RunPhase.REWARD


def test_eel_reactive_shriek_preserves_stun_then_terror():
    run = start('terror_eel')
    enemy, p = run.combat.enemies[0], run.combat.player
    enemy.hp = 71
    p.rules.powers['thorns'] = 1
    step(run, EndTurn())
    assert enemy.stunned
    hp = p.hp
    step(run, EndTurn())
    assert p.hp == hp and enemy.intent.move_name == 'Terror'
    step(run, EndTurn())
    assert p.statuses.get('vulnerable') == 99


def test_fossil_suck_counts_damage_before_fairy_revives_player():
    from game.headless.run.inventory import add_potion
    run = RunEngine(seed=7, max_hp=80, config=RunConfig(), card_ids=(), rng_profile='native')
    add_potion(run.state, 'fairy_in_a_bottle')
    run.start_combat(encounter_id='underdocks_fossil_stalker', cards_per_turn=0)
    run.combat.player.hp = 1
    step(run, EndTurn())
    assert run.combat.player.hp == 24 and run.combat.enemies[0].strength == 3


def test_fog_death_removes_bombs_without_extra_turn_or_reward():
    run = start('living_fog')
    step(run, EndTurn()); step(run, EndTurn())
    assert len(run.combat.enemies) == 2
    bomb = run.combat.enemies[1]
    assert isinstance(bomb, GasBomb) and bomb.hp == 7
    kill(run, run.combat.enemies[0])
    assert bomb.hp == 0 and run.combat.done
    run.finish_combat()
    clone(run)


def test_rat_summons_use_empty_positions_without_reindexing_dead_slots():
    run = start('two_tailed_rats')
    rats = run.combat.enemies
    original = tuple(rats)
    kill(run, rats[1])
    for _ in range(20):
        step(run, EndTurn())
    assert tuple(rats[:3]) == original
    assert len(rats) == 6  # Three calls total, including the vacated initial position.
    living = [e for e in rats if e.is_alive]
    assert sorted(e.position for e in living) == list(range(5))
    assert {e.summon_count for e in living} == {3}
    assert sum(e.summoned_once for e in rats) == 3


def test_stolen_gold_reward_consumes_fixed_amount_population_draw():
    run = start('gremlin_merc')
    step(run, EndTurn())
    finish(run)
    # Ordinary gold and the stolen-back fixed amount both populate from Rewards.
    assert run.state.rng.request_count('reward_gold') >= 2
    reward = next(r for r in run.state.pending['extra_rewards'] if r['source'] == 'stolen_gold')
    assert reward['modifiers'] == {'gold': 20}


@pytest.mark.parametrize('name', ['terror_eel', 'waterfall_giant'])
def test_forced_phase_restore_while_reactive_shuffle_is_pending(name):
    from game.headless.run.inventory import add_relic
    from game.headless.core.actions import ChooseCombatCard
    run = RunEngine(seed=7, max_hp=1000, config=RunConfig(), card_ids=('strike', 'defend'))
    add_relic(run.state, 'centennial_puzzle', cards=run.cards)
    run.start_combat(encounter_id='underdocks_' + name, cards_per_turn=0)
    p, enemy = run.combat.player, run.combat.enemies[0]
    p.rules.powers.update(thorns=2, stratagem=1)
    p.deck.discard_pile.extend(p.deck.draw_pile); p.deck.draw_pile.clear()
    if name == 'terror_eel':
        enemy.hp = 71
    else:
        enemy.hp, enemy.steam, enemy._intent_index = 1, 15, 1
    step(run, EndTurn())
    assert p.rules.selection is not None and enemy.move_interrupted
    from game.headless.core.actions import ConfirmCombatSelection
    for _ in range(6):
        if p.rules.selection is None:
            break
        legal = run.legal_actions()
        choice = next((a for a in legal if isinstance(a, ConfirmCombatSelection)), None)
        step(run, choice or next(a for a in legal if isinstance(a, ChooseCombatCard)))
    assert not enemy.move_interrupted
    assert enemy.stunned if name == 'terror_eel' else enemy.intent.move_name == 'About to Blow'


@pytest.mark.parametrize('name', ['fiend_fire', 'volley', 'stardust', 'shiv', 'the_hunt', 'echoing_slash', 'knockout_blow', 'fisticuffs', 'omnislice', 'hand_of_greed'])
def test_custom_card_attacks_trigger_skittish(name):
    run = start('phantasmal_gardeners', cards=(name, 'defend'))
    p = run.combat.player
    p.energy = 1 if name == 'volley' else 10
    p.rules.stars = 1
    if name == 'knockout_blow':
        run.combat.enemies[0].hp = run.combat.enemies[0].max_hp = 100
    play(run, name)
    assert any(e.skittish_used and e.block == 6 for e in run.combat.enemies if e.is_alive)


def test_suspended_attack_requires_its_owned_completion_task():
    from game.headless.run.inventory import add_relic
    run = RunEngine(seed=7, max_hp=1000, config=RunConfig(), card_ids=('strike', 'bash', 'defend'))
    add_relic(run.state, 'hand_drill', cards=run.cards)
    run.start_combat(encounter_id='underdocks_phantasmal_gardeners', cards_per_turn=10)
    p = run.combat.player
    p.rules.powers.update(vicious=1, stratagem=1)
    for card in tuple(p.hand):
        if card.definition.definition_id != 'strike':
            p.hand.remove(card); p.deck.discard_pile.append(card)
    run.combat.enemies[0].block = 1
    play(run, 'strike')
    assert p.rules.selection is not None
    for duplicate in (False, True):
        snap = saved(run)
        tasks = snap['combat']['player']['rules']['tasks']
        end = next(t for t in tasks if t[0] == 'end_card_attack')
        tasks.append(end) if duplicate else tasks.remove(end)
        with pytest.raises(ValueError):
            RunEngine().restore(snap)


def test_first_skill_generated_card_enters_smogged():
    run = start('living_fog', cards=('distraction',))
    step(run, EndTurn())
    play(run, 'distraction')
    generated = [c for c in run.combat.player.deck.all_cards() if c.definition.definition_id != 'distraction']
    assert generated and all(c.combat_state.smog for c in generated)


def test_random_multihit_waits_until_whole_attack_to_grant_skittish():
    run = start('phantasmal_gardeners', cards=('sword_boomerang',))
    for enemy in tuple(run.combat.enemies[1:]):
        kill(run, enemy)
    enemy = run.combat.enemies[0]
    enemy.hp = enemy.max_hp = 1000
    play(run, 'sword_boomerang')
    assert enemy.hp == 991 and enemy.block == 6 and enemy.skittish_used


def test_giant_revival_removes_ordinary_powers_before_explosion():
    run = start('waterfall_giant')
    step(run, EndTurn())
    enemy = run.combat.enemies[0]
    enemy.apply_status('weak', 3)
    enemy.apply_status('vulnerable', 3)
    enemy.apply_status('dark_shackles', 4)
    enemy.strength = 8
    kill(run, enemy)
    assert enemy.strength == 0 and not enemy.statuses._counts
    assert enemy.steam == 15 and enemy.intent.move_name == 'About to Blow'
    hp = run.combat.player.hp
    step(run, EndTurn())
    assert enemy.intent.attack_damage == 15
    step(run, EndTurn())
    assert run.state.phase is RunPhase.REWARD and run.state.hp == hp - 15
