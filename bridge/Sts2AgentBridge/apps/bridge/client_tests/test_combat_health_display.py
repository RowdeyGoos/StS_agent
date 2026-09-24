"""Visible infinity, finite compatibility, and exact phase/terminal accounting."""
from copy import deepcopy
import json
import unittest
from test_combat_host import host, encoded, revive_decision
from test_combat_potions import Clock, view
from tool_common import ToolFailure


def infinite(identity='b', turn=5):
    value = revive_decision(down=False, identity=identity, round_number=turn)
    value['schema_version'] = 2
    value['enemies'] = [dict(index=0, id='WATERFALL_GIANT', hp_display='infinite', hp=None,
                            max_hp=None, block=0, intents=['stun'])]
    return value


class HealthDisplayTests(unittest.TestCase):
    def test_explicit_infinity_and_legacy_rejection(self):
        v = infinite()
        parsed = host.probe._validate_combat(memoryview(encoded(v)), allow_infinite_health=True)
        self.assertIsNone(parsed['enemies'][0]['hp'])
        self.assertEqual(parsed['recommendation']['action_id'], 'end_turn')
        with self.assertRaises(ToolFailure): host.probe._validate_combat(memoryview(encoded(v)))
        for mutate in (lambda x:x.update(schema_version=1), lambda x:x.update(schema_version=True),
                       lambda x:x['enemies'][0].update(hp=999999999),
                       lambda x:x['enemies'][0].update(max_hp=999999999),
                       lambda x:x['enemies'][0].update(hp_display='unknown'),
                       lambda x:x['enemies'][0].update(hp_display='numeric',hp=5,max_hp=10),
                       lambda x:x['enemies'][0].pop('hp_display')):
            bad=deepcopy(v);mutate(bad)
            with self.subTest(bad=bad), self.assertRaises(ToolFailure):
                host.probe._validate_combat(memoryview(encoded(bad)),allow_infinite_health=True)

    def test_mixed_health_targeting_and_potions(self):
        v=infinite();v['enemies'].append(dict(index=1,id='OTHER',hp_display='numeric',hp=30,max_hp=40,block=0,intents=[]))
        v['legal_actions'].insert(1,dict(action_id='play:0:1',kind='play_card',hand_index=0,target_index=1))
        parsed=host.probe._validate_combat(memoryview(encoded(v)),allow_infinite_health=True)
        self.assertEqual(parsed['recommendation']['action_id'],'play:0:1')
        pv=view(actions=['use:0:0','use:0:1']);pv['combat_decision_id']=v['decision_id']
        self.assertEqual(host.potion_action(pv,parsed),'use:0:1')
        for potion,actions in [('FIRE_POTION',['use:0:0']),('EXPLOSIVE_AMPOULE',['use:0']),('STRENGTH_POTION',['use:0'])]:
            pv=view(potion,actions);pv['combat_decision_id']=v['decision_id']
            self.assertIsNone(host.potion_action(pv,infinite()))

    def test_transition_and_terminal_outcomes(self):
        for defeat in (False,True):
            clock=Clock();posts=[];buffers=[]
            states=[revive_decision(down=False,identity='a'),infinite(),infinite('c',6)]
            terminal=deepcopy(states[-1]);terminal.update(status='complete',actionable=False,decision_id=None,hand=[],legal_actions=[],outcome='defeat' if defeat else 'victory')
            if defeat: terminal['player']['hp']=0
            else: terminal.update(schema_version=1,enemies=[])
            states.append(terminal)
            def request(method,route,body):
                if method=='POST':
                    self.assertEqual(route,host.COMBAT_ACTION)
                    command=json.loads(body);buffers.append(body);posts.append(command)
                    result=dict(schema_version=1,status='accepted',mutation_state='queued',**command,reason='accepted')
                elif route==host.POTION_READ:
                    state=states[len(posts)];result=dict(view(actions=[]),combat_decision_id=state['decision_id'])
                else:
                    self.assertEqual(route,host.COMBAT_READ);result=states[len(posts)]
                raw=encoded(result);buffers.append(raw);return raw
            result=host.run_combat(request,campaign=True,campaign_potions=True,clock=clock,sleep=clock.sleep)
            self.assertEqual(result['status'],'resolved',result)
            self.assertEqual(result['outcome'],'defeat' if defeat else 'victory')
            self.assertEqual((result['attempted'],result['accepted'],result['reconciled']),(3,3,3))
            self.assertEqual([p['action_id'] for p in posts],['play:0:0','end_turn','end_turn'])
            self.assertTrue(all(not any(b) for b in buffers))
            if defeat:
                with self.assertRaises(ToolFailure):host.probe._validate_combat_terminal(memoryview(encoded(terminal)))

    def test_old_sentinel_stops_without_retry_and_keeps_reason(self):
        posts=[]
        def request(method,route,body):
            if method=='POST':
                cmd=json.loads(body);posts.append(cmd)
                return encoded(dict(schema_version=1,status='accepted',mutation_state='queued',**cmd,reason='accepted'))
            v=revive_decision(down=False,identity='a' if not posts else 'b')
            if posts:v['enemies'][0].update(hp=999999999,max_hp=999999999)
            return encoded(v)
        result=host.run_combat(request,campaign=True)
        self.assertEqual((result['attempted'],result['accepted'],result['reconciled']),(1,1,0))
        self.assertEqual(result['code'],'invalid_response')
        self.assertEqual(result['validation_code'],'decision_enemies_mismatch')


if __name__=='__main__':unittest.main()
