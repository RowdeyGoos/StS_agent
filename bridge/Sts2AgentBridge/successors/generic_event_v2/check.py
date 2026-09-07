#!/usr/bin/env python3
"""Build disposable snapshots, run inert fixtures and compile (never run) target adapter."""
from __future__ import annotations
import argparse
import hashlib
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).absolute().parent
PREFIX = 'bridge/Sts2AgentBridge/successors/'
PREVIOUS_SHA = '61e80184e06c064cf573ea2f88e73f690073cec384af8ae4633f1f9c98e739ef'
PREVIOUS_MANIFEST = '93bb01fcbad636647994e2ad3459aec260a98d971e1f4be102157273b9f6a2f4'
PREVIOUS_INVENTORY = '1771c317901b99447ed5314c054e6d4abccde597652da28d322ff49211958f36'
PREVIOUS_CONTRACT = '8cc1c1c9fd4ae6d8e4a12fab5dccd33f4c8ffb79648c28eada833dc1c1b7e9f4'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, code):
    if not value:
        raise ValueError(code)


def sources():
    path = ROOT.parent / 'generic_event_v1/check.py'
    require(not path.is_symlink(), 'predecessor_link')
    manifest = ROOT.parent / 'generic_event_v1/source_identity.json'
    require(not manifest.is_symlink() and sha(manifest.read_bytes()) == PREVIOUS_MANIFEST, 'predecessor_manifest')
    data = path.read_bytes()
    require(sha(data) == PREVIOUS_SHA, 'predecessor_checker')
    previous = types.ModuleType('frozen_generic_predecessor')
    previous.__file__ = str(path)
    exec(compile(data, str(path), 'exec'), previous.__dict__)
    helper, boot, inputs, predecessor, inventories, prior_inventory, prior_contract = previous.sources()
    require(prior_inventory == PREVIOUS_INVENTORY and prior_contract == PREVIOUS_CONTRACT, 'predecessor_identity')
    inventories = dict(inventories, generic_event_v1=prior_inventory)
    require(len(inventories) == 15, 'predecessor_count')
    inputs = dict(inputs)
    own = {}
    helper.reject_links(ROOT)
    for path in sorted(ROOT.rglob('*')):
        helper.reject_links(path)
        relative = path.relative_to(ROOT)
        require(not {'obj', 'bin', '__pycache__'}.intersection(relative.parts), 'source_outputs')
        if path.is_file() and str(relative) != 'source_identity.json':
            own[relative.as_posix()] = helper.read_regular(path)
    inventory = sha(''.join(sha(data) + '  ' + name + '\n' for name, data in sorted(own.items())).encode('ascii'))
    contract_path = ROOT.parents[3] / 'docs/PHASE_1_GENERIC_EVENT_V2_CONTRACT.md'
    helper.reject_links(contract_path)
    contract_hash = sha(helper.read_regular(contract_path))
    identity = ROOT / 'source_identity.json'
    if identity.exists():
        expected = json.loads(identity.read_bytes())
        require(expected == {'schema_version': 1, 'component': 'generic_event_v2',
            'contract_sha256': contract_hash, 'inventory_sha256': inventory, 'files': {name: sha(data) for name, data in own.items()}}, 'source_identity')
    inputs.update({PREFIX + 'generic_event_v2/' + name: data for name, data in own.items()})
    derivation = json.loads(own['native/derivation.json'])
    expected_derived = {PREFIX + 'generic_event_v2/' + name.replace('GenericEventV1', 'GenericEventV2')
                        for name in predecessor if name != 'native/derivation.json'}
    require(expected_derived.issubset({row['target'] for row in derivation['derived']}), 'derivation_inventory')
    require(len({row['target'] for row in derivation['derived']}) == len(derivation['derived']), 'duplicate_derivation')
    for row in derivation['derived']:
        before, after = inputs[row['source']], inputs[row['target']]
        require(sha(before) == row['source_sha256'] and sha(after) == row['target_sha256'], 'derivation_identity')
        delta = ''.join(difflib.unified_diff(before.decode().splitlines(keepends=True), after.decode().splitlines(keepends=True), fromfile=row['source'], tofile=row['target']))
        require(delta == row['unified_diff'], 'derivation_delta')
    for row in derivation['reused']:
        require(sha(inputs[row['source']]) == row['sha256'], 'reused_identity')
    return helper, boot, inputs, own, inventories, inventory, contract_hash


