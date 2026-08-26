"""Training and evaluation CLI for baseline RL experiments."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from json import JSONDecodeError
import platform
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter
from typing import Any, Callable, Sequence

from game.simulation.core import CombatEnv
from game.agents.agent_io import CHECKPOINT_FORMAT_VERSION, save_agent
from game.agents.baselines import (
    EvaluationStats,
    TrainingProgress,
    TrainingResult,
    choose_heuristic_action,
    choose_random_action,
    evaluate_policy,
    train_q_learning,
)
from game.agents.dqn import (
    DQNTrainingResult,
    train_double_dqn,
    train_dqn,
    train_dueling_double_dqn,
)
from game.simulation.env_factory import CombatEnvFactory
from game.agents.ppo import PPOTrainingResult, train_masked_ppo
from game.training.profile import TrainingProfiler, print_training_profile

DEFAULT_Q_LEARNING_RATE = 0.1
DEFAULT_DQN_LEARNING_RATE = 1e-3
DEFAULT_PPO_LEARNING_RATE = 3e-4


def parse_hidden_sizes(value: str | Sequence[int]) -> tuple[int, ...]:
    """Parse hidden sizes from CLI text or a JSON array."""
    if isinstance(value, str):
        raw_values: Sequence[str | int] = tuple(
            part.strip() for part in value.split(",") if part.strip()
        )
    elif isinstance(value, Sequence):
        raw_values = value
        if any(
            not isinstance(raw_value, int) or isinstance(raw_value, bool)
            for raw_value in raw_values
        ):
            raise ValueError("hidden_sizes array values must be positive integers.")
    else:
        raise ValueError("hidden_sizes must be a comma-separated string or an array.")

    if not raw_values:
        raise ValueError("hidden_sizes must contain at least one integer.")
    if any(isinstance(raw_value, bool) for raw_value in raw_values):
        raise ValueError("hidden_sizes values must be positive integers.")

    try:
        hidden_sizes = tuple(int(raw_value) for raw_value in raw_values)
    except (TypeError, ValueError) as exc:
        raise ValueError("hidden_sizes values must be positive integers.") from exc
    if any(hidden_size <= 0 for hidden_size in hidden_sizes):
        raise ValueError("hidden_sizes values must be positive integers.")
    return hidden_sizes


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build the training parser so config defaults and CLI parsing share a schema."""
    parser = argparse.ArgumentParser(
        description="Run baseline training or evaluation on the combat simulator."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help=(
            "Optional JSON configuration file. Explicit CLI arguments override "
            "values loaded from the file."
        ),
    )
    parser.add_argument(
        "--resolved-config-out",
        type=str,
        default=None,
        help="Optional path for writing the fully resolved JSON configuration.",
    )
    parser.add_argument(
        "--print-config",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Print the fully resolved configuration before running.",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for training and baseline evaluation."""
    parser = _build_argument_parser()
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
            "compare",
        ),
        default="compare",
        help="Which baseline workflow to run.",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=500,
        help="Training episodes for q_learning or evaluation episodes otherwise.",
    )
    parser.add_argument(
        "--eval-episodes",
        type=int,
        default=100,
        help="Evaluation episodes per checkpoint and for final evaluation.",
    )
    parser.add_argument(
        "--eval-interval",
        type=int,
        default=100,
        help="Checkpoint interval for q_learning evaluation. Use 0 to disable checkpoint evals.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Base seed for deterministic training and evaluation.",
    )
    parser.add_argument(
        "--encounter-set",
        choices=("simple", "overgrowth_easy"),
        default="overgrowth_easy",
        help="Encounter pool to train or evaluate against.",
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
        "--learning-rate",
        type=float,
        default=None,
        help="Optional shared learning-rate override applied to q_learning, DQN, and PPO.",
    )
    parser.add_argument(
        "--q-learning-rate",
        type=float,
        default=DEFAULT_Q_LEARNING_RATE,
        help="Learning rate for q_learning when --learning-rate is not provided.",
    )
    parser.add_argument(
        "--dqn-learning-rate",
        type=float,
        default=DEFAULT_DQN_LEARNING_RATE,
        help="Learning rate for DQN and Double DQN when --learning-rate is not provided.",
    )
    parser.add_argument(
        "--ppo-learning-rate",
        type=float,
        default=DEFAULT_PPO_LEARNING_RATE,
        help="Learning rate for masked PPO when --learning-rate is not provided.",
    )
    parser.add_argument(
        "--discount",
        type=float,
        default=0.99,
        help="Discount factor for q_learning, dqn, and masked_ppo.",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=1.0,
        help="Initial epsilon for q_learning and dqn exploration.",
    )
    parser.add_argument(
        "--epsilon-min",
        type=float,
        default=0.05,
        help="Minimum epsilon for q_learning and dqn exploration.",
    )
    parser.add_argument(
        "--epsilon-decay",
        type=float,
        default=0.995,
        help="Multiplicative epsilon decay applied after each episode.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Mini-batch size for DQN optimization.",
    )
    parser.add_argument(
        "--replay-capacity",
        type=int,
        default=20000,
        help="Replay buffer capacity for DQN training.",
    )
    parser.add_argument(
        "--warmup-steps",
        type=int,
        default=250,
        help="Environment steps collected before DQN optimization begins.",
    )
    parser.add_argument(
        "--train-frequency",
        type=int,
        default=4,
        help="Run DQN optimization every N environment steps.",
    )
    parser.add_argument(
        "--gradient-steps",
        type=int,
        default=1,
        help="Number of DQN optimizer updates each time training is triggered.",
    )
    parser.add_argument(
        "--target-update-interval",
        type=int,
        default=100,
        help="Number of DQN optimization steps between target network syncs.",
    )
    parser.add_argument(
        "--hidden-sizes",
        type=parse_hidden_sizes,
        default=(128, 128),
        help=(
            "Comma-separated hidden layer sizes for neural agents. JSON configs "
            "may use an integer array."
        ),
    )
    parser.add_argument(
        "--dqn-architecture",
        choices=("flat", "action_feature"),
        default="action_feature",
        help="Q-network architecture used by DQN-family agents.",
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
        help="Restore the best evaluation checkpoint before the final DQN evaluation.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=25,
        help="Episodes between live training progress updates.",
    )
    parser.add_argument(
        "--progress-window",
        type=int,
        default=25,
        help="Number of recent episodes used for rolling progress statistics.",
    )
    parser.add_argument(
        "--save-agent",
        type=str,
        default=None,
        help=(
            "Legacy output file for a trained agent. Prefer --output-dir for a "
            "self-contained run directory."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=(
            "Base directory where a unique run folder containing checkpoint, "
            "config.json, and run.json is created."
        ),
    )
    parser.add_argument(
        "--record-trajectories",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Store full per-step episode histories inside training environments.",
    )
    parser.add_argument(
        "--profile-training",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Collect synchronized PPO phase timings and resource diagnostics. "
            "Profiling adds overhead and is intended for diagnostic runs."
        ),
    )
    parser.add_argument(
        "--profile-out",
        type=str,
        default=None,
        help=(
            "Optional explicit JSON path for the training profile. Supplying it "
            "also enables profiling."
        ),
    )
    parser.add_argument(
        "--rollout-steps",
        type=int,
        default=512,
        help="Total on-policy transitions collected across all PPO environments per update.",
    )
    parser.add_argument(
        "--num-envs",
        type=int,
        default=1,
        help="Number of independent environments used for batched PPO rollout collection.",
    )
    parser.add_argument(
        "--env-workers",
        type=int,
        default=0,
        help=(
            "Persistent CPU simulator worker processes for PPO. Use 0 for the "
            "existing in-process collector."
        ),
    )
    parser.add_argument(
        "--ppo-epochs",
        type=int,
        default=4,
        help="Number of PPO optimization epochs per rollout.",
    )
    parser.add_argument(
        "--ppo-minibatch-size",
        type=int,
        default=64,
        help="Mini-batch size for PPO optimization.",
    )
    parser.add_argument(
        "--gae-lambda",
        type=float,
        default=0.95,
        help="GAE lambda used by masked PPO.",
    )
    parser.add_argument(
        "--clip-ratio",
        type=float,
        default=0.2,
        help="PPO clipping ratio for policy updates.",
    )
    parser.add_argument(
        "--value-loss-coef",
        type=float,
        default=0.5,
        help="Multiplier for the PPO value loss term.",
    )
    parser.add_argument(
        "--entropy-coef",
        type=float,
        default=0.01,
        help="Entropy bonus coefficient for PPO.",
    )
    parser.add_argument(
        "--max-grad-norm",
        type=float,
        default=0.5,
        help="Gradient clipping norm for PPO updates.",
    )
    parser.add_argument(
        "--ppo-policy-architecture",
        choices=("flat", "action_feature", "shared_enemy"),
        default="action_feature",
        help=(
            "Policy head used by masked PPO. shared_enemy applies one encoder to "
            "every enemy and removes raw target-slot position from policy scoring."
        ),
    )
    config_path = _find_config_path(argv)
    if config_path is not None:
        try:
            parser.set_defaults(**_load_config_defaults(parser, config_path))
        except (OSError, JSONDecodeError, ValueError) as exc:
            parser.error(str(exc))
    return parser.parse_args(argv)


