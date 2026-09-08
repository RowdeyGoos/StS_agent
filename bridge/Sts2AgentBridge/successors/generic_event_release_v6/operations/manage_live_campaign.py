#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import contextlib
import ctypes
import errno
import hashlib
import json
import os
import pwd
import stat
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    ToolFailure,
    absolute_path,
    fail,
    main,
    require_hex_64,
)

CAMPAIGN_ID = "GENERIC-EVENT-V6-SMOKE-V1"
STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-generic-event-v6-smoke-v1"
LEGACY_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-r0i-batched-bridge-smoke-v1"
LEGACY_OVERLAY_ROOT_NAME = "Sts2AgentBridge"
ARTIFACT_ROOT = Path("/private/tmp/sts-generic-event-v6-release")
CONFIGURATIONS = {
    "generic": b'{"schema_version":"generic_event_v6_transport_config_v1","enabled":true,"flow_kind":"generic","bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}',
}
CONFIG_HASHES = {flow: hashlib.sha256(data).hexdigest() for flow, data in CONFIGURATIONS.items()}
ITEM_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-item-v1-collection-smoke-v1"
ITEM_OVERLAY_ROOT_NAME = "Sts2AgentBridgeItemV1"
ROOM_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-room-flows-v1-smoke-v1"
ROOM_OVERLAY_ROOT_NAME = "Sts2AgentBridgeRoomFlowsV1"
DIAGNOSTIC_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-shop-diagnostic-v1-smoke-v1"
DIAGNOSTIC_OVERLAY_ROOT_NAME = "Sts2AgentBridgeShopDiagnosticV1"
SHOP_MAP_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-shop-map-permission-v1-smoke-v1"
CARD_SELECTION_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-card-selection-v1-smoke-v1"
CARD_COMPLETION_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-card-selection-completion-v1-smoke-v1"
CARD_OVERLAY_ROOT_NAME = "Sts2AgentBridgeCardSelectionV1"
GENERIC_V5_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-generic-event-v5-smoke-v1"
GENERIC_V5_OVERLAY_ROOT_NAME = "Sts2AgentBridgeGenericEventV5"
GENERIC_V4_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-generic-event-v4-smoke-v1"
GENERIC_V4_OVERLAY_ROOT_NAME = "Sts2AgentBridgeGenericEventV4"
GENERIC_V3_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-generic-event-v3-smoke-v1"
GENERIC_V3_OVERLAY_ROOT_NAME = "Sts2AgentBridgeGenericEventV3"
GENERIC_V2_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-generic-event-v2-smoke-v1"
GENERIC_V2_OVERLAY_ROOT_NAME = "Sts2AgentBridgeGenericEventV2"
GENERIC_V1_STATE_ROOT_NAME = "Sts2AgentBridgeCampaign-generic-event-v1-smoke-v1"
GENERIC_V1_OVERLAY_ROOT_NAME = "Sts2AgentBridgeGenericEventV1"


def configuration_bytes(flow_kind: str) -> bytes:
    if type(flow_kind) is not str or flow_kind not in CONFIGURATIONS:
        fail(EXIT_MISMATCH, "invalid_flow_kind")
    return CONFIGURATIONS[flow_kind]

LOWER_HEX = frozenset(b"0123456789abcdef")

STATE_FILE_NAME = "state.json"
STATE_NEXT_NAME = "state.next"
STAGING_NAME = "staging"
STAGED_OPERATOR_NAME = "operator"
STAGED_OVERLAY_NAME = "overlay"
QUARANTINE_NAME = "quarantine"
QUARANTINE_OVERLAY_NAME = "overlay"
QUARANTINE_OPERATOR_NAME = "operator"
OVERLAY_DLL_NAME = "Sts2AgentBridgeGenericEventV6.dll"
OVERLAY_MANIFEST_NAME = "Sts2AgentBridgeGenericEventV6.json"
CONFIG_FILE_NAME = "config.json"
CREDENTIAL_FILE_NAME = "credential.hex"


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ArtifactPolicy:
    dll: ArtifactSpec
    manifest: ArtifactSpec
    archive: ArtifactSpec


CANONICAL_ARTIFACTS = ArtifactPolicy(
    dll=ArtifactSpec(
        OVERLAY_DLL_NAME,
        379392,
        "96723ba26f9f64a74cd0f1d8ae4217191a13410c5629a1feedc26a44f3890c2f",
    ),
    manifest=ArtifactSpec(
        OVERLAY_MANIFEST_NAME,
        352,
        "c7480a29c041269b9b0991826fa2fd4408cc8673a4427dac9ca299c9396ece62",
    ),
    archive=ArtifactSpec(
        "Sts2AgentBridgeGenericEventV6-1.0.0.zip",
        380172,
        "ecc08551b583fdc64e3fab87bbf6bf3a0ba09ef9e8d5521a824261ee6c97ddd3",
    ),
)


@dataclass(frozen=True)
class CampaignLayout:
    user_profile: Path
    application_support: Path
    macos_root: Path
    mods_parent: Path
    overlay_root: Path
    operator_parent: Path
    config_root: Path
    state_root: Path
    staging_root: Path
    staged_operator: Path
    staged_overlay: Path
    quarantine_root: Path
    quarantine_overlay: Path
    quarantine_operator: Path


@dataclass(frozen=True)
class CampaignState:
    flow_kind: str
    config_sha256: str
    phase: str
    generation: int
    mods_parent_created: bool
    operator_location: str
    overlay_location: str
    purge_progress: int
    campaign_device: int
    campaign_inode: int
    state_file_device: int
    state_file_inode: int
    application_support_device: int
    application_support_inode: int
    macos_root_device: int
    macos_root_inode: int
    mods_parent_device: int
    mods_parent_inode: int
    staging_device: int
    staging_inode: int
    quarantine_device: int
    quarantine_inode: int
    operator_device: int
    operator_inode: int
    config_device: int
    config_inode: int
    config_file_device: int
    config_file_inode: int
    credential_device: int
    credential_inode: int
    overlay_unit_device: int
    overlay_unit_inode: int
    overlay_device: int
    overlay_inode: int
    dll_device: int
    dll_inode: int
    manifest_device: int
    manifest_inode: int


@dataclass(frozen=True)
class CreatedEntry:
    path: Path
    device: int
    inode: int
    is_directory: bool


class CreationTracker:
    def __init__(self) -> None:
        self._entries: list[CreatedEntry] = []

    def record(self, path: Path, metadata: os.stat_result, is_directory: bool) -> None:
        self._entries.append(
            CreatedEntry(path, metadata.st_dev, metadata.st_ino, is_directory)
        )

    def consume(self, path: Path) -> None:
        for index in range(len(self._entries) - 1, -1, -1):
            if self._entries[index].path == path:
                del self._entries[index]
                return
        fail(EXIT_INTERNAL, "internal_failure")

    def rollback(self, preserve_file_until_end: Path | None = None) -> bool:
        ordered = list(reversed(self._entries))
        for entry in ordered:
            try:
                metadata = entry.path.lstat()
            except FileNotFoundError:
                return False
            except OSError:
                return False
            if (
                metadata.st_dev != entry.device
                or metadata.st_ino != entry.inode
                or stat.S_ISDIR(metadata.st_mode) != entry.is_directory
            ):
                return False
            if entry.is_directory:
                expected_children = {
                    child.path.name
                    for child in self._entries
                    if child.path.parent == entry.path
                }
                try:
                    actual_children: set[str] = set()
                    with os.scandir(entry.path) as children:
                        for child in children:
                            if child.name not in expected_children:
                                return False
                            actual_children.add(child.name)
                except OSError:
                    return False
                if actual_children != expected_children:
                    return False

        if preserve_file_until_end is not None:
            preserved = [
                entry for entry in ordered if entry.path == preserve_file_until_end
            ]
            preserved_parent = [
                entry
                for entry in ordered
                if entry.path == preserve_file_until_end.parent
            ]
            if preserved:
                ordered = [
                    entry
                    for entry in ordered
                    if entry not in preserved and entry not in preserved_parent
                ] + preserved + preserved_parent

        complete = True
        for entry in ordered:
            try:
                metadata = entry.path.lstat()
                if (
                    metadata.st_dev != entry.device
                    or metadata.st_ino != entry.inode
                    or stat.S_ISDIR(metadata.st_mode) != entry.is_directory
                ):
                    complete = False
                    break
                if entry.is_directory:
                    os.rmdir(entry.path)
                else:
                    os.unlink(entry.path)
            except OSError:
                complete = False
                break
        return complete


def _parse_effective_uid(value: str) -> int:
    if value != "501":
        fail(EXIT_INVALID_INVOCATION, "invalid_effective_uid")
    return 501


def parse_args(
    arguments: list[str] | None = None,
) -> tuple[str, Path, int, Path | None, str | None, str | None]:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) not in (8, 10):
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    if values[0] != "--mode" or values[2] != "--user-profile" or values[4] != "--effective-uid":
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    mode = values[1]
    if mode not in ("install", "quarantine", "purge"):
        fail(EXIT_INVALID_INVOCATION, "invalid_mode")
    flow_kind = None
    if mode == "install":
        if len(values) != 10 or values[8] != "--flow-kind" or values[9] not in ("generic",):
            fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
        flow_kind = values[9]
    elif len(values) != 8:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    expected_final_flag = (
        "--artifact-root" if mode == "install" else "--expected-state-sha256"
    )
    if values[6] != expected_final_flag:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")

    profile = absolute_path(values[3], "user_profile")
    artifact_root = (
        absolute_path(values[7], "artifact_root")
        if mode == "install"
        else None
    )
    expected_state_sha256 = (
        None
        if mode == "install"
        else require_hex_64(values[7], "state_sha256")
    )
    return (
        mode,
        profile,
        _parse_effective_uid(values[5]),
        artifact_root,
        expected_state_sha256,
        flow_kind,
    )


def _require_identity(user_profile: Path, supplied_uid: int) -> int:
    if sys.platform != "darwin":
        fail(EXIT_UNSAFE_BOUNDARY, "unsupported_platform")
    effective_uid = os.geteuid()
    if supplied_uid != 501 or effective_uid != 501 or supplied_uid != effective_uid:
        fail(EXIT_UNSAFE_BOUNDARY, "effective_uid_mismatch")
    try:
        os_home = os.path.normpath(pwd.getpwuid(effective_uid).pw_dir)
    except KeyError:
        fail(EXIT_UNSAFE_BOUNDARY, "user_identity_unavailable")
    if str(user_profile) != os_home:
        fail(EXIT_UNSAFE_BOUNDARY, "user_profile_mismatch")
    if "\r" in os_home or "\n" in os_home:
        fail(EXIT_UNSAFE_BOUNDARY, "unsafe_user_profile")
    return effective_uid


def _production_layout(user_profile: Path) -> CampaignLayout:
    application_support = user_profile / "Library" / "Application Support"
    install_root = application_support / "Steam" / "steamapps" / "common" / "Slay the Spire 2"
    macos_root = install_root / "SlayTheSpire2.app" / "Contents" / "MacOS"
    mods_parent = macos_root / "mods"
    overlay_root = mods_parent / "Sts2AgentBridgeGenericEventV6"
    operator_parent = application_support / "Sts2AgentBridge"
    config_root = operator_parent / "generic_event_v6"
    state_root = application_support / STATE_ROOT_NAME
    staging_root = state_root / STAGING_NAME
    quarantine_root = state_root / QUARANTINE_NAME
    return CampaignLayout(
        user_profile=user_profile,
        application_support=application_support,
        macos_root=macos_root,
        mods_parent=mods_parent,
        overlay_root=overlay_root,
        operator_parent=operator_parent,
        config_root=config_root,
        state_root=state_root,
        staging_root=staging_root,
        staged_operator=staging_root / STAGED_OPERATOR_NAME,
        staged_overlay=staging_root / STAGED_OVERLAY_NAME,
        quarantine_root=quarantine_root,
        quarantine_overlay=quarantine_root / QUARANTINE_OVERLAY_NAME,
        quarantine_operator=quarantine_root / QUARANTINE_OPERATOR_NAME,
    )


