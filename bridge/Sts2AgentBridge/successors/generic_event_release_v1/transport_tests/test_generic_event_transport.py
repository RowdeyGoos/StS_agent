from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).absolute().parents[1]
sys.path[:0] = [str(ROOT / "transport"), str(ROOT.parent)]
import generic_event_transport as transport

TOKEN = b"0123456789abcdef" * 4


def http(body):
    return transport._RESPONSE_PREFIX + str(len(body)).encode("ascii") + transport._RESPONSE_SUFFIX + body


def action_body(action="select:0", child=True):
    return bytearray(json.dumps({"decision_id": "a" * 64, "action_id": action,
        "child": {"ordinal": 1, "parent_decision_id": "b" * 64, "parent_action_id": "choose:0"} if child else None}, separators=(",", ":")), "ascii")


class Clock:
    def __init__(self):
        self.value = 0.0
        self.sleeps = []

    def __call__(self):
        return self.value

    def sleep(self, amount):
        self.sleeps.append(amount)
        self.value += amount


class FakeSocket:
    def __init__(self, wire, *, fault=None, clock=None, fragment=1024):
        self.parts = [wire[i:i+fragment] for i in range(0, len(wire), fragment)]
        self.fault, self.clock = fault, clock
        self.requests, self.receives, self.sent = [], [], []
        self.closed = 0
        self.endpoint = self.shutdown_how = None
        self.timeouts, self.starts = [], []

    def step(self, phase):
        if self.fault == phase:
            raise OSError("SYNTHETIC_SOCKET_FAILURE_CANARY")
        if self.fault == "late_" + phase:
            self.clock.value = 3.0
        if self.fault == "backwards_" + phase:
            self.clock.value = -1.0
        if self.fault == "nan_" + phase:
            self.clock.value = float("nan")

    def settimeout(self, value):
        self.step("settimeout")
        self.timeouts.append(value)

    def connect(self, endpoint):
        self.step("connect")
        self.endpoint = endpoint
        if self.clock is not None:
            self.starts.append(self.clock.value)

    def sendall(self, request):
        self.requests.append(request)
        self.sent.append(bytes(request))
        self.step("sendall")

    def shutdown(self, how):
        self.shutdown_how = how
        self.step("shutdown")

    def recv_into(self, buffer, maximum):
        self.receives.append(buffer)
        self.step("recv_into")
        if maximum != 1024 or type(buffer) is not bytearray:
            raise AssertionError("owned bounded receive required")
        if not self.parts:
            return 0
        data = self.parts.pop(0)
        buffer[:len(data)] = data
        return len(data)

    def close(self):
        self.closed += 1
        self.step("close")


class Factory:
    def __init__(self, sockets=()):
        self.sockets = list(sockets)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if not self.sockets:
            raise AssertionError("unexpected connection or retry")
        return self.sockets.pop(0)


