"""Immutable, separated trajectory records for ``headless_v0`` episodes.

The policy replay stream is deliberately useful without either sidecar.  It
contains only the then-current :class:`~game.contracts.headless_v0.PolicyView`
plus the chosen advertised candidate.  Terminal hindsight labels and
operational correlation/receipt data use distinct record types and distinct
files, and a manifest written last binds the three finalized byte streams.

This module accepts only non-live ``combat_v0`` and ``structural_fixture``
evidence.  It is not a live capture or audit facility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from game.contracts.headless_v0 import (
    CONTRACT_FINGERPRINT,
    CONTRACT_VERSION,
    BackendManifest,
    ComponentEvidence,
    ContractValidationError,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    EvidenceLabel,
    PolicyView,
    PublicEvent,
    PublicObservation,
    RunOutcome,
    Transition,
    TransitionReason,
    TransitionResult,
    TypedCandidate,
    candidate_from_dict,
    candidate_to_dict,
    canonical_json,
)


TRAJECTORY_SCHEMA = "headless_trajectory_v0"
MANIFEST_SCHEMA = "headless_trajectory_v0.manifest.v1"
POLICY_REPLAY_SCHEMA = "headless_trajectory_v0.policy_replay.v1"
HINDSIGHT_TARGET_SCHEMA = "headless_trajectory_v0.hindsight_target.v1"
SYNTHETIC_AUDIT_SCHEMA = "headless_trajectory_v0.synthetic_audit.v1"
HASH_ALGORITHM = "sha256"

_ID_PATTERN = re.compile(r"[a-z][a-z0-9._-]{0,127}\Z")
_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:+/-]{0,127}\Z")
_OPAQUE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_MAX_MANIFEST_BYTES = 65_536
_MAX_STREAM_BYTES = 16 * 1024 * 1024
_MAX_RECORDS = 1_000_000

_ALLOWED_EVIDENCE = frozenset(
    {EvidenceLabel.COMBAT_V0, EvidenceLabel.STRUCTURAL_FIXTURE}
)


class TrajectoryValidationError(ValueError):
    """Raised when trajectory records or their cross-stream binding are invalid."""


class TrajectoryIntegrityError(TrajectoryValidationError):
    """Raised when finalized bytes do not match their immutable manifest."""


class TrajectoryInterruptedError(TrajectoryValidationError):
    """Raised when a filesystem trajectory has no complete finalized file set."""


class StreamRole(str, Enum):
    POLICY_REPLAY = "policy_replay"
    HINDSIGHT_TARGET = "hindsight_target"
    SYNTHETIC_AUDIT = "synthetic_audit"


class TrajectoryCompletion(str, Enum):
    TERMINAL = "terminal"
    UNSUPPORTED = "unsupported"
    INTERRUPTED = "interrupted"


class InterruptionPoint(str, Enum):
    BEFORE_CHOICE = "before_choice"
    AWAITING_RECEIPT = "awaiting_receipt"
    BEFORE_NEXT_BOUNDARY = "before_next_boundary"
    WAITING = "waiting"
    TRANSITION_STOPPED = "transition_stopped"


_ROLE_ORDER = (
    StreamRole.POLICY_REPLAY,
    StreamRole.HINDSIGHT_TARGET,
    StreamRole.SYNTHETIC_AUDIT,
)
_ROLE_SCHEMAS = {
    StreamRole.POLICY_REPLAY: POLICY_REPLAY_SCHEMA,
    StreamRole.HINDSIGHT_TARGET: HINDSIGHT_TARGET_SCHEMA,
    StreamRole.SYNTHETIC_AUDIT: SYNTHETIC_AUDIT_SCHEMA,
}
_ROLE_SUFFIXES = {
    StreamRole.POLICY_REPLAY: "policy.jsonl",
    StreamRole.HINDSIGHT_TARGET: "target.jsonl",
    StreamRole.SYNTHETIC_AUDIT: "audit.jsonl",
}


def _require_exact_fields(
    value: Mapping[str, Any], required: set[str] | frozenset[str], path: str
) -> None:
    actual = set(value)
    missing = sorted(required - actual)
    unknown = sorted(actual - required)
    if missing:
        raise TrajectoryValidationError(
            f"{path} is missing field(s): {', '.join(missing)}."
        )
    if unknown:
        raise TrajectoryValidationError(
            f"{path} has unknown field(s): {', '.join(unknown)}."
        )


def _require_text(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise TrajectoryValidationError(f"{path} must be a string.")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise TrajectoryValidationError(f"{path} cannot contain an unpaired surrogate.")
    return value


def _require_pattern(value: Any, pattern: re.Pattern[str], path: str) -> str:
    text = _require_text(value, path)
    if pattern.fullmatch(text) is None:
        raise TrajectoryValidationError(f"{path} has an invalid canonical form.")
    return text


def _require_nonnegative_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TrajectoryValidationError(f"{path} must be a nonnegative integer.")
    return value


def _enum_value(enum_type: type[Enum], value: Any, path: str) -> Any:
    if isinstance(value, enum_type):
        return value
    _require_text(value, path)
    try:
        return enum_type(value)
    except ValueError as exc:
        raise TrajectoryValidationError(f"{path} has an unsupported value.") from exc


def _sha256(raw: bytes) -> str:
    return sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class PolicyReplayRecord:
    """One policy-visible boundary and its chosen advertised action, if any."""

    status: DecisionStatus
    phase: DecisionPhase
    observation: PublicObservation
    candidates: tuple[TypedCandidate, ...]
    chosen_action: TypedCandidate | None
    public_events: tuple[PublicEvent, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        try:
            view = PolicyView(
                status=self.status,
                phase=self.phase,
                observation=self.observation,
                candidates=tuple(self.candidates),
                public_events=tuple(self.public_events),
            )
        except (ContractValidationError, TypeError) as exc:
            raise TrajectoryValidationError("Invalid public policy replay boundary.") from exc
        object.__setattr__(self, "status", view.status)
        object.__setattr__(self, "phase", view.phase)
        object.__setattr__(self, "observation", view.observation)
        object.__setattr__(self, "candidates", view.candidates)
        object.__setattr__(self, "public_events", view.public_events)
        chosen = self.chosen_action
        if chosen is not None:
            if chosen not in view.candidates:
                raise TrajectoryValidationError(
                    "chosen_action must equal an advertised current candidate."
                )
        if view.status is not DecisionStatus.ACTIONABLE and chosen is not None:
            raise TrajectoryValidationError(
                "A non-actionable boundary cannot have a chosen action."
            )

    @classmethod
    def from_decision(
        cls, decision: DecisionState, chosen_candidate_id: str | None
    ) -> "PolicyReplayRecord":
        if not isinstance(decision, DecisionState):
            raise TypeError("decision must be a DecisionState.")
        candidates = {
            candidate.candidate_id: candidate for candidate in decision.candidates
        }
        if chosen_candidate_id is None:
            chosen = None
        elif not isinstance(chosen_candidate_id, str):
            raise TypeError("chosen_candidate_id must be a string or None.")
        else:
            chosen = candidates.get(chosen_candidate_id)
            if chosen is None:
                raise TrajectoryValidationError(
                    "The chosen candidate is not advertised by this decision."
                )
        view = decision.policy_view()
        return cls(
            view.status,
            view.phase,
            view.observation,
            view.candidates,
            chosen,
            view.public_events,
        )

    def policy_view(self) -> PolicyView:
        return PolicyView(
            self.status,
            self.phase,
            self.observation,
            self.candidates,
            self.public_events,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [candidate_to_dict(item) for item in self.candidates],
            "chosen_action": (
                None if self.chosen_action is None else candidate_to_dict(self.chosen_action)
            ),
            "observation": self.observation.to_dict(),
            "phase": self.phase.value,
            "public_events": [event.to_dict() for event in self.public_events],
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyReplayRecord":
        _require_exact_fields(
            value,
            {
                "candidates",
                "chosen_action",
                "observation",
                "phase",
                "public_events",
                "status",
            },
            "policy_replay_record",
        )
        observation = value["observation"]
        candidates = value["candidates"]
        chosen = value["chosen_action"]
        events = value["public_events"]
        if not isinstance(observation, Mapping):
            raise TrajectoryValidationError("Policy observation must be an object.")
        if not isinstance(candidates, list) or not all(
            isinstance(item, Mapping) for item in candidates
        ):
            raise TrajectoryValidationError("Policy candidates must be object records.")
        if chosen is not None and not isinstance(chosen, Mapping):
            raise TrajectoryValidationError("chosen_action must be an object or null.")
        if not isinstance(events, list) or not all(
            isinstance(item, Mapping) for item in events
        ):
            raise TrajectoryValidationError("Public events must be object records.")
        try:
            return cls(
                status=value["status"],
                phase=value["phase"],
                observation=PublicObservation.from_dict(observation),
                candidates=tuple(candidate_from_dict(item) for item in candidates),
                chosen_action=None if chosen is None else candidate_from_dict(chosen),
                public_events=tuple(PublicEvent.from_dict(item) for item in events),
            )
        except ContractValidationError as exc:
            raise TrajectoryValidationError("Invalid contract object in policy replay.") from exc


@dataclass(frozen=True, slots=True)
class HindsightTargetRecord:
    """A physically separate terminal target, always marked as hindsight."""

    trajectory_id: str
    completion: TrajectoryCompletion
    policy_record_count: int
    terminal_outcome: RunOutcome | None
    terminal_policy_record_index: int | None
    interruption_point: InterruptionPoint | None = None
    target_kind: str = "terminal_outcome"
    label_timing: str = "hindsight"

    def __post_init__(self) -> None:
        _require_pattern(self.trajectory_id, _ID_PATTERN, "target.trajectory_id")
        completion = _enum_value(
            TrajectoryCompletion, self.completion, "target.completion"
        )
        object.__setattr__(self, "completion", completion)
        count = _require_nonnegative_int(
            self.policy_record_count, "target.policy_record_count"
        )
        if count == 0 or count > _MAX_RECORDS:
            raise TrajectoryValidationError("Target policy_record_count is out of range.")
        if self.target_kind != "terminal_outcome" or self.label_timing != "hindsight":
            raise TrajectoryValidationError(
                "Terminal targets must be explicitly marked as hindsight."
            )
        if completion is TrajectoryCompletion.TERMINAL:
            outcome = _enum_value(RunOutcome, self.terminal_outcome, "target.terminal_outcome")
            index = _require_nonnegative_int(
                self.terminal_policy_record_index,
                "target.terminal_policy_record_index",
            )
            if index != count - 1 or self.interruption_point is not None:
                raise TrajectoryValidationError(
                    "A terminal target must identify the final policy record only."
                )
            object.__setattr__(self, "terminal_outcome", outcome)
        else:
            if self.terminal_outcome is not None or self.terminal_policy_record_index is not None:
                raise TrajectoryValidationError(
                    "Only a terminal trajectory can contain a terminal outcome label."
                )
            if completion is TrajectoryCompletion.INTERRUPTED:
                point = _enum_value(
                    InterruptionPoint,
                    self.interruption_point,
                    "target.interruption_point",
                )
                object.__setattr__(self, "interruption_point", point)
            elif self.interruption_point is not None:
                raise TrajectoryValidationError(
                    "Unsupported completion cannot contain an interruption point."
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "completion": self.completion.value,
            "interruption_point": (
                None if self.interruption_point is None else self.interruption_point.value
            ),
            "label_timing": self.label_timing,
            "policy_record_count": self.policy_record_count,
            "target_kind": self.target_kind,
            "terminal_outcome": (
                None if self.terminal_outcome is None else self.terminal_outcome.value
            ),
            "terminal_policy_record_index": self.terminal_policy_record_index,
            "trajectory_id": self.trajectory_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HindsightTargetRecord":
        _require_exact_fields(
            value,
            {
                "completion",
                "interruption_point",
                "label_timing",
                "policy_record_count",
                "target_kind",
                "terminal_outcome",
                "terminal_policy_record_index",
                "trajectory_id",
            },
            "hindsight_target_record",
        )
        return cls(
            trajectory_id=value["trajectory_id"],
            completion=value["completion"],
            policy_record_count=value["policy_record_count"],
            terminal_outcome=value["terminal_outcome"],
            terminal_policy_record_index=value["terminal_policy_record_index"],
            interruption_point=value["interruption_point"],
            target_kind=value["target_kind"],
            label_timing=value["label_timing"],
        )


@dataclass(frozen=True, slots=True)
class DecisionCorrelation:
    run_id: str
    decision_sequence: int
    decision_hash: str
    candidate_id: str

    def __post_init__(self) -> None:
        _require_pattern(self.run_id, _OPAQUE_ID_PATTERN, "audit.correlation.run_id")
        _require_nonnegative_int(
            self.decision_sequence, "audit.correlation.decision_sequence"
        )
        _require_pattern(
            self.decision_hash, _HASH_PATTERN, "audit.correlation.decision_hash"
        )
        if not self.candidate_id.startswith("cand."):
            raise TrajectoryValidationError(
                "audit.correlation.candidate_id must be a canonical candidate ID."
            )
        _require_pattern(
            self.candidate_id[5:], _HASH_PATTERN, "audit.correlation.candidate_id"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision_hash": self.decision_hash,
            "decision_sequence": self.decision_sequence,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DecisionCorrelation":
        _require_exact_fields(
            value,
            {"candidate_id", "decision_hash", "decision_sequence", "run_id"},
            "decision_correlation",
        )
        return cls(
            run_id=value["run_id"],
            decision_sequence=value["decision_sequence"],
            decision_hash=value["decision_hash"],
            candidate_id=value["candidate_id"],
        )


@dataclass(frozen=True, slots=True)
class SyntheticReceipt:
    result: TransitionResult
    reason: TransitionReason
    next_run_id: str
    next_decision_sequence: int
    next_decision_hash: str

    def __post_init__(self) -> None:
        result = _enum_value(TransitionResult, self.result, "audit.receipt.result")
        reason = _enum_value(TransitionReason, self.reason, "audit.receipt.reason")
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "reason", reason)
        allowed = {
            TransitionResult.ACCEPTED: {TransitionReason.ACCEPTED},
            TransitionResult.STALE: {TransitionReason.STALE_BINDING},
            TransitionResult.REJECTED: {
                TransitionReason.INVALID_CANDIDATE,
                TransitionReason.REJECTED_BY_RULES,
                TransitionReason.UNSUPPORTED,
            },
        }
        if reason not in allowed[result]:
            raise TrajectoryValidationError("Synthetic receipt result/reason is invalid.")
        _require_pattern(self.next_run_id, _OPAQUE_ID_PATTERN, "audit.receipt.next_run_id")
        _require_nonnegative_int(
            self.next_decision_sequence, "audit.receipt.next_decision_sequence"
        )
        _require_pattern(
            self.next_decision_hash,
            _HASH_PATTERN,
            "audit.receipt.next_decision_hash",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_decision_hash": self.next_decision_hash,
            "next_decision_sequence": self.next_decision_sequence,
            "next_run_id": self.next_run_id,
            "reason": self.reason.value,
            "result": self.result.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SyntheticReceipt":
        _require_exact_fields(
            value,
            {
                "next_decision_hash",
                "next_decision_sequence",
                "next_run_id",
                "reason",
                "result",
            },
            "synthetic_receipt",
        )
        return cls(
            result=value["result"],
            reason=value["reason"],
            next_run_id=value["next_run_id"],
            next_decision_sequence=value["next_decision_sequence"],
            next_decision_hash=value["next_decision_hash"],
        )


@dataclass(frozen=True, slots=True)
class SyntheticAuditRecord:
    """Operational metadata for one headless action, never a policy record."""

    trajectory_id: str
    local_sequence: int
    policy_record_index: int
    decision_correlation: DecisionCorrelation
    receipt: SyntheticReceipt
    audit_scope: str = "synthetic_headless"

    def __post_init__(self) -> None:
        _require_pattern(self.trajectory_id, _ID_PATTERN, "audit.trajectory_id")
        _require_nonnegative_int(self.local_sequence, "audit.local_sequence")
        _require_nonnegative_int(self.policy_record_index, "audit.policy_record_index")
        if not isinstance(self.decision_correlation, DecisionCorrelation):
            raise TrajectoryValidationError("Audit decision correlation has the wrong type.")
        if not isinstance(self.receipt, SyntheticReceipt):
            raise TrajectoryValidationError("Audit receipt has the wrong type.")
        if self.audit_scope != "synthetic_headless":
            raise TrajectoryValidationError("Only synthetic headless audit is supported.")
        correlation_identity = (
            self.decision_correlation.run_id,
            self.decision_correlation.decision_sequence,
            self.decision_correlation.decision_hash,
        )
        receipt_identity = (
            self.receipt.next_run_id,
            self.receipt.next_decision_sequence,
            self.receipt.next_decision_hash,
        )
        if self.receipt.result is TransitionResult.ACCEPTED:
            if (
                self.receipt.next_run_id != self.decision_correlation.run_id
                or self.receipt.next_decision_sequence
                <= self.decision_correlation.decision_sequence
            ):
                raise TrajectoryValidationError(
                    "An accepted synthetic receipt must advance the same run."
                )
        elif self.receipt.result is TransitionResult.REJECTED:
            if receipt_identity != correlation_identity:
                raise TrajectoryValidationError(
                    "A rejected synthetic receipt must retain decision identity."
                )
        elif receipt_identity == correlation_identity:
            raise TrajectoryValidationError(
                "A stale synthetic receipt must identify a different authoritative decision."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_scope": self.audit_scope,
            "decision_correlation": self.decision_correlation.to_dict(),
            "local_sequence": self.local_sequence,
            "policy_record_index": self.policy_record_index,
            "receipt": self.receipt.to_dict(),
            "trajectory_id": self.trajectory_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SyntheticAuditRecord":
        _require_exact_fields(
            value,
            {
                "audit_scope",
                "decision_correlation",
                "local_sequence",
                "policy_record_index",
                "receipt",
                "trajectory_id",
            },
            "synthetic_audit_record",
        )
        correlation = value["decision_correlation"]
        receipt = value["receipt"]
        if not isinstance(correlation, Mapping) or not isinstance(receipt, Mapping):
            raise TrajectoryValidationError(
                "Audit correlation and receipt must be objects."
            )
        return cls(
            trajectory_id=value["trajectory_id"],
            local_sequence=value["local_sequence"],
            policy_record_index=value["policy_record_index"],
            decision_correlation=DecisionCorrelation.from_dict(correlation),
            receipt=SyntheticReceipt.from_dict(receipt),
            audit_scope=value["audit_scope"],
        )


def policy_view_for(record: PolicyReplayRecord) -> PolicyView:
    """Return a chooser-safe view, rejecting either non-policy sidecar type."""

    if type(record) is not PolicyReplayRecord:
        raise TypeError("Only PolicyReplayRecord can be converted to a PolicyView.")
    return record.policy_view()


@dataclass(frozen=True, slots=True)
class StreamDescriptor:
    role: StreamRole
    schema: str
    file_name: str
    record_count: int
    sha256: str

    def __post_init__(self) -> None:
        role = _enum_value(StreamRole, self.role, "stream.role")
        object.__setattr__(self, "role", role)
        if self.schema != _ROLE_SCHEMAS[role]:
            raise TrajectoryValidationError("Stream role and schema do not match.")
        _require_text(self.file_name, "stream.file_name")
        _require_nonnegative_int(self.record_count, "stream.record_count")
        if self.record_count > _MAX_RECORDS:
            raise TrajectoryValidationError("Stream record count is out of range.")
        _require_pattern(self.sha256, _HASH_PATTERN, "stream.sha256")

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "record_count": self.record_count,
            "role": self.role.value,
            "schema": self.schema,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StreamDescriptor":
        _require_exact_fields(
            value,
            {"file_name", "record_count", "role", "schema", "sha256"},
            "stream_descriptor",
        )
        return cls(
            role=value["role"],
            schema=value["schema"],
            file_name=value["file_name"],
            record_count=value["record_count"],
            sha256=value["sha256"],
        )


@dataclass(frozen=True, slots=True)
class TrajectoryManifest:
    trajectory_id: str
    completion: TrajectoryCompletion
    contract: str
    contract_fingerprint: str
    backend_id: str
    backend_version: str
    backend_fingerprint: str
    content_version: str
    content_fingerprint: str
    rules_version: str
    rules_fingerprint: str
    evidence: tuple[ComponentEvidence, ...]
    streams: tuple[StreamDescriptor, ...]
    interruption_point: InterruptionPoint | None = None
    schema: str = MANIFEST_SCHEMA
    hash_algorithm: str = HASH_ALGORITHM

    def __post_init__(self) -> None:
        if self.schema != MANIFEST_SCHEMA or self.hash_algorithm != HASH_ALGORITHM:
            raise TrajectoryValidationError("Unsupported trajectory manifest schema.")
        _require_pattern(self.trajectory_id, _ID_PATTERN, "manifest.trajectory_id")
        completion = _enum_value(
            TrajectoryCompletion, self.completion, "manifest.completion"
        )
        object.__setattr__(self, "completion", completion)
        if self.contract != CONTRACT_VERSION or self.contract_fingerprint != CONTRACT_FINGERPRINT:
            raise TrajectoryValidationError("Trajectory contract identity is incompatible.")
        _require_pattern(self.backend_id, _OPAQUE_ID_PATTERN, "manifest.backend_id")
        _require_pattern(self.backend_version, _VERSION_PATTERN, "manifest.backend_version")
        _require_pattern(
            self.backend_fingerprint, _HASH_PATTERN, "manifest.backend_fingerprint"
        )
        _require_pattern(self.content_version, _VERSION_PATTERN, "manifest.content_version")
        _require_pattern(
            self.content_fingerprint, _HASH_PATTERN, "manifest.content_fingerprint"
        )
        _require_pattern(self.rules_version, _VERSION_PATTERN, "manifest.rules_version")
        _require_pattern(
            self.rules_fingerprint, _HASH_PATTERN, "manifest.rules_fingerprint"
        )
        evidence = tuple(self.evidence)
        if not evidence or any(not isinstance(item, ComponentEvidence) for item in evidence):
            raise TrajectoryValidationError("Manifest evidence must be typed and non-empty.")
        if any(item.label not in _ALLOWED_EVIDENCE for item in evidence):
            raise TrajectoryValidationError(
                "Trajectory evidence must remain combat_v0 or structural_fixture."
            )
        components = tuple(item.component for item in evidence)
        if components != tuple(sorted(set(components))):
            raise TrajectoryValidationError(
                "Trajectory evidence components must be unique and sorted."
            )
        object.__setattr__(self, "evidence", evidence)
        streams = tuple(self.streams)
        if tuple(item.role for item in streams) != _ROLE_ORDER:
            raise TrajectoryValidationError(
                "Manifest streams must contain every role in canonical order."
            )
        expected_names = _stream_file_names(self.trajectory_id)
        if any(item.file_name != expected_names[item.role] for item in streams):
            raise TrajectoryValidationError(
                "Manifest stream file names do not match trajectory identity and role."
            )
        object.__setattr__(self, "streams", streams)
        if completion is TrajectoryCompletion.INTERRUPTED:
            point = _enum_value(
                InterruptionPoint,
                self.interruption_point,
                "manifest.interruption_point",
            )
            object.__setattr__(self, "interruption_point", point)
        elif self.interruption_point is not None:
            raise TrajectoryValidationError(
                "Only an interrupted manifest can have an interruption point."
            )

    def descriptor(self, role: StreamRole) -> StreamDescriptor:
        normalized = _enum_value(StreamRole, role, "role")
        return next(item for item in self.streams if item.role is normalized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_fingerprint": self.backend_fingerprint,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "completion": self.completion.value,
            "content_fingerprint": self.content_fingerprint,
            "content_version": self.content_version,
            "contract": self.contract,
            "contract_fingerprint": self.contract_fingerprint,
            "evidence": [item.to_dict() for item in self.evidence],
            "hash_algorithm": self.hash_algorithm,
            "interruption_point": (
                None if self.interruption_point is None else self.interruption_point.value
            ),
            "rules_fingerprint": self.rules_fingerprint,
            "rules_version": self.rules_version,
            "schema": self.schema,
            "streams": [item.to_dict() for item in self.streams],
            "trajectory_id": self.trajectory_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TrajectoryManifest":
        _require_exact_fields(
            value,
            {
                "backend_fingerprint",
                "backend_id",
                "backend_version",
                "completion",
                "content_fingerprint",
                "content_version",
                "contract",
                "contract_fingerprint",
                "evidence",
                "hash_algorithm",
                "interruption_point",
                "rules_fingerprint",
                "rules_version",
                "schema",
                "streams",
                "trajectory_id",
            },
            "trajectory_manifest",
        )
        evidence = value["evidence"]
        streams = value["streams"]
        if not isinstance(evidence, list) or not all(
            isinstance(item, Mapping) for item in evidence
        ):
            raise TrajectoryValidationError("Manifest evidence must be object records.")
        if not isinstance(streams, list) or not all(
            isinstance(item, Mapping) for item in streams
        ):
            raise TrajectoryValidationError("Manifest streams must be object records.")
        try:
            typed_evidence = tuple(ComponentEvidence.from_dict(item) for item in evidence)
        except ContractValidationError as exc:
            raise TrajectoryValidationError("Invalid manifest evidence.") from exc
        return cls(
            trajectory_id=value["trajectory_id"],
            completion=value["completion"],
            contract=value["contract"],
            contract_fingerprint=value["contract_fingerprint"],
            backend_id=value["backend_id"],
            backend_version=value["backend_version"],
            backend_fingerprint=value["backend_fingerprint"],
            content_version=value["content_version"],
            content_fingerprint=value["content_fingerprint"],
            rules_version=value["rules_version"],
            rules_fingerprint=value["rules_fingerprint"],
            evidence=typed_evidence,
            streams=tuple(StreamDescriptor.from_dict(item) for item in streams),
            interruption_point=value["interruption_point"],
            schema=value["schema"],
            hash_algorithm=value["hash_algorithm"],
        )

    def to_bytes(self) -> bytes:
        return canonical_json(self.to_dict()).encode("utf-8")


@dataclass(frozen=True, slots=True)
class TrajectoryPaths:
    policy_replay: Path
    hindsight_target: Path
    synthetic_audit: Path
    manifest: Path

    @classmethod
    def in_directory(
        cls, directory: str | Path, trajectory_id: str
    ) -> "TrajectoryPaths":
        _require_pattern(trajectory_id, _ID_PATTERN, "trajectory_id")
        root = Path(directory)
        names = _stream_file_names(trajectory_id)
        return cls(
            root / names[StreamRole.POLICY_REPLAY],
            root / names[StreamRole.HINDSIGHT_TARGET],
            root / names[StreamRole.SYNTHETIC_AUDIT],
            root / f"{trajectory_id}.manifest.json",
        )


@dataclass(frozen=True, slots=True)
class FinalizedTrajectory:
    """The immutable canonical bytes for all three streams and their manifest."""

    manifest: TrajectoryManifest
    policy_replay_jsonl: bytes
    hindsight_target_jsonl: bytes
    synthetic_audit_jsonl: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, TrajectoryManifest):
            raise TypeError("manifest must be a TrajectoryManifest.")
        for name in (
            "policy_replay_jsonl",
            "hindsight_target_jsonl",
            "synthetic_audit_jsonl",
        ):
            if not isinstance(getattr(self, name), bytes):
                raise TypeError(f"{name} must be bytes.")
        _validate_finalized(self)

    @property
    def manifest_json(self) -> bytes:
        return self.manifest.to_bytes()

    def write_to(self, directory: str | Path) -> TrajectoryPaths:
        """Write separate streams exclusively, committing with the manifest last."""

        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink() or not root.is_dir():
            raise TrajectoryValidationError(
                "Trajectory output root must be a non-symlink directory."
            )
        paths = TrajectoryPaths.in_directory(root, self.manifest.trajectory_id)
        output_paths = (
            paths.policy_replay,
            paths.hindsight_target,
            paths.synthetic_audit,
            paths.manifest,
        )
        collisions = [
            path.name for path in output_paths if path.exists() or path.is_symlink()
        ]
        if collisions:
            raise FileExistsError(
                f"Trajectory output already exists: {', '.join(collisions)}."
            )
        # The manifest is the finalization marker.  A process interruption before
        # it is durable is detected as an incomplete trajectory on load.
        _write_exclusive(paths.policy_replay, self.policy_replay_jsonl)
        _write_exclusive(paths.hindsight_target, self.hindsight_target_jsonl)
        _write_exclusive(paths.synthetic_audit, self.synthetic_audit_jsonl)
        _write_exclusive(paths.manifest, self.manifest_json)
        return paths


@dataclass(frozen=True, slots=True)
class _PendingBoundary:
    policy_record_index: int
    run_id: str
    decision_sequence: int
    decision_hash: str
    candidate_id: str


class TrajectoryRecorder:
    """Build one separated trajectory from authoritative headless decisions."""

    def __init__(self, trajectory_id: str, backend_manifest: BackendManifest) -> None:
        _require_pattern(trajectory_id, _ID_PATTERN, "trajectory_id")
        if not isinstance(backend_manifest, BackendManifest):
            raise TypeError("backend_manifest must be a BackendManifest.")
        if backend_manifest.capabilities.live_truth:
            raise TrajectoryValidationError("Live audit/capture is outside this recorder.")
        if any(item.label not in _ALLOWED_EVIDENCE for item in backend_manifest.evidence):
            raise TrajectoryValidationError(
                "Recorder accepts only combat_v0 or structural_fixture evidence."
            )
        self._trajectory_id = trajectory_id
        self._backend_manifest = backend_manifest
        self._policy_records: list[PolicyReplayRecord] = []
        self._audit_records: list[SyntheticAuditRecord] = []
        self._run_id: str | None = None
        self._last_decision: DecisionState | None = None
        self._pending: _PendingBoundary | None = None
        self._expected_next: tuple[str, int, str] | None = None
        self._transition_stopped = False
        self._finalized = False

    def record_boundary(
        self, decision: DecisionState, chosen_candidate_id: str | None = None
    ) -> PolicyReplayRecord:
        self._require_open()
        if not isinstance(decision, DecisionState):
            raise TypeError("decision must be a DecisionState.")
        if self._pending is not None:
            raise TrajectoryValidationError(
                "The chosen action receipt must be recorded before another boundary."
            )
        if self._transition_stopped:
            raise TrajectoryValidationError(
                "A rejected or stale transition must finalize as interrupted."
            )
        self._validate_decision_provenance(decision)
        if self._run_id is None:
            self._run_id = decision.run_id
            if decision.decision_sequence != 0:
                raise TrajectoryValidationError(
                    "A trajectory must begin at decision sequence zero."
                )
        elif decision.run_id != self._run_id:
            raise TrajectoryValidationError("Trajectory run identity changed.")
        if self._expected_next is not None:
            identity = (
                decision.run_id,
                decision.decision_sequence,
                decision.decision_hash,
            )
            if identity != self._expected_next:
                raise TrajectoryValidationError(
                    "The next boundary does not match the recorded transition receipt."
                )
            self._expected_next = None
        elif self._last_decision is not None:
            raise TrajectoryValidationError(
                "A new boundary requires the preceding accepted transition receipt."
            )
        record = PolicyReplayRecord.from_decision(decision, chosen_candidate_id)
        index = len(self._policy_records)
        self._policy_records.append(record)
        self._last_decision = decision
        if record.chosen_action is not None:
            self._pending = _PendingBoundary(
                index,
                decision.run_id,
                decision.decision_sequence,
                decision.decision_hash,
                record.chosen_action.candidate_id,
            )
        return record

    def record_transition(self, transition: Transition) -> SyntheticAuditRecord:
        self._require_open()
        if not isinstance(transition, Transition):
            raise TypeError("transition must be a Transition.")
        pending = self._pending
        if pending is None:
            raise TrajectoryValidationError(
                "A transition requires a boundary with a chosen action."
            )
        binding = transition.binding
        expected = (
            pending.run_id,
            pending.decision_sequence,
            pending.decision_hash,
            pending.candidate_id,
        )
        actual = (
            binding.run_id,
            binding.decision_sequence,
            binding.decision_hash,
            binding.candidate_id,
        )
        if actual != expected:
            raise TrajectoryValidationError(
                "Transition receipt does not correlate to the chosen boundary action."
            )
        self._validate_decision_provenance(transition.next_decision)
        record = SyntheticAuditRecord(
            trajectory_id=self._trajectory_id,
            local_sequence=len(self._audit_records),
            policy_record_index=pending.policy_record_index,
            decision_correlation=DecisionCorrelation(*expected),
            receipt=SyntheticReceipt(
                transition.result,
                transition.reason,
                transition.next_decision.run_id,
                transition.next_decision.decision_sequence,
                transition.next_decision.decision_hash,
            ),
        )
        self._audit_records.append(record)
        self._pending = None
        if transition.result is TransitionResult.ACCEPTED:
            self._expected_next = (
                transition.next_decision.run_id,
                transition.next_decision.decision_sequence,
                transition.next_decision.decision_hash,
            )
        else:
            self._transition_stopped = True
        return record

    def finalize(self) -> FinalizedTrajectory:
        """Finalize a terminal or unsupported trajectory."""

        self._require_open()
        if not self._policy_records or self._last_decision is None:
            raise TrajectoryValidationError("Cannot finalize an empty trajectory.")
        if self._pending is not None or self._expected_next is not None:
            raise TrajectoryInterruptedError(
                "Trajectory ended between a boundary, receipt, or next boundary."
            )
        status = self._last_decision.status
        if status is DecisionStatus.TERMINAL:
            completion = TrajectoryCompletion.TERMINAL
            try:
                outcome = RunOutcome(self._last_decision.observation.data["outcome"])
            except (KeyError, ValueError) as exc:
                raise TrajectoryValidationError(
                    "Terminal public observation has no supported run outcome."
                ) from exc
            target = HindsightTargetRecord(
                self._trajectory_id,
                completion,
                len(self._policy_records),
                outcome,
                len(self._policy_records) - 1,
            )
        elif status is DecisionStatus.UNSUPPORTED:
            completion = TrajectoryCompletion.UNSUPPORTED
            target = HindsightTargetRecord(
                self._trajectory_id,
                completion,
                len(self._policy_records),
                None,
                None,
            )
        else:
            raise TrajectoryInterruptedError(
                "A non-terminal trajectory must use finalize_interrupted()."
            )
        return self._finalize(completion, target, None)

    def finalize_interrupted(self) -> FinalizedTrajectory:
        """Finalize an explicitly incomplete episode with a detected interruption point."""

        self._require_open()
        if not self._policy_records or self._last_decision is None:
            raise TrajectoryValidationError("Cannot finalize an empty trajectory.")
        if self._last_decision.status in {
            DecisionStatus.TERMINAL,
            DecisionStatus.UNSUPPORTED,
        }:
            raise TrajectoryValidationError(
                "A terminal or unsupported trajectory is not interrupted."
            )
        point = self._interruption_point()
        target = HindsightTargetRecord(
            self._trajectory_id,
            TrajectoryCompletion.INTERRUPTED,
            len(self._policy_records),
            None,
            None,
            point,
        )
        return self._finalize(TrajectoryCompletion.INTERRUPTED, target, point)

    def _interruption_point(self) -> InterruptionPoint:
        assert self._last_decision is not None
        if self._transition_stopped:
            return InterruptionPoint.TRANSITION_STOPPED
        if self._pending is not None:
            return InterruptionPoint.AWAITING_RECEIPT
        if self._expected_next is not None:
            return InterruptionPoint.BEFORE_NEXT_BOUNDARY
        if self._last_decision.status is DecisionStatus.WAITING:
            return InterruptionPoint.WAITING
        return InterruptionPoint.BEFORE_CHOICE

    def _finalize(
        self,
        completion: TrajectoryCompletion,
        target: HindsightTargetRecord,
        interruption_point: InterruptionPoint | None,
    ) -> FinalizedTrajectory:
        policy_raw = _encode_jsonl(self._policy_records)
        target_raw = _encode_jsonl((target,))
        audit_raw = _encode_jsonl(self._audit_records)
        raw_by_role = {
            StreamRole.POLICY_REPLAY: policy_raw,
            StreamRole.HINDSIGHT_TARGET: target_raw,
            StreamRole.SYNTHETIC_AUDIT: audit_raw,
        }
        counts = {
            StreamRole.POLICY_REPLAY: len(self._policy_records),
            StreamRole.HINDSIGHT_TARGET: 1,
            StreamRole.SYNTHETIC_AUDIT: len(self._audit_records),
        }
        names = _stream_file_names(self._trajectory_id)
        streams = tuple(
            StreamDescriptor(
                role,
                _ROLE_SCHEMAS[role],
                names[role],
                counts[role],
                _sha256(raw_by_role[role]),
            )
            for role in _ROLE_ORDER
        )
        source = self._backend_manifest
        manifest = TrajectoryManifest(
            trajectory_id=self._trajectory_id,
            completion=completion,
            contract=source.contract,
            contract_fingerprint=source.contract_fingerprint,
            backend_id=source.backend_id,
            backend_version=source.backend_version,
            backend_fingerprint=source.backend_fingerprint,
            content_version=source.content_version,
            content_fingerprint=source.content_fingerprint,
            rules_version=source.rules_version,
            rules_fingerprint=source.rules_fingerprint,
            evidence=source.evidence,
            streams=streams,
            interruption_point=interruption_point,
        )
        finalized = FinalizedTrajectory(manifest, policy_raw, target_raw, audit_raw)
        self._finalized = True
        return finalized

    def _validate_decision_provenance(self, decision: DecisionState) -> None:
        source = self._backend_manifest
        actual = (
            decision.contract,
            decision.contract_fingerprint,
            decision.backend_id,
            decision.backend_version,
            decision.backend_fingerprint,
            decision.content_version,
            decision.content_fingerprint,
            decision.rules_version,
            decision.rules_fingerprint,
        )
        expected = (
            source.contract,
            source.contract_fingerprint,
            source.backend_id,
            source.backend_version,
            source.backend_fingerprint,
            source.content_version,
            source.content_fingerprint,
            source.rules_version,
            source.rules_fingerprint,
        )
        if actual != expected:
            raise TrajectoryValidationError(
                "Decision provenance does not match the bound backend manifest."
            )

    def _require_open(self) -> None:
        if self._finalized:
            raise TrajectoryValidationError("A finalized trajectory is immutable.")


def validate_trajectory(
    manifest_json: bytes | str,
    policy_replay_jsonl: bytes,
    hindsight_target_jsonl: bytes,
    synthetic_audit_jsonl: bytes,
) -> FinalizedTrajectory:
    """Parse and validate canonical bytes, hashes, roles, and cross-stream joins."""

    manifest_raw = (
        manifest_json.encode("utf-8") if isinstance(manifest_json, str) else manifest_json
    )
    if not isinstance(manifest_raw, bytes):
        raise TypeError("manifest_json must be bytes or text.")
    if len(manifest_raw) > _MAX_MANIFEST_BYTES:
        raise TrajectoryValidationError("Trajectory manifest exceeds its size bound.")
    manifest_value = _load_canonical_object(manifest_raw, "trajectory manifest")
    manifest = TrajectoryManifest.from_dict(manifest_value)
    return FinalizedTrajectory(
        manifest,
        policy_replay_jsonl,
        hindsight_target_jsonl,
        synthetic_audit_jsonl,
    )


def load_trajectory(directory: str | Path, trajectory_id: str) -> FinalizedTrajectory:
    """Load a finalized physical file set; missing members signal interruption."""

    paths = TrajectoryPaths.in_directory(directory, trajectory_id)
    all_paths = (
        paths.policy_replay,
        paths.hindsight_target,
        paths.synthetic_audit,
        paths.manifest,
    )
    missing = [path.name for path in all_paths if not path.exists()]
    if missing:
        raise TrajectoryInterruptedError(
            f"Trajectory file set is incomplete: {', '.join(missing)}."
        )
    for path in all_paths:
        if path.is_symlink() or not path.is_file():
            raise TrajectoryIntegrityError(
                "Trajectory members must be regular non-symlink files."
            )
    return validate_trajectory(
        _read_bounded(paths.manifest, _MAX_MANIFEST_BYTES),
        _read_bounded(paths.policy_replay, _MAX_STREAM_BYTES),
        _read_bounded(paths.hindsight_target, _MAX_STREAM_BYTES),
        _read_bounded(paths.synthetic_audit, _MAX_STREAM_BYTES),
    )


def decode_policy_replay(raw: bytes) -> tuple[PolicyReplayRecord, ...]:
    """Decode only the policy stream into chooser-safe record types."""

    return _decode_jsonl(raw, PolicyReplayRecord.from_dict, "policy replay")


def decode_hindsight_targets(raw: bytes) -> tuple[HindsightTargetRecord, ...]:
    """Decode only the physically separate hindsight target stream."""

    return _decode_jsonl(raw, HindsightTargetRecord.from_dict, "hindsight target")


def decode_synthetic_audit(raw: bytes) -> tuple[SyntheticAuditRecord, ...]:
    """Decode only the non-live operational audit stream."""

    return _decode_jsonl(raw, SyntheticAuditRecord.from_dict, "synthetic audit")


def _validate_finalized(finalized: FinalizedTrajectory) -> None:
    manifest = finalized.manifest
    raw_by_role = {
        StreamRole.POLICY_REPLAY: finalized.policy_replay_jsonl,
        StreamRole.HINDSIGHT_TARGET: finalized.hindsight_target_jsonl,
        StreamRole.SYNTHETIC_AUDIT: finalized.synthetic_audit_jsonl,
    }
    for role, raw in raw_by_role.items():
        if len(raw) > _MAX_STREAM_BYTES:
            raise TrajectoryValidationError(f"{role.value} exceeds its size bound.")
        descriptor = manifest.descriptor(role)
        if _sha256(raw) != descriptor.sha256:
            raise TrajectoryIntegrityError(
                f"{role.value} does not match its finalized stream hash."
            )
    policy = decode_policy_replay(finalized.policy_replay_jsonl)
    targets = decode_hindsight_targets(finalized.hindsight_target_jsonl)
    audits = decode_synthetic_audit(finalized.synthetic_audit_jsonl)
    typed_policy = tuple(policy)
    typed_targets = tuple(targets)
    typed_audits = tuple(audits)
    counts = {
        StreamRole.POLICY_REPLAY: len(typed_policy),
        StreamRole.HINDSIGHT_TARGET: len(typed_targets),
        StreamRole.SYNTHETIC_AUDIT: len(typed_audits),
    }
    if any(manifest.descriptor(role).record_count != counts[role] for role in _ROLE_ORDER):
        raise TrajectoryIntegrityError("Manifest stream record count does not match bytes.")
    _validate_cross_stream(manifest, typed_policy, typed_targets, typed_audits)


def _validate_cross_stream(
    manifest: TrajectoryManifest,
    policy: tuple[PolicyReplayRecord, ...],
    targets: tuple[HindsightTargetRecord, ...],
    audits: tuple[SyntheticAuditRecord, ...],
) -> None:
    if not policy or len(targets) != 1:
        raise TrajectoryValidationError(
            "A trajectory needs policy boundaries and exactly one target record."
        )
    if any(
        record.status is not DecisionStatus.ACTIONABLE
        or record.chosen_action is None
        for record in policy[:-1]
    ):
        raise TrajectoryValidationError(
            "Every non-final policy boundary must be actionable and chosen."
        )
    target = targets[0]
    if target.trajectory_id != manifest.trajectory_id:
        raise TrajectoryIntegrityError("Target trajectory identity does not match manifest.")
    if (
        target.completion is not manifest.completion
        or target.interruption_point is not manifest.interruption_point
        or target.policy_record_count != len(policy)
    ):
        raise TrajectoryIntegrityError("Target completion metadata does not match manifest.")

    chosen_indices = [
        index for index, record in enumerate(policy) if record.chosen_action is not None
    ]
    if tuple(item.local_sequence for item in audits) != tuple(range(len(audits))):
        raise TrajectoryValidationError("Audit local sequence is not contiguous.")
    audit_indices = [item.policy_record_index for item in audits]
    if audit_indices != sorted(set(audit_indices)):
        raise TrajectoryValidationError("Audit policy correlations are not unique and ordered.")
    if any(index >= len(policy) for index in audit_indices):
        raise TrajectoryValidationError("Audit references a missing policy record.")
    if any(item.trajectory_id != manifest.trajectory_id for item in audits):
        raise TrajectoryIntegrityError("Audit trajectory identity does not match manifest.")
    for item in audits:
        chosen = policy[item.policy_record_index].chosen_action
        if chosen is None or chosen.candidate_id != item.decision_correlation.candidate_id:
            raise TrajectoryIntegrityError(
                "Audit decision correlation does not match the chosen policy action."
            )
    missing_receipts = [index for index in chosen_indices if index not in audit_indices]
    if manifest.completion is TrajectoryCompletion.INTERRUPTED:
        if len(missing_receipts) > 1 or (
            missing_receipts and missing_receipts != [len(policy) - 1]
        ):
            raise TrajectoryValidationError(
                "Only the final interrupted choice may lack a receipt."
            )
    elif missing_receipts:
        raise TrajectoryValidationError("A complete trajectory is missing an action receipt.")
    if any(index not in chosen_indices for index in audit_indices):
        raise TrajectoryValidationError("Audit exists without a chosen policy action.")

    for current, following in zip(audits, audits[1:]):
        receipt = current.receipt
        correlation = following.decision_correlation
        if receipt.result is TransitionResult.ACCEPTED and (
            receipt.next_run_id,
            receipt.next_decision_sequence,
            receipt.next_decision_hash,
        ) != (
            correlation.run_id,
            correlation.decision_sequence,
            correlation.decision_hash,
        ):
            raise TrajectoryIntegrityError(
                "Accepted receipt does not correlate to the next audited decision."
            )

    final = policy[-1]
    if manifest.completion is TrajectoryCompletion.TERMINAL:
        if final.status is not DecisionStatus.TERMINAL:
            raise TrajectoryValidationError("Terminal manifest lacks a terminal policy boundary.")
        try:
            visible_outcome = RunOutcome(final.observation.data["outcome"])
        except (KeyError, ValueError) as exc:
            raise TrajectoryValidationError("Final public outcome is invalid.") from exc
        if (
            target.terminal_outcome is not visible_outcome
            or target.terminal_policy_record_index != len(policy) - 1
        ):
            raise TrajectoryIntegrityError(
                "Hindsight target disagrees with the observable terminal boundary."
            )
    elif manifest.completion is TrajectoryCompletion.UNSUPPORTED:
        if final.status is not DecisionStatus.UNSUPPORTED:
            raise TrajectoryValidationError(
                "Unsupported manifest lacks an unsupported policy boundary."
            )
    elif final.status in {DecisionStatus.TERMINAL, DecisionStatus.UNSUPPORTED}:
        raise TrajectoryValidationError(
            "Interrupted manifest cannot end at a completed policy boundary."
        )
    else:
        point = manifest.interruption_point
        final_index = len(policy) - 1
        final_chosen = final.chosen_action is not None
        final_audit = next(
            (item for item in audits if item.policy_record_index == final_index),
            None,
        )
        if point is InterruptionPoint.BEFORE_CHOICE:
            valid_point = (
                final.status is DecisionStatus.ACTIONABLE
                and not final_chosen
                and final_audit is None
            )
        elif point is InterruptionPoint.AWAITING_RECEIPT:
            valid_point = final_chosen and final_audit is None
        elif point is InterruptionPoint.BEFORE_NEXT_BOUNDARY:
            valid_point = (
                final_chosen
                and final_audit is not None
                and final_audit.receipt.result is TransitionResult.ACCEPTED
            )
        elif point is InterruptionPoint.WAITING:
            valid_point = (
                final.status is DecisionStatus.WAITING
                and not final_chosen
                and final_audit is None
            )
        else:
            valid_point = (
                point is InterruptionPoint.TRANSITION_STOPPED
                and final_chosen
                and final_audit is not None
                and final_audit.receipt.result is not TransitionResult.ACCEPTED
            )
        if not valid_point:
            raise TrajectoryIntegrityError(
                "Interruption point does not match the finalized record boundary."
            )


def _stream_file_names(trajectory_id: str) -> dict[StreamRole, str]:
    return {
        role: f"{trajectory_id}.{_ROLE_SUFFIXES[role]}" for role in _ROLE_ORDER
    }


def _encode_jsonl(records: Sequence[Any]) -> bytes:
    return b"".join(
        canonical_json(record.to_dict()).encode("utf-8") + b"\n" for record in records
    )


def _decode_jsonl(raw: bytes, factory: Any, description: str) -> tuple[Any, ...]:
    if not isinstance(raw, bytes):
        raise TypeError(f"{description} bytes must be bytes.")
    if not raw:
        return ()
    if not raw.endswith(b"\n"):
        raise TrajectoryValidationError(f"{description} JSONL must end with a newline.")
    lines = raw[:-1].split(b"\n")
    if len(lines) > _MAX_RECORDS or any(not line for line in lines):
        raise TrajectoryValidationError(f"{description} JSONL has invalid record framing.")
    records = []
    for index, line in enumerate(lines):
        value = _load_canonical_object(line, f"{description} record {index}")
        records.append(factory(value))
    return tuple(records)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise TrajectoryValidationError(f"Duplicate JSON field: {key!r}.")
        value[key] = item
    return value


def _reject_float(value: str) -> None:
    raise TrajectoryValidationError(f"Floating-point JSON is not supported: {value!r}.")


def _load_canonical_object(raw: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_float,
        )
    except TrajectoryValidationError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TrajectoryValidationError(f"Invalid {description} JSON.") from exc
    if not isinstance(value, dict):
        raise TrajectoryValidationError(f"{description} must be a JSON object.")
    try:
        canonical = canonical_json(value).encode("utf-8")
    except ContractValidationError as exc:
        raise TrajectoryValidationError(f"Invalid value in {description}.") from exc
    if raw != canonical:
        raise TrajectoryValidationError(f"{description} is not canonical JSON.")
    return value


def _write_exclusive(path: Path, raw: bytes) -> None:
    if path.is_symlink():
        raise TrajectoryIntegrityError("Trajectory output paths cannot be symlinks.")
    with path.open("xb") as destination:
        destination.write(raw)
        destination.flush()
        os.fsync(destination.fileno())


def _read_bounded(path: Path, limit: int) -> bytes:
    with path.open("rb") as source:
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise TrajectoryValidationError(f"Trajectory member exceeds its size bound: {path.name}.")
    return raw
