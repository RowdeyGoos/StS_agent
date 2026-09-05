#!/usr/bin/env python3
"""Offline Item V1 release gate; never installs, starts or contacts the game."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import types
import xml.etree.ElementTree as ET

ROOT = Path(__file__).absolute().parent
CONTRACT = '9d7d25840fb8910448bd0f8215f4eabdc081c8151a96eb3649f4db3025103b34'
BOOT_CHECK = '483fbf32bd45637e190ccfbca9220f6938e4acdc0b8a00ca9a4c1ff265c2b0d7'
BOOT_MANIFEST = '77aa278f7c7c2cba2523c5c4d474fb2f45eb76dfa3d1faa7feb914a96e4c47ab'
BOOT_INVENTORY = 'a07c2fc58dad78655629f7cd1686a6b9ad108e996e728e80cf2f999733ab602e'


def fail(code: str):
    raise ValueError(code)


def load_bootstrap():
    path = ROOT.parent / 'item_bootstrap_v1' / 'check.py'
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if stat.S_ISLNK(current.lstat().st_mode): fail('bootstrap_helper_link')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != BOOT_CHECK: fail('bootstrap_helper_identity')
    module=types.ModuleType('verified_bootstrap_checker'); module.__file__=str(path)
    exec(compile(data,str(path),'exec'),module.__dict__)
    return module


def verify_projects(files: dict[str,bytes], bootstrap_props: bytes):
    if files['Directory.Build.props'] != bootstrap_props: fail('release_properties_mismatch')
    projects={name for name in files if name.endswith('.csproj')}
    if projects != {'verifier/Sts2AgentBridge.ItemV1.Release.Verifier.csproj',
                    'verifier_tests/Sts2AgentBridge.ItemV1.Release.Verifier.Tests.csproj'}:
        fail('release_project_inventory')
    for path in sorted(projects):
        tree=ET.fromstring(files[path])
        if tree.tag!='Project' or tree.attrib!={'Sdk':'Microsoft.NET.Sdk'}: fail('project_sdk')
        props={}; sources=[]
        for group in tree:
            if group.attrib: fail('project_condition')
            if group.tag=='PropertyGroup':
                for node in group:
                    if node.attrib or len(node) or node.tag in props: fail('project_property_shape')
                    props[node.tag]=node.text
            elif group.tag=='ItemGroup':
                for node in group:
                    if node.tag!='Compile' or set(node.attrib)-{'Include','Link'} or len(node): fail('project_item')
                    name=node.attrib.get('Include','')
                    if '$' in name or '*' in name or Path(name).is_absolute(): fail('project_dynamic_source')
                    resolved=os.path.normpath(str(Path(path).parent/name))
                    if resolved.startswith('../') or resolved not in files or not resolved.endswith('.cs'): fail('project_source_boundary')
                    sources.append(resolved)
            else: fail('project_structure')
        expected={'TargetFramework':'net9.0','OutputType':'Exe','EnableDefaultCompileItems':'false',
                  'AssemblyName':Path(path).stem}
        if 'RootNamespace' in props: expected['RootNamespace']=('Sts2AgentBridge.ItemV1.Release.Verifier.Tests' if path.startswith('verifier_tests/') else 'Sts2AgentBridge.Verifier')
        if path.startswith('verifier_tests/'):
            expected['DefineConstants']='$(DefineConstants);ITEM_RELEASE_TEST_SEAM'
            expected['StartupObject']='Program'
        if props!=expected or len(sources)!=len(set(sources)): fail('project_properties_or_duplicate_source')
        allowed={name for name in files if name.endswith('.cs') and name.startswith('verifier/')}
        if path.startswith('verifier_tests/'):
            allowed.update(name for name in files if name.endswith('.cs') and name.startswith('verifier_tests/'))
        if set(sources)!=allowed: fail('project_compile_closure')


def run(command,cwd,environment):
    value=subprocess.run(command,cwd=cwd,env=environment,stdin=subprocess.DEVNULL,
                         capture_output=True,text=True,timeout=180)
    if value.returncode: fail('offline_command_failed\n'+value.stdout+value.stderr)
    return value.stdout


def verify_cli_negatives(dotnet, verifier, candidate, source, policy, scratch, snapshot, environment):
    root=scratch/'cli-fixtures'; root.mkdir(mode=0o700)
    arguments=[dotnet,str(verifier),'--assembly',str(candidate),'--source-root',str(source),'--policy',str(policy)]
    count=0
    def reject(command):
        nonlocal count
        output=subprocess.run(command,cwd=snapshot,env=environment,stdin=subprocess.DEVNULL,
                              capture_output=True,text=True,timeout=15)
        try: result=json.loads(output.stdout)
        except Exception: fail('cli_fixture_output')
        if (output.returncode not in {2,3,4} or output.stderr or set(result)!={'schema_version','status','code'} or
                result['schema_version']!=1 or result['status']!='failed' or
                not isinstance(result['code'],str) or not result['code'].replace('_','').isalnum()):
            fail('cli_fixture_rejection')
        count+=1
    bad_policy=root/'policy.json'; bad_policy.write_bytes(b'X'+policy.read_bytes()[1:])
    reject(arguments[:-1]+[str(bad_policy)])
    trailing=root/'trailing.dll'; trailing.write_bytes(candidate.read_bytes()+b'X')
    malformed=root/'malformed.dll'; malformed.write_bytes(b'MZ')
    for path in [trailing,malformed]: reject(arguments[:3]+[str(path)]+arguments[4:])
    reject([dotnet,str(verifier),'--extract-policy',str(candidate)])
    reject(arguments[:3]+['relative.dll']+arguments[4:])
    linked=root/'linked.dll'; linked.symlink_to(candidate)
    reject(arguments[:3]+[str(linked)]+arguments[4:])
    linked_parent=root/'linked-parent'; linked_parent.symlink_to(candidate.parent,target_is_directory=True)
    reject(arguments[:3]+[str(linked_parent/candidate.name)]+arguments[4:])
    cloned=root/'source'
    inputs=json.loads(policy.read_bytes())['source_files']
    for entry in inputs:
        target=cloned/entry['path']; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((source/entry['path']).read_bytes())
    changed=cloned/inputs[0]['path']; original=changed.read_bytes()
    clone_arguments=arguments[:5]+[str(cloned)]+arguments[6:]
    changed.write_bytes(original+b'// mutation\n'); reject(clone_arguments)
    changed.unlink(); reject(clone_arguments)
    changed.symlink_to(source/inputs[0]['path']); reject(clone_arguments)
    return {'schema_version':1,'status':'passed','suite':'item_v1_release_cli','check_count':count}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dotnet',type=Path,required=True)
    parser.add_argument('--game-data-dir',type=Path,required=True)
    parser.add_argument('--scratch',type=Path,required=True)
    args=parser.parse_args()
    if sys.version_info<(3,10): fail('python_310_required')
    boot=load_bootstrap(); helper=boot.load_frozen_helper()
    own,inventory=helper.source_snapshot(ROOT,'item_release_v1',CONTRACT)
    bootstrap,_=helper.source_snapshot(ROOT.parent/'item_bootstrap_v1','item_bootstrap_v1',boot.CONTRACT,BOOT_MANIFEST,BOOT_INVENTORY)
    transport,_=helper.source_snapshot(ROOT.parent/'item_transport_v1','item_transport_v1',boot.TRANSPORT_CONTRACT,boot.TRANSPORT_MANIFEST,boot.TRANSPORT_INVENTORY)
    wire,_=helper.source_snapshot(ROOT.parent/'item_wire_v1','item_wire_v1',helper.WIRE_CONTRACT,helper.WIRE_MANIFEST,helper.WIRE_INVENTORY)
    core,_=helper.source_snapshot(ROOT.parent/'item_v1','item_v1',helper.CORE_CONTRACT,helper.CORE_MANIFEST,helper.CORE_INVENTORY)
    helper.verify_old_inventory(ROOT.parents[3]); boot.verify_pure_projects(bootstrap); boot.verify_project(bootstrap)
    verify_projects(own,bootstrap['Directory.Build.props'])
    game=args.game_data_dir
    if not game.is_absolute() or str(game)!=os.path.normpath(str(game)): fail('reference_root')
    helper.reject_links(game)
    references={name:boot.pinned_reference(helper,game/name,size,digest) for name,(size,digest) in boot.REFERENCES.items()}
    if args.scratch.parent!=Path('/private/tmp'): fail('scratch_boundary')
    helper.create_scratch(args.scratch)
    source=args.scratch/'source'; siblings=source/'bridge'/'Sts2AgentBridge'/'successors'
    for component,files in [('item_release_v1',own),('item_bootstrap_v1',bootstrap),('item_transport_v1',transport),('item_wire_v1',wire),('item_v1',core)]:
        for name,data in files.items():
            destination=siblings/component/name; destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('xb') as output: output.write(data)
    snapshot=siblings/'item_release_v1'
    refs=args.scratch/'references'; refs.mkdir()
    for name,data in references.items():
        with (refs/name).open('xb') as output: output.write(data)
    (args.scratch/'tmp').mkdir(mode=0o700)
    environment={'PATH':'/usr/bin:/bin','LC_ALL':'C','TMPDIR':str(args.scratch/'tmp'),
                 'DOTNET_CLI_HOME':str(args.scratch/'cli'),'DOTNET_SKIP_FIRST_TIME_EXPERIENCE':'1',
                 'DOTNET_CLI_TELEMETRY_OPTOUT':'1','DOTNET_GENERATE_ASPNET_CERTIFICATE':'false',
                 'DOTNET_NOLOGO':'1','DOTNET_MULTILEVEL_LOOKUP':'0','MSBUILDDISABLENODEREUSE':'1',
                 'NUGET_PACKAGES':str(args.scratch/'packages'),'PYTHONDONTWRITEBYTECODE':'1'}
    dotnet=str(args.dotnet.resolve(strict=True))
    if run([dotnet,'--version'],snapshot,environment).strip()!='9.0.303': fail('sdk_mismatch')
    nuget=args.scratch/'NuGet.Config'; nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
    artifacts=args.scratch/'artifacts'
    def build(project):
        common=['--artifacts-path',str(artifacts),'-p:STS2GameDataDir='+str(refs),'-m:1']
        run([dotnet,'restore',str(project),'--configfile',str(nuget),*common,'-p:RestoreBuildInParallel=false','-p:NuGetAudit=false'],snapshot,environment)
        run([dotnet,'build',str(project),'--no-restore','-c','Release',*common,'-p:BuildInParallel=false','-p:UseSharedCompilation=false'],snapshot,environment)
        directory=artifacts/'bin'/project.stem/'release'
        deps=json.loads((directory/(project.stem+'.deps.json')).read_text())
        if project.stem!='Sts2AgentBridgeItemV1' and set(deps['libraries'])!={project.stem+'/1.0.0'}: fail('tool_dependency')
        return directory/(project.stem+'.dll')
    inspector=build(siblings/'item_bootstrap_v1'/'production'/'ItemV1.CandidateInspection.csproj')
    verifier=build(snapshot/'verifier'/'Sts2AgentBridge.ItemV1.Release.Verifier.csproj')
    tests=build(snapshot/'verifier_tests'/'Sts2AgentBridge.ItemV1.Release.Verifier.Tests.csproj')
    for dll in [verifier,tests]:
        pure=json.loads(run([dotnet,str(inspector),'--pure',str(dll)],snapshot,environment))
        if pure!={'schema_version':1,'status':'passed','scope':'framework_references_only','assembly_name':dll.stem}: fail('tool_reference')
    candidate=build(siblings/'item_bootstrap_v1'/'production'/'Sts2AgentBridgeItemV1.csproj')
    if set(p.name for p in candidate.parent.iterdir())!={'Sts2AgentBridgeItemV1.dll','Sts2AgentBridgeItemV1.deps.json'}: fail('candidate_outputs')
    policy=snapshot/'policy'/'item_release_policy.json'
    surface=json.loads(run([dotnet,str(verifier),'--assembly',str(candidate),'--source-root',str(source),'--policy',str(policy)],snapshot,environment))
    if surface != {'schema_version':1,'status':'passed','suite':'item_v1_release_surface',
                   'assembly_sha256':'09ea93cd86a4ca502c27357171f7a7efdaf2bcf91a0a3fcffec96ef79745b9f6',
                   'source_projection_sha256':'131404a87a94800c1e9dbda3ef936abf44452befb5f41643b8b392cf6909ba88',
                   'metadata_projection_sha256':'b788963fd45b46eb74578f8a648c75956da3b55be2bac4b2807afc3b4a1748dd',
                   'checked_method_bodies':460}: fail('surface_result')
    cli_negative=verify_cli_negatives(dotnet,verifier,candidate,source,policy,args.scratch,snapshot,environment)
    negative=json.loads(run([dotnet,str(tests),'--candidate',str(candidate),'--source-root',str(source),'--policy',str(policy)],snapshot,environment))
    if negative!={'schema_version':1,'status':'passed','suite':'item_v1_release_verifier','check_count':31}: fail('surface_fixture_result')
    python=[sys.executable,'-B','-I','-S']
    help_output=run([*python,str(snapshot/'operations'/'verify_clean_install.py'),'--help'],snapshot,environment)
    if not all(flag in help_output for flag in ['--install-root','--target-manifest','--mode','--package']): fail('base_verifier_cli_startup')
    summaries={}
    expected_fixtures={
        'client':{'schema_version':1,'status':'passed','suite':'item_v1_client','check_count':11},
        'package':{'schema_version':1,'status':'passed','suite':'item_v1_package','check_count':5,'mutation_cases':9},
    }
    for name,command in [
        ('client',[*python,str(snapshot/'client_tests'/'client_fixtures.py')]),
        ('package',[*python,str(snapshot/'package'/'package_fixtures.py'),str(candidate)]),
        ('operations',[*python,str(snapshot/'operations'/'manage_live_campaign_fixtures.py')]),
        ('runtime',[*python,str(snapshot/'operations'/'check_live_runtime_fixtures.py')]),
    ]:
        summaries[name]=json.loads(run(command,snapshot,environment))
        if summaries[name].get('status')!='passed': fail('fixture_result')
        if name in {'operations','runtime'}:
            suite,count=('manage_live_campaign_fixtures',38) if name=='operations' else ('check_live_runtime_fixtures',17)
            expected={'schema_version':1,'status':'passed','suite':suite,'check_count':count,'checks':summaries[name].get('checks')}
            checks=expected['checks']
            expected_checks=(
                'production_bindings csprng_shape_freshness_and_zeroing bounded_deny_only_acl item_scope_and_legacy_rejection client_metadata_validation_api full_lifecycle_created_mods full_lifecycle_existing_mods production_identity_and_artifact_root cli_surface owner_rejection mode_rejection live_parent_mode_rejection granting_acl_rejection symlink_rejection preexisting_rejection corrupt_artifact_rejection prepublish_rollback_scope install_partial_retention install_changed_target_retention hardlink_rejection generated_mode_rejection extra_child_rejection quarantine_state_write_rejection partial_move_retention state_generation_rejection state_inode_replacement_rejection state_hash_lineage_rejection interrupt_sanitization exclusive_rename phase_and_reinvocation fault_checkpoint_catalog install_fault_retention quarantine_fault_retention purge_created_fault_retention purge_existing_fault_retention dynamic_mutation_guards purge_extra_retention sanitized_output'
                if name=='operations' else
                'joint_require_stopped exact_require_running ambiguous_running_rejected base_port_closed_sample bounded_joint_wait stopped_rejects_all_running base_sample_rejects_open_port restart_during_release_rejected process_probe_duration_bounded port_probe_duration_bounded sleep_capped_to_deadline identity_binding executable_metadata pgrep_boundary live_loopback_boundary argument_closure interrupt_sanitization'
            ).split()
            if checks!=expected_checks: fail('operation_fixture_check_inventory')
            if (summaries[name]!=expected or not isinstance(checks,list) or len(checks)!=count or
                    len(set(checks))!=count or not all(isinstance(item,str) for item in checks)): fail('operation_fixture_exact_result')
        if name in expected_fixtures and summaries[name]!=expected_fixtures[name]: fail('fixture_exact_result')
    package=types.ModuleType('verified_release_package'); package.__file__=str(snapshot/'package'/'release_package.py')
    exec(compile(own['package/release_package.py'],package.__file__,'exec'),package.__dict__)
    files=package.canonical_files(candidate.read_bytes())
    expected_artifacts={
        'Sts2AgentBridgeItemV1.dll':(95232,'09ea93cd86a4ca502c27357171f7a7efdaf2bcf91a0a3fcffec96ef79745b9f6'),
        'Sts2AgentBridgeItemV1.json':(340,'03163de389a7212c39f18c54ace292b8b105e3c7396bf08c871203f6c33978d4'),
        'Sts2AgentBridgeItemV1-1.0.0.zip':(95936,'349c24fa02da4a11e19fa4dd6a08100b805d9c5dbe84b89cd4e3de120a412beb'),
    }
    if package.IDENTITIES!=expected_artifacts or set(files)!=set(expected_artifacts): fail('package_bindings')
    for name,(size,digest) in expected_artifacts.items():
        if len(files[name])!=size or hashlib.sha256(files[name]).hexdigest()!=digest: fail('package_identity')
    release=args.scratch/'release'; release.mkdir(mode=0o700)
    for name,data in files.items():
        with (release/name).open('xb') as output: output.write(data)
    package.verify_files({name:package.read_regular(release/name,size) for name,(size,_) in package.IDENTITIES.items()})
    result={'schema_version':1,'status':'passed','suite':'item_v1_release','source_inventory_sha256':inventory,
            'surface':surface,'surface_fixtures':negative,'cli_fixtures':cli_negative,'fixtures':summaries,
            'artifacts':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()},
            'installed':False,'live_action_attempted':False}
    (args.scratch/'result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':
    main()
