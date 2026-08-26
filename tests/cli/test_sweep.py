"""Tests for the Optuna sweep helper module."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from game.agents.baselines import EvaluationStats

from game.cli import sweep


def test_sweep_cli_defaults() -> None:
    args = sweep.parse_args([])

    assert args.policy == "double_dqn"
    assert args.trials == 20
    assert args.trial_workers == 1
    assert args.journal_file is None
    assert args.train_seeds == 3
    assert args.evaluation_interval == 0
    assert args.metric == "hp_preserving_score"
    assert args.sampler == "tpe"
    assert args.pruner == "none"
    assert args.dqn_architecture == "action_feature"
    assert args.ppo_policy_architecture == "action_feature"
    assert args.deck == "starter"


def test_sweep_selects_named_deck_in_config_and_factory() -> None:
    with TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "deck-sweep.json"
        config_path.write_text(
            json.dumps({"deck": "ironclad_sequencing"}),
            encoding="utf-8",
        )
        args = sweep.parse_args(["--config", str(config_path)])

    env_factory = sweep.make_env_factory(
        args,
        hp_loss_penalty_scale=1.0,
        incoming_damage_shaping_scale=0.0,
    )
    env = env_factory()
    observation = env.reset(seed=7)

    assert sweep.resolved_sweep_config(args)["deck"] == "ironclad_sequencing"
    assert "Pommel Strike" in {
        card_name
        for pile_counts in observation["card_counts"].values()
        for card_name in pile_counts
    }


def test_seed_generation_is_stable() -> None:
    assert sweep.resolve_train_seeds(7, 3) == (7, 1007, 2007)
    assert sweep.resolve_evaluation_seeds(7, 3) == (100007, 101007, 102007)


def test_trial_budget_is_split_globally_across_workers() -> None:
    assert sweep.split_trial_counts(10, 3) == (4, 3, 3)
    assert sweep.split_trial_counts(2, 8) == (1, 1)


def test_cli_param_format_rounds_floats_without_changing_values() -> None:
    params = {
        "discount": 0.9909804901570973,
        "hidden_sizes": [128, 128],
        "learning_rate": 0.00027441587479639626,
    }

    formatted = sweep._format_params(params)

    assert formatted == (
        "discount=0.99098, hidden_sizes=[128, 128], "
        "learning_rate=0.000274416"
    )
    assert params["discount"] == 0.9909804901570973


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


def test_parallel_sweep_runs_global_trial_budget_through_journal() -> None:
    if sweep.optuna is None:
        return

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        journal_path = temp_path / "parallel.journal"
        summary_path = temp_path / "summary.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(sweep.__file__).resolve()),
                "--policy",
                "q_learning",
                "--trials",
                "2",
                "--trial-workers",
                "2",
                "--journal-file",
                str(journal_path),
                "--study-name",
                "parallel_test",
                "--episodes",
                "1",
                "--train-seeds",
                "1",
                "--evaluation-episodes",
                "1",
                "--sampler",
                "random",
                "--json-out",
                str(summary_path),
                "--no-print-config",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0, completed.stderr
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["trials_requested"] == 2
    assert summary["trial_workers"] == 2
    assert summary["trials_existing_before"] == 0
    assert summary["trials_total"] == 2
    assert summary["trials_completed"] == 2
    assert summary["deck"] == "starter"


def test_parallel_sweep_requires_shared_storage() -> None:
    if sweep.optuna is None:
        return
    args = sweep.parse_args(
        [
            "--policy",
            "q_learning",
            "--trials",
            "2",
            "--trial-workers",
            "2",
            "--episodes",
            "1",
            "--train-seeds",
            "1",
            "--evaluation-episodes",
            "1",
        ]
    )

    try:
        sweep.run_sweep(args)
    except ValueError as exc:
        assert "shared Optuna storage" in str(exc)
    else:
        raise AssertionError("Parallel trials without shared storage should fail.")


def test_sweep_config_loads_search_space_and_cli_overrides_base_values() -> None:
    with TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "ppo_sweep.json"
        config_path.write_text(
            json.dumps(
                {
                    "policy": "masked_ppo",
                    "trials": 12,
                    "trial_workers": 2,
                    "journal_file": "sweeps/test.journal",
                    "num_envs": 64,
                    "env_workers": 4,
                    "search_space": {
                        "learning_rate": {
                            "type": "float",
                            "low": 0.0001,
                            "high": 0.0005,
                            "log": True,
                        },
                        "rollout_steps": {
                            "type": "categorical",
                            "choices": [2048, 4096],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

        args = sweep.parse_args(
            ["--config", str(config_path), "--trials", "3"]
        )

    assert args.policy == "masked_ppo"
    assert args.trials == 3
    assert args.trial_workers == 2
    assert args.journal_file == "sweeps/test.journal"
    assert args.num_envs == 64
    assert args.env_workers == 4
    assert args.search_space["rollout_steps"]["choices"] == [2048, 4096]


def test_resolved_ppo_sweep_config_expands_builtin_search_defaults() -> None:
    args = sweep.parse_args(["--policy", "masked_ppo", "--num-envs", "8"])

    resolved = sweep.resolved_sweep_config(args)

    assert resolved["search_space"]["learning_rate"]["type"] == "float"
    assert resolved["search_space"]["num_envs"] == 8
    assert resolved["search_space"]["policy_architecture"] == "action_feature"


def test_ppo_search_space_samples_nested_hidden_sizes() -> None:
    class FirstChoiceTrial:
        def suggest_float(self, _name, low, _high, **_kwargs):
            return low

        def suggest_int(self, _name, low, _high, **_kwargs):
            return low

        def suggest_categorical(self, _name, choices):
            return choices[0]

    args = sweep.parse_args(
        ["--config", "configs/masked_ppo_sweep_overgrowth.json"]
    )

    sampled = sweep._sample_trial_config(FirstChoiceTrial(), args)

    assert sampled["hidden_sizes"] == (128, 128)
    assert sampled["rollout_steps"] == 2048
    assert sampled["minibatch_size"] == 1024
    assert sampled["num_envs"] == 64
    assert sampled["env_workers"] == 4


def test_sweep_config_rejects_unknown_keys() -> None:
    with TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "invalid.json"
        config_path.write_text('{"trialz": 10}', encoding="utf-8")

        try:
            sweep.parse_args(["--config", str(config_path)])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("Unknown sweep config keys should fail parsing.")


def test_sweep_config_rejects_unknown_deck() -> None:
    with TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "invalid-deck.json"
        config_path.write_text('{"deck": "unknown"}', encoding="utf-8")

        try:
            sweep.parse_args(["--config", str(config_path)])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("Unknown named decks should fail parsing.")
