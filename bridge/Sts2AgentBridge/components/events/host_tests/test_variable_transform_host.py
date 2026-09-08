"""Variable transform V2 descriptors and explicit-preview history boundaries."""
import copy
import unittest
from test_generic_event_host import host, Script, run
from test_generic_event_removal_host import removal, drive


def variable(minimum=1, maximum=3, slots=(0,), explicit=None):
    rows = removal(minimum, maximum, slots, len(slots) < maximum if explicit is None else explicit)
    for _, value in rows:
        if value['child'] is not None:
            value['child']['operation'] = 'transform'
            value['child']['contract_version'] = 'card_transform_v2'
            value['payload']['version'] = 'card_transform_v2'
            if value['payload'].get('operation'):
                value['payload']['operation'] = 'transform'
    return rows


class VariableTransformHostTests(unittest.TestCase):
    def test_minimum_intermediate_maximum_at_every_positive_bound(self):
        for minimum in range(1, 9):
            for maximum in range(minimum, 9):
                for count in set((minimum, (minimum + maximum) // 2, maximum)):
                    with self.subTest(minimum=minimum, maximum=maximum, count=count):
                        result, script = drive(variable(minimum, maximum, tuple(reversed(range(count)))))
                        self.assertEqual(result['status'], 'resolved', result)
                        self.assertEqual(result['child_attempted'], count + (2 if count < maximum else 1))
                        self.assertEqual((result['completed_card_children'], result['completed_item_children']), (1, 0))
                        self.assertEqual(result['effects'], 'unverified')
                        self.assertFalse(script.rows)

    def test_each_transform_envelope_rejects_frozen_v1_tag(self):
        for index in range(2, 9):
            rows = variable()
            rows[index][1]['payload']['version'] = 'card_transform_v1'
            result, script = drive(rows)
            self.assertEqual(result['code'], 'invalid_response', (index, result))
            self.assertEqual(result['completed_card_children'], 0)
            self.assertEqual(len(script.calls), index + 1)

    def test_outer_descriptor_v1_cannot_select_new_parser(self):
        rows = variable()
        rows[2][1]['child']['contract_version'] = 'card_transform_v1'
        result, script = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 0)
        self.assertEqual(len(script.calls), 3)

    def test_early_open_requires_received_preview_action(self):
        rows = variable(2, 4, (2, 0))
        payload = rows[6][1]['payload']
        payload.update(phase='preview', legal_actions=['confirm'])
        result, script = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['child_attempted'], 2)
        self.assertEqual(len(script.calls), 7)
        parser = host._load_transform()
        with self.assertRaises(parser._InvalidResponse):
            parser._validate_envelope(payload)

    def test_preview_below_minimum_and_selection_after_preview_stop(self):
        rows = variable(2, 4, (2, 0))
        rows[4][1]['payload']['legal_actions'].append('preview')
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')
        rows = variable()
        p = rows[6][1]['payload']
        p.update(phase='selecting', legal_actions=['select:1', 'select:2', 'select:3', 'preview'])
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_changed_counts_membership_and_final_originals(self):
        for target, field, value in [('child', 'min_select', 2), ('child', 'max_select', 4), ('child', 'domain_count', 5),
                                     ('payload', 'min_select', 2), ('payload', 'max_select', 4), ('payload', 'selected_slots', [1])]:
            rows = variable()
            rows[6][1][target][field] = value
            self.assertEqual(drive(rows)[0]['code'], 'invalid_response')
        rows = variable()
        rows[-4][1]['payload']['selected_cards'][0]['slot'] = 1
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['completed_card_children'], 0)

    def test_lost_and_uncertain_preview_or_final_response_never_retried(self):
        for action in ('preview', 'confirm'):
            for uncertain in (False, True):
                rows = variable()
                actions = iter([v['payload']['action_id'] for m, v in rows if m == 'POST'])
                index = next(i for i, (m, v) in enumerate(rows) if m == 'POST' and v['payload']['action_id'] == action)
                if uncertain:
                    p = rows[index][1]['payload']
                    rows[index][1]['payload'] = {k: p[k] for k in ('schema_version', 'kind', 'version', 'session_nonce', 'parent_ordinal')}
                    rows[index][1]['payload'].update(kind='child_failure', outcome='uncertain')
                else:
                    rows[index] = ('POST', host.TransportFailure())
                script = Script(rows)
                result = run(script, provider=lambda _: next(actions))
                self.assertEqual(result['code'], 'uncertain_action' if uncertain else 'transport_failure', result)
                self.assertEqual(result['completed_card_children'], 0)
                self.assertEqual(result['child_attempted'], 2 if action == 'preview' else 3)
                self.assertEqual(len(script.calls), index + 1)

    def test_fault_failure_wrong_version_is_invalid(self):
        for version, expected in [('card_transform_v2', 'unsupported_state'), ('card_transform_v1', 'invalid_response')]:
            rows = variable()
            p = rows[-4][1]['payload']
            rows[-4][1]['payload'] = dict(schema_version=1, kind='child_observation', version=version,
                session_nonce=p['session_nonce'], parent_ordinal=1, status='unsupported', phase='unsupported',
                operation='', commit_mode='', min_select=0, max_select=0, decision_id='', candidates=[], selected_slots=[], legal_actions=[], prior_results=p['prior_results'])
            result, _ = drive(rows)
            self.assertEqual(result['code'], expected, result)
            self.assertEqual(result['completed_card_children'], 0)
