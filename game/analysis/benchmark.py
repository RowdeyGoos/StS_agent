"""Deterministic fixed-seed policy benchmark reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from ..agents.baselines import PolicyFn, evaluate_policy
from ..simulation.core import CombatEnv
from .watch import TraceableAgent

BENCHMARK_FORMAT_VERSION = 2
PolicySourceKind = Literal["built_in", "checkpoint"]
EnvironmentFactory = Callable[[], CombatEnv]


@dataclass(frozen=True, slots=True)
class BenchmarkEnvironmentConfig:
    """Serializable combat settings shared by every benchmark cell."""

    enemy_hp: int = 40
    player_hp: int = 80
    cards_per_turn: int = 5
    hp_loss_penalty_scale: float = 1.0
    incoming_damage_shaping_scale: float = 0.0
    deck: str = "starter"

    def as_dict(self) -> dict[str, int | float | str]:
        return {
            "deck": self.deck,
            "enemy_hp": self.enemy_hp,
            "player_hp": self.player_hp,
            "cards_per_turn": self.cards_per_turn,
            "hp_loss_penalty_scale": self.hp_loss_penalty_scale,
            "incoming_damage_shaping_scale": self.incoming_damage_shaping_scale,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkPolicyMetadata:
    """Stable identity and provenance for one compared policy."""

    label: str
    source_kind: PolicySourceKind
    policy_type: str
    agent_path: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "label": self.label,
            "source_kind": self.source_kind,
            "policy_type": self.policy_type,
            "agent_path": self.agent_path,
        }


@dataclass(frozen=True, slots=True)
class ResolvedBenchmarkPolicy:
    """Policy metadata plus its executable adapter and optional trained agent."""

    metadata: BenchmarkPolicyMetadata
    policy: PolicyFn = field(repr=False, compare=False)
    agent: TraceableAgent | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class BenchmarkCaseResult:
    """Evaluation metrics for one policy on one fixed encounter."""

    encounter: str
    policy_label: str
    policy_type: str
    metrics: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "encounter": self.encounter,
            "policy_label": self.policy_label,
            "policy_type": self.policy_type,
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Versioned result of a fixed-seed multi-policy benchmark."""

    encounters: tuple[str, ...]
    episodes_per_case: int
    base_seed: int
    environment: BenchmarkEnvironmentConfig
    device: str | None
    policies: tuple[BenchmarkPolicyMetadata, ...]
    results: tuple[BenchmarkCaseResult, ...]

    @property
    def episode_seeds(self) -> tuple[int, ...]:
        """Return the exact combat seeds used in every benchmark cell."""
        return tuple(
            self.base_seed + episode_index
            for episode_index in range(self.episodes_per_case)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
            "config": {
                "encounters": list(self.encounters),
                "episodes_per_case": self.episodes_per_case,
                "base_seed": self.base_seed,
                "episode_seeds": list(self.episode_seeds),
                "environment": self.environment.as_dict(),
                "device": self.device,
            },
            "policies": [policy.as_dict() for policy in self.policies],
            "results": [result.as_dict() for result in self.results],
        }

    def write_json(self, path: str | Path) -> Path:
        """Write deterministic, human-readable benchmark JSON."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.as_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        return output_path


def run_fixed_seed_benchmark(
    *,
    environment_factories: Sequence[tuple[str, EnvironmentFactory]],
    policies: Sequence[ResolvedBenchmarkPolicy],
    episodes: int,
    base_seed: int,
    environment: BenchmarkEnvironmentConfig,
    device: str | None = None,
) -> BenchmarkReport:
    """Evaluate every policy/encounter cell over one identical seed sequence."""
    if episodes <= 0:
        raise ValueError("episodes must be positive.")
    if not environment_factories:
        raise ValueError("At least one encounter is required.")
    if not policies:
        raise ValueError("At least one policy is required.")

    results: list[BenchmarkCaseResult] = []
    for encounter, env_factory in environment_factories:
        for resolved_policy in policies:
            if resolved_policy.agent is not None:
                # Saved Q-learning and DQN agents break exact ties with their own
                # RNG even in evaluation mode. Resetting once per cell prevents
                # encounter ordering from changing benchmark outcomes.
                resolved_policy.agent.rng.seed(base_seed)
            stats = evaluate_policy(
                env_factory=env_factory,
                policy=resolved_policy.policy,
                episodes=episodes,
                seed=base_seed,
            )
            results.append(
                BenchmarkCaseResult(
                    encounter=encounter,
                    policy_label=resolved_policy.metadata.label,
                    policy_type=resolved_policy.metadata.policy_type,
                    metrics=dict(stats.as_dict()),
                )
            )

    return BenchmarkReport(
        encounters=tuple(encounter for encounter, _factory in environment_factories),
        episodes_per_case=episodes,
        base_seed=base_seed,
        environment=environment,
        device=device,
        policies=tuple(policy.metadata for policy in policies),
        results=tuple(results),
    )


def format_benchmark_table(report: BenchmarkReport) -> str:
    """Render stable headline metrics as a compact plain-text table."""
    headings = (
        "Encounter",
        "Policy",
        "Type",
        "N",
        "Win%",
        "Mean HP",
        "Mean damage",
        "Mean reward",
        "Mean steps",
    )
    rows = [
        (
            result.encounter,
            result.policy_label,
            result.policy_type,
            str(int(result.metrics["episodes"])),
            f"{float(result.metrics['win_rate']) * 100.0:.1f}",
            f"{float(result.metrics['mean_player_hp']):.2f}",
            f"{float(result.metrics.get('mean_damage_taken', 0.0)):.2f}",
            f"{float(result.metrics['mean_reward']):.2f}",
            f"{float(result.metrics['mean_steps']):.2f}",
        )
        for result in report.results
    ]
    widths = tuple(
        max(len(headings[column]), *(len(row[column]) for row in rows))
        for column in range(len(headings))
    )

    def format_row(row: Sequence[str]) -> str:
        fragments = []
        for column, value in enumerate(row):
            if column < 3:
                fragments.append(value.ljust(widths[column]))
            else:
                fragments.append(value.rjust(widths[column]))
        return "  ".join(fragments)

    return "\n".join([format_row(headings), *(format_row(row) for row in rows)])
