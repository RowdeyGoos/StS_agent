#!/usr/bin/env python3
"""Isolated generic event release gate; no installation or target-game execution."""
from __future__ import annotations
import argparse,copy,difflib,hashlib,json,os,stat,subprocess,sys,types
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).absolute().parent
PREFIX='bridge/Sts2AgentBridge/successors/'
PREVIOUS_CHECK='db501e62582fb3f512166729f5a588e7f69b3b6021bff6430a7c1dbf9742170f'
PREVIOUS_MANIFEST='a937d52c5803e1275f13f45307f7c8477cb7209115d477d30845bc015c23ede5'
PREVIOUS_INVENTORY='071fca6e4badb7a1f09948f780817cb904cff1c4a460707e3c8bf1942c186363'
HARMONY_BYTES=2328064
HARMONY_SHA='ef1898322c9f5c86dc1b0758b272a9c440823b4a41ca9a0b82a3aa6b3d206387'
PRODUCTION='production/Sts2AgentBridgeGenericEventV8.csproj'
def sha(data):return hashlib.sha256(data).hexdigest()
def require(value,code):
    if not value:raise ValueError(code)
def read_own_source(path):
    # The larger G7 policy/derivation are repository metadata, never target inputs.
    # Frozen predecessors retain their original reader and one-MiB boundary.
    require(path.parent==ROOT or ROOT in path.parents,'own_source_boundary')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and 0<=before.st_size<=4*1024*1024,'own_source_shape')
        data=bytearray()
        while len(data)<before.st_size:
            block=os.read(fd,min(65536,before.st_size-len(data)))
            require(bool(block),'own_source_truncated');data.extend(block)
        identity=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        require(not os.read(fd,1) and identity(before)==identity(os.fstat(fd))==identity(path.lstat()),'own_source_changed')
        return bytes(data)
    finally:os.close(fd)

def sources():
    path=ROOT.parent/'generic_event_release_v7/check.py';require(not path.is_symlink(),'predecessor_link')
    require(sha(path.read_bytes())==PREVIOUS_CHECK,'predecessor_checker')
    manifest=path.parent/'source_identity.json';require(not manifest.is_symlink() and sha(manifest.read_bytes())==PREVIOUS_MANIFEST,'predecessor_manifest')
    previous=types.ModuleType('verified_generic_predecessor');previous.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),previous.__dict__)
    helper,boot,inputs,_,inventories,prior,_=previous.sources()
    require(prior==PREVIOUS_INVENTORY,'predecessor_inventory')
    inventories=dict(inventories,generic_event_release_v7=prior);require(len(inventories)==29,'predecessor_count')
    own={};helper.reject_links(ROOT)
    for path in sorted(ROOT.rglob('*')):
        helper.reject_links(path);relative=path.relative_to(ROOT)
        require(not {'bin','obj','__pycache__'}.intersection(relative.parts),'source_outputs')
        if path.is_file() and relative.as_posix()!='source_identity.json':own[relative.as_posix()]=read_own_source(path)
    inventory=sha(''.join(sha(data)+'  '+name+'\n' for name,data in sorted(own.items())).encode('ascii'))
    contract=ROOT.parents[3]/'docs/PHASE_1_GENERIC_EVENT_RELEASE_V8_CONTRACT.md';helper.reject_links(contract);contract_hash=sha(helper.read_regular(contract))
    identity=ROOT/'source_identity.json'
    if identity.exists():
        require(json.loads(identity.read_bytes())==dict(schema_version=1,component='generic_event_release_v8',contract_sha256=contract_hash,inventory_sha256=inventory,files={name:sha(data) for name,data in own.items()}),'source_identity')
    inputs=dict(inputs);inputs.update({PREFIX+'generic_event_release_v8/'+name:data for name,data in own.items()})
    derivation=json.loads(own['derivation.json']);require(derivation['schema_version']==2,'derivation_schema')
    require(len({r['target'] for r in derivation['derived']})==len(derivation['derived']),'duplicate_derivation')
    for row in derivation['derived']:
        require(row['source'] in inputs and row['target'] in inputs,'derivation_boundary')
        before,after=inputs[row['source']],inputs[row['target']]
        require(sha(before)==row['source_sha256'] and sha(after)==row['target_sha256'],'derivation_identity')
        require(''.join(difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),fromfile=row['source'],tofile=row['target']))==row['unified_diff'],'derivation_delta')
    for row in derivation['reused']:
        require(row['source'] in inputs and sha(inputs[row['source']])==row['sha256'],'reused_identity')
    for row in derivation['created']:
        require(row['target'] in inputs and sha(inputs[row['target']])==row['sha256'],'created_identity')
    validate_provenance_closure(inputs,own,derivation)
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

