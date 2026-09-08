from __future__ import annotations

import json
import unittest

from host import TransportFailure, run_collection


NONCE = "0123456789abcdef0123456789abcdef"
OTHER_NONCE = "fedcba9876543210fedcba9876543210"
DECISION = "1b7f4402e889aa496e56b6eb0087dd2f3c680864ab0d19d60f4a1ab79da4ba22"
RELIC_DECISION = "42a8c9ef2f28e08ee42bb69714fb443e79477994af99af3509e1c2d138fab5de"
FULL_DECISION = "2eff6e0850613ab81124b112772ab8042e40d608525eb53c0a805d42073c8f47"
OTHER_DECISION = "0" * 64

WAITING = (
    '{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    '"session_nonce":"0123456789abcdef0123456789abcdef",'
    '"surface_ordinal":1,"status":"waiting"}'
)
UNSUPPORTED = WAITING.replace('"waiting"', '"unsupported"')
READY = (
    '{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    '"session_nonce":"0123456789abcdef0123456789abcdef",'
    '"surface_ordinal":1,"status":"ready",'
    '"decision_id":"1b7f4402e889aa496e56b6eb0087dd2f3c680864ab0d19d60f4a1ab79da4ba22",'
    '"offers":[{"index":2,"kind":"potion","key":"Potion_A","enabled":true},'
    '{"index":7,"kind":"relic","key":"Relic_B","enabled":true}],'
    '"potion_slots":[null,"Held_1"],'
    '"legal_actions":["collect:2","collect:7"]}'
)
READY_RELIC = (
    '{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    '"session_nonce":"fedcba9876543210fedcba9876543210",'
    '"surface_ordinal":1,"status":"ready",'
    '"decision_id":"42a8c9ef2f28e08ee42bb69714fb443e79477994af99af3509e1c2d138fab5de",'
    '"offers":[{"index":3,"kind":"relic","key":"Relic_Only","enabled":true}],'
    '"potion_slots":[],"legal_actions":["collect:3"]}'
)
READY_FULL_MIXED = (
    '{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    '"session_nonce":"0123456789abcdef0123456789abcdef",'
    '"surface_ordinal":1,"status":"ready",'
    '"decision_id":"2eff6e0850613ab81124b112772ab8042e40d608525eb53c0a805d42073c8f47",'
    '"offers":[{"index":2,"kind":"potion","key":"Potion_A","enabled":true},'
    '{"index":7,"kind":"relic","key":"Relic_B","enabled":true}],'
    '"potion_slots":["Held_0","Held_1"],"legal_actions":["collect:7"]}'
)
ACCEPTED = (
    '{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    '"session_nonce":"0123456789abcdef0123456789abcdef",'
    '"surface_ordinal":1,"status":"accepted",'
    '"decision_id":"1b7f4402e889aa496e56b6eb0087dd2f3c680864ab0d19d60f4a1ab79da4ba22",'
    '"action_id":"collect:2"}'
)
ACCEPTED_RELIC = (
    '{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    '"session_nonce":"fedcba9876543210fedcba9876543210",'
    '"surface_ordinal":1,"status":"accepted",'
    '"decision_id":"42a8c9ef2f28e08ee42bb69714fb443e79477994af99af3509e1c2d138fab5de",'
    '"action_id":"collect:3"}'
)
ACCEPTED_FULL = ACCEPTED.replace(DECISION, FULL_DECISION).replace("collect:2", "collect:7")
RESOLVED = (
    '{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    '"session_nonce":"0123456789abcdef0123456789abcdef",'
    '"surface_ordinal":1,"status":"resolved",'
    '"decision_id":"1b7f4402e889aa496e56b6eb0087dd2f3c680864ab0d19d60f4a1ab79da4ba22",'
    '"action_id":"collect:2","offer_index":2,"kind":"potion",'
    '"key":"Potion_A","result":"collected"}'
)
RESOLVED_RELIC = (
    '{"schema_version":1,"protocol":"item_probe_v1","version":"item_v1",'
    '"session_nonce":"fedcba9876543210fedcba9876543210",'
    '"surface_ordinal":1,"status":"resolved",'
    '"decision_id":"42a8c9ef2f28e08ee42bb69714fb443e79477994af99af3509e1c2d138fab5de",'
    '"action_id":"collect:3","offer_index":3,"kind":"relic",'
    '"key":"Relic_Only","result":"collected"}'
)
RESOLVED_FULL = (
    RESOLVED.replace(DECISION, FULL_DECISION)
    .replace("collect:2", "collect:7")
    .replace('"offer_index":2', '"offer_index":7')
    .replace('"kind":"potion"', '"kind":"relic"')
    .replace('"key":"Potion_A"', '"key":"Relic_B"')
)
REJECTED = WAITING.replace('"waiting"', '"rejected"')
UNCERTAIN = WAITING.replace('"waiting"', '"uncertain"')
ERROR = WAITING.replace(
    '"status":"waiting"', '"status":"error","code":"internal_failure"'
)

