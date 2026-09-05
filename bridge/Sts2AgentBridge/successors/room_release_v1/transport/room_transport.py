"""Fixed-endpoint HTTP transport for the frozen room_flows_v1 controller."""

from __future__ import annotations

import socket
import time
from typing import Any, Callable, Optional

from item_wire_v1.host import TransportFailure
from item_wire_v1.host import item_host
from room_flows_v1.host.room_flow_host import run_flow


_ENDPOINT = ("127.0.0.1", 43117)
_DECISION_ROUTE = "/probe/room-flows-v1/public/decision"
_ACTION_ROUTE = "/probe/room-flows-v1/public/action"
_ITEM_DECISION_ROUTE = "/probe/item-v1/public/item-decision"
_ITEM_ACTION_ROUTE = "/probe/item-v1/public/item-action"
_LOWER_HEX = frozenset(b"0123456789abcdef")

_OPERATION_TIMEOUT_SECONDS = 1.0
_EXCHANGE_TIMEOUT_SECONDS = 3.0
_MAXIMUM_HEADER_BYTES = 1024
_MAXIMUM_BODY_BYTES = 65536
_ITEM_BODY_BYTES = 4096
_RECEIVE_CHUNK_BYTES = 1024
_MINIMUM_REQUEST_INTERVAL = 0.05
_HEADER_TERMINATOR = b"\r\n\r\n"
_RESPONSE_PREFIX = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json; charset=utf-8\r\n"
    b"Content-Length: "
)
_RESPONSE_SUFFIX = (
    b"\r\n"
    b"Cache-Control: no-store\r\n"
    b"X-Content-Type-Options: nosniff\r\n"
    b"Connection: close\r\n"
    b"\r\n"
)
_COMMON_REQUEST_PREFIX = (
    b"Host: 127.0.0.1:43117\r\n"
    b"Authorization: Bearer "
)
_ACCEPT_HEADER = b"\r\nAccept: application/json\r\n"
_CONNECTION_HEADER = b"Connection: close\r\n\r\n"


def _zero(buffer: bytearray) -> None:
    buffer[:] = b"\x00" * len(buffer)


def _fixed_internal_failure() -> dict[str, object]:
    return {"schema_version": 1, "status": "failed", "code": "internal_failure"}


def _credential_is_canonical(credential: bytearray) -> bool:
    return len(credential) == 64 and all(value in _LOWER_HEX for value in credential)


def _decision_is_canonical(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(ord(character) in _LOWER_HEX for character in value)
    )


def _indexed(value: object, prefix: str, maximum: int) -> bool:
    if type(value) is not str or not value.startswith(prefix):
        return False
    digits = value[len(prefix):]
    return (bool(digits) and len(digits) <= 3 and digits.isascii() and digits.isdecimal()
            and (len(digits) == 1 or digits[0] != "0") and int(digits) <= maximum)


def _action_is_canonical(flow: str, route: str, value: object) -> bool:
    if route == _ITEM_ACTION_ROUTE:
        return flow == "event" and _indexed(value, "collect:", 255)
    if route != _ACTION_ROUTE:
        return False
    if flow == "shop":
        return value in ("inventory:close", "leave") or _indexed(value, "buy:card:", 31)
    return flow == "event" and _indexed(value, "choose:", 7)


def _body_limit(flow: str, route: str) -> int:
    if flow not in ("shop", "event"):
        raise ValueError()
    if route in (_DECISION_ROUTE, _ACTION_ROUTE):
        return _MAXIMUM_BODY_BYTES
    if flow == "event" and route in (_ITEM_DECISION_ROUTE, _ITEM_ACTION_ROUTE):
        return _ITEM_BODY_BYTES
    raise ValueError()


