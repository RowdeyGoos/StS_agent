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


def revive_decision(*, down, round_number=5, identity='a'):
    value = json.loads(_FIXTURE_COMBAT)
    value.update(round=round_number, decision_id=identity*64)
    value['enemies'] = ([] if down else [dict(index=0, id='TEST_SUBJECT', hp=150,
        max_hp=150, block=0, intents=['buff'])])
    value['hand'] = value['hand'][:1]
    value['hand'][0]['playable'] = not down
    value['legal_actions'] = [dict(action_id='end_turn', kind='end_turn', hand_index=None, target_index=None)]
    if not down:
        value['legal_actions'].insert(0, dict(action_id='play:0:0', kind='play_card', hand_index=0, target_index=0))
    return value


class ChoiceWire:
    def __init__(self, *, minimum=0, maximum=2, manual=True, version=1, pile='discard'):
        self.minimum, self.maximum, self.manual = minimum, maximum, manual
        self.version, self.pile = version, pile
        self.selected = []
        self.count = 0
        self.closed = False
        self.buffers = []
        self.posts = []
        self.corrupt = lambda value: value

    def request(self, method, route, body):
        assert route == f'/probe/combat-choice-v{self.version}/public/' + ('action' if method == 'POST' else 'decision')
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
            value = dict(schema_version=1, protocol=f'combat_card_choice_v{self.version}', status='accepted', choice_id='c'*64,
                         **request, attempted=self.count, accepted=self.count, reconciled=self.count-1)
        else:
            legal = [('deselect:' if i in self.selected else 'select:') + str(i) for i in range(3)
                     if i in self.selected or len(self.selected) < self.maximum]
            if len(self.selected) >= self.minimum and (self.manual or not self.selected):
                legal.append('confirm')
            value = dict(schema_version=1, protocol=f'combat_card_choice_v{self.version}', status='complete' if self.closed else 'ready',
                         choice_id='c'*64, decision_id=None if self.closed else format(self.count+1, '064x'), pile=self.pile,
                         min_select=self.minimum, max_select=self.maximum, manual_confirmation=self.manual,
                         candidates=None if self.closed else [dict(slot=i, key='STRIKE', upgrade_level=0,
                                      selected=i in self.selected, enabled=True) for i in range(3)],
                         selected_slots=list(self.selected), legal_actions=[] if self.closed else legal,
                         attempted=self.count, accepted=self.count, reconciled=self.count,
                         result='selection_verified' if self.closed else None)
        result = encoded(self.corrupt(value)); self.buffers.append(result); return result


