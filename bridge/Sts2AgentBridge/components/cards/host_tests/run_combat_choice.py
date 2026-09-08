"""Real combat choice service/native adapter fixture consumed by the shared host."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).absolute().parents[3]
sys.path.insert(0, str(ROOT / 'apps/bridge/client'))
from combat_host import run_choice, first_select, minimum_select


def main():
    for provider, count, actions in [(first_select, 2, 3), (minimum_select, 0, 1),
                                    (lambda value, seq=iter(['select:0','deselect:0','select:2','confirm']): next(seq), 1, 4)]:
        process = subprocess.Popen([sys.argv[1], sys.argv[2], '--wire'], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        buffers = []
        try:
            def request(method, route, body):
                value = {'method':method}
                if body is not None: value.update(json.loads(body)); buffers.append(body)
                process.stdin.write(json.dumps(value) + '\n'); process.stdin.flush()
                response = bytearray(process.stdout.readline().encode()); buffers.append(response); return response
            result = run_choice(request, provider=provider)
            assert result['status'] == 'resolved', result
            assert result['selected_count'] == count, result
            assert result['attempted'] == result['accepted'] == result['reconciled'] == actions, result
            assert all(not any(b) for b in buffers)
            process.stdin.close(); process.stdin = None
            _, errors = process.communicate(timeout=5)
            assert process.returncode == 0, errors
        finally:
            if process.poll() is None: process.kill(); process.wait()
    print('{"status":"passed","suite":"combat_choice_host_native","scenarios":3,"target_game_executed":false}')


if __name__ == '__main__': main()
