"""Tests for semantic training timing and persisted profile reports."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from game.cli.analyze_training import parse_args
from game.training.profile import TrainingProfiler, load_training_profile


def test_training_profiler_records_phases_and_resources() -> None:
    profiler = TrainingProfiler("masked_ppo")
    profiler.add_external_process_cpu_seconds(0.25)
    with profiler.measure("ppo.rollout.environment_step", synchronize=False):
        sum(range(100))
    with profiler.measure("ppo.gradient_updates", synchronize=False):
        sum(range(1_000))

    profile = profiler.finalize()

    assert profile.algorithm == "masked_ppo"
    assert profile.wall_seconds >= 0.0
    assert profile.process_cpu_seconds >= 0.25
    assert profile.logical_cpu_count is None or profile.logical_cpu_count > 0
    assert {phase.name for phase in profile.phases} == {
        "ppo.rollout.environment_step",
        "ppo.gradient_updates",
    }
    assert profile.bottleneck_phase in {
        "ppo.rollout.environment_step",
        "ppo.gradient_updates",
    }


def test_training_profile_round_trips_from_run_directory() -> None:
    profile = TrainingProfiler("masked_ppo").finalize()
    with TemporaryDirectory() as temp_dir:
        run_dir = Path(temp_dir) / "run"
        profile_path = profile.write_json(run_dir / "profile.json")
        loaded_from_file = load_training_profile(profile_path)
        loaded_from_directory = load_training_profile(run_dir)

    assert loaded_from_file == loaded_from_directory
    assert loaded_from_file["profile_format_version"] == 1
    assert loaded_from_file["algorithm"] == "masked_ppo"


def test_training_profile_analysis_cli_accepts_multiple_paths() -> None:
    args = parse_args(["run-a", "profile-b.json", "--max-phases", "5"])

    assert args.paths == ["run-a", "profile-b.json"]
    assert args.max_phases == 5
