"""Actual C# room runtime, frozen services, Python socket transport and frozen hosts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import select
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(ROOT/"transport"),str(ROOT.parent)]
import room_transport as transport

def run_suite(dotnet,fixture):
    checks=0
    def check(value):
        nonlocal checks
        checks+=1
        if not value:raise AssertionError("room socket integration check "+str(checks))
    for mode,flow,parents,children in (("shop_success","shop",3,0),("event_continuation","event",3,0),
                                      ("event_item","event",3,1),("lost_receipt","shop",1,0)):
        process=subprocess.Popen([dotnet,fixture,"--fixture",mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        token=bytearray(b"c"*64)
        requests=[]
        try:
            check(bool(select.select([process.stdout],[],[],10)[0]))
            announcement=process.stdout.readline(128)
            endpoint=json.loads(announcement)
            check(type(endpoint) is dict and set(endpoint)=={"port"} and type(endpoint["port"]) is int and
                  1<=endpoint["port"]<=65535 and endpoint["port"]!=43117)
            class Redirect:
                def __init__(self):
                    self.socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                def connect(self,actual):
                    check(actual==("127.0.0.1",43117))
                    self.socket.connect(("127.0.0.1",endpoint["port"]))
                def sendall(self,request):
                    requests.append(request)
                    return self.socket.sendall(request)
                def __getattr__(self,name):return getattr(self.socket,name)
            result=transport._run_with_socket_factory(flow,token,Redirect,clock=time.monotonic,sleep=time.sleep)
            process.stdin.close()
            process.wait(timeout=10)
            diagnostic=process.stderr.read(2048)
            check(process.returncode==0 and process.stdout.read(128)==b"")
            native=json.loads(diagnostic)
            check(set(native)=={"dispatch_count","item_dispatch_count","read_count","terminal","transport_stopped","service_disposed"})
            check(native["transport_stopped"] is True and native["service_disposed"] is True)
            check(native["dispatch_count"]==parents and native["item_dispatch_count"]==children)
            check(result["status"]==("failed" if mode=="lost_receipt" else "passed"))
            check(result["attempted"]==parents and result["accepted"]==(0 if mode=="lost_receipt" else parents))
            check(result["child_attempted"]==children and result["child_accepted"]==children and result["child_reconciled"]==children)
            check(result["reconciled"]==(0 if mode=="lost_receipt" else 3 if flow=="shop" else 1))
            check(result["option_transitions_observed"]==(2 if flow=="event" else 0))
            check(not any(token) and all(not any(request) for request in requests))
            check(len(requests)==(2 if mode=="lost_receipt" else 11 if mode=="event_item" else 7))
            check(native["read_count"]==(1 if mode=="lost_receipt" else 7 if mode=="event_item" else 4))
            check(all(key not in result for key in ("session_nonce","candidates","offers","rendered_text")))
        finally:
            transport._zero(token)
            for request in requests:transport._zero(request)
            if process.poll() is None:
                process.kill();process.wait(timeout=5)
            for stream in (process.stdin,process.stdout,process.stderr):
                if not stream.closed:stream.close()
    print(json.dumps(dict(schema_version=1,status="passed",suite="room_release_socket_composition",check_count=checks),separators=(",",":")))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--dotnet",required=True);parser.add_argument("--fixture",required=True)
    args=parser.parse_args();run_suite(args.dotnet,args.fixture)
