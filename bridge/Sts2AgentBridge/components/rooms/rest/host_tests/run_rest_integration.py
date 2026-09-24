"""Python controller -> real C# wire/session/native adapter -> inert game surfaces."""
import json
import os
import select
import subprocess
import sys
import time
from test_rest_host import host
from test_rest_interactive_host import host as interactive

for action in ("lift", "kindle", "dig", "cook:0:2", "clone", "hatch"):
    process = subprocess.Popen([sys.argv[1], sys.argv[2], "--wire", action], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    calls = []
    try:
        def exchange(method, route, decision, selected, deadline):
            calls.append(method)
            process.stdin.write(json.dumps(dict(method=method, decision=decision, action=selected)).encode() + b"\n")
            process.stdin.flush()
            data = bytearray()
            while not data.endswith(b"\n"):
                if not select.select([process.stdout], [], [], max(0, deadline - time.monotonic()))[0]:
                    raise TimeoutError()
                part = os.read(process.stdout.fileno(), 1)
                if not part:
                    raise RuntimeError("fixture exited")
                data.extend(part)
            return data[:-1]
        result = host.run_rest(exchange, action.split(":")[0], cook_slots=(0, 2) if action.startswith("cook:") else None)
        assert result["status"] == "passed", result
        assert result["after"] == {"lift": 3, "kindle": 14, "dig": 6, "cook:0:2": 69, "clone": 5, "hatch": 6}[action], result
        assert calls == ["GET", "POST", "GET", "GET"], calls
        process.stdin.close()
        assert process.wait(timeout=5) == 0, process.stderr.read().decode()
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=5)
        process.stdout.close(); process.stderr.close()

scenarios = 6
for option in ('heal', 'smith', 'cook', 'lift', 'kindle', 'dig', 'clone', 'hatch'):
    for selection in (('choose', 'cancel', 'preview-cancel') if option in ('smith', 'cook') else ('choose',)):
        process = subprocess.Popen([sys.argv[1], sys.argv[2], '--interactive-wire', option], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        posts, buffers = [], []
        try:
            def exchange(method, route, body):
                command = json.loads(body) if body is not None else {}
                if body is not None:
                    posts.append(command['action_id']); buffers.append(body)
                process.stdin.write(json.dumps(dict(method=method, decision=command.get('decision_id'), action=command.get('action_id'))).encode() + b'\n')
                process.stdin.flush()
                data, deadline = bytearray(), time.monotonic() + 5
                while not data.endswith(b'\n'):
                    if not select.select([process.stdout], [], [], max(0, deadline - time.monotonic()))[0]:
                        raise TimeoutError()
                    part = os.read(process.stdout.fileno(), 1)
                    if not part:
                        raise RuntimeError('fixture exited')
                    data.extend(part)
                result = data[:-1]; buffers.append(result)
                return result
            result = interactive.run_rest(exchange, interactive.controlled_policy(option, selection))
            assert result['status'] == 'resolved', (option, selection, result)
            assert result['outcome'] == ('cancelled' if selection != 'choose' else 'reconciled'), result
            assert result['attempted'] == result['accepted'] == result['reconciled'] == len(posts), result
            assert posts[0] == 'option:' + option
            if option in ('smith', 'cook'):
                count = 0 if selection == 'cancel' else 1 if option == 'smith' else 2
                assert posts == ['option:' + option] + ['select:' + str(i) for i in range(count)] + ['confirm' if selection == 'choose' else 'cancel'], posts
            assert all(not any(b) for b in buffers), 'wire buffers erased'
            process.stdin.close()
            assert process.wait(timeout=5) == 0, process.stderr.read().decode()
            scenarios += 1
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)
            process.stdout.close(); process.stderr.close()
print(json.dumps(dict(status='passed', scenarios=scenarios, game_executed=False)))
