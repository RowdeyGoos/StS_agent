"""Executable provisional ``headless_v0`` decision contract.

This module deliberately contains only backend-neutral data, validation,
canonical JSON codecs, and decision hashing.  It contains no game rules,
backend implementation, live-wire normalization, snapshots, RNG state, scalar
reward, or model representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, Sequence, TypeAlias


CONTRACT_VERSION = "headless_v0"
CANONICALIZATION = "headless_v0_sorted_json_v1"
HASH_ALGORITHM = "sha256"
COMPATIBILITY_CLASS = "exact_contract_fingerprint"


class ContractValidationError(ValueError):
    """Raised when a value does not satisfy the frozen contract."""


class DuplicateFieldError(ContractValidationError):
    """Raised when JSON contains the same object field more than once."""


class EvidenceLabel(str, Enum):
    """Evidence labels accepted by the Phase 1 execution plan."""

    LIVE_OBSERVED = "live_observed"
    BRIDGE_FIXTURE = "bridge_fixture"
    COMBAT_V0 = "combat_v0"
    STRUCTURAL_FIXTURE = "structural_fixture"
    DIFFERENTIAL_VERIFIED = "differential_verified"


class DecisionStatus(str, Enum):
    ACTIONABLE = "actionable"
    WAITING = "waiting"
    TERMINAL = "terminal"
    UNSUPPORTED = "unsupported"


class DecisionPhase(str, Enum):
    COMBAT = "combat"
    REWARD = "reward"
    MAP = "map"
    ROOM = "room"
    TERMINAL = "terminal"
    UNSUPPORTED = "unsupported"


ACTION_PHASES: tuple[DecisionPhase, ...] = (
    DecisionPhase.COMBAT,
    DecisionPhase.REWARD,
    DecisionPhase.MAP,
    DecisionPhase.ROOM,
)


class CandidateKind(str, Enum):
    COMBAT_PLAY_CARD = "combat.play_card"
    COMBAT_END_TURN = "combat.end_turn"
    REWARD_CLAIM_GOLD = "reward.claim_gold"
    REWARD_OPEN_CARD_REWARD = "reward.open_card_reward"
    REWARD_CHOOSE_CARD = "reward.choose_card"
    REWARD_SKIP_CARD = "reward.skip_card"
    REWARD_PROCEED = "reward.proceed"
    MAP_CHOOSE_NODE = "map.choose_node"
    ROOM_REST_HEAL = "room.rest_heal"
    ROOM_EVENT_OPTION = "room.event_option"
    ROOM_PROCEED = "room.proceed"


class TransitionResult(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STALE = "stale"


class TransitionReason(str, Enum):
    ACCEPTED = "accepted"
    INVALID_CANDIDATE = "invalid_candidate"
    REJECTED_BY_RULES = "rejected_by_rules"
    UNSUPPORTED = "unsupported"
    STALE_BINDING = "stale_binding"


_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:+/-]{0,127}\Z")
_SLUG_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,127}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

_FORBIDDEN_POLICY_FIELD_COMPONENTS = frozenset(
    {
        "audit",
        "behavior",
        "commit",
        "control",
        "controller",
        "correlation",
        "credential",
        "debug",
        "diagnostic",
        "encoded",
        "future",
        "hidden",
        "idempotency",
        "index",
        "lease",
        "mask",
        "position",
        "privileged",
        "receipt",
        "request",
        "rng",
        "seed",
        "snapshot",
        "slot",
        "tensor",
        "token",
        "trace",
    }
)
_FORBIDDEN_POLICY_FIELD_NAMES = frozenset(
    {
        "action_mask",
        "behavior_state",
        "decision_hash",
        "private_state",
        "privileged_debug_state",
        "shaped_reward",
        "world_state",
    }
)

# Every object key below PublicObservation.data or PublicEvent.data must be a
# member of this semantic allowlist.  IDs are opaque values, never list
# positions.  Adding a key is therefore a contract change, not an adapter
# convenience.
_PUBLIC_POLICY_FIELD_NAMES = frozenset(
    {
        "after",
        "alive",
        "amount",
        "attack_count",
        "attack_damage",
        "available",
        "before",
        "block",
        "block_gain",
        "can_proceed",
        "can_skip",
        "card_definition_id",
        "card_instance_id",
        "card_offers",
        "claimed",
        "cost",
        "current_node_id",
        "delta",
        "discard_count",
        "discard_pile_size",
        "draw_count",
        "draw_pile_size",
        "edges",
        "enabled",
        "enemies",
        "energy",
        "energy_per_turn",
        "entity_id",
        "exhaust_count",
        "exhaust_pile_size",
        "gold",
        "hand",
        "heal_amount",
        "hp",
        "intent",
        "kind",
        "label",
        "map_node_id",
        "max_hp",
        "move_name",
        "name",
        "node_id",
        "node_kind",
        "nodes",
        "offer_id",
        "offers",
        "opened",
        "option_id",
        "options",
        "outcome",
        "player",
        "reason",
        "reason_code",
        "reward_id",
        "reward_kind",
        "rewards",
        "room_kind",
        "shrink",
        "skippable",
        "slimed_added",
        "source_entity_id",
        "source_node_id",
        "status_name",
        "status_stacks",
        "statuses",
        "strength",
        "strength_gain",
        "summary",
        "target_entity_id",
        "target_node_id",
        "terminal",
        "turn",
        "upgraded",
        "value",
        "visited",
        "visited_node_ids",
        "vulnerable",
        "winner",
    }
)

_PUBLIC_OBSERVATION_TOP_LEVEL_FIELDS: Mapping[DecisionPhase, frozenset[str]] = (
    MappingProxyType(
        {
            DecisionPhase.COMBAT: frozenset(
                {
                    "discard_pile_size",
                    "draw_pile_size",
                    "enemies",
                    "exhaust_pile_size",
                    "hand",
                    "outcome",
                    "player",
                    "terminal",
                    "turn",
                }
            ),
            DecisionPhase.REWARD: frozenset(
                {"can_proceed", "can_skip", "card_offers", "gold", "player", "rewards"}
            ),
            DecisionPhase.MAP: frozenset(
                {"current_node_id", "edges", "nodes", "player", "visited_node_ids"}
            ),
            DecisionPhase.ROOM: frozenset(
                {"can_proceed", "options", "player", "room_kind"}
            ),
            DecisionPhase.TERMINAL: frozenset({"outcome", "player", "summary"}),
            DecisionPhase.UNSUPPORTED: frozenset({"reason", "reason_code"}),
        }
    )
)

_CANDIDATE_FIELD_NAMES: Mapping[CandidateKind, tuple[str, ...]] = MappingProxyType(
    {
        CandidateKind.COMBAT_PLAY_CARD: (
            "candidate_id",
            "kind",
            "card_instance_id",
            "target_entity_id",
        ),
        CandidateKind.COMBAT_END_TURN: ("candidate_id", "kind"),
        CandidateKind.REWARD_CLAIM_GOLD: ("candidate_id", "kind", "amount"),
        CandidateKind.REWARD_OPEN_CARD_REWARD: ("candidate_id", "kind", "reward_id"),
        CandidateKind.REWARD_CHOOSE_CARD: (
            "candidate_id",
            "kind",
            "reward_id",
            "offer_id",
            "card_definition_id",
        ),
        CandidateKind.REWARD_SKIP_CARD: ("candidate_id", "kind", "reward_id"),
        CandidateKind.REWARD_PROCEED: ("candidate_id", "kind"),
        CandidateKind.MAP_CHOOSE_NODE: ("candidate_id", "kind", "map_node_id"),
        CandidateKind.ROOM_REST_HEAL: ("candidate_id", "kind", "heal_amount"),
        CandidateKind.ROOM_EVENT_OPTION: ("candidate_id", "kind", "option_id"),
        CandidateKind.ROOM_PROCEED: ("candidate_id", "kind"),
    }
)

_CANDIDATE_PHASE_NAMES: Mapping[CandidateKind, DecisionPhase] = MappingProxyType(
    {
        CandidateKind.COMBAT_PLAY_CARD: DecisionPhase.COMBAT,
        CandidateKind.COMBAT_END_TURN: DecisionPhase.COMBAT,
        CandidateKind.REWARD_CLAIM_GOLD: DecisionPhase.REWARD,
        CandidateKind.REWARD_OPEN_CARD_REWARD: DecisionPhase.REWARD,
        CandidateKind.REWARD_CHOOSE_CARD: DecisionPhase.REWARD,
        CandidateKind.REWARD_SKIP_CARD: DecisionPhase.REWARD,
        CandidateKind.REWARD_PROCEED: DecisionPhase.REWARD,
        CandidateKind.MAP_CHOOSE_NODE: DecisionPhase.MAP,
        CandidateKind.ROOM_REST_HEAL: DecisionPhase.ROOM,
        CandidateKind.ROOM_EVENT_OPTION: DecisionPhase.ROOM,
        CandidateKind.ROOM_PROCEED: DecisionPhase.ROOM,
    }
)


ImmutableJson: TypeAlias = Any


def _validate_identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise ContractValidationError(f"{path} must be a non-empty opaque identifier.")
    return value


def _validate_version(value: Any, path: str) -> str:
    if not isinstance(value, str) or _VERSION_PATTERN.fullmatch(value) is None:
        raise ContractValidationError(f"{path} must be a non-empty version identifier.")
    return value


def _validate_slug(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SLUG_PATTERN.fullmatch(value) is None:
        raise ContractValidationError(f"{path} must be a lower-case semantic slug.")
    return value


def _validate_fingerprint(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ContractValidationError(f"{path} must be a lower-case SHA-256 digest.")
    return value


def _validate_nonnegative_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractValidationError(f"{path} must be a nonnegative integer.")
    return value


def _validate_positive_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ContractValidationError(f"{path} must be a positive integer.")
    return value


def _enum_value(enum_type: type[Enum], value: Any, path: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise ContractValidationError(f"{path} must be a string enum value.")
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(sorted(item.value for item in enum_type))
        raise ContractValidationError(f"{path} must be one of: {allowed}.") from exc


def _normalized_field_components(key: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
    return tuple(component for component in normalized.split("_") if component)


def _validate_policy_field_name(key: str, path: str) -> None:
    components = _normalized_field_components(key)
    normalized = "_".join(components)
    if (
        normalized in _FORBIDDEN_POLICY_FIELD_NAMES
        or any(component in _FORBIDDEN_POLICY_FIELD_COMPONENTS for component in components)
    ):
        raise ContractValidationError(
            f"{path} uses forbidden policy field name {key!r}."
        )
    if normalized not in _PUBLIC_POLICY_FIELD_NAMES:
        raise ContractValidationError(
            f"{path} uses unknown policy field name {key!r}."
        )


def _validate_public_label(value: str, path: str) -> None:
    components = _normalized_field_components(value)
    normalized = "_".join(components)
    if (
        normalized in _FORBIDDEN_POLICY_FIELD_NAMES
        or any(component in _FORBIDDEN_POLICY_FIELD_COMPONENTS for component in components)
    ):
        raise ContractValidationError(f"{path} uses forbidden public semantics {value!r}.")


def _freeze_json(value: Any, path: str, *, policy_view: bool) -> ImmutableJson:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise ContractValidationError(
            f"{path} cannot contain floating-point values; use normalized integers."
        )
    if isinstance(value, Mapping):
        frozen: dict[str, ImmutableJson] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractValidationError(f"{path} object keys must be strings.")
            if policy_view:
                _validate_policy_field_name(key, path)
            frozen[key] = _freeze_json(
                item,
                f"{path}.{key}",
                policy_view=policy_view,
            )
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(
            _freeze_json(item, f"{path}[{index}]", policy_view=policy_view)
            for index, item in enumerate(value)
        )
    raise ContractValidationError(f"{path} contains a non-JSON value {type(value).__name__}.")


def _thaw_json(value: ImmutableJson) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateFieldError(f"Duplicate JSON field: {key!r}.")
        result[key] = value
    return result


def _reject_json_float(value: str) -> None:
    raise ContractValidationError(f"Floating-point JSON value is not allowed: {value!r}.")


def _reject_json_constant(value: str) -> None:
    raise ContractValidationError(f"Non-finite JSON value is not allowed: {value!r}.")


def _loads_object(text: str | bytes | bytearray) -> dict[str, Any]:
    if not isinstance(text, (str, bytes, bytearray)):
        raise ContractValidationError("JSON input must be text or bytes.")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_float=_reject_json_float,
            parse_constant=_reject_json_constant,
        )
    except DuplicateFieldError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("Invalid JSON input.") from exc
    if not isinstance(value, dict):
        raise ContractValidationError("The JSON root must be an object.")
    return value


def _require_exact_fields(
    value: Mapping[str, Any],
    required: set[str] | frozenset[str],
    path: str,
) -> None:
    actual = set(value)
    missing = sorted(required - actual)
    unknown = sorted(actual - required)
    if missing:
        raise ContractValidationError(f"{path} is missing field(s): {', '.join(missing)}.")
    if unknown:
        raise ContractValidationError(f"{path} has unknown field(s): {', '.join(unknown)}.")


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON for a contract JSON value.

    The named v1 procedure sorts every object key, emits no insignificant
    whitespace or ASCII escaping, rejects floating-point/non-finite values, and
    appends no newline or BOM.
    """

    frozen = _freeze_json(value, "$", policy_view=False)
    try:
        encoded = json.dumps(
            _thaw_json(frozen),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("Value cannot be canonically serialized.") from exc
    return encoded.encode("utf-8")


def canonical_json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _domain_hash(domain: str, value: Any) -> str:
    return sha256(domain.encode("ascii") + b"\0" + canonical_json_bytes(value)).hexdigest()


CONTRACT_SCHEMA: Mapping[str, Any] = _freeze_json(
    {
        "canonicalization": CANONICALIZATION,
        "candidate_fields": {
            kind.value: fields for kind, fields in _CANDIDATE_FIELD_NAMES.items()
        },
        "candidate_identity": "opaque_per_decision_id",
        "candidate_kinds": tuple(kind.value for kind in CandidateKind),
        "candidate_phases": {
            kind.value: phase.value for kind, phase in _CANDIDATE_PHASE_NAMES.items()
        },
        "compatibility_class": COMPATIBILITY_CLASS,
        "contract": CONTRACT_VERSION,
        "decision_hash_domain": "headless_v0.decision.v1",
        "decision_phases": tuple(phase.value for phase in DecisionPhase),
        "decision_statuses": tuple(status.value for status in DecisionStatus),
        "evidence_labels": tuple(label.value for label in EvidenceLabel),
        "hash_algorithm": HASH_ALGORITHM,
        "policy_forbidden_field_components": tuple(
            sorted(_FORBIDDEN_POLICY_FIELD_COMPONENTS)
        ),
        "policy_forbidden_field_names": tuple(sorted(_FORBIDDEN_POLICY_FIELD_NAMES)),
        "policy_public_field_allowlist": tuple(sorted(_PUBLIC_POLICY_FIELD_NAMES)),
        "public_observation_schema": "headless_v0.public_observation.v1",
        "policy_top_level_fields": {
            phase.value: tuple(sorted(fields))
            for phase, fields in _PUBLIC_OBSERVATION_TOP_LEVEL_FIELDS.items()
        },
        "records": {
            "action_request": ("binding", "contract", "contract_fingerprint"),
            "backend_capabilities": (
                "counterfactual_stepping",
                "deterministic_reset",
                "fixture_playback",
                "legacy_shaped_reward_diagnostics",
                "live_truth",
                "snapshot_restore",
            ),
            "backend_manifest": (
                "backend_fingerprint",
                "backend_id",
                "backend_version",
                "capabilities",
                "compatibility_class",
                "content_fingerprint",
                "content_version",
                "contract",
                "contract_fingerprint",
                "evidence",
                "rules_fingerprint",
                "rules_version",
                "supported_phases",
                "unsupported_phases",
            ),
            "component_evidence": ("component", "fingerprint", "label", "version"),
            "decision": (
                "backend_fingerprint",
                "backend_id",
                "backend_version",
                "candidates",
                "content_fingerprint",
                "content_version",
                "contract",
                "contract_fingerprint",
                "decision_hash",
                "decision_sequence",
                "observation",
                "phase",
                "public_events",
                "rules_fingerprint",
                "rules_version",
                "run_id",
                "status",
            ),
            "headless_binding": (
                "candidate_id",
                "decision_hash",
                "decision_sequence",
                "run_id",
            ),
            "public_event": ("data", "event_type", "phase", "sequence"),
            "public_observation": ("data", "phase", "schema"),
            "policy_view": (
                "candidates",
                "observation",
                "phase",
                "public_events",
                "status",
            ),
            "transition": (
                "binding",
                "contract",
                "contract_fingerprint",
                "next_decision",
                "public_events",
                "reason",
                "result",
            ),
        },
        "semantic_invariants": (
            "actionable_requires_nonempty_same_phase_candidates",
            "candidate_ids_unique_per_decision",
            "candidate_order_canonical_by_candidate_id",
            "event_sequences_strictly_increase",
            "manifest_action_phases_are_exact_partition",
            "manifest_evidence_components_unique_and_sorted",
            "non_actionable_has_no_candidates",
            "policy_objects_use_recursive_semantic_field_allowlist",
            "public_json_has_no_floating_point_values",
            "rejected_transition_returns_bound_authoritative_identity",
            "stale_transition_returns_different_authoritative_identity",
            "terminal_and_unsupported_status_require_matching_phase",
            "transition_events_equal_next_decision_events",
            "unadvertised_current_candidate_requires_invalid_candidate_reason",
        ),
        "transition_reason_matrix": {
            "accepted": ("accepted",),
            "rejected": ("invalid_candidate", "rejected_by_rules", "unsupported"),
            "stale": ("stale_binding",),
        },
        "transition_reasons": tuple(reason.value for reason in TransitionReason),
        "transition_results": tuple(result.value for result in TransitionResult),
    },
    "contract_schema",
    policy_view=False,
)
CONTRACT_FINGERPRINT = _domain_hash("headless_v0.contract_schema.v1", CONTRACT_SCHEMA)


@dataclass(frozen=True, slots=True)
class ComponentEvidence:
    component: str
    label: EvidenceLabel
    version: str
    fingerprint: str

    def __post_init__(self) -> None:
        _validate_slug(self.component, "component_evidence.component")
        object.__setattr__(
            self,
            "label",
            _enum_value(EvidenceLabel, self.label, "component_evidence.label"),
        )
        _validate_version(self.version, "component_evidence.version")
        _validate_fingerprint(self.fingerprint, "component_evidence.fingerprint")

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "fingerprint": self.fingerprint,
            "label": self.label.value,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ComponentEvidence":
        _require_exact_fields(
            value,
            {"component", "fingerprint", "label", "version"},
            "component_evidence",
        )
        return cls(
            component=value["component"],
            label=_enum_value(EvidenceLabel, value["label"], "component_evidence.label"),
            version=value["version"],
            fingerprint=value["fingerprint"],
        )


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    deterministic_reset: bool
    counterfactual_stepping: bool
    fixture_playback: bool
    snapshot_restore: bool
    live_truth: bool
    legacy_shaped_reward_diagnostics: bool

    def __post_init__(self) -> None:
        for name in (
            "deterministic_reset",
            "counterfactual_stepping",
            "fixture_playback",
            "snapshot_restore",
            "live_truth",
            "legacy_shaped_reward_diagnostics",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ContractValidationError(f"capabilities.{name} must be a boolean.")

    def to_dict(self) -> dict[str, bool]:
        return {
            "counterfactual_stepping": self.counterfactual_stepping,
            "deterministic_reset": self.deterministic_reset,
            "fixture_playback": self.fixture_playback,
            "legacy_shaped_reward_diagnostics": self.legacy_shaped_reward_diagnostics,
            "live_truth": self.live_truth,
            "snapshot_restore": self.snapshot_restore,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BackendCapabilities":
        fields = {
            "counterfactual_stepping",
            "deterministic_reset",
            "fixture_playback",
            "legacy_shaped_reward_diagnostics",
            "live_truth",
            "snapshot_restore",
        }
        _require_exact_fields(value, fields, "capabilities")
        return cls(**{name: value[name] for name in fields})


@dataclass(frozen=True, slots=True)
class BackendManifest:
    backend_id: str
    backend_version: str
    backend_fingerprint: str
    content_version: str
    content_fingerprint: str
    rules_version: str
    rules_fingerprint: str
    capabilities: BackendCapabilities
    supported_phases: tuple[DecisionPhase, ...]
    unsupported_phases: tuple[DecisionPhase, ...]
    evidence: tuple[ComponentEvidence, ...]
    contract: str = CONTRACT_VERSION
    contract_fingerprint: str = CONTRACT_FINGERPRINT
    compatibility_class: str = COMPATIBILITY_CLASS

    def __post_init__(self) -> None:
        if self.contract != CONTRACT_VERSION:
            raise ContractValidationError(f"manifest.contract must equal {CONTRACT_VERSION!r}.")
        if self.contract_fingerprint != CONTRACT_FINGERPRINT:
            raise ContractValidationError("manifest.contract_fingerprint is incompatible.")
        if self.compatibility_class != COMPATIBILITY_CLASS:
            raise ContractValidationError("manifest.compatibility_class is incompatible.")
        _validate_identifier(self.backend_id, "manifest.backend_id")
        _validate_version(self.backend_version, "manifest.backend_version")
        _validate_fingerprint(self.backend_fingerprint, "manifest.backend_fingerprint")
        _validate_version(self.content_version, "manifest.content_version")
        _validate_fingerprint(self.content_fingerprint, "manifest.content_fingerprint")
        _validate_version(self.rules_version, "manifest.rules_version")
        _validate_fingerprint(self.rules_fingerprint, "manifest.rules_fingerprint")
        if not isinstance(self.capabilities, BackendCapabilities):
            raise ContractValidationError("manifest.capabilities has the wrong type.")

        supported = tuple(
            _enum_value(DecisionPhase, phase, "manifest.supported_phases")
            for phase in self.supported_phases
        )
        unsupported = tuple(
            _enum_value(DecisionPhase, phase, "manifest.unsupported_phases")
            for phase in self.unsupported_phases
        )
        object.__setattr__(self, "supported_phases", supported)
        object.__setattr__(self, "unsupported_phases", unsupported)
        if len(set(supported)) != len(supported) or len(set(unsupported)) != len(unsupported):
            raise ContractValidationError("Manifest phase lists cannot contain duplicates.")
        if set(supported) & set(unsupported):
            raise ContractValidationError("Supported and unsupported phases must be disjoint.")
        if set(supported) | set(unsupported) != set(ACTION_PHASES):
            raise ContractValidationError(
                "Manifest phase lists must partition combat, reward, map, and room."
            )
        if tuple(sorted(supported, key=lambda phase: phase.value)) != supported:
            raise ContractValidationError("Supported phases must use canonical value order.")
        if tuple(sorted(unsupported, key=lambda phase: phase.value)) != unsupported:
            raise ContractValidationError("Unsupported phases must use canonical value order.")

        evidence = tuple(self.evidence)
        if not evidence or any(not isinstance(item, ComponentEvidence) for item in evidence):
            raise ContractValidationError("Manifest evidence must contain typed entries.")
        components = [item.component for item in evidence]
        if len(set(components)) != len(components):
            raise ContractValidationError("Manifest evidence components must be unique.")
        if tuple(sorted(components)) != tuple(components):
            raise ContractValidationError("Manifest evidence must be ordered by component.")
        object.__setattr__(self, "evidence", evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_fingerprint": self.backend_fingerprint,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "capabilities": self.capabilities.to_dict(),
            "compatibility_class": self.compatibility_class,
            "content_fingerprint": self.content_fingerprint,
            "content_version": self.content_version,
            "contract": self.contract,
            "contract_fingerprint": self.contract_fingerprint,
            "evidence": [item.to_dict() for item in self.evidence],
            "rules_fingerprint": self.rules_fingerprint,
            "rules_version": self.rules_version,
            "supported_phases": [phase.value for phase in self.supported_phases],
            "unsupported_phases": [phase.value for phase in self.unsupported_phases],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BackendManifest":
        fields = {
            "backend_fingerprint",
            "backend_id",
            "backend_version",
            "capabilities",
            "compatibility_class",
            "content_fingerprint",
            "content_version",
            "contract",
            "contract_fingerprint",
            "evidence",
            "rules_fingerprint",
            "rules_version",
            "supported_phases",
            "unsupported_phases",
        }
        _require_exact_fields(value, fields, "manifest")
        capabilities = value["capabilities"]
        evidence = value["evidence"]
        supported = value["supported_phases"]
        unsupported = value["unsupported_phases"]
        if not isinstance(capabilities, Mapping):
            raise ContractValidationError("manifest.capabilities must be an object.")
        if not isinstance(evidence, list) or not all(
            isinstance(item, Mapping) for item in evidence
        ):
            raise ContractValidationError("manifest.evidence must be an array of objects.")
        if not isinstance(supported, list) or not isinstance(unsupported, list):
            raise ContractValidationError("Manifest phase fields must be arrays.")
        return cls(
            backend_id=value["backend_id"],
            backend_version=value["backend_version"],
            backend_fingerprint=value["backend_fingerprint"],
            content_version=value["content_version"],
            content_fingerprint=value["content_fingerprint"],
            rules_version=value["rules_version"],
            rules_fingerprint=value["rules_fingerprint"],
            capabilities=BackendCapabilities.from_dict(capabilities),
            supported_phases=tuple(
                _enum_value(DecisionPhase, item, "manifest.supported_phases")
                for item in supported
            ),
            unsupported_phases=tuple(
                _enum_value(DecisionPhase, item, "manifest.unsupported_phases")
                for item in unsupported
            ),
            evidence=tuple(ComponentEvidence.from_dict(item) for item in evidence),
            contract=value["contract"],
            contract_fingerprint=value["contract_fingerprint"],
            compatibility_class=value["compatibility_class"],
        )

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, text: str | bytes | bytearray) -> "BackendManifest":
        return cls.from_dict(_loads_object(text))


@dataclass(frozen=True, slots=True)
class PublicObservation:
    phase: DecisionPhase
    data: Mapping[str, Any]
    schema: str = "headless_v0.public_observation.v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "phase",
            _enum_value(DecisionPhase, self.phase, "public_observation.phase"),
        )
        if self.schema != "headless_v0.public_observation.v1":
            raise ContractValidationError("Unsupported public observation schema.")
        if not isinstance(self.data, Mapping):
            raise ContractValidationError("public_observation.data must be an object.")
        allowed_top_level = _PUBLIC_OBSERVATION_TOP_LEVEL_FIELDS[self.phase]
        unknown_top_level = sorted(set(self.data) - allowed_top_level)
        if unknown_top_level:
            raise ContractValidationError(
                "public_observation.data has field(s) outside the phase schema: "
                + ", ".join(unknown_top_level)
                + "."
            )
        object.__setattr__(
            self,
            "data",
            _freeze_json(self.data, "public_observation.data", policy_view=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"data": _thaw_json(self.data), "phase": self.phase.value, "schema": self.schema}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PublicObservation":
        _require_exact_fields(value, {"data", "phase", "schema"}, "public_observation")
        data = value["data"]
        if not isinstance(data, Mapping):
            raise ContractValidationError("public_observation.data must be an object.")
        return cls(phase=value["phase"], data=data, schema=value["schema"])


@dataclass(frozen=True, slots=True)
class PublicEvent:
    sequence: int
    event_type: str
    phase: DecisionPhase
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        _validate_nonnegative_int(self.sequence, "public_event.sequence")
        _validate_slug(self.event_type, "public_event.event_type")
        _validate_public_label(self.event_type, "public_event.event_type")
        object.__setattr__(
            self,
            "phase",
            _enum_value(DecisionPhase, self.phase, "public_event.phase"),
        )
        if not isinstance(self.data, Mapping):
            raise ContractValidationError("public_event.data must be an object.")
        object.__setattr__(
            self,
            "data",
            _freeze_json(self.data, "public_event.data", policy_view=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": _thaw_json(self.data),
            "event_type": self.event_type,
            "phase": self.phase.value,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PublicEvent":
        _require_exact_fields(value, {"data", "event_type", "phase", "sequence"}, "public_event")
        data = value["data"]
        if not isinstance(data, Mapping):
            raise ContractValidationError("public_event.data must be an object.")
        return cls(
            sequence=value["sequence"],
            event_type=value["event_type"],
            phase=value["phase"],
            data=data,
        )


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    KIND: ClassVar[CandidateKind]

    def __post_init__(self) -> None:
        _validate_identifier(self.candidate_id, "candidate.candidate_id")

    @property
    def kind(self) -> CandidateKind:
        return self.KIND


@dataclass(frozen=True, slots=True)
class CombatPlayCardCandidate(Candidate):
    card_instance_id: str
    target_entity_id: str | None = None
    KIND: ClassVar[CandidateKind] = CandidateKind.COMBAT_PLAY_CARD

    def __post_init__(self) -> None:
        super(CombatPlayCardCandidate, self).__post_init__()
        _validate_identifier(self.card_instance_id, "candidate.card_instance_id")
        if self.target_entity_id is not None:
            _validate_identifier(self.target_entity_id, "candidate.target_entity_id")


@dataclass(frozen=True, slots=True)
class CombatEndTurnCandidate(Candidate):
    KIND: ClassVar[CandidateKind] = CandidateKind.COMBAT_END_TURN


@dataclass(frozen=True, slots=True)
class RewardClaimGoldCandidate(Candidate):
    amount: int
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_CLAIM_GOLD

    def __post_init__(self) -> None:
        super(RewardClaimGoldCandidate, self).__post_init__()
        _validate_positive_int(self.amount, "candidate.amount")


@dataclass(frozen=True, slots=True)
class RewardOpenCardRewardCandidate(Candidate):
    reward_id: str
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_OPEN_CARD_REWARD

    def __post_init__(self) -> None:
        super(RewardOpenCardRewardCandidate, self).__post_init__()
        _validate_identifier(self.reward_id, "candidate.reward_id")


@dataclass(frozen=True, slots=True)
class RewardChooseCardCandidate(Candidate):
    reward_id: str
    offer_id: str
    card_definition_id: str
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_CHOOSE_CARD

    def __post_init__(self) -> None:
        super(RewardChooseCardCandidate, self).__post_init__()
        _validate_identifier(self.reward_id, "candidate.reward_id")
        _validate_identifier(self.offer_id, "candidate.offer_id")
        _validate_identifier(self.card_definition_id, "candidate.card_definition_id")


@dataclass(frozen=True, slots=True)
class RewardSkipCardCandidate(Candidate):
    reward_id: str
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_SKIP_CARD

    def __post_init__(self) -> None:
        super(RewardSkipCardCandidate, self).__post_init__()
        _validate_identifier(self.reward_id, "candidate.reward_id")


@dataclass(frozen=True, slots=True)
class RewardProceedCandidate(Candidate):
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_PROCEED


@dataclass(frozen=True, slots=True)
class MapChooseNodeCandidate(Candidate):
    map_node_id: str
    KIND: ClassVar[CandidateKind] = CandidateKind.MAP_CHOOSE_NODE

    def __post_init__(self) -> None:
        super(MapChooseNodeCandidate, self).__post_init__()
        _validate_identifier(self.map_node_id, "candidate.map_node_id")


@dataclass(frozen=True, slots=True)
class RoomRestHealCandidate(Candidate):
    heal_amount: int
    KIND: ClassVar[CandidateKind] = CandidateKind.ROOM_REST_HEAL

    def __post_init__(self) -> None:
        super(RoomRestHealCandidate, self).__post_init__()
        _validate_positive_int(self.heal_amount, "candidate.heal_amount")


@dataclass(frozen=True, slots=True)
class RoomEventOptionCandidate(Candidate):
    option_id: str
    KIND: ClassVar[CandidateKind] = CandidateKind.ROOM_EVENT_OPTION

    def __post_init__(self) -> None:
        super(RoomEventOptionCandidate, self).__post_init__()
        _validate_identifier(self.option_id, "candidate.option_id")


@dataclass(frozen=True, slots=True)
class RoomProceedCandidate(Candidate):
    KIND: ClassVar[CandidateKind] = CandidateKind.ROOM_PROCEED


TypedCandidate: TypeAlias = (
    CombatPlayCardCandidate
    | CombatEndTurnCandidate
    | RewardClaimGoldCandidate
    | RewardOpenCardRewardCandidate
    | RewardChooseCardCandidate
    | RewardSkipCardCandidate
    | RewardProceedCandidate
    | MapChooseNodeCandidate
    | RoomRestHealCandidate
    | RoomEventOptionCandidate
    | RoomProceedCandidate
)

_TYPED_CANDIDATE_TYPES = (
    CombatPlayCardCandidate,
    CombatEndTurnCandidate,
    RewardClaimGoldCandidate,
    RewardOpenCardRewardCandidate,
    RewardChooseCardCandidate,
    RewardSkipCardCandidate,
    RewardProceedCandidate,
    MapChooseNodeCandidate,
    RoomRestHealCandidate,
    RoomEventOptionCandidate,
    RoomProceedCandidate,
)


_CANDIDATE_PHASE = _CANDIDATE_PHASE_NAMES


def candidate_to_dict(candidate: TypedCandidate) -> dict[str, Any]:
    if type(candidate) not in _TYPED_CANDIDATE_TYPES:
        raise ContractValidationError("Unsupported typed candidate instance.")
    result: dict[str, Any] = {
        "candidate_id": candidate.candidate_id,
        "kind": candidate.kind.value,
    }
    if isinstance(candidate, CombatPlayCardCandidate):
        result.update(
            card_instance_id=candidate.card_instance_id,
            target_entity_id=candidate.target_entity_id,
        )
    elif isinstance(candidate, RewardClaimGoldCandidate):
        result["amount"] = candidate.amount
    elif isinstance(candidate, RewardOpenCardRewardCandidate):
        result["reward_id"] = candidate.reward_id
    elif isinstance(candidate, RewardChooseCardCandidate):
        result.update(
            card_definition_id=candidate.card_definition_id,
            offer_id=candidate.offer_id,
            reward_id=candidate.reward_id,
        )
    elif isinstance(candidate, RewardSkipCardCandidate):
        result["reward_id"] = candidate.reward_id
    elif isinstance(candidate, MapChooseNodeCandidate):
        result["map_node_id"] = candidate.map_node_id
    elif isinstance(candidate, RoomRestHealCandidate):
        result["heal_amount"] = candidate.heal_amount
    elif isinstance(candidate, RoomEventOptionCandidate):
        result["option_id"] = candidate.option_id
    elif not isinstance(
        candidate,
        (CombatEndTurnCandidate, RewardProceedCandidate, RoomProceedCandidate),
    ):
        raise ContractValidationError("Unsupported typed candidate instance.")
    return result


_CANDIDATE_FIELDS: Mapping[CandidateKind, frozenset[str]] = MappingProxyType(
    {kind: frozenset(fields) for kind, fields in _CANDIDATE_FIELD_NAMES.items()}
)


def candidate_from_dict(value: Mapping[str, Any]) -> TypedCandidate:
    if not isinstance(value, Mapping):
        raise ContractValidationError("candidate must be an object.")
    if "kind" not in value:
        raise ContractValidationError("candidate is missing field: kind.")
    kind = _enum_value(CandidateKind, value["kind"], "candidate.kind")
    _require_exact_fields(value, _CANDIDATE_FIELDS[kind], "candidate")
    common = {"candidate_id": value["candidate_id"]}
    if kind is CandidateKind.COMBAT_PLAY_CARD:
        target = value["target_entity_id"]
        if target is not None and not isinstance(target, str):
            raise ContractValidationError("candidate.target_entity_id must be a string or null.")
        return CombatPlayCardCandidate(
            **common,
            card_instance_id=value["card_instance_id"],
            target_entity_id=target,
        )
    if kind is CandidateKind.COMBAT_END_TURN:
        return CombatEndTurnCandidate(**common)
    if kind is CandidateKind.REWARD_CLAIM_GOLD:
        return RewardClaimGoldCandidate(**common, amount=value["amount"])
    if kind is CandidateKind.REWARD_OPEN_CARD_REWARD:
        return RewardOpenCardRewardCandidate(**common, reward_id=value["reward_id"])
    if kind is CandidateKind.REWARD_CHOOSE_CARD:
        return RewardChooseCardCandidate(
            **common,
            reward_id=value["reward_id"],
            offer_id=value["offer_id"],
            card_definition_id=value["card_definition_id"],
        )
    if kind is CandidateKind.REWARD_SKIP_CARD:
        return RewardSkipCardCandidate(**common, reward_id=value["reward_id"])
    if kind is CandidateKind.REWARD_PROCEED:
        return RewardProceedCandidate(**common)
    if kind is CandidateKind.MAP_CHOOSE_NODE:
        return MapChooseNodeCandidate(**common, map_node_id=value["map_node_id"])
    if kind is CandidateKind.ROOM_REST_HEAL:
        return RoomRestHealCandidate(**common, heal_amount=value["heal_amount"])
    if kind is CandidateKind.ROOM_EVENT_OPTION:
        return RoomEventOptionCandidate(**common, option_id=value["option_id"])
    if kind is CandidateKind.ROOM_PROCEED:
        return RoomProceedCandidate(**common)
    raise ContractValidationError("Unsupported candidate kind.")


def _validate_event_sequence(events: tuple[PublicEvent, ...], path: str) -> None:
    if any(not isinstance(event, PublicEvent) for event in events):
        raise ContractValidationError(f"{path} must contain PublicEvent values.")
    sequences = tuple(event.sequence for event in events)
    if any(next_value <= value for value, next_value in zip(sequences, sequences[1:])):
        raise ContractValidationError(f"{path} sequences must be strictly increasing.")


@dataclass(frozen=True, slots=True)
class PolicyView:
    """The only decision payload intended for a chooser or future model."""

    status: DecisionStatus
    phase: DecisionPhase
    observation: PublicObservation
    candidates: tuple[TypedCandidate, ...]
    public_events: tuple[PublicEvent, ...]


def _decision_hash_payload(
    *,
    backend_id: str,
    backend_version: str,
    backend_fingerprint: str,
    content_version: str,
    content_fingerprint: str,
    rules_version: str,
    rules_fingerprint: str,
    run_id: str,
    decision_sequence: int,
    status: DecisionStatus,
    phase: DecisionPhase,
    observation: PublicObservation,
    candidates: tuple[TypedCandidate, ...],
    public_events: tuple[PublicEvent, ...],
) -> dict[str, Any]:
    return {
        "backend_fingerprint": backend_fingerprint,
        "backend_id": backend_id,
        "backend_version": backend_version,
        "candidates": [
            candidate_to_dict(candidate)
            for candidate in sorted(candidates, key=lambda item: item.candidate_id)
        ],
        "content_fingerprint": content_fingerprint,
        "content_version": content_version,
        "contract": CONTRACT_VERSION,
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "decision_sequence": decision_sequence,
        "observation": observation.to_dict(),
        "phase": phase.value,
        "public_events": [event.to_dict() for event in public_events],
        "rules_fingerprint": rules_fingerprint,
        "rules_version": rules_version,
        "run_id": run_id,
        "status": status.value,
    }


@dataclass(frozen=True, slots=True)
class DecisionState:
    backend_id: str
    backend_version: str
    backend_fingerprint: str
    content_version: str
    content_fingerprint: str
    rules_version: str
    rules_fingerprint: str
    run_id: str
    decision_sequence: int
    status: DecisionStatus
    phase: DecisionPhase
    observation: PublicObservation
    candidates: tuple[TypedCandidate, ...]
    decision_hash: str
    public_events: tuple[PublicEvent, ...] = field(default_factory=tuple)
    contract: str = CONTRACT_VERSION
    contract_fingerprint: str = CONTRACT_FINGERPRINT

    def __post_init__(self) -> None:
        if self.contract != CONTRACT_VERSION or self.contract_fingerprint != CONTRACT_FINGERPRINT:
            raise ContractValidationError("Decision contract identity is incompatible.")
        _validate_identifier(self.backend_id, "decision.backend_id")
        _validate_version(self.backend_version, "decision.backend_version")
        _validate_fingerprint(self.backend_fingerprint, "decision.backend_fingerprint")
        _validate_version(self.content_version, "decision.content_version")
        _validate_fingerprint(self.content_fingerprint, "decision.content_fingerprint")
        _validate_version(self.rules_version, "decision.rules_version")
        _validate_fingerprint(self.rules_fingerprint, "decision.rules_fingerprint")
        _validate_identifier(self.run_id, "decision.run_id")
        _validate_nonnegative_int(self.decision_sequence, "decision.decision_sequence")
        object.__setattr__(
            self,
            "status",
            _enum_value(DecisionStatus, self.status, "decision.status"),
        )
        object.__setattr__(
            self,
            "phase",
            _enum_value(DecisionPhase, self.phase, "decision.phase"),
        )
        if not isinstance(self.observation, PublicObservation):
            raise ContractValidationError("decision.observation has the wrong type.")
        if self.observation.phase is not self.phase:
            raise ContractValidationError("Decision and observation phases must match.")

        candidates = tuple(self.candidates)
        if any(type(candidate) not in _TYPED_CANDIDATE_TYPES for candidate in candidates):
            raise ContractValidationError("decision.candidates must contain typed candidates.")
        candidate_ids = [candidate.candidate_id for candidate in candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ContractValidationError("Decision candidate IDs must be unique.")
        if self.status is DecisionStatus.ACTIONABLE:
            if not candidates:
                raise ContractValidationError("An actionable decision requires candidates.")
            if self.phase not in ACTION_PHASES:
                raise ContractValidationError("An actionable decision requires an action phase.")
            if any(_CANDIDATE_PHASE[candidate.kind] is not self.phase for candidate in candidates):
                raise ContractValidationError("Candidate kind does not match the decision phase.")
        elif candidates:
            raise ContractValidationError("A non-actionable decision cannot contain candidates.")
        if (self.status is DecisionStatus.TERMINAL) != (
            self.phase is DecisionPhase.TERMINAL
        ):
            raise ContractValidationError("Terminal status and phase must match.")
        if (self.status is DecisionStatus.UNSUPPORTED) != (
            self.phase is DecisionPhase.UNSUPPORTED
        ):
            raise ContractValidationError("Unsupported status and phase must match.")
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(candidates, key=lambda candidate: candidate.candidate_id)),
        )

        events = tuple(self.public_events)
        _validate_event_sequence(events, "decision.public_events")
        object.__setattr__(self, "public_events", events)

        _validate_fingerprint(self.decision_hash, "decision.decision_hash")
        expected_hash = self.compute_hash()
        if self.decision_hash != expected_hash:
            raise ContractValidationError("Decision hash does not match canonical decision data.")

    @classmethod
    def create(
        cls,
        *,
        backend_id: str,
        backend_version: str,
        backend_fingerprint: str,
        content_version: str,
        content_fingerprint: str,
        rules_version: str,
        rules_fingerprint: str,
        run_id: str,
        decision_sequence: int,
        status: DecisionStatus,
        phase: DecisionPhase,
        observation: PublicObservation,
        candidates: Sequence[TypedCandidate] = (),
        public_events: Sequence[PublicEvent] = (),
    ) -> "DecisionState":
        normalized_status = _enum_value(DecisionStatus, status, "decision.status")
        normalized_phase = _enum_value(DecisionPhase, phase, "decision.phase")
        if not isinstance(observation, PublicObservation):
            raise ContractValidationError("decision.observation has the wrong type.")
        normalized_candidates = tuple(candidates)
        normalized_events = tuple(public_events)
        if any(
            type(candidate) not in _TYPED_CANDIDATE_TYPES
            for candidate in normalized_candidates
        ):
            raise ContractValidationError("decision.candidates must contain typed candidates.")
        if any(not isinstance(event, PublicEvent) for event in normalized_events):
            raise ContractValidationError("decision.public_events must contain PublicEvent values.")
        payload = _decision_hash_payload(
            backend_id=backend_id,
            backend_version=backend_version,
            backend_fingerprint=backend_fingerprint,
            content_version=content_version,
            content_fingerprint=content_fingerprint,
            rules_version=rules_version,
            rules_fingerprint=rules_fingerprint,
            run_id=run_id,
            decision_sequence=decision_sequence,
            status=normalized_status,
            phase=normalized_phase,
            observation=observation,
            candidates=normalized_candidates,
            public_events=normalized_events,
        )
        decision_hash = _domain_hash("headless_v0.decision.v1", payload)
        return cls(
            backend_id=backend_id,
            backend_version=backend_version,
            backend_fingerprint=backend_fingerprint,
            content_version=content_version,
            content_fingerprint=content_fingerprint,
            rules_version=rules_version,
            rules_fingerprint=rules_fingerprint,
            run_id=run_id,
            decision_sequence=decision_sequence,
            status=normalized_status,
            phase=normalized_phase,
            observation=observation,
            candidates=normalized_candidates,
            decision_hash=decision_hash,
            public_events=normalized_events,
        )

    def compute_hash(self) -> str:
        payload = _decision_hash_payload(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            backend_fingerprint=self.backend_fingerprint,
            content_version=self.content_version,
            content_fingerprint=self.content_fingerprint,
            rules_version=self.rules_version,
            rules_fingerprint=self.rules_fingerprint,
            run_id=self.run_id,
            decision_sequence=self.decision_sequence,
            status=self.status,
            phase=self.phase,
            observation=self.observation,
            candidates=self.candidates,
            public_events=self.public_events,
        )
        return _domain_hash("headless_v0.decision.v1", payload)

    def policy_view(self) -> PolicyView:
        return PolicyView(
            status=self.status,
            phase=self.phase,
            observation=self.observation,
            candidates=self.candidates,
            public_events=self.public_events,
        )

    def to_dict(self) -> dict[str, Any]:
        result = _decision_hash_payload(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            backend_fingerprint=self.backend_fingerprint,
            content_version=self.content_version,
            content_fingerprint=self.content_fingerprint,
            rules_version=self.rules_version,
            rules_fingerprint=self.rules_fingerprint,
            run_id=self.run_id,
            decision_sequence=self.decision_sequence,
            status=self.status,
            phase=self.phase,
            observation=self.observation,
            candidates=self.candidates,
            public_events=self.public_events,
        )
        result["decision_hash"] = self.decision_hash
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DecisionState":
        fields = {
            "backend_fingerprint",
            "backend_id",
            "backend_version",
            "candidates",
            "content_fingerprint",
            "content_version",
            "contract",
            "contract_fingerprint",
            "decision_hash",
            "decision_sequence",
            "observation",
            "phase",
            "public_events",
            "rules_fingerprint",
            "rules_version",
            "run_id",
            "status",
        }
        _require_exact_fields(value, fields, "decision")
        observation = value["observation"]
        candidates = value["candidates"]
        events = value["public_events"]
        if not isinstance(observation, Mapping):
            raise ContractValidationError("decision.observation must be an object.")
        if not isinstance(candidates, list) or not all(
            isinstance(item, Mapping) for item in candidates
        ):
            raise ContractValidationError("decision.candidates must be an array of objects.")
        if not isinstance(events, list) or not all(isinstance(item, Mapping) for item in events):
            raise ContractValidationError("decision.public_events must be an array of objects.")
        return cls(
            backend_id=value["backend_id"],
            backend_version=value["backend_version"],
            backend_fingerprint=value["backend_fingerprint"],
            content_version=value["content_version"],
            content_fingerprint=value["content_fingerprint"],
            rules_version=value["rules_version"],
            rules_fingerprint=value["rules_fingerprint"],
            run_id=value["run_id"],
            decision_sequence=value["decision_sequence"],
            status=value["status"],
            phase=value["phase"],
            observation=PublicObservation.from_dict(observation),
            candidates=tuple(candidate_from_dict(item) for item in candidates),
            decision_hash=value["decision_hash"],
            public_events=tuple(PublicEvent.from_dict(item) for item in events),
            contract=value["contract"],
            contract_fingerprint=value["contract_fingerprint"],
        )

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, text: str | bytes | bytearray) -> "DecisionState":
        return cls.from_dict(_loads_object(text))


@dataclass(frozen=True, slots=True)
class HeadlessBinding:
    run_id: str
    decision_sequence: int
    decision_hash: str
    candidate_id: str

    def __post_init__(self) -> None:
        _validate_identifier(self.run_id, "binding.run_id")
        _validate_nonnegative_int(self.decision_sequence, "binding.decision_sequence")
        _validate_fingerprint(self.decision_hash, "binding.decision_hash")
        _validate_identifier(self.candidate_id, "binding.candidate_id")

    @classmethod
    def for_candidate(cls, decision: DecisionState, candidate_id: str) -> "HeadlessBinding":
        if decision.status is not DecisionStatus.ACTIONABLE:
            raise ContractValidationError("Cannot bind an action to a non-actionable decision.")
        if candidate_id not in {candidate.candidate_id for candidate in decision.candidates}:
            raise ContractValidationError("Candidate ID is not advertised by the decision.")
        return cls(
            run_id=decision.run_id,
            decision_sequence=decision.decision_sequence,
            decision_hash=decision.decision_hash,
            candidate_id=candidate_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision_hash": self.decision_hash,
            "decision_sequence": self.decision_sequence,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HeadlessBinding":
        _require_exact_fields(
            value,
            {"candidate_id", "decision_hash", "decision_sequence", "run_id"},
            "binding",
        )
        return cls(
            run_id=value["run_id"],
            decision_sequence=value["decision_sequence"],
            decision_hash=value["decision_hash"],
            candidate_id=value["candidate_id"],
        )


@dataclass(frozen=True, slots=True)
class ActionRequest:
    binding: HeadlessBinding
    contract: str = CONTRACT_VERSION
    contract_fingerprint: str = CONTRACT_FINGERPRINT

    def __post_init__(self) -> None:
        if self.contract != CONTRACT_VERSION or self.contract_fingerprint != CONTRACT_FINGERPRINT:
            raise ContractValidationError("Action request contract identity is incompatible.")
        if not isinstance(self.binding, HeadlessBinding):
            raise ContractValidationError("action_request.binding has the wrong type.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding": self.binding.to_dict(),
            "contract": self.contract,
            "contract_fingerprint": self.contract_fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ActionRequest":
        _require_exact_fields(
            value,
            {"binding", "contract", "contract_fingerprint"},
            "action_request",
        )
        binding = value["binding"]
        if not isinstance(binding, Mapping):
            raise ContractValidationError("action_request.binding must be an object.")
        return cls(
            binding=HeadlessBinding.from_dict(binding),
            contract=value["contract"],
            contract_fingerprint=value["contract_fingerprint"],
        )

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, text: str | bytes | bytearray) -> "ActionRequest":
        return cls.from_dict(_loads_object(text))


@dataclass(frozen=True, slots=True)
class Transition:
    result: TransitionResult
    reason: TransitionReason
    binding: HeadlessBinding
    public_events: tuple[PublicEvent, ...]
    next_decision: DecisionState
    contract: str = CONTRACT_VERSION
    contract_fingerprint: str = CONTRACT_FINGERPRINT

    def __post_init__(self) -> None:
        if self.contract != CONTRACT_VERSION or self.contract_fingerprint != CONTRACT_FINGERPRINT:
            raise ContractValidationError("Transition contract identity is incompatible.")
        object.__setattr__(
            self,
            "result",
            _enum_value(TransitionResult, self.result, "transition.result"),
        )
        object.__setattr__(
            self,
            "reason",
            _enum_value(TransitionReason, self.reason, "transition.reason"),
        )
        if not isinstance(self.binding, HeadlessBinding):
            raise ContractValidationError("transition.binding has the wrong type.")
        if not isinstance(self.next_decision, DecisionState):
            raise ContractValidationError("transition.next_decision has the wrong type.")
        events = tuple(self.public_events)
        _validate_event_sequence(events, "transition.public_events")
        object.__setattr__(self, "public_events", events)
        allowed_reasons = {
            TransitionResult.ACCEPTED: {TransitionReason.ACCEPTED},
            TransitionResult.STALE: {TransitionReason.STALE_BINDING},
            TransitionResult.REJECTED: {
                TransitionReason.INVALID_CANDIDATE,
                TransitionReason.REJECTED_BY_RULES,
                TransitionReason.UNSUPPORTED,
            },
        }
        if self.reason not in allowed_reasons[self.result]:
            raise ContractValidationError("Transition result/reason combination is invalid.")
        if self.result is TransitionResult.ACCEPTED:
            if self.next_decision.run_id != self.binding.run_id:
                raise ContractValidationError("Accepted transition cannot change run identity.")
            if self.next_decision.decision_sequence <= self.binding.decision_sequence:
                raise ContractValidationError("Accepted transition must advance decision sequence.")
        elif self.result is TransitionResult.REJECTED:
            if (
                self.next_decision.run_id != self.binding.run_id
                or self.next_decision.decision_sequence != self.binding.decision_sequence
                or self.next_decision.decision_hash != self.binding.decision_hash
            ):
                raise ContractValidationError(
                    "Rejected transition must return the bound authoritative identity."
                )
            candidate_is_advertised = self.binding.candidate_id in {
                candidate.candidate_id for candidate in self.next_decision.candidates
            }
            candidate_is_invalid = self.reason is TransitionReason.INVALID_CANDIDATE
            if candidate_is_advertised == candidate_is_invalid:
                raise ContractValidationError(
                    "An unadvertised current candidate requires invalid_candidate; "
                    "an advertised candidate cannot use that reason."
                )
        elif (
            self.next_decision.run_id == self.binding.run_id
            and self.next_decision.decision_sequence == self.binding.decision_sequence
            and self.next_decision.decision_hash == self.binding.decision_hash
        ):
            raise ContractValidationError(
                "Stale transition must return an authoritative identity that differs "
                "from the attempted binding."
            )
        if events != self.next_decision.public_events:
            raise ContractValidationError(
                "Transition events must equal the next decision's public events."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding": self.binding.to_dict(),
            "contract": self.contract,
            "contract_fingerprint": self.contract_fingerprint,
            "next_decision": self.next_decision.to_dict(),
            "public_events": [event.to_dict() for event in self.public_events],
            "reason": self.reason.value,
            "result": self.result.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Transition":
        fields = {
            "binding",
            "contract",
            "contract_fingerprint",
            "next_decision",
            "public_events",
            "reason",
            "result",
        }
        _require_exact_fields(value, fields, "transition")
        binding = value["binding"]
        next_decision = value["next_decision"]
        events = value["public_events"]
        if not isinstance(binding, Mapping) or not isinstance(next_decision, Mapping):
            raise ContractValidationError("Transition binding and next_decision must be objects.")
        if not isinstance(events, list) or not all(isinstance(item, Mapping) for item in events):
            raise ContractValidationError("transition.public_events must be an array of objects.")
        return cls(
            result=value["result"],
            reason=value["reason"],
            binding=HeadlessBinding.from_dict(binding),
            public_events=tuple(PublicEvent.from_dict(item) for item in events),
            next_decision=DecisionState.from_dict(next_decision),
            contract=value["contract"],
            contract_fingerprint=value["contract_fingerprint"],
        )

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, text: str | bytes | bytearray) -> "Transition":
        return cls.from_dict(_loads_object(text))
