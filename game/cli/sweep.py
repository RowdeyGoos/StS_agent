"""Optuna-based hyperparameter sweep CLI for RL agents."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from json import JSONDecodeError
import multiprocessing
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Sequence, TypeAlias

from game.agents import dqn as dqn_module
from game.agents import ppo as ppo_module
from game.simulation.core import CombatEnv
from game.simulation.deck_presets import SUPPORTED_DECKS
from game.agents.baselines import EvaluationStats, TrainingResult, train_q_learning
from game.agents.dqn import (
    DQNTrainingResult,
    train_double_dqn,
    train_dqn,
    train_dueling_double_dqn,
)
from game.simulation.env_factory import (
    CombatEnvFactory,
    SUPPORTED_TRAINING_ENCOUNTER_SETS,
)
from game.agents.ppo import PPOTrainingResult, train_masked_ppo

try:
    import optuna
    from optuna.pruners import MedianPruner, NopPruner, SuccessiveHalvingPruner
    from optuna.samplers import RandomSampler, TPESampler
    from optuna.storages import JournalStorage
    try:
        from optuna.storages.journal import JournalFileBackend
    except ImportError:  # pragma: no cover - Optuna 3.x compatibility
        from optuna.storages import JournalFileStorage as JournalFileBackend
    from optuna.trial import FrozenTrial, Trial
except ModuleNotFoundError:  # pragma: no cover - depends on optional dependency
    optuna = None
    MedianPruner = Any
    NopPruner = Any
    SuccessiveHalvingPruner = Any
    RandomSampler = Any
    TPESampler = Any
    JournalStorage = Any
    JournalFileBackend = Any
    FrozenTrial = Any
    Trial = Any

TrainResult: TypeAlias = TrainingResult | DQNTrainingResult | PPOTrainingResult

TRAIN_SEED_STRIDE = 1_000
EVALUATION_SEED_OFFSET = 100_000
TRIAL_WORKER_SEED_STRIDE = 1_000_003

DQN_HIDDEN_SIZE_CHOICES: dict[str, tuple[int, ...]] = {
    "128,128": (128, 128),
    "256,128": (256, 128),
    "256,256": (256, 256),
}
PPO_HIDDEN_SIZE_CHOICES: dict[str, tuple[int, ...]] = {
    "128,128": (128, 128),
    "256,128": (256, 128),
    "256,256": (256, 256),
}
PPO_FLOAT_PARAMETERS = {
    "hp_loss_penalty_scale",
    "incoming_damage_shaping_scale",
    "learning_rate",
    "discount",
    "gae_lambda",
    "clip_ratio",
    "value_loss_coef",
    "entropy_coef",
    "max_grad_norm",
}
PPO_INT_PARAMETERS = {
    "rollout_steps",
    "ppo_epochs",
    "minibatch_size",
    "num_envs",
    "env_workers",
}
PPO_OTHER_PARAMETERS = {"hidden_sizes", "policy_architecture"}
PPO_SEARCH_PARAMETERS = (
    PPO_FLOAT_PARAMETERS | PPO_INT_PARAMETERS | PPO_OTHER_PARAMETERS
)


@dataclass(frozen=True, slots=True)
class SeedRunSummary:
    """One train-seed result inside a sweep trial."""

    train_seed: int | None
    evaluation_seed: int | None
    score: float
    mean_reward: float
    win_rate: float
    mean_steps: float
    mean_player_hp: float


@dataclass(frozen=True, slots=True)
class SweepObjective:
    """Spawn-safe Optuna objective shared by serial and parallel workers."""

    args: argparse.Namespace
    train_seeds: tuple[int, ...]
    evaluation_seeds: tuple[int, ...]
    worker_index: int = 0

    def __call__(self, trial: Trial) -> float:
        sampled_config = _sample_trial_config(trial, self.args)
        env_factory = make_env_factory(
            self.args,
            hp_loss_penalty_scale=sampled_config["hp_loss_penalty_scale"],
            incoming_damage_shaping_scale=sampled_config[
                "incoming_damage_shaping_scale"
            ],
        )
        seed_summaries: list[SeedRunSummary] = []

        for seed_index, (train_seed, evaluation_seed) in enumerate(
            zip(self.train_seeds, self.evaluation_seeds)
        ):
            seed_summary = _train_and_evaluate(
                policy=self.args.policy,
                sampled_config=sampled_config,
                env_factory=env_factory,
                args=self.args,
                train_seed=train_seed,
                evaluation_seed=evaluation_seed,
            )
            seed_summaries.append(seed_summary)

            mean_score = mean(summary.score for summary in seed_summaries)
            trial.report(mean_score, step=seed_index + 1)
            if self.args.pruner != "none" and trial.should_prune():
                trial.set_user_attr(
                    "seed_runs",
                    [asdict(summary) for summary in seed_summaries],
                )
                assert optuna is not None
                raise optuna.TrialPruned()

        aggregate = _aggregate_seed_summaries(seed_summaries)
        trial.set_user_attr(
            "seed_runs",
            [asdict(summary) for summary in seed_summaries],
        )
        for key, value in aggregate.items():
            trial.set_user_attr(key, value)
        trial.set_user_attr("sampled_config", _to_json_ready(sampled_config))

        worker_label = (
            f" worker={self.worker_index}"
            if self.args.trial_workers > 1
            else ""
        )
        print(
            f"[trial {trial.number:03d}{worker_label}] "
            f"score={aggregate['score']:.4f} "
            f"win_rate={aggregate['win_rate']:.4f} "
            f"mean_reward={aggregate['mean_reward']:.4f} "
            f"mean_hp={aggregate['mean_player_hp']:.2f} "
            f"params={_format_params(sampled_config)}",
            flush=True,
        )
        return float(aggregate["score"])


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the sweep entry point."""
    parser = argparse.ArgumentParser(
        description="Run an Optuna-based hyperparameter sweep over the RL trainers."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help=(
            "Optional JSON sweep configuration. Explicit CLI arguments override "
            "values loaded from the file."
        ),
    )
    parser.add_argument(
        "--resolved-config-out",
        type=str,
        default=None,
        help="Optional path for writing the fully resolved sweep configuration.",
    )
    parser.add_argument(
        "--print-config",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Print the fully resolved sweep configuration before running.",
    )
    parser.add_argument(
        "--policy",
        choices=("q_learning", "dqn", "double_dqn", "dueling_double_dqn", "masked_ppo"),
        default="double_dqn",
        help="Which training algorithm to tune.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=20,
        help="Total number of new Optuna trials to run across all trial workers.",
    )
    parser.add_argument(
        "--trial-workers",
        type=int,
        default=1,
        help=(
            "Independent spawned processes that train trials concurrently. Values "
            "above one require --journal-file or --storage."
        ),
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=500,
        help="Training episodes per sweep trial.",
    )
    parser.add_argument(
        "--train-seeds",
        type=int,
        default=3,
        help="How many independent training seeds to average inside each trial.",
    )
    parser.add_argument(
        "--evaluation-episodes",
        type=int,
        default=50,
        help="Held-out evaluation episodes used to score each trained model.",
    )
    parser.add_argument(
        "--evaluation-interval",
        type=int,
        default=0,
        help="Optional checkpoint-evaluation interval during training. Use 0 to disable.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Base seed for deterministic sampling and train/eval seed generation.",
    )
    parser.add_argument(
        "--sampler",
        choices=("tpe", "random"),
        default="tpe",
        help="Optuna sampler to use.",
    )
    parser.add_argument(
        "--pruner",
        choices=("none", "median", "successive_halving"),
        default="none",
        help="Optional Optuna pruner. Conservative defaults are recommended for RL.",
    )
    parser.add_argument(
        "--metric",
        choices=("mean_reward", "win_rate", "hp_preserving_score"),
        default="hp_preserving_score",
        help="Objective metric used to rank trials.",
    )
    parser.add_argument(
        "--hp-weight",
        type=float,
        default=0.25,
        help="Remaining-HP bonus weight used by the hp_preserving_score metric.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="How many completed trials to keep in the saved summary.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Optional wall-clock timeout for the whole study.",
    )
    parser.add_argument(
        "--study-name",
        type=str,
        default=None,
        help="Optional Optuna study name. Useful when resuming from storage.",
    )
    parser.add_argument(
        "--storage",
        type=str,
        default=None,
        help=(
            "Optional shared Optuna database URL. For local parallel workers, "
            "--journal-file is preferred."
        ),
    )
    parser.add_argument(
        "--journal-file",
        type=str,
        default=None,
        help=(
            "Optional local Optuna journal path for safe process coordination and "
            "study resumption. Mutually exclusive with --storage."
        ),
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional JSON path for saving the best-trial summary.",
    )
    parser.add_argument(
        "--encounter-set",
        choices=SUPPORTED_TRAINING_ENCOUNTER_SETS,
        default="overgrowth_easy",
        help="Encounter pool used during the sweep.",
    )
    parser.add_argument(
        "--deck",
        choices=SUPPORTED_DECKS,
        default="starter",
        help="Named deck preset used for every trial.",
    )
    parser.add_argument(
        "--enemy-hp",
        type=int,
        default=40,
        help="Enemy HP for the default simple encounter.",
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
        "--dqn-architecture",
        choices=("flat", "action_feature"),
        default="action_feature",
        help="Fixed DQN-family architecture used during the sweep.",
    )
    parser.add_argument(
        "--ppo-policy-architecture",
        choices=("flat", "action_feature", "shared_enemy"),
        default="action_feature",
        help="Fixed PPO policy head used during the sweep.",
    )
    parser.add_argument(
        "--num-envs",
        type=int,
        default=1,
        help="Number of independent environments used for batched PPO rollouts.",
    )
    parser.add_argument(
        "--env-workers",
        type=int,
        default=0,
        help="Persistent CPU simulator worker processes used by PPO.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help=(
            "Torch device for neural agents, for example `cpu`, `cuda`, or `mps`. "
            "Defaults to CUDA, then Apple MPS, then CPU when available."
        ),
    )
    parser.add_argument(
        "--restore-best-checkpoint",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Restore the best checkpoint before final evaluation for DQN-family and PPO.",
    )
    config_path = _find_config_path(argv)
    search_space: dict[str, Any] | None = None
    if config_path is not None:
        try:
            config_defaults, search_space = _load_sweep_config(parser, config_path)
            parser.set_defaults(**config_defaults)
        except (OSError, JSONDecodeError, ValueError) as exc:
            parser.error(str(exc))
    args = parser.parse_args(argv)
    args.search_space = search_space
    return args


