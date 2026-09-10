"""Bounded combat and nested public discard/exhaust selection on the shared client."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import time
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).absolute().parents[3] / 'tools'))
import probe_live as probe
from tool_common import ToolFailure

CHOICE_READ = '/probe/combat-choice-v1/public/decision'
CHOICE_ACTION = '/probe/combat-choice-v1/public/action'
COMBAT_READ = '/probe/v0/public/combat-decision'
COMBAT_ACTION = '/probe/v0/public/combat-action'
EVENT_COMBAT_READ = '/probe/event-combat-v2/public/decision'
EVENT_ITEM_READ = '/probe/event-combat-v2/public/item-decision'
EVENT_ITEM_ACTION = '/probe/event-combat-v2/public/item-action'


class Stop(Exception):
    pass


def require(value, code='invalid_response'):
    if not value:
        raise Stop(code)


def decode(body):
    require(type(body) is bytearray and 0 < len(body) <= 65536)
    value = json.loads(body, object_pairs_hook=probe._unique_object, parse_constant=probe._reject_json_constant)
    require(type(value) is dict and type(value.get('schema_version')) is int and value['schema_version'] == 1)
    return value


def first_select(value):
    return next((a for a in value['legal_actions'] if a.startswith('select:')),
                'confirm' if 'confirm' in value['legal_actions'] else value['legal_actions'][0])


def minimum_select(value):
    return 'confirm' if 'confirm' in value['legal_actions'] else first_select(value)


def freeze(value):
    if type(value) is dict:
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if type(value) is list:
        return tuple(freeze(v) for v in value)
    return value


class ChoiceController:
    def __init__(self, request, provider, clock, sleep, deadline):
        self.request, self.provider, self.clock, self.sleep = request, provider, clock, sleep
        self.deadline = min(clock() + 30, deadline)
        self.attempted = self.accepted = self.reconciled = self.reads = 0
        self.choice = self.shape = self.bounds = None
        self.selected = []
        self.expected = None
        self.pending = None
        self.used = set()

    def check_time(self):
        require(self.clock() < self.deadline, 'choice_timeout')

    def summary(self, status, code=None):
        return dict(schema_version=1, status=status, code=code, choice_id=self.choice,
                    attempted=self.attempted, accepted=self.accepted, reconciled=self.reconciled,
                    reads=self.reads, selected_count=len(self.selected),
                    result='selection_verified' if status == 'resolved' else None)

    def observation(self, value):
        require(set(value) == {'schema_version', 'protocol', 'status', 'choice_id', 'decision_id', 'pile',
                              'min_select', 'max_select', 'manual_confirmation', 'candidates', 'selected_slots',
                              'legal_actions', 'attempted', 'accepted', 'reconciled', 'result'})
        require(value['protocol'] == 'combat_card_choice_v1' and value['status'] in ('waiting', 'ready', 'complete'))
        status = value['status']
        for key in ('attempted', 'accepted', 'reconciled'):
            require(type(value[key]) is int and 0 <= value[key] <= 32)
        require(value['attempted'] == self.attempted and value['accepted'] == self.accepted and
                self.reconciled <= value['reconciled'] <= self.accepted)
        if value['choice_id'] is None:
            require(self.choice is None and status == 'waiting' and value['pile'] is None and
                    value['min_select'] == value['max_select'] == 0 and not value['manual_confirmation'] and
                    value['selected_slots'] == [] and value['reconciled'] == 0)
        else:
            require(type(value['choice_id']) is str and re.fullmatch('[0-9a-f]{64}', value['choice_id']))
            require(self.choice is None or value['choice_id'] == self.choice)
            self.choice = value['choice_id']
            require(value['pile'] in ('discard', 'exhaust') and type(value['min_select']) is int and
                    type(value['max_select']) is int and 0 <= value['min_select'] <= value['max_select'] <= 8 and
                    value['max_select'] >= 1 and type(value['manual_confirmation']) is bool)
            bounds = (value['pile'], value['min_select'], value['max_select'], value['manual_confirmation'])
            require(self.bounds is None or self.bounds == bounds)
            self.bounds = bounds
        slots = value['selected_slots']
        require(type(slots) is list and len(slots) <= 8 and all(type(i) is int and 0 <= i < 64 for i in slots) and
                slots == sorted(set(slots)))
        if value['reconciled'] > self.reconciled:
            require(self.expected is not None and slots == self.expected and value['reconciled'] == self.reconciled + 1)
            if status != 'complete':
                require(self.pending != 'confirm')
            self.selected = slots
        else:
            require(slots == self.selected)
        self.reconciled = value['reconciled']
        require(type(value['legal_actions']) is list)
        if status == 'ready':
            require(self.choice is not None and type(value['decision_id']) is str and
                    re.fullmatch('[0-9a-f]{64}', value['decision_id']) and self.reconciled == self.accepted)
            cards = value['candidates']
            require(type(cards) is list and value['max_select'] <= len(cards) <= 64)
            for i, card in enumerate(cards):
                require(type(card) is dict and set(card) == {'slot', 'key', 'upgrade_level', 'selected', 'enabled'})
                require(type(card['slot']) is int and card['slot'] == i and type(card['key']) is str and
                        re.fullmatch('[A-Za-z0-9_]{1,96}', card['key']) and type(card['upgrade_level']) is int and
                        0 <= card['upgrade_level'] <= 99 and type(card['selected']) is bool and type(card['enabled']) is bool)
            shape = [(c['key'], c['upgrade_level']) for c in cards]
            require(self.shape is None or self.shape == shape)
            self.shape = shape
            require([i for i, c in enumerate(cards) if c['selected']] == slots)
            legal = [('deselect:' if c['selected'] else 'select:') + str(i) for i, c in enumerate(cards)
                     if c['enabled'] and (c['selected'] or len(slots) < value['max_select'])]
            # Confirmation is controlled by the actual native enabled control.
            if 'confirm' in value['legal_actions']:
                require(value['min_select'] <= len(slots) <= value['max_select'])
                legal.append('confirm')
            require(legal == value['legal_actions'] and legal and value['result'] is None)
            self.pending = None
        else:
            require(value['decision_id'] is None and value['candidates'] is None and value['legal_actions'] == [])
            if status == 'complete':
                require(self.shape is not None and self.expected is not None and slots == self.expected and
                        self.pending is not None and self.reconciled == self.accepted and self.accepted > 0 and
                        self.bounds[1] <= len(slots) <= self.bounds[2] and
                        (self.pending == 'confirm' or not self.bounds[3] and len(slots) == self.bounds[2]) and
                        value['result'] == 'selection_verified')
            else:
                require(value['result'] is None)
        return status

    def run(self, initial):
        body = initial
        try:
            while True:
                self.check_time()
                require(self.reads < 2048, 'choice_read_limit')
                self.reads += 1
                if body is None:
                    body = self.request('GET', CHOICE_READ, None)
                try:
                    self.check_time()
                    value = decode(body)
                finally:
                    body[:] = b'\0' * len(body)
                    body = None
                if value.get('status') == 'failed':
                    require(value.get('protocol') == 'combat_card_choice_v1')
                    raise Stop('native_choice_failed')
                status = self.observation(value)
                if status == 'complete':
                    return self.summary('resolved')
                if status == 'waiting':
                    self.sleep(min(0.05, max(0, self.deadline - self.clock())))
                    continue
                decision = value['decision_id']
                require(decision not in self.used, 'replayed_choice')
                self.used.add(decision)
                try:
                    action = self.provider(freeze(value))
                except Exception:
                    raise Stop('choice_provider_failed') from None
                self.check_time()
                require(type(action) is str and action in value['legal_actions'], 'illegal_choice_provider')
                require(self.attempted < 32, 'choice_action_limit')
                expected = set(self.selected)
                if action.startswith('select:'):
                    expected.add(int(action.split(':')[1]))
                elif action.startswith('deselect:'):
                    expected.remove(int(action.split(':')[1]))
                self.expected = sorted(expected)
                self.pending = action
                self.attempted += 1
                request_body = bytearray(json.dumps({'decision_id': decision, 'action_id': action}, separators=(',', ':')).encode())
                receipt = None
                try:
                    receipt = self.request('POST', CHOICE_ACTION, request_body)
                    self.check_time()
                    response = decode(receipt)
                    require(all(type(response.get(k)) is int for k in ('attempted', 'accepted', 'reconciled')),
                            'choice_receipt_failed')
                    require(response == dict(schema_version=1, protocol='combat_card_choice_v1', status='accepted',
                        choice_id=self.choice, decision_id=decision, action_id=action,
                        attempted=self.attempted, accepted=self.accepted + 1, reconciled=self.reconciled), 'choice_receipt_failed')
                    self.accepted += 1
                finally:
                    request_body[:] = b'\0' * len(request_body)
                    if type(receipt) is bytearray:
                        receipt[:] = b'\0' * len(receipt)
        finally:
            if type(body) is bytearray:
                body[:] = b'\0' * len(body)


def run_choice(request, *, provider=first_select, clock=time.monotonic, sleep=time.sleep,
               deadline=float('inf'), initial=None):
    controller = ChoiceController(request, provider, clock, sleep, deadline)
    try:
        return controller.run(initial)
    except Stop as error:
        code = str(error)
    except KeyboardInterrupt:
        code = 'interrupted'
    except (ValueError, TypeError, KeyError, RecursionError, ToolFailure):
        code = 'invalid_response'
    except Exception:
        code = 'transport_failure'
    return controller.summary('failed', code)


def run_resume_items(request, nonce, *, parent_deadline=float("inf"), clock=time.monotonic, sleep=time.sleep):
    """One owned resume Offer, reusing item_v1 validation and bounded set ordering."""
    sys.path.insert(0, str(Path(__file__).absolute().parents[3] / 'components/item_wire/host'))
    import item_host as codec
    attempted = accepted = reads = 0
    collected = []
    history = []
    pending = None
    shape = None
    count = None
    set_mode = None
    deadline = min(clock() + 30, parent_deadline)
    def parse_item(value):
        raw = bytearray(json.dumps(value, separators=(',', ':')).encode('ascii'))
        try:
            result = codec._decode_response(raw)
            require(result.session_nonce == nonce, 'resume_item_nonce')
            return result
        finally:
            raw[:] = b'\0' * len(raw)
    def settle(value):
        nonlocal pending, shape
        result = parse_item(value)
        require(pending is not None and shape is not None and result.status == 'resolved', 'resume_item_unowned_result')
        offer = shape.offers[0]
        require((result.decision_id, result.action_id) == pending and
                (result.offer_index, result.kind, result.key, result.result) ==
                (offer.index, offer.kind, offer.key, 'collected'), 'resume_item_result_mismatch')
        collected.append(dict(index=offer.index, kind=offer.kind, key=offer.key))
        pending = shape = None
    try:
        while True:
            require(clock() < deadline and reads < 128, 'resume_item_read_limit')
            reads += 1
            raw = request('GET', EVENT_ITEM_READ, None)
            try:
                require(clock() < deadline, 'resume_item_timeout')
                require(type(raw) is bytearray and 0 < len(raw) <= 65536)
                value = json.loads(raw, object_pairs_hook=probe._unique_object, parse_constant=probe._reject_json_constant)
                require(type(value) is dict)
                is_set = value.get('version') == 'item_set_v1'
                require(set_mode is None or is_set == set_mode, 'resume_item_contract_changed')
                set_mode = is_set
                if is_set:
                    require(set(value) == {'version', 'session_nonce', 'status', 'offer_count', 'collected', 'current'} and
                            value['session_nonce'] == nonce and type(value['offer_count']) is int and
                            2 <= value['offer_count'] <= 8 and (count is None or count == value['offer_count']))
                    count = value['offer_count']
                    new = value['collected']
                    require(type(new) is list and len(history) <= len(new) <= min(count, len(history)+1) and new[:len(history)] == history)
                    for row in new: require(parse_item(row).status == 'resolved')
                    if len(new) > len(history):
                        settle(new[-1]); history = new
                    status = value['status']
                    require(status in ('ready', 'waiting', 'resolved'), 'resume_item_stopped')
                    if status == 'resolved':
                        require(value['current'] is None and len(collected) == count == accepted and pending is None)
                        break
                    current = None if value['current'] is None else parse_item(value['current'])
                    require(current is None and status == 'waiting' or current is not None and current.status == status)
                else:
                    count = 1
                    current = parse_item(value)
                    status = current.status
                    if status == 'resolved':
                        settle(value); break
                    require(status in ('ready', 'waiting'), 'resume_item_stopped')
                if status == 'ready':
                    require(pending is None and attempted == accepted == len(collected) and attempted < count and
                            current is not None and len(current.offers) == 1 and len(current.legal_actions) == 1)
                    require(not is_set or current.offers[0].index == len(collected))
                    require(shape is None or shape == current, 'resume_item_changed')
                    shape = current
                    action = current.legal_actions[0]
                    command = bytearray(json.dumps(dict(decision_id=current.decision_id, action_id=action), separators=(',', ':')).encode())
                    receipt = None
                    try:
                        require(clock() < deadline, 'resume_item_timeout')
                        attempted += 1
                        receipt = request('POST', EVENT_ITEM_ACTION, command)
                        require(clock() < deadline, 'resume_item_timeout')
                        result = codec._decode_response(receipt)
                        require(result.status == 'accepted' and result.session_nonce == nonce and
                                (result.decision_id, result.action_id) == (current.decision_id, action), 'resume_item_receipt_failed')
                        accepted += 1
                        pending = (current.decision_id, action)
                    finally:
                        command[:] = b'\0' * len(command)
                        if type(receipt) is bytearray: receipt[:] = b'\0' * len(receipt)
            finally:
                if type(raw) is bytearray: raw[:] = b'\0' * len(raw)
            sleep(min(0.05, max(0, deadline-clock())))
        code = None
    except Stop as error: code = str(error)
    except KeyboardInterrupt: code = 'interrupted'
    except (ValueError, TypeError, KeyError, RecursionError, codec._InvalidResponse): code = 'invalid_resume_item_response'
    except Exception: code = 'resume_item_transport_failure'
    return dict(status='resolved' if code is None else 'failed', code=code, attempted=attempted,
                accepted=accepted, reconciled=len(collected), reads=reads, collected=collected)


def run_combat(request, *, choice_provider=first_select, event_resume_nonce=None, clock=time.monotonic, sleep=time.sleep):
    """One combat, preserving attempted/accepted/reconciled counts on every exit."""
    attempted = accepted = reconciled = reads = choice_probes = stale = 0
    choices = []
    deadline = clock() + 300
    pending = None
    first_round = None
    outcome = None
    resume_reads = 0
    terminal_seen = None
    resume_items = []
    def check():
        require(clock() < deadline, 'combat_timeout')
    try:
        require(event_resume_nonce is None or type(event_resume_nonce) is str and re.fullmatch('[0-9a-f]{32}', event_resume_nonce), 'event_resume_nonce')
        while True:
            check()
            require(reads < 4096, 'combat_read_limit')
            reads += 1
            if event_resume_nonce is not None:
                resume_reads += 1
                resume_body = request('GET', EVENT_COMBAT_READ, None)
                try:
                    check()
                    resume = decode(resume_body)
                    require(set(resume) == {'schema_version', 'protocol', 'session_nonce', 'status'} and
                            resume['protocol'] == 'event_combat_v2' and resume['session_nonce'] == event_resume_nonce and
                            resume['status'] in ('combat', 'waiting', 'item', 'resumed'), 'invalid_event_resume')
                    resume_status = resume['status']
                finally:
                    if type(resume_body) is bytearray: resume_body[:] = b'\0' * len(resume_body)
                if resume_status == 'item':
                    require(not resume_items, 'repeated_resume_offer')
                    child = run_resume_items(request, event_resume_nonce, parent_deadline=deadline, clock=clock, sleep=sleep)
                    resume_items.append(child)
                    require(child['status'] == 'resolved', child['code'])
                    check()
                    continue
                if resume_status == 'resumed':
                    if pending is not None: reconciled += 1
                    outcome = 'event_resumed'
                    break
                if resume_status == 'waiting' or terminal_seen is not None:
                    sleep(min(0.05, max(0, deadline - clock())))
                    continue
            body = request('GET', COMBAT_READ, None)
            try:
                check()
                if body == probe._COMBAT_WAITING:
                    value = None
                elif body.startswith(probe._COMBAT_COMPLETE_PREFIX):
                    terminal = probe._validate_combat_terminal(memoryview(body))
                    require(accepted > 0 or event_resume_nonce is not None, 'combat_already_complete')
                    if pending is not None:
                        reconciled += 1
                        pending = None
                    outcome = terminal['outcome']
                    if event_resume_nonce is not None and outcome == 'victory':
                        terminal_seen = outcome
                        continue
                    break
                else:
                    value = probe._validate_combat(memoryview(body), 'heuristic')
            finally:
                body[:] = b'\0' * len(body)
            # A queued end-turn can leave changed, actionable snapshots in its
            # original round while an earlier card/chooser is still completing.
            # Keep the reservation pending and service that chooser; only the
            # next round (or terminal combat) reconciles this end-turn.
            if value is not None and pending is not None and pending[2] == 'end_turn' and value['round'] == pending[1]:
                value = None
            if value is None:
                choice_probes += 1
                initial = request('GET', CHOICE_READ, None)
                try:
                    check()
                    choice_value = decode(initial)
                    if choice_value.get('choice_id') is not None or choice_value.get('status') == 'failed':
                        require(len(choices) < 32, 'combat_choice_limit')
                        summary = run_choice(request, provider=choice_provider, clock=clock, sleep=sleep,
                                             deadline=deadline, initial=initial)
                        choices.append(summary)
                        require(summary['status'] == 'resolved', 'combat_choice_failed')
                    else:
                        # Validate an idle response too; malformed errors are never a waiting loop.
                        validator = ChoiceController(request, choice_provider, clock, sleep, deadline)
                        require(validator.observation(choice_value) == 'waiting')
                finally:
                    initial[:] = b'\0' * len(initial)
                sleep(min(0.05, max(0, deadline - clock())))
                continue
            if pending is not None:
                if value['decision_id'] == pending[0]:
                    sleep(min(0.05, max(0, deadline - clock())))
                    continue
                require(value['round'] == pending[1] + (1 if pending[2] == 'end_turn' else 0), 'unexpected_combat_round')
                reconciled += 1
                pending = None
            if first_round is None:
                first_round = value['round']
            require(0 <= value['round'] - first_round < 12, 'combat_round_limit')
            require(accepted < 48 and attempted < 72, 'combat_action_limit')
            decision, action = value['decision_id'], value['recommendation']['action_id']
            request_body = bytearray(json.dumps({'decision_id': decision, 'action_id': action}, separators=(',', ':')).encode())
            receipt = None
            attempted += 1
            try:
                receipt = request('POST', COMBAT_ACTION, request_body)
                check()
                response = decode(receipt)
                expected = dict(schema_version=1, status='accepted', mutation_state='queued',
                                decision_id=decision, action_id=action, reason='accepted')
                if response == expected:
                    accepted += 1
                    pending = (decision, value['round'], action)
                else:
                    require(response == dict(expected, status='rejected', mutation_state='none', reason='stale_decision'), 'combat_receipt_failed')
                    stale += 1
                    require(stale <= 24, 'stale_rejection_limit')
            finally:
                request_body[:] = b'\0' * len(request_body)
                if type(receipt) is bytearray:
                    receipt[:] = b'\0' * len(receipt)
        code = None
    except Stop as error:
        code = str(error)
    except KeyboardInterrupt:
        code = 'interrupted'
    except (ValueError, TypeError, KeyError, RecursionError, ToolFailure):
        code = 'invalid_response'
    except Exception:
        code = 'transport_failure'
    result = dict(schema_version=1, status='resolved' if code is None else 'failed', code=code,
                  attempted=attempted, accepted=accepted, reconciled=reconciled, reads=reads,
                  stale_rejections=stale, choice_probes=choice_probes, choices=choices, outcome=outcome)
    if event_resume_nonce is not None: result.update(resume_reads=resume_reads, native_terminal_outcome=terminal_seen, resume_items=resume_items)
    return result
