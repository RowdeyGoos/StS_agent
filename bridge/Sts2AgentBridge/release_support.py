"""Current-source and release identities; no predecessor code or live I/O.

Development reads the current tree. A successful release gate writes a manifest
outside it; live clients require that manifest's separately retained SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET

SDK_VERSION = "9.0.303"
REFERENCES = {
    "sts2.dll": (9363456, "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18"),
    "GodotSharp.dll": (5613568, "0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289"),
    "0Harmony.dll": (2328064, "ef1898322c9f5c86dc1b0758b272a9c440823b4a41ca9a0b82a3aa6b3d206387"),
}
COMMON_COMPONENTS = ("items", "item_wire", "item_transport", "item_bootstrap")
TARGET_COMPONENTS = {"bridge": (*COMMON_COMPONENTS, "rooms", "cards", "events")}
PRODUCTION = {"bridge": "apps/bridge/production/Sts2AgentBridge.csproj"}
IGNORED = {"bin", "obj", "__pycache__", ".pytest_cache", "artifacts"}
SOURCE_SUFFIXES = {".py", ".cs", ".csproj", ".props", ".json"}


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_regular(path: Path, limit: int = 16 * 1024 * 1024) -> bytes:
    """Reject links, nonregular inputs, and replacement or mutation during read."""
    require(path.is_absolute() and str(path) == os.path.normpath(str(path)), "source_path")
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        require(not stat.S_ISLNK(current.lstat().st_mode), "source_link")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= limit, "source_shape")
        chunks = bytearray()
        while len(chunks) < before.st_size:
            chunk = os.read(fd, min(65536, before.st_size - len(chunks)))
            require(bool(chunk), "source_truncated")
            chunks.extend(chunk)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink,
                              s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(not os.read(fd, 1) and identity(before) == identity(os.fstat(fd))
                == identity(path.lstat()), "source_changed")
        return bytes(chunks)
    finally:
        os.close(fd)


def collect_sources(bridge: Path, targets: list[str]) -> dict[str, bytes]:
    roots = set()
    for target in targets:
        require(target in TARGET_COMPONENTS, "unknown_target")
        roots.add("apps/" + target)
        roots.update("components/" + name for name in TARGET_COMPONENTS[target])
    files = {}
    for name in ("check.py", "release_support.py", "global.json", "Directory.Build.props"):
        files[name] = read_regular(bridge / name)
    roots.add("tests/maintenance")
    for root in sorted(roots):
        for path in sorted((bridge / root).rglob("*")):
            relative = path.relative_to(bridge)
            if IGNORED.intersection(relative.parts):
                continue
            require(not path.is_symlink(), "source_link")
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                files[relative.as_posix()] = read_regular(path)
    # Follow explicit project inputs to shared legacy protocol/adapter sources.
    # Historical deployment projects and their checkers are never discovered here.
    pending = [p for p in files if p.endswith(".csproj")]
    seen = set()
    while pending:
        project = pending.pop()
        if project in seen:
            continue
        seen.add(project)
        for node in ET.fromstring(files[project]).iter():
            if node.tag not in ("Compile", "ProjectReference"):
                continue
            name = node.attrib["Include"]
            require(not any(c in name for c in "*?$\\") and not Path(name).is_absolute(), "dynamic_input")
            name = os.path.normpath(str(Path(project).parent / name))
            require(name.startswith(("apps/", "components/", "src/")), "input_boundary")
            if name not in files:
                files[name] = read_regular(bridge / name)
            if node.tag == "ProjectReference":
                pending.append(name)
    # The actual original combat client transport is a maintained consumer.
    for name in ("tools/probe_live.py", "tools/probe_live_fixtures.py",
                 "tools/decision_providers.py", "tools/tool_common.py"):
        if (bridge / name).is_file():
            files[name] = read_regular(bridge / name)
    return dict(sorted(files.items()))


def inventory(files: dict[str, bytes]) -> tuple[dict[str, str], str]:
    hashes = {name: sha(data) for name, data in sorted(files.items())}
    digest = sha("".join(value + "  " + name + "\n" for name, value in hashes.items()).encode())
    return hashes, digest


def project_closure(files: dict[str, bytes], project: str) -> tuple[set[str], set[str]]:
    pending, projects, compiled = [project], set(), set()
    while pending:
        name = pending.pop()
        if name in projects:
            continue
        require(name in files, "missing_project")
        projects.add(name)
        tree = ET.fromstring(files[name])
        require(tree.findtext(".//EnableDefaultCompileItems") == "false", "implicit_compile")
        for node in tree.iter():
            require(node.tag not in ("PackageReference", "Import", "Exec", "UsingTask",
                                     "EmbeddedResource", "Content"), "dynamic_build")
            if node.tag in ("Compile", "ProjectReference"):
                value = node.attrib["Include"]
                require(value and not Path(value).is_absolute()
                        and not any(c in value for c in "*?$\\"), "dynamic_input")
                target = os.path.normpath(str(Path(name).parent / value))
                require(target in files and target.startswith(("apps/", "components/", "src/")), "input_boundary")
                if node.tag == "Compile":
                    compiled.add(target)
                else:
                    pending.append(target)
            if node.tag == "Reference":
                reference = node.attrib.get("Include")
                require(reference in ("sts2", "GodotSharp", "0Harmony"), "reference_boundary")
                require(node.findtext("HintPath") in (
                    "$(HarmonyPath)", "$(STS2GameDataDir)/0Harmony.dll",
                    "$(STS2GameDataDir)/sts2.dll", "$(STS2GameDataDir)/GodotSharp.dll"), "reference_path")
                if reference in ("sts2", "GodotSharp"):
                    require(node.findtext("Private") == "false", "copied_game_reference")
    return projects, compiled


def validate_sources(files: dict[str, bytes], targets: list[str], *, release: bool = False) -> dict[str, int]:
    projects = sorted(name for name in files if name.endswith(".csproj"))
    for project in projects:
        project_closure(files, project)
    for target in targets:
        _, compiled = project_closure(files, PRODUCTION[target])
        require(sum(b'[MegaCrit.Sts2.Core.Modding.ModInitializer(' in files[p]
                    for p in compiled) == 1, "single_initializer")
        require(not any(b"#define BRIDGE_TEST_SEAM" in files[p] for p in compiled), "production_test_seam")
    return {"files": len(files), "projects": len(projects), "targets": len(targets)}


def verify_release_sources(bridge: Path, target: str, manifest: Path, expected_sha256: str) -> None:
    """Authenticate a passed current release before any live credential is read."""
    require(re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None, "release_digest")
    raw = read_regular(manifest)
    require(sha(raw) == expected_sha256, "release_identity")
    release = json.loads(raw)
    require(type(release) is dict and release.get("schema_version") == 1
            and release.get("target") == target and release.get("suite") == "release"
            and release.get("status") == "passed", "release_not_accepted")
    hashes, digest = inventory(collect_sources(bridge, [target]))
    require(release.get("files") == hashes and release.get("source_inventory_sha256") == digest,
            "release_source_mismatch")
    require(type(release.get("checks")) is dict and release["checks"]
            and all(row.get("status") == "passed" for row in release["checks"].values()), "release_checks")
