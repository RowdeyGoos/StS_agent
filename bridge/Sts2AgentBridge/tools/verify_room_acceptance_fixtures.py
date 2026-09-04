#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import inspect
from collections.abc import Callable

import apply_room_live_fixtures as room_fixture
import apply_run_live_fixtures as run_fixture
import verify_room_acceptance as acceptance
from tool_common import EXIT_INTERNAL, EXIT_MISMATCH, ToolFailure, fail, main

_DECISION = "0" * 64


def _encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _original() -> bytes:
    candidate = {"candidate_index": 0, "action_id": "choose:0", "kind": "rest_heal", "stable_id": "HEAL", "enabled": True, "supported": True, "is_proceed": False, "is_dangerous": False}
    return _encode({"schema_version": 1, "status": "ready", "decision_kind": "room", "actionable": True, "decision_id": _DECISION, "screen_kind": "rest_site", "phase": "choose_option", "room_ordinal": 4, "candidates": [candidate], "legal_actions": [{"action_id": "choose:0", "kind": "choose_room_option", "candidate_index": 0}]})


def _inspection() -> bytes:
    return _encode({"schema_version": 1, "status": "waiting", "decision_kind": "room", "actionable": False, "decision_id": None, "screen_kind": "unknown", "phase": "unknown", "room_ordinal": None, "candidates": [], "legal_actions": []})


def _receipt(decision_id: str, action_id: str) -> bytes:
    return _encode({"schema_version": 1, "status": "rejected", "mutation_state": "none", "decision_id": decision_id, "action_id": action_id, "reason": "stale_decision"})


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _expect(operation: Callable[[], object], exit_code: int, code: str) -> None:
    try:
        operation()
    except ToolFailure as error:
        if error.exit_code == exit_code and error.error_code == code:
            return
        fail(EXIT_MISMATCH, "acceptance_fixture_wrong_failure")
    fail(EXIT_MISMATCH, "acceptance_fixture_unexpected_success")


def _verify(
    *,
    original: bytes | None = None,
    inspected: Callable[[], bytes] = _inspection,
    acknowledgement: Callable[[], object] = lambda: "acknowledged",
    sender: Callable[[str, str], bytes] = _receipt,
    clock: Callable[[], float] | None = None,
    acknowledgement_seconds: float = 45.0,
    cleanup: Callable[[], None] | None = None,
) -> tuple[dict[str, object], list[tuple[str, str]], list[str]]:
    attempts: list[tuple[str, str]] = []
    cleaned: list[str] = []
    def send(decision_id: str, action_id: str) -> bytes:
        attempts.append((decision_id, action_id))
        return sender(decision_id, action_id)
    result = acceptance.verify_inspection_map_rejection(
        _original() if original is None else original, inspected, acknowledgement, send,
        clock=_Clock() if clock is None else clock,
        acknowledgement_seconds=acknowledgement_seconds,
        cleanup=lambda: (cleaned.append("done"), cleanup())[1] if cleanup else cleaned.append("done"),
    )
    return result, attempts, cleaned


def _bad_original(value: object, expected: str = "original_snapshot_mismatch") -> None:
    attempts: list[tuple[str, str]] = []
    cleaned: list[str] = []
    _expect(
        lambda: acceptance.verify_inspection_map_rejection(value, _inspection, lambda: "acknowledged", lambda *args: attempts.append(args) or _receipt(*args), cleanup=lambda: cleaned.append("done")),
        EXIT_MISMATCH, expected,
    )
    if attempts or cleaned != ["done"]:
        fail(EXIT_MISMATCH, "acceptance_fixture_bad_precondition_post")


def _success_and_snapshots() -> None:
    result, attempts, cleaned = _verify()
    if result != {"schema_version": 1, "status": "passed", "code": "inspection_map_stale_rejection_verified", "acknowledgement_count": 1, "stale_action_attempt_count": 1} or attempts != [(_DECISION, "choose:0")] or cleaned != ["done"] or any(value in json.dumps(result) for value in (_DECISION, "choose:0", "HEAL")):
        fail(EXIT_MISMATCH, "acceptance_fixture_success_or_privacy")
    for mutate in (
        lambda value: value["candidates"][0].update({"is_dangerous": True}),
        lambda value: value.update({"schema_version": True}),
        lambda value: value.update({"screen_kind": "event", "room_ordinal": -1}),
        lambda value: value["legal_actions"][0].update({"kind": "proceed_room"}),
        lambda value: value["legal_actions"][0].update({"candidate_index": 1}),
    ):
        value = json.loads(_original())
        mutate(value)
        _bad_original(_encode(value))
    _bad_original(_inspection(), "original_snapshot_not_actionable")
    _expect(lambda: _verify(inspected=lambda: b"")[0], EXIT_MISMATCH, "inspection_snapshot_eof")
    _expect(lambda: _verify(inspected=_original)[0], EXIT_MISMATCH, "inspection_actions_not_suppressed")


