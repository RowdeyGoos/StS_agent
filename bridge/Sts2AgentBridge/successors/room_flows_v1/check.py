#!/usr/bin/env python3
"""Offline functional gate for the frozen Room Flows V1 source packet."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import types
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
RELEASE_CHECK = "26ff95959d506a3a3d7ea52f7a75efe6e2046661cc1692c05184339f909eeadd"
RELEASE_MANIFEST = "036e090daa509dfdf9f2eac7f8ab4d5b42a16aca08cecfe28a349402ef2af1a7"
RELEASE_INVENTORY = "c84bc80197c3b948971f4c1c70eb7def95be71eab903c0d278dcc3c318e1d0b0"
SDK_VERSION = "9.0.303"


def fail(code: str) -> None:
    raise SystemExit(code)


def load_release() -> types.ModuleType:
    path = ROOT.parent / "item_release_v1" / "check.py"
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if stat.S_ISLNK(current.lstat().st_mode):
            fail("release_helper_link")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != RELEASE_CHECK:
        fail("release_helper_identity")
    module = types.ModuleType("verified_item_release_checker")
    module.__file__ = str(path)
    exec(compile(data, str(path), "exec"), module.__dict__)
    return module


def _properties(*values: tuple[str, str]) -> dict[str, str]:
    return dict(values)


PROJECTS = {
    "common/Sts2AgentBridge.RoomFlowsV1.Common.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Library"),
                    ("AssemblyName", "Sts2AgentBridge.RoomFlowsV1.Common"),
                    ("EnableDefaultCompileItems", "false")),
        ("RoomFlowContracts.cs", "EventItemChildContracts.cs"),
        ("../../item_v1/core/Sts2AgentBridge.ItemV1.Core.csproj",), False),
    "broker/Sts2AgentBridge.RoomFlowsV1.Broker.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Library"),
                    ("EnableDefaultCompileItems", "false")),
        ("FrozenEventItemChildBroker.cs",),
        ("../common/Sts2AgentBridge.RoomFlowsV1.Common.csproj",
         "../../item_wire_v1/producer/Sts2AgentBridge.ItemV1.Wire.csproj"), False),
    "broker_tests/Sts2AgentBridge.RoomFlowsV1.Broker.Tests.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Exe"),
                    ("EnableDefaultCompileItems", "false")),
        ("Program.cs",), ("../broker/Sts2AgentBridge.RoomFlowsV1.Broker.csproj",), False),
    "shop/core/Sts2AgentBridge.RoomFlowsV1.Shop.Core.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Library"),
                    ("AssemblyName", "Sts2AgentBridge.RoomFlowsV1.Shop.Core"),
                    ("RootNamespace", "Sts2AgentBridge.Successors.RoomFlowsV1.Shop"),
                    ("EnableDefaultCompileItems", "false")),
        ("ShopV1Contracts.cs", "ShopV1CanonicalEncoder.cs", "ShopV1Session.cs"),
        ("../../common/Sts2AgentBridge.RoomFlowsV1.Common.csproj",), False),
    "shop/tests/Sts2AgentBridge.RoomFlowsV1.Shop.Tests.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Exe"),
                    ("AssemblyName", "Sts2AgentBridge.RoomFlowsV1.Shop.Tests"),
                    ("RootNamespace", "Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Tests"),
                    ("EnableDefaultCompileItems", "false")),
        ("Program.cs",), ("../core/Sts2AgentBridge.RoomFlowsV1.Shop.Core.csproj",), False),
    "shop/native/Sts2AgentBridge.RoomFlowsV1.Shop.Native.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Library"),
                    ("AssemblyName", "Sts2AgentBridge.RoomFlowsV1.Shop.Native"),
                    ("RootNamespace", "Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native"),
                    ("EnableDefaultCompileItems", "false")),
        ("PinnedShopV1NativeAdapter.cs",),
        ("../core/Sts2AgentBridge.RoomFlowsV1.Shop.Core.csproj",), True),
    "event/core/Sts2AgentBridge.RoomFlowsV1.Event.Core.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Library"),
                    ("AssemblyName", "Sts2AgentBridge.RoomFlowsV1.Event.Core"),
                    ("RootNamespace", "Sts2AgentBridge.Successors.RoomFlowsV1.Event"),
                    ("EnableDefaultCompileItems", "false")),
        ("EventV1Contracts.cs", "EventV1CanonicalEncoder.cs", "EventV1Session.cs"),
        ("../../common/Sts2AgentBridge.RoomFlowsV1.Common.csproj",), False),
    "event/tests/Sts2AgentBridge.RoomFlowsV1.Event.Tests.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Exe"),
                    ("AssemblyName", "Sts2AgentBridge.RoomFlowsV1.Event.Tests"),
                    ("RootNamespace", "Sts2AgentBridge.Successors.RoomFlowsV1.Event.Tests"),
                    ("EnableDefaultCompileItems", "false")),
        ("Program.cs",), ("../core/Sts2AgentBridge.RoomFlowsV1.Event.Core.csproj",), False),
    "event/native/Sts2AgentBridge.RoomFlowsV1.Event.Native.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Library"),
                    ("AssemblyName", "Sts2AgentBridge.RoomFlowsV1.Event.Native"),
                    ("RootNamespace", "Sts2AgentBridge.Successors.RoomFlowsV1.Event.Native"),
                    ("EnableDefaultCompileItems", "false")),
        ("PinnedEventV1NativeAdapter.cs",),
        ("../core/Sts2AgentBridge.RoomFlowsV1.Event.Core.csproj",
         "../../../item_v1/core/Sts2AgentBridge.ItemV1.Core.csproj"), True),
    "wire/Sts2AgentBridge.RoomFlowsV1.Wire.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Library"),
                    ("EnableDefaultCompileItems", "false")),
        ("RoomFlowWireService.cs", "RoomFlowWireCodec.cs"),
        ("../broker/Sts2AgentBridge.RoomFlowsV1.Broker.csproj",
         "../shop/core/Sts2AgentBridge.RoomFlowsV1.Shop.Core.csproj",
         "../event/core/Sts2AgentBridge.RoomFlowsV1.Event.Core.csproj"), False),
    "integration/Sts2AgentBridge.RoomFlowsV1.Integration.csproj": (
        _properties(("TargetFramework", "net9.0"), ("OutputType", "Exe"),
                    ("EnableDefaultCompileItems", "false")),
        ("Program.cs",), ("../wire/Sts2AgentBridge.RoomFlowsV1.Wire.csproj",), False),
}


def verify_properties(files: dict[str, bytes]) -> None:
    root = ET.fromstring(files["Directory.Build.props"])
    if root.tag != "Project" or root.attrib or len(root) != 1:
        fail("shared_properties_structure")
    group = root[0]
    if group.tag != "PropertyGroup" or group.attrib:
        fail("shared_properties_structure")
    expected = [
        ("LangVersion", {}, "12.0"), ("Nullable", {}, "enable"),
        ("ImplicitUsings", {}, "disable"), ("TreatWarningsAsErrors", {}, "true"),
        ("WarningLevel", {}, "9999"), ("AnalysisLevel", {}, "9.0"),
        ("Deterministic", {}, "true"), ("ContinuousIntegrationBuild", {}, "true"),
        ("DebugType", {}, "none"), ("DebugSymbols", {}, "false"),
        ("PathMap", {}, "$(MSBuildThisFileDirectory)=/_/room_flows_v1/"),
        ("PathMap", {"Condition": "'$(STS2GameDataDir)' != ''"},
         "$(PathMap),$(STS2GameDataDir)=/_/game/"),
    ]
    actual = [(node.tag, node.attrib, node.text) for node in group]
    if actual != expected or any(len(node) for node in group):
        fail("shared_properties_mismatch")


def verify_projects(files: dict[str, bytes]) -> None:
    verify_properties(files)
    project_names = {name for name in files if name.endswith(".csproj")}
    if project_names != set(PROJECTS):
        fail("project_inventory")
    compiled: set[str] = set()
    native_errors = (
        {"Condition": "'$(STS2GameDataDir)' == ''", "Text": "STS2GameDataDir is required."},
        {"Condition": "'$(STS2GameDataDir)' != '' and !$([System.IO.Path]::IsPathFullyQualified('$(STS2GameDataDir)'))",
         "Text": "STS2GameDataDir must be absolute."},
        {"Condition": "'$(STS2GameDataDir)' != '' and !Exists('$(STS2GameDataDir)/sts2.dll')",
         "Text": "Pinned sts2.dll is missing."},
        {"Condition": "'$(STS2GameDataDir)' != '' and !Exists('$(STS2GameDataDir)/GodotSharp.dll')",
         "Text": "Pinned GodotSharp.dll is missing."},
    )
    for name, (expected_properties, expected_compile, expected_projects, native) in PROJECTS.items():
        project = ET.fromstring(files[name])
        if project.tag != "Project" or project.attrib != {"Sdk": "Microsoft.NET.Sdk"}:
            fail("project_sdk")
        properties: dict[str, str | None] = {}
        compile_items: list[str] = []
        project_refs: list[str] = []
        references: list[tuple[str | None, str | None, str | None]] = []
        targets: list[ET.Element] = []
        for group in project:
            if group.tag == "PropertyGroup" and not group.attrib:
                for node in group:
                    if node.tag in properties or node.attrib or len(node):
                        fail("project_property_shape")
                    properties[node.tag] = node.text
            elif group.tag == "ItemGroup" and not group.attrib:
                for node in group:
                    if node.tag == "Compile" and set(node.attrib) == {"Include"} and not len(node):
                        compile_items.append(node.attrib["Include"])
                    elif node.tag == "ProjectReference" and set(node.attrib) == {"Include"} and not len(node):
                        project_refs.append(node.attrib["Include"])
                    elif node.tag == "Reference" and set(node.attrib) == {"Include"}:
                        children = {child.tag: child.text for child in node}
                        if (len(children) != 2 or any(child.attrib or len(child) for child in node) or
                                set(children) != {"HintPath", "Private"}):
                            fail("project_reference_shape")
                        references.append((node.attrib["Include"], children["HintPath"], children["Private"]))
                    else:
                        fail("project_item")
            elif group.tag == "Target":
                targets.append(group)
            else:
                fail("project_structure")
        if properties != expected_properties:
            fail("project_properties")
        if tuple(compile_items) != expected_compile or len(compile_items) != len(set(compile_items)):
            fail("project_compile_closure")
        if tuple(project_refs) != expected_projects or len(project_refs) != len(set(project_refs)):
            fail("project_dependency_closure")
        base = Path(name).parent
        for source in compile_items:
            if "$" in source or "*" in source or Path(source).is_absolute():
                fail("project_dynamic_source")
            resolved = (base / source).as_posix()
            if resolved not in files or not resolved.endswith(".cs"):
                fail("project_source_boundary")
            compiled.add(resolved)
        if native:
            if len(targets) != 1 or targets[0].attrib != {
                    "Name": "ValidatePinnedGameData", "BeforeTargets": "ResolveAssemblyReferences"}:
                fail("native_target_shape")
            if tuple(node.attrib for node in targets[0]) != native_errors or any(
                    node.tag != "Error" or len(node) or node.text for node in targets[0]):
                fail("native_target_body")
            if references != [
                    ("sts2", "$(STS2GameDataDir)/sts2.dll", "false"),
                    ("GodotSharp", "$(STS2GameDataDir)/GodotSharp.dll", "false")]:
                fail("native_reference_closure")
        elif targets or references:
            fail("pure_project_native_input")
    all_sources = {name for name in files if name.endswith(".cs")}
    if compiled != all_sources:
        fail("source_compile_closure")
    python_files = {name for name in files if name.endswith(".py")}
    if python_files != {"check.py", "host/room_flow_host.py", "integration/test_cross_language.py"}:
        fail("python_source_inventory")


def run(command: list[str], cwd: Path, environment: dict[str, str],
        *, allow_sdk_warning: bool = False) -> str:
    result = subprocess.run(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=180, check=False)
    warnings = [line for line in result.stderr.splitlines() if line]
    if (result.returncode or (warnings and not allow_sdk_warning) or
            (allow_sdk_warning and any(line !=
             "CSSM_ModuleLoad(): One or more parameters passed to a function were not valid."
             for line in warnings))):
        fail("offline_command_failed\n" + result.stdout + result.stderr)
    return result.stdout


def parse_exact(output: str, expected: dict[str, object], code: str) -> dict[str, object]:
    try:
        value = json.loads(output)
    except Exception:
        fail(code)
    if value != expected:
        fail(code)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--game-data-dir", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        fail("python_310_required")
    if (len(args.contract_sha256) != 64 or
            any(character not in "0123456789abcdef" for character in args.contract_sha256)):
        fail("contract_identity")

    release = load_release()
    boot = release.load_bootstrap()
    helper = boot.load_frozen_helper()
    own, inventory = helper.source_snapshot(ROOT, "room_flows_v1", args.contract_sha256)
    release_files, release_inventory = helper.source_snapshot(
        ROOT.parent / "item_release_v1", "item_release_v1", release.CONTRACT,
        RELEASE_MANIFEST, RELEASE_INVENTORY)
    bootstrap, bootstrap_inventory = helper.source_snapshot(
        ROOT.parent / "item_bootstrap_v1", "item_bootstrap_v1", boot.CONTRACT,
        release.BOOT_MANIFEST, release.BOOT_INVENTORY)
    transport, transport_inventory = helper.source_snapshot(
        ROOT.parent / "item_transport_v1", "item_transport_v1", boot.TRANSPORT_CONTRACT,
        boot.TRANSPORT_MANIFEST, boot.TRANSPORT_INVENTORY)
    wire, wire_inventory = helper.source_snapshot(
        ROOT.parent / "item_wire_v1", "item_wire_v1", helper.WIRE_CONTRACT,
        helper.WIRE_MANIFEST, helper.WIRE_INVENTORY)
    core, core_inventory = helper.source_snapshot(
        ROOT.parent / "item_v1", "item_v1", helper.CORE_CONTRACT,
        helper.CORE_MANIFEST, helper.CORE_INVENTORY)
    helper.verify_old_inventory(ROOT.parents[3])
    verify_projects(own)

    game = args.game_data_dir
    if not game.is_absolute() or str(game) != os.path.normpath(str(game)):
        fail("reference_root")
    helper.reject_links(game)
    references = {name: boot.pinned_reference(helper, game / name, size, digest)
                  for name, (size, digest) in boot.REFERENCES.items()}
    if args.scratch.parent != Path("/private/tmp"):
        fail("scratch_boundary")
    helper.create_scratch(args.scratch)
    source = args.scratch / "source" / "successors"
    components = (
        ("room_flows_v1", own), ("item_release_v1", release_files),
        ("item_bootstrap_v1", bootstrap), ("item_transport_v1", transport),
        ("item_wire_v1", wire), ("item_v1", core),
    )
    for component, files in components:
        for name, data in files.items():
            destination = source / component / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write(data)
    snapshot = source / "room_flows_v1"
    reference_root = args.scratch / "references"
    reference_root.mkdir()
    for name, data in references.items():
        with (reference_root / name).open("xb") as output:
            output.write(data)
    empty_game = args.scratch / "no_game_inputs"
    empty_game.mkdir()
    temporary = args.scratch / "tmp"
    temporary.mkdir(mode=0o700)
    environment = {
        "PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(temporary),
        "DOTNET_CLI_HOME": str(args.scratch / "cli"),
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false", "DOTNET_NOLOGO": "1",
        "DOTNET_MULTILEVEL_LOOKUP": "0", "DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER": "1",
        "MSBUILDDISABLENODEREUSE": "1", "NUGET_PACKAGES": str(args.scratch / "packages"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    dotnet = str(args.dotnet.resolve(strict=True))
    if run([dotnet, "--version"], snapshot, environment).strip() != SDK_VERSION:
        fail("sdk_mismatch")
    nuget = args.scratch / "NuGet.Config"
    nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
    artifacts = args.scratch / "artifacts"

    def build(relative: str, game_inputs: Path) -> tuple[Path, set[str]]:
        project = snapshot / relative
        common = ["--artifacts-path", str(artifacts),
                  "-p:STS2GameDataDir=" + str(game_inputs), "-m:1"]
        run([dotnet, "restore", str(project), "--configfile", str(nuget), *common,
             "-p:RestoreBuildInParallel=false", "-p:NuGetAudit=false"], snapshot, environment,
            allow_sdk_warning=True)
        run([dotnet, "build", str(project), "--no-restore", "-c", "Release", *common,
             "-p:BuildInParallel=false", "-p:UseSharedCompilation=false"], snapshot, environment,
            allow_sdk_warning=True)
        name = project.stem
        directory = artifacts / "bin" / name / "release"
        dll = directory / (name + ".dll")
        dependencies: set[str] = set()
        dependency_file = directory / (name + ".deps.json")
        if dependency_file.exists():
            value = json.loads(dependency_file.read_text())
            dependencies = {entry.rsplit("/", 1)[0] for entry in value["libraries"]}
        return dll, dependencies

    expected_dependencies = {
        "broker_tests/Sts2AgentBridge.RoomFlowsV1.Broker.Tests.csproj": {
            "Sts2AgentBridge.RoomFlowsV1.Broker.Tests", "Sts2AgentBridge.RoomFlowsV1.Broker",
            "Sts2AgentBridge.RoomFlowsV1.Common", "Sts2AgentBridge.ItemV1.Wire",
            "Sts2AgentBridge.ItemV1.Core"},
        "shop/tests/Sts2AgentBridge.RoomFlowsV1.Shop.Tests.csproj": {
            "Sts2AgentBridge.RoomFlowsV1.Shop.Tests", "Sts2AgentBridge.RoomFlowsV1.Shop.Core",
            "Sts2AgentBridge.RoomFlowsV1.Common", "Sts2AgentBridge.ItemV1.Core"},
        "event/tests/Sts2AgentBridge.RoomFlowsV1.Event.Tests.csproj": {
            "Sts2AgentBridge.RoomFlowsV1.Event.Tests", "Sts2AgentBridge.RoomFlowsV1.Event.Core",
            "Sts2AgentBridge.RoomFlowsV1.Common", "Sts2AgentBridge.ItemV1.Core"},
        "integration/Sts2AgentBridge.RoomFlowsV1.Integration.csproj": {
            "Sts2AgentBridge.RoomFlowsV1.Integration", "Sts2AgentBridge.RoomFlowsV1.Wire",
            "Sts2AgentBridge.RoomFlowsV1.Broker", "Sts2AgentBridge.RoomFlowsV1.Shop.Core",
            "Sts2AgentBridge.RoomFlowsV1.Event.Core", "Sts2AgentBridge.RoomFlowsV1.Common",
            "Sts2AgentBridge.ItemV1.Wire", "Sts2AgentBridge.ItemV1.Core"},
    }
    assemblies: dict[str, Path] = {}
    for relative, expected in expected_dependencies.items():
        dll, dependencies = build(relative, empty_game)
        if dependencies != expected:
            fail("pure_dependency_boundary")
        assemblies[relative] = dll

    broker_output = run([dotnet, str(assemblies[
        "broker_tests/Sts2AgentBridge.RoomFlowsV1.Broker.Tests.csproj"])], snapshot, environment).strip()
    match = re.fullmatch(r"room_flows_broker_checks=([0-9]+)", broker_output)
    if match is None or int(match.group(1)) != 575:
        fail("broker_fixture_result")
    summaries: dict[str, object] = {
        "broker": {"schema_version": 1, "status": "passed",
                   "suite": "room_flows_v1_broker", "check_count": 575},
        "shop": parse_exact(run([dotnet, str(assemblies[
            "shop/tests/Sts2AgentBridge.RoomFlowsV1.Shop.Tests.csproj"])], snapshot, environment),
            {"schema_version": 1, "status": "passed", "suite": "room_flows_v1_shop",
             "check_count": 13}, "shop_fixture_result"),
        "event": parse_exact(run([dotnet, str(assemblies[
            "event/tests/Sts2AgentBridge.RoomFlowsV1.Event.Tests.csproj"])], snapshot, environment),
            {"schema_version": 1, "status": "passed", "suite": "room_flows_v1_event",
             "check_count": 36}, "event_fixture_result"),
    }
    integration = assemblies["integration/Sts2AgentBridge.RoomFlowsV1.Integration.csproj"]
    summaries["wire"] = parse_exact(
        run([dotnet, str(integration), "selftest"], snapshot, environment),
        {"schema_version": 1, "status": "passed", "suite": "room_flows_wire",
         "check_count": 16}, "wire_fixture_result")
    cross = parse_exact(run([
        sys.executable, "-B", "-I", "-S", str(snapshot / "integration" / "test_cross_language.py"),
        "--dotnet", dotnet, "--fixture", str(integration), "--item-host",
        str(source / "item_wire_v1" / "host" / "item_host.py")], snapshot, environment),
        {"schema_version": 1, "status": "passed", "suite": "room_flows_cross_language",
         "check_count": 192}, "cross_language_result")
    summaries["cross_language"] = cross

    native: dict[str, object] = {}
    for flow in ("shop", "event"):
        relative = f"{flow}/native/Sts2AgentBridge.RoomFlowsV1.{flow.title()}.Native.csproj"
        dll, dependencies = build(relative, reference_root)
        expected = {
            f"Sts2AgentBridge.RoomFlowsV1.{flow.title()}.Native",
            f"Sts2AgentBridge.RoomFlowsV1.{flow.title()}.Core",
            "Sts2AgentBridge.RoomFlowsV1.Common", "Sts2AgentBridge.ItemV1.Core"}
        if dependencies != expected:
            fail("native_dependency_boundary")
        native[flow] = {"assembly_sha256": hashlib.sha256(dll.read_bytes()).hexdigest(),
                        "compiled": True, "executed": False}

    frozen_inventories = {
        "item_v1": core_inventory, "item_wire_v1": wire_inventory,
        "item_transport_v1": transport_inventory, "item_bootstrap_v1": bootstrap_inventory,
        "item_release_v1": release_inventory,
    }
    expected_inventories = {
        "item_v1": helper.CORE_INVENTORY, "item_wire_v1": helper.WIRE_INVENTORY,
        "item_transport_v1": boot.TRANSPORT_INVENTORY,
        "item_bootstrap_v1": release.BOOT_INVENTORY,
        "item_release_v1": RELEASE_INVENTORY,
    }
    if frozen_inventories != expected_inventories:
        fail("frozen_inventory_result")
    result = {
        "schema_version": 1, "status": "passed", "suite": "room_flows_v1_offline",
        "source_inventory_sha256": inventory, "frozen_source_inventories": frozen_inventories,
        "old_bridge_file_count": 48, "old_bridge_inventory_sha256": helper.OLD_INVENTORY,
        "synthetic": summaries, "native": native, "pinned_reference_count": len(references),
        "native_assemblies_executed": False, "live_enabled": False,
    }
    (args.scratch / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
