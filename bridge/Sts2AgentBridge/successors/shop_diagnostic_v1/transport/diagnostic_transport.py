"""One fixed authenticated diagnostic GET; no controller or action API."""
from __future__ import annotations
import json
import socket
import time
from pathlib import Path
from typing import Any, Callable

class TransportFailure(Exception):
    pass

_ENDPOINT = ("127.0.0.1", 43117)
_ROUTE = "/probe/shop-diagnostic-v1/public/diagnostic"
_LOWER_HEX = frozenset(b"0123456789abcdef")
_OPERATION_TIMEOUT_SECONDS = 1.0
_EXCHANGE_TIMEOUT_SECONDS = 3.0
_OUTER_TIMEOUT_SECONDS = 10.0
_MAXIMUM_HEADER_BYTES = 1024
_MAXIMUM_BODY_BYTES = 512
_RECEIVE_CHUNK_BYTES = 1024
_HEADER_TERMINATOR = b"\r\n\r\n"
_RESPONSE_PREFIX = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: ")
_RESPONSE_SUFFIX = (b"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n")
_COMMON_REQUEST_PREFIX = b"Host: 127.0.0.1:43117\r\nAuthorization: Bearer "
_ACCEPT_HEADER = b"\r\nAccept: application/json\r\n"
_CONNECTION_HEADER = b"Connection: close\r\n\r\n"

def _zero(buffer: bytearray) -> None:
    buffer[:] = b"\x00" * len(buffer)

def _credential_is_canonical(credential: bytearray) -> bool:
    return len(credential) == 64 and all(value in _LOWER_HEX for value in credential)

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

def _build_request(credential: bytearray) -> bytearray:
    if type(credential) is not bytearray or not _credential_is_canonical(credential):
        raise ValueError()
    request = bytearray(b"GET /probe/shop-diagnostic-v1/public/diagnostic HTTP/1.1\r\n")
    try:
        request.extend(_COMMON_REQUEST_PREFIX)
        request.extend(credential)
        request.extend(_ACCEPT_HEADER)
        request.extend(_CONNECTION_HEADER)
        return request
    except BaseException:
        _zero(request)
        raise


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _parse_record(body: bytearray) -> dict[str, object]:
    if type(body) is not bytearray or not 1 <= len(body) <= _MAXIMUM_BODY_BYTES:
        raise ValueError()
    record = json.loads(body.decode("ascii"), object_pairs_hook=_pairs,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    if (type(record) is not dict or list(record) != ["schema_version", "status", "shop_status", "stage", "reason"]
            or type(record["schema_version"]) is not int or record["schema_version"] != 1
            or record["status"] != "passed"
            or any(type(record[k]) is not str for k in ("status", "shop_status", "stage", "reason"))):
        raise ValueError()
    from diagnostic_values import ALLOWED_RESULTS
    if (record["shop_status"], record["stage"], record["reason"]) not in ALLOWED_RESULTS:
        raise ValueError()
    if bytearray(json.dumps(record, ensure_ascii=True, separators=(",", ":")), "ascii") != body:
        raise ValueError()
    return record


def _failure(code: str) -> dict[str, object]:
    return {"schema_version": 1, "status": "failed", "code": code}


def _run_with_socket_factory(credential: bytearray, socket_factory: Callable[[], Any],
                             *, clock: Callable[[], float]) -> dict[str, object]:
    request = bytearray()
    body = bytearray()
    if type(credential) is not bytearray:
        return _failure("diagnostic_client_failed")
    try:
        deadline = clock() + _OUTER_TIMEOUT_SECONDS
        request = _build_request(credential)
        body = _perform_exchange(request, socket_factory, clock, deadline, _MAXIMUM_BODY_BYTES)
        _check_after_io(clock, deadline)
        result = _parse_record(body)
        _check_after_io(clock, deadline)
        return result
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        raise
    except TransportFailure:
        return _failure("diagnostic_transport_failed")
    except (ValueError, UnicodeError):
        return _failure("diagnostic_response_invalid")
    except Exception:
        return _failure("diagnostic_client_failed")
    finally:
        _zero(request)
        _zero(body)
        _zero(credential)


def run_authenticated_diagnostic(credential: bytearray,
                                 *, clock: Callable[[], float] = time.monotonic) -> dict[str, object]:
    return _run_with_socket_factory(credential, _new_socket, clock=clock)
