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
import apply_run_elite_wire_fixtures as elite_wire
import apply_run_entry_wire_fixtures as entry_wire
import apply_run_wire_fixtures as run_wire
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


def _entry_map(kind: str, limit: int) -> dict[str, object]:
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    entry_wire._map(transcript, "7" * 64, kind)
    result, connector, _ = entry_wire._run(transcript, "map", limit)
    connector.require_complete(1)
    return result


def _default_defeat() -> dict[str, object]:
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    entry_wire._combat_defeat(transcript, "a" * 64)
    result, connector, _ = entry_wire._run(transcript, None, 1)
    connector.require_complete(1)
    return result


def _default_elite() -> dict[str, object]:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    elite_wire._combat_victory(transcript, "a")
    elite_wire._add_reward_then_map(transcript, "3" * 64, "elite", reward_id="4" * 64, revision=0)
    elite_wire._add(transcript, elite_wire._next_combat_ready("7" * 64), entry_wire._GET_COMBAT)
    elite_wire._combat_victory(transcript, "b")
    elite_wire._add_reward_then_map(transcript, "5" * 64, "shop", reward_id="6" * 64, revision=0)
    result, connector, _ = elite_wire._run(transcript, entry_phase="combat", floor_limit=2)
    connector.require_used_clean(sum(request.startswith(b"POST ") for _, request in transcript))
    return result


def _entry_room_handoff() -> dict[str, object]:
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    entry_wire._map(transcript, "b" * 64, "rest_site")
    entry_wire._add(transcript, entry_wire._room_ready("c" * 64, 4), entry_wire._GET_ROOM)
    entry_wire._room(transcript, 4)
    entry_wire._add(transcript, entry_wire._map_complete("rest_site"), entry_wire._GET_MAP)
    entry_wire._add(transcript, entry_wire.map_client._MAP_WAITING, entry_wire._GET_MAP)
    entry_wire._add(transcript, entry_wire._map_ready("d" * 64, "monster"), entry_wire._GET_MAP)
    result, connector, _ = entry_wire._run(transcript, "map", 1)
    connector.require_complete(3)
    return result


def _post_room_elite_victory() -> dict[str, object]:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    elite_wire._combat_victory(transcript, "c")
    elite_wire._add_reward_then_map(transcript, "9" * 64, "rest_site", reward_id="a" * 64, revision=0)
    elite_wire._add(transcript, entry_wire._room_ready("b" * 64, 4), entry_wire._GET_ROOM)
    entry_wire._room(transcript, 4)
    elite_wire._add(transcript, entry_wire._map_complete("rest_site"), entry_wire._GET_MAP)
    elite_wire._add(transcript, entry_wire.map_client._MAP_WAITING, entry_wire._GET_MAP)
    elite_wire._add(transcript, elite_wire._map_ready("c" * 64, "elite"), entry_wire._GET_MAP)
    elite_wire._map(transcript, "c" * 64, "elite")
    elite_wire._add(transcript, elite_wire._next_combat_ready("e" * 64), entry_wire._GET_COMBAT)
    elite_wire._combat_victory(transcript, "d")
    result, connector, _ = elite_wire._run(transcript, entry_phase="combat")
    connector.require_used_clean(sum(request.startswith(b"POST ") for _, request in transcript))
    return result


def _result_contracts() -> None:
    results = [
        (_default_defeat(), "run_defeat"),
        (_entry_map("shop", 1), "floor_limit_reached"),
        (_entry_map("shop", 2), "unsupported_destination_kind"),
        (_entry_map("boss", 2), "act_boundary_reached"),
        (_default_elite(), "floor_limit_reached"),
        (_entry_room_handoff(), "room_handoff_complete"),
        (_post_room_elite_victory(), "room_continuation_complete"),
    ]
    for result, reason in results:
        summary = _summary(result)
        if summary["termination"]["reason"] != reason or set(summary) != {
            "schema_version", "status", "milestone", "source_milestone", "entry_phase",
            "processed_floor_count", "completed_floor_count", "action_totals", "termination",
            "terminal_combat_outcome",
        }:
            fail(EXIT_MISMATCH, "run_acceptance_fixture_actual_result")


