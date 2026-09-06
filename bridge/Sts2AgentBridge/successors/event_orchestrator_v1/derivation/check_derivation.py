#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import xml.etree.ElementTree as ET
MAXIMUM_SOURCE_BYTES = 256_000
def read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file(): raise ValueError("invalid source")
    data = path.read_bytes()
    if not data or len(data) > MAXIMUM_SOURCE_BYTES: raise ValueError("invalid source size")
    return data
def digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--source-root", required=True); args = parser.parse_args()
    root = Path(args.source_root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir(): return 2
    try:
        manifest = json.loads(read(Path(__file__).with_name("source_derivation.json")))
        if type(manifest) is not dict or list(manifest) != ["schema_version","sources","extraction","project_closure"] or manifest["schema_version"] != 1: raise ValueError("manifest shape")
        sources = manifest["sources"]
        if type(sources) is not dict or list(sources) != ["original","bound_item","parent","factories","rules","completion_adapter","project"]: raise ValueError("source list")
        values = {}; checks = 1
        for name, record in sources.items():
            if type(record) is not dict or list(record) != ["path","sha256"]: raise ValueError("source record")
            value = read(root / record["path"])
            if digest(value) != record["sha256"]: raise ValueError("source identity")
            values[name] = value; checks += 1
        extraction = manifest["extraction"]; old = values["original"].decode("utf-8"); start = old.index(extraction["start"])
        imports = old[:start]; imports = imports[:imports.index("/// <summary>")]
        imports = imports.replace(extraction["old_namespace"], extraction["new_namespace"])
        if (imports + old[start:]).encode("utf-8") != values["bound_item"]: raise ValueError("item extraction")
        checks += 1
        project = ET.fromstring(values["project"]); closure = manifest["project_closure"]
        actual_compile = [e.attrib.get("Include") for e in project.findall(".//Compile")]
        actual_projects = [e.attrib.get("Include") for e in project.findall(".//ProjectReference")]
        actual_refs = [e.attrib.get("Include") for e in project.findall(".//Reference")]
        actual_targets = [e.attrib.get("Name") for e in project.findall(".//Target")]
        if actual_compile != closure["compile"] or actual_projects != closure["project_reference"] or actual_refs != closure["reference"] or actual_targets != closure["target"]: raise ValueError("project closure")
        if project.findall(".//PackageReference") or project.findall(".//Import") or project.findall(".//Exec"): raise ValueError("project expansion")
        checks += 1
        print(json.dumps({"schema_version":1,"status":"passed","suite":"event_orchestrator_v1_native_derivation","check_count":checks},separators=(",",":"))); return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, ET.ParseError, json.JSONDecodeError):
        print('{"schema_version":1,"status":"failed","suite":"event_orchestrator_v1_native_derivation","check_count":0}'); return 1
if __name__ == "__main__": raise SystemExit(main())
