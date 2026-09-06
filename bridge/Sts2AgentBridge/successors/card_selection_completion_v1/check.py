#!/usr/bin/env python3
"""Offline card release gate. No install, live endpoint, credential or target execution."""
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
CONTRACT = "bc9626a765bf0e50fd8b39813131931905a2cf01adcf5e297ee6d3ce05c295c8"
CARD_CHECK = "a29f714e15d911ac4f2d056dc2f0521b4aa1809901e2bbeddcf76cc2185e842f"
PROPS = "2b05edd4dbb4532b1e884c6267bf56c732b49415dc43a23245b3d0c3cc30265f"
FROZEN_MANIFESTS = {
    "item_v1": "435219714fa6e667738685f9909396839c46c21612a50bc84a0fc58e584c938a",
    "item_wire_v1": "c930337e74b4eed9f41ba00e804a950a7334a33a96ded7531361312bf5115c10",
    "item_transport_v1": "e8cb05876cba695d8b4d22d5e12e597a4ea4d2fa7d525a160c9ccb223b91fe57",
    "item_bootstrap_v1": "77aa278f7c7c2cba2523c5c4d474fb2f45eb76dfa3d1faa7feb914a96e4c47ab",
    "item_release_v1": "036e090daa509dfdf9f2eac7f8ab4d5b42a16aca08cecfe28a349402ef2af1a7",
    "room_flows_v1": "91f5750b70a7b3c735f487a0e5d3d0315b6c6b32593b6fe452845745e506b213",
    "room_release_v1": "d567c8e91e45fd2bcff2cd446f85d3d7faef3baf2b22b6f7b75ba2490d360957",
    "shop_diagnostic_v1": "3e396cd76438a0c8bb3dec77fd510c7ece0b115404a014c482d5ace4de95577f",
    "shop_map_permission_v1": "14b94d4e0877743e3719ee7904875606fc5a0ae99eccbc4cfebee6bfc0f9f03a",
    "card_selection_v1": "ca4e18dbb66520481881ea86a91925162593f8496c7abccc061a31f1c319a0ac",
    "card_selection_release_v1": "67cb5073c9a39542677a806064d829a8595331f39665fc6a7bfa7ba71666f16c"
}
PROJECT_HASHES: dict[str, str] = {
    "native_tests/Sts2AgentBridge.CardSelectionCompletionV1.Native.Tests.csproj": "03012fc94306901ff60383591df255c0e13d3255c72d7b415c6b1407c2028621",
    "native_tests/Sts2AgentBridge.CardSelectionCompletionV1.OriginalControl.Tests.csproj": "0b613f4d6e7656f0dbc3e654d7416ff9a83482a79d8c17052900f70ecd00f8b3",
    "production/Sts2AgentBridgeCardSelectionV1.csproj": "06aae55108b9753c96e3bbc43eb1f3f0d0146118b81dc797bb57b708cdbfb6f6",
    "verifier/Sts2AgentBridge.CardSelectionV1.Release.Verifier.csproj": "8cf03fbe317261efe72e4ab66b83536a28cfd595559cb99603f71f95be6c7628",
    "verifier_tests/Sts2AgentBridge.CardSelectionV1.Release.Verifier.Tests.csproj": "18b35efb2974fc288915b6c96ac312c8d05ad385e7acf2cf0b53c47547ffef26"
}
PROJECT_COUNT = 5
PRODUCTION = "production/Sts2AgentBridgeCardSelectionV1.csproj"
PURE_TESTS: tuple[tuple[str, str, int], ...] = (
    ("card_selection_release_v1/operator_tests/Sts2AgentBridge.CardSelectionV1.Operator.Tests.csproj", "card_selection_v1_operator", 5),
    ("card_selection_release_v1/lifecycle_tests/Sts2AgentBridge.CardSelectionV1.Bootstrap.Tests.csproj", "card_selection_v1_bootstrap", 14),
    ("card_selection_release_v1/runtime_tests/Sts2AgentBridge.CardSelectionV1.Transport.Tests.csproj", "card_selection_v1_transport", 13),
)
NATIVE_TESTS: tuple[tuple[str, str, int], ...] = (
    ("card_selection_completion_v1/native_tests/Sts2AgentBridge.CardSelectionCompletionV1.OriginalControl.Tests.csproj", "card_selection_completion_diagnostic_original", 13),
    ("card_selection_completion_v1/native_tests/Sts2AgentBridge.CardSelectionCompletionV1.Native.Tests.csproj", "card_selection_completion_v1_native", 87),
)
DERIVATION_SCRIPT = "derivation/check_derivation.py"
DERIVATION_SUITE = "card_selection_completion_v1_derivation"
DERIVATION_COUNT = 7


