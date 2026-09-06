#!/usr/bin/env python3
"""Offline event functional gate. No listener, installation or target execution."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import xml.etree.ElementTree as ET

ROOT = Path(__file__).absolute().parent
COMPONENT = 'event_card_operations_v1'
CONTRACT = 'be480799460c5a5799bd9785d21f1c41d6467c912876cd456b271999408dac6e'
PREVIOUS_CHECK = '22400db95f7f9fbae1f133ce6f8e55ab54ad423c6fbe6f9167017907764aa197'
ORCHESTRATOR_MANIFEST = '70136652a0ba6977061f25c4ab31f91c771b2831461b0b83c3788d66ccbdc1c8'
ORCHESTRATOR_INVENTORY = 'd5dbc6ab497ab06d9fd9de3a06e17bde6f0a46207389cb6a4543c34ce3d646e1'
API = '9275a7773f5685e06546300e0e3c8ca4b4651e16d96c75a259c51fde8873b956'
SCHEMA = '22c563ac03aff7ef522ba2f56e09fb22ea586a44beebd491381130c3d7884eec'
PROPS = '2b05edd4dbb4532b1e884c6267bf56c732b49415dc43a23245b3d0c3cc30265f'
PROJECT_HASHES: dict[str, str] = {
    'broker_tests/Sts2AgentBridge.EventCardOperationsV1.Broker.Tests.csproj': '57177cd9230928c058e789d59c12d81dcf3c944400480af78b57682318aba489',
    'core/Sts2AgentBridge.EventCardOperationsV1.Core.csproj': '71dea1ca202cd7b7c6edcf0236e571505557068523241eeedbe9426312e01f76',
    'core_tests/Sts2AgentBridge.EventCardOperationsV1.Core.Tests.csproj': '60c4b48ae0f15d4eec090e95ceb4cdb6266f858268a415acad8a2864534cb1aa',
    'integration/Sts2AgentBridge.EventCardOperationsV1.Integration.csproj': '7723d67efe257016f5b54998d1cf7f2197fc60bf917df4b00a05bd2a298b4b7e',
    'native/Sts2AgentBridge.EventCardOperationsV1.Native.csproj': '1394a47a4e5d78ecd522b515f3e6b048f97a74ddb322073cca1ddd950427ffb7',
    'native_card_tests/Sts2AgentBridge.EventCardOperationsV1.NativeCard.Tests.csproj': '8ded98124b4bd216d97505be469e4256ee80379a0a69ff90c4fb35f622c29d0e',
    'native_tests/Sts2AgentBridge.EventCardOperationsV1.Native.Composition.Tests.csproj': '57eef08d451a560eaf08daba970e0e8e090bc977b7df70c0d06f5a3032c5e927',
    'native_tests/Sts2AgentBridge.EventCardOperationsV1.Native.Factory.Tests.csproj': '98ee40c1ee7c5c12afc4e0f478ac4804cd67fc0e75fd7235c842dd82b4034017',
    'native_tests/Sts2AgentBridge.EventCardOperationsV1.Native.Tests.csproj': '160a483c4dbf0861d8de7d9459abe3ff2373fb3e3c88b54528317344bf7f6ff6',
    'wire/Sts2AgentBridge.EventCardOperationsV1.Wire.csproj': 'f1bf5c2949de064b10fcdc403f67d0baf06667b673243e0a4304c20159f58cd2',
    'wire_tests/Sts2AgentBridge.EventCardOperationsV1.Wire.Tests.csproj': 'cf4220cf43e820481ef101dd50c4a4febfbc96872cc94a29aef9c836a9d6037d',
}
PURE_TESTS: tuple[tuple[str, str, int], ...] = (
    ('item_v1/tests/Sts2AgentBridge.ItemV1.Tests.csproj', 'item_v1_core', 10),
    ('card_selection_v1/tests/Sts2AgentBridge.CardSelectionV1.Core.Tests.csproj', 'card_selection_v1_core', 16),
    ('card_selection_completion_v1/native_tests/Sts2AgentBridge.CardSelectionCompletionV1.Native.Tests.csproj', 'card_selection_completion_v1_native', 87),
    ('event_orchestrator_v1/core_tests/Sts2AgentBridge.EventOrchestratorV1.Core.Tests.csproj', 'event_orchestrator_v1_core', 12),
    ('event_orchestrator_v1/broker_tests/Sts2AgentBridge.EventOrchestratorV1.Broker.Tests.csproj', 'event_orchestrator_v1_brokers', 6),
    ('event_orchestrator_v1/wire_tests/Sts2AgentBridge.EventOrchestratorV1.Wire.Tests.csproj', 'event_orchestrator_v1_wire', 22),
    ('event_orchestrator_v1/native_tests/Sts2AgentBridge.EventOrchestratorV1.Native.Tests.csproj', 'event_orchestrator_v1_native', 10),
    ('event_orchestrator_v1/native_tests/Sts2AgentBridge.EventOrchestratorV1.Native.Factory.Tests.csproj', 'event_orchestrator_v1_native_factories', 3),
    ('event_card_operations_v1/core_tests/Sts2AgentBridge.EventCardOperationsV1.Core.Tests.csproj', 'event_card_operations_v1_core', 19),
    ('event_card_operations_v1/broker_tests/Sts2AgentBridge.EventCardOperationsV1.Broker.Tests.csproj', 'event_card_operations_v1_brokers', 12),
    ('event_card_operations_v1/wire_tests/Sts2AgentBridge.EventCardOperationsV1.Wire.Tests.csproj', 'event_card_operations_v1_wire', 51),
    ('event_card_operations_v1/native_card_tests/Sts2AgentBridge.EventCardOperationsV1.NativeCard.Tests.csproj', 'event_card_operations_v1_native_card', 11),
    ('event_card_operations_v1/native_tests/Sts2AgentBridge.EventCardOperationsV1.Native.Tests.csproj', 'event_card_operations_v1_native', 14),
    ('event_card_operations_v1/native_tests/Sts2AgentBridge.EventCardOperationsV1.Native.Factory.Tests.csproj', 'event_card_operations_v1_native_factories', 4),
    ('event_card_operations_v1/native_tests/Sts2AgentBridge.EventCardOperationsV1.Native.Composition.Tests.csproj', 'event_card_operations_v1_native_composition', 2),
)
NATIVE_PROJECTS: tuple[str, ...] = ('native/Sts2AgentBridge.EventCardOperationsV1.Native.csproj',)
BUILD_ONLY_PROJECTS: tuple[str, ...] = (
    'wire/Sts2AgentBridge.EventCardOperationsV1.Wire.csproj',
    'integration/Sts2AgentBridge.EventCardOperationsV1.Integration.csproj',
)
PYTHON_TESTS: tuple[tuple[str, str, int], ...] = (('host_tests/test_event_card_operations_host.py', 'event_card_operations_v1_host', 58),)
JSON_TESTS = (('checker_tests/test_event_card_project_boundary.py', 'event_card_operations_v1_project_boundary', 25),)
INTEGRATION_SCRIPT = 'integration_tests/test_event_card_operations_integration.py'
INTEGRATION_SUITE = 'event_card_operations_v1_integration'
INTEGRATION_COUNT = 9
DERIVATION_SCRIPT = 'derivation/check_derivation.py'
DERIVATION_SUITE = 'event_card_operations_v1_derivation'
DERIVATION_COUNT = 304
PREFIX = 'bridge/Sts2AgentBridge/successors/'
AUTHORITY_FILES = {
    'docs/PHASE_1_EVENT_CARD_OPERATIONS_V1_CONTRACT.md': CONTRACT,
    'docs/research/PHASE_1_EVENT_CARD_OPERATIONS_V1_CALLER_SELECTION.md':
        'e34a7190409c99ffed1693cd4af8c6ae37f50932b1c93be093927ae4188cf492',
}


def fail(code: str) -> None:
    raise ValueError(code)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frozen_sources():
    path = ROOT.parent / 'event_orchestrator_v1/check.py'
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            fail('frozen_helper_link')
    data = path.read_bytes()
    if sha(data) != PREVIOUS_CHECK:
        fail('frozen_helper_identity')
    previous = types.ModuleType('verified_orchestrator_checker')
    previous.__file__ = str(path)
    exec(compile(data, str(path), 'exec'), previous.__dict__)
    runner, helper, boot, components, inventories = previous.frozen_sources()
    components['event_orchestrator_v1'], inventories['event_orchestrator_v1'] = helper.source_snapshot(
        ROOT.parent / 'event_orchestrator_v1', 'event_orchestrator_v1', previous.CONTRACT,
        ORCHESTRATOR_MANIFEST, ORCHESTRATOR_INVENTORY)
    helper.verify_old_inventory(ROOT.parents[3])
    if len(components) != 13:
        fail('predecessor_count')
    return runner, helper, boot, components, inventories


def collect_own(helper):
    files = {}
    helper.reject_links(ROOT)
    for p in sorted(ROOT.rglob('*')):
        relative = p.relative_to(ROOT)
        if {'obj', 'bin', '__pycache__'}.intersection(relative.parts):
            fail('generated_source_output')
        helper.reject_links(p)
        if p.is_file() and relative.as_posix() != 'source_identity.json':
            files[relative.as_posix()] = helper.read_regular(p)
    return files


def old_sources(helper):
    repository = ROOT.parents[3]
    bridge = repository / 'bridge/Sts2AgentBridge'
    paths = [p for pattern in ('*.cs', '*.csproj') for p in (bridge / 'src').rglob(pattern)
             if not {'obj', 'bin'}.intersection(p.relative_to(bridge).parts)]
    paths += [bridge / n for n in ('Directory.Build.props', 'global.json', 'Sts2AgentBridge.sln', 'package/Sts2AgentBridge.json')]
    files = {}
    for p in sorted(paths):
        helper.reject_links(p)
        files[p.relative_to(repository).as_posix()] = helper.read_regular(p)
    projection = ''.join(sha(data) + '  ' + name + '\n' for name, data in sorted(files.items()))
    if len(files) != 48 or sha(projection.encode('ascii')) != helper.OLD_INVENTORY:
        fail('old_source_identity')
    return files


def authority_sources(helper):
    result = {}
    for name, digest in AUTHORITY_FILES.items():
        path = ROOT.parents[3] / name
        helper.reject_links(path)
        if path.stat().st_size > 65536:
            fail('authority_size')
        data = helper.read_regular(path)
        if sha(data) != digest:
            fail('authority_identity')
        result[name] = data
    return result


def inputs(components, old):
    return {**old, **{PREFIX + component + '/' + name: data for component, files in components.items() for name, data in files.items()}}


def resolve(project, include):
    if not include or '$' in include or '*' in include or '?' in include or '\\' in include or Path(include).is_absolute():
        fail('dynamic_project_input')
    name = os.path.normpath(str(Path(project).parent / include))
    if name.startswith('../'):
        fail('project_input_escape')
    return name


def project_closure(all_inputs, start, *, pure):
    pending, visited = [start], set()
    while pending:
        project = pending.pop()
        if project in visited:
            continue
        if project not in all_inputs or not project.endswith('.csproj'):
            fail('project_reference_boundary')
        visited.add(project)
        tree = ET.fromstring(all_inputs[project])
        if any(n.tag == 'PackageReference' for n in tree.iter()):
            fail('package_reference')
        if pure and any(n.tag == 'Reference' for n in tree.iter()):
            fail('pure_target_dependency')
        for n in tree.iter('ProjectReference'):
            pending.append(resolve(project, n.attrib['Include']))
    return visited


def verify_projects(components, old):
    own = components[COMPONENT]
    if not PROJECT_HASHES or not PURE_TESTS or not NATIVE_PROJECTS or not INTEGRATION_SCRIPT:
        fail('projects_not_reviewed')
    pins = {'Directory.Build.props': PROPS, 'core/EventOrchestratorV1Contracts.cs': API, 'wire/wire_schema.json': SCHEMA}
    for path, digest in pins.items():
        if sha(own.get(path, b'')) != digest:
            fail('shared_contract_identity')
    controls = {p for p in own if Path(p).suffix.lower() in ('.props', '.targets', '.rsp') or Path(p).name.lower() in ('nuget.config', 'global.json')}
    if controls != {'Directory.Build.props'}:
        fail('build_control_inventory')
    if {p for p in own if p.endswith('.csproj')} != set(PROJECT_HASHES):
        fail('project_inventory')
    all_inputs = inputs(components, old)
    compiled = set()
    for path, digest in PROJECT_HASHES.items():
        if sha(own[path]) != digest:
            fail('project_identity')
        full = PREFIX + COMPONENT + '/' + path
        tree = ET.fromstring(own[path])
        for node in tree.iter():
            if node.tag not in ('Compile', 'ProjectReference', 'EmbeddedResource'):
                continue
            resolved = resolve(full, node.attrib['Include'])
            if resolved not in all_inputs:
                fail('project_input_boundary')
            if node.tag == 'Compile':
                if not resolved.endswith('.cs'):
                    fail('compile_input_type')
                compiled.add(resolved)
    if {PREFIX + COMPONENT + '/' + p for p in own if p.endswith('.cs')} != {p for p in compiled if p.startswith(PREFIX + COMPONENT + '/')}:
        fail('uncompiled_new_source')
    roots = [PREFIX + relative for relative, _, _ in PURE_TESTS]
    roots += [PREFIX + COMPONENT + '/' + relative for relative in (*NATIVE_PROJECTS, *BUILD_ONLY_PROJECTS)]
    if len(roots) != len(set(roots)):
        fail('duplicate_build_root')
    built = set()
    for relative, _, _ in PURE_TESTS:
        built.update(project_closure(all_inputs, PREFIX + relative, pure=True))
    for relative in BUILD_ONLY_PROJECTS:
        built.update(project_closure(all_inputs, PREFIX + COMPONENT + '/' + relative, pure=True))
    for relative in NATIVE_PROJECTS:
        built.update(project_closure(all_inputs, PREFIX + COMPONENT + '/' + relative, pure=False))
    own_projects = {PREFIX + COMPONENT + '/' + p for p in PROJECT_HASHES}
    if {p for p in built if p.startswith(PREFIX + COMPONENT + '/')} != own_projects:
        fail('unbuilt_new_project')
    return all_inputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dotnet', type=Path, required=True)
    parser.add_argument('--game-data-dir', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--unfrozen', action='store_true', help='Explicit candidate check before first source freeze; never accepted source identity.')
    args = parser.parse_args()
    previous, helper, boot, components, inventories = frozen_sources()
    if args.unfrozen:
        if (ROOT / 'source_identity.json').exists():
            fail('unfrozen_mode_after_freeze')
        components[COMPONENT] = collect_own(helper)
        inventory = sha(''.join(sha(data) + '  ' + name + '\n' for name, data in sorted(components[COMPONENT].items())).encode('ascii'))
    else:
        components[COMPONENT], inventory = helper.source_snapshot(ROOT, COMPONENT, CONTRACT)
    old = old_sources(helper)
    all_inputs = verify_projects(components, old)
    authorities = authority_sources(helper)
    if set(all_inputs).intersection(authorities):
        fail('authority_input_collision')
    all_inputs.update(authorities)
    game = args.game_data_dir
    if not game.is_absolute() or str(game) != os.path.normpath(str(game)):
        fail('reference_root')
    helper.reject_links(game)
    references = {name: boot.pinned_reference(helper, game / name, size, digest) for name, (size, digest) in boot.REFERENCES.items()}
    if args.scratch.parent != Path('/private/tmp'):
        fail('scratch_boundary')
    helper.create_scratch(args.scratch)
    dotnet = str(args.dotnet.resolve(strict=True))
    run, passed = previous.run, previous.passed

    def snapshot(destination):
        destination.mkdir()
        source = destination / 'source'
        for name, data in all_inputs.items():
            p = source / name; p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as stream:
                stream.write(data)
        helper.verify_old_inventory(source)
        refs = destination / 'references'; refs.mkdir()
        for name, data in references.items():
            (refs / name).write_bytes(data)
        empty = destination / 'no_game_inputs'; empty.mkdir()
        tmp = destination / 'tmp'; tmp.mkdir(mode=0o700)
        env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'TMPDIR': str(tmp), 'DOTNET_CLI_HOME': str(destination / 'cli'),
               'DOTNET_SKIP_FIRST_TIME_EXPERIENCE': '1', 'DOTNET_CLI_TELEMETRY_OPTOUT': '1', 'DOTNET_GENERATE_ASPNET_CERTIFICATE': 'false',
               'DOTNET_NOLOGO': '1', 'DOTNET_MULTILEVEL_LOOKUP': '0', 'DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER': '1',
               'MSBUILDDISABLENODEREUSE': '1', 'NUGET_PACKAGES': str(destination / 'packages'), 'PYTHONDONTWRITEBYTECODE': '1'}
        own = source / PREFIX / COMPONENT
        nuget = destination / 'NuGet.Config'
        nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
        if run([dotnet, '--version'], own, env).strip() != '9.0.303':
            fail('sdk_identity')
        def build(relative, native=False):
            full = PREFIX + relative
            project = source / full
            graph = project_closure(all_inputs, full, pure=not native)
            allowed = set()
            for name in graph:
                tree = ET.fromstring(all_inputs[name]); assembly = tree.find('.//AssemblyName')
                allowed.add(assembly.text if assembly is not None else Path(name).stem)
            flags = ['--artifacts-path', str(destination / 'artifacts'), '-m:1', '-p:STS2GameDataDir=' + str(refs if native else empty)]
            run([dotnet, 'restore', str(project), '--configfile', str(nuget), *flags, '-p:RestoreBuildInParallel=false', '-p:NuGetAudit=false'], own, env, sdk=True)
            run([dotnet, 'build', str(project), '--no-restore', '-c', 'Release', *flags, '-p:BuildInParallel=false', '-p:UseSharedCompilation=false'], own, env, sdk=True)
            tree = ET.fromstring(all_inputs[full]); named = tree.find('.//AssemblyName'); name = named.text if named is not None else project.stem
            output = destination / 'artifacts/bin' / project.stem / 'release'
            deps = json.loads((output / (name + '.deps.json')).read_bytes())
            libraries = {key.rsplit('/', 1)[0] for key in deps['libraries']}
            if libraries - allowed or any((output / name).exists() for name in ('sts2.dll', 'GodotSharp.dll')):
                fail('output_dependency_boundary')
            return output / (name + '.dll')
        return source, own, env, build

    source, own, env, build = snapshot(args.scratch / 'first')
    summaries, assemblies = {}, {}
    for relative, suite, count in PURE_TESTS:
        assembly = build(relative); assemblies[suite] = assembly
        summaries[suite] = passed(run([dotnet, str(assembly)], own, env), suite, count)
    for relative in BUILD_ONLY_PROJECTS:
        assemblies[INTEGRATION_SUITE] = build(COMPONENT + '/' + relative)
    for relative, suite, count in PYTHON_TESTS:
        output = run([sys.executable, '-B', '-I', '-S', str(own / relative)], own, env, unittest_count=count)
        if output:
            fail('host_fixture_stdout')
        summaries[suite] = {'schema_version': 1, 'status': 'passed', 'suite': suite, 'check_count': count}
    for relative, suite, count in JSON_TESTS:
        summaries[suite] = passed(run([sys.executable, '-B', '-I', '-S', str(own / relative)], own, env), suite, count)
    summaries[INTEGRATION_SUITE] = passed(run([sys.executable, '-B', '-I', '-S', str(own / INTEGRATION_SCRIPT), '--dotnet', dotnet,
        '--fixture', str(assemblies[INTEGRATION_SUITE]), '--host', str(own / 'host/event_orchestrator_host.py')], own, env), INTEGRATION_SUITE, INTEGRATION_COUNT)
    if DERIVATION_SCRIPT:
        summaries[DERIVATION_SUITE] = passed(run([sys.executable, '-B', '-I', '-S', str(own / DERIVATION_SCRIPT), '--source-root', str(source)], own, env), DERIVATION_SUITE, DERIVATION_COUNT)
    native = {p: build(COMPONENT + '/' + p, True) for p in NATIVE_PROJECTS}
    _, _, _, build_second = snapshot(args.scratch / 'second')
    compiled = {}
    for project, first in native.items():
        second = build_second(COMPONENT + '/' + project, True)
        data = first.read_bytes()
        if data != second.read_bytes():
            fail('native_build_reproduction')
        compiled[project] = {'bytes': len(data), 'sha256': sha(data), 'deterministic_build_count': 2, 'executed': False}
    result = {'schema_version': 1, 'status': 'passed', 'suite': 'event_card_operations_v1_offline',
              'source_frozen': not args.unfrozen, 'source_inventory_sha256': inventory,
              'authority_document_sha256': AUTHORITY_FILES,
              'frozen_source_inventories': inventories, 'old_bridge_file_count': 48, 'old_bridge_inventory_sha256': helper.OLD_INVENTORY,
              'synthetic': summaries, 'native_compilation': compiled, 'pinned_reference_count': 2,
              'target_assemblies_executed': False, 'release_ready': False, 'live_campaign_started': False}
    (args.scratch / 'result.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
