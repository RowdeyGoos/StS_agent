#!/usr/bin/env python3
"""Create this component's first identity after candidate gate and source review."""
from pathlib import Path
import hashlib
import json
import types

ROOT = Path(__file__).absolute().parent


def main():
    identity = ROOT / 'source_identity.json'
    if identity.exists() or identity.is_symlink():
        raise ValueError('source_identity_already_exists')
    gate = types.ModuleType('event_initial_freeze'); gate.__file__ = str(ROOT / 'check.py')
    exec(compile((ROOT / 'check.py').read_bytes(), gate.__file__, 'exec'), gate.__dict__)
    _, helper, _, components, _ = gate.frozen_sources()
    files = gate.collect_own(helper); components[gate.COMPONENT] = files
    gate.verify_projects(components, gate.old_sources(helper))
    manifest = {'schema_version': 1, 'component': gate.COMPONENT, 'contract_sha256': gate.CONTRACT,
                'files': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest()} for name, data in sorted(files.items())]}
    data = (json.dumps(manifest, indent=2) + '\n').encode('ascii')
    with identity.open('xb') as stream:
        stream.write(data)
    print(json.dumps({'schema_version': 1, 'status': 'created', 'file_count': len(files), 'manifest_sha256': hashlib.sha256(data).hexdigest()}, sort_keys=True))


if __name__ == '__main__':
    main()
