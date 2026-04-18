"""Masked PPO utilities for the combat environment."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from random import Random
from time import perf_counter
from typing import Any, Callable, Sequence

from .baselines import (
    EpisodeMetrics,
    EvaluationSnapshot,
    EvaluationStats,
    ProgressCallback,
    _maybe_report_progress,
    _episode_seed,
    evaluate_policy,
)
from .core import CombatEnv

VectorObservation = tuple[float, ...]
ActionMask = tuple[int, ...]
ActionFeatureBatch = tuple[tuple[float, ...], ...]

try:
    import torch
    from torch import Tensor, nn, optim
    from torch.distributions import Categorical
except ModuleNotFoundError:  # pragma: no cover - depends on optional dependency
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
    best_evaluation: EvaluationSnapshot | None = None
    restored_best_checkpoint: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return a compact summary for loggers and notebooks."""
        return {
            "episodes": len(self.training_metrics),
            "optimization_steps": self.optimization_steps,
            "device": self.agent.device,
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

        def __init__(self) -> None:
            self.states = []
            self.actions = []
            self.rewards = []
            self.dones = []
            self.values = []
            self.log_probs = []
            self.action_masks = []
            self.action_features = []

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

        def __len__(self) -> int:
            return len(self.actions)

        def compute_returns_and_advantages(
            self,
            last_value: float,
            discount: float,
            gae_lambda: float,
            device: str,
        ) -> dict[str, Tensor]:
            """Return tensorized rollout data plus GAE returns/advantages."""
            rollout_size = len(self)
            advantages = [0.0] * rollout_size
            returns = [0.0] * rollout_size
            gae = 0.0

            for step_index in range(rollout_size - 1, -1, -1):
                next_value = last_value if step_index == rollout_size - 1 else self.values[step_index + 1]
                next_non_terminal = 0.0 if self.dones[step_index] else 1.0
                delta = (
                    self.rewards[step_index]
                    + discount * next_value * next_non_terminal
                    - self.values[step_index]
                )
                gae = delta + discount * gae_lambda * next_non_terminal * gae
                advantages[step_index] = gae
                returns[step_index] = gae + self.values[step_index]

            return {
                "states": torch.as_tensor(self.states, dtype=torch.float32, device=device),
                "actions": torch.as_tensor(self.actions, dtype=torch.long, device=device),
                "old_log_probs": torch.as_tensor(
                    self.log_probs,
                    dtype=torch.float32,
                    device=device,
                ),
                "action_masks": torch.as_tensor(
                    self.action_masks,
                    dtype=torch.bool,
                    device=device,
                ),
                "action_features": torch.as_tensor(
                    self.action_features,
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
            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
            self.rng = Random(seed)

            if self.policy_architecture not in {"flat", "action_feature"}:
                raise ValueError(
                    "policy_architecture must be 'flat' or 'action_feature'."
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
                logits, values = self.actor_critic(state_tensor, action_feature_tensor)
                distribution = self._distribution_from_logits(logits, action_mask_tensor)
                if training:
                    action_tensor = distribution.sample()
                else:
                    action_tensor = distribution.probs.argmax(dim=1)
                log_prob_tensor = distribution.log_prob(action_tensor)
                value_tensor = values.squeeze(0)

            return (
                int(action_tensor.item()),
                float(log_prob_tensor.item()),
                float(value_tensor.item()),
            )

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
            with torch.no_grad():
                state_tensor = torch.as_tensor(
                    state,
                    dtype=torch.float32,
                    device=self.device,
                ).unsqueeze(0)
                values = self.actor_critic.state_values(state_tensor)
            return float(values.squeeze(0).item())

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
                "actor_critic_state": self.actor_critic.state_dict(),
                "optimizer_state": self.optimizer.state_dict(),
            }

        def optimize(
            self,
            rollout: PPORolloutBuffer,
            last_value: float,
        ) -> tuple[float, float, float, float, int]:
            """Run PPO updates over one rollout buffer."""
            if len(rollout) == 0:
                return 0.0, 0.0, 0.0, 0.0, 0

            tensors = rollout.compute_returns_and_advantages(
                last_value=last_value,
                discount=self.discount,
                gae_lambda=self.gae_lambda,
                device=self.device,
            )

            advantages = tensors["advantages"]
            advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)

            rollout_size = len(rollout)
            minibatch_size = min(self.minibatch_size, rollout_size)
            total_loss_sum = 0.0
            policy_loss_sum = 0.0
            value_loss_sum = 0.0
            entropy_sum = 0.0
            optimization_steps = 0

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
                            if self.policy_architecture == "action_feature"
                            else None
                        ),
                    )
                    distribution = self._distribution_from_logits(logits, batch_action_masks)
                    new_log_probs = distribution.log_prob(batch_actions)
                    entropy = distribution.entropy().mean()

                    probability_ratio = torch.exp(new_log_probs - batch_old_log_probs)
                    unclipped_objective = probability_ratio * batch_advantages
                    clipped_objective = torch.clamp(
                        probability_ratio,
                        1.0 - self.clip_ratio,
                        1.0 + self.clip_ratio,
                    ) * batch_advantages
                    policy_loss = -torch.minimum(unclipped_objective, clipped_objective).mean()
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
            if self.policy_architecture != "action_feature":
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
        if ppo_epochs <= 0:
            raise ValueError("ppo_epochs must be positive.")
        if minibatch_size <= 0:
            raise ValueError("minibatch_size must be positive.")
        if progress_interval <= 0:
            raise ValueError("progress_interval must be positive.")
        if progress_window <= 0:
            raise ValueError("progress_window must be positive.")

        training_env = env_factory()
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
            device=device,
            seed=seed,
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

        current_episode_index = 0
        observation = training_env.reset(seed=_episode_seed(seed, current_episode_index))
        state = training_env.encode_observation(observation)

        while current_episode_index < episodes:
            rollout = PPORolloutBuffer()

            while len(rollout) < rollout_steps and current_episode_index < episodes:
                action_mask = training_env.get_action_mask()
                action_features = training_env.encode_action_features(observation)
                action, log_prob, value = agent.sample_action(
                    state,
                    action_mask,
                    action_features=action_features,
                    training=True,
                )
                next_observation, reward, done, _info = training_env.step_discrete(action)
                next_state = training_env.encode_observation(next_observation)
                rollout.add(
                    state=state,
                    action=action,
                    reward=reward,
                    done=done,
                    value=value,
                    log_prob=log_prob,
                    action_mask=action_mask,
                    action_features=action_features,
                )
                state = next_state

                if done:
                    summary = training_env.get_episode_summary()
                    training_metrics.append(
                        EpisodeMetrics(
                            total_reward=summary.total_reward,
                            steps=summary.steps,
                            win=summary.winner == "player",
                            player_hp=summary.player_hp,
                            enemy_hp=summary.enemy_hp,
                        )
                    )
                    current_episode_index += 1

                    if (
                        evaluation_interval > 0
                        and current_episode_index % evaluation_interval == 0
                    ):
                        evaluation_snapshot = EvaluationSnapshot(
                            episode=current_episode_index,
                            stats=evaluate_policy(
                                env_factory=env_factory,
                                policy=lambda env, obs, mask, trained_agent=agent: trained_agent.select_action(
                                    env.encode_observation(obs),
                                    mask,
                                    action_features=env.encode_action_features(obs),
                                    training=False,
                                ),
                                episodes=evaluation_episodes,
                                seed=_episode_seed(seed, 10_000 + current_episode_index),
                            ),
                        )
                        evaluations.append(evaluation_snapshot)
                        if _is_better_evaluation(evaluation_snapshot, best_evaluation):
                            best_evaluation = evaluation_snapshot
                            best_policy_state = deepcopy(agent.actor_critic.state_dict())
                            best_optimizer_state = deepcopy(agent.optimizer.state_dict())

                    _maybe_report_progress(
                        progress_callback=progress_callback,
                        progress_interval=progress_interval,
                        progress_window=progress_window,
                        algorithm="masked_ppo",
                        episode_index=current_episode_index - 1,
                        total_episodes=episodes,
                        epsilon=0.0,
                        training_metrics=training_metrics,
                        evaluations_completed=len(evaluations),
                        training_started_at=training_started_at,
                        optimization_steps=optimization_steps,
                        recent_losses=mean_total_losses[-progress_window:],
                    )

                    if current_episode_index >= episodes:
                        break

                    observation = training_env.reset(
                        seed=_episode_seed(seed, current_episode_index)
                    )
                    state = training_env.encode_observation(observation)
                else:
                    observation = next_observation

            last_rollout_done = rollout.dones[-1] if len(rollout) > 0 else True
            bootstrap_value = 0.0 if last_rollout_done else agent.predict_value(state)

            (
                mean_total_loss,
                mean_policy_loss,
                mean_value_loss,
                mean_entropy,
                update_steps,
            ) = agent.optimize(
                rollout,
                last_value=bootstrap_value,
            )
            mean_total_losses.append(mean_total_loss)
            mean_policy_losses.append(mean_policy_loss)
            mean_value_losses.append(mean_value_loss)
            mean_entropies.append(mean_entropy)
            optimization_steps += update_steps

        restored_best_checkpoint = False
        if restore_best_checkpoint and best_policy_state is not None and best_optimizer_state is not None:
            agent.actor_critic.load_state_dict(best_policy_state)
            agent.optimizer.load_state_dict(best_optimizer_state)
            restored_best_checkpoint = True

        final_evaluation = evaluate_policy(
            env_factory=env_factory,
            policy=lambda env, obs, mask, trained_agent=agent: trained_agent.select_action(
                env.encode_observation(obs),
                mask,
                action_features=env.encode_action_features(obs),
                training=False,
            ),
            episodes=evaluation_episodes,
            seed=(
                _episode_seed(seed, 20_000)
                if final_evaluation_seed is None
                else final_evaluation_seed
            ),
        )
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
