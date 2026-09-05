"""Synthetic process integration: real C# bytes -> actual strict Python controllers."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import select
import subprocess
import sys

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def run_suite(dotnet, fixture, item_path):
    root = Path(__file__).resolve().parents[1]
    host = load("room_flow_host_fixture", root / "host/room_flow_host.py")
    item = load("frozen_item_host_fixture", item_path)
    checks = 0
    def check(value):
        nonlocal checks
        checks += 1
        if not value:
            raise AssertionError("integration check " + str(checks))

    def campaign(mode, *, buy_card=True, mutate=None, elapsed=None):
        process = subprocess.Popen([dotnet, fixture, mode], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        buffers, deadlines, requests = [], [], []
        now = [0.0]
        def exchange(method, route, decision, action, deadline):
            deadlines.append(deadline)
            requests.append((method, route, decision, action))
            request = dict(method=method, route=route, decision_id=decision, action_id=action)
            process.stdin.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            process.stdin.flush()
            if not select.select([process.stdout], [], [], 10.0)[0]:
                raise AssertionError("fixture response timeout")
            raw = process.stdout.readline(host.MAX_BODY + 2)
            check(raw.endswith(b"\n") and len(raw) <= host.MAX_BODY + 1)
            body = bytearray(raw[:-1])
            if mutate is not None:
                value = json.loads(body)
                if mutate(value, method, route):
                    body[:] = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")
            buffers.append(body)
            if elapsed is not None:
                now[0] += elapsed(method, route)
            return body
        def sleep(seconds):
            now[0] += seconds
        try:
            result = host.run_flow("shop" if mode.startswith("shop") else "event", exchange,
                                   item_host=item, buy_card=buy_card, clock=lambda:now[0], sleep=sleep)
            process.stdin.close()
            process.wait(timeout=10)
            diagnostic = process.stderr.read(2048)
            check(process.returncode == 0)
            native = json.loads(diagnostic)
            check(all(not any(b) for b in buffers))
            check(all(d <= 30.0 for d in deadlines))
            check("session_nonce" not in result and "candidates" not in result and "offers" not in result)
            return result, native, requests
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            for stream in (process.stdout, process.stderr):
                stream.close()
            if not process.stdin.closed:
                process.stdin.close()

    for mode, parent, child in (("shop",3,0),("event",3,0),("event_unicode",3,0),("event_choices",3,0),("event_item",3,1)):
        r,n,_ = campaign(mode)
        check(r["status"] == "passed")
        check(r["attempted"] == parent and r["accepted"] == parent)
        check(r["reconciled"] == (3 if mode == "shop" else 1))
        check(r["child_attempted"] == child and r["child_accepted"] == child and r["child_reconciled"] == child)
        check(n["shop_dispatches"] + n["event_dispatches"] == parent and n["item_dispatches"] == child)
        if mode.startswith("event"):
            check(r["option_transitions_observed"] == 2)
    r,n,_ = campaign("shop",buy_card=False)
    check(r["status"] == "passed" and r["attempted"] == 2 and r["reconciled"] == 2 and n["shop_dispatches"] == 2)
    r,n,_ = campaign("shop_uncertain")
    check(r["status"] == "failed" and r["attempted"] == 1 and r["accepted"] == 0 and r["reconciled"] == 0 and n["shop_dispatches"] == 1)
    r,n,_ = campaign("event_item_uncertain")
    check(r["status"] == "failed" and r["attempted"] == 1 and r["accepted"] == 1 and r["child_attempted"] == 1 and r["child_accepted"] == 0 and n["event_dispatches"] == 1 and n["item_dispatches"] == 1)

    def wrong_receipt(v,m,r):
        if v["status"] == "accepted":
            v["session_nonce"] = "f"*32
            return True
        return False
    r,n,_ = campaign("event",mutate=wrong_receipt)
    check(r["status"] == "failed" and r["accepted"] == 0 and n["event_dispatches"] == 1)

    def wrong_prior(v,m,r):
        if v.get("prior_results"):
            v["prior_results"][0]["action_id"] = "leave"
            v["prior_results"][0]["kind"] = "leave"
            if v["status"] == "ready":
                v["decision_id"] = host.shop_digest(v)
            return True
        return False
    r,n,_ = campaign("shop",mutate=wrong_prior)
    check(r["status"] == "failed" and r["accepted"] == 1 and r["reconciled"] == 0 and n["shop_dispatches"] == 1)

    def reserved_key(v,m,r):
        if v.get("candidates") and v["candidates"][0]["stable_id"] == "SECOND":
            v["candidates"][0]["stable_id"] = "FIRST"
            v["decision_id"] = host.event_digest(v)
            return True
        return False
    r,n,_ = campaign("event",mutate=reserved_key)
    check(r["status"] == "failed" and n["event_dispatches"] == 1)

    def bad_text(v,m,r):
        if v.get("candidates"):
            v["candidates"][0]["rendered_text"] = ""
            return True
        return False
    r,n,_ = campaign("event",mutate=bad_text)
    check(r["status"] == "failed" and r["attempted"] == 0 and n["event_dispatches"] == 0)

    def omit_purchase(v,m,r):
        if v.get("offers"):
            v["legal_actions"] = ["inventory:close"]
            v["decision_id"] = host.shop_digest(v)
            return True
        return False
    r,n,_ = campaign("shop",mutate=omit_purchase)
    check(r["status"] == "failed" and r["attempted"] == 0 and n["shop_dispatches"] == 0)

    def omit_choice(v,m,r):
        if len(v.get("candidates", [])) == 2:
            v["legal_actions"] = ["choose:1"]
            v["decision_id"] = host.event_digest(v)
            return True
        return False
    r,n,_ = campaign("event_choices",mutate=omit_choice)
    check(r["status"] == "failed" and r["attempted"] == 0 and n["event_dispatches"] == 0)

    for mode in ("event_choices", "event_item_choices"):
        initial = []
        def text_only(v,m,r):
            if v.get("candidates") and len(v["candidates"]) == 2 and not initial:
                initial.append(json.loads(json.dumps(v)))
            elif v.get("candidates") and v["candidates"][0]["stable_id"] == "SECOND":
                saved = initial[0]
                v["candidates"] = json.loads(json.dumps(saved["candidates"]))
                v["candidates"][0]["rendered_text"] += " changed text"
                v["legal_actions"] = ["choose:1"]
                v["decision_id"] = host.event_digest(v)
                check(host.event_transition_digest(v) == host.event_transition_digest(saved))
                return True
            return False
        r,n,_ = campaign(mode,mutate=text_only)
        check(r["status"] == "failed" and n["event_dispatches"] == 1 and r["option_transitions_observed"] == 0)
        check(r["child_reconciled"] == (1 if mode == "event_item_choices" else 0))

    def child_deadline(method,route):
        if "item-v1" in route:
            return 5.0 if method == "GET" else 6.0
        return 20.0 if method == "POST" else 0.0
    r,n,requests = campaign("event_item",elapsed=child_deadline)
    check(r["status"] == "failed" and r["code"] == "deadline_exceeded")
    check(n["event_dispatches"] == 1 and n["item_dispatches"] == 1)
    check(sum(m=="POST" for m,_,_,_ in requests) == 2)
    print(json.dumps({"schema_version":1,"status":"passed","suite":"room_flows_cross_language","check_count":checks},separators=(",",":")))
    return checks

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--dotnet",required=True)
    parser.add_argument("--fixture",required=True)
    parser.add_argument("--item-host",required=True)
    args=parser.parse_args()
    run_suite(args.dotnet,args.fixture,args.item_host)
