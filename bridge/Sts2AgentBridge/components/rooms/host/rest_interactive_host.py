"""Bounded interactive rest controller; every ready child reaches the callback."""
from __future__ import annotations

import json
import copy
import re
import time

READ = '/probe/rest-v3/public/decision'
ACT = '/probe/rest-v3/public/action'
OPTIONS = ('heal', 'smith', 'lift', 'kindle', 'dig', 'cook', 'clone', 'hatch')
ACTION = re.compile(r'(?:option:(?:heal|smith|lift|kindle|dig|cook|clone|hatch)|(?:de)?select:(?:[0-9]|[1-5][0-9]|6[0-3])|confirm|cancel|reward:(?:(?:open|collect):[0-7]|choose:[0-4]|skip_card|dismiss))\Z')


def require(value, code='invalid_response'):
    if not value:
        raise ValueError(code)


def identifier(value, length=64):
    return type(value) is str and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def decode(body):
    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result)
            result[key] = value
        return result
    def constant(_):
        raise ValueError('invalid_response')
    try:
        require(type(body) is bytearray and 0 < len(body) <= 65536)
        value = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    finally:
        if type(body) is bytearray:
            body[:] = b'\0' * len(body)
    require(type(value) is dict and type(value.get('schema_version')) is int and value['schema_version'] == 3
            and value.get('capability') == 'rest_v3' and identifier(value.get('session_nonce'), 32))
    status, phase = value.get('status'), value.get('phase')
    require(status in ('ready', 'waiting', 'accepted', 'complete', 'unsupported', 'rejected', 'uncertain'))
    require(phase in ('option', 'selection', 'rewards', 'effect', 'action', 'rest', 'unknown'))
    common = {'schema_version', 'capability', 'session_nonce', 'status', 'phase', 'completed'}
    completed = value.get('completed')
    require(type(completed) is list and len(completed) <= 2)
    for row in completed:
        require(type(row) is dict and set(row) == {'decision_id', 'action_id', 'result'} and identifier(row['decision_id'])
                and type(row['action_id']) is str and ACTION.fullmatch(row['action_id'])
                and row['result'] in ('reconciled', 'cancelled'))
    require(len({row['decision_id'] for row in completed}) == len(completed))
    if status == 'accepted':
        require(set(value) == common | {'decision_id', 'action_id'} and phase == 'action' and not completed
                and identifier(value['decision_id']) and type(value['action_id']) is str and ACTION.fullmatch(value['action_id']))
    elif status != 'ready':
        require(set(value) == common)
        require(status != 'complete' or phase == 'rest')
    else:
        extra = {'option': {'options', 'cards'}, 'selection': {'cards', 'minimum', 'maximum', 'cancelable'},
                 'rewards': {'screen_kind', 'rewards'}}
        require(phase in extra and set(value) == common | {'decision_id', 'legal_actions', 'parent_action'} | extra[phase])
        require(identifier(value['decision_id']))
        actions = value['legal_actions']
        require(type(actions) is list and 1 <= len(actions) <= 130
                and all(type(a) is str and ACTION.fullmatch(a) for a in actions) and len(set(actions)) == len(actions))
        parent = value['parent_action']
        require(parent is None if phase == 'option' else type(parent) is str and parent in ['option:' + k for k in OPTIONS])
        if phase in ('option', 'selection'):
            cards = value['cards']
            require(type(cards) is list and len(cards) <= 64)
            for i, card in enumerate(cards):
                require(type(card) is dict and set(card) == {'slot', 'key', 'upgrade', 'removable' if phase == 'option' else 'selected'}
                        and type(card['slot']) is int and card['slot'] == i and type(card['key']) is str
                        and re.fullmatch('[A-Z0-9_]{1,128}', card['key']) and type(card['upgrade']) is int and card['upgrade'] >= 0
                        and type(card.get('removable' if phase == 'option' else 'selected')) is bool)
        if phase == 'option':
            options = value['options']
            require(type(options) is list and 1 <= len(options) <= 8)
            for row in options:
                require(type(row) is dict and set(row) == {'kind', 'enabled', 'counter', 'amount'} and row['kind'] in OPTIONS
                        and type(row['enabled']) is bool and all(type(row[k]) is int and row[k] >= 0 for k in ('counter', 'amount')))
            require(len({r['kind'] for r in options}) == len(options))
            require(actions == ['option:' + r['kind'] for r in options if r['enabled']])
        elif phase == 'selection':
            minimum, maximum = value['minimum'], value['maximum']
            require(type(minimum) is int and type(maximum) is int and 0 <= minimum <= maximum <= 3
                    and maximum > 0 and type(value['cancelable']) is bool)
            selected = sum(c['selected'] for c in cards)
            require(selected <= maximum)
            expected = [('deselect:' if c['selected'] else 'select:') + str(i) for i, c in enumerate(cards)
                        if c['selected'] or selected < maximum]
            expected += ['confirm'] if selected >= minimum else []
            expected += ['cancel'] if value['cancelable'] else []
            require(actions == expected)
        else:
            require(value['screen_kind'] in ('rewards', 'card_reward') and type(value['rewards']) is list and 1 <= len(value['rewards']) <= 8)
            for row in value['rewards']:
                require(type(row) is dict and set(row) == {'slot', 'kind', 'selected', 'key', 'cards'}
                        and type(row['slot']) is int and 0 <= row['slot'] <= 7 and row['kind'] in ('card', 'potion')
                        and type(row['selected']) is bool and (row['key'] is None or type(row['key']) is str and re.fullmatch('[A-Z0-9_]{1,128}', row['key']))
                        and type(row['cards']) is list and len(row['cards']) <= 5
                        and all(type(c) is str and re.fullmatch('[A-Z0-9_]{1,128}', c) for c in row['cards']))
                require(value['screen_kind'] != 'rewards' or not row['cards'])
            require(len({r['slot'] for r in value['rewards']}) == len(value['rewards']))
            require(all(a.startswith('reward:') for a in actions))
            rewards = {r['slot']: r for r in value['rewards']}
            if value['screen_kind'] == 'card_reward':
                require(len(rewards) == 1)
                card = value['rewards'][0]
                require(card['kind'] == 'card' and card['key'] is None and not card['selected'] and 1 <= len(card['cards']) <= 5)
                require(all(a == 'reward:skip_card' or a.startswith('reward:choose:') and int(a.rsplit(':', 1)[1]) < len(card['cards']) for a in actions))
            else:
                for action in actions:
                    if action == 'reward:dismiss':
                        continue
                    require(action.startswith(('reward:open:', 'reward:collect:')))
                    # Native commands address current visible positions. row.slot
                    # retains the original reward ordinal after collected buttons disappear.
                    position = int(action.rsplit(':', 1)[1])
                    require(position < len(value['rewards']))
                    row = value['rewards'][position]
                    require(not row['selected'] and
                            row['kind'] == ('card' if action.startswith('reward:open:') else 'potion'))
    return value


