#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Iterator

import verify_operator_config as verifier
from tool_common import (
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    ToolFailure,
    absolute_path,
    fail,
    main,
    require_directory,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", required=True)
    return parser.parse_args()


@contextlib.contextmanager
def patched(target: object, name: str, replacement: object) -> Iterator[None]:
    original = getattr(target, name)
    setattr(target, name, replacement)
    try:
        yield
    finally:
        setattr(target, name, original)


def expect_failure(
    operation: Callable[[], object],
    exit_code: int,
    error_code: str,
) -> None:
    try:
        operation()
    except ToolFailure as failure:
        if failure.exit_code == exit_code and failure.error_code == error_code:
            return
        fail(EXIT_MISMATCH, "operator_fixture_wrong_rejection")
    fail(EXIT_MISMATCH, "operator_fixture_unexpected_pass")


class ConfigurationTree:
    def __init__(
        self,
        root: Path,
        config: bytes,
        credential: bytes | bytearray,
    ) -> None:
        self.profile = root / "synthetic-profile"
        self.library = self.profile / "Library"
        self.application_support = self.library / "Application Support"
        self.bridge_root = self.application_support / "Sts2AgentBridge"
        self.config_root = self.bridge_root / "r0a"
        self.config_path = self.config_root / "config.json"
        self.credential_path = self.config_root / "credential.hex"

        self.config_root.mkdir(parents=True, mode=0o700)
        self.bridge_root.chmod(0o700)
        self.config_root.chmod(0o700)
        self.config_path.write_bytes(config)
        self.credential_path.write_bytes(credential)
        self.config_path.chmod(0o600)
        self.credential_path.chmod(0o600)


class SyntheticMetadataPath:
    def __init__(
        self,
        metadata: object,
        *,
        data: bytes = b"",
        after: object | None = None,
        read_error: bool = False,
    ) -> None:
        self._metadata = metadata
        self._after = after if after is not None else metadata
        self._data = data
        self._read_error = read_error

    def lstat(self) -> object:
        return self._after

    def open(self, mode: str, *, buffering: int = -1) -> io.BytesIO:
        if mode != "rb" or buffering not in (-1, 0) or self._read_error:
            raise OSError("synthetic read failure")
        return io.BytesIO(self._data)


def metadata(
    mode: int,
    uid: int,
    *,
    nlink: int = 1,
    size: int = 0,
    mtime_ns: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        st_mode=mode,
        st_uid=uid,
        st_nlink=nlink,
        st_size=size,
        st_dev=11,
        st_ino=17,
        st_mtime_ns=mtime_ns,
    )


def invoke_synthetic_operation(
    tree: ConfigurationTree,
    *,
    expected_hash: str,
    config_root: Path | None = None,
    user_profile: Path | None = None,
) -> dict[str, object]:
    uid = os.geteuid()
    arguments = argparse.Namespace(
        user_profile=str(user_profile if user_profile is not None else tree.profile),
        config_root=str(config_root if config_root is not None else tree.config_root),
        expected_config_sha256=expected_hash,
        effective_uid=uid,
    )
    with contextlib.ExitStack() as stack:
        stack.enter_context(patched(verifier, "parse_args", lambda: arguments))
        stack.enter_context(patched(verifier, "require_identity", lambda _profile, _uid: uid))
        stack.enter_context(patched(verifier, "reject_acl", lambda _path: None))
        return verifier.operation()


def capture_credential_buffer() -> tuple[list[bytearray], Callable[..., bytearray]]:
    captured: list[bytearray] = []
    original = verifier.stable_read_mutable

    def recording_read(*args: object, **kwargs: object) -> bytearray:
        buffer = original(*args, **kwargs)
        captured.append(buffer)
        return buffer

    return captured, recording_read


def require_zeroed(buffers: list[bytearray], error_code: str) -> None:
    if len(buffers) != 1 or len(buffers[0]) != 64 or any(buffers[0]):
        fail(EXIT_MISMATCH, error_code)


def operation() -> dict[str, object]:
    args = parse_args()
    work_root = absolute_path(args.work_root, "work_root")
    require_directory(work_root, "work_root", empty=True)
    checks: list[str] = []

    valid_credential = bytearray("0123456789abcdef" * 4, "ascii")
    enabled_hash = hashlib.sha256(verifier.ENABLED_CONFIG).hexdigest()
    disabled_hash = hashlib.sha256(verifier.DISABLED_CONFIG).hexdigest()

    enabled = ConfigurationTree(
        work_root / "enabled",
        verifier.ENABLED_CONFIG,
        valid_credential,
    )
    payload = invoke_synthetic_operation(enabled, expected_hash=enabled_hash)
    if payload.get("status") != "passed" or payload.get("config_sha256") != enabled_hash:
        fail(EXIT_MISMATCH, "operator_fixture_positive_enabled")
    checks.append("positive_enabled")

    captured, recording_read = capture_credential_buffer()
    with patched(verifier, "stable_read_mutable", recording_read):
        payload = invoke_synthetic_operation(enabled, expected_hash=enabled_hash)
    if payload.get("status") != "passed":
        fail(EXIT_MISMATCH, "operator_fixture_zero_success_result")
    require_zeroed(captured, "operator_fixture_zero_success")
    checks.append("credential_zero_success")

    disabled = ConfigurationTree(
        work_root / "disabled",
        verifier.DISABLED_CONFIG,
        valid_credential,
    )
    verifier.zero_mutable_buffer(valid_credential)
    payload = invoke_synthetic_operation(disabled, expected_hash=disabled_hash)
    if payload.get("status") != "passed" or payload.get("config_sha256") != disabled_hash:
        fail(EXIT_MISMATCH, "operator_fixture_positive_disabled")
    checks.append("positive_disabled")

    synthetic_uid = 4242
    identity_profile = work_root / "identity-profile"
    with contextlib.ExitStack() as stack:
        stack.enter_context(patched(verifier.os, "geteuid", lambda: synthetic_uid))
        stack.enter_context(
            patched(
                verifier.pwd,
                "getpwuid",
                lambda _uid: SimpleNamespace(pw_dir=str(identity_profile)),
            )
        )
        if verifier.require_identity(identity_profile, synthetic_uid) != synthetic_uid:
            fail(EXIT_MISMATCH, "operator_fixture_identity_positive")
        expect_failure(
            lambda: verifier.require_identity(identity_profile, synthetic_uid + 1),
            EXIT_UNSAFE_BOUNDARY,
            "effective_uid_mismatch",
        )
        expect_failure(
            lambda: verifier.require_identity(work_root / "other-profile", synthetic_uid),
            EXIT_UNSAFE_BOUNDARY,
            "user_profile_mismatch",
        )
    checks.extend(("identity_positive", "identity_uid", "identity_home"))

    def missing_identity(_uid: int) -> object:
        raise KeyError("synthetic missing identity")

    with contextlib.ExitStack() as stack:
        stack.enter_context(patched(verifier.os, "geteuid", lambda: synthetic_uid))
        stack.enter_context(patched(verifier.pwd, "getpwuid", missing_identity))
        expect_failure(
            lambda: verifier.require_identity(identity_profile, synthetic_uid),
            EXIT_UNSAFE_BOUNDARY,
            "user_identity_unavailable",
        )
    checks.append("identity_unavailable")

    expect_failure(
        lambda: invoke_synthetic_operation(
            enabled,
            expected_hash=enabled_hash,
            config_root=work_root / "wrong-root",
        ),
        EXIT_UNSAFE_BOUNDARY,
        "config_root_mismatch",
    )
    checks.append("root_containment")

    newline_profile = work_root / "profile-with-newline\n"
    newline_root = newline_profile / "Library" / "Application Support" / "Sts2AgentBridge" / "r0a"
    expect_failure(
        lambda: invoke_synthetic_operation(
            enabled,
            expected_hash=enabled_hash,
            config_root=newline_root,
            user_profile=newline_profile,
        ),
        EXIT_UNSAFE_BOUNDARY,
        "unsafe_config_path",
    )
    checks.append("root_control_character")

    with contextlib.ExitStack() as stack:
        stack.enter_context(patched(verifier, "reject_symlink_components", lambda _path: None))
        stack.enter_context(patched(verifier, "reject_acl", lambda _path: None))
        wrong_owner_file = SyntheticMetadataPath(
            metadata(stat.S_IFREG | 0o600, os.geteuid() + 1)
        )
        expect_failure(
            lambda: verifier.require_file_metadata(wrong_owner_file, os.geteuid()),
            EXIT_UNSAFE_BOUNDARY,
            "config_owner",
        )
        wrong_owner_directory = SyntheticMetadataPath(
            metadata(stat.S_IFDIR | 0o700, os.geteuid() + 1)
        )
        expect_failure(
            lambda: verifier.require_directory_metadata(wrong_owner_directory, os.geteuid(), 0o700),
            EXIT_UNSAFE_BOUNDARY,
            "config_owner",
        )
    checks.extend(("file_owner", "directory_owner"))

    metadata_root = work_root / "metadata"
    metadata_root.mkdir(mode=0o700)
    wrong_mode_file = metadata_root / "wrong-mode-file"
    wrong_mode_file.write_bytes(b"x")
    wrong_mode_file.chmod(0o640)
    wrong_mode_directory = metadata_root / "wrong-mode-directory"
    wrong_mode_directory.mkdir(mode=0o750)
    hardlink_source = metadata_root / "hardlink-source"
    hardlink_source.write_bytes(b"x")
    hardlink_source.chmod(0o600)
    hardlink_peer = metadata_root / "hardlink-peer"
    os.link(hardlink_source, hardlink_peer)
    file_link = metadata_root / "file-link"
    file_link.symlink_to(wrong_mode_file)
    directory_link = metadata_root / "directory-link"
    directory_link.symlink_to(wrong_mode_directory, target_is_directory=True)
    regular_kind = metadata_root / "regular-kind"
    regular_kind.write_bytes(b"x")
    regular_kind.chmod(0o600)
    directory_kind = metadata_root / "directory-kind"
    directory_kind.mkdir(mode=0o700)

    with patched(verifier, "reject_acl", lambda _path: None):
        expect_failure(
            lambda: verifier.require_file_metadata(wrong_mode_file, os.geteuid()),
            EXIT_UNSAFE_BOUNDARY,
            "config_file_mode",
        )
        expect_failure(
            lambda: verifier.require_directory_metadata(wrong_mode_directory, os.geteuid(), 0o700),
            EXIT_UNSAFE_BOUNDARY,
            "config_directory_mode",
        )
        expect_failure(
            lambda: verifier.require_file_metadata(hardlink_source, os.geteuid()),
            EXIT_UNSAFE_BOUNDARY,
            "config_link_count",
        )
        expect_failure(
            lambda: verifier.require_file_metadata(file_link, os.geteuid()),
            EXIT_UNSAFE_BOUNDARY,
            "symlink_path_component",
        )
        expect_failure(
            lambda: verifier.require_directory_metadata(directory_link, os.geteuid(), 0o700),
            EXIT_UNSAFE_BOUNDARY,
            "symlink_path_component",
        )
        expect_failure(
            lambda: verifier.require_file_metadata(directory_kind, os.geteuid()),
            EXIT_UNSAFE_BOUNDARY,
            "non_regular_config_file",
        )
        expect_failure(
            lambda: verifier.require_directory_metadata(regular_kind, os.geteuid(), 0o700),
            EXIT_UNSAFE_BOUNDARY,
            "non_directory_config_component",
        )
    checks.extend(
        (
            "file_mode",
            "directory_mode",
            "file_link_count",
            "file_symlink",
            "directory_symlink",
            "file_kind",
            "directory_kind",
        )
    )

    stable_path = metadata_root / "stable"
    stable_path.write_bytes(b"stable")
    stable_metadata = stable_path.lstat()
    if verifier.stable_read(stable_path, stable_metadata, 6) != b"stable":
        fail(EXIT_MISMATCH, "operator_fixture_stable_read")
    checks.append("stable_read")

    oversize_path = metadata_root / "oversize"
    oversize_path.write_bytes(b"12345")
    expect_failure(
        lambda: verifier.stable_read(oversize_path, oversize_path.lstat(), 4),
        EXIT_MISMATCH,
        "config_file_size",
    )
    checks.append("stable_read_cap")

    initial = metadata(stat.S_IFREG | 0o600, os.geteuid(), size=3, mtime_ns=10)
    changed = metadata(stat.S_IFREG | 0o600, os.geteuid(), size=3, mtime_ns=11)
    changing_path = SyntheticMetadataPath(initial, data=b"abc", after=changed)
    expect_failure(
        lambda: verifier.stable_read(changing_path, initial, 3),
        EXIT_UNSAFE_BOUNDARY,
        "changing_config_file",
    )
    short_path = SyntheticMetadataPath(initial, data=b"ab")
    expect_failure(
        lambda: verifier.stable_read(short_path, initial, 3),
        EXIT_UNSAFE_BOUNDARY,
        "changing_config_file",
    )
    failed_path = SyntheticMetadataPath(initial, read_error=True)
    expect_failure(
        lambda: verifier.stable_read(failed_path, initial, 3),
        EXIT_UNSAFE_BOUNDARY,
        "config_read_failed",
    )
    checks.extend(("stable_read_change", "stable_read_short", "stable_read_failure"))

    expect_failure(
        lambda: invoke_synthetic_operation(enabled, expected_hash="0" * 64),
        EXIT_MISMATCH,
        "config_hash",
    )
    checks.append("config_hash")

    invalid_credential = bytearray("A" * 64, "ascii")
    invalid_token = ConfigurationTree(
        work_root / "invalid-token",
        verifier.ENABLED_CONFIG,
        invalid_credential,
    )
    verifier.zero_mutable_buffer(invalid_credential)
    expect_failure(
        lambda: invoke_synthetic_operation(invalid_token, expected_hash=enabled_hash),
        EXIT_MISMATCH,
        "credential_shape",
    )
    checks.append("credential_shape")

    captured, recording_read = capture_credential_buffer()
    with patched(verifier, "stable_read_mutable", recording_read):
        expect_failure(
            lambda: invoke_synthetic_operation(invalid_token, expected_hash=enabled_hash),
            EXIT_MISMATCH,
            "credential_shape",
        )
    require_zeroed(captured, "operator_fixture_zero_failure")
    checks.append("credential_zero_failure")

    def completed(output: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["/bin/ls"], returncode, output, "")

    with contextlib.ExitStack() as stack:
        stack.enter_context(patched(verifier.sys, "platform", "darwin"))
        stack.enter_context(
            patched(
                verifier.subprocess,
                "run",
                lambda *_args, **_kwargs: completed("-rw------- 1 owner group 1 Jan 1 00:00 fixture\n"),
            )
        )
        verifier.reject_acl(enabled.config_path)
    checks.append("acl_clean_listing")

    with contextlib.ExitStack() as stack:
        stack.enter_context(patched(verifier.sys, "platform", "darwin"))
        stack.enter_context(
            patched(
                verifier.subprocess,
                "run",
                lambda *_args, **_kwargs: completed("-rw-------+ 1 owner group 1 Jan 1 00:00 fixture\n"),
            )
        )
        expect_failure(
            lambda: verifier.reject_acl(enabled.config_path),
            EXIT_UNSAFE_BOUNDARY,
            "granting_acl",
        )
    checks.append("acl_plus_marker")

    with contextlib.ExitStack() as stack:
        stack.enter_context(patched(verifier.sys, "platform", "darwin"))
        stack.enter_context(
            patched(
                verifier.subprocess,
                "run",
                lambda *_args, **_kwargs: completed(
                    "-rw------- 1 owner group 1 Jan 1 00:00 fixture\n"
                    " 0: synthetic allow read\n"
                ),
            )
        )
        expect_failure(
            lambda: verifier.reject_acl(enabled.config_path),
            EXIT_UNSAFE_BOUNDARY,
            "granting_acl",
        )
    checks.append("acl_entry")

    with patched(verifier.sys, "platform", "synthetic-non-darwin"):
        expect_failure(
            lambda: verifier.reject_acl(enabled.config_path),
            EXIT_UNSAFE_BOUNDARY,
            "acl_check_unsupported",
        )
    checks.append("acl_platform")

    if sys.platform == "darwin":
        verifier.reject_acl(enabled.config_path)
        checks.append("acl_real_clean_fixture")

    return {
        "schema_version": 1,
        "status": "passed",
        "fixture_count": len(checks),
        "real_acl_check": sys.platform == "darwin",
    }


if __name__ == "__main__":
    main(operation)
