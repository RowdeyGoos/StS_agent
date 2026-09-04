#!/usr/bin/env python3
from __future__ import annotations

import json
import inspect
from collections.abc import Callable

import verify_room_acceptance as acceptance
from tool_common import EXIT_MISMATCH, ToolFailure, fail, main

_DECISION = "0" * 64


def _encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _original() -> bytes:
    candidate = {
        "candidate_index": 0, "action_id": "choose:0", "kind": "rest_heal",
        "stable_id": "HEAL", "enabled": True, "supported": True,
        "is_proceed": False, "is_dangerous": False,
    }
    return _encode({
        "schema_version": 1, "status": "ready", "decision_kind": "room",
        "actionable": True, "decision_id": _DECISION, "screen_kind": "rest_site",
        "phase": "choose_option", "room_ordinal": 4, "candidates": [candidate],
        "legal_actions": [{"action_id": "choose:0", "kind": "choose_room_option", "candidate_index": 0}],
    })


def _inspection(*, suppressed: bool = True) -> bytes:
    if not suppressed:
        return _original()
    return _encode({
        "schema_version": 1, "status": "waiting", "decision_kind": "room",
        "actionable": False, "decision_id": None, "screen_kind": "unknown",
        "phase": "unknown", "room_ordinal": None, "candidates": [], "legal_actions": [],
    })


def _receipt(
    decision_id: str,
    action_id: str,
    *,
    stale: bool = True,
    bound: bool = True,
    action_bound: bool = True,
) -> bytes:
    return _encode({
        "schema_version": 1, "status": "rejected" if stale else "accepted",
        "mutation_state": "none" if stale else "applied",
        "decision_id": decision_id if bound else "1" * 64,
        "action_id": action_id if action_bound else "proceed",
        "reason": "stale_decision" if stale else "accepted",
    })


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _expect_failure(operation: Callable[[], object], code: str) -> None:
    try:
        operation()
    except ToolFailure as error:
        if error.exit_code != EXIT_MISMATCH or error.error_code != code:
            fail(EXIT_MISMATCH, "acceptance_fixture_wrong_failure")
    else:
        fail(EXIT_MISMATCH, "acceptance_fixture_unexpected_success")


def _verify(
    *,
    original: bytes | None = None,
    inspected: bytes | None = None,
    acknowledgement: object = "acknowledged",
    stale: bool = True,
    bound: bool = True,
    action_bound: bool = True,
    late: bool = False,
    late_action: bool = False,
) -> tuple[dict[str, object], list[tuple[str, str]], list[str]]:
    clock = _Clock()
    attempts: list[tuple[str, str]] = []
    cleanup: list[str] = []

    def acknowledge() -> object:
        if late:
            clock.now = 46.0
        return acknowledgement

    def send(decision_id: str, action_id: str) -> bytes:
        attempts.append((decision_id, action_id))
        if late_action:
            clock.now = 46.0
        return _receipt(
            decision_id,
            action_id,
            stale=stale,
            bound=bound,
            action_bound=action_bound,
        )

    result = acceptance.verify_inspection_map_rejection(
        _original() if original is None else original,
        lambda: _inspection() if inspected is None else inspected,
        acknowledge,
        send,
        clock=clock,
        cleanup=lambda: cleanup.append("done"),
    )
    return result, attempts, cleanup


def _success_and_privacy() -> None:
    result, attempts, cleanup = _verify()
    if (
        result != {
            "schema_version": 1, "status": "passed",
            "code": "inspection_map_stale_rejection_verified",
            "acknowledgement_count": 1, "stale_action_attempt_count": 1,
        }
        or attempts != [(_DECISION, "choose:0")]
        or cleanup != ["done"]
        or any(value in json.dumps(result) for value in (_DECISION, "choose:0", "HEAL"))
    ):
        fail(EXIT_MISMATCH, "acceptance_fixture_success_or_privacy")


def _negative_cases() -> None:
    _expect_failure(lambda: _verify(acknowledgement="ack")[0], "operator_acknowledgement_invalid")
    _expect_failure(lambda: _verify(acknowledgement=None)[0], "operator_acknowledgement_invalid")
    _expect_failure(lambda: _verify(late=True)[0], "operator_acknowledgement_timeout")
    _expect_failure(lambda: _verify(late_action=True)[0], "operator_acknowledgement_timeout")
    _expect_failure(lambda: _verify(inspected=b"")[0], "inspection_snapshot_eof")
    _expect_failure(lambda: _verify(original=_inspection())[0], "original_snapshot_not_actionable")
    _expect_failure(lambda: _verify(inspected=_inspection(suppressed=False))[0], "inspection_actions_not_suppressed")
    _expect_failure(lambda: _verify(bound=False)[0], "stale_receipt_mismatch")
    _expect_failure(lambda: _verify(action_bound=False)[0], "stale_receipt_mismatch")
    _expect_failure(lambda: _verify(stale=False)[0], "stale_receipt_mismatch")


def _cleanup_and_canaries() -> None:
    cleanup: list[str] = []
    action_calls = 0

    def send(_: str, __: str) -> bytes:
        nonlocal action_calls
        action_calls += 1
        raise RuntimeError("fixture exception")

    try:
        acceptance.verify_inspection_map_rejection(
            _original(), _inspection, lambda: "acknowledged", send,
            cleanup=lambda: cleanup.append("done"),
        )
    except RuntimeError:
        pass
    else:
        fail(EXIT_MISMATCH, "acceptance_fixture_exception_not_propagated")
    if action_calls != 1 or cleanup != ["done"]:
        fail(EXIT_MISMATCH, "acceptance_fixture_cleanup")
    parameter_names = tuple(inspect.signature(acceptance.verify_inspection_map_rejection).parameters)
    forbidden_exports = ("socket", "probe_live", "Path")
    if (
        any("credential" in value or "identity" in value for value in parameter_names)
        or any(value in acceptance.__dict__ for value in forbidden_exports)
    ):
        fail(EXIT_MISMATCH, "acceptance_fixture_credential_canary")


def _summaries() -> None:
    room = acceptance.summarize_room_result({
        "schema_version": 1, "status": "passed", "milestone": "r0i_room_interaction",
        "accepted_action_count": 2, "routes_checked": 5,
    })
    run = acceptance.summarize_run_result({
        "schema_version": 1, "status": "passed", "milestone": "r0i_bounded_run",
        "completed_floor_count": 1, "readiness": [{"attempts": 1}],
        "action_totals": {"combat": 2, "reward": 1, "map": 2, "room": 2, "total": 7},
    })
    if room != {"code": "room_result_valid", "accepted_action_count": 2, "route_count": 5}:
        fail(EXIT_MISMATCH, "acceptance_fixture_room_summary")
    if run != {"code": "run_result_valid", "completed_floor_count": 1, "readiness_count": 1, "action_count": 7}:
        fail(EXIT_MISMATCH, "acceptance_fixture_run_summary")
    _expect_failure(lambda: acceptance.summarize_room_result({}), "room_result_mismatch")
    _expect_failure(lambda: acceptance.summarize_run_result({}), "run_result_mismatch")


def operation() -> dict[str, object]:
    _success_and_privacy()
    _negative_cases()
    _cleanup_and_canaries()
    _summaries()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "verify_room_acceptance_fixtures",
        "checks": [
            "single_stale_no_mutation_receipt",
            "acknowledgement_and_deadline_rejection",
            "inspection_and_receipt_rejection",
            "exception_cleanup_and_hook_canaries",
            "minimal_room_and_run_summaries",
        ],
        "check_count": 5,
    }


if __name__ == "__main__":
    main(operation)
