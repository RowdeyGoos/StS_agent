import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("rest_host", Path(__file__).resolve().parents[2] / "host/room_flow_host.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class RestHostTests(unittest.TestCase):
    def scenario(self, action="lift", before=2, amount=0):
        common = dict(schema_version=1, protocol="room_flows_v1", version="rest_v2", flow_kind="rest", session_nonce="a" * 32, parent_ordinal=1)
        options = [dict(action_id=host.rest_kind(action), counter=before, enabled=True, amount=amount)]
        cards = [dict(slot=i, key="CARD_" + str(i), upgrade=0, removable=i != 1) for i in range(3)] if action.startswith("cook:") else []
        decision = host.rest_digest(common["session_nonce"], options, cards)
        ready = dict(common, status="ready", phase="choose_option", decision_id=decision, options=options, cards=cards, legal_actions=[action], result=None)
        receipt = dict(common, status="accepted", decision_id=decision, action_id=action)
        waiting = dict(common, status="waiting", phase="action_waiting", decision_id="", options=[], cards=[], legal_actions=[], result=None)
        complete = dict(common, status="complete", phase="complete", decision_id="", options=[], cards=[], legal_actions=[], result=dict(decision_id=decision, action_id=action, before=before, after=before + host.rest_delta(action, amount)))
        return [ready, receipt, waiting, complete]

    def run_host(self, values, action="lift", lost=False, cook_slots=None):
        calls, buffers = [], []
        def exchange(method, route, decision, selected, deadline):
            calls.append((method, selected))
            if lost and method == "POST":
                raise TimeoutError()
            body = bytearray(json.dumps(values.pop(0), separators=(",", ":")).encode())
            buffers.append(body)
            return body
        result = host.run_rest(exchange, action, cook_slots=cook_slots, sleep=lambda _: None)
        self.assertTrue(all(not any(b) for b in buffers))
        return result, calls

    def test_effects(self):
        for action, before in (("lift", 0), ("lift", 2), ("kindle", 0), ("kindle", 12)):
            with self.subTest(action=action, before=before):
                result, calls = self.run_host(self.scenario(action, before), action)
                self.assertEqual(result["status"], "passed")
                self.assertEqual(result["handoff"], "rest")
                self.assertEqual([c for c in calls if c[0] == "POST"], [("POST", action)])

    def test_new_effects(self):
        for action, before, amount in (("dig", 5, 0), ("hatch", 5, 0), ("clone", 3, 2), ("clone", 0, 0), ("cook:0:2", 60, 0)):
            result, calls = self.run_host(self.scenario(action, before, amount), host.rest_kind(action), cook_slots=(0, 2) if action.startswith("cook:") else None)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual(result["action"], action)
            self.assertEqual([c for c in calls if c[0] == "POST"], [("POST", action)])

    def test_cook_default_and_unavailable_pair(self):
        result, calls = self.run_host(self.scenario("cook:0:2", 60), "cook")
        self.assertEqual(result["status"], "passed")
        result, calls = self.run_host(self.scenario("cook:0:2", 60), "cook", cook_slots=(0, 1))
        self.assertEqual(result["code"], "rest_option_unavailable")
        self.assertEqual(calls, [("GET", None)])
        for slots in ((2, 0), (0, 0), (0, 64), (True, 2)):
            with self.assertRaises(ValueError):
                host.run_rest(lambda *_: self.fail("no I/O"), "cook", cook_slots=slots)

    def test_clone_exact_amount(self):
        values = self.scenario("clone", 3, 2); values[-1]["result"]["after"] = 4
        result, calls = self.run_host(values, "clone")
        self.assertEqual(result["code"], "invalid_response")
        self.assertEqual(sum(c[0] == "POST" for c in calls), 1)

    def test_maximum_cook_response_fits(self):
        options = [dict(action_id="cook", counter=60, enabled=True, amount=0)]
        cards = [dict(slot=i, key="A" * 128, upgrade=0, removable=True) for i in range(64)]
        value = self.scenario("cook:0:2", 60)[0]
        value.update(options=options, cards=cards, legal_actions=host.rest_actions(options, cards), decision_id=host.rest_digest(value["session_nonce"], options, cards))
        raw = bytearray(json.dumps(value, separators=(",", ":")).encode())
        self.assertEqual(len(value["legal_actions"]), 2016)
        self.assertLess(len(raw), host.MAX_BODY)
        host.decode(raw, "rest")

    def test_unavailable_no_input(self):
        result, calls = self.run_host(self.scenario("kindle", 0))
        self.assertEqual(result["code"], "rest_option_unavailable")
        self.assertEqual(calls, [("GET", None)])

    def test_bad_response_never_retries(self):
        for index, field, value in ((3, "after", 4), (3, "before", 1), (3, "decision_id", "b" * 64), (3, "action_id", "kindle")):
            values = self.scenario()
            values[index]["result"][field] = value
            result, calls = self.run_host(values)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(sum(c[0] == "POST" for c in calls), 1)
        values = self.scenario(); values[2] = copy.deepcopy(values[0])
        result, calls = self.run_host(values)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(sum(c[0] == "POST" for c in calls), 1)

    def test_lost_receipt(self):
        result, calls = self.run_host(self.scenario(), lost=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(calls, [("GET", None), ("POST", "lift")])

    def test_stale_digest_and_nonce(self):
        values = self.scenario(); values[0]["options"][0]["counter"] = 1
        result, calls = self.run_host(values)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(calls), 1)
        values = self.scenario(); values[2]["session_nonce"] = "b" * 32
        result, calls = self.run_host(values)
        self.assertEqual(result["status"], "failed")

    def test_complete_without_receipt(self):
        result, calls = self.run_host([self.scenario()[-1]])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(calls), 1)

    def test_deadline(self):
        now = [0.0]
        waiting = self.scenario()[2]; waiting["phase"] = "unknown"
        def exchange(*_): return bytearray(json.dumps(waiting, separators=(",", ":")).encode())
        def sleep(seconds): now[0] += seconds
        result = host.run_rest(exchange, "lift", clock=lambda: now[0], sleep=sleep)
        self.assertEqual(result["code"], "deadline_exceeded")
        self.assertEqual(result["attempted"], 0)


if __name__ == "__main__":
    unittest.main()
