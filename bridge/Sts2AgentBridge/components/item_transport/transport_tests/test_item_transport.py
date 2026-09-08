from __future__ import annotations

from contextlib import contextmanager
import socket
import threading
import unittest

from components.item_transport.transport import run_authenticated_collection
from components.item_transport.transport import item_transport as transport


TOKEN_BYTES = b"0123456789abcdef" * 4
DEFAULT_TOKEN = object()
NONCE = "0123456789abcdef0123456789abcdef"
DECISION = "1b7f4402e889aa496e56b6eb0087dd2f3c680864ab0d19d60f4a1ab79da4ba22"

READY = (
    b'{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    b'"session_nonce":"0123456789abcdef0123456789abcdef",'
    b'"surface_ordinal":1,"status":"ready",'
    b'"decision_id":"1b7f4402e889aa496e56b6eb0087dd2f3c680864ab0d19d60f4a1ab79da4ba22",'
    b'"offers":[{"index":2,"kind":"potion","key":"Potion_A","enabled":true},'
    b'{"index":7,"kind":"relic","key":"Relic_B","enabled":true}],'
    b'"potion_slots":[null,"Held_1"],'
    b'"legal_actions":["collect:2","collect:7"]}'
)
ACCEPTED = (
    b'{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    b'"session_nonce":"0123456789abcdef0123456789abcdef",'
    b'"surface_ordinal":1,"status":"accepted",'
    b'"decision_id":"1b7f4402e889aa496e56b6eb0087dd2f3c680864ab0d19d60f4a1ab79da4ba22",'
    b'"action_id":"collect:2"}'
)
RESOLVED = (
    b'{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    b'"session_nonce":"0123456789abcdef0123456789abcdef",'
    b'"surface_ordinal":1,"status":"resolved",'
    b'"decision_id":"1b7f4402e889aa496e56b6eb0087dd2f3c680864ab0d19d60f4a1ab79da4ba22",'
    b'"action_id":"collect:2","offer_index":2,"kind":"potion",'
    b'"key":"Potion_A","result":"collected"}'
)

GET_REQUEST = (
    b"GET /probe/item-v1/public/item-decision HTTP/1.1\r\n"
    b"Host: 127.0.0.1:43117\r\n"
    b"Authorization: Bearer " + TOKEN_BYTES +
    b"\r\nAccept: application/json\r\n"
    b"Connection: close\r\n\r\n"
)
POST_REQUEST = (
    b"POST /probe/item-v1/public/item-action HTTP/1.1\r\n"
    b"Host: 127.0.0.1:43117\r\n"
    b"Authorization: Bearer " + TOKEN_BYTES +
    b"\r\nAccept: application/json\r\n"
    b"X-Sts2-Decision-Id: " + DECISION.encode("ascii") +
    b"\r\nX-Sts2-Action-Id: collect:2\r\n"
    b"Connection: close\r\n\r\n"
)


def http(body: bytes) -> bytes:
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
        b"Cache-Control: no-store\r\n"
        b"X-Content-Type-Options: nosniff\r\n"
        b"Connection: close\r\n\r\n" + body
    )


def failed(code: str) -> dict[str, object]:
    return {"schema_version": 1, "status": "failed", "code": code}


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, duration: float) -> None:
        self.value += duration


class FakeSocket:
    def __init__(self, events: list[object], fault: str | None = None, clock: Clock | None = None) -> None:
        self.events = list(events)
        self.fault = fault
        self.clock = clock
        self.requests: list[bytearray] = []
        self.sent: list[bytes] = []
        self.timeouts: list[float] = []
        self.endpoint = None
        self.shutdown_how = None
        self.close_calls = 0
        self.trace: list[str] = []

    def _step(self, name: str) -> None:
        self.trace.append(name)
        if self.fault == name:
            raise OSError("SYNTHETIC_SOCKET_CANARY")
        if self.fault == "late_" + name and self.clock is not None:
            self.clock.value = 3.0

    def settimeout(self, value: float) -> None:
        self._step("settimeout")
        self.timeouts.append(value)

    def connect(self, endpoint) -> None:
        self._step("connect")
        self.endpoint = endpoint

    def sendall(self, request: bytearray) -> None:
        self._step("sendall")
        self.requests.append(request)
        self.sent.append(bytes(request))

    def shutdown(self, how: int) -> None:
        self._step("shutdown")
        self.shutdown_how = how

    def recv(self, maximum: int):
        self._step("recv")
        if maximum != 1024:
            raise AssertionError("receive cap drift")
        if not self.events:
            return b""
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event

    def close(self) -> None:
        self.close_calls += 1
        self._step("close")