def _require_production_artifact_parent() -> None:
    if ARTIFACT_ROOT.parent != Path("/private/tmp"):
        fail(EXIT_INTERNAL, "internal_failure")
    _require_directory(ARTIFACT_ROOT.parent, 0, 0o1777)


def _components(path: Path) -> list[Path]:
    values: list[Path] = []
    current = path
    while current != current.parent:
        values.append(current)
        current = current.parent
    values.reverse()
    return values


def _reject_symlink_components(path: Path) -> None:
    for component in _components(path):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            fail(EXIT_UNSAFE_BOUNDARY, "missing_path_component")
        except OSError:
            fail(EXIT_UNSAFE_BOUNDARY, "unreadable_path_component")
        if stat.S_ISLNK(metadata.st_mode):
            fail(EXIT_UNSAFE_BOUNDARY, "symlink_path_component")


def _require_directory(
    path: Path,
    uid: int | None,
    exact_mode: int | None,
    *,
    reject_writable: bool = False,
) -> os.stat_result:
    _reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "missing_directory")
    if not stat.S_ISDIR(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, "non_directory")
    if uid is not None and metadata.st_uid != uid:
        fail(EXIT_UNSAFE_BOUNDARY, "owner_mismatch")
    mode = stat.S_IMODE(metadata.st_mode)
    if exact_mode is not None and mode != exact_mode:
        fail(EXIT_UNSAFE_BOUNDARY, "mode_mismatch")
    if reject_writable and mode & 0o022:
        fail(EXIT_UNSAFE_BOUNDARY, "unsafe_directory_mode")
    _require_no_granting_acl_path(path, metadata, is_directory=True)
    return metadata


def _optional_lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "path_check_failed")


def _require_absent(path: Path) -> None:
    _reject_symlink_components(path.parent)
    metadata = _optional_lstat(path)
    if metadata is None:
        return
    if stat.S_ISLNK(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, "symlink_target")
    fail(EXIT_UNSAFE_BOUNDARY, "target_exists")


def _require_absent_without_parent_read(path: Path) -> None:
    metadata = _optional_lstat(path)
    if metadata is None:
        return
    if stat.S_ISLNK(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, "symlink_target")
    fail(EXIT_UNSAFE_BOUNDARY, "target_exists")


def _identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _same_object(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        metadata.st_uid,
    )


def _require_no_granting_acl_fd(descriptor: int) -> None:
    if sys.platform != "darwin":
        fail(EXIT_UNSAFE_BOUNDARY, "acl_inspection_unsupported")
    try:
        library = ctypes.CDLL(None, use_errno=True)
        get_acl = library.acl_get_fd_np
        get_acl.argtypes = [ctypes.c_int, ctypes.c_int]
        get_acl.restype = ctypes.c_void_p
        get_entry = library.acl_get_entry
        get_entry.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        get_entry.restype = ctypes.c_int
        get_tag = library.acl_get_tag_type
        get_tag.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        get_tag.restype = ctypes.c_int
        free_acl = library.acl_free
        free_acl.argtypes = [ctypes.c_void_p]
        free_acl.restype = ctypes.c_int
        ctypes.set_errno(0)
        acl = get_acl(descriptor, 0x00000100)
    except Exception:
        fail(EXIT_UNSAFE_BOUNDARY, "acl_inspection_unsupported")
    if not acl:
        if ctypes.get_errno() == errno.ENOENT:
            return
        fail(EXIT_UNSAFE_BOUNDARY, "acl_inspection_failed")

    disposition: str | None = None
    free_failed = False
    accepted = 0
    try:
        selector = 0
        while True:
            entry = ctypes.c_void_p()
            ctypes.set_errno(0)
            result = get_entry(acl, selector, ctypes.byref(entry))
            if result == -1:
                if ctypes.get_errno() == errno.EINVAL:
                    break
                disposition = "acl_inspection_failed"
                break
            if result != 0 or not entry or accepted >= 169:
                disposition = "acl_inspection_failed"
                break
            tag = ctypes.c_int()
            if get_tag(entry, ctypes.byref(tag)) != 0:
                disposition = "acl_inspection_failed"
                break
            if tag.value == 1:
                disposition = "granting_acl"
                break
            if tag.value != 2:
                disposition = "acl_inspection_failed"
                break
            accepted += 1
            selector = -1
    except Exception:
        disposition = "acl_inspection_failed"
    finally:
        try:
            free_failed = free_acl(acl) != 0
        except Exception:
            free_failed = True
    if free_failed or disposition == "acl_inspection_failed":
        fail(EXIT_UNSAFE_BOUNDARY, "acl_inspection_failed")
    if disposition == "granting_acl":
        fail(EXIT_UNSAFE_BOUNDARY, "granting_acl")


def _require_no_granting_acl_path(
    path: Path,
    metadata: os.stat_result,
    *,
    is_directory: bool,
) -> None:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_CLOEXEC"):
        fail(EXIT_UNSAFE_BOUNDARY, "safe_open_unsupported")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    if is_directory:
        if not hasattr(os, "O_DIRECTORY"):
            fail(EXIT_UNSAFE_BOUNDARY, "safe_open_unsupported")
        flags |= os.O_DIRECTORY
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(metadata):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_acl_target")
        _require_no_granting_acl_fd(descriptor)
        opened_after = os.fstat(descriptor)
        path_after = path.lstat()
    except ToolFailure:
        raise
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "acl_inspection_failed")
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    if (
        _identity(opened_after) != _identity(metadata)
        or _identity(path_after) != _identity(metadata)
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "changing_acl_target")


def _require_recorded_directory(
    metadata: os.stat_result,
    device: int,
    inode: int,
) -> None:
    if metadata.st_dev != device or metadata.st_ino != inode:
        fail(EXIT_UNSAFE_BOUNDARY, "generated_identity_mismatch")


def _require_file_metadata(
    path: Path,
    uid: int,
    mode: int,
    *,
    size: int | None = None,
) -> os.stat_result:
    _reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "missing_generated_file")
    if not stat.S_ISREG(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, "non_regular_generated_file")
    if metadata.st_uid != uid:
        fail(EXIT_UNSAFE_BOUNDARY, "owner_mismatch")
    if metadata.st_nlink != 1:
        fail(EXIT_UNSAFE_BOUNDARY, "link_count_mismatch")
    if stat.S_IMODE(metadata.st_mode) != mode:
        fail(EXIT_UNSAFE_BOUNDARY, "mode_mismatch")
    if size is not None and metadata.st_size != size:
        fail(EXIT_MISMATCH, "file_size_mismatch")
    _require_no_granting_acl_path(path, metadata, is_directory=False)
    return metadata


def _read_stable_file(
    path: Path,
    metadata: os.stat_result,
    cap: int,
) -> bytes:
    if metadata.st_size > cap:
        fail(EXIT_MISMATCH, "file_size_mismatch")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_CLOEXEC"):
        fail(EXIT_UNSAFE_BOUNDARY, "safe_open_unsupported")
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(metadata):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_generated_file")
        _require_no_granting_acl_fd(descriptor)
        with os.fdopen(descriptor, "rb", buffering=0, closefd=True) as stream:
            descriptor = -1
            data = stream.read(cap + 1)
            opened_after = os.fstat(stream.fileno())
        path_after = path.lstat()
    except ToolFailure:
        raise
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "file_read_failed")
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    if (
        _identity(opened_after) != _identity(metadata)
        or _identity(path_after) != _identity(metadata)
        or len(data) != metadata.st_size
        or len(data) > cap
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "changing_generated_file")
    return data


def _zero(buffer: bytearray) -> None:
    for offset in range(len(buffer)):
        buffer[offset] = 0


def _read_mutable_file(
    path: Path,
    metadata: os.stat_result,
    capacity: int,
) -> bytearray:
    buffer = bytearray(capacity)
    descriptor = -1
    stream: Any | None = None
    try:
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_CLOEXEC"):
            fail(EXIT_UNSAFE_BOUNDARY, "safe_open_unsupported")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(metadata):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_generated_file")
        _require_no_granting_acl_fd(descriptor)
        stream = os.fdopen(descriptor, "rb", buffering=0, closefd=True)
        descriptor = -1
        total = 0
        while total < capacity:
            view = memoryview(buffer)[total:]
            try:
                count = stream.readinto(view)
            finally:
                view.release()
            if count is None or count == 0:
                break
            total += count
        opened_after = os.fstat(stream.fileno())
        path_after = path.lstat()
        if (
            _identity(opened_after) != _identity(metadata)
            or _identity(path_after) != _identity(metadata)
            or total != metadata.st_size
        ):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_generated_file")
        del buffer[total:]
        return buffer
    except ToolFailure:
        _zero(buffer)
        raise
    except (OSError, ValueError):
        _zero(buffer)
        fail(EXIT_UNSAFE_BOUNDARY, "file_read_failed")
    finally:
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass
        elif descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _list_exact(path: Path, expected: set[str]) -> None:
    names = _list_allowed(path, expected)
    if names != expected:
        fail(EXIT_MISMATCH, "unexpected_generated_entry")


def _list_allowed(path: Path, allowed: set[str]) -> set[str]:
    names: set[str] = set()
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.name not in allowed:
                    fail(EXIT_MISMATCH, "unexpected_generated_entry")
                names.add(entry.name)
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "directory_read_failed")
    return names


def _validate_artifacts(
    artifact_root: Path,
    uid: int,
    policy: ArtifactPolicy,
) -> tuple[bytes, bytes]:
    _require_directory(artifact_root, uid, 0o700)
    specs = (policy.dll, policy.manifest, policy.archive)
    _list_exact(artifact_root, {spec.name for spec in specs})
    payloads: dict[str, bytes] = {}
    for spec in specs:
        path = artifact_root / spec.name
        metadata = _require_file_metadata(path, uid, 0o644, size=spec.size)
        data = _read_stable_file(path, metadata, spec.size)
        if hashlib.sha256(data).hexdigest() != spec.sha256:
            fail(EXIT_MISMATCH, "artifact_hash_mismatch")
        payloads[spec.name] = data
    return payloads[policy.dll.name], payloads[policy.manifest.name]


