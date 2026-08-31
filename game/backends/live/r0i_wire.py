"""Strict fixture codec for the bridge's ``live_probe_v0`` R0i wire bodies.

This module deliberately does not implement ``headless_v0`` or a transport.
It is a bounded parser for the public decision/receipt bodies emitted by the
checked-in bridge fixture, with control and audit values kept distinct.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple, Union


R0I_WIRE_SCHEMA = "r0i_wire_v0"
EVIDENCE_CLASSIFICATION = "bridge_fixture"
BRIDGE_VERSION = "0.8.0"
PROTOCOL = "live_probe_v0"
SCHEMA_VERSION = 1
VECTOR_COUNT = 36
VECTOR_INVENTORY_SHA256 = "8dfc1e1e2571e66ea5a9652b1c45a80500209dc1b26b4a6bbfe87a44eb1ea1fe"

_FAMILIES = frozenset(("combat", "reward", "map", "room"))
_DECISION_STATUSES = frozenset(("ready", "waiting", "unsupported", "complete"))
_RECEIPT_REASONS = frozenset(
    ("accepted", "stale_decision", "invalid_action", "already_applied", "action_limit_reached")
)
_ID = re.compile(r"[0-9a-f]{64}\Z")
_CORRELATION_ID = re.compile(r"[0-9a-f]{32}\Z")
_COMBAT_PLAY = re.compile(r"play:([0-9])(?::([0-5]))?\Z")
_REWARD_SLOT = re.compile(r"(claim|open):([0-7])\Z")
_REWARD_CHOICE = re.compile(r"choose:([0-4])\Z")
_MAP_SELECT = re.compile(r"select:([0-7])\Z")
_ROOM_CHOOSE = re.compile(r"choose:([0-7])\Z")


class R0iWireError(ValueError):
    """Raised when a body is not an exact supported R0i wire value."""


@dataclass(frozen=True)
class ParserManifest:
    wire_schema: str = R0I_WIRE_SCHEMA
    evidence: str = EVIDENCE_CLASSIFICATION
    bridge_version: str = BRIDGE_VERSION
    protocol: str = PROTOCOL
    schema_version: int = SCHEMA_VERSION
    vector_count: int = VECTOR_COUNT
    vector_inventory_sha256: str = VECTOR_INVENTORY_SHA256


PARSER_MANIFEST = ParserManifest()


@dataclass(frozen=True)
class BridgeBinding:
    """A ready decision identity, bound to this bridge protocol only."""

    protocol: str
    decision_id: str

    def __post_init__(self) -> None:
        if self.protocol != PROTOCOL or not _ID.fullmatch(self.decision_id):
            raise R0iWireError("invalid bridge binding")


@dataclass(frozen=True)
class PublicDecision:
    """Public decision projection. It intentionally has no control token field."""

    family: str
    status: str
    actionable: bool
    binding: Optional[BridgeBinding]
    fields: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.fields, Mapping):
            raise R0iWireError("public decision fields must be a mapping")
        object.__setattr__(self, "fields", _freeze_mapping(self.fields))


@dataclass(frozen=True)
class CombatDecision(PublicDecision):
    pass


@dataclass(frozen=True)
class RewardDecision(PublicDecision):
    pass


@dataclass(frozen=True)
class MapDecision(PublicDecision):
    pass


@dataclass(frozen=True)
class RoomDecision(PublicDecision):
    pass


@dataclass(frozen=True)
class ControlAction:
    """Control-plane request data; authorization is never copied into a public DTO."""

    binding: BridgeBinding
    action_id: str
    authorization_token: str

    def __post_init__(self) -> None:
        if not _ascii(self.action_id) or not _ascii(self.authorization_token):
            raise R0iWireError("invalid control action")


@dataclass(frozen=True)
class ActionReceipt:
    """Audit-plane result, whose family is supplied by the route, never inferred."""

    family: str
    binding: BridgeBinding
    action_id: str
    status: str
    mutation_state: str
    reason: str


@dataclass(frozen=True)
class ErrorEnvelope:
    """Audit-plane HTTP error body, separate from normal action receipts."""

    code: str
    retryable: bool
    mutation_state: str
    correlation_id: str


Decision = Union[CombatDecision, RewardDecision, MapDecision, RoomDecision]


def accepted_vector_inventory(vector_directory: Union[str, Path]) -> Tuple[int, int, str]:
    """Return the exact accepted R0i decision/receipt inventory measurement."""
    root = Path(vector_directory)
    files = sorted(
        (
            item
            for item in root.glob("*.json")
            if any(
                item.name.startswith(family + "_decision_")
                or item.name.startswith(family + "_receipt_")
                for family in _FAMILIES
            )
        ),
        key=lambda item: item.name,
    )
    records = b"".join(
        (sha256(item.read_bytes()).hexdigest() + "  " + item.name + "\n").encode("ascii")
        for item in files
    )
    return len(files), len(records), sha256(records).hexdigest()


def verify_accepted_vector_inventory(vector_directory: Union[str, Path]) -> None:
    count, byte_count, digest = accepted_vector_inventory(vector_directory)
    if (count, byte_count, digest) != (VECTOR_COUNT, 3511, VECTOR_INVENTORY_SHA256):
        raise R0iWireError("accepted R0i vector inventory does not match parser binding")


def verify_parser_manifest(manifest: ParserManifest) -> None:
    """Fail closed if a caller offers a different protocol/schema binding."""
    if not isinstance(manifest, ParserManifest) or (
        type(manifest.wire_schema) is not str or manifest.wire_schema != R0I_WIRE_SCHEMA or
        type(manifest.evidence) is not str or manifest.evidence != EVIDENCE_CLASSIFICATION or
        type(manifest.bridge_version) is not str or manifest.bridge_version != BRIDGE_VERSION or
        type(manifest.protocol) is not str or manifest.protocol != PROTOCOL or
        type(manifest.schema_version) is not int or manifest.schema_version != SCHEMA_VERSION or
        type(manifest.vector_count) is not int or manifest.vector_count != VECTOR_COUNT or
        type(manifest.vector_inventory_sha256) is not str or
        manifest.vector_inventory_sha256 != VECTOR_INVENTORY_SHA256
    ):
        raise R0iWireError("parser manifest does not match the accepted R0i binding")


def parse_decision(body: Union[bytes, str], *, binding: Optional[BridgeBinding] = None) -> Decision:
    value, source = _load(body)
    _keys(value, _decision_keys(value), "decision")
    _equal(value["schema_version"], SCHEMA_VERSION, "schema_version")
    family = _string(value["decision_kind"], "decision_kind")
    status = _string(value["status"], "status")
    if family not in _FAMILIES or status not in _DECISION_STATUSES:
        raise R0iWireError("unsupported decision family or status")
    actionable = _bool(value["actionable"], "actionable")
    decision_id = value["decision_id"]
    if status == "ready":
        if not actionable or not isinstance(decision_id, str) or not _ID.fullmatch(decision_id):
            raise R0iWireError("ready decision requires a canonical decision id")
        actual_binding: Optional[BridgeBinding] = BridgeBinding(PROTOCOL, decision_id)
        if binding is not None and binding != actual_binding:
            raise R0iWireError("decision binding mismatch")
    else:
        if actionable or decision_id is not None:
            raise R0iWireError("inactive decision must be non-actionable and unbound")
        actual_binding = None
        if binding is not None:
            raise R0iWireError("inactive decision cannot have a binding")
    _validate_family_decision(value, family, status)
    decision_type = {
        "combat": CombatDecision,
        "reward": RewardDecision,
        "map": MapDecision,
        "room": RoomDecision,
    }[family]
    fields = _freeze_mapping({key: item for key, item in value.items() if key not in _DECISION_COMMON})
    result = decision_type(family, status, actionable, actual_binding, fields)
    if encode_decision(result) != source:
        raise R0iWireError("decision is not in the canonical R0i wire encoding")
    return result


def encode_decision(decision: Decision) -> bytes:
    if not isinstance(decision, PublicDecision):
        raise R0iWireError("invalid public decision DTO")
    if decision.family not in _FAMILIES or decision.status not in _DECISION_STATUSES or type(decision.actionable) is not bool:
        raise R0iWireError("invalid decision DTO")
    if decision.status == "ready" and not isinstance(decision.binding, BridgeBinding):
        raise R0iWireError("ready decision lacks bridge binding")
    if decision.status != "ready" and decision.binding is not None:
        raise R0iWireError("inactive decision has bridge binding")
    value: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": decision.status,
        "decision_kind": decision.family,
        "actionable": decision.actionable,
        "decision_id": decision.binding.decision_id if decision.binding is not None else None,
    }
    value.update(_thaw(decision.fields))
    _validate_decision_common(value, decision.family, decision.status)
    _validate_family_decision(value, decision.family, decision.status)
    return _encode(value)


def parse_receipt(
    body: Union[bytes, str], *, family: str, binding: Optional[BridgeBinding] = None
) -> ActionReceipt:
    if family not in _FAMILIES:
        raise R0iWireError("receipt family must be explicit and supported")
    value, source = _load(body)
    _keys(value, ("schema_version", "status", "mutation_state", "decision_id", "action_id", "reason"), "receipt")
    _equal(value["schema_version"], SCHEMA_VERSION, "schema_version")
    decision_id = _string(value["decision_id"], "decision_id")
    actual_binding = BridgeBinding(PROTOCOL, decision_id)
    if binding is not None and binding != actual_binding:
        raise R0iWireError("receipt binding mismatch")
    action_id = _string(value["action_id"], "action_id")
    status = _string(value["status"], "status")
    mutation_state = _string(value["mutation_state"], "mutation_state")
    reason = _string(value["reason"], "reason")
    _validate_receipt_values(family, action_id, status, mutation_state, reason)
    receipt = ActionReceipt(family, actual_binding, action_id, status, mutation_state, reason)
    if encode_receipt(receipt) != source:
        raise R0iWireError("receipt is not in the canonical R0i wire encoding")
    return receipt


def encode_receipt(receipt: ActionReceipt) -> bytes:
    if not isinstance(receipt, ActionReceipt) or receipt.family not in _FAMILIES or not isinstance(receipt.binding, BridgeBinding):
        raise R0iWireError("receipt family must be explicit and supported")
    _validate_receipt_values(receipt.family, receipt.action_id, receipt.status, receipt.mutation_state, receipt.reason)
    return _encode(
        {
            "schema_version": SCHEMA_VERSION,
            "status": receipt.status,
            "mutation_state": receipt.mutation_state,
            "decision_id": receipt.binding.decision_id,
            "action_id": receipt.action_id,
            "reason": receipt.reason,
        }
    )


def parse_error_envelope(body: Union[bytes, str]) -> ErrorEnvelope:
    value, source = _load(body)
    _keys(value, ("schema_version", "code", "retryable", "mutation_state", "correlation_id"), "error envelope")
    _equal(value["schema_version"], SCHEMA_VERSION, "schema_version")
    code = _string(value["code"], "code")
    retryable = _bool(value["retryable"], "retryable")
    mutation_state = _string(value["mutation_state"], "mutation_state")
    correlation_id = _string(value["correlation_id"], "correlation_id")
    _validate_error_values(code, retryable, mutation_state, correlation_id)
    result = ErrorEnvelope(code, retryable, mutation_state, correlation_id)
    if encode_error_envelope(result) != source:
        raise R0iWireError("error envelope is not in the canonical R0i wire encoding")
    return result


def encode_error_envelope(error: ErrorEnvelope) -> bytes:
    if not isinstance(error, ErrorEnvelope):
        raise R0iWireError("invalid error envelope DTO")
    _validate_error_values(error.code, error.retryable, error.mutation_state, error.correlation_id)
    return _encode({"schema_version": SCHEMA_VERSION, "code": error.code, "retryable": error.retryable,
                    "mutation_state": error.mutation_state, "correlation_id": error.correlation_id})


_DECISION_COMMON = ("schema_version", "status", "decision_kind", "actionable", "decision_id")
_FAMILY_FIELDS = {
    "combat": ("round", "player", "enemies", "hand", "legal_actions", "outcome"),
    "reward": ("decision_revision", "screen_kind", "player", "rewards", "legal_actions"),
    "map": ("screen_kind", "destination", "candidates", "legal_actions"),
    "room": ("screen_kind", "phase", "room_ordinal", "candidates", "legal_actions"),
}


def _decision_keys(value: Mapping[str, Any]) -> Tuple[str, ...]:
    family = value.get("decision_kind")
    if family not in _FAMILIES:
        raise R0iWireError("decision_kind must select an R0i family")
    keys = list(_DECISION_COMMON)
    for field in _FAMILY_FIELDS[family]:
        if family == "reward" and field == "decision_revision" and value.get("status") != "ready":
            continue
        if family == "combat" and field == "outcome" and value.get("status") != "complete":
            continue
        keys.append(field)
    return tuple(keys)


def _validate_family_decision(value: Mapping[str, Any], family: str, status: str) -> None:
    _keys(value, _decision_keys(value), "decision")
    if family == "combat":
        _integer(value["round"], "round", minimum=0)
        player = _nullable_object(value["player"], "player", ("hp", "max_hp", "block", "energy"))
        if player is not None:
            _nonnegative_fields(player, "player")
        _objects(value["enemies"], ("index", "id", "hp", "max_hp", "block", "intents"), "enemies")
        _objects(value["hand"], ("hand_index", "id", "type", "cost", "target_type", "playable"), "hand")
        _objects(value["legal_actions"], ("action_id", "kind", "hand_index", "target_index"), "legal_actions")
        for index, enemy in enumerate(value["enemies"]):
            _integer(enemy["index"], "enemy index", minimum=0)
            if enemy["index"] != index:
                raise R0iWireError("enemy indexes must be stable")
            _string(enemy["id"], "enemy id")
            _integer(enemy["hp"], "enemy hp", minimum=0)
            _integer(enemy["max_hp"], "enemy max_hp", minimum=0)
            _integer(enemy["block"], "enemy block", minimum=0)
            _strings(enemy["intents"], "enemy intents")
            if len(enemy["intents"]) > 8:
                raise R0iWireError("too many enemy intents")
        for index, card in enumerate(value["hand"]):
            _integer(card["hand_index"], "hand index", minimum=0)
            if card["hand_index"] != index:
                raise R0iWireError("hand indexes must be stable")
            for key in ("id", "type", "cost", "target_type"):
                _string(card[key], "card " + key)
            _bool(card["playable"], "card playable")
        for action in value["legal_actions"]:
            action_id = _string(action["action_id"], "action id")
            _validate_action_id("combat", action_id)
            _nullable_integer(action["hand_index"], "hand_index")
            _nullable_integer(action["target_index"], "target_index")
            if action_id == "end_turn":
                if action["kind"] != "end_turn" or action["hand_index"] is not None or action["target_index"] is not None:
                    raise R0iWireError("invalid end-turn action linkage")
            else:
                match = _COMBAT_PLAY.fullmatch(action_id)
                assert match is not None
                hand_index = int(match.group(1))
                target_index = int(match.group(2)) if match.group(2) is not None else None
                if action["kind"] != "play_card" or action["hand_index"] != hand_index or action["target_index"] != target_index or hand_index >= len(value["hand"]) or target_index is not None and target_index >= len(value["enemies"]):
                    raise R0iWireError("invalid combat action linkage")
        outcome = value.get("outcome")
        _nullable_string(outcome, "outcome")
        if status in ("waiting", "unsupported"):
            if value["round"] != 0 or value["player"] is not None or any(value[key] for key in ("enemies", "hand", "legal_actions")):
                raise R0iWireError("invalid inactive combat decision")
        elif status == "complete":
            if value["round"] < 1 or player is None or player["max_hp"] < 1 or player["hp"] > player["max_hp"] or len(value["enemies"]) > 6 or value["outcome"] not in ("victory", "defeat") or value["hand"] or value["legal_actions"]:
                raise R0iWireError("invalid completed combat decision")
            if value["outcome"] == "victory" and (player["hp"] < 1 or value["enemies"]):
                raise R0iWireError("invalid victory combat decision")
            if value["outcome"] == "defeat" and player["hp"] != 0:
                raise R0iWireError("invalid defeat combat decision")
            for enemy in value["enemies"]:
                if enemy["hp"] < 1 or enemy["hp"] > enemy["max_hp"]:
                    raise R0iWireError("invalid completed combat enemy")
        elif value["round"] < 1 or player is None or "outcome" in value or len(value["enemies"]) > 6 or len(value["hand"]) > 10 or len(value["legal_actions"]) > 64:
            raise R0iWireError("invalid ready combat decision")
    elif family == "reward":
        _string(value["screen_kind"], "screen_kind")
        player = _nullable_object(value["player"], "player", ("hp", "max_hp", "gold", "deck_count"))
        if player is not None:
            _nonnegative_fields(player, "reward player")
            if player["max_hp"] < 1 or player["hp"] < 1 or player["hp"] > player["max_hp"] or player["deck_count"] < 1:
                raise R0iWireError("invalid reward player")
        _objects(value["rewards"], ("reward_slot", "reward_index", "kind", "successfully_selected", "gold_amount", "cards", "card_selection_can_skip"), "rewards")
        _objects(value["legal_actions"], ("action_id", "kind", "reward_slot", "card_slot"), "legal_actions")
        for index, reward in enumerate(value["rewards"]):
            _integer(reward["reward_slot"], "reward slot", minimum=0)
            if reward["reward_slot"] != index or reward["kind"] not in ("gold", "card", "unsupported"):
                raise R0iWireError("invalid reward candidate")
            _integer(reward["reward_index"], "reward index", minimum=0)
            _bool(reward["successfully_selected"], "reward selected")
            _nullable_integer(reward["gold_amount"], "gold amount")
            _strings(reward["cards"], "reward cards")
            _bool(reward["card_selection_can_skip"], "reward can skip")
            if len(reward["cards"]) > 5 or index and reward["reward_index"] <= value["rewards"][index - 1]["reward_index"]:
                raise R0iWireError("invalid reward ordering")
            if reward["kind"] == "gold" and (reward["gold_amount"] is None or reward["cards"] or reward["card_selection_can_skip"]):
                raise R0iWireError("invalid gold reward")
            if reward["kind"] == "card" and (reward["gold_amount"] is not None or not reward["cards"]):
                raise R0iWireError("invalid card reward")
            if reward["kind"] == "unsupported" and (reward["gold_amount"] is not None or reward["cards"] or reward["card_selection_can_skip"]):
                raise R0iWireError("invalid unsupported reward")
        for action in value["legal_actions"]:
            action_id = _string(action["action_id"], "action id")
            _validate_action_id("reward", action_id)
            _nullable_integer(action["reward_slot"], "reward_slot")
            _nullable_integer(action["card_slot"], "card_slot")
            expected_kind, reward_slot, card_slot = _reward_action_shape(action_id)
            if (action["kind"], action["reward_slot"], action["card_slot"]) != (expected_kind, reward_slot, card_slot):
                raise R0iWireError("invalid reward action linkage")
        if status == "ready":
            _integer(value["decision_revision"], "decision_revision", minimum=0)
            if player is None or value["screen_kind"] not in ("rewards", "card_reward") or len(value["rewards"]) > 8:
                raise R0iWireError("invalid ready reward decision")
            _validate_reward_legal_actions(value)
        elif status in ("waiting", "unsupported"):
            if value["screen_kind"] != "unknown" or player is not None or value["rewards"] or value["legal_actions"]:
                raise R0iWireError("invalid inactive reward decision")
        elif value["screen_kind"] != "map" or player is None or value["rewards"] or value["legal_actions"]:
            raise R0iWireError("invalid completed reward decision")
    elif family == "map":
        _string(value["screen_kind"], "screen_kind")
        destination = _nullable_object(value["destination"], "destination", ("candidate_index", "col", "row", "kind"))
        if destination is not None:
            _map_candidate(destination, "destination")
        _objects(value["candidates"], ("candidate_index", "col", "row", "kind"), "candidates")
        _objects(value["legal_actions"], ("action_id", "kind", "candidate_index"), "legal_actions")
        for index, candidate in enumerate(value["candidates"]):
            _map_candidate(candidate, "map candidate")
            if candidate["candidate_index"] != index:
                raise R0iWireError("map candidate indexes must be stable")
        for action_index, action in enumerate(value["legal_actions"]):
            action_id = _string(action["action_id"], "action id")
            _validate_action_id("map", action_id)
            _integer(action["candidate_index"], "candidate index", minimum=0)
            if action["kind"] != "select_map_node" or action_id != "select:" + str(action["candidate_index"]) or action["candidate_index"] != action_index:
                raise R0iWireError("invalid map action kind")
        if status in ("waiting", "unsupported"):
            if value["screen_kind"] != "unknown" or destination is not None or value["candidates"] or value["legal_actions"]:
                raise R0iWireError("invalid inactive map decision")
        elif status == "complete":
            if value["screen_kind"] != "room" or destination is None or value["candidates"] or value["legal_actions"]:
                raise R0iWireError("invalid completed map decision")
        elif value["screen_kind"] != "map" or destination is not None or not value["candidates"] or len(value["candidates"]) > 8 or len(value["candidates"]) != len(value["legal_actions"]):
            raise R0iWireError("invalid ready map decision")
    else:
        _string(value["screen_kind"], "screen_kind")
        _string(value["phase"], "phase")
        if value["room_ordinal"] is not None:
            if _integer(value["room_ordinal"], "room_ordinal", minimum=0) > 999:
                raise R0iWireError("room ordinal exceeds bridge bound")
        _objects(value["candidates"], ("candidate_index", "action_id", "kind", "stable_id", "enabled", "supported", "is_proceed", "is_dangerous"), "candidates")
        _objects(value["legal_actions"], ("action_id", "kind", "candidate_index"), "legal_actions")
        for index, candidate in enumerate(value["candidates"]):
            _integer(candidate["candidate_index"], "room candidate index", minimum=0)
            if candidate["candidate_index"] != index or candidate["kind"] not in ("rest_heal", "rest_unsupported", "event_option", "proceed"):
                raise R0iWireError("invalid room candidate")
            for key in ("action_id", "stable_id"):
                _string(candidate[key], "room " + key)
            for key in ("enabled", "supported", "is_proceed", "is_dangerous"):
                _bool(candidate[key], "room " + key)
            _validate_room_candidate(candidate, value["screen_kind"], index)
        for action in value["legal_actions"]:
            action_id = _string(action["action_id"], "action id")
            _validate_action_id("room", action_id)
            _integer(action["candidate_index"], "candidate index", minimum=0)
            expected_kind = "proceed_room" if action_id == "proceed" else "choose_room_option"
            expected_index = next((item["candidate_index"] for item in value["candidates"] if item["action_id"] == action_id), None)
            if action["kind"] != expected_kind or action["candidate_index"] != expected_index:
                raise R0iWireError("invalid room action kind")
        if status == "waiting":
            if value["screen_kind"] != "unknown" or value["phase"] != "unknown" or value["room_ordinal"] is not None or value["candidates"] or value["legal_actions"]:
                raise R0iWireError("invalid waiting room decision")
        elif status == "unsupported":
            screen_kind = value["screen_kind"]
            ordinal = value["room_ordinal"]
            if value["phase"] != "unsupported" or value["candidates"] or value["legal_actions"] or not (
                screen_kind == "unknown" and ordinal is None or
                screen_kind in ("rest_site", "event") and ordinal is not None
            ):
                raise R0iWireError("invalid unsupported room decision")
        elif status == "complete":
            if value["screen_kind"] not in ("rest_site", "event") or value["phase"] != "complete" or value["room_ordinal"] is None or value["candidates"] or value["legal_actions"]:
                raise R0iWireError("invalid completed room decision")
        elif value["screen_kind"] not in ("rest_site", "event") or value["phase"] not in ("choose_option", "proceed", "choose_or_proceed") or value["room_ordinal"] is None or not value["candidates"] or len(value["candidates"]) > 8 or not value["legal_actions"] or len(value["legal_actions"]) > 8:
            raise R0iWireError("invalid ready room decision")
        elif {action["candidate_index"] for action in value["legal_actions"]} != {
            candidate["candidate_index"] for candidate in value["candidates"] if candidate["enabled"] and candidate["supported"]
        } or len({action["candidate_index"] for action in value["legal_actions"]}) != len(value["legal_actions"]):
            raise R0iWireError("incomplete room legal action set")


def _load(body: Union[bytes, str]) -> Tuple[Mapping[str, Any], bytes]:
    if isinstance(body, str):
        try:
            source = body.encode("ascii")
        except UnicodeEncodeError as error:
            raise R0iWireError("wire body must be ASCII") from error
    elif isinstance(body, bytes):
        source = body
    else:
        raise R0iWireError("wire body must be bytes or str")
    try:
        text = source.decode("ascii")
        value = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise R0iWireError("invalid JSON wire body") from error
    if not isinstance(value, dict):
        raise R0iWireError("wire body must be a JSON object")
    return value, source


def _no_duplicates(pairs: list[Tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise R0iWireError("duplicate JSON field: " + key)
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise R0iWireError("JSON constant is not allowed: " + value)


def _encode(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _keys(value: Mapping[str, Any], expected: Tuple[str, ...], name: str) -> None:
    if tuple(value.keys()) != expected:
        raise R0iWireError(name + " fields are unknown, missing, duplicated, or noncanonical")


def _equal(value: Any, expected: Any, name: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise R0iWireError("invalid " + name)


def _ascii(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 128 and all(" " <= character <= "~" for character in value)


def _string(value: Any, name: str) -> str:
    if not _ascii(value):
        raise R0iWireError("invalid " + name)
    return value


def _nullable_string(value: Any, name: str) -> None:
    if value is not None:
        _string(value, name)


def _bool(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise R0iWireError("invalid " + name)
    return value


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > 2_147_483_647:
        raise R0iWireError("invalid " + name)
    return value


def _nullable_object(value: Any, name: str, expected: Tuple[str, ...]) -> Optional[Mapping[str, Any]]:
    if value is not None:
        return _object(value, expected, name)
    return None


def _object(value: Any, expected: Tuple[str, ...], name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise R0iWireError("invalid " + name)
    _keys(value, expected, name)
    return value


def _objects(value: Any, expected: Tuple[str, ...], name: str) -> None:
    if not isinstance(value, list):
        raise R0iWireError("invalid " + name)
    for item in value:
        _object(item, expected, name)


def _nonnegative_fields(value: Mapping[str, Any], name: str) -> None:
    for key, item in value.items():
        _integer(item, name + " " + key, minimum=0)


def _nullable_integer(value: Any, name: str) -> None:
    if value is not None:
        _integer(value, name, minimum=0)


def _strings(value: Any, name: str) -> None:
    if not isinstance(value, list):
        raise R0iWireError("invalid " + name)
    for item in value:
        _string(item, name)


def _map_candidate(value: Mapping[str, Any], name: str) -> None:
    _integer(value["candidate_index"], name + " index", minimum=0)
    if _integer(value["col"], name + " col", minimum=0) > 15 or _integer(value["row"], name + " row", minimum=0) > 31:
        raise R0iWireError("invalid " + name + " coordinate")
    if value["kind"] not in ("unknown", "shop", "treasure", "rest_site", "monster", "elite", "boss", "ancient"):
        raise R0iWireError("invalid " + name + " kind")


def _validate_decision_common(value: Mapping[str, Any], family: str, status: str) -> None:
    _keys(value, _decision_keys(value), "decision")
    _equal(value["schema_version"], SCHEMA_VERSION, "schema_version")
    if value["decision_kind"] != family or value["status"] != status or type(value["actionable"]) is not bool:
        raise R0iWireError("invalid decision common fields")
    if status == "ready":
        if not value["actionable"] or not isinstance(value["decision_id"], str) or not _ID.fullmatch(value["decision_id"]):
            raise R0iWireError("invalid ready decision binding")
    elif value["actionable"] or value["decision_id"] is not None:
        raise R0iWireError("invalid inactive decision binding")


def _validate_receipt_values(family: str, action_id: str, status: str, mutation_state: str, reason: str) -> None:
    _validate_action_id(family, action_id)
    if reason not in _RECEIPT_REASONS:
        raise R0iWireError("unsupported normal receipt reason")
    if reason == "accepted":
        expected_state = "queued" if family == "combat" else "applied"
        if status != "accepted" or mutation_state != expected_state:
            raise R0iWireError("invalid accepted receipt")
    elif status != "rejected" or mutation_state != "none":
        raise R0iWireError("invalid rejected receipt")


def _validate_error_values(code: str, retryable: bool, mutation_state: str, correlation_id: str) -> None:
    if type(retryable) is not bool or code not in {
        "invalid_request", "unauthenticated", "forbidden", "unsupported_content", "read_only",
        "payload_too_large", "rate_limited", "backend_fault",
    } or mutation_state != "none" or not _CORRELATION_ID.fullmatch(correlation_id):
        raise R0iWireError("invalid error envelope")
    if (code == "rate_limited" and not retryable) or (code != "rate_limited" and code != "backend_fault" and retryable):
        raise R0iWireError("invalid error retryability")


def _validate_action_id(family: str, action_id: str) -> None:
    valid = (
        family == "combat" and (action_id == "end_turn" or _COMBAT_PLAY.fullmatch(action_id)) or
        family == "reward" and (action_id in ("skip_card", "proceed", "skip_rewards") or _REWARD_SLOT.fullmatch(action_id) or _REWARD_CHOICE.fullmatch(action_id)) or
        family == "map" and _MAP_SELECT.fullmatch(action_id) or
        family == "room" and (action_id == "proceed" or _ROOM_CHOOSE.fullmatch(action_id))
    )
    if not valid:
        raise R0iWireError("invalid " + family + " action id")


def _reward_action_shape(action_id: str) -> Tuple[str, Optional[int], Optional[int]]:
    if action_id == "skip_card":
        return "skip_card", None, None
    if action_id in ("proceed", "skip_rewards"):
        return "proceed", None, None
    slot = _REWARD_SLOT.fullmatch(action_id)
    if slot is not None:
        return ("claim_gold" if slot.group(1) == "claim" else "open_card"), int(slot.group(2)), None
    choice = _REWARD_CHOICE.fullmatch(action_id)
    assert choice is not None
    return "choose_card", None, int(choice.group(1))


def _validate_reward_legal_actions(value: Mapping[str, Any]) -> None:
    parent = value["screen_kind"] == "rewards"
    actions = value["legal_actions"]
    rewards = value["rewards"]
    if parent and not 1 <= len(actions) <= 9 or not parent and (len(rewards) != 1 or not 1 <= len(actions) <= 6):
        raise R0iWireError("invalid reward action count")
    seen_slots: set[int] = set()
    seen_cards: set[int] = set()
    seen_skip = False
    seen_proceed = False
    for action in actions:
        kind, reward_slot, card_slot = _reward_action_shape(action["action_id"])
        if kind in ("claim_gold", "open_card"):
            if not parent or reward_slot is None or reward_slot >= len(rewards) or reward_slot in seen_slots:
                raise R0iWireError("invalid parent reward action")
            reward = rewards[reward_slot]
            if reward["successfully_selected"] or (kind == "claim_gold") != (reward["kind"] == "gold"):
                raise R0iWireError("reward action does not match candidate")
            seen_slots.add(reward_slot)
        elif kind == "choose_card":
            if parent or card_slot is None or card_slot >= len(rewards[0]["cards"]) or card_slot in seen_cards:
                raise R0iWireError("invalid card choice action")
            seen_cards.add(card_slot)
        elif kind == "skip_card":
            if parent or seen_skip or not rewards[0]["card_selection_can_skip"]:
                raise R0iWireError("invalid card skip action")
            seen_skip = True
        elif kind == "proceed":
            if not parent or seen_proceed or action["action_id"] != "proceed":
                raise R0iWireError("invalid reward proceed action")
            seen_proceed = True
    if parent and not seen_proceed:
        raise R0iWireError("incomplete parent reward action set")
    if not parent and (rewards[0]["kind"] != "card" or seen_skip != rewards[0]["card_selection_can_skip"] or seen_cards != set(range(len(rewards[0]["cards"])) )):
        raise R0iWireError("incomplete card reward action set")


def _validate_room_candidate(candidate: Mapping[str, Any], screen_kind: str, index: int) -> None:
    action_id = candidate["action_id"]
    proceed = candidate["is_proceed"]
    if action_id != ("proceed" if proceed else "choose:" + str(index)) or len(candidate["stable_id"]) > 96:
        raise R0iWireError("invalid room candidate identity")
    kind = candidate["kind"]
    supported = candidate["supported"]
    dangerous = candidate["is_dangerous"]
    enabled = candidate["enabled"]
    valid_kind = (
        kind == "rest_heal" and screen_kind == "rest_site" and supported and not proceed and not dangerous or
        kind == "rest_unsupported" and screen_kind == "rest_site" and not supported and not proceed and not dangerous or
        kind == "event_option" and screen_kind == "event" and not proceed and supported == (not dangerous) or
        kind == "proceed" and screen_kind == "rest_site" and enabled and supported and proceed and not dangerous
    )
    if not valid_kind or dangerous and enabled:
        raise R0iWireError("invalid room candidate semantics")


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze(item) for key, item in value.items()})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list) or isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if value is None or type(value) in (str, int, bool):
        return value
    raise R0iWireError("unsupported public JSON value")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
