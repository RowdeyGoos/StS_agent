#!/usr/bin/env python3
"""Offline card-selector gate; compiled game adapters are never executed."""
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

ROOT = Path(__file__).absolute().parent
PREVIOUS_CHECK = "d0771649b46ef995babe3b3acee713457bcdc27b74317f050cb1e9734adac7db"
PREVIOUS_MANIFEST = "14b94d4e0877743e3719ee7904875606fc5a0ae99eccbc4cfebee6bfc0f9f03a"
PREVIOUS_INVENTORY = "801977238c91238c5cc33106fe205152557bb0d5238121779f7809b114dbf9ae"
CONTRACT = "af8125ba2dd7bd8d7df85144f5a275d20a347ca7d4fe5bd5e666e53b3f57186c"
PROPS = "2b05edd4dbb4532b1e884c6267bf56c732b49415dc43a23245b3d0c3cc30265f"
PROJECT_HASHES: dict[str, str] = {
    "core/Sts2AgentBridge.CardSelectionV1.Core.csproj": "2a6859b09eac787bee3c3cebabc0a944a40848232888b1f60fb4bd1bc5c975a8",
    "native/Sts2AgentBridge.CardSelectionV1.Native.csproj": "a06bdc32cdae40d9fd5cfc4ec36aff1fbd844b703239e50fa01fe80a00a0c80a",
    "native_tests/Sts2AgentBridge.CardSelectionV1.Native.Tests.csproj": "89a35e16bd9ed848ca69f491fa54dbdc74c021ad9d9237e95f076be2645d8c35",
    "parent_native/Sts2AgentBridge.CardSelectionV1.Parent.Native.csproj": "fbd7f884783338561e6ce848a544e0a5be16ffb41de21de889ed2fc277662bd3",
    "parent_native_adapter_tests/Sts2AgentBridge.CardSelectionV1.Parent.Native.Adapter.Tests.csproj": "17a6f454df3b0344458861de515b83fbd3ff15afc46384c230915009695f5f43",
    "parent_native_tests/Sts2AgentBridge.CardSelectionV1.Parent.Native.Tests.csproj": "6df3df78be65e52b1d99285c0944145a5f5ddd2f8f3b10c84fd7ce1737875599",
    "parent_tests/Sts2AgentBridge.CardSelectionV1.Parent.Tests.csproj": "794f6bac8eecf97d79018e1cd6f98b00d1b12be7e44a6a5e20918b710bdefe5d",
    "parents/Sts2AgentBridge.CardSelectionV1.Parents.csproj": "aacb45bd46eccaf949aadbfc02a14db687df263c1f5151ab151ffbc413d85dda",
    "tests/Sts2AgentBridge.CardSelectionV1.Core.Tests.csproj": "c7c8d9669bd06de9a743165972c4421476d47f370eff093a3f6eaaa52627b80f",
    "wire/Sts2AgentBridge.CardSelectionV1.Wire.csproj": "ddafd4405e874b1b2de56b4f3e1318387d81cb10b5e1cf816580684a3f16d7ad",
    "wire_tests/Sts2AgentBridge.CardSelectionV1.Wire.Tests.csproj": "20fb79177ae77dbe99878789a55f75353611ebdfddeb07368d151efdeff7d998"
}
PURE_TESTS: tuple[tuple[str, str, int], ...] = (
    ("tests/Sts2AgentBridge.CardSelectionV1.Core.Tests.csproj", "card_selection_v1_core", 16),
    ("native_tests/Sts2AgentBridge.CardSelectionV1.Native.Tests.csproj", "card_selection_v1_native", 28),
    ("parent_tests/Sts2AgentBridge.CardSelectionV1.Parent.Tests.csproj", "card_selection_parent_v1", 12),
    ("parent_native_tests/Sts2AgentBridge.CardSelectionV1.Parent.Native.Tests.csproj", "card_selection_parent_v1_native", 5),
    ("parent_native_adapter_tests/Sts2AgentBridge.CardSelectionV1.Parent.Native.Adapter.Tests.csproj", "card_selection_parent_v1_native_adapter", 8),
    ("wire_tests/Sts2AgentBridge.CardSelectionV1.Wire.Tests.csproj", "card_selection_v1_wire", 11),
)
NATIVE_PROJECTS: tuple[str, ...] = (
    "native/Sts2AgentBridge.CardSelectionV1.Native.csproj",
    "parent_native/Sts2AgentBridge.CardSelectionV1.Parent.Native.csproj",
)
SDK_VERSION = "9.0.303"