def _state_bytes(state: CampaignState) -> bytes:
    document = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "flow_kind": state.flow_kind,
        "config_sha256": state.config_sha256,
        "phase": state.phase,
        "generation": state.generation,
        "mods_parent_created": state.mods_parent_created,
        "operator_location": state.operator_location,
        "overlay_location": state.overlay_location,
        "purge_progress": state.purge_progress,
        "campaign_device": state.campaign_device,
        "campaign_inode": state.campaign_inode,
        "state_file_device": state.state_file_device,
        "state_file_inode": state.state_file_inode,
        "application_support_device": state.application_support_device,
        "application_support_inode": state.application_support_inode,
        "macos_root_device": state.macos_root_device,
        "macos_root_inode": state.macos_root_inode,
        "mods_parent_device": state.mods_parent_device,
        "mods_parent_inode": state.mods_parent_inode,
        "staging_device": state.staging_device,
        "staging_inode": state.staging_inode,
        "quarantine_device": state.quarantine_device,
        "quarantine_inode": state.quarantine_inode,
        "operator_device": state.operator_device,
        "operator_inode": state.operator_inode,
        "config_device": state.config_device,
        "config_inode": state.config_inode,
        "config_file_device": state.config_file_device,
        "config_file_inode": state.config_file_inode,
        "credential_device": state.credential_device,
        "credential_inode": state.credential_inode,
        "overlay_unit_device": state.overlay_unit_device,
        "overlay_unit_inode": state.overlay_unit_inode,
        "overlay_device": state.overlay_device,
        "overlay_inode": state.overlay_inode,
        "dll_device": state.dll_device,
        "dll_inode": state.dll_inode,
        "manifest_device": state.manifest_device,
        "manifest_inode": state.manifest_inode,
    }
    return json.dumps(document, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _state_sha256(state: CampaignState) -> str:
    return hashlib.sha256(_state_bytes(state)).hexdigest()


def _require_expected_state_sha256(
    state: CampaignState,
    expected_state_sha256: str,
) -> None:
    if _state_sha256(state) != expected_state_sha256:
        fail(EXIT_MISMATCH, "state_hash_mismatch")


def _validate_state(state: CampaignState) -> None:
    if (type(state.flow_kind) is not str or state.flow_kind not in CONFIGURATIONS or
            state.config_sha256 != CONFIG_HASHES[state.flow_kind]):
        fail(EXIT_MISMATCH, "invalid_state")
    if state.phase not in (
        "preparing",
        "activating",
        "installed",
        "quarantining",
        "quarantined",
        "purging",
    ):
        fail(EXIT_MISMATCH, "invalid_state")
    if type(state.generation) is not int or state.generation <= 0:
        fail(EXIT_MISMATCH, "invalid_state")
    if type(state.purge_progress) is not int or state.purge_progress < 0:
        fail(EXIT_MISMATCH, "invalid_state")
    locations = {"unbound", "staging", "live", "quarantine", "removed"}
    if (
        state.operator_location not in locations
        or state.overlay_location not in locations
    ):
        fail(EXIT_MISMATCH, "invalid_state")

    always_positive = (
        state.campaign_device,
        state.campaign_inode,
        state.state_file_device,
        state.state_file_inode,
        state.application_support_device,
        state.application_support_inode,
        state.macos_root_device,
        state.macos_root_inode,
    )
    if any(type(value) is not int or value <= 0 for value in always_positive):
        fail(EXIT_MISMATCH, "invalid_state")
    if state.mods_parent_created:
        if state.mods_parent_device != 0 or state.mods_parent_inode != 0:
            fail(EXIT_MISMATCH, "invalid_state")
    elif any(
        type(value) is not int or value <= 0
        for value in (state.mods_parent_device, state.mods_parent_inode)
    ):
        fail(EXIT_MISMATCH, "invalid_state")

    bound_identities = (
        state.staging_device,
        state.staging_inode,
        state.operator_device,
        state.operator_inode,
        state.config_device,
        state.config_inode,
        state.config_file_device,
        state.config_file_inode,
        state.credential_device,
        state.credential_inode,
        state.overlay_unit_device,
        state.overlay_unit_inode,
        state.overlay_device,
        state.overlay_inode,
        state.dll_device,
        state.dll_inode,
        state.manifest_device,
        state.manifest_inode,
    )
    if any(type(value) is not int for value in bound_identities):
        fail(EXIT_MISMATCH, "invalid_state")
    all_bound_zero = all(value == 0 for value in bound_identities)
    all_bound_positive = all(value > 0 for value in bound_identities)
    if not (all_bound_zero or all_bound_positive):
        fail(EXIT_MISMATCH, "invalid_state")
    if state.phase != "preparing" and not all_bound_positive:
        fail(EXIT_MISMATCH, "invalid_state")
    if all_bound_zero and (
        state.operator_location != "unbound"
        or state.overlay_location != "unbound"
    ):
        fail(EXIT_MISMATCH, "invalid_state")
    if all_bound_positive and (
        state.operator_location == "unbound"
        or state.overlay_location == "unbound"
    ):
        fail(EXIT_MISMATCH, "invalid_state")

    quarantine_identity = (state.quarantine_device, state.quarantine_inode)
    if all_bound_zero:
        if quarantine_identity != (0, 0):
            fail(EXIT_MISMATCH, "invalid_state")
    elif any(
        type(value) is not int or value <= 0 for value in quarantine_identity
    ):
        fail(EXIT_MISMATCH, "invalid_state")

    if state.phase == "preparing":
        if state.purge_progress != 0:
            fail(EXIT_MISMATCH, "invalid_state")
        if all_bound_positive and (
            state.operator_location != "staging"
            or state.overlay_location != "staging"
        ):
            fail(EXIT_MISMATCH, "invalid_state")
    elif state.phase == "activating":
        valid = (
            ("staging", "staging"),
            ("live", "staging"),
            ("live", "live"),
        )
        if (
            (state.operator_location, state.overlay_location) not in valid
            or state.purge_progress != 0
        ):
            fail(EXIT_MISMATCH, "invalid_state")
    elif state.phase == "installed":
        if (
            state.operator_location != "live"
            or state.overlay_location != "live"
            or state.purge_progress != 0
        ):
            fail(EXIT_MISMATCH, "invalid_state")
    elif state.phase == "quarantining":
        valid = (
            ("live", "live"),
            ("live", "quarantine"),
            ("quarantine", "quarantine"),
        )
        if (
            (state.operator_location, state.overlay_location) not in valid
            or state.purge_progress != 0
        ):
            fail(EXIT_MISMATCH, "invalid_state")
    elif state.phase == "quarantined":
        if (
            state.operator_location != "quarantine"
            or state.overlay_location != "quarantine"
            or state.purge_progress != 0
        ):
            fail(EXIT_MISMATCH, "invalid_state")
    elif state.phase == "purging":
        maximum_progress = 9 if state.mods_parent_created else 8
        overlay_removed_at = 8 if state.mods_parent_created else 7
        if (
            state.purge_progress > maximum_progress
            or state.operator_location
            != ("removed" if state.purge_progress >= 4 else "quarantine")
            or state.overlay_location
            != (
                "removed"
                if state.purge_progress >= overlay_removed_at
                else "quarantine"
            )
        ):
            fail(EXIT_MISMATCH, "invalid_state")

    if state.phase == "preparing":
        expected_generation = 1 if all_bound_zero else 2
    elif state.phase == "activating":
        expected_generation = {
            ("staging", "staging"): 3,
            ("live", "staging"): 4,
            ("live", "live"): 5,
        }[(state.operator_location, state.overlay_location)]
    elif state.phase == "installed":
        expected_generation = 6
    elif state.phase == "quarantining":
        expected_generation = {
            ("live", "live"): 7,
            ("live", "quarantine"): 8,
            ("quarantine", "quarantine"): 9,
        }[(state.operator_location, state.overlay_location)]
    elif state.phase == "quarantined":
        expected_generation = 10
    else:
        expected_generation = 11 + state.purge_progress
    if state.generation != expected_generation:
        fail(EXIT_MISMATCH, "invalid_state")


def _parse_state(data: bytes) -> CampaignState:
    try:
        document = json.loads(data.decode("ascii"))
    except (UnicodeError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, "invalid_state")
    expected_keys = {
        "schema_version",
        "campaign_id",
        "flow_kind",
        "config_sha256",
        "phase",
        "generation",
        "mods_parent_created",
        "operator_location",
        "overlay_location",
        "purge_progress",
        "campaign_device",
        "campaign_inode",
        "state_file_device",
        "state_file_inode",
        "application_support_device",
        "application_support_inode",
        "macos_root_device",
        "macos_root_inode",
        "mods_parent_device",
        "mods_parent_inode",
        "staging_device",
        "staging_inode",
        "quarantine_device",
        "quarantine_inode",
        "operator_device",
        "operator_inode",
        "config_device",
        "config_inode",
        "config_file_device",
        "config_file_inode",
        "credential_device",
        "credential_inode",
        "overlay_unit_device",
        "overlay_unit_inode",
        "overlay_device",
        "overlay_inode",
        "dll_device",
        "dll_inode",
        "manifest_device",
        "manifest_inode",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        fail(EXIT_MISMATCH, "invalid_state")
    if document.get("schema_version") != 1 or document.get("campaign_id") != CAMPAIGN_ID:
        fail(EXIT_MISMATCH, "invalid_state")
    if type(document.get("mods_parent_created")) is not bool:
        fail(EXIT_MISMATCH, "invalid_state")
    identity_keys = (
        "campaign_device",
        "campaign_inode",
        "state_file_device",
        "state_file_inode",
        "application_support_device",
        "application_support_inode",
        "macos_root_device",
        "macos_root_inode",
        "mods_parent_device",
        "mods_parent_inode",
        "staging_device",
        "staging_inode",
        "quarantine_device",
        "quarantine_inode",
        "operator_device",
        "operator_inode",
        "config_device",
        "config_inode",
        "config_file_device",
        "config_file_inode",
        "credential_device",
        "credential_inode",
        "overlay_unit_device",
        "overlay_unit_inode",
        "overlay_device",
        "overlay_inode",
        "dll_device",
        "dll_inode",
        "manifest_device",
        "manifest_inode",
    )
    if any(type(document.get(key)) is not int for key in identity_keys):
        fail(EXIT_MISMATCH, "invalid_state")
    if (
        type(document.get("generation")) is not int
        or type(document.get("purge_progress")) is not int
        or not isinstance(document.get("phase"), str)
        or not isinstance(document.get("operator_location"), str)
        or not isinstance(document.get("overlay_location"), str)
    ):
        fail(EXIT_MISMATCH, "invalid_state")
    state = CampaignState(
        flow_kind=document["flow_kind"],
        config_sha256=document["config_sha256"],
        phase=document["phase"],
        generation=document["generation"],
        mods_parent_created=document["mods_parent_created"],
        operator_location=document["operator_location"],
        overlay_location=document["overlay_location"],
        purge_progress=document["purge_progress"],
        campaign_device=document["campaign_device"],
        campaign_inode=document["campaign_inode"],
        state_file_device=document["state_file_device"],
        state_file_inode=document["state_file_inode"],
        application_support_device=document["application_support_device"],
        application_support_inode=document["application_support_inode"],
        macos_root_device=document["macos_root_device"],
        macos_root_inode=document["macos_root_inode"],
        mods_parent_device=document["mods_parent_device"],
        mods_parent_inode=document["mods_parent_inode"],
        staging_device=document["staging_device"],
        staging_inode=document["staging_inode"],
        quarantine_device=document["quarantine_device"],
        quarantine_inode=document["quarantine_inode"],
        operator_device=document["operator_device"],
        operator_inode=document["operator_inode"],
        config_device=document["config_device"],
        config_inode=document["config_inode"],
        config_file_device=document["config_file_device"],
        config_file_inode=document["config_file_inode"],
        credential_device=document["credential_device"],
        credential_inode=document["credential_inode"],
        overlay_unit_device=document["overlay_unit_device"],
        overlay_unit_inode=document["overlay_unit_inode"],
        overlay_device=document["overlay_device"],
        overlay_inode=document["overlay_inode"],
        dll_device=document["dll_device"],
        dll_inode=document["dll_inode"],
        manifest_device=document["manifest_device"],
        manifest_inode=document["manifest_inode"],
    )
    _validate_state(state)
    if data != _state_bytes(state):
        fail(EXIT_MISMATCH, "noncanonical_state")
    return state


def _read_state_file(
    layout: CampaignLayout,
    uid: int,
) -> tuple[CampaignState, os.stat_result]:
    root_metadata = _require_directory(layout.state_root, uid, 0o700)
    state_path = layout.state_root / STATE_FILE_NAME
    metadata = _require_file_metadata(state_path, uid, 0o600)
    data = _read_stable_file(state_path, metadata, 4096)
    state = _parse_state(data)
    _require_recorded_directory(
        root_metadata,
        state.campaign_device,
        state.campaign_inode,
    )
    if (
        metadata.st_dev != state.state_file_device
        or metadata.st_ino != state.state_file_inode
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "generated_identity_mismatch")
    return state, metadata


def _read_state(layout: CampaignLayout, uid: int) -> tuple[CampaignState, os.stat_result]:
    state, metadata = _read_state_file(layout, uid)
    names = _list_allowed(
        layout.state_root,
        {STATE_FILE_NAME, STAGING_NAME, QUARANTINE_NAME},
    )
    if state.phase in ("preparing", "activating"):
        if not {STATE_FILE_NAME}.issubset(names) or not names.issubset(
            {STATE_FILE_NAME, STAGING_NAME, QUARANTINE_NAME}
        ):
            fail(EXIT_MISMATCH, "unexpected_generated_entry")
        if STAGING_NAME in names:
            staging = _require_directory(layout.staging_root, uid, 0o700)
            if state.staging_device <= 0:
                fail(EXIT_MISMATCH, "unbound_generated_tree")
            _require_recorded_directory(
                staging,
                state.staging_device,
                state.staging_inode,
            )
        if QUARANTINE_NAME in names:
            quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
            if state.quarantine_device <= 0:
                fail(EXIT_MISMATCH, "unbound_generated_tree")
            _require_recorded_directory(
                quarantine,
                state.quarantine_device,
                state.quarantine_inode,
            )
    elif state.phase == "installed":
        if names != {STATE_FILE_NAME, QUARANTINE_NAME}:
            fail(EXIT_MISMATCH, "unexpected_generated_entry")
        quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
        _require_recorded_directory(
            quarantine,
            state.quarantine_device,
            state.quarantine_inode,
        )
        _list_exact(layout.quarantine_root, set())
    elif state.phase in ("quarantining", "quarantined"):
        if names != {STATE_FILE_NAME, QUARANTINE_NAME}:
            fail(EXIT_MISMATCH, "unexpected_generated_entry")
        quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
        _require_recorded_directory(
            quarantine,
            state.quarantine_device,
            state.quarantine_inode,
        )
    else:
        if not {STATE_FILE_NAME}.issubset(names) or not names.issubset(
            {STATE_FILE_NAME, QUARANTINE_NAME}
        ):
            fail(EXIT_MISMATCH, "unexpected_generated_entry")
        if QUARANTINE_NAME in names:
            quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
            _require_recorded_directory(
                quarantine,
                state.quarantine_device,
                state.quarantine_inode,
            )
    return state, metadata


def _write_all(descriptor: int, data: bytes | bytearray) -> None:
    offset = 0
    while offset < len(data):
        view = memoryview(data)[offset:]
        try:
            written = os.write(descriptor, view)
        finally:
            view.release()
        if written <= 0:
            fail(EXIT_UNSAFE_BOUNDARY, "file_write_failed")
        offset += written


def _create_directory(path: Path, uid: int, tracker: CreationTracker) -> os.stat_result:
    try:
        os.mkdir(path, 0o700)
        metadata = path.lstat()
    except FileExistsError:
        fail(EXIT_UNSAFE_BOUNDARY, "target_exists")
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "directory_create_failed")
    tracker.record(path, metadata, True)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != uid
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "created_directory_mismatch")
    _require_no_granting_acl_path(path, metadata, is_directory=True)
    return metadata


