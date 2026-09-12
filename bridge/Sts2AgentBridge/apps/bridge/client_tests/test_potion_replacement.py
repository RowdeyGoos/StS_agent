"""Schema 4 replacement is two separately reconciled mutations."""
import copy
import json
import unittest
from test_potion_policy import PotionPolicyWire
import test_potion_policy
from test_reward_host import encode, host


class ReplacementWire(PotionPolicyWire):
    def __init__(self, size=2):
        self.belt=['OLD_'+str(i) for i in range(size)]
        self.original=list(self.belt)
        super().__init__(free=0)
        self.state['schema_version']=4
        self.state['potion_slots']=list(self.belt)

    def actions(self):
        self.free=self.belt.count(None)
        super().actions()
        if not self.free and any(r['kind']=='potion' for r in self.state['rewards']):
            self.state['legal_actions'][-1:-1]=[
                dict(action_id='discard:'+str(i),kind='discard_potion',reward_slot=None,card_slot=None,potion_slot=i)
                for i,p in enumerate(self.belt) if p==self.original[i]]
        for a in self.state['legal_actions']:a.setdefault('potion_slot',None)
        self.state['potion_slots']=list(self.belt)

    def request(self,method,route,body=None):
        action=None
        if method=='POST':
            request=json.loads(body)
            action=next(a for a in self.state['legal_actions'] if a['action_id']==request['action_id'])
            if action['kind']=='discard_potion':
                self.posts.append(request['action_id']);self.buffers.append(body)
                assert request['decision_id']==self.state['decision_id']
                self.belt[action['potion_slot']]=None;self.revision+=1
                self.state['decision_id']=format(self.revision,'064x');self.state['decision_revision']=self.revision
                self.actions()
                response=self.corrupt(dict(schema_version=1,status='accepted',mutation_state='applied',**request,reason='accepted'),method)
                if isinstance(response,BaseException):raise response
                result=encode(response);self.buffers.append(result);return result
            if action['kind']=='collect_item':
                row=self.state['rewards'][action['reward_slot']]
                if row['kind']=='potion':self.belt[self.belt.index(None)]=row['item_key']
        result=super().request(method,route,body)
        if action and action['kind']=='open_card':
            for a in self.state['legal_actions']:a['potion_slot']=None
        return result


class ReplacementTests(unittest.TestCase):
    run_wire = test_potion_policy.PotionPolicyTests.run_wire
    def test_replace_two_and_protect_collected_potions(self):
        for card in ('first-card','skip-card'):
            wire=ReplacementWire();result=self.run_wire(wire,'replace-first',card)
            self.assertEqual(result['status'],'resolved',result)
            self.assertEqual(result['discarded_potions'],[dict(slot=i,key='OLD_'+str(i)) for i in range(2)])
            self.assertEqual(wire.belt,['POTION','POTION'])
            self.assertEqual(len(result['collected_items']),3)
            self.assertEqual(result['skipped_potions'],[])
            self.assertEqual((result['attempted'],result['accepted'],result['reconciled']),(9,9,9))

    def test_no_eligible_original_stops_without_discarding_new_potion(self):
        wire=ReplacementWire(1);result=self.run_wire(wire,'replace-first')
        self.assertEqual(result['code'],'potion_replacement_unavailable',result)
        self.assertEqual(result['discarded_potions'],[dict(slot=0,key='OLD_0')])
        self.assertEqual(wire.posts.count('discard:0'),1)
        self.assertNotIn('proceed',wire.posts)

    def test_existing_policies_ignore_discard_actions(self):
        for policy in ('stop-on-full','skip-full','skip-all'):
            wire=ReplacementWire();result=self.run_wire(wire,policy)
            self.assertEqual(result['status'],'failed' if policy=='stop-on-full' else 'resolved',result)
            self.assertFalse(any(a.startswith('discard:') for a in wire.posts))

    def test_wrong_inventory_stops_after_one_discard(self):
        for mode in ('unchanged','other_slot','extra_remove','new_key','downgrade','reward_change'):
            wire=ReplacementWire()
            def corrupt(value,method):
                if method=='GET' and wire.posts and wire.posts[-1].startswith('discard:'):
                    if mode=='unchanged':value['potion_slots']=['OLD_0','OLD_1']
                    if mode=='other_slot':value['potion_slots']=['OLD_0',None]
                    if mode=='extra_remove':value['potion_slots']=[None,None]
                    if mode=='new_key':value['potion_slots']=[None,'OTHER']
                    if mode=='reward_change':value['rewards'][1]['item_key']='OTHER'
                    if mode=='downgrade':
                        value['schema_version']=3;value.pop('potion_slots')
                        for a in value['legal_actions']:a.pop('potion_slot')
                return value
            wire.corrupt=corrupt;result=self.run_wire(wire,'replace-first')
            self.assertEqual(result['status'],'failed',(mode,result))
            self.assertEqual(result['discarded_potions'],[])
            self.assertEqual(sum(a.startswith('discard:') for a in wire.posts),1)

    def test_discard_receipt_loss_and_later_collect_loss_are_separate(self):
        for loss in ('discard','collect'):
            wire=ReplacementWire()
            def corrupt(value,method):
                if method=='POST' and wire.posts and (wire.posts[-1].startswith('discard:') if loss=='discard' else 'discard:0' in wire.posts and wire.posts[-1].startswith('collect:')):
                    return OSError('lost response')
                return value
            wire.corrupt=corrupt;result=self.run_wire(wire,'replace-first')
            self.assertEqual(result['status'],'failed',result)
            self.assertEqual(len(result['discarded_potions']),0 if loss=='discard' else 1)
            self.assertEqual(sum(a.startswith('discard:') for a in wire.posts),1)

    def test_malformed_schema4_inventory_and_actions(self):
        for mode in ('large','invalid_key','slot_bound','bool_slot','duplicate','free_discard','missing_slot'):
            wire=ReplacementWire();state=copy.deepcopy(wire.state)
            action=next(a for a in state['legal_actions'] if a['kind']=='discard_potion')
            if mode=='large':state['potion_slots']*=5
            if mode=='invalid_key':state['potion_slots'][0]='private value'
            if mode=='slot_bound':action.update(potion_slot=7,action_id='discard:7')
            if mode=='bool_slot':action['potion_slot']=False
            if mode=='duplicate':state['legal_actions'].insert(-1,copy.deepcopy(action))
            if mode=='free_discard':state['potion_slots'][0]=None
            if mode=='missing_slot':action.pop('potion_slot')
            with self.assertRaises(Exception):host.codec._validate_ready(encode(state))

if __name__=='__main__':unittest.main()
