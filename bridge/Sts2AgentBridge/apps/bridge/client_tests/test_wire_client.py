import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).absolute().parents[1] / 'client'))
from wire_client import BridgeClient, build_request, parse_response
from run_live import core_summary


class ClientBoundaryTests(unittest.TestCase):
    def test_core_outcome_reporting(self):
        for response in ({'status': 'rejected', 'reason': 'stale_decision'},
                         {'code': 'capability_busy'}, {'code': 'bridge_stopped'},
                         {'status': 'backend_fault'}, {'status': 'waiting'}):
            value = {'schema_version': 1, **response}
            self.assertEqual(core_summary('POST', '/probe/v0/public/map-action', value),
                             {'status': 'failed', 'response': value})
        self.assertEqual(core_summary('POST', '/probe/v0/public/map-action',
            {'schema_version': 1, 'status': 'accepted'})['status'], 'passed')

    def test_child_identity_and_injection(self):
        token = bytearray(b'a' * 64)
        value = {'decision_id': 'b' * 64, 'action_id': 'select:15', 'child': {
            'ordinal': 1, 'parent_decision_id': 'c' * 64, 'parent_action_id': 'choose:0'}}
        request = build_request('POST', '/probe/generic-event-v7/public/action', bytearray(json.dumps(value).encode()), token)
        self.assertIn(b'X-Sts2-Child-Ordinal: 1\r\n', request)
        for key, bad in [('action_id', 'choose:0\r\nOrigin: evil'), ('decision_id', 'b' * 63), ('child', {'ordinal': True})]:
            changed = dict(value, **{key: bad})
            with self.assertRaises(ValueError):
                build_request('POST', '/probe/generic-event-v7/public/action', bytearray(json.dumps(changed).encode()), token)

    def test_failed_exchange_cannot_retry_and_close_zeros_credential(self):
        attempts = []
        def connect():
            attempts.append(1)
            raise OSError('unavailable')
        token = bytearray(b'a' * 64)
        client = BridgeClient(token, connector=connect)
        for _ in range(2):
            with self.assertRaises((OSError, ValueError)):
                client.exchange('GET', '/probe/v0/health')
        self.assertEqual(len(attempts), 1)
        client.close()
        self.assertEqual(token, bytearray(64))

    def test_response_framing_rejects_extra_missing_and_diagnostic(self):
        good = bytearray(b'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: 2\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n{}')
        self.assertEqual(parse_response(good, event=False), b'{}')
        for bad in (good + b'x', good[:-1], good.replace(b'Content-Length: 2', b'Content-Length: 02')):
            with self.assertRaises(ValueError):
                parse_response(bad, event=False)
        with self.assertRaises(ValueError):
            parse_response(good, event=True)


if __name__ == '__main__':
    unittest.main()
