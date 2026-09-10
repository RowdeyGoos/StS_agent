"""Resume reward validation, bounded inputs and retained partial evidence."""
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).absolute().parents[3]
sys.path[:0] = [str(ROOT/'apps/bridge/client'), str(ROOT/'components/item_wire/host')]
import combat_host as host
import item_host as codec

NONCE = 'a'*32

def common(status):
    return dict(schema_version=1, protocol='item_probe_v1', version='item_v1',
                session_nonce=NONCE, surface_ordinal=1, status=status)

class Wire:
    def __init__(self, count=1):
        self.count=count; self.index=0; self.pending=None; self.history=[]; self.posts=[]; self.buffers=[]
        self.corrupt=lambda value:value
        self.fail_post=False
    def ready(self):
        index=self.index if self.count>1 else 7
        offer=codec._Offer(index,'potion' if index%2==0 or self.count==1 else 'relic','ITEM_'+str(index),True)
        slots=(None, None); actions=('collect:'+str(index),)
        decision=codec._decision_digest(NONCE,(offer,),slots,actions)
        return dict(common('ready'),decision_id=decision,offers=[dict(index=index,kind=offer.kind,key=offer.key,enabled=True)],potion_slots=list(slots),legal_actions=list(actions))
    def request(self,method,route,body):
        if method=='POST':
            assert route==host.EVENT_ITEM_ACTION
            request=json.loads(body); self.buffers.append(body); self.posts.append(request)
            if self.fail_post: raise OSError('lost receipt')
            self.pending=self.ready()
            value=dict(common('accepted'),**request)
        else:
            assert route==host.EVENT_ITEM_READ
            if self.pending:
                ready=self.pending; offer=ready['offers'][0]
                self.history.append(dict(common('resolved'),decision_id=ready['decision_id'],action_id=ready['legal_actions'][0],
                    offer_index=offer['index'],kind=offer['kind'],key=offer['key'],result='collected'))
                self.index+=1; self.pending=None
            if self.count==1: value=self.history[-1] if self.history else self.ready()
            else: value=dict(version='item_set_v1',session_nonce=NONCE,status='resolved' if self.index==self.count else 'ready',
                offer_count=self.count,collected=json.loads(json.dumps(self.history)),current=None if self.index==self.count else self.ready())
        result=bytearray(json.dumps(self.corrupt(value),separators=(",",":")).encode());self.buffers.append(result);return result

class ResumeItemsTests(unittest.TestCase):
    def test_single_and_ordered_set(self):
        for count in [1,2,8]:
            wire=Wire(count)
            result=host.run_resume_items(wire.request,NONCE,sleep=lambda _:None)
            self.assertEqual((result['status'],result['attempted'],result['accepted'],result['reconciled']),('resolved',count,count,count),result)
            self.assertTrue(all(not any(b) for b in wire.buffers))
    def test_lost_receipt_no_retry(self):
        wire=Wire();wire.fail_post=True
        result=host.run_resume_items(wire.request,NONCE,sleep=lambda _:None)
        self.assertEqual((result['status'],result['attempted'],result['accepted'],len(wire.posts)),('failed',1,0,1),result)
        self.assertTrue(all(not any(b) for b in wire.buffers))
    def test_partial_history_is_retained_and_strictly_typed(self):
        for corrupt in ['boolean','wrong_key','nonce','shrink']:
            wire=Wire(3)
            def change(v):
                if v.get('version')=='item_set_v1' and wire.index==2:
                    if corrupt=='boolean': v['collected'][0]['offer_index']=False
                    if corrupt=='wrong_key': v['collected'][0]['key']='OTHER'
                    if corrupt=='nonce': v['session_nonce']='b'*32
                    if corrupt=='shrink': v['collected']=[]
                return v
            wire.corrupt=change
            result=host.run_resume_items(wire.request,NONCE,sleep=lambda _:None)
            self.assertEqual((result['status'],result['attempted'],result['accepted'],result['reconciled']),('failed',2,2,1),result)
    def test_malformed_ready_and_wrong_receipt(self):
        for mode in ['digest','full','wrong_receipt','unexpected_result']:
            wire=Wire()
            def corrupt(v):
                if v['status']=='ready':
                    if mode=='digest':v['decision_id']='b'*64
                    if mode=='full':v['potion_slots']=['FILLED','FILLED']
                    if mode=='unexpected_result':return dict(common('resolved'),decision_id='b'*64,action_id='collect:7',offer_index=7,kind='potion',key='ITEM_7',result='collected')
                if v['status']=='accepted' and mode=='wrong_receipt':v['session_nonce']='b'*32
                return v
            wire.corrupt=corrupt
            result=host.run_resume_items(wire.request,NONCE,sleep=lambda _:None)
            self.assertEqual(result['status'],'failed',result)
            self.assertEqual(len(wire.posts),1 if mode=='wrong_receipt' else 0)
    def test_parent_deadline_prevents_late_item_action(self):
        wire=Wire(2);now=[299.0]
        def request(*args):
            result=wire.request(*args);now[0]=301.0;return result
        result=host.run_resume_items(request,NONCE,parent_deadline=300,clock=lambda:now[0],sleep=lambda _:None)
        self.assertEqual((result['status'],result['attempted'],len(wire.posts)),('failed',0,0),result)
    def test_combat_resumption_services_items_once_and_keeps_failures(self):
        for fail in [False,True]:
            wire=Wire(2);wire.fail_post=fail
            def request(method,route,body):
                if route==host.EVENT_COMBAT_READ:
                    return bytearray(json.dumps(dict(schema_version=1,protocol='event_combat_v2',session_nonce=NONCE,status='resumed' if wire.index==2 else 'item')).encode())
                return wire.request(method,route,body)
            result=host.run_combat(request,event_resume_nonce=NONCE,sleep=lambda _:None)
            self.assertEqual(result['status'],'failed' if fail else 'resolved',result)
            self.assertEqual(len(result['resume_items']),1,result)
            self.assertEqual(result['resume_items'][0]['attempted'],1 if fail else 2)
            self.assertEqual(result['attempted'],0)

if __name__=='__main__':unittest.main()
