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


def http(body, diagnostic=b"none"):
    return transport._RESPONSE_PREFIX + str(len(body)).encode("ascii") + transport._RESPONSE_MIDDLE + diagnostic + transport._RESPONSE_SUFFIX + body


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


    def test_all_diagnostic_codes_are_exact_and_gameplay_body_unchanged(self):
        for code, text in transport._DIAGNOSTICS.items():
            clock = Clock()
            sock = FakeSocket(http(b'{"gameplay":"unchanged"}', code), clock=clock, fragment=1)
            exchange = transport._AuthenticatedExchange(bytearray(TOKEN), Factory([sock]), transport._MonotonicClock(clock), clock.sleep)
            body = exchange("GET", transport.DECISION_ROUTE, None)
            self.assertEqual(body, b'{"gameplay":"unchanged"}')
            self.assertEqual(exchange.last_response_diagnostic, text)
            transport._zero(body)
            self.assertTrue(all(not any(b) for b in sock.requests + sock.receives))

    def test_diagnostic_allowlist_preserves_old_codes_and_exact_append(self):
        expected = (
            "none",
            "parent_ready",
            "parent_unavailable",
            "parent_waiting",
            "pending_binding_failed",
            "pending_ownership",
            "pending_context",
            "pending_task_failed",
            "pending_chosen_entry",
            "pending_chosen_task",
            "pending_chosen_completion",
            "pending_request_task",
            "pending_screen",
            "pending_selectorless_request",
            "pending_overlay",
            "pending_deck",
            "pending_offers",
            "pending_proceed",
            "prepare_binding",
            "prepare_screen",
            "prepare_external_selector",
            "prepare_deck",
            "prepare_foreground",
            "prepare_family",
            "prepare_grid_node",
            "prepare_grid_state",
            "prepare_holders",
            "prepare_candidates",
            "prepare_geometry",
            "prepare_preview_nodes",
            "prepare_preview_state",
            "prepare_confirm",
            "child_ready",
            "map_ready",
            "capture_disposed",
            "capture_exception",
            "diagnostic_unavailable",
            "candidate_expected_null",
            "candidate_expected_duplicate",
            "candidate_displayed_null",
            "candidate_unexpected_model",
            "candidate_displayed_duplicate",
            "candidate_model_null",
            "candidate_card_null",
            "candidate_hitbox_null",
            "candidate_highlight_null",
            "candidate_card_type",
            "candidate_card_invalid",
            "candidate_hitbox_type",
            "candidate_hitbox_invalid",
            "candidate_highlight_type",
            "candidate_highlight_invalid",
            "candidate_material_null",
            "candidate_material_kind",
            "candidate_material_type",
            "candidate_material_invalid",
            "candidate_stable_key",
            "candidate_domain_count",
            "candidate_domain_bounds",
            "candidate_snapshot_count",
            "candidate_holder_identity",
            "candidate_holder_type",
            "candidate_holder_invalid",
            "candidate_model_identity",
            "candidate_card_identity",
            "candidate_hitbox_identity",
            "candidate_highlight_identity",
            "candidate_material_identity",
            "candidate_key_changed",
            "candidate_level_changed",
            "candidate_shader_read",
            "candidate_highlight_unsettled",
            "candidate_initially_selected",
            "candidate_holder_invisible",
            "candidate_card_invisible",
            "candidate_hitbox_invisible",
            "candidate_enabled_read",
            "candidate_none_enabled",
        )
        self.assertEqual(len(expected), 78)
        self.assertEqual(transport._DIAGNOSTICS, {code.encode("ascii"): code for code in expected})
        self.assertTrue(all(1 <= len(code) <= 32 for code in expected))

    def test_leaf_diagnostic_survives_later_rejected_exchange_without_retry(self):
        for invalid in (b"candidate_unknown", b"CandidateCardType", b"candidate_card_type "):
            clock = Clock()
            factory = Factory([FakeSocket(http(b"{}", b"candidate_card_type"), clock=clock),
                               FakeSocket(http(b"{}", invalid), clock=clock)])
            exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, transport._MonotonicClock(clock), clock.sleep)
            body = exchange("GET", transport.DECISION_ROUTE, None)
            transport._zero(body)
            with self.assertRaises(transport.TransportFailure):
                exchange("GET", transport.DECISION_ROUTE, None)
            self.assertEqual(exchange.last_response_diagnostic, "candidate_card_type")
            with self.assertRaises(transport.TransportFailure):
                exchange("GET", transport.DECISION_ROUTE, None)
            self.assertEqual(factory.calls, 2)

    def test_required_diagnostic_header_grammar(self):
        valid = http(b"{}", b"prepare_geometry")
        header = b"X-Sts2-Native-Diagnostic: prepare_geometry\r\n"
        cases = [valid.replace(header, b""), valid.replace(header, header + header),
                 valid.replace(header, b"X-Sts2-Native-Diagnostic: unknown\r\n"),
                 valid.replace(header, b"X-Sts2-Native-Diagnostic: PrepareGeometry\r\n"),
                 valid.replace(header, b"X-Sts2-Native-Diagnostic: prepare_geometry \r\n"),
                 valid.replace(header, b"X-Sts2-Native-Diagnostic:  prepare_geometry\r\n"),
                 valid.replace(header, b"x-sts2-native-diagnostic: prepare_geometry\r\n"),
                 valid.replace(header, b"X-Sts2-Native-Diagnostic: none\r\nInjected: x\r\n"),
                 valid.replace(header, b"X-Sts2-Native-Diagnostic: " + b"a" * 33 + b"\r\n"),
                 valid.replace(b"X-Content-Type-Options: nosniff\r\n" + header, header + b"X-Content-Type-Options: nosniff\r\n")]
        for wire in cases:
            with self.subTest(wire=wire[:10]), self.assertRaises(transport.TransportFailure):
                self.exchange(wire=wire)

    def test_later_incomplete_or_invalid_exchange_retains_previous_diagnostic(self):
        valid = http(b"{}", b"child_ready")
        for wire, fault in ((valid[:-1], None), (valid + b"x", None), (b"", None),
                            (http(b"{}", b"unknown"), None), (valid, "close"),
                            (valid, "late_close"), (valid, "backwards_close")):
            clock = Clock()
            first = FakeSocket(http(b"{}", b"prepare_geometry"), clock=clock)
            second = FakeSocket(wire, fault=fault, clock=clock)
            if fault == "late_close":
                original = second.step
                def later(phase):
                    original(phase)
                    if phase == "close":
                        clock.value = 30.0
                second.step = later
            factory = Factory([first, second])
            exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, transport._MonotonicClock(clock), clock.sleep)
            body = exchange("GET", transport.DECISION_ROUTE, None)
            transport._zero(body)
            with self.assertRaises(transport.TransportFailure):
                exchange("GET", transport.DECISION_ROUTE, None)
            self.assertEqual(exchange.last_response_diagnostic, "prepare_geometry")
            with self.assertRaises(transport.TransportFailure):
                exchange("GET", transport.DECISION_ROUTE, None)
            self.assertEqual(factory.calls, 2)
            self.assertTrue(all(not any(b) for sock in (first, second) for b in sock.requests + sock.receives))

    def test_response_snapshot_updates_only_after_eof_and_successful_close(self):
        clock = Clock()
        snapshots = []
        class ObservedSocket(FakeSocket):
            def close(self):
                snapshots.append(exchange.last_response_diagnostic)
                super().close()
        sock = ObservedSocket(http(b"{}", b"child_ready"), clock=clock)
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), Factory([sock]), transport._MonotonicClock(clock), clock.sleep)
        body = exchange("GET", transport.DECISION_ROUTE, None)
        self.assertEqual(snapshots, ["none"])
        self.assertEqual(exchange.last_response_diagnostic, "child_ready")
        transport._zero(body)

    def test_reentry_after_response_does_not_publish_diagnostic(self):
        clock = Clock()
        class ReenteringSocket(FakeSocket):
            def close(self):
                with self_case.assertRaises(transport.TransportFailure):
                    exchange("GET", transport.DECISION_ROUTE, None)
                super().close()
        self_case = self
        sock = ReenteringSocket(http(b"{}", b"child_ready"), clock=clock)
        factory = Factory([sock])
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, transport._MonotonicClock(clock), clock.sleep)
        with self.assertRaises(transport.TransportFailure):
            exchange("GET", transport.DECISION_ROUTE, None)
        self.assertEqual(exchange.last_response_diagnostic, "none")
        self.assertEqual(factory.calls, 1)
        self.assertTrue(all(not any(b) for b in sock.requests + sock.receives))

    def test_final_summary_retains_transport_diagnostic_when_host_rejects_json(self):
        clock = Clock()
        token = bytearray(TOKEN)
        factory = Factory([FakeSocket(http(b"{}", b"prepare_geometry"), clock=clock)])
        result = transport._run_with_socket_factory(token, factory, clock=clock, sleep=clock.sleep)
        self.assertEqual(result["code"], "invalid_response")
        self.assertEqual(result["last_response_diagnostic"], "prepare_geometry")
        self.assertEqual(factory.calls, 1)
        self.assertFalse(any(token))
        fresh = transport._run_with_socket_factory(bytearray(b"BAD"), Factory(), clock=clock, sleep=clock.sleep)
        self.assertEqual(fresh["last_response_diagnostic"], "none")

    def test_last_complete_response_can_reset_to_none(self):
        clock = Clock()
        factory = Factory([FakeSocket(http(b"{}", code), clock=clock) for code in (b"prepare_geometry", b"none")])
        exchange = transport._AuthenticatedExchange(bytearray(TOKEN), factory, transport._MonotonicClock(clock), clock.sleep)
        for expected in ("prepare_geometry", "none"):
            body = exchange("GET", transport.DECISION_ROUTE, None)
            self.assertEqual(exchange.last_response_diagnostic, expected)
            transport._zero(body)



if __name__ == "__main__":
    unittest.main()
