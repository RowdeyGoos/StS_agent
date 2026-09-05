#!/usr/bin/env python3
"""Offline room release gate; no installation, live endpoint or target execution."""
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

ROOT=Path(__file__).absolute().parent
ROOM_CHECK="c61218e8673860d864c34a49183eca036d8558fe7d44e1afe7b5b308244c298e"
ROOM_CONTRACT="67c5221f0db9625c9b0c67539dc64899849bfc55780495fa2f8681f4b44f5416"
ROOM_MANIFEST="91f5750b70a7b3c735f487a0e5d3d0315b6c6b32593b6fe452845745e506b213"
ROOM_INVENTORY="96c47beadd96acb1a886748fad5691efca754f83dc1f26064707804a8a178bae"
CONTRACT="f5c0f76a302b78ae30994a96288dd9a70310af908dd63dfc1cef0cf7e566df21"
PROJECTS={
    "runtime/Sts2AgentBridge.RoomFlowsV1.Transport.csproj",
    "runtime_tests/Sts2AgentBridge.RoomFlowsV1.Transport.Tests.csproj",
    "operator_tests/Sts2AgentBridge.RoomFlowsV1.Operator.Tests.csproj",
    "lifecycle_tests/Sts2AgentBridge.RoomFlowsV1.Bootstrap.Tests.csproj",
    "production/Sts2AgentBridgeRoomFlowsV1.csproj",
    "verifier/Sts2AgentBridge.RoomFlowsV1.Release.Verifier.csproj",
    "verifier_tests/Sts2AgentBridge.RoomFlowsV1.Release.Verifier.Tests.csproj",
}
PURE_DEPENDENCIES={
    "Sts2AgentBridge.RoomFlowsV1.Wire","Sts2AgentBridge.RoomFlowsV1.Broker",
    "Sts2AgentBridge.RoomFlowsV1.Common","Sts2AgentBridge.RoomFlowsV1.Shop.Core",
    "Sts2AgentBridge.RoomFlowsV1.Event.Core","Sts2AgentBridge.ItemV1.Wire",
    "Sts2AgentBridge.ItemV1.Core",
}

def fail(code):raise ValueError(code)
def sha(data):return hashlib.sha256(data).hexdigest()

def load_room():
    path=ROOT.parent/"room_flows_v1/check.py"
    current=Path(path.anchor)
    for part in path.parts[1:]:
        current/=part
        if stat.S_ISLNK(current.lstat().st_mode):fail("room_helper_link")
    data=path.read_bytes()
    if sha(data)!=ROOM_CHECK:fail("room_helper_identity")
    module=types.ModuleType("verified_room_checker");module.__file__=str(path)
    exec(compile(data,str(path),"exec"),module.__dict__)
    return module

def verify_properties(own):
    controls={name for name in own if Path(name).suffix.lower() in (".props",".targets",".rsp") or
              Path(name).name.lower() in ("nuget.config","global.json")}
    if controls!={"Directory.Build.props"}:fail("build_control_inventory")
    tree=ET.fromstring(own["Directory.Build.props"])
    if tree.tag!="Project" or tree.attrib or len(tree)!=1 or tree[0].tag!="PropertyGroup" or tree[0].attrib:fail("shared_properties_structure")
    expected=[
        ("ImportDirectoryBuildTargets",{},"false"),("LangVersion",{},"12.0"),("Nullable",{},"enable"),
        ("ImplicitUsings",{},"disable"),("TreatWarningsAsErrors",{},"true"),("WarningLevel",{},"9999"),
        ("AllowUnsafeBlocks",{},"false"),("Deterministic",{},"true"),("ContinuousIntegrationBuild",{},"true"),
        ("AssemblyVersion",{},"1.0.0.0"),("FileVersion",{},"1.0.0.0"),("Version",{},"1.0.0"),
        ("InformationalVersion",{},"1.0.0"),("IncludeSourceRevisionInInformationalVersion",{},"false"),
        ("DebugType",{},"None"),("DebugSymbols",{},"false"),
        ("PathMap",{},"$(MSBuildThisFileDirectory)..=/_/successors/"),
        ("PathMap",{"Condition":"'$(STS2GameDataDir)' != ''"},"$(PathMap),$(STS2GameDataDir)=/_/game/"),
        ("RestoreIgnoreFailedSources",{},"false")]
    if [(n.tag,n.attrib,n.text) for n in tree[0]]!=expected or any(len(n) for n in tree[0]):fail("shared_properties_mismatch")

