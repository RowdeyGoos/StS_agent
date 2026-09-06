#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any, Callable


def _load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location('event_card_operations_integration_host', path)
    if spec is None or spec.loader is None:
        raise AssertionError('host import')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Exchange:
    def __init__(self, dotnet: str, fixture: Path, scenario: str) -> None:
        self.process = subprocess.Popen(
            [dotnet, str(fixture), scenario], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding='utf-8', errors='strict')
        self.calls: list[tuple[str, str]] = []
        self.requests: list[bytearray] = []
        self.responses: list[bytearray] = []
        self.telemetry: list[dict[str, int]] = []

    def request(self, method: str, route: str, body: bytearray | None) -> bytearray:
        self.calls.append((method, route))
        if body is not None:
            self.requests.append(body)
        command = json.dumps({
            'method': method,
            'route': route,
            'body': None if body is None else base64.b64encode(body).decode('ascii'),
        }, separators=(',', ':'))
        if self.process.stdin is None or self.process.stdout is None:
            raise AssertionError('fixture pipes')
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise AssertionError('fixture EOF')
        value = json.loads(line)
        if tuple(value) != ('body', 'parent_dispatches', 'item_dispatches',
                            'card_dispatches', 'disposed_children'):
            raise AssertionError(value)
        self.telemetry.append({key: value[key] for key in value if key != 'body'})
        response = bytearray(base64.b64decode(value['body'], validate=True))
        self.responses.append(response)
        return response

    def close(self, expected_code: int = 0) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            code = self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
            raise AssertionError('fixture timeout')
        if self.process.stderr is None:
            raise AssertionError('stderr pipe')
        stderr = self.process.stderr.read()
        if code != expected_code or stderr:
            raise AssertionError((code, stderr))
        if any(any(buffer) for buffer in self.requests + self.responses):
            raise AssertionError('host buffer not cleared')


def _policies(host: ModuleType) -> dict[str, Any]:
    return {
        'fixture_add_three': host._CardPolicy(
            'FIXTURE.ADD', 'add', 3, 3, 'auto_at_max', 6, 6),
        'fixture_remove_two': host._CardPolicy(
            'FIXTURE.REMOVE', 'remove', 2, 2, 'preview_confirm', 5, 5),
        'fixture_upgrade_two': host._CardPolicy(
            'FIXTURE.UPGRADE', 'upgrade', 2, 2, 'preview_confirm', 5, 5),
        'fixture_transform_two': host._CardPolicy(
            'FIXTURE.TRANSFORM', 'transform', 2, 2, 'preview_confirm', 5, 5),
    }


def _run(dotnet: str, fixture: Path, host: ModuleType, scenario: str,
         provider: Callable[[Any], str], wrapper: Callable | None = None
         ) -> tuple[dict[str, Any], Exchange]:
    exchange = Exchange(dotnet, fixture, scenario)
    request = exchange.request if wrapper is None else (
        lambda method, route, body: wrapper(exchange, method, route, body))
    result = host._run_with_catalog(
        request, provider=provider, clock=lambda: 1.0, sleep=lambda _: None,
        policies=_policies(host))
    exchange.close()
    return result, exchange


