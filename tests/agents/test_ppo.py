"""Tests for masked PPO dependency handling and persistence."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from game.agents import ppo as ppo_module
from game.agents.agent_io import load_agent, save_agent
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy
from game.simulation.env_factory import CombatEnvFactory
from game.agents.ppo import PPOAgent, _compute_interleaved_gae, train_masked_ppo


def _shared_enemy_agent(env: CombatEnv, seed: int = 0) -> PPOAgent:
    encoder = env.encoder
    return PPOAgent(
        observation_size=env.observation_size,
        action_space_size=env.action_space_size,
        hidden_sizes=(16,),
        policy_architecture="shared_enemy",
        action_feature_size=env.action_feature_size,
        max_enemy_count=encoder.max_enemy_count,
        enemy_feature_start=(
            encoder.scalar_feature_count + encoder.pile_count_feature_count
        ),
        enemy_slot_feature_size=encoder.enemy_slot_feature_count,
        uses_target_feature_index=encoder.action_feature_names.index("uses_target"),
        target_slot_feature_index=encoder.action_feature_names.index(
            "target_slot_fraction"
        ),
        device="cpu",
        seed=seed,
    )


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


def test_masked_ppo_batches_multiple_training_environments() -> None:
    if ppo_module.torch is None:
        return

    original_sample_actions = PPOAgent.sample_actions
    sampled_batch_sizes: list[int] = []

    def record_batch_size(self, states, action_masks, action_features=None, training=True):
        sampled_batch_sizes.append(len(states))
        return original_sample_actions(
            self,
            states,
            action_masks,
            action_features=action_features,
            training=training,
        )

    PPOAgent.sample_actions = record_batch_size
    try:
        result = train_masked_ppo(
            env_factory=lambda: CombatEnv(
                enemy_factory=lambda: SimpleEnemy(max_hp=6),
                cards_per_turn=1,
                record_trajectory=False,
            ),
            episodes=4,
            evaluation_interval=0,
            evaluation_episodes=1,
            rollout_steps=8,
            num_envs=2,
            hidden_sizes=(16,),
            seed=0,
            learning_rate=1e-3,
            ppo_epochs=1,
            minibatch_size=4,
            entropy_coef=0.0,
            device="cpu",
        )
    finally:
        PPOAgent.sample_actions = original_sample_actions

    assert len(result.training_metrics) == 4
    assert result.num_envs == 2
    assert max(sampled_batch_sizes) == 2


def test_shared_enemy_policy_is_equivariant_to_enemy_slot_swaps() -> None:
    if ppo_module.torch is None:
        return

    env = CombatEnvFactory(encounter_set="slimes", record_trajectory=False)()
    observation = env.reset(seed=7)
    swapped_observation = deepcopy(observation)
    swapped_observation["enemies"][1], swapped_observation["enemies"][2] = (
        swapped_observation["enemies"][2],
        swapped_observation["enemies"][1],
    )

    encoder = env.encoder
    state = encoder.encode(observation)
    swapped_state = encoder.encode(swapped_observation)
    action_features = encoder.encode_action_features(observation)
    swapped_action_features = encoder.encode_action_features(swapped_observation)
    agent = _shared_enemy_agent(env)

    with ppo_module.torch.no_grad():
        logits, values = agent.actor_critic(
            ppo_module.torch.as_tensor([state], dtype=ppo_module.torch.float32),
            ppo_module.torch.as_tensor(
                [action_features], dtype=ppo_module.torch.float32
            ),
        )
        swapped_logits, swapped_values = agent.actor_critic(
            ppo_module.torch.as_tensor(
                [swapped_state], dtype=ppo_module.torch.float32
            ),
            ppo_module.torch.as_tensor(
                [swapped_action_features], dtype=ppo_module.torch.float32
            ),
        )

    assert ppo_module.torch.allclose(values, swapped_values, atol=1e-7)
    for hand_index in range(encoder.max_hand_size):
        target_one_action = 1 + hand_index * encoder.max_enemy_count + 1
        target_two_action = 1 + hand_index * encoder.max_enemy_count + 2
        assert ppo_module.torch.allclose(
            logits[:, target_one_action],
            swapped_logits[:, target_two_action],
            atol=1e-7,
        )
        assert ppo_module.torch.allclose(
            logits[:, target_two_action],
            swapped_logits[:, target_one_action],
            atol=1e-7,
        )


def test_shared_enemy_ppo_trains_and_round_trips_checkpoint() -> None:
    if ppo_module.torch is None:
        return

    env_factory = CombatEnvFactory(
        encounter_set="slimes",
        cards_per_turn=2,
        record_trajectory=False,
    )
    result = train_masked_ppo(
        env_factory=env_factory,
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
        policy_architecture="shared_enemy",
        device="cpu",
    )

    with TemporaryDirectory() as temp_dir:
        checkpoint_path = Path(temp_dir) / "shared_enemy.pt"
        save_agent(result.agent, checkpoint_path)
        loaded_agent = load_agent(checkpoint_path, device="cpu")

    assert isinstance(loaded_agent, PPOAgent)
    assert loaded_agent.policy_architecture == "shared_enemy"
    assert loaded_agent.max_enemy_count == 3
    assert loaded_agent.enemy_slot_feature_size == result.agent.enemy_slot_feature_size


def test_interleaved_rollout_gae_stays_separate_by_environment() -> None:
    advantages, returns = _compute_interleaved_gae(
        rewards=(1.0, 10.0, 2.0, 20.0),
        dones=(False, False, True, True),
        values=(0.0, 0.0, 0.0, 0.0),
        environment_ids=(0, 1, 0, 1),
        last_value={0: 0.0, 1: 0.0},
        discount=1.0,
        gae_lambda=1.0,
    )

    assert advantages == [3.0, 30.0, 2.0, 20.0]
    assert returns == advantages
