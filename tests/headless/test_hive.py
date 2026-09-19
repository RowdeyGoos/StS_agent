"""Pinned Hive construction vectors and synthetic rule/continuation regressions."""
from copy import deepcopy
import json
from pathlib import Path
import re
import pytest
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn, PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.native_service import NativeRandomService
from game.headless.encounters.hive import ENCOUNTERS, NATIVE_HIVE_ENCOUNTERS
from game.headless.encounters.randomness import EncounterRandom
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.state import RunPhase
from game.headless.run.actions import LeaveRewards, ChooseExtraReward

VECTORS = json.loads((Path(__file__).parents[1] / 'fixtures/headless_native_hive_vectors.json').read_text())


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other = RunEngine()
    other.restore(saved(run))
    assert other.legal_actions() == run.legal_actions()
    assert saved(other) == saved(run)
    return other


def step(run, action):
    other = clone(run)
    run.apply(action)
    other.apply(action)
    assert saved(other) == saved(run)
    clone(run)


def start(name, cards=(), *, hp=10000, draw=None, seed=7, profile='native'):
    run = RunEngine(seed=seed, max_hp=hp, config=RunConfig(), card_ids=cards, rng_profile=profile)
    run.start_combat(encounter_id='hive_' + name, cards_per_turn=min(10, len(cards)) if draw is None else draw, energy_per_turn=30)
    return run


def play(run, name, slot=0):
    card = next(c for c in run.combat.player.hand if c.definition.definition_id == name)
    step(run, PlayCard(card.instance_id, slot if card.spec.uses_target else None))


def choose(run, name):
    card = next(c for c in run.combat.player.deck.offered if c.definition.definition_id == name)
    step(run, ChooseCombatCard(card.instance_id))
    step(run, ConfirmCombatSelection())


def kill(run, enemy):
    previous = enemy.hp
    enemy.hp = 0
    enemy._after_damage(previous, False)
    run.combat.resolve_external_effect()


def end_or_choose(run):
    if run.combat.player.rules.selection:
        choose(run, 'disintegration')
    else:
        step(run, EndTurn())


@pytest.mark.parametrize('row', VECTORS['rows'], ids=lambda r:f"{r['seed']}-{r['floor']}-{r['encounter']}")
def test_native_construction_and_rng_suffixes(row):
    rng = NativeRandomService(row['seed'])
    context = EncounterRandom(rng.root_seed, row['floor'], row['id'].upper(), rng.stream('monster_ai'), rng.stream('niche'))
    enemies = ENCOUNTERS[NATIVE_HIVE_ENCOUNTERS[row['encounter']]](context)
    assert [type(e).__name__ for e in enemies] == [e['type'] for e in row['monsters']]
    assert [e.hp for e in enemies] == [e['hp'] for e in row['monsters']]
    def normalized(n):
        return re.sub('[^a-z]', '', n.replace('TOXIC_SPIT_MOVE', 'Spit').replace('_MOVE', '').lower())
    assert [normalized(e.intent.move_name) for e in enemies] == [normalized(e['move']) for e in row['monsters']]
    for prefix, stream in [('composition', context.composition), ('hp', rng.stream('niche')), ('ai', rng.stream('monster_ai'))]:
        assert stream.counter == row[prefix + 'Counter']
        assert stream.next_double() == row[prefix + 'Suffix']


def test_native_census_and_generation_scope():
    assert len(ENCOUNTERS) == 20
    assert set(NATIVE_HIVE_ENCOUNTERS) == {r['encounter'] for r in VECTORS['rows']}
    assert [sum(e.room_kind == kind for e in ENCOUNTERS.values()) for kind in ('combat', 'elite', 'boss')] == [14, 3, 3]
    from game.headless.encounters.progression import native_ids
    assert not set(ENCOUNTERS) & set(native_ids('overgrowth').values())
    assert not set(ENCOUNTERS) & set(native_ids('underdocks').values())
    assert all(e.act == 2 for e in ENCOUNTERS.values())


