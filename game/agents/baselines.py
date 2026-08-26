"""Baseline policies and simple training utilities for RL experiments."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from time import perf_counter
from typing import Any, Callable, TypeAlias

from ..simulation.core import CombatEnv, Observation
from ..simulation.status import modify_attack_damage_for_statuses

StateKey: TypeAlias = tuple[int, ...]
ActionMask: TypeAlias = tuple[int, ...]
PolicyFn: TypeAlias = Callable[[CombatEnv, Observation, ActionMask], int]
ProgressCallback: TypeAlias = Callable[["TrainingProgress"], None]

CARD_DAMAGE = {
    "Strike": 6,
    "Bash": 8,
    "Slimed": 0,
}


@dataclass(frozen=True, slots=True)
class EpisodeMetrics:
    """Summary metrics for a single rollout episode."""

    total_reward: float
    steps: int
    win: bool
    player_hp: int
    enemy_hp: int


@dataclass(frozen=True, slots=True)
class EvaluationStats:
    """Aggregate statistics over multiple evaluation episodes."""

    episodes: int
    mean_reward: float
    win_rate: float
    mean_steps: float
    mean_player_hp: float

    def as_dict(self) -> dict[str, float | int]:
        """Return a plain dict for logging and reporting."""
        return {
            "episodes": self.episodes,
            "mean_reward": self.mean_reward,
            "win_rate": self.win_rate,
            "mean_steps": self.mean_steps,
            "mean_player_hp": self.mean_player_hp,
        }


@dataclass(frozen=True, slots=True)
class EvaluationSnapshot:
    """Evaluation result captured at a specific training checkpoint."""

    episode: int
    stats: EvaluationStats


@dataclass(frozen=True, slots=True)
class TrainingResult:
    """Container for Q-learning training outputs."""

    agent: "QLearningAgent"
    training_metrics: tuple[EpisodeMetrics, ...]
    evaluations: tuple[EvaluationSnapshot, ...]
    final_evaluation: EvaluationStats

    def as_dict(self) -> dict[str, Any]:
        """Return a compact dict representation of the training result."""
        return {
            "episodes": len(self.training_metrics),
            "final_epsilon": self.agent.epsilon,
            "q_table_size": len(self.agent.q_table),
            "final_evaluation": self.final_evaluation.as_dict(),
            "evaluation_points": [
                {"episode": snapshot.episode, **snapshot.stats.as_dict()}
                for snapshot in self.evaluations
            ],
        }


@dataclass(frozen=True, slots=True)
class TrainingProgress:
    """Snapshot of trainer state for live progress reporting."""

    algorithm: str
    episode: int
    total_episodes: int
    epsilon: float
    elapsed_seconds: float
    eta_seconds: float
    latest_metrics: EpisodeMetrics
    recent_mean_reward: float
    recent_win_rate: float
    recent_mean_steps: float
    evaluations_completed: int
    optimization_steps: int = 0
    recent_mean_loss: float | None = None


def legal_action_indices(action_mask: ActionMask) -> tuple[int, ...]:
    """Return the discrete action indices marked legal by a binary mask."""
    legal_actions = tuple(index for index, is_legal in enumerate(action_mask) if is_legal)
    if not legal_actions:
        raise ValueError("Action mask contains no legal actions.")
    return legal_actions


def choose_random_action(
    _env: CombatEnv,
    _observation: Observation,
    action_mask: ActionMask,
    rng: Random,
) -> int:
    """Choose a uniformly random legal action."""
    return rng.choice(legal_action_indices(action_mask))


def choose_heuristic_action(
    env: CombatEnv,
    observation: Observation,
    action_mask: ActionMask | None = None,
) -> int:
    """Choose a simple hand-crafted action using current combat state."""
    if action_mask is None:
        action_mask = env.get_action_mask()

    legal_indices = tuple(legal_action_indices(action_mask))
    hand = observation["hand"]
    player_state = observation["player"]
    enemy_states = observation.get("enemies", [observation["enemy"]])
    assert isinstance(hand, list)
    assert isinstance(player_state, dict)
    assert isinstance(enemy_states, list)

    player_statuses = player_state["statuses"]
    player_strength = int(player_state.get("strength", 0))
    assert isinstance(player_statuses, dict)

    living_enemy_states = [
        enemy_state
        for enemy_state in enemy_states
        if isinstance(enemy_state, dict) and bool(enemy_state.get("alive", True))
    ]
    incoming_attack = any(
        isinstance(enemy_state["intent"], dict) and int(enemy_state["intent"].get("attack_damage", 0)) > 0
        for enemy_state in living_enemy_states
    )

    for action_index in legal_indices:
        if action_index == 0:
            continue

        action = env.decode_action(action_index)
        hand_index = action[1]
        target_index = 0 if len(action) == 2 else action[2]
        target_enemy = enemy_states[target_index]
        assert isinstance(target_enemy, dict)
        target_statuses = target_enemy["statuses"]
        assert isinstance(target_statuses, dict)

        card_name = str(hand[hand_index])
        card_damage = CARD_DAMAGE.get(card_name, 0)
        effective_damage = modify_attack_damage_for_statuses(
            card_damage,
            target_statuses,
            attacker_statuses=player_statuses,
            attacker_strength=player_strength,
        )
        if effective_damage >= int(target_enemy["hp"]):
            return action_index

    preferred_order = ("Defend", "Bash", "Strike", "Slimed") if incoming_attack else (
        "Bash",
        "Strike",
        "Defend",
        "Slimed",
    )
    for preferred_name in preferred_order:
        preferred_actions = []
        for action_index in legal_indices:
            if action_index == 0:
                continue
            action = env.decode_action(action_index)
            hand_index = action[1]
            if str(hand[hand_index]) != preferred_name:
                continue

            target_index = 0 if len(action) == 2 else action[2]
            target_enemy = enemy_states[target_index]
            assert isinstance(target_enemy, dict)
            target_intent = target_enemy["intent"]
            assert isinstance(target_intent, dict)
            intent_attack_damage = int(target_intent.get("attack_damage", 0))
            intent_attack_count = int(
                target_intent.get(
                    "attack_count",
                    1 if intent_attack_damage > 0 else 0,
                )
            )
            preferred_actions.append(
                (
                    -(intent_attack_damage * intent_attack_count),
                    int(target_enemy["hp"]),
                    target_index,
                    action_index,
                )
            )
        if preferred_actions:
            preferred_actions.sort()
            return preferred_actions[0][3]

    return 0


class QLearningAgent:
    """Simple masked tabular Q-learning agent over encoded observations."""

    def __init__(
        self,
        action_space_size: int,
        learning_rate: float = 0.1,
        discount: float = 0.99,
        epsilon: float = 1.0,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
        seed: int | None = None,
    ) -> None:
        if action_space_size <= 0:
            raise ValueError("action_space_size must be positive.")

        self.action_space_size = action_space_size
        self.learning_rate = learning_rate
        self.discount = discount
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.rng = Random(seed)
        self.q_table: dict[StateKey, list[float]] = {}

    def encode_state(self, env: CombatEnv, observation: Observation) -> StateKey:
        """Map an observation to a discrete table key."""
        return tuple(int(round(value * 10.0)) for value in env.encode_observation(observation))

    def select_action(
        self,
        state: StateKey,
        action_mask: ActionMask,
        training: bool = True,
    ) -> int:
        """Choose an epsilon-greedy legal action."""
        legal_indices = legal_action_indices(action_mask)
        if training and self.rng.random() < self.epsilon:
            return self.rng.choice(legal_indices)

        q_values = self._get_q_values(state)
        best_value = max(q_values[action_index] for action_index in legal_indices)
        best_actions = [
            action_index
            for action_index in legal_indices
            if q_values[action_index] == best_value
        ]
        return self.rng.choice(best_actions)

    def predict_q_values(self, state: StateKey) -> list[float]:
        """Return the current Q-values for one encoded table state."""
        return list(self._get_q_values(state))

    def update(
        self,
        state: StateKey,
        action: int,
        reward: float,
        next_state: StateKey,
        next_action_mask: ActionMask,
        done: bool,
    ) -> None:
        """Apply the tabular Q-learning update rule."""
        q_values = self._get_q_values(state)
        next_q_values = self._get_q_values(next_state)

        target = reward
        if not done:
            legal_next_actions = legal_action_indices(next_action_mask)
            target += self.discount * max(
                next_q_values[action_index] for action_index in legal_next_actions
            )

        q_values[action] += self.learning_rate * (target - q_values[action])

    def decay_epsilon_value(self) -> None:
        """Decay exploration toward the configured minimum."""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def _get_q_values(self, state: StateKey) -> list[float]:
        if state not in self.q_table:
            self.q_table[state] = [0.0] * self.action_space_size
        return self.q_table[state]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the agent."""
        serialized_q_table = [
            {
                "state": list(state),
                "q_values": list(q_values),
            }
            for state, q_values in sorted(self.q_table.items())
        ]
        return {
            "agent_type": "q_learning",
            "action_space_size": self.action_space_size,
            "learning_rate": self.learning_rate,
            "discount": self.discount,
            "epsilon": self.epsilon,
            "epsilon_min": self.epsilon_min,
            "epsilon_decay": self.epsilon_decay,
            "q_table": serialized_q_table,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QLearningAgent":
        """Reconstruct an agent from a serialized snapshot."""
        agent = cls(
            action_space_size=int(payload["action_space_size"]),
            learning_rate=float(payload["learning_rate"]),
            discount=float(payload["discount"]),
            epsilon=float(payload["epsilon"]),
            epsilon_min=float(payload["epsilon_min"]),
            epsilon_decay=float(payload["epsilon_decay"]),
        )
        serialized_q_table = payload.get("q_table", [])
        if not isinstance(serialized_q_table, list):
            raise ValueError("Serialized q_table must be a list.")
        agent.q_table = {
            tuple(int(value) for value in entry["state"]): [
                float(q_value) for q_value in entry["q_values"]
            ]
            for entry in serialized_q_table
        }
        return agent


def rollout_episode(
    env: CombatEnv,
    policy: PolicyFn,
    seed: int | None = None,
) -> EpisodeMetrics:
    """Run one episode with a policy and return summary metrics."""
    observation = env.reset(seed=seed)
    done = False
    total_reward = 0.0
    steps = 0

    while not done:
        action_mask = env.get_action_mask()
        action = policy(env, observation, action_mask)
        if action not in legal_action_indices(action_mask):
            raise ValueError(f"Policy returned illegal action index {action}.")
        observation, reward, done, _info = env.step_discrete(action)
        total_reward += reward
        steps += 1

    summary = env.get_episode_summary()
    return EpisodeMetrics(
        total_reward=total_reward,
        steps=steps,
        win=summary.winner == "player",
        player_hp=summary.player_hp,
        enemy_hp=summary.enemy_hp,
    )


def evaluate_policy(
    env_factory: Callable[[], CombatEnv],
    policy: PolicyFn,
    episodes: int,
    seed: int | None = None,
) -> EvaluationStats:
    """Evaluate a policy over multiple deterministic seeds."""
    if episodes <= 0:
        raise ValueError("episodes must be positive.")

    metrics: list[EpisodeMetrics] = []
    env = env_factory()
    for episode_index in range(episodes):
        episode_seed = _episode_seed(seed, episode_index)
        metrics.append(rollout_episode(env, policy, seed=episode_seed))

    total_reward = sum(metric.total_reward for metric in metrics)
    total_wins = sum(1 for metric in metrics if metric.win)
    total_steps = sum(metric.steps for metric in metrics)
    total_player_hp = sum(metric.player_hp for metric in metrics)

    return EvaluationStats(
        episodes=episodes,
        mean_reward=total_reward / episodes,
        win_rate=total_wins / episodes,
        mean_steps=total_steps / episodes,
        mean_player_hp=total_player_hp / episodes,
    )


def train_q_learning(
    env_factory: Callable[[], CombatEnv],
    episodes: int,
    evaluation_interval: int = 100,
    evaluation_episodes: int = 25,
    seed: int | None = None,
    final_evaluation_seed: int | None = None,
    learning_rate: float = 0.1,
    discount: float = 0.99,
    epsilon: float = 1.0,
    epsilon_min: float = 0.05,
    epsilon_decay: float = 0.995,
    progress_callback: ProgressCallback | None = None,
    progress_interval: int = 25,
    progress_window: int = 25,
) -> TrainingResult:
    """Train a masked tabular Q-learning agent and periodically evaluate it."""
    if episodes <= 0:
        raise ValueError("episodes must be positive.")
    if evaluation_interval < 0:
        raise ValueError("evaluation_interval cannot be negative.")
    if evaluation_episodes <= 0:
        raise ValueError("evaluation_episodes must be positive.")
    if progress_interval <= 0:
        raise ValueError("progress_interval must be positive.")
    if progress_window <= 0:
        raise ValueError("progress_window must be positive.")

    template_env = env_factory()
    agent = QLearningAgent(
        action_space_size=template_env.action_space_size,
        learning_rate=learning_rate,
        discount=discount,
        epsilon=epsilon,
        epsilon_min=epsilon_min,
        epsilon_decay=epsilon_decay,
        seed=seed,
    )

    training_metrics: list[EpisodeMetrics] = []
    evaluations: list[EvaluationSnapshot] = []
    training_started_at = perf_counter()
    env = template_env

    for episode_index in range(episodes):
        observation = env.reset(seed=_episode_seed(seed, episode_index))
        state = agent.encode_state(env, observation)
        done = False

        while not done:
            action_mask = env.get_action_mask()
            action = agent.select_action(state, action_mask, training=True)
            next_observation, reward, done, info = env.step_discrete(action)
            next_state = agent.encode_state(env, next_observation)
            next_mask = tuple(info["action_mask"])
            agent.update(
                state=state,
                action=action,
                reward=reward,
                next_state=next_state,
                next_action_mask=next_mask,
                done=done,
            )
            state = next_state

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
        agent.decay_epsilon_value()

        if evaluation_interval > 0 and (episode_index + 1) % evaluation_interval == 0:
            evaluations.append(
                EvaluationSnapshot(
                    episode=episode_index + 1,
                    stats=evaluate_policy(
                        env_factory=env_factory,
                        policy=lambda env, obs, mask, trained_agent=agent: trained_agent.select_action(
                            trained_agent.encode_state(env, obs),
                            mask,
                            training=False,
                        ),
                        episodes=evaluation_episodes,
                        seed=_episode_seed(seed, 10_000 + episode_index),
                    ),
                )
            )

        _maybe_report_progress(
            progress_callback=progress_callback,
            progress_interval=progress_interval,
            progress_window=progress_window,
            algorithm="q_learning",
            episode_index=episode_index,
            total_episodes=episodes,
            epsilon=agent.epsilon,
            training_metrics=training_metrics,
            evaluations_completed=len(evaluations),
            training_started_at=training_started_at,
            optimization_steps=0,
            recent_losses=None,
        )

    final_evaluation = evaluate_policy(
        env_factory=env_factory,
        policy=lambda env, obs, mask, trained_agent=agent: trained_agent.select_action(
            trained_agent.encode_state(env, obs),
            mask,
            training=False,
        ),
        episodes=evaluation_episodes,
        seed=(
            _episode_seed(seed, 20_000)
            if final_evaluation_seed is None
            else final_evaluation_seed
        ),
    )
    return TrainingResult(
        agent=agent,
        training_metrics=tuple(training_metrics),
        evaluations=tuple(evaluations),
        final_evaluation=final_evaluation,
    )


def _episode_seed(base_seed: int | None, offset: int) -> int | None:
    if base_seed is None:
        return None
    return base_seed + offset


def _maybe_report_progress(
    progress_callback: ProgressCallback | None,
    progress_interval: int,
    progress_window: int,
    algorithm: str,
    episode_index: int,
    total_episodes: int,
    epsilon: float,
    training_metrics: list[EpisodeMetrics],
    evaluations_completed: int,
    training_started_at: float,
    optimization_steps: int,
    recent_losses: list[float] | None,
) -> None:
    if progress_callback is None:
        return

    current_episode = episode_index + 1
    is_interval_step = current_episode % progress_interval == 0
    is_final_step = current_episode == total_episodes
    if not is_interval_step and not is_final_step:
        return

    recent_metrics = training_metrics[-progress_window:]
    elapsed_seconds = perf_counter() - training_started_at
    episodes_per_second = current_episode / elapsed_seconds if elapsed_seconds > 0 else 0.0
    remaining_episodes = total_episodes - current_episode
    eta_seconds = (
        remaining_episodes / episodes_per_second if episodes_per_second > 0 else 0.0
    )

    recent_mean_loss: float | None = None
    if recent_losses:
        recent_mean_loss = sum(recent_losses) / len(recent_losses)

    progress_callback(
        TrainingProgress(
            algorithm=algorithm,
            episode=current_episode,
            total_episodes=total_episodes,
            epsilon=epsilon,
            elapsed_seconds=elapsed_seconds,
            eta_seconds=eta_seconds,
            latest_metrics=training_metrics[-1],
            recent_mean_reward=sum(metric.total_reward for metric in recent_metrics)
            / len(recent_metrics),
            recent_win_rate=sum(1.0 if metric.win else 0.0 for metric in recent_metrics)
            / len(recent_metrics),
            recent_mean_steps=sum(metric.steps for metric in recent_metrics)
            / len(recent_metrics),
            evaluations_completed=evaluations_completed,
            optimization_steps=optimization_steps,
            recent_mean_loss=recent_mean_loss,
        )
    )
