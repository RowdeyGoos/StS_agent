from __future__ import annotations
import json
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT / "transport"))
import diagnostic_transport as transport
TOKEN_BYTES = b"0123456789abcdef" * 4
READY = b'{"schema_version":1,"status":"passed","shop_status":"ready","stage":"complete","reason":"none"}'
def http(body):
    return (b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: "+
            str(len(body)).encode("ascii")+b"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n"+body)

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
    def run_one(self, body=READY, *, wire=None, fault=None, events=None):
        timer=Clock()
        sock=FakeSocket(chunks(http(body) if wire is None else wire) if events is None else events, fault, timer)
        token=bytearray(TOKEN_BYTES); factory=Factory([sock])
        result=transport._run_with_socket_factory(token,factory,clock=timer)
        self.assertFalse(any(token)); self.assertLessEqual(factory.calls,1)
        if factory.calls: self.assertEqual(sock.close_calls,1)
        self.assertTrue(all(not any(request) for request in sock.requests))
        return result,sock,factory

    def test_one_exact_get(self):
        result,sock,factory=self.run_one()
        self.assertEqual(result,json.loads(READY)); self.assertEqual(factory.calls,1)
        self.assertEqual(sock.endpoint,("127.0.0.1",43117))
        self.assertEqual(sock.shutdown_how,socket.SHUT_WR)
        self.assertEqual(sock.sent,[b"GET /probe/shop-diagnostic-v1/public/diagnostic HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "+TOKEN_BYTES+b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"])

    def test_invalid_credential_no_socket(self):
        for value in (b"",b"a"*63,b"a"*65,b"A"*64,b"g"*64,b"a"*63+b"\n"):
            token=bytearray(value); factory=Factory()
            result=transport._run_with_socket_factory(token,factory,clock=Clock())
            self.assertEqual(result["status"],"failed"); self.assertEqual(factory.calls,0); self.assertFalse(any(token))

    def test_strict_record_rejection(self):
        mutations=[READY+b"\n",READY.replace(b'"schema_version":1',b'"schema_version":true'),
                   READY.replace(b'"stage":"complete"',b'"stage":"SYNTHETIC_CANARY"'),
                   READY.replace(b'"shop_status":"ready"',b'"shop_status":"unsupported"'),
                   READY.replace(b'"none"',b'"cost_text_invalid"'),
                   READY.replace(b'"reason":"none"',b'"reason":"none","reason":"none"'),
                   READY.replace(b'"reason":"none"',b'"extra":"canary","reason":"none"'),
                   READY.replace(b'"status":"passed","shop_status":"ready"',b'"shop_status":"ready","status":"passed"'),
                   b"null",b"[]",b'{}',b"NaN",b"\xff",b"X"*513]
        for value in mutations:
            result,_,_=self.run_one(value)
            self.assertEqual(result["status"],"failed"); self.assertNotIn("CANARY",str(result))

    def test_exact_response_framing(self):
        original=http(READY)
        changes=[original+b"x",original[:-1],original.replace(b"200 OK",b"201 OK"),
                 original.replace(b"Content-Length: ",b"Content-Length: 0"),
                 original.replace(b"Connection: close",b"X-Extra: canary\r\nConnection: close"),
                 original.replace(b"\r\n",b"\n"),b"HTTP/1.1 200 OK\r\n"+b"X"*1024]
        for wire in changes:
            result,_,_=self.run_one(wire=wire);self.assertEqual(result["status"],"failed")
        result,_,_=self.run_one(events=[bytes([b]) for b in original])
        self.assertEqual(result,json.loads(READY))

    def test_socket_faults_and_deadlines(self):
        for phase in ("settimeout","connect","sendall","shutdown","recv","close"):
            for fault in (phase,"late_"+phase):
                result,_,factory=self.run_one(fault=fault)
                self.assertEqual(result["status"],"failed");self.assertEqual(factory.calls,1)
                self.assertNotIn("CANARY",str(result))

    def test_lost_delivery_never_retries(self):
        for wire in (b"",http(READY)[:-7]):
            result,sock,factory=self.run_one(wire=wire)
            self.assertEqual(result["status"],"failed"); self.assertEqual(len(sock.sent),1);self.assertEqual(factory.calls,1)

    def test_interruption_zeroing(self):
        for exc in (KeyboardInterrupt(),SystemExit(),GeneratorExit()):
            timer=Clock();sock=FakeSocket([exc],clock=timer);token=bytearray(TOKEN_BYTES);factory=Factory([sock])
            with self.assertRaises(type(exc)):transport._run_with_socket_factory(token,factory,clock=timer)
            self.assertFalse(any(token));self.assertEqual(sock.close_calls,1)
            self.assertTrue(all(not any(r) for r in sock.requests)); self.assertEqual(factory.calls,1)

    def test_every_allowed_record_and_impossible_success(self):
        from diagnostic_values import ALLOWED_RESULTS
        for shop_status,stage,reason in ALLOWED_RESULTS:
            value={"schema_version":1,"status":"passed","shop_status":shop_status,"stage":stage,"reason":reason}
            body=json.dumps(value,separators=(",",":"),ensure_ascii=True).encode("ascii")
            result,_,_=self.run_one(body);self.assertEqual(result,value)
            self.assertLessEqual(len(body),512)
        with self.assertRaises(ValueError):transport._parse_record(bytearray(READY.replace(b'"none"',b'"native_exception"')))

if __name__ == "__main__":
    result=unittest.TextTestRunner(stream=sys.stderr,verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(TransportTests))
    if result.wasSuccessful():print(json.dumps({"schema_version":1,"status":"passed","suite":"shop_diagnostic_transport","check_count":result.testsRun},separators=(",",":")))
    raise SystemExit(0 if result.wasSuccessful() else 1)
