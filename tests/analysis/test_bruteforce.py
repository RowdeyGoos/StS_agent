"""Tests for the exact seeded combat oracle."""

from __future__ import annotations

from game.cli.brute_force import make_env, parse_args
from game.analysis.bruteforce import brute_force_combat, clone_combat_env
from game.simulation.card import DefendCard, StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy


def test_brute_force_finds_and_proves_one_action_lethal() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=1,
        record_trajectory=False,
    )
    initial_observation = env.reset()

    result = brute_force_combat(env, max_steps=4, max_nodes=100)

    assert result.proven_optimal is True
    assert result.found_win is True
    assert result.actions == (("play", 0),)
    assert result.summary is not None
    assert result.summary["player_hp"] == 80
    assert result.summary["steps"] == 1
    assert env.get_observation() == initial_observation
    assert env.episode_step_count == 0


def test_brute_force_optimizes_remaining_hp_before_action_count() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=12),
        cards_per_turn=1,
        record_trajectory=False,
    )
    env.reset()

    result = brute_force_combat(env, max_steps=8, max_nodes=1_000)

    assert result.proven_optimal is True
    assert result.actions == (("play", 0), ("end_turn",), ("play", 0))
    assert result.summary is not None
    assert result.summary["winner"] == "player"
    assert result.summary["player_hp"] == 74


def test_brute_force_handles_stable_multi_enemy_targets() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard(), StrikeCard()],
        encounter_factory=lambda _rng: [
            SimpleEnemy(max_hp=6),
            SimpleEnemy(max_hp=6),
        ],
        cards_per_turn=2,
        max_enemy_count=3,
        record_trajectory=False,
    )
    env.reset()

    result = brute_force_combat(env, max_steps=4, max_nodes=1_000)

    assert result.proven_optimal is True
    assert result.found_win is True
    assert result.summary is not None
    assert result.summary["player_hp"] == 80
    assert len(result.steps) == 2
    assert {step.action[2] for step in result.steps} == {0, 1}


def test_brute_force_reports_unproven_result_at_step_limit() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=40),
        cards_per_turn=1,
        record_trajectory=False,
    )
    env.reset()

    result = brute_force_combat(env, max_steps=1, max_nodes=100)

    assert result.proven_optimal is False
    assert result.termination_reason == "max_steps"
    assert result.summary is None


def test_brute_force_cli_can_select_a_fixed_overgrowth_encounter() -> None:
    args = parse_args(["--encounter", "nibbit", "--seed", "11"])
    env = make_env(args)
    observation = env.reset(seed=args.seed)

    assert observation["enemy_count"] == 1
    assert observation["enemy"]["name"] == "Nibbit"
    assert env.encoder.max_enemy_count == 3


def test_clone_combat_env_preserves_rng_aliases_and_isolates_mutable_state() -> None:
    env = CombatEnv(
        seed=13,
        deck_factory=lambda: [StrikeCard(), DefendCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=12),
        cards_per_turn=2,
        record_trajectory=False,
    )
    initial_observation = env.reset()

    cloned_env = clone_combat_env(env)
    assert cloned_env.player is not None
    assert cloned_env.rng is cloned_env.player.deck.rng
    assert cloned_env.rng is not env.rng
    assert cloned_env.rng.random() == env.rng.random()

    strike_index = cloned_env.get_observation()["hand"].index("Strike")
    cloned_env.step(("play", strike_index))

    assert env.get_observation() == initial_observation
    assert cloned_env.get_observation() != initial_observation


def test_brute_force_skips_only_equivalent_duplicate_card_actions() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard(), StrikeCard(), StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=3,
        record_trajectory=False,
    )
    env.reset()

    result = brute_force_combat(env, max_steps=3, max_nodes=100)

    assert result.proven_optimal is True
    assert result.actions == (("play", 0),)
    # Root, one representative Strike child, and the end-turn child.
    assert result.generated_nodes == 3
