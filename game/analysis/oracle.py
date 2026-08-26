"""Per-decision oracle regret analysis for saved policy traces."""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import Executor
from typing import Any, Callable

from ..simulation.actions import CombatAction
from .bruteforce import brute_force_combat, clone_combat_env
from ..simulation.core import CombatEnv, Observation
from .oracle_pool import (
    OracleSearchTask,
    create_oracle_process_pool,
    prepare_env_for_oracle_process,
    run_oracle_search_task,
)
from .watch import EpisodeTrace

OracleScore = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class OracleActionEvaluation:
    """Best continuation found after committing to one legal action."""

    action_index: int
    action: CombatAction
    proven_optimal: bool
    termination_reason: str
    actions_to_terminal: int | None
    line_action_indices: tuple[int, ...]
    summary: dict[str, Any] | None
    expanded_nodes: int
    generated_nodes: int

    @property
    def score(self) -> OracleScore | None:
        """Return the combat objective score for this action's best line."""
        if self.summary is None or self.actions_to_terminal is None:
            return None
        return _outcome_score(self.summary, self.actions_to_terminal)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable evaluation payload."""
        return {
            "action_index": self.action_index,
            "action": list(self.action),
            "proven_optimal": self.proven_optimal,
            "termination_reason": self.termination_reason,
            "actions_to_terminal": self.actions_to_terminal,
            "line_action_indices": list(self.line_action_indices),
            "summary": self.summary,
            "expanded_nodes": self.expanded_nodes,
            "generated_nodes": self.generated_nodes,
        }


@dataclass(frozen=True, slots=True)
class OracleDecisionAnalysis:
    """Oracle comparison for one action selected by the traced policy."""

    decision_index: int
    turn: int
    observation: Observation
    selected_action_index: int
    selected_action: CombatAction
    action_evaluations: tuple[OracleActionEvaluation, ...]
    best_found_action_indices: tuple[int, ...]
    selected_matches_best_found: bool | None
    selected_is_optimal: bool | None
    comparison_proven: bool
    decisive_dimension: str
    winner_regret: int | None
    player_hp_regret: int | None
    enemy_hp_regret: int | None
    action_count_regret: int | None
    environment_reward_regret: float | None

    @property
    def is_proven_divergence(self) -> bool:
        """Return whether the selected action is proven suboptimal."""
        return self.selected_is_optimal is False

    @property
    def is_best_found_divergence(self) -> bool:
        """Return whether the selected action trails the best line found so far."""
        return self.selected_matches_best_found is False

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable decision payload."""
        return {
            "decision_index": self.decision_index,
            "turn": self.turn,
            "observation": self.observation,
            "selected_action_index": self.selected_action_index,
            "selected_action": list(self.selected_action),
            "action_evaluations": [
                evaluation.as_dict() for evaluation in self.action_evaluations
            ],
            "best_found_action_indices": list(self.best_found_action_indices),
            "selected_matches_best_found": self.selected_matches_best_found,
            "selected_is_optimal": self.selected_is_optimal,
            "comparison_proven": self.comparison_proven,
            "decisive_dimension": self.decisive_dimension,
            "winner_regret": self.winner_regret,
            "player_hp_regret": self.player_hp_regret,
            "enemy_hp_regret": self.enemy_hp_regret,
            "action_count_regret": self.action_count_regret,
            "environment_reward_regret": self.environment_reward_regret,
        }


