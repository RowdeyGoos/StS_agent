#!/usr/bin/env python3
"""Check one maintained bridge capability; never install or launch the game."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from release_support import (PRODUCTION, REFERENCES, SDK_VERSION, TARGET_COMPONENTS,
                             collect_sources, inventory, project_closure,
                             read_regular, require, sha, validate_sources)

ROOT = Path(__file__).absolute().parent


class Gate:
    def __init__(self, targets: list[str], scratch: Path, dotnet: str | None,
                 game_data: Path | None, *, release: bool = False) -> None:
        self.targets, self.scratch, self.dotnet = targets, scratch, dotnet
        self.files = collect_sources(ROOT, targets)
        self.summary = validate_sources(self.files, targets, release=release)
        self.source = scratch / "source/bridge/Sts2AgentBridge"
        for name, data in self.files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.env = {
            "PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(scratch),
            "DOTNET_CLI_HOME": str(scratch / "cli"), "DOTNET_NOLOGO": "1",
            "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false", "DOTNET_MULTILEVEL_LOOKUP": "0",
            "DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER": "1", "MSBUILDDISABLENODEREUSE": "1",
            "NUGET_PACKAGES": str(scratch / "packages"), "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(self.source),
        }
        self.checks: dict[str, dict] = {}
        self.outputs: dict[str, Path] = {}
        self.refs = scratch / "references"
        self.refs.mkdir()
        if game_data is not None:
            for name, (size, digest) in REFERENCES.items():
                data = read_regular(game_data / name)
                require(len(data) == size and sha(data) == digest, "game_reference_identity")
                (self.refs / name).write_bytes(data)
        self.nuget = scratch / "NuGet.Config"
        self.nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')

    def run(self, name: str, command: list[str], cwd: Path | None = None) -> str:
        start = time.monotonic()
        result = subprocess.run(command, cwd=cwd or self.source, env=self.env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=240, check=False)
        log = self.scratch / f"log-{len(self.checks) + 1:03}.txt"
        log.write_bytes(result.stdout)
        self.checks[name] = {"status": "passed" if result.returncode == 0 else "failed",
                             "seconds": round(time.monotonic() - start, 3), "log": log.name}
        if result.returncode:
            print(result.stdout.decode(errors="replace")[-5000:], file=sys.stderr)
            raise ValueError(f"check_failed:{name}:{log}")
        return result.stdout.decode().strip()

    def python(self) -> None:
        folders = sorted({str(Path(p).parent) for p in self.files if p.endswith(".py")
                          and Path(p).parent.name in ("host_tests", "transport_tests", "maintenance")})
        for folder in folders:
            self.run(folder, [sys.executable, "-B", "-m", "unittest", "discover",
                              "-s", str(self.source / folder), "-p", "test_*.py"],
                     cwd=self.source / Path(folder).parent)
        for target in self.targets:
            app = self.source / "apps" / target
            for script in sorted(app.glob("client_tests/*_fixtures.py")):
                self.run(str(script.relative_to(self.source)), [sys.executable, "-B", str(script)])
            for script in sorted(app.glob("operations/*_fixtures.py")):
                if script.name == "verify_clean_install_fixtures.py":
                    continue  # Requires the actual candidate; run in release().
                self.run(str(script.relative_to(self.source)), [sys.executable, "-B", str(script)])

    def build(self, project: str) -> Path:
        if project in self.outputs:
            return self.outputs[project]
        require(self.dotnet is not None, "dotnet_required")
        path = self.source / project
        flags = ["--artifacts-path", str(self.scratch / "artifacts"), "-m:1",
                 "-p:STS2GameDataDir=" + str(self.refs),
                 "-p:HarmonyPath=" + str(self.refs / "0Harmony.dll"),
                 "-p:NuGetAudit=false", "-p:UseSharedCompilation=false", "-p:BuildInParallel=false"]
        self.run("build:" + project, [self.dotnet, "build", str(path), "-c", "Release",
                                     "--configfile", str(self.nuget), *flags])
        assembly = ET.fromstring(self.files[project]).findtext(".//AssemblyName") or path.stem
        output = self.scratch / "artifacts/bin" / path.stem / "release" / (assembly + ".dll")
        require(output.is_file(), "missing_build_output")
        require(not any((output.parent / name).exists() for name in ("sts2.dll", "GodotSharp.dll")),
                "copied_target_game")
        self.outputs[project] = output
        return output

    def behavior(self) -> None:
        require(self.run("sdk", [self.dotnet, "--version"]) == SDK_VERSION, "sdk_identity")
        for project in sorted(p for p in self.files if p.endswith(".csproj")):
            output = self.build(project)
            tree = ET.fromstring(self.files[project])
            if tree.findtext(".//OutputType") != "Exe":
                continue
            folder = Path(project).parent.name
            if folder == "verifier_tests" or not (folder == "tests" or folder.endswith("_tests")):
                continue
            dependencies, _ = project_closure(self.files, project)
            require(all(node.attrib.get("Include") not in ("sts2", "GodotSharp")
                        for p in dependencies for node in ET.fromstring(self.files[p]).iter("Reference")),
                    "game_assembly_in_executable_fixture")
            command = [self.dotnet, str(output)]
            if folder == "operator_tests":
                command += ["--fixture-root", str(self.scratch.with_name(
                    self.scratch.name + "-" + Path(project).stem + "-operator"))]
            self.run("test:" + project, command)
        self.integration()

    def integration(self) -> None:
        def call(name: str, script: str, *args: str) -> None:
            self.run(name, [sys.executable, "-B", str(self.source / script), "--dotnet", self.dotnet, *args])

        if "items" in self.targets:
            self.run("items:host_wire", [sys.executable, "-B", "-c",
                "import json,sys; from pathlib import Path; from cross_language import run_cross_language; "
                "print(json.dumps(run_cross_language(Path(sys.argv[1]), Path(sys.argv[2]), Path('vectors.json'))))",
                self.dotnet, str(self.build("components/item_wire/producer_tests/Sts2AgentBridge.ItemV1.Wire.Tests.csproj"))],
                cwd=self.source / "components/item_wire")
            self.run("items:socket", [sys.executable, "-B", "-c",
                "import json,sys; from pathlib import Path; from cross_socket import run_cross_socket; "
                "print(json.dumps(run_cross_socket(Path(sys.argv[1]), Path(sys.argv[2]))))",
                self.dotnet, str(self.build("components/item_transport/runtime_tests/Sts2AgentBridge.ItemV1.Transport.Tests.csproj"))],
                cwd=self.source / "components/item_transport")
        if "events" in self.targets:
            call("events:host_native", "components/events/integration_tests/test_generic_event_integration.py",
                 "--fixture", str(self.build("components/events/integration/Sts2AgentBridge.GenericEventV7.Integration.csproj")),
                 "--native-fixture", str(self.build("components/events/integration/GenericEventV7.Native.Integration.csproj")),
                 "--host", str(self.source / "components/events/host/generic_event_host.py"))
            call("events:socket", "apps/events/integration/test_generic_event_socket_composition.py",
                 "--fixture", str(self.build("apps/events/integration/GenericEventReleaseV10.SocketFixture.csproj")))
        if "cards" in self.targets:
            call("cards:host_wire", "components/cards/host_tests/run_cross_language.py",
                 "--fixture", str(self.build("components/cards/wire_tests/Sts2AgentBridge.CardSelectionV1.Wire.Tests.csproj")))
            call("cards:socket", "apps/cards/integration/test_card_selection_socket_composition.py",
                 "--fixture", str(self.build("apps/cards/runtime_tests/Sts2AgentBridge.CardSelectionV1.Transport.Tests.csproj")))
        if "rooms" in self.targets:
            call("rooms:host_wire", "apps/rooms/integration/test_shop_map_cross_language.py",
                 "--fixture", str(self.build("apps/rooms/integration/Sts2AgentBridge.ShopMapPermissionV1.Integration.csproj")),
                 "--item-host", str(self.source / "components/item_wire/host/item_host.py"))
            call("rooms:socket", "apps/rooms/integration/test_socket_composition.py",
                 "--fixture", str(self.build("apps/rooms/runtime_tests/Sts2AgentBridge.ShopMapPermissionV1.Transport.Tests.csproj")))

    def release(self) -> dict[str, dict]:
        releases = {}
        for target in self.targets:
            app = self.source / "apps" / target
            candidate = self.build(PRODUCTION[target])
            require(not (candidate.parent / "0Harmony.dll").exists(), "copied_harmony")
            policy = next(app.glob("policy/*.json"))
            verifier_project = str(next(app.glob("verifier/*.csproj")).relative_to(self.source))
            verifier_tests = str(next(app.glob("verifier_tests/*.csproj")).relative_to(self.source))
            source_root = str(self.source.parents[1])
            self.run(target + ":surface", [self.dotnet, str(self.build(verifier_project)),
                "--assembly", str(candidate), "--source-root", source_root, "--policy", str(policy)])
            self.run(target + ":verifier_mutations", [self.dotnet, str(self.build(verifier_tests)),
                "--candidate", str(candidate), "--source-root", source_root, "--policy", str(policy)])
            self.run(target + ":package", [sys.executable, "-B", str(app / "package/package_fixtures.py"), str(candidate)])
            clean = app / "operations/verify_clean_install_fixtures.py"
            if clean.exists():
                self.run(target + ":clean_install", [sys.executable, "-B", str(clean), "--candidate", str(candidate)])
            # Only a completed release gate emits a live-usable manifest. It binds
            # current transitive sources and tests, never an ancestry inventory.
            hashes, digest = inventory(collect_sources(self.source, [target]))
            release = {"schema_version": 1, "status": "passed", "suite": "release", "target": target,
                       "source_inventory_sha256": digest, "files": hashes,
                       "sdk": SDK_VERSION, "references": REFERENCES, "checks": self.checks,
                       "production": {"sha256": sha(candidate.read_bytes()), "bytes": candidate.stat().st_size}}
            releases[target] = release
        return releases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=[*TARGET_COMPONENTS, "all"], default="events")
    parser.add_argument("--suite", choices=["sources", "python", "build", "test", "release"], default="test")
    parser.add_argument("--dotnet", type=Path)
    parser.add_argument("--game-data-dir", type=Path)
    parser.add_argument("--scratch", type=Path, help="New disposable output directory; created exclusively.")
    args = parser.parse_args()
    require(sys.version_info >= (3, 10), "python_310")
    targets = list(TARGET_COMPONENTS) if args.target == "all" else [args.target]
    files = collect_sources(ROOT, targets)
    if args.suite == "sources":
        print(json.dumps({"status": "passed", **validate_sources(files, targets)}))
        return 0
    if args.suite != "python":
        require(args.dotnet is not None and args.game_data_dir is not None, "sdk_and_references_required")
    if args.scratch is None:
        scratch = Path(tempfile.mkdtemp(prefix="sts-bridge-", dir="/private/tmp"))
    else:
        scratch = args.scratch.absolute()
        require(scratch.parent == Path("/private/tmp") and not scratch.exists(), "scratch_boundary")
        scratch.mkdir(mode=0o700)
    start = time.monotonic()
    gate = Gate(targets, scratch, str(args.dotnet.resolve(strict=True)) if args.dotnet else None,
                args.game_data_dir, release=args.suite == "release")
    print(json.dumps({"status": "running", "scratch": str(scratch), "suite": args.suite, "targets": targets}), flush=True)
    try:
        if args.suite == "build":
            require(gate.run("sdk", [gate.dotnet, "--version"]) == SDK_VERSION, "sdk_identity")
            for target in targets:
                gate.build(PRODUCTION[target])
        else:
            gate.python()
            if args.suite != "python":
                gate.behavior()
        releases = gate.release() if args.suite == "release" else {}
        # Changes during a gate cannot receive the evidence from its input copy.
        require(inventory(collect_sources(ROOT, targets)) == inventory(gate.files), "source_changed_during_gate")
        manifests = {}
        for target, release in releases.items():
            path = scratch / (target + "-release.json")
            path.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n")
            manifests[target] = sha(path.read_bytes())
        result = {"status": "passed", "suite": args.suite, "targets": targets,
                  "seconds": round(time.monotonic() - start, 3), "source": gate.summary,
                  "checks": gate.checks, "release_manifests": manifests,
                  "target_game_executed": False, "live_campaign_started": False}
        (scratch / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "checks"} | {"check_groups": len(gate.checks), "scratch": str(scratch)}))
        return 0
    except Exception:
        (scratch / "failed.json").write_text(json.dumps({"status": "failed", "checks": gate.checks}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
