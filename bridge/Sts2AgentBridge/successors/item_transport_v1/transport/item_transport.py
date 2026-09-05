"""Fixed-endpoint HTTP transport for the frozen item_probe_v1 controller."""

from __future__ import annotations

import socket
import time
from typing import Any, Callable, Optional

from item_wire_v1.host import TransportFailure, run_collection


_ENDPOINT = ("127.0.0.1", 43117)
_DECISION_ROUTE = "/probe/item-v1/public/item-decision"
_ACTION_ROUTE = "/probe/item-v1/public/item-action"
_LOWER_HEX = frozenset(b"0123456789abcdef")

_OPERATION_TIMEOUT_SECONDS = 1.0
_EXCHANGE_TIMEOUT_SECONDS = 3.0
_MAXIMUM_HEADER_BYTES = 1024
_MAXIMUM_BODY_BYTES = 4096
_MAXIMUM_RESPONSE_BYTES = 5120
_RECEIVE_CHUNK_BYTES = 1024
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
_GET_PREFIX = b"GET /probe/item-v1/public/item-decision HTTP/1.1\r\n"
_POST_PREFIX = b"POST /probe/item-v1/public/item-action HTTP/1.1\r\n"
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


def _action_is_canonical(value: object) -> bool:
    if type(value) is not str or not value.startswith("collect:"):
        return False
    digits = value[8:]
    if not digits or len(digits) > 3 or (len(digits) > 1 and digits[0] == "0"):
        return False
    if not all("0" <= character <= "9" for character in digits):
        return False
    parsed = int(digits)
    return parsed <= 255 and value == f"collect:{parsed}"


def _build_request(
    method: str,
    route: str,
    decision_id: Optional[str],
    action_id: Optional[str],
    credential: bytearray,
) -> bytearray:
    if type(method) is not str or type(route) is not str:
        raise ValueError()
    if method == "GET" and route == _DECISION_ROUTE:
        if decision_id is not None or action_id is not None:
            raise ValueError()
        request = bytearray(_GET_PREFIX)
    elif method == "POST" and route == _ACTION_ROUTE:
        if not _decision_is_canonical(decision_id) or not _action_is_canonical(action_id):
            raise ValueError()
        request = bytearray(_POST_PREFIX)
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


def _parse_header(response: bytearray, body_offset: int) -> tuple[int, int]:
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
    if digits_end - digits_start > 4 or (
        digits_end - digits_start > 1 and response[digits_start] == ord("0")
    ):
        raise TransportFailure() from None
    length = 0
    for offset in range(digits_start, digits_end):
        digit = response[offset]
        if digit < ord("0") or digit > ord("9"):
            raise TransportFailure() from None
        length = length * 10 + digit - ord("0")
    if length < 1 or length > _MAXIMUM_BODY_BYTES:
        raise TransportFailure() from None
    expected_total = body_offset + length
    if expected_total > _MAXIMUM_RESPONSE_BYTES:
        raise TransportFailure() from None
    return length, expected_total


def _close(client: Any) -> None:
    client.close()


def _perform_exchange(
    request: bytearray,
    socket_factory: Callable[[], Any],
    clock: Callable[[], float],
    host_deadline: float,
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
            if len(response) + len(chunk) > _MAXIMUM_RESPONSE_BYTES:
                raise TransportFailure() from None
            response.extend(chunk)

            if body_offset is None:
                separator = response.find(_HEADER_TERMINATOR)
                if separator >= 0:
                    body_offset = separator + len(_HEADER_TERMINATOR)
                    _, expected_total = _parse_header(response, body_offset)
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
        credential: bytearray,
        socket_factory: Callable[[], Any],
        clock: Callable[[], float],
    ) -> None:
        self._credential = credential
        self._socket_factory = socket_factory
        self._clock = clock

    def __call__(
        self,
        method: str,
        route: str,
        decision_id: Optional[str],
        action_id: Optional[str],
        deadline: float,
    ) -> bytearray:
        request = _build_request(
            method,
            route,
            decision_id,
            action_id,
            self._credential,
        )
        return _perform_exchange(request, self._socket_factory, self._clock, deadline)


def _run_with_socket_factory(
    credential: bytearray,
    socket_factory: Callable[[], Any],
    *,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> dict[str, object]:
    if type(credential) is not bytearray:
        return _fixed_internal_failure()
    try:
        if not _credential_is_canonical(credential):
            return _fixed_internal_failure()
        exchange = _AuthenticatedExchange(credential, socket_factory, clock)
        return run_collection(exchange, clock=clock, sleep=sleep)
    finally:
        _zero(credential)


def run_authenticated_collection(
    credential: bytearray,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Run one item collection against the fixed authenticated loopback endpoint."""

    return _run_with_socket_factory(
        credential,
        _new_socket,
        clock=clock,
        sleep=sleep,
    )
