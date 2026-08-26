"""Persistence helpers for trained agents used in inspection workflows."""

from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Mapping

from . import dqn as dqn_module
from . import ppo as ppo_module
from .baselines import QLearningAgent
from .dqn import DQNAgent, DoubleDQNAgent, DuelingDoubleDQNAgent
from .ppo import PPOAgent

SupportedAgent = (
    QLearningAgent
    | DQNAgent
    | DoubleDQNAgent
    | DuelingDoubleDQNAgent
    | PPOAgent
)
CHECKPOINT_FORMAT_VERSION = 1


def save_agent(
    agent: SupportedAgent,
    path: str | Path,
    training_config: Mapping[str, Any] | None = None,
    run_metadata: Mapping[str, Any] | None = None,
    training_summary: Mapping[str, Any] | None = None,
) -> None:
    """Save a trained agent with optional reproducibility metadata."""
    save_path = Path(path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(agent, QLearningAgent):
        payload = agent.to_dict()
        _add_checkpoint_metadata(
            payload,
            training_config=training_config,
            run_metadata=run_metadata,
            training_summary=training_summary,
        )
        save_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        return

    if isinstance(agent, (DQNAgent, DoubleDQNAgent, DuelingDoubleDQNAgent)):
        if dqn_module.torch is None:
            raise ModuleNotFoundError(
                "Saving DQN-family agents requires the optional dependency 'torch'."
            )
        payload = agent.checkpoint_payload()
        _add_checkpoint_metadata(
            payload,
            training_config=training_config,
            run_metadata=run_metadata,
            training_summary=training_summary,
        )
        dqn_module.torch.save(payload, save_path)
        return

    if isinstance(agent, PPOAgent):
        if ppo_module.torch is None:
            raise ModuleNotFoundError(
                "Saving PPO agents requires the optional dependency 'torch'."
            )
        payload = agent.checkpoint_payload()
        _add_checkpoint_metadata(
            payload,
            training_config=training_config,
            run_metadata=run_metadata,
            training_summary=training_summary,
        )
        ppo_module.torch.save(payload, save_path)
        return

    raise TypeError(f"Unsupported agent type for saving: {type(agent)!r}")


def _add_checkpoint_metadata(
    payload: dict[str, Any],
    *,
    training_config: Mapping[str, Any] | None,
    run_metadata: Mapping[str, Any] | None,
    training_summary: Mapping[str, Any] | None,
) -> None:
    """Attach versioned optional metadata without changing agent loading semantics."""
    payload["checkpoint_format_version"] = CHECKPOINT_FORMAT_VERSION
    if training_config is not None:
        payload["training_config"] = dict(training_config)
    if run_metadata is not None:
        payload["run_metadata"] = dict(run_metadata)
    if training_summary is not None:
        payload["training_summary"] = dict(training_summary)


def load_agent(path: str | Path, device: str | None = None) -> SupportedAgent:
    """Load a saved agent from a checkpoint file or run directory."""
    load_path = resolve_agent_path(path)

    json_payload = _try_load_json_payload(load_path)
    if json_payload is not None:
        agent_type = json_payload.get("agent_type")
        if agent_type == "q_learning":
            return QLearningAgent.from_dict(json_payload)
        raise ValueError(f"Unsupported JSON agent type: {agent_type!r}")

    if dqn_module.torch is None and ppo_module.torch is None:
        raise ModuleNotFoundError(
            "Loading neural agents requires the optional dependency 'torch'."
        )

    torch_module = ppo_module.torch or dqn_module.torch
    checkpoint = torch_module.load(load_path, map_location="cpu")
    if not isinstance(checkpoint, dict):
        raise ValueError("Neural checkpoint must be a dictionary payload.")

    agent_type = checkpoint.get("agent_type")
    if agent_type == "dqn":
        agent_class = DQNAgent
    elif agent_type == "double_dqn":
        agent_class = DoubleDQNAgent
    elif agent_type == "dueling_double_dqn":
        agent_class = DuelingDoubleDQNAgent
    elif agent_type == "masked_ppo":
        agent_class = PPOAgent
    else:
        raise ValueError(f"Unsupported checkpoint agent type: {agent_type!r}")

    if agent_type == "masked_ppo":
        agent = agent_class(
            observation_size=int(checkpoint["observation_size"]),
            action_space_size=int(checkpoint["action_space_size"]),
            hidden_sizes=tuple(int(value) for value in checkpoint["hidden_sizes"]),
            learning_rate=float(checkpoint["learning_rate"]),
            discount=float(checkpoint["discount"]),
            gae_lambda=float(checkpoint["gae_lambda"]),
            clip_ratio=float(checkpoint["clip_ratio"]),
            value_loss_coef=float(checkpoint["value_loss_coef"]),
            entropy_coef=float(checkpoint["entropy_coef"]),
            ppo_epochs=int(checkpoint["ppo_epochs"]),
            minibatch_size=int(checkpoint["minibatch_size"]),
            max_grad_norm=(
                None
                if checkpoint["max_grad_norm"] is None
                else float(checkpoint["max_grad_norm"])
            ),
            policy_architecture=str(checkpoint.get("policy_architecture", "flat")),
            action_feature_size=(
                None
                if checkpoint.get("action_feature_size") is None
                else int(checkpoint["action_feature_size"])
            ),
            max_enemy_count=(
                None
                if checkpoint.get("max_enemy_count") is None
                else int(checkpoint["max_enemy_count"])
            ),
            enemy_feature_start=(
                None
                if checkpoint.get("enemy_feature_start") is None
                else int(checkpoint["enemy_feature_start"])
            ),
            enemy_slot_feature_size=(
                None
                if checkpoint.get("enemy_slot_feature_size") is None
                else int(checkpoint["enemy_slot_feature_size"])
            ),
            uses_target_feature_index=(
                None
                if checkpoint.get("uses_target_feature_index") is None
                else int(checkpoint["uses_target_feature_index"])
            ),
            target_slot_feature_index=(
                None
                if checkpoint.get("target_slot_feature_index") is None
                else int(checkpoint["target_slot_feature_index"])
            ),
            device=device,
        )
        agent.actor_critic.load_state_dict(checkpoint["actor_critic_state"])
        optimizer_state = checkpoint.get("optimizer_state")
        if optimizer_state is not None:
            agent.optimizer.load_state_dict(optimizer_state)
        return agent

    agent = agent_class(
        observation_size=int(checkpoint["observation_size"]),
        action_space_size=int(checkpoint["action_space_size"]),
        hidden_sizes=tuple(int(value) for value in checkpoint["hidden_sizes"]),
        learning_rate=float(checkpoint["learning_rate"]),
        discount=float(checkpoint["discount"]),
        epsilon=float(checkpoint["epsilon"]),
        epsilon_min=float(checkpoint["epsilon_min"]),
        epsilon_decay=float(checkpoint["epsilon_decay"]),
        architecture=str(checkpoint.get("architecture", "flat")),
        action_feature_size=(
            None
            if checkpoint.get("action_feature_size") is None
            else int(checkpoint["action_feature_size"])
        ),
        max_enemy_count=(
            None
            if checkpoint.get("max_enemy_count") is None
            else int(checkpoint["max_enemy_count"])
        ),
        enemy_feature_start=(
            None
            if checkpoint.get("enemy_feature_start") is None
            else int(checkpoint["enemy_feature_start"])
        ),
        enemy_slot_feature_size=(
            None
            if checkpoint.get("enemy_slot_feature_size") is None
            else int(checkpoint["enemy_slot_feature_size"])
        ),
        uses_target_feature_index=(
            None
            if checkpoint.get("uses_target_feature_index") is None
            else int(checkpoint["uses_target_feature_index"])
        ),
        target_slot_feature_index=(
            None
            if checkpoint.get("target_slot_feature_index") is None
            else int(checkpoint["target_slot_feature_index"])
        ),
        device=device,
    )
    agent.policy_network.load_state_dict(checkpoint["policy_network_state"])
    agent.target_network.load_state_dict(checkpoint["target_network_state"])
    optimizer_state = checkpoint.get("optimizer_state")
    if optimizer_state is not None:
        agent.optimizer.load_state_dict(optimizer_state)
    return agent


def resolve_agent_path(path: str | Path) -> Path:
    """Resolve a checkpoint file directly or from a standard run directory."""
    candidate = Path(path)
    if not candidate.is_dir():
        return candidate

    checkpoint_candidates = tuple(
        checkpoint_path
        for checkpoint_path in (
            candidate / "checkpoint.pt",
            candidate / "checkpoint.json",
        )
        if checkpoint_path.is_file()
    )
    if len(checkpoint_candidates) == 1:
        return checkpoint_candidates[0]
    if not checkpoint_candidates:
        raise FileNotFoundError(
            f"Run directory {candidate} does not contain checkpoint.pt or checkpoint.json."
        )
    raise ValueError(
        f"Run directory {candidate} contains multiple checkpoint files; pass one explicitly."
    )


def _try_load_json_payload(path: Path) -> dict[str, Any] | None:
    """Attempt to load a JSON agent payload, returning None if it is not JSON."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None

    try:
        payload = json.loads(text)
    except JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Serialized JSON agent payload must be a dictionary.")
    return payload
