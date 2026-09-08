"""G4 fixed multi-upgrade and cumulative evidence, independent scripted responses."""
import copy
import unittest
from test_generic_event_host import D, Script, env, host, parent, receipt, run, sequential_upgrades, upgrade
from test_generic_event_removal_host import removal, drive


def multi_upgrade(count):
    rows = removal(count, count, tuple(reversed(range(count))))
    for _, value in rows:
        if value['child'] is not None:
            value['child']['operation'] = 'upgrade'
        if value['payload'] is not None and 'operation' in value['payload']:
            value['payload']['operation'] = 'upgrade'
    return rows


class CompletionHostTests(unittest.TestCase):
    def test_fixed_one_through_eight_upgrade_reverse_order(self):
        for count in range(1, 9):
            result, script = drive(multi_upgrade(count))
            self.assertEqual(result['status'], 'resolved', result)
            self.assertEqual(result['child_attempted'], count + 1)
            self.assertEqual(result['completed_card_children'], 1)
            self.assertEqual(result['effects'], 'unverified')
            self.assertFalse(script.rows)

    def test_upgrade_variable_counts_and_mismatched_transform_payload_reject(self):
        for field, value in [('min_select', 1), ('max_select', 3), ('operation', 'transform')]:
            rows = multi_upgrade(2)
            rows[2][1]['child'][field] = value
            result, script = drive(rows)
            self.assertEqual(result['code'], 'invalid_response')
            self.assertEqual(result['child_attempted'], 0)

    def test_multi_upgrade_cannot_preview_below_max(self):
        rows = multi_upgrade(2)
        rows[4][1]['payload']['phase'] = 'preview'
        rows[4][1]['payload']['legal_actions'] = ['confirm']
        result, _ = drive(rows)
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['completed_card_children'], 0)

    def test_multi_upgrade_cannot_advertise_preview_at_max_selecting(self):
        rows = multi_upgrade(2)
        rows[6][1]['payload']['phase'] = 'selecting'
        rows[6][1]['payload']['legal_actions'] = ['preview']
        self.assertEqual(drive(rows)[0]['code'], 'invalid_response')

    def test_precise_terminal_envelope_lag_then_proceed(self):
        rows = upgrade()
        self.assertEqual(rows[6][1]['parent']['completed_card_children'], 0)
        self.assertEqual(rows[7][1]['parent']['completed_card_children'], 1)
        result = run(Script(rows))
        self.assertEqual(result['completed_card_children'], 1)
        self.assertEqual(result['effects'], 'unverified')

    def test_invalid_counts_before_any_child_never_dispatch(self):
        for value in (-1, 1, 5, True, '0', None):
            rows = upgrade()
            rows[0][1]['parent']['completed_card_children'] = value
            script = Script(rows)
            result = run(script)
            self.assertEqual(result['code'], 'invalid_response')
            self.assertEqual(result['parent_attempted'], 0)
            self.assertEqual(result['completed_card_children'], 0)

    def test_terminal_payload_cannot_credit_parent_snapshot_early(self):
        rows = upgrade()
        rows[6][1]['parent']['completed_card_children'] = 1
        result = run(Script(rows))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['completed_card_children'], 0)

    def test_next_snapshot_cannot_regress_or_skip_count(self):
        for index, value in ((7, 0), (7, 2), (9, 0)):
            rows = upgrade()
            rows[index][1]['parent']['completed_card_children'] = value
            result = run(Script(rows))
            self.assertEqual(result['code'], 'invalid_response')
            self.assertEqual(result['completed_card_children'], 1)

    def test_lost_or_malformed_terminal_payload_earns_no_credit(self):
        for malformed in (False, True):
            rows = upgrade()
            if malformed:
                rows[6][1]['payload']['selected_cards'][0]['key'] = 'FOREIGN'
            else:
                rows[6] = ('GET', host.TransportFailure())
            result = run(Script(rows))
            self.assertEqual(result['completed_card_children'], 0)
            self.assertEqual(result['code'], 'invalid_response' if malformed else 'transport_failure')

    def test_repeated_resolved_child_never_double_credits(self):
        rows = upgrade()[:7]
        duplicate = copy.deepcopy(rows[-1][1])
        duplicate['parent']['completed_card_children'] = 1
        rows.append(('GET', duplicate))
        result = run(Script(rows))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['completed_card_children'], 1)

    def test_cleanup_failure_retains_one_latest_unreconciled_child(self):
        value = parent('unsupported', pa=1, ce=1, ca=2, cr=2)
        value['completed_card_children'] = 1
        result = run(Script(upgrade()[:7] + [('GET', env(parent=value))]))
        self.assertEqual(result['code'], 'unsupported_state')
        self.assertEqual(result['completed_card_children'], 1)
        self.assertEqual(result['parent_reconciled'], 0)

    def test_ready_cannot_skip_completed_parent_history(self):
        rows = upgrade()
        rows[7][1]['parent']['prior_results'] = []
        rows[7][1]['parent']['parent_reconciled'] = 0
        result = run(Script(rows))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(result['completed_card_children'], 1)
        self.assertEqual(result['parent_attempted'], 1)

    def test_lost_or_uncertain_proceed_preserves_verified_child(self):
        for value, code in ((host.TransportFailure(), 'transport_failure'),
                            (receipt(D[1], outcome='uncertain'), 'uncertain_action')):
            script = Script(upgrade()[:8] + [('POST', value)])
            result = run(script)
            self.assertEqual(result['code'], code)
            self.assertEqual(result['completed_card_children'], 1)
            self.assertEqual(result['parent_attempted'], 2)
            self.assertEqual(result['effects'], 'unverified')
            self.assertEqual(len(script.calls), 9)

    def test_four_completed_children_accumulate_without_reset(self):
        result = run(Script(sequential_upgrades(4)))
        self.assertEqual(result['status'], 'resolved', result)
        self.assertEqual(result['completed_card_children'], 4)

    def test_no_attempt_failure_has_zero_completed_children(self):
        self.assertEqual(host.run_event(lambda *args: None, provider=None)['completed_card_children'], 0)
