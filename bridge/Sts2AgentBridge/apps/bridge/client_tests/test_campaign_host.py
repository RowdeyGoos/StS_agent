"""Synthetic campaign continuity, route, budget and uncertain-input regressions."""
from copy import deepcopy
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).absolute().parents[1] / 'client'))
import campaign_host as host
import reward_host
import run_live
from test_reward_host import RewardWire


class Clock:
    def __init__(self): self.now = 0.
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


def view(surface='event', act=0, floor=0, **changes):
    return dict(schema_version=1, protocol='campaign_v2', status='ready', surface=surface,
                run_id='a'*32, act_index=act, floor=floor, character='ironclad', ascension=0,
                room_kind='boss' if surface == 'combat' else 'event', hp=10000, max_hp=10000,
                decision_id=None, legal_actions=[], completed_decision_id=None, **changes)


class CampaignWire:
    def __init__(self):
        self.value = view()
        self.map_complete = None
        self.posts, self.buffers, self.calls = [], [], []
        self.mode = 'ok'
        self.corrupt = lambda v: v
        self.clock = Clock()
        self.combat = SimpleNamespace(run_combat=self.fight)
        self.rewards = SimpleNamespace(run_rewards=self.loot)
        self.events = SimpleNamespace(run_event=self.event, first_legal=lambda _: 'choose:0')

    def fight(self, request, **kwargs):
        assert kwargs['campaign'] is True
        self.value.update(surface='rewards')
        return dict(status='resolved', outcome='victory', attempted=9, accepted=9, reconciled=9)

    def loot(self, request, **kwargs):
        assert kwargs['campaign'] is True
        act = self.value['act_index']
        if act == 2:
            self.value.update(surface='event')
        else:
            self.value.update(surface='map', act_index=act+1, floor=self.value['floor']+1)
        return dict(status='resolved', destination='ending' if act == 2 else 'act', attempted=4, accepted=4, reconciled=4)

    def event(self, request, **kwargs):
        won = self.mode == 'early_victory' or self.value['act_index'] == 2
        self.value.update(surface='map')
        return dict(status='resolved', destination='run_won' if won else 'map_handoff',
                    parent_attempted=1, parent_accepted=1, parent_reconciled=1)

    def request(self, method, route, body=None):
        self.calls.append((method, route))
        if route == host.READ:
            result = self.corrupt(deepcopy(self.value))
        elif method == 'POST':
            action = json.loads(body)
            self.posts.append(action)
            self.buffers.append(body)
            assert route == host.maps._MAP_ACTION_ROUTE
            self.map_complete = dict(candidate_index=0, col=1, row=1, kind='boss')
            self.value.update(surface='combat', room_kind='boss', floor=self.value['floor']+1)
            if self.mode == 'lost_receipt': raise OSError('lost receipt')
            result = dict(schema_version=1, status='accepted', mutation_state='applied', **action, reason='accepted')
        elif route == host.maps._MAP_DECISION_ROUTE:
            if self.map_complete:
                if self.mode == 'lost_reconciliation': raise OSError('lost read')
                result = dict(schema_version=1, status='complete', decision_kind='map', actionable=False,
                              decision_id=None, screen_kind='room', destination=self.map_complete, candidates=[], legal_actions=[])
                if self.mode == 'wrong_destination': result['destination'] = dict(self.map_complete, col=2)
                self.map_complete = None
            else:
                result = dict(schema_version=1, status='ready', decision_kind='map', actionable=True,
                              decision_id=format(self.value['act_index']+1, '064x'), screen_kind='map', destination=None,
                              candidates=[dict(candidate_index=0, col=1, row=1, kind='boss')],
                              legal_actions=[dict(action_id='select:0', kind='select_map_node', candidate_index=0)])
        else:
            raise AssertionError(route)
        buffer = bytearray(json.dumps(result, separators=(',', ':')).encode())
        self.buffers.append(buffer)
        return buffer

    def run(self, **options):
        result = host.run_campaign(self.request, None, combat=self.combat, rewards=self.rewards, events=self.events,
                                   shop=None, items=None, setup='controlled_extra_hp', clock=self.clock, sleep=self.clock.sleep, **options)
        assert all(not any(b) for b in self.buffers)
        return result