def _find_config_path(argv: Sequence[str] | None) -> str | None:
    """Read only --config before parsing the complete sweep CLI."""
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=str, default=None)
    config_args, _unknown = config_parser.parse_known_args(argv)
    return config_args.config


def _load_sweep_config(
    parser: argparse.ArgumentParser,
    config_path: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Load base sweep values and an optional hyperparameter search space."""
    path = Path(config_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Sweep config {path} must contain a JSON object.")
    if "config" in payload:
        raise ValueError("Sweep config files cannot include the recursive 'config' key.")

    search_space = payload.pop("search_space", None)
    if search_space is not None and not isinstance(search_space, dict):
        raise ValueError("Sweep config key 'search_space' must be a JSON object.")
    actions_by_dest = {
        action.dest: action
        for action in parser._actions
        if action.dest not in {"help", "config"}
    }
    unknown_keys = sorted(set(payload) - set(actions_by_dest))
    if unknown_keys:
        keys = ", ".join(unknown_keys)
        raise ValueError(
            f"Unknown sweep config key(s): {keys}. "
            "Use snake_case CLI destination names."
        )
    defaults = {
        key: _coerce_config_value(actions_by_dest[key], value)
        for key, value in payload.items()
    }
    if search_space is not None:
        _validate_ppo_search_space(search_space)
    return defaults, search_space


def _coerce_config_value(action: argparse.Action, value: Any) -> Any:
    """Apply argparse-equivalent type and choice validation to a JSON value."""
    if isinstance(action, argparse.BooleanOptionalAction):
        if not isinstance(value, bool):
            raise ValueError(f"Config key '{action.dest}' must be a boolean.")
        converted = value
    elif value is None:
        if action.default is not None:
            raise ValueError(f"Config key '{action.dest}' cannot be null.")
        converted = None
    elif action.type is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Config key '{action.dest}' must be an integer.")
        converted = value
    elif action.type is float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Config key '{action.dest}' must be a number.")
        converted = float(value)
    elif action.type is str:
        if not isinstance(value, str):
            raise ValueError(f"Config key '{action.dest}' must be a string.")
        converted = value
    elif action.type is not None:
        try:
            converted = action.type(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid value for config key '{action.dest}': {value!r}."
            ) from exc
    else:
        converted = value

    if action.choices is not None and converted not in action.choices:
        choices = ", ".join(str(choice) for choice in action.choices)
        raise ValueError(f"Config key '{action.dest}' must be one of: {choices}.")
    return converted


def resolved_sweep_config(args: argparse.Namespace) -> dict[str, Any]:
    """Return the effective, reusable JSON configuration for one sweep."""
    resolved = {
        key: value
        for key, value in vars(args).items()
        if key not in {"config", "search_space"}
    }
    if args.policy == "masked_ppo":
        effective_search_space = _default_ppo_search_space(args)
        if args.search_space is not None:
            effective_search_space.update(args.search_space)
        resolved["search_space"] = effective_search_space
    elif args.search_space is not None:
        resolved["search_space"] = args.search_space
    return dict(sorted(_to_json_ready(resolved).items()))


def write_sweep_config(config: dict[str, Any], path: str | Path) -> Path:
    """Write a reusable resolved sweep configuration."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def make_env_factory(
    args: argparse.Namespace,
    *,
    hp_loss_penalty_scale: float,
    incoming_damage_shaping_scale: float,
) -> Callable[[], CombatEnv]:
    """Create an env factory for one sampled reward-shaping setup."""
    return CombatEnvFactory(
        encounter_set=args.encounter_set,
        deck=args.deck,
        enemy_hp=args.enemy_hp,
        player_hp=args.player_hp,
        cards_per_turn=args.cards_per_turn,
        hp_loss_penalty_scale=hp_loss_penalty_scale,
        incoming_damage_shaping_scale=incoming_damage_shaping_scale,
        record_trajectory=False,
    )


