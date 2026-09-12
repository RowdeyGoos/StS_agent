"""Explicit potion policies leave only authorized offers at a verified map exit."""
import copy
import json
import unittest
from test_reward_host import encode, _parent, _player, host
from test_event_map import Clock, READY as MAP
from run_live import run_combat_map, run_event_combat_map


class PotionPolicyWire:
    def __init__(self, free=0):
        self.state=_parent()
        self.state['schema_version']=3
        self.state['rewards']=self.state['rewards'][:2]
        for row in self.state['rewards']:row['item_key']=None
        for index,kind in ((2,'potion'),(3,'potion'),(4,'relic')):
            self.state['rewards'].append(dict(reward_slot=index,reward_index=index,kind=kind,
                successfully_selected=False,gold_amount=None,cards=[],card_selection_can_skip=False,item_key=kind.upper()))
        self.free=free;self.posts=[];self.buffers=[];self.revision=0;self.parent=None
        self.corrupt=lambda value,method:value
        self.actions()

    def actions(self):
        actions=[]
        for slot,row in enumerate(self.state['rewards']):
            row['reward_slot']=slot
            kind=row['kind']
            if kind=='potion' and not self.free:continue
            action,prefix={'gold':('claim_gold','claim:'),'card':('open_card','open:'),
                'potion':('collect_item','collect:'),'relic':('collect_item','collect:')}[kind]
            actions.append(dict(action_id=prefix+str(slot),kind=action,reward_slot=slot,card_slot=None))
        actions.append(dict(action_id='proceed',kind='proceed',reward_slot=None,card_slot=None))
        self.state['legal_actions']=actions

    def request(self,method,route,body=None):
        if route.endswith('map-decision'):return encode(MAP)
        if method=='POST':
            request=json.loads(body);self.posts.append(request['action_id']);self.buffers.append(body)
            assert request['decision_id']==self.state['decision_id']
            action=next(a for a in self.state['legal_actions'] if a['action_id']==request['action_id'])
            response=dict(schema_version=1,status='accepted',mutation_state='applied',**request,reason='accepted')
            if action['kind']=='proceed':
                self.state=dict(schema_version=1,status='complete',decision_kind='reward',actionable=False,
                    decision_id=None,screen_kind='map',player=self.state['player'],rewards=[],legal_actions=[])
            elif action['kind']=='open_card':
                self.parent=copy.deepcopy(self.state)
                row=copy.deepcopy(self.state['rewards'][action['reward_slot']]);row['reward_slot']=0
                self.state['screen_kind']='card_reward';self.state['rewards']=[row]
                self.state['legal_actions']=[dict(action_id='choose:0',kind='choose_card',reward_slot=None,card_slot=0),
                    dict(action_id='skip_card',kind='skip_card',reward_slot=None,card_slot=None)]
            elif action['kind'] in ('choose_card','skip_card'):
                row=self.state['rewards'][0]
                self.state=self.parent;self.parent=None
                self.state['rewards']=[r for r in self.state['rewards'] if r['reward_index']!=row['reward_index']]
                if action['kind']=='choose_card':self.state['player']['deck_count']+=1
                self.actions()
            else:
                row=self.state['rewards'].pop(action['reward_slot'])
                if row['kind']=='gold':self.state['player']['gold']+=14
                if row['kind']=='potion':self.free-=1
                self.actions()
            self.revision+=1
            if self.state['status']=='ready':
                self.state['decision_id']=format(self.revision,'064x');self.state['decision_revision']=self.revision
        else:response=copy.deepcopy(self.state)
        value=self.corrupt(response,method)
        if isinstance(value,BaseException):raise value
        result=encode(value);self.buffers.append(result);return result


