from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_apply_run_entry_wire_fixture_gate() -> None:
    fixture = Path("bridge/Sts2AgentBridge/tools/apply_run_entry_wire_fixtures.py")
    completed = subprocess.run(
        [sys.executable, "-B", "-E", "-s", "-S", str(fixture)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    assert completed.stdout == (
        '{"schema_version":1,"status":"passed","suite":"apply_run_entry_wire_fixtures",'
        '"check_count":10}\n'
    )
