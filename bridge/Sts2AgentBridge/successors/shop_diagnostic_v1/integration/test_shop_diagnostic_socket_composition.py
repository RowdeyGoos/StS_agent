"""Actual C# diagnostic runtime joined to the Python one-GET transport."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import select
import socket
import struct
import subprocess
import sys
import time


ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT / "transport"))

import diagnostic_transport as transport


_TOKEN = b"c" * 64
_REQUEST = (
    b"GET /probe/shop-diagnostic-v1/public/diagnostic HTTP/1.1\r\n"
    b"Host: 127.0.0.1:43117\r\n"
    b"Authorization: Bearer " + _TOKEN + b"\r\n"
    b"Accept: application/json\r\n"
    b"Connection: close\r\n\r\n"
)
_EXPECTED = {
    "ready": {
        "schema_version": 1,
        "status": "passed",
        "shop_status": "ready",
        "stage": "complete",
        "reason": "none",
    },
    "unsupported": {
        "schema_version": 1,
        "status": "passed",
        "shop_status": "unsupported",
        "stage": "native_offers",
        "reason": "cost_text_invalid",
    },
}


def run_suite(dotnet: str, fixture_assembly: str) -> None:
    checks = 0

    def check(value: object) -> None:
        nonlocal checks
        checks += 1
        if not value:
            raise AssertionError(f"shop diagnostic socket integration check {checks}")

    for scenario in ("ready", "unsupported", "lost_delivery"):
        process = subprocess.Popen(
            [dotnet, fixture_assembly, "--fixture", scenario],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        token = bytearray(_TOKEN)
        requests: list[bytearray] = []
        sent_requests: list[bytes] = []
        factory_calls = 0
        try:
            check(process.stdout is not None and bool(select.select([process.stdout], [], [], 10)[0]))
            announcement = process.stdout.readline(128)
            endpoint = json.loads(announcement)
            check(
                type(endpoint) is dict
                and list(endpoint) == ["port"]
                and type(endpoint["port"]) is int
                and 1 <= endpoint["port"] <= 65535
                and endpoint["port"] != 43117
            )

            class Redirect:
                def __init__(self) -> None:
                    nonlocal factory_calls
                    factory_calls += 1
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                def connect(self, actual: object) -> None:
                    check(actual == ("127.0.0.1", 43117))
                    self.socket.connect(("127.0.0.1", endpoint["port"]))

                def sendall(self, request: bytearray) -> None:
                    requests.append(request)
                    sent_requests.append(bytes(request))
                    self.socket.sendall(request)

                def recv(self, maximum: int) -> bytes:
                    if scenario != "lost_delivery":
                        return self.socket.recv(maximum)
                    # Give the owner-frame loop time to consume the sole reserved
                    # observation, then discard delivery at the client boundary.
                    time.sleep(0.2)
                    self.socket.setsockopt(
                        socket.SOL_SOCKET,
                        socket.SO_LINGER,
                        struct.pack("ii", 1, 0),
                    )
                    self.socket.close()
                    raise ConnectionResetError("synthetic lost delivery")

                def __getattr__(self, name: str) -> object:
                    return getattr(self.socket, name)

            result = transport._run_with_socket_factory(
                token,
                Redirect,
                clock=time.monotonic,
            )

            # The runtime publishes its final counters only after its terminal
            # owner cleanup. Wait for that evidence before ending fixture stdin.
            check(process.stderr is not None and bool(select.select([process.stderr], [], [], 10)[0]))
            diagnostic_bytes = process.stderr.readline(2048)
            check(process.stdin is not None)
            process.stdin.close()
            process.wait(timeout=10)

            check(process.returncode == 0)
            check(process.stdout.read(128) == b"")
            check(process.stderr.read(128) == b"")
            diagnostic = json.loads(diagnostic_bytes)
            check(
                type(diagnostic) is dict
                and list(diagnostic)
                == ["observe_count", "terminal", "transport_stopped", "service_disposed"]
            )
            check(
                diagnostic
                == {
                    "observe_count": 1,
                    "terminal": True,
                    "transport_stopped": True,
                    "service_disposed": True,
                }
            )
            check(result == (
                {"schema_version": 1, "status": "failed", "code": "diagnostic_transport_failed"}
                if scenario == "lost_delivery"
                else _EXPECTED[scenario]
            ))
            check(factory_calls == 1)
            check(len(requests) == 1)
            check(sent_requests == [_REQUEST])
            check(b"POST " not in sent_requests[0])
            check(not any(token))
            check(all(not any(request) for request in requests))
        finally:
            transport._zero(token)
            for request in requests:
                transport._zero(request)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()

    print(json.dumps(
        {
            "schema_version": 1,
            "status": "passed",
            "suite": "shop_diagnostic_socket_composition",
            "check_count": checks,
        },
        separators=(",", ":"),
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", required=True)
    parser.add_argument("--fixture-assembly", required=True)
    arguments = parser.parse_args()
    run_suite(arguments.dotnet, arguments.fixture_assembly)
