"""Multiple native card menus in one owned RewardsSet; strict host composition."""
from __future__ import annotations

import json
from typing import Any, Callable


REWARD_SET_PARTS = ('cards_native', 'cards_host', 'mixed_native', 'mixed_host')


def run_card_reward_set_cases(args: Any, host: Any, exchange_type: Any, *, part: str | None = None) -> int:
    if part is not None and part not in REWARD_SET_PARTS:
        raise ValueError('unknown reward-set part: ' + part)
    checks = run_mixed_reward_set_cases(args,host,exchange_type,part=part) if part is None or part.startswith('mixed_') else 0
    def run(scenario: str, wrapper: Callable | None = None) -> tuple[dict, Any]:
        ex = exchange_type(args.dotnet, args.native_fixture, scenario, native=True)
        request = ex.request if wrapper is None else lambda m, r, b: wrapper(ex, m, r, b)
        def choose(view: Any) -> str:
            p=view.payload
            if view.kind != 'parent' and p.get('phase') == 'choose':
                index=p['offer_index']
                if scenario=='CRS_SKIP' or scenario in ('CRS_MIXED','CRS_DISMISS_DISABLED') and index==0:
                    return f'skip:{index}'
                return f"choose:{index}:{len(p['cards'])-1}"
            return host.first_legal(view)
        try:
            result = host.run_event(request, provider=choose, clock=lambda: 1.0, sleep=lambda _: None)
        finally:
            ex.close()
        return result, ex

    if part is None or part == 'cards_native':
        for scenario in ('CRS_TWO','CRS_THREE','CRS_EIGHT','CRS_MIXED','CRS_SKIP','CRS_OFFER','CRS_COLLECTION','CRS_CHOSEN','CRS_DEFERRED','CRS_DISMISS_DISABLED'):
            result,ex=run(scenario)
            assert result['status']=='resolved', (scenario,result,ex.envelopes[-1])
            count=2 if scenario=='CRS_TWO' else 8 if scenario in ('CRS_EIGHT','CRS_SKIP') else 3
            skipped=count if scenario=='CRS_SKIP' else 1 if scenario in ('CRS_MIXED','CRS_DISMISS_DISABLED') else 0
            assert result['child_attempted']==result['child_accepted']==result['child_reconciled']==2*count+int(skipped>0)
            assert result['parent_accepted']==result['parent_reconciled']==2 and result['completed_card_children']==result['child_episodes']==1
            assert result['completed_item_children']==0 and result['total_attempted']==ex.posts
            end=ex.telemetry[-1]
            assert end==dict(map_open=True,overlay_count=0,opens=count,choices=count-skipped,skips=skipped,dismisses=int(skipped>0),
                             added_slots=[10*i+(0 if i%3==0 else 2 if i%3==1 else 4) for i in range(count) if not (scenario=='CRS_SKIP' or skipped and i==0)]), (scenario,end)
            children=[v for v in ex.envelopes if v['kind']=='decision' and v['child']]
            assert all(v['child']['contract_version']=='card_reward_set_v1' and v['child']['offer_count']==count for v in children)
            done=[v['payload'] for v in children if v['payload']['status']=='resolved']
            assert len(done)==1 and len(done[0]['settled'])==count and done[0]['offer_index']==count
            assert [r['offer_index'] for r in done[0]['settled']]==list(range(count))
            assert sum(r['result']=='skipped' for r in done[0]['settled'])==skipped
            assert any(v['payload']['settled'] and v['parent']['completed_card_children']==0 for v in children)
            checks+=1

        for scenario in ('CRS_OWNER','CRS_CLAIM','CRS_DECK','CRS_WRONG'):
            result,ex=run(scenario)
            assert result['code']=='unsupported_state' and result['completed_card_children']==0, (scenario,result)
            assert ex.telemetry[-1]['choices']==1 and ex.telemetry[-1]['dismisses']==0
            assert result['child_reconciled']==(1 if scenario=='CRS_WRONG' else 3), (scenario,result)
            checks+=1

    if part is None or part == 'cards_host':
        for stage in ('open:0','choose:0:0','open:1','choose:1:2','skip:1','dismiss','terminal'):
            lost=False
            def lose(ex,method,route,body):
                nonlocal lost
                response=ex.request(method,route,body);v=json.loads(response)
                if not lost and v['child'] and (stage=='terminal' and method=='GET' and v['payload']['status']=='resolved' or
                                               method=='POST' and stage!='terminal' and json.loads(body)['action_id']==stage):
                    lost=True;response[:]=b'\0'*len(response);raise host.TransportFailure()
                return response
            result,ex=run('CRS_SKIP' if stage=='skip:1' else 'CRS_MIXED' if stage=='dismiss' else 'CRS_THREE',lose)
            assert lost and result['code']=='transport_failure' and result['completed_card_children']==0, (stage,result)
            expected_posts={'open:0':2,'choose:0:0':3,'open:1':4,'choose:1:2':5,'skip:1':5,'dismiss':8,'terminal':7}
            assert ex.posts==expected_posts[stage], (stage,ex.posts)
            assert ex.telemetry[-1]['opens']<=3 and ex.telemetry[-1]['dismisses']<=1
            checks+=1

        for change in ('version','count','index','slot','action','receipt','history','drop','result','selected','key','level','skip_claim','premature','dismiss'):
            changed=False
            def corrupt(ex,method,route,body):
                nonlocal changed
                response=ex.request(method,route,body);v=json.loads(response);c,p=v['child'],v['payload']
                if not changed and c:
                    if change=='receipt' and method=='POST':p['action_id']='open:7';changed=True
                    elif method=='GET':
                        if p['phase']=='open' and p['offer_index']==0 and change in ('version','count','index'):
                            if change=='version':c['contract_version']='card_reward_v1'
                            if change=='count':p['offer_count']=2
                            if change=='index':p['offer_index']=True
                            changed=True
                        elif p['phase']=='choose' and p['offer_index']==0 and change in ('slot','action','history','premature','dismiss'):
                            if change=='slot':p['cards'][0]['slot']=1
                            if change=='action':p['legal_actions']=['choose:1:0']
                            if change=='history':p['prior_results']=[]
                            if change=='premature':p['status']='resolved';p['phase']='complete'
                            if change=='dismiss':p['phase']='dismiss';p['cards']=[];p['can_skip']=False;p['legal_actions']=['dismiss']
                            changed=True
                        elif p['settled'] and change in ('drop','result','selected','key','level','skip_claim'):
                            row=p['settled'][0]
                            if change=='drop':p['settled']=[];p['offer_index']=0
                            if change=='result':row['result']='dismissed'
                            if change=='selected':row['selected_slot']=4
                            if change=='key':row['key']='CHANGED'
                            if change=='level':row['upgrade_level']=True
                            if change=='skip_claim':row['result']='skipped';row['selected_slot']=None;row['key']=None;row['upgrade_level']=None
                            changed=True
                response[:]=json.dumps(v,separators=(',',':')).encode();return response
            result,ex=run('CRS_THREE',corrupt)
            assert changed and result['code']=='invalid_response' and result['completed_card_children']==0, (change,result)
            assert ex.telemetry[-1]['choices']<=1
            checks+=1
        for field in ('offer_index','selected_slot','upgrade_level'):
            changed=False
            def corrupt_old(ex,method,route,body):
                nonlocal changed
                response=ex.request(method,route,body);v=json.loads(response);p=v['payload']
                if not changed and method=='GET' and v['child'] and p['phase']=='open' and p['offer_index']==1:
                    p['settled'][0][field]=False;changed=True
                response[:]=json.dumps(v,separators=(',',':')).encode();return response
            result,ex=run('CRS_THREE',corrupt_old)
            assert changed and result['code']=='invalid_response' and result['child_reconciled']==2 and result['completed_card_children']==0, (field,result)
            assert ex.telemetry[-1]['opens']==ex.telemetry[-1]['choices']==1
            checks+=1
    return checks