def _open_new_file(
    path: Path,
    uid: int,
    tracker: CreationTracker,
) -> tuple[int, os.stat_result]:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_CLOEXEC"):
        fail(EXIT_UNSAFE_BOUNDARY, "safe_open_unsupported")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags, 0o600)
        metadata = os.fstat(descriptor)
    except FileExistsError:
        fail(EXIT_UNSAFE_BOUNDARY, "target_exists")
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "file_create_failed")
    tracker.record(path, metadata, False)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != uid
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        try:
            os.close(descriptor)
        except OSError:
            pass
        fail(EXIT_UNSAFE_BOUNDARY, "created_file_mismatch")
    _require_no_granting_acl_fd(descriptor)
    return descriptor, metadata


def _create_file(
    path: Path,
    data: bytes | bytearray,
    final_mode: int,
    uid: int,
    tracker: CreationTracker,
) -> os.stat_result:
    descriptor = -1
    opened: os.stat_result | None = None
    try:
        descriptor, opened = _open_new_file(path, uid, tracker)
        _write_all(descriptor, data)
        os.fsync(descriptor)
        os.fchmod(descriptor, final_mode)
        os.fsync(descriptor)
        _require_no_granting_acl_fd(descriptor)
        after = os.fstat(descriptor)
    except ToolFailure:
        raise
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "file_write_failed")
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    if opened is None:
        fail(EXIT_INTERNAL, "internal_failure")
    try:
        path_after = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "created_file_mismatch")
    if (
        _same_object(after) != _same_object(opened)
        or _identity(after) != _identity(path_after)
        or after.st_nlink != 1
        or after.st_size != len(data)
        or stat.S_IMODE(after.st_mode) != final_mode
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "created_file_mismatch")
    return after


def _create_state_record(
    path: Path,
    state: CampaignState,
    uid: int,
    tracker: CreationTracker,
) -> tuple[CampaignState, os.stat_result]:
    if state.state_file_device != 0 or state.state_file_inode != 0:
        fail(EXIT_INTERNAL, "internal_failure")
    descriptor = -1
    opened: os.stat_result | None = None
    bound: CampaignState | None = None
    data = b""
    try:
        descriptor, opened = _open_new_file(path, uid, tracker)
        bound = replace(
            state,
            state_file_device=opened.st_dev,
            state_file_inode=opened.st_ino,
        )
        _validate_state(bound)
        data = _state_bytes(bound)
        _write_all(descriptor, data)
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        _require_no_granting_acl_fd(descriptor)
        after = os.fstat(descriptor)
    except ToolFailure:
        raise
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "state_write_failed")
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    if opened is None or bound is None:
        fail(EXIT_INTERNAL, "internal_failure")
    try:
        path_after = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "state_write_failed")
    if (
        _identity(after) != _identity(path_after)
        or _same_object(after) != _same_object(opened)
        or after.st_nlink != 1
        or after.st_size != len(data)
        or stat.S_IMODE(after.st_mode) != 0o600
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "state_write_failed")
    return bound, after


def _fill_csprng_hex(output: bytearray) -> None:
    if len(output) != 64:
        fail(EXIT_INTERNAL, "internal_failure")
    raw = bytearray(32)
    descriptor = -1
    try:
        descriptor = os.open("/dev/urandom", os.O_RDONLY | os.O_CLOEXEC)
        metadata = os.fstat(descriptor)
        if not stat.S_ISCHR(metadata.st_mode):
            fail(EXIT_UNSAFE_BOUNDARY, "csprng_unavailable")
        total = 0
        while total < len(raw):
            view = memoryview(raw)[total:]
            try:
                count = os.readv(descriptor, [view])
            finally:
                view.release()
            if count <= 0:
                fail(EXIT_UNSAFE_BOUNDARY, "csprng_unavailable")
            total += count
        alphabet = b"0123456789abcdef"
        for index, value in enumerate(raw):
            output[index * 2] = alphabet[value >> 4]
            output[index * 2 + 1] = alphabet[value & 0x0F]
    except ToolFailure:
        raise
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "csprng_unavailable")
    finally:
        _zero(raw)
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _create_credential(
    path: Path,
    uid: int,
    tracker: CreationTracker,
    fill_credential: Callable[[bytearray], None],
) -> os.stat_result:
    credential = bytearray(64)
    try:
        fill_credential(credential)
        if len(credential) != 64 or any(value not in LOWER_HEX for value in credential):
            fail(EXIT_UNSAFE_BOUNDARY, "csprng_unavailable")
        return _create_file(path, credential, 0o600, uid, tracker)
    finally:
        _zero(credential)


def _paths_overlap(first: Path, second: Path) -> bool:
    try:
        common = Path(os.path.commonpath((str(first), str(second))))
    except ValueError:
        return False
    return common == first or common == second


@contextlib.contextmanager
def _private_umask() -> Iterator[None]:
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


# The definitions below are the durable campaign implementation.  They are kept
# together so every external transition uses the same state, inode, ACL, and
# fault-checkpoint rules.


def _no_fault(_checkpoint_name: str) -> None:
    return None


def _checkpoint(fault_hook: Callable[[str], None], name: str) -> None:
    fault_hook(name)


def _fsync_directory(
    path: Path,
    uid: int | None,
    exact_mode: int | None,
) -> None:
    metadata = _require_directory(path, uid, exact_mode)
    if (
        not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_CLOEXEC")
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "safe_open_unsupported")
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        opened = os.fstat(descriptor)
        if _same_object(opened) != _same_object(metadata):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_directory")
        _require_no_granting_acl_fd(descriptor)
        os.fsync(descriptor)
        opened_after = os.fstat(descriptor)
        path_after = path.lstat()
    except ToolFailure:
        raise
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "directory_sync_failed")
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    if (
        _same_object(opened_after) != _same_object(metadata)
        or _same_object(path_after) != _same_object(metadata)
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "changing_directory")


def _atomic_state_update(
    layout: CampaignLayout,
    uid: int,
    predecessor: CampaignState,
    state: CampaignState,
) -> CampaignState:
    current, current_metadata = _read_state_file(layout, uid)
    if (
        current != predecessor
        or state.flow_kind != current.flow_kind
        or state.config_sha256 != current.config_sha256
        or state.state_file_device != 0
        or state.state_file_inode != 0
        or state.generation != current.generation + 1
        or state.campaign_device != current.campaign_device
        or state.campaign_inode != current.campaign_inode
    ):
        fail(EXIT_MISMATCH, "invalid_state_transition")
    state_path = layout.state_root / STATE_FILE_NAME
    next_path = layout.state_root / STATE_NEXT_NAME
    _require_absent_without_parent_read(next_path)
    tracker = CreationTracker()
    try:
        bound, next_metadata = _create_state_record(
            next_path,
            state,
            uid,
            tracker,
        )
        current_after = state_path.lstat()
        if _identity(current_after) != _identity(current_metadata):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_state")
        os.replace(next_path, state_path)
        tracker.consume(next_path)
        _fsync_directory(layout.state_root, uid, 0o700)
        updated = _require_file_metadata(state_path, uid, 0o600)
        data = _read_stable_file(state_path, updated, 4096)
        if data != _state_bytes(bound) or _same_object(updated) != _same_object(
            next_metadata
        ):
            fail(EXIT_UNSAFE_BOUNDARY, "state_update_failed")
        loaded, loaded_metadata = _read_state_file(layout, uid)
        if loaded != bound or _identity(loaded_metadata) != _identity(updated):
            fail(EXIT_UNSAFE_BOUNDARY, "state_update_failed")
    except ToolFailure:
        tracker.rollback()
        raise
    except OSError:
        tracker.rollback()
        fail(EXIT_UNSAFE_BOUNDARY, "state_update_failed")
    return bound


def _next_state(state: CampaignState, **changes: object) -> CampaignState:
    return replace(
        state,
        generation=state.generation + 1,
        state_file_device=0,
        state_file_inode=0,
        **changes,
    )


def _require_recorded(metadata: os.stat_result, device: int, inode: int) -> None:
    if metadata.st_dev != device or metadata.st_ino != inode:
        fail(EXIT_UNSAFE_BOUNDARY, "generated_identity_mismatch")


def _validate_overlay_tree(
    root: Path,
    uid: int,
    policy: ArtifactPolicy,
) -> dict[Path, os.stat_result]:
    records: dict[Path, os.stat_result] = {}
    records[root] = _require_directory(root, uid, 0o700)
    _list_exact(root, {OVERLAY_DLL_NAME, OVERLAY_MANIFEST_NAME})
    for spec in (policy.dll, policy.manifest):
        path = root / spec.name
        metadata = _require_file_metadata(path, uid, 0o644, size=spec.size)
        data = _read_stable_file(path, metadata, spec.size)
        if hashlib.sha256(data).hexdigest() != spec.sha256:
            fail(EXIT_MISMATCH, "generated_content_mismatch")
        records[path] = metadata
    return records


