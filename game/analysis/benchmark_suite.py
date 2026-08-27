"""Resumable full-system benchmark campaign orchestration and reporting."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field, replace
import csv
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter
from typing import Any, Mapping, Sequence

from ..agents.agent_io import load_agent
from ..agents.baselines import (
    EpisodeMetrics,
    QLearningAgent,
    choose_heuristic_action,
    rollout_episode,
)
from ..agents.card_encoder import (
    CARD_EMBEDDING_DIM,
    CARD_ID_EMBEDDING_DIM,
    SharedCardEncoder,
    tensorize_card_zone_records,
)
from ..agents.dqn import DQNAgent, DoubleDQNAgent, DuelingDoubleDQNAgent
from ..agents.ppo import PPOAgent
from ..simulation.card_records import (
    CARD_ID_CAPACITY,
    CARD_RECORD_FORMAT_VERSION,
    card_record_schema_fingerprint,
    extract_card_zone_records,
)
from ..simulation.core import CombatEnv, Observation
from ..simulation.env_factory import CombatEnvFactory
from .watch import policy_from_agent, policy_name_from_agent

SUITE_FORMAT_VERSION = 1
PRIMARY_FIXED_ENCOUNTERS: tuple[str, ...] = (
    "nibbit",
    "slimes",
    "shrinker_beetle",
    "fuzzy_wurm_crawler",
    "mawler",
    "nibbits",
    "shrinker_fuzzy",
)
EASY_FIXED_ENCOUNTERS: frozenset[str] = frozenset(
    {"nibbit", "slimes", "shrinker_beetle", "fuzzy_wurm_crawler"}
)
HARD_FIXED_ENCOUNTERS: frozenset[str] = frozenset(
    {"mawler", "nibbits", "shrinker_fuzzy"}
)
EVALUATION_DECKS: tuple[str, ...] = ("starter", "ironclad_sequencing")
DQN_POLICIES: tuple[str, ...] = ("dqn", "double_dqn", "dueling_double_dqn")
NEURAL_ARCHITECTURES: tuple[str, ...] = ("flat", "action_feature", "shared_enemy")


@dataclass(frozen=True, slots=True)
class PolicyVariant:
    """One algorithm/architecture row in the controlled campaign."""

    label: str
    policy: str
    architecture: str | None = None

    def __post_init__(self) -> None:
        if self.policy == "q_learning":
            if self.architecture is not None:
                raise ValueError("q_learning does not accept an architecture.")
            return
        if self.policy not in {*DQN_POLICIES, "masked_ppo"}:
            raise ValueError(f"Unsupported suite policy: {self.policy!r}")
        if self.architecture not in NEURAL_ARCHITECTURES:
            raise ValueError(
                f"Policy {self.policy!r} requires one of {NEURAL_ARCHITECTURES}."
            )

    @property
    def family(self) -> str:
        if self.policy in DQN_POLICIES:
            return "dqn"
        if self.policy == "masked_ppo":
            return "ppo"
        return "q_learning"


def default_policy_variants() -> tuple[PolicyVariant, ...]:
    """Return all 13 trainable policy variants in stable report order."""
    variants = [PolicyVariant("q_learning", "q_learning")]
    variants.extend(
        PolicyVariant(f"{policy}__{architecture}", policy, architecture)
        for policy in DQN_POLICIES
        for architecture in NEURAL_ARCHITECTURES
    )
    variants.extend(
        PolicyVariant(f"masked_ppo__{architecture}", "masked_ppo", architecture)
        for architecture in NEURAL_ARCHITECTURES
    )
    return tuple(variants)


@dataclass(frozen=True, slots=True)
class BenchmarkSuiteManifest:
    """Resolved, JSON-serializable configuration for one campaign."""

    output_dir: str = "benchmarks/suites/full-system-balanced"
    variants: tuple[PolicyVariant, ...] = field(default_factory=default_policy_variants)
    decks: tuple[str, ...] = EVALUATION_DECKS
    fixed_encounters: tuple[str, ...] = PRIMARY_FIXED_ENCOUNTERS
    screen_transition_budget: int = 32_768
    confirmation_transition_budget: int = 65_536
    time_budget_seconds: float = 900.0
    screen_seed: int = 7
    confirmation_seeds: tuple[int, ...] = (7, 1007, 2007)
    evaluation_episodes: int = 100
    evaluation_base_seed: int = 100_000
    max_parallel_trainings: int = 3
    training_threads: int = 4
    ppo_num_envs: int = 16
    ppo_env_workers: int = 2
    ppo_rollout_steps: int = 2_048
    screen_timeout_seconds: float = 1_800.0
    confirmation_timeout_seconds: float = 2_700.0
    episode_safety_ceiling: int = 10_000_000
    microbenchmark_observations: int = 10_000
    oracle_enabled: bool = True
    oracle_time_limit_seconds: float = 60.0
    historical_roots: tuple[str, ...] = ("runs", "checkpoints")
    common_training_args: Mapping[str, Any] = field(
        default_factory=lambda: {
            "eval_interval": 0,
            "eval_episodes": 1,
            "device": "cpu",
            "restore_best_checkpoint": False,
            "progress_interval": 10_000_000,
            "hp_loss_penalty_scale": 1.0,
            "incoming_damage_shaping_scale": 0.0,
        }
    )
    q_learning_args: Mapping[str, Any] = field(default_factory=dict)
    dqn_args: Mapping[str, Any] = field(default_factory=dict)
    ppo_args: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.variants:
            raise ValueError("A benchmark suite requires at least one trainable variant.")
        labels = [variant.label for variant in self.variants]
        if len(labels) != len(set(labels)):
            raise ValueError("Benchmark-suite variant labels must be unique.")
        if not self.decks or len(self.decks) != len(set(self.decks)):
            raise ValueError("Benchmark-suite decks must be non-empty and unique.")
        if not self.fixed_encounters or len(self.fixed_encounters) != len(
            set(self.fixed_encounters)
        ):
            raise ValueError("Fixed encounters must be non-empty and unique.")
        for name, value in (
            ("screen_transition_budget", self.screen_transition_budget),
            ("confirmation_transition_budget", self.confirmation_transition_budget),
            ("evaluation_episodes", self.evaluation_episodes),
            ("max_parallel_trainings", self.max_parallel_trainings),
            ("training_threads", self.training_threads),
            ("ppo_num_envs", self.ppo_num_envs),
            ("ppo_rollout_steps", self.ppo_rollout_steps),
            ("episode_safety_ceiling", self.episode_safety_ceiling),
            ("microbenchmark_observations", self.microbenchmark_observations),
        ):
            if int(value) <= 0:
                raise ValueError(f"{name} must be positive.")
        if self.time_budget_seconds <= 0.0:
            raise ValueError("time_budget_seconds must be positive.")
        if self.ppo_env_workers < 0 or self.ppo_env_workers > self.ppo_num_envs:
            raise ValueError("ppo_env_workers must be between zero and ppo_num_envs.")
        if self.screen_transition_budget % self.ppo_rollout_steps != 0:
            raise ValueError("The screen transition budget must align with PPO rollouts.")
        if self.confirmation_transition_budget % self.ppo_rollout_steps != 0:
            raise ValueError(
                "The confirmation transition budget must align with PPO rollouts."
            )

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    def as_dict(self) -> dict[str, Any]:
        return {
            "suite_format_version": SUITE_FORMAT_VERSION,
            "output_dir": self.output_dir,
            "variants": [asdict(variant) for variant in self.variants],
            "decks": list(self.decks),
            "fixed_encounters": list(self.fixed_encounters),
            "screen_transition_budget": self.screen_transition_budget,
            "confirmation_transition_budget": self.confirmation_transition_budget,
            "time_budget_seconds": self.time_budget_seconds,
            "screen_seed": self.screen_seed,
            "confirmation_seeds": list(self.confirmation_seeds),
            "evaluation_episodes": self.evaluation_episodes,
            "evaluation_base_seed": self.evaluation_base_seed,
            "max_parallel_trainings": self.max_parallel_trainings,
            "training_threads": self.training_threads,
            "ppo_num_envs": self.ppo_num_envs,
            "ppo_env_workers": self.ppo_env_workers,
            "ppo_rollout_steps": self.ppo_rollout_steps,
            "screen_timeout_seconds": self.screen_timeout_seconds,
            "confirmation_timeout_seconds": self.confirmation_timeout_seconds,
            "episode_safety_ceiling": self.episode_safety_ceiling,
            "microbenchmark_observations": self.microbenchmark_observations,
            "oracle_enabled": self.oracle_enabled,
            "oracle_time_limit_seconds": self.oracle_time_limit_seconds,
            "historical_roots": list(self.historical_roots),
            "common_training_args": dict(self.common_training_args),
            "q_learning_args": dict(self.q_learning_args),
            "dqn_args": dict(self.dqn_args),
            "ppo_args": dict(self.ppo_args),
        }

    def miniature(self, output_dir: str) -> "BenchmarkSuiteManifest":
        """Return a fast deterministic end-to-end smoke configuration."""
        mini_variants = (
            PolicyVariant("q_learning", "q_learning"),
            PolicyVariant("double_dqn__action_feature", "double_dqn", "action_feature"),
            PolicyVariant("masked_ppo__action_feature", "masked_ppo", "action_feature"),
        )
        return replace(
            self,
            output_dir=output_dir,
            variants=mini_variants,
            decks=("starter",),
            fixed_encounters=("nibbit",),
            screen_transition_budget=32,
            confirmation_transition_budget=64,
            time_budget_seconds=0.25,
            confirmation_seeds=(7,),
            evaluation_episodes=2,
            max_parallel_trainings=2,
            training_threads=1,
            ppo_num_envs=1,
            ppo_env_workers=0,
            ppo_rollout_steps=16,
            screen_timeout_seconds=120.0,
            confirmation_timeout_seconds=120.0,
            microbenchmark_observations=16,
            oracle_enabled=False,
        )


def load_suite_manifest(path: str | Path) -> BenchmarkSuiteManifest:
    """Load a strict manifest and reject unknown or mismatched versions."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Benchmark-suite manifest must contain a JSON object.")
    expected_keys = set(BenchmarkSuiteManifest.__dataclass_fields__)
    allowed_keys = expected_keys | {"suite_format_version"}
    unknown = sorted(set(payload) - allowed_keys)
    if unknown:
        raise ValueError(f"Unknown benchmark-suite manifest key(s): {', '.join(unknown)}")
    version = int(payload.pop("suite_format_version", SUITE_FORMAT_VERSION))
    if version != SUITE_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported benchmark-suite format {version}; expected {SUITE_FORMAT_VERSION}."
        )
    if "variants" in payload:
        raw_variants = payload["variants"]
        if not isinstance(raw_variants, list):
            raise ValueError("Manifest variants must be a list.")
        payload["variants"] = tuple(PolicyVariant(**item) for item in raw_variants)
    for tuple_field in (
        "decks",
        "fixed_encounters",
        "confirmation_seeds",
        "historical_roots",
    ):
        if tuple_field in payload:
            payload[tuple_field] = tuple(payload[tuple_field])
    return BenchmarkSuiteManifest(**payload)


@dataclass(frozen=True, slots=True)
class TrainingRunSpec:
    """One independently resumable trainer subprocess."""

    stage: str
    variant: PolicyVariant
    deck: str
    seed: int
    encounter_set: str
    max_environment_steps: int | None
    max_training_seconds: float | None
    timeout_seconds: float

    @property
    def run_id(self) -> str:
        budget_label = (
            f"steps-{self.max_environment_steps}"
            if self.max_environment_steps is not None
            else f"seconds-{self.max_training_seconds:g}"
        )
        return (
            f"{self.stage}__{self.variant.label}__{self.deck}__seed-{self.seed}__"
            f"{budget_label}"
        )


