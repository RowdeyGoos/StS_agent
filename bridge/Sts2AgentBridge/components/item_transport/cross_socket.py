"""Actual synthetic C# loopback -> production Python transport/host gate."""
from __future__ import annotations

import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time

from components.item_transport.transport.item_transport import _run_with_socket_factory

_FIXED_ENDPOINT = ("127.0.0.1", 43117)
_SYNTHETIC_TOKEN = b"b" * 64


def _zero(value: bytearray) -> None:
    value[:] = b"\0" * len(value)


class Fixture:
    def __init__(self, dotnet: Path, assembly: Path, scenario: str) -> None:
        self.process = subprocess.Popen(
            [str(dotnet), str(assembly), "--fixture", scenario],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.stats: dict[str, object] = {}
        metadata = bytearray()
        try:
            assert self.process.stdout is not None
            limit = time.monotonic() + 5
            while not metadata.endswith(b"\n"):
                remaining = limit - time.monotonic()
                assert remaining > 0 and select.select([self.process.stdout], [], [], remaining)[0]
                block = os.read(self.process.stdout.fileno(), 65 - len(metadata))
                assert block, "fixture closed before publication"
                metadata.extend(block)
                assert len(metadata) <= 64
            value = json.loads(metadata)
            assert tuple(value) == ("port",) and type(value["port"]) is int
            assert 1 <= value["port"] <= 65535 and value["port"] != _FIXED_ENDPOINT[1]
            self.endpoint = ("127.0.0.1", value["port"])
        except BaseException:
            self._cleanup_child(preserve_failure=True)
            raise
        finally:
            _zero(metadata)

    def _cleanup_child(self, *, preserve_failure: bool) -> None:
        failure: BaseException | None = None
        try:
            if self.process.poll() is None:
                self.process.kill()
        except BaseException as error:
            failure = error
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except BaseException as error:
                    if failure is None:
                        failure = error
        try:
            self.process.wait(timeout=5)
        except BaseException as error:
            if failure is None:
                failure = error
        if failure is not None and not preserve_failure:
            raise failure from None

    def close(self) -> None:
        try:
            assert self.process.stdin is not None
            self.process.stdin.close()
            self.process.stdin = None
            stdout, stderr = self.process.communicate(timeout=5)
            assert self.process.returncode == 0 and not stdout, "fixture shutdown failure"
            stats = json.loads(stderr)
            assert tuple(stats) == ("dispatch_count", "last_action_index", "read_count", "stopped")
            assert all(type(stats[key]) is int for key in tuple(stats)[:3])
            assert stats["stopped"] is True
            self.stats = stats
        finally:
            self._cleanup_child(preserve_failure=sys.exc_info()[0] is not None)


class RedirectSocket:
    """Test-only redirector; production still asks for its fixed endpoint."""
    def __init__(self, factory: SocketFactory) -> None:
        self.factory = factory
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.requests: list[bytearray] = []
        self.pending = bytearray()
        self.loaded = False
        self.post = False
        self.closed = False
        self.half_closed = False
        self.send_count = 0

    def settimeout(self, value: float) -> None:
        self.socket.settimeout(value)

    def connect(self, endpoint: tuple[str, int]) -> None:
        assert endpoint == _FIXED_ENDPOINT
        self.socket.connect(self.factory.endpoint)

    def sendall(self, request: bytearray) -> None:
        assert type(request) is bytearray and self.send_count == 0
        self.send_count += 1
        self.requests.append(request)
        self.post = request.startswith(b"POST ")
        self.factory.methods.append("POST" if self.post else "GET")
        if self.factory.mode == "origin":
            altered = request.replace(b"Connection: close\r\n", b"Origin: https://synthetic.invalid\r\nConnection: close\r\n")
            try:
                self.socket.sendall(altered)
            finally:
                _zero(altered)
        else:
            self.socket.sendall(request)
            if self.factory.mode == "trailing":
                # The complete valid head arrives before this extra byte. The
                # server must await EOF rather than dispatch at the terminator.
                time.sleep(0.02)
                self.socket.sendall(b"X")

    def shutdown(self, how: int) -> None:
        assert how == socket.SHUT_WR and not self.half_closed
        self.half_closed = True
        self.socket.shutdown(how)

    def recv(self, maximum: int) -> bytes:
        assert 1 <= maximum <= 1024 and self.half_closed
        if self.factory.mode == "lost" and self.post:
            value = self.socket.recv(maximum)
            if value:
                raise OSError("synthetic lost receipt")
            return value
        if self.factory.mode not in ("header", "body"):
            return self.socket.recv(maximum)
        if not self.loaded:
            self.loaded = True
            while True:
                value = self.socket.recv(1024)
                if not value:
                    break
                self.pending.extend(value)
                assert len(self.pending) <= 5120
            if self.factory.mode == "header":
                self.pending[:] = self.pending.replace(b"Content-Length:", b"content-length:", 1)
            else:
                split = self.pending.index(b"\r\n\r\n") + 4
                parsed = json.loads(self.pending[split:])
                parsed["private_canary"] = "SYNTHETIC_ONLY"
                body = bytearray(json.dumps(parsed, separators=(",", ":")).encode("ascii"))
                try:
                    head = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: " +
                            str(len(body)).encode("ascii") + b"\r\nCache-Control: no-store\r\n" +
                            b"X-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n")
                    self.pending[:] = head + body
                finally:
                    _zero(body)
        result = bytes(self.pending[:maximum])
        del self.pending[:maximum]
        return result

    def close(self) -> None:
        assert not self.closed
        self.closed = True
        try:
            self.socket.close()
        finally:
            _zero(self.pending)


