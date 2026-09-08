"""Independent item envelopes: exact frozen parser and generic lineage/accounting."""
import copy
import unittest
from test_generic_event_host import host, Script, run, parent, env, receipt, prior, N


def item_payload(status='ready', kind='relic', index=7):
    item=host._load_item()
    slots=['BASE',None]
    offer=dict(index=index,kind=kind,key='ITEM',enabled=True)
    decision=item._decision_digest(N,(item._Offer(index,kind,'ITEM',True),),tuple(slots),(f'collect:{index}',))
    p=dict(schema_version=1,protocol='item_probe_v1',version='item_v1',session_nonce=N,surface_ordinal=1,status=status)
    if status=='ready':p.update(decision_id=decision,offers=[offer],potion_slots=slots,legal_actions=[f'collect:{index}'])
    elif status=='accepted':p.update(decision_id=decision,action_id=f'collect:{index}')
    elif status=='resolved':p.update(decision_id=decision,action_id=f'collect:{index}',offer_index=index,kind=kind,key='ITEM',result='collected')
    return p


def items(count=1,kind='relic',index=7):
    rows=[];history=[]
    def p(status='ready',i=0,attempted=0,accepted=0,done=0,decision=None,proceed=False):
        value=parent(status,decision=decision or '%064x'%(100+i),history=copy.deepcopy(history),
                     pa=attempted,pr=len(history),ce=i,ca=accepted,cr=done,proceed=proceed)
        value['completed_card_children']=0;value['completed_item_children']=len([r for r in history if r['result']=='child_completed'])
        if status=='ready' and not proceed:value['candidates'][0]['stable_id']=f'UNKNOWN_PAGE_{i}'
        return value
    for i in range(count):
        pd='%064x'%(100+i)
        child=dict(ordinal=i+1,parent_decision_id=pd,parent_action_id='choose:0',kind='item',contract_version='item_v1',offer_count=1)
        rows.extend([('GET',env(parent=p(i=i,attempted=i,accepted=i,done=i,decision=pd))),('POST',receipt(pd)),
                     ('GET',env(parent=p('child',i+1,i+1,i,i),child=child,payload=item_payload(kind=kind,index=index))),
                     ('POST',env('action',child=child,payload=item_payload('accepted',kind,index))),
                     ('GET',env(parent=p('child',i+1,i+1,i+1,i),child=child,payload=item_payload('resolved',kind,index)))])
        history.append(prior(pd,'child_completed'))
    final='%064x'%999
    rows.extend([('GET',env(parent=p(i=count,attempted=count,accepted=count,done=count,decision=final,proceed=True))),
                 ('POST',receipt(final))])
    history.append(prior(final,'map_handoff'))
    rows.append(('GET',env(parent=p('complete',count,count+1,count,count))))
    return rows