def fail(code: str) -> None:
    raise ValueError(code)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_previous():
    path = ROOT.parent / "shop_map_permission_v1/check.py"
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if stat.S_ISLNK(current.lstat().st_mode):
            fail("previous_helper_link")
    data = path.read_bytes()
    if sha(data) != PREVIOUS_CHECK:
        fail("previous_helper_identity")
    module = types.ModuleType("verified_shop_map_checker")
    module.__file__ = str(path)
    exec(compile(data, str(path), "exec"), module.__dict__)
    return module


def frozen_sources():
    ninth = load_previous()
    previous = ninth.load_previous()
    room = previous.load_room()
    release = room.load_release()
    boot = release.load_bootstrap()
    helper = boot.load_frozen_helper()
    contracts = {
        "item_v1": helper.CORE_CONTRACT,
        "item_wire_v1": helper.WIRE_CONTRACT,
        "item_transport_v1": boot.TRANSPORT_CONTRACT,
        "item_bootstrap_v1": boot.CONTRACT,
        "item_release_v1": release.CONTRACT,
        "room_flows_v1": ninth.ROOM_CONTRACT,
        "room_release_v1": ninth.RELEASE_CONTRACT,
        "shop_diagnostic_v1": "4919241452060ba9cb452683f29dc518c9455860b5bfa5eb0ffe0460ff01c68a",
        "shop_map_permission_v1": ninth.CONTRACT,
    }
    pins = {
        "item_v1": (helper.CORE_MANIFEST, helper.CORE_INVENTORY),
        "item_wire_v1": (helper.WIRE_MANIFEST, helper.WIRE_INVENTORY),
        "item_transport_v1": (boot.TRANSPORT_MANIFEST, boot.TRANSPORT_INVENTORY),
        "item_bootstrap_v1": (release.BOOT_MANIFEST, release.BOOT_INVENTORY),
        "item_release_v1": (room.RELEASE_MANIFEST, room.RELEASE_INVENTORY),
        "room_flows_v1": (ninth.ROOM_MANIFEST, ninth.ROOM_INVENTORY),
        "room_release_v1": (ninth.RELEASE_MANIFEST, ninth.RELEASE_INVENTORY),
        "shop_diagnostic_v1": (
            "3e396cd76438a0c8bb3dec77fd510c7ece0b115404a014c482d5ace4de95577f",
            "17a0cd65e0a521e6e682d18c01be9e9c972f60cff5cb1e622ee1ead14266a697"),
        "shop_map_permission_v1": (PREVIOUS_MANIFEST, PREVIOUS_INVENTORY),
    }
    inventories = {}
    for name, contract in contracts.items():
        _, inventories[name] = helper.source_snapshot(
            ROOT.parent / name, name, contract, *pins[name])
    helper.verify_old_inventory(ROOT.parents[3])
    return helper, boot, inventories


