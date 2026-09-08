from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).absolute().parents[1]
sys.path[:0] = [str(ROOT / "transport"), str(ROOT.parents[1])]
import card_selection_transport as transport

spec = importlib.util.spec_from_file_location("card_selection_frozen_host_fixture", ROOT.parents[1] / "components/cards/host_tests/test_card_selection_host.py")
assert spec is not None and spec.loader is not None
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)
TOKEN = b"0123456789abcdef" * 4


def http(body):
    return transport._RESPONSE_PREFIX + str(len(body)).encode("ascii") + transport._RESPONSE_SUFFIX + body


def action_body(action="select:0"):
    return bytearray('{"decision_id":"' + 'a' * 64 + '","action_id":"' + action + '"}', 'ascii')


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


class CardSelectionTransportTests(unittest.TestCase):
    def exchange(self, body=b"{}", *, wire=None, fault=None, fragment=1024,
                 method="GET", route=transport.PARENT, request_body=None):
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

    def test_actual_frozen_host_two_complete_sequences_and_pacing(self):
        for selection, script in (("cheese", frames.cheese_script(delayed=True)), ("smith", frames.smith_script())):
            with self.subTest(selection=selection):
                clock = Clock()
                sockets = [FakeSocket(http(v), clock=clock) for v in script]
                token = bytearray(TOKEN)
                result = transport._run_with_socket_factory(selection, token, Factory(sockets), clock=clock, sleep=clock.sleep)
                self.assertEqual(result, {"schema_version": 1, "status": "passed",
                    "parent_attempted": 2, "parent_accepted": 2, "parent_reconciled": 2,
                    "child_attempted": 2, "child_accepted": 2, "child_reconciled": 2})
                self.assertFalse(any(token))
                for sock in sockets:
                    self.assertEqual(sock.endpoint, ("127.0.0.1", 43117))
                    self.assertEqual(sock.shutdown_how, socket.SHUT_WR)
                    self.assertEqual(sock.closed, 1)
                    self.assertTrue(all(not any(b) for b in sock.requests + sock.receives))
                starts = [s.starts[0] for s in sockets]
                self.assertTrue(all(b - a >= 0.05 - 1e-9 for a, b in zip(starts, starts[1:])))
                self.assertEqual(sum(s.sent[0].startswith(b"POST ") for s in sockets), 4)

    def test_exact_header_adaptation_round_trip_and_all_card_slots(self):
        for route, actions in ((transport.PARENT_ACTION, ["begin", "proceed"]),
                               (transport.CHILD_ACTION, ["preview", "confirm"] + ["select:" + str(n) for n in range(64)])):
            for action in actions:
                body = action_body(action)
                original = bytes(body)
                request = transport._build_request("POST", route, body, bytearray(TOKEN))
                self.assertFalse(any(body))
                expected = (b"POST " + route.encode() + b" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer " + TOKEN +
                    b"\r\nAccept: application/json\r\nX-Sts2-Decision-Id: " + b"a"*64 +
                    b"\r\nX-Sts2-Action-Id: " + action.encode() + b"\r\nConnection: close\r\n\r\n")
                self.assertEqual(request, expected)
                lines = request.split(b"\r\n")
                recovered = b'{"decision_id":"' + lines[4][20:] + b'","action_id":"' + lines[5][18:] + b'"}'
                self.assertEqual(recovered, original)
                transport._zero(request)

    def test_all_four_routes_and_get_has_no_action(self):
        for method, route, action in (("GET", transport.PARENT, None), ("GET", transport.CHILD, None),
                ("POST", transport.PARENT_ACTION, "begin"), ("POST", transport.CHILD_ACTION, "select:0")):
            value, _ = self.exchange(method=method, route=route, request_body=None if action is None else action_body(action))
            self.assertEqual(value, bytearray(b"{}"))
            transport._zero(value)

    def test_noncanonical_post_bodies_and_cross_route_actions_reject(self):
        valid = action_body()
        malformed = [bytearray(b"{}"), bytearray(valid + b"\n"), bytearray(valid.replace(b'"decision_id"', b'"x"')),
                     bytearray(valid.replace(b'"action_id"', b'"action_id" :')),
                     bytearray(valid.replace(b'a'*64, b'A'*64)), bytearray(valid + b" "*257),
                     bytearray(b'{"action_id":"select:0","decision_id":"' + b'a'*64 + b'"}'),
                     bytearray(valid[:-1] + b',"extra":0}'), bytearray(valid[:-1] + b',"action_id":"confirm"}')]
        for action in ("select:64", "select:00", "select:-1", "select:+1", "select:1.0", "begin", "select:1\r\nX: x"):
            malformed.append(action_body(action))
        for body in malformed:
            with self.assertRaises(ValueError):
                transport._build_request("POST", transport.CHILD_ACTION, body, bytearray(TOKEN))
            self.assertFalse(any(body))
        for method, route, body in (("GET", transport.PARENT, action_body()), ("POST", transport.CHILD, action_body()),
                ("GET", transport.PARENT + "?x=1", None), ("POST", transport.PARENT_ACTION, action_body())):
            with self.assertRaises(ValueError):
                transport._build_request(method, route, body, bytearray(TOKEN))

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

    def test_post_lost_receipt_never_retries_and_preserves_attempt_count(self):
        for selection, script in (("cheese", frames.cheese_script()), ("smith", frames.smith_script())):
            clock = Clock()
            sockets = [FakeSocket(http(script[0]), clock=clock), FakeSocket(b"", clock=clock)]
            factory = Factory(sockets)
            token = bytearray(TOKEN)
            result = transport._run_with_socket_factory(selection, token, factory, clock=clock, sleep=clock.sleep)
            self.assertEqual(result["code"], "transport_failure")
            self.assertEqual((result["parent_attempted"], result["parent_accepted"], result["child_attempted"]), (1,0,0))
            self.assertEqual(factory.calls, 2)
            self.assertFalse(any(token))

    def test_failure_latches_and_reentry_cannot_send(self):
        clock = Clock()
        timer = transport._MonotonicClock(clock)
        factory = Factory([FakeSocket(b"", clock=clock)])
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, timer, clock.sleep)
        for _ in range(2):
            with self.assertRaises(transport.TransportFailure):
                exchange("GET", transport.PARENT, None)
        self.assertEqual(factory.calls, 1)
        factory = Factory()
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, timer, clock.sleep)
        exchange._active = True
        with self.assertRaises(transport.TransportFailure):
            exchange("GET", transport.PARENT, None)
        self.assertEqual(factory.calls, 0)

    def test_unexpected_factory_or_receive_fault_is_internal_with_truthful_counts(self):
        for where in ("factory", "receive"):
            clock = Clock()
            class DefectiveSocket(FakeSocket):
                def recv_into(self, buffer, maximum):
                    self.receives.append(buffer)
                    raise ValueError("SYNTHETIC_PROGRAMMING_DEFECT")
            first = FakeSocket(http(frames.cheese_script()[0]), clock=clock)
            second = DefectiveSocket(b"", clock=clock)
            factory = Factory([first, second])
            def connect():
                if where == "factory" and factory.calls == 1:
                    factory.calls += 1
                    raise ValueError("SYNTHETIC_FACTORY_DEFECT")
                return factory()
            token = bytearray(TOKEN)
            result = transport._run_with_socket_factory("cheese", token, connect, clock=clock, sleep=clock.sleep)
            self.assertEqual(result["code"], "internal_failure")
            self.assertEqual((result["parent_attempted"], result["parent_accepted"], result["child_attempted"]), (1, 0, 0))
            self.assertEqual(factory.calls, 2)
            self.assertFalse(any(token))
            self.assertTrue(all(not any(b) for b in first.requests + second.requests + second.receives))

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
                    transport._run_with_socket_factory("cheese", token, Factory([sock]), clock=clock, sleep=clock.sleep)
                self.assertFalse(any(token))
                self.assertEqual(sock.closed, 1)
                self.assertTrue(all(not any(b) for b in sock.requests + sock.receives))

    def test_invalid_configuration_or_credential_never_invokes_host(self):
        for selection, token in (("shop", bytearray(TOKEN)), (False, bytearray(TOKEN)), ("cheese", bytearray(b"A"*64)),
                                 ("smith", bytearray(b"0"*63)), ("smith", bytes(TOKEN))):
            with mock.patch.object(transport, "run_card_selection", side_effect=AssertionError("host called")) as host:
                clock = Clock()
                result = transport._run_with_socket_factory(selection, token, Factory(), clock=clock, sleep=clock.sleep)
                self.assertEqual(result, transport._failure())
                self.assertFalse(host.called)
                if type(token) is bytearray:
                    self.assertFalse(any(token))

    def test_clock_finite_non_decreasing_and_host_deadline(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, "0", 1e308):
            token = bytearray(TOKEN)
            result = transport._run_with_socket_factory("smith", token, Factory(), clock=lambda: value, sleep=lambda _:None)
            self.assertEqual(result, transport._failure())
            self.assertFalse(any(token))
        clock = Clock()
        timer = transport._MonotonicClock(clock)
        factory = Factory()
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, timer, clock.sleep)
        clock.value = 30.0
        with self.assertRaises(transport.TransportFailure):
            exchange("GET", transport.PARENT, None)
        self.assertEqual(factory.calls, 0)

    def test_undersleep_interrupt_and_owned_request_zeroing(self):
        clock = Clock()
        sock = FakeSocket(http(b"{}"), clock=clock)
        factory = Factory([sock])
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, transport._MonotonicClock(clock), lambda _: None)
        result = exchange("GET", transport.PARENT, None)
        transport._zero(result)
        body = action_body("begin")
        with self.assertRaises(transport.TransportFailure):
            exchange("POST", transport.PARENT_ACTION, body)
        self.assertEqual(factory.calls, 1)
        self.assertFalse(any(body))
        token = bytearray(TOKEN)
        with mock.patch.object(transport, "run_card_selection", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                transport._run_with_socket_factory("smith", token, Factory(), clock=clock, sleep=clock.sleep)
        self.assertFalse(any(token))


if __name__ == "__main__":
    unittest.main()
