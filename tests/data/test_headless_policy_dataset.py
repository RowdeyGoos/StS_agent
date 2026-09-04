"""Focused public-boundary tests for trusted headless actor examples."""

from __future__ import annotations

from dataclasses import replace

import pytest

from game.backends.headless.reduced_run_backend import (
    HeadlessRunConfig,
    create_reduced_run_backend,
)
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.data.headless_policy_dataset import (
    ActorDatasetValidationError,
    ActorSplit,
    TrustedExperimentSource,
    load_actor_dataset,
)
from game.training.headless_benchmark import HeadlessBenchmarkConfig, benchmark_headless_rollouts
from game.training.headless_reporting import HeadlessExperimentConfig, write_headless_experiment
from game.training.headless_rollout import (
    ChooserKind,
    CollectorWorkerConfig,
    HeadlessBatchConfig,
    HeadlessRolloutConfig,
)


def _write_experiment(tmp_path, name: str, *, panel: tuple[HeadlessRolloutConfig, ...]):
    backend = create_reduced_run_backend()
    try:
        manifest = backend.manifest()
    finally:
        backend.close()
    config = HeadlessExperimentConfig(
        f"dataset-{name}",
        HeadlessBenchmarkConfig(
            HeadlessBatchConfig(panel, CollectorWorkerConfig(worker_count=1, worker_seed=5)),
            repetitions=1,
        ),
        manifest,
    )
    report = write_headless_experiment(
        tmp_path / name, config, benchmark_headless_rollouts(config.benchmark)
    )
    return TrustedExperimentSource(tmp_path / name, report.sha256)


def _episode(
    identifier: str,
    *,
    seed: int = 7,
    budget: int = 2,
    chooser: ChooserKind = ChooserKind.STRUCTURAL_HEURISTIC,
    policy_seed: int = 11,
) -> HeadlessRolloutConfig:
    return HeadlessRolloutConfig(
        identifier,
        HeadlessRunConfig("simple__starter", CONTENT_FINGERPRINT, seed, {}),
        budget,
        chooser,
        policy_seed,
    )


def test_loads_only_public_actor_boundary_and_has_deterministic_order(tmp_path) -> None:
    source = _write_experiment(
        tmp_path, "development", panel=(_episode("dev-b", seed=8), _episode("dev-a"))
    )

    dataset = load_actor_dataset(development=(source,), held_out=())

    assert dataset.development.split is ActorSplit.DEVELOPMENT
    assert tuple(dataset.development) == dataset.development.examples
    assert [item.provenance.trajectory_id for item in dataset.development] == [
        "dev-b", "dev-b", "dev-a", "dev-a"
    ]
    assert all(item.chosen_candidate_id in {
        candidate.candidate_id for candidate in item.policy_view.candidates
    } for item in dataset.development)
    assert all(set(item.__dataclass_fields__) == {
        "policy_view", "chosen_candidate_id", "provenance"
    } for item in dataset.development)
    assert dataset.development.skip_counts.non_actionable_records == 0
    assert dataset.development.skip_counts.actionable_without_choice_records == 2


def test_final_non_actionable_and_interrupted_no_choice_are_counted_exactly(tmp_path) -> None:
    source = _write_experiment(
        tmp_path,
        "mixed",
        panel=(
            _episode("interrupted", budget=0),
            _episode("terminal", budget=300, seed=9),
        ),
    )

    dataset = load_actor_dataset(development=(source,), held_out=())

    assert dataset.development.skip_counts.actionable_without_choice_records == 1
    assert dataset.development.skip_counts.non_actionable_records == 1
    assert dataset.development.skip_counts.total == 2


def test_duplicate_sample_identity_within_split_rejects(tmp_path) -> None:
    source = _write_experiment(tmp_path, "duplicates", panel=(_episode("same"),))

    with pytest.raises(ActorDatasetValidationError, match="Duplicate actor sample identity"):
        load_actor_dataset(development=(source, source), held_out=())


def test_cross_split_overlap_uses_pins_and_run_config_not_display_or_chooser_fields(tmp_path) -> None:
    development = _write_experiment(
        tmp_path, "development", panel=(_episode("development-display", budget=1),)
    )
    held_out = _write_experiment(
        tmp_path,
        "held-out",
        panel=(
            _episode(
                "held-out-display",
                budget=300,
                chooser=ChooserKind.FIRST_LEGAL,
                policy_seed=999,
            ),
        ),
    )

    with pytest.raises(ActorDatasetValidationError, match="overlap"):
        load_actor_dataset(development=(development,), held_out=(held_out,))


def test_distinct_run_config_permits_declared_panel_separation(tmp_path) -> None:
    development = _write_experiment(tmp_path, "development", panel=(_episode("dev", seed=7),))
    held_out = _write_experiment(tmp_path, "held-out", panel=(_episode("held", seed=8),))

    dataset = load_actor_dataset(development=(development,), held_out=(held_out,))

    assert len(dataset.development) == len(dataset.held_out) == 2
    assert dataset.panel(ActorSplit.HELD_OUT) is dataset.held_out


def test_manifest_anchor_and_trajectory_pin_mismatch_reject(tmp_path, monkeypatch) -> None:
    source = _write_experiment(tmp_path, "trusted", panel=(_episode("trusted"),))
    with pytest.raises(ActorDatasetValidationError, match="Trusted experiment loading failed"):
        load_actor_dataset(
            development=(TrustedExperimentSource(source.root, "0" * 64),), held_out=()
        )

    import game.data.headless_policy_dataset as dataset_module
    from game.training.headless_reporting import load_headless_experiment

    loaded = load_headless_experiment(
        source.root, expected_manifest_sha256=source.expected_manifest_sha256
    )
    key, trajectory = next(iter(loaded.trajectories.items()))
    class _PinMismatchedTrajectory:
        manifest = replace(trajectory.manifest, backend_fingerprint="0" * 64)
        manifest_sha256 = trajectory.manifest_sha256
        policy_replay_jsonl = trajectory.policy_replay_jsonl

    bad_trajectory = _PinMismatchedTrajectory()
    bad_loaded = replace(loaded, trajectories={key: bad_trajectory})
    monkeypatch.setattr(dataset_module, "load_headless_experiment", lambda *_args, **_kwargs: bad_loaded)
    with pytest.raises(ActorDatasetValidationError, match="pins"):
        load_actor_dataset(development=(source,), held_out=())


def test_actor_loader_never_decodes_target_or_audit_streams(tmp_path, monkeypatch) -> None:
    source = _write_experiment(tmp_path, "policy-only", panel=(_episode("policy-only"),))
    import game.data.headless_policy_dataset as dataset_module

    original = dataset_module.load_headless_experiment
    loaded = original(source.root, expected_manifest_sha256=source.expected_manifest_sha256)
    monkeypatch.setattr(
        "game.data.headless_trajectory.decode_hindsight_targets",
        lambda _raw: pytest.fail("target stream entered actor dataset"),
    )
    monkeypatch.setattr(
        "game.data.headless_trajectory.decode_synthetic_audit",
        lambda _raw: pytest.fail("audit stream entered actor dataset"),
    )
    # The established trusted loader validates those streams before this consumer
    # sees a trajectory.  Substitute a trusted preloaded object so this test
    # isolates the dataset's own policy-only conversion boundary.
    monkeypatch.setattr(dataset_module, "load_headless_experiment", lambda *_args, **_kwargs: loaded)

    dataset = load_actor_dataset(development=(source,), held_out=())

    assert len(dataset.development) == 2
