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
                     'remaining_keys', 'remaining_levels') if self.native else
                    ('body', 'parent_dispatches', 'card_dispatches', 'before_child_effects', 'disposed_children',
                     'remaining_keys', 'remaining_levels'))
        assert tuple(value) == expected, value
        self.telemetry.append({k: value[k] for k in value if k != 'body'})
        response = bytearray(base64.b64decode(value['body'], validate=True))
        self.envelopes.append(json.loads(response))
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
        return result, exchange

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

    native_checks = 0
    if args.native_fixture is not None:
        event_types = set()
        for scenario in ('FIRST_EVENT', 'ANOTHER_EVENT', 'HELD_OUT_EVENT', 'DELAYED'):
            native = Exchange(args.dotnet, args.native_fixture, scenario, native=True)
            try:
                result = host.run_event(native.request, provider=host.first_legal,
                                        clock=lambda: 1.0, sleep=lambda _: None)
            finally:
                native.close()
            assert result['status'] == 'resolved', (scenario, result, native.envelopes[-1])
            assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 2
            assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == 2
            assert result['child_episodes'] == 1 and native.posts == 4, result
            end = native.telemetry[-1]
            event_types.add(end['event_type'])
            assert end['upgraded_cards'] == 1 and end['map_open'] and end['overlay_count'] == 0, end
            assert (end['chosen_calls'], end['select_calls'], end['confirm_calls']) == (2, 1, 1), end
            actions = [v['payload']['action_id'] for v in native.envelopes
                       if v['kind'] == 'action' and v['child']]
            assert actions == ['select:0', 'confirm'], actions
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
        removal_types = set()
        native_removal_cases = (
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
            assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 2
            assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == len(actions)
            assert result['child_episodes'] == 1 and native.posts == len(actions) + 2
            end = native.telemetry[-1]
            removal_types.add(end['event_type'])
            selected = {int(a[7:]) for a in actions if a.startswith('select:')}
            expected_indices = [i for i in range(len(end['baseline_keys'])) if i not in selected]
            assert end['remaining_originals'] == expected_indices, (scenario, end)
            assert end['remaining_keys'] == [end['baseline_keys'][i] for i in expected_indices]
            assert end['remaining_levels'] == [end['baseline_levels'][i] for i in expected_indices]
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
            if scenario == 'R_DELAYED_COMPLETION':
                assert any(v['payload']['status'] == 'waiting' for v in children)
            checks += 1
            native_checks += 1
        assert len(removal_types) == 3, removal_types


    print(json.dumps({'schema_version': 1, 'status': 'passed',
                      'suite': 'generic_event_v2_integration', 'check_count': checks,
                      'production_native_checks': native_checks}, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
