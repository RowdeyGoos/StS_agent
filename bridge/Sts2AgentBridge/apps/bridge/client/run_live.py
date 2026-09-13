#!/usr/bin/env python3
"""One client entry point for the unified bridge's bounded capabilities."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).absolute().parents[3]


def verify_map_handoff(request, *, clock=time.monotonic, sleep=time.sleep):
    """Observe a fresh actionable map through the existing codec; never select a node."""
    sys.path.insert(0, str(ROOT / 'tools'))
    import apply_map_live as maps
    from tool_common import ToolFailure

    reads = 0
    code = 'map_handoff_timeout'
    deadline = clock() + 5.0
    try:
        while reads < 100 and clock() < deadline:
            reads += 1
            response = request('GET', maps._MAP_DECISION_ROUTE, None)
            try:
                if clock() >= deadline:
                    break
                if response == maps._MAP_UNSUPPORTED:
                    code = 'map_handoff_unsupported'
                    break
                if response != maps._MAP_WAITING:
                    decision = maps._validate_ready(response)
                    return {'status': 'passed', 'reads': reads,
                            'candidate_count': len(decision['candidates']), 'code': None}
            finally:
                if type(response) is bytearray:
                    response[:] = b'\0' * len(response)
            sleep(min(0.05, max(0.0, deadline - clock())))
    except KeyboardInterrupt:
        code = 'interrupted'
    except (ToolFailure, ValueError, TypeError, KeyError):
        code = 'map_handoff_invalid_response'
    except Exception:
        code = 'map_handoff_transport_failure'
    return {'status': 'failed', 'reads': reads, 'candidate_count': 0, 'code': code}


def run_event_map(request, host, *, event_provider=None, clock=time.monotonic, sleep=time.sleep):
    """Keep event evidence even if the subsequent core observation fails."""
    event = host.run_event(request, provider=event_provider or host.first_legal, clock=clock, sleep=sleep)
    handoff = ({'status': 'not_attempted', 'reads': 0, 'candidate_count': 0, 'code': None}
               if event['status'] != 'resolved' or event.get('destination')!='map_handoff' else
               verify_map_handoff(request, clock=clock, sleep=sleep))
    return {'schema_version': 1,
            'status': 'resolved' if handoff['status'] == 'passed' or event['status']=='resolved' and event.get('destination') in ('run_won','run_abandoned') else 'failed',
            'event': event, 'map_handoff': handoff,
            'code': event['code'] if event['status'] != 'resolved' else (None if event.get('destination') in ('run_won','run_abandoned') else handoff['code'] if handoff['status'] != 'not_attempted' else 'event_destination_not_map')}


def event_option_policy(host, stable_id, abandon_policy="cancel", potion_policy="skip-full"):
    """Select one explicitly requested first parent option, then use advertised actions."""
    if abandon_policy not in ("cancel", "confirm"): raise ValueError("Unknown abandon policy.")
    used = False
    def choose(view):
        nonlocal used
        if view.kind=="item_policy":return host.item_policy_action(view.payload,potion_policy)
        if view.kind == "abandon_confirmation":
            return "confirm_abandon" if abandon_policy == "confirm" else "cancel"
        if used or stable_id is None or view.kind != 'parent': return host.first_legal(view)
        matches = [c['action_id'] for c in view.payload['candidates']
                   if c['stable_id'] == stable_id and c['action_id'] in view.payload['legal_actions']]
        if len(matches) != 1: raise ValueError('Requested event option is not uniquely legal.')
        used = True
        return matches[0]
    return choose


def run_resuming_event_combat(request, event, events, combat, *, event_provider=None,
                              choice_provider=None, potion_policy="skip-full", clock=time.monotonic, sleep=time.sleep):
    """One witnessed event resume; no reward or victory assumption for training expiry."""
    fight = combat.run_combat(request, choice_provider=choice_provider or combat.first_select,
                              event_resume_nonce=event['session_nonce'], resume_potion_policy=potion_policy, clock=clock, sleep=sleep)
    resumed = {'status': 'not_attempted', 'code': None}
    handoff = {'status': 'not_attempted', 'reads': 0, 'candidate_count': 0, 'code': None}
    code = fight['code']
    if fight['status'] == 'resolved':
        if fight['outcome'] != 'event_resumed': code = 'event_not_resumed'
        else:
            resumed = events.run_event(request, provider=event_provider or events.first_legal, clock=clock, sleep=sleep)
            code = resumed['code']
            if resumed['status'] == 'resolved':
                if resumed.get('destination') != 'map_handoff': code = 'event_resume_destination_unsupported'
                else:
                    handoff = verify_map_handoff(request, clock=clock, sleep=sleep)
                    code = handoff['code']
    return {'status': 'resolved' if handoff['status'] == 'passed' else 'failed', 'code': code,
            'combat': fight, 'resumed_event': resumed, 'map_handoff': handoff}


def run_event_combat_map(request, events, combat, rewards, *, event_provider=None,
                         choice_provider=None, reward_policy='first-card', potion_policy='stop-on-full', event_potion_policy='skip-full', clock=time.monotonic, sleep=time.sleep):
    """Complete one non-resuming event combat without treating entry as victory."""
    event=events.run_event(request,provider=event_provider or events.first_legal,clock=clock,sleep=sleep)
    flow={'status':'not_attempted','code':None}
    if event['status']=='resolved' and event.get('destination')=='combat_handoff':
        flow=run_combat_map(request,combat,rewards,choice_provider=choice_provider,
                            reward_policy=reward_policy,potion_policy=potion_policy,clock=clock,sleep=sleep)
    elif event['status']=='resolved' and event.get('destination')=='combat_resume_handoff':
        flow=run_resuming_event_combat(request,event,events,combat,event_provider=event_provider,
            choice_provider=choice_provider,potion_policy=event_potion_policy,clock=clock,sleep=sleep)
    code=event.get('code') if event['status']!='resolved' else (flow.get('code') if flow['status']!='not_attempted' else 'event_combat_not_entered')
    return {'schema_version':1,'status':'resolved' if flow['status']=='resolved' else 'failed',
            'code':code,'event':event,'combat_flow':flow}


def run_combat_map(request, combat, rewards, *, choice_provider=None, reward_policy='first-card', potion_policy='stop-on-full',
                   clock=time.monotonic, sleep=time.sleep):
    """One combat and its gold/card rewards, ending at an observed actionable map."""
    fight = combat.run_combat(request, choice_provider=choice_provider or combat.first_select,
                              clock=clock, sleep=sleep)
    loot = {'status': 'not_attempted', 'code': None}
    handoff = {'status': 'not_attempted', 'reads': 0, 'candidate_count': 0, 'code': None}
    stage = 'combat'
    code = fight['code']
    if fight['status'] == 'resolved':
        if fight['outcome'] != 'victory':
            code = 'combat_defeat'
        else:
            stage = 'rewards'
            loot = rewards.run_rewards(request, policy=reward_policy, potion_policy=potion_policy, clock=clock, sleep=sleep)
            code = loot['code']
            if loot['status'] == 'resolved':
                stage = 'map'
                handoff = verify_map_handoff(request, clock=clock, sleep=sleep)
                code = handoff['code']
    return {'schema_version': 1, 'status': 'resolved' if handoff['status'] == 'passed' else 'failed',
            'stage': stage, 'code': code, 'combat': fight, 'rewards': loot, 'map_handoff': handoff}


def core_summary(method, route, value):
    success = type(value) is dict and value.get('schema_version') == 1
    if method == 'POST':
        success = success and value.get('status') == 'accepted'
    elif route == '/probe/v0/health':
        success = success and value.get('lifecycle_state') == 'running'
    elif route == '/probe/v0/manifest':
        success = success and value.get('bridge_version') == '1.0.0' and value.get('build_compatibility') == 'compatible'
    else:
        success = success and value.get('status') in ('ready', 'waiting', 'complete')
    return {'status': 'passed' if success else 'failed', 'response': value}


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def retain_read_diagnostic(result, client):
    """Keep original stage/counter evidence alongside a bounded runtime failure."""
    if client.read_diagnostic is not None:
        return {**result, 'read_diagnostic': client.read_diagnostic}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-manifest', type=Path, required=True)
    parser.add_argument('--release-sha256', required=True)
    parser.add_argument('--expected-state-sha256', required=True)
    parser.add_argument('--capability', choices=['events', 'event-map', 'event-combat-map', 'combat', 'combat-map', 'combat-choice', 'rewards', 'cards', 'items', 'shop', 'room-event', 'core'], required=True)
    parser.add_argument('--shop-max-purchases', type=int, choices=range(9), default=1, help='Maximum shop purchases, 0 to 8; zero leaves without buying.')
    parser.add_argument('--event-potion-policy', choices=('skip-full','skip-all','replace-first','stop-on-full'), default='skip-full')
    parser.add_argument('--shop-potion-policy', choices=('skip-full','replace-first'), default='skip-full', help='Optionally discard an eligible original potion before buying when the belt is full.')
    parser.add_argument('--shop-removal-policy', choices=('skip','first'), default='skip', help='Optionally remove the first eligible deck card before buying; counts toward the shop limit and gold reserve.')
    parser.add_argument('--shop-purchase-policy', choices=('cards','potions','cards-and-potions','relics','all'), default='cards', help='Shop offer kinds to buy; slot order within the selected kinds.')
    parser.add_argument('--shop-gold-reserve', type=int, default=0, help='Minimum gold to retain after each shop purchase.')
    parser.add_argument('--abandon-policy', choices=('cancel','confirm'), default='cancel', help='Cancel event abandonment popups by default; confirm explicitly ends the run.')
    parser.add_argument('--event-option', help='Exact stable ID of the first parent option; absence or illegality stops before input.')
    parser.add_argument('--choice-policy', choices=['first-select', 'minimum'], default='first-select',
                        help='Combat chooser policy; minimum confirms as soon as native controls allow it.')
    parser.add_argument('--reward-policy', choices=['first-card', 'skip-card'], default='first-card',
                        help='Claim gold, then choose the first card or use the native card skip.')
    parser.add_argument('--potion-policy', choices=['stop-on-full', 'skip-full', 'skip-all', 'replace-first'], default='stop-on-full',
                        help='Terminal rewards: stop on full inventory, leave full-inventory potions, leave all potions, or replace an eligible starting potion.')
    parser.add_argument('--route', help='Core route to observe, or act on with --decision and --action.')
    parser.add_argument('--decision')
    parser.add_argument('--action')
    args = parser.parse_args()
    credential = bytearray()
    client = None
    result = {'status': 'failed', 'code': 'client_preflight_failed'}
    try:
        sys.path.insert(0, str(ROOT))
        from release_support import verify_release_sources
        verify_release_sources(ROOT, 'bridge', args.release_manifest, args.release_sha256)
        sys.path.insert(0, str(ROOT / 'apps/bridge/operations'))
        import manage_live_campaign as manager
        from secure_operator import read_credential
        from wire_client import BridgeClient
        layout, state = manager.validate_installed_for_client(args.expected_state_sha256)
        credential = read_credential(layout.user_profile, os.geteuid(), state, manager.require_no_granting_acl_fd)
        client = BridgeClient(credential)
        if args.capability in ('combat', 'combat-map', 'combat-choice', 'rewards'):
            host = load('unified_combat_host', 'apps/bridge/client/combat_host.py')
            provider = host.first_select if args.choice_policy == 'first-select' else host.minimum_select
            if args.capability in ('combat-map', 'rewards'):
                rewards = load('unified_reward_host', 'apps/bridge/client/reward_host.py')
                result = (run_combat_map(client.exchange, host, rewards, choice_provider=provider, reward_policy=args.reward_policy,potion_policy=args.potion_policy)
                          if args.capability == 'combat-map' else rewards.run_rewards(client.exchange, policy=args.reward_policy,potion_policy=args.potion_policy))
            else:
                result = (host.run_combat(client.exchange, choice_provider=provider) if args.capability == 'combat' else
                          host.run_choice(client.exchange, provider=provider))
        elif args.capability == 'event-combat-map':
            events=load('unified_event_host','components/events/host/generic_event_host.py')
            combat=load('unified_combat_host','apps/bridge/client/combat_host.py')
            rewards=load('unified_reward_host','apps/bridge/client/reward_host.py')
            provider=combat.minimum_select if args.choice_policy=='minimum' else combat.first_select
            result=run_event_combat_map(client.exchange,events,combat,rewards,event_provider=event_option_policy(events,args.event_option,args.abandon_policy,args.event_potion_policy),choice_provider=provider,reward_policy=args.reward_policy,potion_policy=args.potion_policy,event_potion_policy=args.event_potion_policy)
        elif args.capability in ('events', 'event-map'):
            host = load('unified_event_host', 'components/events/host/generic_event_host.py')
            provider = event_option_policy(host,args.event_option,args.abandon_policy,args.event_potion_policy)
            result = (run_event_map(client.exchange, host,event_provider=provider) if args.capability == 'event-map' else
                      host.run_event(client.exchange, provider=provider))
        elif args.capability == 'cards':
            host = load('unified_card_host', 'components/cards/host/card_selection_host.py')
            result = host.run_card_selection(client.exchange)
        elif args.capability in ('items', 'shop', 'room-event'):
            items = load('unified_item_host', 'components/item_wire/host/item_host.py')
            if args.capability == 'items':
                result = items.run_collection(client.item_exchange)
            else:
                rooms = load('unified_room_host', 'components/rooms/host/room_flow_host.py')
                result = rooms.run_flow('shop' if args.capability == 'shop' else 'event', client.item_exchange, item_host=items, max_purchases=args.shop_max_purchases, gold_reserve=args.shop_gold_reserve, purchase_policy=args.shop_purchase_policy, removal_policy=args.shop_removal_policy, potion_policy=args.shop_potion_policy)
        else:
            if not args.route or not args.route.startswith('/probe/v0/') or bool(args.decision) != bool(args.action):
                raise ValueError('core_request')
            body = None if args.action is None else bytearray(json.dumps({'decision_id': args.decision, 'action_id': args.action}, separators=(',', ':')).encode())
            try:
                response = client.exchange('GET' if body is None else 'POST', args.route, body)
                try:
                    result = core_summary('GET' if body is None else 'POST', args.route, json.loads(response))
                finally:
                    response[:] = b'\0' * len(response)
            finally:
                if body is not None:
                    body[:] = b'\0' * len(body)
    except KeyboardInterrupt:
        result = {'status': 'failed', 'code': 'interrupted'}
    except Exception:
        result = {'status': 'failed', 'code': 'client_failed'}
    finally:
        if client is not None:
            result = retain_read_diagnostic(result, client)
            client.close()
        credential[:] = b'\0' * len(credential)
    print(json.dumps(result, separators=(',', ':'), ensure_ascii=True))
    return 0 if result.get('status') in ('passed', 'resolved') else 4


if __name__ == '__main__':
    raise SystemExit(main())
