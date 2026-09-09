#!/usr/bin/env python3
"""Actual generic parent + frozen card + wire + Python host, using inert adapters."""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
from pathlib import Path
import selectors
import subprocess
import sys
import time
from typing import Any, Callable


def load(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location('generic_event_integration_host', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Exchange:
    def __init__(self, dotnet: str, fixture: Path, scenario: str, *, native: bool = False):
        self.native = native
        self.transform = native and scenario.startswith(('T_', 'V_'))
        self.variable_transform = native and scenario.startswith('V_')
        self.results_surface=native and scenario.startswith("S_")
        self.card_offer = native and scenario.startswith("O_")
        self.card_reward = native and scenario.startswith(("CR_","CRS_","MR_"))
        self.item = native and scenario.startswith('I_')
        self.repeated_page = native and scenario.startswith('P_')
        self.process = subprocess.Popen([dotnet, str(fixture), scenario],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, bufsize=0)
        self.selector = selectors.DefaultSelector()
        assert self.process.stdout is not None
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.calls: list[tuple[str, str]] = []
        self.buffers: list[bytearray] = []
        self.envelopes: list[dict[str, Any]] = []
        self.telemetry: list[dict[str, Any]] = []

    def request(self, method: str, route: str, body: bytearray | None) -> bytearray:
        assert (method, route) in (('GET', '/probe/generic-event-v7/public/decision'),
                                    ('POST', '/probe/generic-event-v7/public/action'))
        self.calls.append((method, route))
        if body is not None:
            self.buffers.append(body)
        command = json.dumps({'method': method, 'route': route,
                              'body': None if body is None else base64.b64encode(body).decode('ascii')},
                             separators=(',', ':')).encode('ascii') + b'\n'
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(command)
        self.process.stdin.flush()
        # No unbounded readline or target process: one inert reply is at most 100 KiB.
        line = bytearray()
        deadline = time.monotonic() + 5.0
        while not line.endswith(b'\n'):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(timeout=remaining):
                raise AssertionError('inert driver response deadline')
            part = self.process.stdout.read(1)
            if not part:
                raise AssertionError('inert driver EOF')
            line.extend(part)
            if len(line) > 100_000:
                raise AssertionError('inert driver response size')
        value = json.loads(line)
        expected = (('body', 'event_type', 'upgraded_cards', 'map_open', 'overlay_count',
                     'chosen_calls', 'select_calls', 'confirm_calls', 'preview_calls',
                     'baseline_keys', 'baseline_levels', 'remaining_originals',
                     'remaining_keys', 'remaining_levels', 'offer_keys', 'offer_levels',
                     'slot_offer_indices', 'deck_originals', 'multi_completion_valid', 'derived_hitboxes_retained') if self.native else
                    ('body', 'parent_dispatches', 'card_dispatches', 'before_child_effects', 'disposed_children',
                     'remaining_keys', 'remaining_levels'))
        if self.native and not self.item and not self.transform:
            expected += ("enchantment_keys", "enchantment_amounts")
        if self.item:
            expected = ('body', 'event_type', 'map_open', 'overlay_count', 'chosen_calls',
                        'collect_calls', 'completion_valid', 'item_completions', 'baseline_keys', 'baseline_levels',
                        'remaining_keys', 'remaining_levels')
        if self.transform:
            expected += ('transform_originals', 'transform_final_keys', 'transform_final_levels',
                         'transform_batches', 'transform_completion_valid')
        if self.variable_transform:
            expected += ('preview_holder_count', 'selected_originals')
        if self.repeated_page:
            expected = ('body', 'map_open', 'chosen_calls', 'linger_calls', 'control_calls')
        if self.card_reward:
            expected=("body","map_open","overlay_count","opens","choices","skips","dismisses","added_slots")
        if self.card_offer:
            expected=("body","map_open","overlay_count","choices","confirms","selected","deck")
        if self.results_surface:
            expected=("body","map_open","capstone_open","confirms","chosen_calls","deck")
        assert tuple(value) == expected, value
        self.telemetry.append({k: value[k] for k in value if k != 'body'})
        response = bytearray(base64.b64decode(value['body'], validate=True))
        envelope = json.loads(response)
        assert envelope['protocol'] == 'generic_event_v7', envelope
        self.envelopes.append(envelope)
        self.buffers.append(response)
        return response

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            code = self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
            raise AssertionError('inert driver shutdown timeout') from None
        self.selector.close()
        assert self.process.stderr is not None
        stderr = self.process.stderr.read()
        assert code == 0 and not stderr, (code, stderr)
        assert not any(any(b) for b in self.buffers), 'host did not clear buffers'

    @property
    def posts(self) -> int:
        return sum(method == 'POST' for method, _ in self.calls)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dotnet', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--native-fixture', type=Path)
    args = parser.parse_args()
    host = load(args.host)
    checks = 0

    def run(scenario: str = 'HELD_OUT_991', wrapper: Callable | None = None,
            provider: Callable | None = None, clock: Callable = lambda: 1.0) -> tuple[dict, Exchange]:
        exchange = Exchange(args.dotnet, args.fixture, scenario)
        request = exchange.request if wrapper is None else lambda m, r, b: wrapper(exchange, m, r, b)
        try:
            result = host.run_event(request, provider=provider or host.first_legal,
                                    clock=clock, sleep=lambda _: None)
        finally:
            exchange.close()
        if result['status'] == 'resolved':
            completed_history(result, exchange, result['child_episodes'])
        return result, exchange

    def completed_history(result: dict, ex: Exchange, expected: int, expected_items: int = 0) -> None:
        assert result['completed_card_children'] == expected, result
        assert result['completed_item_children'] == expected_items, result
        cards, items = set(), set()
        for envelope in ex.envelopes:
            if envelope['kind'] != 'decision':
                continue
            parent = envelope['parent']
            assert parent['completed_card_children'] == len(cards), envelope
            assert parent['completed_item_children'] == len(items), envelope
            child, payload = envelope['child'], envelope['payload']
            if child is None:
                continue
            common = ('ordinal', 'parent_decision_id', 'parent_action_id', 'kind', 'contract_version')
            if child['kind'] == 'item':
                assert tuple(child) == common + ('offer_count',), child
                assert child['contract_version'] == 'item_v1' and child['offer_count'] == 1, child
                complete = payload.get('status') == 'resolved'
                seen = items
            else:
                assert child['kind'] == 'card_selection', child
                assert tuple(child) == common + ('operation', 'min_select', 'max_select', 'commit_mode', 'domain_count'), child
                assert child['contract_version'] == (('card_add_v2' if child['operation']=='add' else 'card_transform_v3') if child['min_select']==0 else 'card_remove_v2' if child['operation'] == 'remove' else 'card_enchant_v1' if child['operation'] == 'enchant' else 'card_transform_v2' if child['operation'] == 'transform' else 'card_selection_v1'), child
                complete = payload.get('kind') == 'child_resolved'
                seen = cards
            if complete:
                ordinal = child['ordinal']
                assert ordinal not in cards | items
                seen.add(ordinal)
        assert (len(cards), len(items)) == (expected, expected_items), (result, cards, items)

    baseline_reads = 0
    for scenario in ('FOREST_ARCHIVE', 'CLOCKWORK_GARDEN', 'HELD_OUT_991', 'delayed'):
        result, ex = run(scenario)
        assert result['status'] == 'resolved', (scenario, result, ex.envelopes[-1])
        assert {k: result[k] for k in ('parent_attempted', 'parent_accepted', 'parent_reconciled',
                                      'child_episodes', 'child_attempted', 'child_accepted',
                                      'child_reconciled', 'total_attempted')} == {
            'parent_attempted': 3, 'parent_accepted': 3, 'parent_reconciled': 3,
            'child_episodes': 1, 'child_attempted': 3, 'child_accepted': 3,
            'child_reconciled': 3, 'total_attempted': 6}, result
        assert ex.posts == 6 and ex.telemetry[-1] == {
            'parent_dispatches': 3, 'card_dispatches': 3,
            'before_child_effects': 1, 'disposed_children': 1,
            'remaining_keys': ['Card_0', 'Card_1', 'Card_2'],
            'remaining_levels': [1, 0, 0]}, ex.telemetry
        decisions = [v for v in ex.envelopes if v['kind'] == 'decision']
        phases = [v['parent']['phase'] for v in decisions]
        assert 'choose_option' in phases and 'proceed' in phases and phases[-1] == 'map_handoff'
        resolutions = [i for i, v in enumerate(decisions) if v['payload'] and v['payload']['kind'] == 'child_resolved']
        assert len(resolutions) == 1 and decisions[resolutions[0]]['parent']['status'] == 'child'
        assert decisions[resolutions[0] + 1]['parent']['prior_results'][0]['result'] == 'child_completed'
        child_actions = [v['payload']['action_id'] for v in ex.envelopes
                         if v['kind'] == 'action' and v['child']]
        assert child_actions == ['select:0', 'preview', 'confirm'], child_actions
        assert any(t['before_child_effects'] == 1 and t['card_dispatches'] == 0 for t in ex.telemetry)
        if not baseline_reads:
            baseline_reads = result['reads']
        if scenario == 'delayed':
            assert result['reads'] > baseline_reads, (scenario, result)
        checks += 1

    result, ex = run('early_delta')
    assert result['code'] == 'unsupported_state' and result['effects'] == 'unverified', result
    assert result['parent_reconciled'] == 0 and ex.posts == 4
    assert not any(v['payload'] and v['payload'].get('kind') == 'child_resolved' for v in ex.envelopes)
    checks += 1

    for scenario, code in (('uncertain', 'uncertain_action'), ('unsupported', 'unsupported_state'),
                           ('never_child', 'unsupported_state')):
        result, ex = run(scenario)
        assert result['status'] == 'failed' and result['code'] == code, result
        assert result['parent_attempted'] == 1 and result['effects'] == 'unverified', result
        assert ex.posts == 1 and ex.telemetry[-1]['parent_dispatches'] == 1, ex.telemetry
        assert ex.telemetry[-1]['card_dispatches'] == 0
        checks += 1

    def lost_post(ex: Exchange, method: str, route: str, body: bytearray | None) -> bytearray:
        response = ex.request(method, route, body)
        if method == 'POST':
            response[:] = b'\0' * len(response)
            raise host.TransportFailure()
        return response
    result, ex = run(wrapper=lost_post)
    assert result['code'] == 'transport_failure' and result['parent_attempted'] == 1, result
    assert result['parent_accepted'] == 0 and result['effects'] == 'unverified'
    assert ex.posts == 1 and ex.telemetry[-1]['parent_dispatches'] == 1
    checks += 1

    def wrong_lineage(ex: Exchange, method: str, route: str, body: bytearray | None) -> bytearray:
        if method == 'POST' and ex.posts == 1:
            value = json.loads(body)
            value['child']['parent_decision_id'] = 'f' * 64
            body[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
        return ex.request(method, route, body)
    result, ex = run(wrapper=wrong_lineage)
    assert result['status'] == 'failed' and result['code'] == 'invalid_request', result
    assert ex.posts == 2 and ex.telemetry[-1]['card_dispatches'] == 0
    checks += 1

    for mutation in ('descriptor', 'unknown_key', 'receipt', 'resolved_card'):
        changed = False
        def tamper(ex: Exchange, method: str, route: str, body: bytearray | None) -> bytearray:
            nonlocal changed
            response = ex.request(method, route, body)
            value = json.loads(response)
            if not changed:
                if mutation == 'descriptor' and method == 'GET' and value['child']:
                    value['child']['domain_count'] = 4
                    changed = True
                elif mutation == 'unknown_key' and method == 'GET':
                    value['unknown'] = True
                    changed = True
                elif mutation == 'receipt' and method == 'POST':
                    value['payload']['decision_id'] = 'e' * 64
                    changed = True
                elif mutation == 'resolved_card' and value['payload'] and value['payload'].get('kind') == 'child_resolved':
                    value['payload']['selected_cards'][0]['slot'] = 2
                    changed = True
                if changed:
                    response[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
            return response
        result, ex = run(wrapper=tamper)
        assert changed and result['code'] == 'invalid_response', (mutation, result)
        expected_posts = {'descriptor': 1, 'unknown_key': 0, 'receipt': 1, 'resolved_card': 4}[mutation]
        assert ex.posts == expected_posts, (mutation, ex.posts)
        checks += 1

    provider_calls = 0
    def immutable(view: Any) -> str:
        nonlocal provider_calls
        provider_calls += 1
        view.payload['candidates'][0]['rendered_text'] = 'changed'
        return 'choose:0'
    result, ex = run(provider=immutable)
    assert result['code'] == 'provider_failed' and ex.posts == 0 and provider_calls == 1
    checks += 1

    now = 1.0
    def late_post(ex: Exchange, method: str, route: str, body: bytearray | None) -> bytearray:
        nonlocal now
        response = ex.request(method, route, body)
        if method == 'POST':
            now = 32.0
        return response
    result, ex = run(wrapper=late_post, clock=lambda: now)
    assert result['code'] == 'deadline_exceeded' and result['parent_attempted'] == 1, result
    assert result['parent_accepted'] == 0 and ex.posts == 1
    checks += 1

    def planned(actions: tuple[str, ...]) -> Callable:
        next_action = iter(actions)
        def choose(view: Any) -> str:
            if view.kind == 'parent':
                return view.payload['legal_actions'][0]
            return next(next_action)
        return choose

    removal_configs = (
        ('removal_fixed', 2, 2, 5, ('select:3', 'select:1', 'confirm')),
        ('removal_variable_min', 1, 3, 5, ('select:3', 'preview', 'confirm')),
        ('removal_variable_two', 1, 3, 5, ('select:3', 'select:1', 'preview', 'confirm')),
        ('removal_reverse', 1, 3, 5, ('select:3', 'select:1', 'select:0', 'confirm')),
        ('removal_eight', 8, 8, 9, tuple(f'select:{i}' for i in range(8, 0, -1)) + ('confirm',)),
        ('removal_delayed', 2, 2, 5, ('select:3', 'select:1', 'confirm')),
        ('removal_delayed_completion', 2, 2, 5, ('select:3', 'select:1', 'confirm')),
    )
    removal_reads = 0
    for scenario, minimum, maximum, domain, actions in removal_configs:
        result, ex = run(scenario, provider=planned(actions))
        assert result['status'] == 'resolved', (scenario, result, ex.envelopes[-1])
        assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 3
        assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == len(actions)
        assert result['child_episodes'] == 1 and ex.posts == len(actions) + 3
        selected = {int(a[7:]) for a in actions if a.startswith('select:')}
        remaining = [f'Card_{i}' for i in range(domain) if i not in selected]
        assert ex.telemetry[-1]['remaining_keys'] == remaining, (scenario, ex.telemetry[-1])
        assert ex.telemetry[-1]['remaining_levels'] == [0] * len(remaining)
        actual_actions = tuple(v['payload']['action_id'] for v in ex.envelopes if v['kind'] == 'action' and v['child'])
        assert actual_actions == actions, (scenario, actual_actions)
        decisions = [v for v in ex.envelopes if v['kind'] == 'decision']
        child_decisions = [v for v in decisions if v['child']]
        assert all((v['child']['operation'], v['child']['min_select'], v['child']['max_select'],
                    v['child']['domain_count'], v['child']['commit_mode']) ==
                   ('remove', minimum, maximum, domain, 'preview_confirm') for v in child_decisions)
        assert any(v['payload']['phase'] == 'preview' for v in child_decisions)
        resolved = [i for i, v in enumerate(decisions) if v['payload'] and v['payload'].get('kind') == 'child_resolved']
        assert len(resolved) == 1
        done = decisions[resolved[0]]['payload']
        assert {c['slot'] for c in done['selected_cards']} == selected
        assert all(c['key'] == f"Card_{c['slot']}" and c['upgrade_level'] == 0 for c in done['selected_cards'])
        assert decisions[resolved[0] + 1]['parent']['prior_results'][0]['result'] == 'child_completed'
        if not removal_reads:
            removal_reads = result['reads']
        if scenario in ('removal_delayed', 'removal_delayed_completion'):
            assert result['reads'] > removal_reads, (scenario, result)
        checks += 1

    result, ex = run('removal_early_delta', provider=planned(('select:3', 'select:1', 'confirm')))
    assert result['code'] == 'unsupported_state' and result['effects'] == 'unverified', result
    assert result['parent_reconciled'] == 0 and ex.posts == 4
    assert not any(v['payload'] and v['payload'].get('kind') == 'child_resolved' for v in ex.envelopes)
    checks += 1
    result, ex = run('admission_changed')
    assert result['code'] == 'unsupported_state' and result['parent_accepted'] == 1, result
    assert ex.posts == 1 and ex.telemetry[-1]['card_dispatches'] == 0
    checks += 1

    for mutation in ('operation', 'zero_min', 'max_nine', 'domain_shortcut', 'changed_count', 'duplicate_result'):
        changed = False
        child_reads = 0
        def corrupt_removal(ex: Exchange, method: str, route: str, body: bytearray | None) -> bytearray:
            nonlocal changed, child_reads
            response = ex.request(method, route, body)
            value = json.loads(response)
            if method == 'GET' and value['child']:
                child_reads += 1
                if not changed:
                    if mutation == 'operation':
                        value['child']['operation'] = 'transform'
                        changed = True
                    elif mutation == 'zero_min':
                        value['child']['min_select'] = 0
                        changed = True
                    elif mutation == 'max_nine':
                        value['child']['max_select'] = 9
                        changed = True
                    elif mutation == 'domain_shortcut':
                        value['child']['domain_count'] = value['child']['max_select']
                        changed = True
                    elif mutation == 'changed_count' and child_reads == 2:
                        value['child']['max_select'] = 3
                        changed = True
                    elif mutation == 'duplicate_result' and value['payload']['kind'] == 'child_resolved':
                        value['payload']['selected_cards'][1] = value['payload']['selected_cards'][0]
                        changed = True
                    if changed:
                        response[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
            return response
        result, ex = run('removal_fixed', wrapper=corrupt_removal,
                         provider=planned(('select:3', 'select:1', 'confirm')))
        assert changed and result['code'] == 'invalid_response', (mutation, result)
        assert ex.posts == (4 if mutation == 'duplicate_result' else 2 if mutation == 'changed_count' else 1)
        checks += 1

    for lost_action in ('select:3', 'confirm'):
        def lose_child_response(ex: Exchange, method: str, route: str, body: bytearray | None) -> bytearray:
            response = ex.request(method, route, body)
            if method == 'POST' and json.loads(body)['action_id'] == lost_action:
                response[:] = b'\0' * len(response)
                raise host.TransportFailure()
            return response
        result, ex = run('removal_fixed', wrapper=lose_child_response,
                         provider=planned(('select:3', 'select:1', 'confirm')))
        attempted = 1 if lost_action == 'select:3' else 3
        assert result['code'] == 'transport_failure' and result['effects'] == 'unverified', result
        assert result['parent_accepted'] == 1 and result['parent_reconciled'] == 0
        assert result['child_attempted'] == attempted and result['child_accepted'] == attempted - 1
        assert ex.posts == attempted + 1 and ex.telemetry[-1]['card_dispatches'] == attempted
        if lost_action == 'confirm':
            assert ex.telemetry[-1]['remaining_keys'] == ['Card_0', 'Card_2', 'Card_4']
        else:
            assert len(ex.telemetry[-1]['remaining_keys']) == 5
        checks += 1

    mixed_actions = ('select:0', 'preview', 'confirm', 'select:2', 'select:1', 'confirm')
    result, ex = run('mixed_families', provider=planned(mixed_actions))
    assert result['status'] == 'resolved' and result['child_episodes'] == 2, (result, ex.envelopes[-1])
    assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 3
    assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == 6
    assert result['total_attempted'] == 9 and ex.posts == 9
    assert ex.telemetry[-1]['disposed_children'] == 2 and ex.telemetry[-1]['card_dispatches'] == 6
    assert ex.telemetry[-1]['remaining_keys'] == ['Card_0'] and ex.telemetry[-1]['remaining_levels'] == [1]
    child_frames = [v for v in ex.envelopes if v['kind'] == 'decision' and v['child']]
    by_ordinal = {ordinal: [v for v in child_frames if v['child']['ordinal'] == ordinal] for ordinal in (1, 2)}
    assert all(v['child']['operation'] == 'upgrade' and v['child']['min_select'] == v['child']['max_select'] == 1 for v in by_ordinal[1])
    assert all(v['child']['operation'] == 'remove' and v['child']['min_select'] == v['child']['max_select'] == 2 for v in by_ordinal[2])
    assert by_ordinal[1][0]['child']['parent_decision_id'] != by_ordinal[2][0]['child']['parent_decision_id']
    assert all(sum(v['payload']['kind'] == 'child_resolved' for v in frames) == 1 for frames in by_ordinal.values())
    assert [r['result'] for r in ex.envelopes[-1]['parent']['prior_results']] == ['child_completed', 'child_completed', 'map_handoff']
    checks += 1

    reward_cases = (
        ('reward_auto_fixed', 2, 2, 5, 'auto_at_max', ('select:3', 'select:1')),
        ('reward_auto_variable', 1, 3, 5, 'auto_at_max', ('select:3', 'select:1', 'select:0')),
        ('reward_explicit_fixed', 2, 2, 5, 'explicit_confirm', ('select:3', 'select:1', 'confirm')),
        ('reward_explicit_variable_min', 1, 3, 5, 'explicit_confirm', ('select:3', 'confirm')),
        ('reward_explicit_variable_max', 1, 3, 5, 'explicit_confirm', ('select:3', 'select:1', 'select:0', 'confirm')),
        ('reward_auto_sorted', 2, 2, 5, 'auto_at_max', ('select:3', 'select:1')),
        ('reward_auto_eight', 8, 8, 9, 'auto_at_max', tuple(f'select:{i}' for i in range(8, 0, -1))),
        ('reward_explicit_eight', 8, 8, 9, 'explicit_confirm', tuple(f'select:{i}' for i in range(8, 0, -1)) + ('confirm',)),
        ('reward_auto_delayed_creation', 2, 2, 5, 'auto_at_max', ('select:3', 'select:1')),
        ('reward_auto_partial', 2, 2, 5, 'auto_at_max', ('select:3', 'select:1')),
        ('reward_explicit_delayed_completion', 2, 2, 5, 'explicit_confirm', ('select:3', 'select:1', 'confirm')),
    )
    for scenario, minimum, maximum, domain, mode, actions in reward_cases:
        result, ex = run(scenario, provider=planned(actions))
        assert result['status'] == 'resolved', (scenario, result, ex.envelopes[-1])
        assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 3
        assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == len(actions)
        assert result['child_episodes'] == 1 and ex.posts == len(actions) + 3
        slots = {int(a[7:]) for a in actions if a.startswith('select:')}
        offer_keys = {f"Offer_{domain - 1 - i if 'sorted' in scenario else i}" for i in slots}
        final_keys = ex.telemetry[-1]['remaining_keys']
        assert final_keys[:2] == ['Base_0', 'Base_1'] and set(final_keys[2:]) == offer_keys
        assert len(final_keys) == len(slots) + 2 and ex.telemetry[-1]['remaining_levels'] == [0] * len(final_keys)
        children = [v for v in ex.envelopes if v['kind'] == 'decision' and v['child']]
        assert all((v['child']['operation'], v['child']['min_select'], v['child']['max_select'], v['child']['commit_mode'], v['child']['domain_count']) ==
                   ('add', minimum, maximum, mode, domain) for v in children)
        assert all(v['payload']['phase'] != 'preview' for v in children)
        done = [v['payload'] for v in children if v['payload']['kind'] == 'child_resolved']
        assert len(done) == 1 and {c['key'] for c in done[0]['selected_cards']} == offer_keys
        assert {c['slot'] for c in done[0]['selected_cards']} == slots
        assert tuple(r['action_id'] for r in done[0]['prior_results']) == actions
        assert done[0]['prior_results'][-1]['result'] == ('selected' if mode == 'auto_at_max' else 'committed')
        if scenario == 'reward_auto_delayed_creation':
            assert any(v['kind'] == 'decision' and v['parent']['status'] == 'waiting' for v in ex.envelopes)
        if scenario in ('reward_auto_partial', 'reward_explicit_delayed_completion'):
            assert any(v['payload']['status'] == 'waiting' for v in children)
            assert any(len(t['remaining_keys']) == 3 for t in ex.telemetry)
        checks += 1

    for scenario in ('reward_auto_empty', 'reward_auto_partial_terminal'):
        result, ex = run(scenario, provider=planned(('select:3', 'select:1')))
        assert result['status'] == 'failed' and result['code'] == 'unsupported_state', (scenario, result)
        assert result['effects'] == 'unverified' and result['parent_reconciled'] == 0
        assert ex.posts == 3 and result['child_accepted'] == 2
        assert not any(v['payload'] and v['payload'].get('kind') == 'child_resolved' for v in ex.envelopes)
        checks += 1

    for scenario, actions in (('reward_auto_fixed', ('select:3', 'select:1')),
                              ('reward_explicit_fixed', ('select:3', 'select:1', 'confirm'))):
        def lose_reward_final(ex: Exchange, method: str, route: str, body: bytearray | None) -> bytearray:
            response = ex.request(method, route, body)
            if method == 'POST' and json.loads(body)['action_id'] == actions[-1]:
                response[:] = b'\0' * len(response)
                raise host.TransportFailure()
            return response
        result, ex = run(scenario, wrapper=lose_reward_final, provider=planned(actions))
        assert result['code'] == 'transport_failure' and result['effects'] == 'unverified', result
        assert result['child_attempted'] == len(actions) and result['child_accepted'] == len(actions) - 1
        assert result['parent_accepted'] == 1 and result['parent_reconciled'] == 0
        assert ex.posts == len(actions) + 1 and len(ex.telemetry[-1]['remaining_keys']) == 4
        checks += 1

    three_actions = ('select:0', 'preview', 'confirm', 'select:2', 'select:1', 'confirm', 'select:3', 'select:1', 'confirm')
    result, ex = run('mixed_three', provider=planned(three_actions))
    assert result['status'] == 'resolved' and result['child_episodes'] == 3, (result, ex.envelopes[-1])
    assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 4
    assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == 9
    assert result['total_attempted'] == 13 and ex.posts == 13 and ex.telemetry[-1]['disposed_children'] == 3
    assert ex.telemetry[-1]['remaining_keys'] == ['Card_0', 'Offer_1', 'Offer_3']
    assert ex.telemetry[-1]['remaining_levels'] == [1, 0, 0]
    frames = [v for v in ex.envelopes if v['kind'] == 'decision' and v['child']]
    for ordinal, operation in ((1, 'upgrade'), (2, 'remove'), (3, 'add')):
        episode = [v for v in frames if v['child']['ordinal'] == ordinal]
        assert episode and all(v['child']['operation'] == operation for v in episode)
        assert sum(v['payload']['kind'] == 'child_resolved' for v in episode) == 1
    assert [r['result'] for r in ex.envelopes[-1]['parent']['prior_results']] == ['child_completed'] * 3 + ['map_handoff']
    checks += 1

    result, ex = run('mixed_multi_three', provider=planned(('select:1', 'select:0', 'confirm',
                                                          'select:2', 'select:0', 'confirm',
                                                          'select:3', 'select:1', 'confirm')))
    assert result['status'] == 'resolved' and result['completed_card_children'] == 3, result
    assert result['child_episodes'] == 3 and result['child_reconciled'] == 9 and result['parent_reconciled'] == 4
    assert ex.posts == 13 and ex.telemetry[-1]['remaining_keys'] == ['Card_1', 'Offer_1', 'Offer_3']
    assert ex.telemetry[-1]['remaining_levels'] == [1, 0, 0]
    checks += 1

    for scenario, count in (('upgrade_multi_two', 2), ('upgrade_multi_eight', 8)):
        actions = tuple(f'select:{i}' for i in range(count, 0, -1)) + ('confirm',)
        result, ex = run(scenario, provider=planned(actions))
        assert result['status'] == 'resolved' and result['completed_card_children'] == 1, result
        assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == count + 1
        assert ex.posts == count + 4
        assert ex.telemetry[-1]['remaining_levels'] == [0] + [1] * count
        children = [v for v in ex.envelopes if v['kind'] == 'decision' and v['child']]
        assert all(v['child']['operation'] == 'upgrade' and v['child']['min_select'] == v['child']['max_select'] == count for v in children)
        assert all('preview' not in v['payload'].get('legal_actions', []) for v in children)
        checks += 1

    for scenario, code in (('later_unsupported', 'unsupported_state'), ('later_uncertain', 'uncertain_action'), ('cleanup_failure', 'unsupported_state')):
        result, ex = run(scenario)
        assert result['status'] == 'failed' and result['code'] == code, result
        completed_history(result, ex, 1)
        assert result['child_episodes'] == 1 and result['child_reconciled'] == 3
        assert ex.posts == (5 if scenario == 'later_uncertain' else 4)
        checks += 1

    result, ex = run('repeat_terminal')
    assert result['status'] == 'resolved' and result['completed_card_children'] == 1, result
    assert ex.posts == 6
    checks += 1

    for change in ('skip', 'regress', 'terminal_payload'):
        changed = False
        def corrupt_cumulative(ex: Exchange, method: str, route: str, body: bytearray | None) -> bytearray:
            nonlocal changed
            response = ex.request(method, route, body)
            value = json.loads(response)
            if method == 'GET' and not changed:
                if change == 'skip':
                    value['parent']['completed_card_children'] = 1
                    changed = True
                elif change == 'regress' and value['parent']['completed_card_children'] == 1:
                    value['parent']['completed_card_children'] = 0
                    changed = True
                elif change == 'terminal_payload' and value['payload'] and value['payload'].get('kind') == 'child_resolved':
                    value['payload']['selected_cards'][0]['slot'] = 2
                    changed = True
                if changed:
                    response[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
            return response
        result, ex = run(wrapper=corrupt_cumulative)
        assert changed and result['code'] == 'invalid_response', (change, result)
        assert result['completed_card_children'] == (1 if change == 'regress' else 0), result
        assert ex.posts == (0 if change == 'skip' else 4)
        checks += 1

    for change in ('invent_item', 'reclassify_card'):
        changed = False
        def corrupt_family_count(ex: Exchange, method: str, route: str, body: bytearray | None) -> bytearray:
            nonlocal changed
            response = ex.request(method, route, body)
            value = json.loads(response)
            if method == 'GET' and not changed and (change == 'invent_item' or value['parent']['completed_card_children'] == 1):
                value['parent']['completed_item_children'] = 1
                if change == 'reclassify_card':
                    value['parent']['completed_card_children'] = 0
                response[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
                changed = True
            return response
        result, ex = run(wrapper=corrupt_family_count)
        assert changed and result['code'] == 'invalid_response', (change, result)
        assert result['completed_item_children'] == 0, result
        assert result['completed_card_children'] == (change == 'reclassify_card'), result
        assert ex.posts == (0 if change == 'invent_item' else 4)
        checks += 1

    native_checks = 0
    if args.native_fixture is not None:
        for scenario in ('ENCHANT_PRE_ADD', 'U_PRE_ADD', 'T_PRE_ADD', 'ENCHANT_POST_ADD', 'ENCHANT_PRE_ADD_OWNER'):
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            count = 2 if scenario.startswith(('U_', 'T_')) else 1
            actions = tuple(f'select:{i}' for i in range(count)) + ('confirm',)
            try:
                result = host.run_event(native.request, provider=planned(actions), clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            end = native.telemetry[-1]
            failure = scenario in ('ENCHANT_POST_ADD', 'ENCHANT_PRE_ADD_OWNER')
            assert (result['status'] == 'resolved') != failure, (scenario, result, native.envelopes[-1])
            assert result['completed_card_children'] == (0 if failure else 1), result
            assert native.posts == count + (2 if failure else 3), result
            assert end['select_calls'] == count and end['confirm_calls'] == 1, end
            if not failure:
                completed_history(result, native, 1)
                key = 'SHAME' if scenario == 'U_PRE_ADD' else 'DOUBT' if scenario == 'T_PRE_ADD' else 'DECAY'
                assert end['remaining_keys'].count(key) == 1 and end['map_open'], end
                slot = end['remaining_keys'].index(key)
                assert end['remaining_levels'][slot] == 0 and end['remaining_originals'][slot] == -1, end
                if scenario != 'T_PRE_ADD':
                    assert end['remaining_keys'] == end['baseline_keys'] + [key], end
                    assert end['enchantment_keys'][slot] is None, end
                    if scenario == 'U_PRE_ADD':
                        assert end['multi_completion_valid'] and end['remaining_levels'] == [1, 1] + [0] * (len(end['remaining_keys']) - 2), end
                    else:
                        assert end['enchantment_keys'][0] == 'SOWN' and sum(x is not None for x in end['enchantment_keys']) == 1, end
                else:
                    assert end['remaining_originals'] == list(range(2, len(end['baseline_keys']))) + [-1, -1, -1], end
                    assert len(end['transform_originals']) == 2 and end['transform_batches'] == 2, end
                    assert end['transform_completion_valid'], end
                assert result['effects'] == 'unverified', result
            checks += 1
            native_checks += 1
        for scenario in ('P_REPEAT', 'P_REVISIT', 'P_DELAY', 'P_FAULT', 'P_STALE', 'P_DANGER', 'P_BOUND'):
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            def repeat_provider(view):
                p = view.payload
                if scenario != 'P_BOUND' and p['parent_reconciled'] >= 3 and p['phase'] != 'proceed':
                    return 'choose:1'
                return host.first_legal(view)
            try:
                result = host.run_event(native.request, provider=repeat_provider,
                                        clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            success = scenario in ('P_REPEAT', 'P_REVISIT', 'P_DELAY', 'P_DANGER')
            assert (result['status'] == 'resolved') == success, (scenario, result)
            expected_calls = 3 if scenario == 'P_DANGER' else 12 if scenario == 'P_BOUND' else 5 if success else 2
            end = native.telemetry[-1]
            assert end['chosen_calls'] == native.posts == expected_calls, (scenario, end, result)
            assert all(n <= 1 for n in end['control_calls']), end
            assert end['map_open'] == success and result['child_episodes'] == 0, result
            assert result['parent_reconciled'] == (expected_calls if success or scenario == 'P_BOUND' else 1), result
            if success:
                completed_history(result, native, 0)
                assert result['effects'] == 'unverified', result
            if scenario in ('P_REPEAT', 'P_REVISIT', 'P_DELAY'):
                pages = [e['parent'] for e in native.envelopes if e['kind'] == 'decision' and e['parent']['status'] == 'ready']
                loops = [p for p in pages if p['candidates'][0]['stable_id'] == 'LINGER']
                assert len(loops) >= 2 and len({p['decision_id'] for p in loops}) == len(loops), loops
                assert end['linger_calls'] == 2, end
            if scenario == 'P_DELAY':
                assert any(e['kind'] == 'decision' and e['parent']['status'] == 'waiting' for e in native.envelopes)
            checks += 1
            native_checks += 1
        event_types = set()
        for scenario in ('FIRST_EVENT', 'ANOTHER_EVENT', 'HELD_OUT_EVENT', 'DELAYED', 'ALLOCATED_UPGRADE'):
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            try:
                result = host.run_event(native.request, provider=planned(('select:15', 'confirm')) if scenario == 'ALLOCATED_UPGRADE' else host.first_legal,
                                        clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            assert result['status'] == 'resolved', (scenario, result, native.envelopes[-1])
            completed_history(result, native, 1)
            assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 2
            assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == 2
            assert result['child_episodes'] == 1 and native.posts == 4, result
            end = native.telemetry[-1]
            event_types.add(end['event_type'])
            assert end['upgraded_cards'] == 1 and end['map_open'] and end['overlay_count'] == 0, end
            assert (end['chosen_calls'], end['select_calls'], end['confirm_calls']) == (2, 1, 1), end
            actions = [v['payload']['action_id'] for v in native.envelopes
                       if v['kind'] == 'action' and v['child']]
            assert actions == ['select:15' if scenario == 'ALLOCATED_UPGRADE' else 'select:0', 'confirm'], actions
            selected_slot = 15 if scenario == 'ALLOCATED_UPGRADE' else 0
            assert end['remaining_originals'] == list(range(len(end['baseline_keys'])))
            assert end['remaining_keys'] == end['baseline_keys']
            assert end['remaining_levels'] == [level + (i == selected_slot) for i, level in enumerate(end['baseline_levels'])]
            decisions = [v for v in native.envelopes if v['kind'] == 'decision']
            assert any(v['payload'] and v['payload'].get('phase') == 'preview' for v in decisions)
            resolved = [i for i, v in enumerate(decisions)
                        if v['payload'] and v['payload'].get('kind') == 'child_resolved']
            assert len(resolved) == 1
            assert decisions[resolved[0] + 1]['parent']['prior_results'][0]['result'] == 'child_completed'
            if scenario == 'DELAYED':
                assert any(v['parent']['status'] == 'waiting' and v['child'] is None for v in decisions)
            checks += 1
            native_checks += 1
        assert len(event_types) == 3, event_types
        for scenario in ('ENCHANT_FIRST', 'ENCHANT_DELAY', 'ENCHANT_ALLOCATED', 'ENCHANT_WRONG_EFFECT'):
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            slot = 19 if scenario == 'ENCHANT_ALLOCATED' else 0
            try:
                result = host.run_event(native.request, provider=planned((f'select:{slot}', 'confirm')),
                                        clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            if scenario == 'ENCHANT_WRONG_EFFECT':
                assert result['status'] == 'failed' and result['completed_card_children'] == 0, result
                assert native.telemetry[-1]['confirm_calls'] == 1 and native.posts == 3
            else:
                assert result['status'] == 'resolved', (scenario, result, native.envelopes[-1])
                completed_history(result, native, 1)
                assert result['parent_reconciled'] == result['child_reconciled'] == 2 and native.posts == 4
                end = native.telemetry[-1]
                assert end['enchantment_keys'][slot] == 'SOWN' and end['enchantment_amounts'][slot] == 1
                assert sum(x is not None for x in end['enchantment_keys']) == 1
                assert end['remaining_keys'] == end['baseline_keys'] and end['remaining_levels'] == end['baseline_levels']
                assert end['map_open'] and end['overlay_count'] == 0
                payloads = [v['payload'] for v in native.envelopes if v.get('child')]
                assert all(p['version'] == 'card_enchant_v1' for p in payloads)
                assert all(p['enchantment'] == {'key': 'SOWN', 'amount': 1}
                           for p in payloads if p.get('status') in ('ready', 'resolved'))
            checks += 1
            native_checks += 1
        removal_types = set()
        native_removal_cases = (
            ('R_POST_ADD', 2, 2, 5, ('select:3', 'select:1', 'confirm')),
            ('R_POST_ADD_DELAY', 2, 2, 5, ('select:3', 'select:1', 'confirm')),
            ('R_FIRST', 2, 2, 5, ('select:3', 'select:1', 'confirm')),
            ('R_ANOTHER', 1, 3, 5, ('select:3', 'preview', 'confirm')),
            ('R_HELD_OUT', 1, 3, 5, ('select:3', 'select:1', 'select:0', 'confirm')),
            ('R_VARIABLE_TWO', 1, 3, 5, ('select:3', 'select:1', 'preview', 'confirm')),
            ('R_EIGHT', 8, 8, 9, tuple(f'select:{i}' for i in range(8, 0, -1)) + ('confirm',)),
            ('R_DELAYED_CREATION', 2, 2, 5, ('select:3', 'select:1', 'confirm')),
            ('R_DELAYED_COMPLETION', 2, 2, 5, ('select:3', 'select:1', 'confirm')),
        )
        for scenario, minimum, maximum, domain, actions in native_removal_cases:
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            try:
                result = host.run_event(native.request, provider=planned(actions),
                                        clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            assert result['status'] == 'resolved', (scenario, result, native.envelopes[-1])
            completed_history(result, native, 1)
            assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 2
            assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == len(actions)
            assert result['child_episodes'] == 1 and native.posts == len(actions) + 2
            end = native.telemetry[-1]
            removal_types.add(end['event_type'])
            selected = {int(a[7:]) for a in actions if a.startswith('select:')}
            expected_indices = [i for i in range(len(end['baseline_keys'])) if i not in selected]
            appended = scenario.startswith('R_POST_ADD')
            assert end['remaining_originals'] == expected_indices + ([-1] if appended else []), (scenario, end)
            assert end['remaining_keys'] == [end['baseline_keys'][i] for i in expected_indices] + (['ULTIMATE_STRIKE'] if appended else [])
            assert end['remaining_levels'] == [end['baseline_levels'][i] for i in expected_indices] + ([0] if appended else [])
            payload = next(v['payload'] for v in native.envelopes if v['payload'] and v['payload'].get('kind') == 'child_resolved')
            assert payload['version'] == 'card_remove_v2'
            assert payload['parent_additions'] == dict(status='unverified', cards=[dict(key='ULTIMATE_STRIKE', upgrade_level=0, enchantment=None)] if appended else [])
            assert end['upgraded_cards'] == 0 and end['map_open'] and end['overlay_count'] == 0
            assert (end['chosen_calls'], end['select_calls'], end['preview_calls'], end['confirm_calls']) == (
                2, len(selected), 1, 1), (scenario, end)
            emitted = tuple(v['payload']['action_id'] for v in native.envelopes if v['kind'] == 'action' and v['child'])
            assert emitted == actions
            decisions = [v for v in native.envelopes if v['kind'] == 'decision']
            children = [v for v in decisions if v['child']]
            assert all((v['child']['operation'], v['child']['min_select'], v['child']['max_select'],
                        v['child']['domain_count'], v['child']['commit_mode']) ==
                       ('remove', minimum, maximum, domain, 'preview_confirm') for v in children)
            assert any(v['payload']['phase'] == 'preview' for v in children)
            resolved = [i for i, v in enumerate(decisions) if v['payload'] and v['payload'].get('kind') == 'child_resolved']
            assert len(resolved) == 1
            assert {c['slot'] for c in decisions[resolved[0]]['payload']['selected_cards']} == selected
            assert decisions[resolved[0] + 1]['parent']['prior_results'][0]['result'] == 'child_completed'
            if scenario == 'R_DELAYED_CREATION':
                assert any(v['parent']['status'] == 'waiting' and v['child'] is None for v in decisions)
            if scenario in ('R_DELAYED_COMPLETION', 'R_POST_ADD_DELAY'):
                assert any(v['payload']['status'] == 'waiting' for v in children)
            checks += 1
            native_checks += 1
        assert len(removal_types) == 3, removal_types
        reward_types = set()
        native_reward_cases = (
            ('A_DERIVED', 2, 2, 5, 'auto_at_max', ('select:3', 'select:1')),
            ('A_FIRST', 2, 2, 5, 'auto_at_max', ('select:3', 'select:1')),
            ('A_ANOTHER', 1, 3, 5, 'explicit_confirm', ('select:3', 'confirm')),
            ('A_HELD_OUT', 1, 3, 5, 'auto_at_max', ('select:3', 'select:1', 'select:0')),
            ('A_EXPLICIT_FIXED', 2, 2, 5, 'explicit_confirm', ('select:3', 'select:1', 'confirm')),
            ('A_EXPLICIT_MAX', 1, 3, 5, 'explicit_confirm', ('select:3', 'select:1', 'select:0', 'confirm')),
            ('A_AUTO_EIGHT', 8, 8, 9, 'auto_at_max', tuple(f'select:{i}' for i in range(8, 0, -1))),
            ('A_EXPLICIT_EIGHT', 8, 8, 9, 'explicit_confirm', tuple(f'select:{i}' for i in range(8, 0, -1)) + ('confirm',)),
            ('A_DELAYED_CREATION', 2, 2, 5, 'auto_at_max', ('select:3', 'select:1')),
            ('A_PARTIAL', 2, 2, 5, 'auto_at_max', ('select:3', 'select:1')),
            ('A_DELAYED_COMPLETION', 2, 2, 5, 'explicit_confirm', ('select:3', 'select:1', 'confirm')),
        )
        for scenario, minimum, maximum, domain, mode, actions in native_reward_cases:
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            try:
                result = host.run_event(native.request, provider=planned(actions), clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            assert result['status'] == 'resolved', (scenario, result, native.envelopes[-1])
            completed_history(result, native, 1)
            assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 2
            assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == len(actions)
            assert result['child_episodes'] == 1 and native.posts == len(actions) + 2
            end = native.telemetry[-1]
            reward_types.add(end['event_type'])
            baseline_count = len(end['baseline_keys'])
            slots = {int(a[7:]) for a in actions if a.startswith('select:')}
            selected_offers = {end['slot_offer_indices'][slot] for slot in slots}
            deck_indices = end['deck_originals']
            assert [i for i in deck_indices if i < baseline_count] == list(range(baseline_count)), end
            assert set(i - baseline_count for i in deck_indices if i >= baseline_count) == selected_offers
            assert len(deck_indices) == baseline_count + len(slots) and len(set(deck_indices)) == len(deck_indices)
            all_keys = end['baseline_keys'] + end['offer_keys']
            all_levels = end['baseline_levels'] + end['offer_levels']
            assert end['remaining_keys'] == [all_keys[i] for i in deck_indices]
            assert end['remaining_levels'] == [all_levels[i] for i in deck_indices]
            assert end['map_open'] and end['overlay_count'] == 0 and end['preview_calls'] == 0
            assert (end['chosen_calls'], end['select_calls'], end['confirm_calls']) == (2, len(slots), actions.count('confirm'))
            if scenario == 'A_DERIVED':
                assert end['derived_hitboxes_retained'], end
            children = [v for v in native.envelopes if v['kind'] == 'decision' and v['child']]
            assert all((v['child']['operation'], v['child']['min_select'], v['child']['max_select'], v['child']['commit_mode'], v['child']['domain_count']) ==
                       ('add', minimum, maximum, mode, domain) for v in children)
            assert all(v['payload']['phase'] != 'preview' for v in children)
            resolved = [v['payload'] for v in children if v['payload']['kind'] == 'child_resolved']
            assert len(resolved) == 1 and {c['slot'] for c in resolved[0]['selected_cards']} == slots
            assert {c['key'] for c in resolved[0]['selected_cards']} == {end['offer_keys'][i] for i in selected_offers}
            assert tuple(r['action_id'] for r in resolved[0]['prior_results']) == actions
            assert resolved[0]['prior_results'][-1]['result'] == ('selected' if mode == 'auto_at_max' else 'committed')
            if scenario in ('A_HELD_OUT', 'A_AUTO_EIGHT'):
                assert end['slot_offer_indices'] != list(range(domain)), end
            if scenario == 'A_DELAYED_CREATION':
                assert any(v['kind'] == 'decision' and v['parent']['status'] == 'waiting' for v in native.envelopes)
            if scenario in ('A_PARTIAL', 'A_DELAYED_COMPLETION'):
                assert any(v['payload']['status'] == 'waiting' for v in children)
            if scenario == 'A_PARTIAL':
                assert any(len(t['deck_originals']) == baseline_count + 1 for t in native.telemetry)
            checks += 1
            native_checks += 1
        assert len(reward_types) == 3, reward_types

        for scenario, actions in (('A_FIRST', ('select:3', 'select:1')),
                                  ('A_EXPLICIT_FIXED', ('select:3', 'select:1', 'confirm'))):
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            def lose_native_final(method: str, route: str, body: bytearray | None) -> bytearray:
                response = native.request(method, route, body)
                if method == 'POST' and json.loads(body)['action_id'] == actions[-1]:
                    response[:] = b'\0' * len(response)
                    raise host.TransportFailure()
                return response
            try:
                result = host.run_event(lose_native_final, provider=planned(actions), clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            assert result['code'] == 'transport_failure' and result['effects'] == 'unverified', result
            assert result['parent_accepted'] == 1 and result['parent_reconciled'] == 0
            assert result['child_attempted'] == len(actions) and result['child_accepted'] == len(actions) - 1
            assert native.posts == len(actions) + 1
            assert len(native.telemetry[-1]['deck_originals']) == len(native.telemetry[-1]['baseline_keys']) + 2
            checks += 1
            native_checks += 1


        multi_types = set()
        multi_baseline_reads = 0
        multi_cases = (('U_FIRST', 2, 5), ('U_ANOTHER', 2, 5), ('U_HELD_OUT', 2, 5),
                       ('U_EIGHT', 8, 9), ('U_DELAYED_CREATION', 2, 5),
                       ('U_DELAYED_COMPLETION', 2, 5), ('U_DEFERRED', 2, 5), ('U_PARTIAL', 2, 5), ('U_PARTIAL_EFFECT', 2, 5), ('U_ALLOCATED', 2, 20))
        for scenario, count, domain in multi_cases:
            actions = (tuple(f'select:{i}' for i in range(8, 0, -1)) if count == 8 else ('select:15', 'select:19') if scenario == 'U_ALLOCATED' else ('select:3', 'select:1')) + ('confirm',)
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            try:
                result = host.run_event(native.request, provider=planned(actions), clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            assert result['status'] == 'resolved', (scenario, result, native.envelopes[-1])
            completed_history(result, native, 1)
            assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 2
            assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == count + 1
            assert result['child_episodes'] == 1 and native.posts == count + 3
            end = native.telemetry[-1]
            multi_types.add(end['event_type'])
            selected = {int(a[7:]) for a in actions if a.startswith('select:')}
            assert end['remaining_originals'] == list(range(len(end['baseline_keys'])))
            assert end['remaining_keys'] == end['baseline_keys']
            assert end['remaining_levels'] == [level + (i in selected) for i, level in enumerate(end['baseline_levels'])]
            assert end['upgraded_cards'] == count and end['map_open'] and end['overlay_count'] == 0
            assert end['multi_completion_valid'] and (end['chosen_calls'], end['select_calls'], end['confirm_calls']) == (2, count, 1)
            actual_actions = tuple(v['payload']['action_id'] for v in native.envelopes if v['kind'] == 'action' and v['child'])
            assert actual_actions == actions
            decisions = [v for v in native.envelopes if v['kind'] == 'decision']
            children = [v for v in decisions if v['child']]
            assert all((v['child']['operation'], v['child']['min_select'], v['child']['max_select'], v['child']['domain_count'], v['child']['commit_mode']) ==
                       ('upgrade', count, count, domain, 'preview_confirm') for v in children)
            assert all('preview' not in v['payload'].get('legal_actions', []) for v in children)
            previews = [v for v in children if v['payload']['phase'] == 'preview']
            assert previews and all({c['slot'] for c in v['payload']['candidates'] if c['selected']} == selected for v in previews)
            resolved = [v['payload'] for v in children if v['payload']['kind'] == 'child_resolved']
            assert len(resolved) == 1 and {c['slot'] for c in resolved[0]['selected_cards']} == selected
            assert tuple(r['action_id'] for r in resolved[0]['prior_results']) == actions
            if not multi_baseline_reads:
                multi_baseline_reads = result['reads']
            if scenario in ('U_DELAYED_CREATION', 'U_DELAYED_COMPLETION', 'U_DEFERRED', 'U_PARTIAL', 'U_PARTIAL_EFFECT'):
                assert result['reads'] > multi_baseline_reads, (scenario, result)
                assert any(v['parent']['status'] == 'waiting' or v['payload'] and v['payload']['status'] == 'waiting' for v in decisions)
            if scenario == 'U_PARTIAL_EFFECT':
                assert any(t['upgraded_cards'] == 1 for t in native.telemetry)
            checks += 1
            native_checks += 1
        assert len(multi_types) == 3, multi_types

        for scenario in ('U_FOREIGN_PREVIEW', 'U_REPLACED_PREVIEW'):
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            try:
                result = host.run_event(native.request, provider=planned(('select:3', 'select:1', 'confirm')), clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            assert result['code'] == 'unsupported_state' and result['completed_card_children'] == 0, (scenario, result)
            assert result['child_accepted'] == result['child_reconciled'] == 2 and result['child_attempted'] == 3
            assert native.posts == 4 and native.telemetry[-1]['confirm_calls'] == 0 and native.telemetry[-1]['upgraded_cards'] == 0
            assert not any(v['payload'] and v['payload'].get('kind') == 'child_resolved' for v in native.envelopes)
            checks += 1
            native_checks += 1

        native = Exchange(args.dotnet, args.native_fixture, 'U_HELD_OUT', native=True)
        def lose_multi_confirm(method: str, route: str, body: bytearray | None) -> bytearray:
            response = native.request(method, route, body)
            if method == 'POST' and json.loads(body)['action_id'] == 'confirm':
                response[:] = b'\0' * len(response)
                raise host.TransportFailure()
            return response
        try:
            result = host.run_event(lose_multi_confirm, provider=planned(('select:3', 'select:1', 'confirm')), clock=lambda: 1.0, sleep=lambda _: None)
        finally:
            native.close()
        assert result['code'] == 'transport_failure' and result['completed_card_children'] == 0, result
        assert result['parent_accepted'] == 1 and result['parent_reconciled'] == 0
        assert result['child_attempted'] == 3 and result['child_accepted'] == 2 and native.posts == 4
        assert native.telemetry[-1]['confirm_calls'] == 1 and native.telemetry[-1]['upgraded_cards'] == 2
        checks += 1
        native_checks += 1



    if args.native_fixture is not None:
        for scenario, count in [('ENCHANT_MULTI_TWO',2),('ENCHANT_MULTI_EIGHT',8)]:
            ex=Exchange(args.dotnet,args.native_fixture,scenario,native=True)
            try:
                result=host.run_event(ex.request,provider=planned(tuple(f'select:{19-i}' for i in range(count))+('confirm',)),clock=lambda:1.0,sleep=lambda _:None)
            finally:
                ex.close()
            assert result['status']=='resolved' and result['completed_card_children']==1, (scenario,result,ex.envelopes[-1])
            assert result['child_accepted']==result['child_reconciled']==count+1
            end=ex.telemetry[-1]
            assert end['remaining_originals']==list(range(20)) and end['confirm_calls']==1
            assert end['enchantment_keys']==[None]*(20-count)+['STEADY']*count
            assert end['enchantment_amounts']==[None]*(20-count)+[1]*count
            assert all(v['child']['contract_version']=='card_enchant_v2' for v in ex.envelopes if v['child'])
            checks+=1;native_checks+=1

    if args.native_fixture is not None:
        from generic_event_transform_cases import run_transform_cases
        added = run_transform_cases(args, host, Exchange, planned, completed_history)
        checks += added
        native_checks += added

    if args.native_fixture is not None:
        from generic_event_card_reward_set_cases import run_card_reward_set_cases
        added=run_card_reward_set_cases(args,host,Exchange)
        checks+=added
        native_checks+=added
        from generic_event_card_reward_cases import run_card_reward_cases
        added=run_card_reward_cases(args,host,Exchange)
        checks+=added
        native_checks+=added
        from generic_event_item_cases import run_item_cases
        added = run_item_cases(args, host, Exchange, completed_history)
        checks += added
        native_checks += added

    if args.native_fixture is not None:
        from generic_event_variable_transform_cases import run_variable_transform_cases
        added = run_variable_transform_cases(args, host, Exchange, planned, completed_history)
        checks += added
        native_checks += added

        from generic_event_offer_cases import run_offer_cases
        added=run_offer_cases(args,host,Exchange)
        checks+=added
        native_checks+=added

        from generic_event_surface_cases import run_surface_cases
        added=run_surface_cases(args,host,Exchange)
        checks+=added
        native_checks+=added

    print(json.dumps({'schema_version': 1, 'status': 'passed',
                      'suite': 'generic_event_v7_integration', 'check_count': checks,
                      'production_native_checks': native_checks}, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
