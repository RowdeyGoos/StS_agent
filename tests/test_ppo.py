"""Tests for masked PPO dependency handling and persistence."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from game.agent_io import load_agent, save_agent
from game.core import CombatEnv
from game.enemy import SimpleEnemy
from game.ppo import PPOAgent, train_masked_ppo


def test_masked_ppo_dependency_behavior() -> None:
    env = CombatEnv(
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=1,
        record_trajectory=False,
    )
    try:
        agent = PPOAgent(
            observation_size=env.observation_size,
            action_space_size=env.action_space_size,
            hidden_sizes=(16,),
            policy_architecture="action_feature",
            action_feature_size=env.action_feature_size,
            seed=0,
        )
    except ModuleNotFoundError:
        return

    result = train_masked_ppo(
        env_factory=lambda: CombatEnv(
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
            record_trajectory=False,
        ),
        episodes=2,
        evaluation_interval=0,
        evaluation_episodes=1,
        rollout_steps=4,
        hidden_sizes=(16,),
        seed=0,
        learning_rate=1e-3,
        ppo_epochs=1,
        minibatch_size=2,
        entropy_coef=0.0,
        device=agent.device,
    )

    assert len(result.training_metrics) == 2
    assert result.final_evaluation.episodes == 1
    assert result.best_evaluation is None
    assert result.restored_best_checkpoint is False
    assert result.agent.policy_architecture == "action_feature"
    assert result.agent.action_feature_size == env.action_feature_size

    with TemporaryDirectory() as temp_dir:
        checkpoint_path = Path(temp_dir) / "masked_ppo_agent.pt"
        save_agent(result.agent, checkpoint_path)
        loaded_agent = load_agent(checkpoint_path, device=agent.device)

    assert isinstance(loaded_agent, PPOAgent)
    assert loaded_agent.hidden_sizes == (16,)
    assert loaded_agent.action_space_size == result.agent.action_space_size
    assert loaded_agent.policy_architecture == "action_feature"
