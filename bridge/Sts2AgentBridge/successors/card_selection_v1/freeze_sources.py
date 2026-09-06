#!/usr/bin/env python3
"""Create this reviewed component's initial source identity; never replace one."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import types

ROOT = Path(__file__).absolute().parent


def main() -> None:
    identity = ROOT / "source_identity.json"
    if identity.exists() or identity.is_symlink():
        raise ValueError("source_identity_already_exists")
    path = ROOT / "check.py"
    gate = types.ModuleType("card_selection_initial_freeze")
    gate.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), gate.__dict__)
    helper, _, _ = gate.frozen_sources()
    helper.reject_links(ROOT)
    files: dict[str, bytes] = {}
    for entry in sorted(ROOT.rglob("*")):
        relative = entry.relative_to(ROOT)
        if {"obj", "bin", "__pycache__"}.intersection(relative.parts):
            raise ValueError("generated_build_output_in_source")
        helper.reject_links(entry)
        if entry.is_file():
            files[relative.as_posix()] = helper.read_regular(entry)
    gate.verify_projects(files)
    manifest = {
        "schema_version": 1,
        "component": "card_selection_v1",
        "contract_sha256": gate.CONTRACT,
        "files": [{"path": name, "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(files.items())],
    }
    data = (json.dumps(manifest, indent=2) + "\n").encode("ascii")
    with identity.open("xb") as stream:
        stream.write(data)
    print(json.dumps({"schema_version": 1, "status": "created", "file_count": len(files),
                      "manifest_sha256": hashlib.sha256(data).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
