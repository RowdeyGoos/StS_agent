#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
from collections.abc import Callable

import apply_map_live as map_client
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


def _candidate(index: int, col: int, row: int, kind: str) -> dict[str, object]:
    return {
        "candidate_index": index,
        "col": col,
        "row": row,
        "kind": kind,
    }


def _legal(index: int) -> dict[str, object]:
    return {
        "action_id": f"select:{index}",
        "kind": "select_map_node",
        "candidate_index": index,
    }


def _ready(
    decision_id: str,
    candidates: list[dict[str, object]],
) -> bytes:
    return _encode({
        "schema_version": 1,
        "status": "ready",
        "decision_kind": "map",
        "actionable": True,
        "decision_id": decision_id,
        "screen_kind": "map",
        "destination": None,
        "candidates": candidates,
        "legal_actions": [_legal(index) for index in range(len(candidates))],
    })


def _inactive(status: str) -> bytes:
    return _encode({
        "schema_version": 1,
        "status": status,
        "decision_kind": "map",
        "actionable": False,
        "decision_id": None,
        "screen_kind": "unknown",
        "destination": None,
        "candidates": [],
        "legal_actions": [],
    })


def _complete(destination: dict[str, object]) -> bytes:
    return _encode({
        "schema_version": 1,
        "status": "complete",
        "decision_kind": "map",
        "actionable": False,
        "decision_id": None,
        "screen_kind": "room",
        "destination": destination,
        "candidates": [],
        "legal_actions": [],
    })


def _action_body(decision_id: str, action_id: str, reason: str) -> bytes:
    accepted = reason == "accepted"
    return _encode({
        "schema_version": 1,
        "status": "accepted" if accepted else "rejected",
        "mutation_state": "applied" if accepted else "none",
        "decision_id": decision_id,
        "action_id": action_id,
        "reason": reason,
    })


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
    return (
        b"GET "
        + route.encode("ascii")
        + b" HTTP/1.1\r\n"
        b"Host: 127.0.0.1:43117\r\n"
        b"Authorization: Bearer "
        + _CREDENTIAL
        + b"\r\n"
        b"Accept: application/json\r\n"
        b"Connection: close\r\n"
        b"\r\n"
    )


def _post(decision_id: str, action_id: str) -> bytes:
    return (
        b"POST "
        + map_client._MAP_ACTION_ROUTE.encode("ascii")
        + b" HTTP/1.1\r\n"
        b"Host: 127.0.0.1:43117\r\n"
        b"Authorization: Bearer "
        + _CREDENTIAL
        + b"\r\n"
        b"X-Sts2-Decision-Id: "
        + decision_id.encode("ascii")
        + b"\r\n"
        b"X-Sts2-Action-Id: "
        + action_id.encode("ascii")
        + b"\r\n"
        b"Accept: application/json\r\n"
        b"Connection: close\r\n"
        b"\r\n"
    )


def _request_builder_oracle() -> None:
    for route in (
        probe._BASE_ROUTES[0][1],
        probe._BASE_ROUTES[1][1],
        map_client._MAP_DECISION_ROUTE,
    ):
        actual = bytes(probe._build_request(route, bytearray(_CREDENTIAL)))
        if actual != _get(route):
            fail(EXIT_MISMATCH, "map_fixture_get_builder")
    actual_post = bytes(
        probe._build_action_request(
            map_client._MAP_ACTION_ROUTE,
            bytearray(_CREDENTIAL),
            _DECISION_ZERO,
            "select:0",
        )
    )
    if actual_post != _post(_DECISION_ZERO, "select:0"):
        fail(EXIT_MISMATCH, "map_fixture_post_builder")


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
            fail(EXIT_MISMATCH, "map_fixture_timeout")

    def sendall(self, request: bytearray) -> None:
        if bytes(request) != self.expected_request:
            fail(EXIT_MISMATCH, "map_fixture_request")
        self.request_buffers.append(request)

    def shutdown(self, how: int) -> None:
        if how != probe.socket.SHUT_WR or not (self.request_buffers) or self.write_shutdown or self.closed:
            fail(EXIT_MISMATCH, "apply_map_live_fixture_half_close")
        self.write_shutdown = True

    def recv(self, maximum: int) -> bytes:
        if not self.write_shutdown:
            fail(EXIT_MISMATCH, "apply_map_live_fixture_receive_before_half_close")
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "map_fixture_receive_bound")
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
            fail(EXIT_MISMATCH, "map_fixture_extra_connection")
        result = _Socket(self.responses[self.offset], self.requests[self.offset])
        self.offset += 1
        self.sockets.append(result)
        return result

    def assert_cleanup(self) -> None:
        if self.offset != len(self.responses):
            fail(EXIT_MISMATCH, "map_fixture_missing_connection")
        if any(not item.closed for item in self.sockets):
            fail(EXIT_MISMATCH, "map_fixture_socket_cleanup")
        for item in self.sockets:
            if any(any(request) for request in item.request_buffers):
                fail(EXIT_MISMATCH, "map_fixture_request_not_zeroed")


