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


def verify_sources(manifest: Path, expected_sha256: str) -> None:
    """Validate the selected release bundle before reading a credential."""
    sys.path.insert(0, str(ROOT.parents[1]))
    from release_support import verify_release_sources
    verify_release_sources(ROOT.parents[1], ROOT.name, manifest, expected_sha256)


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
        if (len(args) != 6 or args[0] != '--expected-state-sha256' or len(args[1]) != 64 or
                any(c not in '0123456789abcdef' for c in args[1])):
            raise ValueError()
        if sys.version_info < (3, 10) or sys.platform != 'darwin' or platform.machine() != 'arm64' or os.getuid() != 501 or os.geteuid() != 501:
            raise ValueError()
        if args[2] != '--release-manifest' or args[4] != '--release-sha256':
            raise ValueError()
        verify_sources(Path(args[3]), args[5])
        sys.path[:0] = [str(ROOT / 'operations'), str(ROOT / 'client'), str(ROOT.parents[1])]
        import manage_live_campaign as manager
        from secure_operator import read_credential
        from components.item_transport.transport import run_authenticated_collection
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