class SocketFactory:
    def __init__(self, endpoint: tuple[str, int], mode: str = "normal") -> None:
        self.endpoint = endpoint
        self.mode = mode
        self.sockets: list[RedirectSocket] = []
        self.methods: list[str] = []

    def __call__(self) -> RedirectSocket:
        value = RedirectSocket(self)
        self.sockets.append(value)
        return value

    def verify(self) -> None:
        assert all(value.closed and value.half_closed and value.send_count == 1 for value in self.sockets)
        assert all(not any(request) for value in self.sockets for request in value.requests)
        assert all(not any(value.pending) for value in self.sockets)


def _invoke(factory: SocketFactory, wrong_credential: bool = False) -> dict[str, object]:
    credential = bytearray(b"a" * 64 if wrong_credential else _SYNTHETIC_TOKEN)
    try:
        return _run_with_socket_factory(credential, factory, clock=time.monotonic, sleep=time.sleep)
    finally:
        assert not any(credential), "transport retained synthetic credential"
        factory.verify()


def _case(dotnet: Path, assembly: Path, scenario: str, *, code: str | None = None,
          mode: str = "normal", wrong_credential: bool = False,
          second_controller: bool = False) -> tuple[dict[str, object], dict[str, object], list[str]]:
    fixture = Fixture(dotnet, assembly, scenario)
    factory = SocketFactory(fixture.endpoint, mode)
    try:
        result = _invoke(factory, wrong_credential)
        if code is None:
            assert result["status"] == "passed" and result["attempted"] == result["accepted"] == result["reconciled"] == 1
        else:
            assert result == {"schema_version": 1, "status": "failed", "code": code}, result
        if second_controller:
            assert _invoke(factory) == {"schema_version": 1, "status": "failed", "code": "invalid_response"}
    finally:
        fixture.close()
    assert factory.methods.count("POST") <= 1 and fixture.stats["dispatch_count"] <= 1
    return result, fixture.stats, factory.methods


def run_cross_socket(dotnet: Path, assembly: Path) -> dict[str, int]:
    count = 0
    for scenario, index, kind in (("potion_success", 3, "potion"), ("relic_success", 7, "relic"),
                                  ("delayed", 5, "potion"), ("overlay_closed", 9, "relic"),
                                  ("bounds_ready", 248, "relic")):
        result, stats, methods = _case(dotnet, assembly, scenario)
        assert result["item_kind"] == kind and stats["dispatch_count"] == 1
        assert stats["last_action_index"] == index and methods.count("POST") == 1
        assert stats["read_count"] == methods.count("GET") >= 2
        count += 1
    for scenario, code, dispatches in (("full_belt", "unsupported_state", 0),
                                        ("stale", "unsupported_state", 0),
                                        ("uncertain", "action_uncertain", 1)):
        _, stats, _ = _case(dotnet, assembly, scenario, code=code)
        assert stats["dispatch_count"] == dispatches and stats["read_count"] == 1
        count += 1
    for mode, wrong in (("normal", True), ("origin", False), ("trailing", False)):
        _, stats, methods = _case(dotnet, assembly, "relic_success", code="transport_failure",
                                  mode=mode, wrong_credential=wrong)
        assert stats["dispatch_count"] == stats["read_count"] == 0 and methods == ["GET"]
        count += 1
    for mode, code, dispatches in (("lost", "transport_failure", 1),
                                    ("header", "transport_failure", 0),
                                    ("body", "invalid_response", 0)):
        result, stats, methods = _case(dotnet, assembly, "relic_success", code=code, mode=mode)
        assert stats["dispatch_count"] == dispatches and stats["read_count"] == 1
        assert methods == (["GET", "POST"] if dispatches else ["GET"])
        assert "SYNTHETIC_ONLY" not in json.dumps(result)
        count += 1
    _, stats, methods = _case(dotnet, assembly, "relic_success", second_controller=True)
    assert stats["dispatch_count"] == methods.count("POST") == 1 and stats["read_count"] == 3
    count += 1
    return {"case_count": count, "scenario_count": 8, "fixed_port_connections": 0}