def _base_requests() -> list[bytes]:
    return [_get(probe._BASE_ROUTES[0][1]), _get(probe._BASE_ROUTES[1][1])]


def _base_responses() -> list[bytes]:
    return [_HEALTH, probe._MANIFEST_COMPATIBLE]


def _run_success() -> None:
    candidates = [
        _candidate(0, 2, 3, "monster"),
        _candidate(1, 4, 3, "rest_site"),
    ]
    requests = _base_requests() + [
        _get(map_client._MAP_DECISION_ROUTE),
        _post(_DECISION_ZERO, "select:0"),
        _get(map_client._MAP_DECISION_ROUTE),
        _get(map_client._MAP_DECISION_ROUTE),
    ]
    responses = _base_responses() + [
        _ready(_DECISION_ZERO, candidates),
        _action_body(_DECISION_ZERO, "select:0", "accepted"),
        _inactive("waiting"),
        _complete(candidates[0]),
    ]
    connector = _Connector([_response(value) for value in responses], requests)
    credential = bytearray(_CREDENTIAL)
    payload = map_client._run_apply_map(credential, "first", connector)
    if (
        payload.get("status") != "passed"
        or payload.get("milestone") != "r0g_map_selection"
        or payload.get("decision_provider") != "first"
        or payload.get("applied")
        != {
            "action_id": "select:0",
            "kind": "select_map_node",
            "candidate_index": 0,
            "col": 2,
            "row": 3,
            "node_kind": "monster",
            "basis": "first_reachable",
        }
        or payload.get("after")
        != {"screen_kind": "room", "destination": candidates[0]}
        or payload.get("routes_checked") != len(requests)
    ):
        fail(EXIT_MISMATCH, "map_fixture_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "map_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _expect_failure(
    responses: list[bytes],
    requests: list[bytes],
    expected_code: str,
) -> None:
    connector = _Connector([_response(value) for value in responses], requests)
    credential = bytearray(_CREDENTIAL)
    try:
        map_client._run_apply_map(credential, "first", connector)
    except ToolFailure as failure:
        if failure.exit_code != EXIT_MISMATCH or failure.error_code != expected_code:
            fail(EXIT_MISMATCH, "map_fixture_wrong_rejection")
    else:
        fail(EXIT_MISMATCH, "map_fixture_unexpected_pass")
    if any(credential):
        fail(EXIT_MISMATCH, "map_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _expect_validation_failure(
    operation: Callable[[], object],
    expected_code: str,
) -> None:
    try:
        operation()
    except ToolFailure as failure:
        if failure.exit_code == EXIT_MISMATCH and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "map_fixture_wrong_validation_rejection")
    fail(EXIT_MISMATCH, "map_fixture_validation_unexpected_pass")


def _expect_invocation_failure(arguments: list[str], expected_code: str) -> None:
    try:
        map_client.parse_args(arguments)
    except ToolFailure as failure:
        if failure.exit_code == EXIT_INVALID_INVOCATION and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "map_fixture_wrong_invocation_rejection")
    fail(EXIT_MISMATCH, "map_fixture_invocation_unexpected_pass")


