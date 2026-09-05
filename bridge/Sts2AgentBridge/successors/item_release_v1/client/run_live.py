#!/usr/bin/env python3
"""One fixed campaign read and one frozen item controller invocation."""
from __future__ import annotations
import hashlib
import json
import os
import platform
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).absolute().parents[1]
CONTRACT = '9d7d25840fb8910448bd0f8215f4eabdc081c8151a96eb3649f4db3025103b34'
FROZEN = {
    'item_bootstrap_v1': '77aa278f7c7c2cba2523c5c4d474fb2f45eb76dfa3d1faa7feb914a96e4c47ab',
    'item_transport_v1': 'e8cb05876cba695d8b4d22d5e12e597a4ea4d2fa7d525a160c9ccb223b91fe57',
    'item_wire_v1': 'c930337e74b4eed9f41ba00e804a950a7334a33a96ded7531361312bf5115c10',
    'item_v1': '435219714fa6e667738685f9909396839c46c21612a50bc84a0fc58e584c938a',
}


def _read_source(path: Path) -> bytes:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if stat.S_ISLNK(current.lstat().st_mode):
            raise ValueError()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 <= before.st_size <= 8 * 1024 * 1024:
            raise ValueError()
        data = bytearray()
        while len(data) < before.st_size:
            block = os.read(fd, min(65536, before.st_size - len(data)))
            if not block:
                raise ValueError()
            data.extend(block)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if os.read(fd, 1) or fields(before) != fields(os.fstat(fd)) or fields(before) != fields(path.lstat()):
            raise ValueError()
        return bytes(data)
    finally:
        os.close(fd)


def verify_sources() -> None:
    for component in (*FROZEN, 'item_release_v1'):
        root = ROOT.parent / component
        raw = _read_source(root / 'source_identity.json')
        if component in FROZEN and hashlib.sha256(raw).hexdigest() != FROZEN[component]:
            raise ValueError()
        manifest = json.loads(raw)
        if manifest.get('schema_version') != 1 or manifest.get('component') != component:
            raise ValueError()
        if component == 'item_release_v1' and manifest.get('contract_sha256') != CONTRACT:
            raise ValueError()
        names = set()
        for entry in manifest['files']:
            name = entry['path']
            path = Path(name)
            if path.is_absolute() or str(path) != name or '..' in path.parts or name in names:
                raise ValueError()
            names.add(name)
            if hashlib.sha256(_read_source(root / path)).hexdigest() != entry['sha256']:
                raise ValueError()
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
                  if p.is_file() and p.name != 'source_identity.json' and
                  not set(p.relative_to(root).parts).intersection({'__pycache__', 'bin', 'obj'})}
        if names != actual:
            raise ValueError()


def run_once(expected: str, validate, read, collect, acl):
    token = bytearray()
    try:
        layout, state = validate(expected)
        token = read(layout.user_profile, 501, state, acl)
        # The frozen function owns transfer and zeroing; finally is defensive for exceptions.
        try:
            return collect(token)
        except Exception:
            return {'schema_version': 1, 'status': 'failed', 'code': 'internal_failure'}
    finally:
        token[:] = b'\0' * len(token)


def main() -> int:
    result = {'schema_version': 1, 'status': 'failed', 'code': 'item_client_preflight_failed'}
    try:
        args = sys.argv[1:]
        if (len(args) != 2 or args[0] != '--expected-state-sha256' or len(args[1]) != 64 or
                any(c not in '0123456789abcdef' for c in args[1])):
            raise ValueError()
        if sys.version_info < (3, 10) or sys.platform != 'darwin' or platform.machine() != 'arm64' or os.getuid() != 501 or os.geteuid() != 501:
            raise ValueError()
        verify_sources()
        sys.path[:0] = [str(ROOT / 'operations'), str(ROOT / 'client'), str(ROOT.parent)]
        import manage_live_campaign as manager
        from secure_operator import read_credential
        from item_transport_v1.transport import run_authenticated_collection
        result = run_once(args[1], manager.validate_installed_for_client, read_credential,
                          run_authenticated_collection, manager.require_no_granting_acl_fd)
    except KeyboardInterrupt:
        result = {'schema_version': 1, 'status': 'failed', 'code': 'interrupted'}
    except Exception:
        pass
    print(json.dumps(result, separators=(',', ':'), ensure_ascii=True))
    return 0 if result.get('status') == 'passed' else 4

if __name__ == '__main__':
    raise SystemExit(main())
