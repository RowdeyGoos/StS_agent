"""Real event controller followed by the existing map codec, with no map mutation."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).absolute().parents[3]
sys.path[:0] = [str(ROOT / 'apps/bridge/client'), str(ROOT / 'components/events/host_tests'),
               str(ROOT / 'tools')]
from run_live import run_event_map, verify_map_handoff
from test_generic_event_host import host, Script, upgrade, ordinary
import apply_map_live as maps


READY = dict(schema_version=1, status='ready', decision_kind='map', actionable=True,
             decision_id='b' * 64, screen_kind='map', destination=None,
             candidates=[dict(candidate_index=0, col=2, row=3, kind='monster')],
             legal_actions=[dict(action_id='select:0', kind='select_map_node', candidate_index=0)])


class Clock:
    value = 0.0
    def __call__(self):
        return self.value
    def sleep(self, seconds):
        self.value += seconds


class EventMapTests(unittest.TestCase):
    def exchange(self, rows, event_rows=None):
        event = Script(upgrade() if event_rows is None else event_rows)
        calls, buffers = [], []
        def request(method, route, body):
            if event.rows:
                return event(method, route, body)
            self.assertEqual((method, route, body), ('GET', maps._MAP_DECISION_ROUTE, None))
            calls.append(route)
            value = rows.pop(0) if len(rows) > 1 else rows[0]
            if isinstance(value, BaseException):
                raise value
            response = bytearray(json.dumps(value, separators=(',', ':')).encode()
                                 if type(value) is dict else value)
            buffers.append(response)
            return response
        return request, event, calls, buffers

    def run_flow(self, rows, event_rows=None):
        request, event, calls, buffers = self.exchange(rows, event_rows)
        clock = Clock()
        result = run_event_map(request, host, clock=clock, sleep=clock.sleep)
        self.assertTrue(all(not any(b) for b in buffers + event.buffers))
        return result, event, calls

    def test_completed_child_then_waiting_then_actionable_map(self):
        result, event, calls = self.run_flow([maps._MAP_WAITING, READY])
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual(result['map_handoff'], dict(status='passed', reads=2, candidate_count=1, code=None))
        self.assertEqual(result['event']['completed_card_children'], 1)
        self.assertEqual(result['event']['effects'], 'unverified')
        self.assertEqual(result['event']['child_reconciled'], 2)
        self.assertEqual(sum(method == 'POST' for method, _, _ in event.calls), 4)
        self.assertEqual(len(calls), 2)

    def test_failed_event_never_probes_or_retries(self):
        result, event, calls = self.run_flow([READY], ordinary()[:1] + [('POST', host.TransportFailure())])
        self.assertEqual(result['code'], 'transport_failure')
        self.assertEqual(result['event']['parent_attempted'], 1)
        self.assertEqual(result['map_handoff']['status'], 'not_attempted')
        self.assertEqual(len(event.calls), 2)
        self.assertEqual(calls, [])

    def test_handoff_failure_keeps_successful_event(self):
        for response, code in [(maps._MAP_UNSUPPORTED, 'map_handoff_unsupported'),
                               (OSError('lost'), 'map_handoff_transport_failure'),
                               (KeyboardInterrupt(), 'interrupted'),
                               ({'code': 'capability_busy'}, 'map_handoff_invalid_response')]:
            with self.subTest(code=code):
                result, _, calls = self.run_flow([response])
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['code'], code)
                self.assertEqual(result['event']['status'], 'resolved')
                self.assertEqual(result['event']['completed_card_children'], 1)
                self.assertEqual(len(calls), 1)

    def test_waiting_is_bounded_and_never_success(self):
        result, _, calls = self.run_flow([maps._MAP_WAITING])
        self.assertEqual(result['code'], 'map_handoff_timeout')
        self.assertTrue(1 <= len(calls) <= 100)
        self.assertEqual(result['event']['completed_card_children'], 1)

    def test_expired_response_is_not_success(self):
        clock = Clock()
        response = bytearray(json.dumps(READY).encode())
        def request(*args):
            clock.value += 6
            return response
        result = verify_map_handoff(request, clock=clock, sleep=clock.sleep)
        self.assertEqual(result['code'], 'map_handoff_timeout')
        self.assertEqual(result['reads'], 1)
        self.assertFalse(any(response))

    def test_malformed_or_wrong_surface_is_not_map_evidence(self):
        variants = [b'{}', b'{"status":"ready","status":"waiting"}',
                    b'{"schema_version":1,"status":"unsupported","screen_kind":"unknown","actionable":false,"candidates":[]}']
        for field, value in [('schema_version', 2), ('screen_kind', 'room'), ('decision_id', 'bad'),
                             ('candidates', []), ('legal_actions', []), ('status', 'complete')]:
            changed = copy.deepcopy(READY)
            changed[field] = value
            variants.append(changed)
        for response in variants:
            with self.subTest(response=response):
                result, _, calls = self.run_flow([response])
                self.assertEqual(result['code'], 'map_handoff_invalid_response')
                self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
