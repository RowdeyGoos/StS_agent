"""Adversarial client accounting and nested combat selection transitions."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).absolute().parents[3]
sys.path[:0] = [str(ROOT / 'apps/bridge/client'), str(ROOT / 'tools')]
import combat_host as host
from probe_live_fixtures import _FIXTURE_COMBAT


def encoded(value):
    return bytearray(json.dumps(value, separators=(',', ':')).encode())


class ChoiceWire:
    def __init__(self, *, minimum=0, maximum=2, manual=True):
        self.minimum, self.maximum, self.manual = minimum, maximum, manual
        self.selected = []
        self.count = 0
        self.closed = False
        self.buffers = []
        self.posts = []
        self.corrupt = lambda value: value

    def request(self, method, route, body):
        if method == 'POST':
            self.buffers.append(body)
            request = json.loads(body)
            self.posts.append(request)
            self.count += 1
            action = request['action_id']
            if action.startswith('select:'):
                self.selected = sorted(self.selected + [int(action.split(':')[1])])
            elif action.startswith('deselect:'):
                self.selected.remove(int(action.split(':')[1]))
            self.closed = action == 'confirm' or not self.manual and len(self.selected) == self.maximum
            value = dict(schema_version=1, protocol='combat_card_choice_v1', status='accepted', choice_id='c'*64,
                         **request, attempted=self.count, accepted=self.count, reconciled=self.count-1)
        else:
            legal = [('deselect:' if i in self.selected else 'select:') + str(i) for i in range(3)
                     if i in self.selected or len(self.selected) < self.maximum]
            if len(self.selected) >= self.minimum and (self.manual or not self.selected):
                legal.append('confirm')
            value = dict(schema_version=1, protocol='combat_card_choice_v1', status='complete' if self.closed else 'ready',
                         choice_id='c'*64, decision_id=None if self.closed else format(self.count+1, '064x'), pile='discard',
                         min_select=self.minimum, max_select=self.maximum, manual_confirmation=self.manual,
                         candidates=None if self.closed else [dict(slot=i, key='STRIKE', upgrade_level=0,
                                      selected=i in self.selected, enabled=True) for i in range(3)],
                         selected_slots=list(self.selected), legal_actions=[] if self.closed else legal,
                         attempted=self.count, accepted=self.count, reconciled=self.count,
                         result='selection_verified' if self.closed else None)
        result = encoded(self.corrupt(value)); self.buffers.append(result); return result


class CombatHostTests(unittest.TestCase):
    def test_optional_zero_multiple_and_auto(self):
        for minimum, maximum, manual, provider, expected in [
            (0,2,True,host.minimum_select,0), (1,2,True,host.minimum_select,1),
            (0,2,True,host.first_select,2), (0,1,False,host.first_select,1),
            (2,2,False,host.first_select,2)]:
            with self.subTest(minimum=minimum, maximum=maximum, manual=manual, expected=expected):
                wire = ChoiceWire(minimum=minimum, maximum=maximum, manual=manual)
                result = host.run_choice(wire.request, provider=provider)
                self.assertEqual(result['status'], 'resolved', result)
                self.assertEqual(result['selected_count'], expected)
                self.assertEqual(result['accepted'], result['reconciled'])
                self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_deselect_and_frozen_provider(self):
        wire = ChoiceWire(); actions = iter(['select:0','deselect:0','select:2','confirm'])
        def provider(value):
            with self.assertRaises(TypeError): value['candidates'][0]['key'] = 'BAD'
            return next(actions)
        result = host.run_choice(wire.request, provider=provider)
        self.assertEqual((result['status'], result['selected_count'], result['reconciled']), ('resolved',1,4))

    def test_bad_receipts_never_retry_and_preserve_attempt(self):
        for key, replacement in [('accepted',True), ('choice_id','f'*64), ('action_id','confirm'), ('status','failed')]:
            wire = ChoiceWire()
            wire.corrupt = lambda v: dict(v, **{key:replacement}) if 'action_id' in v else v
            result = host.run_choice(wire.request)
            self.assertEqual((result['status'],result['attempted'],result['accepted'],len(wire.posts)), ('failed',1,0,1))
            self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_lost_receipt_and_bad_reconciliation_keep_counts(self):
        wire = ChoiceWire()
        def request(method, route, body):
            if method == 'POST':
                wire.posts.append(1); wire.buffers.append(body); raise OSError('lost receipt')
            return wire.request(method, route, body)
        result = host.run_choice(request)
        self.assertEqual((result['code'],result['attempted'],result['accepted']), ('transport_failure',1,0))
        self.assertEqual(len(wire.posts),1)
        self.assertTrue(all(not any(b) for b in wire.buffers))
        for key, replacement in [('choice_id','f'*64),('selected_slots',[2]),('max_select',3),('reconciled',0)]:
            wire = ChoiceWire()
            wire.corrupt = lambda v: dict(v, **{key:replacement}) if wire.count and 'action_id' not in v else v
            result = host.run_choice(wire.request)
            self.assertEqual((result['status'],result['attempted'],result['accepted'],result['reconciled']), ('failed',1,1,0))
            self.assertEqual(len(wire.posts),1)

    def test_bounds_provider_timeout_and_initial_cleanup(self):
        for provider in [lambda v: 'select:63', lambda v: 1]:
            wire = ChoiceWire(); result = host.run_choice(wire.request, provider=provider)
            self.assertEqual((result['code'],result['attempted']), ('illegal_choice_provider',0))
        wire = ChoiceWire(); initial = wire.request('GET',host.CHOICE_READ,None)
        result = host.run_choice(wire.request, initial=initial, clock=lambda: 1, deadline=1)
        self.assertEqual(result['code'],'choice_timeout'); self.assertFalse(any(initial))

    def test_combat_choice_resume_and_failure_accounting(self):
        for failure in [None, 'receipt', 'child', 'read']:
            wire = ChoiceWire(); core_posts = []; core_reads = 0; buffers = []
            def request(method, route, body):
                nonlocal core_reads
                if route in (host.CHOICE_READ,host.CHOICE_ACTION):
                    if failure == 'child' and method == 'POST': raise OSError('lost child receipt')
                    return wire.request(method,route,body)
                if method == 'POST':
                    core_posts.append(json.loads(body)); buffers.append(body)
                    if failure == 'receipt': raise OSError('lost core receipt')
                    v = dict(schema_version=1,status='accepted',mutation_state='queued',reason='accepted',**core_posts[-1])
                    result = encoded(v)
                else:
                    core_reads += 1
                    if core_reads == 1: result = bytearray(_FIXTURE_COMBAT)
                    elif failure == 'read': raise OSError('lost read')
                    elif not wire.closed: result = bytearray(host.probe._COMBAT_WAITING)
                    else: result = bytearray(b'{"schema_version":1,"status":"complete","decision_kind":"combat","actionable":false,"decision_id":null,"round":1,"player":{"hp":72,"max_hp":80,"block":0,"energy":2},"enemies":[],"hand":[],"legal_actions":[],"outcome":"victory"}')
                buffers.append(result); return result
            result = host.run_combat(request, sleep=lambda _: None)
            self.assertEqual(result['status'], 'resolved' if failure is None else 'failed',result)
            self.assertEqual(len(core_posts),1)
            self.assertEqual(result['attempted'],1)
            self.assertEqual(result['accepted'],0 if failure == 'receipt' else 1)
            self.assertEqual(result['reconciled'],1 if failure is None else 0)
            if failure == 'child':
                self.assertEqual((result['choices'][0]['attempted'],result['choices'][0]['accepted']), (1,0))
            self.assertTrue(all(not any(b) for b in buffers+wire.buffers))


if __name__ == '__main__': unittest.main()
