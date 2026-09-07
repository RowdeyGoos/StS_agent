"""Removal descriptor, preview, original-set and shared-budget host conformance."""
from __future__ import annotations
import copy
import unittest

from test_generic_event_host import D, N, Script, card, child, env, host, parent, prior, receipt, run, upgrade


def removal(minimum=1, maximum=2, slots=(1, 0), explicit=False, domain=None):
    domain = maximum + 1 if domain is None else domain
    descriptor = dict(child(), operation='remove', min_select=minimum,
                      max_select=maximum, domain_count=domain)
    actions = ['select:%d' % slot for slot in slots] + (['preview'] if explicit else []) + ['confirm']
    rows = [('GET', env(parent=parent())), ('POST', receipt())]
    selected, history = set(), []
    preview = False
    for index, action in enumerate(actions):
        decision = '%064x' % (1500 + index)
        phase = 'preview' if preview or len(selected) == maximum else 'selecting'
        legal = ['confirm'] if phase == 'preview' else [f'select:{i}' for i in range(domain) if i not in selected]
        if phase == 'selecting' and minimum <= len(selected) < maximum:
            legal.append('preview')
        payload = dict(schema_version=1, kind='child_observation', version='card_selection_v1',
                       session_nonce=N, parent_ordinal=1, status='ready', phase=phase,
                       operation='remove', commit_mode='preview_confirm', min_select=minimum,
                       max_select=maximum, decision_id=decision,
                       candidates=[card(i, i in selected) for i in range(domain)],
                       selected_slots=sorted(selected), legal_actions=legal,
                       prior_results=list(history))
        rows.append(('GET', env(parent=parent('child', pa=1, ce=1, ca=index, cr=max(0, index - 1)),
                                child=dict(descriptor), payload=payload)))
        rows.append(('POST', receipt(decision, dict(descriptor), action)))
        history.append(dict(decision_id=decision, action_id=action,
                            result='selected' if action.startswith('select:') else 'previewed' if action == 'preview' else 'committed'))
        if action.startswith('select:'):
            selected.add(int(action[7:]))
        elif action == 'preview':
            preview = True
    total = len(actions)
    resolved = dict(schema_version=1, kind='child_resolved', version='card_selection_v1',
                    session_nonce=N, parent_ordinal=1, status='resolved', phase='complete',
                    operation='remove', selected_cards=[card(i, True) for i in sorted(selected)],
                    prior_results=history)
    rows.append(('GET', env(parent=parent('child', pa=1, ce=1, ca=total, cr=total - 1),
                            child=dict(descriptor), payload=resolved)))
    completed = [prior(result='child_completed')]
    rows.extend([('GET', env(parent=parent(decision=D[1], history=completed, pa=1, pr=1,
                                         ce=1, ca=total, cr=total, proceed=True))),
                 ('POST', receipt(D[1])),
                 ('GET', env(parent=parent('complete', history=completed + [prior(D[1], 'map_handoff')],
                                          pa=2, pr=2, ce=1, ca=total, cr=total)))])
    return rows


def drive(rows):
    # The policy chooses a fixed requested sequence; the transport still validates
    # every choice through the actual host and exact receipt correspondence.
    actions = iter(value['payload']['action_id'] for method, value in rows
                   if method == 'POST' and isinstance(value, dict))
    script = Script(rows)
    result = run(script, provider=lambda _: next(actions))
    return result, script


