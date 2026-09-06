"""Verify exact shop repair specialization of accepted operational sources."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).absolute().parents[1]

def verify() -> int:
    spec = json.loads((ROOT / "operations/source_derivation.json").read_bytes())
    if spec.get("schema_version") != 1:
        raise ValueError("derivation_schema")
    targets = set()
    for item in spec["files"]:
        source = Path(item["source"])
        target = Path(item["target"])
        if (source.is_absolute() or target.is_absolute() or ".." in source.parts or ".." in target.parts
                or target.as_posix() in targets):
            raise ValueError("derivation_path")
        targets.add(target.as_posix())
        raw = (ROOT.parent / source).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["source_sha256"]:
            raise ValueError("derivation_source")
        value = raw.decode("utf-8")
        for change in item["replacements"]:
            if value.count(change["old"]) != change["count"]:
                raise ValueError("derivation_preimage")
            value = value.replace(change["old"], change["new"])
        if value.encode("utf-8") != (ROOT / target).read_bytes():
            raise ValueError("derivation_target")
    return len(targets)

if __name__ == "__main__":
    print(json.dumps({"schema_version":1,"status":"passed","suite":"shop_map_permission_operations_derivation","check_count":verify()},separators=(",",":")))