def _validate_config_tree(root: Path, uid: int, flow_kind: str) -> dict[Path, os.stat_result]:
    records: dict[Path, os.stat_result] = {}
    records[root] = _require_directory(root, uid, 0o700)
    _list_exact(root, {CONFIG_FILE_NAME, CREDENTIAL_FILE_NAME})
    config_path = root / CONFIG_FILE_NAME
    config_metadata = _require_file_metadata(
        config_path,
        uid,
        0o600,
        size=len(configuration_bytes(flow_kind)),
    )
    config_data = _read_stable_file(config_path, config_metadata, len(configuration_bytes(flow_kind)))
    if config_data != configuration_bytes(flow_kind) or hashlib.sha256(config_data).hexdigest() != CONFIG_HASHES[flow_kind]:
        fail(EXIT_MISMATCH, "generated_content_mismatch")
    records[config_path] = config_metadata
    credential_path = root / CREDENTIAL_FILE_NAME
    credential_metadata = _require_file_metadata(credential_path, uid, 0o600, size=64)
    credential = _read_mutable_file(credential_path, credential_metadata, 65)
    try:
        if len(credential) != 64 or any(value not in LOWER_HEX for value in credential):
            fail(EXIT_MISMATCH, "credential_shape")
    finally:
        _zero(credential)
    records[credential_path] = credential_metadata
    return records


def _validate_operator_unit(root: Path, uid: int, flow_kind: str) -> dict[Path, os.stat_result]:
    records: dict[Path, os.stat_result] = {}
    records[root] = _require_directory(root, uid, 0o700)
    _list_exact(root, {"generic_event_v6"})
    records.update(_validate_config_tree(root / "generic_event_v6", uid, flow_kind))
    return records


def _validate_config_tree_metadata(root: Path, uid: int, flow_kind: str) -> dict[Path, os.stat_result]:
    """Validate fixed config and credential metadata without reading token bytes."""
    records: dict[Path, os.stat_result] = {}
    records[root] = _require_directory(root, uid, 0o700)
    _list_exact(root, {CONFIG_FILE_NAME, CREDENTIAL_FILE_NAME})
    config_path = root / CONFIG_FILE_NAME
    config_metadata = _require_file_metadata(
        config_path,
        uid,
        0o600,
        size=len(configuration_bytes(flow_kind)),
    )
    config_data = _read_stable_file(config_path, config_metadata, len(configuration_bytes(flow_kind)))
    if config_data != configuration_bytes(flow_kind) or hashlib.sha256(config_data).hexdigest() != CONFIG_HASHES[flow_kind]:
        fail(EXIT_MISMATCH, "generated_content_mismatch")
    records[config_path] = config_metadata
    credential_path = root / CREDENTIAL_FILE_NAME
    records[credential_path] = _require_file_metadata(
        credential_path,
        uid,
        0o600,
        size=64,
    )
    return records


def _validate_operator_unit_metadata(
    root: Path,
    uid: int,
    flow_kind: str,
) -> dict[Path, os.stat_result]:
    records: dict[Path, os.stat_result] = {}
    records[root] = _require_directory(root, uid, 0o700)
    _list_exact(root, {"generic_event_v6"})
    records.update(_validate_config_tree_metadata(root / "generic_event_v6", uid, flow_kind))
    return records


def _validate_overlay_unit(
    unit_root: Path,
    mods_parent_created: bool,
    uid: int,
    policy: ArtifactPolicy,
) -> dict[Path, os.stat_result]:
    if not mods_parent_created:
        return _validate_overlay_tree(unit_root, uid, policy)
    records: dict[Path, os.stat_result] = {}
    records[unit_root] = _require_directory(unit_root, uid, 0o700)
    _list_exact(unit_root, {"Sts2AgentBridgeGenericEventV6"})
    records.update(
        _validate_overlay_tree(unit_root / "Sts2AgentBridgeGenericEventV6", uid, policy)
    )
    return records


def _require_state_records(
    state: CampaignState,
    operator_root: Path,
    operator: dict[Path, os.stat_result],
    overlay_unit_root: Path,
    overlay: dict[Path, os.stat_result],
) -> None:
    config_root = operator_root / "generic_event_v6"
    overlay_root = (
        overlay_unit_root / "Sts2AgentBridgeGenericEventV6"
        if state.mods_parent_created
        else overlay_unit_root
    )
    bindings = (
        (operator[operator_root], state.operator_device, state.operator_inode),
        (operator[config_root], state.config_device, state.config_inode),
        (
            operator[config_root / CONFIG_FILE_NAME],
            state.config_file_device,
            state.config_file_inode,
        ),
        (
            operator[config_root / CREDENTIAL_FILE_NAME],
            state.credential_device,
            state.credential_inode,
        ),
        (
            overlay[overlay_unit_root],
            state.overlay_unit_device,
            state.overlay_unit_inode,
        ),
        (overlay[overlay_root], state.overlay_device, state.overlay_inode),
        (
            overlay[overlay_root / OVERLAY_DLL_NAME],
            state.dll_device,
            state.dll_inode,
        ),
        (
            overlay[overlay_root / OVERLAY_MANIFEST_NAME],
            state.manifest_device,
            state.manifest_inode,
        ),
    )
    for metadata, device, inode in bindings:
        _require_recorded(metadata, device, inode)


def _validate_live_parents(
    layout: CampaignLayout,
    uid: int,
    state: CampaignState,
) -> None:
    application_support = _require_directory(
        layout.application_support,
        uid,
        None,
        reject_writable=True,
    )
    macos_root = _require_directory(
        layout.macos_root,
        uid,
        None,
        reject_writable=True,
    )
    _require_recorded(
        application_support,
        state.application_support_device,
        state.application_support_inode,
    )
    _require_recorded(
        macos_root,
        state.macos_root_device,
        state.macos_root_inode,
    )
    _require_absent(layout.application_support / LEGACY_STATE_ROOT_NAME)
    _require_absent(layout.application_support / ITEM_STATE_ROOT_NAME)
    _require_absent(layout.application_support / ROOM_STATE_ROOT_NAME)
    _require_absent(layout.application_support / DIAGNOSTIC_STATE_ROOT_NAME)
    _require_absent(layout.application_support / SHOP_MAP_STATE_ROOT_NAME)
    _require_absent(layout.application_support / CARD_SELECTION_STATE_ROOT_NAME)
    _require_absent(layout.application_support / CARD_COMPLETION_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V1_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V5_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V4_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V3_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V2_STATE_ROOT_NAME)
    if not state.mods_parent_created:
        mods = _require_directory(
            layout.mods_parent,
            uid,
            None,
            reject_writable=True,
        )
        _require_recorded(mods, state.mods_parent_device, state.mods_parent_inode)
        _require_absent(layout.mods_parent / LEGACY_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / ITEM_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / ROOM_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / DIAGNOSTIC_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / CARD_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V1_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V5_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V4_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V3_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V2_OVERLAY_ROOT_NAME)


def _active_overlay_unit(layout: CampaignLayout, state: CampaignState) -> Path:
    return layout.mods_parent if state.mods_parent_created else layout.overlay_root


def _validate_installed_sources(
    layout: CampaignLayout,
    uid: int,
    state: CampaignState,
    policy: ArtifactPolicy,
) -> None:
    _validate_live_parents(layout, uid, state)
    operator = _validate_operator_unit(layout.operator_parent, uid, state.flow_kind)
    overlay_unit = _active_overlay_unit(layout, state)
    overlay = _validate_overlay_unit(
        overlay_unit,
        state.mods_parent_created,
        uid,
        policy,
    )
    _require_state_records(
        state,
        layout.operator_parent,
        operator,
        overlay_unit,
        overlay,
    )


def _require_source_absent(
    layout: CampaignLayout,
    uid: int,
    state: CampaignState,
) -> None:
    if _optional_lstat(layout.operator_parent) is not None:
        fail(EXIT_UNSAFE_BOUNDARY, "source_tree_present")
    if state.mods_parent_created:
        if _optional_lstat(layout.mods_parent) is not None:
            fail(EXIT_UNSAFE_BOUNDARY, "source_tree_present")
    else:
        mods = _require_directory(
            layout.mods_parent,
            uid,
            None,
            reject_writable=True,
        )
        _require_recorded(mods, state.mods_parent_device, state.mods_parent_inode)
        if _optional_lstat(layout.overlay_root) is not None:
            fail(EXIT_UNSAFE_BOUNDARY, "source_tree_present")


def _validate_quarantined_units(
    layout: CampaignLayout,
    uid: int,
    state: CampaignState,
    policy: ArtifactPolicy,
) -> tuple[dict[Path, os.stat_result], dict[Path, os.stat_result]]:
    quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
    _require_recorded(
        quarantine,
        state.quarantine_device,
        state.quarantine_inode,
    )
    _list_exact(
        layout.quarantine_root,
        {QUARANTINE_OPERATOR_NAME, QUARANTINE_OVERLAY_NAME},
    )
    operator = _validate_operator_unit(layout.quarantine_operator, uid, state.flow_kind)
    overlay = _validate_overlay_unit(
        layout.quarantine_overlay,
        state.mods_parent_created,
        uid,
        policy,
    )
    _require_state_records(
        state,
        layout.quarantine_operator,
        operator,
        layout.quarantine_overlay,
        overlay,
    )
    return operator, overlay


def _validate_activation_units(
    layout: CampaignLayout,
    uid: int,
    state: CampaignState,
    policy: ArtifactPolicy,
) -> None:
    if state.phase != "activating":
        fail(EXIT_INTERNAL, "internal_failure")
    loaded, _ = _read_state(layout, uid)
    if loaded != state:
        fail(EXIT_UNSAFE_BOUNDARY, "changing_state")
    _validate_live_parents(layout, uid, state)
    staging = _require_directory(layout.staging_root, uid, 0o700)
    _require_recorded(staging, state.staging_device, state.staging_inode)
    quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
    _require_recorded(
        quarantine,
        state.quarantine_device,
        state.quarantine_inode,
    )
    _list_exact(layout.quarantine_root, set())

    expected_staging: set[str] = set()
    if state.operator_location == "staging":
        expected_staging.add(STAGED_OPERATOR_NAME)
        operator_root = layout.staged_operator
    else:
        operator_root = layout.operator_parent
    if state.overlay_location == "staging":
        expected_staging.add(STAGED_OVERLAY_NAME)
        overlay_unit_root = layout.staged_overlay
    else:
        overlay_unit_root = _active_overlay_unit(layout, state)
    _list_exact(layout.staging_root, expected_staging)

    operator = _validate_operator_unit(operator_root, uid, state.flow_kind)
    overlay = _validate_overlay_unit(
        overlay_unit_root,
        state.mods_parent_created,
        uid,
        policy,
    )
    _require_state_records(
        state,
        operator_root,
        operator,
        overlay_unit_root,
        overlay,
    )


def _validate_quarantine_transition_units(
    layout: CampaignLayout,
    uid: int,
    state: CampaignState,
    policy: ArtifactPolicy,
) -> None:
    if state.phase != "quarantining":
        fail(EXIT_INTERNAL, "internal_failure")
    loaded, _ = _read_state(layout, uid)
    if loaded != state:
        fail(EXIT_UNSAFE_BOUNDARY, "changing_state")
    _validate_live_parents(layout, uid, state)
    quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
    _require_recorded(
        quarantine,
        state.quarantine_device,
        state.quarantine_inode,
    )
    expected_quarantine: set[str] = set()
    if state.operator_location == "quarantine":
        expected_quarantine.add(QUARANTINE_OPERATOR_NAME)
        operator_root = layout.quarantine_operator
    else:
        operator_root = layout.operator_parent
    if state.overlay_location == "quarantine":
        expected_quarantine.add(QUARANTINE_OVERLAY_NAME)
        overlay_unit_root = layout.quarantine_overlay
    else:
        overlay_unit_root = _active_overlay_unit(layout, state)
    _list_exact(layout.quarantine_root, expected_quarantine)

    operator = _validate_operator_unit(operator_root, uid, state.flow_kind)
    overlay = _validate_overlay_unit(
        overlay_unit_root,
        state.mods_parent_created,
        uid,
        policy,
    )
    _require_state_records(
        state,
        operator_root,
        operator,
        overlay_unit_root,
        overlay,
    )