class CampaignTests(unittest.TestCase):
    def test_failed_combat_preserves_all_nested_choice_counts_and_bounded_details(self):
        wire = CampaignWire()
        choices = [dict(status='resolved', code=None, native_code=None, pile='draw', attempted=1, accepted=1,
                        reconciled=1, selected_count=1, choice_id='omit-this'),
                   dict(status='failed', code='native_choice_failed', native_code='choice_identity_changed',
                        pile='exhaust', attempted=1, accepted=1, reconciled=0, selected_count=0)]
        wire.combat = SimpleNamespace(run_combat=lambda *a, **k: dict(status='failed', code='combat_choice_failed',
            outcome=None, attempted=21, accepted=21, reconciled=20, choices=choices))
        result = wire.run()
        stage = result['stages'][-1]
        self.assertEqual((stage['attempted'], stage['accepted'], stage['reconciled']), (21, 21, 20))
        self.assertEqual((stage['child_attempted'], stage['child_accepted'], stage['child_reconciled']), (2, 2, 1))
        self.assertEqual(stage['choices'][1]['native_code'], 'choice_identity_changed')
        self.assertNotIn('choice_id', stage['choices'][0])
        self.assertEqual(result['code'], 'combat_choice_failed')

    def test_full_three_act_traversal_needs_witnessed_bosses_and_ending(self):
        wire = CampaignWire()
        result = wire.run()
        self.assertEqual((result['status'], result['outcome'], result['bosses_defeated']), ('resolved', 'victory', [0, 1, 2]), result)
        self.assertEqual(len(wire.posts), 3)
        self.assertEqual(result['setup'], 'controlled_extra_hp')
        self.assertEqual(result['entry_mode'], 'fresh')
        self.assertTrue(result['full_campaign_verified'])
        self.assertEqual([s['destination'] for s in result['stages'] if s['surface'] == 'rewards'], ['act', 'act', 'ending'])

    def test_no_retry_or_false_reconciliation_after_lost_input(self):
        for mode, counts in [('lost_receipt', (1, 0, 0)), ('lost_reconciliation', (1, 1, 0)), ('wrong_destination', (1, 1, 0))]:
            with self.subTest(mode=mode):
                wire = CampaignWire(); wire.mode = mode
                result = wire.run()
                self.assertIsNone(result['outcome'])
                self.assertEqual(len(wire.posts), 1)
                last = result['stages'][-1]
                self.assertEqual(tuple(last[k] for k in ('attempted', 'accepted', 'reconciled')), counts)

    def test_ending_alone_does_not_certify_a_full_campaign(self):
        wire = CampaignWire(); wire.mode = 'early_victory'
        result = wire.run()
        self.assertEqual(result['code'], 'campaign_victory_coverage')
        self.assertIsNone(result['outcome'])
        self.assertEqual(wire.posts, [])

    def test_foreign_run_act_skip_and_wrong_profile_stop_before_next_input(self):
        for key, value in [('run_id', 'b'*32), ('act_index', 2), ('character', 'silent'), ('ascension', True)]:
            with self.subTest(key=key):
                wire = CampaignWire()
                wire.corrupt = lambda v: dict(v, **{key: value}) if v['floor'] else v
                result = wire.run()
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(len(wire.posts), 1)

    def test_late_entry_and_undeclared_extra_hp_fail_without_actions(self):
        for changes in (dict(floor=4), dict(act_index=1), dict(max_hp=80, hp=80)):
            wire = CampaignWire(); wire.value.update(changes)
            self.assertEqual(wire.run()['status'], 'failed')
            self.assertEqual(wire.posts, [])

    def test_resume_act_two_records_only_observed_segment(self):
        wire = CampaignWire(); wire.value = view('combat', act=1, floor=20)
        result = wire.run(entry_mode='resume')
        self.assertEqual((result['status'], result['outcome']), ('resolved', 'continued_victory'), result)
        self.assertEqual(result['entry_mode'], 'resume')
        self.assertEqual((result['entry']['act_index'], result['entry']['floor']), (1, 20))
        self.assertEqual(result['acts_observed'], [1, 2])
        self.assertEqual(result['bosses_defeated'], [1, 2])
        self.assertFalse(result['full_campaign_verified'])

    def test_resume_ending_does_not_infer_any_boss(self):
        wire = CampaignWire(); wire.value = view('event', act=2, floor=50)
        result = wire.run(entry_mode='resume')
        self.assertEqual(result['outcome'], 'continued_victory')
        self.assertEqual(result['acts_observed'], [2])
        self.assertEqual(result['bosses_defeated'], [])
        self.assertFalse(result['full_campaign_verified'])
        self.assertEqual(wire.posts, [])

    def test_resume_never_claims_full_campaign_even_from_first_room(self):
        result = CampaignWire().run(entry_mode='resume')
        self.assertEqual(result['outcome'], 'continued_victory')
        self.assertEqual(result['bosses_defeated'], [0, 1, 2])
        self.assertFalse(result['full_campaign_verified'])

    def test_resume_rejects_early_ending_and_preserves_defeat(self):
        wire = CampaignWire(); wire.value = view('event', act=1, floor=20); wire.mode = 'early_victory'
        result = wire.run(entry_mode='resume')
        self.assertEqual(result['code'], 'campaign_ending_context')
        self.assertIsNone(result['outcome'])
        self.assertEqual(wire.posts, [])
        wire = CampaignWire(); wire.value = view('combat', act=1, floor=20)
        wire.combat.run_combat = lambda *a, **k: dict(status='resolved', outcome='defeat')
        result = wire.run(entry_mode='resume')
        self.assertEqual(result['outcome'], 'defeat')
        self.assertFalse(result['full_campaign_verified'])

    def test_resume_keeps_run_act_and_floor_continuity_after_entry(self):
        for initial_act, key, value in [(1, 'run_id', 'b'*32), (1, 'floor', 19),
                                       (1, 'act_index', 0), (0, 'act_index', 2)]:
            with self.subTest(key=key, value=value):
                wire = CampaignWire(); wire.value = view('map', act=initial_act, floor=20)
                wire.corrupt = lambda v: dict(v, **{key: value}) if v['floor'] > 20 else v
                result = wire.run(entry_mode='resume')
                self.assertEqual(result['code'], 'campaign_continuity')
                self.assertEqual(len(wire.posts), 1)
                self.assertFalse(result['full_campaign_verified'])

    def test_resume_keeps_profile_hp_and_native_failure_guards(self):
        for changes in (dict(character='silent'), dict(ascension=1), dict(max_hp=80, hp=80),
                        dict(surface='overlay'), dict(status='unsupported')):
            wire = CampaignWire(); wire.value = dict(view('combat', act=1, floor=20), **changes)
            result = wire.run(entry_mode='resume')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(wire.posts, [])
        wire = CampaignWire()
        wire.corrupt = lambda _: dict(schema_version=1, protocol='campaign_v2', status='failed', code='campaign_context_failed')
        self.assertEqual(wire.run(entry_mode='resume')['code'], 'campaign_context_failed')
        self.assertEqual(wire.posts, [])

    def test_resume_accepts_native_ready_shop_without_broadening_fresh_entry(self):
        for entry_mode in ('fresh', 'resume'):
            wire = CampaignWire(); wire.value = view('shop', act=1, floor=20)
            campaign = host.Campaign(wire.request, None, combat=None, rewards=None, events=None,
                shop=None, items=None, setup='controlled_extra_hp', entry_mode=entry_mode,
                progress=None, clock=wire.clock, sleep=wire.clock.sleep)
            if entry_mode == 'fresh':
                with self.assertRaisesRegex(host.Stop, 'campaign_entry_required'): campaign.view()
            else:
                self.assertEqual(campaign.view()['surface'], 'shop')
                self.assertEqual(campaign.acts, {1})
                self.assertEqual(campaign.bosses, set())
            self.assertEqual(wire.posts, [])

    def test_campaign_entry_cli_rejects_wrong_capability_and_unknown_mode(self):
        common = ['--release-manifest', '/unused', '--release-sha256', 'a'*64,
                  '--expected-state-sha256', 'b'*64]
        with redirect_stderr(StringIO()):
            for suffix in (['--capability', 'combat', '--campaign-entry', 'resume'],
                           ['--capability', 'campaign', '--campaign-entry', 'resume'],
                           ['--capability', 'campaign', '--campaign-setup', 'normal_hp', '--campaign-entry', 'adopt']):
                with self.assertRaises(SystemExit) as error: run_live.parse_args(common + suffix)
                self.assertEqual(error.exception.code, 2)
        args = run_live.parse_args(common + ['--capability', 'campaign', '--campaign-setup', 'controlled_extra_hp', '--campaign-entry', 'resume'])
        self.assertEqual(args.campaign_entry, 'resume')

    def test_strict_schema_and_unknown_fields(self):
        for value in (dict(view(), schema_version=2), dict(view(), schema_version=True), dict(view(), secret=1)):
            with self.assertRaises(host.Stop): host.validate_view(value)

    def test_true_defeat_remains_defeat(self):
        wire = CampaignWire()
        wire.combat = SimpleNamespace(run_combat=lambda *a, **k: dict(status='resolved', outcome='defeat', attempted=1, accepted=1, reconciled=1))
        result = wire.run()
        self.assertEqual((result['status'], result['outcome'], result['bosses_defeated']), ('resolved', 'defeat', []))

    def test_global_post_budget_does_not_reset_for_a_later_room(self):
        wire = CampaignWire()
        original = host.MAX_POSTS
        try:
            host.MAX_POSTS = 1
            result = wire.run()
        finally:
            host.MAX_POSTS = original
        self.assertEqual(result['code'], 'campaign_post_limit')
        self.assertEqual(len(wire.posts), 1)
        self.assertEqual(result['stages'][-1]['attempted'], 0)

    def test_late_valid_receipt_keeps_known_acceptance(self):
        wire = CampaignWire()
        original = wire.request
        def request(method, route, body=None):
            response = original(method, route, body)
            if method == 'POST':
                wire.clock.now = host.MAX_SECONDS + 1
            return response
        wire.request = request
        result = wire.run()
        self.assertEqual(result['code'], 'campaign_timeout')
        self.assertEqual(tuple(result['stages'][-1][k] for k in ('attempted', 'accepted', 'reconciled')), (1, 1, 0))

    def test_child_counters_survive_global_deadline(self):
        for status, expected_code in [('failed', 'combat_timeout'), ('resolved', 'campaign_timeout')]:
            with self.subTest(status=status):
                wire = CampaignWire()
                def late_fight(*args, **kwargs):
                    wire.clock.now = host.MAX_SECONDS + 1
                    return dict(status=status, code='combat_timeout' if status == 'failed' else None,
                                outcome=None if status == 'failed' else 'victory',
                                attempted=7, accepted=6, reconciled=5)
                wire.combat = SimpleNamespace(run_combat=late_fight)
                result = wire.run()
                self.assertEqual((result['status'], result['code']), ('failed', expected_code))
                stage = result['stages'][-1]
                self.assertEqual(stage['surface'], 'combat')
                self.assertEqual(tuple(stage[k] for k in ('attempted', 'accepted', 'reconciled')), (7, 6, 5))

    def test_event_combat_has_its_own_stage_and_checks_budget_before_start(self):
        for destination in ('combat_handoff', 'combat_resume_handoff'):
            for limited in (False, True):
                with self.subTest(destination=destination, limited=limited):
                    wire = CampaignWire()
                    wire.events.run_event = lambda *a, **k: dict(status='resolved', destination=destination,
                        session_nonce='a'*32, parent_attempted=1, parent_accepted=1, parent_reconciled=1)
                    fights = []
                    def broken_fight(*args, **kwargs):
                        fights.append(kwargs)
                        raise host.Stop('combat_input_uncertain')
                    wire.combat = SimpleNamespace(run_combat=broken_fight)
                    with patch.object(host, 'MAX_STAGES', 1 if limited else 320):
                        result = wire.run()
                    self.assertEqual(result['code'], 'campaign_stage_limit' if limited else 'combat_input_uncertain')
                    self.assertEqual(len(fights), 0 if limited else 1)
                    self.assertEqual(len(result['stages']), 1 if limited else 2)
                    if not limited:
                        self.assertEqual((result['stages'][-1]['surface'], result['stages'][-1]['status']), ('event_combat', 'failed'))

    def test_event_combat_preserves_late_child_evidence(self):
        for destination in ('combat_handoff', 'combat_resume_handoff'):
            wire = CampaignWire()
            wire.events.run_event = lambda *a, **k: dict(status='resolved', destination=destination, session_nonce='a'*32)
            def late_fight(*args, **kwargs):
                wire.clock.now = host.MAX_SECONDS + 1
                return dict(status='failed', code='combat_timeout', attempted=3, accepted=2, reconciled=1)
            wire.combat = SimpleNamespace(run_combat=late_fight)
            result = wire.run()
            self.assertEqual(result['code'], 'combat_timeout')
            self.assertEqual([stage['surface'] for stage in result['stages']], ['event', 'event_combat'])
            self.assertEqual(tuple(result['stages'][-1][k] for k in ('attempted', 'accepted', 'reconciled')), (3, 2, 1))

    def test_campaign_reward_handoffs_use_v2_and_legacy_rejects_them(self):
        for destination in ('act', 'ending'):
            for campaign in (True, False):
                wire = RewardWire(skip=True); clock = Clock()
                wire.corrupt = lambda v, m: dict(v, screen_kind=destination) if v.get('status') == 'complete' else v
                result = reward_host.run_rewards(wire.request, policy='skip-card', campaign=campaign, clock=clock, sleep=clock.sleep)
                self.assertEqual(result['status'], 'resolved' if campaign else 'failed', result)
                if campaign:
                    self.assertEqual(result['destination'], destination)
                    self.assertTrue(all('/reward-v2/' in route for _, route in wire.calls))
                self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_empty_final_boss_rewards_proceed_once_to_ending(self):
        wire = RewardWire(skip=True)
        wire.stage = 3
        wire.state['player']['gold'] = 113
        wire.state['rewards'] = []
        wire.state['legal_actions'] = [wire.state['legal_actions'][-1]]
        wire.waits = 2
        wire.corrupt = lambda v, m: dict(v, screen_kind='ending') if v.get('status') == 'complete' else v
        clock = Clock()
        result = reward_host.run_rewards(wire.request, policy='skip-card', campaign=True, clock=clock, sleep=clock.sleep)
        self.assertEqual((result['status'], result['destination']), ('resolved', 'ending'), result)
        self.assertEqual(tuple(result[k] for k in ('attempted', 'accepted', 'reconciled')), (1, 1, 1))
        self.assertEqual((wire.posts, result['claimed_gold'], result['selected_cards']), (1, 0, []))
        self.assertTrue(all('/reward-v2/' in route for _, route in wire.calls))
        self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_untouched_shop_uses_campaign_proceed_and_reconciles_exact_decision(self):
        for mode in ('ok', 'wrong_completion'):
            wire = CampaignWire()
            original_event, original_request = wire.event, wire.request
            def event(request, **kwargs):
                if wire.value['act_index'] == 0:
                    wire.value.update(surface='shop', decision_id='c'*64, legal_actions=['proceed'])
                    return dict(status='resolved', destination='map_handoff')
                return original_event(request, **kwargs)
            def request(method, route, body=None):
                if route != host.ACTION:
                    return original_request(method, route, body)
                action = json.loads(body)
                self.assertEqual(action, dict(decision_id='c'*64, action_id='proceed'))
                wire.posts.append(action); wire.buffers.append(body)
                wire.value.update(surface='map', decision_id=None, legal_actions=[],
                                  completed_decision_id=('c' if mode == 'ok' else 'd')*64)
                receipt = bytearray(json.dumps(dict(schema_version=1, protocol='campaign_v2', status='accepted', **action)).encode())
                wire.buffers.append(receipt)
                return receipt
            wire.events.run_event = event
            wire.request = request
            result = wire.run()
            stage = next(s for s in result['stages'] if s['surface'] == 'shop')
            self.assertEqual((stage['attempted'], stage['accepted'], stage['reconciled']), (1, 1, 1 if mode == 'ok' else 0))
            self.assertEqual(result['outcome'], 'victory' if mode == 'ok' else None)

    def test_treasure_requires_two_explicit_owned_actions(self):
        for mode in ('ok', 'lost_open_receipt', 'wrong_open_completion', 'early_map', 'lost_skip_receipt', 'native_failure'):
            with self.subTest(mode=mode):
                wire = CampaignWire()
                original_event, original_request = wire.event, wire.request
                treasure_posts = []
                def event(request, **kwargs):
                    if wire.value['act_index'] == 0:
                        wire.value.update(surface='treasure', decision_id='c'*64, legal_actions=['open_chest'])
                        return dict(status='resolved', destination='map_handoff')
                    return original_event(request, **kwargs)
                def request(method, route, body=None):
                    if route != host.ACTION:
                        return original_request(method, route, body)
                    action = json.loads(body)
                    treasure_posts.append(action); wire.buffers.append(body)
                    opening = len(treasure_posts) == 1
                    self.assertEqual(action, dict(decision_id=('c' if opening else 'd')*64,
                                                  action_id='open_chest' if opening else 'skip_relic'))
                    if mode == ('lost_open_receipt' if opening else 'lost_skip_receipt'):
                        raise OSError('uncertain input')
                    if opening:
                        wire.value.update(surface='treasure', decision_id='d'*64, legal_actions=['skip_relic'],
                                          completed_decision_id=('e' if mode == 'wrong_open_completion' else 'c')*64)
                        if mode == 'early_map': wire.value.update(surface='map', decision_id=None, legal_actions=[])
                    else:
                        wire.value.update(surface='map', decision_id=None, legal_actions=[], completed_decision_id='d'*64)
                    value = (dict(schema_version=1, protocol='campaign_v2', status='failed', code='campaign_treasure_failed')
                             if mode == 'native_failure' else dict(schema_version=1, protocol='campaign_v2', status='accepted', **action))
                    receipt = bytearray(json.dumps(value).encode()); wire.buffers.append(receipt)
                    return receipt
                wire.events.run_event = event; wire.request = request
                result = wire.run()
                stages = [s for s in result['stages'] if s['surface'] == 'treasure']
                expected = [(1, 1, 1), (1, 1, 1)] if mode == 'ok' else (
                    [(1, 1, 1), (1, 0, 0)] if mode == 'lost_skip_receipt' else
                    [(1, 0, 0)] if mode in ('lost_open_receipt', 'native_failure') else [(1, 1, 0)])
                self.assertEqual([tuple(s[k] for k in ('attempted', 'accepted', 'reconciled')) for s in stages], expected)
                self.assertEqual(len(treasure_posts), len(expected))
                self.assertEqual(result['outcome'], 'victory' if mode == 'ok' else None)
                if mode == 'native_failure': self.assertEqual(result['code'], 'campaign_treasure_failed')

    def test_treasure_action_surface_and_failure_shape_are_strict(self):
        for surface, actions in [('treasure', ['proceed']), ('shop', ['open_chest']), ('treasure', ['open_chest', 'skip_relic'])]:
            with self.assertRaises(host.Stop):
                host.validate_view(dict(view(surface), decision_id='c'*64, legal_actions=actions))
        with self.assertRaisesRegex(host.Stop, '^campaign_treasure_failed$'):
            host.validate_view(dict(schema_version=1, protocol='campaign_v2', status='failed', code='campaign_treasure_failed'))
        with self.assertRaisesRegex(host.Stop, '^campaign_failure_shape$'):
            host.validate_view(dict(schema_version=1, protocol='campaign_v2', status='failed', code='arbitrary_native_text'))


if __name__ == '__main__':
    unittest.main()
