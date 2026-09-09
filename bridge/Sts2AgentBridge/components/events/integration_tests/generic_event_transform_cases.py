"""Transform cases through production native hooks, the new core, wire, and host."""
from __future__ import annotations

import json
from typing import Any, Callable


def run_transform_cases(args: Any, host: Any, exchange_type: Any,
                        planned: Callable, completed_history: Callable) -> int:
    checks = 0

    def run(scenario: str, actions: tuple[str, ...], wrapper: Callable | None = None) -> tuple[dict, Any]:
        exchange = exchange_type(args.dotnet, args.native_fixture, scenario, native=True)
        request = exchange.request if wrapper is None else lambda m, r, b: wrapper(exchange, m, r, b)
        try:
            result = host.run_event(request, provider=planned(actions), clock=lambda: 1.0, sleep=lambda _: None)
        finally:
            exchange.close()
        return result, exchange

    pair = ('select:3', 'select:1', 'confirm')
    cases = (
        ('T_GENERIC_BIRD', 1, 4, ('select:2', 'confirm'), 1),
        ('T_GENERIC_TORUS', 1, 4, ('select:2', 'confirm'), 1),
        ('T_FIRST', 1, 4, ('select:2', 'confirm'), 1),
        ('T_ANOTHER', 2, 5, pair, 1),
        ('T_HELD_OUT', 2, 5, pair, 1),
        ('T_EIGHT', 8, 9, tuple(f'select:{i}' for i in range(8, 0, -1)) + ('confirm',), 1),
        ('T_SINGLETONS', 2, 5, pair, 2),
        ('T_MIXED_BATCHES', 3, 5, ('select:4', 'select:2', 'select:0', 'confirm'), 2),
        ('T_SUBSTITUTE', 2, 5, pair, 1),
        ('T_PARTIAL', 2, 5, pair, 1),
        ('T_DELAYED_CREATION', 2, 5, pair, 1),
        ('T_DELAYED_COMPLETION', 2, 5, pair, 1),
        ('T_DEFERRED_CONFIRM', 2, 5, pair, 1),
    )
    event_types = set()
    for scenario, count, domain, actions, batches in cases:
        result, ex = run(scenario, actions)
        assert result['status'] == 'resolved', (scenario, result, ex.envelopes[-1])
        completed_history(result, ex, 1)
        assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 2
        assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == count + 1
        assert result['child_episodes'] == 1 and ex.posts == count + 3
        end = ex.telemetry[-1]
        if scenario in ('T_FIRST', 'T_ANOTHER', 'T_HELD_OUT'):
            event_types.add(end['event_type'])
        selected = {int(a[7:]) for a in actions if a.startswith('select:')}
        assert end['transform_completion_valid'] and end['transform_batches'] == batches, (scenario, end)
        assert len(end['transform_originals']) == count and set(end['transform_originals']) == selected
        assert len(set(end['transform_originals'])) == count
        survivors = [i for i in range(len(end['baseline_keys'])) if i not in selected]
        assert end['remaining_originals'] == survivors + [-1] * count, (scenario, end)
        assert end['remaining_keys'] == [end['baseline_keys'][i] for i in survivors] + end['transform_final_keys']
        assert end['remaining_levels'] == [end['baseline_levels'][i] for i in survivors] + end['transform_final_levels']
        assert end['map_open'] and end['overlay_count'] == 0
        assert (end['chosen_calls'], end['select_calls'], end['confirm_calls']) == (2, count, 1)
        children = [v for v in ex.envelopes if v['kind'] == 'decision' and v['child']]
        assert all((v['child']['operation'], v['child']['min_select'], v['child']['max_select'],
                    v['child']['domain_count'], v['child']['commit_mode']) ==
                   ('transform', count, count, domain, 'preview_confirm') for v in children)
        payloads = [v['payload'] for v in ex.envelopes if v['child'] and v['payload']]
        assert payloads and all(p['version'] == 'card_transform_v2' for p in payloads)
        assert all('preview' not in v['payload'].get('legal_actions', []) for v in children)
        resolved = [v['payload'] for v in children if v['payload']['kind'] == 'child_resolved']
        assert len(resolved) == 1
        done = resolved[0]
        assert {c['slot'] for c in done['selected_cards']} == selected
        assert all(c['key'] == end['baseline_keys'][c['slot']] and
                   c['upgrade_level'] == end['baseline_levels'][c['slot']] for c in done['selected_cards'])
        assert tuple(r['action_id'] for r in done['prior_results']) == actions
        assert done['prior_results'][-1]['result'] == 'committed'
        assert tuple(v['payload']['action_id'] for v in ex.envelopes if v['kind'] == 'action' and v['child']) == actions
        # Replacement identities and command witnesses are exclusively inert telemetry.
        public = json.dumps(ex.envelopes)
        assert all(key not in public for key in end['transform_final_keys'])
        if scenario == 'T_PARTIAL':
            baseline_count = len(end['baseline_keys'])
            assert any(len(t['remaining_keys']) == baseline_count - count + 1 for t in ex.telemetry)
            assert any(v['payload']['status'] == 'waiting' for v in children)
        if scenario == 'T_DELAYED_CREATION':
            assert any(v['kind'] == 'decision' and v['parent']['status'] == 'waiting' and v['child'] is None
                       for v in ex.envelopes)
        if scenario in ('T_DELAYED_COMPLETION', 'T_DEFERRED_CONFIRM'):
            assert any(v['payload']['status'] == 'waiting' for v in children)
        checks += 1
    assert len(event_types) == 3, event_types

    result, ex = run('T_GENERIC_FAULT', ('select:2', 'confirm'))
    assert result['status'] != 'resolved' and result['completed_card_children'] == 0
    assert ex.telemetry[-1]['confirm_calls'] == 1 and not ex.telemetry[-1]['map_open']
    checks += 1

    def lose_generic_confirm(ex, method, route, body):
        response = ex.request(method, route, body)
        if method == 'POST' and json.loads(body)['action_id'] == 'confirm':
            response[:] = b'\0' * len(response)
            raise host.TransportFailure()
        return response
    result, ex = run('T_GENERIC_BIRD', ('select:2', 'confirm'), lose_generic_confirm)
    assert result['code'] == 'transport_failure' and result['completed_card_children'] == 0
    assert ex.telemetry[-1]['confirm_calls'] == 1 and ex.posts == 3
    checks += 1

    for lost_action in ('select:3', 'confirm'):
        def lose(ex: Any, method: str, route: str, body: bytearray | None) -> bytearray:
            response = ex.request(method, route, body)
            if method == 'POST' and json.loads(body)['action_id'] == lost_action:
                response[:] = b'\0' * len(response)
                raise host.TransportFailure()
            return response
        result, ex = run('T_HELD_OUT', pair, lose)
        attempted = 1 if lost_action == 'select:3' else 3
        assert result['code'] == 'transport_failure' and result['completed_card_children'] == 0
        assert result['effects'] == 'unverified' and result['parent_reconciled'] == 0
        assert result['child_attempted'] == attempted and result['child_accepted'] == attempted - 1
        assert ex.posts == attempted + 1
        assert ex.telemetry[-1]['confirm_calls'] == (lost_action == 'confirm')
        checks += 1

    for payload_kind in ('child_observation', 'child_dispatch', 'child_resolved'):
        changed = False
        def wrong_version(ex: Any, method: str, route: str, body: bytearray | None) -> bytearray:
            nonlocal changed
            response = ex.request(method, route, body)
            value = json.loads(response)
            payload = value['payload']
            matches = value['child'] and payload and (
                payload_kind == 'child_observation' and value['kind'] == 'decision' and payload.get('kind') != 'child_resolved' or
                payload_kind == 'child_dispatch' and value['kind'] == 'action' or
                payload_kind == 'child_resolved' and payload.get('kind') == 'child_resolved')
            if not changed and matches:
                payload['version'] = 'card_selection_v1'
                response[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
                changed = True
            return response
        result, ex = run('T_HELD_OUT', pair, wrong_version)
        assert changed and result['code'] == 'invalid_response' and result['completed_card_children'] == 0, (payload_kind, result)
        assert ex.posts == {'child_observation': 1, 'child_dispatch': 2, 'child_resolved': 4}[payload_kind]
        checks += 1
    for scenario in ('T_FOREIGN_PREVIEW', 'T_REPLACED_PREVIEW', 'T_NOTIFICATION',
                     'T_BAD_RESULT', 'T_CALLBACK_FAULT', 'T_COMMAND_FAULT',
                     'T_OWNER_NOTIFICATION', 'T_RUN_NOTIFICATION'):
        result, ex = run(scenario, pair)
        assert result['code'] == 'unsupported_state' and result['completed_card_children'] == 0, (scenario, result)
        assert result['effects'] == 'unverified' and result['parent_reconciled'] == 0
        assert result['child_attempted'] == 3 and ex.posts == 4
        before_confirm = scenario in ('T_FOREIGN_PREVIEW', 'T_REPLACED_PREVIEW')
        assert ex.telemetry[-1]['confirm_calls'] == (0 if before_confirm else 1)
        assert result['child_accepted'] == (2 if before_confirm else 3)
        assert not any(v['payload'] and v['payload'].get('kind') == 'child_resolved' for v in ex.envelopes)
        checks += 1

    changed = False
    def wrong_failure_version(ex: Any, method: str, route: str, body: bytearray | None) -> bytearray:
        nonlocal changed
        response = ex.request(method, route, body)
        value = json.loads(response)
        if value['child'] and value['payload'] and value['payload'].get('kind') == 'child_failure':
            value['payload']['version'] = 'card_selection_v1'
            response[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
            changed = True
        return response
    result, ex = run('T_FOREIGN_PREVIEW', pair, wrong_failure_version)
    assert changed and result['code'] == 'invalid_response' and result['completed_card_children'] == 0
    assert ex.posts == 4 and result['child_accepted'] == 2 and ex.telemetry[-1]['confirm_calls'] == 0
    checks += 1
    mixed_actions = (tuple(f'select:{i}' for i in range(8, 0, -1)) + ('confirm',)) * 2 + ('select:2', 'select:3', 'confirm')
    result, ex = run('T_MIXED', mixed_actions)
    assert result['status'] == 'resolved', (result, ex.envelopes[-1])
    completed_history(result, ex, 3)
    assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 4
    assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == 21
    assert ex.posts == 25 and result['child_episodes'] == 3
    end = ex.telemetry[-1]
    assert end['map_open'] and end['overlay_count'] == 0 and end['transform_completion_valid']
    assert (end['chosen_calls'], end['select_calls'], end['confirm_calls']) == (4, 18, 3)
    assert end['transform_batches'] == 2 and len(end['transform_final_keys']) == 16
    baseline_count = len(end['baseline_keys'])
    expected = list(range(baseline_count))
    for ordinal, original in enumerate(end['transform_originals']):
        expected.remove(original)
        expected.append(baseline_count + ordinal)
    assert end['deck_originals'] == expected
    assert end['remaining_levels'] == [1 if i in (2, 3) else 0 for i in range(len(expected))]
    completions = [v for v in ex.envelopes if v['kind'] == 'decision' and v['payload'] and v['payload'].get('kind') == 'child_resolved']
    assert [(v['payload']['operation'], v['payload']['version']) for v in completions] == [
        ('transform', 'card_transform_v2'), ('transform', 'card_transform_v2'), ('upgrade', 'card_selection_v1')]
    assert any(index >= baseline_count for index in end['transform_originals']), 'second transform did not reuse current baseline finals'
    checks += 1

    def lose_last_confirm(ex: Any, method: str, route: str, body: bytearray | None) -> bytearray:
        response = ex.request(method, route, body)
        if method == 'POST':
            action = json.loads(body)
            if action['child'] and action['child']['ordinal'] == 3 and action['action_id'] == 'confirm':
                response[:] = b'\0' * len(response)
                raise host.TransportFailure()
        return response
    result, ex = run('T_MIXED', mixed_actions, lose_last_confirm)
    assert result['code'] == 'transport_failure' and result['completed_card_children'] == 2
    assert result['effects'] == 'unverified' and result['parent_reconciled'] == 2
    assert result['child_attempted'] == 21 and result['child_accepted'] == 20 and ex.posts == 24
    assert ex.telemetry[-1]['confirm_calls'] == 3
    checks += 1

    result, ex = run('T_MIXED_BAD_UPGRADE', mixed_actions)
    assert result['code'] == 'unsupported_state' and result['completed_card_children'] == 2, result
    assert result['effects'] == 'unverified' and result['parent_reconciled'] == 2
    assert result['child_attempted'] == 21 and result['child_accepted'] == 20 and ex.posts == 24
    assert ex.telemetry[-1]['confirm_calls'] == 2
    checks += 1
    return checks
