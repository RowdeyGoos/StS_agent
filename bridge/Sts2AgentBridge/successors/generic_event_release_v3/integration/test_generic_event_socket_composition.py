#!/usr/bin/env python3
"""Actual C# runtime + frozen Python host on synthetic ephemeral loopback only."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import selectors
import socket
import subprocess
import sys
import time
from unittest import mock

ROOT = Path(__file__).absolute().parents[1]
sys.path[:0] = [str(ROOT / 'transport'), str(ROOT.parent)]
import generic_event_transport as transport

# Exact counts follow the fixed inert sequence: one read before each action,
# one after it, plus one parent-resume read per delivered child resolution.
EXPECTED = {
    'FOREST_ARCHIVE': (3, 3, 8, 1), 'removal_fixed': (3, 3, 8, 1),
    'reward_auto_fixed': (3, 2, 7, 1), 'reward_explicit_fixed': (3, 3, 8, 1),
    'mixed_three': (4, 9, 17, 3),
    'provider_throw': (3, 3, 8, 1), 'provider_invalid': (3, 3, 8, 1),
    'native_normal': (2, 2, 6, 1), 'native_selector_release': (2, 2, 7, 1),
    'native_binding_wait': (1, 0, 258, 0), 'native_selector_wait': (1, 0, 258, 0),
    'native_unsupported': (1, 0, 2, 0),
    'lost_parent': (1, 0, 1, 0), 'lost_auto': (1, 2, 3, 1), 'lost_explicit': (1, 3, 4, 1),
}


def read_ready(process):
    assert process.stdout is not None
    result = bytearray()
    deadline = time.monotonic() + 5
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while not result.endswith(b'\n'):
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise ValueError('fixture_readiness_timeout')
                value = process.stdout.read(1)
                if not value or len(result) >= 128:
                    raise ValueError('fixture_readiness_shape')
                result.extend(value)
        value = json.loads(result)
        if (type(value) is not dict or set(value) != {'schema_version', 'status', 'port'} or
                type(value['schema_version']) is not int or value['schema_version'] != 1 or value['status'] != 'ready' or
                type(value['port']) is not int or not 1 <= value['port'] <= 65535 or value['port'] == 43117):
            raise ValueError('fixture_readiness_shape')
        return value['port']
    finally:
        transport._zero(result)


def run_scenario(dotnet, fixture, scenario):
    if scenario not in EXPECTED:
        raise ValueError('fixture_count_not_reviewed')
    process = subprocess.Popen([str(dotnet), str(fixture), '--fixture', scenario],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    token = bytearray(b'c' * 64)
    sockets = []
    try:
        port = read_ready(process)
        class Redirect:
            def __init__(self):
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.requests = []
                self.receives = []
                self.post_count = 0
                self.get_count = 0
                self.closed = 0
                sockets.append(self)
            def connect(self, actual):
                if actual != ('127.0.0.1', 43117):
                    raise AssertionError('production_endpoint_drift')
                self.socket.connect(('127.0.0.1', port))
            def sendall(self, request):
                self.requests.append(request)
                self.post_count += request.startswith(b'POST ')
                self.get_count += request.startswith(b'GET ')
                self.socket.sendall(request)
            def recv_into(self, buffer, maximum):
                self.receives.append(buffer)
                return self.socket.recv_into(buffer, maximum)
            def close(self):
                self.closed += 1
                self.socket.close()
            def __getattr__(self, name):
                return getattr(self.socket, name)
        # Unauthenticated and malformed requests cannot reserve or reach the owner frame.
        for header in (b"Authorization: Bearer " + b"d" * 64,
                       b"Authorization: bearer " + b"c" * 64):
            with socket.create_connection(('127.0.0.1', port), timeout=1) as probe:
                probe.sendall(b"GET /probe/generic-event-v3/public/decision HTTP/1.1\r\nHost: 127.0.0.1:43117\r\n" + header + b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n")
                probe.shutdown(socket.SHUT_WR)
                if probe.recv(1):
                    raise ValueError('unauthorized_request_answered')
        diagnostics = []
        original_exchange = transport._perform_exchange
        def observe(*args):
            result = original_exchange(*args)
            diagnostics.append(result[1])
            return result
        with mock.patch.object(transport, '_perform_exchange', observe):
            result = transport._run_with_socket_factory(token, Redirect,
                clock=time.monotonic, sleep=time.sleep)
        parents, children, reads, episodes = EXPECTED[scenario]
        lost = scenario.startswith('lost_')
        unsupported = scenario in ('native_binding_wait', 'native_selector_wait', 'native_unsupported')
        expected_diagnostic = {'native_binding_wait':'pending_screen','native_selector_wait':'prepare_geometry','native_unsupported':'pending_binding_failed','native_normal':'map_ready','native_selector_release':'map_ready','provider_throw':'diagnostic_unavailable','provider_invalid':'diagnostic_unavailable'}.get(scenario,'none')
        if (result['status'] != ('failed' if lost or unsupported else 'resolved') or
                result['code'] != ('transport_failure' if lost else 'unsupported_state' if unsupported else None) or
                result['parent_attempted'] != parents or result['child_attempted'] != children or
                result['total_attempted'] != parents + children or result['reads'] != reads or
                result['child_episodes'] != episodes or result['last_response_diagnostic'] != expected_diagnostic or any(token)):
            raise ValueError(('host_result_or_credential_cleanup', scenario, result))
        if not lost and not unsupported and (result['parent_accepted'] != parents or result['parent_reconciled'] != parents or
                         result['child_accepted'] != children or result['child_reconciled'] != children or
                         result['effects'] != 'unverified'):
            raise ValueError(('host_history_incomplete', scenario, result))
        if unsupported and (result['parent_accepted'] != 1 or result['parent_reconciled'] != 0 or result['child_accepted'] != 0):
            raise ValueError('unsupported_effect_accounting')
        if scenario == 'native_selector_release' and ('prepare_geometry' not in diagnostics or 'child_ready' not in diagnostics or diagnostics[-1] != 'map_ready'):
            raise ValueError(('native_diagnostic_not_reset', diagnostics))
        if lost and (result['parent_accepted'] != parents - (scenario == 'lost_parent') or
                     result['child_accepted'] != children - (scenario != 'lost_parent')):
            raise ValueError(('lost_receipt_was_retried', scenario, result))
        output, error = process.communicate(timeout=5)
        if process.returncode != 0 or output or len(error) > 512:
            raise ValueError(('fixture_completion_shape', scenario, error))
        stats = json.loads(error)
        wanted = {'schema_version': 1, 'status': 'fixture_complete',
            'parent_dispatches': parents, 'card_dispatches': children,
            'parent_post_count': parents, 'child_post_count': children,
            'read_count': reads, 'diagnostic_samples': parents + children + reads, 'diagnostic_owner': True, 'transport_stopped': True, 'service_disposed': True}
        if stats != wanted or any(type(stats[key]) is not type(value) for key, value in wanted.items()):
            raise ValueError(('fixture_execution_or_cleanup_count', scenario, stats, wanted))
        if (sum(s.post_count for s in sockets) != parents + children or
                sum(s.get_count for s in sockets) != reads or
                any(s.closed != 1 for s in sockets) or
                any(any(buffer) for s in sockets for buffer in s.requests + s.receives)):
            raise ValueError('socket_count_or_owned_cleanup')
    finally:
        transport._zero(token)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dotnet', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    for scenario in EXPECTED:
        run_scenario(args.dotnet, args.fixture, scenario)
    print(json.dumps({'schema_version':1,'status':'passed','suite':'generic_event_release_socket_composition','check_count':len(EXPECTED)}, separators=(',', ':')))


if __name__ == '__main__':
    main()
