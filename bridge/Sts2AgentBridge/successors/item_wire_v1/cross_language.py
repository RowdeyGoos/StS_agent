"""Synthetic-only actual C# core/wire -> Python controller integration gate."""
from __future__ import annotations

import json
import os
from pathlib import Path
import select
import subprocess
import time
from typing import Callable

from host.item_host import TransportFailure, run_collection


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def sleep(self, delay: float) -> None:
        assert 0 <= delay <= 0.1
        self.value += delay


def _zero(buffer: bytearray) -> None:
    buffer[:] = b"\0" * len(buffer)


class FixtureExchange:
    def __init__(self, dotnet: Path, assembly: Path, scenario: str,
                 transform: Callable[[str, bytearray], bytearray] | None = None) -> None:
        self.process = subprocess.Popen(
            [str(dotnet), str(assembly), "--fixture", scenario],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.transform = transform
        self.methods: list[str] = []
        # These retained buffers contain only synthetic fixture values. Their
        # contents must be zero after the production host consumes them.
        self.returned: list[bytearray] = []
        self.max_body_bytes = 0
        self.stats: dict[str, int] = {}
        self.transcript: list[dict[str, object]] = []

    def __call__(self, method: str, route: str, decision_id: str | None,
                 action_id: str | None, deadline: float) -> bytearray:
        assert deadline >= 0
        command = dict(method=method, route=route, decision_id=decision_id,
                       action_id=action_id)
        self.methods.append(method)
        assert self.process.stdin is not None and self.process.stdout is not None
        request = json.dumps(command, separators=(",", ":")).encode("ascii") + b"\n"
        assert len(request) <= 512
        self.process.stdin.write(request)
        self.process.stdin.flush()
        collected = bytearray()
        result: bytearray | None = None
        timeout = time.monotonic() + 5.0
        try:
            while b"\n" not in collected:
                remaining = timeout - time.monotonic()
                if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                    raise AssertionError("synthetic producer did not return a bounded line")
                chunk = os.read(self.process.stdout.fileno(), 4098 - len(collected))
                if not chunk:
                    raise AssertionError("synthetic producer closed without response")
                collected.extend(chunk)
                if len(collected) > 4097:
                    raise AssertionError("synthetic body bound exceeded")
            if collected.count(b"\n") != 1 or not collected.endswith(b"\n"):
                raise AssertionError("synthetic framing mismatch")
            result = collected[:-1]
            self.max_body_bytes = max(self.max_body_bytes, len(result))
            self.transcript.append({"request": command, "body": result.decode("ascii")})
            if self.transform is not None:
                replacement = self.transform(method, result)
                if replacement is not result:
                    _zero(result)
                    result = replacement
            self.returned.append(result)
            return result
        except BaseException:
            if result is not None:
                _zero(result)
            raise
        finally:
            _zero(collected)

    def close(self) -> None:
        try:
            assert self.process.stdin is not None
            self.process.stdin.close()
            self.process.stdin = None
            stdout, stderr = self.process.communicate(timeout=5)
            assert self.process.returncode == 0 and not stdout, "synthetic producer exit mismatch"
            self.stats = json.loads(stderr)
            assert tuple(self.stats) == ("dispatch_count", "last_action_index", "read_count")
            assert all(type(value) is int for value in self.stats.values())
            assert self.stats["read_count"] == self.methods.count("GET")
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            assert all(not any(buffer) for buffer in self.returned), "host retained response bytes"


def _run_case(dotnet: Path, assembly: Path, scenario: str,
              expected_code: str | None = None,
              transform: Callable[[str, bytearray], bytearray] | None = None,
              clock: Clock | None = None) -> tuple[dict[str, object], FixtureExchange]:
    timer = clock or Clock()
    exchange = FixtureExchange(dotnet, assembly, scenario, transform)
    try:
        result = run_collection(exchange, clock=timer.now, sleep=timer.sleep)
    finally:
        exchange.close()
    assert result["status"] == ("passed" if expected_code is None else "failed"), result
    if expected_code is None:
        assert result["attempted"] == result["accepted"] == result["reconciled"] == 1
        assert exchange.methods.count("POST") == exchange.stats["dispatch_count"] == 1
        assert exchange.stats["last_action_index"] >= 0
    else:
        assert result == {"schema_version": 1, "status": "failed", "code": expected_code}, result
        assert exchange.methods.count("POST") <= 1 and exchange.stats["dispatch_count"] <= 1
    return result, exchange


def run_cross_language(dotnet: Path, assembly: Path, vector_path: Path) -> dict[str, int]:
    cases = 0
    positive: dict[str, FixtureExchange] = {}
    for scenario in ("potion_success", "relic_success", "delayed", "overlay_closed"):
        result, exchange = _run_case(dotnet, assembly, scenario)
        if scenario in ("potion_success", "relic_success"):
            assert result["item_kind"] == scenario.split("_")[0]
        positive[scenario] = exchange
        cases += 1
    for scenario, code, dispatches in (
        ("full_belt", "unsupported_state", 0),
        ("stale", "unsupported_state", 0),
        ("uncertain", "action_uncertain", 1),
    ):
        _, exchange = _run_case(dotnet, assembly, scenario, code)
        assert exchange.stats["dispatch_count"] == dispatches
        assert exchange.methods.count("GET") == 1
        cases += 1

    def mutated(kind: str) -> Callable[[str, bytearray], bytearray]:
        def transform(method: str, body: bytearray) -> bytearray:
            if kind == "duplicate":
                return bytearray(b'{"schema_version":1,' + body[1:])
            if kind == "protocol":
                return body.replace(b'"item_probe_v1"', b'"item_probe_v0"', 1)
            if kind == "whitespace":
                return body.replace(b":", b": ", 1)
            value = json.loads(body)
            if kind == "canary":
                value["private_identity"] = "SYNTHETIC_PRIVATE_CANARY"
            elif kind == "digest":
                value["decision_id"] = "0" * 64
            elif kind == "receipt" and method == "POST":
                value["decision_id"] = "0" * 64
            elif kind == "receipt":
                return body
            return bytearray(json.dumps(value, separators=(",", ":")).encode("ascii"))
        return transform

    for kind in ("duplicate", "protocol", "whitespace", "canary", "digest", "receipt"):
        result, exchange = _run_case(dotnet, assembly, "relic_success", "invalid_response", mutated(kind))
        assert "CANARY" not in json.dumps(result)
        assert exchange.stats["dispatch_count"] == (1 if kind == "receipt" else 0)
        cases += 1

    timer = Clock()
    def late_receipt(method: str, body: bytearray) -> bytearray:
        if method == "POST":
            timer.value += 16
        return body
    _, exchange = _run_case(dotnet, assembly, "relic_success", "deadline_exceeded", late_receipt, timer)
    assert exchange.methods == ["GET", "POST"] and exchange.stats["dispatch_count"] == 1
    cases += 1

    def lost_receipt(method: str, body: bytearray) -> bytearray:
        if method == "POST":
            raise TransportFailure("SYNTHETIC_EXCEPTION_CANARY")
        return body
    _, exchange = _run_case(dotnet, assembly, "relic_success", "transport_failure", lost_receipt)
    assert exchange.methods == ["GET", "POST"] and exchange.stats["dispatch_count"] == 1
    cases += 1

    exchange = FixtureExchange(dotnet, assembly, "relic_success")
    timer = Clock()
    try:
        assert run_collection(exchange, clock=timer.now, sleep=timer.sleep)["status"] == "passed"
        result = run_collection(exchange, clock=timer.now, sleep=timer.sleep)
        assert result == {"schema_version": 1, "status": "failed", "code": "invalid_response"}
    finally:
        exchange.close()
    assert exchange.stats["dispatch_count"] == 1 and exchange.methods.count("POST") == 1
    cases += 1

    _, maximum = _run_case(dotnet, assembly, "bounds_ready")
    assert maximum.max_body_bytes == 2890
    # Even the impossible combination of all longer potion/false offers plus
    # eight legal actions is bounded at 2906 bytes; every valid ready is shorter.
    upper = json.loads(maximum.transcript[0]["body"])
    for offer in upper["offers"]:
        offer["kind"], offer["enabled"] = "potion", False
    assert len(json.dumps(upper, separators=(",", ":")).encode("ascii")) == 2906 < 4096
    cases += 1
    vectors = json.loads(vector_path.read_text(encoding="ascii"))
    actual = {name: positive[name].transcript for name in ("potion_success", "relic_success")}
    actual["bounds_ready"] = maximum.transcript
    assert vectors == {"schema_version": 1, "evidence": "synthetic_core_wire", "cases": actual}, \
        "literal producer/controller vector mismatch"
    return {"case_count": cases, "maximum_response_body_bytes": maximum.max_body_bytes,
            "conservative_ready_bound_bytes": 2906}
