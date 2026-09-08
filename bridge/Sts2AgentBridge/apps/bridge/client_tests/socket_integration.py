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
from run_live import verify_map_handoff, run_combat_map
from combat_host import run_combat
import combat_host
import reward_host
import probe_live


def combat(reward_policy=None):
    process = subprocess.Popen([sys.argv[1], sys.argv[2], '--serve-combat-map' if reward_policy else '--serve-combat'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        port = json.loads(process.stdout.readline())['port']
        client = BridgeClient(bytearray(b'a' * 64), connector=lambda: socket.create_connection(('127.0.0.1', port), timeout=2))
        try:
            if reward_policy:
                flow = run_combat_map(client.exchange, combat_host, reward_host, reward_policy=reward_policy)
                assert flow['status'] == 'resolved' and flow['map_handoff']['candidate_count'] == 1, flow
                loot = flow['rewards']
                assert loot['attempted'] == loot['accepted'] == loot['reconciled'] == 4, flow
                assert loot['claimed_gold'] == 14, flow
                assert loot['selected_cards'] == ([] if reward_policy == 'skip-card' else ['ANGER']), flow
                assert loot['skipped_card_rewards'] == (1 if reward_policy == 'skip-card' else 0), flow
                result = flow['combat']
            else:
                result = run_combat(client.exchange)
            assert result['status'] == 'resolved' and result['outcome'] == 'victory', result
            assert result['attempted'] == result['accepted'] == result['reconciled'] == 2, result
            assert len(result['choices']) == 1 and result['choices'][0]['selected_count'] == 1, result
            assert result['choices'][0]['accepted'] == result['choices'][0]['reconciled'] == 1, result
        finally:
            client.close()
        process.stdin.write('stop\n'); process.stdin.flush()
        _, errors = process.communicate(timeout=5)
        assert process.returncode == 0, errors
    finally:
        if process.poll() is None:
            process.kill(); process.wait()


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
        assert verify_map_handoff(client.exchange) == {
            'status': 'passed', 'reads': 1, 'candidate_count': 1, 'code': None}
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
        combat()
        combat('first-card')
        combat('skip-card')
        print('{"status":"passed","suite":"unified_python_socket","capability_clients":7,"original_client":true,"stale_refresh":true,"combat_choice_resume":true,"combat_reward_map_policies":2}')
    finally:
        if process.poll() is None:
            process.kill(); process.wait()


if __name__ == '__main__':
    main()