def _find_config_path(argv: Sequence[str] | None) -> str | None:
    """Read only --config before parsing the full CLI."""
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=str, default=None)
    config_args, _unknown = config_parser.parse_known_args(argv)
    return config_args.config


def _load_config_defaults(
    parser: argparse.ArgumentParser,
    config_path: str,
) -> dict[str, Any]:
    """Load and validate JSON values against the training CLI schema."""
    path = Path(config_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Training config {path} must contain a JSON object.")
    if "config" in payload:
        raise ValueError("Training config files cannot include the recursive 'config' key.")

    actions_by_dest = {
        action.dest: action
        for action in parser._actions
        if action.dest not in {"help", "config"}
    }
    unknown_keys = sorted(set(payload) - set(actions_by_dest))
    if unknown_keys:
        keys = ", ".join(unknown_keys)
        raise ValueError(
            f"Unknown training config key(s): {keys}. Use snake_case CLI destination names."
        )

    return {
        key: _coerce_config_value(actions_by_dest[key], value)
        for key, value in payload.items()
    }


def _coerce_config_value(action: argparse.Action, value: Any) -> Any:
    """Apply argparse-equivalent type and choice validation to one JSON value."""
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
        raise ValueError(
            f"Config key '{action.dest}' must be one of: {choices}."
        )
    return converted


def resolved_training_config(args: argparse.Namespace) -> dict[str, Any]:
    """Return the effective, JSON-serializable configuration for this run."""
    resolved: dict[str, Any] = {}
    for key, value in vars(args).items():
        if key == "config":
            continue
        resolved[key] = list(value) if isinstance(value, tuple) else value
    return dict(sorted(resolved.items()))


def write_training_config(config: dict[str, Any], path: str | Path) -> Path:
    """Write a reusable resolved training configuration."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def agent_config_sidecar_path(agent_path: str | Path) -> Path:
    """Return the readable resolved-config path stored beside an agent."""
    path = Path(agent_path)
    return path.with_suffix(".config.json")


def agent_run_sidecar_path(agent_path: str | Path) -> Path:
    """Return the readable run-metadata path stored beside an agent."""
    path = Path(agent_path)
    return path.with_suffix(".run.json")


def agent_profile_sidecar_path(agent_path: str | Path) -> Path:
    """Return the profiling path stored beside a legacy agent file."""
    path = Path(agent_path)
    return path.with_suffix(".profile.json")


def create_run_directory(
    output_dir: str | Path,
    *,
    policy: str,
    seed: int,
    started_at: datetime,
) -> tuple[str, Path]:
    """Create one collision-resistant directory for a completed training run."""
    timestamp = started_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{timestamp}-{policy}-seed-{seed}"
    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def build_run_metadata(
    result: TrainingResult | DQNTrainingResult | PPOTrainingResult,
    *,
    started_at: datetime,
    started_perf_counter: float,
    config_source: str | None,
) -> dict[str, Any]:
    """Describe the code, runtime, and completed work behind one trained agent."""
    completed_at = datetime.now(timezone.utc)
    agent = result.agent
    best_evaluation = getattr(result, "best_evaluation", None)
    torch_version: str | None = None
    if hasattr(agent, "device"):
        try:
            import torch
        except ModuleNotFoundError:
            pass
        else:
            torch_version = str(torch.__version__)

    git_commit, git_dirty = _git_revision()
    return {
        "started_at": _format_utc_timestamp(started_at),
        "completed_at": _format_utc_timestamp(completed_at),
        "duration_seconds": round(perf_counter() - started_perf_counter, 6),
        "episodes_completed": len(result.training_metrics),
        "environment_steps": sum(metric.steps for metric in result.training_metrics),
        "optimization_steps": int(getattr(result, "optimization_steps", 0)),
        "best_evaluation_episode": (
            None if best_evaluation is None else int(best_evaluation.episode)
        ),
        "restored_best_checkpoint": bool(
            getattr(result, "restored_best_checkpoint", False)
        ),
        "device": (
            None if not hasattr(agent, "device") else str(getattr(agent, "device"))
        ),
        "python_version": platform.python_version(),
        "torch_version": torch_version,
        "platform": platform.system(),
        "machine": platform.machine(),
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "config_source": config_source,
    }


def build_training_summary(
    result: TrainingResult | DQNTrainingResult | PPOTrainingResult,
) -> dict[str, Any]:
    """Build a compact JSON-safe outcome summary without episode trajectories."""
    metrics = result.training_metrics
    summary = _json_safe(result.as_dict())
    assert isinstance(summary, dict)
    summary["training_aggregate"] = {
        "mean_reward": mean(metric.total_reward for metric in metrics),
        "win_rate": mean(1.0 if metric.win else 0.0 for metric in metrics),
        "mean_steps": mean(metric.steps for metric in metrics),
        "mean_player_hp": mean(metric.player_hp for metric in metrics),
    }
    return summary


def _json_safe(value: Any) -> Any:
    """Convert compact result values such as torch.device into JSON-safe data."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _format_utc_timestamp(value: datetime) -> str:
    """Format an aware datetime as a compact UTC ISO-8601 timestamp."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_revision() -> tuple[str | None, bool | None]:
    """Return the current commit and dirty flag when running inside a Git worktree."""
    repo_root = Path(__file__).resolve().parent
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    if commit_result.returncode != 0 or status_result.returncode != 0:
        return None, None
    return commit_result.stdout.strip() or None, bool(status_result.stdout.strip())


def save_training_artifacts(
    result: TrainingResult | DQNTrainingResult | PPOTrainingResult,
    *,
    args: argparse.Namespace,
    label: str,
    training_config: dict[str, Any],
    run_metadata: dict[str, Any],
    training_summary: dict[str, Any],
) -> None:
    """Save one training run using the directory or legacy sidecar layout."""
    training_profile = getattr(result, "profile", None)
    if args.output_dir is not None:
        started_at = datetime.fromisoformat(
            run_metadata["started_at"].replace("Z", "+00:00")
        )
        run_id, run_dir = create_run_directory(
            args.output_dir,
            policy=args.policy,
            seed=args.seed,
            started_at=started_at,
        )
        checkpoint_name = (
            "checkpoint.json" if args.policy == "q_learning" else "checkpoint.pt"
        )
        agent_path = run_dir / checkpoint_name
        config_path = run_dir / "config.json"
        run_path = run_dir / "run.json"
        profile_path = None if training_profile is None else run_dir / "profile.json"
        artifact_layout = "run_directory"
        run_directory: str | None = str(run_dir)
    else:
        assert args.save_agent is not None
        agent_path = Path(args.save_agent)
        config_path = agent_config_sidecar_path(agent_path)
        run_path = agent_run_sidecar_path(agent_path)
        profile_path = (
            None
            if training_profile is None
            else agent_profile_sidecar_path(agent_path)
        )
        run_id = None
        run_directory = None
        artifact_layout = "legacy_sidecars"

    run_metadata = {
        **run_metadata,
        "artifact_layout": artifact_layout,
        "run_id": run_id,
        "run_directory": run_directory,
        "checkpoint_file": agent_path.name,
        "profile_file": None if profile_path is None else profile_path.name,
    }
    save_agent(
        result.agent,
        agent_path,
        training_config=training_config,
        run_metadata=run_metadata,
        training_summary=training_summary,
    )
    write_training_config(training_config, config_path)
    run_path.write_text(
        json.dumps(
            {
                "checkpoint_format_version": CHECKPOINT_FORMAT_VERSION,
                "training_config": training_config,
                "run_metadata": run_metadata,
                "training_summary": training_summary,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if profile_path is not None:
        assert training_profile is not None
        training_profile.write_json(profile_path)
    print(f"Saved {label} agent to {agent_path}")
    print(f"Saved resolved configuration to {config_path}")
    print(f"Saved run metadata to {run_path}")
    if profile_path is not None:
        print(f"Saved training profile to {profile_path}")


def make_env_factory(args: argparse.Namespace) -> Callable[[], CombatEnv]:
    """Build a deterministic env factory from CLI arguments."""
    return CombatEnvFactory(
        encounter_set=args.encounter_set,
        enemy_hp=args.enemy_hp,
        player_hp=args.player_hp,
        cards_per_turn=args.cards_per_turn,
        hp_loss_penalty_scale=args.hp_loss_penalty_scale,
        incoming_damage_shaping_scale=args.incoming_damage_shaping_scale,
        record_trajectory=args.record_trajectories,
    )


def print_evaluation(label: str, stats: EvaluationStats) -> None:
    """Print a compact evaluation summary."""
    stats_dict = stats.as_dict()
    print(
        f"{label}: "
        f"episodes={stats_dict['episodes']} "
        f"mean_reward={stats_dict['mean_reward']:.3f} "
        f"win_rate={stats_dict['win_rate']:.3f} "
        f"mean_steps={stats_dict['mean_steps']:.2f} "
        f"mean_player_hp={stats_dict['mean_player_hp']:.2f}"
    )


def print_training_summary(result: TrainingResult) -> None:
    """Print the main outputs of a Q-learning run."""
    training_rewards = [metric.total_reward for metric in result.training_metrics]
    training_wins = [1.0 if metric.win else 0.0 for metric in result.training_metrics]
    print(
        "Q-learning training: "
        f"episodes={len(result.training_metrics)} "
        f"mean_train_reward={mean(training_rewards):.3f} "
        f"train_win_rate={mean(training_wins):.3f} "
        f"final_epsilon={result.agent.epsilon:.3f} "
        f"q_table_size={len(result.agent.q_table)}"
    )
    for snapshot in result.evaluations:
        print_evaluation(f"  Eval @{snapshot.episode}", snapshot.stats)
    print_evaluation("  Final eval", result.final_evaluation)


def print_deep_value_summary(label: str, result: DQNTrainingResult) -> None:
    """Print the main outputs of a DQN-family training run."""
    training_rewards = [metric.total_reward for metric in result.training_metrics]
    training_wins = [1.0 if metric.win else 0.0 for metric in result.training_metrics]
    non_zero_losses = [loss for loss in result.mean_losses if loss > 0.0]
    mean_loss = mean(non_zero_losses) if non_zero_losses else 0.0
    print(
        f"{label} training: "
        f"episodes={len(result.training_metrics)} "
        f"mean_train_reward={mean(training_rewards):.3f} "
        f"train_win_rate={mean(training_wins):.3f} "
        f"mean_loss={mean_loss:.5f} "
        f"final_epsilon={result.agent.epsilon:.3f} "
        f"architecture={result.agent.architecture} "
        f"optimization_steps={result.optimization_steps} "
        f"device={result.agent.device} "
        f"restored_best={result.restored_best_checkpoint}"
    )
    for snapshot in result.evaluations:
        print_evaluation(f"  Eval @{snapshot.episode}", snapshot.stats)
    if result.best_evaluation is not None:
        print_evaluation(
            f"  Best eval @{result.best_evaluation.episode}",
            result.best_evaluation.stats,
        )
    print_evaluation("  Final eval", result.final_evaluation)


def print_ppo_summary(result: PPOTrainingResult) -> None:
    """Print the main outputs of a masked PPO training run."""
    training_rewards = [metric.total_reward for metric in result.training_metrics]
    training_wins = [1.0 if metric.win else 0.0 for metric in result.training_metrics]
    mean_total_loss = mean(result.mean_total_losses) if result.mean_total_losses else 0.0
    mean_policy_loss = mean(result.mean_policy_losses) if result.mean_policy_losses else 0.0
    mean_value_loss = mean(result.mean_value_losses) if result.mean_value_losses else 0.0
    mean_entropy = mean(result.mean_entropies) if result.mean_entropies else 0.0
    print(
        "Masked PPO training: "
        f"episodes={len(result.training_metrics)} "
        f"mean_train_reward={mean(training_rewards):.3f} "
        f"train_win_rate={mean(training_wins):.3f} "
        f"mean_total_loss={mean_total_loss:.5f} "
        f"mean_policy_loss={mean_policy_loss:.5f} "
        f"mean_value_loss={mean_value_loss:.5f} "
        f"mean_entropy={mean_entropy:.5f} "
        f"optimization_steps={result.optimization_steps} "
        f"num_envs={result.num_envs} "
        f"env_workers={result.env_workers} "
        f"policy_architecture={result.agent.policy_architecture} "
        f"device={result.agent.device} "
        f"restored_best={result.restored_best_checkpoint}"
    )
    for snapshot in result.evaluations:
        print_evaluation(f"  Eval @{snapshot.episode}", snapshot.stats)
    if result.best_evaluation is not None:
        print_evaluation(
            f"  Best eval @{result.best_evaluation.episode}",
            result.best_evaluation.stats,
        )
    print_evaluation("  Final eval", result.final_evaluation)


def resolve_q_learning_rate(args: argparse.Namespace) -> float:
    """Resolve the effective q-learning learning rate from CLI arguments."""
    if args.learning_rate is not None:
        return args.learning_rate
    return args.q_learning_rate


def resolve_dqn_learning_rate(args: argparse.Namespace) -> float:
    """Resolve the effective DQN-family learning rate from CLI arguments."""
    if args.learning_rate is not None:
        return args.learning_rate
    return args.dqn_learning_rate


def resolve_ppo_learning_rate(args: argparse.Namespace) -> float:
    """Resolve the effective PPO learning rate from CLI arguments."""
    if args.learning_rate is not None:
        return args.learning_rate
    return args.ppo_learning_rate


def format_duration(seconds: float) -> str:
    """Format a duration in seconds for compact CLI progress output."""
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def make_progress_reporter() -> Callable[[TrainingProgress], None]:
    """Create a CLI progress reporter for long-running training jobs."""

    def report(progress: TrainingProgress) -> None:
        loss_fragment = ""
        if progress.recent_mean_loss is not None:
            loss_fragment = f" loss={progress.recent_mean_loss:.5f}"

        print(
            f"[{progress.algorithm}] "
            f"{progress.episode}/{progress.total_episodes} "
            f"elapsed={format_duration(progress.elapsed_seconds)} "
            f"eta={format_duration(progress.eta_seconds)} "
            f"recent_reward={progress.recent_mean_reward:.3f} "
            f"recent_win_rate={progress.recent_win_rate:.3f} "
            f"recent_steps={progress.recent_mean_steps:.2f} "
            f"epsilon={progress.epsilon:.3f} "
            f"latest_reward={progress.latest_metrics.total_reward:.3f}"
            f"{loss_fragment} "
            f"evals={progress.evaluations_completed} "
            f"opt_steps={progress.optimization_steps}",
            flush=True,
        )

    return report


def main() -> None:
    """Run the selected baseline training or evaluation workflow."""
    args = parse_args()
    training_config = resolved_training_config(args)
    if args.print_config:
        print("Resolved training configuration:")
        print(json.dumps(training_config, indent=2, sort_keys=True))
    if args.resolved_config_out is not None:
        output_path = write_training_config(training_config, args.resolved_config_out)
        print(f"Wrote resolved training configuration to {output_path}")

    if args.save_agent is not None and args.output_dir is not None:
        raise SystemExit("--save-agent and --output-dir cannot be used together.")
    if (args.profile_training or args.profile_out is not None) and args.policy != "masked_ppo":
        raise SystemExit("Training phase profiling currently supports --policy masked_ppo.")
    saves_training_artifacts = args.save_agent is not None or args.output_dir is not None
    if saves_training_artifacts and args.policy not in {
        "q_learning",
        "dqn",
        "double_dqn",
        "dueling_double_dqn",
        "masked_ppo",
    }:
        raise SystemExit(
            "Saving artifacts is only supported for q_learning, dqn, double_dqn, "
            "dueling_double_dqn, or masked_ppo."
        )

    env_factory = make_env_factory(args)
    hidden_sizes = args.hidden_sizes
    progress_reporter = make_progress_reporter()
    q_learning_rate = resolve_q_learning_rate(args)
    dqn_learning_rate = resolve_dqn_learning_rate(args)
    ppo_learning_rate = resolve_ppo_learning_rate(args)

    if args.policy in {"random", "compare"}:
        random_stats = evaluate_policy(
            env_factory=env_factory,
            policy=lambda env, obs, mask: choose_random_action(
                env,
                obs,
                mask,
                rng=env.rng,
            ),
            episodes=args.eval_episodes if args.policy == "compare" else args.episodes,
            seed=args.seed,
        )
        print_evaluation("Random policy", random_stats)

    if args.policy in {"heuristic", "compare"}:
        heuristic_stats = evaluate_policy(
            env_factory=env_factory,
            policy=choose_heuristic_action,
            episodes=args.eval_episodes if args.policy == "compare" else args.episodes,
            seed=args.seed,
        )
        print_evaluation("Heuristic policy", heuristic_stats)

    if args.policy in {"q_learning", "compare"}:
        run_started_at = datetime.now(timezone.utc)
        run_started_perf_counter = perf_counter()
        result = train_q_learning(
            env_factory=env_factory,
            episodes=args.episodes,
            evaluation_interval=args.eval_interval,
            evaluation_episodes=args.eval_episodes,
            seed=args.seed,
            learning_rate=q_learning_rate,
            discount=args.discount,
            epsilon=args.epsilon,
            epsilon_min=args.epsilon_min,
            epsilon_decay=args.epsilon_decay,
            progress_callback=progress_reporter,
            progress_interval=args.progress_interval,
            progress_window=args.progress_window,
        )
        print_training_summary(result)
        if saves_training_artifacts:
            save_training_artifacts(
                result,
                args=args,
                label="q_learning",
                training_config=training_config,
                run_metadata=build_run_metadata(
                    result,
                    started_at=run_started_at,
                    started_perf_counter=run_started_perf_counter,
                    config_source=args.config,
                ),
                training_summary=build_training_summary(result),
            )

    if args.policy in {"dqn", "compare"}:
        run_started_at = datetime.now(timezone.utc)
        run_started_perf_counter = perf_counter()
        try:
            dqn_result = train_dqn(
                env_factory=env_factory,
                episodes=args.episodes,
                evaluation_interval=args.eval_interval,
                evaluation_episodes=args.eval_episodes,
                replay_capacity=args.replay_capacity,
                batch_size=args.batch_size,
                warmup_steps=args.warmup_steps,
                train_frequency=args.train_frequency,
                gradient_steps=args.gradient_steps,
                target_update_interval=args.target_update_interval,
                hidden_sizes=hidden_sizes,
                seed=args.seed,
                learning_rate=dqn_learning_rate,
                discount=args.discount,
                epsilon=args.epsilon,
                epsilon_min=args.epsilon_min,
                epsilon_decay=args.epsilon_decay,
                device=args.device,
                architecture=args.dqn_architecture,
                restore_best_checkpoint=args.restore_best_checkpoint,
                progress_callback=progress_reporter,
                progress_interval=args.progress_interval,
                progress_window=args.progress_window,
            )
        except ModuleNotFoundError as exc:
            if args.policy == "dqn":
                print(f"DQN unavailable: {exc}")
                raise SystemExit(1)
            print(f"DQN unavailable: {exc}")
        else:
            print_deep_value_summary("DQN", dqn_result)
            if saves_training_artifacts:
                save_training_artifacts(
                    dqn_result,
                    args=args,
                    label="DQN",
                    training_config=training_config,
                    run_metadata=build_run_metadata(
                        dqn_result,
                        started_at=run_started_at,
                        started_perf_counter=run_started_perf_counter,
                        config_source=args.config,
                    ),
                    training_summary=build_training_summary(dqn_result),
                )

    if args.policy in {"double_dqn", "compare"}:
        run_started_at = datetime.now(timezone.utc)
        run_started_perf_counter = perf_counter()
        try:
            double_dqn_result = train_double_dqn(
                env_factory=env_factory,
                episodes=args.episodes,
                evaluation_interval=args.eval_interval,
                evaluation_episodes=args.eval_episodes,
                replay_capacity=args.replay_capacity,
                batch_size=args.batch_size,
                warmup_steps=args.warmup_steps,
                train_frequency=args.train_frequency,
                gradient_steps=args.gradient_steps,
                target_update_interval=args.target_update_interval,
                hidden_sizes=hidden_sizes,
                seed=args.seed,
                learning_rate=dqn_learning_rate,
                discount=args.discount,
                epsilon=args.epsilon,
                epsilon_min=args.epsilon_min,
                epsilon_decay=args.epsilon_decay,
                device=args.device,
                architecture=args.dqn_architecture,
                restore_best_checkpoint=args.restore_best_checkpoint,
                progress_callback=progress_reporter,
                progress_interval=args.progress_interval,
                progress_window=args.progress_window,
            )
        except ModuleNotFoundError as exc:
            if args.policy == "double_dqn":
                print(f"Double DQN unavailable: {exc}")
                raise SystemExit(1)
            print(f"Double DQN unavailable: {exc}")
        else:
            print_deep_value_summary("Double DQN", double_dqn_result)
            if saves_training_artifacts:
                save_training_artifacts(
                    double_dqn_result,
                    args=args,
                    label="Double DQN",
                    training_config=training_config,
                    run_metadata=build_run_metadata(
                        double_dqn_result,
                        started_at=run_started_at,
                        started_perf_counter=run_started_perf_counter,
                        config_source=args.config,
                    ),
                    training_summary=build_training_summary(double_dqn_result),
                )

    if args.policy == "dueling_double_dqn":
        run_started_at = datetime.now(timezone.utc)
        run_started_perf_counter = perf_counter()
        try:
            dueling_double_dqn_result = train_dueling_double_dqn(
                env_factory=env_factory,
                episodes=args.episodes,
                evaluation_interval=args.eval_interval,
                evaluation_episodes=args.eval_episodes,
                replay_capacity=args.replay_capacity,
                batch_size=args.batch_size,
                warmup_steps=args.warmup_steps,
                train_frequency=args.train_frequency,
                gradient_steps=args.gradient_steps,
                target_update_interval=args.target_update_interval,
                hidden_sizes=hidden_sizes,
                seed=args.seed,
                learning_rate=dqn_learning_rate,
                discount=args.discount,
                epsilon=args.epsilon,
                epsilon_min=args.epsilon_min,
                epsilon_decay=args.epsilon_decay,
                device=args.device,
                architecture=args.dqn_architecture,
                restore_best_checkpoint=args.restore_best_checkpoint,
                progress_callback=progress_reporter,
                progress_interval=args.progress_interval,
                progress_window=args.progress_window,
            )
        except ModuleNotFoundError as exc:
            print(f"Dueling Double DQN unavailable: {exc}")
            raise SystemExit(1)
        else:
            print_deep_value_summary("Dueling Double DQN", dueling_double_dqn_result)
            if saves_training_artifacts:
                save_training_artifacts(
                    dueling_double_dqn_result,
                    args=args,
                    label="Dueling Double DQN",
                    training_config=training_config,
                    run_metadata=build_run_metadata(
                        dueling_double_dqn_result,
                        started_at=run_started_at,
                        started_perf_counter=run_started_perf_counter,
                        config_source=args.config,
                    ),
                    training_summary=build_training_summary(dueling_double_dqn_result),
                )

    if args.policy == "masked_ppo":
        run_started_at = datetime.now(timezone.utc)
        run_started_perf_counter = perf_counter()
        profiler = (
            TrainingProfiler("masked_ppo")
            if args.profile_training or args.profile_out is not None
            else None
        )
        try:
            ppo_result = train_masked_ppo(
                env_factory=env_factory,
                episodes=args.episodes,
                evaluation_interval=args.eval_interval,
                evaluation_episodes=args.eval_episodes,
                rollout_steps=args.rollout_steps,
                num_envs=args.num_envs,
                env_workers=args.env_workers,
                hidden_sizes=hidden_sizes,
                seed=args.seed,
                learning_rate=ppo_learning_rate,
                discount=args.discount,
                gae_lambda=args.gae_lambda,
                clip_ratio=args.clip_ratio,
                value_loss_coef=args.value_loss_coef,
                entropy_coef=args.entropy_coef,
                ppo_epochs=args.ppo_epochs,
                minibatch_size=args.ppo_minibatch_size,
                max_grad_norm=args.max_grad_norm,
                policy_architecture=args.ppo_policy_architecture,
                device=args.device,
                restore_best_checkpoint=args.restore_best_checkpoint,
                profiler=profiler,
                progress_callback=progress_reporter,
                progress_interval=args.progress_interval,
                progress_window=args.progress_window,
            )
        except ModuleNotFoundError as exc:
            print(f"Masked PPO unavailable: {exc}")
            raise SystemExit(1)
        else:
            print_ppo_summary(ppo_result)
            if ppo_result.profile is not None:
                print_training_profile(ppo_result.profile)
                if args.profile_out is not None:
                    profile_output_path = ppo_result.profile.write_json(args.profile_out)
                    print(f"Saved training profile to {profile_output_path}")
            if saves_training_artifacts:
                save_training_artifacts(
                    ppo_result,
                    args=args,
                    label="Masked PPO",
                    training_config=training_config,
                    run_metadata=build_run_metadata(
                        ppo_result,
                        started_at=run_started_at,
                        started_perf_counter=run_started_perf_counter,
                        config_source=args.config,
                    ),
                    training_summary=build_training_summary(ppo_result),
                )


if __name__ == "__main__":
    main()
