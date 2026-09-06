#!/usr/bin/env python3
"""Offline shop map-permission repair gate; no installation, live endpoint or target execution."""
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
CONTRACT="b9551348a73bd4ff54433dc9693cbed3ae841bb98bdc3f4763e22f1bcac613db"
# Exact reviewed project bytes also exclude imports, wildcard sources, extra
# targets, packages and test constants in production before any build runs.
PROJECT_HASHES = {'core/Sts2AgentBridge.ShopMapPermissionV1.Core.csproj': '6110c99a3e98c7a34be88b13e6a985b5cc339bc6160d04eef21ad9392fb460f1', 'core_tests/Sts2AgentBridge.ShopMapPermissionV1.Core.Tests.csproj': 'bee3806135e25345deb240e80414b93560a2fb5a78f7a447287e75d3bd762510', 'integration/Sts2AgentBridge.ShopMapPermissionV1.Integration.csproj': 'af5c89a4afff4c3bd630b18c43a92b29b064789acc4581c688fd2a7e252d8eab', 'production/Sts2AgentBridgeRoomFlowsV1.csproj': 'baa478725b553b76572a42a778ed447bf9f74d1ce3610e0cf247a302529385ca', 'runtime_tests/Sts2AgentBridge.ShopMapPermissionV1.Transport.Tests.csproj': 'f9e91656c887293fcfa566f4bb67baf636104e865507c09f85aa480abf2e95b7', 'verifier/Sts2AgentBridge.ShopMapPermissionV1.Release.Verifier.csproj': '68871b216a54f12cbecd4f150507559a50cab60bd70ba6dc80ca45fbc61c190d', 'verifier_tests/Sts2AgentBridge.ShopMapPermissionV1.Release.Verifier.Tests.csproj': '6edd23b80738196210c72af6f6cbb007432363cf3c0fbefab6e0b4401b45d1a1', 'wire/Sts2AgentBridge.ShopMapPermissionV1.Wire.csproj': 'e4fe3d6a322a1143a84c3ebbbe063aee2a5da1d92a23aa6058962c9f5af3941b'}
PROJECTS=set(PROJECT_HASHES)
PURE_DEPENDENCIES={"Sts2AgentBridge.ShopMapPermissionV1.Core","Sts2AgentBridge.ShopMapPermissionV1.Wire",
 "Sts2AgentBridge.RoomFlowsV1.Wire","Sts2AgentBridge.RoomFlowsV1.Broker","Sts2AgentBridge.RoomFlowsV1.Common",
 "Sts2AgentBridge.RoomFlowsV1.Shop.Core","Sts2AgentBridge.RoomFlowsV1.Event.Core","Sts2AgentBridge.ItemV1.Wire","Sts2AgentBridge.ItemV1.Core"}
RELEASE_CHECK="abf81f9b968f3eb1f68e41ffbb3479a0a07d7a98251fe1250f440adf53dd194d"
RELEASE_CONTRACT="f5c0f76a302b78ae30994a96288dd9a70310af908dd63dfc1cef0cf7e566df21"
RELEASE_MANIFEST="d567c8e91e45fd2bcff2cd446f85d3d7faef3baf2b22b6f7b75ba2490d360957"
RELEASE_INVENTORY="1fde216af25f0a94c16e13b869216d7990c862d7ba19d2246060e1f36bfabf4b"

def fail(code):raise ValueError(code)
def sha(data):return hashlib.sha256(data).hexdigest()

def load_previous():
    path=ROOT.parent/"room_release_v1/check.py"
    current=Path(path.anchor)
    for part in path.parts[1:]:
        current/=part
        if stat.S_ISLNK(current.lstat().st_mode):fail("previous_helper_link")
    data=path.read_bytes()
    if sha(data)!=RELEASE_CHECK:fail("previous_helper_identity")
    module=types.ModuleType("verified_previous_checker");module.__file__=str(path)
    exec(compile(data,str(path),"exec"),module.__dict__)
    return module