def _rejected_receipt(reason: str) -> None:
    candidate = _candidate(0, 2, 3, "monster")
    requests = _base_requests() + [
        _get(map_client._MAP_DECISION_ROUTE),
        _post(_DECISION_ZERO, "select:0"),
    ]
    responses = _base_responses() + [
        _ready(_DECISION_ZERO, [candidate]),
        _action_body(_DECISION_ZERO, "select:0", reason),
    ]
    _expect_failure(responses, requests, f"map_action_{reason}")


def operation() -> dict[str, object]:
    checks: list[str] = []

    _request_builder_oracle()
    checks.append("independent_request_builder_oracle")

    rate_limited_response = (
        probe._RATE_LIMITED_HEADER
        + probe._RATE_LIMITED_BODY_PREFIX
        + b"0" * 32
        + probe._RATE_LIMITED_BODY_SUFFIX
    )
    accepted_body = _action_body(_DECISION_ZERO, "select:0", "accepted")
    rate_limited_connector = _Connector(
        [rate_limited_response, _response(accepted_body)],
        [_post(_DECISION_ZERO, "select:0"), _post(_DECISION_ZERO, "select:0")],
    )
    rate_limited_credential = bytearray(_CREDENTIAL)
    sleeps: list[float] = []
    observed = map_client._read_body(
        "map_action",
        map_client._MAP_ACTION_ROUTE,
        rate_limited_credential,
        rate_limited_connector,
        1_000_000_000.0,
        _DECISION_ZERO,
        "select:0",
        sleeper=sleeps.append,
    )
    if observed != accepted_body or sleeps != [map_client._RATE_LIMIT_RETRY_SECONDS]:
        fail(EXIT_MISMATCH, "map_fixture_rate_limit_retry")
    probe._zero(rate_limited_credential)
    rate_limited_connector.assert_cleanup()
    checks.append("exact_rate_limit_post_retry")

    exhausted_connector = _Connector(
        [rate_limited_response, rate_limited_response],
        [_get(map_client._MAP_DECISION_ROUTE), _get(map_client._MAP_DECISION_ROUTE)],
    )
    exhausted_credential = bytearray(_CREDENTIAL)
    try:
        map_client._read_body(
            "map",
            map_client._MAP_DECISION_ROUTE,
            exhausted_credential,
            exhausted_connector,
            1_000_000_000.0,
            sleeper=lambda _: None,
        )
    except ToolFailure as failure:
        if failure.exit_code != EXIT_MISMATCH or failure.error_code != "map_rate_limited":
            fail(EXIT_MISMATCH, "map_fixture_wrong_rate_limit_failure")
    else:
        fail(EXIT_MISMATCH, "map_fixture_rate_limit_exhaustion_accepted")
    probe._zero(exhausted_credential)
    exhausted_connector.assert_cleanup()
    checks.append("rate_limit_retry_exhaustion")

    retryable_response = (
        probe._RETRYABLE_BACKEND_HEADER
        + probe._RETRYABLE_BACKEND_BODY_PREFIX
        + b"0" * 32
        + probe._RETRYABLE_BACKEND_BODY_SUFFIX
    )
    retryable_connector = _Connector(
        [retryable_response],
        [_get(map_client._MAP_DECISION_ROUTE)],
    )
    retryable_credential = bytearray(_CREDENTIAL)
    try:
        map_client._read_body(
            "map",
            map_client._MAP_DECISION_ROUTE,
            retryable_credential,
            retryable_connector,
            1_000_000_000.0,
        )
    except ToolFailure as failure:
        if (
            failure.exit_code != EXIT_MISMATCH
            or failure.error_code != "map_backend_retryable"
        ):
            fail(EXIT_MISMATCH, "map_fixture_wrong_retryable_failure")
    else:
        fail(EXIT_MISMATCH, "map_fixture_retryable_response_accepted")
    probe._zero(retryable_credential)
    retryable_connector.assert_cleanup()
    checks.append("retryable_backend_classification")

    backend_fault_response = (
        probe._BACKEND_FAULT_HEADER
        + probe._BACKEND_FAULT_BODY_PREFIX
        + b"0" * 32
        + probe._BACKEND_FAULT_BODY_SUFFIX
    )
    backend_fault_connector = _Connector(
        [backend_fault_response],
        [_get(map_client._MAP_DECISION_ROUTE)],
    )
    backend_fault_credential = bytearray(_CREDENTIAL)
    try:
        map_client._read_body(
            "map",
            map_client._MAP_DECISION_ROUTE,
            backend_fault_credential,
            backend_fault_connector,
            1_000_000_000.0,
        )
    except ToolFailure as failure:
        if (
            failure.exit_code != EXIT_MISMATCH
            or failure.error_code != "map_backend_fault"
        ):
            fail(EXIT_MISMATCH, "map_fixture_wrong_backend_fault")
    else:
        fail(EXIT_MISMATCH, "map_fixture_backend_fault_accepted")
    probe._zero(backend_fault_credential)
    backend_fault_connector.assert_cleanup()
    checks.append("backend_fault_classification")

    _run_success()
    checks.append("ready_accepted_waiting_complete")

    candidate = _candidate(0, 2, 3, "monster")
    ready = map_client._validate_ready(_ready(_DECISION_ZERO, [candidate]))
    complete = map_client._validate_complete(_complete(candidate))
    if (
        ready["decision_id"] != _DECISION_ZERO
        or ready["candidates"] != [candidate]
        or complete != {"screen_kind": "room", "destination": candidate}
    ):
        fail(EXIT_MISMATCH, "map_fixture_canonical_contract")
    checks.append("canonical_ready_and_complete")

    for status in ("waiting", "unsupported"):
        _expect_failure(
            _base_responses() + [_inactive(status)],
            _base_requests() + [_get(map_client._MAP_DECISION_ROUTE)],
            "map_not_ready",
        )
    checks.append("initial_waiting_and_unsupported")

    for reason in (
        "stale_decision",
        "invalid_action",
        "already_applied",
        "action_limit_reached",
    ):
        _rejected_receipt(reason)
    checks.append("rejected_action_receipts")

    mismatch_requests = _base_requests() + [
        _get(map_client._MAP_DECISION_ROUTE),
        _post(_DECISION_ZERO, "select:0"),
    ]
    _expect_failure(
        _base_responses()
        + [
            _ready(_DECISION_ZERO, [candidate]),
            _action_body(_DECISION_ONE, "select:0", "accepted"),
        ],
        mismatch_requests,
        "map_action_response_mismatch",
    )
    checks.append("receipt_identity_mismatch")

    malformed = bytearray(_ready(_DECISION_ZERO, [candidate]))
    insertion = malformed.find(b'"status"')
    malformed[insertion:insertion] = b'"schema_version":1,'
    _expect_validation_failure(
        lambda: map_client._validate_ready(bytes(malformed)),
        "map_response_mismatch",
    )
    checks.append("duplicate_field_rejected")

    different = _candidate(0, 5, 3, "rest_site")
    destination_requests = mismatch_requests + [_get(map_client._MAP_DECISION_ROUTE)]
    _expect_failure(
        _base_responses()
        + [
            _ready(_DECISION_ZERO, [candidate]),
            _action_body(_DECISION_ZERO, "select:0", "accepted"),
            _complete(different),
        ],
        destination_requests,
        "map_destination_mismatch",
    )
    checks.append("destination_mismatch")

    _expect_failure(
        _base_responses()
        + [
            _ready(_DECISION_ZERO, [candidate]),
            _action_body(_DECISION_ZERO, "select:0", "accepted"),
            _inactive("unsupported"),
        ],
        destination_requests,
        "post_map_state_unsupported",
    )
    checks.append("post_action_unsupported")

    arguments = [
        "--user-profile", "/synthetic-profile",
        "--effective-uid", "501",
        "--decision-provider", "unknown",
    ]
    _expect_invocation_failure(arguments, "invalid_decision_provider")
    checks.append("unknown_provider")

    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_map_live_fixtures",
        "checks": checks,
        "check_count": len(checks),
    }


if __name__ == "__main__":
    main(operation)
