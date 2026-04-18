"""Optuna-based hyperparameter sweep CLI for RL agents."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Sequence, TypeAlias

import game.dqn as dqn_module
import game.ppo as ppo_module
from game import CombatEnv, SimpleEnemy, build_overgrowth_easy_encounter
from game.baselines import EvaluationStats, TrainingResult, train_q_learning
from game.dqn import DQNTrainingResult, train_double_dqn, train_dqn, train_dueling_double_dqn
from game.ppo import PPOTrainingResult, train_masked_ppo

try:
    import optuna
    from optuna.pruners import MedianPruner, NopPruner, SuccessiveHalvingPruner
    from optuna.samplers import RandomSampler, TPESampler
    from optuna.trial import FrozenTrial, Trial
except ModuleNotFoundError:  # pragma: no cover - depends on optional dependency
    optuna = None
    MedianPruner = Any
    NopPruner = Any
    SuccessiveHalvingPruner = Any
    RandomSampler = Any
    TPESampler = Any
    FrozenTrial = Any
    Trial = Any

TrainResult: TypeAlias = TrainingResult | DQNTrainingResult | PPOTrainingResult

TRAIN_SEED_STRIDE = 1_000
EVALUATION_SEED_OFFSET = 100_000

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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the sweep entry point."""
    parser = argparse.ArgumentParser(
        description="Run an Optuna-based hyperparameter sweep over the RL trainers."
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
        help="Number of Optuna trials to run.",
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
        help="Optional Optuna storage URL, for example sqlite:///sweeps/double_dqn.db",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional JSON path for saving the best-trial summary.",
    )
    parser.add_argument(
        "--encounter-set",
        choices=("simple", "overgrowth_easy"),
        default="simple",
        help="Encounter pool used during the sweep.",
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
        choices=("flat", "action_feature"),
        default="action_feature",
        help="Fixed PPO policy head used during the sweep.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Torch device for neural agents, for example `cpu` or `cuda`.",
    )
    parser.add_argument(
        "--restore-best-checkpoint",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Restore the best checkpoint before final evaluation for DQN-family and PPO.",
    )
    return parser.parse_args(argv)