@dataclass(frozen=True, slots=True)
class EvaluationRow:
    """Raw result for one checkpoint, deck, encounter, and combat seed."""

    stage: str
    run_id: str
    variant: str
    policy_type: str
    training_deck: str | None
    evaluation_deck: str
    training_seed: int | None
    encounter: str
    episode_seed: int
    total_reward: float
    steps: int
    win: bool
    player_hp: int
    enemy_hp: int
    damage_taken: int


@dataclass(frozen=True, slots=True)
class VariantScore:
    """Deterministic robust ranking statistics for one variant."""

    variant: str
    macro_win_rate: float
    worst_cell_win_rate: float
    mean_damage_taken: float
    mean_player_hp: float
    mean_reward: float
    episodes: int
    win_rate_interval: tuple[float, float]

    @property
    def ranking_key(self) -> tuple[float, float, float, float, float, str]:
        return (
            -self.macro_win_rate,
            -self.worst_cell_win_rate,
            self.mean_damage_taken,
            -self.mean_player_hp,
            -self.mean_reward,
            self.variant,
        )

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["win_rate_interval"] = list(self.win_rate_interval)
        return payload


def screen_training_specs(manifest: BenchmarkSuiteManifest) -> tuple[TrainingRunSpec, ...]:
    """Return the complete stage-one matrix in deterministic order."""
    return tuple(
        TrainingRunSpec(
            stage="screen",
            variant=variant,
            deck=deck,
            seed=manifest.screen_seed,
            encounter_set="overgrowth_easy",
            max_environment_steps=manifest.screen_transition_budget,
            max_training_seconds=None,
            timeout_seconds=manifest.screen_timeout_seconds,
        )
        for variant in manifest.variants
        for deck in manifest.decks
    )


def confirmation_training_specs(
    manifest: BenchmarkSuiteManifest,
    finalists: Sequence[PolicyVariant],
) -> tuple[TrainingRunSpec, ...]:
    """Return the transition-controlled finalist matrix."""
    return tuple(
        TrainingRunSpec(
            stage="confirmation",
            variant=variant,
            deck=deck,
            seed=seed,
            encounter_set="overgrowth_easy",
            max_environment_steps=manifest.confirmation_transition_budget,
            max_training_seconds=None,
            timeout_seconds=manifest.confirmation_timeout_seconds,
        )
        for variant in finalists
        for deck in manifest.decks
        for seed in manifest.confirmation_seeds
    )


def time_training_specs(
    manifest: BenchmarkSuiteManifest,
    finalists: Sequence[PolicyVariant],
) -> tuple[TrainingRunSpec, ...]:
    """Return isolated equal-wall-time runs for the confirmed variants."""
    return tuple(
        TrainingRunSpec(
            stage="time",
            variant=variant,
            deck=deck,
            seed=manifest.screen_seed,
            encounter_set="overgrowth_easy",
            max_environment_steps=None,
            max_training_seconds=manifest.time_budget_seconds,
            timeout_seconds=max(
                manifest.confirmation_timeout_seconds,
                manifest.time_budget_seconds + 300.0,
            ),
        )
        for variant in finalists
        for deck in manifest.decks
    )


def hard_training_specs(
    manifest: BenchmarkSuiteManifest,
    finalists: Sequence[PolicyVariant],
) -> tuple[TrainingRunSpec, ...]:
    """Return the controlled hard-pool retraining matrix."""
    return tuple(
        TrainingRunSpec(
            stage="hard",
            variant=variant,
            deck=deck,
            seed=seed,
            encounter_set="overgrowth_hard_v1",
            max_environment_steps=manifest.confirmation_transition_budget,
            max_training_seconds=None,
            timeout_seconds=manifest.confirmation_timeout_seconds,
        )
        for variant in finalists
        for deck in manifest.decks
        for seed in manifest.confirmation_seeds
    )


def _run_directory(manifest: BenchmarkSuiteManifest, spec: TrainingRunSpec) -> Path:
    return manifest.output_path / "training" / spec.stage / spec.run_id


def checkpoint_path_for_spec(
    manifest: BenchmarkSuiteManifest,
    spec: TrainingRunSpec,
) -> Path:
    suffix = ".json" if spec.variant.policy == "q_learning" else ".pt"
    return _run_directory(manifest, spec) / f"checkpoint{suffix}"


def _training_args_for_variant(
    manifest: BenchmarkSuiteManifest,
    variant: PolicyVariant,
) -> dict[str, Any]:
    resolved = dict(manifest.common_training_args)
    if variant.family == "q_learning":
        resolved.update(manifest.q_learning_args)
    elif variant.family == "dqn":
        resolved.update(manifest.dqn_args)
        resolved["dqn_architecture"] = variant.architecture
    else:
        resolved.update(manifest.ppo_args)
        resolved.update(
            {
                "ppo_policy_architecture": variant.architecture,
                "num_envs": manifest.ppo_num_envs,
                "env_workers": manifest.ppo_env_workers,
                "rollout_steps": manifest.ppo_rollout_steps,
            }
        )
    reserved = {
        "policy",
        "deck",
        "encounter_set",
        "seed",
        "episodes",
        "save_agent",
        "output_dir",
        "max_environment_steps",
        "max_training_seconds",
    }
    conflict = sorted(reserved & set(resolved))
    if conflict:
        raise ValueError(
            "Suite training argument maps cannot override: " + ", ".join(conflict)
        )
    return resolved


def _append_cli_argument(command: list[str], key: str, value: Any) -> None:
    flag = "--" + key.replace("_", "-")
    if isinstance(value, bool):
        command.append(flag if value else "--no-" + key.replace("_", "-"))
    elif isinstance(value, (list, tuple)):
        command.extend((flag, ",".join(str(item) for item in value)))
    elif value is not None:
        command.extend((flag, str(value)))


def training_command(
    manifest: BenchmarkSuiteManifest,
    spec: TrainingRunSpec,
) -> tuple[str, ...]:
    """Build one explicit, auditable training subprocess command."""
    checkpoint_path = checkpoint_path_for_spec(manifest, spec)
    command = [
        sys.executable,
        "-m",
        "game.cli.train",
        "--policy",
        spec.variant.policy,
        "--deck",
        spec.deck,
        "--encounter-set",
        spec.encounter_set,
        "--seed",
        str(spec.seed),
        "--episodes",
        str(manifest.episode_safety_ceiling),
        "--save-agent",
        str(checkpoint_path),
        "--no-print-config",
    ]
    if spec.max_environment_steps is not None:
        command.extend(("--max-environment-steps", str(spec.max_environment_steps)))
    if spec.max_training_seconds is not None:
        command.extend(("--max-training-seconds", str(spec.max_training_seconds)))
    for key, value in sorted(_training_args_for_variant(manifest, spec.variant).items()):
        _append_cli_argument(command, key, value)
    return tuple(command)


def _training_marker_path(
    manifest: BenchmarkSuiteManifest,
    spec: TrainingRunSpec,
) -> Path:
    return _run_directory(manifest, spec) / "complete.json"


def training_run_is_complete(
    manifest: BenchmarkSuiteManifest,
    spec: TrainingRunSpec,
) -> bool:
    checkpoint = checkpoint_path_for_spec(manifest, spec)
    run_sidecar = checkpoint.with_suffix(".run.json")
    marker = _training_marker_path(manifest, spec)
    if not (checkpoint.is_file() and run_sidecar.is_file() and marker.is_file()):
        return False
    payload = json.loads(marker.read_text(encoding="utf-8"))
    expected_reason = (
        "environment_steps"
        if spec.max_environment_steps is not None
        else "training_time"
    )
    if payload.get("run_id") != spec.run_id:
        return False
    if payload.get("training_stop_reason") != expected_reason:
        return False
    if spec.max_environment_steps is not None:
        return int(payload.get("environment_steps", -1)) == spec.max_environment_steps
    return spec.max_training_seconds is not None


def _subprocess_environment(manifest: BenchmarkSuiteManifest) -> dict[str, str]:
    environment = dict(os.environ)
    thread_count = str(manifest.training_threads)
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": thread_count,
            "MKL_NUM_THREADS": thread_count,
            "VECLIB_MAXIMUM_THREADS": thread_count,
        }
    )
    return environment


def execute_training_run(
    manifest: BenchmarkSuiteManifest,
    spec: TrainingRunSpec,
    *,
    resume: bool = True,
) -> dict[str, Any]:
    """Run or resume one trainer process and return its stable status payload."""
    if resume and training_run_is_complete(manifest, spec):
        (_run_directory(manifest, spec) / "failure.json").unlink(missing_ok=True)
        return json.loads(
            _training_marker_path(manifest, spec).read_text(encoding="utf-8")
        )

    run_dir = _run_directory(manifest, spec)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "training.log"
    checkpoint = checkpoint_path_for_spec(manifest, spec)
    if checkpoint.exists() and not resume:
        raise FileExistsError(
            f"Refusing to overwrite existing suite checkpoint {checkpoint}."
        )

    started = perf_counter()
    with log_path.open("w", encoding="utf-8") as log_file:
        try:
            completed = subprocess.run(
                training_command(manifest, spec),
                cwd=Path.cwd(),
                env=_subprocess_environment(manifest),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                check=False,
                text=True,
                timeout=spec.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            payload = {
                "run_id": spec.run_id,
                "status": "timeout",
                "timeout_seconds": spec.timeout_seconds,
                "duration_seconds": round(perf_counter() - started, 6),
                "error": str(exc),
            }
            _write_json(run_dir / "failure.json", payload)
            return payload

    if completed.returncode != 0:
        payload = {
            "run_id": spec.run_id,
            "status": "failed",
            "returncode": completed.returncode,
            "duration_seconds": round(perf_counter() - started, 6),
            "log": str(log_path),
        }
        _write_json(run_dir / "failure.json", payload)
        return payload

    run_sidecar = checkpoint.with_suffix(".run.json")
    if not run_sidecar.is_file():
        raise RuntimeError(f"Training succeeded without run metadata: {run_sidecar}")
    run_payload = json.loads(run_sidecar.read_text(encoding="utf-8"))
    metadata = run_payload["run_metadata"]
    payload = {
        "run_id": spec.run_id,
        "status": "complete",
        "stage": spec.stage,
        "variant": spec.variant.label,
        "policy": spec.variant.policy,
        "architecture": spec.variant.architecture,
        "deck": spec.deck,
        "seed": spec.seed,
        "encounter_set": spec.encounter_set,
        "checkpoint": str(checkpoint),
        "environment_steps": int(metadata["environment_steps"]),
        "optimization_steps": int(metadata["optimization_steps"]),
        "training_elapsed_seconds": float(metadata["training_elapsed_seconds"]),
        "training_cpu_seconds": float(metadata.get("training_cpu_seconds", 0.0)),
        "checkpoint_training_seconds": float(
            metadata.get(
                "checkpoint_training_seconds",
                min(
                    float(metadata["training_elapsed_seconds"]),
                    float(spec.max_training_seconds)
                    if spec.max_training_seconds is not None
                    else float(metadata["training_elapsed_seconds"]),
                ),
            )
        ),
        "training_stop_reason": str(metadata["training_stop_reason"]),
        "wall_seconds": round(perf_counter() - started, 6),
    }
    expected_reason = (
        "environment_steps"
        if spec.max_environment_steps is not None
        else "training_time"
    )
    if payload["training_stop_reason"] != expected_reason:
        raise RuntimeError(
            f"Run {spec.run_id} stopped for {payload['training_stop_reason']!r}; "
            f"expected {expected_reason!r}."
        )
    if (
        spec.max_environment_steps is not None
        and payload["environment_steps"] != spec.max_environment_steps
    ):
        raise RuntimeError(
            f"Run {spec.run_id} recorded {payload['environment_steps']} transitions; "
            f"expected exactly {spec.max_environment_steps}."
        )
    _write_json(_training_marker_path(manifest, spec), payload)
    (run_dir / "failure.json").unlink(missing_ok=True)
    return payload


def execute_training_matrix(
    manifest: BenchmarkSuiteManifest,
    specs: Sequence[TrainingRunSpec],
    *,
    max_workers: int | None = None,
    resume: bool = True,
) -> tuple[dict[str, Any], ...]:
    """Run independent training cells with bounded process-level concurrency."""
    worker_count = manifest.max_parallel_trainings if max_workers is None else max_workers
    if worker_count <= 0:
        raise ValueError("max_workers must be positive.")
    if worker_count == 1:
        results = [
            execute_training_run(manifest, spec, resume=resume) for spec in specs
        ]
    else:
        results_by_id: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(execute_training_run, manifest, spec, resume=resume): spec
                for spec in specs
            }
            for future in as_completed(futures):
                spec = futures[future]
                results_by_id[spec.run_id] = future.result()
        results = [results_by_id[spec.run_id] for spec in specs]
    failures = [result for result in results if result.get("status") != "complete"]
    _write_json(
        manifest.output_path / "training" / f"{specs[0].stage if specs else 'empty'}-status.json",
        {"results": results},
    )
    if failures:
        failed_ids = ", ".join(str(result["run_id"]) for result in failures)
        raise RuntimeError(f"Training matrix contains failed runs: {failed_ids}")
    return tuple(results)


