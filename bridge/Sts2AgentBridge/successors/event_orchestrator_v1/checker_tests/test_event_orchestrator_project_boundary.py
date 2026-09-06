#!/usr/bin/env python3
"""Synthetic regressions for the event-orchestrator build-input boundary."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import types


ROOT = Path(__file__).absolute().parents[1]


def _load(path: Path, name: str):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


gate = _load(ROOT / "check.py", "event_orchestrator_project_boundary_gate")
freezer = _load(ROOT / "freeze_sources.py", "event_orchestrator_freeze_boundary_gate")


def _project(*items: str) -> bytes:
    return ("<Project>" + "".join(items) + "</Project>").encode("ascii")


def _compile(path: str) -> str:
    return '<ItemGroup><Compile Include="' + path + '" /></ItemGroup>'


def _reference(path: str) -> str:
    return '<ItemGroup><ProjectReference Include="' + path + '" /></ItemGroup>'


def _baseline():
    own = {
        "Directory.Build.props": b"<Project />\n",
        "core/EventOrchestratorV1Contracts.cs": b"namespace Fixture; public interface IApi {}\n",
        "core/Core.cs": b"namespace Fixture; public sealed class Core {}\n",
        "tests/Program.cs": b"namespace Fixture; internal static class Program {}\n",
        "native/Native.cs": b"namespace Fixture; internal sealed class Native {}\n",
        "integration/Integration.cs": b"namespace Fixture; internal sealed class Integration {}\n",
        "wire/wire_schema.json": b'{"schema_version":1}\n',
        "core/Core.csproj": _project(
            _compile("EventOrchestratorV1Contracts.cs"),
            _compile("Core.cs")),
        "tests/Pure.Tests.csproj": _project(
            _reference("../core/Core.csproj"),
            _compile("Program.cs")),
        "native/Native.csproj": _project(
            _reference("../core/Core.csproj"),
            _compile("Native.cs")),
        "integration/Integration.csproj": _project(
            _reference("../core/Core.csproj"),
            _compile("Integration.cs")),
    }
    components = {gate.COMPONENT: own}
    project_hashes = {
        path: gate.sha(data)
        for path, data in own.items()
        if path.endswith(".csproj")
    }
    return components, project_hashes


def _configure(components, project_hashes) -> None:
    own = components[gate.COMPONENT]
    gate.PROPS = gate.sha(own["Directory.Build.props"])
    gate.API = gate.sha(own["core/EventOrchestratorV1Contracts.cs"])
    gate.SCHEMA = gate.sha(own["wire/wire_schema.json"])
    gate.PROJECT_HASHES = dict(project_hashes)
    gate.PURE_TESTS = (
        ("event_orchestrator_v1/tests/Pure.Tests.csproj", "fixture_pure", 1),
    )
    gate.BUILD_ONLY_PROJECTS = ("integration/Integration.csproj",)
    gate.NATIVE_PROJECTS = ("native/Native.csproj",)
    gate.INTEGRATION_SCRIPT = "integration.py"


def _copy(components):
    return {component: dict(files) for component, files in components.items()}


def _expect(code: str, action) -> None:
    try:
        action()
    except ValueError as error:
        if error.args != (code,):
            raise AssertionError((code, error.args)) from error
        return
    raise AssertionError("mutated boundary accepted: " + code)


def main() -> int:
    components, project_hashes = _baseline()
    _configure(components, project_hashes)
    gate.verify_projects(components, {})
    checks = 1

    changed = _copy(components)
    changed[gate.COMPONENT]["extra/Unexpected.csproj"] = _project()
    _expect("project_inventory", lambda: gate.verify_projects(changed, {}))
    checks += 1

    for name in ("Directory.Build.targets", "compiler.rsp", "NuGet.Config"):
        changed = _copy(components)
        changed[gate.COMPONENT][name] = b"<Project />\n"
        _expect("build_control_inventory", lambda changed=changed:
            gate.verify_projects(changed, {}))
        checks += 1

    changed = _copy(components)
    changed[gate.COMPONENT]["core/Uncompiled.cs"] = b"class Uncompiled {}\n"
    _expect("uncompiled_new_source", lambda: gate.verify_projects(changed, {}))
    checks += 1

    changed = _copy(components)
    changed[gate.COMPONENT]["orphan/Orphan.cs"] = b"class Orphan {}\n"
    orphan = _project(_compile("Orphan.cs"))
    changed[gate.COMPONENT]["orphan/Orphan.csproj"] = orphan
    repinned = dict(project_hashes)
    repinned["orphan/Orphan.csproj"] = gate.sha(orphan)
    _configure(changed, repinned)
    _expect("unbuilt_new_project", lambda: gate.verify_projects(changed, {}))
    checks += 1

    _configure(components, project_hashes)
    gate.NATIVE_PROJECTS = ("native/Native.csproj", "native/Native.csproj")
    _expect("duplicate_build_root", lambda: gate.verify_projects(components, {}))
    checks += 1
    _configure(components, project_hashes)

    _expect("project_input_escape", lambda:
        gate.resolve(gate.PREFIX + gate.COMPONENT + "/core/Core.csproj", "../../../../../../escape.cs"))
    checks += 1
    for value in ("*.cs", "$(Injected)/Source.cs", "../core/?.cs", "/tmp/source.cs"):
        _expect("dynamic_project_input", lambda value=value:
            gate.resolve(gate.PREFIX + gate.COMPONENT + "/core/Core.csproj", value))
        checks += 1

    for name in ("core/EventOrchestratorV1Contracts.cs", "wire/wire_schema.json"):
        changed = _copy(components)
        changed[gate.COMPONENT][name] += b" "
        _expect("shared_contract_identity", lambda changed=changed:
            gate.verify_projects(changed, {}))
        checks += 1

    # Build-only integration roots remain pure; building without direct execution
    # must not grant access to compile-only game references.
    changed = _copy(components)
    changed[gate.COMPONENT]["integration/Integration.csproj"] = _project(
        _reference("../core/Core.csproj"), _compile("Integration.cs"),
        '<ItemGroup><Reference Include="Target.Game" /></ItemGroup>')
    repinned = dict(project_hashes)
    repinned["integration/Integration.csproj"] = gate.sha(changed[gate.COMPONENT]["integration/Integration.csproj"])
    _configure(changed, repinned)
    _expect("pure_target_dependency", lambda: gate.verify_projects(changed, {}))
    checks += 1
    _configure(components, project_hashes)

    # A pure test cannot acquire a target Reference through a transitive project.
    prefix = gate.PREFIX + gate.COMPONENT + "/"
    graph = gate.inputs(components, {})
    target_core = _project(
        _compile("EventOrchestratorV1Contracts.cs"),
        _compile("Core.cs"),
        '<ItemGroup><Reference Include="Target.Game" /></ItemGroup>')
    graph[prefix + "core/Core.csproj"] = target_core
    _expect("pure_target_dependency", lambda:
        gate.project_closure(graph, prefix + "tests/Pure.Tests.csproj", pure=True))
    checks += 1

    package_core = _project(
        _compile("EventOrchestratorV1Contracts.cs"),
        _compile("Core.cs"),
        '<ItemGroup><PackageReference Include="Remote" Version="1" /></ItemGroup>')
    graph = gate.inputs(components, {})
    graph[prefix + "core/Core.csproj"] = package_core
    _expect("package_reference", lambda:
        gate.project_closure(graph, prefix + "tests/Pure.Tests.csproj", pure=True))
    checks += 1

    # Re-pin a malformed project so these checks exercise closure rather than
    # merely observing the outer project identity pin.
    changed = _copy(components)
    malformed = _project(_compile("Missing.cs"))
    changed[gate.COMPONENT]["core/Core.csproj"] = malformed
    repinned = dict(project_hashes)
    repinned["core/Core.csproj"] = gate.sha(malformed)
    _configure(changed, repinned)
    _expect("project_input_boundary", lambda: gate.verify_projects(changed, {}))
    checks += 1

    changed = _copy(components)
    changed[gate.COMPONENT]["core/Input.txt"] = b"not source\n"
    wrong_type = _project(_compile("EventOrchestratorV1Contracts.cs"),
                          _compile("Core.cs"), _compile("Input.txt"))
    changed[gate.COMPONENT]["core/Core.csproj"] = wrong_type
    repinned = dict(project_hashes)
    repinned["core/Core.csproj"] = gate.sha(wrong_type)
    _configure(changed, repinned)
    _expect("compile_input_type", lambda: gate.verify_projects(changed, {}))
    checks += 1

    # The freeze helper must never replace either an existing identity file or
    # a link occupying that name. Both checks stop before loading check.py.
    with tempfile.TemporaryDirectory(prefix="event-orchestrator-freeze-") as temporary:
        fixture = Path(temporary)
        original_root = freezer.ROOT
        freezer.ROOT = fixture
        try:
            (fixture / "source_identity.json").write_bytes(b"existing\n")
            _expect("source_identity_already_exists", freezer.main)
            checks += 1
            (fixture / "source_identity.json").unlink()
            (fixture / "target").write_bytes(b"target\n")
            (fixture / "source_identity.json").symlink_to("target")
            _expect("source_identity_already_exists", freezer.main)
            checks += 1
        finally:
            freezer.ROOT = original_root

    print(json.dumps({
        "schema_version": 1,
        "status": "passed",
        "suite": "event_orchestrator_v1_project_boundary",
        "check_count": checks,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
