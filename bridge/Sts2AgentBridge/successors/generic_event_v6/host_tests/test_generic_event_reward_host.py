"""Reward mode-specific completion, exact selected sets, and shared host lifetime."""
from __future__ import annotations
import copy
import unittest

from test_generic_event_host import D, N, Script, card, child, env, host, parent, prior, receipt, run, upgrade
from test_generic_event_removal_host import drive, removal


def reward(minimum=1, maximum=2, slots=(1, 0), mode='auto_at_max', domain=None):
    domain = maximum + 1 if domain is None else domain
    descriptor = dict(child(), operation='add', min_select=minimum, max_select=maximum,
                      commit_mode=mode, domain_count=domain)
    actions = [f'select:{slot}' for slot in slots] + (['confirm'] if mode == 'explicit_confirm' else [])
    rows = [('GET', env(parent=parent())), ('POST', receipt())]
    selected, history = set(), []
    for index, action in enumerate(actions):
        decision = '%064x' % (2500 + index)
        legal = [f'select:{i}' for i in range(domain) if i not in selected] if len(selected) < maximum else []
        if mode == 'explicit_confirm' and minimum <= len(selected) <= maximum:
            legal.append('confirm')
        payload = dict(schema_version=1, kind='child_observation', version='card_selection_v1',
                       session_nonce=N, parent_ordinal=1, status='ready', phase='selecting',
                       operation='add', commit_mode=mode, min_select=minimum, max_select=maximum,
                       decision_id=decision, candidates=[card(i, i in selected) for i in range(domain)],
                       selected_slots=sorted(selected), legal_actions=legal, prior_results=list(history))
        rows.append(('GET', env(parent=parent('child', pa=1, ce=1, ca=index, cr=max(0, index - 1)),
                                child=dict(descriptor), payload=payload)))
        rows.append(('POST', receipt(decision, dict(descriptor), action)))
        history.append(dict(decision_id=decision, action_id=action,
                            result='selected' if action.startswith('select:') else 'committed'))
        if action.startswith('select:'):
            selected.add(int(action[7:]))
    total = len(actions)
    resolved = dict(schema_version=1, kind='child_resolved', version='card_selection_v1',
                    session_nonce=N, parent_ordinal=1, status='resolved', phase='complete', operation='add',
                    selected_cards=[card(i, True) for i in sorted(selected)], prior_results=history)
    rows.append(('GET', env(parent=parent('child', pa=1, ce=1, ca=total, cr=total - 1),
                            child=dict(descriptor), payload=resolved)))
    completed = [prior(result='child_completed')]
    rows.extend([('GET', env(parent=parent(decision=D[1], history=completed, pa=1, pr=1,
                                         ce=1, ca=total, cr=total, proceed=True))),
                 ('POST', receipt(D[1])),
                 ('GET', env(parent=parent('complete', history=completed + [prior(D[1], 'map_handoff')],
                                          pa=2, pr=2, ce=1, ca=total, cr=total)))])
    return rows


def mixed():
    rows, history, offset = [], [], 0
    sources = [upgrade(), removal(), reward(), reward(1, 3, (2,), 'explicit_confirm')]
    for ordinal, source in enumerate(sources, 1):
        mapping = {D[0]: '%064x' % (3000 + ordinal)}
        # Every publication remains unique across child episodes and families.
        for method, value in source:
            if method == 'POST' and value['child']:
                old = value['payload']['decision_id']
                mapping[old] = '%064x' % (4000 + len(mapping) + ordinal * 20)
        def remap(value):
            if isinstance(value, dict): return {k: remap(v) for k, v in value.items()}
            if isinstance(value, list): return [remap(v) for v in value]
            return mapping.get(value, value) if isinstance(value, str) else value
        for method, original in source[:-3]:
            value = remap(original)
            if value['child']:
                value['child']['ordinal'] = ordinal
            if value['parent']:
                p = value['parent']
                p['prior_results'] = list(history)
                p['completed_card_children'] = sum(row['result'] == 'child_completed' for row in history)
                for key in ('parent_attempted', 'parent_accepted', 'parent_reconciled', 'child_episodes'):
                    p[key] += ordinal - 1
                for key in ('child_attempted', 'child_accepted', 'child_reconciled'):
                    p[key] += offset
                p['total_attempted'] += ordinal - 1 + offset
                if p['total_attempted']: p['effects'] = 'unverified'
                if p['status'] == 'ready': p['candidates'][0]['stable_id'] = 'FAMILY.OPTION.%d' % ordinal
            rows.append((method, value))
        offset += sum(method == 'POST' and value['child'] is not None for method, value in source)
        history.append(prior(mapping[D[0]], 'child_completed'))
    final = '%064x' % 9000
    rows.extend([('GET', env(parent=parent(decision=final, history=history, pa=4, pr=4, ce=4,
                                         ca=offset, cr=offset, proceed=True))),
                 ('POST', receipt(final)),
                 ('GET', env(parent=parent('complete', history=history + [prior(final, 'map_handoff')],
                                          pa=5, pr=5, ce=4, ca=offset, cr=offset)))])
    return rows


