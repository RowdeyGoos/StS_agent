#!/usr/bin/env python3
"""Reproducible offline source, pure-core, and compile-only native gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
EXPECTED_SDK = "9.0.303"
EXPECTED_STS2 = "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18"
EXPECTED_GODOT = "0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289"
EXPECTED_REFERENCE_SIZES = {"sts2.dll": 9363456, "GodotSharp.dll": 5613568}
MAXIMUM_REFERENCE_BYTES = 100 * 1024 * 1024
EXPECTED_TEST_OUTPUT = {
    "schema_version": 1,
    "status": "passed",
    "suite": "item_v1_core",
    "check_count": 10,
}


def _fail(message: str) -> None:
    raise SystemExit(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            block = source.read(65536)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if os.path.lexists(current) and stat.S_ISLNK(os.lstat(current).st_mode):
            _fail("symlink path component rejected")


def _new_scratch(path: Path) -> Path:
    base = Path("/private/tmp")
    if (not path.is_absolute() or ".." in path.parts or "." in path.parts or
            path == base or os.path.lexists(path)):
        _fail("scratch must be a new absolute directory below /private/tmp")
    _reject_symlink_components(path.parent)
    base_real = base.resolve(strict=True)
    parent_real = path.parent.resolve(strict=True)
    try:
        common = Path(os.path.commonpath((str(base_real), str(parent_real))))
    except ValueError:
        _fail("scratch containment mismatch")
    if common != base_real:
        _fail("scratch containment mismatch")
    path.mkdir()
    if path.is_symlink() or path.resolve(strict=True).parent != parent_real:
        _fail("scratch identity mismatch")
    return path


def _read_pinned_reference(path: Path, expected_hash: str, expected_size: int) -> bytes:
    if expected_size < 1 or expected_size > MAXIMUM_REFERENCE_BYTES:
        _fail("reference bound mismatch")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except OSError:
        _fail("pinned reference open failed")
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != expected_size:
            _fail("pinned reference shape mismatch")
        content = bytearray()
        digest = hashlib.sha256()
        while len(content) < expected_size:
            block = os.read(descriptor, min(65536, expected_size - len(content)))
            if not block:
                _fail("pinned reference truncated")
            content.extend(block)
            digest.update(block)
        if os.read(descriptor, 1) or digest.hexdigest() != expected_hash:
            _fail("pinned reference identity mismatch")
        return bytes(content)
    finally:
        os.close(descriptor)


def _run(command: list[str], environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        _fail("offline command failed: " + " ".join(command) + "\n" +
              completed.stdout + completed.stderr)
    return completed


def _verify_sources() -> str:
    manifest_path = ROOT / "source_identity.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (type(manifest) is not dict or manifest.get("schema_version") != 1 or
            manifest.get("component") != "item_v1" or
            manifest.get("contract_sha256") !=
            "f955712311994dba6055dd473b8200dc6ca122dddcfb0baf223c0f7312b76869"):
        _fail("source identity header mismatch")
    files = manifest.get("files")
    if type(files) is not list or not files:
        _fail("source identity file list mismatch")
    expected_paths: set[str] = set()
    canonical_lines: list[str] = []
    for entry in files:
        if type(entry) is not dict or tuple(entry) != ("path", "sha256"):
            _fail("source identity entry shape mismatch")
        relative = entry["path"]
        expected = entry["sha256"]
        if (type(relative) is not str or not relative or relative.startswith("/") or
                ".." in Path(relative).parts or relative in expected_paths or
                type(expected) is not str or len(expected) != 64):
            _fail("source identity entry value mismatch")
        path = ROOT / relative
        if not path.is_file() or _sha256(path) != expected:
            _fail("source identity mismatch: " + relative)
        expected_paths.add(relative)
        canonical_lines.append(expected + "  " + relative + "\n")
    actual_paths = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and path.name != "source_identity.json" and
        "__pycache__" not in path.parts
    }
    if actual_paths != expected_paths:
        _fail("source identity inventory mismatch")
    return hashlib.sha256("".join(canonical_lines).encode("ascii")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", required=True, type=Path)
    parser.add_argument("--game-data-dir", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    arguments = parser.parse_args()
    dotnet = arguments.dotnet.resolve(strict=True)
    game = arguments.game_data_dir
    if (not game.is_absolute() or ".." in game.parts or "." in game.parts or
            not game.is_dir()):
        _fail("game data directory shape mismatch")
    _reject_symlink_components(game)
    scratch = _new_scratch(arguments.scratch)
    source_manifest_digest = _verify_sources()
    reference_bytes = {
        "sts2.dll": _read_pinned_reference(
            game / "sts2.dll", EXPECTED_STS2, EXPECTED_REFERENCE_SIZES["sts2.dll"]),
        "GodotSharp.dll": _read_pinned_reference(
            game / "GodotSharp.dll", EXPECTED_GODOT,
            EXPECTED_REFERENCE_SIZES["GodotSharp.dll"]),
    }

    cli_home = scratch / "cli"
    packages = scratch / "packages"
    artifacts = scratch / "artifacts"
    references = scratch / "references"
    cli_home.mkdir()
    packages.mkdir()
    artifacts.mkdir()
    references.mkdir()
    for name, content in reference_bytes.items():
        with (references / name).open("xb") as destination:
            destination.write(content)
    config = scratch / "NuGet.Config"
    config.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<configuration><packageSources><clear /></packageSources></configuration>\n',
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment.update({
        "DOTNET_CLI_HOME": str(cli_home),
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false",
        "DOTNET_NOLOGO": "1",
        "DOTNET_MULTILEVEL_LOOKUP": "0",
        "MSBUILDDISABLENODEREUSE": "1",
        "NUGET_PACKAGES": str(packages),
    })
    version = _run([str(dotnet), "--version"], environment).stdout.strip()
    if version != EXPECTED_SDK:
        _fail("SDK identity mismatch")

    game_property = "-p:STS2GameDataDir=" + str(references)
    test_project = ROOT / "tests" / "Sts2AgentBridge.ItemV1.Tests.csproj"
    native_project = ROOT / "native" / "Sts2AgentBridge.ItemV1.Native.csproj"
    common_restore = ["--configfile", str(config), "--artifacts-path", str(artifacts)]
    common_build = ["--configuration", "Release", "--no-restore",
                    "--artifacts-path", str(artifacts), game_property]

    _run([str(dotnet), "restore", str(test_project), *common_restore, game_property], environment)
    _run([str(dotnet), "build", str(test_project), *common_build], environment)
    test_dir = artifacts / "bin" / "Sts2AgentBridge.ItemV1.Tests" / "release"
    dependencies = (test_dir / "Sts2AgentBridge.ItemV1.Tests.deps.json").read_text(
        encoding="utf-8")
    if ("Sts2AgentBridge.ItemV1.Native" in dependencies or "sts2" in dependencies or
            "GodotSharp" in dependencies):
        _fail("pure test dependency boundary mismatch")
    test = _run(
        [str(dotnet), str(test_dir / "Sts2AgentBridge.ItemV1.Tests.dll")],
        environment,
    )
    if test.stderr or json.loads(test.stdout) != EXPECTED_TEST_OUTPUT or \
            test.stdout != json.dumps(EXPECTED_TEST_OUTPUT, separators=(",", ":")) + "\n":
        _fail("pure core fixture output mismatch")

    _run([str(dotnet), "restore", str(native_project), *common_restore, game_property], environment)
    _run([str(dotnet), "build", str(native_project), *common_build], environment)
    native_dll = (artifacts / "bin" / "Sts2AgentBridge.ItemV1.Native" / "release" /
                  "Sts2AgentBridge.ItemV1.Native.dll")
    if not native_dll.is_file():
        _fail("native compile output missing")

    print(json.dumps({
        "schema_version": 1,
        "status": "passed",
        "suite": "item_v1_offline",
        "core_check_count": 10,
        "native_adapter": "compile_only",
        "sdk_version": EXPECTED_SDK,
        "source_manifest_sha256": source_manifest_digest,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
