"""Find an optimal seeded combat line and optionally compare a trained agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from game.simulation.core import CombatEnv
from game.simulation.env_factory import CombatEnvFactory, SUPPORTED_ENCOUNTERS
from game.analysis.bruteforce import BruteForceProgress, brute_force_combat
from game.agents.agent_io import load_agent
from game.analysis.render import describe_action
from game.analysis.oracle import (
    OracleDecisionAnalysis,
    OraclePolicyAnalysis,
    analyze_episode_trace_with_oracle,
)
from game.analysis.uncertainty import (
    InformationAwareDecisionAnalysis,
    InformationAwarePolicyAnalysis,
    analyze_episode_trace_with_uncertainty,
)
from game.analysis.watch import (
    policy_from_agent,
    policy_name_from_agent,
    trace_policy_episode,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for one seeded oracle search."""
    parser = argparse.ArgumentParser(
        description=(
            "Brute-force one seeded combat, optimizing victory, remaining HP, "
            "remaining enemy HP, and action count in that order."
        )
    )
    parser.add_argument(
        "--encounter",
        choices=SUPPORTED_ENCOUNTERS,
        default="simple",
        help=(
            "Fixed encounter to solve. overgrowth_easy samples from its pool using "
            "the combat seed."
        ),
    )
    parser.add_argument("--seed", type=int, default=7, help="Exact combat seed to solve.")
    parser.add_argument(
        "--enemy-hp",
        type=int,
        default=40,
        help="Enemy HP when --encounter simple is selected.",
    )
    parser.add_argument("--player-hp", type=int, default=80, help="Player max HP.")
    parser.add_argument(
        "--cards-per-turn",
        type=int,
        default=5,
        help="Cards drawn at the start of each player turn.",
    )
    parser.add_argument(
        "--hp-loss-penalty-scale",
        type=float,
        default=1.0,
        help="Environment HP-loss reward penalty used in reported reward totals.",
    )
    parser.add_argument(
        "--incoming-damage-shaping-scale",
        type=float,
        default=0.0,
        help="Environment incoming-damage shaping used in reported reward totals.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=40,
        help="Maximum player decisions in a candidate line.",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=250_000,
        help="Maximum unique search nodes to expand.",
    )
    parser.add_argument(
        "--time-limit-seconds",
        type=float,
        default=None,
        help="Optional wall-clock search limit. Omit to use only node/step limits.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10_000,
        help="Expanded nodes between progress messages.",
    )
    parser.add_argument(
        "--agent-path",
        type=str,
        default=None,
        help="Optional saved RL checkpoint or run directory to compare on the same seed.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Torch device override when loading a neural checkpoint.",
    )
    parser.add_argument(
        "--oracle-regret",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Analyze every agent decision against all legal oracle continuations. "
            "Use --no-oracle-regret for outcome-only comparison."
        ),
    )
    parser.add_argument(
        "--regret-max-steps",
        type=int,
        default=40,
        help="Maximum decisions searched including each candidate agent action.",
    )
    parser.add_argument(
        "--regret-max-nodes-per-action",
        type=int,
        default=25_000,
        help="Maximum oracle nodes expanded for each legal action at each decision.",
    )
    parser.add_argument(
        "--regret-time-limit-per-action",
        type=float,
        default=None,
        help="Optional wall-clock limit for each legal-action continuation search.",
    )
    parser.add_argument(
        "--max-regret-findings",
        type=int,
        default=10,
        help="Maximum ranked policy weak points printed to the terminal.",
    )
    parser.add_argument(
        "--search-workers",
        type=int,
        default=1,
        help=(
            "Processes used for independent saved-agent regret continuations. "
            "The primary exact search keeps one shared frontier."
        ),
    )
    parser.add_argument(
        "--information-aware-regret",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Also compare agent decisions across sampled hidden draw orders and "
            "future RNG streams. This is more expensive and is disabled by default."
        ),
    )
    parser.add_argument(
        "--information-samples",
        type=int,
        default=8,
        help="Hidden-state samples per decision for information-aware regret.",
    )
    parser.add_argument(
        "--information-seed",
        type=int,
        default=1_729,
        help="Independent seed used to sample hidden states reproducibly.",
    )
    parser.add_argument(
        "--information-max-steps",
        type=int,
        default=20,
        help="Maximum decisions in each sampled action continuation.",
    )
    parser.add_argument(
        "--information-max-nodes-per-action",
        type=int,
        default=2_500,
        help="Maximum nodes for each action in each hidden-state sample.",
    )
    parser.add_argument(
        "--information-time-limit-per-action",
        type=float,
        default=None,
        help="Optional time limit for each sampled action continuation.",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional path for the oracle result and agent comparison JSON.",
    )
    return parser.parse_args(argv)


