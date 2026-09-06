#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MAXIMUM_SOURCE_BYTES = 128 * 1024


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("invalid source")
    data = path.read_bytes()
    if not data or len(data) > MAXIMUM_SOURCE_BYTES:
        raise ValueError("invalid source size")
    return data


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    args = parser.parse_args()
    root = Path(args.source_root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        return 2
    manifest_path = Path(__file__).with_name("source_derivation.json")
    try:
        manifest = json.loads(_read(manifest_path))
        if type(manifest) is not dict or list(manifest) != [
            "derived_path", "derived_sha256", "original_path", "original_sha256",
            "replacements", "schema_version"
        ] or manifest["schema_version"] != 1:
            raise ValueError("invalid manifest")
        original = _read(root / manifest["original_path"])
        derived = _read(root / manifest["derived_path"])
        if _digest(original) != manifest["original_sha256"]:
            raise ValueError("original identity")
        value = original
        checks = 1
        replacements = manifest["replacements"]
        if type(replacements) is not list or len(replacements) != 2:
            raise ValueError("replacement count")
        for replacement in replacements:
            if type(replacement) is not dict or list(replacement) != ["count", "new", "old"] or replacement["count"] != 1:
                raise ValueError("replacement shape")
            old = replacement["old"].encode("utf-8")
            new = replacement["new"].encode("utf-8")
            if value.count(old) != 1 or old == new:
                raise ValueError("replacement identity")
            value = value.replace(old, new, 1)
            checks += 2
        if value != derived or _digest(derived) != manifest["derived_sha256"]:
            raise ValueError("derived identity")
        checks += 2
        print(json.dumps({
            "check_count": checks,
            "schema_version": 1,
            "status": "passed",
            "suite": "card_selection_completion_v1_derivation",
        }, separators=(",", ":"), sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
