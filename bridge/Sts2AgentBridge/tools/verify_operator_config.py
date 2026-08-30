#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import pwd
import re
import stat
import subprocess
import sys
from pathlib import Path

from tool_common import (
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    absolute_path,
    fail,
    main,
    reject_symlink_components,
    require_hex_64,
)

ENABLED_CONFIG = b'{"schema_version":"live_probe_v0_config_v1","enabled":true,"bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}'
DISABLED_CONFIG = b'{"schema_version":"live_probe_v0_config_v1","enabled":false,"bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}'
KNOWN_CONFIGS = {
    hashlib.sha256(ENABLED_CONFIG).hexdigest(): ENABLED_CONFIG,
    hashlib.sha256(DISABLED_CONFIG).hexdigest(): DISABLED_CONFIG,
}
LOWER_HEX_CREDENTIAL = re.compile(rb"[0-9a-f]{64}\Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-profile", required=True)
    parser.add_argument("--config-root", required=True)
    parser.add_argument("--expected-config-sha256", required=True)
    parser.add_argument("--effective-uid", required=True, type=int)
    return parser.parse_args()


def require_identity(user_profile: Path, supplied_uid: int) -> int:
    effective_uid = os.geteuid()
    if supplied_uid != effective_uid:
        fail(EXIT_UNSAFE_BOUNDARY, "effective_uid_mismatch")
    try:
        os_home = os.path.normpath(pwd.getpwuid(effective_uid).pw_dir)
    except KeyError:
        fail(EXIT_UNSAFE_BOUNDARY, "user_identity_unavailable")
    if str(user_profile) != os_home:
        fail(EXIT_UNSAFE_BOUNDARY, "user_profile_mismatch")
    return effective_uid


def reject_acl(path: Path) -> None:
    if sys.platform != "darwin":
        fail(EXIT_UNSAFE_BOUNDARY, "acl_check_unsupported")
    try:
        completed = subprocess.run(
            ["/bin/ls", "-lde", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            encoding="utf-8",
            timeout=2,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        fail(EXIT_UNSAFE_BOUNDARY, "acl_check_failed")
    if completed.returncode != 0:
        fail(EXIT_UNSAFE_BOUNDARY, "acl_check_failed")
    lines = completed.stdout.splitlines()
    if not lines:
        fail(EXIT_UNSAFE_BOUNDARY, "acl_check_failed")
    mode_field = lines[0].split(maxsplit=1)[0]
    has_acl_marker = mode_field.endswith("+")
    saw_acl_entry = False
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped and stripped[0].isdigit() and ":" in stripped:
            saw_acl_entry = True
            fields = stripped.split()
            if "allow" in fields:
                fail(EXIT_UNSAFE_BOUNDARY, "granting_acl")
            if "deny" not in fields:
                fail(EXIT_UNSAFE_BOUNDARY, "acl_check_failed")
    if has_acl_marker and not saw_acl_entry:
        fail(EXIT_UNSAFE_BOUNDARY, "granting_acl")


def require_directory_metadata(path: Path, uid: int, mode: int | None) -> None:
    reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "missing_config_component")
    if not stat.S_ISDIR(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, "non_directory_config_component")
    if metadata.st_uid != uid:
        fail(EXIT_UNSAFE_BOUNDARY, "config_owner")
    if mode is not None and stat.S_IMODE(metadata.st_mode) != mode:
        fail(EXIT_UNSAFE_BOUNDARY, "config_directory_mode")
    reject_acl(path)


def require_file_metadata(path: Path, uid: int) -> os.stat_result:
    reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "missing_config_file")
    if not stat.S_ISREG(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, "non_regular_config_file")
    if metadata.st_uid != uid:
        fail(EXIT_UNSAFE_BOUNDARY, "config_owner")
    if metadata.st_nlink != 1:
        fail(EXIT_UNSAFE_BOUNDARY, "config_link_count")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        fail(EXIT_UNSAFE_BOUNDARY, "config_file_mode")
    reject_acl(path)
    return metadata


def stable_read(path: Path, metadata: os.stat_result, cap: int) -> bytes:
    if metadata.st_size > cap:
        fail(EXIT_MISMATCH, "config_file_size")
    try:
        with path.open("rb") as stream:
            data = stream.read(cap + 1)
        after = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "config_read_failed")
    before_identity = (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_identity != after_identity or len(data) != metadata.st_size:
        fail(EXIT_UNSAFE_BOUNDARY, "changing_config_file")
    if len(data) > cap:
        fail(EXIT_MISMATCH, "config_file_size")
    return data


def zero_mutable_buffer(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


def stable_read_mutable(path: Path, metadata: os.stat_result, cap: int) -> bytearray:
    if metadata.st_size > cap:
        fail(EXIT_MISMATCH, "config_file_size")
    data = bytearray(metadata.st_size + 1)
    transferred = False
    try:
        try:
            with path.open("rb", buffering=0) as stream:
                read_count = stream.readinto(data)
            after = path.lstat()
        except OSError:
            fail(EXIT_UNSAFE_BOUNDARY, "config_read_failed")
        before_identity = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
        )
        after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if (
            before_identity != after_identity
            or read_count != metadata.st_size
            or read_count > cap
        ):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_config_file")
        del data[read_count:]
        transferred = True
        return data
    finally:
        if not transferred:
            zero_mutable_buffer(data)


def operation() -> dict[str, object]:
    args = parse_args()
    user_profile = absolute_path(args.user_profile, "user_profile")
    config_root = absolute_path(args.config_root, "config_root")
    expected_hash = require_hex_64(args.expected_config_sha256, "config_sha256")

    uid = require_identity(user_profile, args.effective_uid)
    expected_root = user_profile / "Library" / "Application Support" / "Sts2AgentBridge" / "r0a"
    if str(config_root) != str(expected_root):
        fail(EXIT_UNSAFE_BOUNDARY, "config_root_mismatch")
    if "\n" in str(config_root) or "\r" in str(config_root):
        fail(EXIT_UNSAFE_BOUNDARY, "unsafe_config_path")

    require_directory_metadata(user_profile / "Library", uid, None)
    require_directory_metadata(user_profile / "Library" / "Application Support", uid, None)
    require_directory_metadata(user_profile / "Library" / "Application Support" / "Sts2AgentBridge", uid, 0o700)
    require_directory_metadata(config_root, uid, 0o700)

    config_path = config_root / "config.json"
    credential_path = config_root / "credential.hex"
    config_metadata = require_file_metadata(config_path, uid)
    credential_metadata = require_file_metadata(credential_path, uid)
    config_data = stable_read(config_path, config_metadata, 512)
    config_hash = hashlib.sha256(config_data).hexdigest()
    if config_hash != expected_hash or expected_hash not in KNOWN_CONFIGS:
        fail(EXIT_MISMATCH, "config_hash")
    if config_data != KNOWN_CONFIGS[expected_hash]:
        fail(EXIT_MISMATCH, "config_bytes")

    credential: bytearray | None = None
    try:
        credential = stable_read_mutable(credential_path, credential_metadata, 65)
        if LOWER_HEX_CREDENTIAL.fullmatch(credential) is None:
            fail(EXIT_MISMATCH, "credential_shape")
    finally:
        if credential is not None:
            zero_mutable_buffer(credential)

    return {
        "schema_version": 1,
        "status": "passed",
        "config_sha256": config_hash,
        "credential_shape": "valid",
    }


if __name__ == "__main__":
    main(operation)
