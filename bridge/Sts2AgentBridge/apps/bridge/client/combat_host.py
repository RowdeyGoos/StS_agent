"""Bounded combat and nested public pile selection on the shared client."""
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
CHOICE_READ_V2 = '/probe/combat-choice-v2/public/decision'
CHOICE_ACTION_V2 = '/probe/combat-choice-v2/public/action'
CHOICE_READ_V3 = '/probe/combat-choice-v3/public/decision'
CHOICE_ACTION_V3 = '/probe/combat-choice-v3/public/action'
CHOICE_FAILURES = frozenset(('choice_stopped', 'choice_limit', 'choice_not_fresh', 'unsupported_choice',
    'invalid_candidates', 'choice_read_limit', 'choice_identity_changed', 'unexpected_completion',
    'choice_result_mismatch', 'choice_candidates_changed', 'choice_selection_mismatch', 'unsolicited_selection',
    'choice_reconciliation_timeout', 'choice_not_actionable', 'stale_or_illegal_choice', 'choice_action_limit',
    'uncertain_choice', 'choice_protocol_changed', 'choice_capture_failed'))
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


def campaign_action(value):
    # Frantic Escape moves the player away from The Insatiable's instant kill.
    # Only choose an already validated native legal action; never synthesize one
    # from a card merely being present in hand or from a private boss state.
    for action in value['legal_actions']:
        if (action['kind'] == 'play_card' and
                value['hand'][action['hand_index']]['id'].lower() == 'frantic_escape'):
            return action['action_id']

    chosen = value['recommendation']
    target = chosen['target_index']
    # The Obscura's Parafright revives. Keep the recommended card, but use its
    # native-legal target on the summoner instead of repeatedly killing the illusion.
    # Match public IDs in this decision, not positions retained across summons.
    if (chosen['kind'] == 'play_card' and target is not None and
            value['enemies'][target]['id'].lower() == 'parafright'):
        for action in value['legal_actions']:
            target = action['target_index']
            if (action['kind'] == 'play_card' and action['hand_index'] == chosen['hand_index'] and
                    target is not None and value['enemies'][target]['id'].lower() == 'the_obscura' and
                    value['enemies'][target]['hp'] is not None and value['enemies'][target]['hp'] > 0):
                return action['action_id']
    return chosen['action_id']


def freeze(value):
    if type(value) is dict:
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if type(value) is list:
        return tuple(freeze(v) for v in value)
    return value


