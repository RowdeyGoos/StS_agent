from __future__ import annotations
import json
import socket
import sys
import time
import unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(ROOT/"transport"),str(ROOT.parent)]
import room_transport as transport
from room_flows_v1.host import room_flow_host as host
TOKEN_BYTES=b"0123456789abcdef"*4

def http(body):
    return (b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: "+
            str(len(body)).encode("ascii")+b"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n"+body)

def common(flow,status):
    return dict(schema_version=1,protocol="room_flows_v1",version=flow+"_v1",flow_kind=flow,
                session_nonce="0123456789abcdef"*2,parent_ordinal=1,status=status)

def encode(value):
    return json.dumps(value,ensure_ascii=True,separators=(",",":")).encode("ascii")

def room_frames(flow):
    frames=[]
    if flow=="shop":
        prior=[]
        gold,deck=100,10
        for index,(phase,action) in enumerate((("inventory_browse","buy:card:0"),("inventory_browse","inventory:close"),("room_ready_to_leave","leave"))):
            ready=common(flow,"ready")
            ready.update(phase=phase,decision_id="",player=dict(gold=gold,deck_count=deck),
                         offers=[dict(slot=0,kind="card",key="Strike",displayed_price=50,affordable=True,enabled=True,supported=True)] if index==0 else [],
                         legal_actions=["buy:card:0","inventory:close"] if index==0 else [action],prior_results=prior)
            ready["decision_id"]=host.shop_digest(ready)
            frames.append(encode(ready))
            accepted=common(flow,"accepted");accepted.update(decision_id=ready["decision_id"],action_id=action)
            frames.append(encode(accepted))
            prior=[dict(flow_kind=flow,session_nonce=ready["session_nonce"],parent_ordinal=1,
                        decision_id=ready["decision_id"],action_id=action,
                        kind=("purchase_card","inventory_close","leave")[index],result="reconciled")]
            gold,deck=50,11
        final=common(flow,"complete")
        final.update(phase="complete",decision_id="",player=dict(gold=gold,deck_count=deck),offers=[],legal_actions=[],prior_results=prior)
        frames.append(encode(final))
    else:
        for phase,key,text in (("choose_option","FIRST","Take the safe option"),("proceed","PROCEED","Leave")):
            ready=common(flow,"ready")
            ready.update(phase=phase,decision_id="",candidates=[dict(candidate_index=0,action_id="choose:0",stable_id=key,
                         rendered_text=text,enabled=True,is_dangerous=False,is_proceed=phase=="proceed")],legal_actions=["choose:0"])
            ready["decision_id"]=host.event_digest(ready)
            frames.append(encode(ready))
            accepted=common(flow,"accepted");accepted.update(decision_id=ready["decision_id"],action_id="choose:0")
            frames.append(encode(accepted))
        final=common(flow,"resolved");final.update(decision_id=ready["decision_id"],action_id="choose:0",result="map_handoff")
        frames.append(encode(final))
    return frames

class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, duration: float) -> None:
        self.value += duration


class FakeSocket:
    def __init__(self, events: list[object], fault: str | None = None, clock: Clock | None = None) -> None:
        self.events = list(events)
        self.fault = fault
        self.clock = clock
        self.requests: list[bytearray] = []
        self.sent: list[bytes] = []
        self.timeouts: list[float] = []
        self.endpoint = None
        self.shutdown_how = None
        self.close_calls = 0
        self.trace: list[str] = []

    def _step(self, name: str) -> None:
        self.trace.append(name)
        if self.fault == name:
            raise OSError("SYNTHETIC_SOCKET_CANARY")
        if self.fault == "late_" + name and self.clock is not None:
            self.clock.value = 3.0

    def settimeout(self, value: float) -> None:
        self._step("settimeout")
        self.timeouts.append(value)

    def connect(self, endpoint) -> None:
        self._step("connect")
        self.endpoint = endpoint

    def sendall(self, request: bytearray) -> None:
        self._step("sendall")
        self.requests.append(request)
        self.sent.append(bytes(request))

    def shutdown(self, how: int) -> None:
        self._step("shutdown")
        self.shutdown_how = how

    def recv(self, maximum: int):
        self._step("recv")
        if maximum != 1024:
            raise AssertionError("receive cap drift")
        if not self.events:
            return b""
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event

    def close(self) -> None:
        self.close_calls += 1
        self._step("close")


