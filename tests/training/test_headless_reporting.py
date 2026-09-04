"""Focused persistence tests for the versioned headless experiment envelope."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

import pytest

from game.backends.headless.reduced_run_backend import (
    HeadlessRunConfig,
    create_reduced_run_backend,
)
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import canonical_json_bytes
from game.data.headless_trajectory import TrajectoryIntegrityError
from game.training.headless_benchmark import (
    HeadlessBenchmarkConfig,
    HeadlessBenchmarkResult,
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
    HeadlessBatchResult,
    HeadlessRolloutConfig,
    HeadlessRolloutResult,
    RolloutStopReason,
    run_headless_rollout,
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


def test_writer_rejects_relabelled_budget_trace_and_wrong_trajectory_before_final_marker(tmp_path) -> None:
    config = _config(repetitions=1)
    result = benchmark_headless_rollouts(config.benchmark)
    original = result.batches[0].results[0]
    relabelled = replace(
        original,
        stop_reason=RolloutStopReason.ROUTE_COMPLETE,
        transition_count=999,
    )
    with pytest.raises(ExperimentIntegrityError):
        write_headless_experiment(
            tmp_path / "relabelled",
            config,
            replace(result, batches=(replace(result.batches[0], results=(relabelled,)),)),
        )

    wrong_id = run_headless_rollout(
        HeadlessRolloutConfig(
            "different-trajectory-id",
            original.config.run_config,
            original.config.transition_budget,
            policy_seed=original.config.policy_seed,
        )
    )
    mismatched = replace(original, trajectory=wrong_id.trajectory)
    root = tmp_path / "wrong-id"
    with pytest.raises(ExperimentIntegrityError):
        write_headless_experiment(
            root,
            config,
            replace(result, batches=(replace(result.batches[0], results=(mismatched,)),)),
        )
    assert not root.exists()


def test_loader_rechecks_anchored_report_facts_against_audit_stream(tmp_path) -> None:
    config = _config(repetitions=1)
    result = benchmark_headless_rollouts(config.benchmark)
    root = tmp_path / "experiment"
    report = write_headless_experiment(root, config, result)
    path = root / "experiment.manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["repetitions"][0]["received"][0]["transition_count"] = 999
    changed = canonical_json_bytes(value)
    path.write_bytes(changed)

    with pytest.raises(ExperimentIntegrityError):
        load_headless_experiment(
            root,
            expected_manifest_sha256=sha256(changed).hexdigest(),
        )
    assert report.sha256 != sha256(changed).hexdigest()


def test_report_enforces_interruption_sequence_and_truthful_no_trajectory_failures(tmp_path) -> None:
    config = _config(repetitions=2)
    result = benchmark_headless_rollouts(config.benchmark)
    interrupted_first = replace(result.batches[0], interrupted=True)
    with pytest.raises(ExperimentIntegrityError):
        write_headless_experiment(
            tmp_path / "started-after-interruption",
            config,
            replace(result, batches=(interrupted_first, result.batches[1])),
        )
    with pytest.raises(ExperimentIntegrityError):
        write_headless_experiment(
            tmp_path / "completed-then-unstarted",
            config,
            replace(result, batches=(result.batches[0],)),
        )

    failed = HeadlessRolloutResult(
        config.benchmark.batch.episodes[0],
        RolloutStopReason.FAILED,
        0,
        None,
        None,
        None,
        None,
        "synthetic failure before reset",
    )
    failure_result = HeadlessBenchmarkResult(
        conditions=replace(config.benchmark, repetitions=1),
        elapsed_seconds=0.0,
        episode_count=1,
        transition_count=0,
        episodes_per_second=0.0,
        transitions_per_second=0.0,
        batches=(HeadlessBatchResult((failed,), False, config.benchmark.batch.worker),),
    )
    one = replace(config, benchmark=replace(config.benchmark, repetitions=1))
    report = write_headless_experiment(tmp_path / "failed-no-trajectory", one, failure_result)
    assert load_headless_experiment(
        tmp_path / "failed-no-trajectory", expected_manifest_sha256=report.sha256
    ).trajectories == {}


def test_same_id_and_pins_do_not_independently_authenticate_declared_seeds(tmp_path) -> None:
    """Existing trajectory schema has no seed/config provenance field to inspect."""

    config = _config(repetitions=1)
    result = benchmark_headless_rollouts(config.benchmark)
    original = result.batches[0].results[0]
    other_seed = run_headless_rollout(
        replace(
            original.config,
            run_config=HeadlessRunConfig("simple__starter", CONTENT_FINGERPRINT, 999, {}),
            policy_seed=777,
        )
    )
    assert other_seed.trajectory is not None
    declared_bundle = replace(original, trajectory=other_seed.trajectory)
    artifact = write_headless_experiment(
        tmp_path / "declared-conditions",
        config,
        replace(result, batches=(replace(result.batches[0], results=(declared_bundle,)),)),
    )
    loaded = load_headless_experiment(
        tmp_path / "declared-conditions", expected_manifest_sha256=artifact.sha256
    )
    assert loaded.config.benchmark.batch.episodes[0].run_config.game_seed == 10


def test_writer_bounds_host_measurements_before_creating_output(tmp_path) -> None:
    config = _config(repetitions=1)
    result = benchmark_headless_rollouts(config.benchmark)
    root = tmp_path / "oversized-host"
    with pytest.raises(ExperimentValidationError):
        write_headless_experiment(
            root,
            config,
            result,
            host_measurements={"host_cpu_model": "x" * 257},
        )
    assert not root.exists()
