"""Run one traced combat episode with a selected policy or saved trained agent."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from game import CombatEnv, SimpleEnemy, build_overgrowth_easy_encounter
from game.agent_io import load_agent
from game.render import describe_action, format_observation
from game.watch import (
    describe_top_action_scores,
    policy_name_from_agent,
    policy_from_agent,
    policy_from_named_policy,
    save_episode_trace,
    trace_policy_episode,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for a one-episode policy trace run."""
    parser = argparse.ArgumentParser(
        description="Run one combat with a policy or saved trained agent and log the trace."
    )
    parser.add_argument(
        "--policy",
        choices=(
            "random",
            "heuristic",
            "q_learning",
            "dqn",
            "double_dqn",
            "dueling_double_dqn",
            "masked_ppo",
        ),
        required=True,
        help="Which policy or trained agent type to run.",
    )
    parser.add_argument(
        "--agent-path",
        type=str,
        default=None,
        help="Path to a saved q_learning, DQN-family, or masked_ppo agent checkpoint.",
    )
    parser.add_argument(
        "--encounter-set",
        choices=("simple", "overgrowth_easy"),
        default="simple",
        help="Encounter pool to trace against.",
    )
    parser.add_argument(
        "--enemy-hp",
        type=int,
        default=40,
        help="Enemy HP for the default simple enemy.",
    )
    parser.add_argument(
        "--player-hp",
        type=int,
        default=80,
        help="Player max HP.",
    )
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
        help="Scale factor applied to the per-step player HP loss penalty.",
    )
    parser.add_argument(
        "--incoming-damage-shaping-scale",
        type=float,
        default=0.0,
        help=(
            "Scale for the immediate reward bonus from reducing projected incoming "
            "enemy damage during the player turn."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Seed for the traced combat episode.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Torch device override for loading DQN-family agents.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Optional JSON file path for writing the full combat trace.",
    )
    parser.add_argument(
        "--show-action-scores",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Print top scored legal actions when the loaded agent supports action scores.",
    )
    parser.add_argument(
        "--top-action-scores",
        type=int,
        default=5,
        help="Number of top legal action scores to print per decision.",
    )
    return parser.parse_args(argv)


def make_env(args: argparse.Namespace) -> CombatEnv:
    """Create a combat environment from watch CLI arguments."""
    if args.encounter_set == "overgrowth_easy":
        return CombatEnv(
            player_max_hp=args.player_hp,
            cards_per_turn=args.cards_per_turn,
            encounter_factory=build_overgrowth_easy_encounter,
            max_enemy_count=3,
            hp_loss_penalty_scale=args.hp_loss_penalty_scale,
            incoming_damage_shaping_scale=args.incoming_damage_shaping_scale,
        )
    return CombatEnv(
        player_max_hp=args.player_hp,
        cards_per_turn=args.cards_per_turn,
        enemy_factory=lambda: SimpleEnemy(max_hp=args.enemy_hp),
        hp_loss_penalty_scale=args.hp_loss_penalty_scale,
        incoming_damage_shaping_scale=args.incoming_damage_shaping_scale,
    )


def print_trace(trace: object, show_action_scores: bool, top_action_scores: int) -> None:
    """Print a human-readable combat trace."""
    from game.watch import EpisodeTrace

    assert isinstance(trace, EpisodeTrace)

    print(f"Policy trace: policy={trace.policy_name} seed={trace.seed}")
    print(format_observation(trace.initial_observation))

    for step in trace.steps:
        print(f"\nAction: {describe_action(step.action, step.observation)}")
        if show_action_scores and step.legal_action_scores is not None:
            top_scores = describe_top_action_scores(
                step.legal_action_scores,
                top_n=top_action_scores,
            )
            if top_scores is not None:
                print(f"  Top legal action scores: {top_scores}")
            if step.selected_action_score is not None:
                print(f"  Selected action score: {step.selected_action_score:.3f}")
        if "played_card" in step.info:
            print(f"  Played: {step.info['played_card']}")
        if "enemy_actions" in step.info:
            for enemy_action in step.info["enemy_actions"]:
                intent = enemy_action["intent"]
                print(
                    "  Enemy turn: "
                    f"enemy[{enemy_action['enemy_index']}] {enemy_action['enemy_name']} -> "
                    f"{intent['move_name']} ({intent['kind']} {intent['value']})"
                )
        print(f"  Reward: {step.reward:.3f}")
        print(f"  Next action mask: {step.info['action_mask']}")
        print(format_observation(step.next_observation))

    winner = trace.summary["winner"]
    print(
        "\nCombat summary: "
        f"winner={winner} "
        f"steps={trace.summary['steps']} "
        f"player_hp={trace.summary['player_hp']} "
        f"enemy_hp={trace.summary['enemy_hp']} "
        f"total_reward={trace.summary['total_reward']:.3f}"
    )


def main() -> None:
    """Run one traced combat episode."""
    args = parse_args()

    trained_policy_names = {
        "q_learning",
        "dqn",
        "double_dqn",
        "dueling_double_dqn",
        "masked_ppo",
    }
    if args.policy in trained_policy_names and args.agent_path is None:
        raise SystemExit(
            "--agent-path is required when tracing q_learning, dqn, double_dqn, dueling_double_dqn, or masked_ppo."
        )
    if args.policy not in trained_policy_names and args.agent_path is not None:
        raise SystemExit(
            "--agent-path is only used for q_learning, dqn, double_dqn, dueling_double_dqn, or masked_ppo."
        )

    env = make_env(args)
    traced_agent = None
    if args.policy in trained_policy_names:
        traced_agent = load_agent(args.agent_path, device=args.device)
        loaded_policy_name = policy_name_from_agent(traced_agent)
        if loaded_policy_name != args.policy:
            raise SystemExit(
                f"Loaded agent type {loaded_policy_name!r} does not match "
                f"requested --policy {args.policy!r}."
            )
        policy = policy_from_agent(traced_agent)
    else:
        policy = policy_from_named_policy(args.policy)

    trace = trace_policy_episode(
        env=env,
        policy=policy,
        policy_name=args.policy,
        seed=args.seed,
        traced_agent=traced_agent,
    )
    print_trace(
        trace,
        show_action_scores=args.show_action_scores,
        top_action_scores=args.top_action_scores,
    )

    if args.log_file is not None:
        save_episode_trace(trace, Path(args.log_file))
        print(f"Saved trace log to {args.log_file}")


if __name__ == "__main__":
    main()