class Factory:
    def __init__(self, sockets: list[FakeSocket] | None = None, failure: BaseException | None = None) -> None:
        self.sockets = list(sockets or [])
        self.failure = failure
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        if not self.sockets:
            raise AssertionError("unexpected socket retry")
        return self.sockets.pop(0)


def chunks(data):
    return [data[i:i+1024] for i in range(0,len(data),1024)]

class TransportTests(unittest.TestCase):
    def exchange(self,flow,route,body,*,method="GET",action=None,wire=None,fault=None,clock=None):
        timer=clock or Clock()
        sock=FakeSocket(chunks(http(body) if wire is None else wire),fault,timer)
        token=bytearray(TOKEN_BYTES)
        factory=Factory([sock])
        exchange=transport._AuthenticatedExchange(flow,token,factory,timer,timer.sleep)
        try:
            return exchange(method,route,None if method=="GET" else "a"*64,action,30.0),sock
        finally:
            transport._zero(token)
            self.assertTrue(all(not any(r) for r in sock.requests))
            if factory.calls: self.assertEqual(sock.close_calls,1)

    def test_real_frozen_hosts_full_shop_and_event_sequences(self):
        for flow,posts in (("shop",3),("event",2)):
            with self.subTest(flow=flow):
                sockets=[FakeSocket(chunks(http(body))) for body in room_frames(flow)]
                timer=Clock();token=bytearray(TOKEN_BYTES);factory=Factory(sockets)
                result=transport._run_with_socket_factory(flow,token,factory,clock=timer,sleep=timer.sleep)
                self.assertEqual(result["status"],"passed")
                self.assertEqual(result["attempted"],posts)
                self.assertEqual(result["accepted"],posts)
                self.assertEqual(result["reconciled"],3 if flow=="shop" else 1)
                self.assertFalse(any(token))
                self.assertEqual(sum(s.sent[0].startswith(b"POST ") for s in sockets),posts)
                for s in sockets:
                    self.assertEqual(s.endpoint,("127.0.0.1",43117))
                    self.assertEqual(s.shutdown_how,socket.SHUT_WR)
                    self.assertEqual(s.close_calls,1)
                    self.assertTrue(all(not any(r) for r in s.requests))

    def test_four_route_grammar_and_selected_flow(self):
        allowed=[("shop",transport._DECISION_ROUTE,"GET",None),("shop",transport._ACTION_ROUTE,"POST","buy:card:31"),
                 ("shop",transport._ACTION_ROUTE,"POST","inventory:close"),("shop",transport._ACTION_ROUTE,"POST","leave"),
                 ("event",transport._ACTION_ROUTE,"POST","choose:7"),("event",transport._ITEM_DECISION_ROUTE,"GET",None),
                 ("event",transport._ITEM_ACTION_ROUTE,"POST","collect:255")]
        for flow,route,method,action in allowed:
            body,s=self.exchange(flow,route,b"{}",method=method,action=action)
            self.assertEqual(body,bytearray(b"{}"));transport._zero(body)
            self.assertTrue(s.sent[0].startswith((method+" "+route+" HTTP/1.1\r\n").encode()))
        bad=[("shop",transport._ITEM_DECISION_ROUTE,"GET",None),("event",transport._ACTION_ROUTE,"POST","buy:card:0"),
             ("shop",transport._ACTION_ROUTE,"POST","buy:card:32"),("shop",transport._ACTION_ROUTE,"POST","buy:card:00"),
             ("event",transport._ACTION_ROUTE,"POST","choose:8"),("event",transport._ACTION_ROUTE,"POST","choose:00"),
             ("event",transport._ITEM_ACTION_ROUTE,"POST","collect:256"),("event",transport._ITEM_ACTION_ROUTE,"POST","collect:01"),
             ("event",transport._ITEM_ACTION_ROUTE,"GET",None),("shop",transport._DECISION_ROUTE+"?x=1","GET",None)]
        for flow,route,method,action in bad:
            factory=Factory()
            exchange=transport._AuthenticatedExchange(flow,bytearray(TOKEN_BYTES),factory,Clock())
            with self.assertRaises(ValueError):exchange(method,route,None if method=="GET" else "a"*64,action,30)
            self.assertEqual(factory.calls,0)

    def test_route_specific_body_caps_and_fragmentation(self):
        for route,limit in ((transport._DECISION_ROUTE,65536),(transport._ITEM_DECISION_ROUTE,4096)):
            body,_=self.exchange("event",route,b"A"*limit)
            self.assertEqual(len(body),limit);transport._zero(body)
            with self.assertRaises(transport.TransportFailure):self.exchange("event",route,b"A"*(limit+1))
        response=http(b"{}")
        for mutated in (response+b"x",response[:-1],response.replace(b"200 OK",b"201 OK"),
                        response.replace(b"Content-Length: 2",b"Content-Length: 02"),
                        response.replace(b"Content-Length: 2",b"Content-Length: +2"),
                        response.replace(b"Connection: close",b"X-Extra: x\r\nConnection: close"),
                        response.replace(b"\r\n",b"\n"),b"HTTP/1.1 200 OK\r\n"+b"x"*1024):
            with self.assertRaises(transport.TransportFailure):self.exchange("shop",transport._DECISION_ROUTE,b"",wire=mutated)

    def test_each_socket_fault_deadline_and_close_failure(self):
        for phase in ("settimeout","connect","sendall","shutdown","recv","close"):
            for fault in (phase,"late_"+phase):
                with self.subTest(fault=fault):
                    with self.assertRaises(transport.TransportFailure):self.exchange("shop",transport._DECISION_ROUTE,b"{}",fault=fault)

    def test_lost_receipt_never_retries(self):
        for flow in ("shop","event"):
            frames=room_frames(flow)
            sockets=[FakeSocket(chunks(http(frames[0]))),FakeSocket([])]
            token=bytearray(TOKEN_BYTES);timer=Clock();factory=Factory(sockets)
            result=transport._run_with_socket_factory(flow,token,factory,clock=timer,sleep=timer.sleep)
            self.assertEqual(result["status"],"failed");self.assertEqual(result["attempted"],1)
            self.assertEqual(result["accepted"],0);self.assertEqual(factory.calls,2)
            self.assertFalse(any(token))

    def test_deadline_before_connect_and_cancellation_zeroing(self):
        timer=Clock();timer.value=30
        factory=Factory();token=bytearray(TOKEN_BYTES)
        exchange=transport._AuthenticatedExchange("shop",token,factory,timer)
        with self.assertRaises(transport.TransportFailure):exchange("GET",transport._DECISION_ROUTE,None,None,30)
        self.assertEqual(factory.calls,0);transport._zero(token)
        for error in (KeyboardInterrupt(),SystemExit(),GeneratorExit()):
            sock=FakeSocket([error]);token=bytearray(TOKEN_BYTES);timer=Clock()
            with self.assertRaises(type(error)):
                transport._run_with_socket_factory("shop",token,Factory([sock]),clock=timer,sleep=timer.sleep)
            self.assertFalse(any(token));self.assertEqual(sock.close_calls,1)
            self.assertTrue(all(not any(r) for r in sock.requests))

    def test_long_chain_pacing_shares_parent_child_deadline(self):
        timer=Clock();token=bytearray(TOKEN_BYTES)
        sockets=[FakeSocket(chunks(http(b"{}"))) for _ in range(29)]
        factory=Factory(sockets);starts=[]
        def create():
            starts.append(timer.value)
            return factory()
        exchange=transport._AuthenticatedExchange("event",token,create,timer,timer.sleep)
        for index in range(29):
            route=transport._ITEM_DECISION_ROUTE if index==10 else transport._DECISION_ROUTE
            body=exchange("GET",route,None,None,30.0);transport._zero(body)
        self.assertEqual(factory.calls,29)
        self.assertTrue(all(b-a>=0.05-1e-12 for a,b in zip(starts,starts[1:])))
        self.assertLess(timer.value,1.5)
        # Insufficient remaining child/outer budget stops before creating a socket.
        with self.assertRaises(transport.TransportFailure):
            exchange("GET",transport._ITEM_DECISION_ROUTE,None,None,timer.value+0.025)
        self.assertEqual(factory.calls,29);transport._zero(token)

    def test_invalid_credential_no_socket_and_owned_zeroing(self):
        for raw in (b"",b"a"*63,b"AF"*32,b"a"*65):
            token=bytearray(raw);factory=Factory();timer=Clock()
            result=transport._run_with_socket_factory("shop",token,factory,clock=timer,sleep=timer.sleep)
            self.assertEqual(result["status"],"failed");self.assertFalse(any(token));self.assertEqual(factory.calls,0)

if __name__=="__main__":
    result=unittest.TextTestRunner(stream=sys.stderr,verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(TransportTests))
    if result.wasSuccessful():print(json.dumps(dict(schema_version=1,status="passed",suite="room_release_transport",check_count=result.testsRun),separators=(",",":")))
    raise SystemExit(0 if result.wasSuccessful() else 1)