class ChoiceController:
    def __init__(self, request, provider, clock, sleep, deadline, version=1):
        require(type(version) is int and version in (1, 2, 3), 'choice_version')
        self.version, self.protocol = version, f'combat_card_choice_v{version}'
        self.read_route, self.action_route = {1: (CHOICE_READ, CHOICE_ACTION), 2: (CHOICE_READ_V2, CHOICE_ACTION_V2),
                                              3: (CHOICE_READ_V3, CHOICE_ACTION_V3)}[version]
        self.native_code = None
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
                    pile=self.bounds[0] if self.bounds else None, native_code=self.native_code,
                    result='selection_verified' if status == 'resolved' else None)

    def native_failure(self, value):
        if value.get('status') != 'failed':
            return
        require(set(value) == {'schema_version', 'protocol', 'status', 'code', 'choice_id',
                              'attempted', 'accepted', 'reconciled'} and value['protocol'] == self.protocol and
                type(value['code']) is str and value['code'] in CHOICE_FAILURES and
                all(type(value[k]) is int for k in ('attempted', 'accepted', 'reconciled')) and
                0 <= value['reconciled'] <= value['accepted'] <= value['attempted'] <= 33 and
                (value['choice_id'] is None or type(value['choice_id']) is str and
                 re.fullmatch('[0-9a-f]{64}', value['choice_id'])) and
                (self.choice is None or value['choice_id'] == self.choice), 'invalid_choice_failure')
        # A rejected POST may stop before incrementing the native attempted
        # count. Retain the host's known counts, never infer dispatch from an error.
        self.native_code = value['code']
        raise Stop('native_choice_failed')

    def observation(self, value):
        require(set(value) == {'schema_version', 'protocol', 'status', 'choice_id', 'decision_id', 'pile',
                              'min_select', 'max_select', 'manual_confirmation', 'candidates', 'selected_slots',
                              'legal_actions', 'attempted', 'accepted', 'reconciled', 'result'})
        require(value['protocol'] == self.protocol and value['status'] in ('waiting', 'ready', 'complete'))
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
            require(value['pile'] in (('discard', 'exhaust', 'draw', 'offer') if self.version == 3 else
                                      ('discard', 'exhaust', 'draw') if self.version == 2 else ('discard', 'exhaust')) and type(value['min_select']) is int and
                    type(value['max_select']) is int and 0 <= value['min_select'] <= value['max_select'] <= 8 and
                    value['max_select'] >= 1 and type(value['manual_confirmation']) is bool)
            bounds = (value['pile'], value['min_select'], value['max_select'], value['manual_confirmation'])
            require(self.bounds is None or self.bounds == bounds)
            self.bounds = bounds
            if value['pile'] == 'offer':
                require(bounds[1:] == (1, 1, False))
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
            if value['pile'] == 'offer':
                require(len(cards) <= 3 and slots == [] and 'confirm' not in value['legal_actions'])
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
                    body = self.request('GET', self.read_route, None)
                try:
                    value = decode(body)
                finally:
                    body[:] = b'\0' * len(body)
                    body = None
                self.native_failure(value)
                status = self.observation(value)
                # Keep proven reconciliation from a received observation even
                # at the deadline; never dispatch another input or report success.
                self.check_time()
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
                    receipt = self.request('POST', self.action_route, request_body)
                    response = decode(receipt)
                    self.native_failure(response)
                    require(all(type(response.get(k)) is int for k in ('attempted', 'accepted', 'reconciled')),
                            'choice_receipt_failed')
                    require(response == dict(schema_version=1, protocol=self.protocol, status='accepted',
                        choice_id=self.choice, decision_id=decision, action_id=action,
                        attempted=self.attempted, accepted=self.accepted + 1, reconciled=self.reconciled), 'choice_receipt_failed')
                    self.accepted += 1
                    # A valid receipt remains known acceptance even when it
                    # arrives at the deadline. The child still stops as timed out.
                    self.check_time()
                finally:
                    request_body[:] = b'\0' * len(request_body)
                    if type(receipt) is bytearray:
                        receipt[:] = b'\0' * len(receipt)
        finally:
            if type(body) is bytearray:
                body[:] = b'\0' * len(body)


def run_choice(request, *, provider=first_select, clock=time.monotonic, sleep=time.sleep,
               deadline=float('inf'), initial=None, version=1):
    controller = ChoiceController(request, provider, clock, sleep, deadline, version)
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