class CombatHostTests(unittest.TestCase):
    def test_v3_offer_selection_and_old_version_rejection(self):
        for version in (1, 2, 3):
            wire = ChoiceWire(minimum=1, maximum=1, manual=False, version=version, pile='offer')
            result = host.run_choice(wire.request, version=version)
            self.assertEqual(result['status'], 'resolved' if version == 3 else 'failed')
            self.assertEqual(len(wire.posts), 1 if version == 3 else 0)
            if version == 3:
                self.assertEqual((result['attempted'], result['accepted'], result['reconciled']), (1, 1, 1))

    def test_v3_rejects_optional_or_multiple_or_confirmable_offers(self):
        for minimum, maximum, manual in ((0,1,False), (1,2,False), (1,1,True)):
            wire = ChoiceWire(minimum=minimum, maximum=maximum, manual=manual, version=3, pile='offer')
            self.assertEqual(host.run_choice(wire.request, version=3)['status'], 'failed')
            self.assertEqual(wire.posts, [])
        wire = ChoiceWire(minimum=1, maximum=1, manual=False, version=3, pile='offer')
        wire.corrupt = lambda value: dict(value, legal_actions=value['legal_actions'] + ['confirm'])
        self.assertEqual(host.run_choice(wire.request, version=3)['status'], 'failed')
        self.assertEqual(wire.posts, [])

    def test_v3_rejects_protocol_downgrade_before_another_input(self):
        wire = ChoiceWire(minimum=1, maximum=1, manual=False, version=3, pile='offer')
        wire.corrupt = lambda value: dict(value, protocol='combat_card_choice_v2') if value['status'] == 'complete' else value
        result = host.run_choice(wire.request, version=3)
        self.assertEqual((result['status'], result['attempted'], result['accepted'], result['reconciled']), ('failed',1,1,0))
        self.assertEqual(len(wire.posts), 1)

    def test_campaign_two_revives_remain_combat_until_native_terminal(self):
        states = [revive_decision(down=down, round_number=turn, identity=identity)
                  for down, turn, identity in [(False,5,'a'), (True,5,'b'), (False,6,'c'),
                                                (True,6,'d'), (False,7,'e')]]
        states.append(dict(schema_version=1, status='complete', decision_kind='combat', actionable=False,
            decision_id=None, round=7, player=states[-1]['player'], enemies=[], hand=[], legal_actions=[], outcome='victory'))
        posts, buffers = [], []
        def request(method, route, body):
            if method == 'POST':
                self.assertEqual(route, host.COMBAT_ACTION)
                command = json.loads(body); buffers.append(body)
                expected = states[len(posts)]
                self.assertEqual(command['decision_id'], expected['decision_id'])
                self.assertIn(command['action_id'], [a['action_id'] for a in expected['legal_actions']])
                posts.append(command)
                value = dict(schema_version=1, status='accepted', mutation_state='queued', reason='accepted', **command)
            else:
                self.assertEqual(route, host.COMBAT_READ)
                value = states[len(posts)]
            response = encoded(value); buffers.append(response); return response
        result = host.run_combat(request, campaign=True, sleep=lambda _: None)
        self.assertEqual((result['status'], result['outcome'], result['attempted'], result['accepted'], result['reconciled']),
                         ('resolved', 'victory', 5, 5, 5), result)
        self.assertEqual([p['action_id'] for p in posts], ['play:0:0', 'end_turn', 'play:0:0', 'end_turn', 'play:0:0'])
        self.assertEqual(result['reads'], 6)
        self.assertTrue(all(not any(b) for b in buffers))

    def test_empty_enemy_campaign_rejects_malformed_actions_and_preserves_standalone_profile(self):
        for case in ('standalone', 'phantom_target', 'missing_end_turn', 'duplicate_end_turn', 'invalid_enemies', 'overflow'):
            with self.subTest(case=case):
                value = revive_decision(down=True)
                if case == 'phantom_target':
                    value['hand'][0]['playable'] = True
                    value['legal_actions'].insert(0, dict(action_id='play:0:0', kind='play_card', hand_index=0, target_index=0))
                elif case == 'missing_end_turn': value['legal_actions'] = []
                elif case == 'duplicate_end_turn': value['legal_actions'] *= 2
                elif case == 'invalid_enemies': value['enemies'] = None
                elif case == 'overflow':
                    enemy = revive_decision(down=False)['enemies'][0]
                    value['enemies'] = [dict(enemy, index=i) for i in range(7)]
                buffers, methods = [], []
                def request(method, route, body):
                    methods.append(method)
                    self.assertEqual(method, 'GET')
                    response = encoded(value); buffers.append(response); return response
                result = host.run_combat(request, campaign=case != 'standalone', sleep=lambda _: None)
                self.assertEqual((result['code'], result['attempted'], result['accepted'], result['reconciled']),
                                 ('invalid_response', 0, 0, 0), result)
                self.assertIsNone(result['outcome'])
                self.assertEqual(methods, ['GET'])
                self.assertTrue(all(not any(b) for b in buffers))

    def test_empty_enemy_end_turn_failure_never_retries_or_infers_victory(self):
        for failure in ('receipt', 'reconciliation'):
            with self.subTest(failure=failure):
                posts, buffers = [], []
                def request(method, route, body):
                    if method == 'POST':
                        command = json.loads(body); posts.append(command); buffers.append(body)
                        self.assertEqual(command['action_id'], 'end_turn')
                        if failure == 'receipt': raise OSError('lost receipt')
                        value = dict(schema_version=1, status='accepted', mutation_state='queued', reason='accepted', **command)
                    elif posts: raise OSError('lost reconciliation')
                    else: value = revive_decision(down=True)
                    response = encoded(value); buffers.append(response); return response
                result = host.run_combat(request, campaign=True, sleep=lambda _: None)
                self.assertEqual((result['code'], result['attempted'], result['accepted'], result['reconciled']),
                                 ('transport_failure', 1, 0 if failure == 'receipt' else 1, 0), result)
                self.assertIsNone(result['outcome'])
                self.assertEqual(len(posts), 1)
                self.assertTrue(all(not any(b) for b in buffers))

    def test_late_complete_choice_observation_keeps_reconciliation_but_stops(self):
        now = [0.]
        wire = ChoiceWire(minimum=1, maximum=1, manual=False, version=2, pile='draw')
        def request(method, route, body):
            result = wire.request(method, route, body)
            if method == 'GET' and wire.closed: now[0] = 30.
            return result
        result = host.run_choice(request, version=2, clock=lambda: now[0])
        self.assertEqual((result['code'], result['attempted'], result['accepted'], result['reconciled'], result['selected_count']),
                         ('choice_timeout', 1, 1, 1, 1))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(wire.posts), 1)
        self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_episode_cap_admission_failure_does_not_inherit_previous_child_counts(self):
        buffer = encoded(dict(schema_version=1, protocol='combat_card_choice_v2', status='failed',
                              code='choice_limit', choice_id='c'*64, attempted=3, accepted=3, reconciled=3))
        calls = []
        def request(method, route, body):
            calls.append(method)
            return buffer
        result = host.run_choice(request, version=2)
        self.assertEqual((result['native_code'], result['attempted'], result['accepted'], result['reconciled']),
                         ('choice_limit', 0, 0, 0))
        self.assertEqual(calls, ['GET'])
        self.assertFalse(any(buffer))

    def test_late_accepted_choice_receipt_keeps_acceptance_without_retry(self):
        now = [0.]
        wire = ChoiceWire(version=2, pile='draw')
        def request(method, route, body):
            result = wire.request(method, route, body)
            if method == 'POST': now[0] = 30.
            return result
        result = host.run_choice(request, version=2, clock=lambda: now[0])
        self.assertEqual((result['code'], result['attempted'], result['accepted'], result['reconciled']),
                         ('choice_timeout', 1, 1, 0))
        self.assertEqual(len(wire.posts), 1)
        self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_failed_choice_post_preserves_native_code_without_inventing_acceptance(self):
        wire = ChoiceWire(version=2, pile='draw')
        wire.corrupt = lambda value: (dict(schema_version=1, protocol='combat_card_choice_v2', status='failed',
            code='uncertain_choice', choice_id='c'*64, attempted=1, accepted=0, reconciled=0)
            if 'action_id' in value else value)
        result = host.run_choice(wire.request, version=2)
        self.assertEqual((result['code'], result['native_code'], result['attempted'], result['accepted'], result['reconciled']),
                         ('native_choice_failed', 'uncertain_choice', 1, 0, 0))
        self.assertEqual(len(wire.posts), 1)
        self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_v2_draw_automatic_choice_and_v1_rejection(self):
        for version in (1, 2):
            wire = ChoiceWire(minimum=1, maximum=1, manual=False, version=version, pile='draw')
            result = host.run_choice(wire.request, version=version)
            self.assertEqual(result['status'], 'resolved' if version == 2 else 'failed', result)
            self.assertEqual(len(wire.posts), 1 if version == 2 else 0)
            if version == 2:
                self.assertEqual((result['pile'], result['reconciled']), ('draw', 1))
            self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_native_failure_is_bounded_and_preserves_pending_counts(self):
        wire = ChoiceWire(version=2, pile='draw')
        def corrupt(value):
            if wire.count and 'action_id' not in value:
                return dict(schema_version=1, protocol='combat_card_choice_v2', status='failed',
                            code='choice_identity_changed', choice_id='c'*64, attempted=1, accepted=1, reconciled=0)
            return value
        wire.corrupt = corrupt
        result = host.run_choice(wire.request, version=2)
        self.assertEqual((result['code'], result['native_code'], result['attempted'], result['accepted'], result['reconciled']),
                         ('native_choice_failed', 'choice_identity_changed', 1, 1, 0))
        self.assertEqual(len(wire.posts), 1)
        for code in ('native secret detail', True, None):
            buffer = encoded(dict(schema_version=1, protocol='combat_card_choice_v2', status='failed',
                                  code=code, choice_id=None, attempted=0, accepted=0, reconciled=0))
            result = host.run_choice(lambda *a: buffer, version=2)
            self.assertEqual((result['code'], result['native_code']), ('invalid_choice_failure', None))
            self.assertFalse(any(buffer))

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

    def test_end_turn_waits_for_round_advance_and_services_chooser(self):
        for provider, expected in [(host.minimum_select, 0), (host.first_select, 2)]:
            wire = ChoiceWire(); posts = []; reads = 0; buffers = []
            def ready(round_number, identity):
                v = json.loads(_FIXTURE_COMBAT)
                v.update(round=round_number, decision_id=identity*64, hand=[],
                         legal_actions=[dict(action_id='end_turn',kind='end_turn',hand_index=None,target_index=None)])
                v['player']['energy'] = 0
                return encoded(v)
            def request(method, route, body):
                nonlocal reads
                if route in (host.CHOICE_READ, host.CHOICE_ACTION):
                    return wire.request(method, route, body)
                if method == 'POST':
                    posts.append((reads, json.loads(body))); buffers.append(body)
                    result = encoded(dict(schema_version=1,status='accepted',mutation_state='queued',reason='accepted',**posts[-1][1]))
                else:
                    reads += 1
                    if reads == 1: result = ready(5, 'a')
                    elif not wire.closed: result = ready(5, 'b')  # Changed snapshot; queued end-turn not complete.
                    elif len(posts) == 1: result = ready(6, 'c')
                    else:
                        result = encoded(dict(schema_version=1,status='complete',decision_kind='combat',actionable=False,
                                              decision_id=None,round=7,player=dict(hp=72,max_hp=80,block=0,energy=0),
                                              enemies=[],hand=[],legal_actions=[],outcome='victory'))
                buffers.append(result); return result
            result = host.run_combat(request, choice_provider=provider, sleep=lambda _: None)
            self.assertEqual((result['status'],result['attempted'],result['accepted'],result['reconciled']), ('resolved',2,2,2), result)
            self.assertEqual(result['choices'][0]['selected_count'], expected)
            self.assertEqual([p['decision_id'] for _,p in posts], ['a'*64,'c'*64])
            self.assertTrue(all(not any(b) for b in buffers+wire.buffers))

    def test_end_turn_same_round_is_bounded_without_redispatch(self):
        now = [0.0]; posts = []; buffers = []
        def request(method, route, body):
            if method == 'POST':
                posts.append(json.loads(body)); buffers.append(body)
                result = encoded(dict(schema_version=1,status='accepted',mutation_state='queued',reason='accepted',**posts[-1]))
            elif route == host.CHOICE_READ:
                result = encoded(dict(schema_version=1,protocol='combat_card_choice_v1',status='waiting',choice_id=None,
                                      decision_id=None,pile=None,min_select=0,max_select=0,manual_confirmation=False,
                                      candidates=None,selected_slots=[],legal_actions=[],attempted=0,accepted=0,reconciled=0,result=None))
            else:
                v = json.loads(_FIXTURE_COMBAT)
                v.update(hand=[],decision_id=('b' if posts else 'a')*64,
                         legal_actions=[dict(action_id='end_turn',kind='end_turn',hand_index=None,target_index=None)])
                result = encoded(v)
            buffers.append(result); return result
        result = host.run_combat(request,clock=lambda:now[0],sleep=lambda _:now.__setitem__(0,now[0]+100))
        self.assertEqual((result['code'],result['attempted'],result['accepted'],result['reconciled']), ('combat_timeout',1,1,0), result)
        self.assertEqual(len(posts),1)
        self.assertTrue(all(not any(b) for b in buffers))

    def test_owned_resume_reconciles_pending_training_action_without_victory(self):
        for mode in ['resume', 'stale', 'wrong_nonce', 'fault', 'timeout']:
            probes = []; posts = []; buffers = []; now = [0.0]
            def request(method, route, body):
                if route == host.EVENT_COMBAT_READ:
                    probes.append(route)
                    status = 'combat' if len(probes) == 1 else 'waiting' if mode == 'timeout' else 'resumed'
                    result = encoded(dict(schema_version=1, protocol='event_combat_v2',
                        session_nonce='b'*32 if mode == 'wrong_nonce' else 'a'*32, status='unsupported' if mode == 'fault' else status))
                elif method == 'POST':
                    posts.append(json.loads(body)); buffers.append(body)
                    result = encoded(dict(schema_version=1, status='rejected' if mode == 'stale' else 'accepted',
                        mutation_state='none' if mode == 'stale' else 'queued', reason='stale_decision' if mode == 'stale' else 'accepted', **posts[-1]))
                else:
                    self.assertEqual(route, host.COMBAT_READ)
                    result = bytearray(_FIXTURE_COMBAT)
                buffers.append(result); return result
            result = host.run_combat(request, event_resume_nonce='a'*32,clock=lambda:now[0],sleep=lambda _:now.__setitem__(0,now[0]+100))
            if mode in ['resume', 'stale']:
                self.assertEqual((result['status'], result['outcome'], result['accepted'], result['reconciled']),
                    ('resolved', 'event_resumed', 0 if mode == 'stale' else 1, 0 if mode == 'stale' else 1), result)
                self.assertIsNone(result['native_terminal_outcome'])
            else:
                self.assertEqual(result['code'], 'combat_timeout' if mode == 'timeout' else 'invalid_event_resume', result)
            self.assertEqual(len(posts), 0 if mode in ['wrong_nonce', 'fault'] else 1)
            self.assertTrue(all(not any(b) for b in buffers))

    def test_unexpected_rounds_remain_terminal(self):
        for end_turn, following in [(True,4),(True,7),(False,4),(False,6)]:
            posts = []; reads = 0
            def request(method, route, body):
                nonlocal reads
                if method == 'POST':
                    posts.append(json.loads(body))
                    return encoded(dict(schema_version=1,status='accepted',mutation_state='queued',reason='accepted',**posts[-1]))
                self.assertEqual(route,host.COMBAT_READ)
                reads += 1; v = json.loads(_FIXTURE_COMBAT)
                v.update(round=5 if reads==1 else following,decision_id=('a' if reads==1 else 'b')*64)
                if end_turn:
                    v.update(hand=[],legal_actions=[dict(action_id='end_turn',kind='end_turn',hand_index=None,target_index=None)])
                return encoded(v)
            result = host.run_combat(request,sleep=lambda _:None)
            self.assertEqual((result['code'],result['attempted'],result['accepted'],result['reconciled']), ('unexpected_combat_round',1,1,0),result)
            self.assertEqual(len(posts),1)


