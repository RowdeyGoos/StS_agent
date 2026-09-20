#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
from collections.abc import Callable

import apply_room_live as room
import probe_live as probe
from tool_common import (
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    ToolFailure,
    fail,
    main,
)

_CREDENTIAL = b"0123456789abcdef" * 4
_DECISION_ZERO = "0" * 64
_DECISION_ONE = "1" * 64
_HEALTH = (
    b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"'
    b"00000000000000000000000000000000"
    b'"}'
)


def _encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _candidate(
    index: int,
    kind: str,
    stable_id: str,
    *,
    enabled: bool,
    supported: bool,
    is_proceed: bool = False,
    is_dangerous: bool = False,
) -> dict[str, object]:
    action_id = "proceed" if kind == "proceed" else f"choose:{index}"
    return {
        "candidate_index": index,
        "action_id": action_id,
        "kind": kind,
        "stable_id": stable_id,
        "enabled": enabled,
        "supported": supported,
        "is_proceed": is_proceed,
        "is_dangerous": is_dangerous,
    }


def _legal(candidate: dict[str, object]) -> dict[str, object]:
    action_id = str(candidate["action_id"])
    return {
        "action_id": action_id,
        "kind": "proceed_room" if action_id == "proceed" else "choose_room_option",
        "candidate_index": candidate["candidate_index"],
    }


def _ready(
    decision_id: str,
    screen_kind: str,
    phase: str,
    candidates: list[dict[str, object]],
    legal: list[dict[str, object]],
    *,
    ordinal: int = 4,
) -> bytes:
    return _encode({
        "schema_version": 1,
        "status": "ready",
        "decision_kind": "room",
        "actionable": True,
        "decision_id": decision_id,
        "screen_kind": screen_kind,
        "phase": phase,
        "room_ordinal": ordinal,
        "candidates": candidates,
        "legal_actions": legal,
    })


def _inactive(status: str, screen_kind: str, phase: str, ordinal: int | None) -> bytes:
    return _encode({
        "schema_version": 1,
        "status": status,
        "decision_kind": "room",
        "actionable": False,
        "decision_id": None,
        "screen_kind": screen_kind,
        "phase": phase,
        "room_ordinal": ordinal,
        "candidates": [],
        "legal_actions": [],
    })


_COMPLETE_REST = _inactive("complete", "rest_site", "complete", 4)
_COMPLETE_EVENT = _inactive("complete", "event", "complete", 4)
_UNSUPPORTED_EVENT = _inactive("unsupported", "event", "unsupported", 4)


def _response(body: bytes) -> bytes:
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
        b"Cache-Control: no-store\r\n"
        b"X-Content-Type-Options: nosniff\r\n"
        b"Connection: close\r\n"
        b"\r\n" + body
    )


def _get(route: str) -> bytes:
    return bytes(room._build_get_request(route, bytearray(_CREDENTIAL)))


def _post(decision_id: str, action_id: str) -> bytes:
    return bytes(room._build_action_request(bytearray(_CREDENTIAL), decision_id, action_id))


def _action_body(
    decision_id: str,
    action_id: str,
    *,
    accepted: bool = True,
) -> bytes:
    return _encode({
        "schema_version": 1,
        "status": "accepted" if accepted else "rejected",
        "mutation_state": "applied" if accepted else "none",
        "decision_id": decision_id,
        "action_id": action_id,
        "reason": "accepted" if accepted else "stale_decision",
    })


class _Socket:
    def __init__(self, response: bytes, expected_request: bytes) -> None:
        self.response = response
        self.expected_request = expected_request
        self.offset = 0
        self.closed = False
        self.write_shutdown = False
        self.request_buffers: list[bytearray] = []

    def settimeout(self, value: float) -> None:
        if value <= 0 or value > probe._SOCKET_OPERATION_TIMEOUT_SECONDS:
            fail(EXIT_MISMATCH, "room_fixture_timeout")

    def sendall(self, request: bytearray) -> None:
        if bytes(request) != self.expected_request:
            fail(EXIT_MISMATCH, "room_fixture_request")
        self.request_buffers.append(request)

    def shutdown(self, how: int) -> None:
        if how != probe.socket.SHUT_WR or not (self.request_buffers) or self.write_shutdown or self.closed:
            fail(EXIT_MISMATCH, "apply_room_live_fixture_half_close")
        self.write_shutdown = True

    def recv(self, maximum: int) -> bytes:
        if not self.write_shutdown:
            fail(EXIT_MISMATCH, "apply_room_live_fixture_receive_before_half_close")
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "room_fixture_receive_bound")
        if self.offset >= len(self.response):
            return b""
        end = min(self.offset + 23, len(self.response))
        result = self.response[self.offset:end]
        self.offset = end
        return result

    def close(self) -> None:
        self.closed = True


