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

ROOT = Path(__file__).absolute().parents[1]
sys.path[:0] = [str(ROOT / 'transport'), str(ROOT.parent)]
import card_selection_transport as transport

# Filled from the reviewed deterministic fixture sequence, not learned at runtime.
EXPECTED_CAPTURE_COUNTS: dict[str, int] = {'cheese': 12, 'smith': 12, 'lost_receipt': 2}


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
    if scenario not in EXPECTED_CAPTURE_COUNTS:
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
        selection = 'smith' if scenario == 'smith' else 'cheese'
        result = transport._run_with_socket_factory(selection, token, Redirect,
            clock=time.monotonic, sleep=time.sleep)
        expected = {'schema_version': 1, 'status': 'passed',
            'parent_attempted': 2, 'parent_accepted': 2, 'parent_reconciled': 2,
            'child_attempted': 2, 'child_accepted': 2, 'child_reconciled': 2}
        if scenario == 'lost_receipt':
            expected = {'schema_version': 1, 'status': 'failed', 'code': 'transport_failure',
                'parent_attempted': 1, 'parent_accepted': 0, 'parent_reconciled': 0,
                'child_attempted': 0, 'child_accepted': 0, 'child_reconciled': 0}
        if result != expected or any(token):
            raise ValueError('host_result_or_credential_cleanup')
        output, error = process.communicate(timeout=5)
        if process.returncode != 0 or output or len(error) > 512:
            raise ValueError('fixture_completion_shape')
        stats = json.loads(error)
        lost = scenario == 'lost_receipt'
        wanted = {'schema_version': 1, 'status': 'fixture_complete',
            'capture_count': EXPECTED_CAPTURE_COUNTS[scenario], 'dispatch_count': 1 if lost else 4,
            'parent_post_count': 1 if lost else 2, 'child_post_count': 0 if lost else 2,
            'read_count': 1 if lost else 7, 'transport_stopped': True, 'service_disposed': True}
        if stats != wanted or any(type(stats[key]) is not type(value) for key, value in wanted.items()):
            raise ValueError('fixture_execution_or_cleanup_count')
        if (sum(s.post_count for s in sockets) != (1 if lost else 4) or
                sum(s.get_count for s in sockets) != (1 if lost else 7) or
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
    for scenario in ('cheese', 'smith', 'lost_receipt'):
        run_scenario(args.dotnet, args.fixture, scenario)
    print(json.dumps({'schema_version':1,'status':'passed','suite':'card_selection_release_socket_composition','check_count':3}, separators=(',', ':')))


if __name__ == '__main__':
    main()
