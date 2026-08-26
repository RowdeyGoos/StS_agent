"""Tests for baseline policies and training helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from random import Random
from pathlib import Path
from tempfile import TemporaryDirectory

from game.cli.train import (
    agent_config_sidecar_path,
    agent_profile_sidecar_path,
    agent_run_sidecar_path,
    create_run_directory,
    parse_args,
    resolved_training_config,
    resolve_dqn_learning_rate,
    resolve_ppo_learning_rate,
    resolve_q_learning_rate,
    write_training_config,
)

from game.agents.baselines import (
    TrainingProgress,
    QLearningAgent,
    choose_heuristic_action,
    choose_random_action,
    evaluate_policy,
    train_q_learning,
)
from game.simulation.card import StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy


def test_random_policy_returns_legal_action() -> None:
    env = CombatEnv(seed=0)
    observation = env.reset()
    action_mask = env.get_action_mask()

    action_index = choose_random_action(env, observation, action_mask, rng=Random(0))

    assert action_mask[action_index] == 1


def test_heuristic_policy_wins_easy_episode() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=1,
    )
    stats = evaluate_policy(
        env_factory=lambda: CombatEnv(
            seed=0,
            deck_factory=lambda: [StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
        ),
        policy=choose_heuristic_action,
        episodes=3,
        seed=0,
    )

    assert env.action_space_size == 11
    assert stats.win_rate == 1.0
    assert stats.mean_reward == 1.0


def test_q_learning_update_changes_q_values() -> None:
    agent = QLearningAgent(
        action_space_size=3,
        learning_rate=0.5,
        discount=0.9,
        epsilon=0.0,
        seed=0,
    )
    state = (1, 2, 3)
    next_state = (4, 5, 6)

    agent.q_table[next_state] = [0.0, 1.0, 0.0]
    agent.update(
        state=state,
        action=1,
        reward=0.0,
        next_state=next_state,
        next_action_mask=(1, 1, 0),
        done=False,
    )

    assert agent.q_table[state][1] == 0.45


def test_q_learning_training_produces_evaluation_stats() -> None:
    result = train_q_learning(
        env_factory=lambda: CombatEnv(
            deck_factory=lambda: [StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            player_max_hp=6,
            cards_per_turn=1,
        ),
        episodes=10,
        evaluation_interval=5,
        evaluation_episodes=3,
        seed=0,
        epsilon=0.4,
        epsilon_min=0.0,
        epsilon_decay=0.9,
    )

    assert len(result.training_metrics) == 10
    assert len(result.evaluations) == 2
    assert result.final_evaluation.episodes == 3
    assert len(result.agent.q_table) > 0


def test_q_learning_progress_callback_reports_updates() -> None:
    progress_updates: list[TrainingProgress] = []

    result = train_q_learning(
        env_factory=lambda: CombatEnv(
            deck_factory=lambda: [StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
        ),
        episodes=3,
        evaluation_interval=2,
        evaluation_episodes=1,
        seed=0,
        progress_callback=progress_updates.append,
        progress_interval=2,
        progress_window=2,
    )

    assert len(result.training_metrics) == 3
    assert len(progress_updates) == 2
    assert progress_updates[0].episode == 2
    assert progress_updates[1].episode == 3
    assert progress_updates[-1].algorithm == "q_learning"


def test_cli_uses_separate_default_learning_rates() -> None:
    args = parse_args([])

    assert resolve_q_learning_rate(args) == 0.1
    assert resolve_dqn_learning_rate(args) == 1e-3
    assert resolve_ppo_learning_rate(args) == 3e-4
    assert args.restore_best_checkpoint is True
    assert args.train_frequency == 4
    assert args.gradient_steps == 1
    assert args.record_trajectories is False
    assert args.dqn_architecture == "action_feature"
    assert args.ppo_policy_architecture == "action_feature"
    assert args.num_envs == 1
    assert args.env_workers == 0
    assert args.profile_training is False
    assert args.profile_out is None


def test_cli_shared_learning_rate_override_applies_to_both_algorithms() -> None:
    args = parse_args(["--learning-rate", "0.02"])

    assert resolve_q_learning_rate(args) == 0.02
    assert resolve_dqn_learning_rate(args) == 0.02
    assert resolve_ppo_learning_rate(args) == 0.02


def test_cli_algorithm_specific_learning_rates_remain_available() -> None:
    args = parse_args(
        [
            "--q-learning-rate",
            "0.25",
            "--dqn-learning-rate",
            "0.0005",
            "--ppo-learning-rate",
            "0.0003",
        ]
    )

    assert resolve_q_learning_rate(args) == 0.25
    assert resolve_dqn_learning_rate(args) == 0.0005
    assert resolve_ppo_learning_rate(args) == 0.0003


def test_cli_accepts_dueling_double_dqn_policy() -> None:
    args = parse_args(["--policy", "dueling_double_dqn"])

    assert args.policy == "dueling_double_dqn"


def test_cli_accepts_masked_ppo_policy() -> None:
    args = parse_args(
        [
            "--policy",
            "masked_ppo",
            "--num-envs",
            "8",
            "--env-workers",
            "2",
            "--profile-training",
            "--profile-out",
            "profiles/ppo.json",
        ]
    )

    assert args.policy == "masked_ppo"
    assert args.num_envs == 8
    assert args.env_workers == 2
    assert args.profile_training is True
    assert args.profile_out == "profiles/ppo.json"


def test_cli_accepts_action_conditioned_ppo_architecture() -> None:
    args = parse_args(["--ppo-policy-architecture", "flat"])

    assert args.ppo_policy_architecture == "flat"


def test_cli_accepts_shared_enemy_ppo_architecture() -> None:
    args = parse_args(["--ppo-policy-architecture", "shared_enemy"])

    assert args.ppo_policy_architecture == "shared_enemy"


def test_cli_accepts_action_conditioned_dqn_architecture() -> None:
    args = parse_args(["--dqn-architecture", "flat"])

    assert args.dqn_architecture == "flat"


def test_cli_accepts_shared_enemy_dqn_architecture() -> None:
    args = parse_args(["--dqn-architecture", "shared_enemy"])

    assert args.dqn_architecture == "shared_enemy"


def test_shared_enemy_double_dqn_config_is_reusable() -> None:
    args = parse_args(
        ["--config", "configs/double_dqn_shared_enemy_overgrowth.json"]
    )
    resolved = resolved_training_config(args)

    assert args.policy == "double_dqn"
    assert args.dqn_architecture == "shared_enemy"
    assert resolved["output_dir"] == "runs/double-dqn-shared-enemy-overgrowth"


def test_training_config_loads_json_and_cli_overrides_it() -> None:
    with TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "training.json"
        config_path.write_text(
            json.dumps(
                {
                    "policy": "double_dqn",
                    "episodes": 1200,
                    "hidden_sizes": [256, 128],
                    "restore_best_checkpoint": False,
                    "incoming_damage_shaping_scale": 0.75,
                }
            ),
            encoding="utf-8",
        )
        args = parse_args(
            [
                "--config",
                str(config_path),
                "--episodes",
                "25",
                "--restore-best-checkpoint",
            ]
        )

    assert args.policy == "double_dqn"
    assert args.episodes == 25
    assert args.hidden_sizes == (256, 128)
    assert args.restore_best_checkpoint is True
    assert args.incoming_damage_shaping_scale == 0.75


def test_resolved_training_config_is_reusable() -> None:
    original_args = parse_args(
        [
            "--policy",
            "double_dqn",
            "--episodes",
            "42",
            "--hidden-sizes",
            "64,32",
            "--no-print-config",
        ]
    )
    resolved = resolved_training_config(original_args)

    with TemporaryDirectory() as temp_dir:
        config_path = write_training_config(
            resolved,
            Path(temp_dir) / "resolved.json",
        )
        reloaded_args = parse_args(["--config", str(config_path)])

    assert resolved_training_config(reloaded_args) == resolved
    assert reloaded_args.hidden_sizes == (64, 32)


def test_training_config_rejects_unknown_keys() -> None:
    with TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "invalid.json"
        config_path.write_text('{"episodez": 10}', encoding="utf-8")
        try:
            parse_args(["--config", str(config_path)])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("Unknown config keys should fail parsing.")


def test_agent_config_sidecar_path_replaces_checkpoint_suffix() -> None:
    assert agent_config_sidecar_path("checkpoints/agent.pt") == Path(
        "checkpoints/agent.config.json"
    )
    assert agent_run_sidecar_path("checkpoints/agent.pt") == Path(
        "checkpoints/agent.run.json"
    )
    assert agent_profile_sidecar_path("checkpoints/agent.pt") == Path(
        "checkpoints/agent.profile.json"
    )


def test_create_run_directory_is_unique_and_non_overwriting() -> None:
    started_at = datetime(2026, 8, 25, 12, 30, tzinfo=timezone.utc)
    with TemporaryDirectory() as temp_dir:
        run_id, run_dir = create_run_directory(
            temp_dir,
            policy="double_dqn",
            seed=7,
            started_at=started_at,
        )
        try:
            create_run_directory(
                temp_dir,
                policy="double_dqn",
                seed=7,
                started_at=started_at,
            )
        except FileExistsError:
            pass
        else:
            raise AssertionError("An existing run directory must not be overwritten.")

    assert run_id == "20260825T123000000000Z-double_dqn-seed-7"
    assert run_dir.name == run_id


def test_q_learning_training_can_disable_checkpoint_evaluations() -> None:
    result = train_q_learning(
        env_factory=lambda: CombatEnv(
            deck_factory=lambda: [StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
            record_trajectory=False,
        ),
        episodes=4,
        evaluation_interval=0,
        evaluation_episodes=1,
        seed=0,
    )

    assert len(result.training_metrics) == 4
    assert result.evaluations == ()
    assert result.final_evaluation.episodes == 1