class PotionPolicyTests(unittest.TestCase):
    def run_wire(self,wire,policy='skip-full',card='first-card'):
        clock=Clock()
        result=host.run_rewards(wire.request,policy=card,potion_policy=policy,clock=clock,sleep=clock.sleep)
        self.assertTrue(all(not any(b) for b in wire.buffers))
        return result

    def test_mixed_rewards_and_both_card_policies(self):
        for policy in ('skip-full','skip-all'):
            for free in (0,1,2):
                for card in ('first-card','skip-card'):
                    wire=PotionPolicyWire(free);result=self.run_wire(wire,policy,card)
                    self.assertEqual(result['status'],'resolved',result)
                    taken=free if policy=='skip-full' else 0
                    self.assertEqual(len(result['collected_items']),taken+1)
                    self.assertEqual(result['skipped_potions'],[dict(key='POTION',reward_index=i,
                        reason='inventory_full' if policy=='skip-full' else 'policy') for i in range(2+taken,4)])
                    self.assertEqual(result['claimed_gold'],14)
                    self.assertEqual(result['selected_cards'],['ANGER'] if card=='first-card' else [])
                    self.assertEqual((result['attempted'],result['accepted'],result['reconciled']),(5+taken,)*3)

    def test_default_stops_and_invalid_policy_never_reads(self):
        for free in (0,1):
            result=self.run_wire(PotionPolicyWire(free),'stop-on-full')
            self.assertEqual(result['code'],'potion_inventory_full')
            self.assertEqual(result['skipped_potions'],[])
        wire=PotionPolicyWire();result=self.run_wire(wire,'unknown')
        self.assertEqual((result['code'],result['reads'],wire.posts),('potion_policy',0,[]))

    def test_skip_does_not_accept_unrequested_mutations_or_missing_offers(self):
        for mode in ('missing','changed','selected','relic_action'):
            wire=PotionPolicyWire()
            def corrupt(value,method):
                if method=='GET' and len(wire.posts)==1:
                    if mode=='missing':value['rewards'].pop(1)
                    if mode=='changed':value['rewards'][1]['item_key']='OTHER'
                    if mode=='selected':value['rewards'][1]['successfully_selected']=True
                    if mode=='relic_action':value['legal_actions']=[a for a in value['legal_actions'] if a['kind']!='collect_item']
                    for slot,row in enumerate(value['rewards']):row['reward_slot']=slot
                return value
            wire.corrupt=corrupt;result=self.run_wire(wire)
            self.assertEqual(result['status'],'failed',(mode,result))
            self.assertEqual(result['skipped_potions'],[])
            self.assertEqual(len(wire.posts),1)

    def test_proceed_loss_failure_and_wrong_effect_do_not_count_skips(self):
        for mode in ('receipt_lost','map_lost','player_change','waiting'):
            wire=PotionPolicyWire()
            def corrupt(value,method):
                if wire.posts and wire.posts[-1]=='proceed':
                    if mode=='receipt_lost' and method=='POST':return OSError('lost')
                    if mode=='map_lost' and method=='GET':return OSError('lost')
                    if mode=='player_change' and method=='GET':value['player']['gold']+=1
                    if mode=='waiting' and method=='GET':return json.loads(host.codec._REWARD_WAITING)
                return value
            wire.corrupt=corrupt;result=self.run_wire(wire)
            self.assertEqual(result['status'],'failed',result)
            self.assertEqual(result['skipped_potions'],[])
            self.assertEqual(wire.posts.count('proceed'),1)
            self.assertEqual(result['claimed_gold'],14)
            self.assertEqual(len(result['collected_items']),1)

    def test_event_combat_and_map_failure_preserve_policy_results(self):
        class Combat:
            first_select=None
            @staticmethod
            def run_combat(request,**kwargs):return dict(status='resolved',code=None,outcome='victory')
        class Events:
            first_legal=None
            @staticmethod
            def run_event(request,**kwargs):return dict(status='resolved',code=None,destination='combat_handoff')
        for bad_map in (False,True):
            wire=PotionPolicyWire();clock=Clock()
            def request(method,route,body=None):
                if bad_map and route.endswith('map-decision'):raise OSError('map failed')
                return wire.request(method,route,body)
            result=run_event_combat_map(request,Events,Combat,host,potion_policy='skip-full',clock=clock,sleep=clock.sleep)
            self.assertEqual(result['status'],'failed' if bad_map else 'resolved',result)
            self.assertEqual(len(result['combat_flow']['rewards']['skipped_potions']),2)


if __name__=='__main__':unittest.main()
