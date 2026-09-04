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


def _actual_client_shape(payload: dict[str, object]) -> dict[str, object]:
    """Expand orchestration stubs into the exact granular-client result shapes."""
    result = copy.deepcopy(payload)
    providers = result["providers"]

    def combat(value: dict[str, object]) -> None:
        actions = int(value["accepted_action_count"])
        value.clear()
        value.update({
            "schema_version": 1, "status": "passed", "milestone": "r0e_complete_combat",
            "decision_provider": providers["combat"], "outcome": "victory", "initial_round": 1,
            "final_round": 1, "rounds_observed": 1, "accepted_action_count": actions,
            "action_limit": 48, "round_limit": 12, "final_player": {"hp": 70, "max_hp": 80},
            "final_enemies": [], "actions": [{} for _ in range(actions)],
        })

    def reward(value: dict[str, object]) -> None:
        count = len(value["applied"])
        value.clear()
        value.update({
            "schema_version": 1, "status": "passed", "milestone": "r0i_reward_resolution",
            "decision_provider": providers["reward"],
            "applied": [{"action_id": "proceed", "kind": "proceed", "decision_revision": index, "chosen_card": None} for index in range(count)],
            "claimed_gold": 0, "selected_cards": [], "before": {"player": {"hp": 70, "max_hp": 80}},
            "after": {}, "routes_checked": 3 + 2 * count,
        })

    def map_result(value: dict[str, object]) -> None:
        destination = value["after"]["destination"]
        value.clear()
        value.update({
            "schema_version": 1, "status": "passed", "milestone": "r0g_map_selection",
            "decision_provider": providers["map"],
            "applied": {"action_id": "select:0", "kind": "select_map_node", "candidate_index": destination["candidate_index"], "col": destination["col"], "row": destination["row"], "node_kind": destination["kind"], "basis": "fixture"},
            "before": {}, "after": {"destination": destination}, "routes_checked": 5,
        })

    def room(value: dict[str, object]) -> None:
        value["decision_provider"] = providers["room"]

    for floor in result["floors"]:
        combat(floor["combat"])
        reward(floor["reward"])
        map_result(floor["map"])
    prefix = result.get("entry_prefix")
    if isinstance(prefix, dict):
        map_result(prefix["map"])
        if prefix["reward"] is not None:
            reward(prefix["reward"])
    terminal = result["terminal_combat"]
    if isinstance(terminal, dict):
        outcome = terminal["outcome"]
        combat(terminal)
        terminal["outcome"] = outcome
    handoff = result["room_handoff"]
    if isinstance(handoff, dict):
        room(handoff["room"])
        if isinstance(handoff.get("post_room_map"), dict):
            map_result(handoff["post_room_map"])
        if isinstance(handoff.get("next_combat"), dict):
            outcome = handoff["next_combat"]["outcome"]
            combat(handoff["next_combat"])
            handoff["next_combat"]["outcome"] = outcome
            if terminal is not None:
                result["terminal_combat"] = handoff["next_combat"]
    return result


def _result_contracts() -> None:
    default, _, _ = run_fixture._run_sequence(["monster", "shop"], 2)
    default = _actual_client_shape(default)
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
        entry = _actual_client_shape(entry)
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
    defeat = _actual_client_shape(defeat)
    if _summary(defeat)["terminal_combat_outcome"] != "defeat":
        fail(EXIT_MISMATCH, "run_acceptance_fixture_terminal_summary")
    room_continuation, _, _ = run_fixture._run_sequence(["rest_site", "monster"], 2)
    room_continuation = _actual_client_shape(room_continuation)
    room_summary = _summary(room_continuation)
    if (
        room_summary["action_totals"] != {"combat": 11, "reward": 1, "map": 2, "room": 2, "total": 16}
        or room_summary["termination"] != {"reason": "room_continuation_complete", "after_floor": 1, "destination_kind": "monster"}
    ):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_room_continuation_summary")
    room_defeat, _, _ = run_fixture._run_sequence(["rest_site", "monster"], 2, defeat_on_combat=2)
    room_defeat = _actual_client_shape(room_defeat)
    if _summary(room_defeat)["terminal_combat_outcome"] != "defeat":
        fail(EXIT_MISMATCH, "run_acceptance_fixture_room_defeat_summary")
    for destinations, limit, expected_reason in (
        (["shop"], 2, "unsupported_destination_kind"),
        (["boss"], 2, "act_boundary_reached"),
        (["rest_site"], 1, "room_handoff_complete"),
        (["elite", "shop"], 2, "floor_limit_reached"),
        (["rest_site", "elite"], 2, "room_continuation_complete"),
    ):
        payload, _, _ = run_fixture._run_sequence(destinations, limit)
        if _summary(_actual_client_shape(payload))["termination"]["reason"] != expected_reason:
            fail(EXIT_MISMATCH, "run_acceptance_fixture_termination_contract")


def _malformed_and_privacy() -> None:
    result, _, _ = run_fixture._run_sequence(["monster", "shop"], 2)
    result = _actual_client_shape(result)
    for mutate in (
        lambda value: value.update({"canary": "RAW-SECRET"}),
        lambda value: value["action_totals"].update({"total": 1}),
        lambda value: value["floors"][0].update({"destination_kind": "elite"}),
        lambda value: value["termination"].update({"destination_kind": None}),
        lambda value: value.update({"completed_floor_count": True}),
        lambda value: value.update({"milestone": []}),
        lambda value: value["termination"].update({"reason": []}),
    ):
        malformed = copy.deepcopy(result)
        mutate(malformed)
        _expect_failure(lambda: _summary(malformed), "run_acceptance_result_mismatch")
    canary = copy.deepcopy(result)
    canary["floors"][0]["combat"]["raw_canary"] = "CANARY-PROVIDER"
    _expect_failure(lambda: _summary(canary), "run_acceptance_result_mismatch")


def _in_process_operation_and_fixed_failures() -> None:
    result, _, _ = run_fixture._run_sequence(["monster", "shop"], 2)
    result = _actual_client_shape(result)
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
    with patch.object(live.run, "operation", side_effect=ToolFailure(EXIT_MISMATCH, "SYNTHETIC-ARBITRARY-CANARY")):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    with patch.object(live.run, "operation", side_effect=KeyboardInterrupt):
        try:
            live.operation()
        except KeyboardInterrupt:
            pass
        else:
            fail(EXIT_MISMATCH, "run_acceptance_fixture_interrupt_swallowed")
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
