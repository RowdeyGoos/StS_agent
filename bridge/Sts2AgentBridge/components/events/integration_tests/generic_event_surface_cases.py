"""Result-capstone acknowledgment and inactive combat-layout native paths."""
from __future__ import annotations
import json
from typing import Any

def run_surface_cases(args: Any, host: Any, exchange_type: Any) -> int:
    checks=0
    def run(scenario,wrapper=None):
        ex=exchange_type(args.dotnet,args.native_fixture,scenario,native=True)
        request=ex.request if wrapper is None else lambda m,r,b:wrapper(ex,m,r,b)
        try:result=host.run_event(request,provider=host.first_legal,clock=lambda:1.,sleep=lambda _:None)
        finally:ex.close()
        return result,ex
    for scenario in ('S_ONE','S_TEN','S_MAX','S_CREATION','S_COMPLETION','S_DEFERRED'):
        result,ex=run(scenario);count=1 if scenario=='S_ONE' else 64 if scenario=='S_MAX' else 10
        assert result['status']=='resolved' and result['child_reconciled']==result['child_accepted']==result['child_attempted']==1,(scenario,result,ex.envelopes[-1])
        assert result['completed_card_children']==1 and result['parent_reconciled']==4 and result['completed_item_children']==0
        assert ex.telemetry[-1]==dict(map_open=True,capstone_open=False,confirms=1,chosen_calls=2,deck=[f'Card_{count}']+[f'Final_{i}' for i in range(count)])
        children=[v for v in ex.envelopes if v['child'] and v['kind']=='decision']
        assert all(v['child']['kind']=='card_results' and v['child']['contract_version']=='card_results_v1' for v in children)
        assert children[-1]['payload']['prior_results'][0]['result']=='acknowledged'
        parents=[v['parent'] for v in ex.envelopes if v['kind']=='decision']
        assert all(p['effects'] in ('none_attempted','unverified') for p in parents)
        checks+=1
    for scenario in ('S_STALE','S_DECK','S_FOREIGN','S_FAULT'):
        result,ex=run(scenario);assert result['status']!='resolved' and result['completed_card_children']==0,(scenario,result)
        assert ex.telemetry[-1]['confirms']==int(scenario=='S_FAULT');checks+=1
    for scenario in ('I_COMBAT','I_COMBAT_STARTED','I_COMBAT_REPLACED'):
        result,ex=run(scenario)
        if scenario=='I_COMBAT':
            assert result['status']=='resolved' and result['completed_item_children']==1 and ex.telemetry[-1]['map_open'] and ex.telemetry[-1]['collect_calls']==1 and ex.telemetry[-1]['remaining_keys'][-1]=='INJURY',(scenario,result)
        else:assert result['status']!='resolved' and ex.telemetry[-1]['collect_calls']==0,(scenario,result)
        checks+=1
    for stage in ('confirm','resolved'):
        lost=False
        def lose(ex,m,r,b):
            nonlocal lost
            response=ex.request(m,r,b);v=json.loads(response)
            if not lost and v['child'] and (m=='POST' and stage=='confirm' or m=='GET' and v['payload']['status']==stage):
                lost=True;response[:]=b'\0'*len(response);raise host.TransportFailure()
            return response
        result,ex=run('S_TEN',lose);assert lost and result['code']=='transport_failure' and ex.telemetry[-1]['confirms']==1 and result['completed_card_children']==0;checks+=1
    for change in ('version','count','slot','key','level','empty','action','history','receipt','changed_result','unearned_effect'):
        changed=False
        def corrupt(ex,m,r,b):
            nonlocal changed
            response=ex.request(m,r,b);v=json.loads(response);p=v['payload'];c=v['child']
            if not changed:
                if change=='unearned_effect' and m=='GET' and c is None and v['parent']['completed_card_children']==1:
                    v['parent']['effects']='card_effect_verified';changed=True
                elif c and m=='POST' and change=='receipt':p['action_id']='choose:0';changed=True
                elif c and m=='GET' and p['status']=='resolved' and change=='changed_result':p['cards'][0]['key']='Wrong';changed=True
                elif c and m=='GET' and p['status']=='ready' and change not in ('unearned_effect','receipt','changed_result'):
                    if change=='version':c['contract_version']='card_offer_v1'
                    elif change=='count':c['offer_count']=65
                    elif change=='slot':p['cards'][0]['slot']=True
                    elif change=='key':p['cards'][0]['key']='bad key'
                    elif change=='level':p['cards'][0]['upgrade_level']=-1
                    elif change=='empty':p['cards']=[]
                    elif change=='action':p['legal_actions']=['choose:0']
                    elif change=='history':p['prior_results']=[dict(decision_id='a'*64,action_id='confirm',result='acknowledged')]
                    changed=True
            if changed:
                response[:]=b'\0'*len(response);response=bytearray(json.dumps(v,separators=(',',':')).encode());ex.buffers.append(response)
            return response
        result,ex=run('S_TEN',corrupt);assert changed and result['code']=='invalid_response',(change,result);checks+=1
    return checks
