"""Compare built-in and saved policies over identical fixed combat seeds."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Sequence

from game.agents.agent_io import load_agent
from game.agents.baselines import QLearningAgent
from game.analysis.benchmark import (
    BenchmarkEnvironmentConfig,
    BenchmarkPolicyMetadata,
    BenchmarkReport,
    ResolvedBenchmarkPolicy,
    format_benchmark_table,
    run_fixed_seed_benchmark,
)
from game.analysis.watch import (
    TraceableAgent,
    policy_from_agent,
    policy_from_named_policy,
    policy_name_from_agent,
)
from game.simulation import env_factory as env_factory_module
from game.simulation.env_factory import CombatEnvFactory

_POLICY_LABEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}\Z")
_RESERVED_POLICY_LABELS = frozenset({"random", "heuristic"})


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """One user-supplied benchmark label and checkpoint path."""

    label: str
    path: str


def supported_fixed_encounters() -> tuple[str, ...]:
    """Return the fixed registry, with a fallback for the pre-registry codebase."""
    fixed_registry = getattr(
        env_factory_module,
        "SUPPORTED_FIXED_ENCOUNTERS",
        None,
    )
    if fixed_registry is not None:
        return tuple(str(encounter) for encounter in fixed_registry)
    return tuple(
        encounter
        for encounter in env_factory_module.SUPPORTED_ENCOUNTERS
        if encounter != "overgrowth_easy"
    )


def parse_agent_spec(value: str) -> AgentSpec:
    """Parse LABEL=PATH while allowing equals signs inside the path."""
    if "=" not in value:
        raise argparse.ArgumentTypeError("agent must use LABEL=PATH syntax.")
    label, path = value.split("=", maxsplit=1)
    if not _POLICY_LABEL_PATTERN.fullmatch(label):
        raise argparse.ArgumentTypeError(
            "agent label must match [A-Za-z0-9][A-Za-z0-9_.-]{0,31}."
        )
    if label in _RESERVED_POLICY_LABELS:
        raise argparse.ArgumentTypeError(
            f"agent label {label!r} is reserved for a built-in policy."
        )
    if not path:
        raise argparse.ArgumentTypeError("agent checkpoint path cannot be empty.")
    return AgentSpec(label=label, path=path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse and validate fixed-seed benchmark arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Compare random, heuristic, and saved agents over identical fixed "
            "encounters and combat seeds."
        )
    )
    parser.add_argument(
        "--encounter",
        action="append",
        choices=supported_fixed_encounters(),
        required=True,
        help="Fixed encounter to benchmark. Repeat for multiple encounters.",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=100,
        help="Evaluation episodes per policy/encounter cell.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="First seed in the contiguous episode-seed sequence.",
    )
    parser.add_argument(
        "--agent",
        action="append",
        type=parse_agent_spec,
        default=[],
        metavar="LABEL=PATH",
        help="Labeled checkpoint file or run directory. Repeat for multiple agents.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Optional Torch device override used while loading neural checkpoints.",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional path for the versioned JSON benchmark report.",
    )
    parser.add_argument(
        "--enemy-hp",
        type=int,
        default=40,
        help="Enemy HP when benchmarking the simple encounter.",
    )
    parser.add_argument(
        "--player-hp",
        type=int,
        default=80,
        help="Player maximum HP shared by every benchmark cell.",
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
        help="Scale for the per-step player HP-loss reward penalty.",
    )
    parser.add_argument(
        "--incoming-damage-shaping-scale",
        type=float,
        default=0.0,
        help="Scale for reducing projected incoming-damage reward shaping.",
    )
    args = parser.parse_args(argv)

    if args.episodes <= 0:
        parser.error("--episodes must be positive.")
    if args.enemy_hp <= 0:
        parser.error("--enemy-hp must be positive.")
    if args.player_hp <= 0:
        parser.error("--player-hp must be positive.")
    if args.cards_per_turn <= 0:
        parser.error("--cards-per-turn must be positive.")
    if len(set(args.encounter)) != len(args.encounter):
        parser.error("--encounter values must be unique.")
    agent_labels = [agent_spec.label for agent_spec in args.agent]
    if len(set(agent_labels)) != len(agent_labels):
        parser.error("--agent labels must be unique.")
    return args


def environment_config_from_args(
    args: argparse.Namespace,
) -> BenchmarkEnvironmentConfig:
    """Resolve the environment settings recorded in the report."""
    return BenchmarkEnvironmentConfig(
        enemy_hp=args.enemy_hp,
        player_hp=args.player_hp,
        cards_per_turn=args.cards_per_turn,
        hp_loss_penalty_scale=args.hp_loss_penalty_scale,
        incoming_damage_shaping_scale=args.incoming_damage_shaping_scale,
    )


def make_environment_factories(
    args: argparse.Namespace,
) -> tuple[tuple[str, CombatEnvFactory], ...]:
    """Create one reproducible environment factory for every encounter."""
    return tuple(
        (
            encounter,
            CombatEnvFactory(
                encounter_set=encounter,
                enemy_hp=args.enemy_hp,
                player_hp=args.player_hp,
                cards_per_turn=args.cards_per_turn,
                hp_loss_penalty_scale=args.hp_loss_penalty_scale,
                incoming_damage_shaping_scale=args.incoming_damage_shaping_scale,
                record_trajectory=False,
            ),
        )
        for encounter in args.encounter
    )


def load_benchmark_policies(args: argparse.Namespace) -> tuple[ResolvedBenchmarkPolicy, ...]:
    """Resolve built-ins and labeled checkpoints into shared policy adapters."""
    policies = [
        ResolvedBenchmarkPolicy(
            metadata=BenchmarkPolicyMetadata(
                label=policy_name,
                source_kind="built_in",
                policy_type=policy_name,
            ),
            policy=policy_from_named_policy(policy_name),
        )
        for policy_name in ("random", "heuristic")
    ]
    for agent_spec in args.agent:
        try:
            agent = load_agent(agent_spec.path, device=args.device)
        except (OSError, ValueError, TypeError, ModuleNotFoundError, RuntimeError) as exc:
            raise ValueError(
                f"Could not load policy {agent_spec.label!r} from "
                f"{agent_spec.path!r}: {exc}"
            ) from exc
        policy_type = policy_name_from_agent(agent)
        policies.append(
            ResolvedBenchmarkPolicy(
                metadata=BenchmarkPolicyMetadata(
                    label=agent_spec.label,
                    source_kind="checkpoint",
                    policy_type=policy_type,
                    agent_path=agent_spec.path,
                ),
                policy=policy_from_agent(agent),
                agent=agent,
            )
        )
    return tuple(policies)


def validate_agent_compatibility(
    policies: Sequence[ResolvedBenchmarkPolicy],
    environment_factories: Sequence[tuple[str, CombatEnvFactory]],
) -> None:
    """Fail before evaluation when a checkpoint cannot consume an environment."""
    errors: list[str] = []
    for resolved_policy in policies:
        agent = resolved_policy.agent
        if agent is None:
            continue
        for encounter, env_factory in environment_factories:
            env = env_factory()
            policy_description = (
                f"policy {resolved_policy.metadata.label!r} "
                f"({resolved_policy.metadata.policy_type}) on encounter {encounter!r}"
            )
            if agent.action_space_size != env.action_space_size:
                errors.append(
                    f"{policy_description}: checkpoint action_space_size="
                    f"{agent.action_space_size}, environment action_space_size="
                    f"{env.action_space_size}"
                )
                continue

            observation_size = getattr(agent, "observation_size", None)
            if (
                observation_size is not None
                and int(observation_size) != env.observation_size
            ):
                errors.append(
                    f"{policy_description}: checkpoint observation_size="
                    f"{observation_size}, environment observation_size="
                    f"{env.observation_size}"
                )

            action_feature_size = getattr(agent, "action_feature_size", None)
            if (
                action_feature_size is not None
                and int(action_feature_size) != env.action_feature_size
            ):
                errors.append(
                    f"{policy_description}: checkpoint action_feature_size="
                    f"{action_feature_size}, environment action_feature_size="
                    f"{env.action_feature_size}"
                )

            if isinstance(agent, QLearningAgent) and agent.q_table:
                state_widths = {len(state) for state in agent.q_table}
                if state_widths != {env.observation_size}:
                    errors.append(
                        f"{policy_description}: checkpoint Q-table state widths="
                        f"{sorted(state_widths)}, environment observation_size="
                        f"{env.observation_size}"
                    )

    if errors:
        raise ValueError("Incompatible checkpoint(s):\n  " + "\n  ".join(errors))


def run_benchmark_command(args: argparse.Namespace) -> BenchmarkReport:
    """Load, preflight, and evaluate one benchmark invocation."""
    environment_factories = make_environment_factories(args)
    policies = load_benchmark_policies(args)
    validate_agent_compatibility(policies, environment_factories)
    return run_fixed_seed_benchmark(
        environment_factories=environment_factories,
        policies=policies,
        episodes=args.episodes,
        base_seed=args.seed,
        environment=environment_config_from_args(args),
        device=args.device,
    )


def main(argv: Sequence[str] | None = None) -> None:
    """Run the fixed-seed policy benchmark."""
    args = parse_args(argv)
    try:
        report = run_benchmark_command(args)
    except (OSError, ValueError, TypeError, ModuleNotFoundError, RuntimeError) as exc:
        raise SystemExit(f"Benchmark failed: {exc}") from exc

    print(format_benchmark_table(report))
    if args.json_out is not None:
        output_path = report.write_json(Path(args.json_out))
        print(f"Saved benchmark report to {output_path}")


if __name__ == "__main__":
    main()