class CampaignPolicyTests(unittest.TestCase):
    def assert_dispatch(self, value, expected, *, campaign=True):
        posts, buffers = [], []
        def request(method, route, body):
            if method == 'POST':
                self.assertEqual(route, host.COMBAT_ACTION)
                posts.append(json.loads(body)); buffers.append(body)
                self.assertEqual(posts[-1]['decision_id'], value['decision_id'])
                self.assertIn(posts[-1]['action_id'], [a['action_id'] for a in value['legal_actions']])
                response = dict(schema_version=1, status='accepted', mutation_state='queued', reason='accepted', **posts[-1])
            elif posts:
                self.assertEqual(route, host.COMBAT_READ)
                response = dict(schema_version=1, status='complete', decision_kind='combat', actionable=False,
                    decision_id=None, round=1, player=value['player'], enemies=[], hand=[], legal_actions=[], outcome='victory')
            else:
                self.assertEqual(route, host.COMBAT_READ)
                response = value
            buffer = encoded(response); buffers.append(buffer); return buffer
        result = host.run_combat(request, campaign=campaign, sleep=lambda _: None)
        self.assertEqual((result['status'], result['attempted'], result['accepted'], result['reconciled']),
                         ('resolved', 1, 1, 1), result)
        self.assertEqual([p['action_id'] for p in posts], [expected])
        self.assertTrue(all(not any(b) for b in buffers))

    def obscura_decision(self, summoner_index=1):
        value = json.loads(_FIXTURE_COMBAT)
        value['enemies'] = [dict(index=i, id='THE_OBSCURA' if i == summoner_index else 'PARAFRIGHT',
            hp=71 if i == summoner_index else 6, max_hp=123 if i == summoner_index else 21,
            block=0, intents=['buff']) for i in range(2)]
        value['legal_actions'].insert(1, dict(action_id='play:0:1', kind='play_card', hand_index=0, target_index=1))
        return value

    def test_obscura_target_priority_uses_current_indexes_and_campaign_only(self):
        for campaign in (False, True):
            for summoner_index in (0, 1):
                with self.subTest(campaign=campaign, summoner_index=summoner_index):
                    value = self.obscura_decision(summoner_index)
                    value['legal_actions'].reverse()
                    target = summoner_index if campaign else 1 - summoner_index
                    self.assert_dispatch(value, f'play:0:{target}', campaign=campaign)

    def test_unavailable_summoner_target_keeps_same_card_and_legal_fallback(self):
        for case in ('absent', 'dead', 'unadvertised', 'different_card', 'unknown_summoner', 'unknown_minion'):
            with self.subTest(case=case):
                value = self.obscura_decision()
                if case in ('absent', 'dead', 'unadvertised', 'different_card'):
                    value['legal_actions'] = [a for a in value['legal_actions'] if a['target_index'] != 1]
                if case == 'absent':
                    value['enemies'].pop()
                elif case == 'dead':
                    value['enemies'][1]['hp'] = 0
                elif case == 'different_card':
                    value['hand'].append(dict(hand_index=2, id='BREAK', type='attack', cost='1', target_type='enemy', playable=True))
                    value['legal_actions'].append(dict(action_id='play:2:1', kind='play_card', hand_index=2, target_index=1))
                elif case == 'unknown_summoner':
                    value['enemies'][1]['id'] = 'OTHER_ENEMY'
                elif case == 'unknown_minion':
                    value['enemies'][0]['id'] = 'OTHER_ENEMY'
                self.assert_dispatch(value, 'play:0:0')

    def test_non_targeted_recommendations_are_preserved(self):
        for case, expected in (('self', 'play:1'), ('all_enemies', 'play:0'), ('end_turn', 'end_turn')):
            with self.subTest(case=case):
                value = self.obscura_decision()
                if case == 'self':
                    value['enemies'][0]['intents'] = ['attack']
                elif case == 'all_enemies':
                    value['hand'][0].update(id='CLEAVE', target_type='all_enemies')
                    value['legal_actions'] = [a for a in value['legal_actions'] if a['hand_index'] != 0]
                    value['legal_actions'].append(dict(action_id='play:0', kind='play_card', hand_index=0, target_index=None))
                else:
                    value['hand'] = []
                    value['legal_actions'] = [a for a in value['legal_actions'] if a['kind'] == 'end_turn']
                self.assert_dispatch(value, expected)

    def test_frantic_escape_precedes_summoner_target_priority(self):
        value = self.obscura_decision()
        value['hand'].append(dict(hand_index=2, id='FRANTIC_ESCAPE', type='status', cost='1', target_type='self', playable=True))
        value['legal_actions'].append(dict(action_id='play:2', kind='play_card', hand_index=2, target_index=None))
        self.assert_dispatch(value, 'play:2')

    def test_frantic_escape_priority_uses_only_native_legal_actions(self):
        for campaign in (False, True):
            for legal in (False, True):
                for attacking in (False, True):
                    with self.subTest(campaign=campaign, legal=legal, attacking=attacking):
                        value = json.loads(_FIXTURE_COMBAT)
                        value['enemies'][0].update(id='THE_INSATIABLE', intents=['attack'] if attacking else ['buff'])
                        value['hand'].append(dict(hand_index=2, id='FRANTIC_ESCAPE', type='status', cost='1', target_type='self', playable=legal))
                        if legal:
                            value['legal_actions'].append(dict(action_id='play:2', kind='play_card', hand_index=2, target_index=None))
                        expected = 'play:2' if campaign and legal else 'play:1' if attacking else 'play:0:0'
                        self.assert_dispatch(value, expected, campaign=campaign)


if __name__ == '__main__': unittest.main()