def run_resume_item_policy(request,nonce,initial,policy,*,parent_deadline,clock,sleep):
    sys.path.insert(0,str(Path(__file__).absolute().parents[3]/'components/events/host'))
    import generic_event_host as codec
    tracker=codec.ItemPolicyTracker(nonce);receipts=[];attempted=reads=0;value=initial
    try:
        while True:
            require(clock()<parent_deadline and reads<256,'resume_item_policy_deadline');reads+=1
            if value is None:
                raw=request('GET',EVENT_ITEM_READ,None)
                try:value=json.loads(raw,object_pairs_hook=probe._unique_object,parse_constant=probe._reject_json_constant)
                finally:
                    if type(raw) is bytearray:raw[:]=b'\0'*len(raw)
            require(clock()<parent_deadline,'resume_item_policy_deadline')
            status=tracker.read(value,receipts)
            if status=='resolved':break
            require(status in ('ready','waiting'),'resume_item_policy_stopped')
            if status=='ready':
                require(attempted==len(receipts)==len(tracker.history) and attempted<25,'resume_item_policy_unsettled')
                action=codec.item_policy_action(value,policy);decision=value['decision_id']
                command=bytearray(json.dumps(dict(decision_id=decision,action_id=action),separators=(',',':')).encode());receipt=None
                try:
                    attempted+=1;receipt=request('POST',EVENT_ITEM_ACTION,command)
                    require(clock()<parent_deadline,'resume_item_policy_deadline')
                    r=json.loads(receipt,object_pairs_hook=probe._unique_object,parse_constant=probe._reject_json_constant)
                    require(r==dict(version='item_policy_v1',session_nonce=nonce,decision_id=decision,action_id=action,outcome='accepted'),'resume_item_policy_receipt')
                    receipts.append((decision,action))
                finally:
                    command[:]=b'\0'*len(command)
                    if type(receipt) is bytearray:receipt[:]=b'\0'*len(receipt)
            value=None;sleep(min(.05,max(0,parent_deadline-clock())))
        code=None
    except Stop as error:code=str(error)
    except KeyboardInterrupt:code='interrupted'
    except Exception:code='invalid_resume_item_policy'
    return dict(status='resolved' if code is None else 'failed',code=code,attempted=attempted,accepted=len(receipts),reconciled=len(tracker.history),reads=reads,
                collected=[h for h in tracker.history if h['result']=='collected'],discarded=sum(h['result']=='discarded' for h in tracker.history),skipped=any(h['result']=='skipped' for h in tracker.history))


def run_resume_items(request, nonce, *, potion_policy="skip-full", parent_deadline=float("inf"), clock=time.monotonic, sleep=time.sleep):
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
                if value.get('version')=='item_policy_v1':
                    require(reads==1 and set_mode is None and attempted==accepted==0 and pending is None and not collected and not history,'resume_item_contract_changed')
                    return run_resume_item_policy(request,nonce,value,potion_policy,parent_deadline=deadline,clock=clock,sleep=sleep)
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


POTION_READ = '/probe/combat-potions-v1/public/decision'
POTION_ACTION = '/probe/combat-potions-v1/public/action'


def potion_action(view, combat):
    """A deliberately simple public-state policy over native advertised actions."""
    require(set(view) == {'schema_version', 'protocol', 'status', 'decision_id', 'combat_decision_id', 'potions', 'legal_actions'} and
            view['protocol'] == 'combat_potions_v1' and view['status'] == 'ready' and
            type(view['decision_id']) is str and re.fullmatch('[0-9a-f]{64}', view['decision_id']) and
            type(view['combat_decision_id']) is str and re.fullmatch('[0-9a-f]{64}', view['combat_decision_id']), 'potion_view')
    require(type(view['potions']) is list and len(view['potions']) <= 8 and
            type(view['legal_actions']) is list and len(view['legal_actions']) <= 48, 'potion_bounds')
    if view['combat_decision_id'] != combat['decision_id']:
        return 'refresh'
    slots = {}
    for row in view['potions']:
        require(type(row) is dict and set(row) == {'slot', 'id', 'supported'} and
                type(row['slot']) is int and 0 <= row['slot'] < 8 and row['slot'] not in slots and
                type(row['id']) is str and re.fullmatch('[A-Z][A-Z0-9_]{0,95}', row['id']) and
                type(row['supported']) is bool, 'potion_inventory')
        slots[row['slot']] = row
    candidates = []
    seen = set()
    for action in view['legal_actions']:
        require(type(action) is str and re.fullmatch(r'use:[0-7](?::[0-5])?', action) and action not in seen, 'potion_action')
        seen.add(action)
        parts = action.split(':')
        slot = int(parts[1])
        require(slot in slots and slots[slot]['supported'], 'potion_action_slot')
        target = int(parts[2]) if len(parts) == 3 else None
        require(target is None or target < len(combat['enemies']), 'potion_target')
        candidates.append((action, slots[slot]['id'].lower(), target))
    if combat['enemies'] and all(e.get('hp_display') == 'infinite' for e in combat['enemies']):
        return None
    # An intervening native change invalidates both the potion and card decision.
    player = combat['player']
    attacks = any(a['kind'] == 'play_card' and combat['hand'][a['hand_index']]['type'] == 'attack' for a in combat['legal_actions'])
    threatened = any('attack' in intent.lower() for e in combat['enemies'] for intent in e['intents'])
    eligible = []
    for action, name, target in candidates:
        if target is not None and combat['enemies'][target].get('hp_display') == 'infinite':
            continue
        use = name in {'fire_potion', 'explosive_ampoule', 'strength_potion', 'dexterity_potion', 'heart_of_iron', 'liquid_bronze', 'fruit_juice'}
        if name in {'flex_potion', 'vulnerable_potion'}: use = attacks
        if name in {'block_potion', 'speed_potion', 'weak_potion'}: use = threatened
        if name == 'energy_potion': use = player['energy'] <= 1 and bool(combat['hand'])
        if name in {'blood_potion', 'regen_potion'}: use = player['hp'] <= player['max_hp'] * .8
        if use:
            enemy = combat['enemies'][target] if target is not None else None
            # Prefer a large persistent enemy to respawning minions.
            score = (0 if enemy and enemy['id'].lower() == 'the_obscura' else 1,
                     -(enemy['max_hp'] if enemy else 0), action)
            eligible.append((score, action))
    return min(eligible)[1] if eligible else None