class RewardHostTests(unittest.TestCase):
    def test_fixed_counts_one_through_eight_both_modes_reverse_selection(self):
        for count in range(1, 9):
            for mode in ('auto_at_max', 'explicit_confirm'):
                with self.subTest(count=count, mode=mode):
                    result, script = drive(reward(count, count, tuple(reversed(range(count))), mode))
                    self.assertEqual(result['status'], 'resolved', result)
                    total = count + (mode == 'explicit_confirm')
                    self.assertEqual((result['child_attempted'], result['child_accepted'], result['child_reconciled']), (total,) * 3)
                    self.assertFalse(script.rows)

    def test_variable_auto_minimum_does_not_enable_early_commit(self):
        result, script = drive(reward(1, 4, (3, 1, 2, 0)))
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual([body['action_id'] for method, _, body in script.calls if method == 'POST' and body['child']],
                         ['select:3', 'select:1', 'select:2', 'select:0'])
        self.assertEqual(result['child_reconciled'], 4)

    def test_variable_explicit_can_confirm_at_min_intermediate_or_max(self):
        for slots in ((3, 0), (3, 1, 0), (3, 1, 2, 0)):
            with self.subTest(slots=slots):
                result, _ = drive(reward(2, 4, slots, 'explicit_confirm'))
                self.assertEqual(result['status'], 'resolved', result)
                self.assertEqual(result['child_reconciled'], len(slots) + 1)

    def test_auto_completion_below_max_rejects_even_with_matching_history(self):
        result, _ = drive(reward(1, 3, (0,)))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual((result['child_accepted'], result['child_reconciled']), (1, 0))

    def test_auto_never_accepts_confirm_or_preview_publication(self):
        for action in ('confirm', 'preview'):
            rows = reward(1, 3, (0, 1, 2))
            rows[4][1]['payload']['legal_actions'].append(action)
            result, _ = drive(rows)
            self.assertEqual(result['code'], 'invalid_response')
            self.assertEqual(result['child_attempted'], 1)

    def test_explicit_never_accepts_preview_or_confirm_below_minimum(self):
        for action in ('confirm', 'preview'):
            rows = reward(2, 3, (0, 1), 'explicit_confirm')
            rows[4][1]['payload']['legal_actions'].append(action)
            result, _ = drive(rows)
            self.assertEqual(result['code'], 'invalid_response')
            self.assertEqual(result['child_attempted'], 1)

    def test_explicit_requires_confirm_even_when_selection_hits_max(self):
        rows = reward(2, 2, (1, 0))
        for _, value in rows:
            if value['child']: value['child']['commit_mode'] = 'explicit_confirm'
            if value['payload'] and value['payload'].get('kind') == 'child_observation':
                value['payload']['commit_mode'] = 'explicit_confirm'
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_accepted'], 2)

    def test_auto_cannot_invent_committed_history_for_final_select(self):
        rows = reward()
        rows[-4][1]['payload']['prior_results'][-1]['result'] = 'committed'
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_descriptor_rejects_wrong_modes_counts_and_bool_types(self):
        for field, value in [('commit_mode', 'preview_confirm'), ('commit_mode', 'unknown'),
                             ('min_select', 0), ('min_select', True), ('max_select', True),
                             ('min_select', 3), ('max_select', 9), ('domain_count', 2),
                             ('domain_count', True), ('domain_count', 65), ('operation', 'transform')]:
            with self.subTest(field=field, value=value):
                rows = reward()
                rows[2][1]['child'][field] = value
                result, _ = drive(rows)
                self.assertEqual(result['code'], 'invalid_response')
                self.assertEqual(result['child_attempted'], 0)

    def test_descriptor_and_child_payload_must_agree_on_all_fields(self):
        for field, value in [('commit_mode', 'explicit_confirm'), ('operation', 'remove'),
                             ('min_select', 2), ('max_select', 3)]:
            rows = reward()
            rows[2][1]['payload'][field] = value
            self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_descriptor_cannot_switch_modes_mid_child(self):
        rows = reward()
        rows[4][1]['child']['commit_mode'] = 'explicit_confirm'
        rows[4][1]['payload']['commit_mode'] = 'explicit_confirm'
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_exact_original_shape_and_membership_required_on_resolution(self):
        for mutate in (lambda p: p.update(selected_cards=[card(0, True), card(0, True)]),
                       lambda p: p.update(selected_cards=[card(0, True), card(2, True)]),
                       lambda p: p['selected_cards'][0].update(key='SUBSTITUTED'),
                       lambda p: p['selected_cards'][0].update(upgrade_level=1),
                       lambda p: p.update(operation='remove')):
            rows = reward()
            mutate(rows[-4][1]['payload'])
            self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_reconciled_selection_cannot_disappear_or_change(self):
        rows = reward()
        p = rows[4][1]['payload']
        p['selected_slots'] = [0]
        p['candidates'] = [card(0, True), card(1), card(2)]
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_candidate_shape_drift_rejects_before_next_select(self):
        rows = reward()
        rows[4][1]['payload']['candidates'][2]['key'] = 'SUBSTITUTED'
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 1)

    def test_lost_final_auto_select_or_explicit_confirm_is_not_retried(self):
        for mode in ('auto_at_max', 'explicit_confirm'):
            rows = reward(mode=mode)
            rows[-5] = ('POST', host.TransportFailure())
            script = Script(rows)
            actions = iter(['choose:0', 'select:1', 'select:0'] + (['confirm'] if mode == 'explicit_confirm' else []))
            result = run(script, provider=lambda _: next(actions))
            total = 2 + (mode == 'explicit_confirm')
            self.assertEqual(result['code'], 'transport_failure', result)
            self.assertEqual((result['child_attempted'], result['child_accepted'], result['child_reconciled']),
                             (total, total - 1, total - 1))
            self.assertEqual(result['effects'], 'unverified')
            self.assertEqual(sum(method == 'POST' for method, _, _ in script.calls), total + 1)

    def test_missing_or_wrong_effect_never_marks_child_completed(self):
        for mode in ('auto_at_max', 'explicit_confirm'):
            rows = reward(mode=mode)
            total = 2 + (mode == 'explicit_confirm')
            rows[-4] = ('GET', env(parent=parent('unsupported', pa=1, ce=1, ca=total, cr=total - 1)))
            result, _ = drive(rows)
            self.assertEqual(result['code'], 'unsupported_state')
            self.assertEqual(result['parent_reconciled'], 0)
            self.assertEqual(result['child_reconciled'], total - 1)
            self.assertEqual(result['effects'], 'unverified')

    def test_auto_resolution_can_follow_waiting_after_selector_closes(self):
        rows = reward()
        waiting = copy.deepcopy(rows[-4][1])
        p = waiting['payload']
        waiting['payload'] = dict(schema_version=1, kind='child_observation', version='card_selection_v1',
                                  session_nonce=N, parent_ordinal=1, status='waiting', phase='submitted',
                                  operation='', commit_mode='', min_select=0, max_select=0, decision_id='',
                                  candidates=[], selected_slots=[], legal_actions=[], prior_results=p['prior_results'])
        rows.insert(len(rows) - 4, ('GET', waiting))
        result, _ = drive(rows)
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual(result['child_reconciled'], 2)

    def test_provider_sees_immutable_reward_descriptor_and_posts_only_lineage(self):
        rows = reward(1, 3, (2,), 'explicit_confirm')
        script = Script(rows)
        actions = iter(value['payload']['action_id'] for method, value in rows if method == 'POST')
        def provider(view):
            if view.child:
                self.assertEqual(view.child['operation'], 'add')
                with self.assertRaises(TypeError): view.child['commit_mode'] = 'auto_at_max'
            return next(actions)
        result = run(script, provider=provider)
        self.assertEqual(result['status'], 'resolved')
        for method, _, body in script.calls:
            if method == 'POST' and body['child']:
                self.assertEqual(tuple(body['child']), ('ordinal', 'parent_decision_id', 'parent_action_id'))

    def test_upgrade_removal_auto_add_explicit_add_share_one_lifetime(self):
        result, script = drive(mixed())
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual((result['parent_attempted'], result['parent_reconciled'], result['child_episodes']), (5, 5, 4))
        self.assertEqual((result['child_attempted'], result['child_accepted'], result['child_reconciled']), (9, 9, 9))
        self.assertEqual(result['total_attempted'], 14)
        self.assertFalse(script.rows)


if __name__ == '__main__':
    unittest.main()