def resolve_train_seeds(base_seed: int, count: int) -> tuple[int, ...]:
    """Return stable train seeds shared across every trial."""
    if count <= 0:
        raise ValueError("train-seeds must be positive.")
    return tuple(base_seed + index * TRAIN_SEED_STRIDE for index in range(count))


def resolve_evaluation_seeds(base_seed: int, count: int) -> tuple[int, ...]:
    """Return stable held-out evaluation seeds shared across every trial."""
    if count <= 0:
        raise ValueError("train-seeds must be positive.")
    return tuple(
        base_seed + EVALUATION_SEED_OFFSET + index * TRAIN_SEED_STRIDE
        for index in range(count)
    )


def split_trial_counts(total_trials: int, trial_workers: int) -> tuple[int, ...]:
    """Distribute a global trial budget as evenly as possible across workers."""
    if total_trials <= 0:
        raise ValueError("total_trials must be positive.")
    if trial_workers <= 0:
        raise ValueError("trial_workers must be positive.")
    active_workers = min(total_trials, trial_workers)
    quotient, remainder = divmod(total_trials, active_workers)
    return tuple(
        quotient + (1 if worker_index < remainder else 0)
        for worker_index in range(active_workers)
    )


def _build_optuna_storage(args: argparse.Namespace) -> Any:
    """Build this process's Optuna storage handle from serializable CLI values."""
    if args.journal_file is not None:
        journal_path = Path(args.journal_file).expanduser().resolve()
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        return JournalStorage(JournalFileBackend(str(journal_path)))
    return args.storage


def _storage_description(args: argparse.Namespace) -> str:
    """Return a concise shared-storage label for progress output."""
    if args.journal_file is not None:
        return f"journal {Path(args.journal_file).expanduser().resolve()}"
    return f"database storage {args.storage}"