def _expected(**updates: int | str) -> dict[str, Any]:
    value: dict[str, Any] = {
        'schema_version': 1, 'status': 'passed',
        'parent_attempted': 5, 'parent_accepted': 5,
        'option_transitions_observed': 0, 'parent_exits_reconciled': 1,
        'child_episodes_started': 4, 'child_episodes_completed': 4,
        'item_episodes_completed': 0, 'card_episodes_completed': 4,
        'child_attempted': 15, 'child_accepted': 15, 'child_reconciled': 15,
    }
    value.update(updates)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dotnet', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--host', type=Path, required=True)
    args = parser.parse_args()
    host = _load(args.host)
    checks = 0

    result, exchange = _run(args.dotnet, args.fixture, host, 'all_cards', host.first_legal)
    if result != _expected():
        raise AssertionError(result)
    if exchange.calls.count(('POST', host.ACTION_ROUTE)) != 20:
        raise AssertionError(exchange.calls)
    if exchange.telemetry[-1] != {
            'parent_dispatches': 5, 'item_dispatches': 0,
            'card_dispatches': 15, 'disposed_children': 4}:
        raise AssertionError(exchange.telemetry[-1])
    checks += 1

    result, exchange = _run(args.dotnet, args.fixture, host, 'mixed', host.first_legal)
    if result != _expected(
            parent_attempted=4, parent_accepted=4,
            option_transitions_observed=1,
            child_episodes_started=2, child_episodes_completed=2,
            item_episodes_completed=1, card_episodes_completed=1,
            child_attempted=4, child_accepted=4, child_reconciled=4):
        raise AssertionError(result)
    if exchange.calls.count(('POST', host.ACTION_ROUTE)) != 8:
        raise AssertionError(exchange.calls)
    if exchange.telemetry[-1] != {
            'parent_dispatches': 4, 'item_dispatches': 1,
            'card_dispatches': 3, 'disposed_children': 1}:
        raise AssertionError(exchange.telemetry[-1])
    checks += 1

    provider_calls = 0
    def invalid_provider(_: Any) -> str:
        nonlocal provider_calls
        provider_calls += 1
        return 'choose:7'
    result, exchange = _run(args.dotnet, args.fixture, host, 'all_cards', invalid_provider)
    if result.get('code') != 'invalid_provider' or provider_calls != 1 or any(
            method == 'POST' for method, _ in exchange.calls):
        raise AssertionError((result, exchange.calls))
    checks += 1

    def mutating_provider(view: Any) -> str:
        view.payload['status'] = 'changed'
        return 'choose:0'
    result, exchange = _run(args.dotnet, args.fixture, host, 'all_cards', mutating_provider)
    if result.get('code') != 'provider_failed' or any(
            method == 'POST' for method, _ in exchange.calls):
        raise AssertionError((result, exchange.calls))
    checks += 1

    outer: Exchange | None = None
    def reentrant_provider(_: Any) -> str:
        if outer is None:
            raise AssertionError('outer')
        nested = host._run_with_catalog(
            outer.request, provider=host.first_legal, clock=lambda: 1.0,
            sleep=lambda _: None, policies=_policies(host))
        if nested.get('code') != 'reentrant_provider':
            raise AssertionError(nested)
        return 'choose:0'
    outer = Exchange(args.dotnet, args.fixture, 'all_cards')
    result = host._run_with_catalog(
        outer.request, provider=reentrant_provider, clock=lambda: 1.0,
        sleep=lambda _: None, policies=_policies(host))
    outer.close()
    if result.get('code') != 'reentrant_provider' or any(
            method == 'POST' for method, _ in outer.calls):
        raise AssertionError((result, outer.calls))
    checks += 1

    lost = False
    def lose_first_post(exchange: Exchange, method: str, route: str,
                        body: bytearray | None) -> bytearray:
        nonlocal lost
        response = exchange.request(method, route, body)
        if method == 'POST' and not lost:
            lost = True
            response[:] = b'\0' * len(response)
            raise host.TransportFailure()
        return response
    result, exchange = _run(args.dotnet, args.fixture, host, 'all_cards',
                            host.first_legal, lose_first_post)
    if (result.get('code') != 'transport_failure' or not lost or
            exchange.telemetry[-1]['parent_dispatches'] != 1 or
            sum(method == 'POST' for method, _ in exchange.calls) != 1):
        raise AssertionError((result, exchange.telemetry, exchange.calls))
    checks += 1

    stale_sent = False
    def stale_receipt(exchange: Exchange, method: str, route: str,
                      body: bytearray | None) -> bytearray:
        nonlocal stale_sent
        if method == 'POST' and not stale_sent:
            stale_sent = True
            if body is None:
                raise AssertionError('body')
            value = json.loads(body)
            value['decision_id'] = 'f' * 64
            body[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
        return exchange.request(method, route, body)
    result, exchange = _run(args.dotnet, args.fixture, host, 'all_cards',
                            host.first_legal, stale_receipt)
    if (result.get('code') != 'invalid_response' or not stale_sent or
            exchange.telemetry[-1]['parent_dispatches'] != 0 or
            sum(method == 'POST' for method, _ in exchange.calls) != 1):
        raise AssertionError((result, exchange.telemetry, exchange.calls))
    checks += 1

    receipt_changed = False
    def wrong_receipt(exchange: Exchange, method: str, route: str,
                      body: bytearray | None) -> bytearray:
        nonlocal receipt_changed
        response = exchange.request(method, route, body)
        if method == 'POST' and not receipt_changed:
            receipt_changed = True
            value = json.loads(response)
            value['payload']['decision_id'] = 'e' * 64
            response[:] = json.dumps(value, ensure_ascii=True,
                                      separators=(',', ':')).encode('ascii')
        return response
    result, exchange = _run(args.dotnet, args.fixture, host, 'all_cards',
                            host.first_legal, wrong_receipt)
    if (result.get('code') != 'invalid_response' or not receipt_changed or
            exchange.telemetry[-1]['parent_dispatches'] != 1 or
            sum(method == 'POST' for method, _ in exchange.calls) != 1):
        raise AssertionError((result, exchange.telemetry, exchange.calls))
    checks += 1

    child_context_changed = False
    post_count = 0
    def wrong_child_context(exchange: Exchange, method: str, route: str,
                            body: bytearray | None) -> bytearray:
        nonlocal child_context_changed, post_count
        if method == 'POST':
            post_count += 1
        if method == 'POST' and post_count == 2:
            if body is None:
                raise AssertionError('child body')
            value = json.loads(body)
            if value['child'] is None:
                raise AssertionError('child context')
            child_context_changed = True
            value['child']['parent_decision_id'] = 'd' * 64
            body[:] = json.dumps(value, separators=(',', ':')).encode('ascii')
        return exchange.request(method, route, body)
    result, exchange = _run(args.dotnet, args.fixture, host, 'all_cards',
                            host.first_legal, wrong_child_context)
    if (result.get('code') != 'invalid_response' or not child_context_changed or
            exchange.telemetry[-1]['parent_dispatches'] != 1 or
            exchange.telemetry[-1]['card_dispatches'] != 0 or post_count != 2):
        raise AssertionError((result, exchange.telemetry, exchange.calls))
    checks += 1

    print(json.dumps({'schema_version': 1, 'status': 'passed',
                      'suite': 'event_card_operations_v1_integration',
                      'check_count': checks}, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
