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
                     'chosen_calls', 'select_calls', 'confirm_calls') if self.native else
                    ('body', 'parent_dispatches', 'card_dispatches', 'before_child_effects', 'disposed_children'))
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
            'before_child_effects': 1, 'disposed_children': 1}, ex.telemetry
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

    print(json.dumps({'schema_version': 1, 'status': 'passed',
                      'suite': 'generic_event_v1_integration', 'check_count': checks,
                      'production_native_checks': native_checks}, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
