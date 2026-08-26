"""Tests for replay memory and DQN dependency handling."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import game
import pytest
from game.agents import dqn as dqn_module
from game.agents.agent_io import (
    CHECKPOINT_FORMAT_VERSION,
    load_agent,
    resolve_agent_path,
    save_agent,
)
from game.simulation.core import CombatEnv
from game.agents.dqn import (
    DQNAgent,
    DoubleDQNAgent,
    DuelingDoubleDQNAgent,
    ReplayBuffer,
    ReplayTransition,
    train_double_dqn,
    train_dqn,
    train_dueling_double_dqn,
)
from game.simulation.enemy import SimpleEnemy
from game.simulation.env_factory import CombatEnvFactory


def _shared_enemy_kwargs(env: CombatEnv) -> dict[str, object]:
    encoder = env.encoder
    return {
        "observation_size": env.observation_size,
        "action_space_size": env.action_space_size,
        "hidden_sizes": (16,),
        "architecture": "shared_enemy",
        "action_feature_size": env.action_feature_size,
        "max_enemy_count": encoder.max_enemy_count,
        "enemy_feature_start": (
            encoder.scalar_feature_count + encoder.pile_count_feature_count
        ),
        "enemy_slot_feature_size": encoder.enemy_slot_feature_count,
        "uses_target_feature_index": encoder.action_feature_names.index(
            "uses_target"
        ),
        "target_slot_feature_index": encoder.action_feature_names.index(
            "target_slot_fraction"
        ),
        "device": "cpu",
        "seed": 0,
    }


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


def test_q_learning_checkpoint_can_include_training_config() -> None:
    from game.agents.baselines import QLearningAgent

    agent = QLearningAgent(action_space_size=3, seed=0)
    training_config = {
        "policy": "q_learning",
        "episodes": 25,
        "encounter_set": "simple",
    }
    run_metadata = {
        "episodes_completed": 25,
        "environment_steps": 100,
        "git_commit": "abc123",
    }
    training_summary = {
        "final_evaluation": {"win_rate": 1.0},
    }

    with TemporaryDirectory() as temp_dir:
        run_dir = Path(temp_dir) / "run"
        run_dir.mkdir()
        checkpoint_path = run_dir / "checkpoint.json"
        save_agent(
            agent,
            checkpoint_path,
            training_config=training_config,
            run_metadata=run_metadata,
            training_summary=training_summary,
        )
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        resolved_checkpoint_path = resolve_agent_path(run_dir)
        loaded_agent = load_agent(run_dir)

    assert payload["checkpoint_format_version"] == CHECKPOINT_FORMAT_VERSION
    assert payload["training_config"] == training_config
    assert payload["run_metadata"] == run_metadata
    assert payload["training_summary"] == training_summary
    assert resolved_checkpoint_path == checkpoint_path
    assert loaded_agent.action_space_size == agent.action_space_size


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
            record_trajectory=False,
        ),
        episodes=2,
        evaluation_interval=0,
        evaluation_episodes=1,
        replay_capacity=16,
        batch_size=1,
        warmup_steps=0,
        train_frequency=2,
        gradient_steps=1,
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
    assert result.best_evaluation is None
    assert result.restored_best_checkpoint is False
    assert result.agent.architecture == "action_feature"

    with TemporaryDirectory() as temp_dir:
        checkpoint_path = Path(temp_dir) / "dqn_agent.pt"
        save_agent(result.agent, checkpoint_path)
        loaded_agent = load_agent(checkpoint_path, device=agent.device)

    assert isinstance(loaded_agent, DQNAgent)
    assert loaded_agent.hidden_sizes == (16,)
    assert loaded_agent.action_space_size == result.agent.action_space_size
    assert loaded_agent.architecture == "action_feature"


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
            record_trajectory=False,
        ),
        episodes=2,
        evaluation_interval=0,
        evaluation_episodes=1,
        replay_capacity=16,
        batch_size=1,
        warmup_steps=0,
        train_frequency=2,
        gradient_steps=1,
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
    assert result.best_evaluation is None
    assert result.restored_best_checkpoint is False
    assert result.agent.architecture == "action_feature"

    with TemporaryDirectory() as temp_dir:
        checkpoint_path = Path(temp_dir) / "double_dqn_agent.pt"
        save_agent(result.agent, checkpoint_path)
        loaded_agent = load_agent(checkpoint_path, device=agent.device)

    assert isinstance(loaded_agent, DoubleDQNAgent)
    assert loaded_agent.hidden_sizes == (16,)
    assert loaded_agent.action_space_size == result.agent.action_space_size
    assert loaded_agent.architecture == "action_feature"


def test_dueling_double_dqn_dependency_behavior() -> None:
    assert hasattr(game, "train_dueling_double_dqn")

    try:
        agent = DuelingDoubleDQNAgent(
            observation_size=25,
            action_space_size=11,
            hidden_sizes=(16,),
            seed=0,
        )
    except ModuleNotFoundError:
        return

    result = train_dueling_double_dqn(
        env_factory=lambda: CombatEnv(
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
            record_trajectory=False,
        ),
        episodes=2,
        evaluation_interval=0,
        evaluation_episodes=1,
        replay_capacity=16,
        batch_size=1,
        warmup_steps=0,
        train_frequency=2,
        gradient_steps=1,
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
    assert result.best_evaluation is None
    assert result.restored_best_checkpoint is False
    assert result.agent.architecture == "action_feature"

    with TemporaryDirectory() as temp_dir:
        checkpoint_path = Path(temp_dir) / "dueling_double_dqn_agent.pt"
        save_agent(result.agent, checkpoint_path)
        loaded_agent = load_agent(checkpoint_path, device=agent.device)

    assert isinstance(loaded_agent, DuelingDoubleDQNAgent)
    assert loaded_agent.hidden_sizes == (16,)
    assert loaded_agent.action_space_size == result.agent.action_space_size
    assert loaded_agent.architecture == "action_feature"


@pytest.mark.parametrize(
    "agent_class",
    (DQNAgent, DoubleDQNAgent, DuelingDoubleDQNAgent),
)
def test_shared_enemy_dqn_is_equivariant_to_enemy_slot_swaps(agent_class) -> None:
    if dqn_module.torch is None:
        return

    env = CombatEnvFactory(encounter_set="slimes", record_trajectory=False)()
    observation = env.reset(seed=7)
    swapped_observation = deepcopy(observation)
    swapped_observation["enemies"][1], swapped_observation["enemies"][2] = (
        swapped_observation["enemies"][2],
        swapped_observation["enemies"][1],
    )

    encoder = env.encoder
    action_mask = env.get_action_mask()
    state = encoder.encode(observation)
    swapped_state = encoder.encode(swapped_observation)
    action_features = encoder.encode_action_features(observation)
    swapped_action_features = encoder.encode_action_features(swapped_observation)
    agent = agent_class(**_shared_enemy_kwargs(env))

    q_values = agent.predict_q_values(state, action_mask, action_features)
    swapped_q_values = agent.predict_q_values(
        swapped_state,
        action_mask,
        swapped_action_features,
    )

    assert q_values[0] == pytest.approx(swapped_q_values[0], abs=1e-7)
    for hand_index in range(encoder.max_hand_size):
        target_zero_action = 1 + hand_index * encoder.max_enemy_count
        target_one_action = target_zero_action + 1
        target_two_action = target_zero_action + 2
        assert q_values[target_zero_action] == pytest.approx(
            swapped_q_values[target_zero_action],
            abs=1e-7,
        )
        assert q_values[target_one_action] == pytest.approx(
            swapped_q_values[target_two_action],
            abs=1e-7,
        )
        assert q_values[target_two_action] == pytest.approx(
            swapped_q_values[target_one_action],
            abs=1e-7,
        )


def test_shared_enemy_dqn_omits_target_slot_fraction() -> None:
    if dqn_module.torch is None:
        return

    env = CombatEnvFactory(encounter_set="slimes", record_trajectory=False)()
    observation = env.reset(seed=7)
    state = env.encode_observation(observation)
    action_mask = env.get_action_mask()
    action_features = env.encode_action_features(observation)
    slot_index = env.encoder.action_feature_names.index("target_slot_fraction")
    altered_action_features = tuple(
        tuple(
            0.9375 if feature_index == slot_index else feature
            for feature_index, feature in enumerate(feature_row)
        )
        for feature_row in action_features
    )
    agent = DQNAgent(**_shared_enemy_kwargs(env))

    original = agent.predict_q_values(state, action_mask, action_features)
    altered = agent.predict_q_values(state, action_mask, altered_action_features)

    assert altered == pytest.approx(original, abs=1e-7)


def test_shared_enemy_dueling_advantages_are_centered_over_legal_actions() -> None:
    if dqn_module.torch is None:
        return

    env = CombatEnvFactory(encounter_set="slimes", record_trajectory=False)()
    observation = env.reset(seed=7)
    state = env.encode_observation(observation)
    action_mask, action_features = env.encode_policy_inputs(observation)
    agent = DuelingDoubleDQNAgent(**_shared_enemy_kwargs(env))
    network = agent.policy_network
    state_tensor = dqn_module.torch.as_tensor(
        [state],
        dtype=dqn_module.torch.float32,
    )
    mask_tensor = dqn_module.torch.as_tensor([action_mask], dtype=dqn_module.torch.bool)
    feature_tensor = dqn_module.torch.as_tensor(
        [action_features],
        dtype=dqn_module.torch.float32,
    )

    with dqn_module.torch.no_grad():
        q_values = network(state_tensor, feature_tensor, mask_tensor)
        state_features, _joint_features = network._prepare_action_inputs(
            state_tensor,
            feature_tensor,
        )
        value = network.value_head(state_features).squeeze()
        legal_q_mean = q_values[0, mask_tensor[0]].mean()

    assert dqn_module.torch.allclose(legal_q_mean, value, atol=1e-7)


@pytest.mark.parametrize(
    "missing_field",
    (
        "max_enemy_count",
        "enemy_feature_start",
        "enemy_slot_feature_size",
        "uses_target_feature_index",
        "target_slot_feature_index",
    ),
)
def test_shared_enemy_dqn_requires_layout_metadata(missing_field: str) -> None:
    if dqn_module.torch is None:
        return

    env = CombatEnvFactory(encounter_set="slimes", record_trajectory=False)()
    kwargs = _shared_enemy_kwargs(env)
    kwargs.pop(missing_field)

    with pytest.raises(ValueError, match=missing_field):
        DQNAgent(**kwargs)


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "error_match"),
    (
        ("max_enemy_count", 0, "Enemy encoder dimensions"),
        ("enemy_feature_start", -1, "Enemy feature segment"),
        (
            "uses_target_feature_index",
            10_000,
            "Action feature index",
        ),
    ),
)
def test_shared_enemy_dqn_rejects_invalid_layout_metadata(
    field_name: str,
    invalid_value: int,
    error_match: str,
) -> None:
    if dqn_module.torch is None:
        return

    env = CombatEnvFactory(encounter_set="slimes", record_trajectory=False)()
    kwargs = _shared_enemy_kwargs(env)
    kwargs[field_name] = invalid_value

    with pytest.raises(ValueError, match=error_match):
        DQNAgent(**kwargs)


@pytest.mark.parametrize(
    ("trainer", "agent_class"),
    (
        (train_dqn, DQNAgent),
        (train_double_dqn, DoubleDQNAgent),
        (train_dueling_double_dqn, DuelingDoubleDQNAgent),
    ),
)
def test_shared_enemy_dqn_family_trains_and_round_trips_checkpoint(
    trainer,
    agent_class,
    tmp_path: Path,
) -> None:
    if dqn_module.torch is None:
        return

    env_factory = CombatEnvFactory(
        encounter_set="slimes",
        cards_per_turn=1,
        record_trajectory=False,
    )
    result = trainer(
        env_factory=env_factory,
        episodes=1,
        evaluation_interval=0,
        evaluation_episodes=1,
        replay_capacity=16,
        batch_size=1,
        warmup_steps=0,
        train_frequency=2,
        gradient_steps=1,
        target_update_interval=1,
        hidden_sizes=(16,),
        seed=0,
        epsilon=0.2,
        epsilon_min=0.0,
        epsilon_decay=0.9,
        architecture="shared_enemy",
        device="cpu",
    )
    checkpoint_path = tmp_path / f"{result.agent.algorithm_name}.pt"
    save_agent(result.agent, checkpoint_path)
    loaded_agent = load_agent(checkpoint_path, device="cpu")

    assert isinstance(loaded_agent, agent_class)
    assert loaded_agent.architecture == "shared_enemy"
    assert loaded_agent.max_enemy_count == 3
    assert loaded_agent.enemy_feature_start == result.agent.enemy_feature_start
    assert loaded_agent.enemy_slot_feature_size == result.agent.enemy_slot_feature_size
    assert (
        loaded_agent.uses_target_feature_index
        == result.agent.uses_target_feature_index
    )
    assert (
        loaded_agent.target_slot_feature_index
        == result.agent.target_slot_feature_index
    )

    env = env_factory()
    observation = env.reset(seed=11)
    state = env.encode_observation(observation)
    action_mask, action_features = env.encode_policy_inputs(observation)
    expected_q_values = result.agent.predict_q_values(
        state,
        action_mask,
        action_features,
    )
    loaded_q_values = loaded_agent.predict_q_values(
        state,
        action_mask,
        action_features,
    )
    assert loaded_q_values == pytest.approx(expected_q_values, abs=1e-7)


@pytest.mark.parametrize("architecture", ("flat", "action_feature"))
def test_legacy_dqn_checkpoint_loads_without_layout_metadata(
    architecture: str,
    tmp_path: Path,
) -> None:
    if dqn_module.torch is None:
        return

    env = CombatEnvFactory(encounter_set="slimes", record_trajectory=False)()
    agent = DQNAgent(
        observation_size=env.observation_size,
        action_space_size=env.action_space_size,
        hidden_sizes=(16,),
        architecture=architecture,
        action_feature_size=env.action_feature_size,
        device="cpu",
        seed=0,
    )
    payload = agent.checkpoint_payload()
    for field_name in (
        "max_enemy_count",
        "enemy_feature_start",
        "enemy_slot_feature_size",
        "uses_target_feature_index",
        "target_slot_feature_index",
    ):
        payload.pop(field_name)
    checkpoint_path = tmp_path / f"legacy_{architecture}.pt"
    dqn_module.torch.save(payload, checkpoint_path)

    loaded_agent = load_agent(checkpoint_path, device="cpu")

    assert isinstance(loaded_agent, DQNAgent)
    assert loaded_agent.architecture == architecture
    assert loaded_agent.max_enemy_count is None
