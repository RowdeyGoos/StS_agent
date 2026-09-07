"""Canonical, byte-pinned Generic Event V2 package. No install or game operations."""
from __future__ import annotations
import hashlib
import io
from pathlib import Path
import os
import stat
import zipfile

DLL_NAME = "Sts2AgentBridgeGenericEventV2.dll"
MANIFEST_NAME = "Sts2AgentBridgeGenericEventV2.json"
ZIP_NAME = "Sts2AgentBridgeGenericEventV2-1.0.0.zip"
ARTIFACT_ROOT = Path("/private/tmp/sts-generic-event-v2-release")
IDENTITIES = {
    DLL_NAME: (229888, "49fad4d399abaf2db7265b6649fcac05358342b79f83c44fefcfc58f7031bc02"),
    MANIFEST_NAME: (352, "6d83702879ee9072d0bc9c2659407cc6645aa14950f4de1055ba2a869fc7744c"),
    ZIP_NAME: (230668, "ed00a3b3fe47a9772b38c6d02ca346e35883378f3c31476353e4c9b864f51bbf"),
}
MANIFEST = b'''{
  "id": "Sts2AgentBridgeGenericEventV2",
  "name": "STS2 Agent Bridge Generic Event V2",
  "author": "StS Agent Project",
  "description": "Restricted generic event control bridge for StS agent research",
  "version": "1.0.0",
  "has_pck": false,
  "has_dll": true,
  "dependencies": [],
  "affects_gameplay": true,
  "min_game_version": "0.107.1"
}
'''

def require_identity(name: str, data: bytes) -> None:
    size, digest = IDENTITIES[name]
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("artifact_identity_mismatch")


def canonical_files(dll: bytes) -> dict[str, bytes]:
    require_identity(DLL_NAME, dll)
    require_identity(MANIFEST_NAME, MANIFEST)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, data in ((DLL_NAME, dll), (MANIFEST_NAME, MANIFEST)):
            info = zipfile.ZipInfo("Sts2AgentBridgeGenericEventV2/" + name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data)
    result = {DLL_NAME: dll, MANIFEST_NAME: MANIFEST, ZIP_NAME: output.getvalue()}
    for name, data in result.items():
        require_identity(name, data)
    return result


def verify_files(files: dict[str, bytes]) -> None:
    if set(files) != set(IDENTITIES):
        raise ValueError("artifact_inventory_mismatch")
    for name, data in files.items():
        require_identity(name, data)
    if files != canonical_files(files[DLL_NAME]):
        raise ValueError("noncanonical_package")


def read_regular(path: Path, limit: int) -> bytes:
    if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
        raise ValueError("artifact_path_invalid")
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if stat.S_ISLNK(current.lstat().st_mode):
            raise ValueError("artifact_link_rejected")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit or before.st_nlink != 1:
            raise ValueError("artifact_shape_invalid")
        chunks = bytearray()
        while len(chunks) < before.st_size:
            block = os.read(fd, min(65536, before.st_size - len(chunks)))
            if not block:
                raise ValueError("artifact_truncated")
            chunks.extend(block)
        after = os.fstat(fd)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink,
                              s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if os.read(fd, 1) or identity(before) != identity(after) or identity(after) != identity(path.lstat()):
            raise ValueError("artifact_changed")
        return bytes(chunks)
    finally:
        os.close(fd)


def publish_verified(files: dict[str, bytes]) -> None:
    """Coordinator calls only after full release gate. Never overwrite or adopt."""
    verify_files(files)
    parent = ARTIFACT_ROOT.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or stat.S_IMODE(parent.st_mode) != 0o1777:
        raise ValueError("artifact_parent_invalid")
    ARTIFACT_ROOT.mkdir(mode=0o700)
    for name, data in files.items():
        fd = os.open(ARTIFACT_ROOT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        try:
            offset = 0
            while offset < len(data):
                written = os.write(fd, data[offset:])
                if written <= 0:
                    raise OSError("artifact_write_failed")
                offset += written
            os.fsync(fd)
        finally:
            os.close(fd)
    verify_files({name: read_regular(ARTIFACT_ROOT / name, size) for name, (size, _) in IDENTITIES.items()})
