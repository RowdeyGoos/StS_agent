"""Full graph/client protocol, nested receipts and bounded failure cases."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).absolute().parents[1] / 'client'))
import agent_host as host
from game.agent.contracts import full as f


def graph(kind='combat', action='end_turn', count=1):
    options = tuple(f.Node('option', f'option_{i}', f'option:{i}') for i in range(count))
    decision = f.PublicDecision(f.SCHEMA, f.PROFILE,
        f.Node('run', 'run', fields=(f.Field('hp', 50), f.Field('max_hp', 80))),
        f.Node(kind, kind, children=options),
        tuple(f.Candidate(f'action:{i}', action, f'option:{i}') for i in range(count)))
    return f.to_dict(decision)


class FullWire:
    def __init__(self):
        self.frames = [graph(k, a) for k, a in (
            ('combat', 'end_turn'), ('rest', 'smith'), ('rest', 'choose_upgrade'),
            ('rest', 'confirm_selection'), ('rewards', 'claim_gold'), ('shop', 'open_shop'),
            ('map', 'choose_map_node'), ('event', 'choose_event_option'))]
        self.stage = self.attempted = self.accepted = self.reconciled = 0
        self.buffers = []; self.posts = []; self.corrupt = lambda x: x
        self.outcome = 'victory'; self.reconcile_on_post = False; self.stale = False

    def request(self, method, route, body):
        self.assert_route = route
        row = dict(schema_version=2, protocol='agent_v2', status='ready', decision_id=None,
                   action_id=None, observation=None, code=None, outcome=None)
        if method == 'POST':
            assert route == host.FULL_ACT
            self.buffers.append(body); action = json.loads(body); self.posts.append(action)
            self.attempted += 1
            if self.reconcile_on_post: self.reconciled = self.accepted
            if self.stale:
                self.stale = False
                row = dict(schema_version=2, protocol='agent_v2', status='rejected', mutation_state='none',
                           reason='stale_decision', **action)
            else:
                self.accepted += 1; self.stage += 1
                row.update(status='accepted', **action)
        else:
            assert route == host.FULL_READ
            # More than one parent may remain pending through nested choices.
            self.reconciled = max(self.reconciled, (0, 0, 0, 1)[self.stage] if self.stage < 4 else self.accepted)
            if self.stage == len(self.frames): row.update(status='complete', outcome=self.outcome)
            else: row.update(decision_id=format(self.stage + 1, '064x'), observation=self.frames[self.stage])
        row.update(attempted=self.attempted, accepted=self.accepted, reconciled=self.reconciled,
                   pending=self.accepted - self.reconciled)
        result = bytearray(json.dumps(self.corrupt(row)).encode()); self.buffers.append(result)
        return result


class FullAgentTests(unittest.TestCase):
    def test_failure_categories_are_closed_and_preserve_validated_counts(self):
        for category in (*sorted(host.FULL_FAILURE_CODES), 'private sentinel',
                         'read_native_event_private_sentinel', 'read_native_event_parent_travel\nsecret',
                         ['read_deck_failed'], None):
            with self.subTest(category=category):
                wire = FullWire()
                def failure(row):
                    if wire.stage == 2 and row['status'] == 'ready':
                        row.update(status='failed', code=category, observation=None, decision_id=None,
                                   reconciled=1, pending=1)
                    return row
                wire.corrupt = failure
                result = host.run_agent(wire.request, full=True)
                expected = category if type(category) is str and category in host.FULL_FAILURE_CODES else 'native_failure'
                self.assertEqual(result['code'], expected)
                self.assertEqual((result['attempted'], result['accepted'], result['reconciled'], result['pending']), (2, 2, 1, True))
                self.assertEqual(len(wire.posts), 2)
                self.assertNotIn('private sentinel', json.dumps(result))
                self.assertTrue(all(not any(buffer) for buffer in wire.buffers))

    def test_failure_diagnostic_does_not_accept_regressed_counts(self):
        wire = FullWire()
        def failure(row):
            if wire.stage == 2 and row['status'] == 'ready':
                row.update(status='failed', code='read_deck_failed', observation=None, decision_id=None,
                           attempted=1, accepted=1, reconciled=0, pending=1)
            return row
        wire.corrupt = failure
        result = host.run_agent(wire.request, full=True)
        self.assertEqual(result['code'], 'counts_regressed')
        self.assertEqual(len(wire.posts), 2)

    def test_controlled_map_stop_waits_for_all_owned_actions(self):
        wire = FullWire()
        result = host.run_agent(wire.request, full=True, stop_at_map=True)
        self.assertEqual((result['status'], result['accepted'], result['reconciled'], result['pending']), ('resolved', 6, 6, False), result)
        self.assertEqual(result['outcome']['kind'], 'truncated')
        self.assertEqual(result['outcome']['reason'], 'external_stop')
        self.assertEqual(len(wire.posts), 6)

    def test_shared_policy_all_contexts_and_nested_counts(self):
        for outcome in ('victory', 'defeat', 'run_abandoned'):
            wire = FullWire(); wire.outcome = outcome; seen = []
            def choose(public):
                self.assertIsInstance(public, f.PublicDecision)
                self.assertFalse(hasattr(public, 'decision_id'))
                seen.append(public.context.kind)
                return host.choose_full_action(public)
            result = host.run_agent(wire.request, full=True, policy=choose, sleep=lambda _: None)
            self.assertEqual((result['status'], result['accepted'], result['reconciled'], result['pending']), ('resolved', 8, 8, False), result)
            self.assertEqual(result['outcome']['kind'], 'abandoned' if outcome == 'run_abandoned' else outcome)
            self.assertEqual(result['outcome']['reason'], 'none')
            self.assertEqual(set(seen), {'combat', 'rest', 'rewards', 'shop', 'map', 'event'})
            self.assertTrue(all(not any(buffer) for buffer in wire.buffers))

    def test_revalidation_can_settle_previous_actions_before_receipt(self):
        for stale in (False, True):
            wire = FullWire(); adapter = host.LiveAdapter(wire.request, full=True)
            first = adapter.observe(); self.assertEqual(adapter.step(first.binding, 'action:0').status, 'pending')
            child = adapter.observe(); self.assertTrue(adapter.pending)
            wire.reconcile_on_post = True; wire.stale = stale
            report = adapter.step(child.binding, 'action:0')
            self.assertEqual(report.status, 'rejected' if stale else 'pending')
            self.assertEqual(adapter.counts[2], 1)
            self.assertEqual(adapter.pending, not stale)
            self.assertEqual(adapter.step(child.binding, 'action:0').reason, 'stale_decision')
            self.assertEqual(len(wire.posts), 2)

    def test_slot_capacity_and_private_or_malformed_graph_stop_before_input(self):
        for count in (2048, 2049):
            wire = FullWire(); wire.frames[0] = graph('event', 'choose_event_option', count)
            adapter = host.LiveAdapter(wire.request, full=True)
            if count == 2048:
                frame = adapter.observe()
                self.assertEqual(adapter.step(frame.binding, 'action:2047').status, 'pending')
            else:
                with self.assertRaises(host.AgentFailure): adapter.observe()
                self.assertEqual(wire.posts, [])
        for field in ('seed', 'rng', 'decision_id'):
            wire = FullWire(); wire.frames[0][field] = 'private'
            result = host.run_agent(wire.request, full=True)
            self.assertEqual(result['status'], 'failed'); self.assertEqual(wire.posts, [])

    def test_invalid_receipts_and_lost_transport_never_retry(self):
        for field, value in (('accepted', True), ('pending', 0), ('reconciled', 1), ('decision_id', 'f' * 64), ('action_id', 'action:1')):
            wire = FullWire()
            wire.corrupt = lambda row: dict(row, **{field: value}) if row['status'] == 'accepted' else row
            result = host.run_agent(wire.request, full=True)
            self.assertEqual((result['status'], len(wire.posts), result['pending']), ('failed', 1, True), result)
        wire = FullWire()
        def lost(method, route, body):
            if method == 'POST':
                wire.posts.append(1); wire.buffers.append(body); raise ConnectionError()
            return wire.request(method, route, body)
        result = host.run_agent(lost, full=True)
        self.assertEqual((result['status'], len(wire.posts), result['pending']), ('failed', 1, True))
        self.assertTrue(all(not any(buffer) for buffer in wire.buffers))


if __name__ == '__main__': unittest.main()
