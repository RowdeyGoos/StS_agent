"""End-to-end tests for the bounded deterministic behavior-cloning join."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
import torch

from game.agents.headless_candidate_policy import (
    MODEL_FINGERPRINT,
    CandidatePolicyConfig,
    HeadlessCandidatePolicy,
    config_fingerprint as candidate_config_fingerprint,
)
from game.agents.headless_encoding import ENCODING_FINGERPRINT
from game.backends.headless.reduced_run_backend import (
    HeadlessRunConfig,
    create_reduced_run_backend,
)
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import canonical_json_bytes
from game.data.headless_policy_dataset import TrustedExperimentSource
from game.training.headless_behavior_clone import (
    ACCEPTANCE_FILE_NAME,
    CHECKPOINT_FILE_NAME,
    CLAIM,
    REPORT_FILE_NAME,
    TRAINING_FINGERPRINT,
    BehaviorCloneCancelled,
    BehaviorCloneConfig,
    BehaviorCloneError,
    _checkpoint_digest,
    _masked_loss,
    _state_dict_sha256,
    _verify_artifact_values,
    load_behavior_clone_artifact,
    train_headless_behavior_clone,
)
from game.training.headless_benchmark import (
    HeadlessBenchmarkConfig,
    benchmark_headless_rollouts,
)
from game.training.headless_reporting import (
    HeadlessExperimentConfig,
    write_headless_experiment,
)
from game.training.headless_rollout import (
    ChooserKind,
    CollectorWorkerConfig,
    HeadlessBatchConfig,
    HeadlessRolloutConfig,
)


def _accepted_manifest():
    backend = create_reduced_run_backend()
    try:
        return backend.manifest()
    finally:
        backend.close()


def _episode(
    identifier: str,
    *,
    seed: int,
    budget: int = 3,
    chooser: ChooserKind = ChooserKind.STRUCTURAL_HEURISTIC,
) -> HeadlessRolloutConfig:
    return HeadlessRolloutConfig(
        identifier,
        HeadlessRunConfig("simple__starter", CONTENT_FINGERPRINT, seed, {}),
        budget,
        chooser,
        policy_seed=19,
    )


def _write_source(
    tmp_path: Path,
    name: str,
    episodes: tuple[HeadlessRolloutConfig, ...],
) -> tuple[TrustedExperimentSource, object]:
    manifest = _accepted_manifest()
    config = HeadlessExperimentConfig(
        name,
        HeadlessBenchmarkConfig(
            HeadlessBatchConfig(
                episodes, CollectorWorkerConfig(worker_count=1, worker_seed=23)
            ),
            repetitions=1,
        ),
        manifest,
    )
    report = write_headless_experiment(
        tmp_path / name,
        config,
        benchmark_headless_rollouts(config.benchmark),
    )
    return TrustedExperimentSource(tmp_path / name, report.sha256), manifest


def _panels(tmp_path: Path):
    development, manifest = _write_source(
        tmp_path,
        "bc-development",
        (
            _episode("development-eligible", seed=7),
            _episode("development-zero-example", seed=9, budget=0),
        ),
    )
    held_out, _ = _write_source(
        tmp_path,
        "bc-held-out",
        (_episode("held-out-eligible", seed=8),),
    )
    return development, held_out, manifest


def _torch_globals():
    return {
        "rng": torch.random.get_rng_state().clone(),
        "threads": torch.get_num_threads(),
        "dtype": torch.get_default_dtype(),
        "deterministic": torch.are_deterministic_algorithms_enabled(),
        "warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
    }


def _assert_torch_globals_equal(expected) -> None:
    assert torch.equal(torch.random.get_rng_state(), expected["rng"])
    assert torch.get_num_threads() == expected["threads"]
    assert torch.get_default_dtype() == expected["dtype"]
    assert torch.are_deterministic_algorithms_enabled() == expected["deterministic"]
    assert (
        torch.is_deterministic_algorithms_warn_only_enabled()
        == expected["warn_only"]
    )


def _verify_reanchored(report, checkpoint):
    report_bytes = canonical_json_bytes(report)
    report_sha = sha256(report_bytes).hexdigest()
    changed = deepcopy(checkpoint)
    changed["report_sha256"] = report_sha
    changed["checkpoint_sha256"] = _checkpoint_digest(changed)
    return _verify_artifact_values(
        report_bytes,
        changed,
        expected_report_sha256=report_sha,
        expected_checkpoint_sha256=changed["checkpoint_sha256"],
    )


def test_real_trusted_panels_are_byte_and_tensor_deterministic_with_exact_provenance(
    tmp_path,
) -> None:
    development, held_out, manifest = _panels(tmp_path)
    config = BehaviorCloneConfig(seed=37, epochs=2, batch_size=2)
    before = _torch_globals()

    first = train_headless_behavior_clone(
        development=(development,),
        held_out=(held_out,),
        accepted_backend_manifest=manifest,
        config=config,
    )
    second = train_headless_behavior_clone(
        development=(development,),
        held_out=(held_out,),
        accepted_backend_manifest=manifest,
        config=config,
    )

    assert first.report_bytes == second.report_bytes
    assert first.report_sha256 == second.report_sha256
    assert first.checkpoint_sha256 == second.checkpoint_sha256
    first_state = first.checkpoint_payload["policy"]["state_dict"]
    second_state = second.checkpoint_payload["policy"]["state_dict"]
    assert set(first_state) == set(second_state)
    assert all(torch.equal(first_state[name], second_state[name]) for name in first_state)
    report = first.report_dict()
    assert report["claim"] == CLAIM
    assert report["pins"]["encoding_fingerprint"] == ENCODING_FINGERPRINT
    assert report["pins"]["model_fingerprint"] == MODEL_FINGERPRINT
    assert report["pins"]["training_fingerprint"] == TRAINING_FINGERPRINT
    assert report["aggregate_evidence_labels"] == [
        "combat_v0",
        "structural_fixture",
    ]
    development_report = report["panels"]["development"]
    assert [item["trajectory_id"] for item in development_report["admitted_trajectories"]] == [
        "development-eligible",
        "development-zero-example",
    ]
    assert all(
        [evidence["component"] for evidence in item["evidence"]]
        == sorted(evidence["component"] for evidence in item["evidence"])
        for item in development_report["admitted_trajectories"]
    )
    held_metrics = report["panels"]["held_out"]["metrics"]
    assert held_metrics["accuracy_total"] > 0
    assert 0 <= held_metrics["accuracy_correct"] <= held_metrics["accuracy_total"]
    assert held_metrics["loss_nano"] >= 0
    assert report["training_result"]["finite_gradients"] is True
    _assert_torch_globals_equal(before)


def test_publication_round_trip_requires_complete_anchored_pair(tmp_path) -> None:
    development, held_out, manifest = _panels(tmp_path)
    output_root = tmp_path / "published-smoke"

    artifact = train_headless_behavior_clone(
        development=(development,),
        held_out=(held_out,),
        accepted_backend_manifest=manifest,
        output_root=output_root,
    )
    before_load = _torch_globals()
    loaded = load_behavior_clone_artifact(
        output_root,
        expected_report_sha256=artifact.report_sha256,
        expected_checkpoint_sha256=artifact.checkpoint_sha256,
    )

    assert {item.name for item in output_root.iterdir()} == {
        REPORT_FILE_NAME,
        CHECKPOINT_FILE_NAME,
        ACCEPTANCE_FILE_NAME,
    }
    assert loaded.report_bytes == artifact.report_bytes
    assert loaded.checkpoint_sha256 == artifact.checkpoint_sha256
    assert loaded.output_root == output_root
    policy = loaded.load_policy()
    assert all(
        parameter.device.type == "cpu" and parameter.dtype == torch.float32
        for parameter in policy.parameters()
    )
    _assert_torch_globals_equal(before_load)
    with pytest.raises(FileExistsError):
        train_headless_behavior_clone(
            development=(development,),
            held_out=(held_out,),
            accepted_backend_manifest=manifest,
            output_root=output_root,
        )


def test_float64_caller_can_train_and_load_without_global_state_leaks(tmp_path) -> None:
    development, held_out, manifest = _panels(tmp_path)
    output_root = tmp_path / "float64-caller"
    original_dtype = torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float64)
        before = _torch_globals()
        artifact = train_headless_behavior_clone(
            development=(development,),
            held_out=(held_out,),
            accepted_backend_manifest=manifest,
            output_root=output_root,
        )
        _assert_torch_globals_equal(before)

        returned_policy = artifact.load_policy()
        assert all(
            parameter.device.type == "cpu" and parameter.dtype == torch.float32
            for parameter in returned_policy.parameters()
        )
        _assert_torch_globals_equal(before)

        loaded = load_behavior_clone_artifact(
            output_root,
            expected_report_sha256=artifact.report_sha256,
            expected_checkpoint_sha256=artifact.checkpoint_sha256,
        )
        published_policy = loaded.load_policy()
        assert all(
            parameter.device.type == "cpu" and parameter.dtype == torch.float32
            for parameter in published_policy.parameters()
        )
        _assert_torch_globals_equal(before)

        malformed = deepcopy(artifact.checkpoint_payload)
        malformed["policy"]["encoding_fingerprint"] = "0" * 64
        with pytest.raises(BehaviorCloneError):
            _verify_artifact_values(
                artifact.report_bytes,
                malformed,
                expected_report_sha256=artifact.report_sha256,
                expected_checkpoint_sha256=artifact.checkpoint_sha256,
            )
        _assert_torch_globals_equal(before)
    finally:
        torch.set_default_dtype(original_dtype)


def test_reanchored_pair_rejects_changed_policy_config_and_nested_report_facts(
    tmp_path,
) -> None:
    development, held_out, manifest = _panels(tmp_path)
    artifact = train_headless_behavior_clone(
        development=(development,),
        held_out=(held_out,),
        accepted_backend_manifest=manifest,
    )

    changed_checkpoint = deepcopy(artifact.checkpoint_payload)
    alternate = HeadlessCandidatePolicy(CandidatePolicyConfig(hidden_size=32))
    alternate_payload = alternate.checkpoint_payload()
    alternate_payload["state_dict"] = {
        name: value.detach().cpu().clone()
        for name, value in alternate_payload["state_dict"].items()
    }
    changed_checkpoint["policy"] = alternate_payload
    changed_state_sha = _state_dict_sha256(alternate_payload["state_dict"])
    changed_checkpoint["state_dict_sha256"] = changed_state_sha
    changed_report = artifact.report_dict()
    changed_report["pins"]["state_dict_sha256"] = changed_state_sha
    with pytest.raises(BehaviorCloneError, match="candidate-policy provenance"):
        _verify_reanchored(changed_report, changed_checkpoint)

    mutations = []
    aggregate_subset = artifact.report_dict()
    aggregate_subset["aggregate_evidence_labels"] = ["combat_v0"]
    mutations.append((aggregate_subset, "admitted evidence"))
    unknown_environment = artifact.report_dict()
    unknown_environment["environment"]["unknown"] = "unaccepted"
    mutations.append((unknown_environment, "environment"))
    wrong_source = artifact.report_dict()
    wrong_source["panels"]["development"]["source_manifest_sha256"] = ["0" * 64]
    mutations.append((wrong_source, "declared source"))
    wrong_updates = artifact.report_dict()
    wrong_updates["training_result"]["optimizer_update_count"] += 1
    mutations.append((wrong_updates, "training arithmetic"))

    for changed_report, message in mutations:
        with pytest.raises(BehaviorCloneError, match=message):
            _verify_reanchored(changed_report, artifact.checkpoint_payload)


def test_report_checkpoint_and_dependency_pin_inconsistency_rejects(tmp_path) -> None:
    development, held_out, manifest = _panels(tmp_path)
    output_root = tmp_path / "tamper-smoke"
    artifact = train_headless_behavior_clone(
        development=(development,),
        held_out=(held_out,),
        accepted_backend_manifest=manifest,
        output_root=output_root,
    )

    report = json.loads((output_root / REPORT_FILE_NAME).read_text(encoding="utf-8"))
    report["pins"]["encoding_fingerprint"] = "0" * 64
    changed_report = canonical_json_bytes(report)
    (output_root / REPORT_FILE_NAME).write_bytes(changed_report)
    marker = json.loads((output_root / ACCEPTANCE_FILE_NAME).read_text(encoding="utf-8"))
    marker["report_sha256"] = sha256(changed_report).hexdigest()
    (output_root / ACCEPTANCE_FILE_NAME).write_bytes(canonical_json_bytes(marker))
    with pytest.raises(BehaviorCloneError, match="dependency pins"):
        load_behavior_clone_artifact(
            output_root,
            expected_report_sha256=marker["report_sha256"],
            expected_checkpoint_sha256=artifact.checkpoint_sha256,
        )

    # Recreate the exact artifact, then modify one checkpoint tensor while
    # retaining the original report and logical checkpoint anchors.
    second_root = tmp_path / "tensor-tamper"
    second = train_headless_behavior_clone(
        development=(development,),
        held_out=(held_out,),
        accepted_backend_manifest=manifest,
        output_root=second_root,
    )
    checkpoint = torch.load(
        second_root / CHECKPOINT_FILE_NAME, map_location="cpu", weights_only=True
    )
    name = next(iter(checkpoint["policy"]["state_dict"]))
    checkpoint["policy"]["state_dict"][name].view(-1)[0] += 1.0
    torch.save(checkpoint, second_root / CHECKPOINT_FILE_NAME)
    with pytest.raises(BehaviorCloneError, match="inconsistent|digest"):
        load_behavior_clone_artifact(
            second_root,
            expected_report_sha256=second.report_sha256,
            expected_checkpoint_sha256=second.checkpoint_sha256,
        )


def test_cancellation_after_an_update_restores_torch_and_publishes_nothing(tmp_path) -> None:
    development, held_out, manifest = _panels(tmp_path)
    before = _torch_globals()
    calls = 0

    def cancel_requested() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 6

    output_root = tmp_path / "cancelled-smoke"
    with pytest.raises(BehaviorCloneCancelled):
        train_headless_behavior_clone(
            development=(development,),
            held_out=(held_out,),
            accepted_backend_manifest=manifest,
            config=BehaviorCloneConfig(epochs=4),
            cancel_requested=cancel_requested,
            output_root=output_root,
        )

    assert not output_root.exists()
    assert not list(tmp_path.glob(".cancelled-smoke.incomplete-*"))
    _assert_torch_globals_equal(before)


def test_empty_eligible_panel_and_non_structural_source_are_explicit_errors(
    tmp_path,
) -> None:
    development, manifest = _write_source(
        tmp_path,
        "invalid-development",
        (_episode("invalid-development", seed=7, chooser=ChooserKind.FIRST_LEGAL),),
    )
    held_out, _ = _write_source(
        tmp_path,
        "zero-held-out",
        (_episode("zero-held-out", seed=8, budget=0),),
    )
    with pytest.raises(BehaviorCloneError, match="structural-heuristic"):
        train_headless_behavior_clone(
            development=(development,),
            held_out=(held_out,),
            accepted_backend_manifest=manifest,
        )

    valid_development, _ = _write_source(
        tmp_path,
        "valid-development",
        (_episode("valid-development", seed=10),),
    )
    with pytest.raises(BehaviorCloneError, match="no eligible actor examples"):
        train_headless_behavior_clone(
            development=(valid_development,),
            held_out=(held_out,),
            accepted_backend_manifest=manifest,
        )
    with pytest.raises(BehaviorCloneError, match="at least one trusted source"):
        train_headless_behavior_clone(
            development=(valid_development,),
            held_out=(),
            accepted_backend_manifest=manifest,
        )


def test_loss_masks_padding_explicitly_and_frozen_default_model_pin_is_exact() -> None:
    logits = torch.tensor([[0.0, 1_000_000.0], [0.0, 1.0]], dtype=torch.float32)
    mask = torch.tensor([[True, False], [True, True]], dtype=torch.bool).numpy()
    targets = torch.tensor([0, 1], dtype=torch.long)

    loss = _masked_loss(logits, mask, targets)

    assert torch.isfinite(loss)
    assert loss.item() == pytest.approx(
        torch.nn.functional.cross_entropy(
            torch.tensor([[0.0, -torch.inf], [0.0, 1.0]]), targets
        ).item()
    )
    assert candidate_config_fingerprint(CandidatePolicyConfig()) == (
        "6ab0c79dc5ff04ca66646dbb870145d3b29983367970a6235ed7fba70f9a2ac2"
    )
