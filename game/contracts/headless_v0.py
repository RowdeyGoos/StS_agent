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


class CombatOutcome(str, Enum):
    ONGOING = "ongoing"
    VICTORY = "victory"
    DEFEAT = "defeat"


class RunOutcome(str, Enum):
    VICTORY = "victory"
    DEFEAT = "defeat"
    ABANDONED = "abandoned"


class IntentKind(str, Enum):
    ATTACK = "attack"
    DEFEND = "defend"
    ATTACK_DEFEND = "attack_defend"
    BUFF = "buff"
    DEBUFF = "debuff"
    SHUFFLE = "shuffle"


class StatusKind(str, Enum):
    NONE = "none"
    VULNERABLE = "vulnerable"
    SHRINK = "shrink"


class RewardKind(str, Enum):
    GOLD = "gold"
    CARD = "card"


class NodeKind(str, Enum):
    COMBAT = "combat"
    REST = "rest"
    EVENT = "event"
    TERMINAL = "terminal"


class RoomKind(str, Enum):
    REST = "rest"
    EVENT = "event"


class RoomOptionKind(str, Enum):
    REST_HEAL = "rest_heal"
    EVENT_OPTION = "event_option"


class RoomEffectKind(str, Enum):
    NONE = "none"
    HEAL = "heal"
    GAIN_GOLD = "gain_gold"
    LOSE_HP = "lose_hp"


class UnsupportedReasonCode(str, Enum):
    UNSUPPORTED_PHASE = "unsupported_phase"
    UNSUPPORTED_CONTENT = "unsupported_content"
    UNSUPPORTED_RULE = "unsupported_rule"
    BACKEND_UNAVAILABLE = "backend_unavailable"


class PublicReferenceKind(str, Enum):
    CARD = "card"
    ENEMY = "enemy"
    REWARD = "reward"
    OFFER = "offer"
    NODE = "node"
    OPTION = "option"


class PublicEventKind(str, Enum):
    COMBAT_CARD_PLAYED = "combat.card_played"
    COMBAT_TURN_ENDED = "combat.turn_ended"
    COMBAT_RESOLVED = "combat.resolved"
    REWARD_GOLD_CLAIMED = "reward.gold_claimed"
    REWARD_CARD_OPENED = "reward.card_opened"
    REWARD_CARD_CHOSEN = "reward.card_chosen"
    REWARD_CARD_SKIPPED = "reward.card_skipped"
    REWARD_PROCEEDED = "reward.proceeded"
    MAP_NODE_CHOSEN = "map.node_chosen"
    ROOM_REST_HEALED = "room.rest_healed"
    ROOM_EVENT_OPTION_CHOSEN = "room.event_option_chosen"
    ROOM_PROCEEDED = "room.proceeded"
    RUN_TERMINATED = "run.terminated"


_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:+/-]{0,127}\Z")
_SLUG_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,127}\Z")
_SEMANTIC_ID_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_PUBLIC_REFERENCE_PATTERN = re.compile(
    r"pub\.(card|enemy|reward|offer|node|option)\.[0-9a-f]{64}\Z"
)
_CANDIDATE_ID_PATTERN = re.compile(r"cand\.[0-9a-f]{64}\Z")
_HISTORY_SCOPE_PATTERN = re.compile(r"scope\.history\.[0-9a-f]{64}\Z")
_DECISION_SCOPE_PATTERN = re.compile(r"scope\.decision\.[0-9a-f]{64}\Z")

MAX_COLLECTION_SIZE = 128
MAX_PUBLIC_COUNTER = 1_000_000_000
MAX_PUBLIC_HP = 100_000

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
        "trajectory",
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

_OBSERVATION_SCHEMAS: Mapping[DecisionPhase, Mapping[str, tuple[str, ...]]] = (
    MappingProxyType(
        {
            DecisionPhase.COMBAT: {
                "top": (
                    "discard_pile_size",
                    "draw_pile_size",
                    "enemies",
                    "exhaust_pile_size",
                    "hand",
                    "outcome",
                    "player",
                    "terminal",
                    "turn",
                ),
                "player": (
                    "block",
                    "energy",
                    "energy_per_turn",
                    "hp",
                    "max_hp",
                    "statuses",
                    "strength",
                ),
                "statuses": ("shrink", "vulnerable"),
                "enemy": (
                    "alive",
                    "block",
                    "enemy_definition_id",
                    "enemy_ref",
                    "hp",
                    "intent",
                    "max_hp",
                    "statuses",
                    "strength",
                ),
                "intent": (
                    "attack_count",
                    "attack_damage",
                    "block_gain",
                    "kind",
                    "slimed_added",
                    "status_kind",
                    "status_stacks",
                    "strength_gain",
                ),
                "card": ("card_definition_id", "card_ref", "cost", "upgraded"),
            },
            DecisionPhase.REWARD: {
                "top": ("can_proceed", "player", "rewards"),
                "player": ("deck_size", "gold", "hp", "max_hp"),
                "reward": (
                    "amount",
                    "can_skip",
                    "claimed",
                    "kind",
                    "offers",
                    "opened",
                    "reward_ref",
                ),
                "offer": ("card_definition_id", "offer_ref", "upgraded"),
            },
            DecisionPhase.MAP: {
                "top": (
                    "current_node_ref",
                    "edges",
                    "nodes",
                    "player",
                    "visited_node_refs",
                ),
                "player": ("deck_size", "gold", "hp", "max_hp"),
                "node": ("available", "kind", "node_ref", "visited"),
                "edge": ("source_node_ref", "target_node_ref"),
            },
            DecisionPhase.ROOM: {
                "top": ("can_proceed", "options", "player", "room_kind"),
                "player": ("deck_size", "gold", "hp", "max_hp"),
                "option": ("amount", "effect", "enabled", "kind", "option_ref"),
            },
            DecisionPhase.TERMINAL: {
                "top": ("outcome", "player"),
                "player": ("deck_size", "gold", "hp", "max_hp"),
            },
            DecisionPhase.UNSUPPORTED: {"top": ("reason_code",)},
        }
    )
)

_CANDIDATE_FIELD_NAMES: Mapping[CandidateKind, tuple[str, ...]] = MappingProxyType(
    {
        CandidateKind.COMBAT_PLAY_CARD: (
            "candidate_id",
            "decision_scope",
            "kind",
            "card_ref",
            "target_ref",
        ),
        CandidateKind.COMBAT_END_TURN: ("candidate_id", "decision_scope", "kind"),
        CandidateKind.REWARD_CLAIM_GOLD: (
            "candidate_id",
            "decision_scope",
            "kind",
            "amount",
            "reward_ref",
        ),
        CandidateKind.REWARD_OPEN_CARD_REWARD: (
            "candidate_id",
            "decision_scope",
            "kind",
            "reward_ref",
        ),
        CandidateKind.REWARD_CHOOSE_CARD: (
            "candidate_id",
            "decision_scope",
            "kind",
            "card_definition_id",
            "offer_ref",
            "reward_ref",
        ),
        CandidateKind.REWARD_SKIP_CARD: (
            "candidate_id",
            "decision_scope",
            "kind",
            "reward_ref",
        ),
        CandidateKind.REWARD_PROCEED: ("candidate_id", "decision_scope", "kind"),
        CandidateKind.MAP_CHOOSE_NODE: (
            "candidate_id",
            "decision_scope",
            "kind",
            "node_ref",
        ),
        CandidateKind.ROOM_REST_HEAL: (
            "candidate_id",
            "decision_scope",
            "kind",
            "heal_amount",
            "option_ref",
        ),
        CandidateKind.ROOM_EVENT_OPTION: (
            "candidate_id",
            "decision_scope",
            "kind",
            "option_ref",
        ),
        CandidateKind.ROOM_PROCEED: ("candidate_id", "decision_scope", "kind"),
    }
)