def _run_trial_worker(
    args: argparse.Namespace,
    train_seeds: tuple[int, ...],
    evaluation_seeds: tuple[int, ...],
    study_name: str,
    worker_index: int,
    trial_count: int,
) -> None:
    """Run one spawn-safe share of a process-parallel Optuna study."""
    _ensure_optuna_available()
    assert optuna is not None
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        study_name=study_name,
        storage=_build_optuna_storage(args),
        load_if_exists=True,
        sampler=_build_sampler(args, worker_index=worker_index),
        pruner=_build_pruner(args),
        direction="maximize",
    )
    study.optimize(
        SweepObjective(
            args,
            train_seeds,
            evaluation_seeds,
            worker_index=worker_index,
        ),
        n_trials=trial_count,
        timeout=args.timeout_seconds,
        gc_after_trial=True,
    )


def _run_parallel_trial_workers(
    *,
    args: argparse.Namespace,
    train_seeds: tuple[int, ...],
    evaluation_seeds: tuple[int, ...],
    study_name: str,
    trial_counts: tuple[int, ...],
) -> None:
    """Spawn trial processes and surface any worker failure to the parent."""
    multiprocessing_context = multiprocessing.get_context("spawn")
    processes = [
        multiprocessing_context.Process(
            target=_run_trial_worker,
            args=(
                args,
                train_seeds,
                evaluation_seeds,
                study_name,
                worker_index,
                trial_count,
            ),
            name=f"sweep-trial-worker-{worker_index}",
        )
        for worker_index, trial_count in enumerate(trial_counts)
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join()
    except BaseException:
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            if process.pid is not None:
                process.join()
        raise

    failed_workers = [
        process
        for process in processes
        if process.exitcode != 0
    ]
    if failed_workers:
        failure_details = ", ".join(
            f"{process.name} (exit code {process.exitcode})"
            for process in failed_workers
        )
        raise RuntimeError(f"Parallel sweep worker failure: {failure_details}.")


def score_evaluation(
    stats: EvaluationStats,
    *,
    metric: str,
    player_max_hp: int,
    hp_weight: float,
) -> float:
    """Convert evaluation statistics into a scalar Optuna objective value."""
    if metric == "mean_reward":
        return stats.mean_reward
    if metric == "win_rate":
        return stats.win_rate
    if metric == "hp_preserving_score":
        if player_max_hp <= 0:
            raise ValueError("player_max_hp must be positive.")
        hp_fraction = stats.mean_player_hp / float(player_max_hp)
        return stats.win_rate + hp_weight * hp_fraction
    raise ValueError(f"Unsupported sweep metric: {metric}")


def run_sweep(args: argparse.Namespace) -> dict[str, Any]:
    """Execute the configured study and return a JSON-serializable summary."""
    _ensure_optuna_available()
    _ensure_policy_dependencies(args.policy)
    if args.search_space is not None and args.policy != "masked_ppo":
        raise ValueError("Custom search_space is currently supported for masked_ppo.")

    if args.trials <= 0:
        raise ValueError("trials must be positive.")
    if args.trial_workers <= 0:
        raise ValueError("trial-workers must be positive.")
    if args.episodes <= 0:
        raise ValueError("episodes must be positive.")
    if args.evaluation_episodes <= 0:
        raise ValueError("evaluation-episodes must be positive.")
    if args.evaluation_interval < 0:
        raise ValueError("evaluation-interval cannot be negative.")
    if args.top_k <= 0:
        raise ValueError("top-k must be positive.")
    if args.storage is not None and args.journal_file is not None:
        raise ValueError("storage and journal-file are mutually exclusive.")
    if (
        min(args.trials, args.trial_workers) > 1
        and args.storage is None
        and args.journal_file is None
    ):
        raise ValueError(
            "Parallel trials require shared Optuna storage. Set --journal-file "
            "for a local sweep or --storage for a shared database."
        )

    assert optuna is not None
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    train_seeds = resolve_train_seeds(args.seed, args.train_seeds)
    evaluation_seeds = resolve_evaluation_seeds(args.seed, args.train_seeds)
    study_name = args.study_name or f"sts_agent_{args.policy}_sweep"
    storage = _build_optuna_storage(args)
    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        load_if_exists=storage is not None,
        sampler=_build_sampler(args),
        pruner=_build_pruner(args),
        direction="maximize",
    )
    trials_existing_before = len(study.trials)
    trial_counts = split_trial_counts(args.trials, args.trial_workers)
    if len(trial_counts) == 1:
        study.optimize(
            SweepObjective(args, train_seeds, evaluation_seeds),
            n_trials=trial_counts[0],
            timeout=args.timeout_seconds,
            gc_after_trial=True,
        )
    else:
        print(
            f"Running {args.trials} trials across {len(trial_counts)} "
            f"process workers using {_storage_description(args)}.",
            flush=True,
        )
        _run_parallel_trial_workers(
            args=args,
            train_seeds=train_seeds,
            evaluation_seeds=evaluation_seeds,
            study_name=study_name,
            trial_counts=trial_counts,
        )

        study = optuna.load_study(
            study_name=study_name,
            storage=_build_optuna_storage(args),
            sampler=_build_sampler(args),
            pruner=_build_pruner(args),
        )

    completed_trials = [
        trial
        for trial in study.trials
        if getattr(trial.state, "name", str(trial.state)) == "COMPLETE"
    ]
    if not completed_trials:
        raise RuntimeError("Sweep finished without any completed trials.")

    ordered_trials = sorted(
        completed_trials,
        key=lambda trial: float("-inf") if trial.value is None else float(trial.value),
        reverse=True,
    )
    best_trial = ordered_trials[0]
    summary = {
        "study_name": study.study_name,
        "policy": args.policy,
        "sampler": args.sampler,
        "pruner": args.pruner,
        "metric": args.metric,
        "hp_weight": args.hp_weight,
        "trials_requested": args.trials,
        "trial_workers": len(trial_counts),
        "trials_existing_before": trials_existing_before,
        "trials_total": len(study.trials),
        "trials_completed": len(completed_trials),
        "encounter_set": args.encounter_set,
        "deck": args.deck,
        "episodes": args.episodes,
        "evaluation_episodes": args.evaluation_episodes,
        "train_seeds": list(train_seeds),
        "evaluation_seeds": list(evaluation_seeds),
        "configuration": resolved_sweep_config(args),
        "best_trial": _serialize_trial(best_trial),
        "top_trials": [_serialize_trial(trial) for trial in ordered_trials[: args.top_k]],
    }

    if args.json_out is not None:
        output_path = Path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(_to_json_ready(summary), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    best_value = best_trial.value
    assert best_value is not None
    print(
        f"Best trial: number={best_trial.number} "
        f"score={best_value:.4f} "
        f"params={_format_params(best_trial.params)}",
        flush=True,
    )
    if args.json_out is not None:
        print(f"Saved sweep summary to {args.json_out}", flush=True)

    return summary


def main() -> None:
    """Run the sweep CLI."""
    args = parse_args()
    resolved_config = resolved_sweep_config(args)
    if args.print_config:
        print("Resolved sweep configuration:")
        print(json.dumps(resolved_config, indent=2, sort_keys=True))
    if args.resolved_config_out is not None:
        output_path = write_sweep_config(resolved_config, args.resolved_config_out)
        print(f"Wrote resolved sweep configuration to {output_path}")
    run_sweep(args)


def _sample_trial_config(trial: Trial, args: argparse.Namespace) -> dict[str, Any]:
    """Sample one trial configuration for the chosen policy family."""
    if args.policy == "masked_ppo":
        return _sample_ppo_trial_config(trial, args)

    config: dict[str, Any] = {
        "hp_loss_penalty_scale": trial.suggest_float(
            "hp_loss_penalty_scale",
            0.5,
            3.0,
        ),
        "incoming_damage_shaping_scale": trial.suggest_float(
            "incoming_damage_shaping_scale",
            0.0,
            1.5,
        ),
    }

    if args.policy == "q_learning":
        config.update(
            learning_rate=trial.suggest_float("learning_rate", 1e-3, 0.5, log=True),
            discount=trial.suggest_float("discount", 0.97, 0.999),
            epsilon=trial.suggest_float("epsilon", 0.4, 1.0),
            epsilon_min=trial.suggest_float("epsilon_min", 0.01, 0.2),
            epsilon_decay=trial.suggest_float("epsilon_decay", 0.99, 0.9995),
        )
        return config

    if args.policy in {"dqn", "double_dqn", "dueling_double_dqn"}:
        hidden_sizes_key = trial.suggest_categorical(
            "hidden_sizes",
            tuple(DQN_HIDDEN_SIZE_CHOICES),
        )
        config.update(
            learning_rate=trial.suggest_float("learning_rate", 1e-4, 3e-3, log=True),
            discount=trial.suggest_float("discount", 0.985, 0.9995),
            epsilon=trial.suggest_float("epsilon", 0.6, 1.0),
            epsilon_min=trial.suggest_float("epsilon_min", 0.01, 0.15),
            epsilon_decay=trial.suggest_float("epsilon_decay", 0.995, 0.9995),
            batch_size=trial.suggest_categorical("batch_size", (32, 64, 128)),
            replay_capacity=trial.suggest_categorical(
                "replay_capacity",
                (10_000, 20_000, 40_000),
            ),
            warmup_steps=trial.suggest_categorical("warmup_steps", (128, 250, 512)),
            train_frequency=trial.suggest_categorical("train_frequency", (2, 4, 8)),
            gradient_steps=trial.suggest_categorical("gradient_steps", (1, 2)),
            target_update_interval=trial.suggest_categorical(
                "target_update_interval",
                (50, 100, 200, 400),
            ),
            hidden_sizes=DQN_HIDDEN_SIZE_CHOICES[hidden_sizes_key],
            architecture=args.dqn_architecture,
            gradient_clip=1.0,
        )
        return config

    raise ValueError(f"Unsupported policy for sweep: {args.policy}")


def _default_ppo_search_space(args: argparse.Namespace) -> dict[str, Any]:
    """Return the built-in PPO ranges expressed in the JSON search schema."""
    return {
        "hp_loss_penalty_scale": {
            "type": "float",
            "low": 0.5,
            "high": 3.0,
        },
        "incoming_damage_shaping_scale": {
            "type": "float",
            "low": 0.0,
            "high": 1.5,
        },
        "learning_rate": {
            "type": "float",
            "low": 1e-4,
            "high": 1e-3,
            "log": True,
        },
        "discount": {"type": "float", "low": 0.985, "high": 0.9995},
        "gae_lambda": {"type": "float", "low": 0.9, "high": 0.99},
        "clip_ratio": {"type": "float", "low": 0.1, "high": 0.3},
        "value_loss_coef": {"type": "float", "low": 0.25, "high": 1.0},
        "entropy_coef": {
            "type": "float",
            "low": 1e-4,
            "high": 5e-2,
            "log": True,
        },
        "rollout_steps": {
            "type": "categorical",
            "choices": [256, 512, 1024],
        },
        "ppo_epochs": {"type": "categorical", "choices": [3, 4, 6, 8]},
        "minibatch_size": {
            "type": "categorical",
            "choices": [32, 64, 128],
        },
        "hidden_sizes": {
            "type": "categorical",
            "choices": [list(sizes) for sizes in PPO_HIDDEN_SIZE_CHOICES.values()],
        },
        "policy_architecture": args.ppo_policy_architecture,
        "max_grad_norm": 0.5,
        "num_envs": args.num_envs,
        "env_workers": args.env_workers,
    }


def _sample_ppo_trial_config(trial: Trial, args: argparse.Namespace) -> dict[str, Any]:
    """Sample PPO values from built-in ranges overlaid by the config file."""
    search_space = _default_ppo_search_space(args)
    if args.search_space is not None:
        search_space.update(args.search_space)
    return {
        name: _sample_ppo_parameter(trial, name, specification)
        for name, specification in search_space.items()
    }


def _validate_ppo_search_space(search_space: dict[str, Any]) -> None:
    """Validate custom PPO search-space keys and specification shapes."""
    unknown_keys = sorted(set(search_space) - PPO_SEARCH_PARAMETERS)
    if unknown_keys:
        keys = ", ".join(unknown_keys)
        raise ValueError(f"Unknown PPO search-space parameter(s): {keys}.")
    for name, specification in search_space.items():
        if not isinstance(specification, dict):
            _normalize_ppo_parameter(name, specification)
            continue
        parameter_type = specification.get("type")
        if parameter_type == "fixed":
            if set(specification) != {"type", "value"}:
                raise ValueError(
                    f"Fixed search-space parameter '{name}' requires only type and value."
                )
            _normalize_ppo_parameter(name, specification["value"])
            continue
        if parameter_type == "categorical":
            if set(specification) != {"type", "choices"}:
                raise ValueError(
                    f"Categorical search-space parameter '{name}' requires only "
                    "type and choices."
                )
            choices = specification["choices"]
            if not isinstance(choices, list) or not choices:
                raise ValueError(
                    f"Search-space parameter '{name}' choices must be a non-empty list."
                )
            for choice in choices:
                _normalize_ppo_parameter(name, choice)
            continue
        if parameter_type not in {"float", "int"}:
            raise ValueError(
                f"Search-space parameter '{name}' has unsupported type "
                f"{parameter_type!r}."
            )
        expected_type = "float" if name in PPO_FLOAT_PARAMETERS else "int"
        if parameter_type != expected_type:
            raise ValueError(
                f"Search-space parameter '{name}' must use type '{expected_type}'."
            )
        allowed_keys = {"type", "low", "high", "log", "step"}
        unknown_spec_keys = set(specification) - allowed_keys
        if unknown_spec_keys or "low" not in specification or "high" not in specification:
            raise ValueError(
                f"Search-space parameter '{name}' requires low/high and supports "
                "only type, low, high, log, and step."
            )
        low = _normalize_ppo_parameter(name, specification["low"])
        high = _normalize_ppo_parameter(name, specification["high"])
        if low > high:
            raise ValueError(f"Search-space parameter '{name}' low cannot exceed high.")
        if "log" in specification and not isinstance(specification["log"], bool):
            raise ValueError(f"Search-space parameter '{name}' log must be boolean.")
        if "step" in specification:
            step = specification["step"]
            if not isinstance(step, (int, float)) or isinstance(step, bool) or step <= 0:
                raise ValueError(f"Search-space parameter '{name}' step must be positive.")
        if specification.get("log") and "step" in specification:
            raise ValueError(
                f"Search-space parameter '{name}' cannot combine log and step."
            )


def _sample_ppo_parameter(trial: Trial, name: str, specification: Any) -> Any:
    """Resolve one fixed, categorical, integer, or floating PPO parameter."""
    if not isinstance(specification, dict):
        return _normalize_ppo_parameter(name, specification)
    parameter_type = specification["type"]
    if parameter_type == "fixed":
        return _normalize_ppo_parameter(name, specification["value"])
    if parameter_type == "categorical":
        choices = specification["choices"]
        if name == "hidden_sizes":
            normalized_choices = tuple(
                _normalize_ppo_parameter(name, choice) for choice in choices
            )
            labels = tuple(",".join(str(size) for size in choice) for choice in normalized_choices)
            if len(set(labels)) != len(labels):
                raise ValueError("hidden_sizes search choices must be unique.")
            selected_label = trial.suggest_categorical(name, labels)
            return normalized_choices[labels.index(selected_label)]
        selected = trial.suggest_categorical(name, tuple(choices))
        return _normalize_ppo_parameter(name, selected)
    if parameter_type == "float":
        kwargs = {
            key: specification[key]
            for key in ("log", "step")
            if key in specification
        }
        selected = trial.suggest_float(
            name,
            float(specification["low"]),
            float(specification["high"]),
            **kwargs,
        )
        return _normalize_ppo_parameter(name, selected)
    kwargs = {
        key: specification[key]
        for key in ("log", "step")
        if key in specification
    }
    selected = trial.suggest_int(
        name,
        int(specification["low"]),
        int(specification["high"]),
        **kwargs,
    )
    return _normalize_ppo_parameter(name, selected)


def _normalize_ppo_parameter(name: str, value: Any) -> Any:
    """Validate and normalize one concrete PPO training value."""
    if name in PPO_FLOAT_PARAMETERS:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"PPO parameter '{name}' must be numeric.")
        return float(value)
    if name in PPO_INT_PARAMETERS:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"PPO parameter '{name}' must be an integer.")
        minimum = 0 if name == "env_workers" else 1
        if value < minimum:
            raise ValueError(f"PPO parameter '{name}' must be at least {minimum}.")
        return value
    if name == "hidden_sizes":
        if not isinstance(value, (list, tuple)) or not value:
            raise ValueError("PPO parameter 'hidden_sizes' must be a non-empty array.")
        if any(
            not isinstance(size, int) or isinstance(size, bool) or size <= 0
            for size in value
        ):
            raise ValueError("PPO hidden_sizes values must be positive integers.")
        return tuple(value)
    if name == "policy_architecture":
        if value not in {"flat", "action_feature", "shared_enemy"}:
            raise ValueError(
                "PPO parameter 'policy_architecture' must be flat, action_feature, "
                "or shared_enemy."
            )
        return value
    raise ValueError(f"Unsupported PPO search-space parameter: {name}")


