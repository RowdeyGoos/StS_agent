#!/usr/bin/env python3
"""Verify the functional generic event v4 slice in disposable offline snapshots."""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import xml.etree.ElementTree as ET

ROOT = Path(__file__).absolute().parent
PREFIX = "bridge/Sts2AgentBridge/successors/"
PREVIOUS_CHECK = "b1f57abbefb0c36fb155ebe22691eee72d287c45304381599b527dde163178c5"
PREVIOUS_MANIFEST = "dd0be8c5222ff27a10f179becb053d8c6218fd9ec2e9abb6f7b765002069f99e"
PREVIOUS_INVENTORY = "adade4736245aa9e61efdd8f926b5e4b9a209697bfc1dcf1009a3fb4b0c6d2fc"
HARMONY_BYTES = 2328064
HARMONY_SHA = "ef1898322c9f5c86dc1b0758b272a9c440823b4a41ca9a0b82a3aa6b3d206387"
CONTRACT_SHA = "c8c920769ce80246e3925722716e8b522360d6033b788092f77bbaa36e47a14b"
PRODUCTION = "native/GenericEventV4.Native.csproj"
PROJECTS = {
    PRODUCTION, "core/GenericEventV4.Core.csproj", "wire/GenericEventV4.Wire.csproj",
    "native_tests/GenericEventV4.Native.Tests.csproj",
    "wire_tests/Sts2AgentBridge.GenericEventV4.WireTests.csproj",
    "integration/Sts2AgentBridge.GenericEventV4.Integration.csproj",
    "integration/GenericEventV4.Native.Integration.csproj",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, code):
    if not value:
        raise ValueError(code)


def sources():
    path = ROOT.parent / "generic_event_release_v5/check.py"
    require(not path.is_symlink() and sha(path.read_bytes()) == PREVIOUS_CHECK, "predecessor_checker")
    manifest = path.parent / "source_identity.json"
    require(not manifest.is_symlink() and sha(manifest.read_bytes()) == PREVIOUS_MANIFEST, "predecessor_manifest")
    previous = types.ModuleType("verified_generic_v5_predecessor")
    previous.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), previous.__dict__)
    helper, boot, inputs, _, inventories, prior, _ = previous.sources()
    require(prior == PREVIOUS_INVENTORY, "predecessor_inventory")
    inventories = dict(inventories, generic_event_release_v5=prior)
    require(len(inventories) == 23, "predecessor_count")
    helper.reject_links(ROOT)
    own = {}
    for path in sorted(ROOT.rglob("*")):
        helper.reject_links(path)
        relative = path.relative_to(ROOT)
        require(not {"bin", "obj", "__pycache__"}.intersection(relative.parts), "source_outputs")
        if path.is_file() and relative.as_posix() != "source_identity.json":
            own[relative.as_posix()] = helper.read_regular(path)
    inventory = sha("".join(sha(data) + "  " + name + "\n" for name, data in sorted(own.items())).encode("ascii"))
    contract_path = ROOT.parents[3] / "docs/PHASE_1_GENERIC_EVENT_V4_CONTRACT.md"
    helper.reject_links(contract_path)
    contract = sha(helper.read_regular(contract_path))
    require(contract == CONTRACT_SHA, "accepted_contract_identity")
    identity = ROOT / "source_identity.json"
    if identity.exists():
        require(json.loads(helper.read_regular(identity)) == dict(schema_version=1, component="generic_event_v4",
            contract_sha256=contract, inventory_sha256=inventory,
            files={name: sha(data) for name, data in own.items()}), "source_identity")
    inputs = dict(inputs)
    inputs.update({PREFIX + "generic_event_v4/" + name: data for name, data in own.items()})
    derivation = json.loads(own["derivation.json"])
    require(derivation["schema_version"] == 1, "derivation_schema")
    rows = derivation["derived"]
    require(len(rows) == 32, "derived_inventory")
    require(len({r["target"] for r in rows}) == len(rows), "duplicate_derivation")
    for row in rows:
        require(row["source"] in inputs and row["target"] in inputs, "derivation_boundary")
        before, after = inputs[row["source"]], inputs[row["target"]]
        require(sha(before) == row["source_sha256"] and sha(after) == row["target_sha256"], "derivation_identity")
        require("".join(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True),
            fromfile=row["source"], tofile=row["target"])) == row["unified_diff"], "derivation_delta")
    for row in derivation["reused"]:
        require(row["source"] in inputs and sha(inputs[row["source"]]) == row["sha256"], "reused_identity")
    return helper, boot, inputs, own, inventories, inventory, contract


