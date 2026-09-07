#!/usr/bin/env python3
"""Offline lifecycle correction gate; target assemblies compile only."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
import xml.etree.ElementTree as ET

ROOT = Path(__file__).absolute().parent
PREFIX = 'bridge/Sts2AgentBridge/successors/'
PREVIOUS_CHECK = 'df8cef76dab6537ecbaf3680d213ba43149e94e70b0b0b76d206bfa80644a294'
PREVIOUS_MANIFEST = '82202f06bfc0f12abcf6aa44bde435e95bb157e830e3365b6e3d094e72b7d282'
PREVIOUS_INVENTORY = 'cc3f4bc96d873b76f6835025d6c8bd81d1f55166b8b859cfed046e8eb163e207'
PRODUCTION = 'native/GenericEventLifecycleV1.Native.csproj'
TESTS = 'native_tests/GenericEventLifecycleV1.Native.Tests.csproj'
BASELINE = 'native_tests/GenericEventLifecycleV1.Baseline.Tests.csproj'
INTEGRATION = 'integration/GenericEventLifecycleV1.Native.Integration.csproj'
REPLACEMENTS = {'native/'+name+'.cs' for name in (
    'GenericEventV3Binding', 'GenericEventV3CardAdapter',
    'GenericEventV3RemovalAdapter', 'GenericEventV3RewardAdapter')}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, code):
    if not value:
        raise ValueError(code)


def sources():
    path = ROOT.parent/'generic_event_release_v1/check.py'
    require(not path.is_symlink() and sha(path.read_bytes()) == PREVIOUS_CHECK, 'predecessor_checker')
    manifest = path.parent/'source_identity.json'
    require(not manifest.is_symlink() and sha(manifest.read_bytes()) == PREVIOUS_MANIFEST, 'predecessor_manifest')
    previous = types.ModuleType('verified_lifecycle_predecessor')
    previous.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), previous.__dict__)
    helper, boot, inputs, _, inventories, prior, _ = previous.sources()
    require(prior == PREVIOUS_INVENTORY, 'predecessor_inventory')
    inventories = dict(inventories, generic_event_release_v1=prior)
    require(len(inventories) == 18, 'predecessor_count')
    helper.reject_links(ROOT)
    own = {}
    for path in sorted(ROOT.rglob('*')):
        helper.reject_links(path)
        relative = path.relative_to(ROOT)
        require(not {'bin', 'obj', '__pycache__'}.intersection(relative.parts), 'source_outputs')
        if path.is_file() and relative.as_posix() != 'source_identity.json':
            own[relative.as_posix()] = helper.read_regular(path)
    inventory = sha(''.join(sha(data)+'  '+name+'\n' for name, data in sorted(own.items())).encode('ascii'))
    contract = ROOT.parents[3]/'docs/PHASE_1_GENERIC_EVENT_LIFECYCLE_V1_CONTRACT.md'
    helper.reject_links(contract)
    contract_hash = sha(helper.read_regular(contract))
    identity = ROOT/'source_identity.json'
    if identity.exists():
        require(json.loads(helper.read_regular(identity)) == dict(schema_version=1,
            component='generic_event_lifecycle_v1', contract_sha256=contract_hash,
            inventory_sha256=inventory, files={name:sha(data) for name,data in own.items()}), 'source_identity')
    inputs = dict(inputs)
    inputs.update({PREFIX+'generic_event_lifecycle_v1/'+name:data for name,data in own.items()})
    derivation = json.loads(own['derivation.json'])
    require(derivation['schema_version'] == 1 and len(derivation['derived']) == 12, 'derivation_schema')
    require(len({r['target'] for r in derivation['derived']}) == 12, 'derivation_duplicates')
    for row in derivation['derived']:
        require(row['source'] in inputs and row['target'] in inputs, 'derivation_boundary')
        before, after = inputs[row['source']], inputs[row['target']]
        require(sha(before) == row['source_sha256'] and sha(after) == row['target_sha256'], 'derivation_identity')
        delta = ''.join(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True),
            fromfile=row['source'], tofile=row['target']))
        require(delta == row['unified_diff'], 'derivation_delta')
    return previous, helper, boot, inputs, own, inventories, inventory, contract_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dotnet', type=Path, required=True)
    parser.add_argument('--game-data-dir', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    require(sys.version_info >= (3,10), 'python_310')
    previous, helper, boot, inputs, own, inventories, inventory, contract = sources()
    require(args.scratch.parent == Path('/private/tmp'), 'scratch_boundary')
    helper.create_scratch(args.scratch)
    helper.reject_links(args.game_data_dir)
    references = {name:boot.pinned_reference(helper,args.game_data_dir/name,size,digest)
        for name,(size,digest) in boot.REFERENCES.items()}
    references['0Harmony.dll'] = boot.pinned_reference(helper,args.game_data_dir/'0Harmony.dll',
        previous.HARMONY_BYTES,previous.HARMONY_SHA)
    projects = sorted(name for name in own if name.endswith('.csproj'))
    require(set(projects) == {PRODUCTION, TESTS, BASELINE, INTEGRATION}, 'project_inventory')
    new_prefix = PREFIX+'generic_event_lifecycle_v1/'
    old_prefix = PREFIX+'generic_event_v3/'
    compiled = set()
    for project in projects:
        closure = previous.closure(inputs, new_prefix+project, project == PRODUCTION)
        expected = {old_prefix+p for p in REPLACEMENTS} if project == BASELINE else {new_prefix+p for p in REPLACEMENTS}
        excluded = {new_prefix+p for p in REPLACEMENTS} if project == BASELINE else {old_prefix+p for p in REPLACEMENTS}
        require(expected.issubset(closure) and not excluded.intersection(closure), 'native_replacement_closure')
        compiled.update(closure)
    require({new_prefix+p for p in own if p.endswith('.cs')}.issubset(compiled), 'uncompiled_source')
    dotnet = str(args.dotnet.resolve(strict=True))
    logs = 0

    def run(command, cwd, env):
        nonlocal logs
        logs += 1
        result = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=240, check=False)
        (args.scratch/f'log-{logs:03}.txt').write_bytes(result.stdout)
        require(result.returncode == 0, f'command_failed_log_{logs:03}')
        return result.stdout.decode().strip()

    def snapshot(label):
        dest = args.scratch/label
        source = dest/'source'
        for name,data in inputs.items():
            p = source/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        refs = dest/'references'
        refs.mkdir()
        for name,data in references.items():
            (refs/name).write_bytes(data)
        temp = dest/'tmp'
        temp.mkdir()
        empty = dest/'no_game_inputs'
        empty.mkdir()
        env = {'PATH':'/usr/bin:/bin','LC_ALL':'C','TMPDIR':str(temp),
            'DOTNET_CLI_HOME':str(dest/'cli'),'DOTNET_SKIP_FIRST_TIME_EXPERIENCE':'1',
            'DOTNET_CLI_TELEMETRY_OPTOUT':'1','DOTNET_NOLOGO':'1',
            'DOTNET_GENERATE_ASPNET_CERTIFICATE':'false','DOTNET_MULTILEVEL_LOOKUP':'0',
            'DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER':'1','MSBUILDDISABLENODEREUSE':'1',
            'NUGET_PACKAGES':str(dest/'packages'),'PYTHONDONTWRITEBYTECODE':'1'}
        component = source/new_prefix
        nuget = dest/'NuGet.Config'
        nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
        require(run([dotnet,'--version'],component,env) == '9.0.303', 'sdk_identity')

        def build(relative):
            project = component/relative
            flags = ['--artifacts-path',str(dest/'artifacts'),'-m:1',
                '-p:HarmonyPath='+str(refs/'0Harmony.dll'),
                '-p:STS2GameDataDir='+str(refs if relative == PRODUCTION else empty)]
            run([dotnet,'restore',str(project),'--configfile',str(nuget),*flags,
                '-p:NuGetAudit=false','-p:RestoreBuildInParallel=false'],component,env)
            run([dotnet,'build',str(project),'--no-restore','-c','Release',*flags,
                '-p:UseSharedCompilation=false','-p:BuildInParallel=false'],component,env)
            assembly = ET.parse(project).getroot().find('.//AssemblyName').text
            output = dest/'artifacts/bin'/project.stem/'release'
            require(not any((output/name).exists() for name in ('sts2.dll','GodotSharp.dll')), 'copied_target')
            if relative == PRODUCTION:
                require(not (output/'0Harmony.dll').exists(), 'copied_harmony')
            return output/(assembly+'.dll')
        return component, env, build

    component, env, build = snapshot('first')
    outputs = {p:build(p) for p in projects}
    results = {'baseline':run([dotnet,str(outputs[BASELINE]),'--baseline'],component,env),
        'native':run([dotnet,str(outputs[TESTS])],component,env)}
    inert = build('../generic_event_v3/integration/Sts2AgentBridge.GenericEventV3.Integration.csproj')
    previous_root = component.parent/'generic_event_v3'
    results['native_wire_python'] = run([sys.executable,'-B',
        str(previous_root/'integration_tests/test_generic_event_integration.py'),
        '--dotnet',dotnet,'--fixture',str(inert),'--native-fixture',str(outputs[INTEGRATION]),
        '--host',str(previous_root/'host/generic_event_host.py')],component,env)
    _, _, again = snapshot('second')
    first = outputs[PRODUCTION].read_bytes()
    require(first == again(PRODUCTION).read_bytes(), 'native_reproducibility')
    result = dict(schema_version=1,status='passed',source_inventory_sha256=inventory,
        contract_sha256=contract,frozen_predecessor_count=len(inventories),
        frozen_source_inventories=inventories,tests=results,
        native_compilation=dict(bytes=len(first),sha256=sha(first),executed=False),
        harmony_assembly_sha256=previous.HARMONY_SHA,target_assemblies_executed=False,
        release_ready=False,live_campaign_started=False)
    (args.scratch/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main()