@pytest.mark.parametrize('encounter', ENCOUNTERS)
@pytest.mark.parametrize('profile', ('fixture', 'native'))
def test_every_encounter_trajectory_choices_restore_and_terminal(encounter, profile):
    run = start(encounter.removeprefix('hive_'), profile=profile)
    for _ in range(14):
        if run.combat is None:
            break
        before = saved(run)
        run.legal_actions(); run.snapshot()
        assert saved(run) == before
        end_or_choose(run)
    if run.combat is not None:
        for e in tuple(run.combat.enemies):
            if e.is_alive:
                kill(run, e)
        assert run.combat.done
        run.finish_combat()
    clone(run)
    if encounter == 'hive_the_insatiable':
        assert run.state.phase is RunPhase.DEFEAT
    else:
        assert run.state.phase is RunPhase.REWARD
        assert run.state.act_index == 1
        step(run, LeaveRewards())
        if ENCOUNTERS[encounter].room_kind == 'boss':
            assert run.state.act_completion.act == 2
            assert run.state.phase is RunPhase.ACT_COMPLETE


def test_rock_fully_blocked_hit_stuns_then_recovers():
    run = start('bowlbugs_weak')
    rock = run.combat.enemies[0]
    run.combat.player.block = 15
    step(run, EndTurn())
    assert rock.intent.move_name == 'Dizzy'
    step(run, EndTurn())
    assert rock.intent.move_name == 'Headbutt'


def test_exoskeleton_cap_precedes_block_but_does_not_cap_hp_loss():
    run = start('exoskeletons')
    e = run.combat.enemies[0]
    e.block = 7
    hp = e.hp
    assert e.take_damage(100, is_attack=False) == 2
    assert e.block == 0 and e.hp == hp - 2
    assert e.take_unblockable_damage(10) == 10
    clone(run)


def test_tender_counts_each_card_and_restores_even_artifact_blocked_stat_loss():
    run = start('hunter_killer', ('defend', 'strike'))
    step(run, EndTurn())
    p = run.combat.player
    p.statuses.add('artifact', 1)
    play(run, 'defend')
    assert p.strength == 0 and p.rules.powers['dexterity'] == -1
    play(run, 'strike')
    assert p.strength == -1 and p.rules.powers['dexterity'] == -2
    step(run, EndTurn())
    assert p.strength == 1 and p.rules.powers['dexterity'] == 0


def test_curl_up_waits_for_whole_multihit_card_and_only_triggers_once():
    run = start('louse_progenitor', ('twin_strike', 'strike'))
    e = run.combat.enemies[0]
    hp = e.hp
    play(run, 'twin_strike')
    assert e.hp == hp - 10 and e.block == 14
    play(run, 'strike')
    assert e.block == 8 and not e.curl_up


def test_personal_hive_triggers_each_powered_hit_even_fully_blocked():
    run = start('entomancer', ('twin_strike',))
    e, p = run.combat.enemies[0], run.combat.player
    e.block = 99
    before = run.state.rng.request_count('shuffle')
    play(run, 'twin_strike')
    assert [c.definition.definition_id for c in p.deck.draw_pile] == ['dazed', 'dazed']
    assert run.state.rng.request_count('shuffle') == before + 2
    e.take_damage(1, is_attack=False)
    assert len(p.deck.draw_pile) == 2


def test_vital_spark_taints_existing_and_generated_skills_then_clears_debuff():
    run = start('infested_prism', ('defend', 'strike'))
    p = run.combat.player
    assert next(c for c in p.hand if c.definition.definition_id == 'defend').combat_state.tainted
    play(run, 'defend')
    assert p.rules.powers['tainted'] == 2
    hp = p.hp
    step(run, EndTurn())
    assert p.hp == hp - 12  # 15 + 2 Tainted - 5 Block.
    assert not p.rules.powers.get('tainted')
    from game.headless.powers.hive import generate
    generate(p, 'defend', 'hand', 1)
    assert next(c for c in p.hand if c.definition.definition_id == 'defend').combat_state.tainted
    clone(run)


def test_tunneler_retains_block_then_exact_break_cancels_below():
    run = start('tunneler')
    for _ in range(2): step(run, EndTurn())
    e = run.combat.enemies[0]
    assert e.block == 32 and e.burrowed
    step(run, EndTurn())
    assert e.block == 32
    e.take_damage(32, is_attack=False)
    assert e.intent.move_name == 'Dizzy' and not e.burrowed
    step(run, EndTurn())
    assert e.intent.move_name == 'Bite'


