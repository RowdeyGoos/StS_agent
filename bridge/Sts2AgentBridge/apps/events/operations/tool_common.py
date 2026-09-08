#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable, NoReturn

EXIT_OK = 0
EXIT_INVALID_INVOCATION = 2
EXIT_UNSAFE_BOUNDARY = 3
EXIT_MISMATCH = 4
EXIT_INTERNAL = 5

HEX_64 = re.compile(r"[0-9a-f]{64}\Z")

PACKAGE_ENTRIES = (
    "Sts2AgentBridgeGenericEventV10/Sts2AgentBridgeGenericEventV10.dll",
    "Sts2AgentBridgeGenericEventV10/Sts2AgentBridgeGenericEventV10.json",
)
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_EXTERNAL_ATTR = (stat.S_IFREG | 0o644) << 16

CANONICAL_MANIFEST = (
    b'{\n'
    b'  "id": "Sts2AgentBridgeGenericEventV10",\n'
    b'  "name": "STS2 Agent Bridge Generic Event V10",\n'
    b'  "author": "StS Agent Project",\n'
    b'  "description": "Restricted generic event control bridge for StS agent research",\n'
    b'  "version": "1.0.0",\n'
    b'  "has_pck": false,\n'
    b'  "has_dll": true,\n'
    b'  "dependencies": [],\n'
    b'  "affects_gameplay": true,\n'
    b'  "min_game_version": "0.107.1"\n'
    b'}\n'
)


class ToolFailure(Exception):
    def __init__(self, exit_code: int, error_code: str) -> None:
        super().__init__(error_code)
        self.exit_code = exit_code
        self.error_code = error_code


def fail(exit_code: int, error_code: str) -> NoReturn:
    raise ToolFailure(exit_code, error_code)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))


def run_cli(operation: Callable[[], dict[str, Any]]) -> int:
    try:
        payload = operation()
        emit(payload)
        return EXIT_OK
    except KeyboardInterrupt:
        emit({"schema_version": 1, "status": "failed", "code": "interrupted"})
        return EXIT_INTERNAL
    except ToolFailure as failure:
        emit({"schema_version": 1, "status": "failed", "code": failure.error_code})
        return failure.exit_code
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile):
        emit({"schema_version": 1, "status": "failed", "code": "internal_failure"})
        return EXIT_INTERNAL


def require_hex_64(value: str, label: str) -> str:
    if HEX_64.fullmatch(value) is None:
        fail(EXIT_INVALID_INVOCATION, f"invalid_{label}")
    return value


def absolute_path(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        fail(EXIT_INVALID_INVOCATION, f"non_absolute_{label}")
    if os.path.normpath(value) != value:
        fail(EXIT_UNSAFE_BOUNDARY, f"non_canonical_{label}")
    return path


def _components(path: Path) -> list[Path]:
    components: list[Path] = []
    current = path
    while current != current.parent:
        components.append(current)
        current = current.parent
    components.reverse()
    return components


def reject_symlink_components(path: Path, *, allow_missing_leaf: bool = False) -> None:
    components = _components(path)
    for index, component in enumerate(components):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            if allow_missing_leaf and index == len(components) - 1:
                return
            fail(EXIT_UNSAFE_BOUNDARY, "missing_path_component")
        if stat.S_ISLNK(metadata.st_mode):
            fail(EXIT_UNSAFE_BOUNDARY, "symlink_path_component")


def require_regular_file(path: Path, label: str, *, max_bytes: int | None = None) -> bytes:
    reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        fail(EXIT_UNSAFE_BOUNDARY, f"missing_{label}")
    if not stat.S_ISREG(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, f"non_regular_{label}")
    if max_bytes is not None and metadata.st_size > max_bytes:
        fail(EXIT_MISMATCH, f"oversize_{label}")
    try:
        data = path.read_bytes()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, f"unreadable_{label}")
    if len(data) != metadata.st_size:
        fail(EXIT_UNSAFE_BOUNDARY, f"changing_{label}")
    return data


def require_directory(path: Path, label: str, *, empty: bool = False) -> None:
    reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        fail(EXIT_UNSAFE_BOUNDARY, f"missing_{label}")
    if not stat.S_ISDIR(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, f"non_directory_{label}")
    if empty:
        try:
            if any(path.iterdir()):
                fail(EXIT_UNSAFE_BOUNDARY, f"nonempty_{label}")
        except OSError:
            fail(EXIT_UNSAFE_BOUNDARY, f"unreadable_{label}")


