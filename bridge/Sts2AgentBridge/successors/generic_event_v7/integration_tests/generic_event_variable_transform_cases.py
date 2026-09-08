"""Variable transforms through actual native hooks, v2 journal, wire, and host."""
from __future__ import annotations

import json
from typing import Any, Callable


def run_variable_transform_cases(args: Any, host: Any, exchange_type: Any,
                                 planned: Callable, completed_history: Callable) -> int:
    checks = 0

    def run(scenario: str, actions: tuple[str, ...], wrapper: Callable | None = None) -> tuple[dict, Any]:
        ex = exchange_type(args.dotnet, args.native_fixture, scenario, native=True)
        request = ex.request if wrapper is None else lambda m, r, b: wrapper(ex, m, r, b)
        try:
            result = host.run_event(request, provider=planned(actions), clock=lambda: 1.0, sleep=lambda _: None)
        finally:
            ex.close()
        return result, ex

    one = ('select:3', 'preview', 'confirm')
    two = ('select:5', 'select:3', 'preview', 'confirm')
    three = ('select:5', 'select:3', 'select:1', 'preview', 'confirm')
    cases = (
        ('V_FIRST', 1, 3, 5, one),
        ('V_ANOTHER', 2, 4, 6, two),
        ('V_HELD_OUT', 1, 3, 5, one),
        ('V_INTERMEDIATE', 1, 4, 6, two),
        ('V_MAX', 1, 3, 5, ('select:4', 'select:2', 'select:1', 'confirm')),
        ('V_EIGHT', 2, 8, 9, tuple(f'select:{i}' for i in range(8, 0, -1)) + ('confirm',)),
        ('V_EIGHT_EARLY', 2, 8, 9, ('select:8', 'select:2', 'preview', 'confirm')),
        ('V_DELAYED_PREVIEW', 1, 4, 6, three),
        ('V_PARTIAL_PREVIEW', 1, 4, 6, three),
        ('V_RETIRED_ROOT', 1, 4, 6, two),
        ('V_SUBSTITUTE', 1, 4, 6, two),
        ('V_PARTIAL_EFFECT', 1, 4, 6, two),
        ('V_DELAYED_COMPLETION', 1, 4, 6, two),
        ('V_DEFERRED_CONFIRM', 1, 4, 6, two),
    )
    event_types = set()
    for scenario, minimum, maximum, domain, actions in cases:
        result, ex = run(scenario, actions)
        assert result['status'] == 'resolved', (scenario, result, ex.envelopes[-1])
        completed_history(result, ex, 1)
        assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == 2
        assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == len(actions)
        assert result['child_episodes'] == 1 and ex.posts == len(actions) + 2
        end = ex.telemetry[-1]
        selected = {int(action[7:]) for action in actions if action.startswith('select:')}
        count = len(selected)
        assert minimum <= count <= maximum
        assert end['transform_completion_valid'] and end['transform_batches'] == 1, (scenario, end)
        assert len(end['transform_originals']) == count and set(end['transform_originals']) == selected
        assert set(end['selected_originals']) == selected
        survivors = [i for i in range(len(end['baseline_keys'])) if i not in selected]
        assert end['remaining_originals'] == survivors + [-1] * count
        assert end['remaining_keys'] == [end['baseline_keys'][i] for i in survivors] + end['transform_final_keys']
        assert end['remaining_levels'] == [end['baseline_levels'][i] for i in survivors] + end['transform_final_levels']
        assert end['map_open'] and end['overlay_count'] == 0
        assert (end['chosen_calls'], end['select_calls'], end['preview_calls'], end['confirm_calls']) == (2, count, int('preview' in actions), 1)
        if scenario in ('V_FIRST', 'V_ANOTHER', 'V_HELD_OUT'):
            event_types.add(end['event_type'])
        children = [v for v in ex.envelopes if v['kind'] == 'decision' and v['child']]
        for value in children:
            child, payload = value['child'], value['payload']
            assert (child['kind'], child['contract_version'], child['operation'], child['min_select'],
                    child['max_select'], child['domain_count'], child['commit_mode']) == (
                        'card_selection', 'card_transform_v2', 'transform', minimum, maximum, domain, 'preview_confirm')
            assert payload['version'] == 'card_transform_v2'
            if payload['status'] == 'ready':
                slots = payload['selected_slots']
                if payload['phase'] == 'selecting':
                    assert ('preview' in payload['legal_actions']) == (minimum <= len(slots) < maximum)
                    assert 'confirm' not in payload['legal_actions']
                if payload['phase'] == 'preview':
                    assert set(slots) == selected and payload['legal_actions'] == ['confirm']
                    history_actions = [row['action_id'] for row in payload['prior_results']]
                    assert ('preview' in history_actions) == (count < maximum)
        resolved = [v['payload'] for v in children if v['payload'].get('kind') == 'child_resolved']
        assert len(resolved) == 1
        done = resolved[0]
        assert {c['slot'] for c in done['selected_cards']} == selected
        assert all(c['key'] == end['baseline_keys'][c['slot']] and c['upgrade_level'] == end['baseline_levels'][c['slot']] for c in done['selected_cards'])
        assert tuple(row['action_id'] for row in done['prior_results']) == actions
        assert tuple(row['result'] for row in done['prior_results']) == tuple(
            'selected' if action.startswith('select:') else 'previewed' if action == 'preview' else 'committed' for action in actions)
        assert tuple(v['payload']['action_id'] for v in ex.envelopes if v['kind'] == 'action' and v['child']) == actions
        assert all(key not in json.dumps(ex.envelopes) for key in end['transform_final_keys'])
        if scenario in ('V_DELAYED_PREVIEW', 'V_PARTIAL_PREVIEW', 'V_PARTIAL_EFFECT', 'V_DELAYED_COMPLETION', 'V_DEFERRED_CONFIRM'):
            assert any(v['payload']['status'] == 'waiting' for v in children), scenario
        if scenario == 'V_PARTIAL_PREVIEW':
            assert any(v['kind'] == 'decision' and v['payload'] and v['payload']['status'] == 'waiting' and
                       t['preview_holder_count'] == minimum and len(t['selected_originals']) == count
                       for v, t in zip(ex.envelopes, ex.telemetry))
            assert all(t['preview_holder_count'] == count for v, t in zip(ex.envelopes, ex.telemetry)
                       if v['kind'] == 'decision' and v['payload'] and v['payload'].get('phase') == 'preview')
        if scenario == 'V_PARTIAL_EFFECT':
            assert any(len(t['remaining_keys']) == len(end['baseline_keys']) - count + 1 for t in ex.telemetry)
        checks += 1
    assert len(event_types) == 3

    for lost_action in ('preview', 'confirm'):
        def lose(ex: Any, method: str, route: str, body: bytearray | None) -> bytearray:
            response = ex.request(method, route, body)
            if method == 'POST' and json.loads(body)['action_id'] == lost_action:
                response[:] = b'\0' * len(response)
                raise host.TransportFailure()
            return response
        result, ex = run('V_HELD_OUT', one, lose)
        attempted = 2 if lost_action == 'preview' else 3
        assert result['code'] == 'transport_failure' and result['completed_card_children'] == 0
        assert result['effects'] == 'unverified' and result['parent_reconciled'] == 0
        assert result['child_attempted'] == attempted and result['child_accepted'] == attempted - 1
        assert ex.posts == attempted + 1 and ex.telemetry[-1]['preview_calls'] == 1
        assert ex.telemetry[-1]['confirm_calls'] == int(lost_action == 'confirm')
        checks += 1

    for mutation in ('descriptor_v1', 'observation_v1', 'receipt_v1', 'terminal_v1', 'changed_min',
                     'missing_preview_history', 'wrong_terminal_original', 'late_selection_control'):
        changed = False
        def corrupt(ex: Any, method: str, route: str, body: bytearray | None) -> bytearray:
            nonlocal changed
            response = ex.request(method, route, body)
            value = json.loads(response)
            payload = value['payload']
            if changed or not value['child'] or not payload:
                return response
            child = value['child']
            ready = value['kind'] == 'decision' and payload.get('status') == 'ready'
            preview = ready and payload.get('phase') == 'preview'
            done = payload.get('kind') == 'child_resolved'
            if mutation == 'descriptor_v1': child['contract_version'] = 'card_transform_v1'
            elif mutation == 'observation_v1' and ready: payload['version'] = 'card_transform_v1'
            elif mutation == 'receipt_v1' and value['kind'] == 'action': payload['version'] = 'card_transform_v1'
            elif mutation == 'terminal_v1' and done: payload['version'] = 'card_transform_v1'
            elif mutation == 'changed_min' and preview: child['min_select'] = 2
            elif mutation == 'missing_preview_history' and preview:
                payload['prior_results'] = [row for row in payload['prior_results'] if row['action_id'] != 'preview']
            elif mutation == 'wrong_terminal_original' and done:
                selected = payload['selected_cards'][0]
                selected.update(slot=1, key=ex.telemetry[-1]['baseline_keys'][1], upgrade_level=0)
            elif mutation == 'late_selection_control' and preview: payload['legal_actions'].append('select:1')
            else: return response
            response[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
            changed = True
            return response
        result, ex = run('V_HELD_OUT', one, corrupt)
        assert changed and result['code'] == 'invalid_response' and result['completed_card_children'] == 0, (mutation, result)
        expected_posts = 4 if mutation in ('terminal_v1', 'wrong_terminal_original') else 3 if mutation in (
            'changed_min', 'missing_preview_history', 'late_selection_control') else 2 if mutation == 'receipt_v1' else 1
        assert ex.posts == expected_posts, (mutation, result, ex.posts)
        assert ex.telemetry[-1]['confirm_calls'] == int(expected_posts == 4)
        checks += 1

    for scenario in ('V_MANUAL_FALSE', 'V_MIN_ZERO', 'V_MIN_GT_MAX'):
        result, ex = run(scenario, one)
        assert result['code'] == 'unsupported_state' and result['completed_card_children'] == 0, (scenario, result)
        assert ex.posts == 1 and result['child_attempted'] == 0
        assert ex.telemetry[-1]['select_calls'] == ex.telemetry[-1]['preview_calls'] == ex.telemetry[-1]['confirm_calls'] == 0
        checks += 1

    for scenario in ('V_FOREIGN_PREVIEW', 'V_REPLACED_PREVIEW', 'V_DISABLED_ROOT', 'V_REPLACED_ROOT',
                     'V_UNEXPECTED_EARLY', 'V_LOST_PREVIEW', 'V_FAULT_COMMAND', 'V_REOPEN_PREVIEW', 'V_LATE_TASK_FAULT'):
        result, ex = run(scenario, one)
        assert result['status'] != 'resolved' and result['completed_card_children'] == 0, (scenario, result)
        assert result['effects'] == 'unverified' and result['parent_reconciled'] == 0
        assert result['code'] == 'unsupported_state', (scenario, result)
        assert ex.telemetry[-1]['confirm_calls'] == int(scenario in ('V_FAULT_COMMAND', 'V_LATE_TASK_FAULT'))
        assert not any(v['payload'] and v['payload'].get('kind') == 'child_resolved' for v in ex.envelopes)
        expected = 2 if scenario == 'V_UNEXPECTED_EARLY' else 3 if scenario in (
            'V_DISABLED_ROOT', 'V_REPLACED_ROOT', 'V_LOST_PREVIEW') else 4
        assert ex.posts == expected, (scenario, ex.posts, result)
        if scenario == 'V_LOST_PREVIEW':
            assert ex.telemetry[-1]['preview_calls'] == 1 and len(ex.calls) < 270
        checks += 1

    mixed = two + ('select:2', 'select:3', 'confirm')
    result, ex = run('V_MIXED', mixed)
    assert result['status'] == 'resolved', (result, ex.envelopes[-1])
    completed_history(result, ex, 2)
    assert result['child_episodes'] == 2 and result['parent_reconciled'] == 3
    assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == 7 and ex.posts == 10
    assert ex.telemetry[-1]['map_open'] and ex.telemetry[-1]['overlay_count'] == 0
    assert ex.telemetry[-1]['transform_completion_valid']
    done = [v['payload'] for v in ex.envelopes if v['payload'] and v['payload'].get('kind') == 'child_resolved']
    assert [(v['operation'], v['version']) for v in done] == [('transform', 'card_transform_v2'), ('upgrade', 'card_selection_v1')]
    checks += 1
    result, ex = run('V_MIXED_BAD_UPGRADE', mixed)
    assert result['code'] == 'unsupported_state' and result['completed_card_children'] == 1
    assert result['effects'] == 'unverified' and result['parent_reconciled'] == 1
    assert ex.posts == 9 and result['child_attempted'] == 7 and result['child_accepted'] == 6
    assert ex.telemetry[-1]['confirm_calls'] == 1
    checks += 1
    def lose_second_confirm(ex: Any, method: str, route: str, body: bytearray | None) -> bytearray:
        response = ex.request(method, route, body)
        action = json.loads(body) if body else None
        if method == 'POST' and action['action_id'] == 'confirm' and action['child']['ordinal'] == 2:
            response[:] = b'\0' * len(response)
            raise host.TransportFailure()
        return response
    result, ex = run('V_MIXED', mixed, lose_second_confirm)
    assert result['code'] == 'transport_failure' and result['completed_card_children'] == 1
    assert result['effects'] == 'unverified' and result['parent_reconciled'] == 1
    assert ex.posts == 9 and result['child_attempted'] == 7 and result['child_accepted'] == 6
    assert ex.telemetry[-1]['confirm_calls'] == 2
    checks += 1
    return checks
