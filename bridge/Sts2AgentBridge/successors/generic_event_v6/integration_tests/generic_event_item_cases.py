"""Singleton items through actual native hooks, frozen ItemV1, wire and Python."""
from __future__ import annotations

import json
from typing import Any, Callable


def run_item_cases(args: Any, host: Any, exchange_type: Any, completed_history: Callable) -> int:
    checks = 0

    def run(scenario: str, wrapper: Callable | None = None) -> tuple[dict, Any]:
        ex = exchange_type(args.dotnet, args.native_fixture, scenario, native=True)
        request = ex.request if wrapper is None else lambda m, r, b: wrapper(ex, m, r, b)
        try:
            result = host.run_event(request, provider=host.first_legal, clock=lambda: 1.0, sleep=lambda _: None)
        finally:
            ex.close()
        return result, ex

    def item_decisions(ex: Any) -> list[dict]:
        return [v for v in ex.envelopes if v['kind'] == 'decision' and v['child'] and v['child']['kind'] == 'item']

    types, relic_types = set(), set()
    for scenario in ('I_FIRST', 'I_ANOTHER', 'I_HELD_OUT', 'I_RELIC', 'I_INDEX255',
                     'I_DELAYED_CREATION', 'I_DELAYED_COLLECTION', 'I_DELAYED_OFFER', 'I_DELAYED_CHOSEN',
                     'I_REPEAT', 'I_MIXED', 'I_RELIC_FIRST', 'I_RELIC_ANOTHER', 'I_RELEASE_DISABLED', 'I_DERIVED'):
        result, ex = run(scenario)
        assert result['status'] == 'resolved', (scenario, result, ex.envelopes[-1])
        items = 2 if scenario in ('I_REPEAT', 'I_MIXED') else 1
        cards = 2 if scenario == 'I_MIXED' else 0
        completed_history(result, ex, cards, items)
        assert result['child_episodes'] == items + cards
        assert result['parent_attempted'] == result['parent_accepted'] == result['parent_reconciled'] == items + cards + 1
        assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled']
        assert result['total_attempted'] == ex.posts == result['parent_attempted'] + result['child_attempted']
        end = ex.telemetry[-1]
        assert end['completion_valid'] and end['map_open'] and end['overlay_count'] == 0, (scenario, end)
        assert end['item_completions'] == items
        assert end['collect_calls'] == items and end['chosen_calls'] == items + cards + 1
        if not cards:
            assert result['child_attempted'] == items
            assert end['remaining_keys'] == end['baseline_keys'] and end['remaining_levels'] == end['baseline_levels']
        if scenario in ('I_FIRST', 'I_ANOTHER', 'I_HELD_OUT'):
            types.add(end['event_type'])
        if scenario in ('I_RELIC_FIRST', 'I_RELIC_ANOTHER', 'I_RELIC'):
            relic_types.add(end['event_type'])
        decisions = item_decisions(ex)
        assert decisions
        assert all(v['payload']['protocol'] == 'item_probe_v1' and v['payload']['version'] == 'item_v1' and
                   v['payload']['surface_ordinal'] == 1 for v in decisions)
        ready = [v for v in decisions if v['payload']['status'] == 'ready']
        resolved = [v for v in decisions if v['payload']['status'] == 'resolved']
        assert len(resolved) == items
        for value in resolved:
            owner = value['child']['ordinal']
            published = next(v['payload'] for v in ready if v['child']['ordinal'] == owner)
            offered = published['offers'][0]
            done = value['payload']
            assert len(published['offers']) == 1 and published['legal_actions'] == [f"collect:{offered['index']}"]
            assert (done['offer_index'], done['kind'], done['key'], done['result']) == (offered['index'], offered['kind'], offered['key'], 'collected')
            assert done['decision_id'] == published['decision_id'] and done['action_id'] == published['legal_actions'][0]
        if scenario == 'I_INDEX255':
            assert resolved[0]['payload']['offer_index'] == 255
        if scenario == 'I_REPEAT':
            by_owner = {v['child']['ordinal']: v['payload'] for v in ready}
            assert set(by_owner) == {1, 2} and by_owner[1] == by_owner[2], by_owner
        if scenario == 'I_MIXED':
            families = {v['child']['ordinal']: (v['child']['kind'], v['child'].get('operation'))
                        for v in ex.envelopes if v['child']}
            assert families == {1: ('item', None), 2: ('card_selection', 'upgrade'),
                                3: ('card_selection', 'transform'), 4: ('item', None)}, families
        if scenario == 'I_DELAYED_CREATION':
            assert any(v['kind'] == 'decision' and v['parent']['status'] == 'waiting' and v['child'] is None for v in ex.envelopes)
        if scenario in ('I_DELAYED_COLLECTION', 'I_DELAYED_OFFER', 'I_DELAYED_CHOSEN'):
            waiting = [v for v in decisions if v['payload']['status'] == 'waiting']
            assert waiting and all(v['parent']['parent_attempted'] == 1 and v['parent']['completed_item_children'] == 0 for v in waiting)
        checks += 1
    assert len(types) == len(relic_types) == 3, (types, relic_types)

    for scenario in ('I_FULL', 'I_EXTRA', 'I_HIDDEN', 'I_LINKED', 'I_TERMINAL',
                     'I_TASK_FAULT', 'I_LATE_CLAIM', 'I_LATE_SLOT', 'I_REPLACED_BUTTON'):
        result, ex = run(scenario)
        assert result['code'] == 'unsupported_state', (scenario, result, ex.envelopes[-1])
        assert result['completed_item_children'] == result['completed_card_children'] == 0
        assert result['parent_reconciled'] == result['child_reconciled'] == 0
        after_collect = scenario in ('I_TASK_FAULT', 'I_LATE_CLAIM', 'I_LATE_SLOT')
        assert ex.telemetry[-1]['collect_calls'] == int(after_collect), (scenario, ex.telemetry[-1])
        assert result['child_accepted'] == int(after_collect)
        assert ex.posts == (2 if after_collect or scenario == 'I_REPLACED_BUTTON' else 1)
        checks += 1

    for stage in ('collect', 'terminal', 'second_collect'):
        lost = False
        def lose(ex: Any, method: str, route: str, body: bytearray | None) -> bytearray:
            nonlocal lost
            response = ex.request(method, route, body)
            value = json.loads(response)
            child = value['child']
            if child and child['kind'] == 'item' and not lost and (
                stage == 'terminal' and value['payload']['status'] == 'resolved' or
                stage != 'terminal' and method == 'POST' and child['ordinal'] == (2 if stage == 'second_collect' else 1)):
                lost = True
                response[:] = b'\0' * len(response)
                raise host.TransportFailure()
            return response
        result, ex = run('I_REPEAT' if stage == 'second_collect' else 'I_HELD_OUT', lose)
        assert lost and result['code'] == 'transport_failure', (stage, result)
        previous = int(stage == 'second_collect')
        assert result['completed_item_children'] == previous and result['completed_card_children'] == 0
        assert result['child_attempted'] == previous + 1
        assert result['child_accepted'] == previous + int(stage == 'terminal')
        assert result['child_reconciled'] == previous
        assert ex.telemetry[-1]['collect_calls'] == previous + 1 and ex.posts == 2 * (previous + 1)
        checks += 1

    for change in ('version', 'kind', 'offer_count', 'surface_ordinal', 'receipt_action', 'resolved_index', 'resolved_key', 'old_lineage'):
        changed = False
        first_child = None
        def corrupt(ex: Any, method: str, route: str, body: bytearray | None) -> bytearray:
            nonlocal changed, first_child
            response = ex.request(method, route, body)
            value = json.loads(response)
            child, payload = value['child'], value['payload']
            if not child or child['kind'] != 'item' or changed:
                return response
            if first_child is None:
                first_child = dict(child)
            status = payload['status']
            if change == 'old_lineage' and child['ordinal'] == 2 and status == 'ready':
                value['child'] = first_child
            elif change in ('version', 'kind', 'offer_count', 'surface_ordinal') and status == 'ready':
                if change == 'version': payload['version'] = 'card_selection_v1'
                elif change == 'kind': child['kind'] = 'card_selection'
                elif change == 'offer_count': child['offer_count'] = 2
                else: payload['surface_ordinal'] = 2
            elif change == 'receipt_action' and status == 'accepted':
                payload['action_id'] = 'collect:8'
            elif change.startswith('resolved_') and status == 'resolved':
                if change == 'resolved_index': payload['offer_index'] = 8
                else: payload['key'] = 'DifferentItem'
            else:
                return response
            changed = True
            response[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
            return response
        result, ex = run('I_REPEAT' if change == 'old_lineage' else 'I_HELD_OUT', corrupt)
        assert changed and result['code'] == 'invalid_response', (change, result)
        assert result['completed_item_children'] == int(change == 'old_lineage') and result['completed_card_children'] == 0
        assert ex.telemetry[-1]['collect_calls'] == int(change in ('receipt_action', 'resolved_index', 'resolved_key', 'old_lineage'))
        assert ex.posts == (3 if change == 'old_lineage' else 2 if change in ('receipt_action', 'resolved_index', 'resolved_key') else 1)
        checks += 1
    return checks