def fail(code: str) -> None:
    raise ValueError(code)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_card():
    path = ROOT.parent / "card_selection_v1/check.py"
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if stat.S_ISLNK(current.lstat().st_mode):
            fail("frozen_helper_link")
    data = path.read_bytes()
    if sha(data) != CARD_CHECK:
        fail("frozen_helper_identity")
    module = types.ModuleType("verified_card_component_checker")
    module.__file__ = str(path)
    exec(compile(data, str(path), "exec"), module.__dict__)
    return module


def frozen_sources():
    card = load_card()
    helper, boot, inventories = card.frozen_sources()
    inventories["card_selection_v1"] = "51135dfb6749d58b897bb4670ffa709ca5b756873464c9e045f2ba80f87bfc64"
    inventories["card_selection_release_v1"] = "39fd9535446de173af6d065d7d70e2a5f010923ad2a356363b04e133d73d62fe"
    components = {}
    for name, pin in FROZEN_MANIFESTS.items():
        path = ROOT.parent / name / "source_identity.json"
        helper.reject_links(path)
        raw = helper.read_regular(path)
        if sha(raw) != pin:
            fail("frozen_manifest_identity")
        contract = json.loads(raw)["contract_sha256"]
        components[name], actual = helper.source_snapshot(ROOT.parent / name, name, contract, pin, inventories[name])
        if actual != inventories[name]:
            fail("frozen_inventory_identity")
    return card, helper, boot, components, inventories


def verify_projects(components: dict[str, dict[str, bytes]]) -> None:
    own = components["card_selection_completion_v1"]
    if PROJECT_COUNT < 4 or len(PROJECT_HASHES) != PROJECT_COUNT or len(PURE_TESTS) != 3 or len(NATIVE_TESTS) != 2:
        fail("projects_not_frozen")
    controls = {name for name in own if Path(name).suffix.lower() in (".props", ".targets", ".rsp")
                or Path(name).name.lower() in ("nuget.config", "global.json")}
    if controls != {"Directory.Build.props"} or sha(own["Directory.Build.props"]) != PROPS:
        fail("build_control_identity")
    if {p for p in own if p.endswith(".csproj")} != set(PROJECT_HASHES):
        fail("project_inventory")
    all_inputs = {name + "/" + path: content for name, files in components.items() for path, content in files.items()}
    compiled = set()
    production = []
    for name, digest in PROJECT_HASHES.items():
        if sha(own[name]) != digest:
            fail("project_identity")
        tree = ET.fromstring(own[name])
        for node in tree.iter():
            if node.tag not in ("Compile", "ProjectReference", "EmbeddedResource"):
                continue
            value = node.attrib["Include"]
            if "$" in value or "*" in value or Path(value).is_absolute():
                fail("dynamic_project_input")
            full = os.path.normpath("card_selection_completion_v1/" + str(Path(name).parent / value))
            if full not in all_inputs or full.startswith("../"):
                fail("project_input_boundary")
            if node.tag == "Compile":
                if not full.endswith(".cs"):
                    fail("compile_input_type")
                compiled.add(full)
                if name == PRODUCTION:
                    production.append("bridge/Sts2AgentBridge/successors/" + full)
    policy = json.loads(own["policy/card_selection_release_policy.json"])
    if len(production) != 30 or len(set(production)) != 30 or sorted(production) != [p["path"] for p in policy["source_files"]]:
        fail("production_policy_source_closure")
    for source in policy["source_files"]:
        relative = source["path"].removeprefix("bridge/Sts2AgentBridge/successors/")
        if sha(all_inputs[relative]) != source["sha256"]:
            fail("production_policy_source_identity")
    if {"card_selection_completion_v1/" + p for p in own if p.endswith(".cs")} != {p for p in compiled if p.startswith("card_selection_completion_v1/")}:
        fail("uncompiled_new_source")
    original = components["card_selection_release_v1"][PRODUCTION].decode("utf-8")
    expected = re.sub(r'Include="\.\./(runtime|operator|lifecycle|native)/',
                      r'Include="../../card_selection_release_v1/\1/', original)
    expected = expected.replace('Include="../../card_selection_v1/native/PinnedCardSelectionV1NativeAdapter.cs"',
                                'Include="../native/PinnedCardSelectionV1NativeAdapter.cs"')
    if own[PRODUCTION] != expected.encode("utf-8"):
        fail("production_single_source_substitution")
    for name in PROJECT_HASHES:
        if name == PRODUCTION:
            continue
        pending = ["card_selection_completion_v1/" + name]
        visited = set()
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            tree = ET.fromstring(all_inputs[path])
            if any(node.tag in ("Reference", "PackageReference") for node in tree.iter()):
                fail("pure_external_dependency")
            for node in tree.iter("ProjectReference"):
                reference = os.path.normpath(str(Path(path).parent / node.attrib["Include"]))
                if reference not in all_inputs or reference == "card_selection_completion_v1/" + PRODUCTION:
                    fail("pure_project_boundary")
                pending.append(reference)


