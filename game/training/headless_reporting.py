"""Strict, provenance-bound experiment artifacts for headless rollouts.

This is deliberately a consumer of the accepted rollout, benchmark, and
three-stream trajectory APIs.  It stores trajectories through their existing
writer and reloads them through their existing trusted loader; it never
duplicates or flattens replay, hindsight-target, or synthetic-audit data.

The final experiment manifest is a completion marker, not an authenticator.
Callers retain and later supply its SHA-256 to detect replacement.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Mapping

from game.backends.headless.reduced_run_backend import HeadlessRunConfig
from game.contracts.headless_v0 import BackendManifest, RunOutcome, canonical_json_bytes
from game.data.headless_trajectory import (
    FinalizedTrajectory,
    TrajectoryCompletion,
    TrajectoryPaths,
    decode_hindsight_targets,
    decode_synthetic_audit,
    load_trajectory,
)
from game.training.headless_benchmark import (
    HeadlessBenchmarkConfig,
    HeadlessBenchmarkResult,
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
)


EXPERIMENT_SCHEMA = "headless_experiment_v1"
CONFIG_SCHEMA = "headless_experiment_v1.config.v1"
MANIFEST_SCHEMA = "headless_experiment_v1.manifest.v1"
HASH_ALGORITHM = "sha256"
CONFIG_FILE_NAME = "experiment.config.json"
MANIFEST_FILE_NAME = "experiment.manifest.json"
REPETITIONS_DIRECTORY = "repetitions"
_MAX_FILE_BYTES = 1_048_576
_MAX_HOST_TEXT_BYTES = 256
_ID = re.compile(r"[a-z][a-z0-9._-]{0,127}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class ExperimentValidationError(ValueError):
    """Raised for malformed or inconsistent experiment artifacts."""


class ExperimentIntegrityError(ExperimentValidationError):
    """Raised when an anchored artifact has been modified or swapped."""


class ExperimentInterruptedError(ExperimentValidationError):
    """Raised when an experiment has no final completion manifest."""


def _exact(value: Mapping[str, Any], fields: set[str], path: str) -> None:
    actual = set(value)
    if actual != fields:
        missing = ", ".join(sorted(fields - actual))
        unknown = ", ".join(sorted(actual - fields))
        detail = "; ".join(part for part in (
            f"missing {missing}" if missing else "",
            f"unknown {unknown}" if unknown else "",
        ) if part)
        raise ExperimentValidationError(f"{path} fields are not exact ({detail}).")


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ExperimentValidationError(f"{path} must be canonical text.")
    return value


def _identifier(value: Any, path: str) -> str:
    text = _text(value, path)
    if _ID.fullmatch(text) is None:
        raise ExperimentValidationError(f"{path} has an invalid identifier.")
    return text


def _digest(value: Any, path: str) -> str:
    text = _text(value, path)
    if _HASH.fullmatch(text) is None:
        raise ExperimentValidationError(f"{path} must be a lowercase SHA-256 digest.")
    return text


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ExperimentValidationError(f"{path} must be an integer >= {minimum}.")
    return value


def _canonical_json_value(value: Any, path: str) -> Any:
    try:
        # The contract codec validates JSON primitives, finite values, and text.
        return json.loads(canonical_json_bytes(value).decode("utf-8"))
    except Exception as exc:
        raise ExperimentValidationError(f"{path} is not canonical JSON-safe data.") from exc


def _parse_canonical(raw: bytes, path: str) -> Mapping[str, Any]:
    if not isinstance(raw, bytes) or len(raw) > _MAX_FILE_BYTES:
        raise ExperimentValidationError(f"{path} exceeds its byte limit.")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, item in pairs:
            if key in output:
                raise ExperimentValidationError(f"{path} contains a duplicate field.")
            output[key] = item
        return output

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentValidationError(f"{path} is not valid JSON.") from exc
    if not isinstance(value, Mapping):
        raise ExperimentValidationError(f"{path} must contain an object.")
    try:
        canonical = canonical_json_bytes(value)
    except Exception as exc:
        raise ExperimentValidationError(f"{path} is not canonical JSON.") from exc
    if not hmac.compare_digest(raw, canonical):
        raise ExperimentIntegrityError(f"{path} does not use exact canonical bytes.")
    return value


def _read_regular(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ExperimentIntegrityError(f"{path.name} must be a regular non-symlink file.")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ExperimentValidationError(f"{path.name} exceeds its byte limit.")
    return raw


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


def _under(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ExperimentIntegrityError("Artifact path escapes the chosen output root.") from exc
    return resolved


def _run_config_to_dict(value: HeadlessRolloutConfig) -> dict[str, Any]:
    return {
        "chooser_kind": value.chooser_kind.value,
        "factory": value.factory.to_dict(),
        "policy_seed": value.policy_seed,
        "run_config": value.run_config.to_dict(),
        "trajectory_id": value.trajectory_id,
        "transition_budget": value.transition_budget,
    }


def _run_config_from_dict(value: Any) -> HeadlessRolloutConfig:
    if not isinstance(value, Mapping):
        raise ExperimentValidationError("episode configuration must be an object.")
    _exact(value, {"chooser_kind", "factory", "policy_seed", "run_config", "trajectory_id", "transition_budget"}, "episode configuration")
    if not isinstance(value["run_config"], Mapping) or not isinstance(value["factory"], Mapping):
        raise ExperimentValidationError("episode configuration nested values must be objects.")
    try:
        return HeadlessRolloutConfig(
            trajectory_id=value["trajectory_id"],
            run_config=HeadlessRunConfig.from_dict(value["run_config"]),
            transition_budget=value["transition_budget"],
            chooser_kind=ChooserKind(value["chooser_kind"]),
            policy_seed=value["policy_seed"],
            factory=BackendFactoryDescriptor.from_dict(value["factory"]),
        )
    except (TypeError, ValueError) as exc:
        raise ExperimentValidationError("episode configuration is invalid.") from exc


def _benchmark_to_dict(value: HeadlessBenchmarkConfig) -> dict[str, Any]:
    return {
        "batch": {
            "episodes": [_run_config_to_dict(item) for item in value.batch.episodes],
            "worker": {
                "worker_count": value.batch.worker.worker_count,
                "worker_seed": value.batch.worker.worker_seed,
            },
        },
        "process_safe": value.process_safe,
        "repetitions": value.repetitions,
    }


def _benchmark_from_dict(value: Any) -> HeadlessBenchmarkConfig:
    if not isinstance(value, Mapping):
        raise ExperimentValidationError("benchmark must be an object.")
    _exact(value, {"batch", "process_safe", "repetitions"}, "benchmark")
    batch = value["batch"]
    if not isinstance(batch, Mapping):
        raise ExperimentValidationError("benchmark.batch must be an object.")
    _exact(batch, {"episodes", "worker"}, "benchmark.batch")
    worker = batch["worker"]
    episodes = batch["episodes"]
    if not isinstance(worker, Mapping) or not isinstance(episodes, list):
        raise ExperimentValidationError("benchmark batch fields have invalid types.")
    _exact(worker, {"worker_count", "worker_seed"}, "benchmark.batch.worker")
    if not isinstance(value["process_safe"], bool):
        raise ExperimentValidationError("benchmark.process_safe must be boolean.")
    try:
        return HeadlessBenchmarkConfig(
            HeadlessBatchConfig(
                tuple(_run_config_from_dict(item) for item in episodes),
                CollectorWorkerConfig(worker["worker_count"], worker["worker_seed"]),
            ),
            repetitions=value["repetitions"],
            process_safe=value["process_safe"],
        )
    except (TypeError, ValueError) as exc:
        raise ExperimentValidationError("benchmark configuration is invalid.") from exc


@dataclass(frozen=True, slots=True)
class HeadlessExperimentConfig:
    """The declared deterministic conditions and exact identity pins for one panel.

    Existing trajectory streams authenticate their own ID, backend pins,
    completion and public decision/audit facts.  They do not encode scenario
    settings, game/policy/collector seeds, or transition budget; those remain
    caller-declared conditions bound by this envelope and its external final
    manifest anchor, not independently proven producer provenance.
    """

    experiment_id: str
    benchmark: HeadlessBenchmarkConfig
    backend_manifest: BackendManifest

    def __post_init__(self) -> None:
        _identifier(self.experiment_id, "experiment_id")
        if not isinstance(self.benchmark, HeadlessBenchmarkConfig):
            raise TypeError("benchmark must be a HeadlessBenchmarkConfig.")
        if not isinstance(self.backend_manifest, BackendManifest):
            raise TypeError("backend_manifest must be a BackendManifest.")
        for item in self.benchmark.batch.episodes:
            _identifier(item.trajectory_id, "episode trajectory_id")
            if item.run_config.content_fingerprint != self.backend_manifest.content_fingerprint:
                raise ExperimentValidationError("Episode content pin does not match backend manifest.")
            if item.factory.backend_id != self.backend_manifest.backend_id:
                raise ExperimentValidationError("Episode factory does not match backend manifest.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_manifest": self.backend_manifest.to_dict(),
            "benchmark": _benchmark_to_dict(self.benchmark),
            "experiment_id": self.experiment_id,
            "schema": CONFIG_SCHEMA,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def sha256(self) -> str:
        return sha256(self.to_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HeadlessExperimentConfig":
        _exact(value, {"backend_manifest", "benchmark", "experiment_id", "schema"}, "experiment config")
        if value["schema"] != CONFIG_SCHEMA or not isinstance(value["backend_manifest"], Mapping):
            raise ExperimentValidationError("Experiment configuration schema or manifest is invalid.")
        try:
            return cls(
                experiment_id=value["experiment_id"],
                benchmark=_benchmark_from_dict(value["benchmark"]),
                backend_manifest=BackendManifest.from_dict(value["backend_manifest"]),
            )
        except (TypeError, ValueError) as exc:
            raise ExperimentValidationError("Experiment configuration is invalid.") from exc


@dataclass(frozen=True, slots=True)
class EpisodeReport:
    trajectory_id: str
    stop_reason: RolloutStopReason
    transition_count: int
    initial_decision_sha256: str | None
    final_decision_sha256: str | None
    trajectory_manifest_sha256: str | None
    trajectory_completion: TrajectoryCompletion | None
    terminal_outcome: RunOutcome | None
    failure_present: bool

    def __post_init__(self) -> None:
        _identifier(self.trajectory_id, "episode.trajectory_id")
        object.__setattr__(self, "stop_reason", RolloutStopReason(self.stop_reason))
        _integer(self.transition_count, "episode.transition_count")
        for name in ("initial_decision_sha256", "final_decision_sha256", "trajectory_manifest_sha256"):
            item = getattr(self, name)
            if item is not None:
                _digest(item, f"episode.{name}")
        completion = self.trajectory_completion
        if completion is not None:
            try:
                completion = TrajectoryCompletion(completion)
            except ValueError as exc:
                raise ExperimentValidationError("episode.trajectory_completion is invalid.") from exc
            object.__setattr__(self, "trajectory_completion", completion)
        outcome = self.terminal_outcome
        if outcome is not None:
            try:
                outcome = RunOutcome(outcome)
            except ValueError as exc:
                raise ExperimentValidationError("episode.terminal_outcome is invalid.") from exc
            object.__setattr__(self, "terminal_outcome", outcome)
        if not isinstance(self.failure_present, bool):
            raise TypeError("episode.failure_present must be boolean.")
        if self.stop_reason is RolloutStopReason.FAILED and not self.failure_present:
            raise ExperimentValidationError("A failed episode must report a failure.")
        if self.failure_present and self.stop_reason not in {
            RolloutStopReason.FAILED, RolloutStopReason.INTERRUPTED,
        }:
            raise ExperimentValidationError("Only failed or interrupted episodes may report a failure.")
        if self.trajectory_manifest_sha256 is None:
            if self.stop_reason not in {RolloutStopReason.FAILED, RolloutStopReason.INTERRUPTED} or not self.failure_present:
                raise ExperimentValidationError("A no-trajectory episode must be an explicit failed or interrupted result.")
            if any(item is not None for item in (self.initial_decision_sha256, self.final_decision_sha256, completion, outcome)) or self.transition_count != 0:
                raise ExperimentValidationError("A no-trajectory episode cannot claim unbound execution facts.")
        elif completion is None or self.initial_decision_sha256 is None or self.final_decision_sha256 is None:
            raise ExperimentValidationError("A trajectory report must bind its completion and decision hashes.")
        elif (completion is TrajectoryCompletion.TERMINAL) != (outcome is not None):
            raise ExperimentValidationError("Only a terminal trajectory can report a terminal outcome.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_present": self.failure_present,
            "final_decision_sha256": self.final_decision_sha256,
            "initial_decision_sha256": self.initial_decision_sha256,
            "stop_reason": self.stop_reason.value,
            "trajectory_id": self.trajectory_id,
            "trajectory_completion": None if self.trajectory_completion is None else self.trajectory_completion.value,
            "trajectory_manifest_sha256": self.trajectory_manifest_sha256,
            "terminal_outcome": None if self.terminal_outcome is None else self.terminal_outcome.value,
            "transition_count": self.transition_count,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "EpisodeReport":
        if not isinstance(value, Mapping):
            raise ExperimentValidationError("episode report must be an object.")
        _exact(value, {"failure_present", "final_decision_sha256", "initial_decision_sha256", "stop_reason", "trajectory_id", "trajectory_completion", "trajectory_manifest_sha256", "terminal_outcome", "transition_count"}, "episode report")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class RepetitionReport:
    repetition_index: int
    received: tuple[EpisodeReport, ...]
    pending_trajectory_ids: tuple[str, ...]
    interrupted: bool

    def __post_init__(self) -> None:
        _integer(self.repetition_index, "repetition_index")
        received = tuple(self.received)
        pending = tuple(self.pending_trajectory_ids)
        if any(not isinstance(item, EpisodeReport) for item in received):
            raise TypeError("received must contain EpisodeReport values.")
        if any(_identifier(item, "pending trajectory ID") != item for item in pending):
            raise TypeError("pending trajectory IDs must be valid strings.")
        identifiers = [item.trajectory_id for item in received]
        if len(set(identifiers)) != len(identifiers) or set(identifiers) & set(pending):
            raise ExperimentValidationError("Repetition trajectory identities must be unique and disjoint.")
        if not isinstance(self.interrupted, bool):
            raise TypeError("interrupted must be boolean.")
        if pending and not self.interrupted:
            raise ExperimentValidationError("Only interrupted repetitions may retain pending episodes.")
        # Both collector modes stop immediately upon receiving an INTERRUPTED
        # episode. The converse is not required: cancellation between episodes
        # or during pool cleanup can interrupt a batch without such a result.
        if not self.interrupted and any(
            item.stop_reason is RolloutStopReason.INTERRUPTED for item in received
        ):
            raise ExperimentValidationError("An interrupted episode requires an interrupted repetition.")
        object.__setattr__(self, "received", received)
        object.__setattr__(self, "pending_trajectory_ids", pending)

    def to_dict(self) -> dict[str, Any]:
        return {
            "interrupted": self.interrupted,
            "pending_trajectory_ids": list(self.pending_trajectory_ids),
            "received": [item.to_dict() for item in self.received],
            "repetition_index": self.repetition_index,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RepetitionReport":
        if not isinstance(value, Mapping):
            raise ExperimentValidationError("repetition report must be an object.")
        _exact(value, {"interrupted", "pending_trajectory_ids", "received", "repetition_index"}, "repetition report")
        if not isinstance(value["received"], list) or not isinstance(value["pending_trajectory_ids"], list):
            raise ExperimentValidationError("repetition report collections must be arrays.")
        return cls(
            repetition_index=value["repetition_index"],
            received=tuple(EpisodeReport.from_dict(item) for item in value["received"]),
            pending_trajectory_ids=tuple(value["pending_trajectory_ids"]),
            interrupted=value["interrupted"],
        )


def _rate(value: float, path: str) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ExperimentValidationError(f"{path} must be a finite nonnegative number.")
    return int(round(value * 1_000_000_000))


@dataclass(frozen=True, slots=True)
class NondeterministicMeasurements:
    """Operational values deliberately excluded from deterministic conditions."""

    process_mode: str
    elapsed_nanoseconds: int
    episodes_per_second_nano: int
    transitions_per_second_nano: int
    host_os: str | None = None
    host_architecture: str | None = None
    host_cpu_model: str | None = None
    host_logical_cpu_count: int | None = None
    host_memory_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.process_mode not in {"sequential", "spawned"}:
            raise ExperimentValidationError("measurement process mode is unsupported.")
        for name in ("elapsed_nanoseconds", "episodes_per_second_nano", "transitions_per_second_nano"):
            _integer(getattr(self, name), f"measurement.{name}")
        for name in ("host_os", "host_architecture", "host_cpu_model"):
            item = getattr(self, name)
            if item is not None:
                text = _text(item, f"measurement.{name}")
                if len(text.encode("utf-8")) > _MAX_HOST_TEXT_BYTES:
                    raise ExperimentValidationError(f"measurement.{name} exceeds its byte limit.")
        for name in ("host_logical_cpu_count", "host_memory_bytes"):
            item = getattr(self, name)
            if item is not None:
                _integer(item, f"measurement.{name}")

    @classmethod
    def from_benchmark(cls, result: HeadlessBenchmarkResult, host: Mapping[str, Any] | None = None) -> "NondeterministicMeasurements":
        host_fields = {} if host is None else dict(host)
        allowed = {"host_os", "host_architecture", "host_cpu_model", "host_logical_cpu_count", "host_memory_bytes"}
        if set(host_fields) - allowed:
            raise ExperimentValidationError("Host measurements contain unknown fields.")
        return cls(
            "spawned" if result.conditions.process_safe else "sequential",
            _rate(result.elapsed_seconds, "elapsed_seconds"),
            _rate(result.episodes_per_second, "episodes_per_second"),
            _rate(result.transitions_per_second, "transitions_per_second"),
            **host_fields,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "elapsed_nanoseconds": self.elapsed_nanoseconds,
            "episodes_per_second_nano": self.episodes_per_second_nano,
            "host_architecture": self.host_architecture,
            "host_cpu_model": self.host_cpu_model,
            "host_logical_cpu_count": self.host_logical_cpu_count,
            "host_memory_bytes": self.host_memory_bytes,
            "host_os": self.host_os,
            "process_mode": self.process_mode,
            "transitions_per_second_nano": self.transitions_per_second_nano,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "NondeterministicMeasurements":
        if not isinstance(value, Mapping):
            raise ExperimentValidationError("measurement must be an object.")
        _exact(value, {"elapsed_nanoseconds", "episodes_per_second_nano", "host_architecture", "host_cpu_model", "host_logical_cpu_count", "host_memory_bytes", "host_os", "process_mode", "transitions_per_second_nano"}, "measurement")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class HeadlessExperimentReport:
    config_sha256: str
    repetitions: tuple[RepetitionReport, ...]
    unstarted_repetition_indices: tuple[int, ...]
    measurement: NondeterministicMeasurements

    def __post_init__(self) -> None:
        _digest(self.config_sha256, "config_sha256")
        repetitions = tuple(self.repetitions)
        unstarted = tuple(self.unstarted_repetition_indices)
        if any(not isinstance(item, RepetitionReport) for item in repetitions):
            raise TypeError("repetitions must contain RepetitionReport values.")
        if [item.repetition_index for item in repetitions] != list(range(len(repetitions))):
            raise ExperimentValidationError("Started repetition indices must be contiguous from zero.")
        if list(unstarted) != list(range(len(repetitions), len(repetitions) + len(unstarted))):
            raise ExperimentValidationError("Unstarted repetition indices must be contiguous.")
        if any(not isinstance(item, int) or isinstance(item, bool) for item in unstarted):
            raise TypeError("unstarted repetition indices must be integers.")
        if not isinstance(self.measurement, NondeterministicMeasurements):
            raise TypeError("measurement has the wrong type.")
        object.__setattr__(self, "repetitions", repetitions)
        object.__setattr__(self, "unstarted_repetition_indices", unstarted)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_sha256": self.config_sha256,
            "hash_algorithm": HASH_ALGORITHM,
            "measurement": self.measurement.to_dict(),
            "repetitions": [item.to_dict() for item in self.repetitions],
            "schema": MANIFEST_SCHEMA,
            "unstarted_repetition_indices": list(self.unstarted_repetition_indices),
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def sha256(self) -> str:
        return sha256(self.to_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HeadlessExperimentReport":
        _exact(value, {"config_sha256", "hash_algorithm", "measurement", "repetitions", "schema", "unstarted_repetition_indices"}, "experiment manifest")
        if value["schema"] != MANIFEST_SCHEMA or value["hash_algorithm"] != HASH_ALGORITHM:
            raise ExperimentValidationError("Experiment manifest schema is unsupported.")
        if not isinstance(value["repetitions"], list) or not isinstance(value["unstarted_repetition_indices"], list):
            raise ExperimentValidationError("Experiment manifest collections must be arrays.")
        return cls(
            config_sha256=value["config_sha256"],
            repetitions=tuple(RepetitionReport.from_dict(item) for item in value["repetitions"]),
            unstarted_repetition_indices=tuple(value["unstarted_repetition_indices"]),
            measurement=NondeterministicMeasurements.from_dict(value["measurement"]),
        )


@dataclass(frozen=True, slots=True)
class LoadedHeadlessExperiment:
    config: HeadlessExperimentConfig
    report: HeadlessExperimentReport
    trajectories: Mapping[tuple[int, str], FinalizedTrajectory]


def _same_pins(expected: BackendManifest, trajectory: FinalizedTrajectory) -> bool:
    manifest = trajectory.manifest
    return (
        manifest.contract == expected.contract
        and manifest.contract_fingerprint == expected.contract_fingerprint
        and manifest.backend_id == expected.backend_id
        and manifest.backend_version == expected.backend_version
        and manifest.backend_fingerprint == expected.backend_fingerprint
        and manifest.content_version == expected.content_version
        and manifest.content_fingerprint == expected.content_fingerprint
        and manifest.rules_version == expected.rules_version
        and manifest.rules_fingerprint == expected.rules_fingerprint
        and manifest.evidence == expected.evidence
    )


def _trajectory_facts(
    trajectory: FinalizedTrajectory,
) -> tuple[TrajectoryCompletion, RunOutcome | None, str, str, int]:
    """Extract only execution facts already authenticated by sidecar validation."""

    audits = decode_synthetic_audit(trajectory.synthetic_audit_jsonl)
    targets = decode_hindsight_targets(trajectory.hindsight_target_jsonl)
    if not audits or len(targets) != 1:
        raise ExperimentIntegrityError("Finalized trajectory lacks required audit/target facts.")
    completion = trajectory.manifest.completion
    target = targets[0]
    if target.completion is not completion:
        raise ExperimentIntegrityError("Trajectory target completion does not match its manifest.")
    transitions = sum(item.receipt is not None for item in audits)
    return (
        completion,
        target.terminal_outcome,
        audits[0].decision_correlation.decision_hash,
        audits[-1].decision_correlation.decision_hash,
        transitions,
    )


def _stop_reason_matches(
    stop_reason: RolloutStopReason,
    completion: TrajectoryCompletion,
    outcome: RunOutcome | None,
) -> bool:
    if stop_reason is RolloutStopReason.DEFEAT:
        return completion is TrajectoryCompletion.TERMINAL and outcome is RunOutcome.DEFEAT
    if stop_reason is RolloutStopReason.ROUTE_COMPLETE:
        return completion is TrajectoryCompletion.TERMINAL and outcome is RunOutcome.VICTORY
    if stop_reason is RolloutStopReason.TERMINAL:
        return completion is TrajectoryCompletion.TERMINAL
    if stop_reason is RolloutStopReason.UNSUPPORTED:
        return completion is TrajectoryCompletion.UNSUPPORTED
    if stop_reason is RolloutStopReason.BUDGET_EXHAUSTED:
        return completion is TrajectoryCompletion.INTERRUPTED
    # Failure/cancellation can arrive after a terminal or unsupported boundary.
    # The producer's _partial_trajectory preserves that validated completion;
    # the collector stop reason still controls whether another batch can run.
    return stop_reason in {RolloutStopReason.FAILED, RolloutStopReason.INTERRUPTED}


def _episode_report_from_result(item: HeadlessRolloutResult) -> EpisodeReport:
    if not isinstance(item.config, HeadlessRolloutConfig):
        raise ExperimentValidationError("Received result has no valid rollout configuration.")
    if not isinstance(item.stop_reason, RolloutStopReason):
        raise ExperimentValidationError("Received result has an invalid stop reason.")
    if item.failure is not None and (not isinstance(item.failure, str) or not item.failure):
        raise ExperimentValidationError("Received failure must be nonempty text or None.")
    if item.trajectory is None:
        return EpisodeReport(
            item.config.trajectory_id,
            item.stop_reason,
            item.transition_count,
            None,
            None,
            None,
            None,
            None,
            item.failure is not None,
        )
    completion, outcome, initial_hash, final_hash, transition_count = _trajectory_facts(item.trajectory)
    if item.transition_count != transition_count:
        raise ExperimentIntegrityError("Result transition count disagrees with trajectory audit receipts.")
    if not _stop_reason_matches(item.stop_reason, completion, outcome):
        raise ExperimentIntegrityError("Result stop reason disagrees with finalized trajectory completion.")
    return EpisodeReport(
        item.config.trajectory_id,
        item.stop_reason,
        item.transition_count,
        initial_hash,
        final_hash,
        item.trajectory.manifest_sha256,
        completion,
        outcome,
        item.failure is not None,
    )


def _report_from_batch(index: int, batch: HeadlessBatchResult) -> RepetitionReport:
    received = tuple(
        _episode_report_from_result(item)
        for item in batch.results
    )
    return RepetitionReport(index, received, batch.pending_trajectory_ids, batch.interrupted)


def _validate_report_against_config(config: HeadlessExperimentConfig, report: HeadlessExperimentReport) -> None:
    if report.config_sha256 != config.sha256:
        raise ExperimentIntegrityError("Report is not bound to the supplied configuration bytes.")
    if len(report.repetitions) + len(report.unstarted_repetition_indices) != config.benchmark.repetitions:
        raise ExperimentValidationError("Report does not account for every configured repetition.")
    expected = config.benchmark.batch.episodes
    expected_by_id = {item.trajectory_id: item for item in expected}
    for repetition in report.repetitions:
        received = {item.trajectory_id for item in repetition.received}
        pending = set(repetition.pending_trajectory_ids)
        if not received <= set(expected_by_id) or not pending <= set(expected_by_id):
            raise ExperimentIntegrityError("Report references an episode outside the configured panel.")
        if received | pending != set(expected_by_id):
            raise ExperimentIntegrityError("Repetition does not account for the ordered configured panel.")
        if tuple(item.trajectory_id for item in repetition.received) != tuple(
            item.trajectory_id for item in expected if item.trajectory_id in received
        ):
            raise ExperimentIntegrityError("Received episodes are not in configured panel order.")
        if tuple(repetition.pending_trajectory_ids) != tuple(
            item.trajectory_id for item in expected if item.trajectory_id in pending
        ):
            raise ExperimentIntegrityError("Pending episodes are not in configured panel order.")
        if not repetition.interrupted and received != set(expected_by_id):
            raise ExperimentIntegrityError("A completed repetition has missing results.")
    if any(item.interrupted for item in report.repetitions[:-1]):
        raise ExperimentIntegrityError("No repetition may start after an interrupted repetition.")
    if report.repetitions and report.unstarted_repetition_indices and not report.repetitions[-1].interrupted:
        raise ExperimentIntegrityError("Unstarted repetitions require an interrupted preceding repetition.")


def _validate_benchmark_input(config: HeadlessExperimentConfig, result: HeadlessBenchmarkResult) -> HeadlessExperimentReport:
    if not isinstance(result, HeadlessBenchmarkResult):
        raise TypeError("result must be a HeadlessBenchmarkResult.")
    if result.conditions != config.benchmark:
        raise ExperimentValidationError("Benchmark result conditions do not match experiment configuration.")
    reports = tuple(_report_from_batch(index, batch) for index, batch in enumerate(result.batches))
    report = HeadlessExperimentReport(
        config.sha256,
        reports,
        tuple(range(len(reports), config.benchmark.repetitions)),
        NondeterministicMeasurements.from_benchmark(result),
    )
    _validate_report_against_config(config, report)
    for batch in result.batches:
        if batch.process_safe != config.benchmark.process_safe or batch.worker != config.benchmark.batch.worker:
            raise ExperimentIntegrityError("Batch process conditions do not match the configured collector.")
        for item in batch.results:
            if item.config != {episode.trajectory_id: episode for episode in config.benchmark.batch.episodes}[item.config.trajectory_id]:
                raise ExperimentIntegrityError("Received episode configuration does not match the panel.")
            if item.trajectory is not None and not _same_pins(config.backend_manifest, item.trajectory):
                raise ExperimentIntegrityError("Trajectory identity pins do not match experiment configuration.")
            if item.trajectory is not None and item.trajectory.manifest.trajectory_id != item.config.trajectory_id:
                raise ExperimentIntegrityError("Trajectory identity does not match its configured episode before output creation.")
            if item.transition_count > item.config.transition_budget:
                raise ExperimentIntegrityError("Result transition count exceeds its configured budget.")
            if item.stop_reason is RolloutStopReason.BUDGET_EXHAUSTED and item.transition_count != item.config.transition_budget:
                raise ExperimentIntegrityError("Budget-exhausted result does not consume its configured budget.")
    return report


def _assert_empty_root(root: Path) -> None:
    if root.exists() or root.is_symlink():
        raise FileExistsError("Experiment output root already exists; refusing overwrite.")
    root.mkdir(parents=True, mode=0o700)
    if root.is_symlink() or not root.is_dir():
        raise ExperimentIntegrityError("Experiment output root must be a non-symlink directory.")


def preflight_headless_experiment_output(output_root: str | Path) -> Path:
    """Reject an existing output root before a caller starts any episodes.

    This is intentionally advisory rather than a reservation.  The writer
    repeats the exclusive check immediately before creating the root, so a
    race never becomes an overwrite.
    """

    root = Path(output_root)
    if root.exists() or root.is_symlink():
        raise FileExistsError("Experiment output root already exists; refusing overwrite.")
    return root


def write_headless_experiment(
    output_root: str | Path,
    config: HeadlessExperimentConfig,
    result: HeadlessBenchmarkResult,
    *,
    host_measurements: Mapping[str, Any] | None = None,
) -> HeadlessExperimentReport:
    """Write one new experiment root, committing its final manifest last."""

    if not isinstance(config, HeadlessExperimentConfig):
        raise TypeError("config must be a HeadlessExperimentConfig.")
    report = _validate_benchmark_input(config, result)
    if host_measurements is not None:
        report = HeadlessExperimentReport(
            report.config_sha256, report.repetitions, report.unstarted_repetition_indices,
            NondeterministicMeasurements.from_benchmark(result, host_measurements),
        )
    config_raw = config.to_bytes()
    report_raw = report.to_bytes()
    if len(config_raw) > _MAX_FILE_BYTES or len(report_raw) > _MAX_FILE_BYTES:
        raise ExperimentValidationError("Experiment config or final manifest exceeds its byte limit.")
    root = preflight_headless_experiment_output(output_root)
    _assert_empty_root(root)
    _under(root, root / CONFIG_FILE_NAME)
    _write_exclusive(root / CONFIG_FILE_NAME, config_raw)
    repetitions_root = root / REPETITIONS_DIRECTORY
    repetitions_root.mkdir(mode=0o700)
    for repetition, batch in zip(report.repetitions, result.batches):
        directory = repetitions_root / f"{repetition.repetition_index:06d}"
        _under(root, directory)
        directory.mkdir(mode=0o700)
        reports_by_id = {item.trajectory_id: item for item in repetition.received}
        for episode in batch.results:
            if episode.trajectory is None:
                continue
            episode.trajectory.write_to(directory)
            if episode.trajectory.manifest_sha256 != reports_by_id[episode.config.trajectory_id].trajectory_manifest_sha256:
                raise ExperimentIntegrityError("Trajectory changed while the experiment was being written.")
    # The manifest is intentionally the final write: no loader admits a partial root.
    _write_exclusive(root / MANIFEST_FILE_NAME, report_raw)
    return report


def _verify_directory_shape(root: Path, report: HeadlessExperimentReport) -> None:
    allowed_root = {CONFIG_FILE_NAME, MANIFEST_FILE_NAME, REPETITIONS_DIRECTORY}
    if {item.name for item in root.iterdir()} != allowed_root:
        raise ExperimentIntegrityError("Experiment root contains unexpected or missing members.")
    repetitions_root = root / REPETITIONS_DIRECTORY
    if repetitions_root.is_symlink() or not repetitions_root.is_dir():
        raise ExperimentIntegrityError("Repetitions directory must be a regular directory.")
    expected_directories = {f"{item.repetition_index:06d}" for item in report.repetitions}
    if {item.name for item in repetitions_root.iterdir()} != expected_directories:
        raise ExperimentIntegrityError("Repetition directories do not match the final report.")


def load_headless_experiment(
    output_root: str | Path,
    *,
    expected_manifest_sha256: str,
) -> LoadedHeadlessExperiment:
    """Load a finalized artifact using a caller-held experiment manifest digest."""

    expected_digest = _digest(expected_manifest_sha256, "expected_manifest_sha256")
    root = Path(output_root)
    if root.is_symlink() or not root.is_dir():
        raise ExperimentInterruptedError("Experiment output root is missing or incomplete.")
    config_path = root / CONFIG_FILE_NAME
    manifest_path = root / MANIFEST_FILE_NAME
    if not manifest_path.exists():
        raise ExperimentInterruptedError("Experiment final manifest is missing.")
    config = HeadlessExperimentConfig.from_dict(_parse_canonical(_read_regular(config_path, _MAX_FILE_BYTES), CONFIG_FILE_NAME))
    manifest_raw = _read_regular(manifest_path, _MAX_FILE_BYTES)
    if not hmac.compare_digest(sha256(manifest_raw).hexdigest(), expected_digest):
        raise ExperimentIntegrityError("Experiment manifest does not match the trusted expected SHA-256.")
    report = HeadlessExperimentReport.from_dict(_parse_canonical(manifest_raw, MANIFEST_FILE_NAME))
    _validate_report_against_config(config, report)
    _verify_directory_shape(root, report)
    trajectories: dict[tuple[int, str], FinalizedTrajectory] = {}
    repetitions_root = root / REPETITIONS_DIRECTORY
    for repetition in report.repetitions:
        directory = repetitions_root / f"{repetition.repetition_index:06d}"
        _under(root, directory)
        if directory.is_symlink() or not directory.is_dir():
            raise ExperimentIntegrityError("Repetition directory must be a regular directory.")
        expected_files: set[str] = set()
        for episode in repetition.received:
            if episode.trajectory_manifest_sha256 is None:
                continue
            paths = TrajectoryPaths.in_directory(directory, episode.trajectory_id)
            expected_files.update(path.name for path in (paths.policy_replay, paths.hindsight_target, paths.synthetic_audit, paths.manifest))
            finalized = load_trajectory(directory, episode.trajectory_id, expected_manifest_sha256=episode.trajectory_manifest_sha256)
            if not _same_pins(config.backend_manifest, finalized):
                raise ExperimentIntegrityError("Loaded trajectory identity pins do not match experiment configuration.")
            completion, outcome, initial_hash, final_hash, transition_count = _trajectory_facts(finalized)
            if (
                finalized.manifest.trajectory_id != episode.trajectory_id
                or episode.trajectory_completion is not completion
                or episode.terminal_outcome is not outcome
                or episode.initial_decision_sha256 != initial_hash
                or episode.final_decision_sha256 != final_hash
                or episode.transition_count != transition_count
                or not _stop_reason_matches(episode.stop_reason, completion, outcome)
            ):
                raise ExperimentIntegrityError("Report episode facts do not match its finalized trajectory.")
            expected_config = {item.trajectory_id: item for item in config.benchmark.batch.episodes}[episode.trajectory_id]
            if transition_count > expected_config.transition_budget or (
                episode.stop_reason is RolloutStopReason.BUDGET_EXHAUSTED
                and transition_count != expected_config.transition_budget
            ):
                raise ExperimentIntegrityError("Loaded trajectory does not satisfy its declared transition budget.")
            trajectories[(repetition.repetition_index, episode.trajectory_id)] = finalized
        actual_files = {item.name for item in directory.iterdir()}
        if actual_files != expected_files:
            raise ExperimentIntegrityError("Repetition directory has missing, swapped, or unexpected trajectory files.")
    return LoadedHeadlessExperiment(config, report, trajectories)