def make_env(args: argparse.Namespace) -> CombatEnv:
    """Create the requested fixed or seed-sampled combat environment."""
    return CombatEnvFactory(
        encounter_set=args.encounter,
        enemy_hp=args.enemy_hp,
        player_hp=args.player_hp,
        cards_per_turn=args.cards_per_turn,
        hp_loss_penalty_scale=args.hp_loss_penalty_scale,
        incoming_damage_shaping_scale=args.incoming_damage_shaping_scale,
        record_trajectory=False,
    )()


def print_progress(progress: BruteForceProgress) -> None:
    """Print one compact progress update."""
    best_fragment = "none"
    if progress.best_player_hp is not None:
        best_fragment = f"hp={progress.best_player_hp} steps={progress.best_steps}"
    print(
        "[oracle] "
        f"expanded={progress.expanded_nodes} "
        f"generated={progress.generated_nodes} "
        f"unique={progress.unique_states} "
        f"frontier={progress.frontier_size} "
        f"elapsed={progress.elapsed_seconds:.1f}s "
        f"best={best_fragment}",
        flush=True,
    )


def print_oracle_result(result: object, encounter: str, seed: int) -> None:
    """Print the best line and its proof status."""
    from game.analysis.bruteforce import BruteForceResult

    assert isinstance(result, BruteForceResult)
    print(
        "Oracle search: "
        f"encounter={encounter} seed={seed} "
        f"proven_optimal={result.proven_optimal} "
        f"reason={result.termination_reason} "
        f"expanded={result.expanded_nodes} "
        f"unique={result.unique_states} "
        f"elapsed={result.elapsed_seconds:.2f}s"
    )
    if result.summary is None:
        print("No terminal combat line was found within the configured limits.")
        return

    summary = result.summary
    print(
        "Best result: "
        f"winner={summary['winner']} "
        f"player_hp={summary['player_hp']} "
        f"enemy_hp={summary['enemy_hp']} "
        f"steps={summary['steps']} "
        f"turn={summary['final_turn']} "
        f"total_reward={summary['total_reward']:.3f}"
    )
    for step in result.steps:
        print(
            f"  {step.step_index:02d} turn={step.turn} "
            f"action={step.action_index}:"
            f"{describe_action(step.action, step.observation)} "
            f"reward={step.reward:.3f}"
        )


def _comparison_payload(oracle_result: object, agent_trace: object) -> dict[str, object]:
    from game.analysis.bruteforce import BruteForceResult
    from game.analysis.watch import EpisodeTrace

    assert isinstance(oracle_result, BruteForceResult)
    assert isinstance(agent_trace, EpisodeTrace)
    oracle_summary = oracle_result.summary
    agent_summary = agent_trace.summary
    oracle_actions = oracle_result.action_indices
    agent_actions = tuple(step.action_index for step in agent_trace.steps)
    common_prefix = 0
    for oracle_action, agent_action in zip(oracle_actions, agent_actions):
        if oracle_action != agent_action:
            break
        common_prefix += 1

    metrics: dict[str, object] = {
        "matching_selected_oracle_prefix_steps": common_prefix,
        "same_outcome": (
            oracle_summary is not None
            and oracle_summary["winner"] == agent_summary["winner"]
            and oracle_summary["player_hp"] == agent_summary["player_hp"]
            and oracle_summary["steps"] == agent_summary["steps"]
        ),
    }
    if oracle_summary is not None:
        metrics.update(
            {
                "player_hp_gap": oracle_summary["player_hp"] - agent_summary["player_hp"],
                "step_gap": agent_summary["steps"] - oracle_summary["steps"],
                "environment_reward_gap": (
                    oracle_summary["total_reward"] - agent_summary["total_reward"]
                ),
            }
        )
    return metrics


def print_regret_progress(decision: OracleDecisionAnalysis) -> None:
    """Print one compact update after analyzing an agent decision."""
    if decision.selected_is_optimal is True:
        status = "optimal"
    elif decision.selected_is_optimal is False:
        status = f"diverged:{decision.decisive_dimension}"
    elif decision.selected_matches_best_found is False:
        status = f"unproven_divergence:{decision.decisive_dimension}"
    else:
        status = "unproven"
    print(
        "[regret] "
        f"decision={decision.decision_index} "
        f"turn={decision.turn} "
        f"legal_actions={len(decision.action_evaluations)} "
        f"status={status}",
        flush=True,
    )


