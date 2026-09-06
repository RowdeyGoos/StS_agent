"""Reject altered compile inputs before any build or candidate execution."""
from __future__ import annotations
import json
from pathlib import Path
import types

ROOT = Path(__file__).absolute().parents[1]
path = ROOT / 'check.py'
gate = types.ModuleType('card_release_project_boundary_gate')
gate.__file__ = str(path)
exec(compile(path.read_bytes(), str(path), 'exec'), gate.__dict__)


def main():
    _, helper, _, frozen, _ = gate.frozen_sources()
    own = {}
    for path in ROOT.rglob('*'):
        if path.is_file() and not {'obj','bin','__pycache__'}.intersection(path.relative_to(ROOT).parts):
            helper.reject_links(path)
            own[path.relative_to(ROOT).as_posix()] = helper.read_regular(path)
    frozen['card_selection_completion_v1'] = own
    gate.verify_projects(frozen)
    cases = []
    production = gate.PRODUCTION
    runtime = next(name for name in gate.PROJECT_HASHES if name.startswith('native_tests/') and 'Original' not in name)
    def edited(name, old, new):
        def apply(c):
            assert old in c['card_selection_completion_v1'][name]
            c['card_selection_completion_v1'][name] = c['card_selection_completion_v1'][name].replace(old, new, 1)
        return apply
    def added(name, content):
        return lambda c: c['card_selection_completion_v1'].__setitem__(name, content)
    cases += [added('unknown.csproj', own[runtime]),
        edited(production, b'</Project>', b'<Import Project="/synthetic/foreign.props" /></Project>'),
        edited(production, b'</Project>', b'<ItemGroup><PackageReference Include="Foreign" Version="1" /></ItemGroup></Project>'),
        edited(production, b'</PropertyGroup>', b'<DefineConstants>CARD_SELECTION_RELEASE_TEST_SEAM</DefineConstants></PropertyGroup>'),
        edited(runtime, b'../native/PinnedCardSelectionV1NativeAdapter.cs', b'*.cs'),
        edited(runtime, b'../native/PinnedCardSelectionV1NativeAdapter.cs', b'/synthetic/foreign.cs'),
        edited('Directory.Build.props', b'</Project>', b'<Import Project="/synthetic.props" /></Project>'),
        added('Directory.Build.targets', b'<Project/>'),
        added('build/foreign.rsp', b'/unsafe+'),
        added('runtime/Uncompiled.cs', b'class Uncompiled {}'),
        lambda c: c['card_selection_completion_v1'].pop('native/PinnedCardSelectionV1NativeAdapter.cs')]
    def policy_change(kind):
        def apply(c):
            name = 'policy/card_selection_release_policy.json'
            value = json.loads(c['card_selection_completion_v1'][name])
            if kind == 'order':
                value['source_files'].reverse()
            elif kind == 'path':
                value['source_files'][0]['path'] = '/synthetic/outside.cs'
            else:
                value['source_files'][0]['sha256'] = '0' * 64
            c['card_selection_completion_v1'][name] = json.dumps(value).encode()
        return apply
    cases += [policy_change('order'), policy_change('path'), policy_change('hash')]
    for mutate in cases:
        changed = {component: dict(files) for component, files in frozen.items()}
        mutate(changed)
        try:
            gate.verify_projects(changed)
        except (ValueError, KeyError):
            pass
        else:
            raise AssertionError('altered build boundary accepted')
    print(json.dumps({'schema_version':1,'status':'passed','suite':'card_selection_completion_project_boundary','check_count':1+len(cases)}, separators=(',', ':')))


if __name__ == '__main__':
    main()