def _dirfd_lstat(descriptor: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "rename_classification_failed")


def _rename_no_replace(
    source: Path,
    destination: Path,
    uid: int,
    expected_device: int,
    expected_inode: int,
) -> None:
    if sys.platform != "darwin":
        fail(EXIT_UNSAFE_BOUNDARY, "exclusive_rename_unsupported")
    if source.name in ("", ".", "..") or destination.name in ("", ".", ".."):
        fail(EXIT_INTERNAL, "internal_failure")
    source_parent = _require_directory(source.parent, uid, None)
    destination_parent = _require_directory(destination.parent, uid, None)
    if source_parent.st_dev != destination_parent.st_dev:
        fail(EXIT_UNSAFE_BOUNDARY, "cross_device_move")
    source_metadata = _require_directory(source, uid, 0o700)
    _require_recorded(source_metadata, expected_device, expected_inode)
    _require_absent(destination)
    source_fd = -1
    destination_fd = -1
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        source_fd = os.open(source.parent, flags)
        destination_fd = os.open(destination.parent, flags)
        if (
            _same_object(os.fstat(source_fd)) != _same_object(source_parent)
            or _same_object(os.fstat(destination_fd))
            != _same_object(destination_parent)
        ):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_rename_parent")
        library = ctypes.CDLL(None, use_errno=True)
        renameatx = library.renameatx_np
        renameatx.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameatx.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = renameatx(
            source_fd,
            os.fsencode(source.name),
            destination_fd,
            os.fsencode(destination.name),
            0x00000004 | 0x00000010,
        )
        error_number = ctypes.get_errno()
        source_after = _dirfd_lstat(source_fd, source.name)
        destination_after = _dirfd_lstat(destination_fd, destination.name)
        source_is_exact = (
            source_after is not None
            and source_after.st_dev == expected_device
            and source_after.st_ino == expected_inode
            and stat.S_ISDIR(source_after.st_mode)
        )
        destination_is_exact = (
            destination_after is not None
            and destination_after.st_dev == expected_device
            and destination_after.st_ino == expected_inode
            and stat.S_ISDIR(destination_after.st_mode)
        )
        if result != 0:
            if source_is_exact and destination_after is None:
                fail(EXIT_UNSAFE_BOUNDARY, "exclusive_rename_failed")
            if source_after is None and destination_is_exact:
                fail(EXIT_UNSAFE_BOUNDARY, "rename_ahead_of_state")
            fail(EXIT_UNSAFE_BOUNDARY, "ambiguous_rename")
        if source_after is not None or not destination_is_exact:
            fail(EXIT_UNSAFE_BOUNDARY, "ambiguous_rename")
        os.fsync(source_fd)
        os.fsync(destination_fd)
    except ToolFailure:
        raise
    except (AttributeError, OSError, TypeError):
        fail(EXIT_UNSAFE_BOUNDARY, "exclusive_rename_unsupported")
    finally:
        for descriptor in (destination_fd, source_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
    source_parent_after = _require_directory(source.parent, uid, None)
    destination_parent_after = _require_directory(destination.parent, uid, None)
    if (
        _same_object(source_parent_after) != _same_object(source_parent)
        or _same_object(destination_parent_after) != _same_object(destination_parent)
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "changing_rename_parent")
    moved = _require_directory(destination, uid, 0o700)
    _require_recorded(moved, expected_device, expected_inode)


def _install(
    flow_kind: str,
    layout: CampaignLayout,
    artifact_root: Path,
    uid: int,
    policy: ArtifactPolicy,
    fill_credential: Callable[[bytearray], None],
    rename_operation: Callable[[Path, Path, int, int, int], None],
    fault_hook: Callable[[str], None],
) -> dict[str, object]:
    if any(
        _paths_overlap(artifact_root, mutable)
        for mutable in (layout.state_root, layout.overlay_root, layout.operator_parent)
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "artifact_path_overlap")

    application_support = _require_directory(
        layout.application_support,
        uid,
        None,
        reject_writable=True,
    )
    macos_root = _require_directory(
        layout.macos_root,
        uid,
        None,
        reject_writable=True,
    )
    state_parent = _require_directory(layout.state_root.parent, None, None)
    dll_data, manifest_data = _validate_artifacts(artifact_root, uid, policy)
    _require_absent(layout.state_root)
    _require_absent(layout.application_support / LEGACY_STATE_ROOT_NAME)
    _require_absent(layout.application_support / ITEM_STATE_ROOT_NAME)
    _require_absent(layout.application_support / ROOM_STATE_ROOT_NAME)
    _require_absent(layout.application_support / DIAGNOSTIC_STATE_ROOT_NAME)
    _require_absent(layout.application_support / SHOP_MAP_STATE_ROOT_NAME)
    _require_absent(layout.application_support / CARD_SELECTION_STATE_ROOT_NAME)
    _require_absent(layout.application_support / CARD_COMPLETION_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V1_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V5_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V4_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V3_STATE_ROOT_NAME)
    _require_absent(layout.application_support / GENERIC_V2_STATE_ROOT_NAME)
    _require_absent(layout.operator_parent)

    existing_mods = _optional_lstat(layout.mods_parent)
    mods_parent_created = existing_mods is None
    if mods_parent_created:
        _require_absent_without_parent_read(layout.overlay_root)
        overlay_destination_parent = macos_root
        mods_device = 0
        mods_inode = 0
    else:
        if stat.S_ISLNK(existing_mods.st_mode):
            fail(EXIT_UNSAFE_BOUNDARY, "symlink_target")
        mods = _require_directory(
            layout.mods_parent,
            uid,
            None,
            reject_writable=True,
        )
        _require_absent(layout.overlay_root)
        _require_absent(layout.mods_parent / LEGACY_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / ITEM_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / ROOM_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / DIAGNOSTIC_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / CARD_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V1_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V5_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V4_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V3_OVERLAY_ROOT_NAME)
        _require_absent(layout.mods_parent / GENERIC_V2_OVERLAY_ROOT_NAME)
        overlay_destination_parent = mods
        mods_device = mods.st_dev
        mods_inode = mods.st_ino
    if (
        state_parent.st_dev != application_support.st_dev
        or state_parent.st_dev != overlay_destination_parent.st_dev
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "cross_device_move")

    bootstrap_tracker = CreationTracker()
    durable = False
    state: CampaignState | None = None

    def rollback_bootstrap() -> bool:
        if not bootstrap_tracker.rollback():
            return False
        try:
            _fsync_directory(layout.state_root.parent, None, None)
        except ToolFailure:
            return False
        return _optional_lstat(layout.state_root) is None

    try:
        with _private_umask():
            campaign = _create_directory(layout.state_root, uid, bootstrap_tracker)
            _fsync_directory(layout.state_root.parent, None, None)
            state = CampaignState(
                flow_kind=flow_kind,
                config_sha256=CONFIG_HASHES[flow_kind],
                phase="preparing",
                generation=1,
                mods_parent_created=mods_parent_created,
                operator_location="unbound",
                overlay_location="unbound",
                purge_progress=0,
                campaign_device=campaign.st_dev,
                campaign_inode=campaign.st_ino,
                state_file_device=0,
                state_file_inode=0,
                application_support_device=application_support.st_dev,
                application_support_inode=application_support.st_ino,
                macos_root_device=macos_root.st_dev,
                macos_root_inode=macos_root.st_ino,
                mods_parent_device=mods_device,
                mods_parent_inode=mods_inode,
                staging_device=0,
                staging_inode=0,
                quarantine_device=0,
                quarantine_inode=0,
                operator_device=0,
                operator_inode=0,
                config_device=0,
                config_inode=0,
                config_file_device=0,
                config_file_inode=0,
                credential_device=0,
                credential_inode=0,
                overlay_unit_device=0,
                overlay_unit_inode=0,
                overlay_device=0,
                overlay_inode=0,
                dll_device=0,
                dll_inode=0,
                manifest_device=0,
                manifest_inode=0,
            )
            state, _ = _create_state_record(
                layout.state_root / STATE_FILE_NAME,
                state,
                uid,
                bootstrap_tracker,
            )
            durable = True
            _fsync_directory(layout.state_root, uid, 0o700)
        loaded, _ = _read_state(layout, uid)
        if loaded != state:
            fail(EXIT_MISMATCH, "invalid_state")
        _checkpoint(fault_hook, "install_after_preparing_state")

        staging_tracker = CreationTracker()
        with _private_umask():
            staging = _create_directory(layout.staging_root, uid, staging_tracker)
            quarantine = _create_directory(
                layout.quarantine_root,
                uid,
                staging_tracker,
            )
            operator = _create_directory(
                layout.staged_operator,
                uid,
                staging_tracker,
            )
            staged_config = layout.staged_operator / "generic_event_v6"
            config = _create_directory(staged_config, uid, staging_tracker)
            config_file = _create_file(
                staged_config / CONFIG_FILE_NAME,
                configuration_bytes(flow_kind),
                0o600,
                uid,
                staging_tracker,
            )
            credential_file = _create_credential(
                staged_config / CREDENTIAL_FILE_NAME,
                uid,
                staging_tracker,
                fill_credential,
            )
            overlay_unit = _create_directory(
                layout.staged_overlay,
                uid,
                staging_tracker,
            )
            if mods_parent_created:
                staged_overlay_root = layout.staged_overlay / "Sts2AgentBridgeGenericEventV6"
                overlay = _create_directory(
                    staged_overlay_root,
                    uid,
                    staging_tracker,
                )
            else:
                staged_overlay_root = layout.staged_overlay
                overlay = overlay_unit
            dll = _create_file(
                staged_overlay_root / OVERLAY_DLL_NAME,
                dll_data,
                0o644,
                uid,
                staging_tracker,
            )
            manifest = _create_file(
                staged_overlay_root / OVERLAY_MANIFEST_NAME,
                manifest_data,
                0o644,
                uid,
                staging_tracker,
            )
        for directory in (
            staged_config,
            layout.staged_operator,
            staged_overlay_root,
            layout.staged_overlay,
            layout.quarantine_root,
            layout.staging_root,
            layout.state_root,
        ):
            _fsync_directory(directory, uid, 0o700)

        bound = _next_state(
            state,
            operator_location="staging",
            overlay_location="staging",
            staging_device=staging.st_dev,
            staging_inode=staging.st_ino,
            quarantine_device=quarantine.st_dev,
            quarantine_inode=quarantine.st_ino,
            operator_device=operator.st_dev,
            operator_inode=operator.st_ino,
            config_device=config.st_dev,
            config_inode=config.st_ino,
            config_file_device=config_file.st_dev,
            config_file_inode=config_file.st_ino,
            credential_device=credential_file.st_dev,
            credential_inode=credential_file.st_ino,
            overlay_unit_device=overlay_unit.st_dev,
            overlay_unit_inode=overlay_unit.st_ino,
            overlay_device=overlay.st_dev,
            overlay_inode=overlay.st_ino,
            dll_device=dll.st_dev,
            dll_inode=dll.st_ino,
            manifest_device=manifest.st_dev,
            manifest_inode=manifest.st_ino,
        )
        bound = _atomic_state_update(layout, uid, state, bound)
        state = bound
        staged_operator_records = _validate_operator_unit(layout.staged_operator, uid, state.flow_kind)
        staged_overlay_records = _validate_overlay_unit(
            layout.staged_overlay,
            state.mods_parent_created,
            uid,
            policy,
        )
        _require_state_records(
            state,
            layout.staged_operator,
            staged_operator_records,
            layout.staged_overlay,
            staged_overlay_records,
        )
        _checkpoint(fault_hook, "install_after_inventory_state")

        activating = _next_state(state, phase="activating")
        activating = _atomic_state_update(layout, uid, state, activating)
        state = activating
        _checkpoint(fault_hook, "install_after_activating_state")

        _validate_activation_units(layout, uid, state, policy)
        rename_operation(
            layout.staged_operator,
            layout.operator_parent,
            uid,
            state.operator_device,
            state.operator_inode,
        )
        _checkpoint(fault_hook, "install_after_operator_rename")
        operator_live = _next_state(state, operator_location="live")
        operator_live = _atomic_state_update(layout, uid, state, operator_live)
        state = operator_live
        _checkpoint(fault_hook, "install_after_operator_state")

        _validate_activation_units(layout, uid, state, policy)
        overlay_destination = _active_overlay_unit(layout, state)
        rename_operation(
            layout.staged_overlay,
            overlay_destination,
            uid,
            state.overlay_unit_device,
            state.overlay_unit_inode,
        )
        _checkpoint(fault_hook, "install_after_overlay_rename")
        overlay_live = _next_state(state, overlay_location="live")
        overlay_live = _atomic_state_update(layout, uid, state, overlay_live)
        state = overlay_live
        _checkpoint(fault_hook, "install_after_overlay_state")

        _list_exact(layout.staging_root, set())
        staging_now = _require_directory(layout.staging_root, uid, 0o700)
        _require_recorded(staging_now, state.staging_device, state.staging_inode)
        _rmdir_snapshot(layout.staging_root, staging_now, uid)
        _checkpoint(fault_hook, "install_after_staging_rmdir")

        _validate_installed_sources(layout, uid, state, policy)
        _list_exact(layout.state_root, {STATE_FILE_NAME, QUARANTINE_NAME})
        _list_exact(layout.quarantine_root, set())
        installed = _next_state(state, phase="installed")
        installed = _atomic_state_update(layout, uid, state, installed)
        state = installed
        _checkpoint(fault_hook, "install_after_installed_state")
        loaded, _ = _read_state(layout, uid)
        if loaded != state:
            fail(EXIT_MISMATCH, "invalid_state")
        final_state_sha256 = _state_sha256(loaded)
    except KeyboardInterrupt:
        if not durable:
            if not rollback_bootstrap():
                fail(EXIT_UNSAFE_BOUNDARY, "install_rollback_incomplete")
        raise
    except ToolFailure:
        if not durable:
            if not rollback_bootstrap():
                fail(EXIT_UNSAFE_BOUNDARY, "install_rollback_incomplete")
            raise
        fail(EXIT_UNSAFE_BOUNDARY, "install_partial")
    except Exception:
        if not durable:
            if not rollback_bootstrap():
                fail(EXIT_UNSAFE_BOUNDARY, "install_rollback_incomplete")
            fail(EXIT_INTERNAL, "install_failed")
        fail(EXIT_UNSAFE_BOUNDARY, "install_partial")

    return {
        "schema_version": 1,
        "status": "passed",
        "campaign_id": CAMPAIGN_ID,
        "mode": "install",
        "phase": "installed",
        "mods_parent_created": mods_parent_created,
        "state_sha256": final_state_sha256,
    }


def _quarantine(
    layout: CampaignLayout,
    uid: int,
    policy: ArtifactPolicy,
    expected_state_sha256: str,
    rename_operation: Callable[[Path, Path, int, int, int], None],
    fault_hook: Callable[[str], None],
) -> dict[str, object]:
    state, _ = _read_state(layout, uid)
    _require_expected_state_sha256(state, expected_state_sha256)
    if state.phase != "installed":
        fail(EXIT_MISMATCH, "wrong_phase")
    _validate_installed_sources(layout, uid, state, policy)
    quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
    _require_recorded(
        quarantine,
        state.quarantine_device,
        state.quarantine_inode,
    )
    _list_exact(layout.quarantine_root, set())
    try:
        quarantining = _next_state(
            state,
            phase="quarantining",
        )
        quarantining = _atomic_state_update(layout, uid, state, quarantining)
        state = quarantining
        _checkpoint(fault_hook, "quarantine_after_quarantining_state")

        _validate_quarantine_transition_units(layout, uid, state, policy)
        active_overlay = _active_overlay_unit(layout, state)
        rename_operation(
            active_overlay,
            layout.quarantine_overlay,
            uid,
            state.overlay_unit_device,
            state.overlay_unit_inode,
        )
        _checkpoint(fault_hook, "quarantine_after_overlay_rename")
        overlay_quarantined = _next_state(
            state,
            overlay_location="quarantine",
        )
        overlay_quarantined = _atomic_state_update(
            layout,
            uid,
            state,
            overlay_quarantined,
        )
        state = overlay_quarantined
        _checkpoint(fault_hook, "quarantine_after_overlay_state")

        _validate_quarantine_transition_units(layout, uid, state, policy)
        rename_operation(
            layout.operator_parent,
            layout.quarantine_operator,
            uid,
            state.operator_device,
            state.operator_inode,
        )
        _checkpoint(fault_hook, "quarantine_after_operator_rename")
        operator_quarantined = _next_state(
            state,
            operator_location="quarantine",
        )
        operator_quarantined = _atomic_state_update(
            layout,
            uid,
            state,
            operator_quarantined,
        )
        state = operator_quarantined
        _checkpoint(fault_hook, "quarantine_after_operator_state")

        _validate_live_parents(layout, uid, state)
        _require_source_absent(layout, uid, state)
        _validate_quarantined_units(layout, uid, state, policy)
        final = _next_state(state, phase="quarantined")
        final = _atomic_state_update(layout, uid, state, final)
        state = final
        _checkpoint(fault_hook, "quarantine_after_quarantined_state")
        loaded, _ = _read_state(layout, uid)
        if loaded != state:
            fail(EXIT_MISMATCH, "invalid_state")
        final_state_sha256 = _state_sha256(loaded)
    except KeyboardInterrupt:
        raise
    except ToolFailure:
        fail(EXIT_UNSAFE_BOUNDARY, "quarantine_partial")
    except Exception:
        fail(EXIT_UNSAFE_BOUNDARY, "quarantine_partial")

    return {
        "schema_version": 1,
        "status": "passed",
        "campaign_id": CAMPAIGN_ID,
        "mode": "quarantine",
        "phase": "quarantined",
        "state_sha256": final_state_sha256,
    }


def _unlink_snapshot(
    path: Path,
    metadata: os.stat_result,
    uid: int,
) -> None:
    parent = _require_directory(path.parent, uid, 0o700)
    current = _require_file_metadata(
        path,
        uid,
        stat.S_IMODE(metadata.st_mode),
        size=metadata.st_size,
    )
    if _identity(current) != _identity(metadata):
        fail(EXIT_UNSAFE_BOUNDARY, "purge_target_changed")
    descriptor = -1
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        descriptor = os.open(path.parent, flags)
        if _same_object(os.fstat(descriptor)) != _same_object(parent):
            fail(EXIT_UNSAFE_BOUNDARY, "purge_parent_changed")
        relative = _dirfd_lstat(descriptor, path.name)
        if relative is None or _identity(relative) != _identity(metadata):
            fail(EXIT_UNSAFE_BOUNDARY, "purge_target_changed")
        os.unlink(path.name, dir_fd=descriptor)
        os.fsync(descriptor)
        if _dirfd_lstat(descriptor, path.name) is not None:
            fail(EXIT_UNSAFE_BOUNDARY, "purge_failed")
    except ToolFailure:
        raise
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "purge_failed")
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    parent_after = _require_directory(path.parent, uid, 0o700)
    if _same_object(parent_after) != _same_object(parent):
        fail(EXIT_UNSAFE_BOUNDARY, "purge_parent_changed")


