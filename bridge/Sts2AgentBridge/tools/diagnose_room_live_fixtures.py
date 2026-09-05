#!/usr/bin/env python3
"""Literal actual-client fixtures for the direct room diagnostic."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import copy
import io
import json
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import apply_room_live as room
import diagnose_room_live as direct
import diagnose_run_room_wire_fixtures as wire
import probe_live as probe
from room_stage_diagnostics import RoomStageDiagnostics
from tool_common import EXIT_INTERNAL, EXIT_MISMATCH, ToolFailure, fail, main, run_cli
from verify_room_acceptance import summarize_room_result


_ARGS = [
    "--user-profile",
    wire._PROFILE,
    "--effective-uid",
    "501",
    "--decision-provider",
    "safe",
]
_OUTPUT_KEYS = ("schema_version", "status", "milestone", "code", "room")


def _require(condition: bool, code: str) -> None:
    if not condition:
        fail(EXIT_MISMATCH, code)


def _record(
    stage: str,
    status: str = "none",
    kind: str = "none",
    attempts: int = 0,
    accepted: int = 0,
    attempted_action: str = "none",
    accepted_action: str = "none",
    complete: bool = False,
) -> dict[str, object]:
    return {
        "stage": stage,
        "last_observation_status": status,
        "last_ready_kind": kind,
        "action_exchange_attempt_count": attempts,
        "accepted_receipt_count": accepted,
        "last_attempted_action": attempted_action,
        "last_accepted_action": accepted_action,
        "completion_confirmed": complete,
    }


def _failed(code: str, record: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "failed",
        "milestone": "r0i_room_diagnostic",
        "code": code,
        "room": record,
    }


def _event_ready(decision: str) -> bytes:
    return wire._event_ready(decision)


def _event_action(decision: str) -> wire.Exchange:
    return wire._exchange(
        wire._request(wire._ROOM_ACTION_ROUTE, decision, "choose:1"),
        wire._receipt(decision, "choose:1"),
    )


def _event_complete() -> bytes:
    return wire._room_inactive(
        "complete", screen_kind="event", ordinal=wire._ROOM_ORDINAL
    )


def _invoke(
    transcript: wire.Transcript,
    *,
    arguments: object = None,
) -> tuple[int, dict[str, object]]:
    selected = _ARGS if arguments is None else arguments
    exit_code, payload = wire._invoke(direct, transcript, args=selected)
    _require(
        type(payload) is dict and tuple(payload) == _OUTPUT_KEYS,
        "direct_room_fixture_output_shape",
    )
    room_record = payload["room"]
    _require(
        room_record is None
        or type(room_record) is dict
        and tuple(room_record) == wire._ROOM_KEYS,
        "direct_room_fixture_record_shape",
    )
    return exit_code, payload


def _execute(
    exchanges: list[wire.Exchange],
    expected: dict[str, object],
    *,
    exit_code: int = EXIT_MISMATCH,
    posts: int = 0,
    leak: object = None,
) -> None:
    transcript = wire.Transcript(exchanges, leak=leak)
    observed_exit, payload = _invoke(transcript)
    _require(observed_exit == exit_code, "direct_room_fixture_exit")
    _require(payload == expected, "direct_room_fixture_payload")
    transcript.assert_clean(posts)


def _waiting_cases() -> None:
    waiting = wire._base() + [
        wire._exchange(wire._GET_ROOM, wire._ROOM_WAITING) for _ in range(3)
    ]
    _execute(
        waiting,
        _failed(
            "room_interaction_timeout",
            _record("room_waiting", status="waiting"),
        ),
    )

    decision = wire._IDS[4]
    event_waiting = wire._base() + [
        wire._exchange(wire._GET_ROOM, _event_ready(decision)),
        _event_action(decision),
        *[
            wire._exchange(wire._GET_ROOM, wire._ROOM_WAITING)
            for _ in range(3)
        ],
    ]
    _execute(
        event_waiting,
        _failed(
            "room_interaction_timeout",
            _record(
                "room_waiting",
                "waiting",
                "event",
                1,
                1,
                "event_choice",
                "event_choice",
            ),
        ),
        posts=1,
        leak=("source", "stderr"),
    )


def _unsupported_after_accepted_event() -> None:
    decision = wire._IDS[4]
    unsupported = wire._room_inactive(
        "unsupported",
        screen_kind="event",
        ordinal=wire._ROOM_ORDINAL,
    )
    _execute(
        wire._base()
        + [
            wire._exchange(wire._GET_ROOM, _event_ready(decision)),
            _event_action(decision),
            wire._exchange(wire._GET_ROOM, unsupported),
        ],
        _failed(
            "room_state_unsupported",
            _record(
                "room_validation",
                "unsupported",
                "event",
                1,
                1,
                "event_choice",
                "event_choice",
            ),
        ),
        posts=1,
    )


def _receipt_failures() -> None:
    decision = wire._IDS[4]
    prefix = wire._base() + [wire._exchange(wire._GET_ROOM, _event_ready(decision))]
    action_request = wire._request(wire._ROOM_ACTION_ROUTE, decision, "choose:1")
    exchange = _record(
        "action_exchange", "ready", "event", 1, 0, "event_choice", "none"
    )
    _execute(
        prefix + [wire._exchange(action_request, OSError(wire._EXCEPTION))],
        _failed("room_action_transport_failure", exchange),
        posts=1,
    )
    receipt = _record(
        "action_receipt", "ready", "event", 1, 0, "event_choice", "none"
    )
    for body in (
        b'{"schema_version":1,"status":"unknown"}',
        wire._receipt(decision, "choose:1", decision_override=wire._IDS[9]),
    ):
        _execute(
            prefix + [wire._exchange(action_request, body)],
            _failed("room_action_response_mismatch", receipt),
            posts=1,
        )


def _successful_event() -> dict[str, object]:
    decision = wire._IDS[4]
    return {
        "exchanges": wire._base()
        + [
            wire._exchange(wire._GET_ROOM, _event_ready(decision)),
            _event_action(decision),
            wire._exchange(wire._GET_ROOM, _event_complete()),
        ],
        "payload": {
            "schema_version": 1,
            "status": "passed",
            "milestone": "r0i_room_diagnostic",
            "code": "none",
            "room": _record(
                "complete",
                "complete",
                "event",
                1,
                1,
                "event_choice",
                "event_choice",
                True,
            ),
        },
    }


def _success_and_discarded_summary() -> None:
    case = _successful_event()
    exchanges = case["exchanges"]
    expected = case["payload"]
    _require(
        isinstance(exchanges, list) and isinstance(expected, dict),
        "direct_room_fixture_success_case",
    )
    _execute(copy.deepcopy(exchanges), expected, exit_code=0, posts=1)
    _require(
        tuple(expected) == _OUTPUT_KEYS
        and "run_acceptance" not in expected
        and "accepted_action_count" not in expected,
        "direct_room_fixture_summary_not_emitted",
    )


def _legacy_operation_parity() -> None:
    payload = {"unchanged": True}
    calls: list[dict[str, object]] = []
    credentials: list[bytearray] = []
    connector = object()

    def loader(*_: object) -> bytearray:
        credential = bytearray(wire._CREDENTIAL)
        credentials.append(credential)
        return credential

    def producer(
        credential: bytearray,
        provider: str,
        actual_connector: object,
        **keywords: object,
    ) -> dict[str, object]:
        _require(
            provider == "safe" and actual_connector is connector,
            "direct_room_fixture_operation_arguments",
        )
        calls.append(dict(keywords))
        return payload

    diagnostics = RoomStageDiagnostics()
    with patch.object(room, "parse_args", return_value=(wire._PROFILE, 501, "safe")), patch.object(
        room, "absolute_path", return_value=Path(wire._PROFILE)
    ), patch.object(room.probe, "_require_identity", return_value=501), patch.object(
        room.probe, "_load_fixed_credential", side_effect=loader
    ), patch.object(room.probe, "_literal_loopback_connector", connector), patch.object(
        room, "_run_apply_room", side_effect=producer
    ):
        baseline = room._operation()
        observed = room._operation(diagnostics=diagnostics)
    _require(
        baseline is payload
        and observed is payload
        and calls == [{}, {"diagnostics": diagnostics}],
        "direct_room_fixture_default_parity",
    )
    _require(
        len(credentials) == 2 and all(not any(value) for value in credentials),
        "direct_room_fixture_operation_cleanup",
    )


def _argument_rejections() -> None:
    for arguments, expected_code in (
        ([], "invalid_invocation"),
        (
            [
                "--user-profile",
                wire._PROFILE,
                "--effective-uid",
                "501",
                "--decision-provider",
                "unsafe",
            ],
            "invalid_decision_provider",
        ),
    ):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["diagnose_room_live.py", *arguments]), patch.object(
            probe, "_require_identity"
        ) as identity, patch.object(probe, "_load_fixed_credential") as loader, patch.object(
            probe, "_literal_loopback_connector"
        ) as connector, redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = direct.main()
        expected = _failed(expected_code, _record("not_entered"))
        _require(
            exit_code == 2
            and stderr.getvalue() == ""
            and stdout.getvalue() == json.dumps(expected, separators=(",", ":")) + "\n"
            and not identity.called
            and not loader.called
            and not connector.called,
            "direct_room_fixture_argument_rejection",
        )

    class ChangingFailure(ToolFailure):
        def __init__(self) -> None:
            super().__init__(2, "invalid_decision_provider")
            self.exit_reads = 0
            self.code_reads = 0

        def __getattribute__(self, name: str) -> object:
            if name == "exit_code":
                reads = object.__getattribute__(self, "exit_reads")
                object.__setattr__(self, "exit_reads", reads + 1)
                return 2 if reads == 0 else "RAW-EXIT-CANARY"
            if name == "error_code":
                reads = object.__getattribute__(self, "code_reads")
                object.__setattr__(self, "code_reads", reads + 1)
                return (
                    "invalid_decision_provider"
                    if reads == 0
                    else "RAW-CODE-CANARY"
                )
            return object.__getattribute__(self, name)

    failure = ChangingFailure()
    with patch.object(direct.room, "_operation", side_effect=failure):
        payload, exit_code = direct._execute()
    _require(
        exit_code == 2
        and payload["code"] == "invalid_decision_provider"
        and failure.exit_reads == 1
        and failure.code_reads == 1
        and "CANARY" not in str(payload),
        "direct_room_fixture_changing_failure",
    )

    class FallbackChangingFailure(ToolFailure):
        def __init__(self) -> None:
            super().__init__(EXIT_MISMATCH, "room_interaction_timeout")
            self.exit_reads = 0
            self.code_reads = 0

        def __getattribute__(self, name: str) -> object:
            if name == "exit_code":
                reads = object.__getattribute__(self, "exit_reads")
                object.__setattr__(self, "exit_reads", reads + 1)
                return EXIT_MISMATCH if reads == 0 else 2
            if name == "error_code":
                reads = object.__getattribute__(self, "code_reads")
                object.__setattr__(self, "code_reads", reads + 1)
                return (
                    "room_interaction_timeout"
                    if reads == 0
                    else "room_action_transport_failure"
                )
            return object.__getattribute__(self, name)

    fallback = FallbackChangingFailure()
    with patch.object(direct.room, "_operation", side_effect=fallback):
        payload, exit_code = direct._execute()
    _require(
        exit_code == EXIT_MISMATCH
        and payload["code"] == "room_interaction_timeout"
        and fallback.exit_reads == 1
        and fallback.code_reads == 1,
        "direct_room_fixture_fallback_changing_failure",
    )

    class ThrowingFailure(ToolFailure):
        def __getattribute__(self, name: str) -> object:
            if name in ("exit_code", "error_code"):
                raise RuntimeError("RAW-GETTER-CANARY")
            return object.__getattribute__(self, name)

    throwing = ThrowingFailure(EXIT_MISMATCH, "room_interaction_timeout")
    with patch.object(direct.room, "_operation", side_effect=throwing):
        payload, exit_code = direct._execute()
    _require(
        exit_code == EXIT_INTERNAL
        and payload["code"] == "internal_failure"
        and "CANARY" not in str(payload),
        "direct_room_fixture_throwing_failure",
    )

    class ExplosiveText:
        def __init__(self) -> None:
            self.calls = 0

        def __str__(self) -> str:
            self.calls += 1
            raise RuntimeError("RAW-COERCION-CANARY")

    explosive = ExplosiveText()
    untyped = ToolFailure(EXIT_MISMATCH, explosive)
    with patch.object(direct.room, "_operation", side_effect=untyped):
        payload, exit_code = direct._execute()
    _require(
        exit_code == EXIT_INTERNAL
        and payload["code"] == "internal_failure"
        and explosive.calls == 0
        and "CANARY" not in str(payload),
        "direct_room_fixture_failure_normalization_no_coercion",
    )


def _cancellation_and_unknown_failure() -> None:
    decision = wire._IDS[4]
    request = wire._request(wire._ROOM_ACTION_ROUTE, decision, "choose:1")
    cancellation = wire._base() + [
        wire._exchange(wire._GET_ROOM, _event_ready(decision)),
        wire._exchange(
            request,
            wire._receipt(decision, "choose:1"),
            fail_after_first_chunk=True,
        ),
    ]
    _execute(
        cancellation,
        _failed(
            "interrupted",
            _record(
                "action_exchange",
                "ready",
                "event",
                1,
                0,
                "event_choice",
                "none",
            ),
        ),
        exit_code=EXIT_INTERNAL,
        posts=1,
    )
    unknown = wire._base() + [
        wire._exchange(wire._GET_ROOM, RuntimeError(wire._EXCEPTION))
    ]
    _execute(
        unknown,
        _failed("internal_failure", _record("room_read")),
        exit_code=EXIT_INTERNAL,
    )

    def noisy_failure(*_: object, **__: object) -> object:
        print(wire._EXCEPTION)
        print(wire._SOURCE.decode("ascii"), file=sys.stderr)
        raise RuntimeError(wire._EXCEPTION)

    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(direct.room, "_operation", side_effect=noisy_failure), redirect_stdout(
        stdout
    ), redirect_stderr(stderr):
        exit_code = direct.main()
    _require(
        exit_code == EXIT_INTERNAL
        and stderr.getvalue() == ""
        and wire._EXCEPTION not in stdout.getvalue()
        and wire._SOURCE.decode("ascii") not in stdout.getvalue(),
        "direct_room_fixture_noisy_failure",
    )


def _unsafe_state_and_cleanup_precedence() -> None:
    class CorruptingDiagnostics(RoomStageDiagnostics):
        def record(self) -> dict[str, object]:
            value = super().record()
            value["accepted_receipt_count"] = True
            return value

    case = _successful_event()
    exchanges = case["exchanges"]
    _require(isinstance(exchanges, list), "direct_room_fixture_corrupt_case")
    transcript = wire.Transcript(copy.deepcopy(exchanges))
    with patch.object(direct, "RoomStageDiagnostics", CorruptingDiagnostics):
        exit_code, payload = _invoke(transcript)
    _require(
        exit_code == EXIT_INTERNAL
        and payload == _failed("internal_failure", None),
        "direct_room_fixture_corrupt_state",
    )
    transcript.assert_clean(1)

    transcript = wire.Transcript(copy.deepcopy(exchanges))
    with patch.object(
        direct.acceptance_wrapper, "_clear_mutable_buffers", return_value=False
    ):
        exit_code, payload = _invoke(transcript)
    _require(
        exit_code == EXIT_INTERNAL
        and payload == _failed("internal_failure", None),
        "direct_room_fixture_cleanup_failure",
    )
    transcript.assert_clean(1)

    decision = wire._IDS[4]
    cancellation = wire._base() + [
        wire._exchange(wire._GET_ROOM, _event_ready(decision)),
        wire._exchange(
            wire._request(wire._ROOM_ACTION_ROUTE, decision, "choose:1"),
            wire._receipt(decision, "choose:1"),
            fail_after_first_chunk=True,
        ),
    ]
    transcript = wire.Transcript(cancellation)
    with patch.object(
        direct.acceptance_wrapper,
        "_clear_mutable_buffers",
        side_effect=RuntimeError(wire._EXCEPTION),
    ):
        exit_code, payload = _invoke(transcript)
    _require(
        exit_code == EXIT_INTERNAL
        and payload == _failed("internal_failure", None),
        "direct_room_fixture_cleanup_overrides_interrupt",
    )
    transcript.assert_clean(1)


def _result_count_crosscheck() -> None:
    case = _successful_event()
    exchanges = case["exchanges"]
    _require(isinstance(exchanges, list), "direct_room_fixture_count_case")
    transcript = wire.Transcript(copy.deepcopy(exchanges))
    with patch.object(
        direct,
        "summarize_room_result",
        return_value={
            "code": "room_result_valid",
            "accepted_action_count": 2,
            "route_count": 7,
        },
    ):
        exit_code, payload = _invoke(transcript)
    _require(
        exit_code == EXIT_INTERNAL
        and payload["code"] == "internal_failure"
        and payload["room"] == case["payload"]["room"],
        "direct_room_fixture_count_crosscheck",
    )
    transcript.assert_clean(1)


def _legacy_actual_cli_success() -> None:
    case = _successful_event()
    exchanges = case["exchanges"]
    _require(isinstance(exchanges, list), "direct_room_fixture_legacy_case")
    transcript = wire.Transcript(copy.deepcopy(exchanges))
    stdout, stderr = io.StringIO(), io.StringIO()
    with ExitStack() as stack:
        stack.enter_context(patch.object(sys, "argv", ["apply_room_live.py", *_ARGS]))
        stack.enter_context(patch.object(probe, "_require_identity", return_value=501))
        stack.enter_context(
            patch.object(
                probe, "_load_fixed_credential", side_effect=transcript.credential
            )
        )
        stack.enter_context(
            patch.object(
                probe, "_literal_loopback_connector", side_effect=transcript.connect
            )
        )
        stack.enter_context(
            patch.object(probe.time, "monotonic", side_effect=transcript.clock.monotonic)
        )
        stack.enter_context(
            patch.object(probe.time, "sleep", side_effect=transcript.clock.sleep)
        )
        stack.enter_context(redirect_stdout(stdout))
        stack.enter_context(redirect_stderr(stderr))
        exit_code = run_cli(room.operation)
    _require(exit_code == 0 and stderr.getvalue() == "", "direct_room_fixture_legacy_exit")
    legacy = json.loads(stdout.getvalue())
    summary = summarize_room_result(legacy)
    _require(
        summary["accepted_action_count"] == 1
        and legacy["screen_kind"] == "event"
        and legacy["status"] == "passed",
        "direct_room_fixture_legacy_result",
    )
    transcript.assert_clean(1)


def _disabled_sink_is_detected() -> None:
    case = _successful_event()
    exchanges = case["exchanges"]
    _require(isinstance(exchanges, list), "direct_room_fixture_sink_case")
    transcript = wire.Transcript(
        copy.deepcopy(exchanges), leak=("credential", "stdout")
    )

    class LeakingSink:
        def __init__(self) -> None:
            self.target = sys.stdout

        def write(self, value: str) -> int:
            return self.target.write(value)

        def flush(self) -> None:
            self.target.flush()

    try:
        with patch.object(
            direct.run_diagnostic, "_NonRetainingTextSink", LeakingSink
        ):
            _invoke(transcript)
    except ToolFailure as failure:
        _require(
            failure.error_code == "room_diagnostic_output_privacy",
            "direct_room_fixture_sink_mutant_code",
        )
    else:
        fail(EXIT_MISMATCH, "direct_room_fixture_sink_mutant_survived")
    transcript.assert_clean(1)


def operation() -> dict[str, object]:
    _waiting_cases()
    _unsupported_after_accepted_event()
    _receipt_failures()
    _success_and_discarded_summary()
    _legacy_operation_parity()
    _argument_rejections()
    _cancellation_and_unknown_failure()
    _unsafe_state_and_cleanup_precedence()
    _result_count_crosscheck()
    _legacy_actual_cli_success()
    _disabled_sink_is_detected()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "diagnose_room_live_fixtures",
        "check_count": 11,
    }


if __name__ == "__main__":
    main(operation)