def use_potion(request, decision, action, *, deadline, clock, sleep):
    result = dict(status='failed', code=None, decision_id=decision, action_id=action,
                  attempted=0, accepted=0, reconciled=0)
    until = min(deadline, clock() + 30)
    body = receipt = None
    try:
        require(clock() < until, 'potion_timeout')
        body = bytearray(json.dumps(dict(decision_id=decision, action_id=action), separators=(',', ':')).encode())
        result['attempted'] = 1
        receipt = request('POST', POTION_ACTION, body)
        response = decode(receipt)
        expected = dict(schema_version=1, status='accepted', mutation_state='queued', decision_id=decision, action_id=action, reason='accepted')
        if response == dict(expected, status='rejected', mutation_state='none', reason='stale_decision'):
            result.update(status='stale')
            return result
        require(response == expected, 'potion_receipt')
        result['accepted'] = 1
        for _ in range(640):
            require(clock() < until, 'potion_timeout')
            observed = request('GET', POTION_READ, None)
            try:
                view = decode(observed)
            finally:
                observed[:] = b'\0' * len(observed)
            if view == dict(schema_version=1, protocol='combat_potions_v1', status='resolved', decision_id=decision, action_id=action):
                result['reconciled'] = 1
                require(clock() < until, 'potion_timeout')
                result['status'] = 'resolved'
                return result
            require(view == dict(schema_version=1, protocol='combat_potions_v1', status='waiting'), 'potion_completion')
            sleep(min(.05, max(0, until-clock())))
        raise Stop('potion_read_limit')
    except (KeyboardInterrupt, Exception) as error:
        result['code'] = str(error) if isinstance(error, Stop) else 'potion_transport_or_response'
        return result
    finally:
        if body is not None: body[:] = b'\0' * len(body)
        if type(receipt) is bytearray: receipt[:] = b'\0' * len(receipt)