def _rmdir_snapshot(
    path: Path,
    metadata: os.stat_result,
    uid: int,
    *,
    parent_uid: int | None = None,
    parent_mode: int | None = 0o700,
) -> None:
    effective_parent_uid = uid if parent_uid is None and parent_mode == 0o700 else parent_uid
    parent = _require_directory(path.parent, effective_parent_uid, parent_mode)
    current = _require_directory(path, uid, stat.S_IMODE(metadata.st_mode))
    if _same_object(current) != _same_object(metadata):
        fail(EXIT_UNSAFE_BOUNDARY, "purge_target_changed")
    _list_exact(path, set())
    descriptor = -1
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        descriptor = os.open(path.parent, flags)
        if _same_object(os.fstat(descriptor)) != _same_object(parent):
            fail(EXIT_UNSAFE_BOUNDARY, "purge_parent_changed")
        relative = _dirfd_lstat(descriptor, path.name)
        if (
            relative is None
            or relative.st_dev != metadata.st_dev
            or relative.st_ino != metadata.st_ino
            or not stat.S_ISDIR(relative.st_mode)
        ):
            fail(EXIT_UNSAFE_BOUNDARY, "purge_target_changed")
        os.rmdir(path.name, dir_fd=descriptor)
        os.fsync(descriptor)
        if _dirfd_lstat(descriptor, path.name) is not None:
            fail(EXIT_UNSAFE_BOUNDARY, "purge_failed")
    except ToolFailure:
        raise
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "purge_failed")
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    parent_after = _require_directory(path.parent, effective_parent_uid, parent_mode)
    if _same_object(parent_after) != _same_object(parent):
        fail(EXIT_UNSAFE_BOUNDARY, "purge_parent_changed")


def _validate_purge_remainder(
    layout: CampaignLayout,
    uid: int,
    state: CampaignState,
    operator: dict[Path, os.stat_result],
    overlay: dict[Path, os.stat_result],
) -> None:
    if state.phase != "purging":
        fail(EXIT_INTERNAL, "internal_failure")
    loaded, _ = _read_state_file(layout, uid)
    if loaded != state:
        fail(EXIT_UNSAFE_BOUNDARY, "changing_state")

    progress = state.purge_progress
    final_progress = 9 if state.mods_parent_created else 8
    overlay_removed_at = 8 if state.mods_parent_created else 7
    expected_state_entries = {STATE_FILE_NAME}
    if progress < final_progress:
        expected_state_entries.add(QUARANTINE_NAME)
    _list_exact(layout.state_root, expected_state_entries)

    operator_root = layout.quarantine_operator
    config_root = operator_root / "generic_event_v6"
    overlay_unit_root = layout.quarantine_overlay
    overlay_root = (
        overlay_unit_root / "Sts2AgentBridgeGenericEventV6"
        if state.mods_parent_created
        else overlay_unit_root
    )

    if progress >= final_progress:
        _require_absent_without_parent_read(layout.quarantine_root)
        return
    quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
    _require_recorded(
        quarantine,
        state.quarantine_device,
        state.quarantine_inode,
    )
    expected_quarantine: set[str] = set()
    if progress < 4:
        expected_quarantine.add(QUARANTINE_OPERATOR_NAME)
    if progress < overlay_removed_at:
        expected_quarantine.add(QUARANTINE_OVERLAY_NAME)
    _list_exact(layout.quarantine_root, expected_quarantine)

    if progress < 4:
        current_operator = _require_directory(operator_root, uid, 0o700)
        _require_recorded(
            current_operator,
            state.operator_device,
            state.operator_inode,
        )
        expected_operator = {"generic_event_v6"} if progress < 3 else set()
        _list_exact(operator_root, expected_operator)
        if progress < 3:
            current_config = _require_directory(config_root, uid, 0o700)
            _require_recorded(
                current_config,
                state.config_device,
                state.config_inode,
            )
            expected_config: set[str] = set()
            if progress < 2:
                expected_config.add(CONFIG_FILE_NAME)
            if progress < 1:
                expected_config.add(CREDENTIAL_FILE_NAME)
            _list_exact(config_root, expected_config)
            for name in expected_config:
                path = config_root / name
                original = operator[path]
                current = _require_file_metadata(path, uid, 0o600)
                if _identity(current) != _identity(original):
                    fail(EXIT_UNSAFE_BOUNDARY, "purge_target_changed")

    if progress < overlay_removed_at:
        current_unit = _require_directory(overlay_unit_root, uid, 0o700)
        _require_recorded(
            current_unit,
            state.overlay_unit_device,
            state.overlay_unit_inode,
        )
        if state.mods_parent_created:
            expected_unit = {"Sts2AgentBridgeGenericEventV6"} if progress < 7 else set()
            _list_exact(overlay_unit_root, expected_unit)
            overlay_tree_exists = progress < 7
        else:
            overlay_tree_exists = True
        if overlay_tree_exists:
            current_overlay = _require_directory(overlay_root, uid, 0o700)
            _require_recorded(
                current_overlay,
                state.overlay_device,
                state.overlay_inode,
            )
            expected_overlay: set[str] = set()
            if progress < 6:
                expected_overlay.add(OVERLAY_DLL_NAME)
            if progress < 5:
                expected_overlay.add(OVERLAY_MANIFEST_NAME)
            _list_exact(overlay_root, expected_overlay)
            for name in expected_overlay:
                path = overlay_root / name
                original = overlay[path]
                current = _require_file_metadata(path, uid, 0o644)
                if _identity(current) != _identity(original):
                    fail(EXIT_UNSAFE_BOUNDARY, "purge_target_changed")


