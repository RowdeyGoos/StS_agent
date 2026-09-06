#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _read(path: pathlib.Path, maximum: int = 256_000) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("invalid source")
    data = path.read_bytes()
    if not data or len(data) > maximum:
        raise ValueError("invalid source size")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--source-root", type=pathlib.Path)
    args = parser.parse_args()
    root = (args.source_root or pathlib.Path(__file__).resolve().parents[5]).resolve()
    manifest_path = pathlib.Path(__file__).with_name("derivation_manifest.json")
    manifest = json.loads(_read(manifest_path).decode("utf-8"))
    if type(manifest) is not dict or manifest.get("schema_version") != 1:
        raise ValueError("invalid manifest")

    texts: dict[str, str] = {}
    checks = 1
    sources = manifest["sources"]
    for name, record in sources.items():
        path = root / record["path"]
        data = _read(path)
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError("source identity mismatch")
        texts[name] = _normalized(data.decode("utf-8"))
        checks += 1

    for group in manifest["ordered_groups"]:
        position = -1
        text = texts[group["source"]]
        for anchor in group["anchors"]:
            current = text.find(_normalized(anchor), position + 1)
            if current < 0:
                raise ValueError("ordered source anchor missing")
            position = current
        checks += 1

    original_native = texts["original_native"]
    derived_reader = texts["derived_reader"]
    for substitution in manifest["readiness_substitutions"]:
        if _normalized(substitution["original"]) not in original_native:
            raise ValueError("original readiness anchor missing")
        if _normalized(substitution["derived"]) not in derived_reader:
            raise ValueError("derived readiness anchor missing")
        checks += 1

    production = " ".join((texts["derived_reader"], texts["derived_projector"]))
    for token in manifest["production_omissions"]:
        if token in production:
            raise ValueError("forbidden production token")
    checks += 1

    print(json.dumps({
        "schema_version": 1,
        "status": "passed",
        "suite": "shop_diagnostic_v1_derivation",
        "check_count": checks,
    }, separators=(",", ":"), sort_keys=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print('{"schema_version":1,"status":"failed","suite":"shop_diagnostic_v1_derivation","check_count":0}')
        raise SystemExit(1)