def _build_request(
    flow: str,
    method: str,
    route: str,
    decision_id: Optional[str],
    action_id: Optional[str],
    credential: bytearray,
) -> bytearray:
    if type(flow) is not str or type(method) is not str or type(route) is not str:
        raise ValueError()
    _body_limit(flow, route)
    if method == "GET" and route in (_DECISION_ROUTE, _ITEM_DECISION_ROUTE):
        if decision_id is not None or action_id is not None:
            raise ValueError()
        request = bytearray(f"GET {route} HTTP/1.1\r\n", "ascii")
    elif method == "POST" and route in (_ACTION_ROUTE, _ITEM_ACTION_ROUTE):
        if not _decision_is_canonical(decision_id) or not _action_is_canonical(flow, route, action_id):
            raise ValueError()
        request = bytearray(f"POST {route} HTTP/1.1\r\n", "ascii")
    else:
        raise ValueError()
    try:
        if not _credential_is_canonical(credential):
            raise ValueError()
        request.extend(_COMMON_REQUEST_PREFIX)
        request.extend(credential)
        request.extend(_ACCEPT_HEADER)
        if method == "POST":
            request.extend(b"X-Sts2-Decision-Id: ")
            request.extend(decision_id.encode("ascii"))
            request.extend(b"\r\nX-Sts2-Action-Id: ")
            request.extend(action_id.encode("ascii"))
            request.extend(b"\r\n")
        request.extend(_CONNECTION_HEADER)
        return request
    except BaseException:
        _zero(request)
        raise


def _new_socket() -> socket.socket:
    return socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def _remaining(clock: Callable[[], float], deadline: float) -> float:
    remaining = deadline - clock()
    if remaining <= 0:
        raise TransportFailure() from None
    return remaining


def _set_timeout(client: Any, clock: Callable[[], float], deadline: float) -> None:
    client.settimeout(min(_OPERATION_TIMEOUT_SECONDS, _remaining(clock, deadline)))
    _check_after_io(clock, deadline)


def _check_after_io(clock: Callable[[], float], deadline: float) -> None:
    _remaining(clock, deadline)


def _parse_header(response: bytearray, body_offset: int, maximum_body: int) -> tuple[int, int]:
    if body_offset > _MAXIMUM_HEADER_BYTES:
        raise TransportFailure() from None
    digits_start = len(_RESPONSE_PREFIX)
    digits_end = body_offset - len(_RESPONSE_SUFFIX)
    if (
        not response.startswith(_RESPONSE_PREFIX)
        or digits_end <= digits_start
        or not response.endswith(_RESPONSE_SUFFIX, 0, body_offset)
    ):
        raise TransportFailure() from None
    if digits_end - digits_start > 5 or (
        digits_end - digits_start > 1 and response[digits_start] == ord("0")
    ):
        raise TransportFailure() from None
    length = 0
    for offset in range(digits_start, digits_end):
        digit = response[offset]
        if digit < ord("0") or digit > ord("9"):
            raise TransportFailure() from None
        length = length * 10 + digit - ord("0")
    if length < 1 or length > maximum_body:
        raise TransportFailure() from None
    expected_total = body_offset + length
    if expected_total > _MAXIMUM_HEADER_BYTES + maximum_body:
        raise TransportFailure() from None
    return length, expected_total


def _close(client: Any) -> None:
    client.close()