def verify_projects(components):
    own=components["room_release_v1"]
    verify_properties(own)
    if {p for p in own if p.endswith(".csproj")}!=PROJECTS:fail("project_inventory")
    all_inputs={name+"/"+p for name,files in components.items() for p in files}
    compiled=set()
    policy=json.loads(own["policy/room_release_policy.json"])
    production=[]
    for name in sorted(PROJECTS):
        tree=ET.fromstring(own[name])
        if tree.tag!="Project" or tree.attrib!={"Sdk":"Microsoft.NET.Sdk"}:fail("project_sdk")
        props={};sources=[];refs=[];projects=[];targets=[]
        for group in tree:
            if group.tag=="PropertyGroup" and not group.attrib:
                for n in group:
                    if n.attrib or len(n) or n.tag in props:fail("project_property")
                    props[n.tag]=n.text
            elif group.tag=="ItemGroup" and not group.attrib:
                for n in group:
                    if n.tag in ("Compile","ProjectReference") and set(n.attrib)-{"Include","Link"}==set() and not len(n):
                        value=n.attrib.get("Include","")
                        if "$" in value or "*" in value or Path(value).is_absolute():fail("dynamic_project_input")
                        full=os.path.normpath("room_release_v1/"+str(Path(name).parent/value))
                        if full not in all_inputs:fail("project_input_boundary")
                        if n.tag=="Compile":
                            if not full.endswith(".cs"):fail("compile_input_type")
                            sources.append(full);compiled.add(full)
                        else:projects.append(full)
                    elif n.tag=="Reference" and set(n.attrib)=={"Include"}:
                        if any(c.attrib or len(c) for c in n):fail("reference_shape")
                        refs.append((n.attrib["Include"],[(c.tag,c.text) for c in n]))
                    else:fail("project_item")
            elif group.tag=="Target":targets.append(group)
            else:fail("project_structure")
        allowed={"TargetFramework","OutputType","AssemblyName","RootNamespace","EnableDefaultCompileItems",
                 "LangVersion","Nullable","ImplicitUsings","TreatWarningsAsErrors","WarningLevel","AnalysisLevel",
                 "Deterministic","ContinuousIntegrationBuild","DebugType","DebugSymbols","DefineConstants","StartupObject"}
        if set(props)-allowed:fail("project_properties")
        values={"TargetFramework":"net9.0","EnableDefaultCompileItems":"false","LangVersion":"12.0",
                "Nullable":"enable","ImplicitUsings":"disable","TreatWarningsAsErrors":"true","WarningLevel":"9999",
                "AnalysisLevel":"9.0","Deterministic":"true","ContinuousIntegrationBuild":"true","DebugType":"none",
                "DebugSymbols":"false","AssemblyName":Path(name).stem,
                "OutputType":"Library" if name.startswith(("production/","runtime/")) else "Exe",
                "RootNamespace":"Sts2AgentBridge.Verifier" if name.startswith("verifier/") else
                                "Sts2AgentBridge.RoomFlowsV1.Release.Verifier.Tests" if name.startswith("verifier_tests/") else
                                "Sts2AgentBridge.Successors.RoomReleaseV1"}
        if name.startswith("verifier_tests/"):values["StartupObject"]="Program"
        if name.startswith(("runtime_tests/","lifecycle_tests/")):values["DefineConstants"]="$(DefineConstants);ROOM_RELEASE_TEST_SEAM"
        if name.startswith("operator_tests/"):values["DefineConstants"]="$(DefineConstants);ITEM_BOOTSTRAP_TEST_SEAM;ROOM_RELEASE_TEST_SEAM"
        if any(key not in values or value!=values[key] for key,value in props.items()):fail("project_property_value")
        if any(key not in props for key in ("TargetFramework","OutputType","EnableDefaultCompileItems","AssemblyName")):fail("project_property_missing")
        if len(sources)!=len(set(sources)):fail("duplicate_compile")
        is_test="_tests/" in name
        if "DefineConstants" in props and not is_test:fail("production_test_symbol")
        if name.startswith("production/"):
            if projects or "DefineConstants" in props or props.get("OutputType")!="Library" or props.get("AssemblyName")!="Sts2AgentBridgeRoomFlowsV1":fail("production_composition")
            expected=[("sts2",[("HintPath","$(STS2GameDataDir)/sts2.dll"),("Private","false")]),
                      ("GodotSharp",[("HintPath","$(STS2GameDataDir)/GodotSharp.dll"),("Private","false")])]
            if refs!=expected or len(targets)!=1 or targets[0].attrib!={"Name":"ValidatePinnedGameData","BeforeTargets":"ResolveAssemblyReferences"}:fail("production_reference_boundary")
            expected_errors=[
                {"Condition":"'$(STS2GameDataDir)' == ''","Text":"STS2GameDataDir is required."},
                {"Condition":"'$(STS2GameDataDir)' != '' and !$([System.IO.Path]::IsPathFullyQualified('$(STS2GameDataDir)'))","Text":"STS2GameDataDir must be absolute."},
                {"Condition":"'$(STS2GameDataDir)' != '' and !Exists('$(STS2GameDataDir)/sts2.dll')","Text":"Pinned sts2.dll is missing."},
                {"Condition":"'$(STS2GameDataDir)' != '' and !Exists('$(STS2GameDataDir)/GodotSharp.dll')","Text":"Pinned GodotSharp.dll is missing."}]
            if [n.attrib for n in targets[0]]!=expected_errors or any(n.tag!="Error" or len(n) or n.text for n in targets[0]):fail("production_target")
            production=sorted("bridge/Sts2AgentBridge/successors/"+p for p in sources)
        else:
            if refs or targets or any("/native/" in p or "/production/" in p for p in sources):fail("pure_native_boundary")
            if projects and projects!=["room_flows_v1/wire/Sts2AgentBridge.RoomFlowsV1.Wire.csproj"]:fail("pure_project_references")
    if production!=[p["path"] for p in policy["source_files"]]:fail("production_policy_source_closure")
    if {p for p in own if p.endswith(".cs")}!={p.split("/",1)[1] for p in compiled if p.startswith("room_release_v1/")}:fail("uncompiled_new_source")