def _train_and_evaluate(
    *,
    policy: str,
    sampled_config: dict[str, Any],
    env_factory: Callable[[], CombatEnv],
    args: argparse.Namespace,
    train_seed: int | None,
    evaluation_seed: int | None,
) -> SeedRunSummary:
    """Train one configuration on one seed and return the held-out metrics."""
    result: TrainResult

    if policy == "q_learning":
        result = train_q_learning(
            env_factory=env_factory,
            episodes=args.episodes,
            evaluation_interval=args.evaluation_interval,
            evaluation_episodes=args.evaluation_episodes,
            seed=train_seed,
            final_evaluation_seed=evaluation_seed,
            learning_rate=sampled_config["learning_rate"],
            discount=sampled_config["discount"],
            epsilon=sampled_config["epsilon"],
            epsilon_min=sampled_config["epsilon_min"],
            epsilon_decay=sampled_config["epsilon_decay"],
        )
    elif policy == "dqn":
        result = train_dqn(
            env_factory=env_factory,
            episodes=args.episodes,
            evaluation_interval=args.evaluation_interval,
            evaluation_episodes=args.evaluation_episodes,
            replay_capacity=sampled_config["replay_capacity"],
            batch_size=sampled_config["batch_size"],
            warmup_steps=sampled_config["warmup_steps"],
            train_frequency=sampled_config["train_frequency"],
            gradient_steps=sampled_config["gradient_steps"],
            target_update_interval=sampled_config["target_update_interval"],
            hidden_sizes=sampled_config["hidden_sizes"],
            seed=train_seed,
            final_evaluation_seed=evaluation_seed,
            learning_rate=sampled_config["learning_rate"],
            discount=sampled_config["discount"],
            epsilon=sampled_config["epsilon"],
            epsilon_min=sampled_config["epsilon_min"],
            epsilon_decay=sampled_config["epsilon_decay"],
            gradient_clip=sampled_config["gradient_clip"],
            architecture=sampled_config["architecture"],
            device=args.device,
            restore_best_checkpoint=args.restore_best_checkpoint,
        )
    elif policy == "double_dqn":
        result = train_double_dqn(
            env_factory=env_factory,
            episodes=args.episodes,
            evaluation_interval=args.evaluation_interval,
            evaluation_episodes=args.evaluation_episodes,
            replay_capacity=sampled_config["replay_capacity"],
            batch_size=sampled_config["batch_size"],
            warmup_steps=sampled_config["warmup_steps"],
            train_frequency=sampled_config["train_frequency"],
            gradient_steps=sampled_config["gradient_steps"],
            target_update_interval=sampled_config["target_update_interval"],
            hidden_sizes=sampled_config["hidden_sizes"],
            seed=train_seed,
            final_evaluation_seed=evaluation_seed,
            learning_rate=sampled_config["learning_rate"],
            discount=sampled_config["discount"],
            epsilon=sampled_config["epsilon"],
            epsilon_min=sampled_config["epsilon_min"],
            epsilon_decay=sampled_config["epsilon_decay"],
            gradient_clip=sampled_config["gradient_clip"],
            architecture=sampled_config["architecture"],
            device=args.device,
            restore_best_checkpoint=args.restore_best_checkpoint,
        )
    elif policy == "dueling_double_dqn":
        result = train_dueling_double_dqn(
            env_factory=env_factory,
            episodes=args.episodes,
            evaluation_interval=args.evaluation_interval,
            evaluation_episodes=args.evaluation_episodes,
            replay_capacity=sampled_config["replay_capacity"],
            batch_size=sampled_config["batch_size"],
            warmup_steps=sampled_config["warmup_steps"],
            train_frequency=sampled_config["train_frequency"],
            gradient_steps=sampled_config["gradient_steps"],
            target_update_interval=sampled_config["target_update_interval"],
            hidden_sizes=sampled_config["hidden_sizes"],
            seed=train_seed,
            final_evaluation_seed=evaluation_seed,
            learning_rate=sampled_config["learning_rate"],
            discount=sampled_config["discount"],
            epsilon=sampled_config["epsilon"],
            epsilon_min=sampled_config["epsilon_min"],
            epsilon_decay=sampled_config["epsilon_decay"],
            gradient_clip=sampled_config["gradient_clip"],
            architecture=sampled_config["architecture"],
            device=args.device,
            restore_best_checkpoint=args.restore_best_checkpoint,
        )
    elif policy == "masked_ppo":
        result = train_masked_ppo(
            env_factory=env_factory,
            episodes=args.episodes,
            evaluation_interval=args.evaluation_interval,
            evaluation_episodes=args.evaluation_episodes,
            rollout_steps=sampled_config["rollout_steps"],
            num_envs=sampled_config["num_envs"],
            env_workers=sampled_config["env_workers"],
            hidden_sizes=sampled_config["hidden_sizes"],
            seed=train_seed,
            final_evaluation_seed=evaluation_seed,
            learning_rate=sampled_config["learning_rate"],
            discount=sampled_config["discount"],
            gae_lambda=sampled_config["gae_lambda"],
            clip_ratio=sampled_config["clip_ratio"],
            value_loss_coef=sampled_config["value_loss_coef"],
            entropy_coef=sampled_config["entropy_coef"],
            ppo_epochs=sampled_config["ppo_epochs"],
            minibatch_size=sampled_config["minibatch_size"],
            max_grad_norm=sampled_config["max_grad_norm"],
            policy_architecture=sampled_config["policy_architecture"],
            device=args.device,
            restore_best_checkpoint=args.restore_best_checkpoint,
        )
    else:
        raise ValueError(f"Unsupported policy for sweep: {policy}")

    stats = result.final_evaluation
    return SeedRunSummary(
        train_seed=train_seed,
        evaluation_seed=evaluation_seed,
        score=score_evaluation(
            stats,
            metric=args.metric,
            player_max_hp=args.player_hp,
            hp_weight=args.hp_weight,
        ),
        mean_reward=stats.mean_reward,
        win_rate=stats.win_rate,
        mean_steps=stats.mean_steps,
        mean_player_hp=stats.mean_player_hp,
    )


