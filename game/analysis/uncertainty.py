"""Sampled action analysis that hides information unavailable to the agent.

The exact combat oracle knows pile order and the simulator RNG state.  This
module instead constructs multiple determinizations that all have the same
structured observation, but different unseen draw orders and future random
streams.  Every legal action is evaluated against the same determinizations so
their aggregate outcomes are directly comparable.

Continuation searches are still hindsight-optimal inside each sampled world.
The result is therefore a practical root-action estimate, not an exact POMDP
solution or a proof about the full distribution of possible combats.
"""

from __future__ import annotations

from concurrent.futures import Executor
from dataclasses import dataclass
from math import sqrt
from random import Random
from typing import Any, Callable

from ..simulation.actions import CombatAction
from .bruteforce import clone_combat_env
from ..simulation.core import CombatEnv, Observation
from .oracle import OracleActionEvaluation, OracleScore, evaluate_committed_action
from .oracle_pool import (
    OracleSearchTask,
    create_oracle_process_pool,
    prepare_env_for_oracle_process,
    run_oracle_search_task,
)
from .watch import EpisodeTrace


@dataclass(frozen=True, slots=True)
class InformationAwareActionEvaluation:
    """Aggregate oracle outcomes for one action over sampled hidden worlds."""

    action_index: int
    action: CombatAction
    sample_count: int
    terminal_sample_count: int
    proven_sample_count: int
    win_count: int
    win_rate: float | None
    win_rate_95_low: float | None
    win_rate_95_high: float | None
    mean_player_hp: float | None
    mean_enemy_hp: float | None
    mean_actions_to_terminal: float | None
    mean_environment_reward: float | None
    hindsight_best_sample_count: int
    hindsight_best_rate: float | None
    _sample_scores: tuple[OracleScore | None, ...]

    @property
    def all_samples_terminal(self) -> bool:
        """Return whether every sampled continuation reached a terminal state."""
        return self.terminal_sample_count == self.sample_count

    @property
    def all_sample_searches_proven(self) -> bool:
        """Return whether every sampled continuation was solved exactly."""
        return self.proven_sample_count == self.sample_count

    @property
    def aggregate_score(self) -> tuple[int, int, int, int] | None:
        """Return the lexicographic summed objective when all samples resolved."""
        if not self.all_samples_terminal:
            return None
        scores = tuple(score for score in self._sample_scores if score is not None)
        return (
            sum(score[0] for score in scores),
            sum(score[1] for score in scores),
            sum(score[2] for score in scores),
            sum(score[3] for score in scores),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable aggregate without private sample states."""
        return {
            "action_index": self.action_index,
            "action": list(self.action),
            "sample_count": self.sample_count,
            "terminal_sample_count": self.terminal_sample_count,
            "proven_sample_count": self.proven_sample_count,
            "all_samples_terminal": self.all_samples_terminal,
            "all_sample_searches_proven": self.all_sample_searches_proven,
            "win_count": self.win_count,
            "win_rate": self.win_rate,
            "win_rate_95_low": self.win_rate_95_low,
            "win_rate_95_high": self.win_rate_95_high,
            "mean_player_hp": self.mean_player_hp,
            "mean_enemy_hp": self.mean_enemy_hp,
            "mean_actions_to_terminal": self.mean_actions_to_terminal,
            "mean_environment_reward": self.mean_environment_reward,
            "hindsight_best_sample_count": self.hindsight_best_sample_count,
            "hindsight_best_rate": self.hindsight_best_rate,
        }


@dataclass(frozen=True, slots=True)
class InformationAwareDecisionAnalysis:
    """Sampled information-set comparison for one policy decision."""

    decision_index: int
    turn: int
    observation: Observation
    selected_action_index: int
    selected_action: CombatAction
    sample_count: int
    sampling_seed: int
    action_evaluations: tuple[InformationAwareActionEvaluation, ...]
    best_action_indices: tuple[int, ...]
    selected_matches_best: bool | None
    all_actions_resolved: bool
    all_sample_searches_proven: bool
    decisive_dimension: str
    win_rate_regret: float | None
    mean_player_hp_regret: float | None
    mean_enemy_hp_regret: float | None
    mean_action_count_regret: float | None
    mean_environment_reward_regret: float | None

    @property
    def is_sampled_divergence(self) -> bool:
        """Return whether the selected action trails the sampled best action."""
        return self.selected_matches_best is False

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable decision payload."""
        return {
            "decision_index": self.decision_index,
            "turn": self.turn,
            "observation": self.observation,
            "selected_action_index": self.selected_action_index,
            "selected_action": list(self.selected_action),
            "sample_count": self.sample_count,
            "sampling_seed": self.sampling_seed,
            "action_evaluations": [
                evaluation.as_dict() for evaluation in self.action_evaluations
            ],
            "best_action_indices": list(self.best_action_indices),
            "selected_matches_best": self.selected_matches_best,
            "all_actions_resolved": self.all_actions_resolved,
            "all_sample_searches_proven": self.all_sample_searches_proven,
            "decisive_dimension": self.decisive_dimension,
            "win_rate_regret": self.win_rate_regret,
            "mean_player_hp_regret": self.mean_player_hp_regret,
            "mean_enemy_hp_regret": self.mean_enemy_hp_regret,
            "mean_action_count_regret": self.mean_action_count_regret,
            "mean_environment_reward_regret": self.mean_environment_reward_regret,
        }


@dataclass(frozen=True, slots=True)
class InformationAwarePolicyAnalysis:
    """Sampled information-aware analysis for one complete policy trace."""

    policy_name: str
    combat_seed: int | None
    sample_count: int
    sampling_seed: int
    decisions: tuple[InformationAwareDecisionAnalysis, ...]

    @property
    def sampled_divergences(self) -> tuple[InformationAwareDecisionAnalysis, ...]:
        """Return sampled divergences in episode order."""
        return tuple(
            decision for decision in self.decisions if decision.is_sampled_divergence
        )

    @property
    def unresolved_decisions(self) -> tuple[InformationAwareDecisionAnalysis, ...]:
        """Return decisions where at least one action lacked all terminal samples."""
        return tuple(
            decision for decision in self.decisions if not decision.all_actions_resolved
        )

    @property
    def ranked_weak_points(self) -> tuple[InformationAwareDecisionAnalysis, ...]:
        """Return sampled divergences ranked by expected objective impact."""
        return tuple(
            sorted(
                self.sampled_divergences,
                key=lambda decision: (
                    decision.win_rate_regret or 0.0,
                    decision.mean_player_hp_regret or 0.0,
                    decision.mean_enemy_hp_regret or 0.0,
                    decision.mean_action_count_regret or 0.0,
                    -decision.decision_index,
                ),
                reverse=True,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable policy analysis payload."""
        return {
            "method": "sampled_hidden_state_root_action_oracle",
            "policy_name": self.policy_name,
            "combat_seed": self.combat_seed,
            "sample_count": self.sample_count,
            "sampling_seed": self.sampling_seed,
            "decision_count": len(self.decisions),
            "sampled_divergence_count": len(self.sampled_divergences),
            "unresolved_decision_count": len(self.unresolved_decisions),
            "ranked_weak_point_indices": [
                decision.decision_index for decision in self.ranked_weak_points
            ],
            "limitations": (
                "Each current action is shared across hidden-state samples, but its "
                "continuation is hindsight-optimal within each sample. Results are "
                "Monte Carlo estimates, not full information-set optimality proofs."
            ),
            "decisions": [decision.as_dict() for decision in self.decisions],
        }


def sample_hidden_combat_states(
    env: CombatEnv,
    *,
    sample_count: int,
    sampling_seed: int,
) -> tuple[CombatEnv, ...]:
    """Sample hidden futures that remain identical to the current observation."""
    if sample_count <= 0:
        raise ValueError("sample_count must be positive.")
    env.get_observation()
    sampling_rng = Random(sampling_seed)
    samples: list[CombatEnv] = []
    for _sample_index in range(sample_count):
        sample = clone_combat_env(env)
        assert sample.player is not None
        assert sample.enemies is not None

        # Pile composition is observed, but draw order is not.
        sampling_rng.shuffle(sample.player.deck.draw_pile)

        # Preserve shared-RNG identity while replacing unknowable future streams.
        replacements: dict[int, Random] = {}

        def replacement(source: Random) -> Random:
            source_id = id(source)
            if source_id not in replacements:
                replacements[source_id] = Random(sampling_rng.getrandbits(128))
            return replacements[source_id]

        sample.rng = replacement(sample.rng)
        sample.player.deck.rng = replacement(sample.player.deck.rng)
        for enemy in sample.enemies:
            enemy.rng = replacement(enemy.rng)
        sample.last_observation = sample.get_observation()
        if sample.last_observation != env.get_observation():
            raise RuntimeError("Hidden-state sampling changed the visible observation.")
        samples.append(sample)
    return tuple(samples)


def analyze_information_aware_decision(
    env: CombatEnv,
    selected_action_index: int,
    *,
    decision_index: int = 0,
    sample_count: int = 8,
    sampling_seed: int = 1_729,
    max_steps: int = 20,
    max_nodes_per_action: int = 2_500,
    time_limit_seconds_per_action: float | None = None,
    search_workers: int = 1,
    _executor: Executor | None = None,
) -> InformationAwareDecisionAnalysis:
    """Compare legal actions over hidden futures consistent with one observation."""
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

    sampled_envs = sample_hidden_combat_states(
        env,
        sample_count=sample_count,
        sampling_seed=sampling_seed,
    )
    legal_actions = tuple(env.get_legal_actions())
    if _executor is not None:
        raw_evaluations = _evaluate_sampled_actions_with_executor(
            sampled_envs,
            legal_actions,
            max_steps=max_steps,
            max_nodes_per_action=max_nodes_per_action,
            time_limit_seconds_per_action=time_limit_seconds_per_action,
            executor=_executor,
        )
    elif search_workers > 1:
        with create_oracle_process_pool(search_workers) as executor:
            raw_evaluations = _evaluate_sampled_actions_with_executor(
                sampled_envs,
                legal_actions,
                max_steps=max_steps,
                max_nodes_per_action=max_nodes_per_action,
                time_limit_seconds_per_action=time_limit_seconds_per_action,
                executor=executor,
            )
    else:
        raw_evaluations = []
        for action in legal_actions:
            outcomes = tuple(
                evaluate_committed_action(
                    sampled_env,
                    action,
                    max_steps=max_steps,
                    max_nodes=max_nodes_per_action,
                    time_limit_seconds=time_limit_seconds_per_action,
                )
                for sampled_env in sampled_envs
            )
            raw_evaluations.append((action, outcomes))

    jointly_resolved_samples = tuple(
        sample_index
        for sample_index in range(sample_count)
        if all(
            outcomes[sample_index].score is not None
            for _action, outcomes in raw_evaluations
        )
    )
    hindsight_best_counts: dict[int, int] = {
        env.encode_action(action): 0 for action in legal_actions
    }
    for sample_index in jointly_resolved_samples:
        sample_best_score = max(
            outcomes[sample_index].score
            for _action, outcomes in raw_evaluations
            if outcomes[sample_index].score is not None
        )
        for action, outcomes in raw_evaluations:
            if outcomes[sample_index].score == sample_best_score:
                hindsight_best_counts[env.encode_action(action)] += 1

    evaluations = tuple(
        _aggregate_action_evaluation(
            env,
            action,
            outcomes,
            hindsight_best_count=hindsight_best_counts[env.encode_action(action)],
            jointly_resolved_count=len(jointly_resolved_samples),
        )
        for action, outcomes in raw_evaluations
    )
    resolved_evaluations = [
        evaluation
        for evaluation in evaluations
        if evaluation.aggregate_score is not None
    ]
    best_evaluation = (
        max(resolved_evaluations, key=lambda evaluation: evaluation.aggregate_score)
        if resolved_evaluations
        else None
    )
    best_score = None if best_evaluation is None else best_evaluation.aggregate_score
    best_action_indices = tuple(
        evaluation.action_index
        for evaluation in evaluations
        if evaluation.aggregate_score is not None
        and evaluation.aggregate_score == best_score
    )
    selected_evaluation = next(
        evaluation
        for evaluation in evaluations
        if evaluation.action_index == selected_action_index
    )
    all_actions_resolved = all(
        evaluation.all_samples_terminal for evaluation in evaluations
    )
    if best_evaluation is None or not all_actions_resolved:
        selected_matches_best = None
    else:
        selected_matches_best = selected_evaluation.aggregate_score == best_score
    regret = _calculate_expected_regret(best_evaluation, selected_evaluation)

    return InformationAwareDecisionAnalysis(
        decision_index=decision_index,
        turn=int(observation["turn"]),
        observation=observation,
        selected_action_index=selected_action_index,
        selected_action=env.decode_action(selected_action_index),
        sample_count=sample_count,
        sampling_seed=sampling_seed,
        action_evaluations=evaluations,
        best_action_indices=best_action_indices,
        selected_matches_best=selected_matches_best,
        all_actions_resolved=all_actions_resolved,
        all_sample_searches_proven=all(
            evaluation.all_sample_searches_proven for evaluation in evaluations
        ),
        decisive_dimension=regret[0],
        win_rate_regret=regret[1],
        mean_player_hp_regret=regret[2],
        mean_enemy_hp_regret=regret[3],
        mean_action_count_regret=regret[4],
        mean_environment_reward_regret=regret[5],
    )


def analyze_episode_trace_with_uncertainty(
    env: CombatEnv,
    trace: EpisodeTrace,
    *,
    sample_count: int = 8,
    sampling_seed: int = 1_729,
    max_steps: int = 20,
    max_nodes_per_action: int = 2_500,
    time_limit_seconds_per_action: float | None = None,
    search_workers: int = 1,
    decision_callback: Callable[[InformationAwareDecisionAnalysis], None] | None = None,
) -> InformationAwarePolicyAnalysis:
    """Replay a trace and perform sampled information-aware analysis at each state."""
    if search_workers <= 0:
        raise ValueError("search_workers must be positive.")
    if search_workers > 1:
        with create_oracle_process_pool(search_workers) as executor:
            return _analyze_episode_trace_with_uncertainty(
                env,
                trace,
                sample_count=sample_count,
                sampling_seed=sampling_seed,
                max_steps=max_steps,
                max_nodes_per_action=max_nodes_per_action,
                time_limit_seconds_per_action=time_limit_seconds_per_action,
                search_workers=search_workers,
                executor=executor,
                decision_callback=decision_callback,
            )
    return _analyze_episode_trace_with_uncertainty(
        env,
        trace,
        sample_count=sample_count,
        sampling_seed=sampling_seed,
        max_steps=max_steps,
        max_nodes_per_action=max_nodes_per_action,
        time_limit_seconds_per_action=time_limit_seconds_per_action,
        search_workers=search_workers,
        executor=None,
        decision_callback=decision_callback,
    )


def _analyze_episode_trace_with_uncertainty(
    env: CombatEnv,
    trace: EpisodeTrace,
    *,
    sample_count: int,
    sampling_seed: int,
    max_steps: int,
    max_nodes_per_action: int,
    time_limit_seconds_per_action: float | None,
    search_workers: int,
    executor: Executor | None,
    decision_callback: Callable[[InformationAwareDecisionAnalysis], None] | None,
) -> InformationAwarePolicyAnalysis:
    """Replay implementation that can reuse one process pool across decisions."""
    observation = env.reset(seed=trace.seed)
    decisions: list[InformationAwareDecisionAnalysis] = []
    for trace_step in trace.steps:
        if observation != trace_step.observation:
            raise ValueError(
                "Trace observation does not match the replayed seeded combat state "
                f"at decision {trace_step.step_index}."
            )
        decision_seed = sampling_seed + trace_step.step_index * 1_000_003
        decision = analyze_information_aware_decision(
            env,
            trace_step.action_index,
            decision_index=trace_step.step_index,
            sample_count=sample_count,
            sampling_seed=decision_seed,
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

    return InformationAwarePolicyAnalysis(
        policy_name=trace.policy_name,
        combat_seed=trace.seed,
        sample_count=sample_count,
        sampling_seed=sampling_seed,
        decisions=tuple(decisions),
    )


def _evaluate_sampled_actions_with_executor(
    sampled_envs: tuple[CombatEnv, ...],
    actions: tuple[CombatAction, ...],
    *,
    max_steps: int,
    max_nodes_per_action: int,
    time_limit_seconds_per_action: float | None,
    executor: Executor,
) -> list[tuple[CombatAction, tuple[OracleActionEvaluation, ...]]]:
    prepared_envs = tuple(
        prepare_env_for_oracle_process(sampled_env) for sampled_env in sampled_envs
    )
    tasks = (
        OracleSearchTask(
            env=sampled_env,
            action=action,
            max_steps=max_steps,
            max_nodes=max_nodes_per_action,
            time_limit_seconds=time_limit_seconds_per_action,
        )
        for action in actions
        for sampled_env in prepared_envs
    )
    flat_results = iter(executor.map(run_oracle_search_task, tasks))
    return [
        (
            action,
            tuple(next(flat_results) for _sampled_env in prepared_envs),
        )
        for action in actions
    ]


def _aggregate_action_evaluation(
    env: CombatEnv,
    action: CombatAction,
    outcomes: tuple[OracleActionEvaluation, ...],
    *,
    hindsight_best_count: int,
    jointly_resolved_count: int,
) -> InformationAwareActionEvaluation:
    terminal_outcomes = tuple(outcome for outcome in outcomes if outcome.score is not None)
    terminal_count = len(terminal_outcomes)
    wins = sum(
        1
        for outcome in terminal_outcomes
        if outcome.summary is not None and outcome.summary["winner"] == "player"
    )
    win_rate = None if terminal_count == 0 else wins / terminal_count
    interval = _wilson_interval(wins, terminal_count)

    def mean_summary(key: str) -> float | None:
        values = [
            float(outcome.summary[key])
            for outcome in terminal_outcomes
            if outcome.summary is not None
        ]
        return None if not values else sum(values) / len(values)

    action_counts = [
        outcome.actions_to_terminal
        for outcome in terminal_outcomes
        if outcome.actions_to_terminal is not None
    ]
    action_index = env.encode_action(action)
    return InformationAwareActionEvaluation(
        action_index=action_index,
        action=action,
        sample_count=len(outcomes),
        terminal_sample_count=terminal_count,
        proven_sample_count=sum(outcome.proven_optimal for outcome in outcomes),
        win_count=wins,
        win_rate=win_rate,
        win_rate_95_low=None if interval is None else interval[0],
        win_rate_95_high=None if interval is None else interval[1],
        mean_player_hp=mean_summary("player_hp"),
        mean_enemy_hp=mean_summary("enemy_hp"),
        mean_actions_to_terminal=(
            None if not action_counts else sum(action_counts) / len(action_counts)
        ),
        mean_environment_reward=mean_summary("total_reward"),
        hindsight_best_sample_count=hindsight_best_count,
        hindsight_best_rate=(
            None
            if jointly_resolved_count == 0
            else hindsight_best_count / jointly_resolved_count
        ),
        _sample_scores=tuple(outcome.score for outcome in outcomes),
    )


def _calculate_expected_regret(
    best: InformationAwareActionEvaluation | None,
    selected: InformationAwareActionEvaluation,
) -> tuple[str, float | None, float | None, float | None, float | None, float | None]:
    if best is None or selected.aggregate_score is None:
        return ("unknown", None, None, None, None, None)
    assert best.win_rate is not None and selected.win_rate is not None
    assert best.mean_player_hp is not None and selected.mean_player_hp is not None
    assert best.mean_enemy_hp is not None and selected.mean_enemy_hp is not None
    assert best.mean_actions_to_terminal is not None
    assert selected.mean_actions_to_terminal is not None
    assert best.mean_environment_reward is not None
    assert selected.mean_environment_reward is not None
    regrets = (
        best.win_rate - selected.win_rate,
        best.mean_player_hp - selected.mean_player_hp,
        selected.mean_enemy_hp - best.mean_enemy_hp,
        selected.mean_actions_to_terminal - best.mean_actions_to_terminal,
        best.mean_environment_reward - selected.mean_environment_reward,
    )
    if regrets[0] != 0.0:
        dimension = "win_rate"
    elif regrets[1] != 0.0:
        dimension = "mean_player_hp"
    elif regrets[2] != 0.0:
        dimension = "mean_enemy_hp"
    elif regrets[3] != 0.0:
        dimension = "mean_actions"
    else:
        dimension = "none"
    return (dimension, *regrets)


def _wilson_interval(successes: int, trials: int) -> tuple[float, float] | None:
    if trials == 0:
        return None
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    margin = (
        z
        * sqrt(proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials**2))
        / denominator
    )
    return (max(0.0, center - margin), min(1.0, center + margin))