def _malformed_and_privacy() -> None:
    result = _default_elite()
    for mutate in (
        lambda value: value.update({"canary": "RAW-SECRET"}),
        lambda value: value["action_totals"].update({"total": 1}),
        lambda value: value["floors"][0].update({"destination_kind": "monster"}),
        lambda value: value["termination"].update({"destination_kind": None}),
        lambda value: value.update({"completed_floor_count": True}),
        lambda value: value.update({"milestone": []}),
        lambda value: value["termination"].update({"reason": []}),
        lambda value: value["floors"][0]["combat"].update({"final_player": {}}),
        lambda value: value["floors"][0]["combat"]["final_player"].update({"hp": -9}),
        lambda value: value["floors"][0]["combat"]["actions"][0].update({"raw_canary": "CANARY"}),
        lambda value: value["floors"][0]["reward"]["before"]["rewards"][0].update({"cards": [{"raw_canary": "SYNTHETIC"}]}),
        lambda value: value["floors"][0]["reward"].update({"claimed_gold": -1}),
        lambda value: value["floors"][0]["map"]["before"]["candidates"][0].update({"kind": "CANARY"}),
        lambda value: value["providers"].update({"combat": "CANARY"}),
    ):
        malformed = copy.deepcopy(result)
        mutate(malformed)
        _expect_failure(lambda: _summary(malformed), "run_acceptance_result_mismatch")
    canary = copy.deepcopy(result)
    canary["floors"][0]["combat"]["raw_canary"] = "CANARY-PROVIDER"
    _expect_failure(lambda: _summary(canary), "run_acceptance_result_mismatch")
    room_at_cap = _entry_room_handoff()
    room_at_cap["floor_limit"] = 3
    _expect_failure(lambda: _summary(room_at_cap), "run_acceptance_result_mismatch")
    post_room = _post_room_elite_victory()
    post_room["room_handoff"]["post_room_map"]["applied"]["node_kind"] = "shop"
    post_room["room_handoff"]["post_room_map"]["after"]["destination"]["kind"] = "shop"
    post_room["termination"]["destination_kind"] = "shop"
    _expect_failure(lambda: _summary(post_room), "run_acceptance_result_mismatch")
    floor_with_room = _default_elite()
    floor_with_room["room_handoff"] = copy.deepcopy(_entry_room_handoff()["room_handoff"])
    _expect_failure(lambda: _summary(floor_with_room), "run_acceptance_result_mismatch")
    relabeled_room = _entry_room_handoff()
    relabeled_room["room_handoff"]["destination_kind"] = "ancient"
    _expect_failure(lambda: _summary(relabeled_room), "run_acceptance_result_mismatch")
    relabeled_continuation = _post_room_elite_victory()
    relabeled_continuation["termination"]["reason"] = "unsupported_destination_kind"
    _expect_failure(lambda: _summary(relabeled_continuation), "run_acceptance_result_mismatch")
    defeat_after_shop = _entry_map("shop", 2)
    defeat_after_shop["termination"] = {"reason": "run_defeat", "after_floor": 1, "destination_kind": None}
    defeat_after_shop["terminal_combat"] = copy.deepcopy(_default_defeat()["terminal_combat"])
    defeat_after_shop["action_totals"]["combat"] = 1
    defeat_after_shop["action_totals"]["total"] += 1
    _expect_failure(lambda: _summary(defeat_after_shop), "run_acceptance_result_mismatch")
    leaf_mutations = (
        (_default_defeat, lambda value: value["terminal_combat"]["final_enemies"][0].update({"hp": -1})),
        (_default_defeat, lambda value: value["terminal_combat"]["final_enemies"][0].update({"id": {"raw": "CANARY"}})),
        (_default_defeat, lambda value: value["terminal_combat"]["actions"][0].update({"step": 0})),
        (_default_defeat, lambda value: value["terminal_combat"]["actions"][0].update({"basis": "CANARY"})),
        (_default_elite, lambda value: value["floors"][0]["reward"]["before"].update({"decision_id": "CANARY"})),
        (_default_elite, lambda value: value["floors"][0]["reward"]["after"]["player"].update({"gold": -1})),
        (_default_elite, lambda value: value["floors"][0]["reward"]["before"]["legal_actions"][0].update({"kind": "CANARY"})),
        (_default_elite, lambda value: value["floors"][0]["reward"]["applied"][0].update({"decision_revision": -1})),
        (_default_elite, lambda value: value["floors"][0]["reward"].update({"selected_cards": [{"raw": "CANARY"}]})),
        (_default_elite, lambda value: value["floors"][0]["map"]["before"]["candidates"][0].update({"col": -1})),
        (_default_elite, lambda value: value["floors"][0]["map"]["before"]["legal_actions"][0].update({"action_id": "CANARY"})),
        (_default_elite, lambda value: value["floors"][0]["map"]["applied"].update({"basis": "CANARY"})),
        (_entry_room_handoff, lambda value: value["room_handoff"]["room"]["actions"][0].update({"basis": "CANARY"})),
        (_entry_room_handoff, lambda value: value["room_handoff"]["room"]["final"].update({"raw_canary": "CANARY"})),
    )
    for factory, mutate in leaf_mutations:
        malformed = factory()
        mutate(malformed)
        _expect_failure(lambda malformed=malformed: _summary(malformed), "run_acceptance_result_mismatch")