class Factory:
    def __init__(self, sockets: list[FakeSocket] | None = None, failure: BaseException | None = None) -> None:
        self.sockets = list(sockets or [])
        self.failure = failure
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        if not self.sockets:
            raise AssertionError("unexpected socket retry")
        return self.sockets.pop(0)


def run_with(factory: Factory, token: object = DEFAULT_TOKEN, clock: Clock | None = None):
    selected = bytearray(TOKEN_BYTES) if token is DEFAULT_TOKEN else token
    timer = clock or Clock()
    result = transport._run_with_socket_factory(
        selected,
        factory,
        clock=timer,
        sleep=timer.sleep,
    )
    return result, selected, timer


@contextmanager
def record_zeroes():
    original = transport._zero
    observed: list[bytearray] = []

    def recording(buffer: bytearray) -> None:
        observed.append(buffer)
        original(buffer)

    transport._zero = recording
    try:
        yield observed
    finally:
        transport._zero = original


class TransportTests(unittest.TestCase):
    def assert_socket_clean(self, item: FakeSocket, expected: bytes | None = None) -> None:
        self.assertEqual(("127.0.0.1", 43117), item.endpoint)
        self.assertEqual(socket.SHUT_WR, item.shutdown_how)
        self.assertEqual(1, item.close_calls)
        self.assertTrue(item.timeouts)
        self.assertTrue(all(0 < value <= 1.0 for value in item.timeouts))
        if expected is not None:
            self.assertEqual([expected], item.sent)
        self.assertTrue(all(not any(request) for request in item.requests))

    def test_success_uses_three_sockets_exact_requests_and_cleans_all_buffers(self):
        sockets = [
            FakeSocket([http(READY), b""]),
            FakeSocket([http(ACCEPTED), b""]),
            FakeSocket([http(RESOLVED), b""]),
        ]
        result, token, _ = run_with(Factory(sockets.copy()))
        self.assertEqual(
            {
                "schema_version": 1,
                "status": "passed",
                "milestone": "item_v1_collection",
                "item_kind": "potion",
                "attempted": 1,
                "accepted": 1,
                "reconciled": 1,
            },
            result,
        )
        self.assertFalse(any(token))
        self.assert_socket_clean(sockets[0], GET_REQUEST)
        self.assert_socket_clean(sockets[1], POST_REQUEST)
        self.assert_socket_clean(sockets[2], GET_REQUEST)
        for item in sockets:
            self.assertEqual(1, item.trace.count("sendall"))
            self.assertLess(item.trace.index("sendall"), item.trace.index("shutdown"))
            self.assertLess(item.trace.index("shutdown"), item.trace.index("recv"))

    def test_fragmented_response_is_accepted_only_after_eof(self):
        wrapped = http(READY)
        first = FakeSocket([wrapped[:7], wrapped[7:103], wrapped[103:], b""])
        rest = [FakeSocket([http(ACCEPTED), b""]), FakeSocket([http(RESOLVED), b""])]
        result, token, _ = run_with(Factory([first] + rest))
        self.assertEqual("passed", result["status"])
        self.assertEqual(4, first.trace.count("recv"))
        self.assertFalse(any(token))
        self.assert_socket_clean(first, GET_REQUEST)

    def test_invalid_credentials_never_create_a_socket(self):
        class MutableSubclass(bytearray):
            pass

        for credential, transferred in (
            (bytearray(b"a" * 63), True),
            (bytearray(b"G" * 64), True),
            (b"a" * 64, False),
            (None, False),
            (MutableSubclass(b"a" * 64), False),
        ):
            with self.subTest(kind=type(credential).__name__, size=getattr(credential, "__len__", lambda: -1)()):
                factory = Factory()
                result, selected, _ = run_with(factory, credential)
                self.assertEqual(failed("internal_failure"), result)
                self.assertEqual(0, factory.calls)
                if transferred:
                    self.assertFalse(any(selected))
                else:
                    self.assertTrue(selected is None or any(selected))

    def test_invalid_exchange_metadata_is_rejected_before_socket_creation(self):
        class StringSubclass(str):
            pass

        token = bytearray(TOKEN_BYTES)
        factory = Factory()
        exchange = transport._AuthenticatedExchange(token, factory, Clock())
        cases = (
            ("get", transport._DECISION_ROUTE, None, None),
            ("GET", "/wrong", None, None),
            (StringSubclass("GET"), transport._DECISION_ROUTE, None, None),
            ("GET", transport._DECISION_ROUTE, DECISION, None),
            ("POST", transport._ACTION_ROUTE, None, None),
            ("POST", transport._ACTION_ROUTE, DECISION.upper(), "collect:2"),
            ("POST", transport._ACTION_ROUTE, DECISION, "collect:02"),
            ("POST", transport._ACTION_ROUTE, DECISION, "collect:256"),
        )
        try:
            for method, route, decision, action in cases:
                with self.subTest(method=method, route=route, action=action):
                    with self.assertRaises(ValueError):
                        exchange(method, route, decision, action, 15.0)
            self.assertEqual(0, factory.calls)
        finally:
            transport._zero(token)

    def test_canonical_http_with_malformed_item_body_is_host_invalid_response(self):
        item = FakeSocket([http(b'{"private_canary":"SYNTHETIC"}'), b""])
        result, token, _ = run_with(Factory([item]))
        self.assertEqual(failed("invalid_response"), result)
        self.assertNotIn("CANARY", repr(result))
        self.assertFalse(any(token))
        self.assert_socket_clean(item, GET_REQUEST)

    def test_strict_http_framing_mutations_are_transport_failures(self):
        valid = http(READY)
        separator = valid.index(b"\r\n\r\n") + 4
        cases = (
            valid.replace(b"200 OK", b"201 Created", 1),
            valid.replace(b"Content-Type", b"content-type", 1),
            valid.replace(b"Cache-Control: no-store\r\n", b"", 1),
            valid.replace(b"Connection: close", b"Connection: keep-alive", 1),
            valid.replace(b"Content-Length: ", b"Content-Length: 0", 1),
            valid[:separator] + valid[separator:] + b"trailer",
            valid[:-1],
            b"X" * 1024,
            b"HTTP/1.1 200 OK\n\n" + READY,
            http(b"A" * 4096).replace(b"4096", b"4097", 1) + b"A",
        )
        for response in cases:
            with self.subTest(prefix=response[:35], size=len(response)):
                item = FakeSocket([response, b""])
                result, token, _ = run_with(Factory([item]))
                self.assertEqual(failed("transport_failure"), result)
                self.assertFalse(any(token))
                self.assertEqual(1, item.close_calls)
                self.assertEqual(1, item.trace.count("sendall"))

    def test_noncanonical_content_lengths_and_response_chunk_types_fail(self):
        body = READY
        canonical = http(body)
        cases = (
            canonical.replace(
                b"Content-Length: " + str(len(body)).encode("ascii"),
                b"Content-Length: 0" + str(len(body)).encode("ascii"),
                1,
            ),
            canonical.replace(
                b"Content-Length: " + str(len(body)).encode("ascii"),
                b"Content-Length: +" + str(len(body)).encode("ascii"),
                1,
            ),
            canonical.replace(
                b"Content-Length: " + str(len(body)).encode("ascii"),
                b"Content-Length: 0",
                1,
            ),
        )
        for response in cases:
            with self.subTest(prefix=response[:100]):
                result, token, _ = run_with(Factory([FakeSocket([response, b""])]))
                self.assertEqual(failed("transport_failure"), result)
                self.assertFalse(any(token))

        for chunk in (bytearray(canonical), memoryview(canonical), "not-bytes", b"A" * 1025):
            with self.subTest(chunk_type=type(chunk).__name__):
                result, token, _ = run_with(Factory([FakeSocket([chunk])]))
                self.assertEqual(failed("transport_failure"), result)
                self.assertFalse(any(token))
                if isinstance(chunk, memoryview):
                    chunk.release()

    def test_transport_accepts_4096_body_framing_and_rejects_4097(self):
        maximum = http(b"A" * 4096)
        chunks = [maximum[offset:offset + 1024] for offset in range(0, len(maximum), 1024)]
        item = FakeSocket(chunks + [b""])
        result, token, _ = run_with(Factory([item]))
        self.assertEqual(failed("invalid_response"), result)
        self.assertFalse(any(token))
        self.assertEqual(1, item.close_calls)

        excess = http(b"A" * 4097)
        chunks = [excess[offset:offset + 1024] for offset in range(0, len(excess), 1024)]
        item = FakeSocket(chunks)
        result, token, _ = run_with(Factory([item]))
        self.assertEqual(failed("transport_failure"), result)
        self.assertFalse(any(token))
        self.assertEqual(1, item.close_calls)

    def test_every_socket_phase_fault_is_transport_failure_without_retry(self):
        for phase in ("settimeout", "connect", "sendall", "shutdown", "recv", "close"):
            with self.subTest(phase=phase):
                item = FakeSocket([http(READY), b""], fault=phase)
                factory = Factory([item])
                with record_zeroes() as zeroed:
                    result, token, _ = run_with(factory)
                self.assertEqual(failed("transport_failure"), result)
                self.assertEqual(1, factory.calls)
                self.assertEqual(1, item.close_calls)
                self.assertFalse(any(token))
                self.assertTrue(zeroed)
                self.assertTrue(all(not any(buffer) for buffer in zeroed))

        factory = Factory(failure=OSError("factory-canary"))
        result, token, _ = run_with(factory)
        self.assertEqual(failed("transport_failure"), result)
        self.assertEqual(1, factory.calls)
        self.assertFalse(any(token))
        self.assertNotIn("canary", repr(result))

    def test_unexpected_ordinary_exchange_and_close_faults_are_internal(self):
        for item in (
            FakeSocket([RuntimeError("ordinary-recv-canary")]),
            FakeSocket([http(READY), b""], fault=None),
        ):
            if item.events and item.events[0] == http(READY):
                class OrdinaryCloseSocket(FakeSocket):
                    def close(self) -> None:
                        self.close_calls += 1
                        raise RuntimeError("ordinary-close-canary")

                item = OrdinaryCloseSocket([http(READY), b""])
            with self.subTest(item=type(item).__name__):
                result, token, _ = run_with(Factory([item]))
                self.assertEqual(failed("internal_failure"), result)
                self.assertFalse(any(token))
                self.assertNotIn("canary", repr(result))
                self.assertEqual(1, item.close_calls)

    def test_exchange_deadline_faults_are_transport_failure(self):
        for phase in ("late_settimeout", "late_connect", "late_sendall", "late_shutdown", "late_recv", "late_close"):
            with self.subTest(phase=phase):
                clock = Clock()
                item = FakeSocket([http(READY), b""], fault=phase, clock=clock)
                result, token, _ = run_with(Factory([item]), clock=clock)
                self.assertEqual(failed("transport_failure"), result)
                self.assertFalse(any(token))
                self.assertEqual(1, item.close_calls)

    def test_lost_post_response_is_not_retried(self):
        first = FakeSocket([http(READY), b""])
        lost = FakeSocket([OSError("lost-receipt-canary")])
        factory = Factory([first, lost])
        result, token, _ = run_with(factory)
        self.assertEqual(failed("transport_failure"), result)
        self.assertEqual(2, factory.calls)
        self.assertEqual([POST_REQUEST], lost.sent)
        self.assertFalse(any(token))
        self.assertNotIn("canary", repr(result))

    def test_cancellation_propagates_after_request_response_socket_and_credential_cleanup(self):
        for cancellation in (KeyboardInterrupt(), SystemExit(), GeneratorExit()):
            with self.subTest(kind=type(cancellation).__name__):
                item = FakeSocket([cancellation])
                token = bytearray(TOKEN_BYTES)
                with record_zeroes() as zeroed:
                    with self.assertRaises(type(cancellation)):
                        transport._run_with_socket_factory(
                            token,
                            Factory([item]),
                            clock=Clock(),
                            sleep=lambda _delay: None,
                        )
                self.assertFalse(any(token))
                self.assertEqual(1, item.close_calls)
                self.assertTrue(all(not any(buffer) for buffer in zeroed))

    def test_close_cancellation_propagates_and_zeros_untransferred_response(self):
        class CancelCloseSocket(FakeSocket):
            def close(self) -> None:
                self.close_calls += 1
                raise KeyboardInterrupt()

        item = CancelCloseSocket([http(READY), b""])
        token = bytearray(TOKEN_BYTES)
        with record_zeroes() as zeroed:
            with self.assertRaises(KeyboardInterrupt):
                transport._run_with_socket_factory(
                    token,
                    Factory([item]),
                    clock=Clock(),
                    sleep=lambda _delay: None,
                )
        self.assertFalse(any(token))
        self.assertEqual(1, item.close_calls)
        self.assertTrue(all(not any(buffer) for buffer in zeroed))

    def test_close_cancellation_overrides_prior_ordinary_recv_failure(self):
        class CancelCloseSocket(FakeSocket):
            def close(self) -> None:
                self.close_calls += 1
                raise KeyboardInterrupt()

        item = CancelCloseSocket([RuntimeError("ordinary-recv-canary")])
        token = bytearray(TOKEN_BYTES)
        with record_zeroes() as zeroed:
            with self.assertRaises(KeyboardInterrupt):
                transport._run_with_socket_factory(
                    token,
                    Factory([item]),
                    clock=Clock(),
                    sleep=lambda _delay: None,
                )
        self.assertFalse(any(token))
        self.assertEqual(1, item.close_calls)
        self.assertTrue(all(not any(buffer) for buffer in zeroed))