def require_executable_file(path: Path, label: str) -> None:
    reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        fail(EXIT_UNSAFE_BOUNDARY, f"missing_{label}")
    if not stat.S_ISREG(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, f"non_regular_{label}")
    if metadata.st_mode & 0o111 == 0:
        fail(EXIT_UNSAFE_BOUNDARY, f"non_executable_{label}")


def require_output_file(path: Path, label: str) -> None:
    require_directory(path.parent, f"{label}_parent")
    if path.exists() or path.is_symlink():
        reject_symlink_components(path)
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            fail(EXIT_UNSAFE_BOUNDARY, f"non_regular_{label}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "unreadable_file")
    return digest.hexdigest()


def validate_manifest_bytes(data: bytes) -> None:
    if data != CANONICAL_MANIFEST:
        fail(EXIT_MISMATCH, "manifest_not_canonical")


def build_canonical_zip(dll_data: bytes, manifest_data: bytes, output: Path) -> None:
    validate_manifest_bytes(manifest_data)
    if len(dll_data) < 2 or dll_data[:2] != b"MZ":
        fail(EXIT_MISMATCH, "invalid_managed_dll")
    require_output_file(output, "output")
    temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    if temporary.exists() or temporary.is_symlink():
        fail(EXIT_UNSAFE_BOUNDARY, "temporary_output_exists")
    try:
        with zipfile.ZipFile(
            temporary,
            mode="x",
            compression=zipfile.ZIP_STORED,
            allowZip64=False,
            strict_timestamps=True,
        ) as archive:
            archive.comment = b""
            for name, data in zip(PACKAGE_ENTRIES, (dll_data, manifest_data)):
                info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = ZIP_EXTERNAL_ATTR
                info.extra = b""
                info.comment = b""
                archive.writestr(info, data)
        os.replace(temporary, output)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def inspect_canonical_zip(path: Path) -> tuple[bytes, bytes]:
    package_data = require_regular_file(path, "package")
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            if archive.comment != b"":
                fail(EXIT_MISMATCH, "archive_comment")
            infos = archive.infolist()
            for info in infos:
                name = info.filename
                components = name.split("/")
                if (
                    name.startswith("/")
                    or "\\" in name
                    or any(component in ("", ".", "..") for component in components)
                ):
                    fail(EXIT_MISMATCH, "package_traversal_entry")
                unix_mode = info.external_attr >> 16
                if stat.S_ISLNK(unix_mode):
                    fail(EXIT_MISMATCH, "package_symlink_entry")
                basename = components[-1].lower()
                if basename in ("sts2.dll", "godotsharp.dll", "0harmony.dll"):
                    fail(EXIT_MISMATCH, "package_game_assembly")
            if tuple(info.filename for info in infos) != PACKAGE_ENTRIES:
                expected = set(PACKAGE_ENTRIES)
                extras = [info.filename for info in infos if info.filename not in expected]
                if any(name.lower().endswith(".json") for name in extras):
                    fail(EXIT_MISMATCH, "package_extra_manifest")
                if any(name.lower().endswith(".dll") for name in extras):
                    fail(EXIT_MISMATCH, "package_secondary_dll")
                fail(EXIT_MISMATCH, "package_entries")
            payloads: list[bytes] = []
            for info in infos:
                if info.is_dir():
                    fail(EXIT_MISMATCH, "directory_entry")
                if info.compress_type != zipfile.ZIP_STORED:
                    fail(EXIT_MISMATCH, "compressed_entry")
                if info.date_time != ZIP_TIMESTAMP:
                    fail(EXIT_MISMATCH, "entry_timestamp")
                if info.create_system != 3:
                    fail(EXIT_MISMATCH, "entry_platform")
                if info.external_attr != ZIP_EXTERNAL_ATTR:
                    fail(EXIT_MISMATCH, "entry_mode")
                if info.extra != b"" or info.comment != b"":
                    fail(EXIT_MISMATCH, "entry_metadata")
                payloads.append(archive.read(info))
    except (KeyError, RuntimeError, zipfile.BadZipFile):
        fail(EXIT_MISMATCH, "invalid_package")
    if sha256_bytes(package_data) != sha256_file(path):
        fail(EXIT_UNSAFE_BOUNDARY, "changing_package")
    dll_data, manifest_data = payloads
    if len(dll_data) < 2 or dll_data[:2] != b"MZ":
        fail(EXIT_MISMATCH, "invalid_managed_dll")
    validate_manifest_bytes(manifest_data)
    return dll_data, manifest_data


def main(operation: Callable[[], dict[str, Any]]) -> NoReturn:
    sys.exit(run_cli(operation))
