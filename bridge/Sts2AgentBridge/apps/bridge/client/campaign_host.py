"""One bounded native campaign, using the existing room controllers and listener.

This integration policy tests traversal. It skips optional combat cards, uses supported ordinary potions,
leaves shops, opens chests and skips their relics, rests, and prefers an advertised exit.
It is separate from the full headless policy/encoding profile.
"""
from __future__ import annotations

import json
import re
import time

from combat_host import Stop, decode, require
import apply_map_live as maps
import apply_room_live as rooms

READ = '/probe/campaign-v2/public/decision'
ACTION = '/probe/campaign-v2/public/action'
POLICY = 'native_campaign_smoke_v6'
MAX_POSTS, MAX_READS, MAX_STAGES, MAX_SECONDS = 8192, 131072, 320, 5400


def validate_view(value):
    check_failure(value)
    require(type(value.get('schema_version')) is int and value['schema_version'] == 1, 'campaign_version')
    require(set(value) == {'schema_version', 'protocol', 'status', 'surface', 'run_id',
        'act_index', 'floor', 'character', 'ascension', 'room_kind', 'hp', 'max_hp',
        'decision_id', 'legal_actions', 'completed_decision_id'}, 'campaign_view_shape')
    require(value['protocol'] == 'campaign_v2' and value['status'] in ('ready', 'waiting', 'unsupported'), 'campaign_view')
    require(type(value['run_id']) is str and re.fullmatch('[0-9a-f]{32}', value['run_id']), 'campaign_run_identity')
    require(value['surface'] in ('unknown', 'map', 'combat', 'rewards', 'event', 'rest', 'shop', 'treasure', 'overlay'), 'campaign_surface')
    for key in ('decision_id', 'completed_decision_id'):
        require(value[key] is None or type(value[key]) is str and re.fullmatch('[0-9a-f]{64}', value[key]), 'campaign_decision')
    legal = value['legal_actions']
    expected = ('open_chest', 'skip_relic') if value['surface'] == 'treasure' else ('proceed',)
    require(legal == [] if value['decision_id'] is None else
            type(legal) is list and len(legal) == 1 and legal[0] in expected, 'campaign_actions')
    require(value['decision_id'] is None or value['surface'] in ('treasure', 'shop') and value['status'] == 'ready', 'campaign_actions')
    require(value['surface'] != 'treasure' or value['status'] != 'ready' or value['decision_id'] is not None, 'campaign_actions')
    if value['status'] == 'ready':
        require(type(value['act_index']) is int and 0 <= value['act_index'] <= 2 and
                type(value['floor']) is int and 0 <= value['floor'] <= 80 and
                value['character'] == 'ironclad' and type(value['ascension']) is int and value['ascension'] == 0 and
                type(value['hp']) is int and type(value['max_hp']) is int and 0 <= value['hp'] <= value['max_hp'] and
                type(value['room_kind']) is str and re.fullmatch('[a-z_]{1,24}', value['room_kind']), 'campaign_profile')
    return value


def check_failure(value):
    if value.get('status') == 'failed':
        require(set(value) == {'schema_version', 'protocol', 'status', 'code'} and
                type(value['schema_version']) is int and value['schema_version'] == 1 and
                value['protocol'] == 'campaign_v2' and
                value['code'] in ('campaign_context_failed', 'campaign_treasure_failed'), 'campaign_failure_shape')
        raise Stop(value['code'])


def event_policy(events):
    def choose(view):
        if view.kind == 'item_policy':
            return events.item_policy_action(view.payload, 'skip-full')
        if view.kind == 'abandon_confirmation':
            return 'cancel'
        if view.kind == 'parent':
            exits = [c['action_id'] for c in view.payload['candidates']
                     if c['action_id'] in view.payload['legal_actions'] and
                     any(word in c['stable_id'].upper().split('.') for word in ('LEAVE', 'IGNORE', 'REFUSE', 'PROCEED'))]
            if exits:
                return exits[0]
        return events.first_legal(view)
    return choose


