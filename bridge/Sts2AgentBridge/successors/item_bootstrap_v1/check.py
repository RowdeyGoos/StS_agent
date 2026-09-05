#!/usr/bin/env python3
"""Verified-source, install-free item bootstrap candidate gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import types
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
CONTRACT = "77c2f48e8851548dd1212fa93ab2d9a205f38ea78a2db71380cf19b0904b5d0a"
TRANSPORT_CHECKER = "7e26118ce091b5deef2947462b598e95b4d9bf1dc85dd6d699e23e7cfbb8e49e"
TRANSPORT_MANIFEST = "e8cb05876cba695d8b4d22d5e12e597a4ea4d2fa7d525a160c9ccb223b91fe57"
TRANSPORT_INVENTORY = "53c605d4512e3e14addd0ab1506d8fc59b0b21f5838f24dca752de3356c44770"
TRANSPORT_CONTRACT = "df21fad6f407bbf95a367b5678db53ef9127efd643cc3816458d91f700e35479"
REFERENCES = {
    "sts2.dll": (9363456, "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18"),
    "GodotSharp.dll": (5613568, "0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289"),
}
FROZEN_LINKS = (
    "item_v1/core/ItemV1Contracts.cs",
    "item_v1/core/ItemV1CanonicalEncoder.cs",
    "item_v1/core/ItemV1Session.cs",
    "item_v1/native/PinnedItemV1NativeAdapter.cs",
    "item_wire_v1/producer/ItemWireV1Protocol.cs",
    "item_wire_v1/producer/ItemWireV1Codec.cs",
    "item_wire_v1/producer/ItemWireV1Service.cs",
    "item_transport_v1/runtime/ItemTransportConfiguration.cs",
    "item_transport_v1/runtime/ItemTransportProtocol.cs",
    "item_transport_v1/runtime/ItemTransportRuntime.cs",
    "item_transport_v1/runtime/OwnedByteFrameQueue.cs",
    "item_transport_v1/runtime/kernel/FixedTimeAuthenticator.cs",
    "item_transport_v1/runtime/kernel/MonotonicTokenBucket.cs",
)


def fail(code: str) -> None:
    raise SystemExit(code)


def load_frozen_helper() -> types.ModuleType:
    path = ROOT.parent / "item_transport_v1" / "check.py"
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if stat.S_ISLNK(current.lstat().st_mode):
            fail("helper_link_rejected")
    with path.open("rb") as stream:
        data = stream.read(1024 * 1024 + 1)
    if hashlib.sha256(data).hexdigest() != TRANSPORT_CHECKER:
        fail("helper_identity_mismatch")
    module = types.ModuleType("verified_item_transport_checker")
    module.__file__ = str(path)
    exec(compile(data, str(path), "exec"), module.__dict__)
    return module


def pinned_reference(helper: types.ModuleType, path: Path, size: int, digest: str) -> bytes:
    helper.reject_links(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != size:
            fail("reference_shape_mismatch")
        data = bytearray()
        while len(data) < size:
            block = os.read(fd, min(65536, size - len(data)))
            if not block:
                fail("reference_truncated")
            data.extend(block)
        after = os.fstat(fd)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid,
                                  value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if (os.read(fd, 1) or identity(before) != identity(after) or
                hashlib.sha256(data).hexdigest() != digest):
            fail("reference_identity_mismatch")
        return bytes(data)
    finally:
        os.close(fd)


def run(command: list[str], cwd: Path, environment: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        fail("offline_command_failed\n" + result.stdout + result.stderr)
    return result.stdout



def verify_pure_projects(files: dict[str, bytes]) -> None:
    projects = (
        ("operator_tests/Sts2AgentBridge.ItemV1.Operator.Tests.csproj",
         "Sts2AgentBridge.ItemV1.Operator.Tests", "operator", {"Program.cs"}),
        ("lifecycle_tests/Sts2AgentBridge.ItemV1.Bootstrap.Tests.csproj",
         "Sts2AgentBridge.ItemV1.Bootstrap.Tests", "lifecycle", {"Program.cs"}),
        ("production/ItemV1.CandidateInspection.csproj",
         "ItemV1.CandidateInspection", None, {"InspectCandidate.cs"}),
    )
    for path, name, source_dir, local in projects:
        project = ET.fromstring(files[path])
        if project.tag != "Project" or project.attrib != {"Sdk": "Microsoft.NET.Sdk"}:
            fail("pure_project_sdk")
        if any(group.tag not in {"PropertyGroup", "ItemGroup"} or group.attrib for group in project):
            fail("pure_project_structure")
        properties = {}
        for group in project.findall("PropertyGroup"):
            for node in group:
                if node.tag in properties or node.attrib or len(node):
                    fail("pure_project_property_shape")
                properties[node.tag] = node.text
        expected = {"TargetFramework": "net9.0", "OutputType": "Exe",
                    "AssemblyName": name, "EnableDefaultCompileItems": "false"}
        if "RootNamespace" in properties:
            expected["RootNamespace"] = "Sts2AgentBridge.Successors.ItemBootstrapV1"
        if source_dir == "operator":
            expected["DefineConstants"] = "$(DefineConstants);ITEM_BOOTSTRAP_TEST_SEAM"
        if properties != expected:
            fail("pure_project_properties")
        includes = []
        for group in project.findall("ItemGroup"):
            for node in group:
                if (node.tag != "Compile" or len(node) or
                        set(node.attrib) - {"Include", "Link"} or "Include" not in node.attrib):
                    fail("pure_project_items")
                includes.append(node.attrib["Include"])
        expected_sources = set(local)
        if source_dir:
            expected_sources.update("../" + path for path in files
                                    if path.startswith(source_dir + "/") and path.endswith(".cs"))
        if len(includes) != len(expected_sources) or set(includes) != expected_sources:
            fail("pure_compile_inventory")
    props = ET.fromstring(files["Directory.Build.props"])
    if (props.tag != "Project" or props.attrib or len(props) != 1 or
            props[0].tag != "PropertyGroup" or props[0].attrib):
        fail("shared_properties_structure")
    values = {node.tag: node.text for node in props[0]}
    required = {
        "ImportDirectoryBuildTargets": "false", "LangVersion": "12.0", "Nullable": "enable",
        "ImplicitUsings": "disable", "TreatWarningsAsErrors": "true", "WarningLevel": "9999",
        "AllowUnsafeBlocks": "false", "Deterministic": "true", "ContinuousIntegrationBuild": "true",
        "AssemblyVersion": "1.0.0.0", "FileVersion": "1.0.0.0", "Version": "1.0.0",
        "InformationalVersion": "1.0.0", "IncludeSourceRevisionInInformationalVersion": "false",
        "DebugType": "None", "DebugSymbols": "false", "RestoreIgnoreFailedSources": "false",
        "PathMap": "$(MSBuildThisFileDirectory)..=/_/successors/,$(STS2GameDataDir)=/_/game/",
    }
    if values != required or len(props[0]) != len(required) or any(node.attrib or len(node) for node in props[0]):
        fail("shared_properties_mismatch")


def verify_project(files: dict[str, bytes]) -> list[str]:
    project = ET.fromstring(files["production/Sts2AgentBridgeItemV1.csproj"])
    if (project.tag != "Project" or project.attrib != {"Sdk": "Microsoft.NET.Sdk"} or
            any(group.tag not in {"PropertyGroup", "ItemGroup"} or group.attrib for group in project) or
            any(node.tag not in {"Compile", "Reference"} for group in project.findall("ItemGroup") for node in group)):
        fail("production_project_structure")
    properties = {node.tag: node.text for group in project.findall("PropertyGroup") for node in group}
    expected_properties = {"EnableDefaultCompileItems": "false", "AssemblyName": "Sts2AgentBridgeItemV1",
                           "TargetFramework": "net9.0", "OutputType": "Library",
                           "RootNamespace": "Sts2AgentBridge.Successors.ItemBootstrapV1"}
    if (properties != expected_properties or
            sum(len(group) for group in project.findall("PropertyGroup")) != len(expected_properties) or
            any(node.attrib or len(node) for group in project.findall("PropertyGroup") for node in group)):
        fail("production_project_properties")
    includes = [node.attrib.get("Include") for node in project.findall(".//Compile")]
    own_sources = sorted(name for name in files
                         if name.endswith(".cs") and name.split("/")[0] in
                         {"operator", "lifecycle", "native"})
    expected = {"../../" + name for name in FROZEN_LINKS}
    expected.update("../" + name for name in own_sources)
    if len(includes) != len(expected) or set(includes) != expected:
        fail("production_compile_inventory")
    if any("Condition" in node.attrib for node in project.findall(".//Compile")):
        fail("conditional_production_source")
    refs = project.findall(".//Reference")
    if ({node.attrib.get("Include") for node in refs} != {"sts2", "GodotSharp"} or len(refs) != 2 or
            any(node.findtext("Private") != "false" or
                node.findtext("HintPath") != "$(STS2GameDataDir)/" + node.attrib["Include"] + ".dll"
                for node in refs)):
        fail("production_reference_inventory")
    return own_sources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", required=True, type=Path)
    parser.add_argument("--game-data-dir", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        fail("python_310_required")
    helper = load_frozen_helper()
    own, inventory = helper.source_snapshot(ROOT, "item_bootstrap_v1", CONTRACT)
    transport, _ = helper.source_snapshot(
        ROOT.parent / "item_transport_v1", "item_transport_v1", TRANSPORT_CONTRACT,
        TRANSPORT_MANIFEST, TRANSPORT_INVENTORY)
    wire, _ = helper.source_snapshot(
        ROOT.parent / "item_wire_v1", "item_wire_v1", helper.WIRE_CONTRACT,
        helper.WIRE_MANIFEST, helper.WIRE_INVENTORY)
    core, _ = helper.source_snapshot(
        ROOT.parent / "item_v1", "item_v1", helper.CORE_CONTRACT,
        helper.CORE_MANIFEST, helper.CORE_INVENTORY)
    helper.verify_old_inventory(ROOT.parents[3])
    verify_pure_projects(own)
    own_sources = verify_project(own)
    game = args.game_data_dir
    if not game.is_absolute() or ".." in game.parts or "." in game.parts:
        fail("invalid_reference_root")
    helper.reject_links(game)
    references = {name: pinned_reference(helper, game / name, size, digest)
                  for name, (size, digest) in REFERENCES.items()}
    if args.scratch.parent != Path("/private/tmp"):
        fail("scratch_must_be_direct_physical_tmp_child")
    helper.create_scratch(args.scratch)
    snapshot_parent = args.scratch / "source" / "successors"
    for component, sources in (("item_bootstrap_v1", own), ("item_transport_v1", transport),
                               ("item_wire_v1", wire), ("item_v1", core)):
        for name, data in sources.items():
            destination = snapshot_parent / component / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write(data)
    snapshot = snapshot_parent / "item_bootstrap_v1"
    ref_root = args.scratch / "references"
    ref_root.mkdir()
    for name, data in references.items():
        with (ref_root / name).open("xb") as output:
            output.write(data)
    (args.scratch / "tmp").mkdir(mode=0o700)
    environment = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(args.scratch / "tmp")}
    environment.update({
        "DOTNET_CLI_HOME": str(args.scratch / "cli"), "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false",
        "DOTNET_NOLOGO": "1", "DOTNET_MULTILEVEL_LOOKUP": "0", "MSBUILDDISABLENODEREUSE": "1",
        "NUGET_PACKAGES": str(args.scratch / "packages"), "PYTHONDONTWRITEBYTECODE": "1",
    })
    dotnet = str(args.dotnet.resolve(strict=True))
    if run([dotnet, "--version"], snapshot, environment).strip() != "9.0.303":
        fail("sdk_version_mismatch")
    nuget = args.scratch / "NuGet.Config"
    nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
    artifacts = args.scratch / "artifacts"
    empty_game = args.scratch / "no_game_inputs"
    empty_game.mkdir()

    def build(relative: str, refs: Path) -> Path:
        project = snapshot / relative
        common = ["--artifacts-path", str(artifacts), "-p:STS2GameDataDir=" + str(refs), "-m:1"]
        run([dotnet, "restore", str(project), "--configfile", str(nuget), *common,
             "-p:RestoreBuildInParallel=false", "-p:NuGetAudit=false"], snapshot, environment)
        run([dotnet, "build", str(project), "--no-restore", "-c", "Release", *common,
             "-p:BuildInParallel=false", "-p:UseSharedCompilation=false"], snapshot, environment)
        return artifacts / "bin" / project.stem / "release"

    inspection = build("production/ItemV1.CandidateInspection.csproj", empty_game)
    inspection_name = "ItemV1.CandidateInspection"
    deps = json.loads((inspection / (inspection_name + ".deps.json")).read_text())
    if set(deps["libraries"]) != {inspection_name + "/1.0.0"}:
        fail("inspection_dependency_mismatch")
    inspection_dll = str(inspection / (inspection_name + ".dll"))

    summaries = {}
    for relative, suite in (
        ("operator_tests/Sts2AgentBridge.ItemV1.Operator.Tests.csproj", "item_v1_operator"),
        ("lifecycle_tests/Sts2AgentBridge.ItemV1.Bootstrap.Tests.csproj", "item_v1_bootstrap"),
    ):
        directory = build(relative, empty_game)
        name = Path(relative).stem
        deps = json.loads((directory / (name + ".deps.json")).read_text())
        if set(deps["libraries"]) != {name + "/1.0.0"}:
            fail("synthetic_dependency_mismatch")
        test_dll = str(directory / (name + ".dll"))
        pure = json.loads(run([dotnet, inspection_dll, "--pure", test_dll], snapshot, environment))
        if pure != {"schema_version": 1, "status": "passed", "scope": "framework_references_only",
                    "assembly_name": name}:
            fail("synthetic_assembly_reference_mismatch")
        command = [dotnet, test_dll]
        if suite == "item_v1_operator":
            command += ["--fixture-root", str(args.scratch.with_name(args.scratch.name + "-operator-fixture"))]
        summary = json.loads(run(command, snapshot, environment))
        expected_summary = {"schema_version": 1, "status": "passed", "suite": suite,
                            "check_count": 13 if suite == "item_v1_operator" else 24}
        if summary != expected_summary:
            fail("synthetic_result_mismatch")
        summaries[suite] = summary
    production = build("production/Sts2AgentBridgeItemV1.csproj", ref_root)
    dll = production / "Sts2AgentBridgeItemV1.dll"
    if {p.name for p in production.iterdir()} != {
            "Sts2AgentBridgeItemV1.dll", "Sts2AgentBridgeItemV1.deps.json"}:
        fail("candidate_output_inventory")
    surface = json.loads(run([dotnet, inspection_dll, str(dll)], snapshot, environment))
    expected_surface = {
        "schema_version": 1, "status": "passed", "scope": "candidate_metadata_only",
        "initializer_count": 1, "native_import_count": 13, "frozen_transport_test_method_count": 2,
        "nonframework_references": ["GodotSharp", "sts2"], "production_assembly_executed": False,
    }
    if surface != expected_surface:
        fail("candidate_metadata_mismatch")
    result = {
        "schema_version": 1, "status": "passed", "suite": "item_v1_bootstrap_candidate",
        "source_inventory_sha256": inventory, "frozen_link_count": len(FROZEN_LINKS),
        "new_production_source_count": len(own_sources), "synthetic": summaries,
        "metadata": surface, "dll_sha256": hashlib.sha256(dll.read_bytes()).hexdigest(),
        "live_enabled": False, "surface_release_gate": "pending", "package": "none",
    }
    (args.scratch / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
