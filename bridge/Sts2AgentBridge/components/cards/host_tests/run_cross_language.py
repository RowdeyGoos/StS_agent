"""Drive the actual C# wire fixture through the pure Python host."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

_HOST_PATH = Path(__file__).resolve().parents[1] / "host" / "card_selection_host.py"
_SPEC = importlib.util.spec_from_file_location("card_selection_host_cross", _HOST_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_HOST = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_HOST)


class FixtureTransport:
    def __init__(self, dotnet: str, assembly: str, scenario: str) -> None:
        self.process = subprocess.Popen(
            [dotnet, assembly, "--fixture", scenario],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self.finished = False

    def __call__(self, method: str, route: str, body: bytearray | None) -> bytearray:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("fixture pipes unavailable")
        decision = action = None
        if method == "POST":
            if type(body) is not bytearray:
                raise RuntimeError("missing action body")
            value = json.loads(bytes(body))
            decision, action = value["decision_id"], value["action_id"]
        command = json.dumps(
            {"method": method, "route": route, "decision_id": decision, "action_id": action},
            separators=(",", ":"),
        ).encode("ascii") + b"\n"
        self.process.stdin.write(command)
        self.process.stdin.flush()
        line = self._read_line(self.process.stdout, _HOST.MAX_BODY + 1, 5.0)
        if not line.endswith(b"\n") or len(line) > _HOST.MAX_BODY + 1:
            raise RuntimeError("invalid fixture line")
        return bytearray(line[:-1])

    @staticmethod
    def _read_line(stream, cap: int, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        chunks = bytearray()
        descriptor = stream.fileno()
        while b"\n" not in chunks:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([descriptor], [], [], remaining)[0]:
                raise RuntimeError("fixture read timed out")
            chunk = os.read(descriptor, min(4096, cap + 1 - len(chunks)))
            if not chunk:
                raise RuntimeError("fixture closed early")
            chunks.extend(chunk)
            if len(chunks) > cap:
                raise RuntimeError("fixture line exceeded cap")
        newline = chunks.index(10)
        if newline != len(chunks) - 1:
            raise RuntimeError("fixture emitted extra output")
        return bytes(chunks)

    def finish(self) -> dict[str, object]:
        if self.process.stdin is None or self.process.stderr is None:
            raise RuntimeError("fixture pipes unavailable")
        self.process.stdin.close()
        self.process.stdin = None
        try:
            output, error = self.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            output, error = self.process.communicate(timeout=5)
            raise RuntimeError("fixture completion timed out")
        self.finished = True
        if output or len(error) > 512:
            raise RuntimeError("invalid fixture completion output")
        code = self.process.returncode
        if code != 0:
            raise RuntimeError("fixture failed")
        lines = error.decode("ascii").splitlines()
        if len(lines) != 1:
            raise RuntimeError("invalid fixture stats")
        return json.loads(lines[0])

    def abort(self) -> None:
        if self.finished:
            return
        if self.process.poll() is None:
            self.process.kill()
        try:
            self.process.communicate(timeout=5)
        except (subprocess.TimeoutExpired, ValueError):
            self.process.kill()
            self.process.wait(timeout=5)
        self.finished = True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", required=True)
    parser.add_argument("--fixture", required=True)
    arguments = parser.parse_args()
    expected = {
        "schema_version": 1, "status": "passed",
        "parent_attempted": 2, "parent_accepted": 2, "parent_reconciled": 2,
        "child_attempted": 2, "child_accepted": 2, "child_reconciled": 2,
    }
    for scenario in ("cheese", "smith"):
        transport = FixtureTransport(arguments.dotnet, arguments.fixture, scenario)
        try:
            output = _HOST.run_card_selection(transport, clock=lambda: 0.0, sleep=lambda _: None)
            if output != expected:
                raise RuntimeError("cross-language host failed")
            stats = transport.finish()
            if stats != {
                "schema_version": 1,
                "status": "fixture_complete",
                "capture_count": 7,
                "dispatch_count": 4,
            }:
                raise RuntimeError("fixture stats mismatch")
        finally:
            transport.abort()
    print('{"schema_version":1,"status":"passed","suite":"card_selection_v1_host_cross_language","check_count":2}')
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print('{"schema_version":1,"status":"failed","suite":"card_selection_v1_host_cross_language"}', file=sys.stderr)
        raise SystemExit(1)
