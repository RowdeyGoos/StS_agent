import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('rest_interactive_host', Path(__file__).resolve().parents[2] / 'host/rest_interactive_host.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def value(status, phase, **fields):
    return dict(schema_version=3, capability='rest_v3', session_nonce='a' * 32,
                status=status, phase=phase, completed=[], **fields)


def ident(i):
    return f'{i:064x}'


def completion(i, action, result='reconciled'):
    return dict(decision_id=ident(i), action_id=action, result=result)


def option(kind):
    return value('ready', 'option', decision_id=ident(1), parent_action=None,
                 legal_actions=['option:' + kind], cards=[],
                 options=[dict(kind=kind, enabled=True, counter=0, amount=0)])


def selection(kind, selected=(), maximum=1):
    cards = [dict(slot=i, key='CARD_' + str(i), upgrade=0, selected=i in selected) for i in range(3)]
    actions = [('deselect:' if c['selected'] else 'select:') + str(i) for i, c in enumerate(cards)
               if c['selected'] or len(selected) < maximum]
    return value('ready', 'selection', decision_id=ident(2), parent_action='option:' + kind,
                 cards=cards, minimum=maximum, maximum=maximum, cancelable=True,
                 legal_actions=actions + (['confirm'] if len(selected) == maximum else []) + ['cancel'])


def reward(opened=False, skipped=False):
    return value('ready', 'rewards', decision_id=ident(2), parent_action='option:heal',
                 screen_kind='card_reward' if opened else 'rewards',
                 rewards=[dict(slot=0, kind='card', key=None, selected=False,
                               cards=['BASH', 'STRIKE_IRONCLAD'] if opened else [])],
                 legal_actions=['reward:choose:0', 'reward:choose:1', 'reward:skip_card'] if opened else
                               ['reward:dismiss'] if skipped else ['reward:open:0', 'reward:dismiss'])


def script(kind, children=(), cancelled=False):
    """Parent remains pending; only the final continuation settles it."""
    steps = [(option(kind), 'option:' + kind), *children]
    replies = []
    for i, (view, action) in enumerate(steps, 1):
        view = copy.deepcopy(view); view['decision_id'] = ident(i)
        if i > 2:
            view['completed'] = [completion(i - 1, steps[i - 2][1])]
        replies += [view, value('accepted', 'action', decision_id=ident(i), action_id=action)]
    done = value('complete', 'rest')
    if len(steps) > 1:
        done['completed'].append(completion(len(steps), steps[-1][1]))
    done['completed'].append(completion(1, steps[0][1], 'cancelled' if cancelled else 'reconciled'))
    replies += [value('waiting', 'effect'), done]
    return replies, [a for _, a in steps]


class RestInteractiveTests(unittest.TestCase):
    def run_host(self, replies, actions, *, lost=False, provider=None, clock=lambda: 0, on_request=lambda *_: None):
        calls, buffers, posts, seen = [], [], [], []
        expected = iter(actions)
        def choose(view):
            seen.append(copy.deepcopy(view))
            return provider(view) if provider else next(expected)
        def request(method, route, body):
            calls.append((method, route))
            on_request(method, len(calls))
            if method == 'POST':
                buffers.append(body); posts.append(json.loads(body))
                if lost:
                    raise TimeoutError()
            raw = bytearray(json.dumps(replies.pop(0)).encode()); buffers.append(raw)
            return raw
        result = host.run_rest(request, choose, clock=clock, sleep=lambda _: None)
        self.assertTrue(all(not any(b) for b in buffers), 'request and response buffers erased')
        return result, posts, seen

    def test_each_child_is_a_separate_policy_decision(self):
        cases = [
            ('smith', [(selection('smith'), 'select:0'), (selection('smith', (0,)), 'confirm')], False),
            ('smith', [(selection('smith'), 'cancel')], True),
            ('smith', [(selection('smith'), 'select:0'), (selection('smith', (0,)), 'cancel')], True),
            ('cook', [(selection('cook', maximum=2), 'select:0'),
                      (selection('cook', (0,), 2), 'select:1'), (selection('cook', (0, 1), 2), 'confirm')], False),
            ('heal', [(reward(), 'reward:open:0'), (reward(True), 'reward:choose:1')], False),
            ('heal', [(reward(), 'reward:open:0'), (reward(True), 'reward:skip_card'),
                      (reward(skipped=True), 'reward:dismiss')], False),
        ]
        for kind, children, cancelled in cases:
            with self.subTest(kind=kind, cancelled=cancelled):
                replies, actions = script(kind, children, cancelled)
                result, posts, seen = self.run_host(replies, actions)
                self.assertEqual(result['status'], 'resolved', result)
                self.assertEqual([p['action_id'] for p in posts], actions)
                self.assertEqual(len(seen), len(actions))
                self.assertEqual([result[k] for k in ('attempted', 'accepted', 'reconciled')], [len(actions)] * 3)
                self.assertEqual(result['outcome'], 'cancelled' if cancelled else 'reconciled')

    def test_parent_and_child_receipts_are_required(self):
        base, actions = script('smith', [(selection('smith'), 'cancel')], True)
        for change, code in (
            (lambda r: r[-1]['completed'].reverse(), 'unowned_cancel'),
            (lambda r: r[-1]['completed'].pop(0), 'unowned_cancel'),
            (lambda r: r[2].update(completed=[completion(1, 'option:smith')]), 'premature_parent_completion'),
            (lambda r: r[2].update(parent_action='option:cook'), 'parent_changed'),
            (lambda r: r[2].update(session_nonce='b' * 32), 'session_changed'),
            (lambda r: r[1].update(action_id='option:cook'), 'action_not_accepted'),
            (lambda r: r[-1]['completed'][-1].update(result='reconciled'), 'cancel_result_mismatch'),
        ):
            replies = copy.deepcopy(base); change(replies)
            result, posts, _ = self.run_host(replies, actions)
            self.assertEqual(result['code'], code, result)
            self.assertLessEqual(len(posts), 2)

    def test_lost_receipt_never_retries(self):
        result, posts, _ = self.run_host(*script('heal'), lost=True)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual((result['attempted'], result['accepted'], len(posts)), (1, 0, 1))

    def test_provider_cannot_expand_legal_actions(self):
        def malicious(view):
            view['legal_actions'].append('option:cook')
            return 'option:cook'
        result, posts, _ = self.run_host(*script('smith'), provider=malicious)
        self.assertEqual(result['code'], 'policy_action_unavailable')
        self.assertEqual(posts, [])

    def test_expired_provider_does_not_dispatch(self):
        now = [0]
        def delayed(view):
            now[0] = 121
            return view['legal_actions'][0]
        result, posts, _ = self.run_host(*script('heal'), provider=delayed, clock=lambda: now[0])
        self.assertEqual(result['code'], 'wait_budget')
        self.assertEqual(posts, [])

    def test_late_completion_or_receipt_retains_evidence_but_fails_budget(self):
        for late_call in (2, 4):
            now = [0]
            def late_response(_method, index):
                if index == late_call: now[0] = 121
            result, posts, _ = self.run_host(*script('heal'), clock=lambda: now[0], on_request=late_response)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['code'], 'wait_budget')
            self.assertEqual((result['attempted'], result['accepted'], len(posts)), (1, 1, 1))
            self.assertEqual(result['reconciled'], 1 if late_call == 4 else 0)

    def test_reward_actions_match_current_surface_and_target(self):
        for opened, actions in ((True, ['reward:choose:2']), (True, ['reward:open:0']),
                                (True, ['reward:dismiss']), (False, ['reward:choose:0']),
                                (False, ['reward:skip_card']), (False, ['reward:open:1']),
                                (False, ['reward:collect:0'])):
            row = reward(opened); row['legal_actions'] = actions
            raw = bytearray(json.dumps(row).encode())
            with self.assertRaises(ValueError): host.decode(raw)
            self.assertFalse(any(raw))
        row = reward(); row['rewards'][0]['selected'] = True
        with self.assertRaises(ValueError): host.decode(bytearray(json.dumps(row).encode()))

    def test_collected_rewards_compact_positions_but_keep_original_ordinals(self):
        first = value('ready', 'rewards', decision_id=ident(2), parent_action='option:heal', screen_kind='rewards',
                      rewards=[dict(slot=i, kind='potion', key='POTION_' + str(i), selected=False, cards=[]) for i in range(2)],
                      legal_actions=['reward:collect:0', 'reward:collect:1', 'reward:dismiss'])
        remaining = copy.deepcopy(first)
        remaining['rewards'].pop(0)
        remaining['legal_actions'] = ['reward:collect:0', 'reward:dismiss']
        result, posts, seen = self.run_host(*script('heal', [(first, 'reward:collect:0'), (remaining, 'reward:collect:0')]))
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual(result['reconciled'], 3)
        self.assertEqual(seen[-1]['rewards'][0]['slot'], 1)
        self.assertEqual([p['action_id'] for p in posts], ['option:heal', 'reward:collect:0', 'reward:collect:0'])

    def test_duplicate_decision_cannot_be_reissued(self):
        replies, actions = script('smith', [(selection('smith'), 'select:0'), (selection('smith', (0,)), 'confirm')])
        replies[4]['decision_id'] = replies[2]['decision_id']
        result, posts, _ = self.run_host(replies, actions)
        self.assertEqual(result['code'], 'action_budget')
        self.assertEqual(len(posts), 2)

    def test_malformed_or_private_ready_never_reaches_callback(self):
        candidates = []
        for change in (
            lambda r: r.update(private_seed=2),
            lambda r: r.update(legal_actions=[{}]),
            lambda r: r.update(legal_actions=['option:unknown']),
            lambda r: r['options'][0].update(enabled=False),
            lambda r: r.update(schema_version=True),
        ):
            row = option('heal'); change(row); candidates.append(row)
        row = reward(); row['rewards'][0]['cards'] = ['HIDDEN_CARD']; candidates.append(row)
        row = selection('smith'); row['legal_actions'].insert(0, 'confirm'); candidates.append(row)
        for row in candidates:
            result, posts, seen = self.run_host([row], [])
            self.assertEqual(result['status'], 'failed')
            self.assertEqual((posts, seen), ([], []))
        raw = bytearray(b'{"schema_version":3,"schema_version":3}')
        with self.assertRaises(ValueError): host.decode(raw)
        self.assertFalse(any(raw))

    def test_controlled_policy_respects_native_minimum_and_cancel(self):
        for kind, minimum in (('smith', 1), ('cook', 2)):
            self.assertEqual(host.controlled_policy(kind, 'cancel')(selection(kind, maximum=minimum)), 'cancel')
            self.assertEqual(host.controlled_policy(kind, 'preview-cancel')(selection(kind, maximum=minimum)), 'select:0')
            self.assertEqual(host.controlled_policy(kind, 'preview-cancel')(selection(kind, tuple(range(minimum)), minimum)), 'cancel')
        self.assertEqual(host.controlled_policy('heal', reward='skip-card')(reward(True)), 'reward:skip_card')


if __name__ == '__main__':
    unittest.main()
