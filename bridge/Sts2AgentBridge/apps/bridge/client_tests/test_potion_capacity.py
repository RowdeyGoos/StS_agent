"""Capacity-grant pickup frees slots before a blocked potion or replacement."""
import copy
import json
import unittest
from test_potion_replacement import ReplacementWire
import test_potion_policy
from test_reward_host import host, encode


class CapacityWire(ReplacementWire):
    def __init__(self,size=3):
        super().__init__(size)
        self.state['schema_version']=5
        for row in self.state['rewards']:
            row['potion_capacity_gain']=2 if row['kind']=='relic' else 0
            if row['kind']=='relic':row['item_key']='POTION_BELT'
        self.actions()

    def request(self,method,route,body=None):
        if method=='POST':
            request=json.loads(body)
            action=next(a for a in self.state['legal_actions'] if a['action_id']==request['action_id'])
            if action['kind']=='collect_item':
                row=self.state['rewards'][action['reward_slot']]
                if row.get('potion_capacity_gain'):
                    self.belt += [None,None];self.original += [None,None]
        return super().request(method,route,body)


class CapacityTests(unittest.TestCase):
    run_wire=test_potion_policy.PotionPolicyTests.run_wire

    def test_belt_then_two_potions_with_every_policy(self):
        for policy in ('stop-on-full','skip-full','skip-all','replace-first'):
            for card in ('first-card','skip-card'):
                wire=CapacityWire();result=self.run_wire(wire,policy,card)
                self.assertEqual(result['status'],'resolved',result)
                self.assertEqual(result['potion_capacity_gains'],[dict(key='POTION_BELT',reward_index=4,before=3,after=5)])
                self.assertEqual(result['discarded_potions'],[])
                self.assertFalse(any(a.startswith('discard:') for a in wire.posts))
                self.assertEqual(wire.belt,['OLD_0','OLD_1','OLD_2']+([None,None] if policy=='skip-all' else ['POTION','POTION']))
                self.assertEqual(result['collected_items'][0],dict(kind='relic',key='POTION_BELT',reward_index=4))
                self.assertEqual(len(result['skipped_potions']),2 if policy=='skip-all' else 0)

    def test_invalid_growth_stops_without_accounting_gain(self):
        for mode in ('none','one','three','filled','swapped','downgrade','changed_gain','player'):
            wire=CapacityWire()
            def corrupt(value,method):
                if method=='GET' and len(wire.posts)==2:
                    if mode=='none':value['potion_slots']=value['potion_slots'][:3]
                    if mode=='one':value['potion_slots'].pop()
                    if mode=='three':value['potion_slots'].append(None)
                    if mode=='filled':value['potion_slots'][-1]='OTHER'
                    if mode=='swapped':value['potion_slots'][0]='OTHER'
                    if mode=='player':value['player']['gold']+=1
                    if mode=='changed_gain':value['rewards'][0]['potion_capacity_gain']=2
                    if mode=='downgrade':
                        value['schema_version']=4
                        for r in value['rewards']:r.pop('potion_capacity_gain')
                return value
            wire.corrupt=corrupt;result=self.run_wire(wire)
            self.assertEqual(result['status'],'failed',(mode,result))
            self.assertEqual(result['potion_capacity_gains'],[])
            self.assertEqual(wire.posts,['claim:0','collect:3'])

    def test_lost_belt_or_later_potion_receipt_preserves_only_verified_gain(self):
        for after in (False,True):
            wire=CapacityWire()
            def corrupt(value,method):
                if method=='POST' and len(wire.posts)==(3 if after else 2):return OSError('lost')
                return value
            wire.corrupt=corrupt;result=self.run_wire(wire,'replace-first')
            self.assertEqual(result['status'],'failed',result)
            self.assertEqual(len(result['potion_capacity_gains']),1 if after else 0)
            self.assertEqual(result['discarded_potions'],[])
            self.assertEqual(len(wire.posts),3 if after else 2)

    def test_gain_bounds_type_and_identity(self):
        for mode in ('negative','three','bool','wrong_kind','wrong_key','missing'):
            state=copy.deepcopy(CapacityWire().state);row=state['rewards'][-1]
            if mode=='negative':row['potion_capacity_gain']=-2
            if mode=='three':row['potion_capacity_gain']=3
            if mode=='bool':row['potion_capacity_gain']=True
            if mode=='wrong_kind':row['kind']='potion'
            if mode=='wrong_key':row['item_key']='OTHER'
            if mode=='missing':row.pop('potion_capacity_gain')
            with self.assertRaises(Exception,msg=mode):host.codec._validate_ready(encode(state))

    def test_original_capacity_limit_does_not_authorize_growth(self):
        wire=CapacityWire(7)
        result=self.run_wire(wire,'stop-on-full')
        self.assertEqual(result['code'],'reward_response_mismatch',result)
        self.assertEqual(wire.posts,[])

if __name__=='__main__':unittest.main()