def _purge(
    layout: CampaignLayout,
    uid: int,
    policy: ArtifactPolicy,
    expected_state_sha256: str,
    fault_hook: Callable[[str], None],
) -> dict[str, object]:
    state, _ = _read_state(layout, uid)
    _require_expected_state_sha256(state, expected_state_sha256)
    if state.phase != "quarantined":
        fail(EXIT_MISMATCH, "wrong_phase")
    _validate_live_parents(layout, uid, state)
    _require_source_absent(layout, uid, state)
    operator, overlay = _validate_quarantined_units(layout, uid, state, policy)
    purging = _next_state(state, phase="purging")
    purging = _atomic_state_update(layout, uid, state, purging)
    state = purging
    _checkpoint(fault_hook, "purge_after_purging_state")

    def require_no_active_target(*, validate_remainder: bool = True) -> None:
        _validate_live_parents(layout, uid, state)
        _require_source_absent(layout, uid, state)
        if validate_remainder:
            _validate_purge_remainder(layout, uid, state, operator, overlay)

    def advance(name: str, **changes: object) -> None:
        nonlocal state
        updated = _next_state(
            state,
            purge_progress=state.purge_progress + 1,
            **changes,
        )
        updated = _atomic_state_update(layout, uid, state, updated)
        state = updated
        _checkpoint(fault_hook, name)

    operator_root = layout.quarantine_operator
    config_root = operator_root / "generic_event_v6"
    overlay_unit_root = layout.quarantine_overlay
    overlay_root = (
        overlay_unit_root / "Sts2AgentBridgeGenericEventV6"
        if state.mods_parent_created
        else overlay_unit_root
    )
    try:
        require_no_active_target()
        _unlink_snapshot(
            config_root / CREDENTIAL_FILE_NAME,
            operator[config_root / CREDENTIAL_FILE_NAME],
            uid,
        )
        _checkpoint(fault_hook, "purge_after_credential_unlink")
        advance("purge_after_progress_1_state")

        require_no_active_target()
        _unlink_snapshot(
            config_root / CONFIG_FILE_NAME,
            operator[config_root / CONFIG_FILE_NAME],
            uid,
        )
        _checkpoint(fault_hook, "purge_after_config_unlink")
        advance("purge_after_progress_2_state")

        require_no_active_target()
        _rmdir_snapshot(config_root, operator[config_root], uid)
        _checkpoint(fault_hook, "purge_after_config_rmdir")
        advance("purge_after_progress_3_state")

        require_no_active_target()
        _rmdir_snapshot(operator_root, operator[operator_root], uid)
        _checkpoint(fault_hook, "purge_after_operator_rmdir")
        advance(
            "purge_after_progress_4_state",
            operator_location="removed",
        )

        require_no_active_target()
        _unlink_snapshot(
            overlay_root / OVERLAY_MANIFEST_NAME,
            overlay[overlay_root / OVERLAY_MANIFEST_NAME],
            uid,
        )
        _checkpoint(fault_hook, "purge_after_manifest_unlink")
        advance("purge_after_progress_5_state")

        require_no_active_target()
        _unlink_snapshot(
            overlay_root / OVERLAY_DLL_NAME,
            overlay[overlay_root / OVERLAY_DLL_NAME],
            uid,
        )
        _checkpoint(fault_hook, "purge_after_dll_unlink")
        advance("purge_after_progress_6_state")

        require_no_active_target()
        _rmdir_snapshot(overlay_root, overlay[overlay_root], uid)
        _checkpoint(fault_hook, "purge_after_overlay_rmdir")
        if state.mods_parent_created:
            advance("purge_after_progress_7_state")
            require_no_active_target()
            _rmdir_snapshot(
                overlay_unit_root,
                overlay[overlay_unit_root],
                uid,
            )
            _checkpoint(fault_hook, "purge_after_overlay_unit_rmdir")
            advance(
                "purge_after_progress_8_state",
                overlay_location="removed",
            )
        else:
            advance(
                "purge_after_progress_7_state",
                overlay_location="removed",
            )

        require_no_active_target()
        quarantine = _require_directory(layout.quarantine_root, uid, 0o700)
        _require_recorded(
            quarantine,
            state.quarantine_device,
            state.quarantine_inode,
        )
        _rmdir_snapshot(layout.quarantine_root, quarantine, uid)
        _checkpoint(fault_hook, "purge_after_quarantine_rmdir")
        advance(
            "purge_after_final_progress_state",
            operator_location="removed",
            overlay_location="removed",
        )

        require_no_active_target()
        state_path = layout.state_root / STATE_FILE_NAME
        state_metadata = _require_file_metadata(state_path, uid, 0o600)
        campaign = _require_directory(layout.state_root, uid, 0o700)
        _require_recorded(campaign, state.campaign_device, state.campaign_inode)
        _list_exact(layout.state_root, {STATE_FILE_NAME})
        _unlink_snapshot(state_path, state_metadata, uid)
        _checkpoint(fault_hook, "purge_after_state_unlink")
        require_no_active_target(validate_remainder=False)
        _rmdir_snapshot(
            layout.state_root,
            campaign,
            uid,
            parent_uid=uid,
            parent_mode=None,
        )
        _checkpoint(fault_hook, "purge_after_campaign_rmdir")
        if _optional_lstat(layout.state_root) is not None:
            fail(EXIT_UNSAFE_BOUNDARY, "purge_failed")
        require_no_active_target(validate_remainder=False)
    except KeyboardInterrupt:
        raise
    except (ToolFailure, Exception):
        fail(EXIT_UNSAFE_BOUNDARY, "purge_partial")

    return {
        "schema_version": 1,
        "status": "passed",
        "campaign_id": CAMPAIGN_ID,
        "mode": "purge",
        "phase": "absent",
        "generated_files_removed": 4,
    }


def _run(
    mode: str,
    layout: CampaignLayout,
    uid: int,
    artifact_root: Path | None = None,
    expected_state_sha256: str | None = None,
    *,
    flow_kind: str | None = None,
    policy: ArtifactPolicy = CANONICAL_ARTIFACTS,
    fill_credential: Callable[[bytearray], None] = _fill_csprng_hex,
    rename_operation: Callable[[Path, Path, int, int, int], None] = _rename_no_replace,
    fault_hook: Callable[[str], None] = _no_fault,
) -> dict[str, object]:
    if mode == "install":
        if flow_kind not in ("generic",):
            fail(EXIT_INVALID_INVOCATION, "missing_flow_kind")
        if artifact_root is None:
            fail(EXIT_INVALID_INVOCATION, "missing_artifact_root")
        if expected_state_sha256 is not None:
            fail(EXIT_INVALID_INVOCATION, "unexpected_state_sha256")
        return _install(
            flow_kind,
            layout,
            artifact_root,
            uid,
            policy,
            fill_credential,
            rename_operation,
            fault_hook,
        )
    if flow_kind is not None:
        fail(EXIT_INVALID_INVOCATION, "unexpected_flow_kind")
    if artifact_root is not None:
        fail(EXIT_INVALID_INVOCATION, "unexpected_artifact_root")
    if expected_state_sha256 is None:
        fail(EXIT_INVALID_INVOCATION, "missing_state_sha256")
    if mode == "quarantine":
        return _quarantine(
            layout,
            uid,
            policy,
            expected_state_sha256,
            rename_operation,
            fault_hook,
        )
    if mode == "purge":
        return _purge(layout, uid, policy, expected_state_sha256, fault_hook)
    fail(EXIT_INVALID_INVOCATION, "invalid_mode")


def _operation() -> dict[str, object]:
    (
        mode,
        user_profile,
        supplied_uid,
        artifact_root,
        expected_state_sha256,
        flow_kind,
    ) = parse_args()
    uid = _require_identity(user_profile, supplied_uid)
    if mode == "install" and artifact_root != ARTIFACT_ROOT:
        fail(EXIT_UNSAFE_BOUNDARY, "artifact_root_mismatch")
    _require_production_artifact_parent()
    layout = _production_layout(user_profile)
    return _run(
        mode,
        layout,
        uid,
        artifact_root,
        expected_state_sha256,
        flow_kind=flow_kind,
    )


def require_no_granting_acl_fd(descriptor: int) -> None:
    """Apply the manager's bounded deny-only ACL policy to an open descriptor."""
    _require_no_granting_acl_fd(descriptor)


def validate_installed_for_client(
    expected_state_sha256: str,
) -> tuple[CampaignLayout, CampaignState]:
    """Read-only validation for the fixed live client; credential bytes stay unread."""
    expected = require_hex_64(expected_state_sha256, "state_sha256")
    if sys.platform != "darwin":
        fail(EXIT_UNSAFE_BOUNDARY, "unsupported_platform")
    uid = os.geteuid()
    if uid != 501:
        fail(EXIT_UNSAFE_BOUNDARY, "effective_uid_mismatch")
    try:
        home = os.path.normpath(pwd.getpwuid(uid).pw_dir)
    except KeyError:
        fail(EXIT_UNSAFE_BOUNDARY, "user_identity_unavailable")
    if "\r" in home or "\n" in home:
        fail(EXIT_UNSAFE_BOUNDARY, "unsafe_user_profile")
    profile = Path(home)
    layout = _production_layout(profile)
    state, _ = _read_state(layout, uid)
    _require_expected_state_sha256(state, expected)
    if state.phase != "installed":
        fail(EXIT_MISMATCH, "wrong_phase")
    _validate_live_parents(layout, uid, state)
    operator = _validate_operator_unit_metadata(layout.operator_parent, uid, state.flow_kind)
    overlay_unit = _active_overlay_unit(layout, state)
    overlay = _validate_overlay_unit(
        overlay_unit,
        state.mods_parent_created,
        uid,
        CANONICAL_ARTIFACTS,
    )
    _require_state_records(
        state,
        layout.operator_parent,
        operator,
        overlay_unit,
        overlay,
    )
    return layout, state


def operation() -> dict[str, object]:
    try:
        return _operation()
    except KeyboardInterrupt:
        fail(EXIT_INTERNAL, "interrupted")
    except ToolFailure:
        raise
    except Exception:
        fail(EXIT_INTERNAL, "internal_failure")


if __name__ == "__main__":
    main(operation)