def run_mixed_reward_set_cases(args: Any, host: Any, exchange_type: Any, *, part: str | None = None) -> int:
    checks=0
    def run(scenario='MR_COFFER',wrapper=None):
        ex=exchange_type(args.dotnet,args.native_fixture,scenario,native=True)
        def choose(view):
            if view.kind=='item_policy':
                if scenario=='MR_POLICY_CARD_SKIP' and view.payload['phase']=='choose_card':return 'skip_card'
                return host.item_policy_action(view.payload,'replace-first' if scenario=='MR_POLICY_REPLACE' else 'skip-full')
            if scenario in ('MR_SKIP','MR_CAPACITY_SKIP') and view.payload.get('phase')=='choose':return 'skip:'+str(view.payload['offer_index'])
            return host.first_legal(view)
        try:
            result=host.run_event(ex.request if wrapper is None else lambda m,r,b:wrapper(ex,m,r,b),provider=choose,clock=lambda:1.0,sleep=lambda _:None)
        finally:ex.close()
        return result,ex
    if part is None or part == 'mixed_native':
        for scenario in ('MR_POLICY_SKIP','MR_POLICY_REPLACE','MR_POLICY_CARD_SKIP'):
            result,ex=run(scenario)
            assert result['status']=='resolved',(scenario,result,ex.envelopes[-1:])
            assert result['completed_item_children']==1 and result['completed_card_children']==0
            assert result['child_reconciled']==(6 if scenario=='MR_POLICY_REPLACE' else 3)
            assert ex.telemetry[-1]['map_open'] and ex.telemetry[-1]['overlay_count']==0
            assert ex.telemetry[-1]['skips']==int(scenario=='MR_POLICY_CARD_SKIP')
            checks+=1
        for scenario in ('MR_CAPACITY','MR_CAPACITY_SKIP' ,'MR_COFFER','MR_SKIP','MR_FIRST','MR_EIGHT','MR_COLLECTION','MR_OFFER','MR_CHOSEN'):
            result,ex=run(scenario)
            assert result['status']=='resolved',(scenario,result,ex.envelopes[-1])
            kinds=['relic','card','potion','potion'] if scenario.startswith('MR_CAPACITY') else ['card','relic','card','potion','relic','card','potion','relic'] if scenario=='MR_EIGHT' else ['potion','card','potion'] if scenario in ('MR_FIRST','MR_COLLECTION') else ['card','potion']
            count=len(kinds);actions=sum(2 if k=='card' else 1 for k in kinds)+int(scenario in ('MR_SKIP','MR_CAPACITY_SKIP'))
            assert result['child_attempted']==result['child_accepted']==result['child_reconciled']==actions
            assert result['completed_card_children']==result['child_episodes']==1 and result['completed_item_children']==0 and result['parent_reconciled']==2
            children=[v for v in ex.envelopes if v['kind']=='decision' and v['child']]
            assert all(v['child']['contract_version']=='mixed_reward_set_v1' and v['payload']['offer_kinds']==kinds for v in children)
            done=[v['payload'] for v in children if v['payload']['status']=='resolved']
            assert len(done)==1 and len(done[0]['settled'])==count
            assert [r['kind'] for r in done[0]['settled']]==kinds
            assert sum(v['payload']['phase']=='collect' for v in children)>=kinds.count('potion')+kinds.count('relic')
            end=ex.telemetry[-1]
            assert end['map_open'] and end['overlay_count']==0 and end['opens']==kinds.count('card') and end['dismisses']==int(scenario in ('MR_SKIP','MR_CAPACITY_SKIP'))
            assert end['added_slots']==[10*i for i,k in enumerate(kinds) if k=='card' and scenario not in ('MR_SKIP','MR_CAPACITY_SKIP')]
            checks+=1
        result,ex=run('MR_LATE_SLOT')
        assert result['code']=='unsupported_state' and result['completed_card_children']==0 and result['child_reconciled']==4,(result,ex.envelopes[-1])
        checks+=1
    if part is None or part == 'mixed_host':
        for stage in ('collect:0','collect:2','terminal'):
            changed=False
            def lose(ex,m,r,b):
                nonlocal changed
                response=ex.request(m,r,b);v=json.loads(response)
                if not changed and v['child'] and (m=='POST' and json.loads(b)['action_id']==stage or stage=='terminal' and m=='GET' and v['payload']['status']=='resolved'):
                    changed=True;response[:]=b'\0'*len(response);raise host.TransportFailure()
                return response
            result,ex=run('MR_FIRST',lose)
            assert changed and result['code']=='transport_failure' and result['completed_card_children']==0
            assert ex.posts=={'collect:0':2,'collect:2':5,'terminal':5}[stage]
            checks+=1
        for change in ('kinds','all_cards','version','extra','nested_kind','nested_index','nested_nonce','nested_decision','nested_key','nested_slots','action','card_phase','null_item','item_on_wait','settled_kind','settled_slot','settled_key','old_bool','early_complete'):
            changed=False
            def corrupt(ex,m,r,b):
                nonlocal changed
                response=ex.request(m,r,b);v=json.loads(response);p=v['payload']
                if not changed and m=='GET' and v['child']:
                    if p['phase']=='collect' and p['offer_index']==0 and change not in ('settled_kind','settled_slot','settled_key','old_bool','item_on_wait'):
                        if change=='kinds':p['offer_kinds']=['relic','card','potion']
                        if change=='all_cards':p['offer_kinds']=['card']*3
                        if change=='version':v['child']['contract_version']='card_reward_set_v1'
                        if change=='extra':p['extra']=1
                        if change=='nested_kind':p['item']['offers'][0]['kind']='relic'
                        if change=='nested_index':p['item']['offers'][0]['index']=True
                        if change=='nested_nonce':p['item']['session_nonce']='f'*32
                        if change=='nested_decision':p['item']['decision_id']='a'*64
                        if change=='nested_key':p['item']['offers'][0]['key']='CHANGED'
                        if change=='nested_slots':p['item']['potion_slots']=[None,None,None]
                        if change=='action':p['legal_actions']=['collect:2']
                        if change=='card_phase':p['phase']='open';p['legal_actions']=['open:0'];p['item']=None
                        if change=='null_item':p['item']=None
                        if change=='early_complete':p['status']='resolved';p['phase']='complete';p['decision_id']='';p['legal_actions']=[];p['item']=None
                        changed=True
                    elif p['settled'] and change in ('settled_kind','settled_slot','settled_key','old_bool','item_on_wait'):
                        if change=='settled_kind':p['settled'][0]['kind']='relic'
                        if change=='settled_slot':p['settled'][0]['selected_slot']=0
                        if change=='settled_key':p['settled'][0]['key']='CHANGED'
                        if change=='old_bool' and p['phase']!='open':return response
                        if change=='old_bool':p['settled'][0]['offer_index']=False
                        if change=='item_on_wait':p['item']={}
                        changed=True
                response[:]=json.dumps(v,separators=(',',':')).encode();return response
            result,ex=run('MR_FIRST',corrupt)
            assert changed and result['code']=='invalid_response' and result['completed_card_children']==0,(change,result)
            assert ex.telemetry[-1]['opens']==0
            checks+=1
    return checks
