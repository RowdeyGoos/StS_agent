"""Regression mutations of the reviewed repair build-input boundary."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT))
import check as gate

def components():
    names=("item_v1","item_wire_v1","item_transport_v1","item_bootstrap_v1","item_release_v1",
           "room_flows_v1","room_release_v1","shop_diagnostic_v1","shop_map_permission_v1")
    return {name:{p.relative_to(ROOT.parent/name).as_posix():p.read_bytes() for p in (ROOT.parent/name).rglob("*")
                  if p.is_file() and not {"bin","obj","__pycache__"}.intersection(p.relative_to(ROOT.parent/name).parts)} for name in names}
def rejected(base,path,data):
    changed={name:dict(files) for name,files in base.items()};changed["shop_map_permission_v1"][path]=data
    try:gate.verify_projects(changed)
    except ValueError:return
    raise AssertionError("mutated project boundary accepted")
def main():
    base=components();own=base["shop_map_permission_v1"];gate.verify_projects(base);checks=1
    for name in ("Directory.Build.targets","Extra.props","compiler.rsp","global.json","NuGet.Config"):
        rejected(base,name,b"<Project />\n");checks+=1
    for before,after in ((b"<ImportDirectoryBuildTargets>false",b"<ImportDirectoryBuildTargets>true"),
                         (b"<LangVersion>12.0",b"<LangVersion>11.0"),
                         (b"</Project>",b'<Target Name="Injected" /></Project>')):
        assert own["Directory.Build.props"].count(before)==1
        rejected(base,"Directory.Build.props",own["Directory.Build.props"].replace(before,after));checks+=1
    core="core/Sts2AgentBridge.ShopMapPermissionV1.Core.csproj"
    for before,after in ((b"net9.0",b"net8.0"),(b"<PropertyGroup>",b'<PropertyGroup Condition="True">')):
        assert own[core].count(before)==1
        rejected(base,core,own[core].replace(before,after));checks+=1
    prod="production/Sts2AgentBridgeRoomFlowsV1.csproj"
    for before,after in ((b'Text="STS2GameDataDir is required."',b'Text="Bypass"'),
                         (b'Include="../core/ShopV1Session.cs"',b'Include="../../room_flows_v1/shop/core/ShopV1Session.cs"'),
                         (b"</Project>",b'<ItemGroup><Compile Include="../injected.cs" /></ItemGroup></Project>')):
        assert own[prod].count(before)==1
        rejected(base,prod,own[prod].replace(before,after));checks+=1
    rejected(base,"injected.cs",b"class Unreviewed {}\n");checks+=1
    print(json.dumps({"schema_version":1,"status":"passed","suite":"shop_map_permission_project_boundary","check_count":checks,"candidate_executed":False},separators=(",",":")))
if __name__=="__main__":main()
