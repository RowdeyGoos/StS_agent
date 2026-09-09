"""Owned event CardReward menu through native hooks, wire, and the Python host."""
from __future__ import annotations

import json
from typing import Any, Callable


def run_card_reward_cases(args: Any, host: Any, exchange_type: Any) -> int:
    checks = 0

    def run(scenario: str, wrapper: Callable | None = None) -> tuple[dict, Any]:
        ex = exchange_type(args.dotnet, args.native_fixture, scenario, native=True)
        request = ex.request if wrapper is None else lambda m, r, b: wrapper(ex, m, r, b)
        def choose(view: Any) -> str:
            if view.kind != 'parent' and view.payload.get('phase') == 'choose':
                return 'skip' if scenario == 'CR_SKIP' else f"choose:{len(view.payload['cards'])-1}"
            return host.first_legal(view)
        try:
            result = host.run_event(request, provider=choose, clock=lambda: 1.0, sleep=lambda _: None)
        finally:
            ex.close()
        return result, ex

    for scenario in ('CR_ONE', 'CR_FIVE', 'CR_SKIP', 'CR_OFFER', 'CR_COLLECTION', 'CR_CHOICE', 'CR_DEFERRED', 'CR_DISABLED'):
        result, ex = run(scenario)
        assert result['status'] == 'resolved', (scenario, result, ex.envelopes[-1])
        skip = scenario == 'CR_SKIP'
        assert result['child_attempted'] == result['child_accepted'] == result['child_reconciled'] == (3 if skip else 2)
        assert result['completed_card_children'] == result['child_episodes'] == 1
        assert result['completed_item_children'] == 0
        assert result['parent_accepted'] == result['parent_reconciled'] == 2
        end = ex.telemetry[-1]
        assert end == dict(map_open=True, overlay_count=0, opens=1, choices=int(not skip), skips=int(skip),
                           dismisses=int(skip), added_slots=[] if skip else [0 if scenario == 'CR_ONE' else 4 if scenario == 'CR_FIVE' else 2]), end
        children = [e for e in ex.envelopes if e['kind'] == 'decision' and e['child']]
        assert all(e['child']['kind'] == 'card_reward' and e['child']['contract_version'] == 'card_reward_v1' and e['child']['offer_count'] == 1 for e in children)
        resolved = [e['payload'] for e in children if e['payload']['status'] == 'resolved']
        assert len(resolved) == 1
        assert [h['result'] for h in resolved[0]['prior_results']] == (['opened', 'skipped', 'dismissed'] if skip else ['opened', 'collected'])
        if skip:
            assert any(e['payload']['phase'] == 'dismiss' and e['parent']['completed_card_children'] == 0 for e in children)
        if scenario in ('CR_OFFER', 'CR_COLLECTION', 'CR_CHOICE', 'CR_DEFERRED', 'CR_DISABLED'):
            assert any(e['payload']['status'] == 'waiting' for e in children)
        checks += 1

    for scenario in ('CR_WRONG', 'CR_OWNER'):
        result, ex = run(scenario)
        assert result['code'] == 'unsupported_state' and result['completed_card_children'] == 0, (scenario, result)
        assert ex.telemetry[-1]['opens'] == 1 and ex.telemetry[-1]['choices'] == int(scenario == 'CR_WRONG')
        checks += 1

    for stage in ('open', 'choose:2', 'skip', 'dismiss', 'terminal'):
        lost = False
        def lose(ex, method, route, body):
            nonlocal lost
            response = ex.request(method, route, body)
            value = json.loads(response)
            if not lost and value['child'] and (stage == 'terminal' and method == 'GET' and value['payload']['status'] == 'resolved' or
                                                stage != 'terminal' and method == 'POST' and json.loads(body)['action_id'] == stage):
                lost = True
                response[:] = b'\0' * len(response)
                raise host.TransportFailure()
            return response
        result, ex = run('CR_SKIP' if stage in ('skip', 'dismiss') else 'CR_OFFER', lose)
        assert lost and result['code'] == 'transport_failure' and result['completed_card_children'] == 0, (stage, result)
        end = ex.telemetry[-1]
        assert end['opens'] == 1 and end['choices'] <= 1 and end['skips'] <= 1 and end['dismisses'] <= 1
        assert ex.posts == (2 if stage == 'open' else 4 if stage == 'dismiss' else 3), (stage, ex.posts)
        checks += 1

    for change in ('version', 'kind', 'count', 'nonce', 'slot', 'key', 'level', 'can_skip', 'actions',
                   'receipt', 'history', 'result', 'selected', 'premature', 'dismiss'):
        changed = False
        def corrupt(ex, method, route, body):
            nonlocal changed
            response = ex.request(method, route, body)
            value = json.loads(response)
            c, p = value['child'], value['payload']
            if not changed and c:
                if change == 'receipt' and method == 'POST':
                    p['action_id'] = 'skip'; changed = True
                elif method == 'GET':
                    if change in ('version', 'kind', 'count', 'nonce') and p['phase'] == 'open':
                        if change == 'version': p['version'] = 'item_v1'
                        if change == 'kind': c['kind'] = 'item'
                        if change == 'count': c['offer_count'] = 2
                        if change == 'nonce': p['session_nonce'] = 'f' * 32
                        changed = True
                    elif change in ('slot', 'key', 'level', 'can_skip', 'actions', 'history', 'premature', 'dismiss') and p['phase'] == 'choose':
                        if change == 'slot': p['cards'][0]['slot'] = True
                        if change == 'key': p['cards'][0]['key'] = 'bad key'
                        if change == 'level': p['cards'][0]['upgrade_level'] = -1
                        if change == 'can_skip': p['can_skip'] = 1
                        if change == 'actions': p['legal_actions'] = ['choose:9']
                        if change == 'history': p['prior_results'] = []
                        if change == 'premature': p['status'] = 'resolved'; p['phase'] = 'complete'
                        if change == 'dismiss': p['phase'] = 'dismiss'; p['cards'] = []; p['can_skip'] = False; p['legal_actions'] = ['dismiss']
                        changed = True
                    elif change in ('result', 'selected') and p['status'] == 'resolved':
                        if change == 'result': p['prior_results'][-1]['result'] = 'skipped'
                        else: p['selected_slot'] = 0
                        changed = True
            response[:] = json.dumps(value, separators=(',', ':')).encode()
            return response
        result, ex = run('CR_FIVE', corrupt)
        assert changed and result['code'] == 'invalid_response' and result['completed_card_children'] == 0, (change, result)
        assert ex.telemetry[-1]['choices'] == int(change in ('result', 'selected'))
        checks += 1
    return checks
