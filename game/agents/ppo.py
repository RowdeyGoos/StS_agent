"""Masked PPO utilities for the combat environment."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from random import Random
from time import perf_counter
from typing import Any, Callable, Mapping, Sequence

from .baselines import (
    EpisodeMetrics,
    EvaluationSnapshot,
    EvaluationStats,
    ProgressCallback,
    _maybe_report_progress,
    _episode_seed,
    evaluate_policy,
)
from ..simulation.core import CombatEnv, Observation
from .torch_device import resolve_torch_device
from ..training.profile import TrainingProfile, TrainingProfiler, profile_phase

VectorObservation = tuple[float, ...]
ActionMask = tuple[int, ...]
ActionFeatureBatch = tuple[tuple[float, ...], ...]


def _compute_interleaved_gae(
    rewards: Sequence[float],
    dones: Sequence[bool],
    values: Sequence[float],
    environment_ids: Sequence[int],
    last_value: float | Mapping[int, float],
    discount: float,
    gae_lambda: float,
) -> tuple[list[float], list[float]]:
    """Compute GAE without mixing interleaved environment trajectories."""
    rollout_size = len(rewards)
    if not (
        len(dones) == rollout_size
        and len(values) == rollout_size
        and len(environment_ids) == rollout_size
    ):
        raise ValueError("Rollout GAE inputs must have equal lengths.")

    advantages = [0.0] * rollout_size
    returns = [0.0] * rollout_size
    if isinstance(last_value, Mapping):
        next_values = {
            int(environment_id): float(value)
            for environment_id, value in last_value.items()
        }
    else:
        next_values = {0: float(last_value)}
    gae_by_environment: dict[int, float] = {}

    for step_index in range(rollout_size - 1, -1, -1):
        environment_id = environment_ids[step_index]
        next_non_terminal = 0.0 if dones[step_index] else 1.0
        if next_non_terminal and environment_id not in next_values:
            raise ValueError(
                "A bootstrap value is required for every non-terminal "
                "environment trajectory."
            )
        next_state_value = next_values.get(environment_id, 0.0)
        delta = (
            rewards[step_index]
            + discount * next_state_value * next_non_terminal
            - values[step_index]
        )
        gae = (
            delta
            + discount
            * gae_lambda
            * next_non_terminal
            * gae_by_environment.get(environment_id, 0.0)
        )
        advantages[step_index] = gae
        returns[step_index] = gae + values[step_index]
        gae_by_environment[environment_id] = gae
        next_values[environment_id] = values[step_index]

    return advantages, returns

try:
    import numpy as np
    import torch
    from torch import Tensor, nn, optim
    from torch.distributions import Categorical
except ModuleNotFoundError:  # pragma: no cover - depends on optional dependency
    np = None
    torch = None
    Tensor = Any
    nn = None
    optim = None
    Categorical = Any


@dataclass(frozen=True, slots=True)
class PPOTrainingResult:
    """Outputs from masked PPO training and evaluation."""

    agent: "PPOAgent"
    training_metrics: tuple[EpisodeMetrics, ...]
    evaluations: tuple[EvaluationSnapshot, ...]
    final_evaluation: EvaluationStats
    optimization_steps: int
    mean_total_losses: tuple[float, ...]
    mean_policy_losses: tuple[float, ...]
    mean_value_losses: tuple[float, ...]
    mean_entropies: tuple[float, ...]
    num_envs: int = 1
    env_workers: int = 0
    profile: TrainingProfile | None = None
    best_evaluation: EvaluationSnapshot | None = None
    restored_best_checkpoint: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return a compact summary for loggers and notebooks."""
        return {
            "episodes": len(self.training_metrics),
            "optimization_steps": self.optimization_steps,
            "num_envs": self.num_envs,
            "env_workers": self.env_workers,
            "device": self.agent.device,
            "profile": None if self.profile is None else self.profile.summary_dict(),
            "final_evaluation": self.final_evaluation.as_dict(),
            "best_evaluation": (
                None
                if self.best_evaluation is None
                else {
                    "episode": self.best_evaluation.episode,
                    **self.best_evaluation.stats.as_dict(),
                }
            ),
            "restored_best_checkpoint": self.restored_best_checkpoint,
            "evaluation_points": [
                {"episode": snapshot.episode, **snapshot.stats.as_dict()}
                for snapshot in self.evaluations
            ],
        }


