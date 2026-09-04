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
    number = _finite_number(value, "clock_callback_failure")
    if number < 0:
        fail(EXIT_INTERNAL, "clock_callback_failure")
    return number


def _finite_number(value: object, code: str) -> float:
    if type(value) not in (int, float):
        fail(EXIT_INTERNAL, code)
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        fail(EXIT_INTERNAL, code)
    if not math.isfinite(number):
        fail(EXIT_INTERNAL, code)
    return number


def verify_inspection_map_rejection(
    original_snapshot: bytes,
    inspection_snapshot_reader: Callable[[], bytes],
    acknowledge: Callable[[float], object],
    stale_action_sender: Callable[[str, str], bytes],
    *,
    clock: Callable[[], float] = time.monotonic,
    acknowledgement_seconds: float = _MAXIMUM_ACKNOWLEDGEMENT_SECONDS,
    cleanup: Callable[[], None] | None = None,
) -> dict[str, object]:
    """Verify one original rest-heal action becomes stale after inspection.

    Hooks are trusted, bounded, cooperative callbacks: they must return promptly
    and must not log or retain raw data. ``acknowledge(deadline)`` receives the
    absolute deadline in the supplied clock's units and must bound any operator
    wait to it. An immediate acknowledgement after direct UI inspection is also
    supported. Checks reject late returns but cannot preempt a hanging hook,
    including cleanup; this function creates no background worker or service.

    Raised callback failures become fixed codes. The original snapshot and
    receipt are held only in memory and never included in verifier output.
    """
    receipt = bytearray()
    primary_failure = False
    try:
        timeout = _finite_number(acknowledgement_seconds, "invalid_acknowledgement_timeout")
        if not 0 < timeout <= _MAXIMUM_ACKNOWLEDGEMENT_SECONDS:
            fail(EXIT_INTERNAL, "invalid_acknowledgement_timeout")
        decision_id, action_id = _original_action(original_snapshot)
        previous_time = _clock_value(clock)
        deadline = previous_time + timeout
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
        acknowledged = _callback("acknowledgement", acknowledge, deadline)
        check_deadline()
        if type(acknowledged) is not str or acknowledged != _ACKNOWLEDGED:
            fail(EXIT_MISMATCH, "operator_acknowledgement_invalid")
        inspected = _callback("inspection_snapshot", inspection_snapshot_reader)
        check_deadline()
        if type(inspected) is bytes and not inspected:
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
        type(result["schema_version"]) is not int
        or result["schema_version"] != 1 or result["status"] != "passed"
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
    """Summarize accepted R0I-COMPOSE-09 output without validating its history.

    Only the selected schema/count fields are checked. Nested component results
    and their reconciliation are not validated here, so even complete current
    client output remains explicitly ``run_result_unvalidated``.
    """
    if not isinstance(result, dict):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    floor_count, action_totals, readiness = result.get("completed_floor_count"), result.get("action_totals"), result.get("readiness")
    if (
        type(result.get("schema_version")) is not int
        or result.get("schema_version") != 1 or result.get("status") != "passed"
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


# The run result is deliberately validated here, rather than by a live wrapper:
# this module owns no transport or controller semantics and never returns nested
# client material.  Keep these allowlists local to the result contract so a
# future producer addition requires an explicit acceptance-validator review.
_RUN_MILESTONES = frozenset(("r0i_bounded_run", "r0i_bounded_run_entry"))
_DESTINATION_KINDS = frozenset(
    ("unknown", "shop", "treasure", "rest_site", "monster", "elite", "boss", "ancient")
)
_TERMINATION_REASONS = frozenset(
    (
        "floor_limit_reached",
        "act_boundary_reached",
        "unsupported_destination_kind",
        "run_defeat",
        "room_handoff_complete",
        "room_continuation_complete",
    )
)
_ACTION_TOTAL_NAMES = ("combat", "reward", "map", "room", "total")


def _integer(value: object, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return value


def _exact_dict(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return value


def _component(value: object, milestone: str) -> dict[str, object]:
    if (
        not isinstance(value, dict)
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != 1
        or value.get("status") != "passed"
        or value.get("milestone") != milestone
    ):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return value


def _component_actions(value: object, milestone: str, maximum: int) -> int:
    return _integer(_component(value, milestone).get("accepted_action_count"), 1, maximum)


def _destination_from_map(value: object) -> str:
    map_result = _component(value, "r0g_map_selection")
    after = map_result.get("after")
    destination = after.get("destination") if isinstance(after, dict) else None
    kind = destination.get("kind") if isinstance(destination, dict) else None
    if type(kind) is not str or kind not in _DESTINATION_KINDS:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return kind


def _reward_actions(value: object) -> int:
    applied = _component(value, "r0i_reward_resolution").get("applied")
    if not isinstance(applied, list) or len(applied) > 17:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return len(applied)


def _readiness(value: object) -> None:
    item = _exact_dict(value, {"next_combat_attempts", "reward_attempts", "map_attempts"})
    for name in item:
        _integer(item[name])
    if _integer(item["reward_attempts"]) < 1 or _integer(item["map_attempts"]) < 1:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")


def _terminal_outcome(value: object) -> tuple[dict[str, object] | None, str | None, int]:
    if value is None:
        return None, None, 0
    terminal = _component(value, "r0e_complete_combat")
    outcome = terminal.get("outcome")
    if outcome not in ("victory", "defeat"):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return terminal, outcome, _component_actions(terminal, "r0e_complete_combat", 48)


def _room_handoff(value: object) -> tuple[dict[str, object] | None, int, int, int, str | None, dict[str, object] | None]:
    """Return room, combat, and map contributions plus continuation facts."""
    if value is None:
        return None, 0, 0, 0, None, None
    if not isinstance(value, dict):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    required = {"after_floor", "destination_kind", "expected_screen_kind", "preflight", "room", "map_attempts"}
    optional = {"post_room_map", "next_combat_attempts", "next_combat"}
    if not required.issubset(value) or set(value) - required - optional:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    after_floor = _integer(value["after_floor"], 1, 3)
    kind = value["destination_kind"]
    screen = value["expected_screen_kind"]
    if type(kind) is not str or kind not in _DESTINATION_KINDS or screen not in ("rest_site", "event"):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    preflight = _exact_dict(value["preflight"], {"attempts", "screen_kind", "room_ordinal"})
    if _integer(preflight["attempts"], 1) < 1 or preflight["screen_kind"] != screen:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    _integer(preflight["room_ordinal"], 0, 999)
    room_result = _component(value["room"], "r0i_room_interaction")
    room_actions = _component_actions(room_result, "r0i_room_interaction", 12)
    if room_result.get("screen_kind") != screen or room_result.get("room_ordinal") != preflight["room_ordinal"]:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    _integer(value["map_attempts"], 1)
    post_map = value.get("post_room_map")
    next_combat = value.get("next_combat")
    if (post_map is None) != (next_combat is None):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if post_map is None:
        if "next_combat_attempts" in value:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        return value, room_actions, 0, 0, None, None
    post_kind = _destination_from_map(post_map)
    _integer(value.get("next_combat_attempts"), 1)
    continuation = _component(next_combat, "r0e_complete_combat")
    continuation_actions = _component_actions(continuation, "r0e_complete_combat", 48)
    outcome = continuation.get("outcome")
    if outcome not in ("victory", "defeat"):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return value, room_actions, 1, continuation_actions, post_kind, continuation


def summarize_run_acceptance_result(result: object) -> dict[str, object]:
    """Validate a bounded-run result and return its minimal safe aggregate.

    The input is retained only while this function executes.  The returned
    dictionary intentionally cannot contain provider names, nested component
    records, identities, payloads, hashes, or arbitrary producer text.
    """
    if not isinstance(result, dict):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    milestone = result.get("milestone")
    if milestone not in _RUN_MILESTONES:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    common = {
        "schema_version", "status", "milestone", "providers", "floor_limit",
        "completed_floor_count", "action_totals", "readiness", "floors",
        "terminal_combat", "room_handoff", "termination",
    }
    entry_only = {"entry_phase", "processed_floor_count", "entry_prefix"}
    expected = common | (entry_only if milestone == "r0i_bounded_run_entry" else set())
    if (
        set(result) != expected
        or type(result.get("schema_version")) is not int
        or result.get("schema_version") != 1
        or result.get("status") != "passed"
    ):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    floor_limit = _integer(result["floor_limit"], 1, 3)
    providers = _exact_dict(result["providers"], {"combat", "reward", "map", "room"})
    if any(type(item) is not str or not item for item in providers.values()):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    floors = result["floors"]
    readiness = result["readiness"]
    if not isinstance(floors, list) or not isinstance(readiness, list) or len(readiness) != len(floors):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    completed = _integer(result["completed_floor_count"], 0, floor_limit)
    if completed != len(floors):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    expected_floor = 1 if milestone == "r0i_bounded_run" else 2
    combat_actions = reward_actions = 0
    for floor, ready in zip(floors, readiness):
        item = _exact_dict(floor, {"floor_number", "destination_kind", "combat", "reward", "map"})
        if _integer(item["floor_number"], 1, 3) != expected_floor:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        expected_floor += 1
        kind = item["destination_kind"]
        if type(kind) is not str or kind not in _DESTINATION_KINDS or _destination_from_map(item["map"]) != kind:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        combat = _component(item["combat"], "r0e_complete_combat")
        if combat.get("outcome") != "victory":
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        combat_actions += _component_actions(combat, "r0e_complete_combat", 48)
        reward_actions += _reward_actions(item["reward"])
        _readiness(ready)

    prefix_reward_actions = 0
    prefix_map_actions = 0
    processed: int
    entry_phase = "combat"
    if milestone == "r0i_bounded_run_entry":
        entry_phase = result["entry_phase"]
        prefix = _exact_dict(
            result["entry_prefix"],
            {"floor_number", "destination_kind", "observed_phases", "unavailable_phases", "combat", "reward", "map", "readiness"},
        )
        if entry_phase not in ("reward", "map") or _integer(prefix["floor_number"], 1, 1) != 1:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        prefix_kind = prefix["destination_kind"]
        if type(prefix_kind) is not str or prefix_kind not in _DESTINATION_KINDS or _destination_from_map(prefix["map"]) != prefix_kind:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if prefix["combat"] is not None:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        expected_observed = ["reward", "map"] if entry_phase == "reward" else ["map"]
        expected_unavailable = ["combat"] if entry_phase == "reward" else ["combat", "reward"]
        if prefix["observed_phases"] != expected_observed or prefix["unavailable_phases"] != expected_unavailable:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if entry_phase == "reward":
            prefix_reward_actions = _reward_actions(prefix["reward"])
        elif prefix["reward"] is not None:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        prefix_ready = _exact_dict(prefix["readiness"], {"next_combat_attempts", "reward_attempts", "map_attempts"})
        if _integer(prefix_ready["next_combat_attempts"]) != 0:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if entry_phase == "reward" and (
            _integer(prefix_ready["reward_attempts"]) != 0
            or _integer(prefix_ready["map_attempts"], 1) < 1
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if entry_phase == "map" and (
            _integer(prefix_ready["reward_attempts"]) != 0
            or _integer(prefix_ready["map_attempts"]) != 0
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        prefix_map_actions = 1
        processed = _integer(result["processed_floor_count"], 1, floor_limit)
    else:
        processed = 0

    handoff, room_actions, handoff_maps, continuation_actions, handoff_kind, continuation = _room_handoff(result["room_handoff"])
    terminal, terminal_outcome, terminal_actions = _terminal_outcome(result["terminal_combat"])
    if terminal is not None and continuation is not None:
        if terminal != continuation or terminal_outcome != continuation.get("outcome") or terminal_actions != continuation_actions:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        terminal_actions = 0  # The terminal is the same accepted continuation action trace.
    computed_map_actions = len(floors) + prefix_map_actions + handoff_maps
    if milestone == "r0i_bounded_run":
        processed = computed_map_actions
    if processed != computed_map_actions or processed > floor_limit:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    totals = _exact_dict(result["action_totals"], set(_ACTION_TOTAL_NAMES))
    computed = {
        "combat": combat_actions + continuation_actions + terminal_actions,
        "reward": reward_actions + prefix_reward_actions,
        "map": computed_map_actions,
        "room": room_actions,
    }
    computed["total"] = sum(computed.values())
    if any(_integer(totals[name]) != computed[name] for name in _ACTION_TOTAL_NAMES):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    termination = _exact_dict(result["termination"], {"reason", "after_floor", "destination_kind"})
    reason, after_floor, destination = termination["reason"], _integer(termination["after_floor"], 0, floor_limit), termination["destination_kind"]
    if reason not in _TERMINATION_REASONS or (destination is not None and (type(destination) is not str or destination not in _DESTINATION_KINDS)):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if reason == "run_defeat":
        expected_after_floor = processed if continuation is None else processed - 1
        if (
            destination is not None
            or terminal_outcome != "defeat"
            or after_floor != expected_after_floor
            or (continuation is not None and terminal != continuation)
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif terminal is not None:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if reason == "floor_limit_reached":
        if destination is None or after_floor != floor_limit or processed != floor_limit:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif reason in ("act_boundary_reached", "unsupported_destination_kind"):
        if destination is None or after_floor != processed or processed >= floor_limit:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif reason == "room_handoff_complete":
        if (
            handoff is None
            or continuation is not None
            or destination != handoff.get("destination_kind")
            or after_floor != handoff.get("after_floor")
            or after_floor != processed
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif reason == "room_continuation_complete":
        if (
            handoff is None
            or continuation is None
            or continuation.get("outcome") != "victory"
            or destination != handoff_kind
            or after_floor != handoff.get("after_floor")
            or after_floor + 1 != processed
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return {
        "schema_version": 1,
        "status": "passed",
        "milestone": "r0i_bounded_run_acceptance",
        "source_milestone": milestone,
        "entry_phase": entry_phase,
        "processed_floor_count": processed,
        "completed_floor_count": completed,
        "action_totals": computed,
        "termination": {"reason": reason, "after_floor": after_floor, "destination_kind": destination},
        "terminal_combat_outcome": terminal_outcome,
    }
