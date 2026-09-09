"""Native direct offers and bundle preview through the strict production host."""
from __future__ import annotations
import json
from typing import Any


def run_offer_cases(args: Any, host: Any, exchange_type: Any) -> int:
    checks=0
    def run(scenario, wrapper=None, slot=None):
        ex=exchange_type(args.dotnet,args.native_fixture,scenario,native=True)
        def choose(view):
            if view.kind=='card_offer' and view.payload['phase']=='choose':
                return 'choose:'+str(len(view.payload['offers'])-1 if slot is None else slot)
            return host.first_legal(view)
        request=ex.request if wrapper is None else lambda m,r,b:wrapper(ex,m,r,b)
        try:result=host.run_event(request,provider=choose,clock=lambda:1.,sleep=lambda _:None)
        finally:ex.close()
        return result,ex
    for scenario in ('O_CARD','O_BUNDLE','O_CARD_CREATION','O_BUNDLE_CREATION','O_CARD_CHOICE','O_BUNDLE_CHOICE','O_BUNDLE_CONFIRM','O_BUNDLE_PARTIAL','O_CARD_COMPLETION','O_BUNDLE_COMPLETION'):
        result,ex=run(scenario);bundle=not scenario.startswith('O_CARD');slot=4 if bundle else 2
        assert result['status']=='resolved',(scenario,result,ex.envelopes[-1])
        assert result['child_attempted']==result['child_accepted']==result['child_reconciled']==(2 if bundle else 1)
        assert result['completed_card_children']==result['child_episodes']==1 and result['completed_item_children']==0
        assert result['parent_reconciled']==result['parent_accepted']==4
        assert ex.telemetry[-1]==dict(map_open=True,overlay_count=0,choices=1,confirms=int(bundle),selected=slot,deck=['Card_0','Card_1','Card_2']+[f'Offer_{slot}_{j}' for j in range(8 if bundle else 1)])
        checks+=1
    for scenario in ('O_CARD','O_BUNDLE'):
        for slot in range(3 if scenario=='O_CARD' else 5):
            result,ex=run(scenario,slot=slot);assert result['status']=='resolved' and ex.telemetry[-1]['selected']==slot;checks+=1
    for scenario in ('O_CARD_FAULT','O_BUNDLE_FAULT','O_CARD_WRONG','O_BUNDLE_WRONG','O_CARD_EXTRA','O_BUNDLE_EXTRA'):
        result,ex=run(scenario);assert result['code']=='unsupported_state' and result['completed_card_children']==0,(scenario,result);assert ex.telemetry[-1]['choices']==1;checks+=1
    for scenario,stage in (('O_CARD','choose'),('O_BUNDLE','choose'),('O_BUNDLE','confirm'),('O_BUNDLE','resolved')):
        lost=False
        def lose(ex,m,r,b):
            nonlocal lost
            response=ex.request(m,r,b);v=json.loads(response);p=v['payload']
            if not lost and v['child'] and ((m=='POST' and p['action_id'].startswith(stage)) or (m=='GET' and p['status']==stage)):
                lost=True;response[:]=b'\0'*len(response);raise host.TransportFailure()
            return response
        result,ex=run(scenario,lose);assert lost and result['code']=='transport_failure' and ex.telemetry[-1]['choices']<=1 and ex.telemetry[-1]['confirms']<=1;checks+=1
    for change in ('version','count','offer_index','slot','key','level','empty','extra_card','selected','actions','history','receipt','preview_domain','preview_history','resolved_domain','resolved_selected'):
        changed=False
        def corrupt(ex,m,r,b):
            nonlocal changed
            response=ex.request(m,r,b);v=json.loads(response);c,p=v['child'],v['payload']
            if not changed and c:
                if change=='receipt' and m=='POST':p['action_id']='choose:0';changed=True
                elif m=='GET' and p['status']=='ready' and p['phase']=='choose' and change not in ('receipt','preview_domain','preview_history','resolved_domain','resolved_selected'):
                    if change=='version':c['contract_version']='card_reward_v1'
                    elif change=='count':c['offer_count']=4
                    elif change=='offer_index':p['offers'][0]['index']=True
                    elif change=='slot':p['offers'][0]['cards'][0]['slot']=1
                    elif change=='key':p['offers'][0]['cards'][0]['key']='bad key'
                    elif change=='level':p['offers'][0]['cards'][0]['upgrade_level']=-1
                    elif change=='empty':p['offers'][0]['cards']=[]
                    elif change=='extra_card':p['offers'][0]['cards'].append(dict(p['offers'][0]['cards'][0]))
                    elif change=='selected':p['selected_index']=0
                    elif change=='actions':p['legal_actions']=['confirm']
                    elif change=='history':p['prior_results']=[dict(decision_id='a'*64,action_id='choose:0',result='collected')]
                    changed=True
                elif m=='GET' and p['phase']=='preview' and change.startswith('preview_'):
                    if change=='preview_domain':p['offers'][0]['cards'][0]['key']='Changed'
                    else:p['prior_results']=[]
                    changed=True
                elif m=='GET' and p['status']=='resolved' and change.startswith('resolved_'):
                    if change=='resolved_domain':p['offers'][0]['cards'][0]['upgrade_level']+=1
                    else:p['selected_index']=0
                    changed=True
            if changed:
                response[:]=b'\0'*len(response);response=bytearray(json.dumps(v,separators=(',',':')).encode());ex.buffers.append(response)
            return response
        result,ex=run('O_BUNDLE',corrupt);assert changed and result['code']=='invalid_response' and result['completed_card_children']==0,(change,result);checks+=1
    return checks
