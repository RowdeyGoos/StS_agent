"""Focused persistence tests for the versioned headless experiment envelope."""

from __future__ import annotations

from dataclasses import replace

import pytest

from game.backends.headless.reduced_run_backend import (
    HeadlessRunConfig,
    create_reduced_run_backend,
)
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.data.headless_trajectory import TrajectoryIntegrityError
from game.training.headless_benchmark import (
    HeadlessBenchmarkConfig,
    benchmark_headless_rollouts,
)
from game.training.headless_reporting import (
    ExperimentIntegrityError,
    ExperimentInterruptedError,
    ExperimentValidationError,
    HeadlessExperimentConfig,
    load_headless_experiment,
    preflight_headless_experiment_output,
    write_headless_experiment,
)
from game.training.headless_rollout import (
    CollectorWorkerConfig,
    HeadlessBatchConfig,
    HeadlessRolloutConfig,
)


def _config(*, episodes: int = 1, repetitions: int = 2) -> HeadlessExperimentConfig:
    backend = create_reduced_run_backend()
    try:
        manifest = backend.manifest()
    finally:
        backend.close()
    panel = tuple(
        HeadlessRolloutConfig(
            trajectory_id=f"reporting-{index}",
            run_config=HeadlessRunConfig(
                "simple__starter", CONTENT_FINGERPRINT, index + 10, {}
            ),
            transition_budget=1,
            policy_seed=index + 20,
        )
        for index in range(episodes)
    )
    benchmark = HeadlessBenchmarkConfig(
        HeadlessBatchConfig(panel, CollectorWorkerConfig(worker_count=1, worker_seed=77)),
        repetitions=repetitions,
    )
    return HeadlessExperimentConfig("reporting-v1", benchmark, manifest)


def test_writer_and_trusted_loader_preserve_repetition_scoped_trajectories(tmp_path) -> None:
    config = _config()
    result = benchmark_headless_rollouts(config.benchmark)
    root = tmp_path / "experiment"

    report = write_headless_experiment(
        root,
        config,
        result,
        host_measurements={"host_os": "synthetic", "host_logical_cpu_count": 1},
    )
    loaded = load_headless_experiment(root, expected_manifest_sha256=report.sha256)

    assert loaded.config == config
    assert loaded.report == report
    assert set(loaded.trajectories) == {(0, "reporting-0"), (1, "reporting-0")}
    assert (
        root / "repetitions" / "000000" / "reporting-0.policy.jsonl"
    ).read_bytes() == loaded.trajectories[(0, "reporting-0")].policy_replay_jsonl
    assert loaded.report.measurement.process_mode == "sequential"
    assert loaded.report.measurement.host_os == "synthetic"


def test_loader_requires_external_anchor_and_final_marker(tmp_path) -> None:
    config = _config(repetitions=1)
    result = benchmark_headless_rollouts(config.benchmark)
    root = tmp_path / "experiment"
    report = write_headless_experiment(root, config, result)

    with pytest.raises(ExperimentIntegrityError):
        load_headless_experiment(root, expected_manifest_sha256="0" * 64)
    (root / "experiment.manifest.json").unlink()
    with pytest.raises(ExperimentInterruptedError):
        load_headless_experiment(root, expected_manifest_sha256=report.sha256)


def test_writer_refuses_condition_pin_mismatch_and_output_overwrite(tmp_path) -> None:
    config = _config(repetitions=1)
    result = benchmark_headless_rollouts(config.benchmark)
    root = tmp_path / "experiment"
    assert preflight_headless_experiment_output(root) == root
    write_headless_experiment(root, config, result)

    with pytest.raises(FileExistsError):
        preflight_headless_experiment_output(root)
    with pytest.raises(FileExistsError):
        write_headless_experiment(root, config, result)
    with pytest.raises(ExperimentValidationError):
        write_headless_experiment(
            tmp_path / "different",
            replace(config, benchmark=replace(config.benchmark, process_safe=True)),
            result,
        )


def test_loader_rejects_extra_files_and_trajectory_manifest_swaps(tmp_path) -> None:
    config = _config(episodes=2, repetitions=1)
    result = benchmark_headless_rollouts(config.benchmark)
    root = tmp_path / "experiment"
    report = write_headless_experiment(root, config, result)
    directory = root / "repetitions" / "000000"

    (directory / "unexpected.txt").write_text("no", encoding="utf-8")
    with pytest.raises(ExperimentIntegrityError):
        load_headless_experiment(root, expected_manifest_sha256=report.sha256)
    (directory / "unexpected.txt").unlink()
    source = directory / "reporting-1.manifest.json"
    target = directory / "reporting-0.manifest.json"
    target.write_bytes(source.read_bytes())
    with pytest.raises(TrajectoryIntegrityError):
        load_headless_experiment(root, expected_manifest_sha256=report.sha256)


def test_config_and_report_reject_unknown_host_fields_and_duplicate_trajectory_identity(tmp_path) -> None:
    config = _config(repetitions=1)
    with pytest.raises(ValueError):
        HeadlessBatchConfig(
            (config.benchmark.batch.episodes[0], config.benchmark.batch.episodes[0])
        )
    result = benchmark_headless_rollouts(config.benchmark)
    with pytest.raises(ExperimentValidationError):
        write_headless_experiment(
            tmp_path / "unknown-host-field",
            config,
            result,
            host_measurements={"free_form_host_dump": "not permitted"},
        )