def test_slumber_counts_damage_hits_and_side_ends_with_distinct_wake_paths():
    run = start('slumbering_beetle')
    e = run.combat.enemies[2]
    e.take_damage(16, is_attack=False)
    e.take_damage(1, is_attack=False)
    assert e.slumber == 1
    e.take_damage(1, is_attack=False)
    assert e.intent.move_name == 'Wake Up'
    step(run, EndTurn())
    assert e.intent.move_name == 'Roll Out' and e.plating == 0
    natural = start('slumbering_beetle')
    for _ in range(3): step(natural, EndTurn())
    beetle = natural.combat.enemies[2]
    assert beetle.intent.move_name == 'Roll Out' and beetle.plating == 0 and beetle.block == 13


def test_ovicopter_hatches_in_place_using_exclusive_niche_bounds():
    run = start('ovicopter')
    step(run, EndTurn())
    p = run.combat.player
    assert [e.position for e in run.combat.enemies[1:]] == [5, 4, 3]
    eggs = run.combat.enemies[1:]
    ids = list(map(id, eggs))
    rng = deepcopy(p.deck.niche_rng)
    expected = [rng.randrange(19, 22) for _ in eggs][::-1]
    step(run, EndTurn())
    assert list(map(id, run.combat.enemies[1:])) == ids
    assert [e.hp for e in eggs] == expected
    assert all(e.name == 'Hatchling' and e.intent.move_name == 'Nibble' for e in eggs)
    kill(run, run.combat.enemies[0])
    assert run.combat.done and all(e.hp == 0 for e in eggs)


def test_obscura_illusion_revives_same_slot_and_dies_with_owner():
    run = start('the_obscura')
    step(run, EndTurn())
    child = run.combat.enemies[1]
    for _ in range(2):
        kill(run, child)
        assert child.hp == 0 and child.intent.move_name == 'Revive'
        step(run, EndTurn())
        assert child.hp == 21
    kill(run, run.combat.enemies[0])
    assert run.combat.done and not child.is_alive


def test_decimillipede_revives_and_all_segments_must_be_dead():
    run = start('decimillipede')
    enemies = run.combat.enemies
    assert len({e.hp for e in enemies}) == 3 and all(e.hp % 2 == 0 for e in enemies)
    e = enemies[0]
    e.strength = 5
    e.apply_status('weak', 2)
    kill(run, e)
    assert not run.combat.done and e.strength == 0 and not e.statuses.get('weak')
    assert e.intent.move_name == 'Dead'
    step(run, EndTurn())
    assert e.intent.move_name == 'Reattach' and e.hp == 0
    step(run, EndTurn())
    assert e.hp == 25
    for enemy in enemies: kill(run, enemy)
    assert run.combat.done


def test_decimillipede_fatal_only_on_final_segment():
    run = start('decimillipede', ('feed',) * 3)
    initial = run.combat.player.max_hp
    for i in range(3):
        run.combat.enemies[i].hp = 1
        play(run, 'feed', i)
        if i < 2:
            assert run.combat.player.max_hp == initial
    assert run.state.max_hp == initial + 3


def test_knowledge_demon_all_three_choices_and_round_continuations():
    run = start('knowledge_demon', ('defend',) * 5)
    step(run, EndTurn())
    choose(run, 'mind_rot')
    p = run.combat.player
    assert len(p.hand) == 4 and p.rules.powers['mind_rot'] == 1
    for _ in range(4): step(run, EndTurn())
    choose(run, 'sloth')
    for _ in range(3): play(run, 'defend')
    assert not any(isinstance(a, PlayCard) for a in run.legal_actions())
    for _ in range(4): step(run, EndTurn())
    choose(run, 'waste_away')
    assert p.energy == 29
    assert run.combat.enemies[0].curses_chosen == 3
    for _ in range(8): step(run, EndTurn())
    assert run.combat.player.rules.selection is None


