#!/usr/bin/env python3
"""Capture-off checks for the reviewed inspection-map room boundary."""
from __future__ import annotations

import json
import math
import time
from collections.abc import Callable

import apply_room_live as room
from tool_common import EXIT_INTERNAL, EXIT_MISMATCH, ToolFailure, fail

_ACKNOWLEDGED = "acknowledged"
_MAXIMUM_ACKNOWLEDGEMENT_SECONDS = 45.0


def _validated_snapshot(snapshot: object, code: str) -> dict[str, object]:
    if type(snapshot) is not bytes:
        fail(EXIT_MISMATCH, code)
    try:
        return room._validate_room(snapshot)
    except ToolFailure:
        fail(EXIT_MISMATCH, code)


def _original_action(snapshot: object) -> tuple[str, str]:
    decision = _validated_snapshot(snapshot, "original_snapshot_mismatch")
    if (
        decision["status"] != "ready"
        or decision["screen_kind"] != "rest_site"
        or decision["phase"] not in ("choose_option", "choose_or_proceed")
    ):
        fail(EXIT_MISMATCH, "original_snapshot_not_actionable")
    legal = decision["legal_actions"]
    candidates = decision["candidates"]
    if not isinstance(legal, list) or not isinstance(candidates, list):
        fail(EXIT_INTERNAL, "internal_failure")
    legal_ids = {item["action_id"] for item in legal if isinstance(item, dict)}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        action_id = candidate.get("action_id")
        if (
            candidate.get("kind") == "rest_heal"
            and candidate.get("enabled") is True
            and candidate.get("supported") is True
            and candidate.get("is_dangerous") is False
            and isinstance(action_id, str)
            and action_id in legal_ids
        ):
            decision_id = decision.get("decision_id")
            if isinstance(decision_id, str):
                return decision_id, action_id
    fail(EXIT_MISMATCH, "original_snapshot_safe_action_missing")


def _require_inspection_suppressed(snapshot: object) -> None:
    if _validated_snapshot(snapshot, "inspection_snapshot_mismatch")["status"] != "waiting":
        fail(EXIT_MISMATCH, "inspection_actions_not_suppressed")


def _stale_receipt(decision_id: str, action_id: str) -> bytes:
    return (
        b'{"schema_version":1,"status":"rejected","mutation_state":"none",'
        b'"decision_id":"' + decision_id.encode("ascii") + b'","action_id":"'
        + action_id.encode("ascii") + b'","reason":"stale_decision"}'
    )


def _callback(label: str, operation: Callable[..., object], *arguments: object) -> object:
    try:
        return operation(*arguments)
    except BaseException:
        fail(EXIT_INTERNAL, f"{label}_callback_failure")


def _clock_value(clock: Callable[[], float]) -> float:
    value = _callback("clock", clock)
    if type(value) not in (int, float) or not math.isfinite(float(value)) or value < 0:
        fail(EXIT_INTERNAL, "clock_callback_failure")
    return float(value)


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
    """Verify one original rest-heal action becomes stale after inspection.

    Every injected callback has a fixed sanitized failure code. The original
    snapshot and receipt are held only in memory and never included in output.
    """
    receipt = bytearray()
    primary_failure = False
    try:
        if (
            type(acknowledgement_seconds) not in (int, float)
            or not math.isfinite(float(acknowledgement_seconds))
            or acknowledgement_seconds <= 0
            or acknowledgement_seconds > _MAXIMUM_ACKNOWLEDGEMENT_SECONDS
        ):
            fail(EXIT_INTERNAL, "invalid_acknowledgement_timeout")
        decision_id, action_id = _original_action(original_snapshot)
        previous_time = _clock_value(clock)
        deadline = previous_time + float(acknowledgement_seconds)
        if not math.isfinite(deadline):
            fail(EXIT_INTERNAL, "clock_callback_failure")

        def check_deadline() -> None:
            nonlocal previous_time
            current_time = _clock_value(clock)
            if current_time < previous_time:
                fail(EXIT_INTERNAL, "clock_callback_failure")
            previous_time = current_time
            if current_time >= deadline:
                fail(EXIT_MISMATCH, "operator_acknowledgement_timeout")

        check_deadline()
        if _callback("acknowledgement", acknowledge) != _ACKNOWLEDGED:
            fail(EXIT_MISMATCH, "operator_acknowledgement_invalid")
        check_deadline()
        inspected = _callback("inspection_snapshot", inspection_snapshot_reader)
        check_deadline()
        if inspected == b"":
            fail(EXIT_MISMATCH, "inspection_snapshot_eof")
        _require_inspection_suppressed(inspected)
        check_deadline()
        sent = _callback("stale_action", stale_action_sender, decision_id, action_id)
        check_deadline()
        if type(sent) is not bytes:
            fail(EXIT_MISMATCH, "stale_receipt_mismatch")
        receipt.extend(sent)
        if bytes(receipt) != _stale_receipt(decision_id, action_id):
            fail(EXIT_MISMATCH, "stale_receipt_mismatch")
        return {
            "schema_version": 1, "status": "passed",
            "code": "inspection_map_stale_rejection_verified",
            "acknowledgement_count": 1, "stale_action_attempt_count": 1,
        }
    except BaseException:
        primary_failure = True
        raise
    finally:
        for index in range(len(receipt)):
            receipt[index] = 0
        if cleanup is not None:
            try:
                cleanup()
            except BaseException:
                if not primary_failure:
                    fail(EXIT_INTERNAL, "cleanup_callback_failure")


