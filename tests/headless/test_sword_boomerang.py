"""Random multihit attacks, independent target RNG and Vantom interaction."""

import json
from copy import deepcopy
from random import Random

import pytest

from game.analysis.bruteforce import clone_combat_env
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.monsters.vantom import Vantom
from game.headless.run.engine import RunEngine
from game.headless.run.actions import ChooseNode, ChooseRewardCard
from game.cli.headless_play import choose_demo_action
from game.simulation.core import CombatEnv


def saved(combat):
    return json.loads(json.dumps(combat.snapshot()))


def setup(upgrade=0, enemies=None):
    combat = CombatEngine(deck_factory=lambda: [DEFAULT_CARDS.create("sword_boomerang", upgrade_level=upgrade)],
                          encounter_factory=enemies or (lambda rng: [Vantom(rng)]))
    combat.reset(seed=11)
    return combat


def action(combat):
    return PlayCard(combat.player.hand[0].instance_id)


@pytest.mark.parametrize("upgrade,hits", [(0, 3), (1, 4)])
def test_boomerang_strips_one_slippery_stack_per_hit_costs_one_and_discards(upgrade, hits):
    combat = setup(upgrade)
    assert action(combat) in combat.legal_actions()
    assert PlayCard(combat.player.hand[0].instance_id, 0) not in combat.legal_actions()
    combat.apply(action(combat))
    assert combat.enemies[0].hp == 173 - hits
    assert combat.enemies[0].statuses.get("slippery") == 8 - hits
    assert combat.player.energy == 2 and len(combat.player.deck.discard_pile) == 1
    assert combat.player.deck.exhaust_pile == []


@pytest.mark.parametrize("upgrade,hits", [(0, 3), (1, 4)])
def test_each_hit_uses_strength_weak_vulnerable_and_block(upgrade, hits):
    combat = setup(upgrade, lambda rng: [SimpleEnemy(max_hp=100)])
    combat.player.gain_strength(2)
    combat.player.apply_status("weak", 1)
    enemy = combat.enemies[0]
    enemy.apply_status("vulnerable", 2)
    enemy.gain_block(6)
    combat.apply(action(combat))
    assert enemy.hp == 100 - (hits * 5 - 6)  # floor(5 * .75 * 1.5) = 5 per hit.
    assert enemy.block == 0


def test_slippery_expires_mid_card_then_later_hit_deals_full_damage():
    combat = setup()
    combat.enemies[0].statuses.decrement("slippery", 6)
    combat.apply(action(combat))
    assert combat.enemies[0].hp == 173 - 1 - 1 - 3


def test_targets_are_reselected_after_death_and_last_kill_stops_rolls():
    combat = setup(1, lambda rng: [SimpleEnemy(max_hp=1), SimpleEnemy(max_hp=1)])
    expected = Random()
    expected.setstate(combat.player.deck.target_rng.getstate())
    remaining = [0, 1]
    remaining.remove(expected.choice(remaining))
    expected.choice(remaining)
    result = combat.apply(action(combat))
    assert result.winner == "player" and all(not e.is_alive for e in combat.enemies)
    assert combat.player.deck.target_rng.getstate() == expected.getstate()
    assert len(combat.enemies) == 2  # Dead slots are not compacted.


def test_dead_slots_excluded_and_repeated_target_allowed():
    combat = setup(1, lambda rng: [SimpleEnemy(max_hp=100) for _ in range(3)])
    combat.enemies[1].hp = 0
    expected = Random()
    expected.setstate(combat.player.deck.target_rng.getstate())
    hits = [expected.choice((0, 2)) for _ in range(4)]
    combat.apply(action(combat))
    assert [e.hp for e in combat.enemies] == [100 - hits.count(0) * 3, 0, 100 - hits.count(2) * 3]
    assert combat.player.deck.target_rng.getstate() == expected.getstate()


def test_reads_rejected_targets_restore_and_rng_isolation():
    combat = setup(enemies=lambda rng: [SimpleEnemy(max_hp=100) for _ in range(3)])
    before = saved(combat)
    combat.legal_actions()
    for enemy in combat.enemies:
        enemy.to_observation()
    with pytest.raises(ValueError):
        combat.apply(PlayCard(combat.player.hand[0].instance_id, 0))
    assert saved(combat) == before
    clone = CombatEngine()
    clone.restore(before)
    assert clone.player.deck.target_rng is not combat.player.deck.target_rng
    assert clone.player.deck.target_rng is not clone.player.deck.selection_rng
    deck_rng = combat.player.deck.rng.getstate()
    hand_rng = combat.player.deck.selection_rng.getstate()
    for engine in (combat, clone):
        engine.apply(action(engine))
    assert saved(combat) == saved(clone)
    assert combat.player.deck.rng.getstate() == deck_rng
    assert combat.player.deck.selection_rng.getstate() == hand_rng


def test_target_rng_restore_rejects_missing_or_invalid_reference_atomically():
    combat = setup()
    before = saved(combat)
    for corrupt in ("missing", "reference", "old_schema"):
        invalid = deepcopy(before)
        if corrupt == "missing": invalid["deck"].pop("target_rng")
        elif corrupt == "reference": invalid["deck"]["target_rng"] = 999
        else: invalid["schema"] = "headless_combat_state_v3"
        with pytest.raises(ValueError):
            combat.restore(invalid)
        assert saved(combat) == before


def test_search_clone_keeps_target_rng_independent_even_without_encoding_new_cards():
    env = CombatEnv(deck_factory=lambda: [DEFAULT_CARDS.create("sword_boomerang")])
    # Direct engine setup avoids claiming that the legacy encoder supports the card.
    CombatEngine.reset(env)
    clone = clone_combat_env(env)
    assert clone.player.deck.target_rng is not env.player.deck.target_rng
    before = env.player.deck.target_rng.getstate()
    clone.player.deck.target_rng.random()
    assert env.player.deck.target_rng.getstate() == before


def test_act1_reward_pool_can_acquire_and_permanently_upgrade_boomerang():
    selected = None
    for seed in range(20):
        run = RunEngine.ironclad_slice(seed=seed, route="overgrowth-act1")
        for _ in range(100):
            if ChooseRewardCard("sword_boomerang") in run.legal_actions():
                selected = run
                break
            if not run.legal_actions() or run.state.combats_completed:
                break
            run.apply(choose_demo_action(run, "rest"))
        if selected is not None:
            break
    assert selected is not None
    selected.apply(ChooseRewardCard("sword_boomerang"))
    card = selected.state.deck[-1]
    assert card.definition.definition_id == "sword_boomerang"
    from game.headless.run.actions import LeaveRewards
    selected.apply(LeaveRewards())
    selected.upgrade_card(card.instance_id)
    assert card.upgrade_level == 1
    clone = RunEngine()
    clone.restore(saved(selected))
    assert saved(clone) == saved(selected)


def test_state_key_distinguishes_future_target_and_hand_selection_rng():
    from game.analysis.bruteforce import _combat_state_key, _RngStateRegistry, _CardStateRegistry
    env = CombatEnv()
    env.reset()
    rngs, cards = _RngStateRegistry(), _CardStateRegistry()
    before = _combat_state_key(env, rngs, cards)
    env.player.deck.target_rng.random()
    after_target = _combat_state_key(env, rngs, cards)
    env.player.deck.selection_rng.random()
    assert before != after_target != _combat_state_key(env, rngs, cards)
