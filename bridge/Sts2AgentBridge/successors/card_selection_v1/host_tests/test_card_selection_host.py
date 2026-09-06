from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import unittest

_HOST_PATH = Path(__file__).resolve().parents[1] / "host" / "card_selection_host.py"
_SPEC = importlib.util.spec_from_file_location("card_selection_host_under_test", _HOST_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_HOST = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_HOST)
CHILD = _HOST.CHILD
CHILD_ACTION = _HOST.CHILD_ACTION
PARENT = _HOST.PARENT
PARENT_ACTION = _HOST.PARENT_ACTION
TransportFailure = _HOST.TransportFailure
run_card_selection = _HOST.run_card_selection

NONCE = "1" * 32
D0, D1, D2, D3, D4 = (character * 64 for character in "abcde")


def body(value):
    return bytearray(json.dumps(value, separators=(",", ":")), "ascii")


def parent_observation(status, phase, decision="", kind="", policy="", actions=None):
    return body({
        "schema_version": 1, "kind": "parent_observation",
        "version": "card_selection_parent_v1", "session_nonce": NONCE,
        "parent_ordinal": 1, "status": status, "phase": phase,
        "parent_kind": kind, "policy": policy, "decision_id": decision,
        "legal_actions": [] if actions is None else actions,
    })


def parent_receipt(decision, action):
    return body({
        "schema_version": 1, "kind": "parent_receipt",
        "version": "card_selection_parent_v1", "session_nonce": NONCE,
        "parent_ordinal": 1, "decision_id": decision, "action_id": action,
        "outcome": "accepted",
    })


def parent_resolved(begin=D0, proceed=D4):
    return body({
        "schema_version": 1, "kind": "parent_resolved",
        "version": "card_selection_parent_v1", "session_nonce": NONCE,
        "parent_ordinal": 1, "status": "resolved", "result": "map_handoff",
        "begin_decision_id": begin, "begin_action_id": "begin",
        "proceed_decision_id": proceed, "proceed_action_id": "proceed",
    })


def candidate(slot, selected=False, key=None):
    return {
        "slot": slot, "key": key or f"Card_{slot}", "upgrade_level": 0,
        "visible": True, "enabled": True, "selected": selected,
    }


def result(decision, action):
    return {
        "decision_id": decision, "action_id": action,
        "result": "selected" if action.startswith("select:") else "previewed" if action == "preview" else "committed",
    }


def child_ready(decision, selected, history, *, policy="cheese", phase="selecting", domain=8):
    cards = [candidate(slot, slot in selected) for slot in range(domain)]
    actions = [f"select:{slot}" for slot in range(domain) if slot not in selected]
    if policy == "smith" and phase == "preview":
        actions = ["confirm"]
    return body({
        "schema_version": 1, "kind": "child_observation",
        "version": "card_selection_v1", "session_nonce": NONCE,
        "parent_ordinal": 1, "status": "ready", "phase": phase,
        "operation": "upgrade" if policy == "smith" else "add",
        "commit_mode": "preview_confirm" if policy == "smith" else "auto_at_max",
        "min_select": 1 if policy == "smith" else 2,
        "max_select": 1 if policy == "smith" else 2,
        "decision_id": decision, "candidates": cards,
        "selected_slots": selected, "legal_actions": actions,
        "prior_results": history,
    })


def child_receipt(decision, action):
    return body({
        "schema_version": 1, "kind": "child_receipt",
        "version": "card_selection_v1", "session_nonce": NONCE,
        "parent_ordinal": 1, "decision_id": decision, "action_id": action,
        "outcome": "accepted",
    })


def child_waiting(phase, history):
    return body({
        "schema_version": 1, "kind": "child_observation",
        "version": "card_selection_v1", "session_nonce": NONCE,
        "parent_ordinal": 1, "status": "waiting", "phase": phase,
        "operation": "", "commit_mode": "", "min_select": 0,
        "max_select": 0, "decision_id": "", "candidates": [],
        "selected_slots": [], "legal_actions": [], "prior_results": history,
    })