class RedirectSocket:
    def __init__(self, port: int, endpoints: list[tuple[str, int]]) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._port = port
        self._endpoints = endpoints

    def settimeout(self, value: float) -> None:
        self._socket.settimeout(value)

    def connect(self, endpoint: tuple[str, int]) -> None:
        self._endpoints.append(endpoint)
        if endpoint != ("127.0.0.1", 43117):
            raise AssertionError("production endpoint drift")
        self._socket.connect(("127.0.0.1", self._port))

    def sendall(self, value: bytearray) -> None:
        self._socket.sendall(value)

    def shutdown(self, how: int) -> None:
        self._socket.shutdown(how)

    def recv(self, maximum: int) -> bytes:
        return self._socket.recv(maximum)

    def close(self) -> None:
        self._socket.close()


class EphemeralServer:
    def __init__(self, responses: list[bytes], expected: list[bytes]) -> None:
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.listener.settimeout(2.0)
            self.listener.bind(("127.0.0.1", 0))
            self.listener.listen(3)
        except BaseException:
            self.listener.close()
            raise
        self.port = self.listener.getsockname()[1]
        self.responses = responses
        self.expected = expected
        self.errors: list[BaseException] = []
        self.thread = threading.Thread(target=self._run)

    def start(self) -> None:
        self.thread.start()

    def _run(self) -> None:
        try:
            for response, expected in zip(self.responses, self.expected):
                connection, _ = self.listener.accept()
                request = bytearray()
                try:
                    while True:
                        chunk = connection.recv(1024)
                        if not chunk:
                            break
                        request.extend(chunk)
                    if bytes(request) != expected:
                        raise AssertionError("ephemeral request mismatch")
                    connection.sendall(response)
                finally:
                    transport._zero(request)
                    connection.close()
        except BaseException as error:
            self.errors.append(error)
        finally:
            self.listener.close()

    def join(self) -> None:
        self.thread.join(3.0)
        if self.thread.is_alive():
            raise AssertionError("ephemeral server did not stop")
        if self.errors:
            raise self.errors[0]


class EphemeralSocketTests(unittest.TestCase):
    def test_real_stdlib_sockets_use_only_test_redirect_and_client_half_close(self):
        server = EphemeralServer(
            [http(READY), http(ACCEPTED), http(RESOLVED)],
            [GET_REQUEST, POST_REQUEST, GET_REQUEST],
        )
        server.start()
        endpoints: list[tuple[str, int]] = []
        token = bytearray(TOKEN_BYTES)
        try:
            result = transport._run_with_socket_factory(
                token,
                lambda: RedirectSocket(server.port, endpoints),
                clock=Clock(),
                sleep=lambda _delay: None,
            )
        finally:
            server.join()
        self.assertEqual("passed", result["status"])
        self.assertFalse(any(token))
        self.assertEqual([("127.0.0.1", 43117)] * 3, endpoints)


if __name__ == "__main__":
    unittest.main()