class RemovalHostTests(unittest.TestCase):
    def test_all_exact_counts_one_through_eight_reverse_selection(self):
        for count in range(1, 9):
            with self.subTest(count=count):
                result, script = drive(removal(count, count, tuple(reversed(range(count)))))
                self.assertEqual(result['status'], 'resolved', result)
                self.assertEqual(result['child_attempted'], count + 1)
                self.assertEqual(result['child_accepted'], count + 1)
                self.assertEqual(result['child_reconciled'], count + 1)
                self.assertFalse(script.rows)

    def test_variable_count_can_preview_at_min_or_intermediate_count(self):
        for slots in ((2, 0), (3, 1, 0)):
            with self.subTest(slots=slots):
                result, _ = drive(removal(2, 4, slots, explicit=True))
                self.assertEqual(result['status'], 'resolved', result)
                self.assertEqual(result['child_attempted'], len(slots) + 2)

    def test_variable_count_automatically_previews_at_max(self):
        result, script = drive(removal(1, 4, (3, 1, 2, 0)))
        self.assertEqual(result['status'], 'resolved', result)
        actions = [body['action_id'] for method, _, body in script.calls if method == 'POST' and body['child']]
        self.assertEqual(actions, ['select:3', 'select:1', 'select:2', 'select:0', 'confirm'])

    def test_duplicate_selected_originals_cannot_be_hidden_by_set_conversion(self):
        rows = removal()
        payload = rows[-4][1]['payload']
        payload['selected_cards'] = [card(0, True), card(0, True)]
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_reconciled'], 2)

    def test_foreign_selected_original_with_correct_count_rejects(self):
        rows = removal()
        rows[-4][1]['payload']['selected_cards'] = [card(0, True), card(2, True)]
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_duplicate_public_selected_slots_reject(self):
        rows = removal()
        rows[6][1]['payload']['selected_slots'] = [0, 0]
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_preview_cannot_claim_different_originals_after_highlights_clear(self):
        rows = removal()
        payload = rows[6][1]['payload']
        payload['selected_slots'] = [0, 2]
        payload['candidates'] = [card(0, True), card(1), card(2, True)]
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_automatic_preview_below_max_requires_explicit_preview_receipt(self):
        rows = removal(1, 3, (0,), explicit=True)
        payload = rows[4][1]['payload']
        payload['phase'] = 'preview'
        payload['legal_actions'] = ['confirm']
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 1)

    def test_at_max_removal_must_show_preview_not_another_preview_action(self):
        rows = removal()
        payload = rows[6][1]['payload']
        payload['phase'] = 'selecting'
        payload['legal_actions'] = ['preview']
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 2)

    def test_preview_cancellation_cannot_reopen_selection(self):
        rows = removal(1, 3, (0,), explicit=True)
        payload = rows[6][1]['payload']
        payload['phase'] = 'selecting'
        payload['legal_actions'] = ['select:1', 'select:2', 'select:3', 'preview']
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 2)

    def test_admitted_count_and_mode_reject_bool_zero_overflow_and_shortcuts(self):
        for field, value in [('min_select', True), ('max_select', True), ('min_select', 0),
                             ('min_select', 3), ('max_select', 9), ('domain_count', 2),
                             ('domain_count', 65), ('domain_count', True),
                             ('commit_mode', 'auto_at_max'), ('commit_mode', 'explicit_confirm'),
                             ('operation', 'transform'), ('operation', 'add')]:
            with self.subTest(field=field, value=value):
                rows = removal()
                rows[2][1]['child'][field] = value
                result, _ = drive(rows)
                self.assertEqual(result['code'], 'invalid_response', result)
                self.assertEqual(result['child_attempted'], 0)

    def test_valid_removal_descriptor_does_not_override_child_payload(self):
        for field, value in [('operation', 'upgrade'), ('min_select', 2), ('max_select', 3),
                             ('commit_mode', 'auto_at_max')]:
            with self.subTest(field=field):
                rows = removal()
                rows[2][1]['payload'][field] = value
                self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_descriptor_cannot_change_between_selection_and_preview(self):
        rows = removal()
        rows[6][1]['child']['min_select'] = 2
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 2)

    def test_preview_before_minimum_has_no_legal_action(self):
        rows = removal(2, 3, (0, 1), explicit=True)
        rows[4][1]['payload']['legal_actions'].append('preview')
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_wrong_operation_on_resolved_payload_rejects(self):
        rows = removal()
        rows[-4][1]['payload']['operation'] = 'upgrade'
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_partial_effect_failure_preserves_all_received_action_history(self):
        rows = removal()
        rows[-4] = ('GET', env(parent=parent('unsupported', pa=1, ce=1, ca=3, cr=2)))
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'unsupported_state')
        self.assertEqual((result['parent_accepted'], result['parent_reconciled']), (1, 0))
        self.assertEqual((result['child_attempted'], result['child_accepted'], result['child_reconciled']), (3, 3, 2))
        self.assertEqual(result['effects'], 'unverified')

    def test_uncertain_final_confirm_is_never_retried(self):
        rows = removal()
        rows[7][1]['payload']['outcome'] = 'uncertain'
        # Frozen failure payload intentionally has no untrusted decision identity.
        rows[7][1]['payload'] = dict(schema_version=1, kind='child_failure', version='card_selection_v1',
                                   session_nonce=N, parent_ordinal=1, outcome='uncertain')
        script = Script(rows)
        actions = iter(['choose:0', 'select:1', 'select:0', 'confirm'])
        result = run(script, provider=lambda _: next(actions))
        self.assertEqual(result['code'], 'uncertain_action')
        self.assertEqual((result['child_attempted'], result['child_accepted'], result['child_reconciled']), (3, 2, 2))
        self.assertEqual(sum(method == 'POST' for method, _, _ in script.calls), 4)

    def test_removal_descriptor_stays_immutable_in_provider_and_is_absent_from_posts(self):
        rows = removal(1, 3, (2,), explicit=True)
        script = Script(rows)
        actions = iter(value['payload']['action_id'] for method, value in rows if method == 'POST')
        def provider(view):
            if view.child:
                self.assertEqual(view.child['operation'], 'remove')
                with self.assertRaises(TypeError):
                    view.child['min_select'] = 0
            return next(actions)
        result = run(script, provider=provider)
        self.assertEqual(result['status'], 'resolved')
        for method, _, body in script.calls:
            if method == 'POST' and body['child']:
                self.assertEqual(tuple(body['child']), ('ordinal', 'parent_decision_id', 'parent_action_id'))


    def test_upgrade_then_removal_share_parent_without_descriptor_leakage(self):
        rows = upgrade()[:7]
        def remap(value):
            if isinstance(value, dict):
                return {key: remap(item) for key, item in value.items()}
            if isinstance(value, list):
                return [remap(item) for item in value]
            return D[4] if value == D[0] else value
        for method, original in removal():
            value = remap(original)
            if value['child'] is not None:
                value['child']['ordinal'] = 2
            if value['parent'] is not None:
                p = value['parent']
                p['prior_results'] = [prior(result='child_completed')] + p['prior_results']
                p['parent_attempted'] += 1
                p['parent_accepted'] += 1
                p['parent_reconciled'] += 1
                p['child_episodes'] += 1
                p['child_attempted'] += 2
                p['child_accepted'] += 2
                p['child_reconciled'] += 2
                p['total_attempted'] += 3
                p['effects'] = 'unverified'
                if p['status'] == 'ready' and p['phase'] == 'choose_option':
                    p['candidates'][0]['stable_id'] = 'REMOVAL.OPTION'
            rows.append((method, value))
        result, script = drive(rows)
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual((result['parent_accepted'], result['parent_reconciled'], result['child_episodes']), (3, 3, 2))
        self.assertEqual((result['child_attempted'], result['child_accepted'], result['child_reconciled']), (5, 5, 5))
        self.assertEqual(result['total_attempted'], 8)
        self.assertFalse(script.rows)


if __name__ == '__main__':
    unittest.main()