def closure(inputs, project, native):
    pending = [project]
    visited = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        require(current in inputs, 'missing_project')
        tree = ET.fromstring(inputs[current])
        require(tree.find('.//EnableDefaultCompileItems').text == 'false', 'implicit_compile')
        for node in tree.iter():
            require(node.tag not in ('PackageReference', 'Import', 'Exec', 'UsingTask'), 'dynamic_build')
            if node.tag in ('Compile', 'ProjectReference'):
                value = node.attrib['Include']
                require(value and not any(c in value for c in '*?$\\') and not Path(value).is_absolute(), 'dynamic_input')
                target = os.path.normpath(str(Path(current).parent / value))
                require(target in inputs and not target.startswith('../'), 'input_boundary')
                if node.tag == 'ProjectReference':
                    pending.append(target)
            if node.tag == 'Reference':
                name = node.attrib.get('Include')
                require(name == '0Harmony' or (native and name in ('sts2', 'GodotSharp')), 'reference_boundary')
                hint = node.find('HintPath')
                require(hint is not None and hint.text in (
                    '$(HarmonyPath)', '$(STS2GameDataDir)/sts2.dll', '$(STS2GameDataDir)/GodotSharp.dll'), 'reference_path')
    return visited


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dotnet', type=Path, required=True)
    parser.add_argument('--game-data-dir', type=Path, required=True)
    parser.add_argument('--harmony-package', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    helper, boot, inputs, own, inventories, inventory, contract_hash = sources()
    require(args.scratch.parent == Path('/private/tmp'), 'scratch_boundary')
    helper.create_scratch(args.scratch)
    dependency = json.loads(own['dependency.json'])
    helper.reject_links(args.harmony_package)
    require(args.harmony_package.is_file() and args.harmony_package.stat().st_size <= 20_000_000, 'package_size')
    package = args.harmony_package.read_bytes()
    require(sha(package) == dependency['package_sha256'], 'package_identity')
    with zipfile.ZipFile(args.harmony_package) as archive:
        harmony = archive.read(dependency['member'])
    require(len(harmony) == dependency['assembly_bytes'] and sha(harmony) == dependency['assembly_sha256'], 'harmony_identity')
    helper.reject_links(args.game_data_dir)
    references = {name: boot.pinned_reference(helper, args.game_data_dir / name, size, digest)
                  for name, (size, digest) in boot.REFERENCES.items()}
    projects = sorted(name for name in own if name.endswith('.csproj'))
    require(set(projects) == {
        'core/GenericEventV2.Core.csproj', 'native/GenericEventV2.Native.csproj',
        'native_tests/GenericEventV2.Native.Tests.csproj', 'wire/GenericEventV2.Wire.csproj',
        'wire_tests/Sts2AgentBridge.GenericEventV2.WireTests.csproj',
        'integration/Sts2AgentBridge.GenericEventV2.Integration.csproj',
        'integration/GenericEventV2.Native.Integration.csproj'}, 'project_inventory')
    require({'host_tests/test_generic_event_host.py', 'host_tests/test_generic_event_removal_host.py', 'integration_tests/test_generic_event_integration.py'}.issubset(own), 'required_test_inventory')
    for project in projects:
        closure(inputs, PREFIX + 'generic_event_v2/' + project, project.startswith('native/'))
    dotnet = str(args.dotnet.resolve(strict=True))
    log_number = 0

    def run(command, cwd, env):
        nonlocal log_number
        log_number += 1
        result = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False)
        (args.scratch / f'log-{log_number:03}.txt').write_bytes(result.stdout)
        require(result.returncode == 0, f'command_failed_log_{log_number:03}')
        return result.stdout.decode('utf-8', errors='strict')

    def snapshot(name):
        destination = args.scratch / name
        source = destination / 'source'
        for relative, data in inputs.items():
            p = source / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        refs = destination / 'references'
        refs.mkdir()
        for filename, data in references.items():
            (refs / filename).write_bytes(data)
        harmony_path = destination / '0Harmony.dll'
        harmony_path.write_bytes(harmony)
        tmp = destination / 'tmp'
        tmp.mkdir()
        env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'TMPDIR': str(tmp),
            'DOTNET_CLI_HOME': str(destination / 'cli'), 'DOTNET_SKIP_FIRST_TIME_EXPERIENCE': '1',
            'DOTNET_CLI_TELEMETRY_OPTOUT': '1', 'DOTNET_NOLOGO': '1',
            'DOTNET_GENERATE_ASPNET_CERTIFICATE': 'false', 'DOTNET_MULTILEVEL_LOOKUP': '0',
            'DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER': '1', 'MSBUILDDISABLENODEREUSE': '1',
            'NUGET_PACKAGES': str(destination / 'packages'), 'PYTHONDONTWRITEBYTECODE': '1'}
        component = source / PREFIX / 'generic_event_v2'
        nuget = destination / 'NuGet.Config'
        nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
        require(run([dotnet, '--version'], component, env).strip() == '9.0.303', 'sdk_identity')

        def build(relative):
            project = component / relative
            native = relative.startswith('native/')
            flags = ['--artifacts-path', str(destination / 'artifacts'), '-m:1',
                '-p:HarmonyPath=' + str(harmony_path),
                '-p:STS2GameDataDir=' + str(refs if native else destination / 'no_game_inputs')]
            run([dotnet, 'restore', str(project), '--configfile', str(nuget), *flags,
                '-p:NuGetAudit=false', '-p:RestoreBuildInParallel=false'], component, env)
            run([dotnet, 'build', str(project), '--no-restore', '-c', 'Release', *flags,
                '-p:UseSharedCompilation=false', '-p:BuildInParallel=false'], component, env)
            tree = ET.fromstring(own[relative])
            assembly = tree.find('.//AssemblyName').text
            output = destination / 'artifacts/bin' / project.stem / 'release'
            require(not any((output / n).exists() for n in ('sts2.dll', 'GodotSharp.dll')), 'copied_target')
            return output / (assembly + '.dll')
        return component, env, build

    component, env, build = snapshot('first')
    outputs = {}
    test_results = {}
    for project in projects:
        outputs[project] = build(project)
        if project.startswith(('core_tests/', 'native_tests/', 'wire_tests/')):
            output = run([dotnet, str(outputs[project])], component, env)
            test_results[project] = output.strip()
    for script in sorted((component / 'host_tests').glob('test_*.py')):
        test_results[script.name] = run([sys.executable, '-B', str(script)], component, env).strip()
    integration = [p for p in projects if p.startswith('integration/')]
    require(len(integration) == 2, 'integration_project')
    for script in sorted((component / 'integration_tests').glob('test_*.py')):
        test_results[script.name] = run([sys.executable, '-B', str(script), '--dotnet', dotnet,
            '--fixture', str(outputs['integration/Sts2AgentBridge.GenericEventV2.Integration.csproj']),
            '--native-fixture', str(outputs['integration/GenericEventV2.Native.Integration.csproj']), '--host', str(component / 'host/generic_event_host.py')], component, env).strip()
    native_projects = [p for p in projects if p.startswith('native/')]
    require(len(native_projects) == 1, 'native_project')
    _, _, build_again = snapshot('second')
    native_outputs = {}
    for project in native_projects:
        first = outputs[project].read_bytes()
        require(first == build_again(project).read_bytes(), 'native_reproducibility')
        native_outputs[project] = {'bytes': len(first), 'sha256': sha(first), 'executed': False}
    result = {'schema_version': 1, 'status': 'passed', 'source_inventory_sha256': inventory, 'contract_sha256': contract_hash,
        'frozen_predecessor_count': len(inventories), 'frozen_source_inventories': inventories,
        'tests': test_results, 'native_compilation': native_outputs,
        'harmony_assembly_sha256': sha(harmony), 'target_assemblies_executed': False,
        'release_ready': False, 'live_campaign_started': False}
    (args.scratch / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