PASSED_POTION = {
    "schema_version": 1,
    "status": "passed",
    "milestone": "item_v1_collection",
    "item_kind": "potion",
    "attempted": 1,
    "accepted": 1,
    "reconciled": 1,
}


def failed(code: str) -> dict[str, object]:
    return {"schema_version": 1, "status": "failed", "code": code}


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, duration: float) -> None:
        self.sleeps.append(duration)
        self.now += duration


class ScriptedExchange:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, object, object, float]] = []
        self.returned: list[bytearray] = []

    def __call__(self, method, route, decision_id, action_id, deadline):
        self.calls.append((method, route, decision_id, action_id, deadline))
        if not self.responses:
            raise AssertionError("unexpected exchange")
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            item = item()
        if type(item) is str:
            item = bytearray(item, "utf-8")
        if type(item) is bytearray:
            self.returned.append(item)
        return item

    def assert_zeroed(self, case: unittest.TestCase) -> None:
        case.assertTrue(self.returned)
        case.assertTrue(all(not any(buffer) for buffer in self.returned))


class HostTests(unittest.TestCase):
    def run_script(self, script: ScriptedExchange, clock: FakeClock | None = None):
        clock = clock or FakeClock()
        result = run_collection(script, clock=clock, sleep=clock.sleep)
        return result, clock

    def test_potion_success_uses_first_advertised_action_and_one_deadline(self):
        script = ScriptedExchange(READY, ACCEPTED, RESOLVED)
        result, _ = self.run_script(script)
        self.assertEqual(PASSED_POTION, result)
        self.assertEqual(
            [
                ("GET", "/probe/item-v1/public/item-decision", None, None),
                ("POST", "/probe/item-v1/public/item-action", DECISION, "collect:2"),
                ("GET", "/probe/item-v1/public/item-decision", None, None),
            ],
            [call[:4] for call in script.calls],
        )
        self.assertEqual({15.0}, {call[4] for call in script.calls})
        script.assert_zeroed(self)

    def test_delayed_relic_success_waits_before_and_after_receipt(self):
        waiting_other = WAITING.replace(NONCE, OTHER_NONCE)
        script = ScriptedExchange(
            waiting_other,
            READY_RELIC,
            ACCEPTED_RELIC,
            waiting_other,
            RESOLVED_RELIC,
        )
        result, clock = self.run_script(script)
        self.assertEqual(
            {
                "schema_version": 1,
                "status": "passed",
                "milestone": "item_v1_collection",
                "item_kind": "relic",
                "attempted": 1,
                "accepted": 1,
                "reconciled": 1,
            },
            result,
        )
        self.assertEqual([0.1, 0.1], clock.sleeps)
        self.assertEqual(1, sum(call[0] == "POST" for call in script.calls))
        script.assert_zeroed(self)

    def test_full_belt_mixed_screen_selects_only_advertised_relic(self):
        script = ScriptedExchange(READY_FULL_MIXED, ACCEPTED_FULL, RESOLVED_FULL)
        result, _ = self.run_script(script)
        self.assertEqual("relic", result["item_kind"])
        self.assertEqual((FULL_DECISION, "collect:7"), script.calls[1][2:4])
        script.assert_zeroed(self)

    def test_unsupported_and_application_error_stop_without_action(self):
        for body, expected in (
            (UNSUPPORTED, "unsupported_state"),
            (ERROR, "internal_failure"),
        ):
            with self.subTest(expected=expected):
                script = ScriptedExchange(body)
                result, _ = self.run_script(script)
                self.assertEqual(failed(expected), result)
                self.assertEqual(["GET"], [call[0] for call in script.calls])
                script.assert_zeroed(self)

    def test_rejected_uncertain_and_lost_receipts_never_retry(self):
        for receipt, expected in (
            (REJECTED, "action_rejected"),
            (UNCERTAIN, "action_uncertain"),
            (TransportFailure("credential-canary"), "transport_failure"),
        ):
            with self.subTest(expected=expected):
                script = ScriptedExchange(READY, receipt)
                result, _ = self.run_script(script)
                self.assertEqual(failed(expected), result)
                self.assertEqual(["GET", "POST"], [call[0] for call in script.calls])
                self.assertNotIn("canary", repr(result))
                script.assert_zeroed(self)

    def test_post_accept_transport_failure_is_terminal_without_retry(self):
        script = ScriptedExchange(READY, ACCEPTED, TransportFailure("lost read"))
        result, _ = self.run_script(script)
        self.assertEqual(failed("transport_failure"), result)
        self.assertEqual(["GET", "POST", "GET"], [call[0] for call in script.calls])
        script.assert_zeroed(self)

    def test_ordinary_exchange_exception_is_fixed_internal_failure(self):
        script = ScriptedExchange(RuntimeError("private_native_pointer_0x123"))
        result, _ = self.run_script(script)
        self.assertEqual(failed("internal_failure"), result)
        self.assertNotIn("private", repr(result))

    def test_null_immutable_and_subclass_responses_are_invalid(self):
        class MutableSubclass(bytearray):
            pass

        subclass = MutableSubclass(WAITING, "ascii")
        for response in (None, WAITING.encode("ascii"), subclass):
            with self.subTest(response_type=type(response).__name__):
                script = ScriptedExchange(response)
                result, _ = self.run_script(script)
                self.assertEqual(failed("invalid_response"), result)
                self.assertEqual(1, len(script.calls))
        self.assertTrue(any(subclass), "non-exact buffers remain exchange-owned")

    def test_canonical_json_and_private_canary_mutations_are_rejected_and_zeroed(self):
        reordered = READY.replace(
            '{"schema_version":1,"protocol":"item_probe_v1"',
            '{"protocol":"item_probe_v1","schema_version":1',
        )
        duplicate = READY.replace('"status":"ready"', '"status":"ready","status":"ready"')
        unknown = READY[:-1] + ',"native_pointer":"credential-canary"}'
        mutations = (
            READY + "\n",
            READY.replace("item_probe_v1", "item_probe_\\u00761"),
            READY.replace('"schema_version":1', '"schema_version":true'),
            READY.replace('"surface_ordinal":1', '"surface_ordinal":1.0'),
            READY.replace("Potion_A", "Potion_é"),
            reordered,
            duplicate,
            unknown,
            " " * 4097,
            "{",
        )
        for mutation in mutations:
            with self.subTest(prefix=mutation[:30]):
                script = ScriptedExchange(mutation)
                result, _ = self.run_script(script)
                self.assertEqual(failed("invalid_response"), result)
                self.assertEqual({"schema_version", "status", "code"}, set(result))
                self.assertNotIn("canary", repr(result))
                script.assert_zeroed(self)

    def test_ready_digest_shape_order_action_and_bounds_mutations_are_rejected(self):
        nine_offers = [
            {"index": index, "kind": "relic", "key": f"R{index}", "enabled": True}
            for index in range(9)
        ]
        oversized = {
            "schema_version": 1,
            "protocol": "item_probe_v1",
            "version": "item_v1",
            "session_nonce": NONCE,
            "surface_ordinal": 1,
            "status": "ready",
            "decision_id": OTHER_DECISION,
            "offers": nine_offers,
            "potion_slots": [],
            "legal_actions": [f"collect:{index}" for index in range(9)],
        }
        mutations = (
            READY.replace(DECISION, OTHER_DECISION),
            READY.replace('["collect:2","collect:7"]', '["collect:7","collect:2"]'),
            READY.replace('["collect:2","collect:7"]', '["collect:2"]'),
            READY.replace('"index":7', '"index":2'),
            READY.replace("Potion_A", "bad-key"),
            READY.replace("Potion_A", "A" * 129),
            READY.replace("collect:2", "collect:02"),
            READY.replace('"index":7', '"index":256'),
            READY.replace('[null,"Held_1"]', "[null,null,null,null,null,null,null,null,null]"),
            json.dumps(oversized, separators=(",", ":")),
        )
        for mutation in mutations:
            with self.subTest(prefix=mutation[:40]):
                script = ScriptedExchange(mutation)
                result, _ = self.run_script(script)
                self.assertEqual(failed("invalid_response"), result)
                self.assertEqual(1, len(script.calls))
                script.assert_zeroed(self)

    def test_ready_accepts_exact_offer_slot_index_and_key_boundaries(self):
        offers = [
            {"index": index, "kind": "relic", "key": f"R{index}", "enabled": True}
            for index in range(7)
        ] + [{"index": 255, "kind": "relic", "key": "A" * 128, "enabled": True}]
        actions = [f"collect:{index}" for index in range(7)] + ["collect:255"]
        maximum_ready = json.dumps(
            {
                "schema_version": 1,
                "protocol": "item_probe_v1",
                "version": "item_v1",
                "session_nonce": NONCE,
                "surface_ordinal": 1,
                "status": "ready",
                "decision_id": "402d194ef6e6b514b0fec51475d96cbcda82393e577f4cc14e5512544349d2bb",
                "offers": offers,
                "potion_slots": [None] * 8,
                "legal_actions": actions,
            },
            separators=(",", ":"),
        )
        accepted = ACCEPTED.replace(DECISION, "402d194ef6e6b514b0fec51475d96cbcda82393e577f4cc14e5512544349d2bb").replace("collect:2", "collect:0")
        resolved = (
            RESOLVED.replace(DECISION, "402d194ef6e6b514b0fec51475d96cbcda82393e577f4cc14e5512544349d2bb")
            .replace("collect:2", "collect:0")
            .replace('"offer_index":2', '"offer_index":0')
            .replace('"kind":"potion"', '"kind":"relic"')
            .replace('"key":"Potion_A"', '"key":"R0"')
        )
        script = ScriptedExchange(maximum_ready, accepted, resolved)
        result, _ = self.run_script(script)
        self.assertEqual("passed", result["status"])
        self.assertEqual("relic", result["item_kind"])
        self.assertEqual("collect:0", script.calls[1][3])
        script.assert_zeroed(self)

    def test_receipt_requires_exact_nonce_decision_and_action(self):
        mutations = (
            ACCEPTED.replace(NONCE, OTHER_NONCE),
            ACCEPTED.replace(DECISION, OTHER_DECISION),
            ACCEPTED.replace("collect:2", "collect:7"),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation[-90:]):
                script = ScriptedExchange(READY, mutation, RESOLVED)
                result, _ = self.run_script(script)
                self.assertEqual(failed("invalid_response"), result)
                self.assertEqual(["GET", "POST"], [call[0] for call in script.calls])
                script.assert_zeroed(self)

    def test_resolved_requires_every_original_offer_correlation(self):
        alternate_offer = (
            RESOLVED.replace("collect:2", "collect:7")
            .replace('"offer_index":2', '"offer_index":7')
        )
        mutations = (
            RESOLVED.replace(NONCE, OTHER_NONCE),
            RESOLVED.replace(DECISION, OTHER_DECISION),
            alternate_offer,
            RESOLVED.replace('"kind":"potion"', '"kind":"relic"'),
            RESOLVED.replace("Potion_A", "Other_Key"),
            RESOLVED.replace("collected", "declined"),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation[-100:]):
                script = ScriptedExchange(READY, ACCEPTED, mutation)
                result, _ = self.run_script(script)
                self.assertEqual(failed("invalid_response"), result)
                self.assertEqual(["GET", "POST", "GET"], [call[0] for call in script.calls])
                script.assert_zeroed(self)

    def test_unsolicited_resolved_and_ready_after_acceptance_are_invalid(self):
        for responses, methods in (
            ((RESOLVED,), ["GET"]),
            ((READY, ACCEPTED, READY), ["GET", "POST", "GET"]),
            ((READY, RESOLVED), ["GET", "POST"]),
        ):
            with self.subTest(methods=methods):
                script = ScriptedExchange(*responses)
                result, _ = self.run_script(script)
                self.assertEqual(failed("invalid_response"), result)
                self.assertEqual(methods, [call[0] for call in script.calls])
                script.assert_zeroed(self)

    def test_session_drift_from_waiting_and_after_acceptance_stops_immediately(self):
        changed_waiting = WAITING.replace(NONCE, OTHER_NONCE)
        cases = (
            ((WAITING, READY_RELIC), ["GET", "GET"]),
            ((READY, ACCEPTED, changed_waiting), ["GET", "POST", "GET"]),
        )
        for responses, methods in cases:
            with self.subTest(methods=methods):
                script = ScriptedExchange(*responses)
                result = run_collection(script, clock=lambda: 0.0, sleep=lambda _delay: None)
                self.assertEqual(failed("invalid_response"), result)
                self.assertEqual(methods, [call[0] for call in script.calls])
                script.assert_zeroed(self)

    def test_unsupported_or_error_after_acceptance_preserves_fixed_failure(self):
        for body, code in ((UNSUPPORTED, "unsupported_state"), (ERROR, "internal_failure")):
            with self.subTest(code=code):
                script = ScriptedExchange(READY, ACCEPTED, body)
                result, _ = self.run_script(script)
                self.assertEqual(failed(code), result)
                self.assertEqual(["GET", "POST", "GET"], [call[0] for call in script.calls])
                script.assert_zeroed(self)

    def test_read_limit_is_exactly_256_without_an_action(self):
        script = ScriptedExchange(*([WAITING] * 256))
        result = run_collection(script, clock=lambda: 0.0, sleep=lambda _delay: None)
        self.assertEqual(failed("read_limit_reached"), result)
        self.assertEqual(256, len(script.calls))
        self.assertTrue(all(call[0] == "GET" for call in script.calls))
        script.assert_zeroed(self)

    def test_read_limit_is_shared_across_pre_and_post_acceptance_reads(self):
        script = ScriptedExchange(*([WAITING] * 254), READY, ACCEPTED, WAITING)
        result = run_collection(script, clock=lambda: 0.0, sleep=lambda _delay: None)
        self.assertEqual(failed("read_limit_reached"), result)
        self.assertEqual(256, sum(call[0] == "GET" for call in script.calls))
        self.assertEqual(1, sum(call[0] == "POST" for call in script.calls))
        self.assertEqual("GET", script.calls[-1][0])
        script.assert_zeroed(self)

    def test_ready_on_final_read_does_not_dispatch_without_reconciliation_budget(self):
        script = ScriptedExchange(*([WAITING] * 255), READY, ACCEPTED)
        result = run_collection(script, clock=lambda: 0.0, sleep=lambda _delay: None)
        self.assertEqual(failed("read_limit_reached"), result)
        self.assertEqual(256, len(script.calls))
        self.assertTrue(all(call[0] == "GET" for call in script.calls))
        script.assert_zeroed(self)

    def test_deadline_before_first_exchange_makes_no_request(self):
        values = iter((0.0, 15.0))
        script = ScriptedExchange(READY)
        result = run_collection(script, clock=lambda: next(values), sleep=lambda _delay: None)
        self.assertEqual(failed("deadline_exceeded"), result)
        self.assertEqual([], script.calls)

    def test_late_initial_response_is_zeroed_and_never_adopted(self):
        clock = FakeClock()

        def late_ready():
            clock.now = 15.0
            return READY

        script = ScriptedExchange(late_ready)
        result, _ = self.run_script(script, clock)
        self.assertEqual(failed("deadline_exceeded"), result)
        self.assertEqual(["GET"], [call[0] for call in script.calls])
        script.assert_zeroed(self)

    def test_late_receipt_is_not_accepted_and_no_reconciliation_follows(self):
        clock = FakeClock()

        def late_receipt():
            clock.now = 15.0
            return ACCEPTED

        script = ScriptedExchange(READY, late_receipt, RESOLVED)
        result, _ = self.run_script(script, clock)
        self.assertEqual(failed("deadline_exceeded"), result)
        self.assertEqual(["GET", "POST"], [call[0] for call in script.calls])
        script.assert_zeroed(self)

    def test_late_resolved_response_cannot_reconcile(self):
        clock = FakeClock()

        def late_resolved():
            clock.now = 15.0
            return RESOLVED

        script = ScriptedExchange(READY, ACCEPTED, late_resolved)
        result, _ = self.run_script(script, clock)
        self.assertEqual(failed("deadline_exceeded"), result)
        self.assertEqual(["GET", "POST", "GET"], [call[0] for call in script.calls])
        script.assert_zeroed(self)

    def test_wait_sleep_is_clamped_to_remaining_deadline_and_checked_after(self):
        clock = FakeClock()

        def almost_late_waiting():
            clock.now = 14.95
            return WAITING

        script = ScriptedExchange(almost_late_waiting)
        result, _ = self.run_script(script, clock)
        self.assertEqual(failed("deadline_exceeded"), result)
        self.assertEqual(1, len(clock.sleeps))
        self.assertGreater(clock.sleeps[0], 0.0)
        self.assertLessEqual(clock.sleeps[0], 0.1)
        self.assertAlmostEqual(15.0, clock.now)
        script.assert_zeroed(self)

    def test_cancellation_after_exchange_zeroes_owned_buffer_and_propagates(self):
        class InterruptingClock:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 3:
                    raise KeyboardInterrupt()
                return 0.0

        script = ScriptedExchange(READY)
        with self.assertRaises(KeyboardInterrupt):
            run_collection(script, clock=InterruptingClock(), sleep=lambda _delay: None)
        script.assert_zeroed(self)

    def test_cancellation_from_action_exchange_and_sleep_propagates(self):
        action_script = ScriptedExchange(READY, KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.run_script(action_script)
        action_script.assert_zeroed(self)

        waiting_script = ScriptedExchange(WAITING)
        with self.assertRaises(KeyboardInterrupt):
            run_collection(waiting_script, clock=lambda: 0.0, sleep=lambda _delay: (_ for _ in ()).throw(KeyboardInterrupt()))
        waiting_script.assert_zeroed(self)

        for cancellation in (SystemExit(), GeneratorExit()):
            with self.subTest(cancellation=type(cancellation).__name__):
                script = ScriptedExchange(READY, cancellation)
                with self.assertRaises(type(cancellation)):
                    self.run_script(script)
                script.assert_zeroed(self)

    def test_clock_and_sleep_faults_are_sanitized_internal_failures(self):
        class BrokenClock:
            def __call__(self):
                raise RuntimeError("credential-canary")

        result = run_collection(ScriptedExchange(READY), clock=BrokenClock(), sleep=lambda _delay: None)
        self.assertEqual(failed("internal_failure"), result)

        script = ScriptedExchange(WAITING)
        result = run_collection(
            script,
            clock=lambda: 0.0,
            sleep=lambda _delay: (_ for _ in ()).throw(RuntimeError("private-canary")),
        )
        self.assertEqual(failed("internal_failure"), result)
        self.assertNotIn("canary", repr(result))
        script.assert_zeroed(self)

        class LateBrokenClock:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 3:
                    raise RuntimeError("post-exchange-canary")
                return 0.0

        script = ScriptedExchange(READY)
        result = run_collection(script, clock=LateBrokenClock(), sleep=lambda _delay: None)
        self.assertEqual(failed("internal_failure"), result)
        script.assert_zeroed(self)


if __name__ == "__main__":
    unittest.main()
