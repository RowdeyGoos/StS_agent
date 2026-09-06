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
COMPONENT = 'event_orchestrator_v1'
CONTRACT = 'da7cdbf6efcb6f2786e59a64a0b0d9ed7f9b355cd966f8a73b61d385987c543d'
PREVIOUS_CHECK = '9756019716ebad482276aa5564d6a844b07769de4ac67f501db61c30d9303419'
COMPLETION_MANIFEST = 'c31cb310fd4a72cad84aa23acddca18a7c0ff665b081b4b045dabaac87c9d74b'
COMPLETION_INVENTORY = '92cbd6071d5ed39c1de8e36dbdb7c8f9af8379da5d4d4fa48397837389f05dab'
API = '37f37caecb1a439761112b38a36229a25c29a2a674236978ae5f0bbde80b5fb1'
SCHEMA = 'e4da960bf0525b93d1526e01f44c01c190efe408c31b86e865e3082d21c4e399'
PROPS = '2b05edd4dbb4532b1e884c6267bf56c732b49415dc43a23245b3d0c3cc30265f'
# Filled only after project closure and implementation review; empty is fail-closed.
PROJECT_HASHES: dict[str, str] = {
    'broker_tests/Sts2AgentBridge.EventOrchestratorV1.Broker.Tests.csproj': 'd51c3f18c244a7de92bafe656b774bf17c1b246be041ecf7126bf40007118263',
    'brokers/Sts2AgentBridge.EventOrchestratorV1.Brokers.csproj': 'c290d607e683c8bec688c13c7a3d9226dd143a59f7a419cadccf0f7eb00a9b6a',
    'core/Sts2AgentBridge.EventOrchestratorV1.Core.csproj': '5cacc5fa7a979ca2009c78bd2eefc404e3f06cacfa34f26c6faec0e2f5f7e550',
    'core_tests/Sts2AgentBridge.EventOrchestratorV1.Core.Tests.csproj': '2815f99100b3dbf0dbfeda1bf7c6284e3fce127d226bd19f09ecf6fa458f7f76',
    'integration/Sts2AgentBridge.EventOrchestratorV1.Integration.csproj': 'cb5a918a8ffaa0ec9f67828626df59fbc6382877ccd175fe7cfda12890bac120',
    'native/Sts2AgentBridge.EventOrchestratorV1.Native.csproj': '9ba8807a3791d0e7a237c799d8514f84a37e350b69c7905a0dd1b71ec9c2164c',
    'native_tests/Sts2AgentBridge.EventOrchestratorV1.Native.Factory.Tests.csproj': '534bacad16b53dc32742bb03bfbdcc02f085b91f10daaa72cf4d552096abdfaa',
    'native_tests/Sts2AgentBridge.EventOrchestratorV1.Native.Tests.csproj': '43b2762c7abd5c02b3674816afb7a78443faac208716a9799708c379e4212011',
    'wire/Sts2AgentBridge.EventOrchestratorV1.Wire.csproj': 'a4a6336e3366b3da287495e6435f0b46dadd0e3f0d6dcfa823e40cbc3de51fc2',
    'wire_tests/Sts2AgentBridge.EventOrchestratorV1.Wire.Tests.csproj': '8840675ae51f9b69aa6fd7681ff1a64ec832cb03f5bfc1d2f9ca7615b6e0d6df',
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
)
NATIVE_PROJECTS: tuple[str, ...] = ('native/Sts2AgentBridge.EventOrchestratorV1.Native.csproj',)
BUILD_ONLY_PROJECTS: tuple[str, ...] = ('integration/Sts2AgentBridge.EventOrchestratorV1.Integration.csproj',)
PYTHON_TESTS: tuple[tuple[str, str, int], ...] = (('host_tests/test_event_host.py', 'event_orchestrator_v1_host', 37),)
JSON_TESTS = (('checker_tests/test_event_orchestrator_project_boundary.py', 'event_orchestrator_v1_project_boundary', 22),)
INTEGRATION_SCRIPT = 'integration_tests/test_event_orchestrator_integration.py'
INTEGRATION_SUITE = 'event_orchestrator_v1_integration'
INTEGRATION_COUNT = 9
DERIVATION_SCRIPT = 'derivation/check_derivation.py'
DERIVATION_SUITE = 'event_orchestrator_v1_native_derivation'
DERIVATION_COUNT = 10
PREFIX = 'bridge/Sts2AgentBridge/successors/'


def fail(code: str) -> None:
    raise ValueError(code)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frozen_sources():
    path = ROOT.parent / 'card_selection_completion_v1/check.py'
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            fail('frozen_helper_link')
    data = path.read_bytes()
    if sha(data) != PREVIOUS_CHECK:
        fail('frozen_helper_identity')
    previous = types.ModuleType('verified_completion_checker')
    previous.__file__ = str(path)
    exec(compile(data, str(path), 'exec'), previous.__dict__)
    _, helper, boot, components, inventories = previous.frozen_sources()
    components['card_selection_completion_v1'], inventories['card_selection_completion_v1'] = helper.source_snapshot(
        ROOT.parent / 'card_selection_completion_v1', 'card_selection_completion_v1', previous.CONTRACT,
        COMPLETION_MANIFEST, COMPLETION_INVENTORY)
    helper.verify_old_inventory(ROOT.parents[3])
    if len(components) != 12:
        fail('predecessor_count')
    return previous, helper, boot, components, inventories


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
        assemblies['event_orchestrator_v1_integration'] = build(COMPONENT + '/' + relative)
    for relative, suite, count in PYTHON_TESTS:
        output = run([sys.executable, '-B', '-I', '-S', str(own / relative)], own, env, unittest_count=count)
        if output:
            fail('host_fixture_stdout')
        summaries[suite] = {'schema_version': 1, 'status': 'passed', 'suite': suite, 'check_count': count}
    for relative, suite, count in JSON_TESTS:
        summaries[suite] = passed(run([sys.executable, '-B', '-I', '-S', str(own / relative)], own, env), suite, count)
    summaries[INTEGRATION_SUITE] = passed(run([sys.executable, '-B', '-I', '-S', str(own / INTEGRATION_SCRIPT), '--dotnet', dotnet,
        '--fixture', str(assemblies['event_orchestrator_v1_integration']), '--host', str(own / 'host/event_orchestrator_host.py')], own, env), INTEGRATION_SUITE, INTEGRATION_COUNT)
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
    result = {'schema_version': 1, 'status': 'passed', 'suite': 'event_orchestrator_v1_offline',
              'source_frozen': not args.unfrozen, 'source_inventory_sha256': inventory,
              'frozen_source_inventories': inventories, 'old_bridge_file_count': 48, 'old_bridge_inventory_sha256': helper.OLD_INVENTORY,
              'synthetic': summaries, 'native_compilation': compiled, 'pinned_reference_count': 2,
              'target_assemblies_executed': False, 'release_ready': False, 'live_campaign_started': False}
    (args.scratch / 'result.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
