#!/usr/bin/env python3
"""Isolated generic event release gate; no installation or target-game execution."""
from __future__ import annotations
import argparse,difflib,hashlib,json,os,subprocess,sys,types
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).absolute().parent
PREFIX='bridge/Sts2AgentBridge/successors/'
PREVIOUS_CHECK='632c971dd33ef7f701358c1d694a37ca5bd5364db517edbdafdaf70351d81209'
PREVIOUS_MANIFEST='33c07bef9d61c5bcef595d995a7c3986dcb51c34b55af9b38fa33218d46e0613'
PREVIOUS_INVENTORY='07cbec259e8d2e2a9b2509a51ec38071fe6cb6bc93a0cfdca2691f8e006be847'
HARMONY_BYTES=2328064
HARMONY_SHA='ef1898322c9f5c86dc1b0758b272a9c440823b4a41ca9a0b82a3aa6b3d206387'
PRODUCTION='production/Sts2AgentBridgeGenericEventV5.csproj'
def sha(data):return hashlib.sha256(data).hexdigest()
def require(value,code):
    if not value:raise ValueError(code)
def sources():
    path=ROOT.parent/'generic_event_release_v4/check.py';require(not path.is_symlink(),'predecessor_link')
    require(sha(path.read_bytes())==PREVIOUS_CHECK,'predecessor_checker')
    manifest=path.parent/'source_identity.json';require(not manifest.is_symlink() and sha(manifest.read_bytes())==PREVIOUS_MANIFEST,'predecessor_manifest')
    previous=types.ModuleType('verified_generic_predecessor');previous.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),previous.__dict__)
    helper,boot,inputs,_,inventories,prior,_=previous.sources()
    require(prior==PREVIOUS_INVENTORY,'predecessor_inventory')
    inventories=dict(inventories,generic_event_release_v4=prior);require(len(inventories)==22,'predecessor_count')
    own={};helper.reject_links(ROOT)
    for path in sorted(ROOT.rglob('*')):
        helper.reject_links(path);relative=path.relative_to(ROOT)
        require(not {'bin','obj','__pycache__'}.intersection(relative.parts),'source_outputs')
        if path.is_file() and relative.as_posix()!='source_identity.json':own[relative.as_posix()]=helper.read_regular(path)
    inventory=sha(''.join(sha(data)+'  '+name+'\n' for name,data in sorted(own.items())).encode('ascii'))
    contract=ROOT.parents[3]/'docs/PHASE_1_GENERIC_EVENT_RELEASE_V5_CONTRACT.md';helper.reject_links(contract);contract_hash=sha(helper.read_regular(contract))
    identity=ROOT/'source_identity.json'
    if identity.exists():
        require(json.loads(identity.read_bytes())==dict(schema_version=1,component='generic_event_release_v5',contract_sha256=contract_hash,inventory_sha256=inventory,files={name:sha(data) for name,data in own.items()}),'source_identity')
    inputs=dict(inputs);inputs.update({PREFIX+'generic_event_release_v5/'+name:data for name,data in own.items()})
    derivation=json.loads(own['derivation.json']);require(derivation['schema_version']==1,'derivation_schema')
    require(len({r['target'] for r in derivation['derived']})==len(derivation['derived']),'duplicate_derivation')
    for row in derivation['derived']:
        require(row['source'] in inputs and row['target'] in inputs,'derivation_boundary')
        before,after=inputs[row['source']],inputs[row['target']]
        require(sha(before)==row['source_sha256'] and sha(after)==row['target_sha256'],'derivation_identity')
        require(''.join(difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),fromfile=row['source'],tofile=row['target']))==row['unified_diff'],'derivation_delta')
    return helper,boot,inputs,own,inventories,inventory,contract_hash