def _evaluation_cell_path(
    manifest: BenchmarkSuiteManifest,
    stage: str,
    run_id: str,
    evaluation_deck: str,
    encounter: str,
) -> Path:
    return (
        manifest.output_path
        / "evaluations"
        / stage
        / run_id
        / evaluation_deck
        / f"{encounter}.json"
    )


def _validate_agent_for_environment(agent: Any, env: CombatEnv, description: str) -> None:
    errors: list[str] = []
    if int(agent.action_space_size) != env.action_space_size:
        errors.append(
            f"action_space_size checkpoint={agent.action_space_size} env={env.action_space_size}"
        )
    observation_size = getattr(agent, "observation_size", None)
    if observation_size is not None and int(observation_size) != env.observation_size:
        errors.append(
            f"observation_size checkpoint={observation_size} env={env.observation_size}"
        )
    action_feature_size = getattr(agent, "action_feature_size", None)
    if (
        action_feature_size is not None
        and int(action_feature_size) != env.action_feature_size
    ):
        errors.append(
            "action_feature_size "
            f"checkpoint={action_feature_size} env={env.action_feature_size}"
        )
    architecture = getattr(agent, "architecture", None)
    policy_architecture = getattr(agent, "policy_architecture", None)
    if "shared_enemy" in {architecture, policy_architecture}:
        expected_layout = {
            "max_enemy_count": env.encoder.max_enemy_count,
            "enemy_feature_start": (
                env.encoder.scalar_feature_count
                + env.encoder.pile_count_feature_count
            ),
            "enemy_slot_feature_size": env.encoder.enemy_slot_feature_count,
            "uses_target_feature_index": env.encoder.action_feature_names.index(
                "uses_target"
            ),
            "target_slot_feature_index": env.encoder.action_feature_names.index(
                "target_slot_fraction"
            ),
        }
        for field_name, expected in expected_layout.items():
            actual = getattr(agent, field_name, None)
            if actual is None or int(actual) != expected:
                errors.append(f"{field_name} checkpoint={actual} env={expected}")
    if isinstance(agent, QLearningAgent) and agent.q_table:
        widths = {len(state) for state in agent.q_table}
        if widths != {env.observation_size}:
            errors.append(
                f"q_table_state_widths checkpoint={sorted(widths)} env={env.observation_size}"
            )
    if errors:
        raise ValueError(f"Incompatible {description}: " + "; ".join(errors))


def _metrics_to_row(
    *,
    stage: str,
    run_id: str,
    variant: str,
    policy_type: str,
    training_deck: str | None,
    evaluation_deck: str,
    training_seed: int | None,
    encounter: str,
    episode_seed: int,
    metrics: EpisodeMetrics,
) -> EvaluationRow:
    return EvaluationRow(
        stage=stage,
        run_id=run_id,
        variant=variant,
        policy_type=policy_type,
        training_deck=training_deck,
        evaluation_deck=evaluation_deck,
        training_seed=training_seed,
        encounter=encounter,
        episode_seed=episode_seed,
        total_reward=metrics.total_reward,
        steps=metrics.steps,
        win=metrics.win,
        player_hp=metrics.player_hp,
        enemy_hp=metrics.enemy_hp,
        damage_taken=metrics.damage_taken,
    )


def evaluate_checkpoint_spec(
    manifest: BenchmarkSuiteManifest,
    spec: TrainingRunSpec,
    *,
    resume: bool = True,
) -> tuple[EvaluationRow, ...]:
    """Evaluate one trained checkpoint on every fixed encounter and both decks."""
    checkpoint = checkpoint_path_for_spec(manifest, spec)
    agent = load_agent(checkpoint, device="cpu")
    policy = policy_from_agent(agent)
    policy_type = policy_name_from_agent(agent)
    rows: list[EvaluationRow] = []

    for evaluation_deck in manifest.decks:
        for encounter in manifest.fixed_encounters:
            cell_path = _evaluation_cell_path(
                manifest,
                spec.stage,
                spec.run_id,
                evaluation_deck,
                encounter,
            )
            if resume and cell_path.is_file():
                payload = json.loads(cell_path.read_text(encoding="utf-8"))
                rows.extend(EvaluationRow(**row) for row in payload["rows"])
                continue

            env_factory = CombatEnvFactory(
                encounter_set=encounter,
                deck=evaluation_deck,
                record_trajectory=False,
                hp_loss_penalty_scale=1.0,
                incoming_damage_shaping_scale=0.0,
            )
            env = env_factory()
            _validate_agent_for_environment(
                agent,
                env,
                f"{spec.variant.label!r} on {evaluation_deck}/{encounter}",
            )
            agent.rng.seed(manifest.evaluation_base_seed)
            cell_rows = []
            for episode_index in range(manifest.evaluation_episodes):
                episode_seed = manifest.evaluation_base_seed + episode_index
                metrics = rollout_episode(env, policy, seed=episode_seed)
                cell_rows.append(
                    _metrics_to_row(
                        stage=spec.stage,
                        run_id=spec.run_id,
                        variant=spec.variant.label,
                        policy_type=policy_type,
                        training_deck=spec.deck,
                        evaluation_deck=evaluation_deck,
                        training_seed=spec.seed,
                        encounter=encounter,
                        episode_seed=episode_seed,
                        metrics=metrics,
                    )
                )
            _write_json(cell_path, {"rows": [asdict(row) for row in cell_rows]})
            rows.extend(cell_rows)
    return tuple(rows)


def evaluate_builtin_baselines(
    manifest: BenchmarkSuiteManifest,
    *,
    resume: bool = True,
) -> tuple[EvaluationRow, ...]:
    """Evaluate random and heuristic once on the controlled combat grid."""
    rows: list[EvaluationRow] = []
    for policy_name in ("random", "heuristic"):
        run_id = f"builtin__{policy_name}"
        for evaluation_deck in manifest.decks:
            for encounter in manifest.fixed_encounters:
                cell_path = _evaluation_cell_path(
                    manifest,
                    "screen",
                    run_id,
                    evaluation_deck,
                    encounter,
                )
                if resume and cell_path.is_file():
                    payload = json.loads(cell_path.read_text(encoding="utf-8"))
                    rows.extend(EvaluationRow(**row) for row in payload["rows"])
                    continue
                env = CombatEnvFactory(
                    encounter_set=encounter,
                    deck=evaluation_deck,
                    record_trajectory=False,
                    hp_loss_penalty_scale=1.0,
                    incoming_damage_shaping_scale=0.0,
                )()
                if policy_name == "random":
                    policy = lambda active_env, obs, mask: active_env.rng.choice(
                        [index for index, legal in enumerate(mask) if legal]
                    )
                else:
                    policy = choose_heuristic_action
                cell_rows = []
                for episode_index in range(manifest.evaluation_episodes):
                    episode_seed = manifest.evaluation_base_seed + episode_index
                    metrics = rollout_episode(env, policy, seed=episode_seed)
                    cell_rows.append(
                        _metrics_to_row(
                            stage="screen",
                            run_id=run_id,
                            variant=policy_name,
                            policy_type=policy_name,
                            training_deck=None,
                            evaluation_deck=evaluation_deck,
                            training_seed=None,
                            encounter=encounter,
                            episode_seed=episode_seed,
                            metrics=metrics,
                        )
                    )
                _write_json(cell_path, {"rows": [asdict(row) for row in cell_rows]})
                rows.extend(cell_rows)
    return tuple(rows)


def evaluate_training_matrix(
    manifest: BenchmarkSuiteManifest,
    specs: Sequence[TrainingRunSpec],
    *,
    include_builtins: bool = False,
    resume: bool = True,
    max_workers: int | None = None,
) -> tuple[EvaluationRow, ...]:
    """Evaluate a complete stage with resumable per-cell artifacts."""
    worker_count = manifest.max_parallel_trainings if max_workers is None else max_workers
    rows_by_id: dict[str, tuple[EvaluationRow, ...]] = {}
    if worker_count == 1:
        for spec in specs:
            rows_by_id[spec.run_id] = evaluate_checkpoint_spec(
                manifest,
                spec,
                resume=resume,
            )
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    evaluate_checkpoint_spec,
                    manifest,
                    spec,
                    resume=resume,
                ): spec
                for spec in specs
            }
            for future in as_completed(futures):
                spec = futures[future]
                rows_by_id[spec.run_id] = future.result()
    rows = [row for spec in specs for row in rows_by_id[spec.run_id]]
    if include_builtins:
        rows.extend(evaluate_builtin_baselines(manifest, resume=resume))
    stage = specs[0].stage if specs else "empty"
    _write_evaluation_outputs(manifest, stage, rows)
    return tuple(rows)


def _cell_key(row: EvaluationRow) -> tuple[Any, ...]:
    return (
        row.variant,
        row.training_deck,
        row.training_seed,
        row.evaluation_deck,
        row.encounter,
    )


def score_variants(rows: Sequence[EvaluationRow]) -> tuple[VariantScore, ...]:
    """Compute macro/worst-cell robust scores with deterministic tie-breaking."""
    grouped_by_variant: dict[str, list[EvaluationRow]] = {}
    for row in rows:
        if row.training_deck is None:
            continue
        grouped_by_variant.setdefault(row.variant, []).append(row)

    scores: list[VariantScore] = []
    for variant, variant_rows in grouped_by_variant.items():
        cells: dict[tuple[Any, ...], list[EvaluationRow]] = {}
        for row in variant_rows:
            cells.setdefault(_cell_key(row), []).append(row)
        cell_win_rates = [
            statistics.fmean(1.0 if row.win else 0.0 for row in cell_rows)
            for cell_rows in cells.values()
        ]
        wins = sum(1 for row in variant_rows if row.win)
        interval = wilson_interval(wins, len(variant_rows))
        scores.append(
            VariantScore(
                variant=variant,
                macro_win_rate=statistics.fmean(cell_win_rates),
                worst_cell_win_rate=min(cell_win_rates),
                mean_damage_taken=statistics.fmean(
                    row.damage_taken for row in variant_rows
                ),
                mean_player_hp=statistics.fmean(row.player_hp for row in variant_rows),
                mean_reward=statistics.fmean(row.total_reward for row in variant_rows),
                episodes=len(variant_rows),
                win_rate_interval=interval,
            )
        )
    return tuple(sorted(scores, key=lambda score: score.ranking_key))