def child_resolved(selected, history, operation="add"):
    return body({
        "schema_version": 1, "kind": "child_resolved",
        "version": "card_selection_v1", "session_nonce": NONCE,
        "parent_ordinal": 1, "status": "resolved", "phase": "complete",
        "operation": operation, "selected_cards": [candidate(slot, True) for slot in selected],
        "prior_results": history,
    })


def cheese_script(*, delayed=False):
    r0 = result(D1, "select:0")
    r1 = result(D2, "select:1")
    values = [
        parent_observation("ready", "initial", D0, "event", "cheese_gorge_add_two", ["begin"]),
        parent_receipt(D0, "begin"),
    ]
    if delayed:
        values.append(parent_observation("waiting", "transient"))
    values.extend([
        parent_observation("waiting", "card_child"),
        child_ready(D1, [], []),
        child_receipt(D1, "select:0"),
    ])
    if delayed:
        values.append(child_waiting("transient", []))
    values.extend([
        child_ready(D2, [0], [r0]),
        child_receipt(D2, "select:1"),
    ])
    if delayed:
        values.append(child_waiting("submitted", [r0]))
    values.extend([
        child_resolved([0, 1], [r0, r1]),
        parent_observation("ready", "after", D4, "event", "cheese_gorge_add_two", ["proceed"]),
        parent_receipt(D4, "proceed"),
        parent_resolved(),
    ])
    return values


def smith_script():
    selected = result(D1, "select:0")
    committed = result(D2, "confirm")
    return [
        parent_observation("ready", "initial", D0, "rest", "rest_smith_upgrade_one", ["begin"]),
        parent_receipt(D0, "begin"),
        parent_observation("waiting", "card_child"),
        child_ready(D1, [], [], policy="smith", domain=3),
        child_receipt(D1, "select:0"),
        child_ready(D2, [0], [selected], policy="smith", phase="preview", domain=3),
        child_receipt(D2, "confirm"),
        child_resolved([0], [selected, committed], operation="upgrade"),
        parent_observation("ready", "after", D4, "rest", "rest_smith_upgrade_one", ["proceed"]),
        parent_receipt(D4, "proceed"),
        parent_resolved(),
    ]


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration


class Script:
    def __init__(self, values):
        self.values = list(values)
        self.calls = []
        self.responses = []
        self.requests = []

    def __call__(self, method, path, request_body):
        self.calls.append((method, path, None if request_body is None else bytes(request_body)))
        if type(request_body) is bytearray:
            self.requests.append(request_body)
        if not self.values:
            raise AssertionError("unexpected request")
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        if callable(value):
            value = value()
        self.responses.append(value)
        return value

    def zeroed(self, case):
        case.assertTrue(all(not any(item) for item in self.responses))
        case.assertTrue(all(not any(item) for item in self.requests))