def verify_projects(files: dict[str, bytes]) -> None:
    if not PROJECT_HASHES or not PURE_TESTS or not NATIVE_PROJECTS:
        fail("unreviewed_projects")
    if sha(files.get("Directory.Build.props", b"")) != PROPS:
        fail("project_properties_identity")
    if {p for p in files if p.endswith(".csproj")} != set(PROJECT_HASHES):
        fail("project_inventory")
    if any(Path(p).name in ("Directory.Build.targets", "NuGet.Config", "global.json") for p in files):
        fail("unexpected_build_configuration")
    compiled = set()
    graph: dict[str, set[str]] = {}
    for name, digest in PROJECT_HASHES.items():
        if sha(files[name]) != digest:
            fail("project_identity")
        tree = ET.fromstring(files[name])
        graph[name] = set()
        for node in tree.iter():
            if node.tag not in ("Compile", "ProjectReference", "EmbeddedResource"):
                continue
            value = node.attrib["Include"]
            if "$" in value or "*" in value or Path(value).is_absolute():
                fail("dynamic_project_input")
            full = os.path.normpath(str(Path(name).parent / value))
            if full not in files or full.startswith("../"):
                fail("project_input_boundary")
            if node.tag == "Compile":
                if not full.endswith(".cs"):
                    fail("compile_input_type")
                compiled.add(full)
            elif node.tag == "ProjectReference":
                if full not in PROJECT_HASHES:
                    fail("project_reference_boundary")
                graph[name].add(full)
    if {p for p in files if p.endswith(".cs")} != compiled:
        fail("uncompiled_new_source")
    for project, _, _ in PURE_TESTS:
        pending = [project]
        visited = set()
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            if current in NATIVE_PROJECTS:
                fail("pure_native_project_dependency")
            if any(n.tag == "Reference" for n in ET.fromstring(files[current]).iter()):
                fail("pure_external_reference")
            pending.extend(graph[current])


