"""Shared-policy protocol and adversarial dispatch/reconciliation fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).absolute().parents[1] / 'client'))
import agent_host as host


def frames():
    values = json.loads(Path(__file__).with_name('agent_pair.json').read_text())['decisions']
    # Candidate indexes are transport bindings, so assign contiguous slots here.
    for value in values:
        for i, candidate in enumerate(value['candidates']):
            candidate['ref'] = f'action:{i}'
    empty = dict(status='not_applicable', value=None)
    gold = dict(ref='reward:0', kind='gold', presentation='summary', amount=dict(status='known', value=12),
                cards=empty, potion=empty, relic=empty, resolved=False)
    card = dict(ref='reward:1', kind='card', presentation='summary', amount=empty,
                cards=empty, potion=empty, relic=empty, resolved=False)
    def reward(entries, actions):
        result = deepcopy(values[0])
        result['context'] = dict(kind='rewards', entries=deepcopy(entries))
        result['candidates'] = [dict(ref=f'action:{i}', kind=k, subject=s, target=t)
                                for i, (k, s, t) in enumerate(actions)]
        return result
    parent = reward([gold, card], [('claim_reward','reward:0',None), ('open_card_reward','reward:1',None), ('leave_rewards',None,None)])
    no_gold = reward([card], [('open_card_reward','reward:1',None), ('leave_rewards',None,None)])
    offer = deepcopy(values[0]['run']['deck']['value'][0]); offer['ref'] = 'card:99'
    opened = dict(card, presentation='choice', cards=dict(status='known', value=[offer]))
    child = reward([opened], [('choose_reward_card','reward:1','card:99'), ('skip_reward','reward:1',None)])
    resolved = reward([], [('leave_rewards',None,None)])
    map_view = deepcopy(values[0]); target = map_view['run']['map']['value']['nodes'][-1]['ref']
    map_view['context'] = dict(kind='map', reachable=[target])
    map_view['candidates'] = [dict(ref='action:0', kind='choose_map_node', subject=target, target=None)]
    return values + [parent, no_gold, child, resolved, map_view]


class Wire:
    def __init__(self):
        self.frames = frames(); self.stage = self.attempted = self.accepted = self.reconciled = 0
        self.wait = False; self.buffers = []; self.posts = []; self.corrupt = lambda x: x; self.stale = 0

    def request(self, method, route, body):
        value = dict(schema_version=1, protocol='agent_v1', status='waiting', decision_id=None,
                     action_id=None, observation=None, code=None, outcome=None, parent_pending=False, child_pending=False)
        if method == 'POST':
            assert route == host.ACT
            self.buffers.append(body); action = json.loads(body); self.posts.append(action)
            self.attempted += 1
            if self.stale:
                self.stale -= 1
                value = dict(schema_version=1, protocol='agent_v1', status='rejected', mutation_state='none',
                             reason='stale_decision', **action)
            else:
                self.accepted += 1; self.stage += 1; self.wait = True
                value.update(status='accepted', parent_pending=True, child_pending=2 <= self.stage <= 4, **action)
        elif self.wait:
            self.wait = False
            value.update(parent_pending=True, child_pending=2 <= self.stage <= 4)
        elif self.stage == len(self.frames):
            self.reconciled = self.accepted
            value.update(status='complete', outcome='slice_complete')
        else:
            self.reconciled = self.accepted - int(1 <= self.stage <= 3)
            value.update(status='ready', decision_id=format(self.stage+1, '064x'), observation=self.frames[self.stage],
                         parent_pending=1 <= self.stage <= 3)
        value.update(attempted=self.attempted, accepted=self.accepted, reconciled=self.reconciled)
        result = bytearray(json.dumps(self.corrupt(value)).encode()); self.buffers.append(result)
        return result


class AgentTests(unittest.TestCase):
    def test_same_public_only_chooser_through_nested_slice_and_map_dispatch(self):
        for dispatch in (False, True):
            wire = Wire(); received = []
            def choose(public):
                self.assertIsInstance(public, host.c.PublicDecision)
                self.assertFalse(hasattr(public, 'decision_id'))
                received.append(public)
                return host.choose_action(public)
            result = host.run_agent(wire.request, policy=choose, dispatch_map=dispatch, sleep=lambda _: None)
            self.assertEqual(result['status'], 'resolved', result)
            self.assertEqual(result['accepted'], result['reconciled'])
            self.assertFalse(result['pending'])
            self.assertEqual(set(result['decision_kinds']), {'combat','card_selection','rewards','map'})
            self.assertEqual(result['outcome']['reason'], 'slice_complete')
            self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_stale_no_mutation_reobserve_is_bounded(self):
        for count in (1, 4):
            wire = Wire(); wire.stale = count
            result = host.run_agent(wire.request, sleep=lambda _: None)
            self.assertEqual(result['status'], 'resolved' if count == 1 else 'failed', result)
            if count == 4:
                self.assertEqual(result['accepted'], 0)
                self.assertEqual(len(wire.posts), 4)

    def test_uncertain_receipts_never_retry(self):
        for error in (ConnectionError(), KeyboardInterrupt()):
            wire = Wire()
            def request(method, route, body):
                if method == 'POST':
                    wire.posts.append(1); wire.buffers.append(body); raise error
                return wire.request(method, route, body)
            result = host.run_agent(request, sleep=lambda _: None)
            self.assertEqual((result['status'],result['attempted'],result['accepted'],len(wire.posts)), ('failed',1,0,1))
            self.assertTrue(result['pending'], result)
            self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_invalid_accepted_receipts_cannot_claim_acceptance(self):
        for field, value in (('accepted',True), ('decision_id','f'*64), ('action_id','action:99'), ('protocol','agent_v2')):
            wire = Wire(); wire.corrupt = lambda row: dict(row, **{field:value}) if row['status']=='accepted' else row
            result = host.run_agent(wire.request, sleep=lambda _: None)
            self.assertEqual((result['status'],result['accepted'],len(wire.posts)), ('failed',0,1), result)
            self.assertTrue(result['pending'])

    def test_changed_version_missing_fields_and_private_fields_stop_before_post(self):
        for change in ('version','missing','private','unknown','duplicate'):
            wire = Wire()
            def corrupt(row):
                row = deepcopy(row)
                if change == 'version': row['protocol'] = 'agent_v2'
                if change == 'missing': del row['observation']['run']['gold']
                if change == 'private': row['observation']['seed'] = 999
                if change == 'unknown': row['observation']['run']['deck'] = dict(status='unknown',value=None)
                if change == 'duplicate': row['observation']['candidates'][1]['ref'] = row['observation']['candidates'][0]['ref']
                return row
            wire.corrupt = corrupt
            result = host.run_agent(wire.request, sleep=lambda _: None)
            self.assertEqual(result['status'],'failed')
            self.assertEqual(wire.posts,[])

    def test_reconciliation_failure_and_cleanup_failure_keep_parent_pending(self):
        for change in ('counts','failed'):
            wire = Wire()
            def corrupt(row):
                if wire.stage == 1 and row['status']=='ready':
                    if change == 'counts': return dict(row, reconciled=row['accepted'])
                    return dict(row, status='failed', code='cleanup_failure', observation=None, decision_id=None)
                return row
            wire.corrupt = corrupt
            result = host.run_agent(wire.request, sleep=lambda _: None)
            self.assertEqual(result['status'],'failed')
            self.assertEqual(len(wire.posts),1)
            self.assertTrue(result['pending'])

    def test_local_invalid_or_stale_binding_never_dispatches(self):
        wire = Wire(); adapter = host.LiveAdapter(wire.request); frame = adapter.observe()
        self.assertEqual(adapter.step(object(),'action:0').reason, 'stale_decision')
        self.assertEqual(adapter.step(frame.binding,'action:999').reason, 'invalid_action')
        self.assertEqual(wire.posts,[])


if __name__ == '__main__':
    unittest.main()
