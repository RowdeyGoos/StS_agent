#!/usr/bin/env python3
"""Offline gate for the versioned item service and host; no game inputs."""
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
CORE = ROOT.parent / "item_v1"
WIRE_CONTRACT = "e138680c587914bc0ded9734bdd48cbcbb7b55354117c407953b12cf6edd1df1"
CORE_CONTRACT = "f955712311994dba6055dd473b8200dc6ca122dddcfb0baf223c0f7312b76869"
CORE_INVENTORY = "3b37c6646fce5ad076703829ffd91f8a4d03e51083431727b517b51af8ce9a99"
CORE_MANIFEST = "435219714fa6e667738685f9909396839c46c21612a50bc84a0fc58e584c938a"
OLD_INVENTORY = "a0ca37bb2d0ad36fcb68eafe5163ac8174074b0e6f861c69c2ac357873f75f2a"
SDK_VERSION = "9.0.303"
MAX_SOURCE_BYTES = 1024 * 1024


def fail(code: str) -> None:
    raise SystemExit(code)


def read_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    try:
        facts = os.fstat(descriptor)
        if not stat.S_ISREG(facts.st_mode) or not 0 <= facts.st_size <= MAX_SOURCE_BYTES:
            fail("source_shape_mismatch")
        data = bytearray()
        while len(data) < facts.st_size:
            part = os.read(descriptor, min(65536, facts.st_size - len(data)))
            if not part:
                fail("source_truncated")
            data.extend(part)
        if os.read(descriptor, 1):
            fail("source_grew")
        return bytes(data)
    finally:
        os.close(descriptor)


def reject_links(path: Path) -> None:
    current = Path(path.anchor)
    for segment in path.parts[1:]:
        current /= segment
        if os.path.lexists(current) and stat.S_ISLNK(os.lstat(current).st_mode):
            fail("symlink_path_rejected")


def source_snapshot(root: Path, component: str, contract: str,
                    expected_manifest: str | None = None,
                    expected_inventory: str | None = None) -> tuple[dict[str, bytes], str]:
    manifest_bytes = read_regular(root / "source_identity.json")
    if expected_manifest and hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest:
        fail("dependency_manifest_mismatch")
    manifest = json.loads(manifest_bytes)
    if (type(manifest) is not dict or manifest.get("schema_version") != 1 or
            manifest.get("component") != component or manifest.get("contract_sha256") != contract):
        fail("source_manifest_header_mismatch")
    entries = manifest.get("files")
    if type(entries) is not list or not entries:
        fail("source_manifest_entries_mismatch")
    files: dict[str, bytes] = {}
    lines: list[str] = []
    for entry in entries:
        if type(entry) is not dict or tuple(entry) != ("path", "sha256"):
            fail("source_manifest_entry_mismatch")
        name, digest = entry["path"], entry["sha256"]
        if (type(name) is not str or not name or Path(name).is_absolute() or
                ".." in Path(name).parts or name in files or
                type(digest) is not str or len(digest) != 64 or
                any(c not in "0123456789abcdef" for c in digest)):
            fail("source_manifest_value_mismatch")
        reject_links(root / name)
        content = read_regular(root / name)
        if hashlib.sha256(content).hexdigest() != digest:
            fail("source_digest_mismatch")
        files[name] = content
        lines.append(digest + "  " + name + "\n")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() and p.name != "source_identity.json" and
              "__pycache__" not in p.parts}
    if list(files) != sorted(files) or actual != set(files):
        fail("source_inventory_mismatch")
    inventory = hashlib.sha256("".join(lines).encode("ascii")).hexdigest()
    if expected_inventory and inventory != expected_inventory:
        fail("dependency_inventory_mismatch")
    files["source_identity.json"] = manifest_bytes
    return files, inventory


def verify_old_inventory(repository: Path) -> None:
    bridge = repository / "bridge" / "Sts2AgentBridge"
    source = bridge / "src"
    paths = [p for pattern in ("*.cs", "*.csproj") for p in source.rglob(pattern)
             if not {"bin", "obj"}.intersection(p.relative_to(source).parts[:-1])]
    paths += [bridge / name for name in ("Directory.Build.props", "global.json",
              "Sts2AgentBridge.sln", "package/Sts2AgentBridge.json")]
    paths.sort(key=lambda p: p.relative_to(repository).as_posix())
    records = []
    for path in paths:
        reject_links(path)
        records.append(hashlib.sha256(read_regular(path)).hexdigest() + "  " +
                       path.relative_to(repository).as_posix() + "\n")
    digest = hashlib.sha256("".join(records).encode("ascii")).hexdigest()
    if len(paths) != 48 or digest != OLD_INVENTORY:
        fail("old_bridge_inventory_mismatch")


def create_scratch(path: Path) -> None:
    base = Path("/private/tmp")
    if not path.is_absolute() or ".." in path.parts or path == base or os.path.lexists(path):
        fail("invalid_scratch")
    reject_links(path.parent)
    parent_real = path.parent.resolve(strict=True)
    if Path(os.path.commonpath((str(base.resolve()), str(parent_real)))) != base:
        fail("scratch_outside_boundary")
    path.mkdir()
    if path.is_symlink() or path.resolve(strict=True).parent != parent_real:
        fail("scratch_link_mismatch")