class Campaign:
    def __init__(self, request, item_exchange, *, combat, rewards, events, shop, items,
                 setup, entry_mode, progress, clock, sleep):
        require(setup in ('controlled_extra_hp', 'normal_hp'), 'campaign_setup')
        require(entry_mode in ('fresh', 'resume'), 'campaign_entry_mode')
        self.request, self.item_exchange = request, item_exchange
        self.combat, self.rewards, self.events, self.shop, self.items = combat, rewards, events, shop, items
        self.setup, self.progress, self.clock, self.sleep = setup, progress, clock, sleep
        self.entry_mode = entry_mode
        self.start = clock()
        self.deadline = self.start + MAX_SECONDS
        self.posts = self.reads = 0
        self.stages = []
        self.run_id = None
        self.act = self.floor = -1
        self.acts = set()
        self.bosses = set()
        self.entry = None
        self.local_counts = dict(attempted=0, accepted=0, reconciled=0)
        self.stage_recorded = True
        self.surface = 'entry'

    def check(self):
        require(self.clock() < self.deadline, 'campaign_timeout')

    def exchange(self, method, route, body=None):
        self.check()
        if method == 'POST':
            require(self.posts < MAX_POSTS, 'campaign_post_limit')
            self.posts += 1
        else:
            require(self.reads < MAX_READS, 'campaign_read_limit')
            self.reads += 1
        # No retries at this boundary, including lost receipts and uncertain input.
        return self.request(method, route, body)

    def item_request(self, method, route, decision, action, deadline):
        # Reuse the same budget and transport; the old item's adapter only changes
        # argument shape and maps its transport exception.
        body = None if method == 'GET' else bytearray(json.dumps({'decision_id': decision, 'action_id': action}, separators=(',', ':')).encode())
        try:
            self.check()
            require(self.clock() < deadline, 'campaign_child_timeout')
            return self.exchange(method, route, body)
        finally:
            if body is not None:
                body[:] = b'\0' * len(body)

    def get(self, route, validator=decode):
        body = self.exchange('GET', route)
        try:
            self.check()
            return validator(body)
        finally:
            body[:] = b'\0' * len(body)

    def post(self, route, decision, action, validator=None):
        body = bytearray(json.dumps({'decision_id': decision, 'action_id': action}, separators=(',', ':')).encode())
        receipt = None
        before_posts = self.posts
        try:
            receipt = self.exchange('POST', route, body)
            if validator:
                validator(receipt, decision, action)
            else:
                value = decode(receipt)
                check_failure(value)
                require(value == dict(schema_version=1, protocol='campaign_v2', status='accepted', decision_id=decision, action_id=action), 'campaign_receipt')
            self.local_counts['accepted'] += 1
            self.check()
        finally:
            self.local_counts['attempted'] += self.posts - before_posts
            body[:] = b'\0' * len(body)
            if receipt is not None:
                receipt[:] = b'\0' * len(receipt)

    def view(self):
        value = validate_view(self.get(READ))
        require(value['status'] != 'unsupported', 'campaign_surface_unsupported')
        if value['status'] == 'ready':
            if self.run_id is None:
                if self.entry_mode == 'fresh':
                    require(value['act_index'] == 0 and value['floor'] <= 1 and value['surface'] in ('event', 'map'), 'campaign_entry_required')
                else:
                    require(value['surface'] in ('event', 'map', 'combat', 'rewards', 'rest', 'shop', 'treasure'), 'campaign_entry_required')
                require(self.setup != 'controlled_extra_hp' or value['max_hp'] > 80, 'campaign_extra_hp_required')
                self.run_id = value['run_id']
                self.entry = {k: value[k] for k in ('act_index', 'floor', 'surface', 'character', 'ascension', 'hp', 'max_hp')}
                # A resumed segment starts its own continuity and coverage record.
                # Never infer earlier bosses or adopt another host's pending input.
                self.act, self.floor = value['act_index'], value['floor']
            require(value['run_id'] == self.run_id and self.act <= value['act_index'] <= self.act + 1 and value['floor'] >= self.floor, 'campaign_continuity')
            self.act, self.floor = value['act_index'], value['floor']
            self.acts.add(self.act)
        return value

    def begin_stage(self, surface):
        self.check()
        require(len(self.stages) < MAX_STAGES, 'campaign_stage_limit')
        self.surface = surface
        self.stage_recorded = False
        self.local_counts = dict(attempted=0, accepted=0, reconciled=0)

    def record(self, surface, result):
        # Save completed child evidence even when the operation used the last
        # available time. The stage budget is checked before starting any child.
        counts = {key: result.get(key, 0) for key in ('attempted', 'accepted', 'reconciled', 'parent_attempted', 'parent_accepted', 'parent_reconciled', 'child_attempted', 'child_accepted', 'child_reconciled')}
        stage = dict(index=len(self.stages), act_index=self.act, floor=self.floor, surface=surface,
                     status=result['status'], code=result.get('code'), outcome=result.get('outcome'), destination=result.get('destination'), **counts)
        if 'choices' in result:
            stage['choices'] = [{k: child.get(k) for k in ('status', 'code', 'native_code', 'pile',
                                'attempted', 'accepted', 'reconciled', 'selected_count')} for child in result['choices']]
            for key in ('attempted', 'accepted', 'reconciled'):
                stage['child_' + key] = sum(child[key] for child in result['choices'])
        if 'potions' in result:
            stage['potions'] = result['potions']
            for key in ('attempted', 'accepted', 'reconciled'):
                stage['potion_' + key] = sum(p[key] for p in result['potions'])
        if 'validation_code' in result: stage['validation_code'] = result['validation_code']
        self.stages.append(stage)
        self.stage_recorded = True
        if self.progress:
            self.progress(stage)
        require(result['status'] in ('resolved', 'passed'), result.get('code') or 'campaign_stage_failed')
        self.check()

    def map(self):
        before = self.get(maps._MAP_DECISION_ROUTE, maps._validate_ready)
        priorities = {'rest_site': 0, 'monster': 1, 'shop': 2, 'treasure': 3, 'elite': 4, 'unknown': 5, 'ancient': 6, 'boss': 7}
        chosen = min(before['candidates'], key=lambda c: (priorities[c['kind']], c['candidate_index']))
        action = 'select:' + str(chosen['candidate_index'])
        self.post(maps._MAP_ACTION_ROUTE, before['decision_id'], action, maps._validate_action)
        until = min(self.clock() + 30, self.deadline)
        while self.clock() < until:
            body = self.exchange('GET', maps._MAP_DECISION_ROUTE)
            try:
                value = decode(body)
                if value.get('status') == 'complete':
                    result = maps._validate_complete(body)
                    require(result['destination'] == chosen, 'campaign_map_destination')
                    self.local_counts['reconciled'] += 1
                    return dict(status='resolved', attempted=1, accepted=1, reconciled=1)
                require(value.get('status') == 'waiting' or value.get('status') == 'ready' and maps._validate_ready(body) == before, 'campaign_map_transition')
            finally:
                body[:] = b'\0' * len(body)
            self.sleep(.1)
        raise Stop('campaign_map_timeout')

    def rest(self):
        pending = None
        counts = dict(attempted=0, accepted=0, reconciled=0)
        until = min(self.clock() + 30, self.deadline)
        ordinal = None
        while self.clock() < until:
            value = self.get(rooms._ROOM_DECISION_ROUTE, rooms._validate_room)
            require(value['status'] != 'unsupported', 'campaign_rest_unsupported')
            if value['status'] == 'waiting':
                self.sleep(.1); continue
            require(value['screen_kind'] == 'rest_site' and (ordinal is None or value['room_ordinal'] == ordinal), 'campaign_rest_identity')
            ordinal = value['room_ordinal']
            if pending:
                if value['decision_id'] == pending[0]:
                    self.sleep(.1); continue
                require(value['status'] != 'complete' or pending[1] == 'proceed', 'campaign_rest_transition')
                counts['reconciled'] += 1
                self.local_counts['reconciled'] += 1
                pending = None
                if value['status'] == 'complete':
                    return dict(status='resolved', **counts)
            require(value['status'] == 'ready' and counts['accepted'] < 2, 'campaign_rest_state')
            legal = {a['action_id'] for a in value['legal_actions']}
            action = next((c['action_id'] for c in value['candidates'] if c['kind'] == 'rest_heal' and c['action_id'] in legal), 'proceed')
            require(action in legal, 'campaign_rest_action')
            counts['attempted'] += 1
            self.post(rooms._ROOM_ACTION_ROUTE, value['decision_id'], action, rooms._validate_action_response)
            counts['accepted'] += 1
            pending = (value['decision_id'], action)
        raise Stop('campaign_rest_timeout')

    def proceed(self, view):
        action = view['legal_actions'][0]
        self.post(ACTION, view['decision_id'], action)
        until = min(self.clock() + 30, self.deadline)
        while self.clock() < until:
            after = self.view()
            if after['status'] == 'ready':
                require(after['completed_decision_id'] == view['decision_id'] and
                        after['act_index'] == view['act_index'] and after['floor'] == view['floor'], 'campaign_proceed_transition')
                if action == 'open_chest':
                    require(after['surface'] == 'treasure' and after['legal_actions'] == ['skip_relic'] and
                            after['decision_id'] != view['decision_id'], 'campaign_treasure_transition')
                else:
                    require(after['surface'] == 'map', 'campaign_proceed_transition')
                self.local_counts['reconciled'] += 1
                return dict(status='resolved', attempted=1, accepted=1, reconciled=1)
            self.sleep(.1)
        raise Stop('campaign_proceed_timeout')

    def run(self):
        outcome, code = None, None
        provider = event_policy(self.events)
        try:
            while True:
                self.check()
                view = self.view()
                if view['status'] == 'waiting':
                    self.sleep(.1); continue
                surface = view['surface']
                self.begin_stage(surface)
                if surface == 'map':
                    self.record(surface, self.map())
                elif surface == 'rest':
                    self.record(surface, self.rest())
                elif surface == 'treasure':
                    self.record(surface, self.proceed(view))
                elif surface == 'shop':
                    result = (self.proceed(view) if view['decision_id'] is not None else
                        self.shop.run_flow('shop', self.item_request, item_host=self.items, max_purchases=0, clock=self.clock, sleep=self.sleep))
                    self.record(surface, result)
                elif surface == 'rewards':
                    self.record(surface, self.rewards.run_rewards(self.exchange, policy='skip-card', potion_policy='skip-full', campaign=True, clock=self.clock, sleep=self.sleep))
                elif surface in ('combat', 'event'):
                    result = (self.combat.run_combat(self.exchange, campaign=True, campaign_potions=True, clock=self.clock, sleep=self.sleep) if surface == 'combat' else
                              self.events.run_event(self.exchange, provider=provider, clock=self.clock, sleep=self.sleep))
                    self.record(surface, result)
                    if surface == 'combat':
                        if result['outcome'] == 'defeat':
                            outcome = 'defeat'; break
                        require(result['outcome'] == 'victory', 'campaign_combat_outcome')
                        if view['room_kind'] == 'boss':
                            self.bosses.add(self.act)
                    elif result.get('destination') == 'run_won':
                        if self.entry_mode == 'fresh':
                            require(self.acts == self.bosses == {0, 1, 2}, 'campaign_victory_coverage')
                            outcome = 'victory'
                        else:
                            require(self.act == 2, 'campaign_ending_context')
                            outcome = 'continued_victory'
                        break
                    elif result.get('destination') == 'combat_resume_handoff':
                        self.begin_stage('event_combat')
                        fight = self.combat.run_combat(self.exchange, campaign=True, campaign_potions=True, event_resume_nonce=result['session_nonce'], resume_potion_policy='skip-full', clock=self.clock, sleep=self.sleep)
                        self.record('event_combat', fight)
                        require(fight['outcome'] == 'event_resumed', 'campaign_event_resume')
                    elif result.get('destination') == 'combat_handoff':
                        self.begin_stage('event_combat')
                        fight = self.combat.run_combat(self.exchange, campaign=True, campaign_potions=True, clock=self.clock, sleep=self.sleep)
                        self.record('event_combat', fight)
                        if fight['outcome'] == 'defeat':
                            outcome = 'defeat'; break
                        require(fight['outcome'] == 'victory', 'campaign_combat_outcome')
                    else:
                        require(result.get('destination') == 'map_handoff', 'campaign_event_destination')
                else:
                    raise Stop('campaign_surface_unsupported')
        except Stop as error:
            code = str(error)
        except KeyboardInterrupt:
            code = 'interrupted'
        except Exception:
            code = 'campaign_failure'
        if not self.stage_recorded:
            # Preserve known local receipts if a later reconciliation read fails.
            self.stages.append(dict(index=len(self.stages), act_index=self.act, floor=self.floor,
                surface=self.surface, status='failed', code=code, **self.local_counts))
        return dict(schema_version=1, status='resolved' if outcome else 'failed', code=code,
                    policy=POLICY, setup=self.setup, entry_mode=self.entry_mode, entry=self.entry, outcome=outcome,
                    full_campaign_verified=outcome == 'victory',
                    acts_observed=sorted(self.acts), bosses_defeated=sorted(self.bosses), stages=self.stages,
                    attempted=self.posts, reads=self.reads, elapsed_seconds=round(self.clock()-self.start, 3))


def run_campaign(request, item_exchange, *, combat, rewards, events, shop, items,
                 setup, entry_mode='fresh', progress=None, clock=time.monotonic, sleep=time.sleep):
    return Campaign(request, item_exchange, combat=combat, rewards=rewards, events=events,
                    shop=shop, items=items, setup=setup, entry_mode=entry_mode, progress=progress, clock=clock, sleep=sleep).run()