def _aggregate_seed_summaries(seed_summaries: Sequence[SeedRunSummary]) -> dict[str, float]:
    """Average per-seed metrics into one trial summary."""
    if not seed_summaries:
        raise ValueError("seed_summaries cannot be empty.")
    return {
        "score": mean(summary.score for summary in seed_summaries),
        "mean_reward": mean(summary.mean_reward for summary in seed_summaries),
        "win_rate": mean(summary.win_rate for summary in seed_summaries),
        "mean_steps": mean(summary.mean_steps for summary in seed_summaries),
        "mean_player_hp": mean(summary.mean_player_hp for summary in seed_summaries),
    }


def _build_sampler(args: argparse.Namespace, *, worker_index: int = 0) -> Any:
    """Create a sampler with a stable, distinct RNG stream per process worker."""
    sampler_seed = args.seed + worker_index * TRIAL_WORKER_SEED_STRIDE
    if args.sampler == "random":
        return RandomSampler(seed=sampler_seed)
    return TPESampler(seed=sampler_seed)


def _build_pruner(args: argparse.Namespace) -> Any:
    """Create the configured Optuna pruner."""
    if args.pruner == "median":
        return MedianPruner(n_startup_trials=5, n_warmup_steps=1)
    if args.pruner == "successive_halving":
        return SuccessiveHalvingPruner(min_resource=1)
    return NopPruner()


