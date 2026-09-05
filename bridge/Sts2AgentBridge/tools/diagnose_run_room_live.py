#!/usr/bin/env python3
"""Emit one fixed room-stage diagnostic for the existing bounded run."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from contextlib import redirect_stderr, redirect_stdout
from typing import Union

import apply_run_acceptance_live as acceptance_wrapper
import apply_run_live as run
from room_stage_diagnostics import RoomStageDiagnostics, validate_room_stage_record
from tool_common import EXIT_INTERNAL, ToolFailure, emit
from verify_room_acceptance import (
    _KNOWN_PRODUCTION_FAILURE_CODES,
    summarize_run_acceptance_result,
)


_SUMMARY_KEYS = (
    "schema_version",
    "status",
    "milestone",
    "source_milestone",
    "entry_phase",
    "processed_floor_count",
    "completed_floor_count",
    "action_totals",
    "termination",
    "terminal_combat_outcome",
)
_ACTION_TOTAL_KEYS = ("combat", "reward", "map", "room", "total")
_TERMINATION_KEYS = ("reason", "after_floor", "destination_kind")
_SOURCE_MILESTONES = frozenset(("r0i_bounded_run", "r0i_bounded_run_entry"))
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
_DESTINATION_KINDS = frozenset(
    ("unknown", "shop", "treasure", "rest_site", "monster", "elite", "boss", "ancient")
)


class _NonRetainingTextSink:
    """Discard nested text without retaining a transcript in memory."""

    encoding = "utf-8"

    def write(self, value: str) -> int:
        if type(value) is not str:
            raise TypeError("text required")
        return len(value)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


def _validate_run_acceptance_summary(value: object) -> dict[str, object]:
    if type(value) is not dict or tuple(value) != _SUMMARY_KEYS:
        raise ValueError("run acceptance shape")
    source = value["source_milestone"]
    entry_phase = value["entry_phase"]
    processed = value["processed_floor_count"]
    completed = value["completed_floor_count"]
    totals = value["action_totals"]
    termination = value["termination"]
    outcome = value["terminal_combat_outcome"]
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or type(value["status"]) is not str
        or value["status"] != "passed"
        or type(value["milestone"]) is not str
        or value["milestone"] != "r0i_bounded_run_acceptance"
        or type(source) is not str
        or source not in _SOURCE_MILESTONES
        or type(entry_phase) is not str
        or entry_phase not in ("combat", "reward", "map")
        or (source == "r0i_bounded_run" and entry_phase != "combat")
        or (source == "r0i_bounded_run_entry" and entry_phase == "combat")
        or type(processed) is not int
        or type(completed) is not int
        or not 0 <= completed <= processed <= 3
        or type(totals) is not dict
        or tuple(totals) != _ACTION_TOTAL_KEYS
        or type(termination) is not dict
        or tuple(termination) != _TERMINATION_KEYS
        or (
            outcome is not None
            and (type(outcome) is not str or outcome not in ("victory", "defeat"))
        )
    ):
        raise ValueError("run acceptance value")
    counts = tuple(totals[name] for name in _ACTION_TOTAL_KEYS)
    if (
        any(type(count) is not int or count < 0 for count in counts)
        or totals["room"] > 12
        or totals["total"]
        != totals["combat"] + totals["reward"] + totals["map"] + totals["room"]
    ):
        raise ValueError("run acceptance totals")
    reason = termination["reason"]
    after_floor = termination["after_floor"]
    destination = termination["destination_kind"]
    if (
        type(reason) is not str
        or reason not in _TERMINATION_REASONS
        or type(after_floor) is not int
        or not 0 <= after_floor <= 3
        or (
            destination is not None
            and (type(destination) is not str or destination not in _DESTINATION_KINDS)
        )
    ):
        raise ValueError("run acceptance termination")
    return {
        "schema_version": value["schema_version"],
        "status": value["status"],
        "milestone": value["milestone"],
        "source_milestone": source,
        "entry_phase": entry_phase,
        "processed_floor_count": processed,
        "completed_floor_count": completed,
        "action_totals": {name: totals[name] for name in _ACTION_TOTAL_KEYS},
        "termination": {name: termination[name] for name in _TERMINATION_KEYS},
        "terminal_combat_outcome": outcome,
    }


def _validate_success_consistency(
    room: dict[str, object],
    run_acceptance: dict[str, object],
) -> None:
    totals = run_acceptance["action_totals"]
    if type(totals) is not dict or type(totals.get("room")) is not int:
        raise ValueError("run room total")
    room_actions = totals["room"]
    stage = room["stage"]
    attempts = room["action_exchange_attempt_count"]
    accepted = room["accepted_receipt_count"]
    if stage == "not_entered":
        if room_actions != 0:
            raise ValueError("unentered room total")
        return
    if (
        room_actions == 0
        or stage != "complete"
        or room["completion_confirmed"] is not True
        or attempts != accepted
        or accepted != room_actions
    ):
        raise ValueError("completed room total")


def _payload(
    status: str,
    code: str,
    room: Union[dict[str, object], None],
    run_acceptance: Union[dict[str, object], None],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": status,
        "milestone": "r0i_run_room_diagnostic",
        "code": code,
        "room": room,
        "run_acceptance": run_acceptance,
    }


def _failure_code(failure: ToolFailure) -> tuple[str, int]:
    try:
        exit_code = failure.exit_code
        error_code = failure.error_code
        if (
            type(exit_code) is int
            and exit_code in (2, 3, 4, 5)
            and type(error_code) is str
            and error_code in _KNOWN_PRODUCTION_FAILURE_CODES
        ):
            return error_code, exit_code
    except BaseException:
        pass
    return "internal_failure", EXIT_INTERNAL


def _execute() -> tuple[dict[str, object], int]:
    diagnostics: Union[RoomStageDiagnostics, None] = None
    result: object = None
    run_acceptance: Union[dict[str, object], None] = None
    status = "failed"
    code = "internal_failure"
    exit_code = EXIT_INTERNAL
    sink = _NonRetainingTextSink()
    with redirect_stdout(sink), redirect_stderr(sink):
        try:
            diagnostics = RoomStageDiagnostics()
            result = run._operation(room_diagnostics=diagnostics)
            run_acceptance = _validate_run_acceptance_summary(
                summarize_run_acceptance_result(result)
            )
            room = validate_room_stage_record(diagnostics.record())
            _validate_success_consistency(room, run_acceptance)
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
            room = validate_room_stage_record(diagnostics.record())
            diagnostic_ok = True
        except BaseException:
            room = None
            diagnostic_ok = False
        try:
            cleanup_ok = acceptance_wrapper._clear_mutable_buffers(result)
        except BaseException:
            cleanup_ok = False
        if not diagnostic_ok or cleanup_ok is not True:
            return _payload("failed", "internal_failure", None, None), EXIT_INTERNAL
        if status != "passed":
            run_acceptance = None
        return _payload(status, code, room, run_acceptance), exit_code


def operation() -> dict[str, object]:
    return _execute()[0]


def main() -> int:
    payload, exit_code = _execute()
    emit(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
