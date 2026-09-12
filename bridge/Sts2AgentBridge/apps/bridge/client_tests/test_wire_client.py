import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).absolute().parents[1] / 'client'))
from wire_client import BridgeClient, build_request, parse_response
from run_live import core_summary


class ClientBoundaryTests(unittest.TestCase):
    def test_sphere_actions_require_event_child_and_canonical_bounds(self):
        route = '/probe/generic-event-v7/public/action'
        token = bytearray(b'a' * 64)
        lineage = dict(ordinal=1, parent_decision_id='c' * 64, parent_action_id='choose:0')
        def request(action, path=route, child=lineage):
            value = dict(decision_id='b' * 64, action_id=action)
            if path == route: value['child'] = child
            return build_request('POST', path, bytearray(json.dumps(value).encode()), token)
        actions = ['tool:small', 'tool:big', 'reward:skip_card']
        actions += [f'reward:{kind}:{i}' for kind in ('claim', 'collect', 'open') for i in range(8)]
        actions += [f'reward:choose:{i}' for i in range(5)]
        for action in actions:
            self.assertIn(('X-Sts2-Action-Id: ' + action + '\r\n').encode(), request(action))
            for path in ('/probe/v0/public/reward-action', '/card-selection-v1/child/action'):
                with self.assertRaises(ValueError): request(action, path)
            with self.assertRaises(ValueError): request(action, child=None)
        for action in ('tool:huge', 'reward:claim:8', 'reward:choose:5', 'reward:open:00',
                       'reward:discard:0', 'tool:big\r\nOrigin: evil'):
            with self.assertRaises(ValueError): request(action)

    def test_abandon_actions_encode_with_exact_event_lineage(self):
        for action in ('cancel','confirm_abandon'):
            value=dict(decision_id='b'*64,action_id=action,child=dict(ordinal=1,parent_decision_id='c'*64,parent_action_id='choose:1'))
            request=build_request('POST','/probe/generic-event-v7/public/action',bytearray(json.dumps(value).encode()),bytearray(b'a'*64))
            self.assertIn(('X-Sts2-Action-Id: '+action+'\r\n').encode(),request)
            self.assertIn(b'X-Sts2-Child-Ordinal: 1\r\n',request)
            self.assertIn(b'X-Sts2-Parent-Action-Id: choose:1\r\n',request)

    def test_pacing_covers_reads_and_writes_without_bursting(self):
        clock = FakeClock()
        opened, sent = [], []
        def connect():
            opened.append(clock.value)
            return FakeSocket(sent)
        client = BridgeClient(bytearray(b'a' * 64), connector=connect, clock=clock, sleep=clock.sleep)
        for i in range(40):
            if i % 2:
                body = bytearray(json.dumps({'decision_id': 'b' * 64, 'action_id': 'proceed'}).encode())
                client.exchange('POST', '/probe/v0/public/reward-action', body)
            else:
                client.exchange('GET', '/probe/v0/health')
        self.assertEqual(len(sent), 40)
        self.assertTrue(all(b - a >= 0.059999 for a, b in zip(opened, opened[1:])))
        self.assertTrue(all(not any(buffer) for buffer in sent))
        client.close()

    def test_expiry_or_interruption_while_pacing_does_not_connect_or_retry(self):
        for mode in ('deadline', 'oversleep', 'interrupt'):
            clock = FakeClock(); opened = []; sent = []
            def connect():
                opened.append(1)
                return FakeSocket(sent)
            def sleep(seconds):
                if mode == 'interrupt': raise KeyboardInterrupt()
                clock.value += seconds + 3
            client = BridgeClient(bytearray(b'a' * 64), connector=connect, clock=clock, sleep=sleep)
            client.exchange('GET', '/probe/v0/health')
            body = bytearray(json.dumps({'decision_id': 'b' * 64, 'action_id': 'proceed'}).encode())
            with self.assertRaises((ValueError, KeyboardInterrupt)):
                client.exchange('POST', '/probe/v0/public/reward-action', body,
                                deadline=0.01 if mode == 'deadline' else None)
            with self.assertRaises(ValueError): client.exchange('GET', '/probe/v0/health')
            self.assertEqual((len(opened),len(sent)), (1,1))
            client.close()

    def test_connection_finishing_after_deadline_never_sends(self):
        clock = FakeClock(); sent = []
        def connect():
            clock.value += 3
            return FakeSocket(sent)
        client = BridgeClient(bytearray(b'a' * 64), connector=connect, clock=clock, sleep=clock.sleep)
        with self.assertRaises(ValueError): client.exchange('GET','/probe/v0/health')
        self.assertEqual(sent,[])
        client.close()

    def test_shop_actions_match_the_existing_room_protocol(self):
        token = bytearray(b'a' * 64)
        route = '/probe/room-flows-v1/public/action'
        def request(action, path=route):
            return build_request('POST', path, bytearray(json.dumps({
                'decision_id': 'b' * 64, 'action_id': action}).encode()), token)
        for action in ('buy:card:0', 'buy:card:9', 'buy:card:10', 'buy:card:31', 'inventory:close', 'leave'):
            self.assertIn(('X-Sts2-Action-Id: ' + action + '\r\n').encode(), request(action))
        for action in ('buy:card:32', 'buy:card:00', 'buy:relic:0', 'inventory:open', 'buy:card:0\r\nOrigin: evil'):
            with self.assertRaises(ValueError):
                request(action)
        for path in ('/probe/v0/public/combat-action', '/probe/item-v1/public/item-action',
                     '/card-selection-v1/parent/action'):
            with self.assertRaises(ValueError):
                request('buy:card:0', path)

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


class FakeClock:
    value = 0.0
    def __call__(self): return self.value
    def sleep(self, seconds): self.value += seconds


class FakeSocket:
    def __init__(self, sent):
        self.sent = sent
        self.response = b'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: 2\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n{}'
    def settimeout(self, seconds): pass
    def sendall(self, data): self.sent.append(data)
    def shutdown(self, how): pass
    def recv(self, count):
        response, self.response = self.response, b''
        return response
    def close(self): pass


if __name__ == '__main__':
    unittest.main()