def _ensure_optuna_available() -> None:
    """Raise a friendly error if Optuna is missing."""
    if optuna is not None:
        return
    raise ModuleNotFoundError(
        "Hyperparameter sweeps require the optional dependency 'optuna'. "
        "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
    )


def _ensure_policy_dependencies(policy: str) -> None:
    """Raise a friendly error if the chosen policy is missing required deps."""
    if policy in {"dqn", "double_dqn", "dueling_double_dqn"} and dqn_module.torch is None:
        raise ModuleNotFoundError(
            "DQN-family sweeps require the optional dependency 'torch'. "
            "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
        )
    if policy == "masked_ppo" and ppo_module.torch is None:
        raise ModuleNotFoundError(
            "Masked PPO sweeps require the optional dependency 'torch'. "
            "Install it with `pip install -r requirements.txt` or `pip install -e .[rl]`."
        )


def _serialize_trial(trial: FrozenTrial) -> dict[str, Any]:
    """Return a JSON-safe trial summary."""
    return {
        "number": trial.number,
        "state": getattr(trial.state, "name", str(trial.state)),
        "value": trial.value,
        "params": _to_json_ready(trial.params),
        "user_attrs": _to_json_ready(trial.user_attrs),
    }


def _to_json_ready(value: Any) -> Any:
    """Recursively convert tuples and paths into JSON-safe objects."""
    if isinstance(value, dict):
        return {str(key): _to_json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_to_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _format_params(params: dict[str, Any]) -> str:
    """Format params compactly for CLI logging."""
    return ", ".join(
        f"{key}={_format_param_value(value)}"
        for key, value in sorted(_to_json_ready(params).items())
    )


def _format_param_value(value: Any) -> str:
    """Round floats for logs without changing stored or trained values."""
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, list):
        return "[" + ", ".join(_format_param_value(item) for item in value) + "]"
    if isinstance(value, dict):
        entries = (
            f"{key}: {_format_param_value(item)}"
            for key, item in sorted(value.items())
        )
        return "{" + ", ".join(entries) + "}"
    return str(value)


if __name__ == "__main__":
    main()