def wilson_interval(
    successes: int,
    total: int,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    """Return a two-sided Wilson score interval for one binomial proportion."""
    if total <= 0:
        return (0.0, 0.0)
    proportion = successes / total
    denominator = 1.0 + (z * z / total)
    centre = proportion + (z * z / (2.0 * total))
    spread = z * math.sqrt(
        (proportion * (1.0 - proportion) / total)
        + (z * z / (4.0 * total * total))
    )
    return ((centre - spread) / denominator, (centre + spread) / denominator)


def select_confirmation_finalists(
    manifest: BenchmarkSuiteManifest,
    scores: Sequence[VariantScore],
) -> tuple[PolicyVariant, ...]:
    """Choose four screen finalists while retaining DQN and PPO representation."""
    by_label = {variant.label: variant for variant in manifest.variants}
    eligible = [score for score in scores if score.variant in by_label]
    if len(eligible) <= 4:
        return tuple(by_label[score.variant] for score in eligible)
    selected = [by_label[score.variant] for score in eligible[:4]]
    for required_family in ("dqn", "ppo"):
        if any(variant.family == required_family for variant in selected):
            continue
        replacement = next(
            by_label[score.variant]
            for score in eligible
            if by_label[score.variant].family == required_family
        )
        replace_index = next(
            index
            for index in range(len(selected) - 1, -1, -1)
            if selected[index].family not in {required_family}
            and sum(
                1 for item in selected if item.family == selected[index].family
            )
            > 1
        )
        selected[replace_index] = replacement
    ranking_index = {score.variant: index for index, score in enumerate(eligible)}
    return tuple(sorted(selected, key=lambda variant: ranking_index[variant.label]))


def select_hard_finalists(
    manifest: BenchmarkSuiteManifest,
    scores: Sequence[VariantScore],
) -> tuple[PolicyVariant, ...]:
    """Choose best DQN, best PPO, and best remaining confirmed variant."""
    by_label = {variant.label: variant for variant in manifest.variants}
    ranked = [by_label[score.variant] for score in scores if score.variant in by_label]
    best_dqn = next(variant for variant in ranked if variant.family == "dqn")
    best_ppo = next(variant for variant in ranked if variant.family == "ppo")
    selected = [best_dqn, best_ppo]
    selected.append(next(variant for variant in ranked if variant not in selected))
    return tuple(selected)


def _write_evaluation_outputs(
    manifest: BenchmarkSuiteManifest,
    stage: str,
    rows: Sequence[EvaluationRow],
) -> None:
    output_dir = manifest.output_path / "evaluations"
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"{stage}-episodes.jsonl"
    jsonl_path.write_text(
        "".join(json.dumps(asdict(row), sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    scores = score_variants(rows)
    _write_json(
        output_dir / f"{stage}-summary.json",
        {
            "stage": stage,
            "evaluation_base_seed": manifest.evaluation_base_seed,
            "evaluation_seeds": [
                manifest.evaluation_base_seed + index
                for index in range(manifest.evaluation_episodes)
            ],
            "variant_scores": [score.as_dict() for score in scores],
        },
    )
    csv_path = output_dir / f"{stage}-summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=(
                "variant",
                "macro_win_rate",
                "worst_cell_win_rate",
                "mean_damage_taken",
                "mean_player_hp",
                "mean_reward",
                "episodes",
                "win_rate_interval_low",
                "win_rate_interval_high",
            ),
        )
        writer.writeheader()
        for score in scores:
            score_values = {
                key: value
                for key, value in score.as_dict().items()
                if key != "win_rate_interval"
            }
            writer.writerow(
                {
                    **score_values,
                    "win_rate_interval_low": score.win_rate_interval[0],
                    "win_rate_interval_high": score.win_rate_interval[1],
                }
            )


def catalog_historical_checkpoints(
    manifest: BenchmarkSuiteManifest,
) -> tuple[dict[str, Any], ...]:
    """Inventory every recognizable historical checkpoint without adapting it."""
    candidates: set[Path] = set()
    for raw_root in manifest.historical_roots:
        root = Path(raw_root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.name in {"checkpoint.pt", "checkpoint.json"}:
                candidates.add(path)
                continue
            if path.suffix == ".pt":
                candidates.add(path)
                continue
            if path.suffix == ".json" and not path.name.endswith(
                (".config.json", ".run.json", ".profile.json")
            ):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(payload, dict) and payload.get("agent_type") == "q_learning":
                    candidates.add(path)

    reference_env = CombatEnvFactory(
        encounter_set="overgrowth_easy",
        deck="starter",
        record_trajectory=False,
    )()
    inventory: list[dict[str, Any]] = []
    for path in sorted(candidates, key=lambda item: str(item)):
        entry: dict[str, Any] = {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "loadable": False,
            "compatible": False,
        }
        try:
            agent = load_agent(path, device="cpu")
            entry.update(
                {
                    "loadable": True,
                    "policy_type": policy_name_from_agent(agent),
                    "observation_size": getattr(agent, "observation_size", None),
                    "action_space_size": getattr(agent, "action_space_size", None),
                    "action_feature_size": getattr(agent, "action_feature_size", None),
                    "architecture": getattr(
                        agent,
                        "architecture",
                        getattr(agent, "policy_architecture", None),
                    ),
                }
            )
            try:
                _validate_agent_for_environment(agent, reference_env, str(path))
            except ValueError as exc:
                entry["compatibility_error"] = str(exc)
            else:
                entry["compatible"] = True
        except Exception as exc:  # Historical artifacts may predate current loaders.
            entry["load_error"] = f"{type(exc).__name__}: {exc}"

        run_sidecar = path.with_suffix(".run.json")
        if run_sidecar.is_file():
            try:
                run_payload = json.loads(run_sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
            else:
                metadata = run_payload.get("run_metadata", {})
                config = run_payload.get("training_config", {})
                entry["historical_budget"] = {
                    "episodes_completed": metadata.get("episodes_completed"),
                    "environment_steps": metadata.get("environment_steps"),
                    "duration_seconds": metadata.get("duration_seconds"),
                    "training_deck": config.get("deck", "starter"),
                    "encounter_set": config.get("encounter_set"),
                }
        inventory.append(entry)

    _write_json(
        manifest.output_path / "checkpoint-inventory.json",
        {
            "current_environment": {
                "observation_size": reference_env.observation_size,
                "action_space_size": reference_env.action_space_size,
                "action_feature_size": reference_env.action_feature_size,
            },
            "checkpoints": inventory,
        },
    )
    return tuple(inventory)


def evaluate_compatible_historical_checkpoints(
    manifest: BenchmarkSuiteManifest,
    inventory: Sequence[Mapping[str, Any]],
    *,
    resume: bool = True,
) -> tuple[EvaluationRow, ...]:
    """Evaluate compatible history as context, never as controlled rankings."""
    rows: list[EvaluationRow] = []
    for historical_index, entry in enumerate(inventory):
        if not bool(entry.get("compatible")):
            continue
        path = Path(str(entry["path"]))
        run_id = f"historical-{historical_index:03d}"
        label = f"historical:{path.parent.name or path.stem}"
        agent = load_agent(path, device="cpu")
        policy = policy_from_agent(agent)
        policy_type = policy_name_from_agent(agent)
        historical_budget = entry.get("historical_budget", {})
        training_deck = (
            str(historical_budget.get("training_deck", "starter"))
            if isinstance(historical_budget, Mapping)
            else "starter"
        )
        for evaluation_deck in manifest.decks:
            for encounter in manifest.fixed_encounters:
                cell_path = _evaluation_cell_path(
                    manifest,
                    "historical",
                    run_id,
                    evaluation_deck,
                    encounter,
                )
                if resume and cell_path.is_file():
                    payload = json.loads(cell_path.read_text(encoding="utf-8"))
                    rows.extend(EvaluationRow(**row) for row in payload["rows"])
                    continue
                env = CombatEnvFactory(
                    encounter_set=encounter,
                    deck=evaluation_deck,
                    record_trajectory=False,
                    hp_loss_penalty_scale=1.0,
                    incoming_damage_shaping_scale=0.0,
                )()
                _validate_agent_for_environment(agent, env, label)
                agent.rng.seed(manifest.evaluation_base_seed)
                cell_rows = []
                for episode_index in range(manifest.evaluation_episodes):
                    episode_seed = manifest.evaluation_base_seed + episode_index
                    metrics = rollout_episode(env, policy, seed=episode_seed)
                    cell_rows.append(
                        _metrics_to_row(
                            stage="historical",
                            run_id=run_id,
                            variant=label,
                            policy_type=policy_type,
                            training_deck=training_deck,
                            evaluation_deck=evaluation_deck,
                            training_seed=None,
                            encounter=encounter,
                            episode_seed=episode_seed,
                            metrics=metrics,
                        )
                    )
                _write_json(cell_path, {"rows": [asdict(row) for row in cell_rows]})
                rows.extend(cell_rows)
    _write_evaluation_outputs(manifest, "historical", rows)
    return tuple(rows)


def collect_card_observation_corpus(
    manifest: BenchmarkSuiteManifest,
) -> tuple[tuple[CombatEnv, Observation], ...]:
    """Collect deterministic visible states from both decks and fixed encounters."""
    corpus: list[tuple[CombatEnv, Observation]] = []
    episode_index = 0
    combinations = tuple(
        (deck, encounter)
        for deck in manifest.decks
        for encounter in manifest.fixed_encounters
    )
    while len(corpus) < manifest.microbenchmark_observations:
        deck, encounter = combinations[episode_index % len(combinations)]
        env = CombatEnvFactory(
            encounter_set=encounter,
            deck=deck,
            record_trajectory=False,
            hp_loss_penalty_scale=1.0,
            incoming_damage_shaping_scale=0.0,
        )()
        observation = env.reset(seed=manifest.evaluation_base_seed + episode_index)
        done = False
        while not done and len(corpus) < manifest.microbenchmark_observations:
            corpus.append((env, observation))
            mask = env.get_action_mask()
            action = choose_heuristic_action(env, observation, mask)
            observation, _reward, done, _info = env.step_discrete(action)
        episode_index += 1
    return tuple(corpus)


def _median_seconds(callable_: Any, repeats: int = 5) -> float:
    samples = []
    for _repeat in range(repeats):
        started = perf_counter()
        callable_()
        samples.append(perf_counter() - started)
    return statistics.median(samples)


def run_card_encoding_microbenchmark(
    manifest: BenchmarkSuiteManifest,
) -> dict[str, Any]:
    """Compare current encoding costs with the opt-in card-record kernel."""
    try:
        import torch
    except ModuleNotFoundError as exc:
        payload = {"available": False, "error": str(exc)}
        _write_json(manifest.output_path / "card-encoding-microbenchmark.json", payload)
        return payload

    corpus = collect_card_observation_corpus(manifest)
    observations = tuple(observation for _env, observation in corpus)
    records = tuple(extract_card_zone_records(observation) for observation in observations)

    legacy_elapsed = _median_seconds(
        lambda: [env.encode_observation(observation) for env, observation in corpus],
        repeats=3,
    )
    extraction_elapsed = _median_seconds(
        lambda: [extract_card_zone_records(observation) for observation in observations],
        repeats=3,
    )
    tensorization_elapsed = _median_seconds(
        lambda: tensorize_card_zone_records(records, device="cpu"),
        repeats=3,
    )

    torch.manual_seed(0)
    encoder = SharedCardEncoder()
    encoder.eval()
    parameter_count = sum(parameter.numel() for parameter in encoder.parameters())
    legacy_latency: dict[str, float] = {}
    extraction_latency: dict[str, float] = {}
    tensorization_latency: dict[str, float] = {}
    latency: dict[str, float] = {}
    for batch_size in (1, 32, 256):
        batch_corpus = tuple(
            corpus[index % len(corpus)] for index in range(batch_size)
        )
        batch_observations = tuple(observation for _env, observation in batch_corpus)
        batch_records = tuple(
            records[index % len(records)] for index in range(batch_size)
        )
        legacy_latency[str(batch_size)] = _median_seconds(
            lambda batch_corpus=batch_corpus: [
                env.encode_observation(observation)
                for env, observation in batch_corpus
            ],
            repeats=10,
        ) / batch_size
        extraction_latency[str(batch_size)] = _median_seconds(
            lambda batch_observations=batch_observations: [
                extract_card_zone_records(observation)
                for observation in batch_observations
            ],
            repeats=10,
        ) / batch_size
        tensorization_latency[str(batch_size)] = _median_seconds(
            lambda batch_records=batch_records: tensorize_card_zone_records(
                batch_records,
                device="cpu",
            ),
            repeats=10,
        ) / batch_size
        tensors = tensorize_card_zone_records(batch_records, device="cpu")
        with torch.no_grad():
            encoder(tensors)
        elapsed = _median_seconds(
            lambda tensors=tensors: encoder(tensors),
            repeats=10,
        )
        latency[str(batch_size)] = elapsed / batch_size

    sample_tensors = tensorize_card_zone_records(records[: min(8, len(records))])
    encoded = encoder(sample_tensors)
    tensor_bytes = sum(
        tensor.numel() * tensor.element_size()
        for tensor in (
            sample_tensors.hand_ids,
            sample_tensors.hand_mask,
            sample_tensors.pile_ids,
            sample_tensors.pile_counts,
            sample_tensors.pile_mask,
            encoded.hand_embeddings,
            encoded.pooled_hand_embedding,
            encoded.pile_embeddings,
            encoded.pile_total_counts,
        )
    )

    permuted_piles = type(sample_tensors)(
        hand_ids=sample_tensors.hand_ids,
        hand_mask=sample_tensors.hand_mask,
        pile_ids=sample_tensors.pile_ids.flip(-1),
        pile_counts=sample_tensors.pile_counts.flip(-1),
        pile_mask=sample_tensors.pile_mask.flip(-1),
    )
    with torch.no_grad():
        permuted_pile_output = encoder(permuted_piles)
    pile_invariant = bool(
        torch.allclose(
            encoded.pile_embeddings,
            permuted_pile_output.pile_embeddings,
            atol=1e-6,
        )
    )
    count_sensitive_tensors = type(sample_tensors)(
        hand_ids=sample_tensors.hand_ids,
        hand_mask=sample_tensors.hand_mask,
        pile_ids=sample_tensors.pile_ids,
        pile_counts=sample_tensors.pile_counts.clone(),
        pile_mask=sample_tensors.pile_mask,
    )
    first_count_index = tuple(
        int(value) for value in count_sensitive_tensors.pile_mask.nonzero()[0]
    )
    count_sensitive_tensors.pile_counts[first_count_index] += 1
    with torch.no_grad():
        count_sensitive_output = encoder(count_sensitive_tensors)
    pile_count_sensitive = not bool(
        torch.allclose(
            encoded.pile_embeddings,
            count_sensitive_output.pile_embeddings,
            atol=1e-6,
        )
    )
    padding_zero = bool(
        torch.count_nonzero(
            encoded.hand_embeddings.masked_select(
                (~sample_tensors.hand_mask).unsqueeze(-1)
            )
        )
        == 0
    )

    hand_permutation = torch.arange(sample_tensors.hand_ids.shape[1] - 1, -1, -1)
    permuted_hands = type(sample_tensors)(
        hand_ids=sample_tensors.hand_ids[:, hand_permutation],
        hand_mask=sample_tensors.hand_mask[:, hand_permutation],
        pile_ids=sample_tensors.pile_ids,
        pile_counts=sample_tensors.pile_counts,
        pile_mask=sample_tensors.pile_mask,
    )
    with torch.no_grad():
        permuted_hand_output = encoder(permuted_hands)
    hand_equivariant = bool(
        torch.allclose(
            encoded.hand_embeddings[:, hand_permutation],
            permuted_hand_output.hand_embeddings,
            atol=1e-6,
        )
        and torch.allclose(
            encoded.pooled_hand_embedding,
            permuted_hand_output.pooled_hand_embedding,
            atol=1e-6,
        )
    )

    encoder.train()
    encoder.zero_grad(set_to_none=True)
    gradient_output = encoder(sample_tensors)
    gradient_loss = (
        gradient_output.hand_embeddings.sum()
        + gradient_output.pile_embeddings.sum()
    )
    gradient_loss.backward()
    gradient_nonzero = any(
        parameter.grad is not None and bool(torch.count_nonzero(parameter.grad))
        for parameter in encoder.parameters()
    )

    synthetic_card_id = 9
    semantic_table = encoder.card_semantic_features.detach().clone()
    semantic_table[synthetic_card_id, 0] = 1.0
    torch.manual_seed(0)
    synthetic_encoder = SharedCardEncoder(semantic_table)
    synthetic_output = synthetic_encoder.encode_card_ids(
        torch.tensor([[synthetic_card_id]], dtype=torch.long)
    )
    synthetic_dimension_stable = tuple(synthetic_output.shape) == (
        1,
        1,
        CARD_EMBEDDING_DIM,
    )

    reference_env = corpus[0][0]
    payload = {
        "available": True,
        "card_record_format_version": CARD_RECORD_FORMAT_VERSION,
        "schema_fingerprint": card_record_schema_fingerprint(),
        "observations": len(observations),
        "card_id_capacity": CARD_ID_CAPACITY,
        "card_id_embedding_dim": CARD_ID_EMBEDDING_DIM,
        "card_embedding_dim": CARD_EMBEDDING_DIM,
        "learnable_parameters": parameter_count,
        "legacy_seconds_total": legacy_elapsed,
        "record_extraction_seconds_total": extraction_elapsed,
        "record_tensorization_seconds_total": tensorization_elapsed,
        "legacy_seconds_per_observation": legacy_latency,
        "record_extraction_seconds_per_observation": extraction_latency,
        "record_tensorization_seconds_per_observation": tensorization_latency,
        "encoder_seconds_per_observation": latency,
        "sample_tensor_bytes": tensor_bytes,
        "pile_permutation_invariant": pile_invariant,
        "pile_count_sensitive": pile_count_sensitive,
        "hand_slot_equivariant": hand_equivariant,
        "padding_zero": padding_zero,
        "gradient_nonzero": gradient_nonzero,
        "synthetic_append_dimension_stable": synthetic_dimension_stable,
        "current_legacy_observation_width": reference_env.observation_size,
        "current_legacy_action_feature_width": reference_env.action_feature_size,
        "projected_legacy_growth": {
            str(additional_cards): {
                "observation_width": (
                    reference_env.observation_size + 14 * additional_cards
                ),
                "action_feature_width": (
                    reference_env.action_feature_size + additional_cards
                ),
                "card_record_embedding_width": CARD_EMBEDDING_DIM,
            }
            for additional_cards in (10, 50, 100)
        },
        "policy_win_rate_comparison_available": False,
        "limitation": (
            "card_records_v1 is not connected to policy training; end-to-end "
            "integration and retraining are required before win-rate comparison."
        ),
    }
    _write_json(manifest.output_path / "card-encoding-microbenchmark.json", payload)
    return payload


def benchmark_model_resources(
    manifest: BenchmarkSuiteManifest,
    specs: Sequence[TrainingRunSpec],
) -> tuple[dict[str, Any], ...]:
    """Measure checkpoint size, model size, and CPU inference latency."""
    try:
        import torch
    except ModuleNotFoundError:
        torch = None

    results: list[dict[str, Any]] = []
    for spec in specs:
        checkpoint = checkpoint_path_for_spec(manifest, spec)
        agent = load_agent(checkpoint, device="cpu")
        env = CombatEnvFactory(
            encounter_set="overgrowth_easy",
            deck=spec.deck,
            record_trajectory=False,
        )()
        observation = env.reset(seed=manifest.evaluation_base_seed)
        state = env.encode_observation(observation)
        action_mask, action_features = env.encode_policy_inputs(observation)
        result: dict[str, Any] = {
            "run_id": spec.run_id,
            "variant": spec.variant.label,
            "deck": spec.deck,
            "checkpoint_size_bytes": checkpoint.stat().st_size,
            "q_table_size": len(agent.q_table) if isinstance(agent, QLearningAgent) else None,
            "parameter_count": None,
            "inference_seconds_per_observation": {},
        }

        if isinstance(agent, QLearningAgent):
            state_key = agent.encode_state(env, observation)
            for batch_size in (1, 32, 256):
                elapsed = _median_seconds(
                    lambda batch_size=batch_size: [
                        agent.predict_q_values(state_key) for _index in range(batch_size)
                    ],
                    repeats=10,
                )
                result["inference_seconds_per_observation"][str(batch_size)] = (
                    elapsed / batch_size
                )
        elif torch is not None and isinstance(
            agent,
            (DQNAgent, DoubleDQNAgent, DuelingDoubleDQNAgent),
        ):
            result["parameter_count"] = sum(
                parameter.numel() for parameter in agent.policy_network.parameters()
            )
            for batch_size in (1, 32, 256):
                states = torch.as_tensor(
                    [state] * batch_size,
                    dtype=torch.float32,
                    device=agent.device,
                )
                masks = torch.as_tensor(
                    [action_mask] * batch_size,
                    dtype=torch.bool,
                    device=agent.device,
                )
                features = (
                    None
                    if agent.architecture == "flat"
                    else torch.as_tensor(
                        [action_features] * batch_size,
                        dtype=torch.float32,
                        device=agent.device,
                    )
                )
                with torch.no_grad():
                    agent._compute_network_q_values(
                        network=agent.policy_network,
                        states=states,
                        action_masks=masks,
                        action_features=features,
                    )
                def run_dqn_inference(
                    states: Any = states,
                    masks: Any = masks,
                    features: Any = features,
                ) -> Any:
                    with torch.no_grad():
                        return agent._compute_network_q_values(
                            network=agent.policy_network,
                            states=states,
                            action_masks=masks,
                            action_features=features,
                        )

                elapsed = _median_seconds(
                    run_dqn_inference,
                    repeats=20,
                )
                result["inference_seconds_per_observation"][str(batch_size)] = (
                    elapsed / batch_size
                )
        elif torch is not None and isinstance(agent, PPOAgent):
            result["parameter_count"] = sum(
                parameter.numel() for parameter in agent.actor_critic.parameters()
            )
            for batch_size in (1, 32, 256):
                states = torch.as_tensor(
                    [state] * batch_size,
                    dtype=torch.float32,
                    device=agent.device,
                )
                features = (
                    None
                    if agent.policy_architecture == "flat"
                    else torch.as_tensor(
                        [action_features] * batch_size,
                        dtype=torch.float32,
                        device=agent.device,
                    )
                )
                with torch.no_grad():
                    agent.actor_critic(states, features)
                def run_ppo_inference(
                    states: Any = states,
                    features: Any = features,
                ) -> Any:
                    with torch.no_grad():
                        return agent.actor_critic(states, features)

                elapsed = _median_seconds(
                    run_ppo_inference,
                    repeats=20,
                )
                result["inference_seconds_per_observation"][str(batch_size)] = (
                    elapsed / batch_size
                )
        results.append(result)

    _write_json(
        manifest.output_path / "model-resource-benchmarks.json",
        {"results": results},
    )
    return tuple(results)


def run_bounded_oracle_diagnostics(
    manifest: BenchmarkSuiteManifest,
    hard_specs: Sequence[TrainingRunSpec],
    hard_rows: Sequence[EvaluationRow],
) -> tuple[dict[str, Any], ...]:
    """Run bounded regret diagnostics on two representative episodes per finalist/deck."""
    if not manifest.oracle_enabled:
        return ()
    selected_specs = [
        spec for spec in hard_specs if spec.seed == manifest.confirmation_seeds[0]
    ]
    tasks: list[tuple[TrainingRunSpec, str, int]] = []
    for spec in selected_specs:
        candidate_rows = [
            row
            for row in hard_rows
            if row.run_id == spec.run_id and row.evaluation_deck == spec.deck
        ]
        encounter_rows: dict[str, list[EvaluationRow]] = {}
        for row in candidate_rows:
            encounter_rows.setdefault(row.encounter, []).append(row)
        if not encounter_rows:
            continue
        worst_encounter = min(
            encounter_rows,
            key=lambda encounter: (
                statistics.fmean(
                    1.0 if row.win else 0.0 for row in encounter_rows[encounter]
                ),
                encounter,
            ),
        )
        rows = sorted(encounter_rows[worst_encounter], key=lambda row: row.episode_seed)
        failures = [row for row in rows if not row.win]
        wins = [row for row in rows if row.win]
        representatives: list[EvaluationRow] = []
        if failures:
            representatives.append(failures[0])
        if wins:
            representatives.append(wins[0])
        if len(representatives) < 2:
            remaining = sorted(rows, key=lambda row: (row.player_hp, row.episode_seed))
            for row in remaining:
                if row not in representatives:
                    representatives.append(row)
                if len(representatives) == 2:
                    break
        tasks.extend(
            (spec, worst_encounter, row.episode_seed)
            for row in representatives[:2]
        )

    def run_task(task: tuple[TrainingRunSpec, str, int]) -> dict[str, Any]:
        spec, encounter, episode_seed = task
        output_dir = manifest.output_path / "oracle" / spec.run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{encounter}__seed-{episode_seed}.json"
        log_path = json_path.with_suffix(".log")
        if json_path.is_file():
            return {
                "run_id": spec.run_id,
                "encounter": encounter,
                "seed": episode_seed,
                "status": "complete",
                "json": str(json_path),
                "resumed": True,
            }
        command = (
            sys.executable,
            "-m",
            "game.cli.brute_force",
            "--encounter",
            encounter,
            "--deck",
            spec.deck,
            "--seed",
            str(episode_seed),
            "--agent-path",
            str(checkpoint_path_for_spec(manifest, spec)),
            "--device",
            "cpu",
            "--max-steps",
            "40",
            "--max-nodes",
            "25000",
            "--time-limit-seconds",
            str(manifest.oracle_time_limit_seconds),
            "--regret-max-steps",
            "40",
            "--regret-max-nodes-per-action",
            "5000",
            "--regret-time-limit-per-action",
            "2",
            "--json-out",
            str(json_path),
        )
        with log_path.open("w", encoding="utf-8") as log_file:
            try:
                completed = subprocess.run(
                    command,
                    cwd=Path.cwd(),
                    env=_subprocess_environment(manifest),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=max(600.0, manifest.oracle_time_limit_seconds * 4.0),
                )
            except subprocess.TimeoutExpired:
                return {
                    "run_id": spec.run_id,
                    "encounter": encounter,
                    "seed": episode_seed,
                    "status": "timeout",
                    "json": str(json_path),
                    "log": str(log_path),
                    "resumed": False,
                }
        return {
            "run_id": spec.run_id,
            "encounter": encounter,
            "seed": episode_seed,
            "status": "complete" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "json": str(json_path),
            "log": str(log_path),
            "resumed": False,
        }

    results_by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(3, max(1, len(tasks)))) as executor:
        futures = {executor.submit(run_task, task): task for task in tasks}
        for future in as_completed(futures):
            spec, encounter, episode_seed = futures[future]
            results_by_key[(spec.run_id, encounter, episode_seed)] = future.result()
    results = tuple(
        results_by_key[(spec.run_id, encounter, episode_seed)]
        for spec, encounter, episode_seed in tasks
    )
    _write_json(manifest.output_path / "oracle" / "index.json", {"results": results})
    return results


def _paired_comparisons(rows: Sequence[EvaluationRow]) -> list[dict[str, Any]]:
    scores = score_variants(rows)
    if not scores:
        return []
    leader = scores[0].variant
    leader_rows = {
        (
            row.training_deck,
            row.training_seed,
            row.evaluation_deck,
            row.encounter,
            row.episode_seed,
        ): row
        for row in rows
        if row.variant == leader
    }
    comparisons = []
    for score in scores[1:]:
        competitor_rows = {
            (
                row.training_deck,
                row.training_seed,
                row.evaluation_deck,
                row.encounter,
                row.episode_seed,
            ): row
            for row in rows
            if row.variant == score.variant
        }
        shared_keys = sorted(set(leader_rows) & set(competitor_rows), key=str)
        if not shared_keys:
            continue
        win_differences = [
            (1.0 if leader_rows[key].win else 0.0)
            - (1.0 if competitor_rows[key].win else 0.0)
            for key in shared_keys
        ]
        mean_win_difference = statistics.fmean(win_differences)
        if len(win_differences) > 1:
            margin = 1.959963984540054 * statistics.stdev(win_differences) / math.sqrt(
                len(win_differences)
            )
        else:
            margin = 0.0
        comparisons.append(
            {
                "leader": leader,
                "competitor": score.variant,
                "paired_episodes": len(shared_keys),
                "mean_win_difference": mean_win_difference,
                "win_difference_95_interval": [
                    max(-1.0, mean_win_difference - margin),
                    min(1.0, mean_win_difference + margin),
                ],
                "mean_damage_difference": statistics.fmean(
                    leader_rows[key].damage_taken
                    - competitor_rows[key].damage_taken
                    for key in shared_keys
                ),
            }
        )
    return comparisons


def _deck_transfer_summary(rows: Sequence[EvaluationRow]) -> list[dict[str, Any]]:
    summaries = []
    for variant in sorted({row.variant for row in rows if row.training_deck is not None}):
        variant_rows = [row for row in rows if row.variant == variant]
        in_deck = [row for row in variant_rows if row.training_deck == row.evaluation_deck]
        cross_deck = [row for row in variant_rows if row.training_deck != row.evaluation_deck]
        if not in_deck or not cross_deck:
            continue
        in_win = statistics.fmean(1.0 if row.win else 0.0 for row in in_deck)
        cross_win = statistics.fmean(1.0 if row.win else 0.0 for row in cross_deck)
        summaries.append(
            {
                "variant": variant,
                "in_deck_win_rate": in_win,
                "cross_deck_win_rate": cross_win,
                "generalization_gap": in_win - cross_win,
            }
        )
    return summaries


def _row_group_summary(rows: Sequence[EvaluationRow]) -> dict[str, Any]:
    """Return deterministic descriptive metrics for one non-empty row group."""
    if not rows:
        return {
            "episodes": 0,
            "win_rate": 0.0,
            "mean_damage_taken": 0.0,
            "mean_player_hp": 0.0,
            "mean_reward": 0.0,
            "win_rate_interval": [0.0, 0.0],
        }
    wins = sum(1 for row in rows if row.win)
    return {
        "episodes": len(rows),
        "win_rate": wins / len(rows),
        "mean_damage_taken": statistics.fmean(row.damage_taken for row in rows),
        "mean_player_hp": statistics.fmean(row.player_hp for row in rows),
        "mean_reward": statistics.fmean(row.total_reward for row in rows),
        "win_rate_interval": list(wilson_interval(wins, len(rows))),
    }


def _reference_baseline_summary(rows: Sequence[EvaluationRow]) -> list[dict[str, Any]]:
    summaries = []
    for variant in ("random", "heuristic"):
        variant_rows = [row for row in rows if row.variant == variant]
        if variant_rows:
            summaries.append({"variant": variant, **_row_group_summary(variant_rows)})
    return summaries


def _difficulty_summary(rows: Sequence[EvaluationRow]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for variant in sorted({row.variant for row in rows if row.training_deck is not None}):
        variant_rows = [row for row in rows if row.variant == variant]
        for label, encounters in (
            ("easy", EASY_FIXED_ENCOUNTERS),
            ("hard", HARD_FIXED_ENCOUNTERS),
        ):
            group = [row for row in variant_rows if row.encounter in encounters]
            if group:
                summaries.append(
                    {"variant": variant, "difficulty": label, **_row_group_summary(group)}
                )
    return summaries


def _training_seed_distribution(rows: Sequence[EvaluationRow]) -> list[dict[str, Any]]:
    """Summarize between-training-seed variability for confirmation runs."""
    summaries = []
    for variant in sorted({row.variant for row in rows if row.training_seed is not None}):
        by_seed: dict[int, list[EvaluationRow]] = {}
        for row in rows:
            if row.variant == variant and row.training_seed is not None:
                by_seed.setdefault(row.training_seed, []).append(row)
        seed_win_rates = [
            _row_group_summary(by_seed[seed])["win_rate"] for seed in sorted(by_seed)
        ]
        if not seed_win_rates:
            continue
        summaries.append(
            {
                "variant": variant,
                "training_seeds": sorted(by_seed),
                "seed_win_rates": seed_win_rates,
                "mean_win_rate": statistics.fmean(seed_win_rates),
                "median_win_rate": statistics.median(seed_win_rates),
                "min_win_rate": min(seed_win_rates),
                "max_win_rate": max(seed_win_rates),
                "spread": max(seed_win_rates) - min(seed_win_rates),
            }
        )
    return summaries


def _hard_training_comparison(
    easy_rows: Sequence[EvaluationRow],
    hard_rows: Sequence[EvaluationRow],
    finalists: Sequence[PolicyVariant],
) -> list[dict[str, Any]]:
    """Compare matched easy-trained and hard-trained finalist evaluations."""
    comparisons: list[dict[str, Any]] = []
    finalist_labels = {variant.label for variant in finalists}
    for variant in sorted(finalist_labels):
        for difficulty, encounters in (
            ("all", frozenset(PRIMARY_FIXED_ENCOUNTERS)),
            ("easy", EASY_FIXED_ENCOUNTERS),
            ("hard", HARD_FIXED_ENCOUNTERS),
        ):
            easy_group = [
                row
                for row in easy_rows
                if row.variant == variant and row.encounter in encounters
            ]
            hard_group = [
                row
                for row in hard_rows
                if row.variant == variant and row.encounter in encounters
            ]
            if not easy_group or not hard_group:
                continue
            easy_summary = _row_group_summary(easy_group)
            hard_summary = _row_group_summary(hard_group)
            comparisons.append(
                {
                    "variant": variant,
                    "difficulty": difficulty,
                    "easy_trained_win_rate": easy_summary["win_rate"],
                    "hard_trained_win_rate": hard_summary["win_rate"],
                    "win_rate_difference": (
                        hard_summary["win_rate"] - easy_summary["win_rate"]
                    ),
                    "easy_trained_mean_damage": easy_summary["mean_damage_taken"],
                    "hard_trained_mean_damage": hard_summary["mean_damage_taken"],
                    "mean_damage_difference": (
                        hard_summary["mean_damage_taken"]
                        - easy_summary["mean_damage_taken"]
                    ),
                }
            )
    return comparisons


def _training_throughput_summary(
    manifest: BenchmarkSuiteManifest,
    stage: str,
) -> list[dict[str, Any]]:
    path = manifest.output_path / "training" / f"{stage}-status.json"
    if not path.is_file():
        return []
    results = json.loads(path.read_text(encoding="utf-8"))["results"]
    summaries = []
    for result in results:
        elapsed = float(result.get("training_elapsed_seconds", 0.0))
        summaries.append(
            {
                **result,
                "transitions_per_second": (
                    float(result["environment_steps"]) / elapsed if elapsed > 0.0 else 0.0
                ),
                "updates_per_second": (
                    float(result["optimization_steps"]) / elapsed if elapsed > 0.0 else 0.0
                ),
            }
        )
    return summaries


def _resource_summary(
    model_resources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for variant in sorted({str(row["variant"]) for row in model_resources}):
        rows = [row for row in model_resources if row["variant"] == variant]
        parameter_values = [
            int(row["parameter_count"])
            for row in rows
            if row.get("parameter_count") is not None
        ]
        q_sizes = [
            int(row["q_table_size"])
            for row in rows
            if row.get("q_table_size") is not None
        ]
        summaries.append(
            {
                "variant": variant,
                "parameter_count": (
                    None if not parameter_values else int(statistics.median(parameter_values))
                ),
                "q_table_size": None if not q_sizes else int(statistics.median(q_sizes)),
                "checkpoint_size_bytes": int(
                    statistics.median(int(row["checkpoint_size_bytes"]) for row in rows)
                ),
                "inference_seconds_per_observation": {
                    batch: statistics.median(
                        float(row["inference_seconds_per_observation"][batch])
                        for row in rows
                    )
                    for batch in ("1", "32", "256")
                },
            }
        )
    return summaries


def _oracle_result_summary(
    oracle_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    enriched = []
    for result in oracle_results:
        item = dict(result)
        json_path = Path(str(result.get("json", "")))
        if result.get("status") == "complete" and json_path.is_file():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            oracle = payload.get("oracle", {})
            item.update(
                {
                    "proven_optimal": bool(oracle.get("proven_optimal", False)),
                    "termination_reason": oracle.get("termination_reason"),
                    "expanded_nodes": oracle.get("expanded_nodes"),
                    "oracle_regret": payload.get("oracle_regret"),
                }
            )
        enriched.append(item)
    proven = sum(1 for item in enriched if item.get("proven_optimal"))
    return {
        "cases": enriched,
        "complete_cases": sum(1 for item in enriched if item.get("status") == "complete"),
        "proven_cases": proven,
        "resource_limited_cases": sum(
            1
            for item in enriched
            if item.get("status") == "complete" and not item.get("proven_optimal")
        ),
    }


def _simple_environment_sanity(manifest: BenchmarkSuiteManifest) -> dict[str, Any]:
    """Exercise the intentionally different single-enemy environment separately."""
    rows = []
    for deck in manifest.decks:
        env = CombatEnvFactory(
            encounter_set="simple",
            deck=deck,
            record_trajectory=False,
        )()
        metrics = rollout_episode(
            env,
            choose_heuristic_action,
            seed=manifest.evaluation_base_seed,
        )
        rows.append(
            {
                "deck": deck,
                "observation_size": env.observation_size,
                "action_space_size": env.action_space_size,
                "action_feature_size": env.action_feature_size,
                "heuristic_smoke": asdict(metrics),
            }
        )
    multi_env = CombatEnvFactory(
        encounter_set=manifest.fixed_encounters[0],
        deck=manifest.decks[0],
        record_trajectory=False,
    )()
    return {
        "status": "passed",
        "simple": rows,
        "multi_enemy_reference": {
            "encounter": manifest.fixed_encounters[0],
            "observation_size": multi_env.observation_size,
            "action_space_size": multi_env.action_space_size,
            "action_feature_size": multi_env.action_feature_size,
        },
        "intentionally_separate_from_leaderboards": True,
    }


def write_suite_report(
    manifest: BenchmarkSuiteManifest,
    *,
    screen_rows: Sequence[EvaluationRow],
    confirmation_rows: Sequence[EvaluationRow],
    time_rows: Sequence[EvaluationRow],
    hard_rows: Sequence[EvaluationRow],
    inventory: Sequence[Mapping[str, Any]],
    card_microbenchmark: Mapping[str, Any],
    model_resources: Sequence[Mapping[str, Any]],
    confirmation_finalists: Sequence[PolicyVariant],
    hard_finalists: Sequence[PolicyVariant],
    oracle_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Write deterministic machine-readable and Markdown campaign reports."""
    stage_rows = {
        "screen": screen_rows,
        "confirmation": confirmation_rows,
        "time": time_rows,
        "hard": hard_rows,
    }
    stage_scores = {
        stage: score_variants(rows) for stage, rows in stage_rows.items()
    }
    transfer = _deck_transfer_summary(confirmation_rows)
    references = _reference_baseline_summary(screen_rows)
    confirmation_difficulty = _difficulty_summary(confirmation_rows)
    confirmation_seed_distribution = _training_seed_distribution(confirmation_rows)
    hard_comparison = _hard_training_comparison(
        confirmation_rows,
        hard_rows,
        hard_finalists,
    )
    paired_comparisons = _paired_comparisons(confirmation_rows)
    time_throughput = _training_throughput_summary(manifest, "time")
    resources = _resource_summary(model_resources)
    oracle_summary = _oracle_result_summary(oracle_results)
    simple_sanity = _simple_environment_sanity(manifest)
    _write_json(manifest.output_path / "simple-environment-sanity.json", simple_sanity)
    compatible_history = sum(1 for entry in inventory if entry.get("compatible"))
    recommendations: list[str] = []
    if stage_scores["confirmation"]:
        recommendations.append(
            "Use the confirmation leader as the current controlled baseline: "
            + stage_scores["confirmation"][0].variant
            + "."
        )
    if any(summary["generalization_gap"] > 0.05 for summary in transfer):
        recommendations.append(
            "Prioritize deterministic named-deck sampling; at least one finalist loses "
            "more than five win-rate points under cross-deck transfer."
        )
    else:
        recommendations.append(
            "Cross-deck transfer gaps are at most five points; deck sampling remains "
            "useful but is not the clearest immediate bottleneck."
        )
    if card_microbenchmark.get("available"):
        recommendations.append(
            "Integrate card_records_v1 behind an explicit policy/checkpoint contract "
            "before making any learning-quality claim."
        )
    hard_overall = [
        item
        for item in hard_comparison
        if item["difficulty"] == "all"
    ]
    if hard_overall:
        best_hard_gain = max(hard_overall, key=lambda item: item["win_rate_difference"])
        recommendations.append(
            "Use hard-pool training selectively: the largest overall measured gain was "
            f"{best_hard_gain['win_rate_difference']:+.1%} for "
            f"{best_hard_gain['variant']}; inspect the per-difficulty table before "
            "replacing easy-pool training globally."
        )

    try:
        import torch
    except ModuleNotFoundError:
        torch_version: str | None = None
    else:
        torch_version = str(torch.__version__)

    payload = {
        "suite_format_version": SUITE_FORMAT_VERSION,
        "manifest": manifest.as_dict(),
        "runtime": {
            "python_version": platform.python_version(),
            "torch_version": torch_version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
        },
        "controlled_rankings": {
            stage: [score.as_dict() for score in scores]
            for stage, scores in stage_scores.items()
        },
        "confirmation_finalists": [variant.label for variant in confirmation_finalists],
        "hard_finalists": [variant.label for variant in hard_finalists],
        "reference_baselines": references,
        "deck_transfer": transfer,
        "confirmation_by_difficulty": confirmation_difficulty,
        "confirmation_training_seed_distribution": confirmation_seed_distribution,
        "paired_confirmation_comparisons": paired_comparisons,
        "hard_training_comparison": hard_comparison,
        "time_training_throughput": time_throughput,
        "resource_summary": resources,
        "simple_environment_sanity": simple_sanity,
        "historical_checkpoint_count": len(inventory),
        "compatible_historical_checkpoint_count": compatible_history,
        "card_encoding_microbenchmark": dict(card_microbenchmark),
        "model_resource_benchmarks": [dict(result) for result in model_resources],
        "oracle_results": oracle_summary,
        "recommendations": recommendations,
    }
    _write_json(manifest.output_path / "summary.json", payload)

    lines = [
        "# Full-System Benchmark Report",
        "",
        "The primary ranking uses identical environment-transition budgets. "
        "The equal-time ranking is separate and includes only isolated finalist runs.",
        "",
        f"Screening budget: {manifest.screen_transition_budget:,} transitions; "
        f"confirmation/hard budget: {manifest.confirmation_transition_budget:,} "
        f"transitions; isolated budget: {manifest.time_budget_seconds:.0f} seconds. "
        "Combat-level Wilson intervals do not replace the separate training-seed "
        "spread shown below.",
        "",
    ]
    for stage, title in (
        ("screen", "Screening: equal transitions"),
        ("confirmation", "Confirmation: equal transitions"),
        ("time", "Finalists: equal exclusive time"),
        ("hard", "Hard-pool retraining"),
    ):
        lines.extend((f"## {title}", ""))
        scores = stage_scores[stage]
        if not scores:
            lines.extend(("No completed results.", ""))
            continue
        lines.extend(
            (
                "| Rank | Variant | Macro win | 95% combat CI | Worst cell | Mean damage | Mean HP |",
                "|---:|---|---:|---:|---:|---:|---:|",
            )
        )
        for rank, score in enumerate(scores, start=1):
            lines.append(
                f"| {rank} | {score.variant} | {score.macro_win_rate:.3f} | "
                f"{score.win_rate_interval[0]:.3f}–{score.win_rate_interval[1]:.3f} | "
                f"{score.worst_cell_win_rate:.3f} | "
                f"{score.mean_damage_taken:.2f} | {score.mean_player_hp:.2f} |"
            )
        lines.append("")
    lines.extend(("## Random and heuristic references", ""))
    if references:
        lines.extend(
            (
                "| Policy | Win rate | 95% combat CI | Mean damage | Mean HP |",
                "|---|---:|---:|---:|---:|",
            )
        )
        for summary in references:
            interval = summary["win_rate_interval"]
            lines.append(
                f"| {summary['variant']} | {summary['win_rate']:.3f} | "
                f"{interval[0]:.3f}–{interval[1]:.3f} | "
                f"{summary['mean_damage_taken']:.2f} | "
                f"{summary['mean_player_hp']:.2f} |"
            )
        lines.append("")
    lines.extend(("## Deck transfer", ""))
    if transfer:
        lines.extend(
            (
                "| Variant | In-deck win | Cross-deck win | Gap |",
                "|---|---:|---:|---:|",
            )
        )
        for summary in transfer:
            lines.append(
                f"| {summary['variant']} | {summary['in_deck_win_rate']:.3f} | "
                f"{summary['cross_deck_win_rate']:.3f} | "
                f"{summary['generalization_gap']:.3f} |"
            )
        lines.append("")
    lines.extend(("## Easy versus hard encounters", ""))
    lines.extend(
        (
            "| Variant | Group | Win rate | Mean damage |",
            "|---|---|---:|---:|",
        )
    )
    for summary in confirmation_difficulty:
        lines.append(
            f"| {summary['variant']} | {summary['difficulty']} | "
            f"{summary['win_rate']:.3f} | {summary['mean_damage_taken']:.2f} |"
        )
    lines.append("")

    lines.extend(("## Confirmation training-seed spread", ""))
    lines.extend(
        (
            "| Variant | Mean | Median | Min | Max | Spread |",
            "|---|---:|---:|---:|---:|---:|",
        )
    )
    for summary in confirmation_seed_distribution:
        lines.append(
            f"| {summary['variant']} | {summary['mean_win_rate']:.3f} | "
            f"{summary['median_win_rate']:.3f} | {summary['min_win_rate']:.3f} | "
            f"{summary['max_win_rate']:.3f} | {summary['spread']:.3f} |"
        )
    lines.append("")

    lines.extend(("## Paired confirmation differences", ""))
    if paired_comparisons:
        lines.extend(
            (
                "| Leader | Competitor | Paired episodes | Win difference | 95% paired CI | Damage difference |",
                "|---|---|---:|---:|---:|---:|",
            )
        )
        for comparison in paired_comparisons:
            interval = comparison["win_difference_95_interval"]
            lines.append(
                f"| {comparison['leader']} | {comparison['competitor']} | "
                f"{comparison['paired_episodes']} | "
                f"{comparison['mean_win_difference']:+.3f} | "
                f"{interval[0]:+.3f}–{interval[1]:+.3f} | "
                f"{comparison['mean_damage_difference']:+.2f} |"
            )
        lines.append("")

    lines.extend(("## Hard-pool training effect", ""))
    lines.extend(
        (
            "Positive win differences favor hard-pool training; positive damage differences mean more damage was taken.",
            "",
            "| Variant | Evaluation group | Easy-trained win | Hard-trained win | Difference | Damage difference |",
            "|---|---|---:|---:|---:|---:|",
        )
    )
    for comparison in hard_comparison:
        lines.append(
            f"| {comparison['variant']} | {comparison['difficulty']} | "
            f"{comparison['easy_trained_win_rate']:.3f} | "
            f"{comparison['hard_trained_win_rate']:.3f} | "
            f"{comparison['win_rate_difference']:+.3f} | "
            f"{comparison['mean_damage_difference']:+.2f} |"
        )
    lines.append("")

    lines.extend(("## Exclusive-time throughput", ""))
    if (
        manifest.output_path
        / "superseded"
        / "time-stage-before-checkpoint-timestamp"
    ).is_dir():
        lines.extend(
            (
                "The initial timing pass is preserved under `superseded/` for audit. "
                "It is excluded from every aggregate below; the current runs record "
                "the precise retained optimizer-state time.",
                "",
            )
        )
    lines.extend(
        (
            "| Variant | Deck | Transitions | Updates | Checkpoint time (s) | Transitions/s | CPU seconds |",
            "|---|---|---:|---:|---:|---:|---:|",
        )
    )
    for result in time_throughput:
        lines.append(
            f"| {result['variant']} | {result['deck']} | "
            f"{result['environment_steps']:,} | {result['optimization_steps']:,} | "
            f"{result.get('checkpoint_training_seconds', result['training_elapsed_seconds']):.6f} | "
            f"{result['transitions_per_second']:.1f} | "
            f"{result.get('training_cpu_seconds', 0.0):.1f} |"
        )
    lines.append("")

    lines.extend(("## Model resources and inference", ""))
    lines.extend(
        (
            "Medians combine the two screening-deck checkpoints for each variant.",
            "",
            "| Variant | Parameters | Q states | Checkpoint MiB | Batch 1 µs/item | Batch 32 µs/item | Batch 256 µs/item |",
            "|---|---:|---:|---:|---:|---:|---:|",
        )
    )
    for resource in resources:
        latency = resource["inference_seconds_per_observation"]
        lines.append(
            f"| {resource['variant']} | "
            f"{resource['parameter_count'] if resource['parameter_count'] is not None else '—'} | "
            f"{resource['q_table_size'] if resource['q_table_size'] is not None else '—'} | "
            f"{resource['checkpoint_size_bytes'] / (1024 * 1024):.2f} | "
            f"{latency['1'] * 1e6:.2f} | {latency['32'] * 1e6:.2f} | "
            f"{latency['256'] * 1e6:.2f} |"
        )
    lines.append("")
    lines.extend(
        (
            "## Card records",
            "",
            "`card_records_v1` is a computational representation experiment only. "
            "It is not connected to a trainable policy, so this report deliberately "
            "does not assign it a win rate.",
            "",
            f"Corpus observations: {card_microbenchmark.get('observations', 0):,}; "
            f"learnable parameters: {card_microbenchmark.get('learnable_parameters', 0):,}; "
            f"sample tensor bytes: {card_microbenchmark.get('sample_tensor_bytes', 0):,}.",
            "",
            "| Batch | Legacy encode µs/obs | Record extraction µs/obs | Tensorization µs/obs | Shared forward µs/obs |",
            "|---:|---:|---:|---:|---:|",
        )
    )
    for batch in ("1", "32", "256"):
        legacy_seconds = card_microbenchmark.get(
            "legacy_seconds_per_observation", {}
        ).get(batch, 0.0)
        extraction_seconds = card_microbenchmark.get(
            "record_extraction_seconds_per_observation", {}
        ).get(batch, 0.0)
        tensorization_seconds = card_microbenchmark.get(
            "record_tensorization_seconds_per_observation", {}
        ).get(batch, 0.0)
        encoder_seconds = card_microbenchmark.get(
            "encoder_seconds_per_observation", {}
        ).get(batch, 0.0)
        lines.append(
            f"| {batch} | {legacy_seconds * 1e6:.2f} | "
            f"{extraction_seconds * 1e6:.2f} | "
            f"{tensorization_seconds * 1e6:.2f} | "
            f"{encoder_seconds * 1e6:.2f} |"
        )
    projected_growth = card_microbenchmark.get("projected_legacy_growth", {})
    lines.extend(
        (
            "",
            "Legacy projected widths after +10/+50/+100 cards: "
            + ", ".join(
                f"{count}: obs {projected_growth.get(count, {}).get('observation_width', '—')}, "
                f"action {projected_growth.get(count, {}).get('action_feature_width', '—')}"
                for count in ("10", "50", "100")
            )
            + ". The card-record tensor dimensions remain fixed under the synthetic "
            "append-only registry test. Pile permutation invariance, count "
            "sensitivity, zero padding, hand-slot equivariance, and gradient flow "
            "all passed.",
            "",
            "## Simple-environment sanity check",
            "",
            "The `simple` encounter is intentionally excluded from multi-enemy "
            "leaderboards because its observation/action layout differs. Separate "
            "seeded heuristic smoke runs passed for both decks.",
            "",
            "## Bounded oracle diagnostics",
            "",
            f"Completed {oracle_summary['complete_cases']} cases: "
            f"{oracle_summary['proven_cases']} proven and "
            f"{oracle_summary['resource_limited_cases']} stopped at a resource bound. "
            "Resource-limited results are not presented as exact regret proofs.",
            "",
            "## Historical checkpoints",
            "",
            f"Cataloged {len(inventory)} checkpoints; {compatible_history} match the "
            "current representation. Historical results retain their original budgets "
            "and are not included in controlled rankings.",
            "",
            "## Recommendations",
            "",
        )
    )
    lines.extend(f"- {recommendation}" for recommendation in recommendations)
    lines.append("")
    (manifest.output_path / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


def _variant_map(manifest: BenchmarkSuiteManifest) -> dict[str, PolicyVariant]:
    return {variant.label: variant for variant in manifest.variants}


def _read_selection(
    manifest: BenchmarkSuiteManifest,
    name: str,
) -> tuple[PolicyVariant, ...]:
    path = manifest.output_path / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    variants = _variant_map(manifest)
    return tuple(variants[label] for label in payload["variants"])


def _load_stage_rows(
    manifest: BenchmarkSuiteManifest,
    stage: str,
) -> tuple[EvaluationRow, ...]:
    path = manifest.output_path / "evaluations" / f"{stage}-episodes.jsonl"
    if not path.is_file():
        return ()
    return tuple(
        EvaluationRow(**json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def run_full_benchmark_suite(
    manifest: BenchmarkSuiteManifest,
    *,
    stages: Sequence[str] = (
        "inventory",
        "card_encoding",
        "screen",
        "confirmation",
        "time",
        "hard",
        "oracle",
        "report",
    ),
    resume: bool = True,
) -> dict[str, Any]:
    """Run selected campaign stages, reusing complete stage artifacts."""
    allowed_stages = {
        "inventory",
        "card_encoding",
        "screen",
        "confirmation",
        "time",
        "hard",
        "oracle",
        "report",
    }
    unknown = sorted(set(stages) - allowed_stages)
    if unknown:
        raise ValueError(f"Unknown suite stage(s): {', '.join(unknown)}")
    output = manifest.output_path
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.resolved.json"
    resolved_payload = manifest.as_dict()
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing != resolved_payload:
            raise ValueError(
                f"Resolved manifest differs from existing campaign {manifest_path}."
            )
    else:
        _write_json(manifest_path, resolved_payload)

    inventory = (
        catalog_historical_checkpoints(manifest)
        if "inventory" in stages
        else tuple(
            json.loads((output / "checkpoint-inventory.json").read_text(encoding="utf-8"))[
                "checkpoints"
            ]
        )
    )
    card_microbenchmark = (
        run_card_encoding_microbenchmark(manifest)
        if "card_encoding" in stages
        else json.loads(
            (output / "card-encoding-microbenchmark.json").read_text(encoding="utf-8")
        )
    )

    screen_specs = screen_training_specs(manifest)
    if "screen" in stages:
        execute_training_matrix(manifest, screen_specs, resume=resume)
        screen_rows = evaluate_training_matrix(
            manifest,
            screen_specs,
            include_builtins=True,
            resume=resume,
        )
        model_resources = benchmark_model_resources(manifest, screen_specs)
        screen_scores = score_variants(screen_rows)
        confirmation_finalists = select_confirmation_finalists(
            manifest,
            screen_scores,
        )
        _write_json(
            output / "confirmation-selection.json",
            {
                "basis": "screen_equal_transitions",
                "variants": [variant.label for variant in confirmation_finalists],
            },
        )
    else:
        screen_rows = _load_stage_rows(manifest, "screen")
        model_resources_payload = json.loads(
            (output / "model-resource-benchmarks.json").read_text(encoding="utf-8")
        )
        model_resources = tuple(model_resources_payload["results"])
        confirmation_finalists = _read_selection(
            manifest,
            "confirmation-selection",
        )

    confirmation_specs = confirmation_training_specs(
        manifest,
        confirmation_finalists,
    )
    if "confirmation" in stages:
        execute_training_matrix(manifest, confirmation_specs, resume=resume)
        confirmation_rows = evaluate_training_matrix(
            manifest,
            confirmation_specs,
            resume=resume,
        )
        confirmation_scores = score_variants(confirmation_rows)
        hard_finalists = select_hard_finalists(manifest, confirmation_scores)
        _write_json(
            output / "hard-selection.json",
            {
                "basis": "confirmation_equal_transitions",
                "variants": [variant.label for variant in hard_finalists],
            },
        )
    else:
        confirmation_rows = _load_stage_rows(manifest, "confirmation")
        hard_finalists = _read_selection(manifest, "hard-selection")

    time_specs = time_training_specs(manifest, confirmation_finalists)
    if "time" in stages:
        execute_training_matrix(
            manifest,
            time_specs,
            max_workers=1,
            resume=resume,
        )
        time_rows = evaluate_training_matrix(
            manifest,
            time_specs,
            resume=resume,
        )
    else:
        time_rows = _load_stage_rows(manifest, "time")

    hard_specs = hard_training_specs(manifest, hard_finalists)
    if "hard" in stages:
        execute_training_matrix(manifest, hard_specs, resume=resume)
        hard_rows = evaluate_training_matrix(
            manifest,
            hard_specs,
            resume=resume,
        )
    else:
        hard_rows = _load_stage_rows(manifest, "hard")

    if "inventory" in stages:
        evaluate_compatible_historical_checkpoints(
            manifest,
            inventory,
            resume=resume,
        )

    oracle_results = (
        run_bounded_oracle_diagnostics(manifest, hard_specs, hard_rows)
        if "oracle" in stages
        else tuple(
            json.loads(
                (output / "oracle" / "index.json").read_text(encoding="utf-8")
            )["results"]
        )
        if (output / "oracle" / "index.json").is_file()
        else ()
    )
    report = (
        write_suite_report(
            manifest,
            screen_rows=screen_rows,
            confirmation_rows=confirmation_rows,
            time_rows=time_rows,
            hard_rows=hard_rows,
            inventory=inventory,
            card_microbenchmark=card_microbenchmark,
            model_resources=model_resources,
            confirmation_finalists=confirmation_finalists,
            hard_finalists=hard_finalists,
            oracle_results=oracle_results,
        )
        if "report" in stages
        else {}
    )
    return report


def _write_json(path: str | Path, payload: Any) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(output_path.name + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return output_path