def print_oracle_regret_analysis(
    analysis: OraclePolicyAnalysis,
    *,
    max_findings: int,
) -> None:
    """Print the first divergence and highest-impact policy weak points."""
    if max_findings < 0:
        raise ValueError("max_findings cannot be negative.")
    first_divergence = next(iter(analysis.proven_divergences), None)
    print(
        "Oracle regret summary: "
        f"decisions={len(analysis.decisions)} "
        f"proven_divergences={len(analysis.proven_divergences)} "
        f"uncertain_decisions={len(analysis.uncertain_decisions)} "
        "first_proven_divergence="
        f"{('none' if first_divergence is None else first_divergence.decision_index)}"
    )

    findings = analysis.ranked_weak_points[:max_findings]
    for rank, decision in enumerate(findings, start=1):
        proof_label = "PROVEN" if decision.comparison_proven else "BEST-FOUND"
        best_descriptions = [
            describe_action(evaluation.action, decision.observation)
            for evaluation in decision.action_evaluations
            if evaluation.action_index in decision.best_found_action_indices
        ]
        print(
            f"  Weak point #{rank}: decision={decision.decision_index} "
            f"turn={decision.turn} confidence={proof_label} "
            f"decisive_dimension={decision.decisive_dimension}"
        )
        print(
            "    Selected: "
            f"{describe_action(decision.selected_action, decision.observation)}"
        )
        print(f"    Best action(s): {', '.join(best_descriptions)}")
        print(
            "    Regret: "
            f"winner={decision.winner_regret} "
            f"player_hp={decision.player_hp_regret} "
            f"enemy_hp={decision.enemy_hp_regret} "
            f"actions={decision.action_count_regret} "
            f"environment_reward={decision.environment_reward_regret}"
        )
        for evaluation in decision.action_evaluations:
            markers: list[str] = []
            if evaluation.action_index == decision.selected_action_index:
                markers.append("selected")
            if evaluation.action_index in decision.best_found_action_indices:
                markers.append("best")
            marker = f" ({','.join(markers)})" if markers else ""
            if evaluation.summary is None:
                outcome = "no terminal line found"
            else:
                outcome = (
                    f"winner={evaluation.summary['winner']} "
                    f"hp={evaluation.summary['player_hp']} "
                    f"enemy_hp={evaluation.summary['enemy_hp']} "
                    f"actions={evaluation.actions_to_terminal}"
                )
            print(
                f"      [{evaluation.action_index}] "
                f"{describe_action(evaluation.action, decision.observation)}{marker}: "
                f"{outcome} proven={evaluation.proven_optimal}"
            )


def print_information_progress(decision: InformationAwareDecisionAnalysis) -> None:
    """Print one compact update after a sampled information-set decision."""
    if decision.selected_matches_best is True:
        status = "sampled_best"
    elif decision.selected_matches_best is False:
        status = f"sampled_divergence:{decision.decisive_dimension}"
    else:
        status = "unresolved"
    print(
        "[information-aware] "
        f"decision={decision.decision_index} "
        f"turn={decision.turn} "
        f"samples={decision.sample_count} "
        f"legal_actions={len(decision.action_evaluations)} "
        f"status={status}",
        flush=True,
    )


def print_information_aware_analysis(
    analysis: InformationAwarePolicyAnalysis,
    *,
    max_findings: int,
) -> None:
    """Print sampled weak points based on information available to the agent."""
    if max_findings < 0:
        raise ValueError("max_findings cannot be negative.")
    print(
        "Information-aware regret summary: "
        f"decisions={len(analysis.decisions)} "
        f"samples_per_decision={analysis.sample_count} "
        f"sampled_divergences={len(analysis.sampled_divergences)} "
        f"unresolved_decisions={len(analysis.unresolved_decisions)}"
    )
    print(
        "  Monte Carlo estimate: current actions share hidden-state samples; "
        "continuations are hindsight-optimal within each sample."
    )
    for rank, decision in enumerate(
        analysis.ranked_weak_points[:max_findings], start=1
    ):
        best_descriptions = [
            describe_action(evaluation.action, decision.observation)
            for evaluation in decision.action_evaluations
            if evaluation.action_index in decision.best_action_indices
        ]
        print(
            f"  Sampled weak point #{rank}: decision={decision.decision_index} "
            f"turn={decision.turn} decisive_dimension={decision.decisive_dimension}"
        )
        print(
            "    Selected: "
            f"{describe_action(decision.selected_action, decision.observation)}"
        )
        print(f"    Best sampled action(s): {', '.join(best_descriptions)}")
        print(
            "    Expected regret: "
            f"win_rate={decision.win_rate_regret} "
            f"player_hp={decision.mean_player_hp_regret} "
            f"enemy_hp={decision.mean_enemy_hp_regret} "
            f"actions={decision.mean_action_count_regret} "
            f"environment_reward={decision.mean_environment_reward_regret}"
        )
        for evaluation in decision.action_evaluations:
            markers: list[str] = []
            if evaluation.action_index == decision.selected_action_index:
                markers.append("selected")
            if evaluation.action_index in decision.best_action_indices:
                markers.append("best")
            marker = f" ({','.join(markers)})" if markers else ""
            win_rate = (
                "n/a" if evaluation.win_rate is None else f"{evaluation.win_rate:.1%}"
            )
            win_interval = (
                "n/a"
                if evaluation.win_rate_95_low is None
                or evaluation.win_rate_95_high is None
                else (
                    f"{evaluation.win_rate_95_low:.1%}-"
                    f"{evaluation.win_rate_95_high:.1%}"
                )
            )
            hp = (
                "n/a"
                if evaluation.mean_player_hp is None
                else f"{evaluation.mean_player_hp:.2f}"
            )
            best_rate = (
                "n/a"
                if evaluation.hindsight_best_rate is None
                else f"{evaluation.hindsight_best_rate:.1%}"
            )
            print(
                f"      [{evaluation.action_index}] "
                f"{describe_action(evaluation.action, decision.observation)}{marker}: "
                f"win_rate={win_rate} win_rate_95={win_interval} mean_hp={hp} "
                f"hindsight_best={best_rate} "
                f"resolved={evaluation.terminal_sample_count}/{evaluation.sample_count}"
            )


