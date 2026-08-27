"""Configuration, scoring, scheduling, and report tests for the full suite."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import threading
from time import sleep

import pytest

from game.analysis import benchmark_suite as suite


def _row(
    variant: str,
    *,
    win: bool,
    damage: int,
    encounter: str = "nibbit",
    training_deck: str = "starter",
    evaluation_deck: str = "starter",
    seed: int = 100000,
) -> suite.EvaluationRow:
    return suite.EvaluationRow(
        stage="screen",
        run_id=f"run-{variant}",
        variant=variant,
        policy_type=variant.split("__", 1)[0],
        training_deck=training_deck,
        evaluation_deck=evaluation_deck,
        training_seed=7,
        encounter=encounter,
        episode_seed=seed,
        total_reward=1.0 if win else -1.0,
        steps=5,
        win=win,
        player_hp=80 - damage,
        enemy_hp=0 if win else 10,
        damage_taken=damage,
    )


def test_default_manifest_contains_complete_matrix() -> None:
    manifest = suite.BenchmarkSuiteManifest()
    assert len(manifest.variants) == 13
    assert len(suite.screen_training_specs(manifest)) == 26
    assert manifest.screen_transition_budget % manifest.ppo_rollout_steps == 0
    assert manifest.confirmation_transition_budget % manifest.ppo_rollout_steps == 0


def test_manifest_loader_is_strict(tmp_path: Path) -> None:
    path = tmp_path / "suite.json"
    path.write_text(json.dumps({"unknown": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown benchmark-suite"):
        suite.load_suite_manifest(path)


def test_score_order_uses_win_then_worst_cell_then_damage() -> None:
    rows = (
        _row("a", win=True, damage=20, encounter="nibbit"),
        _row("a", win=False, damage=30, encounter="mawler", seed=100001),
        _row("b", win=True, damage=10, encounter="nibbit"),
        _row("b", win=False, damage=20, encounter="mawler", seed=100001),
    )
    scores = suite.score_variants(rows)
    assert [score.variant for score in scores] == ["b", "a"]


def test_finalist_selection_keeps_dqn_and_ppo() -> None:
    manifest = suite.BenchmarkSuiteManifest()
    labels = [variant.label for variant in manifest.variants]
    scores = tuple(
        suite.VariantScore(
            variant=label,
            macro_win_rate=1.0 - index * 0.01,
            worst_cell_win_rate=0.9,
            mean_damage_taken=5.0,
            mean_player_hp=75.0,
            mean_reward=0.9,
            episodes=10,
            win_rate_interval=(0.5, 1.0),
        )
        for index, label in enumerate(labels)
    )
    finalists = suite.select_confirmation_finalists(manifest, scores)
    assert len(finalists) == 4
    assert any(variant.family == "dqn" for variant in finalists)
    assert any(variant.family == "ppo" for variant in finalists)


def test_parallel_scheduler_respects_worker_bound(tmp_path: Path, monkeypatch) -> None:
    manifest = replace(
        suite.BenchmarkSuiteManifest(),
        output_dir=str(tmp_path),
        variants=suite.default_policy_variants()[:4],
        decks=("starter",),
        max_parallel_trainings=2,
    )
    specs = suite.screen_training_specs(manifest)
    lock = threading.Lock()
    active = 0
    maximum = 0

    def fake_execute(_manifest, spec, *, resume=True):
        nonlocal active, maximum
        del resume
        with lock:
            active += 1
            maximum = max(maximum, active)
        sleep(0.02)
        with lock:
            active -= 1
        return {"run_id": spec.run_id, "status": "complete"}

    monkeypatch.setattr(suite, "execute_training_run", fake_execute)
    suite.execute_training_matrix(manifest, specs)
    assert maximum == 2


def test_thread_environment_is_bounded() -> None:
    manifest = replace(suite.BenchmarkSuiteManifest(), training_threads=4)
    environment = suite._subprocess_environment(manifest)
    assert environment["OMP_NUM_THREADS"] == "4"
    assert environment["MKL_NUM_THREADS"] == "4"
    assert environment["VECLIB_MAXIMUM_THREADS"] == "4"


def test_report_markdown_is_deterministic(tmp_path: Path) -> None:
    manifest_a = replace(
        suite.BenchmarkSuiteManifest(),
        output_dir=str(tmp_path / "a"),
    )
    manifest_b = replace(manifest_a, output_dir=str(tmp_path / "b"))
    rows = (_row("double_dqn__action_feature", win=True, damage=5),)
    variant = next(
        item for item in manifest_a.variants if item.label == "double_dqn__action_feature"
    )
    kwargs = {
        "screen_rows": rows,
        "confirmation_rows": rows,
        "time_rows": (),
        "hard_rows": rows,
        "inventory": (),
        "card_microbenchmark": {"available": True},
        "model_resources": (),
        "confirmation_finalists": (variant,),
        "hard_finalists": (variant,),
        "oracle_results": (),
    }
    manifest_a.output_path.mkdir(parents=True)
    manifest_b.output_path.mkdir(parents=True)
    suite.write_suite_report(manifest_a, **kwargs)
    suite.write_suite_report(manifest_b, **kwargs)
    assert (manifest_a.output_path / "report.md").read_bytes() == (
        manifest_b.output_path / "report.md"
    ).read_bytes()


def test_card_microbenchmark_exposes_kernel_limitations(tmp_path: Path) -> None:
    manifest = replace(
        suite.BenchmarkSuiteManifest(),
        output_dir=str(tmp_path),
        decks=("starter",),
        fixed_encounters=("nibbit",),
        microbenchmark_observations=4,
    )
    result = suite.run_card_encoding_microbenchmark(manifest)
    assert result["pile_permutation_invariant"] is True
    assert result["hand_slot_equivariant"] is True
    assert result["synthetic_append_dimension_stable"] is True
    assert result["policy_win_rate_comparison_available"] is False
