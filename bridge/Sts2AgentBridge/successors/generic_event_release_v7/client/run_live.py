#!/usr/bin/env python3
"""One fixed campaign and one frozen generic event controller invocation."""
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
CONTRACT = "be7accd099024241400d26e691a3e1cf533d975087846db895e4b90c1c0e30a8"
PREVIOUS_CHECK_SHA256 = "5ebe65a68f3444fed2c68035ad7776d952666c538dc4e14fdeb272d61655f5c8"


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
    path = ROOT.parent/'generic_event_v7/check.py'
    raw = _read_source(path)
    if hashlib.sha256(raw).hexdigest() != PREVIOUS_CHECK_SHA256:
        raise ValueError()
    import types
    previous = types.ModuleType('verified_generic_component')
    previous.__file__ = str(path)
    exec(compile(raw,str(path),'exec'),previous.__dict__)
    previous.sources()
    manifest = json.loads(_read_source(ROOT/'source_identity.json'))
    if (manifest.get('schema_version') != 1 or manifest.get('component') != 'generic_event_release_v7'
            or manifest.get('contract_sha256') != CONTRACT or type(manifest.get('files')) is not dict):
        raise ValueError()
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and p.name != 'source_identity.json'}
    if set(manifest['files']) != actual:
        raise ValueError()
    for name,digest in manifest['files'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or path.as_posix() != name:
            raise ValueError()
        if hashlib.sha256(_read_source(ROOT/path)).hexdigest() != digest:
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
            return {'schema_version': 1, 'status': 'failed', 'code': 'internal_failure', 'last_response_diagnostic': 'none', 'completed_card_children': 0, 'completed_item_children': 0}
    finally:
        token[:] = b'\0' * len(token)


def main() -> int:
    result = {'schema_version': 1, 'status': 'failed', 'code': 'generic_event_client_preflight_failed', 'last_response_diagnostic': 'none', 'completed_card_children': 0, 'completed_item_children': 0}
    try:
        args = sys.argv[1:]
        if (len(args) != 2 or args[0] != '--expected-state-sha256' or len(args[1]) != 64 or
                any(c not in '0123456789abcdef' for c in args[1])):
            raise ValueError()
        if sys.version_info < (3, 10) or sys.platform != 'darwin' or platform.machine() != 'arm64' or os.getuid() != 501 or os.geteuid() != 501:
            raise ValueError()
        verify_sources()
        sys.path[:0] = [str(ROOT / 'operations'), str(ROOT / 'client'), str(ROOT / 'transport'), str(ROOT.parent)]
        import manage_live_campaign as manager
        from secure_operator import read_credential
        from generic_event_transport import run_authenticated_generic_event
        result = run_once(args[1], manager.validate_installed_for_client, read_credential,
                          run_authenticated_generic_event, manager.require_no_granting_acl_fd)
    except KeyboardInterrupt:
        result = {'schema_version': 1, 'status': 'failed', 'code': 'interrupted', 'last_response_diagnostic': 'none', 'completed_card_children': 0, 'completed_item_children': 0}
    except Exception:
        pass
    print(json.dumps(result, separators=(',', ':'), ensure_ascii=True))
    return 0 if result.get('status') == 'resolved' else 4

if __name__ == '__main__':
    raise SystemExit(main())