def test_disintegration_stacks_6_7_8_and_artifact_blocks_choice():
    run = start('knowledge_demon')
    step(run, EndTurn()); choose(run, 'disintegration')
    for amount in (13, 21):
        for _ in range(4): step(run, EndTurn())
        choose(run, 'disintegration')
        assert run.combat.player.rules.powers['disintegration'] == amount
    other = start('knowledge_demon')
    other.combat.player.statuses.add('artifact', 1)
    step(other, EndTurn()); choose(other, 'mind_rot')
    assert 'mind_rot' not in other.combat.player.rules.powers
    assert other.combat.enemies[0].curses_chosen == 1


def test_insatiable_frantic_escape_insertion_cost_growth_and_forced_death():
    run = start('the_insatiable')
    before = run.state.rng.request_count('shuffle')
    step(run, EndTurn())
    p = run.combat.player
    e = run.combat.enemies[0]
    assert e.sandpit == 4
    assert len(p.deck.draw_pile) == len(p.deck.discard_pile) == 3
    assert run.state.rng.request_count('shuffle') == before + 6
    card = p.deck.draw_pile.pop(); p.hand.append(card)
    play(run, 'frantic_escape')
    assert e.sandpit == 5 and card.combat_state.combat_cost_change == 1
    p.deck.discard_pile.remove(card); p.hand.append(card)
    play(run, 'frantic_escape')
    assert e.sandpit == 6 and card.combat_state.combat_cost_change == 2
    p.rules.powers['intangible'] = 99
    for _ in range(6):
        if run.combat: step(run, EndTurn())
    assert run.state.phase is RunPhase.DEFEAT


def test_kaiser_facing_targeted_cards_and_rage():
    run = start('kaiser_crab', ('strike', 'thunderclap'))
    p = run.combat.player
    assert p.rules.auxiliaries['surrounded'] == 0
    play(run, 'strike', 0)
    assert p.rules.auxiliaries['surrounded'] == 1
    play(run, 'thunderclap')
    assert p.rules.auxiliaries['surrounded'] == 1
    hp = p.hp
    step(run, EndTurn())
    assert p.hp == hp - 12 - 4
    crusher, rocket = run.combat.enemies
    kill(run, crusher)
    assert rocket.strength == 6 and rocket.block == 99
    assert p.rules.auxiliaries['surrounded'] == 0
    clone(run)


@pytest.mark.parametrize('claim', (True, False))
def test_hopper_steals_before_damage_and_returns_exact_card_as_optional_reward(claim):
    run = start('thieving_hopper', ('inflame', 'strike', 'defend'), draw=0)
    original = next(c for c in run.state.deck if c.definition.definition_id == 'inflame')
    original.upgrade()
    step(run, EndTurn())
    e = run.combat.enemies[0]
    assert e.stolen_id == original.instance_id
    assert original not in run.state.deck and len(run.state.stolen_cards) == 1
    kill(run, e); run.finish_combat()
    clone(run)
    row = next(i for i,r in enumerate(run.state.pending['extra_rewards']) if r['kind'] == 'stolen_card')
    step(run, ChooseExtraReward(row, original.instance_id if claim else None))
    returned = [c for c in run.state.deck if c.instance_id == original.instance_id]
    assert bool(returned) == claim
    if claim:
        assert returned[0].upgrade_level == 1
    step(run, LeaveRewards())


def test_hopper_escape_loses_card_but_keeps_normal_gold_and_snapshot():
    run = start('thieving_hopper', ('strike',), draw=0)
    for _ in range(5): step(run, EndTurn())
    assert not run.state.deck and not run.state.stolen_cards
    assert 10 <= run.state.pending['gold'] <= 20
    assert not any(r['kind'] == 'stolen_card' for r in run.state.pending['extra_rewards'])


def test_flutter_reduces_powered_hits_and_stun_skips_planned_move():
    run = start('thieving_hopper')
    for _ in range(2): step(run, EndTurn())
    e, p = run.combat.enemies[0], run.combat.player
    assert e.intent.move_name == 'Hat Trick' and e.flutter == 5
    e.take_damage(1, is_attack=False)
    assert e.flutter == 5
    for _ in range(5):
        assert e.take_damage(2, attacker_statuses=p.statuses) == 1
    assert e.intent.kind == 'stun' and e.flutter == 0
    step(run, EndTurn())
    assert e.intent.move_name == 'Nab'


