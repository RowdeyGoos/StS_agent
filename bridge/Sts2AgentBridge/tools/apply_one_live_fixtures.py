#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from collections.abc import Callable

import apply_one_live as apply_one
import probe_live as probe
from tool_common import (
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    ToolFailure,
    fail,
    main,
)

_CREDENTIAL = b"0123456789abcdef" * 4
_DECISION_BEFORE = "0" * 64
_DECISION_AFTER = "1" * 64
_HEALTH = (
    b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"'
    b"00000000000000000000000000000000"
    b'"}'
)
_COMBAT_BEFORE = (
    b'{"schema_version":1,"status":"ready","decision_kind":"combat","actionable":true,'
    b'"decision_id":"' + _DECISION_BEFORE.encode("ascii") + b'","round":1,'
    b'"player":{"hp":80,"max_hp":80,"block":0,"energy":3},'
    b'"enemies":[{"index":0,"id":"NIBBIT","hp":43,"max_hp":43,"block":0,"intents":["attack"]}],'
    b'"hand":[{"hand_index":0,"id":"STRIKE_IRONCLAD","type":"attack","cost":"1","target_type":"anyenemy","playable":true},'
    b'{"hand_index":1,"id":"DEFEND_IRONCLAD","type":"skill","cost":"1","target_type":"self","playable":true}],'
    b'"legal_actions":[{"action_id":"play:0:0","kind":"play_card","hand_index":0,"target_index":0},'
    b'{"action_id":"play:1","kind":"play_card","hand_index":1,"target_index":null},'
    b'{"action_id":"end_turn","kind":"end_turn","hand_index":null,"target_index":null}]}'
)
_COMBAT_AFTER = (
    _COMBAT_BEFORE
    .replace(_DECISION_BEFORE.encode("ascii"), _DECISION_AFTER.encode("ascii"), 1)
    .replace(b'"block":0,"energy":3', b'"block":5,"energy":2', 1)
)


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
    return bytes(probe._build_request(route, bytearray(_CREDENTIAL)))


def _post(action_id: str) -> bytes:
    return bytes(probe._build_action_request(
        probe._ACTION_ROUTE,
        bytearray(_CREDENTIAL),
        _DECISION_BEFORE,
        action_id,
    ))


def _action_body(action_id: str, accepted: bool = True) -> bytes:
    status = b"accepted" if accepted else b"rejected"
    mutation = b"queued" if accepted else b"none"
    reason = b"accepted" if accepted else b"stale_decision"
    return (
        b'{"schema_version":1,"status":"' + status +
        b'","mutation_state":"' + mutation +
        b'","decision_id":"' + _DECISION_BEFORE.encode("ascii") +
        b'","action_id":"' + action_id.encode("ascii") +
        b'","reason":"' + reason + b'"}'
    )


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
            fail(EXIT_MISMATCH, "apply_fixture_timeout")

    def sendall(self, request: bytearray) -> None:
        if bytes(request) != self.expected_request:
            fail(EXIT_MISMATCH, "apply_fixture_request")
        self.request_buffers.append(request)

    def shutdown(self, how: int) -> None:
        if how != probe.socket.SHUT_WR or not (self.request_buffers) or self.write_shutdown or self.closed:
            fail(EXIT_MISMATCH, "apply_one_live_fixture_half_close")
        self.write_shutdown = True

    def recv(self, maximum: int) -> bytes:
        if not self.write_shutdown:
            fail(EXIT_MISMATCH, "apply_one_live_fixture_receive_before_half_close")
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "apply_fixture_receive_bound")
        if self.offset >= len(self.response):
            return b""
        end = min(self.offset + 19, len(self.response))
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
            fail(EXIT_MISMATCH, "apply_fixture_extra_connection")
        result = _Socket(self.responses[self.offset], self.requests[self.offset])
        self.offset += 1
        self.sockets.append(result)
        return result

    def assert_cleanup(self) -> None:
        if self.offset != len(self.responses):
            fail(EXIT_MISMATCH, "apply_fixture_missing_connection")
        if any(not item.closed for item in self.sockets):
            fail(EXIT_MISMATCH, "apply_fixture_socket_cleanup")
        for item in self.sockets:
            if any(any(request) for request in item.request_buffers):
                fail(EXIT_MISMATCH, "apply_fixture_request_not_zeroed")


def _run_success(provider: str, action_id: str, basis: str) -> None:
    requests = [
        _get(probe._BASE_ROUTES[0][1]),
        _get(probe._BASE_ROUTES[1][1]),
        _get(probe._COMBAT_ROUTE[0][1]),
        _post(action_id),
        _get(probe._COMBAT_ROUTE[0][1]),
    ]
    responses = [
        _response(_HEALTH),
        _response(probe._MANIFEST_COMPATIBLE),
        _response(_COMBAT_BEFORE),
        _response(_action_body(action_id)),
        _response(_COMBAT_AFTER),
    ]
    connector = _Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    payload = apply_one._run_apply_one(credential, provider, connector)
    applied = payload.get("applied")
    if (
        payload.get("status") != "passed"
        or payload.get("routes_checked") != 5
        or payload.get("decision_provider") != provider
        or not isinstance(applied, dict)
        or applied.get("action_id") != action_id
        or applied.get("basis") != basis
    ):
        fail(EXIT_MISMATCH, "apply_fixture_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "apply_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _expect_rejected_response() -> None:
    action_id = "play:1"
    requests = [
        _get(probe._BASE_ROUTES[0][1]),
        _get(probe._BASE_ROUTES[1][1]),
        _get(probe._COMBAT_ROUTE[0][1]),
        _post(action_id),
    ]
    responses = [
        _response(_HEALTH),
        _response(probe._MANIFEST_COMPATIBLE),
        _response(_COMBAT_BEFORE),
        _response(_action_body(action_id, accepted=False)),
    ]
    connector = _Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    try:
        apply_one._run_apply_one(credential, "heuristic", connector)
    except ToolFailure as failure:
        if failure.exit_code != EXIT_MISMATCH or failure.error_code != "action_response_mismatch":
            fail(EXIT_MISMATCH, "apply_fixture_wrong_rejection")
    else:
        fail(EXIT_MISMATCH, "apply_fixture_unexpected_pass")
    if any(credential):
        fail(EXIT_MISMATCH, "apply_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _expect_invocation_failure(operation: Callable[[], object], expected_code: str) -> None:
    try:
        operation()
    except ToolFailure as failure:
        if failure.exit_code == EXIT_INVALID_INVOCATION and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "apply_fixture_wrong_invocation_rejection")
    fail(EXIT_MISMATCH, "apply_fixture_invocation_unexpected_pass")


def operation() -> dict[str, object]:
    checks: list[str] = []
    _run_success("heuristic", "play:1", "incoming_attack")
    checks.append("heuristic_provider")
    _run_success("first-legal", "play:0:0", "first_legal")
    checks.append("first_legal_provider")
    _expect_rejected_response()
    checks.append("rejected_action_response")
    base = [
        "--user-profile", "/synthetic-profile",
        "--effective-uid", "501",
        "--decision-provider", "unknown",
    ]
    _expect_invocation_failure(
        lambda: apply_one.parse_args(base),
        "invalid_decision_provider",
    )
    checks.append("unknown_provider")
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_one_live_fixtures",
        "checks": checks,
        "check_count": len(checks),
    }


if __name__ == "__main__":
    main(operation)