def _callbacks_cleanup_and_receipts() -> None:
    _expect(lambda: _verify(acknowledgement=lambda: "partial")[0], EXIT_MISMATCH, "operator_acknowledgement_invalid")
    clock = _Clock()
    _expect(lambda: _verify(acknowledgement=lambda: setattr(clock, "now", 46.0) or "acknowledged", clock=clock)[0], EXIT_MISMATCH, "operator_acknowledgement_timeout")
    clock = _Clock()
    _expect(lambda: _verify(sender=lambda decision, action: setattr(clock, "now", 46.0) or _receipt(decision, action), clock=clock)[0], EXIT_MISMATCH, "operator_acknowledgement_timeout")
    for seconds in (math.nan, math.inf, -1.0, True):
        _bad_timeout(seconds)
    _expect(lambda: _verify(acknowledgement=lambda: (_ for _ in ()).throw(ToolFailure(4, "synthetic canary")))[0], EXIT_INTERNAL, "acknowledgement_callback_failure")
    _expect(lambda: _verify(sender=lambda *_: (_ for _ in ()).throw(RuntimeError("synthetic")))[0], EXIT_INTERNAL, "stale_action_callback_failure")
    _expect(lambda: _verify(cleanup=lambda: (_ for _ in ()).throw(RuntimeError("synthetic")))[0], EXIT_INTERNAL, "cleanup_callback_failure")
    _expect(lambda: _verify(sender=lambda decision, action: _receipt("1" * 64, action))[0], EXIT_MISMATCH, "stale_receipt_mismatch")
    _expect(lambda: _verify(sender=lambda decision, action: _receipt(decision, "proceed"))[0], EXIT_MISMATCH, "stale_receipt_mismatch")
    _expect(lambda: _verify(sender=lambda *_: _encode({"status": "accepted"}))[0], EXIT_MISMATCH, "stale_receipt_mismatch")
    cleaned: list[str] = []
    _expect(lambda: acceptance.verify_inspection_map_rejection(_inspection(), _inspection, lambda: "acknowledged", _receipt, cleanup=lambda: cleaned.append("done") or (_ for _ in ()).throw(RuntimeError("synthetic"))), EXIT_MISMATCH, "original_snapshot_not_actionable")
    if cleaned != ["done"]:
        fail(EXIT_MISMATCH, "acceptance_fixture_cleanup")
    parameters = inspect.signature(acceptance.verify_inspection_map_rejection).parameters
    if any("credential" in name or "identity" in name for name in parameters):
        fail(EXIT_MISMATCH, "acceptance_fixture_credential_canary")


def _bad_timeout(seconds: object) -> None:
    attempts: list[tuple[str, str]] = []
    cleaned: list[str] = []
    _expect(lambda: acceptance.verify_inspection_map_rejection(_original(), _inspection, lambda: "acknowledged", lambda *args: attempts.append(args) or _receipt(*args), acknowledgement_seconds=seconds, cleanup=lambda: cleaned.append("done")), EXIT_INTERNAL, "invalid_acknowledgement_timeout")
    if attempts or cleaned != ["done"]:
        fail(EXIT_MISMATCH, "acceptance_fixture_timeout_cleanup")


def _real_result_summaries() -> None:
    heal = room_fixture._candidate(0, "rest_heal", "HEAL", enabled=True, supported=True)
    proceed = room_fixture._candidate(0, "proceed", "proceed", enabled=True, supported=True, is_proceed=True)
    first = room_fixture._ready(_DECISION, "rest_site", "choose_option", [heal], [room_fixture._legal(heal)])
    second = room_fixture._ready("1" * 64, "rest_site", "proceed", [proceed], [room_fixture._legal(proceed)])
    responses = room_fixture._base_responses() + [first, room_fixture._action_body(_DECISION, "choose:0"), second, room_fixture._action_body("1" * 64, "proceed"), room_fixture._COMPLETE_REST]
    requests = room_fixture._base_requests() + [room_fixture._get(room_fixture.room._ROOM_DECISION_ROUTE), room_fixture._post(_DECISION, "choose:0"), room_fixture._get(room_fixture.room._ROOM_DECISION_ROUTE), room_fixture._post("1" * 64, "proceed"), room_fixture._get(room_fixture.room._ROOM_DECISION_ROUTE)]
    connector = room_fixture._Connector([room_fixture._response(item) for item in responses], requests)
    credential = bytearray(room_fixture._CREDENTIAL)
    room_result = room_fixture.room._run_apply_room(credential, "safe", connector)
    connector.assert_cleanup()
    if any(credential) or acceptance.summarize_room_result(room_result) != {"code": "room_result_valid", "accepted_action_count": 2, "route_count": 7}:
        fail(EXIT_MISMATCH, "acceptance_fixture_room_summary")
    malformed_room = dict(room_result)
    malformed_room["accepted_action_count"] = True
    _expect(lambda: acceptance.summarize_room_result(malformed_room), EXIT_MISMATCH, "room_result_mismatch")
    run_result, _, _ = run_fixture._run_sequence(["shop"], 1)
    if acceptance.summarize_run_result(run_result).get("code") != "run_result_unvalidated":
        fail(EXIT_MISMATCH, "acceptance_fixture_run_summary")
    partial = {"schema_version": 1, "status": "passed", "milestone": "r0i_bounded_run", "completed_floor_count": 1, "readiness": [], "action_totals": {"combat": 999999, "reward": 0, "map": 0, "room": 0, "total": 999999}}
    if acceptance.summarize_run_result(partial).get("code") != "run_result_unvalidated":
        fail(EXIT_MISMATCH, "acceptance_fixture_partial_run_summary")
    _expect(lambda: acceptance.summarize_run_result({"completed_floor_count": True}), EXIT_MISMATCH, "run_result_mismatch")


def operation() -> dict[str, object]:
    _success_and_snapshots()
    _callbacks_cleanup_and_receipts()
    _real_result_summaries()
    return {"schema_version": 1, "status": "passed", "suite": "verify_room_acceptance_fixtures", "checks": ["accepted_room_validator_and_no_post_preconditions", "acknowledgement_deadline_and_callback_sanitization", "cleanup_and_credential_canaries", "real_room_and_explicitly_unvalidated_run_summaries"], "check_count": 4}


if __name__ == "__main__":
    main(operation)
