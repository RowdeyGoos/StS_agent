"""Focused persistence tests for the versioned headless experiment envelope."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

import pytest
import game.training.headless_rollout as rollout_module

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
    BackendFactoryDescriptor,
    ChooserKind,
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


@pytest.mark.parametrize("cause", ("keyboard", "unadvertised", "between_episodes"))
def test_real_interrupted_panel_preserves_received_pending_and_unstarted(tmp_path, monkeypatch, cause) -> None:
    config = _config(episodes=3, repetitions=3)
    if cause == "between_episodes":
        original_entry = rollout_module._run_batch_entry
        calls = 0

        def entry(episode):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt("synthetic between-episode cancellation")
            return original_entry(episode)

        monkeypatch.setattr(rollout_module, "_run_batch_entry", entry)
    else:
        def chooser_factory(_config):
            def choose(_view):
                if cause == "keyboard":
                    raise KeyboardInterrupt("synthetic chooser cancellation")
                return "unadvertised-synthetic-candidate"
            return choose

        monkeypatch.setattr(rollout_module, "_make_chooser", chooser_factory)

    result = benchmark_headless_rollouts(config.benchmark)
    assert len(result.batches) == 1
    batch = result.batches[0]
    assert batch.interrupted and len(batch.results) == 1
    received = batch.results[0]
    assert received.stop_reason is (
        RolloutStopReason.BUDGET_EXHAUSTED if cause == "between_episodes"
        else RolloutStopReason.INTERRUPTED
    )
    assert (received.failure is not None) == (cause == "keyboard")
    expected_pending = tuple(
        item.trajectory_id for item in config.benchmark.batch.episodes
        if item.trajectory_id != received.config.trajectory_id
    )
    assert batch.pending_trajectory_ids == expected_pending
    root = tmp_path / cause
    report = write_headless_experiment(root, config, result)
    loaded = load_headless_experiment(root, expected_manifest_sha256=report.sha256)
    assert loaded.report == report
    assert report.repetitions[0].interrupted
    assert report.repetitions[0].pending_trajectory_ids == expected_pending
    assert report.unstarted_repetition_indices == (1, 2)
    assert loaded.trajectories == {(0, received.config.trajectory_id): received.trajectory}


@pytest.mark.parametrize("completion", ("terminal", "unsupported"))
def test_cancellation_after_completed_boundary_preserves_completion_and_stops_benchmark(
    tmp_path, monkeypatch, completion,
) -> None:
    config = _config(repetitions=2)
    episode = replace(config.benchmark.batch.episodes[0], transition_budget=300)
    if completion == "unsupported":
        episode = replace(
            episode,
            chooser_kind=ChooserKind.SEEDED_RANDOM,
            policy_seed=5,
            run_config=HeadlessRunConfig(
                "simple__starter", CONTENT_FINGERPRINT, 7,
                {"event_id": "cool_spring", "combat_settings": {"enemy_max_hp": 1}},
            ),
        )
    config = replace(config, benchmark=replace(
        config.benchmark, batch=replace(config.benchmark.batch, episodes=(episode,)),
    ))

    def interrupt_before_finalization(_result, _backend):
        raise KeyboardInterrupt("synthetic cancellation after completed boundary")

    monkeypatch.setattr(rollout_module, "_stop_reason", interrupt_before_finalization)
    result = benchmark_headless_rollouts(config.benchmark)
    assert len(result.batches) == 1 and result.batches[0].interrupted
    received = result.batches[0].results[0]
    assert received.stop_reason is RolloutStopReason.INTERRUPTED
    assert received.failure is not None and received.trajectory is not None
    assert received.trajectory.manifest.completion.value == completion
    root = tmp_path / completion
    report = write_headless_experiment(root, config, result)
    loaded = load_headless_experiment(root, expected_manifest_sha256=report.sha256)
    assert loaded.report.repetitions[0].received[0].trajectory_completion.value == completion
    assert loaded.report.unstarted_repetition_indices == (1,)
    assert loaded.trajectories[(0, episode.trajectory_id)] == received.trajectory


@pytest.mark.parametrize("has_trajectory", (True, False))
def test_real_failed_episodes_keep_failure_flag_and_allow_later_repetitions(
    tmp_path, monkeypatch, has_trajectory,
) -> None:
    config = _config(repetitions=2)

    def fail(_argument):
        raise RuntimeError("synthetic producer failure")

    if has_trajectory:
        monkeypatch.setattr(rollout_module, "_make_chooser", lambda _config: fail)
    else:
        monkeypatch.setattr(BackendFactoryDescriptor, "create", fail)
    result = benchmark_headless_rollouts(config.benchmark)
    assert len(result.batches) == 2
    for batch in result.batches:
        assert not batch.interrupted
        assert batch.results[0].stop_reason is RolloutStopReason.FAILED
        assert batch.results[0].failure is not None
        assert (batch.results[0].trajectory is not None) == has_trajectory
    root = tmp_path / "failed"
    report = write_headless_experiment(root, config, result)
    loaded = load_headless_experiment(root, expected_manifest_sha256=report.sha256)
    assert loaded.report == report
    assert not report.unstarted_repetition_indices
    assert all(rep.received[0].failure_present for rep in report.repetitions)
    assert len(loaded.trajectories) == (2 if has_trajectory else 0)


@pytest.mark.parametrize("mutation", (
    "interrupted_unflagged", "interrupted_then_started", "failed_without_failure",
    "failed_without_failure_no_trajectory", "ordinary_with_failure",
))
@pytest.mark.parametrize("boundary", ("writer", "loader"))
def test_inconsistent_episode_flags_and_repetition_order_are_rejected(
    tmp_path, mutation, boundary,
) -> None:
    config = _config(repetitions=2)
    result = benchmark_headless_rollouts(config.benchmark)
    root = tmp_path / "invalid"
    interrupted = mutation.startswith("interrupted")
    failed = mutation.startswith("failed")
    reason = (RolloutStopReason.INTERRUPTED if interrupted else
              RolloutStopReason.FAILED if failed else RolloutStopReason.BUDGET_EXHAUSTED)
    failure = None if failed else "synthetic failure"
    batch_interrupted = mutation == "interrupted_then_started"
    no_trajectory = mutation.endswith("no_trajectory")

    if boundary == "writer":
        changes = {"stop_reason": reason, "failure": failure}
        if no_trajectory:
            changes.update(trajectory=None, transition_count=0)
        episode = replace(result.batches[0].results[0], **changes)
        batch = replace(result.batches[0], results=(episode,), interrupted=batch_interrupted)
        changed_result = replace(result, batches=(batch, result.batches[1]))
        with pytest.raises(ExperimentValidationError):
            write_headless_experiment(root, config, changed_result)
        assert not root.exists()
    else:
        write_headless_experiment(root, config, result)
        path = root / "experiment.manifest.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        repetition = value["repetitions"][0]
        repetition["interrupted"] = batch_interrupted
        episode = repetition["received"][0]
        episode.update(stop_reason=reason.value, failure_present=failure is not None)
        if no_trajectory:
            episode.update(
                trajectory_manifest_sha256=None, trajectory_completion=None,
                terminal_outcome=None, initial_decision_sha256=None,
                final_decision_sha256=None, transition_count=0,
            )
        changed = canonical_json_bytes(value)
        path.write_bytes(changed)
        # A fresh external anchor bypasses the byte mismatch to exercise the
        # semantic validator, including the exact unflagged-interruption repro.
        with pytest.raises(ExperimentValidationError):
            load_headless_experiment(root, expected_manifest_sha256=sha256(changed).hexdigest())
