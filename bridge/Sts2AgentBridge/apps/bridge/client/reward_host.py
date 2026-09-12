"""Bounded gold/card/item reward resolution using the maintained native reward codec."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).absolute().parents[3] / 'tools'))
import apply_reward_live as codec
from combat_host import Stop, decode, require
from tool_common import ToolFailure

READ = '/probe/v0/public/reward-decision'
ACTION = '/probe/v0/public/reward-action'


def run_rewards(request, *, policy='first-card', potion_policy='stop-on-full', clock=time.monotonic, sleep=time.sleep):
    attempted = accepted = reconciled = reads = stale = 0
    claimed_gold = skipped = 0
    selected_cards = []
    claimed_special_cards = []
    collected_items = []
    skipped_potions = []
    discarded_potions = []
    capacity_gains = []
    capacity_schema = None
    pending = None
    finished = set()
    offers = None
    before_player = after_player = None
    deadline = clock() + 45

    def check():
        require(clock() < deadline, 'reward_timeout')

    def offer(reward):
        return (reward['kind'], reward['gold_amount'], tuple(reward['cards']), reward.get('item_key'), reward.get('potion_capacity_gain',0))

    def validate_domain(state):
        nonlocal offers, capacity_schema
        if capacity_schema is None:capacity_schema=state.get('capacity_rewards',False)
        require(state.get('capacity_rewards',False)==capacity_schema,'reward_offer_changed')
        for slot, reward in enumerate(state['rewards']):
            require(type(reward['reward_slot']) is int and reward['reward_slot'] == slot)
            require(reward['kind'] != 'unsupported' or reward['successfully_selected'], 'unsupported_reward')
        if offers is None:
            require(state['screen_kind'] == 'rewards', 'reward_parent_required')
            offers = {r['reward_index']: offer(r) for r in state['rewards']}
            finished.update(r['reward_index'] for r in state['rewards'] if r['successfully_selected'])
        for reward in state['rewards']:
            require(not reward['successfully_selected'] or reward['reward_index'] in finished, 'reward_selected_without_action')
            require(offers.get(reward['reward_index']) == offer(reward), 'reward_offer_changed')
        if state['screen_kind'] == 'rewards':
            actions = {a['action_id'] for a in state['legal_actions']}
            for slot, reward in enumerate(state['rewards']):
                if reward['successfully_selected'] or reward['reward_index'] in finished:
                    require('claim:' + str(slot) not in actions and 'open:' + str(slot) not in actions and 'take:' + str(slot) not in actions and 'collect:' + str(slot) not in actions,
                            'reward_offered_again')
                else:
                    prefix = {'gold': 'claim:', 'special_card': 'take:', 'card': 'open:', 'potion': 'collect:', 'relic': 'collect:'}.get(reward['kind'], 'open:')
                    require(prefix + str(slot) in actions or reward['kind'] == 'potion' and (potion_policy != 'stop-on-full' or codec._capacity_action(state) is not None),
                            'potion_inventory_full' if reward['kind'] == 'potion' else 'unresolved_reward')
            # Visible slots may compact after collection. Stable set indices may
            # disappear only after a verified claim, choice or skip.
            visible = {r['reward_index'] for r in state['rewards']}
            require(set(offers) - visible <= finished, 'reward_disappeared')

    try:
        require(policy in ('first-card', 'skip-card'), 'reward_policy')
        require(potion_policy in ('stop-on-full', 'skip-full', 'skip-all', 'replace-first'), 'potion_policy')
        while True:
            check()
            require(reads < 512, 'reward_read_limit')
            reads += 1
            body = None
            try:
                body = request('GET', READ, None)
                check()
                require(type(body) is bytearray and 0 < len(body) <= 65536)
                value = json.loads(body, object_pairs_hook=codec.probe._unique_object, parse_constant=codec.probe._reject_json_constant)
                require(type(value) is dict)
                if body == codec._REWARD_WAITING:
                    state = None
                else:
                    require(body != codec._REWARD_UNSUPPORTED, 'unsupported_reward')
                    state = (codec._validate_complete(body) if value.get('status') == 'complete' else
                             codec._validate_ready(body))
            finally:
                if type(body) is bytearray:
                    body[:] = b'\0' * len(body)
            if state is None:
                sleep(min(0.05, max(0, deadline - clock())))
                continue
            if pending is not None:
                before, action = pending
                if state.get('decision_id') == before['decision_id']:
                    require(state == before, 'reward_identity_reused')
                    sleep(min(0.05, max(0, deadline - clock())))
                    continue
                codec._validate_transition(before, state, action)
                kind = action['kind']
                if kind == 'open_card':
                    opened = before['rewards'][action['reward_slot']]
                    require(state['rewards'][0]['reward_index'] == opened['reward_index'] and
                            offer(state['rewards'][0]) == offer(opened), 'reward_child_mismatch')
                # Count only transitions that the native reader has reconciled.
                if kind == 'claim_gold':
                    reward = before['rewards'][action['reward_slot']]
                    claimed_gold += reward['gold_amount']
                    finished.add(reward['reward_index'])
                elif kind == 'discard_potion':
                    slot=action['potion_slot']
                    discarded_potions.append(dict(slot=slot,key=before['potion_slots'][slot]))
                elif kind == 'collect_item':
                    reward = before['rewards'][action['reward_slot']]
                    collected_items.append(dict(kind=reward['kind'], key=reward['item_key'], reward_index=reward['reward_index']))
                    if reward.get('potion_capacity_gain',0):
                        capacity_gains.append(dict(key=reward['item_key'],reward_index=reward['reward_index'],before=len(before['potion_slots']),after=len(state['potion_slots'])))
                    finished.add(reward['reward_index'])
                elif kind == 'claim_special_card':
                    reward = before['rewards'][action['reward_slot']]
                    claimed_special_cards.append(reward['cards'][0])
                    finished.add(reward['reward_index'])
                elif kind in ('choose_card', 'skip_card'):
                    reward = before['rewards'][0]
                    finished.add(reward['reward_index'])
                    if kind == 'choose_card': selected_cards.append(reward['cards'][action['card_slot']])
                    else: skipped += 1
                reconciled += 1
                pending = None
                after_player = state['player']
                if kind == 'proceed':
                    skipped_potions = [dict(key=r['item_key'], reward_index=r['reward_index'],
                        reason='policy' if potion_policy == 'skip-all' else 'inventory_full')
                        for slot, r in enumerate(before['rewards']) if r['kind'] == 'potion' and not r['successfully_selected']]
                    break
            require(state['screen_kind'] != 'map', 'reward_already_complete')
            validate_domain(state)
            if before_player is None:
                before_player = state['player']
            after_player = state['player']
            action = codec._choose_action(state, policy, potion_policy)
            if policy == 'skip-card' and action['kind'] == 'open_card':
                require(state['rewards'][action['reward_slot']]['card_selection_can_skip'], 'card_reward_not_skippable')
            require(accepted < 17 and attempted < 25, 'reward_action_limit')
            decision, action_id = state['decision_id'], action['action_id']
            request_body = bytearray(json.dumps({'decision_id': decision, 'action_id': action_id}, separators=(',', ':')).encode())
            receipt = None
            attempted += 1
            try:
                receipt = request('POST', ACTION, request_body)
                check()
                response = decode(receipt)
                rejected = dict(schema_version=1, status='rejected', mutation_state='none',
                                decision_id=decision, action_id=action_id, reason='stale_decision')
                if response == rejected:
                    stale += 1
                    require(stale <= 8, 'reward_stale_limit')
                else:
                    codec._validate_action_response(receipt, decision, action_id)
                    accepted += 1
                    pending = (state, action)
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
        codes = {'potion_replacement_unavailable', 'potion_discard_reconciliation_failed', 'reward_response_mismatch', 'reward_complete_response_mismatch', 'reward_action_response_mismatch',
                 'gold_claim_reconciliation_failed', 'special_card_claim_reconciliation_failed', 'item_claim_reconciliation_failed', 'card_open_reconciliation_failed', 'card_choice_reconciliation_failed',
                 'card_skip_reconciliation_failed', 'reward_proceed_reconciliation_failed', 'reward_revision_mismatch',
                 'card_reward_not_skippable', 'reward_provider_no_action'}
        code = error.error_code if error.error_code in codes else 'reward_response_mismatch'
    except (ValueError, TypeError, KeyError, IndexError, RecursionError):
        code = 'reward_response_mismatch'
    except Exception:
        code = 'reward_transport_failure'
    return dict(schema_version=1, status='resolved' if code is None else 'failed', code=code,
                policy=policy, potion_policy=potion_policy, skipped_potions=skipped_potions, discarded_potions=discarded_potions, potion_capacity_gains=capacity_gains, attempted=attempted, accepted=accepted, reconciled=reconciled,
                reads=reads, stale_rejections=stale, claimed_gold=claimed_gold,
                selected_cards=selected_cards, claimed_special_cards=claimed_special_cards, collected_items=collected_items, skipped_card_rewards=skipped,
                before_player=before_player, after_player=after_player)
