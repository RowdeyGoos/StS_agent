"""Policy tracing helpers for single-combat inspection and logging."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..agents.baselines import (
    PolicyFn,
    QLearningAgent,
    choose_heuristic_action,
    choose_random_action,
    legal_action_indices,
)
from ..simulation.core import CombatEnv, Observation
from ..agents.dqn import DQNAgent, DoubleDQNAgent, DuelingDoubleDQNAgent
from ..agents.ppo import PPOAgent

TraceableAgent = (
    QLearningAgent | DQNAgent | DoubleDQNAgent | DuelingDoubleDQNAgent | PPOAgent
)


@dataclass(frozen=True, slots=True)
class StepTrace:
    """One traced player decision and resulting environment transition."""

    step_index: int
    turn: int
    action_index: int
    action: tuple[object, ...]
    reward: float
    done: bool
    observation: Observation
    next_observation: Observation
    info: dict[str, Any]
    action_mask: tuple[int, ...]
    legal_actions: tuple[tuple[object, ...], ...]
    legal_action_scores: dict[int, float] | None = None
    selected_action_score: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the step trace."""
        return {
            "step_index": self.step_index,
            "turn": self.turn,
            "action_index": self.action_index,
            "action": list(self.action),
            "reward": self.reward,
            "done": self.done,
            "observation": self.observation,
            "next_observation": self.next_observation,
            "info": self.info,
            "action_mask": list(self.action_mask),
            "legal_actions": [list(action) for action in self.legal_actions],
            "legal_action_scores": self.legal_action_scores,
            "selected_action_score": self.selected_action_score,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StepTrace":
        """Reconstruct one step trace from JSON data."""
        raw_scores = payload.get("legal_action_scores")
        legal_action_scores = None
        if isinstance(raw_scores, dict):
            legal_action_scores = {
                int(action_index): float(score)
                for action_index, score in raw_scores.items()
            }

        raw_legal_actions = payload.get("legal_actions", [])
        legal_actions = tuple(
            tuple(action)
            for action in raw_legal_actions
            if isinstance(action, list)
        )
        raw_action_mask = payload.get("action_mask", [])
        action_mask = tuple(int(value) for value in raw_action_mask)
        return cls(
            step_index=int(payload["step_index"]),
            turn=int(payload["turn"]),
            action_index=int(payload["action_index"]),
            action=tuple(payload["action"]),
            reward=float(payload["reward"]),
            done=bool(payload["done"]),
            observation=dict(payload["observation"]),
            next_observation=dict(payload["next_observation"]),
            info=dict(payload["info"]),
            action_mask=action_mask,
            legal_actions=legal_actions,
            legal_action_scores=legal_action_scores,
            selected_action_score=(
                None
                if payload.get("selected_action_score") is None
                else float(payload["selected_action_score"])
            ),
        )


@dataclass(frozen=True, slots=True)
class EpisodeTrace:
    """Full trace of one policy-controlled combat episode."""

    policy_name: str
    seed: int | None
    initial_observation: Observation
    steps: tuple[StepTrace, ...]
    summary: dict[str, Any]
    encounter: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the episode trace."""
        return {
            "policy_name": self.policy_name,
            "seed": self.seed,
            "encounter": self.encounter,
            "initial_observation": self.initial_observation,
            "steps": [step.as_dict() for step in self.steps],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EpisodeTrace":
        """Reconstruct a traced episode from JSON data."""
        raw_steps = payload.get("steps", [])
        return cls(
            policy_name=str(payload["policy_name"]),
            seed=None if payload.get("seed") is None else int(payload["seed"]),
            initial_observation=dict(payload["initial_observation"]),
            steps=tuple(
                StepTrace.from_dict(step)
                for step in raw_steps
                if isinstance(step, dict)
            ),
            summary=dict(payload["summary"]),
            encounter=(
                None
                if payload.get("encounter") is None
                else str(payload["encounter"])
            ),
        )


def policy_from_named_policy(policy_name: str) -> PolicyFn:
    """Return a built-in policy function by name."""
    if policy_name == "heuristic":
        return choose_heuristic_action
    if policy_name == "random":
        return lambda env, obs, mask: choose_random_action(env, obs, mask, rng=env.rng)
    raise ValueError(f"Unsupported built-in policy name: {policy_name!r}")


def policy_from_agent(agent: TraceableAgent) -> PolicyFn:
    """Adapt a trained agent into the common policy callable interface."""
    if isinstance(agent, QLearningAgent):
        return lambda env, obs, mask: agent.select_action(
            agent.encode_state(env, obs),
            mask,
            training=False,
        )
    if isinstance(agent, (DQNAgent, DoubleDQNAgent, DuelingDoubleDQNAgent, PPOAgent)):
        if isinstance(agent, PPOAgent):
            return lambda env, obs, mask: agent.select_action(
                env.encode_observation(obs),
                mask,
                action_features=env.encode_action_features(obs, action_mask=mask),
                training=False,
            )
        return lambda env, obs, mask: agent.select_action(
            env.encode_observation(obs),
            mask,
            action_features=env.encode_action_features(obs, action_mask=mask),
            training=False,
        )
    raise TypeError(f"Unsupported agent type for policy adaptation: {type(agent)!r}")


def policy_name_from_agent(agent: TraceableAgent) -> str:
    """Return the stable policy name for one trained agent instance."""
    if isinstance(agent, QLearningAgent):
        return "q_learning"
    if isinstance(agent, PPOAgent):
        return "masked_ppo"
    if isinstance(agent, DuelingDoubleDQNAgent):
        return "dueling_double_dqn"
    if isinstance(agent, DoubleDQNAgent):
        return "double_dqn"
    if isinstance(agent, DQNAgent):
        return "dqn"
    raise TypeError(f"Unsupported agent type for policy naming: {type(agent)!r}")


def legal_action_scores_for_agent(
    agent: TraceableAgent,
    env: CombatEnv,
    observation: Observation,
    action_mask: tuple[int, ...],
) -> dict[int, float]:
    """Return per-legal-action scores for a trained agent at one decision point."""
    if isinstance(agent, QLearningAgent):
        state = agent.encode_state(env, observation)
        q_values = agent.predict_q_values(state)
    elif isinstance(agent, (DQNAgent, DoubleDQNAgent, DuelingDoubleDQNAgent)):
        encoded_observation = env.encode_observation(observation)
        q_values = agent.predict_q_values(
            encoded_observation,
            action_mask=action_mask,
            action_features=env.encode_action_features(
                observation,
                action_mask=action_mask,
            ),
        )
    elif isinstance(agent, PPOAgent):
        encoded_observation = env.encode_observation(observation)
        q_values = agent.predict_action_scores(
            encoded_observation,
            action_mask,
            action_features=env.encode_action_features(
                observation,
                action_mask=action_mask,
            ),
        )
    else:
        raise TypeError(f"Unsupported agent type for action scoring: {type(agent)!r}")

    return {
        action_index: q_values[action_index]
        for action_index, is_legal in enumerate(action_mask)
        if is_legal
    }


def trace_policy_episode(
    env: CombatEnv,
    policy: PolicyFn,
    policy_name: str,
    seed: int | None = None,
    traced_agent: TraceableAgent | None = None,
    encounter: str | None = None,
) -> EpisodeTrace:
    """Run one traced combat episode using a policy or trained agent."""
    observation = env.reset(seed=seed)
    initial_observation = observation
    done = False
    steps: list[StepTrace] = []

    while not done:
        action_mask = env.get_action_mask()
        legal_actions = tuple(env.get_legal_actions())
        action = policy(env, observation, action_mask)
        if action not in legal_action_indices(action_mask):
            raise ValueError(f"Policy returned illegal action index {action}.")
        legal_action_scores = None
        selected_action_score = None
        if traced_agent is not None:
            legal_action_scores = legal_action_scores_for_agent(
                traced_agent,
                env,
                observation,
                action_mask,
            )
            selected_action_score = legal_action_scores.get(action)

        next_observation, reward, done, info = env.step_discrete(action)
        steps.append(
            StepTrace(
                step_index=len(steps),
                turn=int(observation["turn"]),
                action_index=action,
                action=env.decode_action(action),
                reward=reward,
                done=done,
                observation=observation,
                next_observation=next_observation,
                info=dict(info),
                action_mask=action_mask,
                legal_actions=legal_actions,
                legal_action_scores=legal_action_scores,
                selected_action_score=selected_action_score,
            )
        )
        observation = next_observation

    return EpisodeTrace(
        policy_name=policy_name,
        seed=seed,
        initial_observation=initial_observation,
        steps=tuple(steps),
        summary=env.get_episode_summary().as_dict(),
        encounter=encounter,
    )


def save_episode_trace(trace: EpisodeTrace, path: str | Path) -> None:
    """Write a traced episode to a JSON file."""
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        json.dumps(trace.as_dict(), indent=2),
        encoding="utf-8",
    )


def load_episode_trace(path: str | Path) -> EpisodeTrace:
    """Load a traced episode JSON log from disk."""
    trace_path = Path(path)
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Episode trace payload must be a dictionary.")
    return EpisodeTrace.from_dict(payload)


def describe_top_action_scores(
    action_scores: dict[int, float] | None,
    top_n: int = 5,
) -> str | None:
    """Return a compact text summary of the highest-scored legal actions."""
    if not action_scores:
        return None

    ranked_scores = sorted(
        action_scores.items(),
        key=lambda item: (-item[1], item[0]),
    )[:max(1, top_n)]
    fragments = [f"{action_index}:{score:.3f}" for action_index, score in ranked_scores]
    return ", ".join(fragments)