def controlled_policy(option, selection='choose', reward='first-card'):
    require(option in OPTIONS and selection in ('choose', 'cancel', 'preview-cancel') and reward in ('first-card', 'skip-card'), 'policy')
    def choose(view):
        legal = view['legal_actions']
        if view['phase'] == 'option':
            result = 'option:' + option
        elif view['phase'] == 'selection':
            if selection == 'cancel' or selection == 'preview-cancel' and 'confirm' in legal:
                result = 'cancel'
            elif 'confirm' in legal:
                result = 'confirm'
            else:
                result = next((a for a in legal if a.startswith('select:')), None)
        elif reward == 'skip-card' and 'reward:skip_card' in legal:
            result = 'reward:skip_card'
        else:
            result = next((a for prefix in ('reward:collect:', 'reward:open:', 'reward:choose:')
                           for a in legal if a.startswith(prefix)), 'reward:dismiss')
        require(result in legal, 'policy_action_unavailable')
        return result
    return choose


def run_rest(request, provider, *, clock=time.monotonic, sleep=time.sleep):
    started, nonce = clock(), None
    attempted = accepted = reads = 0
    pending, completed, issued = {}, {}, set()
    parent = None
    def result(status, code=None):
        return dict(schema_version=3, capability='rest_v3', status=status, attempted=attempted, accepted=accepted,
                    reconciled=len(completed), reads=reads, code=code, outcome=completed.get(parent, {}).get('result'))
    try:
        while reads < 4096 and clock() - started < 120:
            view = decode(request('GET', READ, None)); reads += 1
            nonce = nonce or view['session_nonce']; require(view['session_nonce'] == nonce, 'session_changed')
            for row in view['completed']:
                key = row['decision_id']
                if key in completed:
                    require(completed[key] == row, 'completion_changed')
                    continue
                require(pending.get(key) == row['action_id'], 'unowned_completion')
                require(key != parent or view['status'] == 'complete', 'premature_parent_completion')
                cancelled = pending.get(parent) in ('option:smith', 'option:cook') and any(r['action_id'] == 'cancel' for r in completed.values())
                require(row['result'] != 'cancelled' or key == parent and cancelled, 'unowned_cancel')
                require(key != parent or (row['result'] == 'cancelled') == cancelled, 'cancel_result_mismatch')
                completed[key] = row; del pending[key]
            require(clock() - started < 120, 'wait_budget')
            status = view['status']
            if status == 'complete':
                require(parent in completed and not pending and len(completed) == accepted, 'incomplete_actions')
                return result('resolved')
            if status == 'waiting':
                sleep(.05); continue
            require(status == 'ready', 'native_' + status)
            require(not pending if parent is None else set(pending) == {parent}, 'unreconciled_child')
            require(view['phase'] == 'option' if parent is None else
                    view['phase'] in ('selection', 'rewards') and view['parent_action'] == pending[parent], 'parent_changed')
            require(view['decision_id'] not in issued and attempted < 128, 'action_budget')
            action = provider(copy.deepcopy(view))
            require(type(action) is str and action in view['legal_actions'], 'policy_action_unavailable')
            require(clock() - started < 120, 'wait_budget')
            command = dict(decision_id=view['decision_id'], action_id=action)
            body = bytearray(json.dumps(command, separators=(',', ':')).encode())
            attempted += 1; issued.add(command['decision_id'])
            try:
                receipt = decode(request('POST', ACT, body))
            finally:
                body[:] = b'\0' * len(body)
            require(receipt['session_nonce'] == nonce and receipt['status'] == 'accepted'
                    and all(receipt[k] == v for k, v in command.items()), 'action_not_accepted')
            accepted += 1; pending[command['decision_id']] = action
            if parent is None:
                require(action.startswith('option:'), 'parent_required'); parent = command['decision_id']
            require(clock() - started < 120, 'wait_budget')
        return result('failed', 'wait_budget')
    except KeyboardInterrupt:
        return result('failed', 'interrupted')
    except Exception as error:
        known = {'invalid_response', 'session_changed', 'completion_changed', 'unowned_completion', 'premature_parent_completion',
                 'unowned_cancel', 'cancel_result_mismatch', 'incomplete_actions', 'unreconciled_child', 'action_budget', 'policy_action_unavailable',
                 'action_not_accepted', 'parent_required', 'parent_changed', 'wait_budget', 'native_unsupported', 'native_rejected', 'native_uncertain'}
        return result('failed', str(error) if type(error) is ValueError and str(error) in known else 'controller_failed')
