#!/usr/bin/env python3
"""Synthetic, capture-off fixture gate for bounded-run acceptance summaries."""
from __future__ import annotations

import copy
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import apply_run_acceptance_live as live
import apply_run_live_fixtures as run_fixture
import verify_room_acceptance as acceptance
from tool_common import EXIT_INTERNAL, EXIT_MISMATCH, ToolFailure, fail, run_cli


def _encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _expect_failure(operation: object, code: str, exit_code: int = EXIT_MISMATCH) -> None:
    try:
        operation()  # type: ignore[operator]
    except ToolFailure as failure:
        if failure.exit_code == exit_code and failure.error_code == code:
            return
    fail(EXIT_MISMATCH, "run_acceptance_fixture_wrong_failure")


def _summary(payload: dict[str, object]) -> dict[str, object]:
    return acceptance.summarize_run_acceptance_result(payload)


def _result_contracts() -> None:
    default, _, _ = run_fixture._run_sequence(["monster", "shop"], 2)
    expected_default = {
        "schema_version": 1, "status": "passed", "milestone": "r0i_bounded_run_acceptance",
        "source_milestone": "r0i_bounded_run", "entry_phase": "combat",
        "processed_floor_count": 2, "completed_floor_count": 2,
        "action_totals": {"combat": 11, "reward": 2, "map": 2, "room": 0, "total": 15},
        "termination": {"reason": "floor_limit_reached", "after_floor": 2, "destination_kind": "shop"},
        "terminal_combat_outcome": None,
    }
    if _summary(default) != expected_default:
        fail(EXIT_MISMATCH, "run_acceptance_fixture_default_summary")
    for phase in ("map", "reward"):
        entry, _, _ = run_fixture._run_sequence(["monster", "shop"], 2, entry_phase=phase)
        summary = _summary(entry)
        if (
            summary["source_milestone"] != "r0i_bounded_run_entry"
            or summary["entry_phase"] != phase
            or summary["processed_floor_count"] != 2
            or summary["completed_floor_count"] != 1
            or summary["termination"] != {"reason": "floor_limit_reached", "after_floor": 2, "destination_kind": "shop"}
        ):
            fail(EXIT_MISMATCH, "run_acceptance_fixture_entry_summary")
    defeat, _, _ = run_fixture._run_sequence(["monster"], 1, defeat_on_combat=1)
    if _summary(defeat)["terminal_combat_outcome"] != "defeat":
        fail(EXIT_MISMATCH, "run_acceptance_fixture_terminal_summary")
    room_continuation, _, _ = run_fixture._run_sequence(["rest_site", "monster"], 2)
    room_summary = _summary(room_continuation)
    if (
        room_summary["action_totals"] != {"combat": 11, "reward": 1, "map": 2, "room": 2, "total": 16}
        or room_summary["termination"] != {"reason": "room_continuation_complete", "after_floor": 1, "destination_kind": "monster"}
    ):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_room_continuation_summary")
    room_defeat, _, _ = run_fixture._run_sequence(["rest_site", "monster"], 2, defeat_on_combat=2)
    if _summary(room_defeat)["terminal_combat_outcome"] != "defeat":
        fail(EXIT_MISMATCH, "run_acceptance_fixture_room_defeat_summary")


def _malformed_and_privacy() -> None:
    result, _, _ = run_fixture._run_sequence(["monster", "shop"], 2)
    for mutate in (
        lambda value: value.update({"canary": "RAW-SECRET"}),
        lambda value: value["action_totals"].update({"total": 1}),
        lambda value: value["floors"][0].update({"destination_kind": "elite"}),
        lambda value: value["termination"].update({"destination_kind": None}),
        lambda value: value.update({"completed_floor_count": True}),
    ):
        malformed = copy.deepcopy(result)
        mutate(malformed)
        _expect_failure(lambda: _summary(malformed), "run_acceptance_result_mismatch")
    canary = copy.deepcopy(result)
    canary["providers"]["combat"] = "CANARY-PROVIDER"
    rendered = _encoded(_summary(canary))
    if "CANARY" in rendered or "decision_id" in rendered or "action_id" in rendered:
        fail(EXIT_MISMATCH, "run_acceptance_fixture_summary_leak")


def _in_process_operation_and_fixed_failures() -> None:
    result, _, _ = run_fixture._run_sequence(["monster", "shop"], 2)
    with patch.object(live.run, "operation", return_value=result) as operation:
        summary = live.operation()
    if operation.call_count != 1 or summary != _summary(result):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_in_process_operation")
    buffered = copy.deepcopy(result)
    mutable_canary = bytearray(b"RAW-CANARY")
    buffered["fixture_buffer"] = mutable_canary
    with patch.object(live.run, "operation", return_value=buffered):
        _expect_failure(live.operation, "run_acceptance_result_mismatch")
    if any(mutable_canary):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_buffer_cleanup")
    with patch.object(live.run, "operation", side_effect=RuntimeError("RAW-CANARY")):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    with patch.object(live.run, "operation", side_effect=ToolFailure(EXIT_MISMATCH, "run_map_result_mismatch")):
        _expect_failure(live.operation, "run_map_result_mismatch")
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(live.run, "operation", side_effect=RuntimeError("RAW-CANARY")), redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(live.operation)
    if (
        exit_code != EXIT_INTERNAL
        or stdout.getvalue() != '{"schema_version":1,"status":"failed","code":"run_acceptance_callback_failure"}\n'
        or stderr.getvalue() != ""
        or "CANARY" in stdout.getvalue()
    ):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_fixed_failure_output")


def operation() -> dict[str, object]:
    _result_contracts()
    _malformed_and_privacy()
    _in_process_operation_and_fixed_failures()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_run_acceptance_live_fixtures",
        "check_count": 3,
    }


if __name__ == "__main__":
    from tool_common import main
    main(operation)