def run(command, cwd, env, *, sdk=False, unittest_count=None):
    result = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        fail("offline_command_failed\n" + result.stdout + result.stderr)
    if sdk:
        if any(line != "CSSM_ModuleLoad(): One or more parameters passed to a function were not valid."
               for line in result.stderr.splitlines() if line):
            fail("sdk_stderr")
    elif unittest_count is not None:
        match = re.fullmatch(r"[.]+\n-+\nRan ([0-9]+) tests? in [0-9.]+s\n\nOK\n", result.stderr)
        if match is None or int(match.group(1)) != unittest_count:
            fail("unittest_stderr")
    elif result.stderr:
        fail("unexpected_stderr")
    return result.stdout


def passed(output, suite, count=None):
    result = json.loads(output)
    if type(result) is not dict or type(result.get("schema_version")) is not int or result["schema_version"] != 1 or result.get("status") != "passed" or result.get("suite") != suite:
        fail("fixture_result")
    expected = {"schema_version", "status", "suite", "check_count"}
    if suite in ("manage_live_campaign_fixtures", "check_live_runtime_fixtures"):
        expected.add("checks")
        checks = result["checks"]
        if type(checks) is not list or any(type(x) is not str or not re.fullmatch("[a-z0-9_]{1,100}", x) for x in checks) or len(set(checks)) != len(checks) or len(checks) != result["check_count"]:
            fail("fixture_check_names")
    if suite == "card_selection_completion_package":
        expected.add("mutation_cases")
        if type(result["mutation_cases"]) is not int or result["mutation_cases"] != 9:
            fail("package_mutations")
    if set(result) != expected or type(result["check_count"]) is not int or result["check_count"] < 1 or count is not None and result["check_count"] != count:
        fail("fixture_result_shape")
    result.pop("checks", None)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--game-data-dir", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        fail("python_310_required")
    card, helper, boot, components, inventories = frozen_sources()
    components["card_selection_completion_v1"], inventory = helper.source_snapshot(ROOT, "card_selection_completion_v1", CONTRACT)
    verify_projects(components)
    repository = ROOT.parents[3]
    bridge = repository / "bridge/Sts2AgentBridge"
    legacy = bridge / "src"
    old_paths = [path for pattern in ("*.cs", "*.csproj") for path in legacy.rglob(pattern)
                 if not {"bin", "obj"}.intersection(path.relative_to(legacy).parts[:-1])]
    old_paths += [bridge / name for name in ("Directory.Build.props", "global.json",
                  "Sts2AgentBridge.sln", "package/Sts2AgentBridge.json")]
    old_files = {}
    for path in sorted(old_paths, key=lambda item: item.relative_to(repository).as_posix()):
        helper.reject_links(path)
        old_files[path.relative_to(repository).as_posix()] = helper.read_regular(path)
    old_projection = "".join(sha(data) + "  " + name + "\n" for name, data in old_files.items())
    if len(old_files) != 48 or sha(old_projection.encode("ascii")) != helper.OLD_INVENTORY:
        fail("old_snapshot_identity")
    game = args.game_data_dir
    if not game.is_absolute() or str(game) != os.path.normpath(str(game)):
        fail("reference_root")
    helper.reject_links(game)
    references = {name: boot.pinned_reference(helper, game / name, size, digest) for name, (size, digest) in boot.REFERENCES.items()}
    if args.scratch.parent != Path("/private/tmp"):
        fail("scratch_boundary")
    helper.create_scratch(args.scratch)
    dotnet = str(args.dotnet.resolve(strict=True))

    def snapshot_at(destination):
        destination.mkdir()
        source = destination / "source"
        siblings = source / "bridge/Sts2AgentBridge/successors"
        for component, files in components.items():
            for name, data in files.items():
                path = siblings / component / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(data)
        for name, data in old_files.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
        helper.verify_old_inventory(source)
        refs = destination / "references"
        refs.mkdir()
        for name, data in references.items():
            (refs / name).write_bytes(data)
        empty = destination / "no_game_inputs"
        empty.mkdir()
        tmp = destination / "tmp"
        tmp.mkdir(mode=0o700)
        env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(tmp),
               "DOTNET_CLI_HOME": str(destination / "cli"), "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
               "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false",
               "DOTNET_NOLOGO": "1", "DOTNET_MULTILEVEL_LOOKUP": "0", "DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER": "1",
               "MSBUILDDISABLENODEREUSE": "1", "NUGET_PACKAGES": str(destination / "packages"),
               "PYTHONDONTWRITEBYTECODE": "1"}
        own = siblings / "card_selection_completion_v1"
        nuget = destination / "NuGet.Config"
        nuget.write_text("<configuration><packageSources><clear /></packageSources></configuration>\n")
        if run([dotnet, "--version"], own, env).strip() != "9.0.303":
            fail("sdk_mismatch")
        pure_names = {Path(path).stem for name, files in components.items() for path in files if path.endswith(".csproj")
                      and not any(part in ("native", "parent_native", "production") for part in Path(path).parts)}
        def build(relative, native=False):
            project = siblings / relative
            artifacts = destination / "artifacts"
            flags = ["--artifacts-path", str(artifacts), "-m:1", "-p:STS2GameDataDir=" + str(refs if native else empty)]
            run([dotnet, "restore", str(project), "--configfile", str(nuget), *flags,
                 "-p:RestoreBuildInParallel=false", "-p:NuGetAudit=false"], own, env, sdk=True)
            run([dotnet, "build", str(project), "--no-restore", "-c", "Release", *flags,
                 "-p:BuildInParallel=false", "-p:UseSharedCompilation=false"], own, env, sdk=True)
            name = project.stem
            directory = artifacts / "bin" / name / "release"
            assembly = directory / (name + ".dll")
            deps = json.loads((directory / (name + ".deps.json")).read_bytes())
            names = {key.rsplit("/", 1)[0] for key in deps["libraries"]}
            dlls = {p.name for p in directory.glob("*.dll")}
            if native:
                if names != {name} or dlls != {name + ".dll"}:
                    fail("production_output_boundary")
            elif names - pure_names or {"sts2.dll", "GodotSharp.dll", "Sts2AgentBridgeCardSelectionV1.dll"}.intersection(dlls):
                fail("pure_dependency_boundary")
            return assembly
        return source, siblings, own, env, build

    source, siblings, own, env, build = snapshot_at(args.scratch / "first")
    summaries, assemblies = {}, {}
    for project, suite, count in (*PURE_TESTS, *NATIVE_TESTS):
        assembly = build(project)
        assemblies[suite] = assembly
        arguments = [dotnet, str(assembly)]
        if "/operator_tests/" in project:
            fixture = Path("/private/tmp") / ("card-release-operator-" + sha(str(args.scratch).encode())[:24])
            arguments += ["--fixture-root", str(fixture)]
        summaries[suite] = passed(run(arguments, own, env), suite, count)
    summaries["socket_composition"] = passed(run([sys.executable, "-B", "-I", "-S",
        str(siblings / "card_selection_release_v1/integration/test_card_selection_socket_composition.py"), "--dotnet", dotnet,
        "--fixture", str(assemblies["card_selection_v1_transport"])], own, env), "card_selection_release_socket_composition", 3)
    for relative, suite, count, unit in (
        ("checker_tests/test_card_selection_completion_project_boundary.py", "card_selection_completion_project_boundary", 15, False),
        ("client_tests/client_fixtures.py", "card_selection_completion_client", 13, True),
        ("operations/manage_live_campaign_fixtures.py", "manage_live_campaign_fixtures", 39, False),
        ("operations/check_live_runtime_fixtures.py", "check_live_runtime_fixtures", 17, False),
        ("operations/predecessor_conflict_fixtures.py", "card_selection_completion_predecessor_conflicts", 20, False),
        ("operations/verify_source_derivation.py", "card_selection_completion_operations_derivation", 14, False),
        (DERIVATION_SCRIPT, DERIVATION_SUITE, DERIVATION_COUNT, False)):
        extra = ["--source-root", str(source)] if relative == DERIVATION_SCRIPT else []
        summaries[suite] = passed(run([sys.executable, "-B", "-I", "-S", str(own / relative), *extra], own, env,
                                     unittest_count=count if unit else None), suite, count)
    output = run([sys.executable, "-B", "-I", "-S", str(siblings / "card_selection_release_v1/transport_tests/test_card_selection_transport.py")], own, env, unittest_count=14)
    if output:
        fail("transport_fixture_stdout")
    summaries["python_transport"] = {"schema_version": 1, "status": "passed", "suite": "card_selection_completion_python_transport", "check_count": 14}
    candidate = build("card_selection_completion_v1/" + PRODUCTION, native=True)
    _, _, _, _, second_build = snapshot_at(args.scratch / "second")
    second = second_build("card_selection_completion_v1/" + PRODUCTION, native=True)
    if candidate.read_bytes() != second.read_bytes():
        fail("candidate_reproduction")
    verifier = build("card_selection_completion_v1/verifier/Sts2AgentBridge.CardSelectionV1.Release.Verifier.csproj")
    mutations = build("card_selection_completion_v1/verifier_tests/Sts2AgentBridge.CardSelectionV1.Release.Verifier.Tests.csproj")
    policy = own / "policy/card_selection_release_policy.json"
    surface = json.loads(run([dotnet, str(verifier), "--assembly", str(candidate), "--source-root", str(source), "--policy", str(policy)], own, env))
    fixed = json.loads(policy.read_bytes())
    if (set(surface) != {"schema_version", "status", "suite", "assembly_sha256", "checked_method_bodies", "metadata_projection_sha256", "source_projection_sha256"}
            or type(surface["schema_version"]) is not int or surface["schema_version"] != 1 or surface["status"] != "passed"
            or surface["suite"] != "card_selection_v1_release_surface" or surface["assembly_sha256"] != sha(candidate.read_bytes())
            or surface["assembly_sha256"] != fixed["candidate_sha256"] or surface["checked_method_bodies"] != fixed["checked_method_bodies"]
            or surface["metadata_projection_sha256"] != fixed["metadata_projection_sha256"] or surface["source_projection_sha256"] != fixed["source_projection_sha256"]):
        fail("surface_result_identity")
    summaries["surface"] = surface
    summaries["verifier_mutations"] = passed(run([dotnet, str(mutations), "--candidate", str(candidate),
        "--source-root", str(source), "--policy", str(policy)], own, env), "card_selection_v1_release_verifier", 57)
    ninth = card.load_previous()
    predecessor_release = ninth.load_previous().load_room().load_release()
    summaries["verifier_cli"] = predecessor_release.verify_cli_negatives(dotnet, verifier, candidate, source, policy, args.scratch, own, env)
    summaries["verifier_cli"]["suite"] = "card_selection_completion_cli"
    summaries["package"] = passed(run([sys.executable, "-B", "-I", "-S", str(own / "package/package_fixtures.py"), str(candidate)], own, env, unittest_count=5), "card_selection_completion_package", 5)
    summaries["clean_install"] = passed(run([sys.executable, "-B", "-I", "-S", str(own / "operations/verify_clean_install_fixtures.py"), "--candidate", str(candidate)], own, env), "verify_clean_install_fixtures", 7)
    result = {"schema_version": 1, "status": "passed", "suite": "card_selection_completion_v1_offline",
              "source_inventory_sha256": inventory, "frozen_source_inventories": inventories,
              "old_bridge_file_count": 48, "old_bridge_inventory_sha256": helper.OLD_INVENTORY,
              "candidate": {"bytes": candidate.stat().st_size, "sha256": sha(candidate.read_bytes()),
                            "deterministic_build_count": 2, "executed": False},
              "synthetic": summaries, "pinned_reference_count": 2,
              "target_assemblies_executed": False, "live_campaign_started": False}
    (args.scratch / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
