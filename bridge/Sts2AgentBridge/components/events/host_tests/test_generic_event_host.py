"""Independent wire scripts exercise host ownership, immutability and failure accounting."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).absolute().parents[1] / 'host/generic_event_host.py'
SPEC = importlib.util.spec_from_file_location('generic_event_host_under_test', PATH)
host = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = host
SPEC.loader.exec_module(host)
N = 'a' * 32
D = ['%064x' % i for i in range(1, 12)]


def env(kind='decision', parent=None, child=None, payload=None):
    return dict(schema_version=1, protocol='generic_event_v9', session_nonce=N,
                kind=kind, parent=parent, child=child, payload=payload)


def candidate(key='UNREGISTERED.option', proceed=False, dangerous=False):
    return dict(index=0, action_id='choose:0', stable_id=key, rendered_text='Choose <upgrade> + confirm',
                enabled=True, is_dangerous=dangerous, is_proceed=proceed,
                discovery='none' if proceed else 'deferred')


def parent(status='ready', decision=D[0], history=None, pa=0, pr=0, ce=0, ca=0, cr=0, proceed=False):
    phase = {'ready': 'proceed' if proceed else 'choose_option', 'waiting': 'waiting',
             'child': 'child', 'complete': 'map_handoff', 'unsupported': 'unsupported'}[status]
    return dict(status=status, phase=phase, decision_id=decision if status == 'ready' else '',
                candidates=[candidate('PROCEED' if proceed else 'UNREGISTERED.option', proceed)] if status == 'ready' else [],
                legal_actions=['choose:0'] if status == 'ready' else [], prior_results=history or [],
                parent_attempted=pa, parent_accepted=pa, parent_reconciled=pr, child_episodes=ce,
                child_attempted=ca, child_accepted=ca, child_reconciled=cr, total_attempted=pa + ca,
                effects='unverified' if pa else 'none_attempted',
                completed_card_children=sum(row['result'] == 'child_completed' for row in history or []), completed_item_children=0)


def prior(decision=D[0], result='option_transition'):
    return dict(decision_id=decision, action_id='choose:0', result=result)


def receipt(decision=D[0], child=None, action='choose:0', outcome='accepted'):
    if child is None:
        payload = dict(version='generic_event_v9', session_nonce=N, decision_id=decision, action_id=action, outcome=outcome)
    else:
        payload = dict(schema_version=1, kind='child_receipt', version=child['contract_version'],
                       session_nonce=N, parent_ordinal=1, decision_id=decision, action_id=action, outcome=outcome)
    return env('action', child=child, payload=payload)


def child():
    return dict(ordinal=1, parent_decision_id=D[0], parent_action_id='choose:0', kind='card_selection', contract_version='card_selection_v1', operation='upgrade',
                min_select=1, max_select=1, commit_mode='preview_confirm', domain_count=2)


def card(slot=0, selected=False):
    return dict(slot=slot, key='STRIKE' if slot == 0 else 'DEFEND', upgrade_level=0,
                visible=True, enabled=True, selected=selected)


def child_payload(phase='selecting', decision=D[2], history=None):
    selected = phase != 'selecting'
    return dict(schema_version=1, kind='child_observation', version='card_selection_v1', session_nonce=N,
                parent_ordinal=1, status='ready', phase=phase, operation='upgrade', commit_mode='preview_confirm',
                min_select=1, max_select=1, decision_id=decision,
                candidates=[card(0, selected), card(1)], selected_slots=[0] if selected else [],
                legal_actions=['confirm'] if selected else ['select:0', 'select:1'], prior_results=history or [])


def combat_entry(resumes=False):
    done = parent('complete', history=[prior(result='combat_handoff')], pa=1, pr=1)
    done['phase'] = 'combat_resume_handoff' if resumes else 'combat_handoff'
    done['prior_results'][0]['result'] = done['phase']
    return [('GET', env(parent=parent())), ('POST', receipt()), ('GET', env(parent=done))]


def ordinary():
    h = [prior()]
    return [('GET', env(parent=parent())), ('POST', receipt()),
            ('GET', env(parent=parent(decision=D[1], history=h, pa=1, pr=1, proceed=True))),
            ('POST', receipt(D[1])),
            ('GET', env(parent=parent('complete', history=h + [prior(D[1], 'map_handoff')], pa=2, pr=2)))]


def upgrade():
    c = child()
    selected = dict(decision_id=D[2], action_id='select:0', result='selected')
    committed = dict(decision_id=D[3], action_id='confirm', result='committed')
    resolved = dict(schema_version=1, kind='child_resolved', version='card_selection_v1', session_nonce=N,
                    parent_ordinal=1, status='resolved', phase='complete', operation='upgrade',
                    selected_cards=[card(0, True)], prior_results=[selected, committed])
    h = [prior(result='child_completed')]
    return [('GET', env(parent=parent())), ('POST', receipt()),
            ('GET', env(parent=parent('child', pa=1, ce=1), child=c, payload=child_payload())),
            ('POST', receipt(D[2], c, 'select:0')),
            ('GET', env(parent=parent('child', pa=1, ce=1, ca=1), child=c,
                        payload=child_payload('preview', D[3], [selected]))),
            ('POST', receipt(D[3], c, 'confirm')),
            ('GET', env(parent=parent('child', pa=1, ce=1, ca=2, cr=1), child=c, payload=resolved)),
            ('GET', env(parent=parent(decision=D[1], history=h, pa=1, pr=1, ce=1, ca=2, cr=2, proceed=True))),
            ('POST', receipt(D[1])),
            ('GET', env(parent=parent('complete', history=h + [prior(D[1], 'map_handoff')],
                                     pa=2, pr=2, ce=1, ca=2, cr=2)))]


def sequential_upgrades(count=4):
    rows, history = [], []
    def replace(value, mapping):
        if isinstance(value, dict):
            return {k: replace(v, mapping) for k, v in value.items()}
        if isinstance(value, list):
            return [replace(v, mapping) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    for i in range(count):
        mapping = {D[0]: '%064x' % (100 + i * 3), D[2]: '%064x' % (101 + i * 3), D[3]: '%064x' % (102 + i * 3)}
        for method, original in upgrade()[:7]:
            value = replace(original, mapping)
            if value['child'] is not None:
                value['child']['ordinal'] = i + 1
            if value['parent'] is not None:
                p = value['parent']
                p['prior_results'] = list(history)
                p['completed_card_children'] = sum(row['result'] == 'child_completed' for row in history)
                p['parent_attempted'] += i
                p['parent_accepted'] += i
                p['parent_reconciled'] += i
                p['child_episodes'] += i
                p['child_attempted'] += i * 2
                p['child_accepted'] += i * 2
                p['child_reconciled'] += i * 2
                p['total_attempted'] += i * 3
                if p['total_attempted']:
                    p['effects'] = 'unverified'
                if p['status'] == 'ready':
                    p['candidates'][0]['stable_id'] = 'NEW_EVENT.page_%d' % i
            rows.append((method, value))
        history.append(prior(mapping[D[0]], 'child_completed'))
    final = '%064x' % 500
    rows.extend([('GET', env(parent=parent(decision=final, history=history, pa=count, pr=count, ce=count, ca=count * 2, cr=count * 2, proceed=True))),
                 ('POST', receipt(final)),
                 ('GET', env(parent=parent('complete', history=history + [prior(final, 'map_handoff')], pa=count + 1, pr=count + 1, ce=count, ca=count * 2, cr=count * 2)))])
    return rows


class Script:
    def __init__(self, rows):
        self.rows = copy.deepcopy(rows)
        self.calls = []
        self.buffers = []

    def __call__(self, method, route, body):
        self.calls.append((method, route, None if body is None else json.loads(body)))
        expected, value = self.rows.pop(0)
        assert method == expected
        assert route == (host.DECISION_ROUTE if method == 'GET' else host.ACTION_ROUTE)
        if isinstance(value, Exception):
            raise value
        buffer = value if isinstance(value, bytearray) else bytearray(json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode())
        self.buffers.append(buffer)
        return buffer


def run(script, **kwargs):
    return host.run_event(script, provider=kwargs.pop('provider', host.first_legal),
                          clock=kwargs.pop('clock', lambda: 1.0), sleep=lambda _: None, **kwargs)


class GenericHostTests(unittest.TestCase):
    def test_combat_entry_is_a_distinct_destination(self):
        script = Script(combat_entry())
        result = run(script)
        self.assertEqual((result['status'], result['destination'], result['parent_reconciled']),
                         ('resolved', 'combat_handoff', 1), result)
        self.assertTrue(all(not any(buf) for buf in script.buffers))

    def test_resuming_entry_retains_nonce_for_continuation(self):
        result = run(Script(combat_entry(True)))
        self.assertEqual((result['status'], result['destination'], result['session_nonce']),
                         ('resolved', 'combat_resume_handoff', N), result)

    def test_terminal_history_and_proceed_must_match_destination(self):
        for mode in ['history', 'proceed', 'map_phase']:
            rows = combat_entry()
            if mode == 'history': rows[-1][1]['parent']['prior_results'][0]['result'] = 'option_transition'
            if mode == 'proceed': rows[0] = ('GET', env(parent=parent(proceed=True)))
            if mode == 'map_phase': rows[-1][1]['parent']['phase'] = 'map_handoff'
            script = Script(rows)
            result = run(script)
            self.assertEqual(result['status'], 'failed', (mode, result))
            self.assertEqual(sum(method == 'POST' for method, _, _ in script.calls), 1)

    def test_ordinary_page_and_explicit_proceed(self):
        script = Script(ordinary())
        result = run(script)
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual((result['parent_attempted'], result['parent_accepted'], result['parent_reconciled']), (2, 2, 2))
        self.assertTrue(all(not any(buf) for buf in script.buffers))
        self.assertFalse(script.rows)

    def test_unknown_event_uses_generic_upgrade_and_lineage_only_posts(self):
        script = Script(upgrade())
        result = run(script)
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual((result['child_episodes'], result['child_attempted'], result['child_accepted'], result['child_reconciled']), (1, 2, 2, 2))
        posts = [body for method, _, body in script.calls if method == 'POST']
        self.assertEqual(posts[1]['child'], {k: child()[k] for k in host._CHILD[:3]})
        self.assertNotIn('operation', posts[1]['child'])

    def test_provider_sees_deeply_immutable_public_values(self):
        seen = []
        def provider(view):
            seen.append(view.kind)
            with self.assertRaises(TypeError):
                view.payload['legal_actions'][0] = 'oops'
            if view.kind == 'parent':
                with self.assertRaises(TypeError):
                    view.payload['candidates'][0]['enabled'] = False
            else:
                with self.assertRaises(TypeError):
                    view.child['operation'] = 'remove'
            return host.first_legal(view)
        self.assertEqual(run(Script(upgrade()), provider=provider)['status'], 'resolved')
        self.assertEqual(seen, ['parent', 'card_selection', 'card_selection', 'parent'])

    def test_transport_failure_preserves_attempt_without_retry(self):
        script = Script(ordinary()[:1] + [('POST', host.TransportFailure())])
        result = run(script)
        self.assertEqual(result['code'], 'transport_failure')
        self.assertEqual((result['parent_attempted'], result['parent_accepted'], result['effects']), (1, 0, 'unverified'))
        self.assertEqual(len(script.calls), 2)

    def test_uncertain_receipt_stops_without_retry(self):
        script = Script(ordinary()[:1] + [('POST', receipt(outcome='uncertain'))])
        result = run(script)
        self.assertEqual(result['code'], 'uncertain_action')
        self.assertEqual(result['parent_attempted'], 1)
        self.assertEqual(result['parent_accepted'], 0)

    def test_provider_cannot_supply_unadvertised_action(self):
        script = Script(ordinary())
        result = run(script, provider=lambda _: 'choose:7')
        self.assertEqual(result['code'], 'invalid_provider')
        self.assertEqual(len(script.calls), 1)

    def test_late_provider_never_posts(self):
        now = [0.0]
        def provider(view):
            now[0] = 31.0
            return host.first_legal(view)
        script = Script(ordinary())
        result = run(script, provider=provider, clock=lambda: now[0])
        self.assertEqual(result['code'], 'deadline_exceeded')
        self.assertEqual(result['total_attempted'], 0)

    def test_late_post_is_not_accepted_and_never_retried(self):
        now = [0.0]
        script = Script(ordinary())
        def request(method, route, body):
            value = script(method, route, body)
            if method == 'POST':
                now[0] = 31.0
            return value
        result = run(request, clock=lambda: now[0])
        self.assertEqual(result['code'], 'deadline_exceeded')
        self.assertEqual((result['parent_attempted'], result['parent_accepted']), (1, 0))
        self.assertEqual(len(script.calls), 2)

    def test_reentrant_provider_poison_outer_controller(self):
        def provider(view):
            result = run(lambda *args: self.fail('nested transport must not execute'))
            self.assertEqual(result['code'], 'reentrant_provider')
            return host.first_legal(view)
        script = Script(ordinary())
        result = run(script, provider=provider)
        self.assertEqual(result['code'], 'reentrant_provider')
        self.assertEqual(len(script.calls), 1)

    def test_invalid_outer_and_parent_shapes(self):
        mutations = [lambda v: v.update(extra=1), lambda v: v.update(session_nonce='b' * 32),
                     lambda v: v['parent'].update(parent_attempted=True),
                     lambda v: v['parent'].update(effects='zero_effects'),
                     lambda v: v['parent']['candidates'][0].update(discovery='registered')]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                rows = ordinary()
                target = 2 if index == 1 else 0
                mutation(rows[target][1])
                result = run(Script(rows))
                self.assertEqual(result['code'], 'invalid_response', result)

    def test_duplicate_json_keys_rejected(self):
        body = bytearray(b'{"schema_version":1,"schema_version":1}')
        self.assertEqual(run(Script([('GET', body)]))['code'], 'invalid_response')

    def test_wrong_receipt_correlation_preserves_attempt(self):
        rows = ordinary()
        rows[1][1]['payload']['decision_id'] = D[8]
        result = run(Script(rows))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual((result['parent_attempted'], result['parent_accepted']), (1, 0))

    def test_child_descriptor_and_owner_mutations_reject(self):
        for field, value in [('operation', 'remove'), ('min_select', 2), ('max_select', 2),
                             ('domain_count', 1), ('parent_decision_id', D[8]), ('ordinal', 2)]:
            with self.subTest(field=field):
                rows = upgrade()
                rows[2][1]['child'][field] = value
                result = run(Script(rows))
                self.assertEqual(result['code'], 'invalid_response', result)
                self.assertEqual(result['child_attempted'], 0)

    def test_admitted_descriptor_cannot_change(self):
        rows = upgrade()
        rows[4][1]['child'] = dict(rows[4][1]['child'], domain_count=3)
        result = run(Script(rows))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 1)

    def test_candidate_shape_cannot_change(self):
        rows = upgrade()
        rows[4][1]['payload']['candidates'][0]['key'] = 'BASH'
        result = run(Script(rows))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 1)

    def test_child_cannot_disappear_before_resolution(self):
        rows = upgrade()
        rows[4] = ('GET', env(parent=parent('waiting', pa=1, ce=1, ca=1)))
        self.assertEqual(run(Script(rows))['code'], 'invalid_response')

    def test_parent_cannot_claim_foreign_or_early_child_completion(self):
        rows = ordinary()
        rows[2][1]['parent']['prior_results'][0]['result'] = 'child_completed'
        self.assertEqual(run(Script(rows))['code'], 'invalid_response')

    def test_parent_effect_before_unsupported_child_is_unverified(self):
        rows = ordinary()[:2] + [('GET', env(parent=parent('unsupported', pa=1)))]
        result = run(Script(rows))
        self.assertEqual(result['code'], 'unsupported_state')
        self.assertEqual((result['parent_attempted'], result['parent_accepted'], result['effects']), (1, 1, 'unverified'))

    def test_replayed_parent_decision_does_not_call_provider_twice(self):
        rows = ordinary()
        rows[2][1]['parent']['decision_id'] = D[0]
        calls = []
        result = run(Script(rows), provider=lambda view: calls.append(view.kind) or host.first_legal(view))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(calls, ['parent'])

    def test_repeated_key_requires_fresh_decision_and_completed_history(self):
        rows, history = [], []
        for i in range(4):
            rows += [('GET', env(parent=parent(decision=D[i], history=list(history), pa=i, pr=i, proceed=i == 3))),
                     ('POST', receipt(D[i]))]
            history.append(prior(D[i], 'map_handoff' if i == 3 else 'option_transition'))
        rows += [('GET', env(parent=parent('complete', history=history, pa=4, pr=4)))]
        result = run(Script(rows))
        self.assertEqual((result['status'], result['parent_reconciled']), ('resolved', 4))
        for mutation in ('decision', 'unreconciled'):
            bad = copy.deepcopy(rows)
            if mutation == 'decision':
                bad[2][1]['parent']['decision_id'] = D[0]
            else:
                bad[2][1]['parent'].update(prior_results=[], parent_reconciled=0)
            script = Script(bad)
            self.assertEqual(run(script)['code'], 'invalid_response')
            self.assertEqual(len(script.calls), 3)  # One POST only; no repeat input.

    def test_read_budget_shared_and_bounded(self):
        calls = []
        def request(method, route, body):
            calls.append(method)
            return bytearray(json.dumps(env(parent=parent('waiting')), separators=(',', ':')).encode())
        result = run(request)
        self.assertEqual(result['code'], 'read_limit')
        self.assertEqual(result['reads'], 2048)
        self.assertEqual(len(calls), 2048)

    def test_nonfinite_and_regressing_clock_reject(self):
        for value in (float('nan'), float('inf'), True):
            with self.subTest(value=value):
                self.assertEqual(run(Script(ordinary()), clock=lambda: value)['code'], 'internal_failure')
        values = iter([1.0, 0.0])
        self.assertEqual(run(Script(ordinary()), clock=lambda: next(values))['code'], 'internal_failure')


    def test_parent_action_budget_stops_thirteenth_dispatch(self):
        rows, history = [], []
        for i in range(13):
            decision = '%064x' % (100 + i)
            p = parent(decision=decision, history=list(history), pa=i, pr=i)
            p['candidates'][0]['stable_id'] = 'HELD_OUT.option_%d' % i
            rows.append(('GET', env(parent=p)))
            if i < 12:
                rows.append(('POST', receipt(decision)))
                history.append(prior(decision))
        script = Script(rows)
        result = run(script)
        self.assertEqual(result['code'], 'action_limit', result)
        self.assertEqual((result['parent_attempted'], result['parent_accepted'], result['parent_reconciled']), (12, 12, 12))
        self.assertEqual(sum(method == 'POST' for method, _, _ in script.calls), 12)

    def test_completed_child_cannot_reopen(self):
        rows = upgrade()
        rows.insert(7, copy.deepcopy(rows[6]))
        result = run(Script(rows))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 2)
        self.assertEqual(result['child_reconciled'], 2)

    def test_child_transport_failure_keeps_parent_and_prior_child_accounting(self):
        rows = upgrade()[:5] + [('POST', host.TransportFailure())]
        result = run(Script(rows))
        self.assertEqual(result['code'], 'transport_failure')
        self.assertEqual((result['parent_attempted'], result['parent_accepted']), (1, 1))
        self.assertEqual((result['child_attempted'], result['child_accepted'], result['child_reconciled']), (2, 1, 1))
        self.assertEqual(result['effects'], 'unverified')

    def test_native_counters_cannot_forge_reconciliation(self):
        rows = ordinary()
        rows[2][1]['parent']['parent_reconciled'] = 0
        result = run(Script(rows))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['parent_reconciled'], 0)

    def test_frozen_card_schema_version_is_checked_before_validator(self):
        rows = upgrade()
        rows[2][1]['payload']['schema_version'] = True
        self.assertEqual(run(Script(rows))['code'], 'invalid_response')

    def test_csharp_escaped_public_text_is_accepted(self):
        rows = ordinary()
        value = json.dumps(rows[0][1], separators=(',', ':')).replace('<', r'\u003C').replace('>', r'\u003E').replace('+', r'\u002B')
        rows[0] = ('GET', bytearray(value.encode()))
        self.assertEqual(run(Script(rows))['status'], 'resolved')


    def test_native_unsupported_can_terminate_active_child_without_completion(self):
        rows = upgrade()[:5] + [('POST', receipt(D[3], child(), 'confirm')),
                ('GET', env(parent=parent('unsupported', pa=1, ce=1, ca=2, cr=1)))]
        result = run(Script(rows))
        self.assertEqual(result['code'], 'unsupported_state')
        self.assertEqual((result['child_episodes'], result['child_attempted'], result['child_accepted'], result['child_reconciled']), (1, 2, 2, 1))
        self.assertEqual(result['parent_reconciled'], 0)
        self.assertEqual(result['effects'], 'unverified')


    def test_resolved_selected_original_must_match_exact_selection_receipt(self):
        rows = upgrade()
        rows[6][1]['payload']['selected_cards'] = [card(1, True)]
        result = run(Script(rows))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_reconciled'], 1)

    def test_selected_ready_slots_must_match_exact_selection_receipt(self):
        rows = upgrade()
        p = rows[4][1]['payload']
        p['selected_slots'] = [1]
        p['candidates'] = [card(0), card(1, True)]
        p['prior_results'] = [dict(decision_id=D[2], action_id='select:1', result='selected')]
        self.assertEqual(run(Script(rows))['code'], 'invalid_response')

    def test_parent_text_bound_is_utf8_bytes_and_controls_are_restricted(self):
        for text in ('é' * 513, 'control\x00', 'control\x7f', 'control\x85'):
            with self.subTest(text=text[:12]):
                rows = ordinary()
                rows[0][1]['parent']['candidates'][0]['rendered_text'] = text
                self.assertEqual(run(Script(rows))['code'], 'invalid_response')
        rows = ordinary()
        rows[0][1]['parent']['candidates'][0]['rendered_text'] = 'Line 1\nLine 2\tIndented'
        self.assertEqual(run(Script(rows))['status'], 'resolved')


    def test_four_sequential_children_keep_separate_receipts_and_shared_budget(self):
        result = run(Script(sequential_upgrades()))
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual((result['parent_accepted'], result['parent_reconciled'], result['child_episodes']), (5, 5, 4))
        self.assertEqual((result['child_attempted'], result['child_accepted'], result['child_reconciled']), (8, 8, 8))
        self.assertEqual(result['total_attempted'], 13)

    def test_fifth_child_is_rejected_without_any_fifth_child_action(self):
        result = run(Script(sequential_upgrades(5)))
        self.assertEqual(result['code'], 'invalid_response', result)
        self.assertEqual(result['child_episodes'], 4)
        self.assertEqual(result['child_attempted'], 8)


if __name__ == '__main__':
    unittest.main()