def verify_projects(components):
    own=components["shop_map_permission_v1"]
    load_previous().verify_properties(own)
    if {p for p in own if p.endswith(".csproj")}!=PROJECTS:fail("project_inventory")
    all_inputs={name+"/"+p for name,files in components.items() for p in files}
    compiled=set();production=[]
    for name,expected in PROJECT_HASHES.items():
        if sha(own[name])!=expected:fail("project_identity")
        tree=ET.fromstring(own[name])
        for n in tree.iter():
            if n.tag not in ("Compile","ProjectReference","EmbeddedResource"):continue
            value=n.attrib["Include"]
            if "$" in value or "*" in value or Path(value).is_absolute():fail("dynamic_project_input")
            full=os.path.normpath("shop_map_permission_v1/"+str(Path(name).parent/value))
            if full not in all_inputs:fail("project_input_boundary")
            if n.tag=="Compile":
                if not full.endswith(".cs"):fail("compile_input_type")
                compiled.add(full)
                if name.startswith("production/"):production.append("bridge/Sts2AgentBridge/successors/"+full)
    policy=json.loads(own["policy/room_release_policy.json"])
    if sorted(production)!=[p["path"] for p in policy["source_files"]] or len(production)!=37:
        fail("production_policy_source_closure")
    if {p for p in own if p.endswith(".cs")}!={p.split("/",1)[1] for p in compiled if p.startswith("shop_map_permission_v1/")}:
        fail("uncompiled_new_source")

    original=components["room_release_v1"]["production/Sts2AgentBridgeRoomFlowsV1.csproj"].decode()
    expected=re.sub(r'Include="\.\./(runtime|operator|lifecycle|native)/',r'Include="../../room_release_v1/\1/',original)
    expected=expected.replace('Include="../../room_flows_v1/shop/core/ShopV1Session.cs"','Include="../core/ShopV1Session.cs"')
    if own["production/Sts2AgentBridgeRoomFlowsV1.csproj"]!=expected.encode():fail("production_single_source_substitution")

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
            "room_release_package":{"mutation_cases"},"room_release_project_boundary":{"candidate_executed"},"shop_map_permission_project_boundary":{"candidate_executed"}}
    if suite=="shop_map_permission_v1_release_surface":
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
    previous=load_previous();room=previous.load_room();release=room.load_release();boot=release.load_bootstrap();helper=boot.load_frozen_helper()
    contracts={"item_v1":helper.CORE_CONTRACT,"item_wire_v1":helper.WIRE_CONTRACT,
               "item_transport_v1":boot.TRANSPORT_CONTRACT,"item_bootstrap_v1":boot.CONTRACT,
               "item_release_v1":release.CONTRACT,"room_flows_v1":ROOM_CONTRACT,
               "room_release_v1":RELEASE_CONTRACT,"shop_diagnostic_v1":"4919241452060ba9cb452683f29dc518c9455860b5bfa5eb0ffe0460ff01c68a"}
    pins={"item_v1":(helper.CORE_MANIFEST,helper.CORE_INVENTORY),
          "item_wire_v1":(helper.WIRE_MANIFEST,helper.WIRE_INVENTORY),
          "item_transport_v1":(boot.TRANSPORT_MANIFEST,boot.TRANSPORT_INVENTORY),
          "item_bootstrap_v1":(release.BOOT_MANIFEST,release.BOOT_INVENTORY),
          "item_release_v1":(room.RELEASE_MANIFEST,room.RELEASE_INVENTORY),
          "room_flows_v1":(ROOM_MANIFEST,ROOM_INVENTORY),"room_release_v1":(RELEASE_MANIFEST,RELEASE_INVENTORY),
          "shop_diagnostic_v1":("3e396cd76438a0c8bb3dec77fd510c7ece0b115404a014c482d5ace4de95577f","17a0cd65e0a521e6e682d18c01be9e9c972f60cff5cb1e622ee1ead14266a697")}
    components={};inventories={}
    for name in contracts:
        components[name],inventories[name]=helper.source_snapshot(ROOT.parent/name,name,contracts[name],*pins[name])
    components["shop_map_permission_v1"],inventory=helper.source_snapshot(ROOT,"shop_map_permission_v1",CONTRACT)
    helper.verify_old_inventory(ROOT.parents[3]);room.verify_projects(components["room_flows_v1"])
    previous.verify_projects(components)
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
        own=siblings/"shop_map_permission_v1";nuget=destination/"NuGet.Config"
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
        ("shop_map_permission_v1/core_tests/Sts2AgentBridge.ShopMapPermissionV1.Core.Tests.csproj","repaired_shop","shop_map_permission_v1_core",14),
        ("room_release_v1/operator_tests/Sts2AgentBridge.RoomFlowsV1.Operator.Tests.csproj","operator","room_flows_v1_operator",5),
        ("room_release_v1/lifecycle_tests/Sts2AgentBridge.RoomFlowsV1.Bootstrap.Tests.csproj","bootstrap","room_flows_v1_bootstrap",12),
        ("shop_map_permission_v1/runtime_tests/Sts2AgentBridge.ShopMapPermissionV1.Transport.Tests.csproj","runtime","room_flow_transport",1254),
    ]
    assemblies={}
    for relative,key,suite,count in tests:
        assembly=build(relative);assemblies[key]=assembly
        arguments=[dotnet,str(assembly)]
        if key=="operator":
            # The operator fixture accepts an absent synthetic home directly
            # below /private/tmp; it creates and removes that home itself.
            fixture_root=Path("/private/tmp")/("room-release-operator-"+sha(str(args.scratch).encode("utf-8"))[:24])
            arguments.extend(["--fixture-root",str(fixture_root)])
        summaries[key]=passed(run(arguments,own,env),suite,count)
    summaries["socket_composition"]=passed(run([sys.executable,"-B","-I","-S",str(siblings/"room_release_v1/integration/test_socket_composition.py"),
        "--dotnet",dotnet,"--fixture",str(assemblies["runtime"])],own,env),"room_release_socket_composition",87)
    for relative,key,suite,count in (
        ("checker_tests/test_shop_map_project_boundary.py","project_boundary","shop_map_permission_project_boundary",15),
        ("transport_tests/test_shop_map_transport.py","python_transport","room_release_transport",8),
        ("client_tests/client_fixtures.py","client","room_release_client",13),
        ("operations/manage_live_campaign_fixtures.py","campaign_manager","manage_live_campaign_fixtures",39),
        ("operations/check_live_runtime_fixtures.py","runtime_operations","check_live_runtime_fixtures",17),
        ("operations/verify_source_derivation.py","operations_derivation","shop_map_permission_operations_derivation",15),
        ("operations/predecessor_conflict_fixtures.py","predecessor_conflicts","shop_map_permission_predecessor_conflicts",7),
        ("derivation/check_derivation.py","core_derivation","shop_map_permission_v1_derivation",15),
        ("integration/verify_fixture_derivation.py","fixture_derivation","shop_map_permission_fixture_derivation",3)):
        summaries[key]=passed(run([sys.executable,"-B","-I","-S",str(own/relative)],own,env,
                                  unittest=key in ("python_transport","client")),suite,count)
    candidate=build("shop_map_permission_v1/production/Sts2AgentBridgeRoomFlowsV1.csproj",native=True)
    second_source,_,_,_,second_build=snapshot_at(args.scratch/"second")
    second=second_build("shop_map_permission_v1/production/Sts2AgentBridgeRoomFlowsV1.csproj",native=True)
    if candidate.read_bytes()!=second.read_bytes():fail("candidate_reproduction")
    verifier=build("shop_map_permission_v1/verifier/Sts2AgentBridge.ShopMapPermissionV1.Release.Verifier.csproj")
    mutations=build("shop_map_permission_v1/verifier_tests/Sts2AgentBridge.ShopMapPermissionV1.Release.Verifier.Tests.csproj")
    policy=own/"policy/room_release_policy.json"
    summaries["surface"]=passed(run([dotnet,str(verifier),"--assembly",str(candidate),"--source-root",str(source),"--policy",str(policy)],own,env),"shop_map_permission_v1_release_surface")
    fixed_policy=json.loads(policy.read_bytes())
    surface=summaries["surface"]
    if (surface["assembly_sha256"]!=sha(candidate.read_bytes()) or
        surface["assembly_sha256"]!=fixed_policy["candidate_sha256"] or
        surface["metadata_projection_sha256"]!=fixed_policy["metadata_projection_sha256"] or
        surface["source_projection_sha256"]!=fixed_policy["source_projection_sha256"] or
        surface["checked_method_bodies"]!=fixed_policy["checked_method_bodies"]):fail("surface_result_identity")
    summaries["verifier_mutations"]=passed(run([dotnet,str(mutations),"--candidate",str(candidate),"--source-root",str(source),"--policy",str(policy)],own,env),"shop_map_permission_v1_release_verifier",40)
    summaries["verifier_cli"]=release.verify_cli_negatives(dotnet,verifier,candidate,source,policy,args.scratch,own,env)
    summaries["verifier_cli"]["suite"]="room_release_cli"
    summaries["package"]=passed(run([sys.executable,"-B","-I","-S",str(own/"package/package_fixtures.py"),str(candidate)],own,env,unittest=True),"room_release_package",5)
    summaries["clean_install"]=passed(run([sys.executable,"-B","-I","-S",str(own/"operations/verify_clean_install_fixtures.py"),
        "--candidate",str(candidate)],own,env),"verify_clean_install_fixtures",7)
    # Frozen capability fixtures are repeated on this same verified snapshot.
    for relative,key,suite,count in (
        ("shop/tests/Sts2AgentBridge.RoomFlowsV1.Shop.Tests.csproj","shop","room_flows_v1_shop",13),
        ("event/tests/Sts2AgentBridge.RoomFlowsV1.Event.Tests.csproj","event","room_flows_v1_event",36)):
        assembly=build("room_flows_v1/"+relative)
        summaries[key]=passed(run([dotnet,str(assembly)],own,env),suite,count)
    broker=build("room_flows_v1/broker_tests/Sts2AgentBridge.RoomFlowsV1.Broker.Tests.csproj")
    if run([dotnet,str(broker)],own,env).strip()!="room_flows_broker_checks=575":fail("broker_result")
    summaries["broker"]={"schema_version":1,"status":"passed","check_count":575}
    integration=build("shop_map_permission_v1/integration/Sts2AgentBridge.ShopMapPermissionV1.Integration.csproj")
    summaries["wire"]=passed(run([dotnet,str(integration),"selftest"],own,env),"room_flows_wire",16)
    summaries["frozen_cross_language"]=passed(run([sys.executable,"-B","-I","-S",str(siblings/"room_flows_v1/integration/test_cross_language.py"),
        "--dotnet",dotnet,"--fixture",str(integration),"--item-host",str(siblings/"item_wire_v1/host/item_host.py")],own,env),"room_flows_cross_language",192)
    result={"schema_version":1,"status":"passed","suite":"shop_map_permission_v1_offline","source_inventory_sha256":inventory,
            "frozen_source_inventories":inventories,"old_bridge_file_count":48,"old_bridge_inventory_sha256":helper.OLD_INVENTORY,
            "candidate":{"bytes":candidate.stat().st_size,"sha256":sha(candidate.read_bytes()),"deterministic_build_count":2,"executed":False},
            "synthetic":summaries,"pinned_reference_count":2,"target_assemblies_executed":False,"live_campaign_started":False}
    (args.scratch/"result.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))

if __name__=="__main__":main()