def closure(inputs, project, production):
    pending, visited, compiled = [project], set(), set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        require(current in inputs, "missing_project")
        tree = ET.fromstring(inputs[current])
        require(tree.find(".//EnableDefaultCompileItems").text == "false", "implicit_compile")
        for node in tree.iter():
            require(node.tag not in ("PackageReference", "Import", "Exec", "UsingTask", "EmbeddedResource"), "dynamic_build")
            if node.tag in ("Compile", "ProjectReference"):
                value = node.attrib["Include"]
                require(value and not any(c in value for c in "*?$\\") and not Path(value).is_absolute(), "dynamic_input")
                target = os.path.normpath(str(Path(current).parent / value))
                require(target in inputs and not target.startswith("../"), "input_boundary")
                if node.tag == "ProjectReference":
                    pending.append(target)
                else:
                    compiled.add(target)
            if node.tag == "Reference":
                name = node.attrib.get("Include")
                require(name == "0Harmony" or production and name in ("sts2", "GodotSharp"), "reference_boundary")
                require(node.find("HintPath").text in ("$(HarmonyPath)", "$(STS2GameDataDir)/sts2.dll", "$(STS2GameDataDir)/GodotSharp.dll"), "reference_path")
    return compiled


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--game-data-dir", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    require(sys.version_info >= (3, 10), "python_310")
    helper, boot, inputs, own, inventories, inventory, contract = sources()
    require(args.scratch.parent == Path("/private/tmp"), "scratch_boundary")
    helper.create_scratch(args.scratch)
    helper.reject_links(args.game_data_dir)
    references = {name: boot.pinned_reference(helper, args.game_data_dir / name, size, digest)
                  for name, (size, digest) in boot.REFERENCES.items()}
    references["0Harmony.dll"] = boot.pinned_reference(helper, args.game_data_dir / "0Harmony.dll", HARMONY_BYTES, HARMONY_SHA)
    dependency = json.loads(own["dependency.json"])
    require(dependency == dict(schema_version=1, source="pinned_game_owned_harmony",
        assembly_bytes=HARMONY_BYTES, assembly_sha256=HARMONY_SHA), "dependency_identity")
    projects = sorted(name for name in own if name.endswith(".csproj"))
    require(set(projects) == PROJECTS, "project_inventory")
    compiled = set()
    production_sources = closure(inputs, PREFIX + "generic_event_v4/" + PRODUCTION, True)
    native_sources = {PREFIX + "generic_event_v4/" + name for name in own if name.startswith("native/") and name.endswith(".cs")}
    require(native_sources.issubset(production_sources), "native_production_closure")
    for name in ("GenericEventV3CardAdapter", "GenericEventV3RemovalAdapter", "GenericEventV3RewardAdapter"):
        before = inputs[PREFIX + "generic_event_release_v5/native/" + name + ".cs"]
        after = own["native/" + name.replace("V3", "V4") + ".cs"]
        require(after == before.replace(b"GenericEventV3", b"GenericEventV4"), "preserved_native_namespace_only")
    forbidden = {PREFIX + component + "/native/" for component in ("generic_event_v3", "generic_event_lifecycle_v1", "generic_event_release_v5")}
    require(not any(any(name.startswith(prefix) for prefix in forbidden) for name in production_sources), "old_native_duplicate")
    for project in projects:
        current = closure(inputs, PREFIX + "generic_event_v4/" + project, project == PRODUCTION)
        compiled.update(current)
        if project.startswith("native_tests/") or project == "integration/GenericEventV4.Native.Integration.csproj":
            require(native_sources.issubset(current), "actual_native_fixture_closure")
    require({PREFIX + "generic_event_v4/" + name for name in own if name.endswith(".cs")}.issubset(compiled), "uncompiled_source")
    reused = json.loads(own["derivation.json"])["reused"]
    expected_reused = {name for name in compiled if not name.startswith(PREFIX + "generic_event_v4/")}
    expected_reused.add(PREFIX + "card_selection_v1/host/card_selection_host.py")
    require(len(reused) == len(expected_reused) and {row["source"] for row in reused} == expected_reused, "reused_closure")
    require({"host_tests/test_generic_event_host.py", "host_tests/test_generic_event_removal_host.py",
        "host_tests/test_generic_event_reward_host.py", "host_tests/test_generic_event_completion_host.py",
        "native_tests/MultiUpgradeFixtures.cs", "integration_tests/test_generic_event_integration.py"}.issubset(own), "required_tests")
    dotnet = str(args.dotnet.resolve(strict=True))
    logs = 0
    def run(command, cwd, env):
        nonlocal logs
        logs += 1
        result = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240, check=False)
        (args.scratch / f"log-{logs:03}.txt").write_bytes(result.stdout)
        require(result.returncode == 0, f"command_failed_log_{logs:03}")
        return result.stdout.decode().strip()
    def snapshot(label):
        dest = args.scratch / label
        source = dest / "source"
        for name, data in inputs.items():
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        refs = dest / "references"
        refs.mkdir()
        for name, data in references.items():
            (refs / name).write_bytes(data)
        temp = dest / "tmp"
        temp.mkdir()
        empty = dest / "no_game_inputs"
        empty.mkdir()
        env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(temp), "DOTNET_CLI_HOME": str(dest / "cli"),
            "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1",
            "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false", "DOTNET_MULTILEVEL_LOOKUP": "0",
            "DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER": "1", "MSBUILDDISABLENODEREUSE": "1",
            "NUGET_PACKAGES": str(dest / "packages"), "PYTHONDONTWRITEBYTECODE": "1"}
        component = source / PREFIX / "generic_event_v4"
        nuget = dest / "NuGet.Config"
        nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
        require(run([dotnet, "--version"], component, env) == "9.0.303", "sdk_identity")
        def build(project):
            flags = ["--artifacts-path", str(dest / "artifacts"), "-m:1", "-p:HarmonyPath=" + str(refs / "0Harmony.dll"),
                "-p:STS2GameDataDir=" + str(refs if project == PRODUCTION else empty)]
            path = component / project
            run([dotnet, "restore", str(path), "--configfile", str(nuget), *flags, "-p:NuGetAudit=false", "-p:RestoreBuildInParallel=false"], component, env)
            run([dotnet, "build", str(path), "--no-restore", "-c", "Release", *flags, "-p:UseSharedCompilation=false", "-p:BuildInParallel=false"], component, env)
            assembly = ET.parse(path).getroot().find(".//AssemblyName").text
            output = dest / "artifacts/bin" / path.stem / "release"
            require(not any((output / name).exists() for name in ("sts2.dll", "GodotSharp.dll")), "copied_target")
            if project == PRODUCTION:
                require(not (output / "0Harmony.dll").exists(), "copied_harmony")
            return output / (assembly + ".dll")
        return component, env, build
    component, env, build = snapshot("first")
    outputs, tests = {}, {}
    for project in projects:
        outputs[project] = build(project)
        if project.startswith(("native_tests/", "wire_tests/")):
            tests[project] = run([dotnet, str(outputs[project])], component, env)
    tests["host_tests"] = run([sys.executable, "-B", "-m", "unittest", "discover",
        "-s", str(component / "host_tests"), "-p", "test_*.py"], component, env)
    for script in sorted((component / "integration_tests").glob("test_*.py")):
        tests[str(script.relative_to(component))] = run([sys.executable, "-B", str(script), "--dotnet", dotnet,
            "--fixture", str(outputs["integration/Sts2AgentBridge.GenericEventV4.Integration.csproj"]),
            "--native-fixture", str(outputs["integration/GenericEventV4.Native.Integration.csproj"]),
            "--host", str(component / "host/generic_event_host.py")], component, env)
    _, _, again = snapshot("second")
    first = outputs[PRODUCTION].read_bytes()
    require(first == again(PRODUCTION).read_bytes(), "native_reproducibility")
    result = dict(schema_version=1, status="passed", source_inventory_sha256=inventory, contract_sha256=contract,
        frozen_predecessor_count=len(inventories), frozen_source_inventories=inventories, tests=tests,
        production_source_count=len(production_sources),
        native_compilation={PRODUCTION: dict(bytes=len(first), sha256=sha(first), executed=False)},
        harmony_assembly_sha256=HARMONY_SHA, target_assemblies_executed=False, release_ready=False, live_campaign_started=False)
    (args.scratch / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