def closure(inputs,project,production):
    pending=[project];visited=set();compiled=set()
    while pending:
        current=pending.pop()
        if current in visited:continue
        visited.add(current);require(current in inputs,'missing_project');tree=ET.fromstring(inputs[current])
        require(tree.find('.//EnableDefaultCompileItems').text=='false','implicit_compile')
        for node in tree.iter():
            require(node.tag not in ('PackageReference','Import','Exec','UsingTask','EmbeddedResource'),'dynamic_build')
            if node.tag in ('Compile','ProjectReference'):
                value=node.attrib['Include'];require(value and not any(c in value for c in '*?$\\') and not Path(value).is_absolute(),'dynamic_input')
                target=os.path.normpath(str(Path(current).parent/value));require(target in inputs and not target.startswith('../'),'input_boundary')
                if node.tag=='ProjectReference':pending.append(target)
                else:compiled.add(target)
            if node.tag=='Reference':
                name=node.attrib.get('Include');require(name=='0Harmony' or production and name in ('sts2','GodotSharp'),'reference_boundary')
                require(node.find('HintPath').text in ('$(HarmonyPath)','$(STS2GameDataDir)/0Harmony.dll','$(STS2GameDataDir)/sts2.dll','$(STS2GameDataDir)/GodotSharp.dll'),'reference_path')
    return compiled

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dotnet',type=Path,required=True);parser.add_argument('--game-data-dir',type=Path,required=True);parser.add_argument('--scratch',type=Path,required=True)
    args=parser.parse_args();require(sys.version_info>=(3,10),'python_310')
    helper,boot,inputs,own,inventories,inventory,contract=sources()
    require(args.scratch.parent==Path('/private/tmp'),'scratch_boundary');helper.create_scratch(args.scratch)
    helper.reject_links(args.game_data_dir)
    references={name:boot.pinned_reference(helper,args.game_data_dir/name,size,digest) for name,(size,digest) in boot.REFERENCES.items()}
    references['0Harmony.dll']=boot.pinned_reference(helper,args.game_data_dir/'0Harmony.dll',HARMONY_BYTES,HARMONY_SHA)
    projects=sorted(name for name in own if name.endswith('.csproj'))
    require(set(projects)=={PRODUCTION,'runtime/Sts2AgentBridge.GenericEventV5.Transport.csproj',
        'runtime_tests/GenericEventReleaseV5.RuntimeTests.csproj','integration/GenericEventReleaseV5.SocketFixture.csproj',
        'operator_tests/Sts2AgentBridge.GenericEventV5.Operator.Tests.csproj',
        'lifecycle_tests/Sts2AgentBridge.GenericEventV5.Bootstrap.Tests.csproj',
        'native_tests/Sts2AgentBridge.GenericEventV5.Native.Tests.csproj',
        'verifier/Sts2AgentBridge.GenericEventV5.Release.Verifier.csproj',
        'verifier_tests/Sts2AgentBridge.GenericEventV5.Release.Verifier.Tests.csproj',
        'diagnostic_native_tests/GenericEventReleaseV5.Preserved.Tests.csproj',
        'diagnostic_native_tests/GenericEventReleaseV5.Diagnostics.Tests.csproj',
        'diagnostic_native_tests/GenericEventReleaseV5.Candidates.Tests.csproj',
        'diagnostic_native_tests/GenericEventReleaseV5.BaselineTrace.Tests.csproj'},'project_inventory')
    production_sources=closure(inputs,PREFIX+'generic_event_release_v5/'+PRODUCTION,True)
    replacement_names=('GenericEventV3CardAdapter','GenericEventV3RemovalAdapter','GenericEventV3RewardAdapter','PinnedGenericEventV3NativeAdapter')
    replacements={PREFIX+'generic_event_release_v5/native/'+name+'.cs' for name in replacement_names}
    original={PREFIX+component+'/native/'+name+'.cs' for component in ('generic_event_v3','generic_event_lifecycle_v1','generic_event_release_v3','generic_event_release_v4') for name in replacement_names}
    require(replacements.issubset(production_sources) and not original.intersection(production_sources),'diagnostic_replacement_closure')
    for name in ('GenericEventV3CardAdapter','GenericEventV3RemovalAdapter','PinnedGenericEventV3NativeAdapter'):
        before=inputs[PREFIX+'generic_event_release_v4/native/'+name+'.cs']
        after=own['native/'+name+'.cs']
        require(after==before.replace(b'GenericEventReleaseV4',b'GenericEventReleaseV5'),'nonreward_namespace_only')
    require(PREFIX+'generic_event_lifecycle_v1/native/GenericEventV3Binding.cs' in production_sources and PREFIX+'generic_event_v3/native/GenericEventV3Binding.cs' not in production_sources,'lifecycle_binding_closure')
    require({PREFIX+'generic_event_v3/'+name for name in ('core/GenericEventV3Session.cs','wire/GenericEventV3WireService.cs','native/GenericEventV3Hooks.cs')}.issubset(production_sources),'frozen_gameplay_closure')
    for project in ('native_tests/Sts2AgentBridge.GenericEventV5.Native.Tests.csproj','diagnostic_native_tests/GenericEventReleaseV5.Preserved.Tests.csproj','diagnostic_native_tests/GenericEventReleaseV5.Diagnostics.Tests.csproj','diagnostic_native_tests/GenericEventReleaseV5.Candidates.Tests.csproj','integration/GenericEventReleaseV5.SocketFixture.csproj'):
        native_sources=closure(inputs,PREFIX+'generic_event_release_v5/'+project,False)
        require(replacements.issubset(native_sources) and not original.intersection(native_sources),'diagnostic_fixture_closure')
    baseline_sources=closure(inputs,PREFIX+'generic_event_release_v5/diagnostic_native_tests/GenericEventReleaseV5.BaselineTrace.Tests.csproj',False)
    baseline_native={PREFIX+'generic_event_release_v4/native/'+name+'.cs' for name in replacement_names}
    require(baseline_native.issubset(baseline_sources) and not replacements.intersection(baseline_sources),'frozen_trace_baseline_closure')
    require(PREFIX+'generic_event_release_v4/runtime/GenericEventDiagnosticCode.cs' in baseline_sources and PREFIX+'generic_event_release_v5/runtime/GenericEventDiagnosticCode.cs' not in baseline_sources,'frozen_trace_enum_closure')
    policy_sources=json.loads(own['policy/generic_event_release_policy.json'])['source_files']
    require({row['path'] for row in policy_sources}==production_sources and len(policy_sources)==len(production_sources),'policy_source_closure')
    require(all(sha(inputs[row['path']])==row['sha256'] for row in policy_sources),'policy_source_identity')
    compiled=set()
    for p in projects:compiled.update(closure(inputs,PREFIX+'generic_event_release_v5/'+p,p==PRODUCTION))
    require({PREFIX+'generic_event_release_v5/'+p for p in own if p.endswith('.cs')}.issubset(compiled),'uncompiled_source')
    required={'diagnostic_native_tests/compare_traces.py','client_tests/client_fixtures.py','transport_tests/test_generic_event_transport.py','integration/test_generic_event_socket_composition.py','operations/manage_live_campaign_fixtures.py','operations/predecessor_conflict_fixtures.py','package/package_fixtures.py'}
    require(required.issubset(own),'required_tests')
    dotnet=str(args.dotnet.resolve(strict=True));logs=0
    def run(command,cwd,env):
        nonlocal logs
        logs+=1;result=subprocess.run(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240,check=False)
        (args.scratch/f'log-{logs:03}.txt').write_bytes(result.stdout);require(result.returncode==0,f'command_failed_log_{logs:03}')
        return result.stdout.decode().strip()
    def snapshot(label):
        dest=args.scratch/label;source=dest/'source'
        for name,data in inputs.items():
            p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        # Read-only checker/client source validation needs frozen manifests and contracts.
        for name in inventories:
            src=ROOT.parent/name/'source_identity.json';target=source/PREFIX/name/'source_identity.json';target.write_bytes(helper.read_regular(src))
            manifest=json.loads(src.read_bytes())
            for doc in (ROOT.parents[3]/'docs').glob('PHASE_1*CONTRACT.md'):
                data=helper.read_regular(doc)
                if sha(data)==manifest['contract_sha256']:
                    target=source/'docs'/doc.name;target.parent.mkdir(exist_ok=True);target.write_bytes(data)
        doc=source/'docs/PHASE_1_GENERIC_EVENT_RELEASE_V5_CONTRACT.md';doc.parent.mkdir(exist_ok=True);doc.write_bytes((ROOT.parents[3]/'docs/PHASE_1_GENERIC_EVENT_RELEASE_V5_CONTRACT.md').read_bytes())
        if (ROOT/'source_identity.json').exists():(source/PREFIX/'generic_event_release_v5/source_identity.json').write_bytes((ROOT/'source_identity.json').read_bytes())
        refs=dest/'references';refs.mkdir()
        for name,data in references.items():(refs/name).write_bytes(data)
        temp=dest/'tmp';temp.mkdir();empty=dest/'no_game_inputs';empty.mkdir()
        env={'PATH':'/usr/bin:/bin','LC_ALL':'C','TMPDIR':str(temp),'DOTNET_CLI_HOME':str(dest/'cli'),'DOTNET_SKIP_FIRST_TIME_EXPERIENCE':'1','DOTNET_CLI_TELEMETRY_OPTOUT':'1','DOTNET_NOLOGO':'1','DOTNET_GENERATE_ASPNET_CERTIFICATE':'false','DOTNET_MULTILEVEL_LOOKUP':'0','DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER':'1','MSBUILDDISABLENODEREUSE':'1','NUGET_PACKAGES':str(dest/'packages'),'PYTHONDONTWRITEBYTECODE':'1'}
        component=source/PREFIX/'generic_event_release_v5';nuget=dest/'NuGet.Config';nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
        require(run([dotnet,'--version'],component,env)=='9.0.303','sdk_identity')
        def build(p):
            project=component/p;native=p==PRODUCTION
            flags=['--artifacts-path',str(dest/'artifacts'),'-m:1','-p:HarmonyPath='+str(refs/'0Harmony.dll'),'-p:STS2GameDataDir='+str(refs if native else empty)]
            run([dotnet,'restore',str(project),'--configfile',str(nuget),*flags,'-p:NuGetAudit=false','-p:RestoreBuildInParallel=false'],component,env)
            run([dotnet,'build',str(project),'--no-restore','-c','Release',*flags,'-p:UseSharedCompilation=false','-p:BuildInParallel=false'],component,env)
            assembly=ET.parse(project).getroot().find('.//AssemblyName').text
            out=dest/'artifacts/bin'/project.stem/'release'
            require(not any((out/name).exists() for name in ('sts2.dll','GodotSharp.dll')),'copied_target')
            if native:require(not (out/'0Harmony.dll').exists(),'copied_harmony')
            return out/(assembly+'.dll')
        return source,component,env,build
    source,component,env,build=snapshot('first');outputs={};results={}
    for p in projects:
        outputs[p]=build(p)
        if p.startswith(('runtime_tests/','lifecycle_tests/','operator_tests/','native_tests/','diagnostic_native_tests/')):
            command=[dotnet,str(outputs[p])]
            if p.startswith('operator_tests/'):
                command+=['--fixture-root',str(args.scratch.with_name(args.scratch.name+'-operator-fixture'))]
            results[p]=run(command,component,env)
    results['candidate_trace_comparison']=run([sys.executable,'-B',str(component/'diagnostic_native_tests/compare_traces.py'),'--dotnet',dotnet,'--baseline-dll',str(outputs['diagnostic_native_tests/GenericEventReleaseV5.BaselineTrace.Tests.csproj']),'--candidate-dll',str(outputs['diagnostic_native_tests/GenericEventReleaseV5.Candidates.Tests.csproj'])],component,env)
    lifecycle_native=build('../generic_event_lifecycle_v1/native_tests/GenericEventLifecycleV1.Native.Tests.csproj')
    results['lifecycle_native_with_game_harmony']=run([dotnet,str(lifecycle_native)],component,env)
    verifier=outputs['verifier/Sts2AgentBridge.GenericEventV5.Release.Verifier.csproj']
    policy=component/'policy/generic_event_release_policy.json'
    results['production_verifier']=run([dotnet,str(verifier),'--assembly',str(outputs[PRODUCTION]),'--source-root',str(source),'--policy',str(policy)],component,env)
    # Verify candidate metadata and source policy through the bounded verifier CLI.
    vp='verifier_tests/Sts2AgentBridge.GenericEventV5.Release.Verifier.Tests.csproj'
    results[vp]=run([dotnet,str(outputs[vp]),'--candidate',str(outputs[PRODUCTION]),'--source-root',str(source),'--policy',str(policy)],component,env)
    for folder in ('transport_tests','client_tests','operations'):
        for script in sorted((component/folder).glob('*.py')):
            if not (script.name.startswith('test_') or script.name.endswith('_fixtures.py')):continue
            cmd=[sys.executable,'-B',str(script)]
            if script.name=='verify_clean_install_fixtures.py':cmd+=['--candidate',str(outputs[PRODUCTION])]
            results[str(script.relative_to(component))]=run(cmd,component,env)
    if (component/'source_identity.json').exists():
        results['client_source_validation']=run([sys.executable,'-B','-c',"import runpy; m=runpy.run_path('client/run_live.py'); m['verify_sources'](); print('frozen client sources verified; no credential read')"],component,env)
    results['package']=run([sys.executable,'-B',str(component/'package/package_fixtures.py'),str(outputs[PRODUCTION])],component,env)
    fixture_projects=[p for p in projects if p.startswith('integration/')];require(len(fixture_projects)==1,'socket_fixture_inventory')
    results['socket_composition']=run([sys.executable,'-B',str(component/'integration/test_generic_event_socket_composition.py'),'--dotnet',dotnet,'--fixture',str(outputs[fixture_projects[0]])],component,env)
    _,_,_,again=snapshot('second');first=outputs[PRODUCTION].read_bytes();require(first==again(PRODUCTION).read_bytes(),'production_reproducibility')
    result=dict(schema_version=1,status='passed',source_inventory_sha256=inventory,contract_sha256=contract,frozen_predecessor_count=len(inventories),frozen_source_inventories=inventories,tests=results,production={'bytes':len(first),'sha256':sha(first),'executed':False},game_harmony={'bytes':HARMONY_BYTES,'sha256':HARMONY_SHA,'executed_in_inert_fixtures':True},target_game_assemblies_executed=False,live_campaign_started=False)
    (args.scratch/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