def summarize_room_result(result: object) -> dict[str, object]:
    required = {
        "schema_version", "status", "milestone", "decision_provider", "screen_kind",
        "room_ordinal", "accepted_action_count", "actions", "final", "routes_checked",
    }
    if not isinstance(result, dict) or set(result) != required:
        fail(EXIT_MISMATCH, "room_result_mismatch")
    action_count = result["accepted_action_count"]
    route_count = result["routes_checked"]
    actions = result["actions"]
    screen_kind = result["screen_kind"]
    if (
        result["schema_version"] != 1 or result["status"] != "passed"
        or result["milestone"] != "r0i_room_interaction" or result["decision_provider"] != "safe"
        or screen_kind not in ("rest_site", "event")
        or type(result["room_ordinal"]) is not int or not 0 <= result["room_ordinal"] <= 999
        or type(action_count) is not int or not 1 <= action_count <= room._MAXIMUM_ACCEPTED_ACTIONS
        or not isinstance(actions, list) or len(actions) != action_count
        or type(route_count) is not int or route_count < 3 + 2 * action_count
    ):
        fail(EXIT_MISMATCH, "room_result_mismatch")
    seen: set[str] = set()
    for action in actions:
        if not isinstance(action, dict) or set(action) != {"decision_id", "action_id", "basis", "phase"}:
            fail(EXIT_MISMATCH, "room_result_mismatch")
        decision_id, action_id = action["decision_id"], action["action_id"]
        basis, phase = action["basis"], action["phase"]
        if (
            not isinstance(decision_id, str) or not room._canonical_decision_id(decision_id)
            or decision_id in seen or not isinstance(action_id, str)
            or not room._canonical_action_id(action_id)
            or phase not in ("choose_option", "proceed", "choose_or_proceed")
        ):
            fail(EXIT_MISMATCH, "room_result_mismatch")
        seen.add(decision_id)
        valid = (
            basis == "rest_heal" and screen_kind == "rest_site" and action_id != "proceed" and phase in ("choose_option", "choose_or_proceed")
        ) or (
            basis == "proceed" and screen_kind == "rest_site" and action_id == "proceed" and phase in ("proceed", "choose_or_proceed")
        ) or (
            basis == "event_first_supported" and screen_kind == "event" and action_id != "proceed" and phase in ("choose_option", "choose_or_proceed")
        )
        if not valid:
            fail(EXIT_MISMATCH, "room_result_mismatch")
    try:
        final = room._validate_room(json.dumps(result["final"], ensure_ascii=True, separators=(",", ":")).encode("ascii"))
    except (ToolFailure, TypeError, ValueError):
        fail(EXIT_MISMATCH, "room_result_mismatch")
    if final["status"] != "complete" or final["screen_kind"] != screen_kind or final["room_ordinal"] != result["room_ordinal"]:
        fail(EXIT_MISMATCH, "room_result_mismatch")
    return {"code": "room_result_valid", "accepted_action_count": action_count, "route_count": route_count}


def summarize_run_result(result: object) -> dict[str, object]:
    """Produce an explicitly unvalidated aggregate until R0I-COMPOSE-09 lands."""
    if not isinstance(result, dict):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    floor_count, action_totals, readiness = result.get("completed_floor_count"), result.get("action_totals"), result.get("readiness")
    if (
        result.get("schema_version") != 1 or result.get("status") != "passed"
        or result.get("milestone") != "r0i_bounded_run" or type(floor_count) is not int
        or not 0 <= floor_count <= 3 or not isinstance(readiness, list) or not isinstance(action_totals, dict)
    ):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    counts = tuple(action_totals.get(name) for name in ("combat", "reward", "map", "room", "total"))
    if any(type(value) is not int or value < 0 for value in counts):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    combat, reward, map_actions, room_actions, total = counts
    if total != combat + reward + map_actions + room_actions:
        fail(EXIT_MISMATCH, "run_result_mismatch")
    return {"code": "run_result_unvalidated", "completed_floor_count": floor_count, "readiness_count": len(readiness), "action_count": total}