def validate_provenance_closure(inputs,own,derivation):
    own_prefix=PREFIX+'generic_event_release_v8/'
    expected_created={own_prefix+name for name in ('gameplay_tests/OffscreenFixtures.cs','verifier/GenericEventOffscreenSurface.cs','integration/OffscreenSocketFixture.cs')}
    created=[row['target'] for row in derivation['created']]
    require(len(created)==len(set(created)) and set(created)==expected_created,'created_complete_closure')
    expected_derived={own_prefix+name for name in own if name not in ('README.md','derivation.json')} - expected_created
    derived=[row['target'] for row in derivation['derived']]
    require(len(derived)==len(set(derived)) and set(derived)==expected_derived,'derived_complete_closure')
    expected_reused=set()
    for name in own:
        if name.endswith('.csproj'):
            expected_reused.update(closure(inputs,own_prefix+name,name==PRODUCTION))
    expected_reused.update(PREFIX+name for name in (
        'generic_event_v7/host/generic_event_host.py','generic_event_v7/host/card_transform_host.py',
        'card_selection_v1/host/card_selection_host.py','item_wire_v1/host/item_host.py'))
    expected_reused={name for name in expected_reused if not name.startswith(own_prefix)}
    reused=[row['source'] for row in derivation['reused']]
    require(len(reused)==len(set(reused)) and set(reused)==expected_reused,'reused_complete_closure')

