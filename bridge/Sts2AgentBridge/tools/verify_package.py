#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tool_common import (
    EXIT_MISMATCH,
    absolute_path,
    fail,
    inspect_canonical_zip,
    main,
    require_hex_64,
    sha256_bytes,
    sha256_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--expected-dll-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    return parser.parse_args()


def operation() -> dict[str, object]:
    args = parse_args()
    package_path = absolute_path(args.package, "package")
    expected_dll = require_hex_64(args.expected_dll_sha256, "dll_sha256")
    expected_manifest = require_hex_64(args.expected_manifest_sha256, "manifest_sha256")
    dll_data, manifest_data = inspect_canonical_zip(package_path)
    dll_hash = sha256_bytes(dll_data)
    manifest_hash = sha256_bytes(manifest_data)
    if dll_hash != expected_dll:
        fail(EXIT_MISMATCH, "dll_hash_mismatch")
    if manifest_hash != expected_manifest:
        fail(EXIT_MISMATCH, "manifest_hash_mismatch")
    return {
        "schema_version": 1,
        "status": "passed",
        "entry_count": 2,
        "dll_sha256": dll_hash,
        "manifest_sha256": manifest_hash,
        "package_sha256": sha256_file(package_path),
    }


if __name__ == "__main__":
    main(operation)