class _Connector:
    def __init__(self, responses: list[bytes], requests: list[bytes]) -> None:
        self.responses = responses
        self.requests = requests
        self.offset = 0
        self.sockets: list[_Socket] = []

    def __call__(self) -> _Socket:
        if self.offset >= len(self.responses):
            fail(EXIT_MISMATCH, "room_fixture_extra_connection")
        result = _Socket(self.responses[self.offset], self.requests[self.offset])
        self.offset += 1
        self.sockets.append(result)
        return result

    def assert_cleanup(self) -> None:
        if self.offset != len(self.responses):
            fail(EXIT_MISMATCH, "room_fixture_missing_connection")
        if any(not item.closed for item in self.sockets):
            fail(EXIT_MISMATCH, "room_fixture_socket_cleanup")
        for item in self.sockets:
            if any(any(request) for request in item.request_buffers):
                fail(EXIT_MISMATCH, "room_fixture_request_not_zeroed")


def _run_case(
    responses: list[bytes],
    requests: list[bytes],
    *,
    expected_screen: str,
    expected_actions: list[tuple[str, str]],
    expected_context: tuple[str, int] | None = None,
) -> None:
    connector = _Connector([_response(value) for value in responses], requests)
    credential = bytearray(_CREDENTIAL)
    payload = room._run_apply_room(
        credential,
        "safe",
        connector,
        expected_context=expected_context,
    )
    actions = payload.get("actions")
    actual = [] if not isinstance(actions, list) else [
        (str(value.get("action_id")), str(value.get("basis")))
        for value in actions if isinstance(value, dict)
    ]
    if (
        payload.get("status") != "passed"
        or payload.get("screen_kind") != expected_screen
        or payload.get("accepted_action_count") != len(expected_actions)
        or actual != expected_actions
        or payload.get("routes_checked") != len(requests)
    ):
        fail(EXIT_MISMATCH, "room_fixture_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "room_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _base_requests() -> list[bytes]:
    return [_get(probe._BASE_ROUTES[0][1]), _get(probe._BASE_ROUTES[1][1])]


def _base_responses() -> list[bytes]:
    return [_HEALTH, probe._MANIFEST_COMPATIBLE]


def _rest_heal_then_proceed() -> None:
    heal = _candidate(0, "rest_heal", "HEAL", enabled=True, supported=True)
    smith = _candidate(1, "rest_unsupported", "SMITH", enabled=True, supported=False)
    first = _ready(_DECISION_ZERO, "rest_site", "choose_option", [heal, smith], [_legal(heal)])
    spent_heal = _candidate(0, "rest_heal", "HEAL", enabled=False, supported=True)
    blocked_smith = _candidate(1, "rest_unsupported", "SMITH", enabled=True, supported=False)
    proceed = _candidate(
        2, "proceed", "proceed", enabled=True, supported=True, is_proceed=True,
    )
    second = _ready(
        _DECISION_ONE,
        "rest_site",
        "proceed",
        [spent_heal, blocked_smith, proceed],
        [_legal(proceed)],
    )
    requests = _base_requests() + [
        _get(room._ROOM_DECISION_ROUTE),
        _post(_DECISION_ZERO, "choose:0"),
        _get(room._ROOM_DECISION_ROUTE),
        _post(_DECISION_ONE, "proceed"),
        _get(room._ROOM_DECISION_ROUTE),
    ]
    responses = _base_responses() + [
        first,
        _action_body(_DECISION_ZERO, "choose:0"),
        second,
        _action_body(_DECISION_ONE, "proceed"),
        _COMPLETE_REST,
    ]
    _run_case(
        responses,
        requests,
        expected_screen="rest_site",
        expected_actions=[("choose:0", "rest_heal"), ("proceed", "proceed")],
    )


def _event_handles_indexed_game_proceed_and_rejects_fatal() -> None:
    safe = _candidate(0, "event_option", "EVENT.SAFE", enabled=True, supported=True)
    fatal = _candidate(
        1,
        "event_option",
        "EVENT.FATAL",
        enabled=False,
        supported=False,
        is_dangerous=True,
    )
    decision = _ready(
        _DECISION_ZERO,
        "event",
        "choose_option",
        [safe, fatal],
        [_legal(safe)],
    )
    proceed = _candidate(
        0,
        "event_option",
        "EVENT.PROCEED",
        enabled=True,
        supported=True,
    )
    proceed_decision = _ready(
        _DECISION_ONE,
        "event",
        "choose_option",
        [proceed],
        [_legal(proceed)],
    )
    requests = _base_requests() + [
        _get(room._ROOM_DECISION_ROUTE),
        _post(_DECISION_ZERO, "choose:0"),
        _get(room._ROOM_DECISION_ROUTE),
        _get(room._ROOM_DECISION_ROUTE),
        _post(_DECISION_ONE, "choose:0"),
        _get(room._ROOM_DECISION_ROUTE),
    ]
    responses = _base_responses() + [
        decision,
        _action_body(_DECISION_ZERO, "choose:0"),
        _inactive("waiting", "unknown", "unknown", None),
        proceed_decision,
        _action_body(_DECISION_ONE, "choose:0"),
        _COMPLETE_EVENT,
    ]
    _run_case(
        responses,
        requests,
        expected_screen="event",
        expected_actions=[
            ("choose:0", "event_first_supported"),
            ("choose:0", "event_first_supported"),
        ],
        expected_context=("event", 4),
    )


def _expect_failure(
    responses: list[bytes],
    requests: list[bytes],
    expected_code: str,
    *,
    expected_context: tuple[str, int] | None = None,
) -> None:
    connector = _Connector([_response(value) for value in responses], requests)
    credential = bytearray(_CREDENTIAL)
    try:
        room._run_apply_room(
            credential,
            "safe",
            connector,
            expected_context=expected_context,
        )
    except ToolFailure as failure:
        if failure.exit_code != EXIT_MISMATCH or failure.error_code != expected_code:
            fail(EXIT_MISMATCH, "room_fixture_wrong_rejection")
    else:
        fail(EXIT_MISMATCH, "room_fixture_unexpected_pass")
    if any(credential):
        fail(EXIT_MISMATCH, "room_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _expect_invocation_failure(operation: Callable[[], object], expected_code: str) -> None:
    try:
        operation()
    except ToolFailure as failure:
        if failure.exit_code == EXIT_INVALID_INVOCATION and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "room_fixture_wrong_invocation_rejection")
    fail(EXIT_MISMATCH, "room_fixture_invocation_unexpected_pass")


def operation() -> dict[str, object]:
    checks: list[str] = []
    _rest_heal_then_proceed()
    checks.append("rest_heal_then_proceed")
    _event_handles_indexed_game_proceed_and_rejects_fatal()
    checks.append("indexed_event_proceed_and_fatal_guard")

    event = _candidate(0, "event_option", "EVENT.SAFE", enabled=True, supported=True)
    decision = _ready(_DECISION_ZERO, "event", "choose_option", [event], [_legal(event)])
    _expect_failure(
        _base_responses() + [decision],
        _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
        "room_expected_context_mismatch",
        expected_context=("event", 5),
    )
    checks.append("same_kind_different_ordinal_rejected_before_post")
    _expect_failure(
        _base_responses() + [decision],
        _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
        "room_expected_context_mismatch",
        expected_context=("rest_site", 4),
    )
    checks.append("wrong_kind_rejected_before_post")
    _expect_failure(
        [],
        [],
        "room_expected_context_invalid",
        expected_context=("unknown", 4),
    )
    checks.append("invalid_expected_context_rejected_without_transport")
    _expect_failure(
        _base_responses() + [_COMPLETE_REST],
        _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
        "room_not_ready",
    )
    checks.append("initial_completion_is_not_readiness")
    prefix_requests = _base_requests() + [
        _get(room._ROOM_DECISION_ROUTE),
        _post(_DECISION_ZERO, "choose:0"),
    ]
    prefix_responses = _base_responses() + [
        decision,
        _action_body(_DECISION_ZERO, "choose:0"),
    ]
    _expect_failure(
        prefix_responses + [_UNSUPPORTED_EVENT],
        prefix_requests + [_get(room._ROOM_DECISION_ROUTE)],
        "room_state_unsupported",
    )
    checks.append("nested_unsupported_fails_closed")
    _expect_failure(
        prefix_responses + [decision],
        prefix_requests + [_get(room._ROOM_DECISION_ROUTE)],
        "room_decision_replayed",
    )
    checks.append("decision_replay_rejected")
    _expect_failure(
        prefix_responses + [_COMPLETE_REST],
        prefix_requests + [_get(room._ROOM_DECISION_ROUTE)],
        "room_completion_mismatch",
    )
    checks.append("wrong_post_action_completion_rejected")
    invalid_event_proceed = _candidate(
        0,
        "event_option",
        "EVENT.PROCEED",
        enabled=True,
        supported=True,
        is_proceed=True,
    )
    _expect_failure(
        _base_responses()
        + [
            _ready(
                _DECISION_ZERO,
                "event",
                "choose_option",
                [invalid_event_proceed],
                [_legal(invalid_event_proceed)],
            )
        ],
        _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
        "room_response_mismatch",
    )
    checks.append("wire_invalid_event_proceed_rejected")

    literal_event_proceed = _candidate(
        0,
        "proceed",
        "proceed",
        enabled=True,
        supported=True,
        is_proceed=True,
    )
    _expect_failure(
        _base_responses()
        + [
            _ready(
                _DECISION_ZERO,
                "event",
                "proceed",
                [literal_event_proceed],
                [_legal(literal_event_proceed)],
            )
        ],
        _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
        "room_response_mismatch",
    )
    checks.append("literal_event_proceed_rejected")

    heal = _candidate(0, "rest_heal", "HEAL", enabled=True, supported=True)
    disabled_proceed = _candidate(
        1,
        "proceed",
        "proceed",
        enabled=False,
        supported=True,
        is_proceed=True,
    )
    _expect_failure(
        _base_responses()
        + [
            _ready(
                _DECISION_ZERO,
                "rest_site",
                "choose_option",
                [heal, disabled_proceed],
                [_legal(heal)],
            )
        ],
        _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
        "room_response_mismatch",
    )
    checks.append("disabled_proceed_rejected")

    dangerous_event = _candidate(
        1,
        "event_option",
        "EVENT.FATAL",
        enabled=True,
        supported=False,
        is_dangerous=True,
    )
    _expect_failure(
        _base_responses()
        + [
            _ready(
                _DECISION_ZERO,
                "event",
                "choose_option",
                [event, dangerous_event],
                [_legal(event)],
            )
        ],
        _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
        "room_response_mismatch",
    )
    checks.append("enabled_dangerous_event_rejected")

    dangerous_rest = _candidate(
        1,
        "rest_unsupported",
        "SMITH",
        enabled=False,
        supported=False,
        is_dangerous=True,
    )
    _expect_failure(
        _base_responses()
        + [
            _ready(
                _DECISION_ZERO,
                "rest_site",
                "choose_option",
                [heal, dangerous_rest],
                [_legal(heal)],
            )
        ],
        _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
        "room_response_mismatch",
    )
    checks.append("dangerous_rest_unsupported_rejected")

    first_proceed = _candidate(
        0,
        "proceed",
        "proceed",
        enabled=True,
        supported=True,
        is_proceed=True,
    )
    duplicate_proceed = _candidate(
        1,
        "proceed",
        "proceed",
        enabled=True,
        supported=True,
        is_proceed=True,
    )
    _expect_failure(
        _base_responses()
        + [
            _ready(
                _DECISION_ZERO,
                "rest_site",
                "proceed",
                [first_proceed, duplicate_proceed],
                [_legal(first_proceed)],
            )
        ],
        _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
        "room_response_mismatch",
    )
    checks.append("duplicate_proceed_action_rejected")

    for invalid_version in (True, 1.0):
        invalid = json.loads(decision)
        invalid["schema_version"] = invalid_version
        _expect_failure(
            _base_responses() + [_encode(invalid)],
            _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
            "room_response_mismatch",
        )
    checks.append("non_integer_schema_versions_rejected")

    for invalid_index in (False, 0.0):
        invalid = json.loads(decision)
        invalid["candidates"][0]["candidate_index"] = invalid_index
        _expect_failure(
            _base_responses() + [_encode(invalid)],
            _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
            "room_response_mismatch",
        )
    checks.append("non_integer_candidate_indices_rejected")

    for invalid_unsupported in (
        _inactive("unsupported", "unknown", "unsupported", 4),
        _inactive("unsupported", "event", "unsupported", None),
    ):
        _expect_failure(
            _base_responses() + [invalid_unsupported],
            _base_requests() + [_get(room._ROOM_DECISION_ROUTE)],
            "room_response_mismatch",
        )
    checks.append("unsupported_screen_ordinal_pairing_rejected")

    queued_receipt = _encode({
        "schema_version": 1,
        "status": "accepted",
        "mutation_state": "queued",
        "decision_id": _DECISION_ZERO,
        "action_id": "choose:0",
        "reason": "accepted",
    })
    _expect_failure(
        _base_responses() + [decision, queued_receipt],
        prefix_requests,
        "room_action_response_mismatch",
    )
    checks.append("queued_room_receipt_rejected")

    _expect_failure(
        _base_responses() + [decision, _action_body(_DECISION_ZERO, "choose:0", accepted=False)],
        prefix_requests,
        "room_action_stale_decision",
    )
    checks.append("rejected_action_response")

    arguments = [
        "--user-profile", "/synthetic-profile",
        "--effective-uid", "501",
        "--decision-provider", "unknown",
    ]
    _expect_invocation_failure(
        lambda: room.parse_args(arguments),
        "invalid_decision_provider",
    )
    checks.append("unknown_provider")
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_room_live_fixtures",
        "checks": checks,
        "check_count": len(checks),
    }


if __name__ == "__main__":
    main(operation)