def run(command: list[str], cwd: Path, env: dict[str, str], *, sdk: bool = False, unittest: int | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        fail("offline_command_failed\n" + result.stdout + result.stderr)
    if sdk:
        if any(line != "CSSM_ModuleLoad(): One or more parameters passed to a function were not valid."
               for line in result.stderr.splitlines() if line):
            fail("sdk_stderr")
    elif unittest is not None:
        match = re.fullmatch(r"[.]+\n-+\nRan ([0-9]+) tests? in [0-9.]+s\n\nOK\n", result.stderr)
        if match is None or int(match.group(1)) != unittest:
            fail("unittest_stderr")
    elif result.stderr:
        fail("unexpected_stderr")
    return result.stdout


def passed(output: str, suite: str, count: int | None = None) -> dict:
    result = json.loads(output)
    if (type(result) is not dict or
            set(result) != {"schema_version", "status", "suite", "check_count"} or
            type(result["schema_version"]) is not int or result["schema_version"] != 1 or
            result["status"] != "passed" or result["suite"] != suite or
            type(result["check_count"]) is not int or result["check_count"] < 1 or
            count is not None and result["check_count"] != count):
        fail("fixture_result")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--game-data-dir", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        fail("python_310_required")
    helper, boot, inventories = frozen_sources()
    files, inventory = helper.source_snapshot(ROOT, "card_selection_v1", CONTRACT)
    verify_projects(files)
    game = args.game_data_dir
    if not game.is_absolute() or str(game) != os.path.normpath(str(game)):
        fail("reference_root")
    helper.reject_links(game)
    references = {name: boot.pinned_reference(helper, game / name, size, digest)
                  for name, (size, digest) in boot.REFERENCES.items()}
    if args.scratch.parent != Path("/private/tmp"):
        fail("scratch_boundary")
    helper.create_scratch(args.scratch)
    dotnet = str(args.dotnet.resolve(strict=True))

    def snapshot(destination: Path):
        destination.mkdir()
        own = destination / "source/card_selection_v1"
        for name, data in files.items():
            path = own / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
        refs = destination / "references"
        refs.mkdir()
        for name, data in references.items():
            (refs / name).write_bytes(data)
        empty = destination / "no_game_inputs"
        empty.mkdir()
        tmp = destination / "tmp"
        tmp.mkdir(mode=0o700)
        env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(tmp),
               "DOTNET_CLI_HOME": str(destination / "cli"),
               "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
               "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false", "DOTNET_NOLOGO": "1",
               "DOTNET_MULTILEVEL_LOOKUP": "0", "DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER": "1",
               "MSBUILDDISABLENODEREUSE": "1", "NUGET_PACKAGES": str(destination / "packages"),
               "PYTHONDONTWRITEBYTECODE": "1"}
        nuget = destination / "NuGet.Config"
        nuget.write_text("<configuration><packageSources><clear /></packageSources></configuration>\n")
        if run([dotnet, "--version"], own, env).strip() != SDK_VERSION:
            fail("sdk_mismatch")

        def build(relative: str, native: bool = False) -> Path:
            project = own / relative
            artifacts = destination / "artifacts"
            flags = ["--artifacts-path", str(artifacts), "-m:1",
                     "-p:STS2GameDataDir=" + str(refs if native else empty)]
            run([dotnet, "restore", str(project), "--configfile", str(nuget), *flags,
                 "-p:RestoreBuildInParallel=false", "-p:NuGetAudit=false"], own, env, sdk=True)
            run([dotnet, "build", str(project), "--no-restore", "-c", "Release", *flags,
                 "-p:BuildInParallel=false", "-p:UseSharedCompilation=false"], own, env, sdk=True)
            name = project.stem
            output = artifacts / "bin" / name / "release"
            assembly = output / (name + ".dll")
            deps = json.loads((output / (name + ".deps.json")).read_bytes())
            names = {key.rsplit("/", 1)[0] for key in deps["libraries"]}
            allowed = {Path(p).stem for p in PROJECT_HASHES
                       if native or p not in NATIVE_PROJECTS}
            if names - allowed or any(p.name in ("sts2.dll", "GodotSharp.dll") for p in output.glob("*.dll")):
                fail("output_dependency_boundary")
            return assembly
        return own, env, build

    own, env, build = snapshot(args.scratch / "first")
    summaries = {}
    assemblies = {}
    for project, suite, count in PURE_TESTS:
        assembly = build(project)
        assemblies[suite] = assembly
        summaries[suite] = passed(run([dotnet, str(assembly)], own, env), suite, count)
    summaries["project_boundary"] = passed(run(
        [sys.executable, "-B", "-I", "-S", str(own / "checker_tests/check_project_boundary.py")],
        own, env), "card_selection_v1_project_boundary", 15)
    host_output = run([sys.executable, "-B", "-I", "-S",
                       str(own / "host_tests/test_card_selection_host.py")], own, env, unittest=13)
    if host_output:
        fail("host_fixture_stdout")
    summaries["host_unit"] = {"schema_version": 1, "status": "passed",
                              "suite": "card_selection_v1_host_unit", "check_count": 13}
    summaries["host_cross_language"] = passed(run(
        [sys.executable, "-B", "-I", "-S", str(own / "host_tests/run_cross_language.py"),
         "--dotnet", dotnet, "--fixture", str(assemblies["card_selection_v1_wire"])], own, env),
        "card_selection_v1_host_cross_language", 2)
    native = {project: build(project, native=True) for project in NATIVE_PROJECTS}
    _, _, second_build = snapshot(args.scratch / "second")
    native_results = {}
    for project, first in native.items():
        second = second_build(project, native=True)
        data = first.read_bytes()
        if data != second.read_bytes():
            fail("native_build_reproduction")
        native_results[project] = {"bytes": len(data), "sha256": sha(data),
                                   "deterministic_build_count": 2, "executed": False}
    result = {"schema_version": 1, "status": "passed", "suite": "card_selection_v1_offline",
              "source_inventory_sha256": inventory, "frozen_source_inventories": inventories,
              "old_bridge_file_count": 48, "old_bridge_inventory_sha256": helper.OLD_INVENTORY,
              "synthetic": summaries, "native_compilation": native_results,
              "pinned_reference_count": 2, "target_assemblies_executed": False,
              "release_ready": False, "live_campaign_started": False}
    (args.scratch / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
