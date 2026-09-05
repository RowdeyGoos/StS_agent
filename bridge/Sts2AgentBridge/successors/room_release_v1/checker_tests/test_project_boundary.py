#!/usr/bin/env python3
"""Static regressions for the room release project's build-input boundary."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SUCCESSORS = ROOT.parent
sys.path.insert(0, str(ROOT))

import check as gate


def _files(component: str) -> dict[str, bytes]:
    root = SUCCESSORS / component
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
        and not {"bin", "obj", "__pycache__"}.intersection(path.relative_to(root).parts)
    }


def _components() -> dict[str, dict[str, bytes]]:
    names = (
        "item_v1",
        "item_wire_v1",
        "item_transport_v1",
        "item_bootstrap_v1",
        "item_release_v1",
        "room_flows_v1",
        "room_release_v1",
    )
    components = {name: _files(name) for name in names}
    production = components["room_release_v1"]["production/Sts2AgentBridgeRoomFlowsV1.csproj"]
    import xml.etree.ElementTree as ET

    source_paths = []
    for node in ET.fromstring(production).iter("Compile"):
        relative = node.attrib["Include"]
        normalized = os.path.normpath("room_release_v1/production/" + relative)
        source_paths.append("bridge/Sts2AgentBridge/successors/" + normalized)
    components["room_release_v1"]["policy/room_release_policy.json"] = json.dumps(
        {"source_files": [{"path": path} for path in sorted(source_paths)]},
        separators=(",", ":"),
    ).encode("ascii")
    return components


def _replace(data: bytes, before: bytes, after: bytes) -> bytes:
    if data.count(before) != 1:
        raise AssertionError("fixture mutation literal is not unique")
    return data.replace(before, after)


def _expect_rejected(components: dict[str, dict[str, bytes]]) -> None:
    try:
        gate.verify_projects(components)
    except ValueError:
        return
    raise AssertionError("mutated build input was accepted")


def main() -> int:
    base = _components()
    gate.verify_projects(base)
    checks = 1

    for name in (
        "Directory.Build.targets",
        "Extra.props",
        "compiler.rsp",
        "global.json",
        "NuGet.Config",
    ):
        changed = {component: dict(files) for component, files in base.items()}
        changed["room_release_v1"][name] = b"<Project />\n"
        _expect_rejected(changed)
        checks += 1

    props_path = "Directory.Build.props"
    for before, after in (
        (b"<ImportDirectoryBuildTargets>false</ImportDirectoryBuildTargets>",
         b"<ImportDirectoryBuildTargets>true</ImportDirectoryBuildTargets>"),
        (b"<LangVersion>12.0</LangVersion>",
         b"<LangVersion Condition=\"'1' == '1'\">12.0</LangVersion>"),
        (b"</Project>", b"  <Target Name=\"Injected\" />\n</Project>"),
    ):
        changed = {component: dict(files) for component, files in base.items()}
        changed["room_release_v1"][props_path] = _replace(
            changed["room_release_v1"][props_path], before, after)
        _expect_rejected(changed)
        checks += 1

    runtime_path = "runtime/Sts2AgentBridge.RoomFlowsV1.Transport.csproj"
    changed = {component: dict(files) for component, files in base.items()}
    changed["room_release_v1"][runtime_path] = _replace(
        changed["room_release_v1"][runtime_path],
        b"<TargetFramework>net9.0</TargetFramework>",
        b"<TargetFramework>net8.0</TargetFramework>")
    _expect_rejected(changed)
    checks += 1

    changed = {component: dict(files) for component, files in base.items()}
    changed["room_release_v1"][runtime_path] = _replace(
        changed["room_release_v1"][runtime_path],
        b"<PropertyGroup>", b"<PropertyGroup Condition=\"'1' == '1'\">")
    _expect_rejected(changed)
    checks += 1

    production_path = "production/Sts2AgentBridgeRoomFlowsV1.csproj"
    for before, after in (
        (b"Condition=\"'$(STS2GameDataDir)' == ''\"",
         b"Condition=\"'$(STS2GameDataDir)' != ''\""),
        (b'Text="STS2GameDataDir is required."',
         b'Text="An altered error."'),
    ):
        changed = {component: dict(files) for component, files in base.items()}
        changed["room_release_v1"][production_path] = _replace(
            changed["room_release_v1"][production_path], before, after)
        _expect_rejected(changed)
        checks += 1

    for injected in (
        b"  <Import Project=\"/private/tmp/injected.targets\" />\n",
        b"  <ItemGroup><PackageReference Include=\"Injected\" Version=\"1\" /></ItemGroup>\n",
    ):
        changed = {component: dict(files) for component, files in base.items()}
        changed["room_release_v1"][runtime_path] = _replace(
            changed["room_release_v1"][runtime_path], b"</Project>", injected + b"</Project>")
        _expect_rejected(changed)
        checks += 1

    print(json.dumps({
        "schema_version": 1,
        "status": "passed",
        "suite": "room_release_project_boundary",
        "check_count": checks,
        "candidate_executed": False,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
