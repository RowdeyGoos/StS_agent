#!/usr/bin/env python3
"""Capture-off checks for the reviewed inspection-map room boundary.

This module deliberately has no command that can discover an endpoint, identity,
configuration, or credential.  Callers retain snapshots in their own process and
inject the three transient operations needed for one bounded verification.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable

from tool_common import EXIT_INTERNAL, EXIT_MISMATCH, fail

_ACKNOWLEDGED = "acknowledged"
_MAXIMUM_ACKNOWLEDGEMENT_SECONDS = 45.0
_LOWER_HEX = frozenset("0123456789abcdef")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _decode_snapshot(snapshot: bytes, code: str) -> dict[str, object]:
    try:
        value = json.loads(
            snapshot.decode("ascii"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constant")),
        )
    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, code)
    if not isinstance(value, dict):
        fail(EXIT_MISMATCH, code)
    return value


def _decision_id(value: object) -> str | None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _LOWER_HEX for character in value)
    ):
        return None
    return value


def _original_action(snapshot: bytes) -> tuple[str, str]:
    value = _decode_snapshot(snapshot, "original_snapshot_mismatch")
    expected = {
        "schema_version",
        "status",
        "decision_kind",
        "actionable",
        "decision_id",
        "screen_kind",
        "phase",
        "room_ordinal",
        "candidates",
        "legal_actions",
    }
    if (
        set(value) != expected
        or value.get("schema_version") != 1
        or value.get("status") != "ready"
        or value.get("decision_kind") != "room"
        or value.get("actionable") is not True
    ):
        fail(EXIT_MISMATCH, "original_snapshot_not_actionable")
    decision_id = _decision_id(value.get("decision_id"))
    candidates = value.get("candidates")
    legal_actions = value.get("legal_actions")
    if decision_id is None or not isinstance(candidates, list) or not isinstance(legal_actions, list):
        fail(EXIT_MISMATCH, "original_snapshot_mismatch")
    legal_ids = {
        item.get("action_id")
        for item in legal_actions
        if isinstance(item, dict) and isinstance(item.get("action_id"), str)
    }
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        action_id = candidate.get("action_id")
        if (
            candidate.get("kind") == "rest_heal"
            and candidate.get("enabled") is True
            and candidate.get("supported") is True
            and isinstance(action_id, str)
            and action_id in legal_ids
        ):
            return decision_id, action_id
    fail(EXIT_MISMATCH, "original_snapshot_safe_action_missing")


def _require_inspection_suppressed(snapshot: bytes) -> None:
    value = _decode_snapshot(snapshot, "inspection_snapshot_mismatch")
    if (
        set(value)
        != {
            "schema_version", "status", "decision_kind", "actionable", "decision_id",
            "screen_kind", "phase", "room_ordinal", "candidates", "legal_actions",
        }
        or value.get("schema_version") != 1
        or value.get("status") != "waiting"
        or value.get("decision_kind") != "room"
        or value.get("actionable") is not False
        or value.get("decision_id") is not None
        or value.get("screen_kind") != "unknown"
        or value.get("phase") != "unknown"
        or value.get("room_ordinal") is not None
        or value.get("candidates") != []
        or value.get("legal_actions") != []
    ):
        fail(EXIT_MISMATCH, "inspection_actions_not_suppressed")


def _stale_receipt(decision_id: str, action_id: str) -> bytes:
    return (
        b'{"schema_version":1,"status":"rejected","mutation_state":"none",'
        b'"decision_id":"' + decision_id.encode("ascii") + b'","action_id":"'
        + action_id.encode("ascii") + b'","reason":"stale_decision"}'
    )


def _within_deadline(clock: Callable[[], float], deadline: float) -> None:
    if clock() >= deadline:
        fail(EXIT_MISMATCH, "operator_acknowledgement_timeout")


def verify_inspection_map_rejection(
    original_snapshot: bytes,
    inspection_snapshot_reader: Callable[[], bytes],
    acknowledge: Callable[[], object],
    stale_action_sender: Callable[[str, str], bytes],
    *,
    clock: Callable[[], float] = time.monotonic,
    acknowledgement_seconds: float = _MAXIMUM_ACKNOWLEDGEMENT_SECONDS,
    cleanup: Callable[[], None] | None = None,
) -> dict[str, object]:
    """Verify one original action becomes stale while an inspection map is open.

    The original snapshot is only inspected in memory.  The verifier calls
    ``stale_action_sender`` exactly once after an exact acknowledgement and never
    logs snapshots, IDs, receipts, or callback data.
    """
    if (
        type(acknowledgement_seconds) not in (int, float)
        or acknowledgement_seconds <= 0
        or acknowledgement_seconds > _MAXIMUM_ACKNOWLEDGEMENT_SECONDS
    ):
        fail(EXIT_INTERNAL, "internal_failure")
    receipt = bytearray()
    try:
        decision_id, action_id = _original_action(original_snapshot)
        deadline = clock() + float(acknowledgement_seconds)
        _within_deadline(clock, deadline)
        if acknowledge() != _ACKNOWLEDGED:
            fail(EXIT_MISMATCH, "operator_acknowledgement_invalid")
        _within_deadline(clock, deadline)
        inspection_snapshot = inspection_snapshot_reader()
        if not isinstance(inspection_snapshot, bytes) or not inspection_snapshot:
            fail(EXIT_MISMATCH, "inspection_snapshot_eof")
        _require_inspection_suppressed(inspection_snapshot)
        _within_deadline(clock, deadline)
        sent = stale_action_sender(decision_id, action_id)
        if not isinstance(sent, bytes):
            fail(EXIT_MISMATCH, "stale_receipt_mismatch")
        receipt.extend(sent)
        if bytes(receipt) != _stale_receipt(decision_id, action_id):
            fail(EXIT_MISMATCH, "stale_receipt_mismatch")
        _within_deadline(clock, deadline)
        return {
            "schema_version": 1,
            "status": "passed",
            "code": "inspection_map_stale_rejection_verified",
            "acknowledgement_count": 1,
            "stale_action_attempt_count": 1,
        }
    finally:
        for index in range(len(receipt)):
            receipt[index] = 0
        if cleanup is not None:
            cleanup()


def summarize_room_result(result: object) -> dict[str, object]:
    if not isinstance(result, dict):
        fail(EXIT_MISMATCH, "room_result_mismatch")
    action_count = result.get("accepted_action_count")
    route_count = result.get("routes_checked")
    if (
        result.get("schema_version") != 1
        or result.get("status") != "passed"
        or result.get("milestone") != "r0i_room_interaction"
        or type(action_count) is not int
        or action_count < 1
        or type(route_count) is not int
        or route_count < 1
    ):
        fail(EXIT_MISMATCH, "room_result_mismatch")
    return {
        "code": "room_result_valid",
        "accepted_action_count": action_count,
        "route_count": route_count,
    }


def summarize_run_result(result: object) -> dict[str, object]:
    if not isinstance(result, dict):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    floor_count = result.get("completed_floor_count")
    action_totals = result.get("action_totals")
    readiness = result.get("readiness")
    if (
        result.get("schema_version") != 1
        or result.get("status") != "passed"
        or result.get("milestone") != "r0i_bounded_run"
        or type(floor_count) is not int
        or floor_count < 0
        or not isinstance(readiness, list)
        or not isinstance(action_totals, dict)
    ):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    counts = tuple(action_totals.get(name) for name in ("combat", "reward", "map", "room", "total"))
    if any(type(value) is not int or value < 0 for value in counts):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    combat, reward, map_actions, room, total = counts
    if total != combat + reward + map_actions + room:
        fail(EXIT_MISMATCH, "run_result_mismatch")
    return {
        "code": "run_result_valid",
        "completed_floor_count": floor_count,
        "readiness_count": len(readiness),
        "action_count": total,
    }
