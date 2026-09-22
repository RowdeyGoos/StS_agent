"""Python controller -> real C# wire/session/native adapter -> inert game surfaces."""
import json
import os
import select
import subprocess
import sys
import time
from test_rest_host import host

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
print(json.dumps(dict(status="passed", scenarios=6, game_executed=False)))
