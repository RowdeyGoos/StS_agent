"""Bounded gold/card reward resolution using the maintained native reward codec."""
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


def run_rewards(request, *, policy='first-card', clock=time.monotonic, sleep=time.sleep):
    attempted = accepted = reconciled = reads = stale = 0
    claimed_gold = skipped = 0
    selected_cards = []
    pending = None
    finished = set()
    offers = None
    before_player = after_player = None
    deadline = clock() + 45

    def check():
        require(clock() < deadline, 'reward_timeout')

    def offer(reward):
        return (reward['kind'], reward['gold_amount'], tuple(reward['cards']))

    def validate_domain(state):
        nonlocal offers
        for slot, reward in enumerate(state['rewards']):
            require(type(reward['reward_slot']) is int and reward['reward_slot'] == slot)
            require(reward['kind'] != 'unsupported' or reward['successfully_selected'], 'unsupported_reward')
        if offers is None:
            require(state['screen_kind'] == 'rewards', 'reward_parent_required')
            offers = {r['reward_index']: offer(r) for r in state['rewards']}
            finished.update(r['reward_index'] for r in state['rewards'] if r['successfully_selected'])
        for reward in state['rewards']:
            require(offers.get(reward['reward_index']) == offer(reward), 'reward_offer_changed')
        if state['screen_kind'] == 'rewards':
            actions = {a['action_id'] for a in state['legal_actions']}
            for slot, reward in enumerate(state['rewards']):
                if reward['successfully_selected'] or reward['reward_index'] in finished:
                    require('claim:' + str(slot) not in actions and 'open:' + str(slot) not in actions,
                            'reward_offered_again')
                else:
                    prefix = 'claim:' if reward['kind'] == 'gold' else 'open:'
                    require(prefix + str(slot) in actions, 'unresolved_reward')
            # Visible slots may compact after collection. Stable set indices may
            # disappear only after a verified claim, choice or skip.
            visible = {r['reward_index'] for r in state['rewards']}
            require(set(offers) - visible <= finished, 'reward_disappeared')

    try:
        require(policy in ('first-card', 'skip-card'), 'reward_policy')
        while True:
            check()
            require(reads < 512, 'reward_read_limit')
            reads += 1
            body = None
            try:
                body = request('GET', READ, None)
                check()
                value = decode(body)
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
                elif kind in ('choose_card', 'skip_card'):
                    reward = before['rewards'][0]
                    finished.add(reward['reward_index'])
                    if kind == 'choose_card': selected_cards.append(reward['cards'][action['card_slot']])
                    else: skipped += 1
                reconciled += 1
                pending = None
                after_player = state['player']
                if kind == 'proceed':
                    break
            require(state['screen_kind'] != 'map', 'reward_already_complete')
            validate_domain(state)
            if before_player is None:
                before_player = state['player']
            after_player = state['player']
            action = codec._choose_action(state, policy)
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
        codes = {'reward_response_mismatch', 'reward_complete_response_mismatch', 'reward_action_response_mismatch',
                 'gold_claim_reconciliation_failed', 'card_open_reconciliation_failed', 'card_choice_reconciliation_failed',
                 'card_skip_reconciliation_failed', 'reward_proceed_reconciliation_failed', 'reward_revision_mismatch',
                 'card_reward_not_skippable', 'reward_provider_no_action'}
        code = error.error_code if error.error_code in codes else 'reward_response_mismatch'
    except (ValueError, TypeError, KeyError, IndexError, RecursionError):
        code = 'reward_response_mismatch'
    except Exception:
        code = 'reward_transport_failure'
    return dict(schema_version=1, status='resolved' if code is None else 'failed', code=code,
                policy=policy, attempted=attempted, accepted=accepted, reconciled=reconciled,
                reads=reads, stale_rejections=stale, claimed_gold=claimed_gold,
                selected_cards=selected_cards, skipped_card_rewards=skipped,
                before_player=before_player, after_player=after_player)
