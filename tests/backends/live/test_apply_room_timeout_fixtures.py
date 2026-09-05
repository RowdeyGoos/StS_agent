from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_apply_room_timeout_fixture_gate() -> None:
    fixture = Path("bridge/Sts2AgentBridge/tools/apply_room_timeout_fixtures.py")
    completed = subprocess.run(
        [sys.executable, "-B", "-E", "-s", "-S", str(fixture)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    assert completed.stdout == (
        '{"schema_version":1,"status":"passed","suite":"apply_room_timeout_fixtures",'
        '"check_count":13}\n'
    )
