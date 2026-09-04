#!/usr/bin/env python3
"""Synthetic regression gate for the frozen probe and room exchange clients."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import apply_room_live as room
import probe_live as probe
from tool_common import EXIT_INTERNAL, EXIT_MISMATCH, ToolFailure, fail, main


_CREDENTIAL = b"0123456789abcdef" * 4
_DECISION_ID = "0" * 64
_GET_HEALTH = (
    b"GET /probe/v0/health HTTP/1.1\r\n"
    b"Host: 127.0.0.1:43117\r\n"
    b"Authorization: Bearer " + _CREDENTIAL + b"\r\n"
    b"Accept: application/json\r\nConnection: close\r\n\r\n"
)
_GET_ROOM = (
    b"GET /probe/v0/public/room-decision HTTP/1.1\r\n"
    b"Host: 127.0.0.1:43117\r\n"
    b"Authorization: Bearer " + _CREDENTIAL + b"\r\n"
    b"Accept: application/json\r\nConnection: close\r\n\r\n"
)
_POST_ROOM = (
    b"POST /probe/v0/public/room-action HTTP/1.1\r\n"
    b"Host: 127.0.0.1:43117\r\n"
    b"Authorization: Bearer " + _CREDENTIAL + b"\r\n"
    b"X-Sts2-Decision-Id: " + _DECISION_ID.encode("ascii") + b"\r\n"
    b"X-Sts2-Action-Id: choose:0\r\n"
    b"Accept: application/json\r\nConnection: close\r\n\r\n"
)


class _Socket:
    def __init__(self, events: list[object], *, close_error: BaseException | None = None) -> None:
        self._events = iter(events)
        self._close_error = close_error
        self.closed = False
        self.requests: list[bytearray] = []
        self.sent_bytes: list[bytes] = []
        self.timeouts: list[float] = []
        self.receive_calls = 0

    def settimeout(self, value: float) -> None:
        if not 0 < value <= probe._SOCKET_OPERATION_TIMEOUT_SECONDS:
            fail(EXIT_MISMATCH, "transport_fixture_timeout_bound")
        self.timeouts.append(value)

    def sendall(self, request: bytearray) -> None:
        self.requests.append(request)
        self.sent_bytes.append(bytes(request))

    def recv(self, maximum: int) -> bytes | bytearray | memoryview:
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "transport_fixture_receive_bound")
        self.receive_calls += 1
        event = next(self._events, b"")
        if isinstance(event, BaseException):
            raise event
        return event  # type: ignore[return-value]

    def close(self) -> None:
        self.closed = True
        if self._close_error is not None:
            raise self._close_error


class _Connector:
    def __init__(self, socket: _Socket) -> None:
        self.socket = socket
        self.calls = 0

    def __call__(self) -> _Socket:
        self.calls += 1
        if self.calls != 1:
            fail(EXIT_MISMATCH, "transport_fixture_retry")
        return self.socket


class _Clock:
    def __init__(self, values: list[float] | None = None) -> None:
        self._values = iter(values or ())

    def __call__(self) -> float:
        return next(self._values, 0.0)


@contextmanager
def _clock(values: list[float] | None = None) -> Iterator[None]:
    original = probe.time.monotonic
    probe.time.monotonic = _Clock(values)  # type: ignore[assignment]
    try:
        yield
    finally:
        probe.time.monotonic = original  # type: ignore[assignment]


@contextmanager
def _record_zeroes() -> Iterator[list[bytearray]]:
    original = probe._zero
    observed: list[bytearray] = []

    def record(value: bytearray) -> None:
        observed.append(value)
        original(value)

    probe._zero = record
    try:
        yield observed
    finally:
        probe._zero = original


def _expect_failure(operation: Callable[[], object], code: str) -> None:
    try:
        operation()
    except ToolFailure as failure:
        if failure.exit_code == EXIT_MISMATCH and failure.error_code == code:
            return
        fail(EXIT_MISMATCH, "transport_fixture_wrong_failure")
    fail(EXIT_MISMATCH, "transport_fixture_unexpected_pass")


def _assert_socket(
    connector: _Connector,
    expected_request: bytes | None,
    *,
    receives: int | None = None,
) -> None:
    socket = connector.socket
    if connector.calls != 1 or not socket.closed:
        fail(EXIT_MISMATCH, "transport_fixture_connection_bound")
    if expected_request is None:
        if socket.requests:
            fail(EXIT_MISMATCH, "transport_fixture_unexpected_request")
    elif len(socket.sent_bytes) != 1 or socket.sent_bytes[0] != expected_request:
        fail(EXIT_MISMATCH, "transport_fixture_request_bytes")
    if receives is not None and socket.receive_calls != receives:
        fail(EXIT_MISMATCH, "transport_fixture_receive_count")
    if any(any(request) for request in socket.requests):
        fail(EXIT_MISMATCH, "transport_fixture_request_not_zeroed")
    if expected_request is not None and not socket.timeouts:
        fail(EXIT_MISMATCH, "transport_fixture_timeout_missing")


def _probe_get(connector: _Connector, deadline: float = 10.0) -> bytearray:
    return probe._exchange("probe", "/probe/v0/health", bytearray(_CREDENTIAL), connector, deadline)


def _room_get(connector: _Connector, deadline: float = 10.0) -> bytearray:
    return room._exchange("room", room._ROOM_DECISION_ROUTE, bytearray(_CREDENTIAL), connector, deadline)


def _room_post(connector: _Connector) -> bytearray:
    return room._exchange(
        "room", room._ROOM_ACTION_ROUTE, bytearray(_CREDENTIAL), connector, 10.0,
        _DECISION_ID, "choose:0",
    )


def _success_case(call: Callable[[_Connector], bytearray], expected_request: bytes) -> None:
    connector = _Connector(_Socket([b"response", b""]))
    with _clock():
        response = call(connector)
    if bytes(response) != b"response":
        fail(EXIT_MISMATCH, "transport_fixture_response_ownership")
    _assert_socket(connector, expected_request, receives=2)
    probe._zero(response)


def _route_rejections() -> None:
    for exchange, route in ((probe._exchange, "/not-allowed"), (room._exchange, "/not-allowed")):
        connector = _Connector(_Socket([]))
        with _clock():
            try:
                exchange("probe" if exchange is probe._exchange else "room", route, bytearray(_CREDENTIAL), connector, 10.0)
            except ToolFailure as failure:
                if failure.exit_code != EXIT_INTERNAL or failure.error_code != "internal_failure":
                    fail(EXIT_MISMATCH, "transport_fixture_route_rejection")
            else:
                fail(EXIT_MISMATCH, "transport_fixture_route_accepted")
        _assert_socket(connector, None)


def _initial_timeouts() -> None:
    for call, code in ((_probe_get, "probe_transport_timeout"), (_room_get, "room_transport_timeout")):
        connector = _Connector(_Socket([]))
        with _clock([10.0]):
            _expect_failure(lambda: call(connector, 10.0), code)
        if connector.calls != 0:
            fail(EXIT_MISMATCH, "transport_fixture_initial_timeout_connected")


def _labelled_failures() -> None:
    for call, request, label in ((_probe_get, _GET_HEALTH, "probe"), (_room_get, _GET_ROOM, "room")):
        socket = _Socket([OSError("synthetic")])
        connector = _Connector(socket)
        with _clock():
            _expect_failure(lambda: call(connector), f"{label}_transport_failure")
        _assert_socket(connector, request, receives=1)

        connector = _Connector(_Socket([b"x", b""]))
        with _clock([0.0, 0.0, 0.0, 0.0, 10.0]):
            _expect_failure(lambda: call(connector), f"{label}_transport_timeout")
        _assert_socket(connector, request, receives=1)


def _bounds() -> None:
    for call, request, label in ((_probe_get, _GET_HEALTH, "probe"), (_room_get, _GET_ROOM, "room")):
        connector = _Connector(_Socket([b""]))
        with _clock():
            _expect_failure(lambda: call(connector), f"{label}_empty_response")
        _assert_socket(connector, request, receives=1)

        connector = _Connector(_Socket([b"x" * (probe._RECEIVE_CHUNK_BYTES + 1)]))
        with _clock():
            _expect_failure(lambda: call(connector), f"{label}_transport_mismatch")
        _assert_socket(connector, request, receives=1)

        connector = _Connector(_Socket([b"x" * probe._RECEIVE_CHUNK_BYTES] * 8 + [b"x"]))
        with _clock():
            _expect_failure(lambda: call(connector), f"{label}_response_too_large")
        _assert_socket(connector, request, receives=9)


def _exceptional_cleanup() -> None:
    cases: tuple[tuple[str, Callable[[_Connector], bytearray], bytes], ...] = (
        ("probe", _probe_get, _GET_HEALTH),
        ("room", _room_get, _GET_ROOM),
    )
    for label, call, request in cases:
        for exception_name, interruption in (
            ("keyboard_interrupt", KeyboardInterrupt()),
            ("system_exit", SystemExit()),
            ("unexpected_recv", RuntimeError("synthetic")),
        ):
            connector = _Connector(_Socket([b"partial", interruption]))
            with _record_zeroes() as zeroes, _clock():
                try:
                    call(connector)
                except type(interruption):
                    pass
                else:
                    fail(EXIT_MISMATCH, "transport_fixture_exception_swallowed")
            _assert_socket(connector, request, receives=2)
            if not any(len(value) == len(b"partial") and not any(value) for value in zeroes):
                fail(EXIT_MISMATCH, f"{label}_{exception_name}_response_not_zeroed")


def _close_precedence() -> None:
    for label, call, request in (("probe", _probe_get, _GET_HEALTH), ("room", _room_get, _GET_ROOM)):
        connector = _Connector(_Socket([b"partial", b""], close_error=RuntimeError("synthetic")))
        with _record_zeroes() as zeroes, _clock():
            try:
                call(connector)
            except RuntimeError:
                pass
            else:
                fail(EXIT_MISMATCH, "transport_fixture_close_error_swallowed")
        _assert_socket(connector, request, receives=2)
        if not any(len(value) == len(b"partial") and not any(value) for value in zeroes):
            fail(EXIT_MISMATCH, f"{label}_close_response_not_zeroed")


def _inflight_close_precedence() -> None:
    for label, call, request in (("probe", _probe_get, _GET_HEALTH), ("room", _room_get, _GET_ROOM)):
        for failure_name, failure in (
            ("transport", OSError("synthetic")),
            ("cancellation", KeyboardInterrupt()),
        ):
            connector = _Connector(_Socket([b"partial", failure], close_error=RuntimeError("synthetic")))
            with _record_zeroes() as zeroes, _clock():
                try:
                    call(connector)
                except RuntimeError:
                    pass
                else:
                    fail(EXIT_MISMATCH, "transport_fixture_inflight_close_error_swallowed")
            _assert_socket(connector, request, receives=2)
            if not any(len(value) == len(b"partial") and not any(value) for value in zeroes):
                fail(EXIT_MISMATCH, f"{label}_{failure_name}_close_response_not_zeroed")


def operation() -> dict[str, object]:
    _success_case(_probe_get, _GET_HEALTH)
    _success_case(_room_get, _GET_ROOM)
    _success_case(_room_post, _POST_ROOM)
    _route_rejections()
    _initial_timeouts()
    _labelled_failures()
    _bounds()
    _exceptional_cleanup()
    _close_precedence()
    _inflight_close_precedence()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "bounded_transport_fixtures",
        "check_count": 29,
    }


if __name__ == "__main__":
    main(operation)
