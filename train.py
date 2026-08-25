"""Training and evaluation entry point for baseline RL experiments."""

from __future__ import annotations

import argparse
from statistics import mean
from typing import Callable, Sequence

from game import CombatEnv, SimpleEnemy, build_overgrowth_easy_encounter
from game.agent_io import save_agent
from game.baselines import (
    EvaluationStats,
    TrainingProgress,
    TrainingResult,
    choose_heuristic_action,
    choose_random_action,
    evaluate_policy,
    train_q_learning,
)
from game.dqn import (
    DQNTrainingResult,
    train_double_dqn,
    train_dqn,
    train_dueling_double_dqn,
)
from game.ppo import PPOTrainingResult, train_masked_ppo

DEFAULT_Q_LEARNING_RATE = 0.1
DEFAULT_DQN_LEARNING_RATE = 1e-3
DEFAULT_PPO_LEARNING_RATE = 3e-4


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for training and baseline evaluation."""
    parser = argparse.ArgumentParser(
        description="Run baseline training or evaluation on the combat simulator."
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
        type=str,
        default="128,128",
        help="Comma-separated hidden layer sizes for the DQN MLP.",
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
        help="Torch device for neural agents, for example `cpu` or `cuda`.",
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
        help="Optional output path for saving a trained q_learning, DQN-family, or PPO agent.",
    )
    parser.add_argument(
        "--record-trajectories",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Store full per-step episode histories inside training environments.",
    )
    parser.add_argument(
        "--rollout-steps",
        type=int,
        default=512,
        help="Number of on-policy environment steps collected per PPO update.",
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
        choices=("flat", "action_feature"),
        default="action_feature",
        help="Policy head used by masked PPO.",
    )
    return parser.parse_args(argv)


def make_env_factory(args: argparse.Namespace) -> Callable[[], CombatEnv]:
    """Build a deterministic env factory from CLI arguments."""
    if args.encounter_set == "overgrowth_easy":
        return lambda: CombatEnv(
            player_max_hp=args.player_hp,
            cards_per_turn=args.cards_per_turn,
            encounter_factory=build_overgrowth_easy_encounter,
            max_enemy_count=3,
            hp_loss_penalty_scale=args.hp_loss_penalty_scale,
            incoming_damage_shaping_scale=args.incoming_damage_shaping_scale,
            record_trajectory=args.record_trajectories,
        )

    return lambda: CombatEnv(
        player_max_hp=args.player_hp,
        cards_per_turn=args.cards_per_turn,
        enemy_factory=lambda: SimpleEnemy(max_hp=args.enemy_hp),
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


def parse_hidden_sizes(value: str) -> tuple[int, ...]:
    """Parse a comma-separated hidden-size specification."""
    hidden_sizes = tuple(
        int(part.strip())
        for part in value.split(",")
        if part.strip()
    )
    if not hidden_sizes:
        raise ValueError("hidden-sizes must contain at least one integer.")
    return hidden_sizes


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
    if args.save_agent is not None and args.policy not in {
        "q_learning",
        "dqn",
        "double_dqn",
        "dueling_double_dqn",
        "masked_ppo",
    }:
        raise SystemExit(
            "--save-agent is only supported for q_learning, dqn, double_dqn, dueling_double_dqn, or masked_ppo."
        )

    env_factory = make_env_factory(args)
    hidden_sizes = parse_hidden_sizes(args.hidden_sizes)
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
        if args.save_agent is not None:
            save_agent(result.agent, args.save_agent)
            print(f"Saved q_learning agent to {args.save_agent}")

    if args.policy in {"dqn", "compare"}:
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
            if args.save_agent is not None:
                save_agent(dqn_result.agent, args.save_agent)
                print(f"Saved DQN agent to {args.save_agent}")

    if args.policy in {"double_dqn", "compare"}:
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
            if args.save_agent is not None:
                save_agent(double_dqn_result.agent, args.save_agent)
                print(f"Saved Double DQN agent to {args.save_agent}")

    if args.policy == "dueling_double_dqn":
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
            if args.save_agent is not None:
                save_agent(dueling_double_dqn_result.agent, args.save_agent)
                print(f"Saved Dueling Double DQN agent to {args.save_agent}")

    if args.policy == "masked_ppo":
        try:
            ppo_result = train_masked_ppo(
                env_factory=env_factory,
                episodes=args.episodes,
                evaluation_interval=args.eval_interval,
                evaluation_episodes=args.eval_episodes,
                rollout_steps=args.rollout_steps,
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
                progress_callback=progress_reporter,
                progress_interval=args.progress_interval,
                progress_window=args.progress_window,
            )
        except ModuleNotFoundError as exc:
            print(f"Masked PPO unavailable: {exc}")
            raise SystemExit(1)
        else:
            print_ppo_summary(ppo_result)
            if args.save_agent is not None:
                save_agent(ppo_result.agent, args.save_agent)
                print(f"Saved Masked PPO agent to {args.save_agent}")


if __name__ == "__main__":
    main()