_PUBLIC_EVENT_SPECS: Mapping[PublicEventKind, tuple[DecisionPhase, tuple[str, ...]]] = (
    MappingProxyType(
        {
            PublicEventKind.COMBAT_CARD_PLAYED: (
                DecisionPhase.COMBAT,
                ("card_definition_id", "target_enemy_definition_id"),
            ),
            PublicEventKind.COMBAT_TURN_ENDED: (DecisionPhase.COMBAT, ()),
            PublicEventKind.COMBAT_RESOLVED: (DecisionPhase.COMBAT, ("outcome",)),
            PublicEventKind.REWARD_GOLD_CLAIMED: (
                DecisionPhase.REWARD,
                ("amount",),
            ),
            PublicEventKind.REWARD_CARD_OPENED: (
                DecisionPhase.REWARD,
                ("offer_count",),
            ),
            PublicEventKind.REWARD_CARD_CHOSEN: (
                DecisionPhase.REWARD,
                ("card_definition_id", "upgraded"),
            ),
            PublicEventKind.REWARD_CARD_SKIPPED: (DecisionPhase.REWARD, ()),
            PublicEventKind.REWARD_PROCEEDED: (DecisionPhase.REWARD, ()),
            PublicEventKind.MAP_NODE_CHOSEN: (DecisionPhase.MAP, ("node_kind",)),
            PublicEventKind.ROOM_REST_HEALED: (
                DecisionPhase.ROOM,
                ("amount",),
            ),
            PublicEventKind.ROOM_EVENT_OPTION_CHOSEN: (
                DecisionPhase.ROOM,
                ("amount", "effect"),
            ),
            PublicEventKind.ROOM_PROCEEDED: (DecisionPhase.ROOM, ()),
            PublicEventKind.RUN_TERMINATED: (DecisionPhase.TERMINAL, ("outcome",)),
        }
    )
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


def _validate_unicode_text(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(f"{path} must be a string.")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ContractValidationError(f"{path} cannot contain an unpaired surrogate.")
    return value


def _validate_identifier(value: Any, path: str) -> str:
    if _ID_PATTERN.fullmatch(_validate_unicode_text(value, path)) is None:
        raise ContractValidationError(f"{path} must be a non-empty opaque identifier.")
    return value


def _validate_version(value: Any, path: str) -> str:
    if _VERSION_PATTERN.fullmatch(_validate_unicode_text(value, path)) is None:
        raise ContractValidationError(f"{path} must be a non-empty version identifier.")
    return value


def _validate_slug(value: Any, path: str) -> str:
    if _SLUG_PATTERN.fullmatch(_validate_unicode_text(value, path)) is None:
        raise ContractValidationError(f"{path} must be a lower-case semantic slug.")
    return value


def _validate_fingerprint(value: Any, path: str) -> str:
    if _SHA256_PATTERN.fullmatch(_validate_unicode_text(value, path)) is None:
        raise ContractValidationError(f"{path} must be a lower-case SHA-256 digest.")
    return value


def _validate_nonnegative_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractValidationError(f"{path} must be a nonnegative integer.")
    return value


def _validate_bounded_int(value: Any, path: str, minimum: int, maximum: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
        or value > maximum
    ):
        raise ContractValidationError(
            f"{path} must be an integer from {minimum} through {maximum}."
        )
    return value


def _validate_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ContractValidationError(f"{path} must be a boolean.")
    return value


def _validate_semantic_id(value: Any, path: str) -> str:
    text = _validate_unicode_text(value, path)
    if _SEMANTIC_ID_PATTERN.fullmatch(text) is None:
        raise ContractValidationError(f"{path} must be a canonical semantic identifier.")
    return text


def _enum_value(enum_type: type[Enum], value: Any, path: str) -> Any:
    if isinstance(value, enum_type):
        return value
    _validate_unicode_text(value, path)
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(sorted(item.value for item in enum_type))
        raise ContractValidationError(f"{path} must be one of: {allowed}.") from exc


def _normalized_field_components(key: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
    return tuple(component for component in normalized.split("_") if component)


def _validate_policy_field_name(key: str, path: str) -> None:
    _validate_unicode_text(key, path)
    components = _normalized_field_components(key)
    normalized = "_".join(components)
    if (
        normalized in _FORBIDDEN_POLICY_FIELD_NAMES
        or any(component in _FORBIDDEN_POLICY_FIELD_COMPONENTS for component in components)
    ):
        raise ContractValidationError(
            f"{path} uses forbidden policy field name {key!r}."
        )


def _freeze_json(value: Any, path: str, *, policy_view: bool) -> ImmutableJson:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _validate_unicode_text(value, path)
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
            _validate_unicode_text(key, f"{path} object key")
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
    return _thaw_json(_freeze_json(value, "$", policy_view=False))


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
        return encoded.encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ContractValidationError("Value cannot be canonically serialized.") from exc


def canonical_json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _domain_hash(domain: str, value: Any) -> str:
    return sha256(domain.encode("ascii") + b"\0" + canonical_json_bytes(value)).hexdigest()


def public_history_scope(history_ordinal: int) -> str:
    ordinal = _validate_bounded_int(
        history_ordinal,
        "history_ordinal",
        0,
        MAX_PUBLIC_COUNTER,
    )
    digest = _domain_hash(
        "headless_v0.public_history_scope.v1",
        {"history_ordinal": ordinal},
    )
    return f"scope.history.{digest}"


def public_decision_scope(history_scope: str, decision_ordinal: int) -> str:
    history = _validate_unicode_text(history_scope, "history_scope")
    if _HISTORY_SCOPE_PATTERN.fullmatch(history) is None:
        raise ContractValidationError("history_scope must be canonically derived.")
    ordinal = _validate_bounded_int(
        decision_ordinal,
        "decision_ordinal",
        0,
        MAX_PUBLIC_COUNTER,
    )
    digest = _domain_hash(
        "headless_v0.public_decision_scope.v1",
        {"decision_ordinal": ordinal, "history_scope": history},
    )
    return f"scope.decision.{digest}"


@dataclass(frozen=True, slots=True)
class PublicScope:
    """Policy-visible allocation state for decision and reveal lifetimes.

    The ordinals describe public history only. They are not engine sequence
    numbers, run IDs, RNG counters, storage handles, or other private state.
    """

    history_ordinal: int
    decision_ordinal: int
    reveal_ordinals: Mapping[str, int]

    def __post_init__(self) -> None:
        _validate_bounded_int(
            self.history_ordinal,
            "public_scope.history_ordinal",
            0,
            MAX_PUBLIC_COUNTER,
        )
        _validate_bounded_int(
            self.decision_ordinal,
            "public_scope.decision_ordinal",
            0,
            MAX_PUBLIC_COUNTER,
        )
        if not isinstance(self.reveal_ordinals, Mapping):
            raise ContractValidationError("public_scope.reveal_ordinals must be an object.")
        normalized: dict[str, int] = {}
        for raw_kind, value in self.reveal_ordinals.items():
            kind = _enum_value(
                PublicReferenceKind,
                raw_kind,
                "public_scope.reveal_ordinals key",
            )
            if kind.value in normalized:
                raise ContractValidationError("Public reveal kinds must be unique.")
            normalized[kind.value] = _validate_bounded_int(
                value,
                f"public_scope.reveal_ordinals.{kind.value}",
                0,
                MAX_PUBLIC_COUNTER,
            )
        expected = {kind.value for kind in PublicReferenceKind}
        _require_exact_fields(
            normalized,
            frozenset(expected),
            "public_scope.reveal_ordinals",
        )
        object.__setattr__(self, "reveal_ordinals", MappingProxyType(normalized))

    @property
    def history_scope(self) -> str:
        return public_history_scope(self.history_ordinal)

    @property
    def decision_scope(self) -> str:
        return public_decision_scope(self.history_scope, self.decision_ordinal)

    def reveal_ordinal(self, kind: PublicReferenceKind) -> int:
        return self.reveal_ordinals[kind.value]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_ordinal": self.decision_ordinal,
            "history_ordinal": self.history_ordinal,
            "reveal_ordinals": dict(self.reveal_ordinals),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PublicScope":
        _require_exact_fields(
            value,
            {"decision_ordinal", "history_ordinal", "reveal_ordinals"},
            "public_scope",
        )
        reveals = value["reveal_ordinals"]
        if not isinstance(reveals, Mapping):
            raise ContractValidationError("public_scope.reveal_ordinals must be an object.")
        return cls(
            history_ordinal=value["history_ordinal"],
            decision_ordinal=value["decision_ordinal"],
            reveal_ordinals=reveals,
        )


def _require_object(
    value: Any,
    path: str,
    fields: Sequence[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{path} must be an object.")
    _require_exact_fields(value, frozenset(fields), path)
    return value


def _require_array(
    value: Any,
    path: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_COLLECTION_SIZE,
) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ContractValidationError(f"{path} must be an array.")
    result = tuple(value)
    if not minimum <= len(result) <= maximum:
        raise ContractValidationError(
            f"{path} must contain from {minimum} through {maximum} items."
        )
    return result


def _reference_value(kind: PublicReferenceKind, basis: Mapping[str, Any]) -> str:
    digest = _domain_hash(f"headless_v0.public_ref.{kind.value}.v1", basis)
    return f"pub.{kind.value}.{digest}"


def _reference_scope_basis(scope: PublicScope, kind: PublicReferenceKind) -> dict[str, Any]:
    if not isinstance(scope, PublicScope):
        raise ContractValidationError("Reference scope must be a PublicScope.")
    return {
        "history_scope": scope.history_scope,
        "reveal_ordinal": scope.reveal_ordinal(kind),
    }


def combat_card_reference(
    scope: PublicScope,
    card_definition_id: str,
    presentation_ordinal: int,
) -> str:
    """Derive a reveal-scoped card alias from explicit public presentation data."""

    definition = _validate_semantic_id(card_definition_id, "card_definition_id")
    ordinal = _validate_bounded_int(
        presentation_ordinal,
        "presentation_ordinal",
        0,
        MAX_COLLECTION_SIZE - 1,
    )
    basis = _reference_scope_basis(scope, PublicReferenceKind.CARD)
    basis.update(card_definition_id=definition, presentation_ordinal=ordinal)
    return _reference_value(
        PublicReferenceKind.CARD,
        basis,
    )


def combat_enemy_reference(
    scope: PublicScope,
    enemy_definition_id: str,
    presentation_ordinal: int,
) -> str:
    """Derive an encounter-reveal alias without accepting an internal ID."""

    definition = _validate_semantic_id(enemy_definition_id, "enemy_definition_id")
    ordinal = _validate_bounded_int(
        presentation_ordinal,
        "presentation_ordinal",
        0,
        MAX_COLLECTION_SIZE - 1,
    )
    basis = _reference_scope_basis(scope, PublicReferenceKind.ENEMY)
    basis.update(enemy_definition_id=definition, presentation_ordinal=ordinal)
    return _reference_value(
        PublicReferenceKind.ENEMY,
        basis,
    )


def reward_reference(
    scope: PublicScope,
    kind: RewardKind | str,
    presentation_ordinal: int,
) -> str:
    normalized = _enum_value(RewardKind, kind, "reward_kind")
    ordinal = _validate_bounded_int(
        presentation_ordinal,
        "presentation_ordinal",
        0,
        MAX_COLLECTION_SIZE - 1,
    )
    basis = _reference_scope_basis(scope, PublicReferenceKind.REWARD)
    basis.update(kind=normalized.value, presentation_ordinal=ordinal)
    return _reference_value(
        PublicReferenceKind.REWARD,
        basis,
    )


def reward_offer_reference(
    scope: PublicScope,
    reward_ref: str,
    card_definition_id: str,
    presentation_ordinal: int,
) -> str:
    reward_value = _validate_public_reference(
        reward_ref,
        PublicReferenceKind.REWARD,
        "reward_ref",
    )
    definition = _validate_semantic_id(card_definition_id, "card_definition_id")
    ordinal = _validate_bounded_int(
        presentation_ordinal,
        "presentation_ordinal",
        0,
        MAX_COLLECTION_SIZE - 1,
    )
    basis = _reference_scope_basis(scope, PublicReferenceKind.OFFER)
    basis.update(
        card_definition_id=definition,
        presentation_ordinal=ordinal,
        reward_ref=reward_value,
    )
    return _reference_value(
        PublicReferenceKind.OFFER,
        basis,
    )


def map_node_reference(
    scope: PublicScope,
    kind: NodeKind | str,
    presentation_ordinal: int,
) -> str:
    normalized = _enum_value(NodeKind, kind, "node_kind")
    ordinal = _validate_bounded_int(
        presentation_ordinal,
        "presentation_ordinal",
        0,
        MAX_COLLECTION_SIZE - 1,
    )
    basis = _reference_scope_basis(scope, PublicReferenceKind.NODE)
    basis.update(kind=normalized.value, presentation_ordinal=ordinal)
    return _reference_value(
        PublicReferenceKind.NODE,
        basis,
    )


def room_option_reference(
    scope: PublicScope,
    room_kind: RoomKind | str,
    option_kind: RoomOptionKind | str,
    presentation_ordinal: int,
) -> str:
    room = _enum_value(RoomKind, room_kind, "room_kind")
    option = _enum_value(RoomOptionKind, option_kind, "option_kind")
    ordinal = _validate_bounded_int(
        presentation_ordinal,
        "presentation_ordinal",
        0,
        MAX_COLLECTION_SIZE - 1,
    )
    basis = _reference_scope_basis(scope, PublicReferenceKind.OPTION)
    basis.update(
        option_kind=option.value,
        presentation_ordinal=ordinal,
        room_kind=room.value,
    )
    return _reference_value(
        PublicReferenceKind.OPTION,
        basis,
    )


def _validate_public_reference(
    value: Any,
    kind: PublicReferenceKind,
    path: str,
) -> str:
    text = _validate_unicode_text(value, path)
    match = _PUBLIC_REFERENCE_PATTERN.fullmatch(text)
    if match is None or match.group(1) != kind.value:
        raise ContractValidationError(f"{path} must be a canonical public {kind.value} reference.")
    return text


def _validate_candidate_id(value: Any, path: str) -> str:
    text = _validate_unicode_text(value, path)
    if _CANDIDATE_ID_PATTERN.fullmatch(text) is None:
        raise ContractValidationError(f"{path} must be a derived candidate identifier.")
    return text


def _validate_decision_scope(value: Any, path: str) -> str:
    text = _validate_unicode_text(value, path)
    if _DECISION_SCOPE_PATTERN.fullmatch(text) is None:
        raise ContractValidationError(f"{path} must be a canonical public decision scope.")
    return text


def _validate_statuses(value: Any, path: str) -> None:
    statuses = _require_object(value, path, _OBSERVATION_SCHEMAS[DecisionPhase.COMBAT]["statuses"])
    _validate_bounded_int(statuses["shrink"], f"{path}.shrink", 0, MAX_PUBLIC_COUNTER)
    _validate_bounded_int(
        statuses["vulnerable"],
        f"{path}.vulnerable",
        0,
        MAX_PUBLIC_COUNTER,
    )


def _validate_hp_pair(value: Mapping[str, Any], path: str) -> None:
    maximum = _validate_bounded_int(value["max_hp"], f"{path}.max_hp", 1, MAX_PUBLIC_HP)
    _validate_bounded_int(value["hp"], f"{path}.hp", 0, maximum)


def _validate_run_player(value: Any, path: str) -> None:
    player = _require_object(
        value,
        path,
        _OBSERVATION_SCHEMAS[DecisionPhase.REWARD]["player"],
    )
    _validate_hp_pair(player, path)
    _validate_bounded_int(player["gold"], f"{path}.gold", 0, MAX_PUBLIC_COUNTER)
    _validate_bounded_int(player["deck_size"], f"{path}.deck_size", 0, MAX_COLLECTION_SIZE)


def _validate_intent(value: Any, path: str) -> None:
    intent = _require_object(
        value,
        path,
        _OBSERVATION_SCHEMAS[DecisionPhase.COMBAT]["intent"],
    )
    kind = _enum_value(IntentKind, intent["kind"], f"{path}.kind")
    status_kind = _enum_value(StatusKind, intent["status_kind"], f"{path}.status_kind")
    numeric_names = (
        "attack_count",
        "attack_damage",
        "block_gain",
        "slimed_added",
        "status_stacks",
        "strength_gain",
    )
    values = {
        name: _validate_bounded_int(
            intent[name],
            f"{path}.{name}",
            0,
            MAX_PUBLIC_COUNTER,
        )
        for name in numeric_names
    }
    attack = values["attack_damage"] > 0 and values["attack_count"] > 0
    valid = {
        IntentKind.ATTACK: attack
        and values["block_gain"] == 0
        and values["strength_gain"] == 0
        and status_kind is StatusKind.NONE
        and values["status_stacks"] == 0
        and values["slimed_added"] == 0,
        IntentKind.ATTACK_DEFEND: attack
        and values["block_gain"] > 0
        and values["strength_gain"] == 0
        and status_kind is StatusKind.NONE
        and values["status_stacks"] == 0
        and values["slimed_added"] == 0,
        IntentKind.DEFEND: not attack
        and values["attack_damage"] == 0
        and values["attack_count"] == 0
        and values["block_gain"] > 0
        and values["strength_gain"] == 0
        and status_kind is StatusKind.NONE
        and values["status_stacks"] == 0
        and values["slimed_added"] == 0,
        IntentKind.BUFF: values["attack_damage"] == 0
        and values["attack_count"] == 0
        and values["block_gain"] == 0
        and values["strength_gain"] > 0
        and status_kind is StatusKind.NONE
        and values["status_stacks"] == 0
        and values["slimed_added"] == 0,
        IntentKind.DEBUFF: values["attack_damage"] == 0
        and values["attack_count"] == 0
        and values["block_gain"] == 0
        and values["strength_gain"] == 0
        and status_kind is not StatusKind.NONE
        and values["status_stacks"] > 0
        and values["slimed_added"] == 0,
        IntentKind.SHUFFLE: values["attack_damage"] == 0
        and values["attack_count"] == 0
        and values["block_gain"] == 0
        and values["strength_gain"] == 0
        and status_kind is StatusKind.NONE
        and values["status_stacks"] == 0
        and values["slimed_added"] > 0,
    }
    if not valid[kind]:
        raise ContractValidationError(f"{path} fields do not match intent kind {kind.value!r}.")


def _validate_combat_observation(data: Mapping[str, Any], scope: PublicScope) -> None:
    path = "public_observation.data"
    _require_exact_fields(data, frozenset(_OBSERVATION_SCHEMAS[DecisionPhase.COMBAT]["top"]), path)
    _validate_bounded_int(data["turn"], f"{path}.turn", 1, MAX_PUBLIC_COUNTER)
    player = _require_object(
        data["player"],
        f"{path}.player",
        _OBSERVATION_SCHEMAS[DecisionPhase.COMBAT]["player"],
    )
    _validate_hp_pair(player, f"{path}.player")
    for name in ("block", "energy", "energy_per_turn", "strength"):
        minimum = 1 if name == "energy_per_turn" else 0
        _validate_bounded_int(
            player[name],
            f"{path}.player.{name}",
            minimum,
            MAX_PUBLIC_COUNTER,
        )
    _validate_statuses(player["statuses"], f"{path}.player.statuses")

    enemies = _require_array(data["enemies"], f"{path}.enemies", minimum=1)
    enemy_refs: set[str] = set()
    for index, raw_enemy in enumerate(enemies):
        enemy_path = f"{path}.enemies[{index}]"
        enemy = _require_object(
            raw_enemy,
            enemy_path,
            _OBSERVATION_SCHEMAS[DecisionPhase.COMBAT]["enemy"],
        )
        definition = _validate_semantic_id(
            enemy["enemy_definition_id"],
            f"{enemy_path}.enemy_definition_id",
        )
        expected_ref = combat_enemy_reference(scope, definition, index)
        if enemy["enemy_ref"] != expected_ref:
            raise ContractValidationError(f"{enemy_path}.enemy_ref is not canonically derived.")
        enemy_refs.add(expected_ref)
        _validate_hp_pair(enemy, enemy_path)
        for name in ("block", "strength"):
            _validate_bounded_int(
                enemy[name],
                f"{enemy_path}.{name}",
                0,
                MAX_PUBLIC_COUNTER,
            )
        alive = _validate_bool(enemy["alive"], f"{enemy_path}.alive")
        if alive != (enemy["hp"] > 0):
            raise ContractValidationError(f"{enemy_path}.alive must equal hp > 0.")
        _validate_statuses(enemy["statuses"], f"{enemy_path}.statuses")
        _validate_intent(enemy["intent"], f"{enemy_path}.intent")
    if len(enemy_refs) != len(enemies):
        raise ContractValidationError(f"{path}.enemies contains duplicate public references.")

    hand = _require_array(data["hand"], f"{path}.hand")
    card_refs: set[str] = set()
    for index, raw_card in enumerate(hand):
        card_path = f"{path}.hand[{index}]"
        card = _require_object(
            raw_card,
            card_path,
            _OBSERVATION_SCHEMAS[DecisionPhase.COMBAT]["card"],
        )
        definition = _validate_semantic_id(
            card["card_definition_id"],
            f"{card_path}.card_definition_id",
        )
        expected_ref = combat_card_reference(scope, definition, index)
        if card["card_ref"] != expected_ref:
            raise ContractValidationError(f"{card_path}.card_ref is not canonically derived.")
        card_refs.add(expected_ref)
        _validate_bounded_int(card["cost"], f"{card_path}.cost", 0, MAX_PUBLIC_COUNTER)
        _validate_bool(card["upgraded"], f"{card_path}.upgraded")
    if len(card_refs) != len(hand):
        raise ContractValidationError(f"{path}.hand contains duplicate public references.")
    for name in ("draw_pile_size", "discard_pile_size", "exhaust_pile_size"):
        _validate_bounded_int(data[name], f"{path}.{name}", 0, MAX_PUBLIC_COUNTER)
    terminal = _validate_bool(data["terminal"], f"{path}.terminal")
    outcome = _enum_value(CombatOutcome, data["outcome"], f"{path}.outcome")
    if terminal != (outcome is not CombatOutcome.ONGOING):
        raise ContractValidationError(f"{path}.terminal and outcome are inconsistent.")
    living_enemies = sum(bool(enemy["alive"]) for enemy in enemies)
    if outcome is CombatOutcome.ONGOING and (player["hp"] == 0 or living_enemies == 0):
        raise ContractValidationError(f"{path} ongoing outcome requires living actors.")
    if outcome is CombatOutcome.VICTORY and (player["hp"] == 0 or living_enemies != 0):
        raise ContractValidationError(f"{path} victory outcome is inconsistent with actors.")
    if outcome is CombatOutcome.DEFEAT and player["hp"] != 0:
        raise ContractValidationError(f"{path} defeat outcome requires zero player hp.")


def _validate_reward_observation(data: Mapping[str, Any], scope: PublicScope) -> None:
    path = "public_observation.data"
    _require_exact_fields(data, frozenset(_OBSERVATION_SCHEMAS[DecisionPhase.REWARD]["top"]), path)
    _validate_run_player(data["player"], f"{path}.player")
    _validate_bool(data["can_proceed"], f"{path}.can_proceed")
    rewards = _require_array(data["rewards"], f"{path}.rewards")
    reward_refs: set[str] = set()
    for index, raw_reward in enumerate(rewards):
        reward_path = f"{path}.rewards[{index}]"
        reward = _require_object(
            raw_reward,
            reward_path,
            _OBSERVATION_SCHEMAS[DecisionPhase.REWARD]["reward"],
        )
        kind = _enum_value(RewardKind, reward["kind"], f"{reward_path}.kind")
        expected_ref = reward_reference(scope, kind, index)
        if reward["reward_ref"] != expected_ref:
            raise ContractValidationError(f"{reward_path}.reward_ref is not canonically derived.")
        reward_refs.add(expected_ref)
        amount = _validate_bounded_int(
            reward["amount"],
            f"{reward_path}.amount",
            0,
            MAX_PUBLIC_COUNTER,
        )
        claimed = _validate_bool(reward["claimed"], f"{reward_path}.claimed")
        opened = _validate_bool(reward["opened"], f"{reward_path}.opened")
        can_skip = _validate_bool(reward["can_skip"], f"{reward_path}.can_skip")
        offers = _require_array(reward["offers"], f"{reward_path}.offers")
        if kind is RewardKind.GOLD:
            if amount <= 0 or opened or can_skip or offers:
                raise ContractValidationError(f"{reward_path} is not a canonical gold reward.")
        else:
            if amount != 0 or (not opened and offers) or (can_skip and (not opened or claimed)):
                raise ContractValidationError(f"{reward_path} is not a canonical card reward.")
        offer_refs: set[str] = set()
        for offer_index, raw_offer in enumerate(offers):
            offer_path = f"{reward_path}.offers[{offer_index}]"
            offer = _require_object(
                raw_offer,
                offer_path,
                _OBSERVATION_SCHEMAS[DecisionPhase.REWARD]["offer"],
            )
            definition = _validate_semantic_id(
                offer["card_definition_id"],
                f"{offer_path}.card_definition_id",
            )
            expected_offer_ref = reward_offer_reference(
                scope,
                expected_ref,
                definition,
                offer_index,
            )
            if offer["offer_ref"] != expected_offer_ref:
                raise ContractValidationError(f"{offer_path}.offer_ref is not canonically derived.")
            offer_refs.add(expected_offer_ref)
            _validate_bool(offer["upgraded"], f"{offer_path}.upgraded")
        if len(offer_refs) != len(offers):
            raise ContractValidationError(f"{reward_path}.offers has duplicate references.")
    if len(reward_refs) != len(rewards):
        raise ContractValidationError(f"{path}.rewards has duplicate references.")


def _validate_map_observation(data: Mapping[str, Any], scope: PublicScope) -> None:
    path = "public_observation.data"
    _require_exact_fields(data, frozenset(_OBSERVATION_SCHEMAS[DecisionPhase.MAP]["top"]), path)
    _validate_run_player(data["player"], f"{path}.player")
    nodes = _require_array(data["nodes"], f"{path}.nodes", minimum=1)
    node_refs: set[str] = set()
    visited_from_nodes: set[str] = set()
    for index, raw_node in enumerate(nodes):
        node_path = f"{path}.nodes[{index}]"
        node = _require_object(
            raw_node,
            node_path,
            _OBSERVATION_SCHEMAS[DecisionPhase.MAP]["node"],
        )
        kind = _enum_value(NodeKind, node["kind"], f"{node_path}.kind")
        expected_ref = map_node_reference(scope, kind, index)
        if node["node_ref"] != expected_ref:
            raise ContractValidationError(f"{node_path}.node_ref is not canonically derived.")
        node_refs.add(expected_ref)
        _validate_bool(node["available"], f"{node_path}.available")
        if _validate_bool(node["visited"], f"{node_path}.visited"):
            visited_from_nodes.add(expected_ref)
    if len(node_refs) != len(nodes):
        raise ContractValidationError(f"{path}.nodes has duplicate references.")
    current_ref = data["current_node_ref"]
    if current_ref is not None:
        _validate_public_reference(
            current_ref,
            PublicReferenceKind.NODE,
            f"{path}.current_node_ref",
        )
        if current_ref not in node_refs:
            raise ContractValidationError(f"{path}.current_node_ref does not resolve.")
    visited_values = _require_array(data["visited_node_refs"], f"{path}.visited_node_refs")
    expected_visited = tuple(
        node["node_ref"] for node in nodes if node["visited"]
    )
    for value in visited_values:
        _validate_public_reference(
            value,
            PublicReferenceKind.NODE,
            f"{path}.visited_node_refs",
        )
    if visited_values != expected_visited or set(visited_values) != visited_from_nodes:
        raise ContractValidationError(f"{path}.visited_node_refs is inconsistent with nodes.")
    edges = _require_array(data["edges"], f"{path}.edges")
    seen_edges: set[tuple[str, str]] = set()
    for index, raw_edge in enumerate(edges):
        edge_path = f"{path}.edges[{index}]"
        edge = _require_object(
            raw_edge,
            edge_path,
            _OBSERVATION_SCHEMAS[DecisionPhase.MAP]["edge"],
        )
        source = _validate_public_reference(
            edge["source_node_ref"], PublicReferenceKind.NODE, f"{edge_path}.source_node_ref"
        )
        target = _validate_public_reference(
            edge["target_node_ref"], PublicReferenceKind.NODE, f"{edge_path}.target_node_ref"
        )
        if source not in node_refs or target not in node_refs or source == target:
            raise ContractValidationError(f"{edge_path} has unresolved or reflexive references.")
        seen_edges.add((source, target))
    if len(seen_edges) != len(edges):
        raise ContractValidationError(f"{path}.edges contains duplicates.")
    if seen_edges and tuple(
        (edge["source_node_ref"], edge["target_node_ref"]) for edge in edges
    ) != tuple(sorted(seen_edges)):
        raise ContractValidationError(f"{path}.edges must use canonical reference order.")


def _validate_room_observation(data: Mapping[str, Any], scope: PublicScope) -> None:
    path = "public_observation.data"
    _require_exact_fields(data, frozenset(_OBSERVATION_SCHEMAS[DecisionPhase.ROOM]["top"]), path)
    _validate_run_player(data["player"], f"{path}.player")
    room_kind = _enum_value(RoomKind, data["room_kind"], f"{path}.room_kind")
    _validate_bool(data["can_proceed"], f"{path}.can_proceed")
    options = _require_array(data["options"], f"{path}.options")
    option_refs: set[str] = set()
    for index, raw_option in enumerate(options):
        option_path = f"{path}.options[{index}]"
        option = _require_object(
            raw_option,
            option_path,
            _OBSERVATION_SCHEMAS[DecisionPhase.ROOM]["option"],
        )
        option_kind = _enum_value(RoomOptionKind, option["kind"], f"{option_path}.kind")
        effect = _enum_value(RoomEffectKind, option["effect"], f"{option_path}.effect")
        expected_ref = room_option_reference(scope, room_kind, option_kind, index)
        if option["option_ref"] != expected_ref:
            raise ContractValidationError(f"{option_path}.option_ref is not canonically derived.")
        option_refs.add(expected_ref)
        _validate_bool(option["enabled"], f"{option_path}.enabled")
        amount = _validate_bounded_int(
            option["amount"],
            f"{option_path}.amount",
            0,
            MAX_PUBLIC_COUNTER,
        )
        if room_kind is RoomKind.REST:
            if (
                option_kind is not RoomOptionKind.REST_HEAL
                or effect is not RoomEffectKind.HEAL
                or amount <= 0
            ):
                raise ContractValidationError(f"{option_path} is not a canonical rest option.")
        elif option_kind is not RoomOptionKind.EVENT_OPTION:
            raise ContractValidationError(f"{option_path} is not a canonical event option.")
        elif (effect is RoomEffectKind.NONE) != (amount == 0):
            raise ContractValidationError(f"{option_path}.amount does not match its effect.")
    if len(option_refs) != len(options):
        raise ContractValidationError(f"{path}.options has duplicate references.")


def _validate_terminal_observation(data: Mapping[str, Any], scope: PublicScope) -> None:
    del scope
    path = "public_observation.data"
    _require_exact_fields(
        data,
        frozenset(_OBSERVATION_SCHEMAS[DecisionPhase.TERMINAL]["top"]),
        path,
    )
    outcome = _enum_value(RunOutcome, data["outcome"], f"{path}.outcome")
    _validate_run_player(data["player"], f"{path}.player")
    if outcome is RunOutcome.VICTORY and data["player"]["hp"] == 0:
        raise ContractValidationError(f"{path} victory requires positive player hp.")
    if outcome is RunOutcome.DEFEAT and data["player"]["hp"] != 0:
        raise ContractValidationError(f"{path} defeat requires zero player hp.")


def _validate_unsupported_observation(data: Mapping[str, Any], scope: PublicScope) -> None:
    del scope
    path = "public_observation.data"
    _require_exact_fields(
        data,
        frozenset(_OBSERVATION_SCHEMAS[DecisionPhase.UNSUPPORTED]["top"]),
        path,
    )
    _enum_value(UnsupportedReasonCode, data["reason_code"], f"{path}.reason_code")


def _validate_public_observation(
    phase: DecisionPhase,
    data: Mapping[str, Any],
    scope: PublicScope,
) -> None:
    validators = {
        DecisionPhase.COMBAT: _validate_combat_observation,
        DecisionPhase.REWARD: _validate_reward_observation,
        DecisionPhase.MAP: _validate_map_observation,
        DecisionPhase.ROOM: _validate_room_observation,
        DecisionPhase.TERMINAL: _validate_terminal_observation,
        DecisionPhase.UNSUPPORTED: _validate_unsupported_observation,
    }
    validators[phase](data, scope)


def _validate_public_event_payload(
    event_type: PublicEventKind,
    phase: DecisionPhase,
    data: Mapping[str, Any],
) -> None:
    expected_phase, fields = _PUBLIC_EVENT_SPECS[event_type]
    if phase is not expected_phase:
        raise ContractValidationError("public_event phase does not match event_type.")
    _require_exact_fields(data, frozenset(fields), "public_event.data")
    if event_type is PublicEventKind.COMBAT_CARD_PLAYED:
        _validate_semantic_id(
            data["card_definition_id"],
            "public_event.data.card_definition_id",
        )
        target = data["target_enemy_definition_id"]
        if target is not None:
            _validate_semantic_id(target, "public_event.data.target_enemy_definition_id")
    elif event_type is PublicEventKind.COMBAT_RESOLVED:
        outcome = _enum_value(CombatOutcome, data["outcome"], "public_event.data.outcome")
        if outcome is CombatOutcome.ONGOING:
            raise ContractValidationError("combat.resolved requires a terminal outcome.")
    elif event_type is PublicEventKind.REWARD_GOLD_CLAIMED:
        _validate_bounded_int(data["amount"], "public_event.data.amount", 1, MAX_PUBLIC_COUNTER)
    elif event_type is PublicEventKind.REWARD_CARD_OPENED:
        _validate_bounded_int(
            data["offer_count"],
            "public_event.data.offer_count",
            0,
            MAX_COLLECTION_SIZE,
        )
    elif event_type is PublicEventKind.REWARD_CARD_CHOSEN:
        _validate_semantic_id(data["card_definition_id"], "public_event.data.card_definition_id")
        _validate_bool(data["upgraded"], "public_event.data.upgraded")
    elif event_type is PublicEventKind.MAP_NODE_CHOSEN:
        _enum_value(NodeKind, data["node_kind"], "public_event.data.node_kind")
    elif event_type is PublicEventKind.ROOM_REST_HEALED:
        _validate_bounded_int(data["amount"], "public_event.data.amount", 1, MAX_PUBLIC_COUNTER)
    elif event_type is PublicEventKind.ROOM_EVENT_OPTION_CHOSEN:
        effect = _enum_value(RoomEffectKind, data["effect"], "public_event.data.effect")
        amount = _validate_bounded_int(
            data["amount"],
            "public_event.data.amount",
            0,
            MAX_PUBLIC_COUNTER,
        )
        if (effect is RoomEffectKind.NONE) != (amount == 0):
            raise ContractValidationError("room event amount does not match effect.")
    elif event_type is PublicEventKind.RUN_TERMINATED:
        _enum_value(RunOutcome, data["outcome"], "public_event.data.outcome")


CONTRACT_SCHEMA: Mapping[str, Any] = _freeze_json(
    {
        "canonicalization": CANONICALIZATION,
        "candidate_fields": {
            kind.value: fields for kind, fields in _CANDIDATE_FIELD_NAMES.items()
        },
        "candidate_hash_domain": "headless_v0.candidate.v1",
        "candidate_identity": "sha256_of_public_decision_scope_and_normalized_semantics",
        "candidate_id_format": "cand.<sha256>",
        "candidate_kinds": tuple(kind.value for kind in CandidateKind),
        "candidate_phases": {
            kind.value: phase.value for kind, phase in _CANDIDATE_PHASE_NAMES.items()
        },
        "compatibility_class": COMPATIBILITY_CLASS,
        "contract": CONTRACT_VERSION,
        "cross_field_rules": (
            "combat_alive_equals_hp_positive",
            "combat_intent_effect_fields_match_finite_kind",
            "combat_outcome_matches_terminal_and_living_actors",
            "map_current_visited_and_edges_resolve_to_nodes",
            "reward_gold_and_card_shapes_match_kind_opened_claimed_skip_state",
            "room_option_kind_effect_amount_match_room_kind",
            "terminal_outcome_matches_player_hp_where_determined",
        ),
        "decision_hash_domain": "headless_v0.decision.v1",
        "decision_phases": tuple(phase.value for phase in DecisionPhase),
        "decision_statuses": tuple(status.value for status in DecisionStatus),
        "evidence_labels": tuple(label.value for label in EvidenceLabel),
        "hash_algorithm": HASH_ALGORITHM,
        "finite_public_enums": {
            "combat_outcome": tuple(item.value for item in CombatOutcome),
            "intent_kind": tuple(item.value for item in IntentKind),
            "node_kind": tuple(item.value for item in NodeKind),
            "reward_kind": tuple(item.value for item in RewardKind),
            "room_effect_kind": tuple(item.value for item in RoomEffectKind),
            "room_kind": tuple(item.value for item in RoomKind),
            "room_option_kind": tuple(item.value for item in RoomOptionKind),
            "run_outcome": tuple(item.value for item in RunOutcome),
            "status_kind": tuple(item.value for item in StatusKind),
            "unsupported_reason_code": tuple(item.value for item in UnsupportedReasonCode),
        },
        "limits": {
            "max_collection_size": MAX_COLLECTION_SIZE,
            "max_public_counter": MAX_PUBLIC_COUNTER,
            "max_public_hp": MAX_PUBLIC_HP,
        },
        "observation_schemas": {
            phase.value: {name: fields for name, fields in schema.items()}
            for phase, schema in _OBSERVATION_SCHEMAS.items()
        },
        "policy_forbidden_field_components": tuple(
            sorted(_FORBIDDEN_POLICY_FIELD_COMPONENTS)
        ),
        "policy_forbidden_field_names": tuple(sorted(_FORBIDDEN_POLICY_FIELD_NAMES)),
        "public_observation_schema": "headless_v0.public_observation.v1",
        "public_scope": {
            "allocation_rules": {
                "decision_ordinal": "increments_for_each_distinct_public_decision_in_history",
                "history_ordinal": "changes_when_the_public_history_lifetime_restarts",
                "reveal_ordinal": "per_kind_increment_after_declared_public_linkage_expires",
            },
            "decision_domain": "headless_v0.public_decision_scope.v1",
            "fields": ("decision_ordinal", "history_ordinal", "reveal_ordinals"),
            "history_domain": "headless_v0.public_history_scope.v1",
            "reveal_kinds": tuple(kind.value for kind in PublicReferenceKind),
        },
        "public_event_specs": {
            kind.value: {"fields": fields, "phase": phase.value}
            for kind, (phase, fields) in _PUBLIC_EVENT_SPECS.items()
        },
        "public_reference": {
            "format": "pub.<kind>.<sha256>",
            "hash_domain_template": "headless_v0.public_ref.<kind>.v1",
            "kinds": tuple(kind.value for kind in PublicReferenceKind),
            "basis": {
                "card": (
                    "history_scope",
                    "reveal_ordinal",
                    "card_definition_id",
                    "presentation_ordinal",
                ),
                "enemy": (
                    "history_scope",
                    "reveal_ordinal",
                    "enemy_definition_id",
                    "presentation_ordinal",
                ),
                "node": ("history_scope", "reveal_ordinal", "kind", "presentation_ordinal"),
                "offer": (
                    "history_scope",
                    "reveal_ordinal",
                    "card_definition_id",
                    "presentation_ordinal",
                    "reward_ref",
                ),
                "option": (
                    "history_scope",
                    "reveal_ordinal",
                    "option_kind",
                    "presentation_ordinal",
                    "room_kind",
                ),
                "reward": (
                    "history_scope",
                    "reveal_ordinal",
                    "kind",
                    "presentation_ordinal",
                ),
            },
            "lifetimes": {
                "card": "hand_reveal_until_public_linkage_break",
                "enemy": "combat_encounter_reveal",
                "node": "map_graph_reveal",
                "offer": "opened_card_reward_reveal",
                "option": "room_decision_reveal",
                "reward": "reward_screen_reveal",
            },
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
            "public_observation": ("data", "phase", "public_scope", "schema"),
            "public_scope": ("decision_ordinal", "history_ordinal", "reveal_ordinals"),
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
            "candidate_ids_derived_only_from_public_scope_and_normalized_semantics",
            "candidate_ids_include_canonical_public_decision_scope",
            "candidate_order_canonical_by_derived_public_id",
            "candidate_references_resolve_in_same_public_observation",
            "combat_pile_counts_are_combat_v0_or_structural_not_live_truth",
            "exact_path_phase_schemas_and_raw_key_spelling",
            "map_set_like_reference_arrays_use_canonical_order",
            "event_sequences_are_zero_based_contiguous",
            "finite_event_catalog_with_exact_phase_and_payload",
            "manifest_action_phases_are_exact_partition",
            "manifest_evidence_components_unique_and_sorted",
            "non_actionable_has_no_candidates",
            "policy_view_revalidates_status_candidate_provenance_uniqueness_event_sequence",
            "public_aliases_derived_from_explicit_public_presentation_basis",
            "public_reference_continuity_requires_same_history_and_reveal_allocation",
            "public_reference_expiry_requires_new_reveal_ordinal",
            "public_projector_provenance_required_outside_contract_validation",
            "public_json_has_no_floating_point_values",
            "public_json_rejects_unpaired_utf16_surrogates",
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
    public_scope: PublicScope
    schema: str = "headless_v0.public_observation.v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "phase",
            _enum_value(DecisionPhase, self.phase, "public_observation.phase"),
        )
        if self.schema != "headless_v0.public_observation.v1":
            raise ContractValidationError("Unsupported public observation schema.")
        if not isinstance(self.public_scope, PublicScope):
            raise ContractValidationError("public_observation.public_scope has the wrong type.")
        if not isinstance(self.data, Mapping):
            raise ContractValidationError("public_observation.data must be an object.")
        _validate_public_observation(self.phase, self.data, self.public_scope)
        object.__setattr__(
            self,
            "data",
            _freeze_json(self.data, "public_observation.data", policy_view=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": _thaw_json(self.data),
            "phase": self.phase.value,
            "public_scope": self.public_scope.to_dict(),
            "schema": self.schema,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PublicObservation":
        _require_exact_fields(
            value,
            {"data", "phase", "public_scope", "schema"},
            "public_observation",
        )
        data = value["data"]
        scope = value["public_scope"]
        if not isinstance(data, Mapping):
            raise ContractValidationError("public_observation.data must be an object.")
        if not isinstance(scope, Mapping):
            raise ContractValidationError("public_observation.public_scope must be an object.")
        return cls(
            phase=value["phase"],
            data=data,
            public_scope=PublicScope.from_dict(scope),
            schema=value["schema"],
        )


@dataclass(frozen=True, slots=True)
class PublicEvent:
    sequence: int
    event_type: PublicEventKind
    phase: DecisionPhase
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        _validate_bounded_int(
            self.sequence,
            "public_event.sequence",
            0,
            MAX_COLLECTION_SIZE - 1,
        )
        object.__setattr__(
            self,
            "event_type",
            _enum_value(PublicEventKind, self.event_type, "public_event.event_type"),
        )
        object.__setattr__(
            self,
            "phase",
            _enum_value(DecisionPhase, self.phase, "public_event.phase"),
        )
        if not isinstance(self.data, Mapping):
            raise ContractValidationError("public_event.data must be an object.")
        _validate_public_event_payload(self.event_type, self.phase, self.data)
        object.__setattr__(
            self,
            "data",
            _freeze_json(self.data, "public_event.data", policy_view=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": _thaw_json(self.data),
            "event_type": self.event_type.value,
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
    decision_scope: str
    candidate_id: str = field(init=False)
    KIND: ClassVar[CandidateKind]

    def __post_init__(self) -> None:
        _validate_decision_scope(self.decision_scope, "candidate.decision_scope")
        object.__setattr__(self, "candidate_id", _derive_candidate_id(self))

    @property
    def kind(self) -> CandidateKind:
        return self.KIND


@dataclass(frozen=True, slots=True)
class CombatPlayCardCandidate(Candidate):
    card_ref: str
    target_ref: str | None = None
    KIND: ClassVar[CandidateKind] = CandidateKind.COMBAT_PLAY_CARD

    def __post_init__(self) -> None:
        _validate_public_reference(self.card_ref, PublicReferenceKind.CARD, "candidate.card_ref")
        if self.target_ref is not None:
            _validate_public_reference(
                self.target_ref,
                PublicReferenceKind.ENEMY,
                "candidate.target_ref",
            )
        super(CombatPlayCardCandidate, self).__post_init__()


@dataclass(frozen=True, slots=True)
class CombatEndTurnCandidate(Candidate):
    KIND: ClassVar[CandidateKind] = CandidateKind.COMBAT_END_TURN


@dataclass(frozen=True, slots=True)
class RewardClaimGoldCandidate(Candidate):
    reward_ref: str
    amount: int
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_CLAIM_GOLD

    def __post_init__(self) -> None:
        _validate_public_reference(
            self.reward_ref,
            PublicReferenceKind.REWARD,
            "candidate.reward_ref",
        )
        _validate_bounded_int(
            self.amount,
            "candidate.amount",
            1,
            MAX_PUBLIC_COUNTER,
        )
        super(RewardClaimGoldCandidate, self).__post_init__()


@dataclass(frozen=True, slots=True)
class RewardOpenCardRewardCandidate(Candidate):
    reward_ref: str
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_OPEN_CARD_REWARD

    def __post_init__(self) -> None:
        _validate_public_reference(
            self.reward_ref,
            PublicReferenceKind.REWARD,
            "candidate.reward_ref",
        )
        super(RewardOpenCardRewardCandidate, self).__post_init__()


@dataclass(frozen=True, slots=True)
class RewardChooseCardCandidate(Candidate):
    reward_ref: str
    offer_ref: str
    card_definition_id: str
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_CHOOSE_CARD

    def __post_init__(self) -> None:
        _validate_public_reference(
            self.reward_ref,
            PublicReferenceKind.REWARD,
            "candidate.reward_ref",
        )
        _validate_public_reference(
            self.offer_ref,
            PublicReferenceKind.OFFER,
            "candidate.offer_ref",
        )
        _validate_semantic_id(self.card_definition_id, "candidate.card_definition_id")
        super(RewardChooseCardCandidate, self).__post_init__()


@dataclass(frozen=True, slots=True)
class RewardSkipCardCandidate(Candidate):
    reward_ref: str
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_SKIP_CARD

    def __post_init__(self) -> None:
        _validate_public_reference(
            self.reward_ref,
            PublicReferenceKind.REWARD,
            "candidate.reward_ref",
        )
        super(RewardSkipCardCandidate, self).__post_init__()


@dataclass(frozen=True, slots=True)
class RewardProceedCandidate(Candidate):
    KIND: ClassVar[CandidateKind] = CandidateKind.REWARD_PROCEED


@dataclass(frozen=True, slots=True)
class MapChooseNodeCandidate(Candidate):
    node_ref: str
    KIND: ClassVar[CandidateKind] = CandidateKind.MAP_CHOOSE_NODE

    def __post_init__(self) -> None:
        _validate_public_reference(
            self.node_ref,
            PublicReferenceKind.NODE,
            "candidate.node_ref",
        )
        super(MapChooseNodeCandidate, self).__post_init__()


@dataclass(frozen=True, slots=True)
class RoomRestHealCandidate(Candidate):
    option_ref: str
    heal_amount: int
    KIND: ClassVar[CandidateKind] = CandidateKind.ROOM_REST_HEAL

    def __post_init__(self) -> None:
        _validate_public_reference(
            self.option_ref,
            PublicReferenceKind.OPTION,
            "candidate.option_ref",
        )
        _validate_bounded_int(
            self.heal_amount,
            "candidate.heal_amount",
            1,
            MAX_PUBLIC_COUNTER,
        )
        super(RoomRestHealCandidate, self).__post_init__()


@dataclass(frozen=True, slots=True)
class RoomEventOptionCandidate(Candidate):
    option_ref: str
    KIND: ClassVar[CandidateKind] = CandidateKind.ROOM_EVENT_OPTION

    def __post_init__(self) -> None:
        _validate_public_reference(
            self.option_ref,
            PublicReferenceKind.OPTION,
            "candidate.option_ref",
        )
        super(RoomEventOptionCandidate, self).__post_init__()


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


def _candidate_semantics(candidate: TypedCandidate) -> dict[str, Any]:
    if type(candidate) not in _TYPED_CANDIDATE_TYPES:
        raise ContractValidationError("Unsupported typed candidate instance.")
    result: dict[str, Any] = {"kind": candidate.kind.value}
    if isinstance(candidate, CombatPlayCardCandidate):
        result.update(card_ref=candidate.card_ref, target_ref=candidate.target_ref)
    elif isinstance(candidate, RewardClaimGoldCandidate):
        result.update(amount=candidate.amount, reward_ref=candidate.reward_ref)
    elif isinstance(candidate, RewardOpenCardRewardCandidate):
        result["reward_ref"] = candidate.reward_ref
    elif isinstance(candidate, RewardChooseCardCandidate):
        result.update(
            card_definition_id=candidate.card_definition_id,
            offer_ref=candidate.offer_ref,
            reward_ref=candidate.reward_ref,
        )
    elif isinstance(candidate, RewardSkipCardCandidate):
        result["reward_ref"] = candidate.reward_ref
    elif isinstance(candidate, MapChooseNodeCandidate):
        result["node_ref"] = candidate.node_ref
    elif isinstance(candidate, RoomRestHealCandidate):
        result.update(heal_amount=candidate.heal_amount, option_ref=candidate.option_ref)
    elif isinstance(candidate, RoomEventOptionCandidate):
        result["option_ref"] = candidate.option_ref
    elif not isinstance(
        candidate,
        (CombatEndTurnCandidate, RewardProceedCandidate, RoomProceedCandidate),
    ):
        raise ContractValidationError("Unsupported typed candidate instance.")
    return result


def _derive_candidate_id(candidate: TypedCandidate) -> str:
    digest = _domain_hash(
        "headless_v0.candidate.v1",
        {
            "decision_scope": candidate.decision_scope,
            "semantics": _candidate_semantics(candidate),
        },
    )
    return f"cand.{digest}"


def candidate_to_dict(candidate: TypedCandidate) -> dict[str, Any]:
    result = _candidate_semantics(candidate)
    result["candidate_id"] = candidate.candidate_id
    result["decision_scope"] = candidate.decision_scope
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
    encoded_candidate_id = _validate_candidate_id(
        value["candidate_id"],
        "candidate.candidate_id",
    )
    decision_scope = _validate_decision_scope(
        value["decision_scope"],
        "candidate.decision_scope",
    )
    if kind is CandidateKind.COMBAT_PLAY_CARD:
        target = value["target_ref"]
        if target is not None and not isinstance(target, str):
            raise ContractValidationError("candidate.target_ref must be a string or null.")
        candidate: TypedCandidate = CombatPlayCardCandidate(
            decision_scope=decision_scope,
            card_ref=value["card_ref"],
            target_ref=target,
        )
    elif kind is CandidateKind.COMBAT_END_TURN:
        candidate = CombatEndTurnCandidate(decision_scope)
    elif kind is CandidateKind.REWARD_CLAIM_GOLD:
        candidate = RewardClaimGoldCandidate(
            decision_scope=decision_scope,
            reward_ref=value["reward_ref"],
            amount=value["amount"],
        )
    elif kind is CandidateKind.REWARD_OPEN_CARD_REWARD:
        candidate = RewardOpenCardRewardCandidate(
            decision_scope=decision_scope,
            reward_ref=value["reward_ref"],
        )
    elif kind is CandidateKind.REWARD_CHOOSE_CARD:
        candidate = RewardChooseCardCandidate(
            decision_scope=decision_scope,
            reward_ref=value["reward_ref"],
            offer_ref=value["offer_ref"],
            card_definition_id=value["card_definition_id"],
        )
    elif kind is CandidateKind.REWARD_SKIP_CARD:
        candidate = RewardSkipCardCandidate(
            decision_scope=decision_scope,
            reward_ref=value["reward_ref"],
        )
    elif kind is CandidateKind.REWARD_PROCEED:
        candidate = RewardProceedCandidate(decision_scope)
    elif kind is CandidateKind.MAP_CHOOSE_NODE:
        candidate = MapChooseNodeCandidate(
            decision_scope=decision_scope,
            node_ref=value["node_ref"],
        )
    elif kind is CandidateKind.ROOM_REST_HEAL:
        candidate = RoomRestHealCandidate(
            decision_scope=decision_scope,
            option_ref=value["option_ref"],
            heal_amount=value["heal_amount"],
        )
    elif kind is CandidateKind.ROOM_EVENT_OPTION:
        candidate = RoomEventOptionCandidate(
            decision_scope=decision_scope,
            option_ref=value["option_ref"],
        )
    elif kind is CandidateKind.ROOM_PROCEED:
        candidate = RoomProceedCandidate(decision_scope)
    else:
        raise ContractValidationError("Unsupported candidate kind.")
    if encoded_candidate_id != candidate.candidate_id:
        raise ContractValidationError("candidate.candidate_id is not canonically derived.")
    return candidate


def _validate_candidate_references(
    observation: PublicObservation,
    candidates: tuple[TypedCandidate, ...],
) -> None:
    data = observation.data
    expected_scope = observation.public_scope.decision_scope
    if any(candidate.decision_scope != expected_scope for candidate in candidates):
        raise ContractValidationError(
            "Candidate decision_scope does not match its public observation."
        )
    if observation.phase is DecisionPhase.COMBAT:
        if data["terminal"] or data["outcome"] != CombatOutcome.ONGOING.value:
            raise ContractValidationError("An actionable combat observation cannot be terminal.")
        card_refs = {card["card_ref"] for card in data["hand"]}
        living_enemy_refs = {
            enemy["enemy_ref"] for enemy in data["enemies"] if enemy["alive"]
        }
        for candidate in candidates:
            if isinstance(candidate, CombatPlayCardCandidate):
                if candidate.card_ref not in card_refs:
                    raise ContractValidationError("Combat candidate card_ref does not resolve.")
                if (
                    candidate.target_ref is not None
                    and candidate.target_ref not in living_enemy_refs
                ):
                    raise ContractValidationError("Combat candidate target_ref does not resolve.")
        return

    if observation.phase is DecisionPhase.REWARD:
        rewards = {reward["reward_ref"]: reward for reward in data["rewards"]}
        for candidate in candidates:
            if isinstance(candidate, RewardProceedCandidate):
                if not data["can_proceed"]:
                    raise ContractValidationError("Reward proceed is not publicly available.")
                continue
            reward_ref = candidate.reward_ref
            if reward_ref not in rewards:
                raise ContractValidationError("Reward candidate reward_ref does not resolve.")
            reward = rewards[reward_ref]
            if reward["claimed"]:
                raise ContractValidationError("Reward candidate references a claimed reward.")
            if isinstance(candidate, RewardClaimGoldCandidate):
                if reward["kind"] != RewardKind.GOLD.value or reward["amount"] != candidate.amount:
                    raise ContractValidationError("Gold candidate does not match its reward.")
            elif isinstance(candidate, RewardOpenCardRewardCandidate):
                if reward["kind"] != RewardKind.CARD.value or reward["opened"]:
                    raise ContractValidationError("Open-card candidate does not match its reward.")
            elif isinstance(candidate, RewardChooseCardCandidate):
                offers = {offer["offer_ref"]: offer for offer in reward["offers"]}
                if (
                    reward["kind"] != RewardKind.CARD.value
                    or not reward["opened"]
                    or candidate.offer_ref not in offers
                    or offers[candidate.offer_ref]["card_definition_id"]
                    != candidate.card_definition_id
                ):
                    raise ContractValidationError("Choose-card candidate does not match its offer.")
            elif isinstance(candidate, RewardSkipCardCandidate):
                if (
                    reward["kind"] != RewardKind.CARD.value
                    or not reward["opened"]
                    or not reward["can_skip"]
                ):
                    raise ContractValidationError("Skip-card candidate is not publicly available.")
        return

    if observation.phase is DecisionPhase.MAP:
        available_refs = {
            node["node_ref"] for node in data["nodes"] if node["available"]
        }
        for candidate in candidates:
            if candidate.node_ref not in available_refs:
                raise ContractValidationError("Map candidate node_ref is not available.")
        return

    if observation.phase is DecisionPhase.ROOM:
        options = {option["option_ref"]: option for option in data["options"]}
        for candidate in candidates:
            if isinstance(candidate, RoomProceedCandidate):
                if not data["can_proceed"]:
                    raise ContractValidationError("Room proceed is not publicly available.")
                continue
            option_ref = candidate.option_ref
            if option_ref not in options or not options[option_ref]["enabled"]:
                raise ContractValidationError("Room candidate option_ref is not available.")
            option = options[option_ref]
            if isinstance(candidate, RoomRestHealCandidate):
                if (
                    option["kind"] != RoomOptionKind.REST_HEAL.value
                    or option["effect"] != RoomEffectKind.HEAL.value
                    or option["amount"] != candidate.heal_amount
                ):
                    raise ContractValidationError("Rest-heal candidate does not match its option.")
            elif option["kind"] != RoomOptionKind.EVENT_OPTION.value:
                raise ContractValidationError("Event candidate does not match its option.")


def _validate_event_sequence(events: tuple[PublicEvent, ...], path: str) -> None:
    if any(not isinstance(event, PublicEvent) for event in events):
        raise ContractValidationError(f"{path} must contain PublicEvent values.")
    sequences = tuple(event.sequence for event in events)
    if sequences != tuple(range(len(events))):
        raise ContractValidationError(
            f"{path} sequences must be canonical contiguous values starting at zero."
        )


@dataclass(frozen=True, slots=True)
class PolicyView:
    """The only decision payload intended for a chooser or future model."""

    status: DecisionStatus
    phase: DecisionPhase
    observation: PublicObservation
    candidates: tuple[TypedCandidate, ...]
    public_events: tuple[PublicEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "status",
            _enum_value(DecisionStatus, self.status, "policy_view.status"),
        )
        object.__setattr__(
            self,
            "phase",
            _enum_value(DecisionPhase, self.phase, "policy_view.phase"),
        )
        if not isinstance(self.observation, PublicObservation):
            raise ContractValidationError("policy_view.observation has the wrong type.")
        if self.observation.phase is not self.phase:
            raise ContractValidationError("Policy view and observation phases must match.")
        if (self.status is DecisionStatus.TERMINAL) != (
            self.phase is DecisionPhase.TERMINAL
        ):
            raise ContractValidationError("Policy terminal status and phase must match.")
        if (self.status is DecisionStatus.UNSUPPORTED) != (
            self.phase is DecisionPhase.UNSUPPORTED
        ):
            raise ContractValidationError("Policy unsupported status and phase must match.")
        candidates = tuple(self.candidates)
        if any(type(candidate) not in _TYPED_CANDIDATE_TYPES for candidate in candidates):
            raise ContractValidationError("policy_view.candidates must be typed candidates.")
        if self.status is DecisionStatus.ACTIONABLE:
            if not candidates or self.phase not in ACTION_PHASES:
                raise ContractValidationError("Actionable policy view requires candidates.")
            if any(_CANDIDATE_PHASE[item.kind] is not self.phase for item in candidates):
                raise ContractValidationError("Policy candidate phase does not match.")
            _validate_candidate_references(self.observation, candidates)
        elif candidates:
            raise ContractValidationError("Non-actionable policy view cannot have candidates.")
        candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ContractValidationError("Policy candidate IDs must be unique.")
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(candidates, key=lambda item: item.candidate_id)),
        )
        events = tuple(self.public_events)
        _validate_event_sequence(events, "policy_view.public_events")
        object.__setattr__(self, "public_events", events)


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
            _validate_candidate_references(self.observation, candidates)
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
        _validate_candidate_id(self.candidate_id, "binding.candidate_id")

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
