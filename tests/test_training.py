"""Tests for baseline policies and training helpers."""

from __future__ import annotations

from random import Random

from train import parse_args, resolve_dqn_learning_rate, resolve_q_learning_rate

from game.baselines import (
    TrainingProgress,
    QLearningAgent,
    choose_heuristic_action,
    choose_random_action,
    evaluate_policy,
    train_q_learning,
)
from game.card import StrikeCard
from game.core import CombatEnv
from game.enemy import SimpleEnemy


def test_random_policy_returns_legal_action() -> None:
    env = CombatEnv(seed=0)
    observation = env.reset()
    action_mask = env.get_action_mask()

    action_index = choose_random_action(env, observation, action_mask, rng=Random(0))

    assert action_mask[action_index] == 1


def test_heuristic_policy_wins_easy_episode() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=1,
    )
    stats = evaluate_policy(
        env_factory=lambda: CombatEnv(
            seed=0,
            deck_factory=lambda: [StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
        ),
        policy=choose_heuristic_action,
        episodes=3,
        seed=0,
    )

    assert env.action_space_size == 11
    assert stats.win_rate == 1.0
    assert stats.mean_reward == 1.0


def test_q_learning_update_changes_q_values() -> None:
    agent = QLearningAgent(
        action_space_size=3,
        learning_rate=0.5,
        discount=0.9,
        epsilon=0.0,
        seed=0,
    )
    state = (1, 2, 3)
    next_state = (4, 5, 6)

    agent.q_table[next_state] = [0.0, 1.0, 0.0]
    agent.update(
        state=state,
        action=1,
        reward=0.0,
        next_state=next_state,
        next_action_mask=(1, 1, 0),
        done=False,
    )

    assert agent.q_table[state][1] == 0.45


def test_q_learning_training_produces_evaluation_stats() -> None:
    result = train_q_learning(
        env_factory=lambda: CombatEnv(
            deck_factory=lambda: [StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            player_max_hp=6,
            cards_per_turn=1,
        ),
        episodes=10,
        evaluation_interval=5,
        evaluation_episodes=3,
        seed=0,
        epsilon=0.4,
        epsilon_min=0.0,
        epsilon_decay=0.9,
    )

    assert len(result.training_metrics) == 10
    assert len(result.evaluations) == 2
    assert result.final_evaluation.episodes == 3
    assert len(result.agent.q_table) > 0


def test_q_learning_progress_callback_reports_updates() -> None:
    progress_updates: list[TrainingProgress] = []

    result = train_q_learning(
        env_factory=lambda: CombatEnv(
            deck_factory=lambda: [StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
        ),
        episodes=3,
        evaluation_interval=2,
        evaluation_episodes=1,
        seed=0,
        progress_callback=progress_updates.append,
        progress_interval=2,
        progress_window=2,
    )

    assert len(result.training_metrics) == 3
    assert len(progress_updates) == 2
    assert progress_updates[0].episode == 2
    assert progress_updates[1].episode == 3
    assert progress_updates[-1].algorithm == "q_learning"


def test_cli_uses_separate_default_learning_rates() -> None:
    args = parse_args([])

    assert resolve_q_learning_rate(args) == 0.1
    assert resolve_dqn_learning_rate(args) == 1e-3
    assert args.restore_best_checkpoint is True


def test_cli_shared_learning_rate_override_applies_to_both_algorithms() -> None:
    args = parse_args(["--learning-rate", "0.02"])

    assert resolve_q_learning_rate(args) == 0.02
    assert resolve_dqn_learning_rate(args) == 0.02


def test_cli_algorithm_specific_learning_rates_remain_available() -> None:
    args = parse_args(["--q-learning-rate", "0.25", "--dqn-learning-rate", "0.0005"])

    assert resolve_q_learning_rate(args) == 0.25
    assert resolve_dqn_learning_rate(args) == 0.0005
