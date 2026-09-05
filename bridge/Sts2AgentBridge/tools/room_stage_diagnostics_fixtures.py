#!/usr/bin/env python3
"""Deterministic unit fixtures for the bounded room-stage diagnostic."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import copy
import io
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import apply_room_live as room
import apply_room_live_fixtures as room_fixture
import apply_run_acceptance_live_fixtures as acceptance_fixture
import apply_run_live as run
import diagnose_run_room_live as diagnostic_cli
import probe_live as probe
from room_stage_diagnostics import RoomStageDiagnostics, validate_room_stage_record
from tool_common import EXIT_INTERNAL, EXIT_MISMATCH, ToolFailure, fail, main


def _require(condition: bool, code: str) -> None:
    if not condition:
        fail(EXIT_MISMATCH, code)


def _expect_value_failure(operation: object) -> None:
    try:
        operation()  # type: ignore[operator]
    except ValueError:
        return
    fail(EXIT_MISMATCH, "room_diagnostic_fixture_expected_value_failure")


def _fill_complete(diagnostics: RoomStageDiagnostics, action_count: int = 2) -> None:
    diagnostics.enter_context_validation()
    diagnostics.begin_health_read()
    diagnostics.begin_manifest_read()
    for index in range(action_count):
        diagnostics.begin_room_read()
        diagnostics.begin_room_validation()
        diagnostics.validated_observation("ready", "rest_site")
        diagnostics.begin_action_exchange(
            "rest_heal" if index == 0 else "rest_proceed"
        )
        diagnostics.begin_action_receipt()
        diagnostics.accept_receipt()
        diagnostics.mark_post_action()
    diagnostics.begin_room_read()
    diagnostics.begin_room_validation()
    diagnostics.validated_observation("complete")
    diagnostics.mark_complete()


def _fill_waiting(diagnostics: RoomStageDiagnostics) -> None:
    diagnostics.enter_context_validation()
    diagnostics.begin_health_read()
    diagnostics.begin_manifest_read()
    diagnostics.begin_room_read()
    diagnostics.begin_room_validation()
    diagnostics.validated_observation("ready", "rest_site")
    diagnostics.begin_action_exchange("rest_heal")
    diagnostics.begin_action_receipt()
    diagnostics.accept_receipt()
    diagnostics.mark_post_action()
    diagnostics.begin_room_read()
    diagnostics.begin_room_validation()
    diagnostics.validated_observation("waiting")
    diagnostics.mark_room_waiting()


def _record_contract_and_corruption() -> None:
    default = RoomStageDiagnostics().record()
    _require(
        default
        == {
            "stage": "not_entered",
            "last_observation_status": "none",
            "last_ready_kind": "none",
            "action_exchange_attempt_count": 0,
            "accepted_receipt_count": 0,
            "last_attempted_action": "none",
            "last_accepted_action": "none",
            "completion_confirmed": False,
        },
        "room_diagnostic_fixture_default_record",
    )
    diagnostics = RoomStageDiagnostics()
    _fill_complete(diagnostics)
    complete = diagnostics.record()
    _require(
        complete["stage"] == "complete"
        and complete["action_exchange_attempt_count"] == 2
        and complete["accepted_receipt_count"] == 2
        and complete["last_attempted_action"] == "rest_proceed"
        and complete["last_accepted_action"] == "rest_proceed"
        and complete["completion_confirmed"] is True,
        "room_diagnostic_fixture_complete_record",
    )
    corruptions = (
        ("stage", "RAW-CANARY"),
        ("last_observation_status", "RAW-CANARY"),
        ("last_ready_kind", "RAW-CANARY"),
        ("action_exchange_attempt_count", True),
        ("action_exchange_attempt_count", 13),
        ("accepted_receipt_count", 0),
        ("last_attempted_action", "event_choice"),
        ("last_accepted_action", "none"),
        ("completion_confirmed", False),
    )
    for name, value in corruptions:
        malformed = dict(complete)
        malformed[name] = value
        _expect_value_failure(lambda malformed=malformed: validate_room_stage_record(malformed))
    extra = dict(complete)
    extra["raw"] = "RAW-CANARY"
    _expect_value_failure(lambda: validate_room_stage_record(extra))
    reordered = {name: complete[name] for name in reversed(tuple(complete))}
    _expect_value_failure(lambda: validate_room_stage_record(reordered))

    replacement = RoomStageDiagnostics()
    replacement.enter_context_validation()
    replacement.begin_health_read()
    replacement.begin_manifest_read()
    replacement.begin_room_read()
    replacement.begin_room_validation()
    replacement.validated_observation("ready", "rest_site")
    replacement.begin_action_exchange("rest_heal")
    replacement.begin_action_receipt()
    replacement.accept_receipt()
    replacement.mark_post_action()
    replacement.begin_room_read()
    replacement.begin_room_validation()
    replacement.validated_observation("ready", "event")
    replaced = replacement.record()
    _require(
        replaced["stage"] == "room_validation"
        and replaced["last_ready_kind"] == "event"
        and replaced["last_accepted_action"] == "rest_heal",
        "room_diagnostic_fixture_wrong_kind_ready_retained",
    )


def _room_client_default_parity_and_stages() -> None:
    heal = room_fixture._candidate(
        0, "rest_heal", "HEAL", enabled=True, supported=True
    )
    ready = room_fixture._ready(
        room_fixture._DECISION_ZERO,
        "rest_site",
        "choose_option",
        [heal],
        [room_fixture._legal(heal)],
    )
    responses = room_fixture._base_responses() + [
        ready,
        room_fixture._action_body(room_fixture._DECISION_ZERO, "choose:0"),
        room_fixture._COMPLETE_REST,
    ]
    requests = room_fixture._base_requests() + [
        room_fixture._get(room._ROOM_DECISION_ROUTE),
        room_fixture._post(room_fixture._DECISION_ZERO, "choose:0"),
        room_fixture._get(room._ROOM_DECISION_ROUTE),
    ]
    baseline_connector = room_fixture._Connector(
        [room_fixture._response(value) for value in responses], requests
    )
    baseline_credential = bytearray(room_fixture._CREDENTIAL)
    baseline = room._run_apply_room(
        baseline_credential, "safe", baseline_connector, expected_context=("rest_site", 4)
    )
    diagnostic_connector = room_fixture._Connector(
        [room_fixture._response(value) for value in responses], requests
    )
    diagnostic_credential = bytearray(room_fixture._CREDENTIAL)
    diagnostics = RoomStageDiagnostics()
    observed = room._run_apply_room(
        diagnostic_credential,
        "safe",
        diagnostic_connector,
        expected_context=("rest_site", 4),
        diagnostics=diagnostics,
    )
    _require(baseline == observed, "room_diagnostic_fixture_default_parity")
    _require(
        diagnostics.record()["stage"] == "complete"
        and diagnostics.record()["accepted_receipt_count"] == 1,
        "room_diagnostic_fixture_room_complete",
    )
    _require(
        not any(baseline_credential) and not any(diagnostic_credential),
        "room_diagnostic_fixture_credential_cleanup",
    )
    baseline_connector.assert_cleanup()
    diagnostic_connector.assert_cleanup()


def _room_client_failures_and_cleanup() -> None:
    heal = room_fixture._candidate(
        0, "rest_heal", "HEAL", enabled=True, supported=True
    )
    ready = room_fixture._ready(
        room_fixture._DECISION_ZERO,
        "rest_site",
        "choose_option",
        [heal],
        [room_fixture._legal(heal)],
    )
    responses = room_fixture._base_responses() + [
        ready,
        room_fixture._action_body(
            room_fixture._DECISION_ZERO, "choose:0", accepted=False
        ),
    ]
    requests = room_fixture._base_requests() + [
        room_fixture._get(room._ROOM_DECISION_ROUTE),
        room_fixture._post(room_fixture._DECISION_ZERO, "choose:0"),
    ]
    connector = room_fixture._Connector(
        [room_fixture._response(value) for value in responses], requests
    )
    credential = bytearray(room_fixture._CREDENTIAL)
    diagnostics = RoomStageDiagnostics()
    try:
        room._run_apply_room(credential, "safe", connector, diagnostics=diagnostics)
    except ToolFailure as failure:
        _require(
            failure.exit_code == EXIT_MISMATCH
            and failure.error_code == "room_action_stale_decision",
            "room_diagnostic_fixture_rejected_receipt_code",
        )
    else:
        fail(EXIT_MISMATCH, "room_diagnostic_fixture_rejected_receipt_passed")
    record = diagnostics.record()
    _require(
        record["stage"] == "action_receipt"
        and record["action_exchange_attempt_count"] == 1
        and record["accepted_receipt_count"] == 0,
        "room_diagnostic_fixture_rejected_receipt_stage",
    )
    _require(not any(credential), "room_diagnostic_fixture_rejected_credential")
    connector.assert_cleanup()

    event = room_fixture._candidate(
        0, "event_option", "EVENT.SAFE", enabled=True, supported=True
    )
    event_ready = room_fixture._ready(
        room_fixture._DECISION_ONE,
        "event",
        "choose_option",
        [event],
        [room_fixture._legal(event)],
    )
    replacement_responses = room_fixture._base_responses() + [
        ready,
        room_fixture._action_body(room_fixture._DECISION_ZERO, "choose:0"),
        event_ready,
    ]
    replacement_requests = room_fixture._base_requests() + [
        room_fixture._get(room._ROOM_DECISION_ROUTE),
        room_fixture._post(room_fixture._DECISION_ZERO, "choose:0"),
        room_fixture._get(room._ROOM_DECISION_ROUTE),
    ]
    replacement_connector = room_fixture._Connector(
        [room_fixture._response(value) for value in replacement_responses],
        replacement_requests,
    )
    replacement_credential = bytearray(room_fixture._CREDENTIAL)
    replacement_diagnostics = RoomStageDiagnostics()
    try:
        room._run_apply_room(
            replacement_credential,
            "safe",
            replacement_connector,
            diagnostics=replacement_diagnostics,
        )
    except ToolFailure as failure:
        _require(
            failure.error_code == "room_transition_mismatch",
            "room_diagnostic_fixture_replacement_code",
        )
    else:
        fail(EXIT_MISMATCH, "room_diagnostic_fixture_replacement_passed")
    replacement_record = replacement_diagnostics.record()
    _require(
        replacement_record["stage"] == "room_validation"
        and replacement_record["last_observation_status"] == "ready"
        and replacement_record["last_ready_kind"] == "event"
        and replacement_record["accepted_receipt_count"] == 1
        and replacement_record["last_accepted_action"] == "rest_heal",
        "room_diagnostic_fixture_replacement_record",
    )
    _require(
        not any(replacement_credential),
        "room_diagnostic_fixture_replacement_credential",
    )
    replacement_connector.assert_cleanup()

    class TransportConnector(room_fixture._Connector):
        def __call__(self) -> object:
            if self.offset == 3:
                raise TimeoutError("RAW-TRANSPORT-CANARY")
            return super().__call__()

    transport_responses = room_fixture._base_responses() + [ready]
    transport_requests = room_fixture._base_requests() + [
        room_fixture._get(room._ROOM_DECISION_ROUTE)
    ]
    transport = TransportConnector(
        [room_fixture._response(value) for value in transport_responses],
        transport_requests,
    )
    transport_credential = bytearray(room_fixture._CREDENTIAL)
    transport_diagnostics = RoomStageDiagnostics()
    try:
        room._run_apply_room(
            transport_credential, "safe", transport, diagnostics=transport_diagnostics
        )
    except ToolFailure as failure:
        _require(
            failure.error_code == "room_action_transport_failure",
            "room_diagnostic_fixture_transport_code",
        )
    else:
        fail(EXIT_MISMATCH, "room_diagnostic_fixture_transport_passed")
    _require(
        transport_diagnostics.record()["stage"] == "action_exchange",
        "room_diagnostic_fixture_transport_stage",
    )
    _require(
        not any(transport_credential), "room_diagnostic_fixture_transport_credential"
    )
    transport.assert_cleanup()

    class ExplodingDiagnostics(RoomStageDiagnostics):
        def begin_room_validation(self) -> None:
            super().begin_room_validation()
            raise RuntimeError("RAW-DIAGNOSTIC-CANARY")

    exploding_connector = room_fixture._Connector(
        [room_fixture._response(value) for value in transport_responses],
        transport_requests,
    )
    exploding_credential = bytearray(room_fixture._CREDENTIAL)
    try:
        room._run_apply_room(
            exploding_credential,
            "safe",
            exploding_connector,
            diagnostics=ExplodingDiagnostics(),
        )
    except RuntimeError:
        pass
    else:
        fail(EXIT_MISMATCH, "room_diagnostic_fixture_callback_passed")
    _require(
        not any(exploding_credential), "room_diagnostic_fixture_callback_credential"
    )
    exploding_connector.assert_cleanup()


def _run_propagation_and_default_signature() -> None:
    source = acceptance_fixture._entry_room_handoff()
    prefix = source["entry_prefix"]
    handoff = source["room_handoff"]
    _require(
        isinstance(prefix, dict) and isinstance(handoff, dict),
        "room_diagnostic_fixture_source",
    )
    credentials: list[bytearray] = []

    def credential_loader() -> bytearray:
        value = bytearray(b"x" * 64)
        credentials.append(value)
        return value

    def map_runner(credential: bytearray, provider: str, connector: object) -> object:
        return copy.deepcopy(prefix["map"])

    def room_waiter(credential: bytearray, kind: str, connector: object) -> object:
        return copy.deepcopy(handoff["preflight"])

    def map_waiter(credential: bytearray, connector: object) -> int:
        return 1

    calls: list[object] = []

    def legacy_room_runner(
        credential: bytearray,
        provider: str,
        connector: object,
        *,
        expected_context: object = None,
    ) -> object:
        calls.append(expected_context)
        return copy.deepcopy(handoff["room"])

    baseline = run._run_bounded_run(
        credential_loader,
        object(),
        "first-legal",
        "first-card",
        "first",
        "safe",
        1,
        map_runner=map_runner,
        room_waiter=room_waiter,
        room_runner=legacy_room_runner,
        map_waiter=map_waiter,
        entry_phase="map",
    )
    diagnostics = RoomStageDiagnostics()

    def diagnostic_room_runner(
        credential: bytearray,
        provider: str,
        connector: object,
        *,
        expected_context: object = None,
        diagnostics: object = None,
    ) -> object:
        calls.append((expected_context, diagnostics))
        return copy.deepcopy(handoff["room"])

    observed = run._run_bounded_run(
        credential_loader,
        object(),
        "first-legal",
        "first-card",
        "first",
        "safe",
        1,
        map_runner=map_runner,
        room_waiter=room_waiter,
        room_runner=diagnostic_room_runner,
        map_waiter=map_waiter,
        entry_phase="map",
        room_diagnostics=diagnostics,
    )
    _require(baseline == observed, "room_diagnostic_fixture_run_parity")
    _require(
        calls == [("rest_site", 4), (("rest_site", 4), diagnostics)],
        "room_diagnostic_fixture_run_forwarding",
    )
    _require(
        all(not any(value) for value in credentials),
        "room_diagnostic_fixture_run_credentials",
    )


def _cli_success_failure_and_suppression() -> None:
    no_room_result = acceptance_fixture._default_defeat()
    for argument_count in (14, 16):
        arguments = ["RAW-ARGUMENT-CANARY"] * argument_count

        def no_room_operation(*, room_diagnostics: object = None) -> object:
            _require(
                isinstance(room_diagnostics, RoomStageDiagnostics)
                and sys.argv[1:] == arguments,
                "room_diagnostic_fixture_cli_delegation",
            )
            return no_room_result

        with patch.object(sys, "argv", ["diagnose_run_room_live.py", *arguments]), patch.object(
            diagnostic_cli.run, "_operation", side_effect=no_room_operation
        ) as operation:
            payload, exit_code = diagnostic_cli._execute()
        _require(
            operation.call_count == 1
            and exit_code == 0
            and payload["status"] == "passed"
            and payload["code"] == "none"
            and payload["room"]["stage"] == "not_entered"
            and payload["run_acceptance"]["action_totals"]["room"] == 0,
            "room_diagnostic_fixture_cli_no_room_success",
        )

    room_result = acceptance_fixture._entry_room_handoff()

    def room_operation(*, room_diagnostics: object = None) -> object:
        _require(
            isinstance(room_diagnostics, RoomStageDiagnostics),
            "room_diagnostic_fixture_cli_recorder",
        )
        _fill_complete(room_diagnostics)
        return room_result

    with patch.object(diagnostic_cli.run, "_operation", side_effect=room_operation):
        payload, exit_code = diagnostic_cli._execute()
    _require(
        exit_code == 0
        and payload["status"] == "passed"
        and payload["room"]["accepted_receipt_count"] == 2
        and payload["run_acceptance"]["action_totals"]["room"] == 2,
        "room_diagnostic_fixture_cli_room_success",
    )

    def known_failure(*, room_diagnostics: object = None) -> object:
        _require(isinstance(room_diagnostics, RoomStageDiagnostics), "room_diagnostic_fixture_known_recorder")
        _fill_waiting(room_diagnostics)
        raise ToolFailure(EXIT_MISMATCH, "room_interaction_timeout")

    with patch.object(diagnostic_cli.run, "_operation", side_effect=known_failure):
        payload, exit_code = diagnostic_cli._execute()
    _require(
        exit_code == EXIT_MISMATCH
        and payload["code"] == "room_interaction_timeout"
        and payload["room"]["stage"] == "room_waiting"
        and payload["run_acceptance"] is None,
        "room_diagnostic_fixture_cli_known_failure",
    )

    for failure in (
        ToolFailure(EXIT_MISMATCH, "RAW-UNKNOWN-CANARY"),
        ToolFailure(True, "room_interaction_timeout"),
        ToolFailure(EXIT_MISMATCH, ["RAW-CANARY"]),
    ):
        with patch.object(diagnostic_cli.run, "_operation", side_effect=failure):
            payload, exit_code = diagnostic_cli._execute()
        _require(
            exit_code == EXIT_INTERNAL
            and payload["code"] == "internal_failure"
            and "CANARY" not in str(payload),
            "room_diagnostic_fixture_cli_unknown_failure",
        )

    with patch.object(diagnostic_cli.run, "_operation", side_effect=KeyboardInterrupt):
        payload, exit_code = diagnostic_cli._execute()
    _require(
        exit_code == EXIT_INTERNAL
        and payload["code"] == "interrupted"
        and payload["run_acceptance"] is None,
        "room_diagnostic_fixture_cli_interrupted",
    )

    def noisy_failure(*, room_diagnostics: object = None) -> object:
        print("RAW-STDOUT-CANARY")
        print("RAW-STDERR-CANARY", file=sys.stderr)
        raise RuntimeError("RAW-EXCEPTION-CANARY")

    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(diagnostic_cli.run, "_operation", side_effect=noisy_failure), redirect_stdout(
        stdout
    ), redirect_stderr(stderr):
        exit_code = diagnostic_cli.main()
    _require(
        exit_code == EXIT_INTERNAL
        and stderr.getvalue() == ""
        and "CANARY" not in stdout.getvalue()
        and stdout.getvalue()
        == '{"schema_version":1,"status":"failed","milestone":"r0i_run_room_diagnostic","code":"internal_failure","room":{"stage":"not_entered","last_observation_status":"none","last_ready_kind":"none","action_exchange_attempt_count":0,"accepted_receipt_count":0,"last_attempted_action":"none","last_accepted_action":"none","completion_confirmed":false},"run_acceptance":null}\n',
        "room_diagnostic_fixture_cli_suppression",
    )


def _cli_corruption_crosscheck_and_cleanup() -> None:
    room_result = acceptance_fixture._entry_room_handoff()

    def corrupt_state(*, room_diagnostics: object = None) -> object:
        _require(isinstance(room_diagnostics, RoomStageDiagnostics), "room_diagnostic_fixture_corrupt_recorder")
        room_diagnostics.stage = "RAW-STATE-CANARY"
        raise RuntimeError("RAW-EXCEPTION-CANARY")

    with patch.object(diagnostic_cli.run, "_operation", side_effect=corrupt_state):
        payload, exit_code = diagnostic_cli._execute()
    _require(
        exit_code == EXIT_INTERNAL
        and payload["room"] is None
        and payload["run_acceptance"] is None
        and "CANARY" not in str(payload),
        "room_diagnostic_fixture_cli_state_corruption",
    )

    def mismatched_counts(*, room_diagnostics: object = None) -> object:
        _require(isinstance(room_diagnostics, RoomStageDiagnostics), "room_diagnostic_fixture_crosscheck_recorder")
        _fill_complete(room_diagnostics, 1)
        return room_result

    with patch.object(diagnostic_cli.run, "_operation", side_effect=mismatched_counts):
        payload, exit_code = diagnostic_cli._execute()
    _require(
        exit_code == EXIT_INTERNAL
        and payload["code"] == "internal_failure"
        and payload["run_acceptance"] is None,
        "room_diagnostic_fixture_cli_crosscheck",
    )

    mutable = bytearray(b"RAW-MUTABLE-CANARY")
    malformed = copy.deepcopy(acceptance_fixture._default_defeat())
    malformed["raw"] = mutable
    with patch.object(diagnostic_cli.run, "_operation", return_value=malformed):
        payload, exit_code = diagnostic_cli._execute()
    _require(
        exit_code == EXIT_INTERNAL
        and not any(mutable)
        and payload["run_acceptance"] is None,
        "room_diagnostic_fixture_cli_mutable_cleanup",
    )

    with patch.object(diagnostic_cli.run, "_operation", return_value=acceptance_fixture._default_defeat()), patch.object(
        diagnostic_cli.acceptance_wrapper, "_clear_mutable_buffers", return_value=False
    ):
        payload, exit_code = diagnostic_cli._execute()
    _require(
        exit_code == EXIT_INTERNAL
        and payload["room"] is None
        and payload["run_acceptance"] is None,
        "room_diagnostic_fixture_cli_cleanup_failure",
    )

    summary = diagnostic_cli._validate_run_acceptance_summary(
        diagnostic_cli.summarize_run_acceptance_result(
            acceptance_fixture._default_defeat()
        )
    )
    malformed_summary = dict(summary)
    malformed_summary["raw"] = "RAW-CANARY"
    _expect_value_failure(
        lambda: diagnostic_cli._validate_run_acceptance_summary(malformed_summary)
    )
    bool_count = copy.deepcopy(summary)
    bool_count["action_totals"]["room"] = False
    _expect_value_failure(
        lambda: diagnostic_cli._validate_run_acceptance_summary(bool_count)
    )
    for name in ("status", "milestone", "terminal_combat_outcome"):
        wrong_type = copy.deepcopy(summary)
        wrong_type[name] = True
        _expect_value_failure(
            lambda wrong_type=wrong_type: diagnostic_cli._validate_run_acceptance_summary(
                wrong_type
            )
        )

    with patch.object(
        diagnostic_cli, "RoomStageDiagnostics", side_effect=RuntimeError("RAW-CONSTRUCTOR-CANARY")
    ):
        payload, exit_code = diagnostic_cli._execute()
    _require(
        exit_code == EXIT_INTERNAL
        and payload["room"] is None
        and payload["run_acceptance"] is None
        and "CANARY" not in str(payload),
        "room_diagnostic_fixture_cli_constructor_failure",
    )


def operation() -> dict[str, object]:
    _record_contract_and_corruption()
    _room_client_default_parity_and_stages()
    _room_client_failures_and_cleanup()
    _run_propagation_and_default_signature()
    _cli_success_failure_and_suppression()
    _cli_corruption_crosscheck_and_cleanup()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "room_stage_diagnostics_fixtures",
        "check_count": 6,
    }


if __name__ == "__main__":
    main(operation)