@dataclass(frozen=True, slots=True)
class OraclePolicyAnalysis:
    """Per-decision oracle analysis for one complete policy episode."""

    policy_name: str
    seed: int | None
    decisions: tuple[OracleDecisionAnalysis, ...]

    @property
    def proven_divergences(self) -> tuple[OracleDecisionAnalysis, ...]:
        """Return proven suboptimal decisions in episode order."""
        return tuple(
            decision for decision in self.decisions if decision.is_proven_divergence
        )

    @property
    def uncertain_decisions(self) -> tuple[OracleDecisionAnalysis, ...]:
        """Return decisions whose full legal-action comparison was not proven."""
        return tuple(
            decision for decision in self.decisions if not decision.comparison_proven
        )

    @property
    def ranked_weak_points(self) -> tuple[OracleDecisionAnalysis, ...]:
        """Return divergences ranked by objective impact, then episode order."""
        divergences = [
            decision
            for decision in self.decisions
            if decision.is_best_found_divergence
        ]
        return tuple(
            sorted(
                divergences,
                key=lambda decision: (*_severity_key(decision), -decision.decision_index),
                reverse=True,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable analysis payload."""
        first_divergence = next(iter(self.proven_divergences), None)
        return {
            "policy_name": self.policy_name,
            "seed": self.seed,
            "decision_count": len(self.decisions),
            "proven_divergence_count": len(self.proven_divergences),
            "uncertain_decision_count": len(self.uncertain_decisions),
            "first_proven_divergence_index": (
                None if first_divergence is None else first_divergence.decision_index
            ),
            "ranked_weak_point_indices": [
                decision.decision_index for decision in self.ranked_weak_points
            ],
            "decisions": [decision.as_dict() for decision in self.decisions],
        }


def analyze_oracle_decision(
    env: CombatEnv,
    selected_action_index: int,
    *,
    decision_index: int = 0,
    max_steps: int = 40,
    max_nodes_per_action: int = 25_000,
    time_limit_seconds_per_action: float | None = None,
    search_workers: int = 1,
    _executor: Executor | None = None,
) -> OracleDecisionAnalysis:
    """Evaluate every legal action from the environment's current state."""
    if max_steps <= 0:
        raise ValueError("max_steps must be positive.")
    if search_workers <= 0:
        raise ValueError("search_workers must be positive.")
    observation = env.get_observation()
    action_mask = env.get_action_mask()
    if (
        selected_action_index < 0
        or selected_action_index >= len(action_mask)
        or not action_mask[selected_action_index]
    ):
        raise ValueError(
            f"Selected action index {selected_action_index} is not legal in this state."
        )

    legal_actions = tuple(env.get_legal_actions())
    if _executor is not None:
        evaluations = _evaluate_actions_with_executor(
            env,
            legal_actions,
            max_steps=max_steps,
            max_nodes_per_action=max_nodes_per_action,
            time_limit_seconds_per_action=time_limit_seconds_per_action,
            executor=_executor,
        )
    elif search_workers > 1:
        with create_oracle_process_pool(search_workers) as executor:
            evaluations = _evaluate_actions_with_executor(
                env,
                legal_actions,
                max_steps=max_steps,
                max_nodes_per_action=max_nodes_per_action,
                time_limit_seconds_per_action=time_limit_seconds_per_action,
                executor=executor,
            )
    else:
        evaluations = tuple(
            evaluate_committed_action(
                env,
                action,
                max_steps=max_steps,
                max_nodes=max_nodes_per_action,
                time_limit_seconds=time_limit_seconds_per_action,
            )
            for action in legal_actions
        )
    scored_evaluations = [
        evaluation for evaluation in evaluations if evaluation.score is not None
    ]
    best_evaluation = (
        max(scored_evaluations, key=lambda evaluation: evaluation.score)
        if scored_evaluations
        else None
    )
    best_score = None if best_evaluation is None else best_evaluation.score
    best_action_indices = tuple(
        evaluation.action_index
        for evaluation in evaluations
        if evaluation.score is not None and evaluation.score == best_score
    )
    selected_evaluation = next(
        evaluation
        for evaluation in evaluations
        if evaluation.action_index == selected_action_index
    )
    comparison_proven = bool(evaluations) and all(
        evaluation.proven_optimal and evaluation.score is not None
        for evaluation in evaluations
    )
    if best_evaluation is None:
        selected_matches_best = None
    elif selected_evaluation.score is None:
        selected_matches_best = False
    else:
        selected_matches_best = selected_evaluation.score == best_score
    selected_is_optimal = (
        selected_matches_best if comparison_proven else None
    )
    regret = _calculate_regret(best_evaluation, selected_evaluation)

    return OracleDecisionAnalysis(
        decision_index=decision_index,
        turn=int(observation["turn"]),
        observation=observation,
        selected_action_index=selected_action_index,
        selected_action=env.decode_action(selected_action_index),
        action_evaluations=evaluations,
        best_found_action_indices=best_action_indices,
        selected_matches_best_found=selected_matches_best,
        selected_is_optimal=selected_is_optimal,
        comparison_proven=comparison_proven,
        decisive_dimension=regret[0],
        winner_regret=regret[1],
        player_hp_regret=regret[2],
        enemy_hp_regret=regret[3],
        action_count_regret=regret[4],
        environment_reward_regret=regret[5],
    )


def analyze_episode_trace_with_oracle(
    env: CombatEnv,
    trace: EpisodeTrace,
    *,
    max_steps: int = 40,
    max_nodes_per_action: int = 25_000,
    time_limit_seconds_per_action: float | None = None,
    search_workers: int = 1,
    decision_callback: Callable[[OracleDecisionAnalysis], None] | None = None,
) -> OraclePolicyAnalysis:
    """Replay a policy trace and evaluate every action at every visited state."""
    if search_workers <= 0:
        raise ValueError("search_workers must be positive.")
    if search_workers > 1:
        with create_oracle_process_pool(search_workers) as executor:
            return _analyze_episode_trace_with_oracle(
                env,
                trace,
                max_steps=max_steps,
                max_nodes_per_action=max_nodes_per_action,
                time_limit_seconds_per_action=time_limit_seconds_per_action,
                search_workers=search_workers,
                executor=executor,
                decision_callback=decision_callback,
            )
    return _analyze_episode_trace_with_oracle(
        env,
        trace,
        max_steps=max_steps,
        max_nodes_per_action=max_nodes_per_action,
        time_limit_seconds_per_action=time_limit_seconds_per_action,
        search_workers=search_workers,
        executor=None,
        decision_callback=decision_callback,
    )


def _analyze_episode_trace_with_oracle(
    env: CombatEnv,
    trace: EpisodeTrace,
    *,
    max_steps: int,
    max_nodes_per_action: int,
    time_limit_seconds_per_action: float | None,
    search_workers: int,
    executor: Executor | None,
    decision_callback: Callable[[OracleDecisionAnalysis], None] | None,
) -> OraclePolicyAnalysis:
    """Replay implementation that can reuse one process pool across decisions."""
    observation = env.reset(seed=trace.seed)
    decisions: list[OracleDecisionAnalysis] = []
    for trace_step in trace.steps:
        if observation != trace_step.observation:
            raise ValueError(
                "Trace observation does not match the replayed seeded combat state "
                f"at decision {trace_step.step_index}."
            )
        decision = analyze_oracle_decision(
            env,
            trace_step.action_index,
            decision_index=trace_step.step_index,
            max_steps=max_steps,
            max_nodes_per_action=max_nodes_per_action,
            time_limit_seconds_per_action=time_limit_seconds_per_action,
            search_workers=search_workers,
            _executor=executor,
        )
        decisions.append(decision)
        if decision_callback is not None:
            decision_callback(decision)
        observation, _reward, _done, _info = env.step_discrete(trace_step.action_index)

    return OraclePolicyAnalysis(
        policy_name=trace.policy_name,
        seed=trace.seed,
        decisions=tuple(decisions),
    )


def _evaluate_actions_with_executor(
    env: CombatEnv,
    actions: tuple[CombatAction, ...],
    *,
    max_steps: int,
    max_nodes_per_action: int,
    time_limit_seconds_per_action: float | None,
    executor: Executor,
) -> tuple[OracleActionEvaluation, ...]:
    prepared_env = prepare_env_for_oracle_process(env)
    tasks = (
        OracleSearchTask(
            env=prepared_env,
            action=action,
            max_steps=max_steps,
            max_nodes=max_nodes_per_action,
            time_limit_seconds=time_limit_seconds_per_action,
        )
        for action in actions
    )
    return tuple(executor.map(run_oracle_search_task, tasks))


def evaluate_committed_action(
    env: CombatEnv,
    action: CombatAction,
    *,
    max_steps: int,
    max_nodes: int,
    time_limit_seconds: float | None,
) -> OracleActionEvaluation:
    """Evaluate one committed action with the seeded hindsight oracle."""
    child_env = clone_combat_env(env)
    action_index = child_env.encode_action(action)
    child_env.step(action)
    if child_env.done:
        return OracleActionEvaluation(
            action_index=action_index,
            action=action,
            proven_optimal=True,
            termination_reason="immediate_terminal",
            actions_to_terminal=1,
            line_action_indices=(action_index,),
            summary=child_env.get_episode_summary().as_dict(),
            expanded_nodes=0,
            generated_nodes=1,
        )

    continuation = brute_force_combat(
        child_env,
        max_steps=max_steps - 1,
        max_nodes=max_nodes,
        time_limit_seconds=time_limit_seconds,
    )
    actions_to_terminal = (
        None if continuation.summary is None else 1 + len(continuation.steps)
    )
    return OracleActionEvaluation(
        action_index=action_index,
        action=action,
        proven_optimal=continuation.proven_optimal,
        termination_reason=continuation.termination_reason,
        actions_to_terminal=actions_to_terminal,
        line_action_indices=(action_index, *continuation.action_indices),
        summary=continuation.summary,
        expanded_nodes=continuation.expanded_nodes,
        generated_nodes=1 + continuation.generated_nodes,
    )


def _calculate_regret(
    best: OracleActionEvaluation | None,
    selected: OracleActionEvaluation,
) -> tuple[str, int | None, int | None, int | None, int | None, float | None]:
    if best is None or best.summary is None or selected.summary is None:
        return ("unknown", None, None, None, None, None)

    best_summary = best.summary
    selected_summary = selected.summary
    winner_regret = (
        (1 if best_summary["winner"] == "player" else 0)
        - (1 if selected_summary["winner"] == "player" else 0)
    )
    player_hp_regret = int(best_summary["player_hp"]) - int(
        selected_summary["player_hp"]
    )
    enemy_hp_regret = int(selected_summary["enemy_hp"]) - int(
        best_summary["enemy_hp"]
    )
    action_count_regret = (
        None
        if best.actions_to_terminal is None or selected.actions_to_terminal is None
        else selected.actions_to_terminal - best.actions_to_terminal
    )
    reward_regret = float(best_summary["total_reward"]) - float(
        selected_summary["total_reward"]
    )

    if winner_regret != 0:
        decisive_dimension = "winner"
    elif player_hp_regret != 0:
        decisive_dimension = "player_hp"
    elif enemy_hp_regret != 0:
        decisive_dimension = "enemy_hp"
    elif action_count_regret != 0:
        decisive_dimension = "actions"
    else:
        decisive_dimension = "none"
    return (
        decisive_dimension,
        winner_regret,
        player_hp_regret,
        enemy_hp_regret,
        action_count_regret,
        reward_regret,
    )


def _outcome_score(summary: dict[str, Any], actions_to_terminal: int) -> OracleScore:
    return (
        1 if summary["winner"] == "player" else 0,
        int(summary["player_hp"]),
        -int(summary["enemy_hp"]),
        -actions_to_terminal,
    )


def _severity_key(decision: OracleDecisionAnalysis) -> tuple[int, int, float]:
    dimension_rank = {
        "unknown": 0,
        "none": 0,
        "actions": 1,
        "enemy_hp": 2,
        "player_hp": 3,
        "winner": 4,
    }[decision.decisive_dimension]
    magnitude_by_dimension: dict[str, float] = {
        "unknown": 0.0,
        "none": 0.0,
        "actions": float(decision.action_count_regret or 0),
        "enemy_hp": float(decision.enemy_hp_regret or 0),
        "player_hp": float(decision.player_hp_regret or 0),
        "winner": float(decision.winner_regret or 0),
    }
    return (
        1 if decision.comparison_proven else 0,
        dimension_rank,
        magnitude_by_dimension[decision.decisive_dimension],
    )
