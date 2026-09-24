"""Potion policy legality, exact completion, and interrupted accounting."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
sys.path[:0] = [str(Path(__file__).absolute().parents[1] / 'client'), str(Path(__file__).absolute().parents[3] / 'tools')]
import combat_host as host
from probe_live_fixtures import _FIXTURE_COMBAT
from test_combat_host import encoded

class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


def view(name='FIRE_POTION', actions=None):
    return dict(schema_version=1, protocol='combat_potions_v1', status='ready', decision_id='a'*64,
                combat_decision_id='0'*64, potions=[dict(slot=0, id=name, supported=True)],
                legal_actions=actions if actions is not None else ['use:0:0'])

class PotionTests(unittest.TestCase):
    def setUp(self): self.combat = json.loads(_FIXTURE_COMBAT)
    def test_damage_and_persistent_target(self):
        self.combat['enemies'].append(dict(index=1, id='THE_OBSCURA', hp=30, max_hp=300, block=0, intents=['attack']))
        self.assertEqual(host.potion_action(view(actions=['use:0:0','use:0:1']), self.combat), 'use:0:1')
    def test_public_conditions(self):
        for name in ('BLOOD_POTION','REGEN_POTION','ENERGY_POTION'):
            self.assertIsNone(host.potion_action(view(name,['use:0']), self.combat))
        self.combat['player'].update(hp=30, energy=0)
        for name in ('BLOOD_POTION','REGEN_POTION','ENERGY_POTION'):
            self.assertEqual(host.potion_action(view(name,['use:0']), self.combat), 'use:0')
    def test_malformed_and_unsupported(self):
        for change in (lambda v:v['legal_actions'].append('use:0:0'),lambda v:v['legal_actions'].append('use:1'),lambda v:v['potions'][0].update(supported=False)):
            v=view();change(v)
            with self.assertRaises(host.Stop):host.potion_action(v,self.combat)
        self.assertIsNone(host.potion_action(view('ATTACK_POTION',[]),self.combat))
        v=view(actions=['use:0:1']);v['combat_decision_id']='b'*64
        self.assertEqual(host.potion_action(v,self.combat),'refresh')
    def drive(self, mode):
        clock=Clock(); buffers=[]; posts=[]; reads=[]
        def request(method, route, body):
            if method=='POST':
                posts.append(json.loads(body));buffers.append(body)
                if mode=='lost_receipt':raise OSError()
                response=dict(schema_version=1,status='accepted',mutation_state='queued',decision_id='a'*64,action_id='use:0:0',reason='accepted')
                if mode=='stale':response.update(status='rejected',mutation_state='none',reason='stale_decision')
            else:
                reads.append(route)
                if mode=='lost_read':raise OSError()
                if len(reads)==1 and mode!='late':response=dict(schema_version=1,protocol='combat_potions_v1',status='waiting')
                else:
                    response=dict(schema_version=1,protocol='combat_potions_v1',status='resolved',decision_id='a'*64,action_id='use:0:0')
                    if mode=='wrong_id':response['decision_id']='b'*64
                    if mode=='late':clock.now=31
            result=encoded(response);buffers.append(result);return result
        result=host.use_potion(request,'a'*64,'use:0:0',deadline=60,clock=clock,sleep=clock.sleep)
        self.assertEqual(len(posts),1)
        self.assertTrue(all(not any(b) for b in buffers))
        return result
    def test_completion_counts(self):
        for mode,expected in [('ok',(1,1,1)),('lost_receipt',(1,0,0)),('lost_read',(1,1,0)),('wrong_id',(1,1,0)),('stale',(1,0,0)),('late',(1,1,1))]:
            with self.subTest(mode=mode):
                result=self.drive(mode)
                self.assertEqual(tuple(result[k] for k in ('attempted','accepted','reconciled')),expected)
                self.assertEqual(result['status'],'resolved' if mode=='ok' else 'stale' if mode=='stale' else 'failed')
    def test_potion_finisher_without_card_action(self):
        clock=Clock();pending=False;finished=False;posts=[]
        def request(method, route, body):
            nonlocal pending,finished
            if route==host.COMBAT_READ:
                if finished:
                    terminal=json.loads(_FIXTURE_COMBAT)
                    terminal.update(status='complete', actionable=False, decision_id=None, enemies=[], hand=[], legal_actions=[], outcome='victory')
                    return encoded(terminal)
                return bytearray(_FIXTURE_COMBAT)
            if route==host.POTION_READ:
                if pending:
                    finished=True
                    return encoded(dict(schema_version=1,protocol='combat_potions_v1',status='resolved',decision_id='a'*64,action_id='use:0:0'))
                return encoded(view())
            self.assertEqual(route,host.POTION_ACTION);posts.append(json.loads(body));pending=True
            return encoded(dict(schema_version=1,status='accepted',mutation_state='queued',**posts[-1],reason='accepted'))
        result=host.run_combat(request,campaign=True,campaign_potions=True,clock=clock,sleep=clock.sleep)
        self.assertEqual(result['status'],'resolved',result)
        self.assertEqual(result['accepted'],0)
        self.assertEqual(result['potions'][0]['reconciled'],1)
        self.assertEqual(len(posts),1)

if __name__=='__main__':unittest.main()
