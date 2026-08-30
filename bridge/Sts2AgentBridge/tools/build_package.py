#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tool_common import absolute_path, build_canonical_zip, main, require_regular_file, sha256_bytes, sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def operation() -> dict[str, object]:
    args = parse_args()
    dll_path = absolute_path(args.dll, "dll")
    manifest_path = absolute_path(args.manifest, "manifest")
    output_path = absolute_path(args.output, "output")
    dll_data = require_regular_file(dll_path, "dll")
    manifest_data = require_regular_file(manifest_path, "manifest", max_bytes=4096)
    build_canonical_zip(dll_data, manifest_data, output_path)
    return {
        "schema_version": 1,
        "status": "passed",
        "entry_count": 2,
        "dll_sha256": sha256_bytes(dll_data),
        "manifest_sha256": sha256_bytes(manifest_data),
        "package_sha256": sha256_file(output_path),
    }


if __name__ == "__main__":
    main(operation)
