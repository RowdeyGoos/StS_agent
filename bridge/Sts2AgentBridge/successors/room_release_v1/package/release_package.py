"""Canonical, byte-pinned Room Flows V1 package. No install or game operations."""
from __future__ import annotations
import hashlib
import io
from pathlib import Path
import os
import stat
import zipfile

DLL_NAME = "Sts2AgentBridgeRoomFlowsV1.dll"
MANIFEST_NAME = "Sts2AgentBridgeRoomFlowsV1.json"
ZIP_NAME = "Sts2AgentBridgeRoomFlowsV1-1.0.0.zip"
ARTIFACT_ROOT = Path("/private/tmp/sts-room-flows-v1-release")
IDENTITIES = {
    DLL_NAME: (177152, "60db75fa1c50c46bc2a6426b269a9aa5aebca9211a136de79f801ec1cdfa5a6f"),
    MANIFEST_NAME: (344, "9b361b08e3e99de5322d24811c24497c37662ded1c9e5623a2b4e9cc9ab38812"),
    ZIP_NAME: (177900, "ee030cad1bb019b1793f04a6faaf94caa65b821d4c349fecd83ba668f61c4819"),
}
MANIFEST = b'''{
  "id": "Sts2AgentBridgeRoomFlowsV1",
  "name": "STS2 Agent Bridge Room Flows V1",
  "author": "StS Agent Project",
  "description": "Restricted shop and event flow bridge for StS agent research",
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
            info = zipfile.ZipInfo("Sts2AgentBridgeRoomFlowsV1/" + name, (1980, 1, 1, 0, 0, 0))
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