def run(command: list[str], cwd: Path, environment: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        fail("offline_command_failed\n" + result.stdout + result.stderr)
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        fail("python_310_required")
    wire_files, inventory = source_snapshot(ROOT, "item_wire_v1", WIRE_CONTRACT)
    core_files, _ = source_snapshot(CORE, "item_v1", CORE_CONTRACT, CORE_MANIFEST, CORE_INVENTORY)
    verify_old_inventory(ROOT.parents[3])
    create_scratch(args.scratch)
    snapshot = args.scratch / "source" / "item_wire_v1"
    for name, files in (("item_wire_v1", wire_files), ("item_v1", core_files)):
        for relative, content in files.items():
            destination = args.scratch / "source" / name / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write(content)
    environment = dict(os.environ)
    environment.update({
        "DOTNET_CLI_HOME": str(args.scratch / "cli"),
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false", "DOTNET_NOLOGO": "1",
        "DOTNET_MULTILEVEL_LOOKUP": "0", "MSBUILDDISABLENODEREUSE": "1",
        "NUGET_PACKAGES": str(args.scratch / "packages"), "PYTHONDONTWRITEBYTECODE": "1",
    })
    dotnet = args.dotnet.resolve(strict=True)
    if run([str(dotnet), "--version"], snapshot, environment).strip() != SDK_VERSION:
        fail("sdk_version_mismatch")
    config = args.scratch / "NuGet.Config"
    config.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
    artifacts = args.scratch / "artifacts"
    # The unchanged core PathMap expects a nonempty value; this directory is
    # deliberately empty. Neither project references native/game assemblies.
    empty_game = args.scratch / "no_game_inputs"
    empty_game.mkdir()
    property_arg = "-p:STS2GameDataDir=" + str(empty_game)
    project = snapshot / "producer_tests" / "Sts2AgentBridge.ItemV1.Wire.Tests.csproj"
    run([str(dotnet), "restore", str(project), "--configfile", str(config),
         "--artifacts-path", str(artifacts), property_arg, "-m:1",
         "-p:RestoreBuildInParallel=false", "-p:NuGetAudit=false"], snapshot, environment)
    run([str(dotnet), "build", str(project), "--no-restore", "-c", "Release",
         "--artifacts-path", str(artifacts), property_arg, "-m:1",
         "-p:BuildInParallel=false", "-p:UseSharedCompilation=false"], snapshot, environment)
    test_dir = artifacts / "bin" / "Sts2AgentBridge.ItemV1.Wire.Tests" / "release"
    dependencies = json.loads((test_dir / "Sts2AgentBridge.ItemV1.Wire.Tests.deps.json").read_text())
    libraries = {key.split("/")[0] for key in dependencies["libraries"]}
    if libraries != {"Sts2AgentBridge.ItemV1.Core", "Sts2AgentBridge.ItemV1.Wire",
                      "Sts2AgentBridge.ItemV1.Wire.Tests"}:
        fail("pure_dependency_boundary_mismatch")
    assembly = test_dir / "Sts2AgentBridge.ItemV1.Wire.Tests.dll"
    producer = json.loads(run([str(dotnet), str(assembly)], snapshot, environment))
    if producer != {"schema_version": 1, "status": "passed",
                    "suite": "item_v1_wire_producer", "check_count": 9}:
        fail("producer_gate_failed")
    host_script = (
        "import sys,unittest;sys.path.insert(0,sys.argv[1]);"
        "suite=unittest.defaultTestLoader.discover('host_tests',top_level_dir='.');"
        "result=unittest.TextTestRunner(verbosity=0).run(suite);"
        "assert result.wasSuccessful();print(result.testsRun)"
    )
    host_count = int(run([sys.executable, "-B", "-I", "-S", "-c", host_script, str(snapshot)],
                         snapshot, environment).strip())
    if host_count != 27:
        fail("host_test_count_mismatch")
    cross_script = (
        "import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
        "from cross_language import run_cross_language;"
        "print(json.dumps(run_cross_language(Path(sys.argv[2]),Path(sys.argv[3]),"
        "Path(sys.argv[4])),separators=(',',':')))"
    )
    cross = json.loads(run([sys.executable, "-B", "-I", "-S", "-c", cross_script,
                           str(snapshot), str(dotnet), str(assembly), str(snapshot / "vectors.json")],
                          snapshot, environment))
    if cross != {"case_count": 17, "maximum_response_body_bytes": 2890,
                 "conservative_ready_bound_bytes": 2906}:
        fail("cross_summary_mismatch")
    print(json.dumps({"schema_version": 1, "status": "passed", "suite": "item_wire_v1_offline",
                      "source_inventory_sha256": inventory, "core_inventory_sha256": CORE_INVENTORY,
                      "old_bridge_file_count": 48, "old_bridge_inventory_sha256": OLD_INVENTORY,
                      "producer": producer, "host_test_count": host_count, "cross_language": cross,
                      "game_inputs": "none", "live_enabled": False}, separators=(",", ":")))


if __name__ == "__main__":
    main()