def provenance_mutations(inputs,own):
    original=json.loads(own['derivation.json']);count=0
    for key,code in (('derived','derived_complete_closure'),('reused','reused_complete_closure'),('created','created_complete_closure')):
        for duplicate in (False,True):
            changed=copy.deepcopy(original)
            if duplicate:changed[key].append(changed[key][0])
            else:changed[key].pop()
            try:validate_provenance_closure(inputs,own,changed)
            except ValueError as error:require(str(error)==code,'provenance_mutation_rejection')
            else:raise ValueError('provenance_mutation_accepted')
            count+=1
    return dict(status='passed',mutation_cases=count)

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
    require(set(projects)=={PRODUCTION,'runtime/Sts2AgentBridge.GenericEventV8.Transport.csproj',
        'runtime_tests/GenericEventReleaseV8.RuntimeTests.csproj','integration/GenericEventReleaseV8.SocketFixture.csproj',
        'operator_tests/Sts2AgentBridge.GenericEventV8.Operator.Tests.csproj',
        'lifecycle_tests/Sts2AgentBridge.GenericEventV8.Bootstrap.Tests.csproj',
        'native_tests/Sts2AgentBridge.GenericEventV8.Native.Tests.csproj',
        'verifier/Sts2AgentBridge.GenericEventV8.Release.Verifier.csproj',
        'verifier_tests/Sts2AgentBridge.GenericEventV8.Release.Verifier.Tests.csproj','gameplay_tests/GenericEventReleaseV8.Offscreen.Tests.csproj'},'project_inventory')
    production_sources=closure(inputs,PREFIX+'generic_event_release_v8/'+PRODUCTION,True)
    gameplay=closure(inputs,PREFIX+'generic_event_v7/native/GenericEventV7.Native.csproj',True)|closure(inputs,PREFIX+'generic_event_v7/wire/GenericEventV7.Wire.csproj',False)
    old_adapter=PREFIX+'generic_event_v7/native/GenericEventV7TransformAdapter.cs'
    new_adapter=PREFIX+'generic_event_release_v8/gameplay/GenericEventV7TransformAdapter.cs'
    require(old_adapter not in production_sources and new_adapter in production_sources and (gameplay-{old_adapter}).issubset(production_sources),'exact_g7_adapter_substitution')
    require({p for p in production_sources if p.startswith(PREFIX+'generic_event_release_v8/gameplay/')}=={new_adapter},'only_offscreen_gameplay_replacement')
    require(len(production_sources)==56,'production_source_count')
    require(not any('/generic_event_v3/' in p or '/generic_event_lifecycle_v1/' in p for p in production_sources),'old_gameplay_excluded')
    frozen_diagnostic={PREFIX+'generic_event_release_v5/runtime/'+name+'.cs' for name in ('GenericEventDiagnosticCode','GenericEventDiagnosticCodec')}
    require(frozen_diagnostic.issubset(production_sources),'frozen_diagnostic_closure')
    for p in production_sources:
        if p.startswith(PREFIX+'generic_event_release_v8/native/'):
            require(Path(p).name in ('ProductionGenericEventRuntimeFactory.cs','PinnedGenericEventHarmonyGuard.cs','GenericEventBootstrapHost.cs','GenericEventBootstrapSupport.cs','GenericEventGodotFrameConnector.cs','GenericEventModEntry.cs'),'no_native_gameplay_replacements')
    native_fixture_sources=closure(inputs,PREFIX+'generic_event_release_v8/native_tests/Sts2AgentBridge.GenericEventV8.Native.Tests.csproj',False)
    require(production_sources.issubset(native_fixture_sources),'production_native_fixture_closure')
    policy_sources=json.loads(own['policy/generic_event_release_policy.json'])['source_files']
    require({row['path'] for row in policy_sources}==production_sources and len(policy_sources)==len(production_sources),'policy_source_closure')
    require(all(sha(inputs[row['path']])==row['sha256'] for row in policy_sources),'policy_source_identity')
    compiled=set()
    for p in projects:compiled.update(closure(inputs,PREFIX+'generic_event_release_v8/'+p,p==PRODUCTION))
    require({PREFIX+'generic_event_release_v8/'+p for p in own if p.endswith('.cs')}.issubset(compiled),'uncompiled_source')
    required={'client_tests/client_fixtures.py','transport_tests/test_generic_event_transport.py','integration/test_generic_event_socket_composition.py','operations/manage_live_campaign_fixtures.py','operations/predecessor_conflict_fixtures.py','package/package_fixtures.py'}
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
        doc=source/'docs/PHASE_1_GENERIC_EVENT_RELEASE_V8_CONTRACT.md';doc.parent.mkdir(exist_ok=True);doc.write_bytes((ROOT.parents[3]/'docs/PHASE_1_GENERIC_EVENT_RELEASE_V8_CONTRACT.md').read_bytes())
        if (ROOT/'source_identity.json').exists():(source/PREFIX/'generic_event_release_v8/source_identity.json').write_bytes((ROOT/'source_identity.json').read_bytes())
        refs=dest/'references';refs.mkdir()
        for name,data in references.items():(refs/name).write_bytes(data)
        temp=dest/'tmp';temp.mkdir();empty=dest/'no_game_inputs';empty.mkdir()
        env={'PATH':'/usr/bin:/bin','LC_ALL':'C','TMPDIR':str(temp),'DOTNET_CLI_HOME':str(dest/'cli'),'DOTNET_SKIP_FIRST_TIME_EXPERIENCE':'1','DOTNET_CLI_TELEMETRY_OPTOUT':'1','DOTNET_NOLOGO':'1','DOTNET_GENERATE_ASPNET_CERTIFICATE':'false','DOTNET_MULTILEVEL_LOOKUP':'0','DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER':'1','MSBUILDDISABLENODEREUSE':'1','NUGET_PACKAGES':str(dest/'packages'),'PYTHONDONTWRITEBYTECODE':'1'}
        component=source/PREFIX/'generic_event_release_v8';nuget=dest/'NuGet.Config';nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
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
    source,component,env,build=snapshot('first');outputs={};results={'source_provenance_mutations':provenance_mutations(inputs,own)}
    g7_scratch=args.scratch.with_name(args.scratch.name+'-g7')
    g7_run=run([sys.executable,'-B',str(ROOT.parent/'generic_event_v7/check.py'),'--dotnet',dotnet,'--game-data-dir',str(args.game_data_dir),'--scratch',str(g7_scratch)],ROOT,env)
    g7=json.loads((g7_scratch/'result.json').read_bytes())
    require(g7['status']=='passed' and g7['source_inventory_sha256']=='1f263d7916cb9bb2cd973cce2e72eb4e21ba04e92ff3554ae7e1e0ca490d66df','frozen_g7_regression')
    results['frozen_g7_regression']=dict(result_sha256=sha((g7_scratch/'result.json').read_bytes()),tests=g7['tests'])
    for p in projects:
        outputs[p]=build(p)
        if p.startswith(('runtime_tests/','lifecycle_tests/','operator_tests/','native_tests/','gameplay_tests/')):
            command=[dotnet,str(outputs[p])]
            if p.startswith('operator_tests/'):
                command+=['--fixture-root',str(args.scratch.with_name(args.scratch.name+'-operator-fixture'))]
            results[p]=run(command,component,env)
    verifier=outputs['verifier/Sts2AgentBridge.GenericEventV8.Release.Verifier.csproj']
    policy=component/'policy/generic_event_release_policy.json'
    results['production_verifier']=run([dotnet,str(verifier),'--assembly',str(outputs[PRODUCTION]),'--source-root',str(source),'--policy',str(policy)],component,env)
    # Verify candidate metadata and source policy through the bounded verifier CLI.
    vp='verifier_tests/Sts2AgentBridge.GenericEventV8.Release.Verifier.Tests.csproj'
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