class GenericEventTransportTests(unittest.TestCase):
    def exchange(self, body=b"{}", *, wire=None, fault=None, fragment=1024,
                 method="GET", route=transport.DECISION_ROUTE, request_body=None):
        clock = Clock()
        sock = FakeSocket(http(body) if wire is None else wire, fault=fault, clock=clock, fragment=fragment)
        factory = Factory([sock])
        credential = bytearray(TOKEN)
        timer = transport._MonotonicClock(clock)
        exchange = transport._AuthenticatedExchange(credential, factory, timer, clock.sleep)
        try:
            result = exchange(method, route, request_body)
            return result, sock
        finally:
            transport._zero(credential)
            self.assertTrue(all(not any(b) for b in sock.requests + sock.receives))
            self.assertEqual(sock.closed, 1)

    def test_body_cap_exact_and_fragmented_headers(self):
        value, _ = self.exchange(b"A" * 65536)
        self.assertEqual(len(value), 65536)
        transport._zero(value)
        value, _ = self.exchange(fragment=1)
        self.assertEqual(value, b"{}")
        transport._zero(value)
        with self.assertRaises(transport.TransportFailure):
            self.exchange(b"A" * 65537)

    def test_response_grammar_length_trailing_and_eof(self):
        valid = http(b"{}")
        cases = [valid + b"x", valid[:-1], valid.replace(b"200 OK", b"400 Bad Request"),
                 valid.replace(b"Content-Length: 2", b"Content-Length: 02"),
                 valid.replace(b"Content-Length: 2", b"Content-Length: +2"),
                 valid.replace(b"Content-Length: 2", b"Content-Length: 0"),
                 valid.replace(b"Connection: close", b"X: x\r\nConnection: close"),
                 valid.replace(b"\r\n", b"\n"), b"A" * 1024, b""]
        for wire in cases:
            with self.subTest(wire=wire[:20]), self.assertRaises(transport.TransportFailure):
                self.exchange(wire=wire)

    def test_every_socket_phase_failure_lateness_and_invalid_clock(self):
        for phase in ("settimeout", "connect", "sendall", "shutdown", "recv_into", "close"):
            for prefix in ("", "late_", "backwards_", "nan_"):
                with self.subTest(fault=prefix+phase), self.assertRaises(transport.TransportFailure):
                    self.exchange(fault=prefix+phase)

    def test_failure_latches_and_reentry_cannot_send(self):
        clock = Clock()
        timer = transport._MonotonicClock(clock)
        factory = Factory([FakeSocket(b"", clock=clock)])
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, timer, clock.sleep)
        for _ in range(2):
            with self.assertRaises(transport.TransportFailure):
                exchange("GET", transport.DECISION_ROUTE, None)
        self.assertEqual(factory.calls, 1)
        factory = Factory()
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, timer, clock.sleep)
        exchange._active = True
        with self.assertRaises(transport.TransportFailure):
            exchange("GET", transport.DECISION_ROUTE, None)
        self.assertEqual(factory.calls, 0)

    def test_cleanup_ordinary_fault_preserves_active_control_exception(self):
        for control in (KeyboardInterrupt, SystemExit, GeneratorExit):
            for cleanup in (OSError, ValueError):
                clock = Clock()
                class InterruptedSocket(FakeSocket):
                    def recv_into(self, buffer, maximum):
                        self.receives.append(buffer)
                        raise control()
                    def close(self):
                        self.closed += 1
                        raise cleanup("SYNTHETIC_CLEANUP_FAULT")
                sock = InterruptedSocket(b"", clock=clock)
                token = bytearray(TOKEN)
                with self.assertRaises(control):
                    transport._run_with_socket_factory(token, Factory([sock]), clock=clock, sleep=clock.sleep)
                self.assertFalse(any(token))
                self.assertEqual(sock.closed, 1)
                self.assertTrue(all(not any(b) for b in sock.requests + sock.receives))

    def test_clock_finite_non_decreasing_and_host_deadline(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, "0", 1e308):
            token = bytearray(TOKEN)
            result = transport._run_with_socket_factory(token, Factory(), clock=lambda: value, sleep=lambda _:None)
            self.assertEqual(result, transport._failure())
            self.assertFalse(any(token))
        clock = Clock()
        timer = transport._MonotonicClock(clock)
        factory = Factory()
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, timer, clock.sleep)
        clock.value = 30.0
        with self.assertRaises(transport.TransportFailure):
            exchange("GET", transport.DECISION_ROUTE, None)
        self.assertEqual(factory.calls, 0)

    def test_undersleep_interrupt_and_owned_request_zeroing(self):
        clock = Clock()
        sock = FakeSocket(http(b"{}"), clock=clock)
        factory = Factory([sock])
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, transport._MonotonicClock(clock), lambda _: None)
        result = exchange("GET", transport.DECISION_ROUTE, None)
        transport._zero(result)
        body = action_body("choose:0", False)
        with self.assertRaises(transport.TransportFailure):
            exchange("POST", transport.ACTION_ROUTE, body)
        self.assertEqual(factory.calls, 1)
        self.assertFalse(any(body))
        token = bytearray(TOKEN)
        with mock.patch.object(transport, "run_event", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                transport._run_with_socket_factory(token, Factory(), clock=clock, sleep=clock.sleep)
        self.assertFalse(any(token))

    def test_all_parent_child_actions_and_lineage(self):
        for child, actions in ((False, ["choose:" + str(i) for i in range(8)]),
                              (True, ["select:" + str(i) for i in range(64)] + ["preview", "confirm"])):
            for action in actions:
                body = action_body(action, child)
                request = transport._build_request("POST", transport.ACTION_ROUTE, body, bytearray(TOKEN))
                self.assertFalse(any(body))
                lines = request.split(b"\r\n")
                self.assertEqual(len(lines), 12 if child else 9)
                self.assertEqual(lines[5], b"X-Sts2-Action-Id: " + action.encode())
                if child:
                    self.assertEqual(lines[6:9], [b"X-Sts2-Child-Ordinal: 1", b"X-Sts2-Parent-Decision-Id: " + b"b"*64, b"X-Sts2-Parent-Action-Id: choose:0"])
                transport._zero(request)

    def test_malformed_and_noncanonical_lineage_bodies(self):
        valid = action_body()
        cases = [valid + b"\n", valid.replace(b'"ordinal":1', b'"ordinal":true'),
                 valid.replace(b'"ordinal":1', b'"ordinal":0'), valid.replace(b'"ordinal":1', b'"ordinal":5'),
                 valid.replace(b'"child":', b'"child" :'), valid.replace(b'"parent_decision_id"', b'"wrong"'),
                 valid.replace(b'"choose:0"', b'"select:0"'), valid.replace(b'b'*64, b'B'*64),
                 valid[:-1] + b',"child":null}', valid.replace(b'"select:0"', b'"select:64"'),
                 valid.replace(b'"select:0"', b'"select:00"'), valid.replace(b'"select:0"', b'"choose:0"')]
        for value in cases:
            body = bytearray(value)
            with self.assertRaises(ValueError):
                transport._build_request("POST", transport.ACTION_ROUTE, body, bytearray(TOKEN))
            self.assertFalse(any(body))

    def test_invalid_credential_never_invokes_host(self):
        for token in (bytearray(b"A"*64), bytearray(b"0"*63), bytes(TOKEN)):
            with mock.patch.object(transport, "run_event", side_effect=AssertionError("host called")) as host:
                clock = Clock()
                self.assertEqual(transport._run_with_socket_factory(token, Factory(), clock=clock, sleep=clock.sleep), transport._failure())
                self.assertFalse(host.called)
                if type(token) is bytearray:
                    self.assertFalse(any(token))



if __name__ == "__main__":
    unittest.main()
