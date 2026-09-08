"""Reward effects, loss accounting and combat-to-map stage boundaries."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).absolute().parents[3]
sys.path[:0] = [str(ROOT / 'apps/bridge/client'), str(ROOT / 'tools')]
import reward_host as host
from run_live import run_combat_map
from apply_reward_live_fixtures import _parent, _child, _player
from test_event_map import Clock, READY as MAP


def encode(value):
    return bytearray(json.dumps(value, separators=(',', ':')).encode())


class RewardWire:
    def __init__(self, *, skip=False):
        self.state = _parent()
        self.state['rewards'].pop()  # Gold and cards; unsupported items tested separately.
        self.stage = self.posts = 0
        self.skip = skip
        self.calls, self.buffers = [], []
        self.corrupt = lambda value, method: value
        self.stale = 0
        self.waits = 0

    def request(self, method, route, body=None):
        self.calls.append((method,route))
        if method == 'POST':
            self.posts += 1
            self.buffers.append(body)
            request = json.loads(body)
            action = ['claim:0','open:0','skip_card' if self.skip else 'choose:0','proceed'][self.stage]
            assert request == dict(decision_id=self.state['decision_id'],action_id=action), request
            response = dict(schema_version=1,status='accepted',mutation_state='applied',**request,reason='accepted')
            if self.stale:
                self.stale -= 1
                response.update(status='rejected',mutation_state='none',reason='stale_decision')
            else:
                self.stage += 1
                if self.stage == 1:
                    self.state['player']['gold'] += 14
                    self.state['rewards'].pop(0)  # Native visible slots may compact.
                    self.state['rewards'][0]['reward_slot'] = 0
                    self.state['legal_actions'] = [dict(action_id='open:0',kind='open_card',reward_slot=0,card_slot=None),
                                                  dict(action_id='proceed',kind='proceed',reward_slot=None,card_slot=None)]
                elif self.stage == 2:
                    self.state = _child(gold=113)
                elif self.stage == 3:
                    self.state = _parent(gold=113,deck_count=10 if self.skip else 11)
                    self.state['rewards'] = []
                    self.state['legal_actions'] = [self.state['legal_actions'][-1]]
                else:
                    self.state = dict(schema_version=1,status='complete',decision_kind='reward',actionable=False,
                                      decision_id=None,screen_kind='map',player=_player(113,10 if self.skip else 11),rewards=[],legal_actions=[])
                if self.stage < 4:
                    self.state['decision_revision'] = self.stage
                    self.state['decision_id'] = format(self.stage,'064x')
        elif self.waits:
            self.waits -= 1
            response = json.loads(host.codec._REWARD_WAITING)
        else:
            response = copy.deepcopy(self.state)
        value = self.corrupt(response,method)
        if isinstance(value,BaseException): raise value
        buffer = encode(value); self.buffers.append(buffer); return buffer


class RewardHostTests(unittest.TestCase):
    def run_wire(self, wire, policy='first-card'):
        clock = Clock()
        result = host.run_rewards(wire.request,policy=policy,clock=clock,sleep=clock.sleep)
        self.assertTrue(all(not any(b) for b in wire.buffers))
        return result

    def test_gold_card_and_skip_effects(self):
        for skip in (False,True):
            wire = RewardWire(skip=skip); wire.waits=2
            result = self.run_wire(wire,'skip-card' if skip else 'first-card')
            self.assertEqual(result['status'],'resolved',result)
            self.assertEqual((result['attempted'],result['accepted'],result['reconciled']), (4,4,4))
            self.assertEqual((result['claimed_gold'],result['selected_cards'],result['skipped_card_rewards']),
                             (14,[] if skip else ['ANGER'],1 if skip else 0))

    def test_known_stale_refresh_and_bounded_rejections(self):
        wire=RewardWire();wire.stale=1
        result=self.run_wire(wire)
        self.assertEqual((result['status'],result['attempted'],result['accepted'],result['reconciled'],result['stale_rejections']),
                         ('resolved',5,4,4,1))
        wire=RewardWire();wire.stale=10
        result=self.run_wire(wire)
        self.assertEqual((result['code'],result['attempted'],result['accepted']),('reward_stale_limit',9,0))

    def test_lost_rejected_and_malformed_receipts_never_retry(self):
        for failure in [OSError('lost'), KeyboardInterrupt(), dict(status='rejected'), {'schema_version':True}]:
            wire=RewardWire()
            wire.corrupt=lambda value,method: failure if method=='POST' else value
            result=self.run_wire(wire)
            self.assertEqual(result['status'],'failed')
            self.assertEqual((result['attempted'],result['accepted'],result['reconciled'],wire.posts),(1,0,0,1))
            self.assertEqual(result['claimed_gold'],0)

    def test_reconciliation_failure_keeps_only_verified_effects(self):
        for after_stage,key,replacement,expected in [(1,'gold',112,(1,1,0,0)),(3,'deck_count',10,(3,3,2,14))]:
            wire=RewardWire()
            def corrupt(value,method):
                if method=='GET' and wire.stage==after_stage: value['player'][key]=replacement
                return value
            wire.corrupt=corrupt
            result=self.run_wire(wire)
            self.assertEqual(result['status'],'failed')
            self.assertEqual(tuple(result[k] for k in ('attempted','accepted','reconciled','claimed_gold')),expected)
            self.assertEqual(result['selected_cards'],[])

    def test_unknown_rewards_missing_actions_and_changed_child_stop(self):
        wire=RewardWire();wire.state=_parent()
        result=self.run_wire(wire)
        self.assertEqual((result['code'],wire.posts),('unsupported_reward',0))
        wire=RewardWire();wire.state['legal_actions'].pop(0)
        self.assertEqual(self.run_wire(wire)['code'],'unresolved_reward');self.assertEqual(wire.posts,0)
        for key,value in [('reward_index',5),('cards',['BASH','ANGER'])]:
            wire=RewardWire()
            def corrupt(response,method):
                if method=='GET' and wire.stage==2: response['rewards'][0][key]=value
                return response
            wire.corrupt=corrupt
            result=self.run_wire(wire)
            self.assertEqual(result['code'],'reward_child_mismatch',result)
            self.assertEqual((result['accepted'],result['reconciled'],wire.posts),(2,1,2))

    def test_non_skippable_preflight_and_foreign_completed_state(self):
        wire=RewardWire();wire.state['rewards'][1]['card_selection_can_skip']=False
        result=self.run_wire(wire,'skip-card')
        self.assertEqual((result['code'],result['accepted'],result['reconciled']),('card_reward_not_skippable',1,1))
        wire=RewardWire()
        wire.state=dict(schema_version=1,status='complete',decision_kind='reward',actionable=False,decision_id=None,
                        screen_kind='map',player=_player(),rewards=[],legal_actions=[])
        self.assertEqual(self.run_wire(wire)['code'],'reward_already_complete');self.assertEqual(wire.posts,0)

    def test_waiting_and_late_receipt_are_bounded(self):
        wire=RewardWire();wire.waits=10000
        result=self.run_wire(wire)
        self.assertEqual((result['code'],result['reads'],wire.posts),('reward_read_limit',512,0))
        wire=RewardWire();clock=Clock()
        def request(method,route,body):
            result=wire.request(method,route,body)
            if method=='POST': clock.value+=46
            return result
        result=host.run_rewards(request,clock=clock,sleep=clock.sleep)
        self.assertEqual((result['code'],result['attempted'],result['accepted']),('reward_timeout',1,0))
        self.assertTrue(all(not any(b) for b in wire.buffers))

    def test_accepted_action_with_unchanged_observation_is_never_resent(self):
        for changed in (False,True):
            wire=RewardWire();initial=copy.deepcopy(wire.state)
            if changed: initial['player']['gold']+=1
            wire.corrupt=lambda value,method: initial if method=='GET' and wire.stage==1 else value
            result=self.run_wire(wire)
            self.assertEqual(result['code'],'reward_identity_reused' if changed else 'reward_read_limit')
            self.assertEqual((result['attempted'],result['accepted'],result['reconciled'],wire.posts),(1,1,0,1))

    def test_prior_claim_is_not_counted_and_uncollected_disappearance_stops(self):
        wire=RewardWire()
        wire.state['rewards'][0]['successfully_selected']=True
        wire.state['player']['gold']=113
        wire.state['legal_actions'].pop(0)
        # This is an already collected offer, not a claim by this controller.
        wire.state['rewards'].pop(0)
        wire.state['rewards'][0]['reward_slot']=0
        wire.state['legal_actions'][0]['action_id']='open:0'
        wire.state['legal_actions'][0]['reward_slot']=0
        wire.state['decision_revision']=1
        wire.state['decision_id']=format(1,'064x')
        wire.stage=1
        result=self.run_wire(wire)
        self.assertEqual((result['status'],result['claimed_gold'],result['accepted']),('resolved',0,3))
        wire=RewardWire()
        def corrupt(value,method):
            if method=='GET' and wire.stage==1:
                value['rewards']=[]
                value['legal_actions']=value['legal_actions'][-1:]
            return value
        wire.corrupt=corrupt
        result=self.run_wire(wire)
        self.assertEqual((result['code'],result['claimed_gold'],wire.posts),('reward_disappeared',14,1))


class CombatMapTests(unittest.TestCase):
    def test_stages_preserve_partial_results_and_do_not_advance_after_failure(self):
        for failure in [None,'combat','defeat','rewards','map']:
            wire=RewardWire();clock=Clock();calls=[]
            combat_result=dict(status='failed' if failure=='combat' else 'resolved',code='lost' if failure=='combat' else None,
                               outcome='defeat' if failure=='defeat' else 'victory',attempted=2,accepted=1,reconciled=1,
                               choices=[dict(status='resolved',accepted=1,reconciled=1)])
            class Combat:
                first_select=None
                @staticmethod
                def run_combat(request,**kwargs): return combat_result
            if failure=='rewards':
                wire.corrupt=lambda v,m: OSError('lost') if m=='POST' else v
            def request(method,route,body=None):
                calls.append(route)
                if route.endswith('map-decision'):
                    if failure=='map': raise OSError('lost map')
                    return encode(MAP)
                return wire.request(method,route,body)
            result=run_combat_map(request,Combat,host,clock=clock,sleep=clock.sleep)
            self.assertEqual(result['status'],'resolved' if failure is None else 'failed',result)
            self.assertIs(result['combat'],combat_result)
            if failure in ('combat','defeat'):
                self.assertEqual(calls,[]);self.assertEqual(result['rewards']['status'],'not_attempted')
            elif failure=='rewards':
                self.assertEqual(result['rewards']['attempted'],1)
                self.assertEqual(result['map_handoff']['status'],'not_attempted')
            else:
                self.assertEqual(result['rewards']['reconciled'],4)
                self.assertEqual(result['rewards']['claimed_gold'],14)


if __name__ == '__main__': unittest.main()
