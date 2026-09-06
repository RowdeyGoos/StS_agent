#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib


def _read(path: pathlib.Path, maximum: int = 256_000) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("invalid source")
    data = path.read_bytes()
    if not data or len(data) > maximum:
        raise ValueError("invalid source size")
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--source-root", type=pathlib.Path)
    args = parser.parse_args()
    root = (args.source_root or pathlib.Path(__file__).resolve().parents[5]).resolve()
    manifest_path = pathlib.Path(__file__).with_name("derivation_manifest.json")
    manifest = json.loads(_read(manifest_path).decode("utf-8"))
    if type(manifest) is not dict or manifest.get("schema_version") != 1:
        raise ValueError("invalid manifest")
    checks = 1

    original_record = manifest["original"]
    derived_record = manifest["derived"]
    original_bytes = _read(root / original_record["path"])
    derived_bytes = _read(root / derived_record["path"])
    if _sha256(original_bytes) != original_record["sha256"]:
        raise ValueError("original identity mismatch")
    checks += 1
    if _sha256(derived_bytes) != derived_record["sha256"]:
        raise ValueError("derived identity mismatch")
    checks += 1

    for record in manifest["linked_sources"]:
        if _sha256(_read(root / record["path"])) != record["sha256"]:
            raise ValueError("linked source identity mismatch")
        checks += 1

    project_record = manifest["core_project"]
    project_bytes = _read(root / project_record["path"])
    if _sha256(project_bytes) != project_record["sha256"]:
        raise ValueError("project identity mismatch")
    checks += 1
    project_text = project_bytes.decode("utf-8")
    position = -1
    for anchor in project_record["ordered_anchors"]:
        position = project_text.find(anchor, position + 1)
        if position < 0:
            raise ValueError("project closure mismatch")
    checks += 1

    expected = original_bytes.decode("utf-8")
    actual = derived_bytes.decode("utf-8")
    for replacement in manifest["replacements"]:
        old = replacement["old"]
        new = replacement["new"]
        if expected.count(old) != 1 or actual.count(new) != 1:
            raise ValueError("replacement anchor mismatch")
        expected = expected.replace(old, new, 1)
        checks += 1
    if expected != actual:
        raise ValueError("unexpected derived source change")
    checks += 1

    occurrences = manifest["map_travel_enabled_occurrences"]
    token = "capture.MapTravelEnabled"
    if (original_bytes.decode("utf-8").count(token) != occurrences["original"] or
            actual.count(token) != occurrences["derived"]):
        raise ValueError("permission predicate count mismatch")
    checks += 1

    method = manifest["unchanged_method"]
    original_start = original_bytes.index(method["start"].encode("utf-8"))
    original_end = original_bytes.index(method["end"].encode("utf-8"), original_start)
    derived_start = derived_bytes.index(method["start"].encode("utf-8"))
    derived_end = derived_bytes.index(method["end"].encode("utf-8"), derived_start)
    original_method = original_bytes[original_start:original_end]
    derived_method = derived_bytes[derived_start:derived_end]
    if original_method != derived_method or _sha256(derived_method) != method["sha256"]:
        raise ValueError("ReconcileLeave changed")
    checks += 1

    print(json.dumps({
        "schema_version": 1,
        "status": "passed",
        "suite": "shop_map_permission_v1_derivation",
        "check_count": checks,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print('{"schema_version":1,"status":"failed","suite":"shop_map_permission_v1_derivation","check_count":0}')
        raise SystemExit(1)
