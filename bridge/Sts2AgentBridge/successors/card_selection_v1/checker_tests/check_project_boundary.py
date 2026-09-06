#!/usr/bin/env python3
"""Reject altered build inputs before a build or candidate can execute."""
from __future__ import annotations
import json
from pathlib import Path
import types

ROOT = Path(__file__).absolute().parents[1]
module = types.ModuleType("card_selection_gate")
module.__file__ = str(ROOT / "check.py")
exec(compile((ROOT / "check.py").read_bytes(), module.__file__, "exec"), module.__dict__)
files = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in ROOT.rglob("*")
         if p.is_file() and "__pycache__" not in p.parts}
checks = 0

def reject(mutator, expected):
    global checks
    changed = dict(files)
    mutator(changed)
    try:
        module.verify_projects(changed)
    except ValueError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError("Mutated project accepted")
    checks += 1

module.verify_projects(files)
checks += 1
project = "core/Sts2AgentBridge.CardSelectionV1.Core.csproj"
reject(lambda f: f.__setitem__("extra.csproj", f[project]), "project_inventory")
reject(lambda f: f.pop(project), "project_inventory")
for injection in (
    b'<Import Project="/private/tmp/foreign.targets" />',
    b'<ItemGroup><Compile Include="*.cs" /></ItemGroup>',
    b'<ItemGroup><Compile Include="../../foreign.cs" /></ItemGroup>',
    b'<ItemGroup><ProjectReference Include="../../other/Other.csproj" /></ItemGroup>',
    b'<ItemGroup><PackageReference Include="Unselected" Version="1.0.0" /></ItemGroup>',
    b'<Target Name="BeforeBuild"><Exec Command="unselected" /></Target>',
    b'<PropertyGroup><EnableDefaultCompileItems>true</EnableDefaultCompileItems></PropertyGroup>',
):
    reject(lambda f, x=injection: f.__setitem__(project, f[project].replace(b'</Project>', x + b'</Project>')),
           "project_identity")
reject(lambda f: f.__setitem__("Directory.Build.props", f["Directory.Build.props"] + b"\n"),
       "project_properties_identity")
reject(lambda f: f.__setitem__("core/Uncompiled.cs", b"class Uncompiled {}"), "uncompiled_new_source")
reject(lambda f: f.__setitem__("NuGet.Config", b"<configuration/>"), "unexpected_build_configuration")
reject(lambda f: f.__setitem__("Directory.Build.targets", b"<Project/>"), "unexpected_build_configuration")
reject(lambda f: f.pop("core/CardSelectionV1Session.cs"), "project_input_boundary")
print(json.dumps({"schema_version": 1, "status": "passed", "suite": "card_selection_v1_project_boundary",
                  "check_count": checks}, sort_keys=True, separators=(",", ":")))