def run_combat(request, *, choice_provider=first_select, event_resume_nonce=None, resume_potion_policy="skip-full", campaign=False, campaign_potions=False, clock=time.monotonic, sleep=time.sleep):
    """One combat, preserving attempted/accepted/reconciled counts on every exit."""
    attempted = accepted = reconciled = reads = choice_probes = stale = 0
    choices = []
    potions = []
    choice_version = 3 if campaign else 1
    choice_read = CHOICE_READ_V3 if campaign else CHOICE_READ
    deadline = clock() + (900 if campaign else 300)
    pending = None
    first_round = None
    outcome = None
    resume_reads = 0
    terminal_seen = None
    validation_code = None
    resume_items = []
    def check():
        require(clock() < deadline, 'combat_timeout')
    try:
        require(event_resume_nonce is None or type(event_resume_nonce) is str and re.fullmatch('[0-9a-f]{32}', event_resume_nonce), 'event_resume_nonce')
        while True:
            check()
            require(reads < (16384 if campaign else 4096), 'combat_read_limit')
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
                    child = run_resume_items(request, event_resume_nonce, potion_policy=resume_potion_policy, parent_deadline=deadline, clock=clock, sleep=sleep)
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
                elif body.startswith((probe._COMBAT_COMPLETE_PREFIX, probe._COMBAT_COMPLETE_PREFIX_V2)):
                    terminal = probe._validate_combat_terminal(memoryview(body), allow_infinite_health=campaign)
                    require(accepted > 0 or any(p['reconciled'] for p in potions) or event_resume_nonce is not None, 'combat_already_complete')
                    if pending is not None:
                        reconciled += 1
                        pending = None
                    outcome = terminal['outcome']
                    if event_resume_nonce is not None and outcome == 'victory':
                        terminal_seen = outcome
                        continue
                    break
                else:
                    value = probe._validate_combat(memoryview(body), 'heuristic',
                                                   allow_empty_enemies=campaign, allow_infinite_health=campaign)
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
                initial = request('GET', choice_read, None)
                try:
                    check()
                    choice_value = decode(initial)
                    if choice_value.get('choice_id') is not None or choice_value.get('status') == 'failed':
                        require(len(choices) < 32, 'combat_choice_limit')
                        summary = run_choice(request, provider=choice_provider, clock=clock, sleep=sleep,
                                             deadline=deadline, initial=initial, version=choice_version)
                        choices.append(summary)
                        require(summary['status'] == 'resolved', 'combat_choice_failed')
                    else:
                        # Validate an idle response too; malformed errors are never a waiting loop.
                        validator = ChoiceController(request, choice_provider, clock, sleep, deadline, choice_version)
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
            require(0 <= value['round'] - first_round < (96 if campaign else 12), 'combat_round_limit')
            require(accepted < (512 if campaign else 48) and attempted < (768 if campaign else 72), 'combat_action_limit')
            if campaign_potions:
                require(campaign, 'potion_campaign_required')
                observed = request('GET', POTION_READ, None)
                try:
                    check()
                    potion_view = decode(observed)
                    waiting = potion_view == dict(schema_version=1, protocol='combat_potions_v1', status='waiting')
                    selected = 'refresh' if waiting else potion_action(potion_view, value)
                finally:
                    observed[:] = b'\0' * len(observed)
                if selected == 'refresh':
                    sleep(min(.05, max(0, deadline-clock())))
                    continue
                if selected is not None:
                    require(len(potions) < 24, 'combat_potion_limit')
                    used = use_potion(request, potion_view['decision_id'], selected, deadline=deadline, clock=clock, sleep=sleep)
                    used['potion_id'] = next(p['id'] for p in potion_view['potions'] if p['slot'] == int(selected.split(':')[1]))
                    potions.append(used)
                    require(used['status'] in ('resolved', 'stale'), used['code'] or 'potion_failed')
                    continue
            decision = value['decision_id']
            action = campaign_action(value) if campaign else value['recommendation']['action_id']
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
    except ToolFailure as error:
        code = 'invalid_response'
        validation_code = error.error_code
    except (ValueError, TypeError, KeyError, RecursionError):
        code = 'invalid_response'
    except Exception:
        code = 'transport_failure'
    result = dict(schema_version=1, status='resolved' if code is None else 'failed', code=code,
                  attempted=attempted, accepted=accepted, reconciled=reconciled, reads=reads,
                  stale_rejections=stale, choice_probes=choice_probes, choices=choices, outcome=outcome)
    if campaign_potions: result['potions'] = potions
    if validation_code is not None: result['validation_code'] = validation_code
    if event_resume_nonce is not None: result.update(resume_reads=resume_reads, native_terminal_outcome=terminal_seen, resume_items=resume_items)
    return result
