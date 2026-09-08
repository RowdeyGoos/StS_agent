"""Actual shared and original Python clients against the unified C# listener."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).absolute().parents[3]
sys.path[:0] = [str(ROOT / 'apps/bridge/client'), str(ROOT / 'tools')]
from wire_client import BridgeClient, parse_response
import probe_live


def main():
    process = subprocess.Popen([sys.argv[1], sys.argv[2], '--serve'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        port = json.loads(process.stdout.readline())['port']
        connector = lambda: socket.create_connection(('127.0.0.1', port), timeout=2)
        client = BridgeClient(bytearray(b'a' * 64), connector=connector)
        action = bytearray(json.dumps({'decision_id': 'b' * 64, 'action_id': 'end_turn'}).encode())
        stale = json.loads(client.exchange('POST', '/probe/v0/public/combat-action', action))
        assert (stale['status'], stale['mutation_state'], stale['reason']) == ('rejected', 'none', 'stale_decision')
        # The controller refreshes after a known pre-dispatch rejection. This
        # request used to fail because the shared host closed its listener.
        assert json.loads(client.exchange('GET', '/probe/v0/public/combat-decision'))['status'] == 'waiting'
        for route in ['/probe/generic-event-v7/public/decision', '/card-selection-v1/parent',
                      '/probe/room-flows-v1/public/decision', '/probe/item-v1/public/item-decision']:
            assert json.loads(client.exchange('GET', route))['status'] == 'ready'
            if route == '/probe/room-flows-v1/public/decision':
                purchase = bytearray(json.dumps({'decision_id': 'c' * 64, 'action_id': 'buy:card:0'}).encode())
                assert json.loads(client.exchange('POST', '/probe/room-flows-v1/public/action', purchase))['status'] == 'resolved'
            else:
                assert json.loads(client.exchange('GET', route))['status'] == 'resolved'
        assert json.loads(client.exchange('GET', '/probe/v0/public/map-decision'))['status'] == 'waiting'
        # Reuse the actual base-controller exchange helper, including SHUT_WR.
        def build():
            return bytearray(b'GET /probe/v0/manifest HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer ' + b'a' * 64 +
                             b'\r\nAccept: application/json\r\nConnection: close\r\n\r\n')
        response = probe_live._exchange_request('unified', build, connector, time.monotonic() + 3, 'expired')
        body = parse_response(response, event=False)
        probe_live._validate_manifest(memoryview(body))
        assert json.loads(body)['bridge_version'] == '1.0.0'
        client.close()
        process.stdin.write('stop\n'); process.stdin.flush()
        _, errors = process.communicate(timeout=5)
        assert process.returncode == 0, errors
        print('{"status":"passed","suite":"unified_python_socket","capability_clients":5,"original_client":true,"stale_refresh":true}')
    finally:
        if process.poll() is None:
            process.kill(); process.wait()


if __name__ == '__main__':
    main()
