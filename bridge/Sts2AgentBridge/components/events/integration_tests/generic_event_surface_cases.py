"""Result-capstone acknowledgment and inactive combat-layout native paths."""
from __future__ import annotations
import json
from typing import Any

def run_surface_cases(args: Any, host: Any, exchange_type: Any) -> int:
    checks=0
    def run(scenario,wrapper=None):
        ex=exchange_type(args.dotnet,args.native_fixture,scenario,native=True)
        request=ex.request if wrapper is None else lambda m,r,b:wrapper(ex,m,r,b)
        def choose(view):
            if scenario.startswith("AB_"):
                if view.kind=="abandon_confirmation":return "cancel" if scenario=="AB_CANCEL" else "confirm_abandon"
                if view.kind=="parent" and ex.telemetry[-1]["cancels"] and len(view.payload["legal_actions"])==2:return "choose:1"
            if scenario=='CS_SKIP' and view.kind=='crystal_sphere' and 'reward:skip_card' in view.payload['legal_actions']:return 'reward:skip_card'
            if scenario=='FM_LEAVE' and view.kind=='parent':
                for option in view.payload['candidates']:
                    if option['stable_id']=='FAKE_MERCHANT.CLOSE':return option['action_id']
            return host.first_legal(view)
        try:result=host.run_event(request,provider=choose,clock=lambda:1.,sleep=lambda _:None)
        finally:ex.close()
        return result,ex
    result,ex=run('INCREMENTAL')
    assert not ex.cleanup_failed and result['status']=='resolved',result
    assert all(v['kind']=='decision' and v['parent']['status']=='waiting' for v in ex.envelopes[:32])
    assert ex.envelopes[32]['parent']['status']=='ready'
    assert result['parent_attempted']==result['parent_accepted']==result['parent_reconciled']==2,result
    checks+=1
    for scenario in ('AB_CANCEL','AB_CONFIRM','AB_DELAY','AB_FAULT','AB_STALE'):
        result,ex=run(scenario);end=ex.telemetry[-1]
        if scenario in ('AB_FAULT','AB_STALE'):
            assert result['status']=='failed' and result['parent_reconciled']==0 and not end['map_open'],(scenario,result)
            assert end['abandons']==int(scenario=='AB_FAULT')
        else:
            assert not ex.cleanup_failed and result['status']=='resolved' and result['child_reconciled']==1,(scenario,result,ex.envelopes[-1])
            assert result['destination']==('map_handoff' if scenario=='AB_CANCEL' else 'run_abandoned')
            assert result['parent_reconciled']==(3 if scenario=='AB_CANCEL' else 1)
            assert result['completed_card_children']==result['completed_item_children']==0 and result['effects']=='unverified'
            assert not end['modal_open'] and end['abandons']==int(scenario!='AB_CANCEL') and end['cancels']==int(scenario=='AB_CANCEL')
            assert end['map_open']==(scenario=='AB_CANCEL')
        checks+=1
    for change in ('lost_receipt','consequence','actions','result','parent_terminal'):
        changed=False
        def corrupt_abandon(ex,m,r,b):
            nonlocal changed
            response=ex.request(m,r,b);v=json.loads(response);p=v['payload'];c=v['child']
            if not changed:
                if change=='lost_receipt' and c and m=='POST':
                    changed=True;response[:]=b'\0'*len(response);raise host.TransportFailure()
                if c and m=='GET' and p['status']=='ready' and change in ('consequence','actions'):
                    p['consequence']='map_handoff' if change=='consequence' else p['consequence']
                    if change=='actions':p['legal_actions']=['confirm_abandon','cancel']
                    changed=True
                if c and m=='GET' and p['status']=='resolved' and change=='result':
                    p['prior_results'][0]['result']='cancelled';p['phase']='cancelled';changed=True
                if not c and m=='GET' and v['parent']['status']=='ready' and change=='parent_terminal':
                    v['parent']['status']='complete';v['parent']['phase']='run_abandoned';changed=True
            if changed:
                response[:]=b'\0'*len(response);response=bytearray(json.dumps(v,separators=(',',':')).encode());ex.buffers.append(response)
            return response
        result,ex=run('AB_CONFIRM',corrupt_abandon)
        assert changed and result['code']==('transport_failure' if change=='lost_receipt' else 'invalid_response'),(change,result)
        assert ex.telemetry[-1]['abandons']<=1
        checks+=1
    result,ex=run('FINISHED_TRAVEL')
    assert not ex.cleanup_failed and result['status']=='resolved',result
    assert result['parent_attempted']==result['parent_accepted']==result['parent_reconciled']==1,result
    assert ex.telemetry[-1]['map_open'],ex.telemetry[-1]
    checks+=1
    for scenario in ('CS_EMPTY','CS_MIXED','CS_SKIP','CS_DELAY','CS_CURSE','CS_FREED'):
        result,ex=run(scenario)
        assert not ex.cleanup_failed and result['status']=='resolved' and result['parent_reconciled']==2,(scenario,result,ex.envelopes[-1])
        end=ex.telemetry[-1]
        assert end['map_open'] and end['reveals']==10 and end['leaves']==1 and end['tools']==1,(scenario,end)
        assert end['skips']==(1 if scenario=='CS_SKIP' else 0)
        if scenario=='CS_CURSE':assert end['deck'].count('DOUBT')==10
        children=[v for v in ex.envelopes if v['child'] and v['kind']=='decision']
        assert all(v['child']['contract_version']=='crystal_sphere_v1' for v in children)
        assert result['effects']=='unverified'
        checks+=1
    result,ex=run('CS_BAD')
    assert ex.cleanup_failed and result['status']=='failed' and ex.telemetry[-1]['purchases']==1 and not ex.telemetry[-1]['map_open'],result
    checks+=1
    for stage in ('reveal','purchase','leave'):
        lost=False
        def lose_sphere(ex,m,r,b):
            nonlocal lost
            response=ex.request(m,r,b);end=ex.telemetry[-1]
            if not lost and m=='POST' and (stage=='reveal' and end['reveals']==1 or stage=='purchase' and end['purchases']==1 or stage=='leave' and end['leaves']==1):
                lost=True;response[:]=b'\0'*len(response);raise host.TransportFailure()
            return response
        result,ex=run('CS_MIXED',lose_sphere)
        assert ex.cleanup_failed and lost and result['code']=='transport_failure',(stage,result)
        assert ex.telemetry[-1]['reveals']==(1 if stage=='reveal' else 10)
        checks+=1
    for scenario in ('FM_BUY','FM_POOR','FM_LEAVE','FM_DELAY'):
        result,ex=run(scenario)
        purchases=0 if scenario in ('FM_POOR','FM_LEAVE') else 6
        assert not ex.cleanup_failed and result['status']=='resolved' and result['parent_reconciled']==purchases+3,(scenario,result)
        end=ex.telemetry[-1]
        assert end['map_open'] and end['opens']==end['closes']==end['leaves']==1 and end['purchases']==purchases
        assert end['gold']==(0 if scenario=='FM_POOR' else 99-10*purchases) and len(end['relics'])==purchases
        checks+=1
    result,ex=run('FM_WRONG')
    assert ex.cleanup_failed and result['status']=='failed' and ex.telemetry[-1]['purchases']==1 and not ex.telemetry[-1]['map_open']
    checks+=1
    for stage in ('purchase','leave'):
        lost=False
        def lose_merchant(ex,m,r,b):
            nonlocal lost
            response=ex.request(m,r,b)
            if not lost and m=='POST' and (stage=='purchase' and ex.telemetry[-1]['purchases']==1 or stage=='leave' and ex.telemetry[-1]['leaves']==1):
                lost=True;response[:]=b'\0'*len(response);raise host.TransportFailure()
            return response
        result,ex=run('FM_BUY',lose_merchant)
        assert ex.cleanup_failed and lost and result['code']=='transport_failure'
        assert ex.telemetry[-1]['purchases']==(1 if stage=='purchase' else 6)
        checks+=1
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