class HostTests(unittest.TestCase):
    def run_script(self, values, clock=None):
        script = Script(values)
        clock = clock or Clock()
        output = run_card_selection(script, clock=clock, sleep=clock.sleep)
        return output, script, clock

    def test_cheese_exact_two_full_parent_sequence(self):
        output, script, _ = self.run_script(cheese_script())
        self.assertEqual({
            "schema_version": 1, "status": "passed",
            "parent_attempted": 2, "parent_accepted": 2, "parent_reconciled": 2,
            "child_attempted": 2, "child_accepted": 2, "child_reconciled": 2,
        }, output)
        self.assertEqual(["GET", "POST", "GET", "GET", "POST", "GET", "POST", "GET", "GET", "POST", "GET"], [call[0] for call in script.calls])
        self.assertEqual(["select:0", "select:1"], [json.loads(call[2])["action_id"] for call in script.calls if call[1] == CHILD_ACTION])
        script.zeroed(self)

    def test_rest_exact_one_preview_confirm(self):
        output, script, _ = self.run_script(smith_script())
        self.assertEqual("passed", output["status"])
        self.assertEqual(2, output["child_attempted"])
        self.assertEqual(["select:0", "confirm"], [json.loads(call[2])["action_id"] for call in script.calls if call[1] == CHILD_ACTION])
        script.zeroed(self)

    def test_transient_and_pending_do_not_inflate_counts(self):
        output, script, clock = self.run_script(cheese_script(delayed=True))
        self.assertEqual("passed", output["status"])
        self.assertEqual(2, output["child_reconciled"])
        self.assertEqual(3, len(clock.sleeps))
        self.assertEqual(2, sum(call[0] == "POST" and call[1] == CHILD_ACTION for call in script.calls))
        script.zeroed(self)

    def test_exact_two_never_confirms_one(self):
        values = cheese_script()
        malformed = json.loads(bytes(values[5]))
        malformed["legal_actions"].append("confirm")
        values[5] = body(malformed)
        output, script, _ = self.run_script(values)
        self.assertEqual("invalid_response", output["code"])
        self.assertEqual(1, output["child_attempted"])
        self.assertEqual(1, output["child_accepted"])
        self.assertEqual(0, output["child_reconciled"])
        script.zeroed(self)

    def test_history_and_resolved_shape_tampering_fails_before_count(self):
        cases = []
        wrong_history = cheese_script()
        value = json.loads(bytes(wrong_history[5]))
        value["prior_results"][0]["decision_id"] = D3
        wrong_history[5] = body(value)
        cases.append(wrong_history)
        wrong_card = cheese_script()
        value = json.loads(bytes(wrong_card[7]))
        value["selected_cards"][0]["key"] = "Foreign"
        wrong_card[7] = body(value)
        cases.append(wrong_card)
        for values in cases:
            with self.subTest():
                output, script, _ = self.run_script(values)
                self.assertEqual("invalid_response", output["code"])
                script.zeroed(self)

    def test_reused_decisions_and_reordered_candidates_stop_before_next_post(self):
        reused_child = cheese_script()
        value = json.loads(bytes(reused_child[5]))
        value["decision_id"] = D1
        reused_child[5] = body(value)

        reordered = cheese_script()
        value = json.loads(bytes(reordered[5]))
        value["candidates"] = list(reversed(value["candidates"]))
        value["legal_actions"] = [
            f"select:{item['slot']}" for item in value["candidates"] if not item["selected"]
        ]
        reordered[5] = body(value)

        reused_parent = cheese_script()
        value = json.loads(bytes(reused_parent[8]))
        value["decision_id"] = D0
        reused_parent[8] = body(value)

        for values, expected_posts in ((reused_child, 2), (reordered, 2), (reused_parent, 3)):
            with self.subTest(expected_posts=expected_posts):
                output, script, _ = self.run_script(values)
                self.assertEqual("invalid_response", output["code"])
                self.assertEqual(expected_posts, sum(call[0] == "POST" for call in script.calls))
                script.zeroed(self)

    def test_smith_cannot_resolve_without_confirm_and_fixed_ints_are_exact(self):
        selected = result(D1, "select:0")
        missing_confirm = smith_script()[:5] + [child_resolved([0], [selected], operation="upgrade")]
        output, script, _ = self.run_script(missing_confirm)
        self.assertEqual("invalid_response", output["code"])
        self.assertEqual(1, output["child_attempted"])
        self.assertEqual(0, output["child_reconciled"])
        script.zeroed(self)

        malformed_wait = cheese_script()
        malformed_wait.insert(5, child_waiting("transient", []))
        value = json.loads(bytes(malformed_wait[5]))
        value["min_select"] = False
        malformed_wait[5] = body(value)
        output, script, _ = self.run_script(malformed_wait)
        self.assertEqual("invalid_response", output["code"])
        script.zeroed(self)

        premature_wait = cheese_script()
        premature_wait.insert(3, child_waiting("transient", []))
        output, script, _ = self.run_script(premature_wait)
        self.assertEqual("invalid_response", output["code"])
        self.assertEqual(0, output["child_attempted"])
        script.zeroed(self)

    def test_canonical_duplicate_extra_type_and_size_rejected(self):
        good = parent_observation("ready", "initial", D0, "event", "cheese_gorge_add_two", ["begin"])
        mutations = (
            bytearray(b" " + good),
            bytearray(bytes(good) + b"\n"),
            bytearray(bytes(good).replace(b'"status":"ready"', b'"status":"ready","status":"ready"')),
            bytearray(bytes(good)[:-1] + b',"native_ref":"canary"}'),
            bytearray(bytes(good).replace(b'"parent_ordinal":1', b'"parent_ordinal":true')),
            bytearray(b"{" + b" " * 65535),
        )
        for mutation in mutations:
            with self.subTest(prefix=mutation[:30]):
                output, script, _ = self.run_script([mutation])
                self.assertEqual("invalid_response", output["code"])
                self.assertEqual(0, output["parent_attempted"])
                script.zeroed(self)

    def test_transport_and_uncertain_post_never_retry(self):
        for make_failure, code in (
            (lambda: TransportFailure("credential-canary"), "transport_failure"),
            (lambda: RuntimeError("native-pointer-canary"), "internal_failure"),
            (lambda: body({"schema_version": 1, "kind": "parent_failure", "version": "card_selection_parent_v1", "session_nonce": NONCE, "parent_ordinal": 1, "outcome": "uncertain"}), "action_uncertain"),
        ):
            with self.subTest(code=code):
                output, script, _ = self.run_script(cheese_script()[:1] + [make_failure()])
                self.assertEqual(code, output["code"])
                self.assertEqual(1, output["parent_attempted"])
                self.assertEqual(0, output["parent_accepted"])
                self.assertEqual(2, len(script.calls))
                self.assertNotIn("canary", repr(output))
                script.zeroed(self)

    def test_deadline_before_post_and_after_late_response(self):
        clock = Clock()

        def late_ready():
            clock.now = 30.0
            return parent_observation("ready", "initial", D0, "event", "cheese_gorge_add_two", ["begin"])

        output, script, _ = self.run_script([late_ready], clock)
        self.assertEqual("deadline_exceeded", output["code"])
        self.assertEqual(0, output["parent_attempted"])
        script.zeroed(self)

        values = iter((0.0, 30.0))
        script = Script([])
        output = run_card_selection(script, clock=lambda: next(values), sleep=lambda _: None)
        self.assertEqual("deadline_exceeded", output["code"])
        self.assertEqual([], script.calls)

        ticks = iter((0.0, 0.0, 0.0, 30.0))
        script = Script(cheese_script()[:1])
        output = run_card_selection(script, clock=lambda: next(ticks), sleep=lambda _: None)
        self.assertEqual("deadline_exceeded", output["code"])
        self.assertEqual(["GET"], [call[0] for call in script.calls])
        self.assertEqual(0, output["parent_attempted"])
        script.zeroed(self)

    def test_nonfinite_and_backwards_clocks_fail_fixed(self):
        for ticks in ((0.0, float("nan")), (1.0, 0.5)):
            with self.subTest(ticks=ticks):
                values = iter(ticks)
                script = Script(cheese_script()[:1])
                output = run_card_selection(script, clock=lambda: next(values), sleep=lambda _: None)
                self.assertEqual("internal_failure", output["code"])
                self.assertEqual([], script.calls)

    def test_read_cap_reserves_before_transport(self):
        waiting = parent_observation("waiting", "initial")
        script = Script([bytearray(waiting) for _ in range(1024)])
        output = run_card_selection(script, clock=lambda: 0.0, sleep=lambda _: None)
        self.assertEqual("read_limit_reached", output["code"])
        self.assertEqual(1024, len(script.calls))
        script.zeroed(self)

    def test_response_and_request_buffers_are_exact_owned_types(self):
        class Sub(bytearray):
            pass

        subclass = Sub(parent_observation("waiting", "initial"))
        output, script, _ = self.run_script([subclass])
        self.assertEqual("invalid_response", output["code"])
        self.assertTrue(any(subclass), "foreign subclass remains request-owned")

        script = Script(cheese_script())
        output = run_card_selection(script, clock=lambda: 0.0, sleep=lambda _: None)
        self.assertEqual("passed", output["status"])
        self.assertTrue(script.requests)
        script.zeroed(self)


if __name__ == "__main__":
    unittest.main()