@pytest.mark.parametrize('mutation', ('foreign_owner', 'wrong_offer', 'wrong_round', 'skip_choice'))
def test_knowledge_snapshot_rejects_unowned_choice(mutation):
    run = start('knowledge_demon')
    step(run, EndTurn())
    s = saved(run)
    if mutation == 'foreign_owner': s['combat']['player']['rules']['selection']['source'] = 'monster.3'
    elif mutation == 'wrong_offer': s['combat']['deck']['piles']['offered'][0]['definition_id'] = 'strike'
    elif mutation == 'wrong_round': s['combat']['enemies'][0]['state']['curses_chosen'] = 2
    else: s['combat']['player']['rules']['selection'] = None
    with pytest.raises(ValueError): run.restore(s)


def test_stolen_snapshot_cannot_duplicate_permanent_or_combat_identity():
    run = start('thieving_hopper', ('strike',), draw=0)
    step(run, EndTurn())
    s = saved(run)
    s['state']['deck'].append(s['state']['stolen_cards'][0])
    with pytest.raises(ValueError): run.restore(s)
    s = saved(run)
    s['combat']['enemies'][0]['state']['stolen_id'] = ''
    with pytest.raises(ValueError): run.restore(s)


@pytest.mark.parametrize('name', ('louse_progenitor', 'entomancer'))
def test_lethal_card_hit_skips_after_received_hooks_and_restores(name):
    run = start(name, ('strike',))
    run.combat.enemies[0].hp = 1
    play(run, 'strike')
    assert run.state.phase is RunPhase.REWARD
    clone(run)


def test_zero_damage_without_block_does_not_dizzy_rock():
    run = start('bowlbugs_weak')
    e = run.combat.enemies[0]
    e.strength = -15
    step(run, EndTurn())
    assert e.intent.move_name == 'Headbutt'


@pytest.mark.parametrize('op', ('hive_enemy_start', 'hive_player_end'))
@pytest.mark.parametrize('forge_receipt', (False, True))
def test_hive_boundary_cannot_be_injected_at_card_selection(op, forge_receipt):
    run = start('the_insatiable', ('armaments', 'strike', 'defend'), draw=10)
    step(run, EndTurn())
    play(run, 'armaments')
    s = saved(run)
    r = s['combat']['player']['rules']
    r['tasks'].append([op])
    if forge_receipt:
        r['pending_events'].append(dict(context=r['active_hook'], task=[op]))
    with pytest.raises(ValueError): run.restore(s)


@pytest.mark.parametrize('name,power', [('kaiser_crab', 'surrounded'), ('hunter_killer', 'tender')])
@pytest.mark.parametrize('value', [None, -1, 99])
def test_owned_hive_auxiliaries_are_required_and_bounded(name, power, value):
    run = start(name)
    if power == 'tender': step(run, EndTurn())
    s = saved(run)
    aux = s['combat']['player']['rules']['auxiliaries']
    if value is None: del aux[power]
    else: aux[power] = value
    with pytest.raises(ValueError): run.restore(s)


def test_sandpit_forced_death_cleans_active_orbs():
    from game.headless.core.combat import CombatEngine
    engine = CombatEngine(seed=7, encounter_factory=ENCOUNTERS['hive_the_insatiable'],
                          deck_factory=lambda: [DEFAULT_CARDS.create('zap')], player_max_hp=1000)
    engine.reset()
    card = engine.player.hand[0]
    engine.apply(PlayCard(card.instance_id))
    assert engine.player.rules.orb_order
    for _ in range(5): engine.apply(EndTurn())
    assert engine.done and engine.player.hp == 0 and not engine.player.rules.orb_order
    other = CombatEngine()
    other.restore(json.loads(json.dumps(engine.snapshot())))
    assert other.snapshot() == engine.snapshot()


