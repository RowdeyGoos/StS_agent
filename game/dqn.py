"""Deep Q-Network utilities for the combat environment."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from random import Random
from time import perf_counter
from typing import Any, Callable, Sequence, TypeAlias

from .baselines import (
    EpisodeMetrics,
    EvaluationSnapshot,
    EvaluationStats,
    ProgressCallback,
    _maybe_report_progress,
    _episode_seed,
    evaluate_policy,
    legal_action_indices,
)
from .core import CombatEnv

VectorObservation = tuple[float, ...]
ActionMask = tuple[int, ...]
DeepValueAgentFactory: TypeAlias = Callable[..., "DQNAgent"]

try:
    import torch
    from torch import Tensor, nn, optim
except ModuleNotFoundError:  # pragma: no cover - depends on optional dependency
    torch = None
    Tensor = Any
    nn = None
    optim = None


@dataclass(frozen=True, slots=True)
class ReplayTransition:
    """One transition stored in replay memory."""

    state: VectorObservation
    action: int
    reward: float
    next_state: VectorObservation
    next_action_mask: ActionMask
    done: bool


class ReplayBuffer:
    """Fixed-capacity replay memory for off-policy training."""

    def __init__(self, capacity: int, seed: int | None = None) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive.")
        self._buffer: deque[ReplayTransition] = deque(maxlen=capacity)
        self.rng = Random(seed)

    def add(self, transition: ReplayTransition) -> None:
        """Append a transition to replay memory."""
        self._buffer.append(transition)

    def sample(self, batch_size: int) -> list[ReplayTransition]:
        """Sample a random mini-batch without replacement."""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive.")
        if batch_size > len(self._buffer):
            raise ValueError("batch_size cannot exceed replay buffer size.")
        return self.rng.sample(list(self._buffer), batch_size)

    def __len__(self) -> int:
        return len(self._buffer)


@dataclass(frozen=True, slots=True)
class DQNTrainingResult:
    """Outputs from DQN training and evaluation."""

    agent: "DQNAgent"
    training_metrics: tuple[EpisodeMetrics, ...]
    evaluations: tuple[EvaluationSnapshot, ...]
    final_evaluation: EvaluationStats
    optimization_steps: int
    mean_losses: tuple[float, ...]
    best_evaluation: EvaluationSnapshot | None = None
    restored_best_checkpoint: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return a compact summary for loggers and notebooks."""
        return {
            "episodes": len(self.training_metrics),
            "final_epsilon": self.agent.epsilon,
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

    class DQNNetwork(nn.Module):
        """Simple MLP used to estimate Q-values from encoded observations."""

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
            layers.append(nn.Linear(current_dim, output_dim))
            self.model = nn.Sequential(*layers)

        def forward(self, inputs: Tensor) -> Tensor:
            """Compute Q-values for a batch of encoded observations."""
            return self.model(inputs)


    class DQNAgent:
        """Masked DQN agent with target network and epsilon-greedy exploration."""

        def __init__(
            self,
            observation_size: int,
            action_space_size: int,
            hidden_sizes: Sequence[int] = (128, 128),
            learning_rate: float = 1e-3,
            discount: float = 0.99,
            epsilon: float = 1.0,
            epsilon_min: float = 0.05,
            epsilon_decay: float = 0.995,
            device: str | None = None,
            seed: int | None = None,
        ) -> None:
            if observation_size <= 0 or action_space_size <= 0:
                raise ValueError("observation_size and action_space_size must be positive.")

            if seed is not None:
                torch.manual_seed(seed)

            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
            self.discount = discount
            self.epsilon = epsilon
            self.epsilon_min = epsilon_min
            self.epsilon_decay = epsilon_decay
            self.rng = Random(seed)

            self.policy_network = DQNNetwork(
                input_dim=observation_size,
                output_dim=action_space_size,
                hidden_sizes=hidden_sizes,
            ).to(self.device)
            self.target_network = DQNNetwork(
                input_dim=observation_size,
                output_dim=action_space_size,
                hidden_sizes=hidden_sizes,
            ).to(self.device)
            self.target_network.load_state_dict(self.policy_network.state_dict())
            self.target_network.eval()

            self.optimizer = optim.Adam(self.policy_network.parameters(), lr=learning_rate)
            self.loss_fn = nn.SmoothL1Loss()

        def select_action(
            self,
            state: VectorObservation,
            action_mask: ActionMask,
            training: bool = True,
        ) -> int:
            """Choose an epsilon-greedy legal action."""
            legal_indices = legal_action_indices(action_mask)
            if training and self.rng.random() < self.epsilon:
                return self.rng.choice(legal_indices)

            q_values = self.predict_q_values(state)
            best_value = max(q_values[action_index] for action_index in legal_indices)
            best_actions = [
                action_index
                for action_index in legal_indices
                if q_values[action_index] == best_value
            ]
            return self.rng.choice(best_actions)

        def predict_q_values(self, state: VectorObservation) -> list[float]:
            """Run the policy network for one encoded state."""
            with torch.no_grad():
                state_tensor = torch.tensor(
                    [list(state)],
                    dtype=torch.float32,
                    device=self.device,
                )
                q_values = self.policy_network(state_tensor).squeeze(0)
            return [float(value) for value in q_values.detach().cpu().tolist()]

        def optimize(
            self,
            replay_buffer: ReplayBuffer,
            batch_size: int,
            gradient_clip: float | None = 1.0,
        ) -> float | None:
            """Run one DQN optimization step from replay memory."""
            if len(replay_buffer) < batch_size:
                return None

            transitions = replay_buffer.sample(batch_size)

            states = torch.tensor(
                [list(transition.state) for transition in transitions],
                dtype=torch.float32,
                device=self.device,
            )
            actions = torch.tensor(
                [transition.action for transition in transitions],
                dtype=torch.long,
                device=self.device,
            ).unsqueeze(1)
            rewards = torch.tensor(
                [transition.reward for transition in transitions],
                dtype=torch.float32,
                device=self.device,
            )
            next_states = torch.tensor(
                [list(transition.next_state) for transition in transitions],
                dtype=torch.float32,
                device=self.device,
            )
            dones = torch.tensor(
                [transition.done for transition in transitions],
                dtype=torch.float32,
                device=self.device,
            )
            next_action_masks = torch.tensor(
                [list(transition.next_action_mask) for transition in transitions],
                dtype=torch.bool,
                device=self.device,
            )

            predicted_q_values = self.policy_network(states).gather(1, actions).squeeze(1)

            with torch.no_grad():
                max_next_q_values = self._compute_next_state_values(
                    next_states=next_states,
                    next_action_masks=next_action_masks,
                )
                targets = rewards + (1.0 - dones) * self.discount * max_next_q_values

            loss = self.loss_fn(predicted_q_values, targets)
            self.optimizer.zero_grad()
            loss.backward()
            if gradient_clip is not None:
                nn.utils.clip_grad_norm_(self.policy_network.parameters(), gradient_clip)
            self.optimizer.step()
            return float(loss.item())

        def update_target_network(self) -> None:
            """Copy the policy network weights to the target network."""
            self.target_network.load_state_dict(self.policy_network.state_dict())

        def decay_epsilon_value(self) -> None:
            """Decay exploration toward the configured minimum."""
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        def _compute_next_state_values(
            self,
            next_states: Tensor,
            next_action_masks: Tensor,
        ) -> Tensor:
            """Estimate bootstrap values using the target network max over legal actions."""
            next_q_values = self.target_network(next_states)
            return _masked_max_q_values(next_q_values, next_action_masks)


    class DoubleDQNAgent(DQNAgent):
        """Double DQN variant that decouples action selection and evaluation."""

        def _compute_next_state_values(
            self,
            next_states: Tensor,
            next_action_masks: Tensor,
        ) -> Tensor:
            """Select next actions with the policy network and evaluate with the target network."""
            policy_next_q_values = self.policy_network(next_states)
            masked_policy_next_q_values = _mask_illegal_q_values(
                policy_next_q_values,
                next_action_masks,
            )
            selected_next_actions = masked_policy_next_q_values.argmax(dim=1, keepdim=True)

            target_next_q_values = self.target_network(next_states)
            chosen_target_q_values = target_next_q_values.gather(
                1,
                selected_next_actions,
            ).squeeze(1)
            has_legal_actions = next_action_masks.any(dim=1)
            return torch.where(
                has_legal_actions,
                chosen_target_q_values,
                torch.zeros_like(chosen_target_q_values),
            )


    def train_dqn(
        env_factory: Callable[[], CombatEnv],
        episodes: int,
        evaluation_interval: int = 100,
        evaluation_episodes: int = 25,
        replay_capacity: int = 20_000,
        batch_size: int = 64,
        warmup_steps: int = 250,
        target_update_interval: int = 100,
        hidden_sizes: Sequence[int] = (128, 128),
        seed: int | None = None,
        learning_rate: float = 1e-3,
        discount: float = 0.99,
        epsilon: float = 1.0,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
        gradient_clip: float | None = 1.0,
        device: str | None = None,
        restore_best_checkpoint: bool = True,
        progress_callback: ProgressCallback | None = None,
        progress_interval: int = 25,
        progress_window: int = 25,
    ) -> DQNTrainingResult:
        """Train a standard DQN agent and periodically evaluate greedy performance."""
        return _train_deep_value_agent(
            algorithm="dqn",
            agent_factory=DQNAgent,
            env_factory=env_factory,
            episodes=episodes,
            evaluation_interval=evaluation_interval,
            evaluation_episodes=evaluation_episodes,
            replay_capacity=replay_capacity,
            batch_size=batch_size,
            warmup_steps=warmup_steps,
            target_update_interval=target_update_interval,
            hidden_sizes=hidden_sizes,
            seed=seed,
            learning_rate=learning_rate,
            discount=discount,
            epsilon=epsilon,
            epsilon_min=epsilon_min,
            epsilon_decay=epsilon_decay,
            gradient_clip=gradient_clip,
            device=device,
            restore_best_checkpoint=restore_best_checkpoint,
            progress_callback=progress_callback,
            progress_interval=progress_interval,
            progress_window=progress_window,
        )


    def train_double_dqn(
        env_factory: Callable[[], CombatEnv],
        episodes: int,
        evaluation_interval: int = 100,
        evaluation_episodes: int = 25,
        replay_capacity: int = 20_000,
        batch_size: int = 64,
        warmup_steps: int = 250,
        target_update_interval: int = 100,
        hidden_sizes: Sequence[int] = (128, 128),
        seed: int | None = None,
        learning_rate: float = 1e-3,
        discount: float = 0.99,
        epsilon: float = 1.0,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
        gradient_clip: float | None = 1.0,
        device: str | None = None,
        restore_best_checkpoint: bool = True,
        progress_callback: ProgressCallback | None = None,
        progress_interval: int = 25,
        progress_window: int = 25,
    ) -> DQNTrainingResult:
        """Train a Double DQN agent and periodically evaluate greedy performance."""
        return _train_deep_value_agent(
            algorithm="double_dqn",
            agent_factory=DoubleDQNAgent,
            env_factory=env_factory,
            episodes=episodes,
            evaluation_interval=evaluation_interval,
            evaluation_episodes=evaluation_episodes,
            replay_capacity=replay_capacity,
            batch_size=batch_size,
            warmup_steps=warmup_steps,
            target_update_interval=target_update_interval,
            hidden_sizes=hidden_sizes,
            seed=seed,
            learning_rate=learning_rate,
            discount=discount,
            epsilon=epsilon,
            epsilon_min=epsilon_min,
            epsilon_decay=epsilon_decay,
            gradient_clip=gradient_clip,
            device=device,
            restore_best_checkpoint=restore_best_checkpoint,
            progress_callback=progress_callback,
            progress_interval=progress_interval,
            progress_window=progress_window,
        )


    def _train_deep_value_agent(
        algorithm: str,
        agent_factory: DeepValueAgentFactory,
        env_factory: Callable[[], CombatEnv],
        episodes: int,
        evaluation_interval: int = 100,
        evaluation_episodes: int = 25,
        replay_capacity: int = 20_000,
        batch_size: int = 64,
        warmup_steps: int = 250,
        target_update_interval: int = 100,
        hidden_sizes: Sequence[int] = (128, 128),
        seed: int | None = None,
        learning_rate: float = 1e-3,
        discount: float = 0.99,
        epsilon: float = 1.0,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
        gradient_clip: float | None = 1.0,
        device: str | None = None,
        restore_best_checkpoint: bool = True,
        progress_callback: ProgressCallback | None = None,
        progress_interval: int = 25,
        progress_window: int = 25,
    ) -> DQNTrainingResult:
        """Shared trainer for DQN-family agents."""
        if episodes <= 0:
            raise ValueError("episodes must be positive.")
        if evaluation_interval <= 0:
            raise ValueError("evaluation_interval must be positive.")
        if evaluation_episodes <= 0:
            raise ValueError("evaluation_episodes must be positive.")
        if replay_capacity <= 0:
            raise ValueError("replay_capacity must be positive.")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive.")
        if target_update_interval <= 0:
            raise ValueError("target_update_interval must be positive.")
        if progress_interval <= 0:
            raise ValueError("progress_interval must be positive.")
        if progress_window <= 0:
            raise ValueError("progress_window must be positive.")

        template_env = env_factory()
        agent = agent_factory(
            observation_size=template_env.observation_size,
            action_space_size=template_env.action_space_size,
            hidden_sizes=hidden_sizes,
            learning_rate=learning_rate,
            discount=discount,
            epsilon=epsilon,
            epsilon_min=epsilon_min,
            epsilon_decay=epsilon_decay,
            device=device,
            seed=seed,
        )
        replay_buffer = ReplayBuffer(capacity=replay_capacity, seed=seed)

        training_metrics: list[EpisodeMetrics] = []
        evaluations: list[EvaluationSnapshot] = []
        mean_losses: list[float] = []
        total_environment_steps = 0
        optimization_steps = 0
        training_started_at = perf_counter()
        best_evaluation: EvaluationSnapshot | None = None
        best_policy_state: dict[str, Tensor] | None = None
        best_target_state: dict[str, Tensor] | None = None

        for episode_index in range(episodes):
            env = env_factory()
            observation = env.reset(seed=_episode_seed(seed, episode_index))
            state = tuple(float(value) for value in env.encode_observation(observation))
            done = False
            episode_losses: list[float] = []

            while not done:
                action_mask = env.get_action_mask()
                action = agent.select_action(state, action_mask, training=True)
                next_observation, reward, done, info = env.step_discrete(action)
                next_state = tuple(
                    float(value) for value in env.encode_observation(next_observation)
                )
                next_action_mask = tuple(int(value) for value in info["action_mask"])

                replay_buffer.add(
                    ReplayTransition(
                        state=state,
                        action=action,
                        reward=reward,
                        next_state=next_state,
                        next_action_mask=next_action_mask,
                        done=done,
                    )
                )

                state = next_state
                total_environment_steps += 1

                if total_environment_steps >= warmup_steps:
                    loss = agent.optimize(
                        replay_buffer=replay_buffer,
                        batch_size=batch_size,
                        gradient_clip=gradient_clip,
                    )
                    if loss is not None:
                        episode_losses.append(loss)
                        optimization_steps += 1
                        if optimization_steps % target_update_interval == 0:
                            agent.update_target_network()

            summary = env.get_episode_summary()
            training_metrics.append(
                EpisodeMetrics(
                    total_reward=summary.total_reward,
                    steps=summary.steps,
                    win=summary.winner == "player",
                    player_hp=summary.player_hp,
                    enemy_hp=summary.enemy_hp,
                )
            )
            mean_losses.append(
                sum(episode_losses) / len(episode_losses) if episode_losses else 0.0
            )
            agent.decay_epsilon_value()

            if (episode_index + 1) % evaluation_interval == 0:
                evaluation_snapshot = EvaluationSnapshot(
                    episode=episode_index + 1,
                    stats=evaluate_policy(
                        env_factory=env_factory,
                        policy=lambda env, obs, mask, trained_agent=agent: trained_agent.select_action(
                            tuple(float(value) for value in env.encode_observation(obs)),
                            mask,
                            training=False,
                        ),
                        episodes=evaluation_episodes,
                        seed=_episode_seed(seed, 10_000 + episode_index),
                    ),
                )
                evaluations.append(evaluation_snapshot)
                if _is_better_evaluation(evaluation_snapshot, best_evaluation):
                    best_evaluation = evaluation_snapshot
                    best_policy_state = deepcopy(agent.policy_network.state_dict())
                    best_target_state = deepcopy(agent.target_network.state_dict())

            _maybe_report_progress(
                progress_callback=progress_callback,
                progress_interval=progress_interval,
                progress_window=progress_window,
                algorithm=algorithm,
                episode_index=episode_index,
                total_episodes=episodes,
                epsilon=agent.epsilon,
                training_metrics=training_metrics,
                evaluations_completed=len(evaluations),
                training_started_at=training_started_at,
                optimization_steps=optimization_steps,
                recent_losses=mean_losses[-progress_window:],
            )

        restored_best_checkpoint = False
        if restore_best_checkpoint and best_policy_state is not None and best_target_state is not None:
            agent.policy_network.load_state_dict(best_policy_state)
            agent.target_network.load_state_dict(best_target_state)
            restored_best_checkpoint = True

        final_evaluation = evaluate_policy(
            env_factory=env_factory,
            policy=lambda env, obs, mask, trained_agent=agent: trained_agent.select_action(
                tuple(float(value) for value in env.encode_observation(obs)),
                mask,
                training=False,
            ),
            episodes=evaluation_episodes,
            seed=_episode_seed(seed, 20_000),
        )
        return DQNTrainingResult(
            agent=agent,
            training_metrics=tuple(training_metrics),
            evaluations=tuple(evaluations),
            final_evaluation=final_evaluation,
            optimization_steps=optimization_steps,
            mean_losses=tuple(mean_losses),
            best_evaluation=best_evaluation,
            restored_best_checkpoint=restored_best_checkpoint,
        )


    def _mask_illegal_q_values(q_values: Tensor, action_masks: Tensor) -> Tensor:
        """Set illegal action logits to negative infinity before max or argmax."""
        negative_infinity = torch.full_like(q_values, float("-inf"))
        return torch.where(action_masks, q_values, negative_infinity)


    def _masked_max_q_values(q_values: Tensor, action_masks: Tensor) -> Tensor:
        """Compute the max Q-value over legal actions, returning zero if none are legal."""
        masked_q_values = _mask_illegal_q_values(q_values, action_masks)
        max_q_values = masked_q_values.max(dim=1).values
        has_legal_actions = action_masks.any(dim=1)
        return torch.where(has_legal_actions, max_q_values, torch.zeros_like(max_q_values))


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

    class DQNNetwork:
        """Placeholder network that explains the missing dependency."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise ModuleNotFoundError(
                "DQN support requires the optional dependency 'torch'. "
                "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
            )


    class DQNAgent:
        """Placeholder agent that explains the missing dependency."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise ModuleNotFoundError(
                "DQN support requires the optional dependency 'torch'. "
                "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
            )


    class DoubleDQNAgent:
        """Placeholder agent that explains the missing dependency."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise ModuleNotFoundError(
                "Double DQN support requires the optional dependency 'torch'. "
                "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
            )


    def train_dqn(*_args: Any, **_kwargs: Any) -> DQNTrainingResult:
        """Placeholder trainer that explains the missing dependency."""
        raise ModuleNotFoundError(
            "DQN support requires the optional dependency 'torch'. "
            "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
        )


    def train_double_dqn(*_args: Any, **_kwargs: Any) -> DQNTrainingResult:
        """Placeholder trainer that explains the missing dependency."""
        raise ModuleNotFoundError(
            "Double DQN support requires the optional dependency 'torch'. "
            "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
        )
