"""Deterministic host fixtures: no sockets, target assemblies or user data."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / 'host/event_orchestrator_host.py'
spec = importlib.util.spec_from_file_location('event_host_tested', PATH)
host = importlib.util.module_from_spec(spec); sys.modules[spec.name] = host; spec.loader.exec_module(host)
N = 'a' * 32


def parent(key='INITIAL', *, prior=None, policy='item_reward', text='Choose', proceed=False):
    if policy == 'cheese_gorge_add_two' and not proceed:
        key = 'ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE'
    c = dict(candidate_index=0, action_id='choose:0', stable_id='PROCEED' if proceed else key, rendered_text=text, enabled=True, is_dangerous=False, is_proceed=proceed, child_policy='' if proceed else policy, child_domain_count=8 if policy == 'cheese_gorge_add_two' and not proceed else 0)
    p = dict(schema_version=1, kind='parent_observation', version='event_card_operations_v1', session_nonce=N, parent_ordinal=1, status='ready', phase='proceed' if proceed else 'choose_option', decision_id='', candidates=[c], legal_actions=['choose:0'], child=None, prior_result=prior)
    p['decision_id'] = host._projection(p, text=True)
    return p


def prior(p, result='option_transition', child=None):
    return dict(decision_id=p['decision_id'], action_id='choose:0', result=result, child=child)


def resolved(p):
    return dict(schema_version=1, kind='parent_resolved', version='event_card_operations_v1', session_nonce=N, parent_ordinal=1, status='resolved', phase='complete', decision_id=p['decision_id'], action_id='choose:0', result='map_handoff', prior_result=prior(p, 'map_handoff'))


def correlation(p, kind, ordinal=1):
    return dict(kind=kind, child_ordinal=ordinal, parent_decision_id=p['decision_id'], parent_action_id='choose:0')


def envelope(p, c=None):
    return dict(schema_version=1, protocol='event_card_operations_v1', session_nonce=N, child=c, payload=p)


def card(selected=()):
    history = [dict(decision_id=str(i + 1) * 64, action_id=f'select:{slot}', result='selected') for i, slot in enumerate(selected)]
    candidates = [dict(slot=i, key=f'CARD_{i}', upgrade_level=0, visible=True, enabled=True, selected=i in selected) for i in range(8)]
    if len(selected) == 2:
        return dict(schema_version=1, kind='child_resolved', version='card_selection_v1', session_nonce=N, parent_ordinal=1, status='resolved', phase='complete', operation='add', selected_cards=[c for c in candidates if c['selected']], prior_results=history)
    return dict(schema_version=1, kind='child_observation', version='card_selection_v1', session_nonce=N, parent_ordinal=1, status='ready', phase='selecting', operation='add', commit_mode='auto_at_max', min_select=2, max_select=2, decision_id=str(len(selected) + 1) * 64, candidates=candidates, selected_slots=list(selected), legal_actions=[f'select:{i}' for i in range(8) if i not in selected], prior_results=history)


def item():
    # Exact frozen item canonical digest for one relic and no potion slots.
    parts = '7:item_v1;32:' + N + ';1;1;0;5:relic;5:RELIC;1;0;1;9:collect:0;'
    return dict(schema_version=1, protocol='item_probe_v1', version='item_v1', session_nonce=N, surface_ordinal=1, status='ready', decision_id=hashlib.sha256(parts.encode()).hexdigest(), offers=[dict(index=0, kind='relic', key='RELIC', enabled=True)], potion_slots=[], legal_actions=['collect:0'])


def item_resolved(p):
    return dict(schema_version=1, protocol='item_probe_v1', version='item_v1', session_nonce=N, surface_ordinal=1, status='resolved', decision_id=p['decision_id'], action_id='collect:0', offer_index=0, kind='relic', key='RELIC', result='collected')


class Transport:
    def __init__(self, reads, receipt_mutator=None):
        self.reads = list(reads); self.posts = []; self.buffers = []; self.last = None
        self.receipt_mutator = receipt_mutator
    def __call__(self, method, route, body):
        if method == 'GET':
            assert route == host.DECISION_ROUTE and body is None
            self.last = self.reads.pop(0)
            result = self.last
        else:
            assert route == host.ACTION_ROUTE
            self.buffers.append(body)
            v = json.loads(body); self.posts.append(v)
            assert v['child'] == self.last['child']
            c = v['child']
            if c is None:
                p = dict(schema_version=1, kind='parent_receipt', version='event_card_operations_v1', session_nonce=N, parent_ordinal=1, status='accepted', decision_id=v['decision_id'], action_id=v['action_id'])
            elif c['kind'] == 'card_selection':
                p = dict(schema_version=1, kind='child_receipt', version='card_selection_v1', session_nonce=N, parent_ordinal=1, decision_id=v['decision_id'], action_id=v['action_id'], outcome='accepted')
            else:
                p = dict(schema_version=1, protocol='item_probe_v1', version='item_v1', session_nonce=N, surface_ordinal=1, status='accepted', decision_id=v['decision_id'], action_id=v['action_id'])
            result = envelope(p, c)
            if self.receipt_mutator:
                self.receipt_mutator(result)
        buf = bytearray(json.dumps(result, ensure_ascii=True, separators=(',', ':')).encode())
        self.buffers.append(buf)
        return buf


class HostTests(unittest.TestCase):
    def run_flow(self, transport, provider=host.first_legal, **kwargs):
        result = host.run_event(transport, provider=provider, clock=kwargs.get('clock', lambda: 0), sleep=kwargs.get('sleep', lambda _: None))
        self.assertTrue(all(not any(b) for b in transport.buffers))
        return result
    def ordinary(self):
        p = parent(); end = parent(proceed=True, prior=prior(p))
        return Transport([envelope(p), envelope(end), envelope(resolved(end))])
    def test_ordinary(self):
        t = self.ordinary(); r = self.run_flow(t)
        self.assertEqual(r['status'], 'passed', r)
        self.assertEqual((r['parent_attempted'], r['parent_accepted'], r['option_transitions_observed'], r['parent_exits_reconciled']), (2, 2, 1, 1))
    def test_multi_page(self):
        p = parent(); second = parent('SECOND', prior=prior(p)); end = parent(proceed=True, prior=prior(second))
        t = Transport([envelope(p), envelope(second), envelope(end), envelope(resolved(end))])
        self.assertEqual(self.run_flow(t)['parent_accepted'], 3)
    def test_card_child(self):
        p = parent(policy='cheese_gorge_add_two'); c = correlation(p, 'card_selection')
        end = parent(proceed=True, prior=prior(p, 'child_completed', c))
        t = Transport([envelope(p), envelope(card(), c), envelope(card((0,)), c), envelope(card((0, 1)), c), envelope(end), envelope(resolved(end))])
        r = self.run_flow(t)
        self.assertEqual(r['status'], 'passed', r)
        self.assertEqual((r['card_episodes_completed'], r['child_accepted'], r['child_reconciled']), (1, 2, 2))
    def test_item_child(self):
        p = parent(); c = correlation(p, 'item'); reward = item()
        end = parent(proceed=True, prior=prior(p, 'child_completed', c))
        t = Transport([envelope(p), envelope(reward, c), envelope(item_resolved(reward), c), envelope(end), envelope(resolved(end))])
        r = self.run_flow(t)
        self.assertEqual(r['status'], 'passed', r)
        self.assertEqual((r['item_episodes_completed'], r['child_reconciled']), (1, 1))
    def test_sequential_children(self):
        p = parent(); c = correlation(p, 'item'); reward = item()
        second = parent('SECOND', policy='cheese_gorge_add_two', prior=prior(p, 'child_completed', c)); c2 = correlation(second, 'card_selection', 2)
        end = parent(proceed=True, prior=prior(second, 'child_completed', c2))
        t = Transport([envelope(p), envelope(reward, c), envelope(item_resolved(reward), c), envelope(second), envelope(card(), c2), envelope(card((0,)), c2), envelope(card((0, 1)), c2), envelope(end), envelope(resolved(end))])
        r = self.run_flow(t); self.assertEqual(r['status'], 'passed', r); self.assertEqual(r['child_episodes_completed'], 2); self.assertEqual(r['option_transitions_observed'], 0)
    def test_invalid_provider_no_post(self):
        t = self.ordinary(); r = self.run_flow(t, lambda _: 'bad')
        self.assertEqual(r['code'], 'invalid_provider'); self.assertEqual(t.posts, [])
    def test_throwing_provider_no_post(self):
        def provider(_):
            raise RuntimeError('private text')
        t = self.ordinary(); r = self.run_flow(t, provider)
        self.assertEqual(r['code'], 'provider_failed'); self.assertNotIn('private', str(r)); self.assertEqual(t.posts, [])
    def test_deep_immutable_provider(self):
        def provider(v):
            with self.assertRaises(TypeError):
                v.payload['candidates'][0]['enabled'] = False
            with self.assertRaises(TypeError):
                v.payload['legal_actions'][0] = 'bad'
            return host.first_legal(v)
        self.assertEqual(self.run_flow(self.ordinary(), provider)['status'], 'passed')
    def test_reentrant_provider(self):
        t = self.ordinary()
        def provider(v):
            r = host.run_event(t, provider=host.first_legal, clock=lambda: 0)
            self.assertEqual(r['code'], 'reentrant_provider')
            return host.first_legal(v)
        r = self.run_flow(t, provider); self.assertEqual(r['code'], 'reentrant_provider'); self.assertEqual(t.posts, [])
    def test_late_provider_no_post(self):
        n = [0]
        def provider(v):
            n[0] = 30
            return host.first_legal(v)
        t = self.ordinary(); r = self.run_flow(t, provider, clock=lambda: n[0]); self.assertEqual(r['code'], 'deadline_exceeded'); self.assertEqual(t.posts, [])
    def test_missing_provider_rejected_by_signature(self):
        with self.assertRaises(TypeError):
            host.run_event(self.ordinary())
    def test_uncertain_action_not_retried(self):
        t = self.ordinary()
        def mutate(r):
            p = r['payload']; p.pop('decision_id'); p.pop('action_id'); p['kind'] = 'parent_failure'; p['status'] = 'failed'; p['code'] = 'uncertain'
        t.receipt_mutator = mutate
        r = self.run_flow(t); self.assertEqual(r['status'], 'failed'); self.assertEqual(len(t.posts), 1)
    def test_receipt_mismatch(self):
        t = self.ordinary(); t.receipt_mutator = lambda r: r['payload'].update(decision_id='f' * 64)
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)
    def test_early_child(self):
        c = correlation(parent(), 'card_selection')
        t = Transport([envelope(card(), c)]); self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(t.posts, [])
    def test_wrong_child_policy(self):
        p = parent(); c = correlation(p, 'card_selection')
        t = Transport([envelope(p), envelope(card(), c)]); self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)
    def test_text_only_transition(self):
        p = parent(); second = parent(text='Text changed', prior=prior(p))
        t = Transport([envelope(p), envelope(second)]); self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)
    def test_card_domain_substitution(self):
        p = parent(policy='cheese_gorge_add_two'); c = correlation(p, 'card_selection'); changed = card((0,)); changed['candidates'][0]['key'] = 'REPLACED'
        t = Transport([envelope(p), envelope(card(), c), envelope(changed, c)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 2)
    def test_item_result_substitution(self):
        p = parent(); c = correlation(p, 'item'); reward = item(); changed = item_resolved(reward); changed['key'] = 'REPLACED'
        t = Transport([envelope(p), envelope(reward, c), envelope(changed, c)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response')
    def test_duplicate_json_key_cleared(self):
        body = bytearray(b'{"schema_version":1,"schema_version":1}')
        r = host.run_event(lambda *_: body, provider=host.first_legal, clock=lambda: 0)
        self.assertEqual(r['code'], 'invalid_response'); self.assertFalse(any(body))
    def test_parent_wrong_digest(self):
        p = parent(); p['decision_id'] = 'f' * 64
        t = Transport([envelope(p)]); self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(t.posts, [])
    def test_summary_closed(self):
        r = self.run_flow(self.ordinary()); self.assertEqual(set(r), {'schema_version', 'status', *host._FIELDS})
    def test_transport_failure_after_reservation(self):
        t = self.ordinary()
        def request(m, route, body):
            if m == 'POST':
                t.buffers.append(body)
                raise host.TransportFailure()
            return t(m, route, body)
        r = host.run_event(request, provider=host.first_legal, clock=lambda: 0)
        self.assertEqual(r['code'], 'transport_failure'); self.assertEqual(r['parent_attempted'], 1); self.assertTrue(all(not any(b) for b in t.buffers))

    def test_noncanonical_outer_rejected(self):
        for raw in (json.dumps(envelope(parent()), indent=1).encode(), json.dumps(envelope(parent()), separators=(',', ':')).encode().replace(b'INITIAL', b'\\u0049NITIAL')):
            buf = bytearray(raw)
            r = host.run_event(lambda *_: buf, provider=host.first_legal, clock=lambda: 0)
            self.assertEqual(r['code'], 'invalid_response'); self.assertFalse(any(buf))
    def test_unicode_parent_text(self):
        p = parent(text='Choose "é" <&> 😀\nNext'); end = parent(proceed=True, prior=prior(p))
        t = Transport([envelope(p), envelope(end), envelope(resolved(end))])
        self.assertEqual(self.run_flow(t)['status'], 'passed')
    def test_missing_transition_receipt(self):
        p = parent(); end = parent(proceed=True)
        t = Transport([envelope(p), envelope(end)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)
    def test_parent_before_child_resolution(self):
        p = parent(policy='cheese_gorge_add_two'); c = correlation(p, 'card_selection')
        end = parent(proceed=True, prior=prior(p, 'child_completed', c))
        t = Transport([envelope(p), envelope(card(), c), envelope(end)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 2)
    def test_child_correlation_replaced(self):
        p = parent(policy='cheese_gorge_add_two'); c = correlation(p, 'card_selection'); c2 = dict(c, child_ordinal=2)
        t = Transport([envelope(p), envelope(card(), c), envelope(card((0,)), c2)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 2)
    def test_card_history_retraction(self):
        p = parent(policy='cheese_gorge_add_two'); c = correlation(p, 'card_selection')
        waiting = dict(schema_version=1, kind='child_observation', version='card_selection_v1', session_nonce=N, parent_ordinal=1, status='waiting', phase='submitted', operation='', commit_mode='', min_select=0, max_select=0, decision_id='', candidates=[], selected_slots=[], legal_actions=[], prior_results=[])
        t = Transport([envelope(p), envelope(card(), c), envelope(card((0,)), c), envelope(waiting, c)])
        r = self.run_flow(t); self.assertEqual(r['code'], 'invalid_response'); self.assertEqual(r['child_reconciled'], 1)
    def test_read_budget_no_reset(self):
        p = parent(); p.update(status='waiting', phase='waiting', decision_id='', candidates=[], legal_actions=[])
        t = Transport([envelope(p)] * 2048)
        r = self.run_flow(t); self.assertEqual(r['code'], 'read_limit'); self.assertEqual(t.posts, []); self.assertEqual(t.reads, [])
    def test_deadline_before_first_request(self):
        ticks = iter((0, 30))
        t = self.ordinary(); r = self.run_flow(t, clock=lambda: next(ticks))
        self.assertEqual(r['code'], 'deadline_exceeded'); self.assertEqual(len(t.reads), 3)
    def test_aba_reserved_choice(self):
        p = parent(); second = parent('SECOND', prior=prior(p)); third = parent(prior=prior(second), text='Back again')
        t = Transport([envelope(p), envelope(second), envelope(third)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 2)
    def test_repeated_child_resolution_rejected(self):
        p = parent(); c = correlation(p, 'item'); reward = item()
        t = Transport([envelope(p), envelope(reward, c), envelope(item_resolved(reward), c), envelope(item_resolved(reward), c)])
        r = self.run_flow(t); self.assertEqual(r['code'], 'invalid_response'); self.assertEqual(r['child_episodes_completed'], 1)
    def test_foreign_nonce(self):
        p = parent(); end = envelope(parent(proceed=True, prior=prior(p))); end['session_nonce'] = 'b' * 32
        t = Transport([envelope(p), end]); self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)
    def test_unknown_parent_field(self):
        p = parent(); p['hidden'] = True
        t = Transport([envelope(p)]); self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(t.posts, [])

    def test_deadline_crosses_before_sleep(self):
        p = parent(); p.update(status='waiting', phase='waiting', decision_id='', candidates=[], legal_actions=[])
        ticks = iter((0, 0, 0, 0, 30)); slept = []
        t = Transport([envelope(p)])
        r = self.run_flow(t, clock=lambda: next(ticks), sleep=slept.append)
        self.assertEqual(r['code'], 'deadline_exceeded'); self.assertEqual(slept, [])
    def test_waiting_transition_closes_child_window(self):
        p = parent(); c = correlation(p, 'item')
        waiting = parent(prior=prior(p)); waiting.update(status='waiting', phase='waiting', decision_id='', candidates=[], legal_actions=[])
        t = Transport([envelope(p), envelope(waiting), envelope(item(), c)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)
    def test_completed_child_requires_child_prior(self):
        p = parent(); c = correlation(p, 'item'); reward = item()
        end = parent(proceed=True, prior=prior(p))
        t = Transport([envelope(p), envelope(reward, c), envelope(item_resolved(reward), c), envelope(end)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 2)



# Inert descriptors exercise shared validation; public run_event stays closed.
POLICIES = {
    'fixture_add_three': host._CardPolicy('FIXTURE.ADD', 'add', 3, 3, 'auto_at_max', 6, 6),
    'fixture_remove_two': host._CardPolicy('FIXTURE.REMOVE', 'remove', 2, 2, 'explicit_confirm', 4, 9),
    'fixture_upgrade_two': host._CardPolicy('FIXTURE.UPGRADE', 'upgrade', 2, 2, 'preview_confirm', 4, 9),
    'fixture_transform_two': host._CardPolicy('FIXTURE.TRANSFORM', 'transform', 2, 2, 'preview_confirm', 4, 9),
}


def generic_parent(name, domain=6, *, policies=POLICIES):
    p = parent(policies[name].stable_id, policy=name)
    p['candidates'][0]['child_domain_count'] = domain
    p['decision_id'] = host._projection(p, text=True)
    return p


def generic_card(name, actions=(), *, domain=6, phase='selecting', complete=False, policies=POLICIES):
    policy = policies[name]
    selected = [int(a[7:]) for a in actions if a.startswith('select:')]
    history = [dict(decision_id=hashlib.sha256(str(i).encode()).hexdigest(), action_id=a,
                    result='selected' if a.startswith('select:') else 'previewed' if a == 'preview' else 'committed')
               for i, a in enumerate(actions)]
    candidates = [dict(slot=i, key=f'CARD_{i}', upgrade_level=0, visible=True, enabled=True,
                       selected=i in selected) for i in range(domain)]
    if complete:
        return dict(schema_version=1, kind='child_resolved', version='card_selection_v1',
                    session_nonce=N, parent_ordinal=1, status='resolved', phase='complete',
                    operation=policy.operation, selected_cards=[c for c in candidates if c['selected']], prior_results=history)
    legal = [f'select:{i}' for i in range(domain) if i not in selected] if phase == 'selecting' and len(selected) < policy.maximum else []
    if len(selected) >= policy.minimum:
        if policy.commit_mode == 'explicit_confirm' or phase == 'preview': legal.append('confirm')
        elif policy.commit_mode == 'preview_confirm': legal.append('preview')
    return dict(schema_version=1, kind='child_observation', version='card_selection_v1',
                session_nonce=N, parent_ordinal=1, status='ready', phase=phase, operation=policy.operation,
                commit_mode=policy.commit_mode, min_select=policy.minimum, max_select=policy.maximum,
                decision_id=hashlib.sha256(str(len(actions)).encode()).hexdigest(), candidates=candidates,
                selected_slots=selected, legal_actions=legal, prior_results=history)


def generic_flow(name, *, policies=POLICIES, domain=6):
    policy = policies[name]; p = generic_parent(name, domain, policies=policies); c = correlation(p, 'card_selection')
    reads = [envelope(p)]; actions = []
    for i in range(policy.maximum):
        reads.append(envelope(generic_card(name, actions, domain=domain, policies=policies), c)); actions.append(f'select:{i}')
    if policy.commit_mode != 'auto_at_max':
        reads.append(envelope(generic_card(name, actions, domain=domain, policies=policies), c))
        if policy.commit_mode == 'preview_confirm':
            actions.append('preview'); reads.append(envelope(generic_card(name, actions, phase='preview', domain=domain, policies=policies), c))
        actions.append('confirm')
    reads.append(envelope(generic_card(name, actions, complete=True, domain=domain, policies=policies), c))
    end = parent(proceed=True, prior=prior(p, 'child_completed', c))
    reads.extend([envelope(end), envelope(resolved(end))])
    return Transport(reads)


class GenericHostTests(unittest.TestCase):
    def run_flow(self, t, policies=POLICIES):
        r = host._run_with_catalog(t, provider=host.first_legal, clock=lambda: 0, sleep=lambda _: None, policies=policies)
        self.assertTrue(all(not any(b) for b in t.buffers))
        return r

    def test_production_event_upgrades_use_public_entry(self):
        for name in ('aroma_maintain_control_upgrade_one', 'sapphire_eat_upgrade_one'):
            for domain in (2, 64):
                with self.subTest(name=name, domain=domain):
                    t = generic_flow(name, policies=host._PRODUCTION_POLICIES, domain=domain)
                    r = host.run_event(t, provider=host.first_legal, clock=lambda: 0, sleep=lambda _: None)
                    self.assertEqual(r['status'], 'passed', r)
                    self.assertEqual((r['card_episodes_completed'], r['child_accepted'], r['child_reconciled']), (1, 3, 3))
                    self.assertTrue(all(not any(b) for b in t.buffers))

    def test_production_upgrade_rejects_substituted_resolved_original(self):
        name = 'aroma_maintain_control_upgrade_one'
        t = generic_flow(name, policies=host._PRODUCTION_POLICIES, domain=2)
        result = next(v['payload'] for v in t.reads if v['payload'].get('kind') == 'child_resolved')
        result['selected_cards'][0].update(slot=1, key='CARD_1')
        r = host.run_event(t, provider=host.first_legal, clock=lambda: 0)
        self.assertEqual(r['code'], 'invalid_response')
        self.assertEqual(len(t.posts), 4)  # parent, select, preview, confirm; never Proceed
        self.assertTrue(all(not any(b) for b in t.buffers))

    def test_production_upgrade_excludes_selectorless_domain(self):
        for name in ('aroma_maintain_control_upgrade_one', 'sapphire_eat_upgrade_one'):
            for domain in (0, 1, 65):
                p = generic_parent(name, domain, policies=host._PRODUCTION_POLICIES)
                t = Transport([envelope(p)])
                r = host.run_event(t, provider=host.first_legal, clock=lambda: 0)
                self.assertEqual(r['code'], 'invalid_response'); self.assertEqual(t.posts, [])

    def test_production_policy_cannot_bind_paired_unsupported_option(self):
        pairs = (('aroma_maintain_control_upgrade_one', 'AROMA_OF_CHAOS.pages.INITIAL.options.LET_GO'),
                 ('sapphire_eat_upgrade_one', 'SAPPHIRE_SEED.pages.INITIAL.options.PLANT'))
        for name, key in pairs:
            p = generic_parent(name, 2, policies=host._PRODUCTION_POLICIES)
            p['candidates'][0]['stable_id'] = key; p['decision_id'] = host._projection(p, text=True)
            t = Transport([envelope(p)])
            r = host.run_event(t, provider=host.first_legal, clock=lambda: 0)
            self.assertEqual(r['code'], 'invalid_response'); self.assertEqual(t.posts, [])

    def test_production_single_upgrade_rejects_multi_select_child(self):
        name = 'aroma_maintain_control_upgrade_one'
        t = generic_flow(name, policies=host._PRODUCTION_POLICIES, domain=2)
        t.reads[1]['payload']['max_select'] = 2
        r = host.run_event(t, provider=host.first_legal, clock=lambda: 0)
        self.assertEqual(r['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)

    def test_multi_card_operations(self):
        for name, count in [('fixture_add_three', 3), ('fixture_remove_two', 3), ('fixture_upgrade_two', 4), ('fixture_transform_two', 4)]:
            with self.subTest(name=name):
                t = generic_flow(name); r = self.run_flow(t)
                self.assertEqual(r['status'], 'passed', r)
                self.assertEqual((r['card_episodes_completed'], r['child_accepted'], r['child_reconciled']), (1, count, count))

    def test_public_entry_does_not_enable_fixture_catalog(self):
        t = generic_flow('fixture_add_three')
        r = host.run_event(t, provider=host.first_legal, clock=lambda: 0)
        self.assertEqual(r['code'], 'invalid_response'); self.assertEqual(t.posts, [])

    def test_supported_card_cannot_skip_child(self):
        p = generic_parent('fixture_remove_two'); end = parent(proceed=True, prior=prior(p))
        t = Transport([envelope(p), envelope(end)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)

    def test_child_domain_bound_before_dispatch(self):
        t = generic_flow('fixture_remove_two'); t.reads[1]['payload'] = generic_card('fixture_remove_two', domain=5)
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)

    def test_parent_domain_invalid_before_dispatch(self):
        for value in [0, 3, 10, True]:
            p = generic_parent('fixture_remove_two', value); t = Transport([envelope(p)])
            self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(t.posts, [])

    def test_wrong_operation_before_child_action(self):
        t = generic_flow('fixture_remove_two'); t.reads[1]['payload']['operation'] = 'add'
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)

    def test_wrong_counts_before_child_action(self):
        t = generic_flow('fixture_remove_two'); t.reads[1]['payload'].update(min_select=1, max_select=1)
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 1)

    def test_wrong_stable_key_before_parent_action(self):
        p = generic_parent('fixture_remove_two'); p['candidates'][0]['stable_id'] = 'OTHER'
        p['decision_id'] = host._projection(p, text=True); t = Transport([envelope(p)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(t.posts, [])

    def test_known_card_cannot_fall_back_to_item(self):
        p = parent(POLICIES['fixture_remove_two'].stable_id); t = Transport([envelope(p)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(t.posts, [])

    def test_unsupported_option_is_observed_but_not_legal(self):
        p = parent(); c = dict(p['candidates'][0], candidate_index=1, action_id='choose:1',
                               stable_id='UNSUPPORTED', child_policy='unsupported_card')
        p['candidates'].append(c); p['decision_id'] = host._projection(p, text=True)
        end = parent(proceed=True, prior=prior(p)); t = Transport([envelope(p), envelope(end), envelope(resolved(end))])
        self.assertEqual(self.run_flow(t)['status'], 'passed')
        self.assertEqual(t.posts[0]['action_id'], 'choose:0')

    def test_unsupported_option_cannot_be_legal(self):
        p = parent(policy='unsupported_card'); t = Transport([envelope(p)])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(t.posts, [])

    def test_missing_confirm_cannot_resolve(self):
        t = generic_flow('fixture_remove_two'); t.reads[3] = envelope(generic_card('fixture_remove_two', ['select:0', 'select:1'], complete=True), t.reads[3]['child'])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 3)

    def test_preview_cannot_regress_to_selection(self):
        t = generic_flow('fixture_upgrade_two'); t.reads[4]['payload'] = generic_card('fixture_upgrade_two', ['select:0', 'select:1', 'preview'])
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 4)

    def test_preview_selected_public_set_is_preserved(self):
        # Native cleared highlights must already have been reconciled by the core.
        t = generic_flow('fixture_upgrade_two'); p = t.reads[4]['payload']
        for c in p['candidates']: c['selected'] = False
        p['selected_slots'] = []
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 4)

    def test_wrong_result_model(self):
        t = generic_flow('fixture_upgrade_two'); t.reads[5]['payload']['selected_cards'][0]['key'] = 'OTHER'
        self.assertEqual(self.run_flow(t)['code'], 'invalid_response'); self.assertEqual(len(t.posts), 5)

    def test_catalog_duplicate_key_rejected(self):
        policies = dict(POLICIES); policies['duplicate'] = POLICIES['fixture_remove_two']
        t = generic_flow('fixture_add_three')
        self.assertEqual(self.run_flow(t, policies)['code'], 'invalid_response'); self.assertEqual(t.posts, [])


if __name__ == '__main__':
    unittest.main()
