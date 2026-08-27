"""Focused coverage for transition- and active-time trainer budgets."""

from __future__ import annotations

import pytest

from game.agents.baselines import train_q_learning
from game.agents.dqn import train_dqn
from game.agents.ppo import train_masked_ppo
from game.simulation.env_factory import CombatEnvFactory
from game.training.budget import TrainingBudget


def simple_factory():
    return CombatEnvFactory(encounter_set="simple", record_trajectory=False)()


def test_training_budget_validation_and_precedence() -> None:
    with pytest.raises(ValueError, match="max_environment_steps"):
        TrainingBudget(max_environment_steps=0)
    with pytest.raises(ValueError, match="max_training_seconds"):
        TrainingBudget(max_training_seconds=0.0)

    budget = TrainingBudget(max_environment_steps=10, max_training_seconds=1.0)
    assert budget.stop_reason(environment_steps=10, elapsed_seconds=2.0) == (
        "environment_steps"
    )
    assert budget.remaining_environment_steps(4) == 6


def test_q_learning_stops_at_exact_transition_budget() -> None:
    result = train_q_learning(
        simple_factory,
        episodes=100,
        evaluation_interval=0,
        evaluation_episodes=1,
        seed=7,
        max_environment_steps=7,
    )
    assert result.environment_steps == 7
    assert result.stop_reason == "environment_steps"
    assert result.training_elapsed_seconds >= 0.0
    assert result.training_cpu_seconds >= 0.0


def test_dqn_stops_at_exact_transition_budget() -> None:
    result = train_dqn(
        simple_factory,
        episodes=100,
        evaluation_interval=0,
        evaluation_episodes=1,
        seed=7,
        replay_capacity=64,
        batch_size=4,
        warmup_steps=4,
        train_frequency=1,
        hidden_sizes=(8,),
        device="cpu",
        restore_best_checkpoint=False,
        max_environment_steps=12,
    )
    assert result.environment_steps == 12
    assert result.stop_reason == "environment_steps"
    assert result.optimization_steps > 0
    assert result.training_cpu_seconds >= 0.0


def test_ppo_stops_on_aligned_optimizer_boundary() -> None:
    result = train_masked_ppo(
        simple_factory,
        episodes=100,
        evaluation_interval=0,
        evaluation_episodes=1,
        rollout_steps=16,
        num_envs=1,
        hidden_sizes=(8,),
        ppo_epochs=1,
        minibatch_size=8,
        device="cpu",
        restore_best_checkpoint=False,
        max_environment_steps=32,
        seed=7,
    )
    assert result.environment_steps == 32
    assert result.stop_reason == "environment_steps"
    assert result.optimization_steps == 4
    assert result.training_cpu_seconds >= 0.0


def test_time_budget_can_stop_before_one_episode_finishes() -> None:
    result = train_q_learning(
        simple_factory,
        episodes=100,
        evaluation_interval=0,
        evaluation_episodes=1,
        seed=7,
        max_training_seconds=1e-12,
    )
    assert result.environment_steps == 0
    assert result.stop_reason == "training_time"
    assert result.training_metrics == ()
