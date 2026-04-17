"""Tests for replay memory and DQN dependency handling."""

from __future__ import annotations

import game
from game.core import CombatEnv
from game.dqn import (
    DQNAgent,
    DoubleDQNAgent,
    ReplayBuffer,
    ReplayTransition,
    train_double_dqn,
    train_dqn,
)
from game.enemy import SimpleEnemy


def test_replay_buffer_capacity_and_sampling() -> None:
    buffer = ReplayBuffer(capacity=2, seed=0)
    transition_a = ReplayTransition((1.0,), 0, 0.0, (2.0,), (1,), False)
    transition_b = ReplayTransition((2.0,), 1, 1.0, (3.0,), (1,), False)
    transition_c = ReplayTransition((3.0,), 0, -1.0, (4.0,), (1,), True)

    buffer.add(transition_a)
    buffer.add(transition_b)
    buffer.add(transition_c)

    sampled = buffer.sample(2)

    assert len(buffer) == 2
    assert transition_a not in sampled
    assert all(isinstance(transition, ReplayTransition) for transition in sampled)


def test_dqn_dependency_behavior() -> None:
    try:
        agent = DQNAgent(
            observation_size=25,
            action_space_size=11,
            hidden_sizes=(16,),
            seed=0,
        )
    except ModuleNotFoundError:
        return

    result = train_dqn(
        env_factory=lambda: CombatEnv(
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
        ),
        episodes=2,
        evaluation_interval=1,
        evaluation_episodes=1,
        replay_capacity=16,
        batch_size=1,
        warmup_steps=0,
        target_update_interval=1,
        hidden_sizes=(16,),
        seed=0,
        epsilon=0.2,
        epsilon_min=0.0,
        epsilon_decay=0.9,
        device=agent.device,
    )

    assert len(result.training_metrics) == 2
    assert result.final_evaluation.episodes == 1
    assert result.best_evaluation is not None
    assert result.restored_best_checkpoint is True


def test_double_dqn_dependency_behavior() -> None:
    assert hasattr(game, "train_double_dqn")

    try:
        agent = DoubleDQNAgent(
            observation_size=25,
            action_space_size=11,
            hidden_sizes=(16,),
            seed=0,
        )
    except ModuleNotFoundError:
        return

    result = train_double_dqn(
        env_factory=lambda: CombatEnv(
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
        ),
        episodes=2,
        evaluation_interval=1,
        evaluation_episodes=1,
        replay_capacity=16,
        batch_size=1,
        warmup_steps=0,
        target_update_interval=1,
        hidden_sizes=(16,),
        seed=0,
        epsilon=0.2,
        epsilon_min=0.0,
        epsilon_decay=0.9,
        device=agent.device,
    )

    assert len(result.training_metrics) == 2
    assert result.final_evaluation.episodes == 1
    assert result.best_evaluation is not None
    assert result.restored_best_checkpoint is True