@pytest.mark.parametrize('name,slot,damage', [('decimillipede', 0, 5), ('the_obscura', 1, 16)])
def test_reactive_death_pauses_without_extra_hits_or_premature_revive(name, slot, damage):
    from game.headless.run.inventory import add_relic
    run = RunEngine(seed=7, max_hp=1000, config=RunConfig(), card_ids=('strike', 'defend'))
    add_relic(run.state, 'centennial_puzzle', cards=run.cards)
    run.start_combat(encounter_id='hive_' + name, cards_per_turn=0)
    if slot: step(run, EndTurn())
    p, enemy = run.combat.player, run.combat.enemies[slot]
    enemy.hp, enemy._intent_index = 1, 0
    for e in run.combat.enemies:
        if e is not enemy: e.stunned = True
    p.rules.powers.update(thorns=2, stratagem=1)
    p.deck.discard_pile.extend(p.deck.draw_pile); p.deck.draw_pile.clear()
    before = p.hp
    step(run, EndTurn())
    assert p.rules.selection is not None and enemy.move_interrupted
    for _ in range(6):
        if p.rules.selection is None: break
        legal = run.legal_actions()
        action = next((a for a in legal if isinstance(a, ConfirmCombatSelection)), None)
        step(run, action or next(a for a in legal if isinstance(a, ChooseCombatCard)))
    assert not enemy.move_interrupted and enemy.hp == 0 and p.hp == before - damage
    step(run, EndTurn())
    assert enemy.hp == (25 if name == 'decimillipede' else 21)


def test_ovicopter_turn_order_keeps_stable_slots():
    run = start('ovicopter')
    step(run, EndTurn())
    result = run.combat.apply(EndTurn())
    assert [a['enemy_index'] for a in result.details['enemy_actions']] == [3, 2, 1, 0]


def test_hopper_stolen_reward_preserves_injected_catalog():
    from dataclasses import replace
    from game.headless.cards.catalog import CardCatalog
    cards = CardCatalog((*DEFAULT_CARDS.definitions, replace(DEFAULT_CARDS.definition('strike'), definition_id='custom_strike')))
    run = RunEngine(seed=7, config=RunConfig(), cards=cards, card_ids=('custom_strike',))
    run.start_combat(encounter_id='hive_thieving_hopper', cards_per_turn=0)
    run.apply(EndTurn())
    kill(run, run.combat.enemies[0])
    run.finish_combat()
    other = RunEngine(cards=cards)
    other.restore(saved(run))
    assert other.snapshot() == run.snapshot()
    reward = next(r for r in run.state.pending['extra_rewards'] if r['kind'] == 'stolen_card')
    assert reward['modifiers']['card']['definition_id'] == 'custom_strike'


def test_decimillipede_doom_after_own_move_prepares_next_turn_reattach():
    run = start('decimillipede')
    enemy = run.combat.enemies[0]
    enemy.statuses.add('doom', enemy.hp)
    step(run, EndTurn())
    assert enemy.hp == 0 and enemy.intent.move_name == 'Reattach'
    step(run, EndTurn())
    assert enemy.hp == 25


def test_ovicopter_paused_move_binds_cursor_to_stable_target_slot():
    from game.headless.run.inventory import add_relic
    run = RunEngine(seed=7, max_hp=1000, config=RunConfig(), card_ids=('strike', 'defend'))
    add_relic(run.state, 'centennial_puzzle', cards=run.cards)
    run.start_combat(encounter_id='hive_ovicopter', cards_per_turn=0)
    step(run, EndTurn())
    p = run.combat.player
    p.rules.powers['stratagem'] = 1
    p.deck.discard_pile.extend(p.deck.draw_pile); p.deck.draw_pile.clear()
    step(run, EndTurn())
    assert p.rules.enemy_turn['slot'] == 3
    assert p.rules.enemy_turn['order'] == [3, 2, 1, 0]
    for replacement in (None, [0, 1, 2, 3]):
        state = saved(run)
        progress = state['combat']['player']['rules']['enemy_turn']
        if replacement is None: del progress['order']
        else: progress['order'] = replacement
        with pytest.raises(ValueError): run.restore(state)
    while p.rules.selection is not None:
        legal = run.legal_actions()
        action = next((a for a in legal if isinstance(a, ConfirmCombatSelection)), None)
        step(run, action or next(a for a in legal if isinstance(a, ChooseCombatCard)))
    assert p.rules.player_side