def _perform_exchange(
    request: bytearray,
    socket_factory: Callable[[], Any],
    clock: Callable[[], float],
    host_deadline: float,
    maximum_body: int,
) -> bytearray:
    response = bytearray()
    client: Any | None = None
    failure_active = False
    try:
        entry = clock()
        if entry >= host_deadline:
            raise TransportFailure() from None
        exchange_deadline = min(host_deadline, entry + _EXCHANGE_TIMEOUT_SECONDS)

        client = socket_factory()
        _set_timeout(client, clock, exchange_deadline)
        client.connect(_ENDPOINT)
        _check_after_io(clock, exchange_deadline)

        _set_timeout(client, clock, exchange_deadline)
        client.sendall(request)
        _check_after_io(clock, exchange_deadline)

        _set_timeout(client, clock, exchange_deadline)
        client.shutdown(socket.SHUT_WR)
        _check_after_io(clock, exchange_deadline)

        body_offset: int | None = None
        expected_total: int | None = None
        while True:
            _set_timeout(client, clock, exchange_deadline)
            chunk = client.recv(_RECEIVE_CHUNK_BYTES)
            _check_after_io(clock, exchange_deadline)
            if type(chunk) is not bytes:
                raise TransportFailure() from None
            if len(chunk) > _RECEIVE_CHUNK_BYTES:
                raise TransportFailure() from None
            if not chunk:
                break
            if len(response) + len(chunk) > _MAXIMUM_HEADER_BYTES + maximum_body:
                raise TransportFailure() from None
            response.extend(chunk)

            if body_offset is None:
                separator = response.find(_HEADER_TERMINATOR)
                if separator >= 0:
                    body_offset = separator + len(_HEADER_TERMINATOR)
                    _, expected_total = _parse_header(response, body_offset, maximum_body)
                elif len(response) >= _MAXIMUM_HEADER_BYTES:
                    raise TransportFailure() from None
            if expected_total is not None and len(response) > expected_total:
                raise TransportFailure() from None

        if body_offset is None or expected_total is None or len(response) != expected_total:
            raise TransportFailure() from None

        closing = client
        client = None
        _close(closing)
        _check_after_io(clock, exchange_deadline)

        del response[:body_offset]
        return response
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        failure_active = True
        _zero(response)
        raise
    except TransportFailure:
        failure_active = True
        _zero(response)
        raise TransportFailure() from None
    except (OSError, TimeoutError):
        failure_active = True
        _zero(response)
        raise TransportFailure() from None
    except Exception:
        failure_active = True
        _zero(response)
        raise
    finally:
        _zero(request)
        if client is not None:
            closing = client
            client = None
            try:
                _close(closing)
            except (KeyboardInterrupt, SystemExit, GeneratorExit):
                _zero(response)
                raise
            except (OSError, TimeoutError):
                if not failure_active:
                    _zero(response)
                    raise TransportFailure() from None
            except Exception:
                if not failure_active:
                    _zero(response)
                    raise


class _AuthenticatedExchange:
    def __init__(
        self,
        flow: str,
        credential: bytearray,
        socket_factory: Callable[[], Any],
        clock: Callable[[], float],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._flow = flow
        self._credential = credential
        self._socket_factory = socket_factory
        self._clock = clock
        self._sleep = sleep
        self._not_before = 0.0

    def __call__(
        self,
        method: str,
        route: str,
        decision_id: Optional[str],
        action_id: Optional[str],
        deadline: float,
    ) -> bytearray:
        request = _build_request(
            self._flow,
            method,
            route,
            decision_id,
            action_id,
            self._credential,
        )
        try:
            now = self._clock()
            if now >= deadline:
                raise TransportFailure() from None
            if now < self._not_before:
                if self._not_before >= deadline:
                    raise TransportFailure() from None
                self._sleep(self._not_before - now)
                now = self._clock()
                if now < self._not_before or now >= deadline:
                    raise TransportFailure() from None
            self._not_before = now + _MINIMUM_REQUEST_INTERVAL
            return _perform_exchange(request, self._socket_factory, self._clock, deadline, _body_limit(self._flow, route))
        finally:
            # Pacing/cancellation can fail before the exchange takes ownership.
            _zero(request)


def _run_with_socket_factory(
    flow: str,
    credential: bytearray,
    socket_factory: Callable[[], Any],
    *,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> dict[str, object]:
    if type(credential) is not bytearray:
        return _fixed_internal_failure()
    try:
        if flow not in ("shop", "event") or not _credential_is_canonical(credential):
            return _fixed_internal_failure()
        exchange = _AuthenticatedExchange(flow, credential, socket_factory, clock, sleep)
        return run_flow(flow, exchange, item_host=item_host, buy_card=True, clock=clock, sleep=sleep)
    finally:
        _zero(credential)


def run_authenticated_flow(
    flow: str,
    credential: bytearray,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Run one protected selected room flow against the fixed authenticated endpoint."""

    return _run_with_socket_factory(
        flow,
        credential,
        _new_socket,
        clock=clock,
        sleep=sleep,
    )