def run(command,cwd,env,*,sdk=False,unittest=False):
    r=subprocess.run(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
    if r.returncode:fail("offline_command_failed\n"+r.stdout+r.stderr)
    error=r.stderr
    if sdk:
        if any(x!="CSSM_ModuleLoad(): One or more parameters passed to a function were not valid." for x in error.splitlines() if x):fail("sdk_stderr")
    elif unittest:
        if not re.fullmatch(r"[.s]+\n-+\nRan [0-9]+ tests? in [0-9.]+s\n\nOK(?: \(skipped=[0-9]+\))?\n",error):fail("unittest_stderr")
    elif error:fail("unexpected_stderr")
    return r.stdout

def passed(output,suite=None,count=None):
    value=json.loads(output)
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"]!=1 or value.get("status")!="passed":fail("fixture_result")
    if suite is not None and value.get("suite")!=suite:fail("fixture_suite")
    base={"schema_version","status","suite","check_count"}
    extras={"manage_live_campaign_fixtures":{"checks"},"check_live_runtime_fixtures":{"checks"},
            "room_release_package":{"mutation_cases"},"room_release_project_boundary":{"candidate_executed"}}
    if suite=="room_flows_v1_release_surface":
        expected={"schema_version","status","suite","assembly_sha256","checked_method_bodies","metadata_projection_sha256","source_projection_sha256"}
        if set(value)!=expected:fail("surface_result_shape")
        return value
    if set(value)!=base|extras.get(suite,set()):fail("fixture_result_shape")
    if type(value["check_count"]) is not int or value["check_count"]<1 or (count is not None and value["check_count"]!=count):fail("fixture_count")
    if "checks" in value:
        checks=value.pop("checks")
        if type(checks) is not list or len(checks)!=value["check_count"] or len(set(checks))!=len(checks) or any(type(x) is not str or not re.fullmatch("[a-z0-9_]{1,100}",x) for x in checks):fail("fixture_check_codes")
    if "mutation_cases" in value and value["mutation_cases"]!=9:fail("package_mutation_count")
    if "candidate_executed" in value and value["candidate_executed"] is not False:fail("checker_execution_boundary")
    return value

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dotnet",type=Path,required=True)
    parser.add_argument("--game-data-dir",type=Path,required=True)
    parser.add_argument("--scratch",type=Path,required=True)
    args=parser.parse_args()
    if sys.version_info<(3,10):fail("python_310_required")
    room=load_room();release=room.load_release();boot=release.load_bootstrap();helper=boot.load_frozen_helper()
    contracts={"item_v1":helper.CORE_CONTRACT,"item_wire_v1":helper.WIRE_CONTRACT,
               "item_transport_v1":boot.TRANSPORT_CONTRACT,"item_bootstrap_v1":boot.CONTRACT,
               "item_release_v1":release.CONTRACT,"room_flows_v1":ROOM_CONTRACT}
    pins={"item_v1":(helper.CORE_MANIFEST,helper.CORE_INVENTORY),
          "item_wire_v1":(helper.WIRE_MANIFEST,helper.WIRE_INVENTORY),
          "item_transport_v1":(boot.TRANSPORT_MANIFEST,boot.TRANSPORT_INVENTORY),
          "item_bootstrap_v1":(release.BOOT_MANIFEST,release.BOOT_INVENTORY),
          "item_release_v1":(room.RELEASE_MANIFEST,room.RELEASE_INVENTORY),
          "room_flows_v1":(ROOM_MANIFEST,ROOM_INVENTORY)}
    components={};inventories={}
    for name in contracts:
        components[name],inventories[name]=helper.source_snapshot(ROOT.parent/name,name,contracts[name],*pins[name])
    components["room_release_v1"],inventory=helper.source_snapshot(ROOT,"room_release_v1",CONTRACT)
    helper.verify_old_inventory(ROOT.parents[3]);room.verify_projects(components["room_flows_v1"])
    verify_projects(components)
    game=args.game_data_dir
    if not game.is_absolute() or str(game)!=os.path.normpath(str(game)):fail("reference_root")
    helper.reject_links(game)
    references={name:boot.pinned_reference(helper,game/name,size,digest) for name,(size,digest) in boot.REFERENCES.items()}
    if args.scratch.parent!=Path("/private/tmp"):fail("scratch_boundary")
    helper.create_scratch(args.scratch)
    dotnet=str(args.dotnet.resolve(strict=True))
    def snapshot_at(destination):
        destination.mkdir()
        source=destination/"source";siblings=source/"bridge/Sts2AgentBridge/successors"
        for component,files in components.items():
            for name,data in files.items():
                p=siblings/component/name;p.parent.mkdir(parents=True,exist_ok=True)
                with p.open("xb") as output:output.write(data)
        refs=destination/"references";refs.mkdir()
        for name,data in references.items():(refs/name).write_bytes(data)
        empty=destination/"no_game_inputs";empty.mkdir()
        tmp=destination/"tmp";tmp.mkdir(mode=0o700)
        env={"PATH":"/usr/bin:/bin","LC_ALL":"C","TMPDIR":str(tmp),"DOTNET_CLI_HOME":str(destination/"cli"),
             "DOTNET_SKIP_FIRST_TIME_EXPERIENCE":"1","DOTNET_CLI_TELEMETRY_OPTOUT":"1","DOTNET_GENERATE_ASPNET_CERTIFICATE":"false",
             "DOTNET_NOLOGO":"1","DOTNET_MULTILEVEL_LOOKUP":"0","DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER":"1",
             "MSBUILDDISABLENODEREUSE":"1","NUGET_PACKAGES":str(destination/"packages"),"PYTHONDONTWRITEBYTECODE":"1"}
        own=siblings/"room_release_v1";nuget=destination/"NuGet.Config"
        nuget.write_text("<configuration><packageSources><clear /></packageSources></configuration>\n")
        if run([dotnet,"--version"],own,env).strip()!="9.0.303":fail("sdk_mismatch")
        def build(relative,native=False):
            project=siblings/relative;art=destination/"artifacts"
            flags=["--artifacts-path",str(art),"-p:STS2GameDataDir="+str(refs if native else empty),"-m:1"]
            run([dotnet,"restore",str(project),"--configfile",str(nuget),*flags,"-p:RestoreBuildInParallel=false","-p:NuGetAudit=false"],own,env,sdk=True)
            run([dotnet,"build",str(project),"--no-restore","-c","Release",*flags,"-p:BuildInParallel=false","-p:UseSharedCompilation=false"],own,env,sdk=True)
            name=project.stem;directory=art/"bin"/name/"release"
            assembly=directory/(name+".dll")
            deps=json.loads((directory/(name+".deps.json")).read_bytes())
            names={x.rsplit("/",1)[0] for x in deps["libraries"]}
            if native:
                if names!={name} or {p.name for p in directory.glob("*.dll")}!={name+".dll"}:fail("production_output_boundary")
            elif names-{name}-PURE_DEPENDENCIES or any(p.name in ("sts2.dll","GodotSharp.dll","Sts2AgentBridgeRoomFlowsV1.dll") for p in directory.glob("*.dll")):
                fail("pure_dependency_boundary")
            return assembly
        return source,siblings,own,env,build
    source,siblings,own,env,build=snapshot_at(args.scratch/"first")
    summaries={}
    tests=[
        ("operator_tests/Sts2AgentBridge.RoomFlowsV1.Operator.Tests.csproj","operator","room_flows_v1_operator",5),
        ("lifecycle_tests/Sts2AgentBridge.RoomFlowsV1.Bootstrap.Tests.csproj","bootstrap","room_flows_v1_bootstrap",12),
        ("runtime_tests/Sts2AgentBridge.RoomFlowsV1.Transport.Tests.csproj","runtime","room_flow_transport",1254),
    ]
    assemblies={}
    for relative,key,suite,count in tests:
        assembly=build("room_release_v1/"+relative);assemblies[key]=assembly
        arguments=[dotnet,str(assembly)]
        if key=="operator":
            # The operator fixture accepts an absent synthetic home directly
            # below /private/tmp; it creates and removes that home itself.
            fixture_root=Path("/private/tmp")/("room-release-operator-"+sha(str(args.scratch).encode("utf-8"))[:24])
            arguments.extend(["--fixture-root",str(fixture_root)])
        summaries[key]=passed(run(arguments,own,env),suite,count)
    summaries["socket_composition"]=passed(run([sys.executable,"-B","-I","-S",str(own/"integration/test_socket_composition.py"),
        "--dotnet",dotnet,"--fixture",str(assemblies["runtime"])],own,env),"room_release_socket_composition",87)
    for relative,key,suite,count in (
        ("checker_tests/test_project_boundary.py","project_boundary","room_release_project_boundary",15),
        ("transport_tests/test_room_transport.py","python_transport","room_release_transport",8),
        ("client_tests/client_fixtures.py","client","room_release_client",13),
        ("operations/manage_live_campaign_fixtures.py","campaign_manager","manage_live_campaign_fixtures",39),
        ("operations/check_live_runtime_fixtures.py","runtime_operations","check_live_runtime_fixtures",17)):
        summaries[key]=passed(run([sys.executable,"-B","-I","-S",str(own/relative)],own,env,
                                  unittest=key in ("python_transport","client")),suite,count)
    candidate=build("room_release_v1/production/Sts2AgentBridgeRoomFlowsV1.csproj",native=True)
    second_source,_,_,_,second_build=snapshot_at(args.scratch/"second")
    second=second_build("room_release_v1/production/Sts2AgentBridgeRoomFlowsV1.csproj",native=True)
    if candidate.read_bytes()!=second.read_bytes():fail("candidate_reproduction")
    verifier=build("room_release_v1/verifier/Sts2AgentBridge.RoomFlowsV1.Release.Verifier.csproj")
    mutations=build("room_release_v1/verifier_tests/Sts2AgentBridge.RoomFlowsV1.Release.Verifier.Tests.csproj")
    policy=own/"policy/room_release_policy.json"
    summaries["surface"]=passed(run([dotnet,str(verifier),"--assembly",str(candidate),"--source-root",str(source),"--policy",str(policy)],own,env),"room_flows_v1_release_surface")
    fixed_policy=json.loads(policy.read_bytes())
    surface=summaries["surface"]
    if (surface["assembly_sha256"]!=sha(candidate.read_bytes()) or
        surface["assembly_sha256"]!=fixed_policy["candidate_sha256"] or
        surface["metadata_projection_sha256"]!=fixed_policy["metadata_projection_sha256"] or
        surface["source_projection_sha256"]!=fixed_policy["source_projection_sha256"] or
        surface["checked_method_bodies"]!=fixed_policy["checked_method_bodies"]):fail("surface_result_identity")
    summaries["verifier_mutations"]=passed(run([dotnet,str(mutations),"--candidate",str(candidate),"--source-root",str(source),"--policy",str(policy)],own,env),"room_flows_v1_release_verifier",35)
    summaries["verifier_cli"]=release.verify_cli_negatives(dotnet,verifier,candidate,source,policy,args.scratch,own,env)
    summaries["verifier_cli"]["suite"]="room_release_cli"
    summaries["package"]=passed(run([sys.executable,"-B","-I","-S",str(own/"package/package_fixtures.py"),str(candidate)],own,env,unittest=True),"room_release_package",5)
    # Frozen capability fixtures are repeated on this same verified snapshot.
    for relative,key,suite,count in (
        ("shop/tests/Sts2AgentBridge.RoomFlowsV1.Shop.Tests.csproj","shop","room_flows_v1_shop",13),
        ("event/tests/Sts2AgentBridge.RoomFlowsV1.Event.Tests.csproj","event","room_flows_v1_event",36)):
        assembly=build("room_flows_v1/"+relative)
        summaries[key]=passed(run([dotnet,str(assembly)],own,env),suite,count)
    broker=build("room_flows_v1/broker_tests/Sts2AgentBridge.RoomFlowsV1.Broker.Tests.csproj")
    if run([dotnet,str(broker)],own,env).strip()!="room_flows_broker_checks=575":fail("broker_result")
    summaries["broker"]={"schema_version":1,"status":"passed","check_count":575}
    integration=build("room_flows_v1/integration/Sts2AgentBridge.RoomFlowsV1.Integration.csproj")
    summaries["wire"]=passed(run([dotnet,str(integration),"selftest"],own,env),"room_flows_wire",16)
    summaries["frozen_cross_language"]=passed(run([sys.executable,"-B","-I","-S",str(siblings/"room_flows_v1/integration/test_cross_language.py"),
        "--dotnet",dotnet,"--fixture",str(integration),"--item-host",str(siblings/"item_wire_v1/host/item_host.py")],own,env),"room_flows_cross_language",192)
    result={"schema_version":1,"status":"passed","suite":"room_release_v1_offline","source_inventory_sha256":inventory,
            "frozen_source_inventories":inventories,"old_bridge_file_count":48,"old_bridge_inventory_sha256":helper.OLD_INVENTORY,
            "candidate":{"bytes":candidate.stat().st_size,"sha256":sha(candidate.read_bytes()),"deterministic_build_count":2,"executed":False},
            "synthetic":summaries,"pinned_reference_count":2,"target_assemblies_executed":False,"live_campaign_started":False}
    (args.scratch/"result.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))

if __name__=="__main__":main()
