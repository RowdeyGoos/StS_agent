#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess

from tool_common import (
    EXIT_INTERNAL,
    EXIT_MISMATCH,
    absolute_path,
    fail,
    main,
    require_directory,
    require_executable_file,
    require_regular_file,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--dotnet", required=True)
    result.add_argument("--verifier", required=True)
    result.add_argument("--assembly", required=True)
    result.add_argument("--policy", required=True)
    result.add_argument("--source-root", required=True)
    return result


def operation() -> dict[str, object]:
    args = parser().parse_args()
    dotnet = absolute_path(args.dotnet, "dotnet")
    verifier = absolute_path(args.verifier, "verifier")
    assembly = absolute_path(args.assembly, "assembly")
    policy = absolute_path(args.policy, "policy")
    source_root = absolute_path(args.source_root, "source_root")
    require_executable_file(dotnet, "dotnet")
    require_regular_file(verifier, "verifier", max_bytes=64 * 1024 * 1024)
    require_regular_file(assembly, "assembly", max_bytes=64 * 1024 * 1024)
    require_regular_file(policy, "policy", max_bytes=1024 * 1024)
    require_directory(source_root, "source_root")
    try:
        result = subprocess.run(
            [
                str(dotnet),
                str(verifier),
                "--assembly",
                str(assembly),
                "--policy",
                str(policy),
                "--source-root",
                str(source_root),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=300,
            env={
                "PATH": "/usr/bin:/bin",
                "LANG": "C",
                "LC_ALL": "C",
                "DOTNET_NOLOGO": "1",
                "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
                "DOTNET_MULTILEVEL_LOOKUP": "0",
            },
        )
    except subprocess.TimeoutExpired:
        fail(EXIT_MISMATCH, "surface_timeout")
    except OSError:
        fail(EXIT_INTERNAL, "surface_process")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        fail(EXIT_MISMATCH, "surface_output")
    if (
        result.returncode != 0
        or not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("status") != "passed"
    ):
        fail(EXIT_MISMATCH, "surface_mismatch")
    return {
        "schema_version": 1,
        "status": "passed",
        "assembly_sha256": payload.get("assembly_sha256"),
        "route_count": payload.get("route_count"),
        "checked_method_bodies": payload.get("checked_method_bodies"),
    }


if __name__ == "__main__":
    main(operation)
