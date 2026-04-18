"""Tests for the Optuna sweep helper module."""

from __future__ import annotations

from game.baselines import EvaluationStats

import sweep


def test_sweep_cli_defaults() -> None:
    args = sweep.parse_args([])

    assert args.policy == "double_dqn"
    assert args.trials == 20
    assert args.train_seeds == 3
    assert args.evaluation_interval == 0
    assert args.metric == "hp_preserving_score"
    assert args.sampler == "tpe"
    assert args.pruner == "none"
    assert args.dqn_architecture == "action_feature"
    assert args.ppo_policy_architecture == "action_feature"


def test_seed_generation_is_stable() -> None:
    assert sweep.resolve_train_seeds(7, 3) == (7, 1007, 2007)
    assert sweep.resolve_evaluation_seeds(7, 3) == (100007, 101007, 102007)


def test_hp_preserving_score_uses_remaining_hp_fraction() -> None:
    stats = EvaluationStats(
        episodes=10,
        mean_reward=0.4,
        win_rate=0.8,
        mean_steps=12.0,
        mean_player_hp=40.0,
    )

    score = sweep.score_evaluation(
        stats,
        metric="hp_preserving_score",
        player_max_hp=80,
        hp_weight=0.25,
    )

    assert score == 0.925


def test_run_sweep_requires_optuna_when_dependency_is_missing() -> None:
    if sweep.optuna is not None:
        return

    args = sweep.parse_args(
        [
            "--policy",
            "q_learning",
            "--trials",
            "1",
            "--episodes",
            "1",
            "--evaluation-episodes",
            "1",
            "--train-seeds",
            "1",
        ]
    )

    try:
        sweep.run_sweep(args)
    except ModuleNotFoundError as exc:
        assert "optuna" in str(exc)
    else:
        raise AssertionError("Expected run_sweep to require optuna when unavailable.")
