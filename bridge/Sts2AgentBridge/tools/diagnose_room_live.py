#!/usr/bin/env python3
"""Emit one fixed room-stage diagnostic for the existing direct room client."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from contextlib import redirect_stderr, redirect_stdout
from typing import Union

import apply_room_live as room
import apply_run_acceptance_live as acceptance_wrapper
import diagnose_run_room_live as run_diagnostic
from room_stage_diagnostics import RoomStageDiagnostics, validate_room_stage_record
from tool_common import EXIT_INTERNAL, ToolFailure, emit
from verify_room_acceptance import summarize_room_result


def _validated_room_summary(value: object) -> dict[str, object]:
    if type(value) is not dict or tuple(value) != (
        "code",
        "accepted_action_count",
        "route_count",
    ):
        raise ValueError("room acceptance shape")
    code = value["code"]
    accepted = value["accepted_action_count"]
    routes = value["route_count"]
    if (
        type(code) is not str
        or code != "room_result_valid"
        or type(accepted) is not int
        or not 1 <= accepted <= 12
        or type(routes) is not int
        or routes < 3 + 2 * accepted
    ):
        raise ValueError("room acceptance value")
    return {
        "code": code,
        "accepted_action_count": accepted,
        "route_count": routes,
    }


def _validate_success_consistency(
    diagnostics: dict[str, object],
    summary: dict[str, object],
    result: object,
) -> None:
    if type(result) is not dict:
        raise ValueError("room result type")
    screen_kind = result.get("screen_kind")
    attempts = diagnostics["action_exchange_attempt_count"]
    accepted = diagnostics["accepted_receipt_count"]
    if (
        diagnostics["stage"] != "complete"
        or diagnostics["completion_confirmed"] is not True
        or type(attempts) is not int
        or type(accepted) is not int
        or attempts < 1
        or attempts != accepted
        or accepted != summary["accepted_action_count"]
        or type(screen_kind) is not str
        or screen_kind not in ("rest_site", "event")
        or diagnostics["last_ready_kind"] != screen_kind
    ):
        raise ValueError("room diagnostic success")


def _failure_code(failure: ToolFailure) -> tuple[str, int]:
    try:
        exit_code = failure.exit_code
        error_code = failure.error_code
    except BaseException:
        return "internal_failure", EXIT_INTERNAL
    if (
        type(exit_code) is int
        and exit_code == 2
        and type(error_code) is str
        and error_code == "invalid_decision_provider"
    ):
        return error_code, exit_code
    try:
        normalized = ToolFailure(exit_code, error_code)
    except BaseException:
        return "internal_failure", EXIT_INTERNAL
    return run_diagnostic._failure_code(normalized)


def _payload(
    status: str,
    code: str,
    diagnostics: Union[dict[str, object], None],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": status,
        "milestone": "r0i_room_diagnostic",
        "code": code,
        "room": diagnostics,
    }


def _execute() -> tuple[dict[str, object], int]:
    diagnostics: Union[RoomStageDiagnostics, None] = None
    result: object = None
    status = "failed"
    code = "internal_failure"
    exit_code = EXIT_INTERNAL
    sink = run_diagnostic._NonRetainingTextSink()
    with redirect_stdout(sink), redirect_stderr(sink):
        try:
            diagnostics = RoomStageDiagnostics()
            result = room._operation(diagnostics=diagnostics)
            summary = _validated_room_summary(summarize_room_result(result))
            record = validate_room_stage_record(diagnostics.record())
            _validate_success_consistency(record, summary, result)
            status = "passed"
            code = "none"
            exit_code = 0
        except KeyboardInterrupt:
            status = "failed"
            code = "interrupted"
            exit_code = EXIT_INTERNAL
        except ToolFailure as failure:
            status = "failed"
            code, exit_code = _failure_code(failure)
        except BaseException:
            status = "failed"
            code = "internal_failure"
            exit_code = EXIT_INTERNAL

        try:
            if diagnostics is None:
                raise ValueError("missing room diagnostics")
            record = validate_room_stage_record(diagnostics.record())
            diagnostic_ok = True
        except BaseException:
            record = None
            diagnostic_ok = False
        try:
            cleanup_ok = acceptance_wrapper._clear_mutable_buffers(result)
        except BaseException:
            cleanup_ok = False
        if not diagnostic_ok or cleanup_ok is not True:
            return _payload("failed", "internal_failure", None), EXIT_INTERNAL
        return _payload(status, code, record), exit_code


def operation() -> dict[str, object]:
    return _execute()[0]


def main() -> int:
    payload, exit_code = _execute()
    emit(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
