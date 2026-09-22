"""Actual shared and original Python clients against the unified C# listener."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).absolute().parents[3]
sys.path[:0] = [str(ROOT / 'apps/bridge/client'), str(ROOT / 'tools')]
from wire_client import BridgeClient, parse_response
from run_live import verify_map_handoff, run_combat_map, run_event_map, retain_read_diagnostic, load
from combat_host import run_combat
import combat_host
import reward_host
import probe_live
sys.path.insert(0, str(ROOT / "components/rooms/host"))
import room_flow_host


def rest(action):
    process = subprocess.Popen([sys.argv[1], sys.argv[2], '--serve-rest', action], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        port = json.loads(process.stdout.readline())['port']
        client = BridgeClient(bytearray(b'a' * 64), connector=lambda: socket.create_connection(('127.0.0.1', port), timeout=2))
        try:
            result = room_flow_host.run_rest(client.item_exchange, action.split(":")[0], cook_slots=(0, 2) if action.startswith("cook:") else None)
            assert result['status'] == 'passed' and result['handoff'] == 'rest', result
            assert result['attempted'] == result['accepted'] == result['reconciled'] == 1, result
            # A subsequent core read proves the room module relinquished ownership.
            assert verify_map_handoff(client.exchange)['status'] == 'passed'
        finally:
            client.close()
        process.stdin.write('stop\n'); process.stdin.flush()
        _, errors = process.communicate(timeout=5)
        assert process.returncode == 0, errors
    finally:
        if process.poll() is None:
            process.kill(); process.wait()


def combat(reward_policy=None, event_resume=False, resume_items=False, special_card=False, item_rewards=False, full_potions=False, replace_potions=False, capacity_potions=False, healing_relic=False, potion_policy="stop-on-full"):
    process = subprocess.Popen([sys.argv[1], sys.argv[2], '--serve-healing-relic' if healing_relic else '--serve-capacity-potions' if capacity_potions else '--serve-replace-potions' if replace_potions else '--serve-full-potions' if full_potions else '--serve-combat-items' if item_rewards else '--serve-special-card' if special_card else '--serve-resume-items' if resume_items else '--serve-event-resume' if event_resume else '--serve-combat-map' if reward_policy else '--serve-combat'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        port = json.loads(process.stdout.readline())['port']
        client = BridgeClient(bytearray(b'a' * 64), connector=lambda: socket.create_connection(('127.0.0.1', port), timeout=2))
        try:
            if event_resume:
                assert json.loads(client.exchange('GET','/probe/generic-event-v7/public/decision'))['status']=='resolved'
                result=run_combat(client.exchange,event_resume_nonce='0123456789abcdef0123456789abcdef')
                assert result['status']=='resolved' and result['outcome']=='event_resumed', result
                assert result['attempted']==result['accepted']==result['reconciled']==1, result
                assert result['resume_reads']==(3 if resume_items else 2) and result['native_terminal_outcome'] is None, result
                if resume_items: assert result['resume_items'][0]['attempted']==result['resume_items'][0]['accepted']==result['resume_items'][0]['reconciled']==1, result
                assert verify_map_handoff(client.exchange)['status']=='passed'
            elif reward_policy:
                flow = run_combat_map(client.exchange, combat_host, reward_host, reward_policy=reward_policy,potion_policy=potion_policy)
                assert flow['status'] == 'resolved' and flow['map_handoff']['candidate_count'] == 1, flow
                loot = flow['rewards']
                assert loot['attempted'] == loot['accepted'] == loot['reconciled'] == (9 if replace_potions else 7 if item_rewards or capacity_potions else 5 if special_card or full_potions else 4), flow
                assert loot['skipped_potions'] == ([dict(key='POTION',reward_index=i,reason='inventory_full' if potion_policy=='skip-full' else 'policy') for i in (2,3)] if full_potions else []), flow
                assert loot['discarded_potions'] == ([dict(slot=i,key='OLD_'+str(i)) for i in range(2)] if replace_potions else []), flow
                assert loot['potion_capacity_gains'] == ([dict(key='POTION_BELT',reward_index=4,before=2,after=4)] if capacity_potions else []), flow
                assert loot['claimed_gold'] == 14, flow
                if healing_relic:assert loot['before_player']['hp']==33 and loot['after_player']['hp']==41, flow
                assert loot['collected_items'] == ([dict(kind='relic',key='POTION_BELT',reward_index=4),dict(kind='potion',key='POTION',reward_index=2),dict(kind='potion',key='POTION',reward_index=3)] if capacity_potions else [dict(kind='relic',key='RELIC',reward_index=4),dict(kind='potion',key='POTION',reward_index=2),dict(kind='potion',key='POTION',reward_index=3)] if replace_potions else [dict(kind='potion',key='POTION',reward_index=2),dict(kind='potion',key='POTION',reward_index=3),dict(kind='relic',key='FAKE_LEES_WAFFLE' if healing_relic else 'RELIC',reward_index=4)] if item_rewards else [dict(kind='relic',key='RELIC',reward_index=4)] if full_potions else []), flow
                assert loot['claimed_special_cards'] == (['LANTERN_KEY'] if special_card else []), flow
                assert loot['selected_cards'] == ([] if reward_policy == 'skip-card' else ['ANGER']), flow
                assert loot['skipped_card_rewards'] == (1 if reward_policy == 'skip-card' else 0), flow
                result = flow['combat']
            else:
                result = run_combat(client.exchange)
            if not event_resume:
                assert result['status'] == 'resolved' and result['outcome'] == 'victory', result
                assert result['attempted'] == result['accepted'] == result['reconciled'] == 2, result
                assert len(result['choices']) == 1 and result['choices'][0]['selected_count'] == 1, result
                assert result['choices'][0]['accepted'] == result['choices'][0]['reconciled'] == 1, result
        finally:
            client.close()
        process.stdin.write('stop\n'); process.stdin.flush()
        _, errors = process.communicate(timeout=5)
        assert process.returncode == 0, errors
    finally:
        if process.poll() is None:
            process.kill(); process.wait()


def read_timeout():
    for route in ('/probe/generic-event-v7/public/decision', '/probe/v0/health'):
        process = subprocess.Popen([sys.argv[1], sys.argv[2], '--serve-read-timeout'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            port = json.loads(process.stdout.readline())['port']
            client = BridgeClient(bytearray(b'a' * 64), connector=lambda: socket.create_connection(('127.0.0.1', port), timeout=2))
            try:
                if route.startswith('/probe/generic-event-v7/'):
                    host = load('read_timeout_event_host', 'components/events/host/generic_event_host.py')
                    result = retain_read_diagnostic(run_event_map(client.exchange, host), client)
                    assert result['status'] == 'failed' and result['event']['code'] == 'invalid_response', result
                    assert result['event']['total_attempted'] == 0 and result['map_handoff']['status'] == 'not_attempted', result
                    diagnostic = result['read_diagnostic']
                    assert diagnostic['code'] == 'dispatch_timeout_before_claim', result
                    assert len(diagnostic['stages']) == 1 and diagnostic['stages'][0]['stage'] == 'dispatch', result
                    assert diagnostic['stages'][0]['active'] is True and 0 <= diagnostic['stages'][0]['elapsed_ms'] <= 3000, result
                else:
                    reply = client.exchange('GET', route)
                    try:
                        value=json.loads(reply)
                        assert {k:v for k,v in value.items() if k!='stages'} == dict(schema_version=1, kind='error', code='dispatch_timeout_before_claim')
                        assert len(value['stages'])==1 and value['stages'][0]['stage']=='dispatch' and value['stages'][0]['active'] is True
                        assert 0<=value['stages'][0]['elapsed_ms']<=3000
                    finally:
                        reply[:] = b'\0' * len(reply)
            finally:
                client.close()
            process.stdin.write('stop\n'); process.stdin.flush()
            _, errors = process.communicate(timeout=5)
            assert process.returncode == 0, errors
        finally:
            if process.poll() is None:
                process.kill(); process.wait()


def shop(options, expected, scenario="normal", corrupt=None, expected_potions=0, slots=None, expected_relics=0, relics=None, expected_removals=0, deck_keys=None, expected_discards=0):
    process=subprocess.Popen([sys.argv[1],sys.argv[2],"--serve-shop",scenario],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        port=json.loads(process.stdout.readline())["port"]
        client=BridgeClient(bytearray(b"a"*64),connector=lambda:socket.create_connection(("127.0.0.1",port),timeout=2))
        posts=0
        def exchange(method,route,decision,action,deadline):
            nonlocal posts
            raw=client.item_exchange(method,route,decision,action,deadline)
            if method=="POST":
                posts+=1
                if corrupt=="lost_receipt" and posts==2:
                    raw[:]=b"\0"*len(raw)
                    raise ConnectionError("lost second receipt")
            elif corrupt=="replayed_result" and posts==2:
                value=json.loads(raw)
                if value.get("prior_results"):
                    value["prior_results"][0]["action_id"]="buy:card:0"
                    value["decision_id"]=room_flow_host.shop_digest(value)
                    raw[:]=json.dumps(value,ensure_ascii=True,separators=(",", ":")).encode()
                    room_flow_host.decode(raw,"shop")  # Reach correlation, not malformed JSON/hash validation.
            return raw
        try:
            result=room_flow_host.run_flow("shop",exchange,**options)
            failed=scenario.endswith("bad_debit") or corrupt is not None
            assert result["status"]==("failed" if failed else "passed"),result
            if failed:
                assert result["attempted"]==2 and result["accepted"]==(1 if corrupt=="lost_receipt" else 2) and result["reconciled"]==1,result
            else:
                assert result["attempted"]==result["accepted"]==result["reconciled"]==expected+expected_discards+2,result
                assert verify_map_handoff(client.exchange)["status"]=="passed"
        finally:client.close()
        process.stdin.write("stop\n");process.stdin.flush()
        output,errors=process.communicate(timeout=5)
        assert process.returncode==0,errors
        actual=json.loads(output)
        assert actual["purchases"]==expected and actual["disposals"]==expected+expected_discards,actual
        assert actual["deck"]==expected+(3 if scenario.startswith("removal_") else 1)-expected_potions-expected_relics-2*expected_removals,actual
        assert actual["closes"]==actual["leaves"]==(0 if failed else 1),actual
        if scenario=="normal" or scenario.startswith(("potion_","relic_","removal_")):assert actual["gold"]==100-10*expected-(1 if scenario.endswith("bad_debit") else 0),actual
        if deck_keys is not None:assert actual["deck_keys"]==deck_keys,actual
        if relics is not None:assert actual["relics"]==relics,actual
        if slots is not None:assert actual["potions"]==slots,actual
    finally:
        if process.poll() is None:process.kill();process.wait()


def shop_policies():
    def no_io(*args):raise AssertionError("invalid policy performed I/O")
    for field,values in (("max_purchases",(-1,9,True,None,"2")),("gold_reserve",(-1,2147483648,True,None,"2")),("purchase_policy",("unsupported",True,None,3,[])),("removal_policy",("all",True,None,3,[]))):
        for value in values:
            try:room_flow_host.run_flow("shop",no_io,**{field:value})
            except ValueError:pass
            else:raise AssertionError("invalid policy accepted")
    shop({},1)
    for count in (0,2,8):shop({"max_purchases":count},count)
    shop({"buy_card":False,"max_purchases":8},0)
    for reserve,expected in ((75,2),(90,1),(95,0),(100,0),(2147483647,0)):
        shop({"max_purchases":8,"gold_reserve":reserve},expected)
    shop({"max_purchases":8},1,"unaffordable")
    shop({"max_purchases":8,"gold_reserve":100},8,"free")
    shop({"max_purchases":2,"gold_reserve":80},2,"prices")
    shop({"max_purchases":8,"gold_reserve":80},2,"repriced")
    shop({"max_purchases":8},2,"bad_debit")
    for corrupt in ("lost_receipt","replayed_result"):shop({"max_purchases":8},2,corrupt=corrupt)


def shop_removal_policies():
    shop({},1,"removal_mixed",deck_keys=["OLD","REMOVE_ME","KEEP","CARD_0"])
    shop({"purchase_policy":"all","max_purchases":8},2,"removal_mixed",expected_potions=1,deck_keys=["OLD","REMOVE_ME","KEEP","CARD_0"])
    shop({"removal_policy":"first"},1,"removal_mixed",expected_removals=1,deck_keys=["OLD","KEEP"])
    shop({"removal_policy":"first","purchase_policy":"all","max_purchases":8},3,"removal_mixed",expected_removals=1,expected_potions=1,deck_keys=["OLD","KEEP","CARD_0"])
    shop({"removal_policy":"first","max_purchases":0},0,"removal_mixed",deck_keys=["OLD","REMOVE_ME","KEEP"])
    shop({"removal_policy":"first","purchase_policy":"all","max_purchases":8,"gold_reserve":90},1,"removal_mixed",expected_removals=1)
    shop({"removal_policy":"first","purchase_policy":"all","max_purchases":8,"gold_reserve":95},0,"removal_mixed")
    shop({"removal_policy":"first","purchase_policy":"all","max_purchases":8},2,"removal_empty",expected_potions=1,deck_keys=["OLD","REMOVE_ME","KEEP","CARD_0"])
    shop({"removal_policy":"first","max_purchases":8},2,"removal_bad_debit",expected_removals=1)
    shop({"removal_policy":"first","max_purchases":8},2,"removal_mixed",corrupt="lost_receipt",expected_removals=1)


def shop_relic_policies():
    shop({"max_purchases":8},1,"relic_mixed",slots=["OLD_POTION"],relics=["OLD_RELIC"])
    shop({"purchase_policy":"cards-and-potions","max_purchases":8},1,"relic_mixed",slots=["OLD_POTION"],relics=["OLD_RELIC"])
    shop({"purchase_policy":"relics","max_purchases":8},2,"relic_mixed",expected_relics=2,slots=["OLD_POTION",None,None],relics=["OLD_RELIC","POTION_BELT","RELIC_3"])
    shop({"purchase_policy":"all","max_purchases":8},5,"relic_mixed",expected_relics=2,expected_potions=2,slots=["OLD_POTION","POTION_2","POTION_4"],relics=["OLD_RELIC","POTION_BELT","RELIC_3"])
    shop({"purchase_policy":"all","max_purchases":2},2,"relic_mixed",expected_relics=1,slots=["OLD_POTION",None,None],relics=["OLD_RELIC","POTION_BELT"])
    shop({"purchase_policy":"relics","max_purchases":8,"gold_reserve":90},1,"relic_mixed",expected_relics=1,slots=["OLD_POTION",None,None],relics=["OLD_RELIC","POTION_BELT"])
    shop({"purchase_policy":"all","max_purchases":8,"gold_reserve":95},0,"relic_mixed",relics=["OLD_RELIC"])
    shop({"purchase_policy":"all","max_purchases":8},2,"relic_full",expected_relics=1,slots=["OLD_POTION"]+["OLD_"+str(i) for i in range(1,8)],relics=["OLD_RELIC","RELIC_3"])
    shop({"purchase_policy":"relics","max_purchases":8},1,"relic_owned",expected_relics=1,slots=["OLD_POTION"],relics=["OLD_RELIC","POTION_BELT","RELIC_3"])
    shop({"purchase_policy":"relics","max_purchases":8},2,"relic_bad_debit",expected_relics=2,slots=["OLD_POTION",None,None],relics=["OLD_RELIC","POTION_BELT","RELIC_3"])


def shop_potion_policies():
    shop({"max_purchases":8},2,"potion_mixed",slots=["OLD",None,None])
    shop({"purchase_policy":"potions","max_purchases":8},2,"potion_mixed",expected_potions=2,slots=["OLD","POTION_1","POTION_2"])
    shop({"purchase_policy":"cards-and-potions","max_purchases":8},4,"potion_mixed",expected_potions=2,slots=["OLD","POTION_1","POTION_2"])
    shop({"purchase_policy":"cards-and-potions","max_purchases":2},2,"potion_mixed",expected_potions=1,slots=["OLD","POTION_1",None])
    shop({"purchase_policy":"cards-and-potions","max_purchases":8,"gold_reserve":75},2,"potion_mixed",expected_potions=1,slots=["OLD","POTION_1",None])
    shop({"purchase_policy":"potions","max_purchases":8,"gold_reserve":95},0,"potion_mixed",slots=["OLD",None,None])
    shop({"purchase_policy":"potions","max_purchases":8},0,"potion_full",slots=["OLD","OLD_1","OLD_2"])
    shop({"purchase_policy":"cards-and-potions","max_purchases":8},2,"potion_full",slots=["OLD","OLD_1","OLD_2"])
    shop({"purchase_policy":"potions","max_purchases":8},0,"potion_zero",slots=[])
    shop({"purchase_policy":"potions","max_purchases":8},2,"potion_holes",expected_potions=2,slots=["POTION_1","OLD_1","POTION_2"])
    shop({"purchase_policy":"cards-and-potions","max_purchases":8},2,"potion_bad_debit",expected_potions=1,slots=["OLD","POTION_1",None])


def main():
    process = subprocess.Popen([sys.argv[1], sys.argv[2], '--serve'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        port = json.loads(process.stdout.readline())['port']
        connector = lambda: socket.create_connection(('127.0.0.1', port), timeout=2)
        client = BridgeClient(bytearray(b'a' * 64), connector=connector)
        action = bytearray(json.dumps({'decision_id': 'b' * 64, 'action_id': 'end_turn'}).encode())
        stale = json.loads(client.exchange('POST', '/probe/v0/public/combat-action', action))
        assert (stale['status'], stale['mutation_state'], stale['reason']) == ('rejected', 'none', 'stale_decision')
        # The controller refreshes after a known pre-dispatch rejection. This
        # request used to fail because the shared host closed its listener.
        assert json.loads(client.exchange('GET', '/probe/v0/public/combat-decision'))['status'] == 'waiting'
        for route in ['/probe/generic-event-v7/public/decision', '/card-selection-v1/parent',
                      '/probe/room-flows-v1/public/decision', '/probe/item-v1/public/item-decision']:
            assert json.loads(client.exchange('GET', route))['status'] == 'ready'
            if route == '/probe/room-flows-v1/public/decision':
                purchase = bytearray(json.dumps({'decision_id': 'c' * 64, 'action_id': 'buy:card:0'}).encode())
                assert json.loads(client.exchange('POST', '/probe/room-flows-v1/public/action', purchase))['status'] == 'resolved'
            else:
                assert json.loads(client.exchange('GET', route))['status'] == 'resolved'
        for i, sphere_action in enumerate(('tool:big', 'reveal:120', 'reward:claim:7',
                                          'reward:collect:7', 'reward:open:7',
                                          'reward:choose:4', 'reward:skip_card', 'dismiss', 'cancel', 'confirm_abandon', 'skip_remaining', 'discard:0', 'skip_card')):
            assert json.loads(client.exchange('GET', '/probe/generic-event-v7/public/decision'))['status'] == 'ready'
            sphere_body = bytearray(json.dumps(dict(decision_id=f'{i+100:064x}', action_id=sphere_action,
                child=dict(ordinal=1, parent_decision_id='d'*64, parent_action_id='choose:0'))).encode())
            try:
                assert json.loads(client.exchange('POST', '/probe/generic-event-v7/public/action', sphere_body))['status'] == 'resolved'
            finally:
                sphere_body[:] = b'\0' * len(sphere_body)
        assert verify_map_handoff(client.exchange) == {
            'status': 'passed', 'reads': 1, 'candidate_count': 1, 'code': None}
        # Reuse the actual base-controller exchange helper, including SHUT_WR.
        def build():
            return bytearray(b'GET /probe/v0/manifest HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer ' + b'a' * 64 +
                             b'\r\nAccept: application/json\r\nConnection: close\r\n\r\n')
        response = probe_live._exchange_request('unified', build, connector, time.monotonic() + 3, 'expired')
        body = parse_response(response, event=False)
        probe_live._validate_manifest(memoryview(body))
        assert json.loads(body)['bridge_version'] == '1.0.0'
        client.close()
        process.stdin.write('stop\n'); process.stdin.flush()
        _, errors = process.communicate(timeout=5)
        assert process.returncode == 0, errors
        shop_policies()
        shop_potion_policies()
        shop_relic_policies()
        shop_removal_policies()
        shop({"max_purchases":8},8,"restock_card")
        shop({"potion_policy":"skip-full","purchase_policy":"potions","max_purchases":8},0,"replacement_potion",slots=["OLD_A","OLD_B"])
        shop({"potion_policy":"replace-first","purchase_policy":"potions","max_purchases":8},2,"replacement_potion",expected_potions=2,expected_discards=2,slots=["POTION_0","POTION_0"])

        read_timeout()
        rest('lift')
        rest('kindle')
        rest('dig')
        rest('clone')
        rest('hatch')
        rest('cook:0:2')
        combat()
        combat('first-card')
        combat('skip-card')
        for potion_policy in ('skip-full','skip-all'):
            combat('first-card',full_potions=True,potion_policy=potion_policy)
            combat('skip-card',full_potions=True,potion_policy=potion_policy)
        for capacity_policy in ('stop-on-full','replace-first'):
            combat('first-card',capacity_potions=True,potion_policy=capacity_policy)
            combat('skip-card',capacity_potions=True,potion_policy=capacity_policy)
        combat('first-card',replace_potions=True,potion_policy='replace-first')
        combat('skip-card',replace_potions=True,potion_policy='replace-first')
        combat('first-card',item_rewards=True,healing_relic=True)
        combat('skip-card',item_rewards=True,healing_relic=True)
        combat('first-card',item_rewards=True)
        combat('skip-card',item_rewards=True)
        combat('first-card',special_card=True)
        combat('skip-card',special_card=True)
        combat(event_resume=True)
        combat(event_resume=True,resume_items=True)
        print('{"status":"passed","suite":"unified_python_socket","shop_policy_cases":20,"shop_invalid_policies":20,"shop_potion_cases":11,"shop_relic_cases":10,"shop_removal_cases":10,"capability_clients":7,"original_client":true,"stale_refresh":true,"combat_choice_resume":true,"combat_reward_map_policies":2,"event_combat_resume":true,"resume_item_post":true,"special_card_post_policies":2,"combat_item_post_policies":2,"full_potion_policy_combinations":4}')
    finally:
        if process.poll() is None:
            process.kill(); process.wait()


if __name__ == '__main__':
    main()