def _in_process_operation_and_fixed_failures() -> None:
    result = _default_defeat()
    with patch.object(live.run, "operation", return_value=result) as operation:
        summary = live.operation()
    if operation.call_count != 1 or summary != _summary(result):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_in_process_operation")
    for argument_count in (14, 16):
        arguments = [f"argument-{index}" for index in range(argument_count)]
        def delegated() -> dict[str, object]:
            if sys.argv[1:] != arguments:
                fail(EXIT_MISMATCH, "run_acceptance_fixture_argument_delegation")
            return result
        with patch.object(sys, "argv", ["apply_run_acceptance_live.py", *arguments]), patch.object(live.run, "operation", side_effect=delegated):
            live.operation()
    buffered = copy.deepcopy(result)
    mutable_canary = bytearray(b"RAW-CANARY")
    buffered["fixture_buffer"] = mutable_canary
    with patch.object(live.run, "operation", return_value=buffered):
        _expect_failure(live.operation, "run_acceptance_result_mismatch")
    if any(mutable_canary):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_buffer_cleanup")
    with patch.object(live.run, "operation", side_effect=RuntimeError("RAW-CANARY")):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    for known in ("run_map_result_mismatch", "reward_state_unsupported", "reward_action_response_mismatch", "map_action_transport_failure", "combat_round_limit_reached", "map_action_stale_decision", "map_action_invalid_action", "map_rate_limited", "map_backend_retryable", "map_backend_fault"):
        with patch.object(live.run, "operation", side_effect=ToolFailure(EXIT_MISMATCH, known)):
            _expect_failure(live.operation, known)
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    elite_wire._map(transcript, "e" * 64, "elite")
    elite_wire._add(transcript, elite_wire._next_combat_ready("0" * 64), entry_wire._GET_COMBAT)
    elite_wire._combat_victory(transcript, "d")
    elite_wire._add(transcript, elite_wire.reward_client._REWARD_UNSUPPORTED, entry_wire._GET_REWARD)
    connector, credentials = elite_wire._Connector(transcript), elite_wire._Credentials()
    def actual_failure() -> dict[str, object]:
        with entry_wire._clock():
            return elite_wire.run._run_bounded_run(credentials, connector, "first-legal", "first-card", "elite", "safe", 3, entry_phase="map")
    with patch.object(live.run, "operation", side_effect=actual_failure):
        _expect_failure(live.operation, "reward_state_unsupported")
    credentials.require_zeroed()
    connector.require_used_clean(5)
    decision = "f" * 64
    for response, code in (
        (elite_wire.map_fixture._action_body(decision, "select:0", "stale_decision"), "map_action_stale_decision"),
        (elite_wire.map_fixture._action_body(decision, "select:0", "invalid_action"), "map_action_invalid_action"),
        (TimeoutError("SYNTHETIC-CANARY"), "map_action_transport_failure"),
    ):
        receipt_transcript: list[tuple[bytes | BaseException, bytes]] = []
        entry_wire._base(receipt_transcript)
        elite_wire._add(receipt_transcript, elite_wire._map_ready(decision, "elite"), entry_wire._GET_MAP)
        expected = entry_wire._post(entry_wire._MAP_POST, decision, "select:0")
        receipt_transcript.append((response if isinstance(response, BaseException) else elite_wire._http(response), expected))
        receipt_connector, receipt_credentials = elite_wire._Connector(receipt_transcript), elite_wire._Credentials()
        def actual_receipt_failure() -> dict[str, object]:
            with entry_wire._clock():
                return elite_wire.run._run_bounded_run(receipt_credentials, receipt_connector, "first-legal", "first-card", "elite", "safe", 3, entry_phase="map")
        with patch.object(live.run, "operation", side_effect=actual_receipt_failure):
            _expect_failure(live.operation, code)
        receipt_credentials.require_zeroed()
        receipt_connector.require_used_clean(1)
    with patch.object(live.run, "operation", side_effect=ToolFailure(EXIT_MISMATCH, "SYNTHETIC-ARBITRARY-CANARY")):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    with patch.object(live.run, "operation", side_effect=ToolFailure(EXIT_MISMATCH, ["SYNTHETIC-CANARY"])):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    with patch.object(live.run, "operation", side_effect=KeyboardInterrupt):
        try:
            live.operation()
        except KeyboardInterrupt:
            pass
        else:
            fail(EXIT_MISMATCH, "run_acceptance_fixture_interrupt_swallowed")
    with patch.object(live.run, "operation", side_effect=SystemExit("SYNTHETIC-CANARY")):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
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
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(live.run, "operation", side_effect=SystemExit("SYNTHETIC-CANARY")), redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(live.operation)
    if exit_code != EXIT_INTERNAL or "CANARY" in stdout.getvalue() + stderr.getvalue():
        fail(EXIT_MISMATCH, "run_acceptance_fixture_system_exit_output")


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