def make_env_factory(
    args: argparse.Namespace,
    *,
    hp_loss_penalty_scale: float,
    incoming_damage_shaping_scale: float,
) -> Callable[[], CombatEnv]:
    """Create an env factory for one sampled reward-shaping setup."""
    if args.encounter_set == "overgrowth_easy":
        return lambda: CombatEnv(
            player_max_hp=args.player_hp,
            cards_per_turn=args.cards_per_turn,
            encounter_factory=build_overgrowth_easy_encounter,
            max_enemy_count=3,
            hp_loss_penalty_scale=hp_loss_penalty_scale,
            incoming_damage_shaping_scale=incoming_damage_shaping_scale,
            record_trajectory=False,
        )

    return lambda: CombatEnv(
        player_max_hp=args.player_hp,
        cards_per_turn=args.cards_per_turn,
        enemy_factory=lambda: SimpleEnemy(max_hp=args.enemy_hp),
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

    if args.trials <= 0:
        raise ValueError("trials must be positive.")
    if args.episodes <= 0:
        raise ValueError("episodes must be positive.")
    if args.evaluation_episodes <= 0:
        raise ValueError("evaluation-episodes must be positive.")
    if args.evaluation_interval < 0:
        raise ValueError("evaluation-interval cannot be negative.")
    if args.top_k <= 0:
        raise ValueError("top-k must be positive.")

    assert optuna is not None
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    train_seeds = resolve_train_seeds(args.seed, args.train_seeds)
    evaluation_seeds = resolve_evaluation_seeds(args.seed, args.train_seeds)
    sampler = _build_sampler(args)
    pruner = _build_pruner(args)
    study = optuna.create_study(
        study_name=args.study_name or f"sts_agent_{args.policy}_sweep",
        storage=args.storage,
        load_if_exists=args.storage is not None,
        sampler=sampler,
        pruner=pruner,
        direction="maximize",
    )

    def objective(trial: Trial) -> float:
        sampled_config = _sample_trial_config(trial, args)
        env_factory = make_env_factory(
            args,
            hp_loss_penalty_scale=sampled_config["hp_loss_penalty_scale"],
            incoming_damage_shaping_scale=sampled_config["incoming_damage_shaping_scale"],
        )
        seed_summaries: list[SeedRunSummary] = []

        for seed_index, (train_seed, evaluation_seed) in enumerate(
            zip(train_seeds, evaluation_seeds)
        ):
            seed_summary = _train_and_evaluate(
                policy=args.policy,
                sampled_config=sampled_config,
                env_factory=env_factory,
                args=args,
                train_seed=train_seed,
                evaluation_seed=evaluation_seed,
            )
            seed_summaries.append(seed_summary)

            mean_score = mean(summary.score for summary in seed_summaries)
            trial.report(mean_score, step=seed_index + 1)
            if args.pruner != "none" and trial.should_prune():
                trial.set_user_attr(
                    "seed_runs",
                    [asdict(summary) for summary in seed_summaries],
                )
                raise optuna.TrialPruned()

        aggregate = _aggregate_seed_summaries(seed_summaries)
        trial.set_user_attr("seed_runs", [asdict(summary) for summary in seed_summaries])
        for key, value in aggregate.items():
            trial.set_user_attr(key, value)
        trial.set_user_attr("sampled_config", _to_json_ready(sampled_config))

        print(
            f"[trial {trial.number:03d}] "
            f"score={aggregate['score']:.4f} "
            f"win_rate={aggregate['win_rate']:.4f} "
            f"mean_reward={aggregate['mean_reward']:.4f} "
            f"mean_hp={aggregate['mean_player_hp']:.2f} "
            f"params={_format_params(sampled_config)}",
            flush=True,
        )
        return float(aggregate["score"])

    study.optimize(
        objective,
        n_trials=args.trials,
        timeout=args.timeout_seconds,
        gc_after_trial=True,
    )

    completed_trials = [
        trial for trial in study.trials if getattr(trial.state, "name", str(trial.state)) == "COMPLETE"
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
        "trials_completed": len(completed_trials),
        "encounter_set": args.encounter_set,
        "episodes": args.episodes,
        "evaluation_episodes": args.evaluation_episodes,
        "train_seeds": list(train_seeds),
        "evaluation_seeds": list(evaluation_seeds),
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
    run_sweep(args)


def _sample_trial_config(trial: Trial, args: argparse.Namespace) -> dict[str, Any]:
    """Sample one trial configuration for the chosen policy family."""
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

    if args.policy == "masked_ppo":
        hidden_sizes_key = trial.suggest_categorical(
            "hidden_sizes",
            tuple(PPO_HIDDEN_SIZE_CHOICES),
        )
        config.update(
            learning_rate=trial.suggest_float("learning_rate", 1e-4, 1e-3, log=True),
            discount=trial.suggest_float("discount", 0.985, 0.9995),
            gae_lambda=trial.suggest_float("gae_lambda", 0.9, 0.99),
            clip_ratio=trial.suggest_float("clip_ratio", 0.1, 0.3),
            value_loss_coef=trial.suggest_float("value_loss_coef", 0.25, 1.0),
            entropy_coef=trial.suggest_float("entropy_coef", 1e-4, 5e-2, log=True),
            rollout_steps=trial.suggest_categorical("rollout_steps", (256, 512, 1024)),
            ppo_epochs=trial.suggest_categorical("ppo_epochs", (3, 4, 6, 8)),
            minibatch_size=trial.suggest_categorical("minibatch_size", (32, 64, 128)),
            hidden_sizes=PPO_HIDDEN_SIZE_CHOICES[hidden_sizes_key],
            policy_architecture=args.ppo_policy_architecture,
            max_grad_norm=0.5,
        )
        return config

    raise ValueError(f"Unsupported policy for sweep: {args.policy}")


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


def _build_sampler(args: argparse.Namespace) -> Any:
    """Create the configured Optuna sampler."""
    if args.sampler == "random":
        return RandomSampler(seed=args.seed)
    return TPESampler(seed=args.seed)


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
        f"{key}={value}"
        for key, value in sorted(_to_json_ready(params).items())
    )


if __name__ == "__main__":
    main()