def main() -> None:
    """Run one oracle search and optional learned-policy comparison."""
    args = parse_args()
    env = make_env(args)
    env.reset(seed=args.seed)
    result = brute_force_combat(
        env,
        max_steps=args.max_steps,
        max_nodes=args.max_nodes,
        time_limit_seconds=args.time_limit_seconds,
        progress_callback=print_progress,
        progress_interval=args.progress_interval,
    )
    print_oracle_result(result, args.encounter, args.seed)

    output_payload: dict[str, object] = {
        "encounter": args.encounter,
        "seed": args.seed,
        "search_workers": args.search_workers,
        "oracle": result.as_dict(),
    }
    if args.agent_path is not None:
        agent = load_agent(args.agent_path, device=args.device)
        policy_name = policy_name_from_agent(agent)
        agent_trace = trace_policy_episode(
            env=make_env(args),
            policy=policy_from_agent(agent),
            policy_name=policy_name,
            seed=args.seed,
            traced_agent=agent,
            encounter=args.encounter,
        )
        metrics = _comparison_payload(result, agent_trace)
        summary = agent_trace.summary
        print(
            "Agent result: "
            f"policy={policy_name} "
            f"winner={summary['winner']} "
            f"player_hp={summary['player_hp']} "
            f"steps={summary['steps']} "
            f"total_reward={summary['total_reward']:.3f}"
        )
        print(
            "Comparison: "
            f"hp_gap={metrics.get('player_hp_gap', 'n/a')} "
            f"step_gap={metrics.get('step_gap', 'n/a')} "
            f"reward_gap={metrics.get('environment_reward_gap', 'n/a')} "
            "matching_selected_oracle_prefix="
            f"{metrics['matching_selected_oracle_prefix_steps']}"
        )
        output_payload["agent_trace"] = agent_trace.as_dict()
        output_payload["comparison"] = metrics
        if args.oracle_regret:
            regret_analysis = analyze_episode_trace_with_oracle(
                env=make_env(args),
                trace=agent_trace,
                max_steps=args.regret_max_steps,
                max_nodes_per_action=args.regret_max_nodes_per_action,
                time_limit_seconds_per_action=args.regret_time_limit_per_action,
                search_workers=args.search_workers,
                decision_callback=print_regret_progress,
            )
            print_oracle_regret_analysis(
                regret_analysis,
                max_findings=args.max_regret_findings,
            )
            output_payload["oracle_regret"] = regret_analysis.as_dict()
        if args.information_aware_regret:
            information_analysis = analyze_episode_trace_with_uncertainty(
                env=make_env(args),
                trace=agent_trace,
                sample_count=args.information_samples,
                sampling_seed=args.information_seed,
                max_steps=args.information_max_steps,
                max_nodes_per_action=args.information_max_nodes_per_action,
                time_limit_seconds_per_action=(
                    args.information_time_limit_per_action
                ),
                search_workers=args.search_workers,
                decision_callback=print_information_progress,
            )
            print_information_aware_analysis(
                information_analysis,
                max_findings=args.max_regret_findings,
            )
            output_payload["information_aware_regret"] = (
                information_analysis.as_dict()
            )

    if args.json_out is not None:
        output_path = Path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
        print(f"Saved oracle result to {args.json_out}")


if __name__ == "__main__":
    main()