if torch is not None and nn is not None and optim is not None:

    class PPOActorCriticNetwork(nn.Module):
        """Shared MLP with a flat discrete policy head plus a value head."""

        def __init__(
            self,
            input_dim: int,
            output_dim: int,
            hidden_sizes: Sequence[int] = (128, 128),
        ) -> None:
            super().__init__()
            if input_dim <= 0 or output_dim <= 0:
                raise ValueError("input_dim and output_dim must be positive.")
            if not hidden_sizes:
                raise ValueError("hidden_sizes must contain at least one layer size.")

            layers: list[nn.Module] = []
            current_dim = input_dim
            for hidden_dim in hidden_sizes:
                if hidden_dim <= 0:
                    raise ValueError("Hidden layer sizes must be positive.")
                layers.append(nn.Linear(current_dim, hidden_dim))
                layers.append(nn.ReLU())
                current_dim = hidden_dim

            self.feature_extractor = nn.Sequential(*layers)
            self.policy_head = nn.Linear(current_dim, output_dim)
            self.value_head = nn.Linear(current_dim, 1)

        def forward(
            self,
            inputs: Tensor,
            action_features: Tensor | None = None,
        ) -> tuple[Tensor, Tensor]:
            """Return flat action logits and scalar state values for a batch."""
            del action_features
            features = self.feature_extractor(inputs)
            return self.policy_head(features), self.value_head(features).squeeze(-1)

        def state_values(self, inputs: Tensor) -> Tensor:
            """Return scalar state values without requiring action features."""
            features = self.feature_extractor(inputs)
            return self.value_head(features).squeeze(-1)


    class ActionConditionedPPOActorCriticNetwork(nn.Module):
        """Actor-critic network that scores legal actions from action features."""

        def __init__(
            self,
            input_dim: int,
            action_feature_dim: int,
            hidden_sizes: Sequence[int] = (128, 128),
        ) -> None:
            super().__init__()
            if input_dim <= 0 or action_feature_dim <= 0:
                raise ValueError("input_dim and action_feature_dim must be positive.")
            if not hidden_sizes:
                raise ValueError("hidden_sizes must contain at least one layer size.")

            feature_layers: list[nn.Module] = []
            current_dim = input_dim
            for hidden_dim in hidden_sizes:
                if hidden_dim <= 0:
                    raise ValueError("Hidden layer sizes must be positive.")
                feature_layers.append(nn.Linear(current_dim, hidden_dim))
                feature_layers.append(nn.ReLU())
                current_dim = hidden_dim

            joint_hidden_dim = current_dim
            self.feature_extractor = nn.Sequential(*feature_layers)
            self.action_scorer = nn.Sequential(
                nn.Linear(current_dim + action_feature_dim, joint_hidden_dim),
                nn.ReLU(),
                nn.Linear(joint_hidden_dim, 1),
            )
            self.value_head = nn.Linear(current_dim, 1)

        def forward(
            self,
            inputs: Tensor,
            action_features: Tensor | None = None,
        ) -> tuple[Tensor, Tensor]:
            """Return per-action logits and scalar state values for a batch."""
            if action_features is None:
                raise ValueError(
                    "Action-conditioned PPO requires action feature tensors."
                )

            state_features = self.feature_extractor(inputs)
            repeated_state_features = state_features.unsqueeze(1).expand(
                -1,
                action_features.shape[1],
                -1,
            )
            joint_features = torch.cat(
                [repeated_state_features, action_features],
                dim=-1,
            )
            logits = self.action_scorer(joint_features).squeeze(-1)
            values = self.value_head(state_features).squeeze(-1)
            return logits, values

        def state_values(self, inputs: Tensor) -> Tensor:
            """Return scalar state values without requiring action features."""
            state_features = self.feature_extractor(inputs)
            return self.value_head(state_features).squeeze(-1)


    class SharedEnemyPPOActorCriticNetwork(nn.Module):
        """Score actions with permutation-equivariant shared enemy embeddings."""

        def __init__(
            self,
            input_dim: int,
            output_dim: int,
            action_feature_dim: int,
            max_enemy_count: int,
            enemy_feature_start: int,
            enemy_slot_feature_dim: int,
            uses_target_feature_index: int,
            target_slot_feature_index: int,
            hidden_sizes: Sequence[int] = (128, 128),
        ) -> None:
            super().__init__()
            if input_dim <= 0 or output_dim <= 0 or action_feature_dim <= 1:
                raise ValueError("Network input and output dimensions must be positive.")
            if max_enemy_count <= 0 or enemy_slot_feature_dim <= 0:
                raise ValueError("Enemy encoder dimensions must be positive.")
            if not hidden_sizes or any(size <= 0 for size in hidden_sizes):
                raise ValueError("hidden_sizes must contain positive layer sizes.")
            enemy_feature_end = (
                enemy_feature_start + max_enemy_count * enemy_slot_feature_dim
            )
            if enemy_feature_start < 0 or enemy_feature_end > input_dim:
                raise ValueError("Enemy feature segment falls outside the observation.")
            for feature_index in (
                uses_target_feature_index,
                target_slot_feature_index,
            ):
                if not 0 <= feature_index < action_feature_dim:
                    raise ValueError("Action feature index falls outside its feature row.")

            self.output_dim = output_dim
            self.max_enemy_count = max_enemy_count
            self.enemy_feature_start = enemy_feature_start
            self.enemy_feature_end = enemy_feature_end
            self.enemy_slot_feature_dim = enemy_slot_feature_dim
            self.uses_target_feature_index = uses_target_feature_index
            self.target_slot_feature_index = target_slot_feature_index

            embedding_dim = int(hidden_sizes[0])
            self.enemy_encoder = nn.Sequential(
                nn.Linear(enemy_slot_feature_dim, embedding_dim),
                nn.ReLU(),
            )

            non_enemy_dim = input_dim - max_enemy_count * enemy_slot_feature_dim
            state_layers: list[nn.Module] = []
            current_dim = non_enemy_dim + embedding_dim
            for hidden_dim in hidden_sizes:
                state_layers.append(nn.Linear(current_dim, hidden_dim))
                state_layers.append(nn.ReLU())
                current_dim = hidden_dim
            self.state_encoder = nn.Sequential(*state_layers)
            self.action_scorer = nn.Sequential(
                nn.Linear(
                    current_dim + embedding_dim + action_feature_dim - 1,
                    current_dim,
                ),
                nn.ReLU(),
                nn.Linear(current_dim, 1),
            )
            self.value_head = nn.Linear(current_dim, 1)

            target_indices = [
                0 if action_index == 0 else (action_index - 1) % max_enemy_count
                for action_index in range(output_dim)
            ]
            self.register_buffer(
                "action_target_indices",
                torch.as_tensor(target_indices, dtype=torch.long),
                persistent=False,
            )

        def _encode_state(self, inputs: Tensor) -> tuple[Tensor, Tensor]:
            enemy_slots = inputs[
                :, self.enemy_feature_start : self.enemy_feature_end
            ].reshape(-1, self.max_enemy_count, self.enemy_slot_feature_dim)
            enemy_embeddings = self.enemy_encoder(enemy_slots)

            # "alive" is the first feature in every encoded enemy slot. Masking
            # after the shared MLP also removes its bias for padded/dead slots.
            alive_mask = enemy_slots[..., :1].clamp(0.0, 1.0)
            living_enemy_embeddings = enemy_embeddings * alive_mask
            pooled_enemy_embedding = living_enemy_embeddings.sum(dim=1) / (
                alive_mask.sum(dim=1).clamp_min(1.0)
            )
            non_enemy_features = torch.cat(
                [
                    inputs[:, : self.enemy_feature_start],
                    inputs[:, self.enemy_feature_end :],
                ],
                dim=-1,
            )
            state_features = self.state_encoder(
                torch.cat([non_enemy_features, pooled_enemy_embedding], dim=-1)
            )
            return state_features, living_enemy_embeddings

        def forward(
            self,
            inputs: Tensor,
            action_features: Tensor | None = None,
        ) -> tuple[Tensor, Tensor]:
            """Return target-aware logits and scalar values for a batch."""
            if action_features is None:
                raise ValueError("Shared-enemy PPO requires action feature tensors.")
            if action_features.shape[1] != self.output_dim:
                raise ValueError("Action feature rows do not match the action space.")

            state_features, enemy_embeddings = self._encode_state(inputs)
            target_embeddings = enemy_embeddings[:, self.action_target_indices, :]
            uses_target = action_features[
                ..., self.uses_target_feature_index : self.uses_target_feature_index + 1
            ]
            target_embeddings = target_embeddings * uses_target

            # The discrete action index still selects the stable enemy slot, but
            # its ordinal fraction must not become a learnable target preference.
            slot_index = self.target_slot_feature_index
            position_free_action_features = torch.cat(
                [
                    action_features[..., :slot_index],
                    action_features[..., slot_index + 1 :],
                ],
                dim=-1,
            )
            repeated_state_features = state_features.unsqueeze(1).expand(
                -1, self.output_dim, -1
            )
            logits = self.action_scorer(
                torch.cat(
                    [
                        repeated_state_features,
                        target_embeddings,
                        position_free_action_features,
                    ],
                    dim=-1,
                )
            ).squeeze(-1)
            return logits, self.value_head(state_features).squeeze(-1)

        def state_values(self, inputs: Tensor) -> Tensor:
            """Return values from permutation-invariant pooled enemy context."""
            state_features, _enemy_embeddings = self._encode_state(inputs)
            return self.value_head(state_features).squeeze(-1)


    @dataclass(slots=True)
    class PPORolloutBuffer:
        """Simple on-policy rollout storage used by masked PPO."""

        states: list[VectorObservation]
        actions: list[int]
        rewards: list[float]
        dones: list[bool]
        values: list[float]
        log_probs: list[float]
        action_masks: list[ActionMask]
        action_features: list[ActionFeatureBatch]
        environment_ids: list[int]

        def __init__(self) -> None:
            self.states = []
            self.actions = []
            self.rewards = []
            self.dones = []
            self.values = []
            self.log_probs = []
            self.action_masks = []
            self.action_features = []
            self.environment_ids = []

        def add(
            self,
            state: VectorObservation,
            action: int,
            reward: float,
            done: bool,
            value: float,
            log_prob: float,
            action_mask: ActionMask,
            action_features: ActionFeatureBatch,
            environment_id: int = 0,
        ) -> None:
            """Append one on-policy transition."""
            self.states.append(state)
            self.actions.append(action)
            self.rewards.append(reward)
            self.dones.append(done)
            self.values.append(value)
            self.log_probs.append(log_prob)
            self.action_masks.append(action_mask)
            self.action_features.append(action_features)
            self.environment_ids.append(environment_id)

        def __len__(self) -> int:
            return len(self.actions)

        def compute_returns_and_advantages(
            self,
            last_value: float | Mapping[int, float],
            discount: float,
            gae_lambda: float,
            device: str,
        ) -> dict[str, Tensor]:
            """Return tensorized rollout data plus GAE returns/advantages."""
            advantages, returns = _compute_interleaved_gae(
                rewards=self.rewards,
                dones=self.dones,
                values=self.values,
                environment_ids=self.environment_ids,
                last_value=last_value,
                discount=discount,
                gae_lambda=gae_lambda,
            )

            states = np.asarray(self.states, dtype=np.float32)
            actions = np.asarray(self.actions, dtype=np.int64)
            old_log_probs = np.asarray(self.log_probs, dtype=np.float32)
            action_masks = np.asarray(self.action_masks, dtype=np.bool_)
            action_features = np.asarray(self.action_features, dtype=np.float32)
            return {
                "states": torch.as_tensor(states, dtype=torch.float32, device=device),
                "actions": torch.as_tensor(actions, dtype=torch.long, device=device),
                "old_log_probs": torch.as_tensor(
                    old_log_probs,
                    dtype=torch.float32,
                    device=device,
                ),
                "action_masks": torch.as_tensor(
                    action_masks,
                    dtype=torch.bool,
                    device=device,
                ),
                "action_features": torch.as_tensor(
                    action_features,
                    dtype=torch.float32,
                    device=device,
                ),
                "returns": torch.as_tensor(returns, dtype=torch.float32, device=device),
                "advantages": torch.as_tensor(
                    advantages,
                    dtype=torch.float32,
                    device=device,
                ),
            }


    class PPOAgent:
        """Masked PPO agent with flat or action-conditioned policy scoring."""

        def __init__(
            self,
            observation_size: int,
            action_space_size: int,
            hidden_sizes: Sequence[int] = (128, 128),
            learning_rate: float = 3e-4,
            discount: float = 0.99,
            gae_lambda: float = 0.95,
            clip_ratio: float = 0.2,
            value_loss_coef: float = 0.5,
            entropy_coef: float = 0.01,
            ppo_epochs: int = 4,
            minibatch_size: int = 64,
            max_grad_norm: float | None = 0.5,
            policy_architecture: str = "flat",
            action_feature_size: int | None = None,
            max_enemy_count: int | None = None,
            enemy_feature_start: int | None = None,
            enemy_slot_feature_size: int | None = None,
            uses_target_feature_index: int | None = None,
            target_slot_feature_index: int | None = None,
            device: str | None = None,
            seed: int | None = None,
        ) -> None:
            if observation_size <= 0 or action_space_size <= 0:
                raise ValueError("observation_size and action_space_size must be positive.")
            if ppo_epochs <= 0:
                raise ValueError("ppo_epochs must be positive.")
            if minibatch_size <= 0:
                raise ValueError("minibatch_size must be positive.")

            if seed is not None:
                torch.manual_seed(seed)

            self.observation_size = observation_size
            self.action_space_size = action_space_size
            self.hidden_sizes = tuple(int(hidden_size) for hidden_size in hidden_sizes)
            self.learning_rate = learning_rate
            self.discount = discount
            self.gae_lambda = gae_lambda
            self.clip_ratio = clip_ratio
            self.value_loss_coef = value_loss_coef
            self.entropy_coef = entropy_coef
            self.ppo_epochs = ppo_epochs
            self.minibatch_size = minibatch_size
            self.max_grad_norm = max_grad_norm
            self.policy_architecture = policy_architecture
            self.action_feature_size = action_feature_size
            self.max_enemy_count = max_enemy_count
            self.enemy_feature_start = enemy_feature_start
            self.enemy_slot_feature_size = enemy_slot_feature_size
            self.uses_target_feature_index = uses_target_feature_index
            self.target_slot_feature_index = target_slot_feature_index
            self.device = resolve_torch_device(device, torch)
            self.rng = Random(seed)

            if self.policy_architecture not in {
                "flat",
                "action_feature",
                "shared_enemy",
            }:
                raise ValueError(
                    "policy_architecture must be 'flat', 'action_feature', or "
                    "'shared_enemy'."
                )
            if self.policy_architecture == "action_feature":
                if self.action_feature_size is None or self.action_feature_size <= 0:
                    raise ValueError(
                        "action_feature_size must be positive for action_feature PPO."
                    )
                self.actor_critic = ActionConditionedPPOActorCriticNetwork(
                    input_dim=observation_size,
                    action_feature_dim=self.action_feature_size,
                    hidden_sizes=hidden_sizes,
                ).to(self.device)
            elif self.policy_architecture == "shared_enemy":
                required_metadata = {
                    "max_enemy_count": self.max_enemy_count,
                    "enemy_feature_start": self.enemy_feature_start,
                    "enemy_slot_feature_size": self.enemy_slot_feature_size,
                    "uses_target_feature_index": self.uses_target_feature_index,
                    "target_slot_feature_index": self.target_slot_feature_index,
                }
                if self.action_feature_size is None or self.action_feature_size <= 0:
                    raise ValueError(
                        "action_feature_size must be positive for shared_enemy PPO."
                    )
                if any(value is None for value in required_metadata.values()):
                    missing = ", ".join(
                        name for name, value in required_metadata.items() if value is None
                    )
                    raise ValueError(
                        f"Shared-enemy PPO is missing encoder metadata: {missing}."
                    )
                self.actor_critic = SharedEnemyPPOActorCriticNetwork(
                    input_dim=observation_size,
                    output_dim=action_space_size,
                    action_feature_dim=self.action_feature_size,
                    max_enemy_count=int(self.max_enemy_count),
                    enemy_feature_start=int(self.enemy_feature_start),
                    enemy_slot_feature_dim=int(self.enemy_slot_feature_size),
                    uses_target_feature_index=int(self.uses_target_feature_index),
                    target_slot_feature_index=int(self.target_slot_feature_index),
                    hidden_sizes=hidden_sizes,
                ).to(self.device)
            else:
                self.actor_critic = PPOActorCriticNetwork(
                    input_dim=observation_size,
                    output_dim=action_space_size,
                    hidden_sizes=hidden_sizes,
                ).to(self.device)
            self.optimizer = optim.Adam(self.actor_critic.parameters(), lr=learning_rate)

        @property
        def algorithm_name(self) -> str:
            """Return the stable algorithm name used in saved checkpoints."""
            return "masked_ppo"

        def select_action(
            self,
            state: VectorObservation,
            action_mask: ActionMask,
            action_features: ActionFeatureBatch | None = None,
            training: bool = True,
        ) -> int:
            """Choose an action from the masked policy."""
            action, _log_prob, _value = self.sample_action(
                state,
                action_mask,
                action_features=action_features,
                training=training,
            )
            return action

        def sample_action(
            self,
            state: VectorObservation,
            action_mask: ActionMask,
            action_features: ActionFeatureBatch | None = None,
            training: bool = True,
        ) -> tuple[int, float, float]:
            """Sample or greedily choose one legal action, returning action/log-prob/value."""
            return self.sample_actions(
                states=(state,),
                action_masks=(action_mask,),
                action_features=(
                    None if action_features is None else (action_features,)
                ),
                training=training,
            )[0]

        def sample_actions(
            self,
            states: Sequence[VectorObservation],
            action_masks: Sequence[ActionMask],
            action_features: Sequence[ActionFeatureBatch] | None = None,
            training: bool = True,
        ) -> list[tuple[int, float, float]]:
            """Sample or greedily choose actions for a batch of environment states."""
            batch_size = len(states)
            if batch_size == 0:
                return []
            if len(action_masks) != batch_size:
                raise ValueError("states and action_masks must have equal lengths.")
            if action_features is not None and len(action_features) != batch_size:
                raise ValueError("states and action_features must have equal lengths.")

            with torch.no_grad():
                state_tensor = torch.as_tensor(
                    states,
                    dtype=torch.float32,
                    device=self.device,
                )
                action_mask_tensor = torch.as_tensor(
                    action_masks,
                    dtype=torch.bool,
                    device=self.device,
                )
                action_feature_tensor = self._action_feature_batch_tensor(action_features)
                logits, values = self.actor_critic(state_tensor, action_feature_tensor)
                distribution = self._distribution_from_logits(logits, action_mask_tensor)
                if training:
                    # CPU multinomial avoids an MPS defect that can intermittently
                    # select zero-probability (masked) actions.
                    action_tensor = torch.multinomial(
                        distribution.probs.detach().cpu(),
                        num_samples=1,
                    ).squeeze(1).to(self.device)
                else:
                    action_tensor = distribution.probs.argmax(dim=1)
                log_prob_tensor = distribution.log_prob(action_tensor)

            actions = [int(value) for value in action_tensor.detach().cpu().tolist()]
            log_probs = [
                float(value) for value in log_prob_tensor.detach().cpu().tolist()
            ]
            state_values = [float(value) for value in values.detach().cpu().tolist()]
            for batch_index, action in enumerate(actions):
                if not action_masks[batch_index][action]:
                    raise RuntimeError(
                        "Masked PPO sampled an illegal action at batch index "
                        f"{batch_index}: {action}."
                    )
            return list(zip(actions, log_probs, state_values))

        def predict_action_scores(
            self,
            state: VectorObservation,
            action_mask: ActionMask,
            action_features: ActionFeatureBatch | None = None,
        ) -> list[float]:
            """Return masked action probabilities for one encoded state."""
            with torch.no_grad():
                state_tensor = torch.as_tensor(
                    state,
                    dtype=torch.float32,
                    device=self.device,
                ).unsqueeze(0)
                action_mask_tensor = torch.as_tensor(
                    action_mask,
                    dtype=torch.bool,
                    device=self.device,
                ).unsqueeze(0)
                action_feature_tensor = self._action_feature_tensor(action_features)
                logits, _values = self.actor_critic(state_tensor, action_feature_tensor)
                distribution = self._distribution_from_logits(logits, action_mask_tensor)
                probabilities = distribution.probs.squeeze(0)
            return [float(value) for value in probabilities.detach().cpu().tolist()]

        def predict_value(self, state: VectorObservation) -> float:
            """Return the state-value estimate for one encoded state."""
            return self.predict_values((state,))[0]

        def predict_values(
            self,
            states: Sequence[VectorObservation],
        ) -> list[float]:
            """Return state-value estimates for a batch of encoded states."""
            if len(states) == 0:
                return []
            with torch.no_grad():
                state_tensor = torch.as_tensor(
                    states,
                    dtype=torch.float32,
                    device=self.device,
                )
                values = self.actor_critic.state_values(state_tensor)
            return [float(value) for value in values.detach().cpu().tolist()]

        def checkpoint_payload(self) -> dict[str, Any]:
            """Return a serializable snapshot of the agent state."""
            return {
                "agent_type": self.algorithm_name,
                "observation_size": self.observation_size,
                "action_space_size": self.action_space_size,
                "hidden_sizes": list(self.hidden_sizes),
                "learning_rate": self.learning_rate,
                "discount": self.discount,
                "gae_lambda": self.gae_lambda,
                "clip_ratio": self.clip_ratio,
                "value_loss_coef": self.value_loss_coef,
                "entropy_coef": self.entropy_coef,
                "ppo_epochs": self.ppo_epochs,
                "minibatch_size": self.minibatch_size,
                "max_grad_norm": self.max_grad_norm,
                "policy_architecture": self.policy_architecture,
                "action_feature_size": self.action_feature_size,
                "max_enemy_count": self.max_enemy_count,
                "enemy_feature_start": self.enemy_feature_start,
                "enemy_slot_feature_size": self.enemy_slot_feature_size,
                "uses_target_feature_index": self.uses_target_feature_index,
                "target_slot_feature_index": self.target_slot_feature_index,
                "actor_critic_state": self.actor_critic.state_dict(),
                "optimizer_state": self.optimizer.state_dict(),
            }

        def optimize(
            self,
            rollout: PPORolloutBuffer,
            last_value: float | Mapping[int, float],
            profiler: TrainingProfiler | None = None,
        ) -> tuple[float, float, float, float, int]:
            """Run PPO updates over one rollout buffer."""
            if len(rollout) == 0:
                return 0.0, 0.0, 0.0, 0.0, 0

            with profile_phase(profiler, "ppo.gae_and_tensorization"):
                tensors = rollout.compute_returns_and_advantages(
                    last_value=last_value,
                    discount=self.discount,
                    gae_lambda=self.gae_lambda,
                    device=self.device,
                )

                advantages = tensors["advantages"]
                advantages = (advantages - advantages.mean()) / (
                    advantages.std(unbiased=False) + 1e-8
                )

            rollout_size = len(rollout)
            minibatch_size = min(self.minibatch_size, rollout_size)
            total_loss_sum = 0.0
            policy_loss_sum = 0.0
            value_loss_sum = 0.0
            entropy_sum = 0.0
            optimization_steps = 0

            with profile_phase(profiler, "ppo.gradient_updates"):
                for _epoch_index in range(self.ppo_epochs):
                    permutation = torch.randperm(rollout_size, device=self.device)
                    for start in range(0, rollout_size, minibatch_size):
                        batch_indices = permutation[start : start + minibatch_size]
                        batch_states = tensors["states"][batch_indices]
                        batch_actions = tensors["actions"][batch_indices]
                        batch_old_log_probs = tensors["old_log_probs"][batch_indices]
                        batch_returns = tensors["returns"][batch_indices]
                        batch_advantages = advantages[batch_indices]
                        batch_action_masks = tensors["action_masks"][batch_indices]
                        batch_action_features = tensors["action_features"][batch_indices]

                        logits, values = self.actor_critic(
                            batch_states,
                            (
                                batch_action_features
                                if self.policy_architecture
                                in {"action_feature", "shared_enemy"}
                                else None
                            ),
                        )
                        distribution = self._distribution_from_logits(
                            logits, batch_action_masks
                        )
                        new_log_probs = distribution.log_prob(batch_actions)
                        entropy = distribution.entropy().mean()

                        probability_ratio = torch.exp(
                            new_log_probs - batch_old_log_probs
                        )
                        unclipped_objective = probability_ratio * batch_advantages
                        clipped_objective = torch.clamp(
                            probability_ratio,
                            1.0 - self.clip_ratio,
                            1.0 + self.clip_ratio,
                        ) * batch_advantages
                        policy_loss = -torch.minimum(
                            unclipped_objective, clipped_objective
                        ).mean()
                        value_loss = ((values - batch_returns) ** 2).mean()
                        total_loss = (
                            policy_loss
                            + self.value_loss_coef * value_loss
                            - self.entropy_coef * entropy
                        )

                        self.optimizer.zero_grad(set_to_none=True)
                        total_loss.backward()
                        if self.max_grad_norm is not None:
                            nn.utils.clip_grad_norm_(
                                self.actor_critic.parameters(),
                                self.max_grad_norm,
                            )
                        self.optimizer.step()

                        total_loss_sum += float(total_loss.item())
                        policy_loss_sum += float(policy_loss.item())
                        value_loss_sum += float(value_loss.item())
                        entropy_sum += float(entropy.item())
                        optimization_steps += 1

            divisor = max(1, optimization_steps)
            return (
                total_loss_sum / divisor,
                policy_loss_sum / divisor,
                value_loss_sum / divisor,
                entropy_sum / divisor,
                optimization_steps,
            )

        def _action_feature_tensor(
            self,
            action_features: ActionFeatureBatch | None,
        ) -> Tensor | None:
            if self.policy_architecture not in {"action_feature", "shared_enemy"}:
                return None
            if action_features is None:
                raise ValueError(
                    "Action-conditioned PPO requires action features for action selection."
                )
            return torch.as_tensor(
                action_features,
                dtype=torch.float32,
                device=self.device,
            ).unsqueeze(0)

        def _action_feature_batch_tensor(
            self,
            action_features: Sequence[ActionFeatureBatch] | None,
        ) -> Tensor | None:
            if self.policy_architecture not in {"action_feature", "shared_enemy"}:
                return None
            if action_features is None:
                raise ValueError(
                    "Action-conditioned PPO requires action features for action selection."
                )
            return torch.as_tensor(
                action_features,
                dtype=torch.float32,
                device=self.device,
            )

        def _distribution_from_logits(
            self,
            logits: Tensor,
            action_masks: Tensor,
        ) -> Categorical:
            masked_logits = _mask_policy_logits(logits, action_masks)
            return Categorical(logits=masked_logits)


    def train_masked_ppo(
        env_factory: Callable[[], CombatEnv],
        episodes: int,
        evaluation_interval: int = 100,
        evaluation_episodes: int = 25,
        rollout_steps: int = 512,
        num_envs: int = 1,
        env_workers: int = 0,
        hidden_sizes: Sequence[int] = (128, 128),
        seed: int | None = None,
        final_evaluation_seed: int | None = None,
        learning_rate: float = 3e-4,
        discount: float = 0.99,
        gae_lambda: float = 0.95,
        clip_ratio: float = 0.2,
        value_loss_coef: float = 0.5,
        entropy_coef: float = 0.01,
        ppo_epochs: int = 4,
        minibatch_size: int = 64,
        max_grad_norm: float | None = 0.5,
        policy_architecture: str = "action_feature",
        device: str | None = None,
        restore_best_checkpoint: bool = True,
        profiler: TrainingProfiler | None = None,
        progress_callback: ProgressCallback | None = None,
        progress_interval: int = 25,
        progress_window: int = 25,
    ) -> PPOTrainingResult:
        """Train a masked PPO agent and periodically evaluate greedy performance."""
        if episodes <= 0:
            raise ValueError("episodes must be positive.")
        if evaluation_interval < 0:
            raise ValueError("evaluation_interval cannot be negative.")
        if evaluation_episodes <= 0:
            raise ValueError("evaluation_episodes must be positive.")
        if rollout_steps <= 0:
            raise ValueError("rollout_steps must be positive.")
        if num_envs <= 0:
            raise ValueError("num_envs must be positive.")
        if env_workers < 0:
            raise ValueError("env_workers cannot be negative.")
        if env_workers > min(num_envs, episodes):
            raise ValueError("env_workers cannot exceed the number of active environments.")
        if ppo_epochs <= 0:
            raise ValueError("ppo_epochs must be positive.")
        if minibatch_size <= 0:
            raise ValueError("minibatch_size must be positive.")
        if progress_interval <= 0:
            raise ValueError("progress_interval must be positive.")
        if progress_window <= 0:
            raise ValueError("progress_window must be positive.")

        active_environment_count = min(num_envs, episodes)
        with profile_phase(
            profiler, "ppo.setup.environment_creation", synchronize=False
        ):
            training_env = env_factory()
            training_envs = [training_env]
            if env_workers == 0:
                training_envs.extend(
                    env_factory() for _ in range(active_environment_count - 1)
                )
        with profile_phase(profiler, "ppo.setup.agent_creation", synchronize=False):
            agent = PPOAgent(
                observation_size=training_env.observation_size,
                action_space_size=training_env.action_space_size,
                hidden_sizes=hidden_sizes,
                learning_rate=learning_rate,
                discount=discount,
                gae_lambda=gae_lambda,
                clip_ratio=clip_ratio,
                value_loss_coef=value_loss_coef,
                entropy_coef=entropy_coef,
                ppo_epochs=ppo_epochs,
                minibatch_size=minibatch_size,
                max_grad_norm=max_grad_norm,
                policy_architecture=policy_architecture,
                action_feature_size=training_env.action_feature_size,
                max_enemy_count=training_env.encoder.max_enemy_count,
                enemy_feature_start=(
                    training_env.encoder.scalar_feature_count
                    + training_env.encoder.pile_count_feature_count
                ),
                enemy_slot_feature_size=training_env.encoder.enemy_slot_feature_count,
                uses_target_feature_index=(
                    training_env.encoder.action_feature_names.index("uses_target")
                ),
                target_slot_feature_index=(
                    training_env.encoder.action_feature_names.index(
                        "target_slot_fraction"
                    )
                ),
                device="cpu" if env_workers > 0 and device is None else device,
                seed=seed,
            )
        if profiler is not None:
            profiler.attach_torch(torch, agent.device)
        if env_workers > 0 and agent.device != "cpu":
            raise ValueError("env_workers currently supports CPU PPO training only.")

        parallel_pool = None
        if env_workers > 0:
            from ..training.ppo_env_pool import ParallelPPOEnvPool

            with profile_phase(
                profiler, "ppo.setup.environment_workers", synchronize=False
            ):
                parallel_pool = ParallelPPOEnvPool(
                    env_factory,
                    num_envs=active_environment_count,
                    num_workers=env_workers,
                    observation_size=training_env.observation_size,
                    action_space_size=training_env.action_space_size,
                    action_feature_size=training_env.action_feature_size,
                )

        training_metrics: list[EpisodeMetrics] = []
        evaluations: list[EvaluationSnapshot] = []
        mean_total_losses: list[float] = []
        mean_policy_losses: list[float] = []
        mean_value_losses: list[float] = []
        mean_entropies: list[float] = []
        optimization_steps = 0
        training_started_at = perf_counter()
        best_evaluation: EvaluationSnapshot | None = None
        best_policy_state: dict[str, Tensor] | None = None
        best_optimizer_state: dict[str, Any] | None = None

        observations: list[Observation | None] = []
        states: list[VectorObservation | None] = []
        slot_episode_indices: list[int | None] = []
        with profile_phase(profiler, "ppo.rollout.episode_reset", synchronize=False):
            if parallel_pool is not None:
                parallel_pool.reset(
                    {
                        environment_id: _episode_seed(seed, environment_id)
                        for environment_id in range(active_environment_count)
                    }
                )
                observations = [None] * active_environment_count
                states = [None] * active_environment_count
                slot_episode_indices = list(range(active_environment_count))
            else:
                for environment_id, environment in enumerate(training_envs):
                    observation = environment.reset(
                        seed=_episode_seed(seed, environment_id)
                    )
                    observations.append(observation)
                    states.append(environment.encode_observation(observation))
                    slot_episode_indices.append(environment_id)

        next_episode_index = active_environment_count
        completed_episodes = 0
        collector_cursor = 0

        while completed_episodes < episodes:
            rollout = PPORolloutBuffer()

            while len(rollout) < rollout_steps and completed_episodes < episodes:
                ordered_slots = [
                    (collector_cursor + offset) % active_environment_count
                    for offset in range(active_environment_count)
                ]
                active_slots = [
                    environment_id
                    for environment_id in ordered_slots
                    if slot_episode_indices[environment_id] is not None
                ]
                if not active_slots:
                    raise RuntimeError(
                        "PPO has unfinished episodes but no active environments."
                    )
                remaining_rollout_steps = rollout_steps - len(rollout)
                batch_slots = active_slots[:remaining_rollout_steps]
                collector_cursor = (batch_slots[-1] + 1) % active_environment_count

                with profile_phase(
                    profiler, "ppo.rollout.batch_preparation", synchronize=False
                ):
                    if parallel_pool is not None:
                        (
                            typed_batch_states,
                            batch_action_masks,
                            batch_action_features,
                        ) = parallel_pool.policy_inputs(batch_slots)
                    else:
                        batch_states = tuple(
                            states[environment_id] for environment_id in batch_slots
                        )
                        if any(state is None for state in batch_states):
                            raise RuntimeError(
                                "Active PPO environment is missing its state."
                            )
                        typed_batch_states = tuple(
                            state for state in batch_states if state is not None
                        )
                        batch_policy_inputs = tuple(
                            training_envs[environment_id].encode_policy_inputs(
                                observations[environment_id]
                            )
                            for environment_id in batch_slots
                        )
                        batch_action_masks = tuple(
                            action_mask
                            for action_mask, _action_features in batch_policy_inputs
                        )
                        batch_action_features = tuple(
                            action_features
                            for _action_mask, action_features in batch_policy_inputs
                        )
                with profile_phase(profiler, "ppo.rollout.policy_inference"):
                    samples = agent.sample_actions(
                        typed_batch_states,
                        batch_action_masks,
                        action_features=batch_action_features,
                        training=True,
                    )

                parallel_steps = None
                if parallel_pool is not None:
                    with profile_phase(
                        profiler,
                        "ppo.rollout.parallel_environment_update",
                        synchronize=False,
                    ):
                        parallel_steps = parallel_pool.step(
                            batch_slots,
                            [sample[0] for sample in samples],
                        )

                pending_parallel_resets: dict[int, int | None] = {}
                for batch_index, (
                    environment_id,
                    state,
                    action_mask,
                    action_features,
                    sample,
                ) in enumerate(
                    zip(
                        batch_slots,
                        typed_batch_states,
                        batch_action_masks,
                        batch_action_features,
                        samples,
                    )
                ):
                    action, log_prob, value = sample
                    if parallel_steps is not None:
                        next_observation = None
                        next_state = parallel_steps.next_states[batch_index]
                        reward = float(parallel_steps.rewards[batch_index])
                        done = bool(parallel_steps.dones[batch_index])
                        summary = parallel_steps.summaries[batch_index]
                    else:
                        environment = training_envs[environment_id]
                        with profile_phase(
                            profiler,
                            "ppo.rollout.environment_step",
                            synchronize=False,
                        ):
                            next_observation, reward, done, _info = (
                                environment.step_discrete(action)
                            )
                        with profile_phase(
                            profiler,
                            "ppo.rollout.observation_encoding",
                            synchronize=False,
                        ):
                            next_state = environment.encode_observation(next_observation)
                        summary = environment.get_episode_summary() if done else None
                    rollout.add(
                        state=state,
                        action=action,
                        reward=reward,
                        done=done,
                        value=value,
                        log_prob=log_prob,
                        action_mask=action_mask,
                        action_features=action_features,
                        environment_id=environment_id,
                    )

                    if done:
                        if summary is None:
                            raise RuntimeError(
                                "Terminal PPO environment is missing its episode summary."
                            )
                        training_metrics.append(
                            EpisodeMetrics(
                                total_reward=summary.total_reward,
                                steps=summary.steps,
                                win=summary.winner == "player",
                                player_hp=summary.player_hp,
                                enemy_hp=summary.enemy_hp,
                            )
                        )
                        completed_episodes += 1

                        if (
                            evaluation_interval > 0
                            and completed_episodes % evaluation_interval == 0
                        ):
                            with profile_phase(profiler, "ppo.evaluation"):
                                evaluation_snapshot = EvaluationSnapshot(
                                    episode=completed_episodes,
                                    stats=evaluate_policy(
                                        env_factory=env_factory,
                                        policy=lambda env, obs, mask, trained_agent=agent: trained_agent.select_action(
                                            env.encode_observation(obs),
                                            mask,
                                            action_features=env.encode_action_features(
                                                obs,
                                                action_mask=mask,
                                            ),
                                            training=False,
                                        ),
                                        episodes=evaluation_episodes,
                                        seed=_episode_seed(
                                            seed, 10_000 + completed_episodes
                                        ),
                                    ),
                                )
                            evaluations.append(evaluation_snapshot)
                            if _is_better_evaluation(
                                evaluation_snapshot, best_evaluation
                            ):
                                best_evaluation = evaluation_snapshot
                                with profile_phase(
                                    profiler, "ppo.checkpoint_state_copy"
                                ):
                                    best_policy_state = deepcopy(
                                        agent.actor_critic.state_dict()
                                    )
                                    best_optimizer_state = deepcopy(
                                        agent.optimizer.state_dict()
                                    )

                        with profile_phase(
                            profiler, "ppo.progress_reporting", synchronize=False
                        ):
                            _maybe_report_progress(
                                progress_callback=progress_callback,
                                progress_interval=progress_interval,
                                progress_window=progress_window,
                                algorithm="masked_ppo",
                                episode_index=completed_episodes - 1,
                                total_episodes=episodes,
                                epsilon=0.0,
                                training_metrics=training_metrics,
                                evaluations_completed=len(evaluations),
                                training_started_at=training_started_at,
                                optimization_steps=optimization_steps,
                                recent_losses=mean_total_losses[-progress_window:],
                            )

                        if next_episode_index < episodes:
                            next_seed = _episode_seed(seed, next_episode_index)
                            if parallel_pool is not None:
                                pending_parallel_resets[environment_id] = next_seed
                            else:
                                with profile_phase(
                                    profiler,
                                    "ppo.rollout.episode_reset",
                                    synchronize=False,
                                ):
                                    reset_observation = environment.reset(seed=next_seed)
                                    observations[environment_id] = reset_observation
                                    states[environment_id] = (
                                        environment.encode_observation(reset_observation)
                                    )
                            slot_episode_indices[environment_id] = next_episode_index
                            next_episode_index += 1
                        else:
                            observations[environment_id] = None
                            states[environment_id] = None
                            slot_episode_indices[environment_id] = None
                    elif parallel_pool is None:
                        observations[environment_id] = next_observation
                        states[environment_id] = next_state

                    if parallel_pool is None and completed_episodes >= episodes:
                        break

                if parallel_pool is not None and pending_parallel_resets:
                    with profile_phase(
                        profiler, "ppo.rollout.episode_reset", synchronize=False
                    ):
                        parallel_pool.reset(pending_parallel_resets)

            bootstrap_slots = [
                environment_id
                for environment_id in set(rollout.environment_ids)
                if slot_episode_indices[environment_id] is not None
            ]
            if parallel_pool is not None:
                typed_bootstrap_states = parallel_pool.states(bootstrap_slots)
            else:
                bootstrap_states = tuple(
                    states[environment_id] for environment_id in bootstrap_slots
                )
                typed_bootstrap_states = tuple(
                    state for state in bootstrap_states if state is not None
                )
            with profile_phase(profiler, "ppo.bootstrap_value_inference"):
                bootstrap_predictions = agent.predict_values(typed_bootstrap_states)
            bootstrap_values = {
                environment_id: value
                for environment_id, value in zip(
                    bootstrap_slots,
                    bootstrap_predictions,
                )
            }

            (
                mean_total_loss,
                mean_policy_loss,
                mean_value_loss,
                mean_entropy,
                update_steps,
            ) = agent.optimize(
                rollout,
                last_value=bootstrap_values,
                profiler=profiler,
            )
            mean_total_losses.append(mean_total_loss)
            mean_policy_losses.append(mean_policy_loss)
            mean_value_losses.append(mean_value_loss)
            mean_entropies.append(mean_entropy)
            optimization_steps += update_steps

        if parallel_pool is not None:
            parallel_pool.close()
            if profiler is not None:
                profiler.add_external_process_cpu_seconds(
                    parallel_pool.worker_cpu_seconds
                )

        restored_best_checkpoint = False
        if restore_best_checkpoint and best_policy_state is not None and best_optimizer_state is not None:
            with profile_phase(profiler, "ppo.checkpoint_restore"):
                agent.actor_critic.load_state_dict(best_policy_state)
                agent.optimizer.load_state_dict(best_optimizer_state)
                restored_best_checkpoint = True

        with profile_phase(profiler, "ppo.evaluation"):
            final_evaluation = evaluate_policy(
                env_factory=env_factory,
                policy=lambda env, obs, mask, trained_agent=agent: trained_agent.select_action(
                    env.encode_observation(obs),
                    mask,
                    action_features=env.encode_action_features(
                        obs,
                        action_mask=mask,
                    ),
                    training=False,
                ),
                episodes=evaluation_episodes,
                seed=(
                    _episode_seed(seed, 20_000)
                    if final_evaluation_seed is None
                    else final_evaluation_seed
                ),
            )
        training_profile = None if profiler is None else profiler.finalize()
        return PPOTrainingResult(
            agent=agent,
            training_metrics=tuple(training_metrics),
            evaluations=tuple(evaluations),
            final_evaluation=final_evaluation,
            optimization_steps=optimization_steps,
            mean_total_losses=tuple(mean_total_losses),
            mean_policy_losses=tuple(mean_policy_losses),
            mean_value_losses=tuple(mean_value_losses),
            mean_entropies=tuple(mean_entropies),
            num_envs=num_envs,
            env_workers=env_workers,
            profile=training_profile,
            best_evaluation=best_evaluation,
            restored_best_checkpoint=restored_best_checkpoint,
        )


    def _mask_policy_logits(logits: Tensor, action_masks: Tensor) -> Tensor:
        """Set illegal action logits to a large negative value before softmax."""
        large_negative = torch.full_like(logits, -1e9)
        return torch.where(action_masks, logits, large_negative)


    def _is_better_evaluation(
        candidate: EvaluationSnapshot,
        incumbent: EvaluationSnapshot | None,
    ) -> bool:
        """Return whether a candidate checkpoint should replace the current best."""
        if incumbent is None:
            return True
        candidate_key = (
            candidate.stats.win_rate,
            candidate.stats.mean_reward,
            candidate.stats.mean_player_hp,
            -candidate.stats.mean_steps,
            candidate.episode,
        )
        incumbent_key = (
            incumbent.stats.win_rate,
            incumbent.stats.mean_reward,
            incumbent.stats.mean_player_hp,
            -incumbent.stats.mean_steps,
            incumbent.episode,
        )
        return candidate_key > incumbent_key

else:

    class PPOActorCriticNetwork:
        """Placeholder network that explains the missing dependency."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise ModuleNotFoundError(
                "Masked PPO support requires the optional dependency 'torch'. "
                "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
            )


    class PPORolloutBuffer:
        """Placeholder rollout buffer that explains the missing dependency."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise ModuleNotFoundError(
                "Masked PPO support requires the optional dependency 'torch'. "
                "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
            )


    class PPOAgent:
        """Placeholder agent that explains the missing dependency."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise ModuleNotFoundError(
                "Masked PPO support requires the optional dependency 'torch'. "
                "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
            )


    def train_masked_ppo(*_args: Any, **_kwargs: Any) -> PPOTrainingResult:
        """Placeholder trainer that explains the missing dependency."""
        raise ModuleNotFoundError(
            "Masked PPO support requires the optional dependency 'torch'. "
            "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
        )