class ItemHostTests(unittest.TestCase):
    def test_potion_relic_and_sparse_reward_index(self):
        for kind in ('potion','relic'):
            for index in (0,7,255):
                script=Script(items(kind=kind,index=index));seen=[]
                result=run(script,provider=lambda view:(seen.append(view.kind),host.first_legal(view))[1])
                self.assertEqual(result['status'],'resolved',result)
                self.assertEqual((result['completed_card_children'],result['completed_item_children'],result['child_reconciled']),(0,1,1))
                self.assertEqual(seen,['parent','item','parent'])
                self.assertTrue(all(not any(b) for b in script.buffers))
    def test_identical_relic_hash_in_four_distinct_children(self):
        rows=items(4);self.assertEqual(rows[2][1]['payload']['decision_id'],rows[7][1]['payload']['decision_id'])
        script=Script(rows);result=run(script)
        self.assertEqual(result['status'],'resolved',result)
        self.assertEqual((result['completed_item_children'],result['child_attempted'],result['child_reconciled']),(4,4,4))
    def test_wrong_descriptor_family_count_or_extra_card_field(self):
        for key,value in [('kind','card_selection'),('contract_version','card_selection_v1'),('offer_count',True),('offer_count',2),('operation','add')]:
            rows=items();rows[2][1]['child'][key]=value;script=Script(rows);result=run(script)
            self.assertEqual(result['code'],'invalid_response');self.assertEqual(result['child_attempted'],0)
    def test_item_payload_versions_all_phases(self):
        for index in (2,3,4):
            for key,value in [('version','card_selection_v1'),('protocol','card_transform_v2'),('surface_ordinal',2),('session_nonce','b'*32)]:
                rows=items();rows[index][1]['payload'][key]=value;script=Script(rows);result=run(script)
                self.assertEqual(result['code'],'invalid_response');self.assertEqual(len(script.calls),index+1)
                self.assertEqual(result['completed_item_children'],0)
    def test_terminal_offer_must_match_receipt_and_shape(self):
        for key,value in [('offer_index',8),('key','OTHER'),('kind','potion'),('result','accepted'),('action_id','collect:8'),('decision_id','f'*64)]:
            rows=items();rows[4][1]['payload'][key]=value;script=Script(rows);result=run(script)
            self.assertEqual(result['code'],'invalid_response');self.assertEqual(result['completed_item_children'],0)
    def test_ready_shape_and_legal_action_strict(self):
        for mutate in (lambda p:p['offers'].append(dict(p['offers'][0],index=8)),
                       lambda p:p['legal_actions'].append('collect:7'),
                       lambda p:p['legal_actions'].__setitem__(0,'collect:07'),
                       lambda p:p['potion_slots'].__setitem__(1,'FULL'),
                       lambda p:p['offers'][0].__setitem__('enabled',False)):
            rows=items(kind='potion');mutate(rows[2][1]['payload']);script=Script(rows);result=run(script)
            self.assertEqual(result['code'],'invalid_response');self.assertEqual(result['child_attempted'],0)
    def test_old_item_lineage_replay_stops_second_dispatch(self):
        rows=items(2);rows[7][1]['child']=rows[2][1]['child'];script=Script(rows);result=run(script)
        self.assertEqual(result['code'],'invalid_response');self.assertEqual(result['child_attempted'],1)
    def test_uncertain_and_lost_response_no_retry(self):
        for lost in (False,True):
            rows=items();rows[3]=('POST',host.TransportFailure() if lost else env('action',child=rows[2][1]['child'],payload=item_payload('uncertain')))
            script=Script(rows);result=run(script)
            self.assertEqual(result['code'],'transport_failure' if lost else 'uncertain_action')
            self.assertEqual((result['child_attempted'],result['child_accepted'],result['completed_item_children']),(1,0,0))
            self.assertEqual(len(script.calls),4)
    def test_waiting_and_lost_terminal_keep_uncertain_effect_uncredited(self):
        rows=items();rows.insert(4,('GET',env(parent=copy.deepcopy(rows[4][1]['parent']),child=rows[4][1]['child'],payload=item_payload('waiting'))))
        self.assertEqual(run(Script(rows))['status'],'resolved')
        rows[5]=('GET',host.TransportFailure());result=run(Script(rows))
        self.assertEqual((result['child_accepted'],result['child_reconciled'],result['completed_item_children']),(1,0,0))
    def test_counter_lag_bounds_and_family_reclassification(self):
        for index,key,value in [(0,'completed_item_children',1),(4,'completed_item_children',1),(5,'completed_item_children',0),(5,'completed_card_children',1),(0,'completed_item_children',True),(0,'completed_item_children',5)]:
            rows=items();rows[index][1]['parent'][key]=value;result=run(Script(rows))
            self.assertEqual(result['code'],'invalid_response')
            self.assertEqual(result['completed_item_children'],1 if index==5 else 0)
    def test_later_unsupported_retains_completed_item_and_effect_label(self):
        rows=items();p=rows[5][1]['parent'];p.update(status='unsupported',phase='unsupported',decision_id='',candidates=[],legal_actions=[],effects='item_effect_verified')
        result=run(Script(rows));self.assertEqual(result['code'],'unsupported_state')
        self.assertEqual(result['completed_item_children'],1)
    def test_cleanup_failure_allowed_latest_missing_history_only(self):
        rows=items();p=rows[5][1]['parent'];p.update(status='unsupported',phase='unsupported',decision_id='',candidates=[],legal_actions=[],prior_results=[],parent_reconciled=0)
        result=run(Script(rows));self.assertEqual(result['code'],'unsupported_state');self.assertEqual(result['completed_item_children'],1)
    def test_repeated_terminal_does_not_credit_twice(self):
        rows=items();r=copy.deepcopy(rows[4]);r[1]['parent']['completed_item_children']=1;r[1]['parent']['child_reconciled']=1
        rows.insert(5,r);result=run(Script(rows));self.assertEqual(result['code'],'invalid_response');self.assertEqual(result['completed_item_children'],1)
    def test_verified_effect_kind_and_latest_parent_owner(self):
        for index,label in [(0,'item_effect_verified'),(5,'card_effect_verified'),(7,'item_effect_verified')]:
            rows=items();rows[index][1]['parent']['effects']=label
            self.assertEqual(run(Script(rows))['code'],'invalid_response')
        from test_generic_event_host import upgrade
        rows=upgrade();rows[7][1]['parent']['effects']='item_effect_verified'
        self.assertEqual(run(Script(rows))['code'],'invalid_response')

    def test_empty_summary_has_both_zero_counters(self):
        result=host.run_event(lambda *args:None,provider=None)
        self.assertEqual((result['completed_item_children'],result['completed_card_children']),(0,0))
