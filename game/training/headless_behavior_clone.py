"""Deterministic behavior-cloning plumbing for trusted headless actor panels.

This is a deliberately small proof that the accepted public encoder, trusted
actor dataset, and variable-candidate policy can be joined safely.  It is not a
target-game policy, a fidelity result, or a general training entry point.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

import torch
from torch import Tensor
from torch.nn import functional as F

from game.agents.headless_candidate_policy import (
    MODEL_FINGERPRINT,
    POLICY_VERSION,
    CandidatePolicyConfig,
    CandidatePolicyError,
    HeadlessCandidatePolicy,
    config_fingerprint as candidate_config_fingerprint,
)
from game.agents.headless_encoding import (
    ENCODING_FINGERPRINT,
    ENCODING_VERSION,
    collate_policy_views,
    encode_policy_view,
)
from game.contracts.headless_v0 import (
    BackendManifest,
    ComponentEvidence,
    ContractValidationError,
    EvidenceLabel,
    canonical_json_bytes,
)
from game.data.headless_policy_dataset import (
    ActorDataset,
    ActorExample,
    ActorSplitDataset,
    TrustedExperimentSource,
    load_actor_dataset,
)
from game.training.headless_reporting import (
    ExperimentIntegrityError,
    ExperimentValidationError,
    load_headless_experiment,
)
from game.training.headless_rollout import ChooserKind


BEHAVIOR_CLONE_VERSION = "headless_behavior_clone_v1"
REPORT_SCHEMA = "headless_behavior_clone_v1.report.v1"
CHECKPOINT_SCHEMA = "headless_behavior_clone_v1.checkpoint.v1"
ACCEPTANCE_SCHEMA = "headless_behavior_clone_v1.acceptance.v1"
REPORT_FILE_NAME = "behavior_clone.report.json"
CHECKPOINT_FILE_NAME = "behavior_clone.checkpoint.pt"
ACCEPTANCE_FILE_NAME = "artifact.accepted.json"
CLAIM = "structural_heuristic_imitation_plumbing_only"

_EXPECTED_ENCODING_FINGERPRINT = (
    "3eee27f82ad803d1d47ac5d2ac6ba6fcce2d236f977fde589fe6ee38a9608fa1"
)
_EXPECTED_MODEL_FINGERPRINT = (
    "aa645dcb765ec55eaa74cffc0c367e12671d159a9f42a71024739c48f3dc43d6"
)
_EXPECTED_CANDIDATE_CONFIG_FINGERPRINT = (
    "6ab0c79dc5ff04ca66646dbb870145d3b29983367970a6235ed7fba70f9a2ac2"
)
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_LOSS_SCALE = 1_000_000_000
_MAX_SOURCES_PER_PANEL = 128
_MAX_TRAJECTORIES_PER_PANEL = 4_096
_MAX_EXAMPLES_PER_PANEL = 16_384
_MAX_REPORT_BYTES = 4 * 1024 * 1024
_MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024


class BehaviorCloneError(ValueError):
    """Raised when smoke conditions or artifact provenance are invalid."""


class BehaviorCloneCancelled(RuntimeError):
    """Raised at a cooperative cancellation boundary before publication."""


def _domain_hash(domain: str, value: Mapping[str, Any]) -> str:
    return sha256(
        domain.encode("utf-8") + bytes((0,)) + canonical_json_bytes(value)
    ).hexdigest()


TRAINING_FINGERPRINT = _domain_hash(
    "headless_behavior_clone_v1.training.v1",
    {
        "behavior_clone_version": BEHAVIOR_CLONE_VERSION,
        "candidate_config_fingerprint": _EXPECTED_CANDIDATE_CONFIG_FINGERPRINT,
        "claim": CLAIM,
        "device": "cpu",
        "dtype": "float32",
        "encoding_fingerprint": _EXPECTED_ENCODING_FINGERPRINT,
        "loss": "masked_cross_entropy_explicit_negative_infinity_padding",
        "model_fingerprint": _EXPECTED_MODEL_FINGERPRINT,
        "optimizer": "torch.optim.SGD",
        "order": "declared_source_repetition_episode_policy_ordinal_no_shuffle",
        "report_schema": REPORT_SCHEMA,
        "thread_count": 1,
    },
)


@dataclass(frozen=True, slots=True)
class BehaviorCloneConfig:
    """Small bounded training configuration; rates use exact nano-units."""

    seed: int = 0
    epochs: int = 2
    batch_size: int = 16
    learning_rate_nano: int = 10_000_000

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise BehaviorCloneError("seed must be an integer, not bool.")
        if (
            not isinstance(self.epochs, int)
            or isinstance(self.epochs, bool)
            or not 1 <= self.epochs <= 16
        ):
            raise BehaviorCloneError("epochs must be an integer in [1, 16].")
        if (
            not isinstance(self.batch_size, int)
            or isinstance(self.batch_size, bool)
            or not 1 <= self.batch_size <= 256
        ):
            raise BehaviorCloneError("batch_size must be an integer in [1, 256].")
        if (
            not isinstance(self.learning_rate_nano, int)
            or isinstance(self.learning_rate_nano, bool)
            or not 1 <= self.learning_rate_nano <= 1_000_000_000
        ):
            raise BehaviorCloneError(
                "learning_rate_nano must be an integer in [1, 1000000000]."
            )

    @property
    def learning_rate(self) -> float:
        return self.learning_rate_nano / _LOSS_SCALE

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        return _domain_hash(
            "headless_behavior_clone_v1.config.v1",
            {
                "behavior_clone_version": BEHAVIOR_CLONE_VERSION,
                "training_fingerprint": TRAINING_FINGERPRINT,
                "config": self.to_dict(),
            },
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BehaviorCloneConfig":
        if not isinstance(value, Mapping) or set(value) != {
            "seed",
            "epochs",
            "batch_size",
            "learning_rate_nano",
        }:
            raise BehaviorCloneError("behavior-clone config fields are not exact.")
        try:
            return cls(**dict(value))
        except TypeError as exc:
            raise BehaviorCloneError("behavior-clone config is invalid.") from exc


@dataclass(frozen=True, slots=True)
class BehaviorCloneArtifact:
    """Validated report/checkpoint values, optionally published to one root."""

    report_bytes: bytes
    checkpoint_payload: Mapping[str, Any]
    report_sha256: str
    checkpoint_sha256: str
    output_root: Path | None = None

    def report_dict(self) -> dict[str, Any]:
        return json.loads(self.report_bytes.decode("utf-8"))

    def load_policy(self) -> HeadlessCandidatePolicy:
        policy = self.checkpoint_payload["policy"]
        if not isinstance(policy, Mapping):  # pragma: no cover - constructor verifies
            raise BehaviorCloneError("checkpoint policy payload is invalid.")
        with _preserve_torch_rng():
            return HeadlessCandidatePolicy.from_checkpoint_payload(policy, device="cpu")


def _assert_frozen_dependencies() -> None:
    if (
        ENCODING_VERSION != "headless_encoding_v1"
        or ENCODING_FINGERPRINT != _EXPECTED_ENCODING_FINGERPRINT
    ):
        raise BehaviorCloneError("accepted headless encoding pin changed.")
    if (
        POLICY_VERSION != "headless_candidate_policy_v1"
        or MODEL_FINGERPRINT != _EXPECTED_MODEL_FINGERPRINT
    ):
        raise BehaviorCloneError("accepted candidate-policy model pin changed.")
    if (
        candidate_config_fingerprint(CandidatePolicyConfig())
        != _EXPECTED_CANDIDATE_CONFIG_FINGERPRINT
    ):
        raise BehaviorCloneError("accepted candidate-policy config pin changed.")


def _cancel_if_requested(cancel_requested: Callable[[], bool] | None) -> None:
    if cancel_requested is None:
        return
    if not callable(cancel_requested):
        raise TypeError("cancel_requested must be callable or None.")
    if cancel_requested():
        raise BehaviorCloneCancelled("behavior-clone smoke cancelled before publication")


@contextmanager
def _deterministic_torch(seed: int) -> Iterator[None]:
    """Temporarily establish and then exactly restore the touched Torch globals."""

    previous_rng = torch.random.get_rng_state().clone()
    previous_threads = torch.get_num_threads()
    previous_dtype = torch.get_default_dtype()
    previous_deterministic = torch.are_deterministic_algorithms_enabled()
    previous_warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    try:
        torch.set_num_threads(1)
        torch.set_default_dtype(torch.float32)
        torch.use_deterministic_algorithms(True, warn_only=False)
        # Seed only the CPU default generator used by CPU module initialization.
        torch.random.default_generator.manual_seed(seed)
        yield
    finally:
        torch.random.set_rng_state(previous_rng)
        torch.use_deterministic_algorithms(
            previous_deterministic, warn_only=previous_warn_only
        )
        torch.set_default_dtype(previous_dtype)
        torch.set_num_threads(previous_threads)


@contextmanager
def _preserve_torch_rng() -> Iterator[None]:
    """Construct CPU checkpoints in float32 without leaking caller Torch state."""

    previous_rng = torch.random.get_rng_state().clone()
    previous_dtype = torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float32)
        yield
    finally:
        torch.random.set_rng_state(previous_rng)
        torch.set_default_dtype(previous_dtype)


def _provenance_dict(value: Any) -> dict[str, Any]:
    return {
        "experiment_manifest_sha256": value.experiment_manifest_sha256,
        "policy_record_ordinal": value.policy_record_ordinal,
        "repetition_index": value.repetition_index,
        "trajectory_id": value.trajectory_id,
        "trajectory_manifest_sha256": value.trajectory_manifest_sha256,
    }


def _trajectory_dict(value: Any) -> dict[str, Any]:
    return {
        "evidence": [item.to_dict() for item in value.evidence],
        "experiment_manifest_sha256": value.experiment_manifest_sha256,
        "repetition_index": value.repetition_index,
        "trajectory_id": value.trajectory_id,
        "trajectory_manifest_sha256": value.trajectory_manifest_sha256,
    }


def _panel_identity(
    panel: ActorSplitDataset, sources: Sequence[TrustedExperimentSource]
) -> dict[str, Any]:
    return {
        "admitted_trajectories": [
            _trajectory_dict(item) for item in panel.admitted_trajectories
        ],
        "examples": [
            {
                "chosen_candidate_id": item.chosen_candidate_id,
                "provenance": _provenance_dict(item.provenance),
            }
            for item in panel.examples
        ],
        "source_manifest_sha256": [item.expected_manifest_sha256 for item in sources],
        "split": panel.split.value,
    }


def _data_identity(
    dataset: ActorDataset,
    development: Sequence[TrustedExperimentSource],
    held_out: Sequence[TrustedExperimentSource],
    accepted_backend_manifest: BackendManifest,
) -> tuple[str, dict[str, Any]]:
    identity = {
        "accepted_backend_manifest": accepted_backend_manifest.to_dict(),
        "development": _panel_identity(dataset.development, development),
        "held_out": _panel_identity(dataset.held_out, held_out),
    }
    return _domain_hash("headless_behavior_clone_v1.data.v1", identity), identity


def _validate_sources(
    sources: Sequence[TrustedExperimentSource],
    *,
    panel_name: str,
    cancel_requested: Callable[[], bool] | None,
) -> None:
    if not sources:
        raise BehaviorCloneError(f"{panel_name} must declare at least one trusted source.")
    if len(sources) > _MAX_SOURCES_PER_PANEL:
        raise BehaviorCloneError(f"{panel_name} declares too many trusted sources.")
    for source in sources:
        _cancel_if_requested(cancel_requested)
        try:
            loaded = load_headless_experiment(
                source.root,
                expected_manifest_sha256=source.expected_manifest_sha256,
            )
        except (ExperimentIntegrityError, ExperimentValidationError, OSError) as exc:
            raise BehaviorCloneError(
                f"{panel_name} structural-heuristic source validation failed."
            ) from exc
        if any(
            episode.chooser_kind is not ChooserKind.STRUCTURAL_HEURISTIC
            for episode in loaded.config.benchmark.batch.episodes
        ):
            raise BehaviorCloneError(
                f"{panel_name} must contain only structural-heuristic episodes."
            )


def _validate_dataset_bounds(dataset: ActorDataset) -> None:
    for panel in (dataset.development, dataset.held_out):
        if not panel.examples:
            raise BehaviorCloneError(
                f"{panel.split.value} has no eligible actor examples."
            )
        if len(panel.examples) > _MAX_EXAMPLES_PER_PANEL:
            raise BehaviorCloneError(f"{panel.split.value} has too many actor examples.")
        if len(panel.admitted_trajectories) > _MAX_TRAJECTORIES_PER_PANEL:
            raise BehaviorCloneError(
                f"{panel.split.value} has too many admitted trajectories."
            )
    if not dataset.aggregate_evidence_labels:
        raise BehaviorCloneError("actor dataset has no component evidence labels.")


def _batches(
    values: Sequence[ActorExample], batch_size: int
) -> Iterator[Sequence[ActorExample]]:
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


def _prepared_batch(examples: Sequence[ActorExample]) -> tuple[Any, Tensor]:
    encoded = tuple(encode_policy_view(item.policy_view) for item in examples)
    batch = collate_policy_views(encoded)
    targets: list[int] = []
    for item, candidate_ids in zip(examples, batch.candidate_ids):
        try:
            targets.append(candidate_ids.index(item.chosen_candidate_id))
        except ValueError as exc:  # Defensive join check after accepted loader/encoder.
            raise BehaviorCloneError(
                "chosen candidate is absent from its encoded advertised set."
            ) from exc
    return batch, torch.tensor(targets, dtype=torch.long, device="cpu")


def _masked_loss(logits: Tensor, candidate_mask: Any, targets: Tensor) -> Tensor:
    mask = torch.as_tensor(candidate_mask, dtype=torch.bool, device="cpu")
    if logits.device.type != "cpu" or logits.dtype != torch.float32:
        raise BehaviorCloneError("behavior-clone logits must be CPU float32.")
    if logits.shape != mask.shape or logits.shape[0] != targets.shape[0]:
        raise BehaviorCloneError("behavior-clone loss inputs do not align.")
    if logits.shape[1] == 0 or not bool(mask.any(dim=1).all().item()):
        raise BehaviorCloneError("every actor example must advertise a candidate.")
    rows = torch.arange(targets.shape[0], device="cpu")
    if not bool(mask[rows, targets].all().item()):
        raise BehaviorCloneError("a behavior-clone target selects padding.")
    # The candidate model deliberately emits zero at padding.  Zero is not a
    # legal logit, so the supervised loss applies its own explicit hard mask.
    masked_logits = logits.masked_fill(~mask, -torch.inf)
    loss = F.cross_entropy(masked_logits, targets, reduction="mean")
    if not bool(torch.isfinite(loss).item()):
        raise BehaviorCloneError("behavior-clone loss is non-finite.")
    return loss


def _evaluate(
    policy: HeadlessCandidatePolicy,
    panel: ActorSplitDataset,
    batch_size: int,
    cancel_requested: Callable[[], bool] | None,
) -> dict[str, int]:
    total_loss = 0.0
    correct = 0
    count = 0
    policy.eval()
    with torch.no_grad():
        for examples in _batches(panel.examples, batch_size):
            _cancel_if_requested(cancel_requested)
            batch, targets = _prepared_batch(examples)
            logits = policy(batch)
            mask = torch.as_tensor(batch.candidate_mask, dtype=torch.bool)
            masked_logits = logits.masked_fill(~mask, -torch.inf)
            losses = F.cross_entropy(masked_logits, targets, reduction="none")
            if not bool(torch.isfinite(losses).all().item()):
                raise BehaviorCloneError("evaluation loss is non-finite.")
            selected = policy.select_candidate_ids(batch)
            for row, selected_id in enumerate(selected):
                if selected_id not in batch.candidate_ids[row]:
                    raise BehaviorCloneError(
                        "candidate policy selected outside its advertised set."
                    )
            total_loss += float(losses.sum().item())
            correct += int((masked_logits.argmax(dim=1) == targets).sum().item())
            count += len(examples)
    if count == 0:  # Guarded earlier, retained to keep metric construction total.
        raise BehaviorCloneError(f"{panel.split.value} has no evaluable examples.")
    return {
        "accuracy_correct": correct,
        "accuracy_total": count,
        "loss_nano": int(round((total_loss / count) * _LOSS_SCALE)),
    }


def _state_dict_sha256(state_dict: Mapping[str, Tensor]) -> str:
    entries: list[dict[str, Any]] = []
    for name in sorted(state_dict):
        value = state_dict[name]
        if type(value) is not Tensor or value.device.type != "cpu":
            raise BehaviorCloneError("checkpoint state must contain exact CPU tensors.")
        snapshot = value.detach().contiguous()
        if snapshot.dtype != torch.float32 or not bool(torch.isfinite(snapshot).all().item()):
            raise BehaviorCloneError("checkpoint state must contain finite float32 tensors.")
        entries.append(
            {
                "dtype": "float32",
                "name": name,
                "shape": list(snapshot.shape),
                "tensor_sha256": sha256(snapshot.numpy().tobytes(order="C")).hexdigest(),
            }
        )
    return _domain_hash("headless_behavior_clone_v1.state_dict.v1", {"tensors": entries})


def _snapshot_policy(policy: HeadlessCandidatePolicy) -> dict[str, Any]:
    payload = dict(policy.checkpoint_payload())
    raw_state = payload["state_dict"]
    if not isinstance(raw_state, Mapping):  # pragma: no cover - accepted model contract
        raise BehaviorCloneError("candidate policy returned an invalid state_dict.")
    payload["state_dict"] = {
        name: value.detach().cpu().clone() for name, value in raw_state.items()
    }
    return payload


def _checkpoint_digest(payload: Mapping[str, Any]) -> str:
    policy = payload["policy"]
    if not isinstance(policy, Mapping):
        raise BehaviorCloneError("checkpoint policy metadata is invalid.")
    policy_metadata = {key: value for key, value in policy.items() if key != "state_dict"}
    identity = {
        key: value
        for key, value in payload.items()
        if key not in {"checkpoint_sha256", "policy"}
    }
    identity["policy"] = policy_metadata
    return _domain_hash("headless_behavior_clone_v1.checkpoint.identity.v1", identity)


def _runtime_environment() -> dict[str, Any]:
    return {
        "byteorder": sys.byteorder,
        "deterministic_algorithms": True,
        "deterministic_warn_only": False,
        "device": "cpu",
        "dtype": "float32",
        "machine": platform.machine(),
        "operating_system": platform.system(),
        "operating_system_release": platform.release(),
        "process_count": 1,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "torch_thread_count": 1,
        "torch_version": torch.__version__,
    }


def _panel_report(
    panel: ActorSplitDataset,
    sources: Sequence[TrustedExperimentSource],
    metrics: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "admitted_trajectories": [
            _trajectory_dict(item) for item in panel.admitted_trajectories
        ],
        "example_count": len(panel.examples),
        "metrics": dict(metrics),
        "source_manifest_sha256": [
            source.expected_manifest_sha256 for source in sources
        ],
        "skip_counts": {
            "actionable_without_choice_records": (
                panel.skip_counts.actionable_without_choice_records
            ),
            "non_actionable_records": panel.skip_counts.non_actionable_records,
            "total": panel.skip_counts.total,
        },
    }


def _train(
    dataset: ActorDataset,
    config: BehaviorCloneConfig,
    cancel_requested: Callable[[], bool] | None,
) -> tuple[dict[str, Any], int, bool]:
    policy = HeadlessCandidatePolicy(CandidatePolicyConfig()).to(
        device="cpu", dtype=torch.float32
    )
    if any(
        parameter.device.type != "cpu" or parameter.dtype != torch.float32
        for parameter in policy.parameters()
    ):
        raise BehaviorCloneError("candidate policy is not entirely CPU float32.")
    optimizer = torch.optim.SGD(policy.parameters(), lr=config.learning_rate)
    update_count = 0
    gradients_finite = True
    policy.train()
    for _ in range(config.epochs):
        for examples in _batches(dataset.development.examples, config.batch_size):
            _cancel_if_requested(cancel_requested)
            batch, targets = _prepared_batch(examples)
            optimizer.zero_grad(set_to_none=True)
            loss = _masked_loss(policy(batch), batch.candidate_mask, targets)
            loss.backward()
            gradients = [parameter.grad for parameter in policy.parameters()]
            gradients_finite = gradients_finite and all(
                gradient is not None
                and bool(torch.isfinite(gradient).all().item())
                for gradient in gradients
            )
            if not gradients_finite:
                raise BehaviorCloneError("behavior-clone gradients are non-finite.")
            optimizer.step()
            if any(not bool(torch.isfinite(parameter).all().item()) for parameter in policy.parameters()):
                raise BehaviorCloneError("behavior-clone parameters are non-finite.")
            update_count += 1
            _cancel_if_requested(cancel_requested)
    development_metrics = _evaluate(
        policy, dataset.development, config.batch_size, cancel_requested
    )
    held_out_metrics = _evaluate(
        policy, dataset.held_out, config.batch_size, cancel_requested
    )
    return (
        {
            "policy": _snapshot_policy(policy),
            "development_metrics": development_metrics,
            "held_out_metrics": held_out_metrics,
        },
        update_count,
        gradients_finite,
    )


def _exact(value: Mapping[str, Any], fields: set[str], path: str) -> None:
    if set(value) != fields:
        raise BehaviorCloneError(f"{path} fields are not exact.")


def _report_integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise BehaviorCloneError(f"{path} must be an integer >= {minimum}.")
    return value


def _report_digest(value: Any, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise BehaviorCloneError(f"{path} must be a lowercase SHA-256 digest.")
    return value


def _validate_report_environment(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise BehaviorCloneError("report environment must be an object.")
    fields = {
        "byteorder",
        "deterministic_algorithms",
        "deterministic_warn_only",
        "device",
        "dtype",
        "machine",
        "operating_system",
        "operating_system_release",
        "process_count",
        "python_implementation",
        "python_version",
        "torch_thread_count",
        "torch_version",
    }
    _exact(value, fields, "report environment")
    if (
        value["byteorder"] not in {"little", "big"}
        or value["deterministic_algorithms"] is not True
        or value["deterministic_warn_only"] is not False
        or value["device"] != "cpu"
        or value["dtype"] != "float32"
        or value["process_count"] != 1
        or value["torch_thread_count"] != 1
    ):
        raise BehaviorCloneError("report environment deterministic facts are invalid.")
    for name in (
        "machine",
        "operating_system",
        "operating_system_release",
        "python_implementation",
        "python_version",
        "torch_version",
    ):
        item = value[name]
        if not isinstance(item, str) or not item or len(item.encode("utf-8")) > 256:
            raise BehaviorCloneError(f"report environment {name} is invalid.")


def _validate_report_metrics(value: Any, path: str, example_count: int) -> None:
    if not isinstance(value, Mapping):
        raise BehaviorCloneError(f"{path} must be an object.")
    _exact(value, {"accuracy_correct", "accuracy_total", "loss_nano"}, path)
    correct = _report_integer(value["accuracy_correct"], f"{path}.accuracy_correct")
    total = _report_integer(value["accuracy_total"], f"{path}.accuracy_total", minimum=1)
    _report_integer(value["loss_nano"], f"{path}.loss_nano")
    if total != example_count or correct > total:
        raise BehaviorCloneError(f"{path} does not match its panel example count.")


def _validate_report_skip_counts(value: Any, path: str) -> None:
    if not isinstance(value, Mapping):
        raise BehaviorCloneError(f"{path} must be an object.")
    _exact(
        value,
        {"actionable_without_choice_records", "non_actionable_records", "total"},
        path,
    )
    without_choice = _report_integer(
        value["actionable_without_choice_records"],
        f"{path}.actionable_without_choice_records",
    )
    non_actionable = _report_integer(
        value["non_actionable_records"], f"{path}.non_actionable_records"
    )
    total = _report_integer(value["total"], f"{path}.total")
    if total != without_choice + non_actionable:
        raise BehaviorCloneError(f"{path}.total is inconsistent.")


def _validate_report_trajectory(
    value: Any,
    *,
    path: str,
    source_digests: set[str],
) -> tuple[tuple[str, int, str, str], set[str]]:
    if not isinstance(value, Mapping):
        raise BehaviorCloneError(f"{path} must be an object.")
    _exact(
        value,
        {
            "evidence",
            "experiment_manifest_sha256",
            "repetition_index",
            "trajectory_id",
            "trajectory_manifest_sha256",
        },
        path,
    )
    experiment_sha = _report_digest(
        value["experiment_manifest_sha256"],
        f"{path}.experiment_manifest_sha256",
    )
    if experiment_sha not in source_digests:
        raise BehaviorCloneError(f"{path} does not belong to a declared source.")
    repetition_index = _report_integer(
        value["repetition_index"], f"{path}.repetition_index"
    )
    trajectory_id = value["trajectory_id"]
    if (
        not isinstance(trajectory_id, str)
        or not trajectory_id
        or len(trajectory_id.encode("utf-8")) > 128
    ):
        raise BehaviorCloneError(f"{path}.trajectory_id is invalid.")
    trajectory_sha = _report_digest(
        value["trajectory_manifest_sha256"],
        f"{path}.trajectory_manifest_sha256",
    )
    raw_evidence = value["evidence"]
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise BehaviorCloneError(f"{path}.evidence must be a nonempty array.")
    try:
        evidence = tuple(ComponentEvidence.from_dict(item) for item in raw_evidence)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise BehaviorCloneError(f"{path}.evidence is invalid.") from exc
    components = tuple(item.component for item in evidence)
    if components != tuple(sorted(set(components))):
        raise BehaviorCloneError(f"{path}.evidence components are not unique and sorted.")
    allowed = {EvidenceLabel.COMBAT_V0, EvidenceLabel.STRUCTURAL_FIXTURE}
    if any(item.label not in allowed for item in evidence):
        raise BehaviorCloneError(f"{path}.evidence contains an unaccepted label.")
    return (
        (experiment_sha, repetition_index, trajectory_id, trajectory_sha),
        {item.label.value for item in evidence},
    )


def _validate_report_panel(
    value: Any, *, path: str
) -> tuple[int, set[tuple[str, int, str, str]], set[str]]:
    if not isinstance(value, Mapping):
        raise BehaviorCloneError(f"{path} must be an object.")
    _exact(
        value,
        {
            "admitted_trajectories",
            "example_count",
            "metrics",
            "skip_counts",
            "source_manifest_sha256",
        },
        path,
    )
    source_values = value["source_manifest_sha256"]
    if (
        not isinstance(source_values, list)
        or not 1 <= len(source_values) <= _MAX_SOURCES_PER_PANEL
    ):
        raise BehaviorCloneError(f"{path}.source_manifest_sha256 is invalid.")
    sources = {
        _report_digest(item, f"{path}.source_manifest_sha256")
        for item in source_values
    }
    if len(sources) != len(source_values):
        raise BehaviorCloneError(f"{path} source manifests must be unique.")
    example_count = _report_integer(
        value["example_count"], f"{path}.example_count", minimum=1
    )
    if example_count > _MAX_EXAMPLES_PER_PANEL:
        raise BehaviorCloneError(f"{path}.example_count exceeds the smoke bound.")
    _validate_report_metrics(value["metrics"], f"{path}.metrics", example_count)
    _validate_report_skip_counts(value["skip_counts"], f"{path}.skip_counts")
    trajectories = value["admitted_trajectories"]
    if (
        not isinstance(trajectories, list)
        or not trajectories
        or len(trajectories) > _MAX_TRAJECTORIES_PER_PANEL
    ):
        raise BehaviorCloneError(f"{path}.admitted_trajectories is invalid.")
    identities: set[tuple[str, int, str, str]] = set()
    labels: set[str] = set()
    for index, item in enumerate(trajectories):
        identity, item_labels = _validate_report_trajectory(
            item,
            path=f"{path}.admitted_trajectories[{index}]",
            source_digests=sources,
        )
        if identity in identities:
            raise BehaviorCloneError(f"{path} duplicates admitted trajectory identity.")
        identities.add(identity)
        labels.update(item_labels)
    return example_count, identities, labels


def _validate_report_nested(value: Mapping[str, Any], config: BehaviorCloneConfig) -> None:
    _validate_report_environment(value["environment"])
    panels = value["panels"]
    if not isinstance(panels, Mapping):
        raise BehaviorCloneError("report panels must be an object.")
    _exact(panels, {"development", "held_out"}, "report panels")
    development_count, development_trajectories, development_labels = (
        _validate_report_panel(
            panels["development"], path="report panels.development"
        )
    )
    _, held_out_trajectories, held_out_labels = _validate_report_panel(
        panels["held_out"], path="report panels.held_out"
    )
    if development_trajectories & held_out_trajectories:
        raise BehaviorCloneError("report panels share admitted trajectory identity.")
    labels = value["aggregate_evidence_labels"]
    expected_labels = sorted(development_labels | held_out_labels)
    if labels != expected_labels:
        raise BehaviorCloneError(
            "report aggregate evidence labels do not equal admitted evidence."
        )
    training = value["training_result"]
    if not isinstance(training, Mapping):
        raise BehaviorCloneError("report training_result must be an object.")
    _exact(
        training,
        {
            "finite_gradients",
            "optimizer_update_count",
            "training_example_visits",
        },
        "report training_result",
    )
    if training["finite_gradients"] is not True:
        raise BehaviorCloneError("report must retain finite-gradient acceptance.")
    updates = _report_integer(
        training["optimizer_update_count"],
        "report training_result.optimizer_update_count",
        minimum=1,
    )
    visits = _report_integer(
        training["training_example_visits"],
        "report training_result.training_example_visits",
        minimum=1,
    )
    expected_updates = config.epochs * (
        (development_count + config.batch_size - 1) // config.batch_size
    )
    if updates != expected_updates or visits != development_count * config.epochs:
        raise BehaviorCloneError("report training arithmetic is inconsistent.")


def _parse_report(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or len(raw) > _MAX_REPORT_BYTES:
        raise BehaviorCloneError("behavior-clone report exceeds its byte limit.")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BehaviorCloneError("behavior-clone report has a duplicate field.")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BehaviorCloneError("behavior-clone report is not valid JSON.") from exc
    if not isinstance(value, dict):
        raise BehaviorCloneError("behavior-clone report must be an object.")
    try:
        canonical = canonical_json_bytes(value)
    except ContractValidationError as exc:
        raise BehaviorCloneError("behavior-clone report is not canonical JSON.") from exc
    if not hmac.compare_digest(raw, canonical):
        raise BehaviorCloneError("behavior-clone report bytes are not canonical.")
    _exact(
        value,
        {
            "aggregate_evidence_labels",
            "behavior_clone_version",
            "claim",
            "environment",
            "panels",
            "pins",
            "schema",
            "training_result",
        },
        "report",
    )
    if (
        value["schema"] != REPORT_SCHEMA
        or value["behavior_clone_version"] != BEHAVIOR_CLONE_VERSION
        or value["claim"] != CLAIM
    ):
        raise BehaviorCloneError("behavior-clone report schema or claim is invalid.")
    pins = value["pins"]
    if not isinstance(pins, dict):
        raise BehaviorCloneError("behavior-clone report pins must be an object.")
    _exact(
        pins,
        {
            "accepted_backend_manifest",
            "accepted_backend_manifest_sha256",
            "candidate_policy_config_fingerprint",
            "data_fingerprint",
            "encoding_fingerprint",
            "encoding_version",
            "model_fingerprint",
            "policy_version",
            "state_dict_sha256",
            "training_config",
            "training_config_fingerprint",
            "training_fingerprint",
        },
        "report pins",
    )
    if (
        pins["encoding_version"] != ENCODING_VERSION
        or pins["encoding_fingerprint"] != ENCODING_FINGERPRINT
        or pins["policy_version"] != POLICY_VERSION
        or pins["model_fingerprint"] != MODEL_FINGERPRINT
        or pins["candidate_policy_config_fingerprint"]
        != _EXPECTED_CANDIDATE_CONFIG_FINGERPRINT
        or pins["training_fingerprint"] != TRAINING_FINGERPRINT
    ):
        raise BehaviorCloneError("behavior-clone report dependency pins changed.")
    config = BehaviorCloneConfig.from_dict(pins["training_config"])
    if config.fingerprint != pins["training_config_fingerprint"]:
        raise BehaviorCloneError("behavior-clone report config fingerprint changed.")
    try:
        manifest = BackendManifest.from_dict(pins["accepted_backend_manifest"])
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise BehaviorCloneError("report backend manifest is invalid.") from exc
    manifest_sha = sha256(canonical_json_bytes(manifest.to_dict())).hexdigest()
    if manifest_sha != pins["accepted_backend_manifest_sha256"]:
        raise BehaviorCloneError("report backend-manifest fingerprint changed.")
    for name in ("data_fingerprint", "state_dict_sha256"):
        if not isinstance(pins[name], str) or _HASH.fullmatch(pins[name]) is None:
            raise BehaviorCloneError(f"report {name} is not a SHA-256 digest.")
    labels = value["aggregate_evidence_labels"]
    allowed_labels = {EvidenceLabel.COMBAT_V0.value, EvidenceLabel.STRUCTURAL_FIXTURE.value}
    if (
        not isinstance(labels, list)
        or not labels
        or labels != sorted(set(labels))
        or any(label not in allowed_labels for label in labels)
    ):
        raise BehaviorCloneError("report aggregate evidence labels are invalid.")
    _validate_report_nested(value, config)
    return value


def _verify_artifact_values(
    report_bytes: bytes,
    checkpoint_payload: Mapping[str, Any],
    *,
    expected_report_sha256: str,
    expected_checkpoint_sha256: str,
    output_root: Path | None = None,
) -> BehaviorCloneArtifact:
    _assert_frozen_dependencies()
    report_sha = sha256(report_bytes).hexdigest()
    if (
        not isinstance(expected_report_sha256, str)
        or _HASH.fullmatch(expected_report_sha256) is None
        or not hmac.compare_digest(report_sha, expected_report_sha256)
    ):
        raise BehaviorCloneError("behavior-clone report digest does not match its anchor.")
    report = _parse_report(report_bytes)
    if not isinstance(checkpoint_payload, Mapping):
        raise BehaviorCloneError("behavior-clone checkpoint must be an object.")
    _exact(
        checkpoint_payload,
        {
            "checkpoint_sha256",
            "data_fingerprint",
            "policy",
            "report_sha256",
            "schema",
            "state_dict_sha256",
            "training_config_fingerprint",
            "training_fingerprint",
        },
        "checkpoint",
    )
    if checkpoint_payload["schema"] != CHECKPOINT_SCHEMA:
        raise BehaviorCloneError("behavior-clone checkpoint schema changed.")
    policy_payload = checkpoint_payload["policy"]
    if not isinstance(policy_payload, Mapping):
        raise BehaviorCloneError("behavior-clone checkpoint policy is invalid.")
    try:
        with _preserve_torch_rng():
            policy = HeadlessCandidatePolicy.from_checkpoint_payload(
                policy_payload, device="cpu"
            )
    except CandidatePolicyError as exc:
        raise BehaviorCloneError("candidate-policy checkpoint validation failed.") from exc
    state_sha = _state_dict_sha256(policy.state_dict())
    pins = report["pins"]
    policy_consistency = {
        "policy_version": pins["policy_version"],
        "encoding_version": pins["encoding_version"],
        "encoding_fingerprint": pins["encoding_fingerprint"],
        "model_fingerprint": pins["model_fingerprint"],
        "config_fingerprint": pins["candidate_policy_config_fingerprint"],
    }
    if any(policy_payload[name] != value for name, value in policy_consistency.items()):
        raise BehaviorCloneError(
            "report/checkpoint candidate-policy provenance is inconsistent."
        )
    consistency = {
        "report_sha256": report_sha,
        "data_fingerprint": pins["data_fingerprint"],
        "state_dict_sha256": state_sha,
        "training_config_fingerprint": pins["training_config_fingerprint"],
        "training_fingerprint": TRAINING_FINGERPRINT,
    }
    if any(checkpoint_payload[name] != value for name, value in consistency.items()):
        raise BehaviorCloneError("report/checkpoint provenance is inconsistent.")
    if pins["state_dict_sha256"] != state_sha:
        raise BehaviorCloneError("report/checkpoint tensor identity is inconsistent.")
    checkpoint_sha = _checkpoint_digest(checkpoint_payload)
    if (
        not isinstance(expected_checkpoint_sha256, str)
        or _HASH.fullmatch(expected_checkpoint_sha256) is None
        or checkpoint_payload["checkpoint_sha256"] != checkpoint_sha
        or not hmac.compare_digest(checkpoint_sha, expected_checkpoint_sha256)
    ):
        raise BehaviorCloneError("behavior-clone checkpoint digest does not match its anchor.")
    frozen_checkpoint = dict(checkpoint_payload)
    frozen_policy = dict(policy_payload)
    frozen_policy["state_dict"] = {
        name: value.detach().cpu().clone()
        for name, value in policy.state_dict().items()
    }
    frozen_checkpoint["policy"] = frozen_policy
    return BehaviorCloneArtifact(
        report_bytes,
        frozen_checkpoint,
        report_sha,
        checkpoint_sha,
        output_root,
    )


def _write_exclusive(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _publish(
    artifact: BehaviorCloneArtifact,
    output_root: Path,
    cancel_requested: Callable[[], bool] | None,
) -> BehaviorCloneArtifact:
    if not isinstance(output_root, Path):
        raise TypeError("output_root must be a pathlib.Path.")
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.incomplete-", dir=output_root.parent)
    )
    published = False
    try:
        _write_exclusive(temporary / REPORT_FILE_NAME, artifact.report_bytes)
        checkpoint_path = temporary / CHECKPOINT_FILE_NAME
        descriptor = os.open(checkpoint_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                torch.save(artifact.checkpoint_payload, handle)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise
        if checkpoint_path.stat().st_size > _MAX_CHECKPOINT_BYTES:
            raise BehaviorCloneError("behavior-clone checkpoint exceeds its byte limit.")
        _cancel_if_requested(cancel_requested)
        os.replace(temporary, output_root)
        published = True
        marker = canonical_json_bytes(
            {
                "checkpoint_sha256": artifact.checkpoint_sha256,
                "report_sha256": artifact.report_sha256,
                "schema": ACCEPTANCE_SCHEMA,
            }
        )
        _write_exclusive(output_root / ACCEPTANCE_FILE_NAME, marker)
        return BehaviorCloneArtifact(
            artifact.report_bytes,
            artifact.checkpoint_payload,
            artifact.report_sha256,
            artifact.checkpoint_sha256,
            output_root,
        )
    except BaseException:
        target = output_root if published else temporary
        if target.exists() and not target.is_symlink():
            shutil.rmtree(target)
        raise


def train_headless_behavior_clone(
    *,
    development: Iterable[TrustedExperimentSource],
    held_out: Iterable[TrustedExperimentSource],
    accepted_backend_manifest: BackendManifest,
    config: BehaviorCloneConfig = BehaviorCloneConfig(),
    cancel_requested: Callable[[], bool] | None = None,
    output_root: Path | None = None,
) -> BehaviorCloneArtifact:
    """Train/evaluate one tiny trusted structural-heuristic cloning smoke.

    The accepted actor loader is always the admission path.  The optional
    output directory appears accepted only after both artifacts validate and a
    final acceptance marker is written.
    """

    _assert_frozen_dependencies()
    if type(config) is not BehaviorCloneConfig:
        raise TypeError("config must be an exact BehaviorCloneConfig.")
    if not isinstance(accepted_backend_manifest, BackendManifest):
        raise TypeError("accepted_backend_manifest must be a BackendManifest.")
    development_sources = tuple(development)
    held_out_sources = tuple(held_out)
    if any(type(item) is not TrustedExperimentSource for item in development_sources):
        raise TypeError("development must contain exact TrustedExperimentSource values.")
    if any(type(item) is not TrustedExperimentSource for item in held_out_sources):
        raise TypeError("held_out must contain exact TrustedExperimentSource values.")
    for panel_name, sources in (
        ("development", development_sources),
        ("held_out", held_out_sources),
    ):
        if not sources:
            raise BehaviorCloneError(
                f"{panel_name} must declare at least one trusted source."
            )
        if len(sources) > _MAX_SOURCES_PER_PANEL:
            raise BehaviorCloneError(f"{panel_name} declares too many trusted sources.")
    if output_root is not None:
        if not isinstance(output_root, Path):
            raise TypeError("output_root must be a pathlib.Path or None.")
        if output_root.exists() or output_root.is_symlink():
            raise FileExistsError(output_root)
    _cancel_if_requested(cancel_requested)

    # This call is the trusted admission boundary.  No manually assembled
    # ActorDataset is accepted by the public training API.
    dataset = load_actor_dataset(
        development=development_sources,
        held_out=held_out_sources,
        accepted_backend_manifest=accepted_backend_manifest,
    )
    _validate_sources(
        development_sources,
        panel_name="development",
        cancel_requested=cancel_requested,
    )
    _validate_sources(
        held_out_sources,
        panel_name="held_out",
        cancel_requested=cancel_requested,
    )
    _validate_dataset_bounds(dataset)
    data_fingerprint, _ = _data_identity(
        dataset,
        development_sources,
        held_out_sources,
        accepted_backend_manifest,
    )
    _cancel_if_requested(cancel_requested)

    with _deterministic_torch(config.seed):
        trained, update_count, gradients_finite = _train(
            dataset, config, cancel_requested
        )
        policy_payload = trained["policy"]
        if not isinstance(policy_payload, Mapping):  # pragma: no cover
            raise BehaviorCloneError("candidate policy snapshot is invalid.")
        state_sha = _state_dict_sha256(policy_payload["state_dict"])
        backend_manifest_sha = sha256(
            canonical_json_bytes(accepted_backend_manifest.to_dict())
        ).hexdigest()
        report = {
            "aggregate_evidence_labels": [
                label.value for label in dataset.aggregate_evidence_labels
            ],
            "behavior_clone_version": BEHAVIOR_CLONE_VERSION,
            "claim": CLAIM,
            "environment": _runtime_environment(),
            "panels": {
                "development": _panel_report(
                    dataset.development,
                    development_sources,
                    trained["development_metrics"],
                ),
                "held_out": _panel_report(
                    dataset.held_out,
                    held_out_sources,
                    trained["held_out_metrics"],
                ),
            },
            "pins": {
                "accepted_backend_manifest": accepted_backend_manifest.to_dict(),
                "accepted_backend_manifest_sha256": backend_manifest_sha,
                "candidate_policy_config_fingerprint": (
                    _EXPECTED_CANDIDATE_CONFIG_FINGERPRINT
                ),
                "data_fingerprint": data_fingerprint,
                "encoding_fingerprint": ENCODING_FINGERPRINT,
                "encoding_version": ENCODING_VERSION,
                "model_fingerprint": MODEL_FINGERPRINT,
                "policy_version": POLICY_VERSION,
                "state_dict_sha256": state_sha,
                "training_config": config.to_dict(),
                "training_config_fingerprint": config.fingerprint,
                "training_fingerprint": TRAINING_FINGERPRINT,
            },
            "schema": REPORT_SCHEMA,
            "training_result": {
                "finite_gradients": gradients_finite,
                "optimizer_update_count": update_count,
                "training_example_visits": len(dataset.development) * config.epochs,
            },
        }
        report_bytes = canonical_json_bytes(report)
        report_sha = sha256(report_bytes).hexdigest()
        checkpoint: dict[str, Any] = {
            "data_fingerprint": data_fingerprint,
            "policy": policy_payload,
            "report_sha256": report_sha,
            "schema": CHECKPOINT_SCHEMA,
            "state_dict_sha256": state_sha,
            "training_config_fingerprint": config.fingerprint,
            "training_fingerprint": TRAINING_FINGERPRINT,
        }
        checkpoint["checkpoint_sha256"] = _checkpoint_digest(checkpoint)
        artifact = _verify_artifact_values(
            report_bytes,
            checkpoint,
            expected_report_sha256=report_sha,
            expected_checkpoint_sha256=checkpoint["checkpoint_sha256"],
        )
        _cancel_if_requested(cancel_requested)
        if output_root is not None:
            artifact = _publish(artifact, output_root, cancel_requested)
        return artifact


def load_behavior_clone_artifact(
    root: Path,
    *,
    expected_report_sha256: str,
    expected_checkpoint_sha256: str,
) -> BehaviorCloneArtifact:
    """Load only a complete, externally anchored report/checkpoint pair."""

    if not isinstance(root, Path):
        raise TypeError("root must be a pathlib.Path.")
    if root.is_symlink() or not root.is_dir():
        raise BehaviorCloneError("behavior-clone artifact root must be a directory.")
    if {item.name for item in root.iterdir()} != {
        REPORT_FILE_NAME,
        CHECKPOINT_FILE_NAME,
        ACCEPTANCE_FILE_NAME,
    }:
        raise BehaviorCloneError("behavior-clone artifact file set is not exact.")
    for name in (REPORT_FILE_NAME, CHECKPOINT_FILE_NAME, ACCEPTANCE_FILE_NAME):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise BehaviorCloneError("behavior-clone artifact files must be regular.")
    report_bytes = (root / REPORT_FILE_NAME).read_bytes()
    if len(report_bytes) > _MAX_REPORT_BYTES:
        raise BehaviorCloneError("behavior-clone report exceeds its byte limit.")
    checkpoint_path = root / CHECKPOINT_FILE_NAME
    if checkpoint_path.stat().st_size > _MAX_CHECKPOINT_BYTES:
        raise BehaviorCloneError("behavior-clone checkpoint exceeds its byte limit.")
    marker_bytes = (root / ACCEPTANCE_FILE_NAME).read_bytes()
    try:
        marker = json.loads(marker_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BehaviorCloneError("behavior-clone acceptance marker is invalid.") from exc
    if (
        not isinstance(marker, dict)
        or set(marker) != {"schema", "report_sha256", "checkpoint_sha256"}
        or marker["schema"] != ACCEPTANCE_SCHEMA
        or canonical_json_bytes(marker) != marker_bytes
        or marker["report_sha256"] != expected_report_sha256
        or marker["checkpoint_sha256"] != expected_checkpoint_sha256
    ):
        raise BehaviorCloneError("behavior-clone acceptance marker is inconsistent.")
    try:
        checkpoint = torch.load(
            checkpoint_path, map_location="cpu", weights_only=True
        )
    except Exception as exc:
        raise BehaviorCloneError("behavior-clone checkpoint could not be loaded.") from exc
    return _verify_artifact_values(
        report_bytes,
        checkpoint,
        expected_report_sha256=expected_report_sha256,
        expected_checkpoint_sha256=expected_checkpoint_sha256,
        output_root=root,
    )
