#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


def _load(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("event_orchestrator_integration_host", path)
    if spec is None or spec.loader is None:
        raise AssertionError("host import")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Exchange:
    def __init__(self, dotnet: str, fixture: Path, module: Any,
                 scenario: str = "sequential") -> None:
        self.module = module
        self.process = subprocess.Popen(
            [dotnet, str(fixture), scenario], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="strict")
        self.calls: list[tuple[str, str]] = []
        self.requests: list[bytearray] = []
        self.responses: list[bytearray] = []
        self.telemetry: list[dict[str, int]] = []

    def request(self, method: str, route: str, body: bytearray | None) -> bytearray:
        self.calls.append((method, route))
        if body is not None:
            self.requests.append(body)
        command = json.dumps({
            "method": method,
            "route": route,
            "body": None if body is None else base64.b64encode(body).decode("ascii"),
        }, separators=(",", ":"))
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise AssertionError("fixture EOF")
        value = json.loads(line)
        if set(value) != {"body", "parent_dispatches", "item_dispatches", "card_dispatches"}:
            raise AssertionError(value)
        self.telemetry.append({key: value[key] for key in value if key != "body"})
        response = bytearray(base64.b64decode(value["body"], validate=True))
        self.responses.append(response)
        return response

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            code = self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            code = self.process.wait(timeout=5)
            raise AssertionError("fixture timeout")
        assert self.process.stderr is not None
        stderr = self.process.stderr.read()
        if code != 0 or stderr:
            raise AssertionError((code, stderr))
        if any(any(buffer) for buffer in self.requests + self.responses):
            raise AssertionError("host buffer not cleared")


def _run(dotnet: str, fixture: Path, host: Any,
         provider: Callable[[Any], str],
         request_wrapper: Callable[[Exchange, str, str, bytearray | None], bytearray] | None = None,
         scenario: str = "sequential",
         ) -> tuple[dict[str, Any], Exchange]:
    exchange = Exchange(dotnet, fixture, host, scenario)
    callback = exchange.request if request_wrapper is None else (
        lambda method, route, body: request_wrapper(exchange, method, route, body))
    result = host.run_event(callback, provider=provider, clock=lambda: 1.0, sleep=lambda _: None)
    exchange.close()
    return result, exchange


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--host", type=Path, required=True)
    args = parser.parse_args()
    host = _load(args.host)
    checks = 0

    result, exchange = _run(args.dotnet, args.fixture, host, host.first_legal)
    expected = {
        "schema_version": 1, "status": "passed",
        "parent_attempted": 3, "parent_accepted": 3,
        "option_transitions_observed": 0, "parent_exits_reconciled": 1,
        "child_episodes_started": 2, "child_episodes_completed": 2,
        "item_episodes_completed": 1, "card_episodes_completed": 1,
        "child_attempted": 3, "child_accepted": 3, "child_reconciled": 3,
    }
    if result != expected:
        raise AssertionError(result)
    if exchange.calls.count(("POST", host.ACTION_ROUTE)) != 6:
        raise AssertionError(exchange.calls)
    if exchange.telemetry[-1] != {
            "parent_dispatches": 3, "item_dispatches": 1, "card_dispatches": 2}:
        raise AssertionError(exchange.telemetry[-1])
    checks += 1

    result, exchange = _run(args.dotnet, args.fixture, host, host.first_legal,
                            scenario="ordinary")
    ordinary = dict(expected)
    ordinary.update(parent_attempted=3, parent_accepted=3,
                    option_transitions_observed=2,
                    child_episodes_started=0, child_episodes_completed=0,
                    item_episodes_completed=0, card_episodes_completed=0,
                    child_attempted=0, child_accepted=0, child_reconciled=0)
    if result != ordinary:
        raise AssertionError(result)
    if exchange.telemetry[-1] != {
            "parent_dispatches": 3, "item_dispatches": 0, "card_dispatches": 0}:
        raise AssertionError(exchange.telemetry[-1])
    checks += 1

    provider_calls = 0
    def invalid_provider(_: Any) -> str:
        nonlocal provider_calls
        provider_calls += 1
        return "choose:7"
    result, exchange = _run(args.dotnet, args.fixture, host, invalid_provider)
    if result["status"] != "failed" or result["code"] != "invalid_provider" or provider_calls != 1:
        raise AssertionError(result)
    if any(method == "POST" for method, _ in exchange.calls):
        raise AssertionError(exchange.calls)
    checks += 1

    def immutable_provider(view: Any) -> str:
        view.payload["status"] = "changed"
        return "choose:0"
    result, exchange = _run(args.dotnet, args.fixture, host, immutable_provider)
    if result["status"] != "failed" or result["code"] != "provider_failed":
        raise AssertionError(result)
    if any(method == "POST" for method, _ in exchange.calls):
        raise AssertionError(exchange.calls)
    checks += 1

    outer_exchange: Exchange | None = None
    def reentrant_provider(_: Any) -> str:
        assert outer_exchange is not None
        nested = host.run_event(outer_exchange.request, provider=host.first_legal,
                                clock=lambda: 1.0, sleep=lambda _: None)
        if nested.get("code") != "reentrant_provider":
            raise AssertionError(nested)
        return "choose:0"
    outer_exchange = Exchange(args.dotnet, args.fixture, host)
    result = host.run_event(outer_exchange.request, provider=reentrant_provider,
                            clock=lambda: 1.0, sleep=lambda _: None)
    outer_exchange.close()
    if result["status"] != "failed" or result["code"] != "reentrant_provider":
        raise AssertionError(result)
    if any(method == "POST" for method, _ in outer_exchange.calls):
        raise AssertionError(outer_exchange.calls)
    checks += 1

    lost = False
    def lose_after_dispatch(exchange: Exchange, method: str, route: str,
                            body: bytearray | None) -> bytearray:
        nonlocal lost
        response = exchange.request(method, route, body)
        if method == "POST" and not lost:
            lost = True
            response[:] = b"\0" * len(response)
            raise host.TransportFailure()
        return response
    result, exchange = _run(args.dotnet, args.fixture, host, host.first_legal,
                            lose_after_dispatch)
    if result["status"] != "failed" or result["code"] != "transport_failure" or not lost:
        raise AssertionError(result)
    if len([call for call in exchange.calls if call[0] == "POST"]) != 1:
        raise AssertionError(exchange.calls)
    checks += 1

    saved_receipt: bytes | None = None
    duplicated = False
    def duplicate_receipt(exchange: Exchange, method: str, route: str,
                          body: bytearray | None) -> bytearray:
        nonlocal saved_receipt, duplicated
        response = exchange.request(method, route, body)
        if method == "POST" and saved_receipt is None:
            saved_receipt = bytes(response)
            return response
        if method == "GET" and saved_receipt is not None and not duplicated:
            duplicated = True
            response[:] = b"\0" * len(response)
            replacement = bytearray(saved_receipt)
            exchange.responses.append(replacement)
            return replacement
        return response
    result, exchange = _run(args.dotnet, args.fixture, host, host.first_legal,
                            duplicate_receipt)
    if result["status"] != "failed" or result["code"] != "invalid_response" or not duplicated:
        raise AssertionError(result)
    if len([call for call in exchange.calls if call[0] == "POST"]) != 1:
        raise AssertionError(exchange.calls)
    checks += 1

    mutated = False
    def stale_child(exchange: Exchange, method: str, route: str,
                    body: bytearray | None) -> bytearray:
        nonlocal mutated
        if method == "POST" and body is not None:
            value = json.loads(body)
            child = value["child"]
            if child is not None and not mutated:
                child["child_ordinal"] += 1
                replacement = bytearray(json.dumps(value, separators=(",", ":")).encode("ascii"))
                try:
                    response = exchange.request(method, route, replacement)
                finally:
                    replacement[:] = b"\0" * len(replacement)
                mutated = True
                return response
        return exchange.request(method, route, body)
    result, exchange = _run(args.dotnet, args.fixture, host, host.first_legal, stale_child)
    if result["status"] != "failed" or result["code"] != "invalid_response" or not mutated:
        raise AssertionError(result)
    if exchange.telemetry[-1]["item_dispatches"] != 0:
        raise AssertionError(exchange.telemetry[-1])
    checks += 1

    changed = False
    def noncanonical_outer(exchange: Exchange, method: str, route: str,
                           body: bytearray | None) -> bytearray:
        nonlocal changed
        response = exchange.request(method, route, body)
        if not changed:
            changed = True
            replacement = bytearray(b"{ " + response[1:])
            response[:] = b"\0" * len(response)
            exchange.responses.append(replacement)
            return replacement
        return response
    result, exchange = _run(args.dotnet, args.fixture, host, host.first_legal,
                            noncanonical_outer)
    if result["status"] != "failed" or result["code"] != "invalid_response" or not changed:
        raise AssertionError(result)
    if any(method == "POST" for method, _ in exchange.calls):
        raise AssertionError(exchange.calls)
    checks += 1

    print(json.dumps({"schema_version": 1, "status": "passed",
                      "suite": "event_orchestrator_v1_integration",
                      "check_count": checks}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
