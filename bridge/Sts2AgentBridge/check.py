#!/usr/bin/env python3
"""Check the unified production bridge or one capability module; never install or launch the game."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
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
        self.component = "all"
        self.only: set[str] = set()
        self.list_only = False
        self.available: list[str] = []
        self.jobs = 4
        self.event_groups: list[str] = []
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
        self._lock = threading.Lock()
        self._active: dict[int, subprocess.Popen] = {}
        self._aborted = False
        self._next_log = 0
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
        # A check may own Python workers and C# children. Bound and terminate the
        # whole process group on timeout/interruption, not only its coordinator.
        with self._lock:
            require(not self._aborted, "gate_aborted")
            self._next_log += 1
            log = self.scratch / f"log-{self._next_log:03}.txt"
            process = subprocess.Popen(command, cwd=cwd or self.source, env=self.env,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            self._active[process.pid] = process
        timed_out = False
        try:
            output, _ = process.communicate(timeout=240)
        except BaseException as error:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output, _ = process.communicate()
            if not isinstance(error, subprocess.TimeoutExpired):
                raise
            timed_out = True
        finally:
            with self._lock:
                self._active.pop(process.pid, None)
        log.write_bytes(output)
        passed = process.returncode == 0 and not timed_out
        row = {"status": "passed" if passed else "failed",
               "seconds": round(time.monotonic() - start, 3), "log": log.name}
        if timed_out:
            row["failure"] = "timeout"
        with self._lock:
            self.checks[name] = row
        if not passed:
            print(output.decode(errors="replace")[-5000:], file=sys.stderr)
            raise ValueError(f"check_failed:{name}:{log}")
        return output.decode().strip()

    def run_parallel(self, commands: list[tuple[str, list[str]]]) -> None:
        """Overlap only prepared, isolated event executables; builds stay serial."""
        if self.jobs == 1 or len(commands) < 2:
            for name, command in commands:
                self.run(name, command)
            return
        pool = ThreadPoolExecutor(max_workers=2)
        try:
            futures = [pool.submit(self.run, name, command) for name, command in commands]
            for future in as_completed(futures):
                future.result()
        except BaseException:
            # Hold the spawn lock so a queued worker cannot start after abort.
            # Each active check owns its entire process group, including C# children.
            with self._lock:
                self._aborted = True
                for pid in self._active:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            raise
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    def selected(self, name: str) -> bool:
        if name not in self.available:
            self.available.append(name)
        return not self.list_only and (not self.only or name in self.only)

    def python_check(self, name: str, command: list[str], cwd: Path | None = None) -> None:
        if self.selected(name):
            self.run(name, command, cwd)

    def python(self) -> None:
        folders = sorted({str(Path(p).parent) for p in self.files if p.endswith(".py")
                          and Path(p).parent.name in ("host_tests", "transport_tests", "maintenance")})
        for folder in folders:
            if not self.affected(folder):
                continue
            self.python_check(folder, [sys.executable, "-B", "-m", "unittest", "discover",
                              "-s", str(self.source / folder), "-p", "test_*.py"],
                     cwd=self.source / Path(folder).parent)
        for target in self.targets:
            app = self.source / "apps" / target
            if self.component not in ("all", "host", "core"):
                continue
            self.python_check("client", [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(app / "client_tests"), "-p", "test_*.py"])
            self.python_check("core_client", [sys.executable, "-B", str(self.source / "tools/probe_live_fixtures.py")])
            self.python_check("reward_codec", [sys.executable, "-B", str(self.source / "tools/apply_reward_live_fixtures.py")])
            for script in sorted(app.glob("client_tests/*_fixtures.py")):
                self.python_check(str(script.relative_to(self.source)), [sys.executable, "-B", str(script)])
            for script in sorted(app.glob("operations/*_fixtures.py")):
                if script.name == "verify_clean_install_fixtures.py":
                    continue  # Requires the actual candidate; run in release().
                self.python_check(str(script.relative_to(self.source)), [sys.executable, "-B", str(script)])

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
        if project in PRODUCTION.values():
            require(not (output.parent / "0Harmony.dll").exists(), "copied_production_harmony")
        self.outputs[project] = output
        return output

    def affected(self, name: str) -> bool:
        if self.component == "all": return True
        if self.component in ("host", "core"):
            return name.startswith(("apps/bridge/", "tests/maintenance/"))
        names = {"items": ("items", "item_wire", "item_transport", "item_bootstrap"),
                 "rooms": ("rooms",), "cards": ("cards",), "events": ("events",)}[self.component]
        return any(name.startswith("components/" + part + "/") for part in names)

    def behavior(self) -> None:
        event_commands: list[tuple[str, list[str]]] = []
        if not self.list_only:
            require(self.run("sdk", [self.dotnet, "--version"]) == SDK_VERSION, "sdk_identity")
        for project in sorted(p for p in self.files if p.endswith(".csproj") and self.affected(p)):
            tree = ET.fromstring(self.files[project])
            folder = Path(project).parent.name
            if tree.findtext(".//OutputType") != "Exe" or not (folder == "tests" or folder.endswith("_tests")):
                continue
            if not self.selected("test:" + project):
                continue
            dependencies, _ = project_closure(self.files, project)
            require(all(node.attrib.get("Include") not in ("sts2", "GodotSharp")
                        for p in dependencies for node in ET.fromstring(self.files[p]).iter("Reference")),
                    "game_assembly_in_executable_fixture")
            command = [self.dotnet, str(self.build(project))]
            if folder == "operator_tests":
                command += ["--fixture-root", str(self.scratch.with_name(
                    self.scratch.name + "-" + Path(project).stem + "-operator"))]
            if project == "components/events/native_tests/GenericEventV7.Native.Tests.csproj":
                event_commands.append(("test:" + project, command))
            else:
                self.run("test:" + project, command)
        if self.component in ("all", "events") and self.selected("events:host_native"):
            command = [sys.executable, "-B", str(self.source / "components/events/integration_tests/test_generic_event_integration.py"),
                "--dotnet", self.dotnet, "--fixture", str(self.build("components/events/integration/Sts2AgentBridge.GenericEventV7.Integration.csproj")),
                "--host", str(self.source / "components/events/host/generic_event_host.py"), "--jobs", str(self.jobs)]
            if set(self.event_groups) != {"wire"}:
                command += ["--native-fixture", str(self.build("components/events/integration/GenericEventV7.Native.Integration.csproj"))]
            for group in self.event_groups:
                command += ["--group", group]
            event_commands.append(("events:host_native", command))
        self.run_parallel(event_commands)
        if self.component in ("all", "rooms") and self.selected("rooms:rest_host_native"):
            self.run("rooms:rest_host_native", [sys.executable, "-B", str(self.source / "components/rooms/rest/host_tests/run_rest_integration.py"),
                self.dotnet, str(self.build("components/rooms/rest/tests/Sts2AgentBridge.RestV2.Tests.csproj"))])
        if self.component in ("all", "cards"):
            if self.selected("cards:combat_host_native"):
                self.run("cards:combat_host_native", [sys.executable, "-B", str(self.source / "components/cards/host_tests/run_combat_choice.py"),
                    self.dotnet, str(self.build("components/cards/combat_tests/CombatCardChoice.Tests.csproj"))])
            if self.selected("cards:host_wire"):
                self.run("cards:host_wire", [sys.executable, "-B", str(self.source / "components/cards/host_tests/run_cross_language.py"),
                    "--dotnet", self.dotnet, "--fixture", str(self.build("components/cards/wire_tests/Sts2AgentBridge.CardSelectionV1.Wire.Tests.csproj"))])
        if self.component in ("all", "host", "core") and self.selected("shared_client:socket"):
            self.run("shared_client:socket", [sys.executable, "-B", str(self.source / "apps/bridge/client_tests/socket_integration.py"),
                self.dotnet, str(self.build("apps/bridge/tests/Sts2AgentBridge.Unified.Tests.csproj"))])

    def prepare_identity(self) -> None:
        """Bind the built candidate once, before packaging/installation fixtures.

        identity.json is release metadata, never a C# build input. A failed gate
        still cannot publish a live-usable release manifest.
        """
        candidate = self.build(PRODUCTION["bridge"])
        command = [sys.executable, "-B", str(self.source / "apps/bridge/package/prepare_identity.py"), str(candidate)]
        raw = self.run("package_identity", command) + "\n"
        name = "apps/bridge/package/identity.json"
        require(read_regular(ROOT / name) == self.files[name], "identity_changed_during_gate")
        (ROOT / name).write_text(raw)
        self.files[name] = raw.encode()
        (self.source / name).write_text(raw)

    def release(self) -> dict[str, dict]:
        candidate = self.build(PRODUCTION["bridge"])
        app = self.source / "apps/bridge"
        # A new binary gets one independent reproducibility build. Exact bytes
        # are then reused by verifier, package and installation fixtures.
        second = self.scratch / "reproduce"
        import shutil
        shutil.copytree(self.source, second / "source")
        self.run("reproducible_build", [self.dotnet, "build", str(second / "source" / PRODUCTION["bridge"]),
            "-c", "Release", "--configfile", str(self.nuget), "--artifacts-path", str(second / "artifacts"),
            "-m:1", "-p:STS2GameDataDir=" + str(self.refs), "-p:NuGetAudit=false", "-p:UseSharedCompilation=false"])
        repeated = second / "artifacts/bin/Sts2AgentBridge/release/Sts2AgentBridgeUnified.dll"
        require(read_regular(candidate) == read_regular(repeated), "nonreproducible_binary")
        verifier = self.build("apps/bridge/verifier/Sts2AgentBridge.Unified.Verifier.csproj")
        self.run("production_surface", [self.dotnet, str(verifier), str(candidate), str(self.refs / "sts2.dll"),
            str(self.build("components/events/native_tests/GenericEventV7.Native.Tests.csproj"))])
        self.run("production_surface_rejections", [sys.executable, "-B", str(app / "verifier/negative_fixtures.py"),
            self.dotnet, str(verifier), str(candidate), str(self.build("apps/bridge/tests/Sts2AgentBridge.Unified.Tests.csproj"))])
        self.run("package", [sys.executable, "-B", str(app / "package/package_fixtures.py"), str(candidate)])
        self.run("clean_install", [sys.executable, "-B", str(app / "operations/verify_clean_install_fixtures.py"), "--candidate", str(candidate)])
        self.run("package_output", [sys.executable, "-B", str(app / "package/prepare_identity.py"), str(candidate), str(self.scratch / "package")])
        hashes, digest = inventory(self.files)
        return {"bridge": {"schema_version": 1, "status": "passed", "suite": "release", "target": "bridge",
            "source_inventory_sha256": digest, "files": hashes, "sdk": SDK_VERSION, "references": REFERENCES,
            "checks": self.checks, "production": {"sha256": sha(read_regular(candidate)), "bytes": candidate.stat().st_size},
            "package": json.loads(self.files["apps/bridge/package/identity.json"])}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["bridge"], default="bridge")
    parser.add_argument("--component", choices=["all", "host", "core", "items", "rooms", "cards", "events"], default="all")
    parser.add_argument("--suite", choices=["sources", "python", "build", "test", "release"], default="test")
    parser.add_argument("--check", action="append", default=[],
                        help="Run an exact check name; repeat to select several. Development only.")
    parser.add_argument("--list-checks", action="store_true", help="List selectable checks without running them.")
    parser.add_argument("--jobs", type=int, choices=range(1, 9), default=4,
                        help="Maximum isolated event integration workers (default: 4).")
    from components.events.integration_tests.test_generic_event_integration import GROUPS
    parser.add_argument("--event-group", action="append", choices=GROUPS, default=[],
                        help="Narrow --check events:host_native to related cases. Development only.")
    parser.add_argument("--dotnet", type=Path)
    parser.add_argument("--game-data-dir", type=Path)
    parser.add_argument("--scratch", type=Path, help="New disposable output directory; created exclusively.")
    args = parser.parse_args()
    require(sys.version_info >= (3, 10), "python_310")
    targets = ["bridge"]
    require(args.suite != "release" or args.component == "all", "release_requires_all_components")
    require(not (args.check or args.list_checks or args.event_group) or args.suite in ("python", "test"),
            "selection_requires_development_suite")
    require(not args.event_group or (args.suite == "test" and args.component in ("all", "events")
            and "events:host_native" in args.check), "event_group_requires_integration_check")
    files = collect_sources(ROOT, targets)
    if args.suite == "sources":
        print(json.dumps({"status": "passed", **validate_sources(files, targets)}))
        return 0
    if args.suite != "python" and not args.list_checks:
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
    gate.component, gate.only = args.component, set(args.check)
    gate.jobs, gate.event_groups = args.jobs, args.event_group
    # Discover names before running anything, so typos cannot become an empty pass.
    gate.list_only = True
    gate.python()
    if args.suite != "python":
        gate.behavior()
    unknown = gate.only - set(gate.available)
    require(not unknown, "unknown_check:" + ",".join(sorted(unknown)))
    if args.list_checks:
        print(json.dumps({"checks": gate.available, "event_groups": GROUPS}))
        return 0
    gate.list_only = False
    print(json.dumps({"status": "running", "scratch": str(scratch), "suite": args.suite, "targets": targets}), flush=True)
    try:
        if args.suite == "release":
            gate.prepare_identity()
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
                  "component": args.component, "selected_checks": args.check,
                  "event_groups": args.event_group, "integration_jobs": args.jobs,
                  "target_game_executed": False, "live_campaign_started": False}
        (scratch / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "checks"} | {"check_groups": len(gate.checks), "scratch": str(scratch)}))
        return 0
    except Exception:
        (scratch / "failed.json").write_text(json.dumps({"status": "failed", "checks": gate.checks}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
