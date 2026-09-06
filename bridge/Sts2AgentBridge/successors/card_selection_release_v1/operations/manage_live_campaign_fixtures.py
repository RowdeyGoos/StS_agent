#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Callable
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import manage_live_campaign as manager
from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    ToolFailure,
    fail,
    main,
    run_cli,
)

_DLL_DATA = b"MZ" + (b"synthetic-dll" * 7)
_MANIFEST_DATA = b'{"synthetic":"manifest"}'
_ARCHIVE_DATA = b"PK\x03\x04synthetic-canonical-archive"
_FIXTURE_CREDENTIAL = b"a5" * 32

_EXPECTED_CANONICAL_ARTIFACTS = (
    (
        "Sts2AgentBridgeCardSelectionV1.dll",
        202240,
        "61e5617a744587479ef7f9346b8f5d7f9356f695b536d333beff046bd367689b",
    ),
    (
        "Sts2AgentBridgeCardSelectionV1.json",
        370,
        "a1995763b15143a87bb4effc42fdb55ebeb818fed2dce543fea2be51db50ffb2",
    ),
    (
        "Sts2AgentBridgeCardSelectionV1-1.0.0.zip",
        203046,
        "f1cb2208b9a3d13b3f660ce1c716b0e75f5713de24a4ecd42e244145c02ae27f",
    ),
)

_POLICY = manager.ArtifactPolicy(
    dll=manager.ArtifactSpec(
        manager.OVERLAY_DLL_NAME,
        len(_DLL_DATA),
        hashlib.sha256(_DLL_DATA).hexdigest(),
    ),
    manifest=manager.ArtifactSpec(
        manager.OVERLAY_MANIFEST_NAME,
        len(_MANIFEST_DATA),
        hashlib.sha256(_MANIFEST_DATA).hexdigest(),
    ),
    archive=manager.ArtifactSpec(
        "Sts2AgentBridgeCardSelectionV1-0.1.0.zip",
        len(_ARCHIVE_DATA),
        hashlib.sha256(_ARCHIVE_DATA).hexdigest(),
    ),
)


class FixtureTree:
    def __init__(self, root: Path, *, preexisting_mods: bool = False, flow_kind: str = "cheese") -> None:
        self.flow_kind = flow_kind
        self.root = root
        self.profile = root / "synthetic-profile"
        self.application_support = self.profile / "Library" / "Application Support"
        install_root = (
            self.application_support
            / "Steam"
            / "steamapps"
            / "common"
            / "Slay the Spire 2"
        )
        self.macos_root = install_root / "SlayTheSpire2.app" / "Contents" / "MacOS"
        self.mods_parent = self.macos_root / "mods"
        self.overlay_root = self.mods_parent / "Sts2AgentBridgeCardSelectionV1"
        self.operator_parent = self.application_support / "Sts2AgentBridge"
        self.config_root = self.operator_parent / "card_selection_v1"
        self.state_root = root / "private-state"
        self.staging_root = self.state_root / manager.STAGING_NAME
        self.quarantine_root = self.state_root / manager.QUARANTINE_NAME
        self.artifact_root = root / "artifacts"
        self.unrelated_mod = self.mods_parent / "unrelated-mod.txt"
        self.state_sha256: str | None = None

        self.macos_root.mkdir(parents=True, mode=0o700)
        self.application_support.chmod(0o700)
        self.macos_root.chmod(0o700)
        self.artifact_root.mkdir(mode=0o700)
        self.artifact_root.chmod(0o700)
        self._write_artifact(_POLICY.dll, _DLL_DATA)
        self._write_artifact(_POLICY.manifest, _MANIFEST_DATA)
        self._write_artifact(_POLICY.archive, _ARCHIVE_DATA)
        if preexisting_mods:
            self.mods_parent.mkdir(mode=0o755)
            self.mods_parent.chmod(0o755)
            self.unrelated_mod.write_bytes(b"unrelated-sentinel")
            self.unrelated_mod.chmod(0o600)

        self.layout = manager.CampaignLayout(
            user_profile=self.profile,
            application_support=self.application_support,
            macos_root=self.macos_root,
            mods_parent=self.mods_parent,
            overlay_root=self.overlay_root,
            operator_parent=self.operator_parent,
            config_root=self.config_root,
            state_root=self.state_root,
            staging_root=self.staging_root,
            staged_operator=self.staging_root / manager.STAGED_OPERATOR_NAME,
            staged_overlay=self.staging_root / manager.STAGED_OVERLAY_NAME,
            quarantine_root=self.quarantine_root,
            quarantine_overlay=self.quarantine_root / manager.QUARANTINE_OVERLAY_NAME,
            quarantine_operator=self.quarantine_root / manager.QUARANTINE_OPERATOR_NAME,
        )

    def _write_artifact(self, spec: manager.ArtifactSpec, data: bytes) -> None:
        path = self.artifact_root / spec.name
        path.write_bytes(data)
        path.chmod(0o644)


class CredentialFiller:
    def __init__(self, *, fail_after_fill: bool = False) -> None:
        self.buffers: list[bytearray] = []
        self.fail_after_fill = fail_after_fill

    def __call__(self, output: bytearray) -> None:
        output[:] = _FIXTURE_CREDENTIAL
        self.buffers.append(output)
        if self.fail_after_fill:
            raise OSError("synthetic credential failure containing a path and secret")

    def require_zeroed(self) -> None:
        if not self.buffers or any(any(buffer) for buffer in self.buffers):
            fail(EXIT_MISMATCH, "campaign_fixture_secret_not_zeroed")


class InterruptingCredentialFiller(CredentialFiller):
    def __call__(self, output: bytearray) -> None:
        output[:] = _FIXTURE_CREDENTIAL
        self.buffers.append(output)
        raise KeyboardInterrupt


class InjectedCrash(BaseException):
    pass


@dataclass
class CrashAt:
    target: str
    observed: list[str]
    triggered: bool = False

    def __call__(self, checkpoint: str) -> None:
        self.observed.append(checkpoint)
        if checkpoint == self.target:
            self.triggered = True
            raise InjectedCrash


class RecordCheckpoints:
    def __init__(self) -> None:
        self.observed: list[str] = []

    def __call__(self, checkpoint: str) -> None:
        self.observed.append(checkpoint)


class MutateAt:
    def __init__(self, target: str, mutation: Callable[[], None]) -> None:
        self.target = target
        self.mutation = mutation
        self.triggered = False

    def __call__(self, checkpoint: str) -> None:
        if checkpoint == self.target and not self.triggered:
            self.mutation()
            self.triggered = True


def _install(
    tree: FixtureTree,
    filler: CredentialFiller | None = None,
    *,
    fault_hook: Callable[[str], None] = manager._no_fault,
) -> dict[str, object]:
    selected = filler if filler is not None else CredentialFiller()
    payload = manager._run(
        "install",
        tree.layout,
        os.geteuid(),
        tree.artifact_root,
        flow_kind=tree.flow_kind,
        policy=_POLICY,
        fill_credential=selected,
        fault_hook=fault_hook,
    )
    selected.require_zeroed()
    state_sha256 = payload.get("state_sha256")
    if not isinstance(state_sha256, str) or len(state_sha256) != 64:
        fail(EXIT_MISMATCH, "campaign_fixture_state_hash_output")
    tree.state_sha256 = state_sha256
    return payload


def _quarantine(
    tree: FixtureTree,
    rename_operation: Callable[[Path, Path, int, int, int], None] = manager._rename_no_replace,
    *,
    fault_hook: Callable[[str], None] = manager._no_fault,
) -> dict[str, object]:
    if tree.state_sha256 is None:
        fail(EXIT_INTERNAL, "campaign_fixture_missing_state_hash")
    payload = manager._run(
        "quarantine",
        tree.layout,
        os.geteuid(),
        expected_state_sha256=tree.state_sha256,
        policy=_POLICY,
        rename_operation=rename_operation,
        fault_hook=fault_hook,
    )
    state_sha256 = payload.get("state_sha256")
    if not isinstance(state_sha256, str) or len(state_sha256) != 64:
        fail(EXIT_MISMATCH, "campaign_fixture_state_hash_output")
    tree.state_sha256 = state_sha256
    return payload


def _purge(
    tree: FixtureTree,
    *,
    fault_hook: Callable[[str], None] = manager._no_fault,
) -> dict[str, object]:
    if tree.state_sha256 is None:
        fail(EXIT_INTERNAL, "campaign_fixture_missing_state_hash")
    return manager._run(
        "purge",
        tree.layout,
        os.geteuid(),
        expected_state_sha256=tree.state_sha256,
        policy=_POLICY,
        fault_hook=fault_hook,
    )


def _expect_failure(
    operation: Callable[[], object],
    *,
    code: str | None = None,
    exit_code: int | None = None,
) -> ToolFailure:
    try:
        operation()
    except ToolFailure as failure:
        if code is not None and failure.error_code != code:
            fail(EXIT_MISMATCH, "campaign_fixture_wrong_rejection")
        if exit_code is not None and failure.exit_code != exit_code:
            fail(EXIT_MISMATCH, "campaign_fixture_wrong_exit")
        return failure
    fail(EXIT_MISMATCH, "campaign_fixture_unexpected_pass")


def _require_absent(*paths: Path) -> None:
    if any(path.exists() or path.is_symlink() for path in paths):
        fail(EXIT_MISMATCH, "campaign_fixture_expected_absent")


def _require_file(path: Path, data: bytes, mode: int) -> None:
    if not path.is_file() or path.read_bytes() != data:
        fail(EXIT_MISMATCH, "campaign_fixture_file_content")
    if (path.stat().st_mode & 0o777) != mode:
        fail(EXIT_MISMATCH, "campaign_fixture_file_mode")


def _stat_if_present(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        fail(EXIT_MISMATCH, "campaign_fixture_retained_stat")


def _replace_with_self_bound_state(tree: FixtureTree) -> manager.CampaignState:
    state_path = tree.state_root / manager.STATE_FILE_NAME
    document = json.loads(state_path.read_text(encoding="ascii"))
    replacement = tree.root / "self-bound-state-replacement"
    replacement.write_bytes(b"")
    replacement.chmod(0o600)
    metadata = replacement.lstat()
    document["state_file_device"] = metadata.st_dev
    document["state_file_inode"] = metadata.st_ino
    replacement.write_text(
        json.dumps(document, ensure_ascii=True, separators=(",", ":")),
        encoding="ascii",
    )
    replacement.chmod(0o600)
    os.replace(replacement, state_path)
    state, _ = manager._read_state(tree.layout, os.geteuid())
    return state


def _require_recorded_path(
    path: Path,
    uid: int,
    device: int,
    inode: int,
    *,
    directory: bool,
    mode: int,
) -> bool:
    metadata = _stat_if_present(path)
    if metadata is None:
        return False
    expected_kind = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        not expected_kind(metadata.st_mode)
        or metadata.st_uid != uid
        or stat.S_IMODE(metadata.st_mode) != mode
        or metadata.st_dev != device
        or metadata.st_ino != inode
        or (not directory and metadata.st_nlink != 1)
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_inode_adoption")
    return True


def _assert_recorded_retention(
    tree: FixtureTree,
    state: manager.CampaignState,
) -> None:
    uid = os.geteuid()
    if not _require_recorded_path(
        tree.state_root,
        uid,
        state.campaign_device,
        state.campaign_inode,
        directory=True,
        mode=0o700,
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_missing_campaign_state")
    if not _require_recorded_path(
        tree.state_root / manager.STATE_FILE_NAME,
        uid,
        state.state_file_device,
        state.state_file_inode,
        directory=False,
        mode=0o600,
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_missing_campaign_state")

    if state.staging_device > 0 and _stat_if_present(tree.staging_root) is not None:
        _require_recorded_path(
            tree.staging_root,
            uid,
            state.staging_device,
            state.staging_inode,
            directory=True,
            mode=0o700,
        )
    if state.quarantine_device > 0 and _stat_if_present(tree.quarantine_root) is not None:
        _require_recorded_path(
            tree.quarantine_root,
            uid,
            state.quarantine_device,
            state.quarantine_inode,
            directory=True,
            mode=0o700,
        )

    if state.operator_device == 0:
        if any(
            _stat_if_present(path) is not None
            for path in (
                tree.layout.staged_operator,
                tree.operator_parent,
                tree.layout.quarantine_operator,
            )
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_unbound_adoption")
        return

    operator_candidates = (
        tree.layout.staged_operator,
        tree.operator_parent,
        tree.layout.quarantine_operator,
    )
    present_operators = [
        path
        for path in operator_candidates
        if _require_recorded_path(
            path,
            uid,
            state.operator_device,
            state.operator_inode,
            directory=True,
            mode=0o700,
        )
    ]
    overlay_active = tree.mods_parent if state.mods_parent_created else tree.overlay_root
    overlay_candidates = (
        tree.layout.staged_overlay,
        overlay_active,
        tree.layout.quarantine_overlay,
    )
    present_overlays = [
        path
        for path in overlay_candidates
        if _require_recorded_path(
            path,
            uid,
            state.overlay_unit_device,
            state.overlay_unit_inode,
            directory=True,
            mode=0o700,
        )
    ]
    if len(present_operators) > 1 or len(present_overlays) > 1:
        fail(EXIT_MISMATCH, "campaign_fixture_duplicate_generated_unit")
    if state.phase != "purging" and (
        len(present_operators) != 1 or len(present_overlays) != 1
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_missing_generated_unit")

    for operator_root in present_operators:
        config_root = operator_root / "card_selection_v1"
        config_present = _require_recorded_path(
            config_root,
            uid,
            state.config_device,
            state.config_inode,
            directory=True,
            mode=0o700,
        )
        if config_present:
            for name, device, inode in (
                (
                    manager.CONFIG_FILE_NAME,
                    state.config_file_device,
                    state.config_file_inode,
                ),
                (
                    manager.CREDENTIAL_FILE_NAME,
                    state.credential_device,
                    state.credential_inode,
                ),
            ):
                _require_recorded_path(
                    config_root / name,
                    uid,
                    device,
                    inode,
                    directory=False,
                    mode=0o600,
                )

    for overlay_unit in present_overlays:
        overlay_root = (
            overlay_unit / "Sts2AgentBridgeCardSelectionV1"
            if state.mods_parent_created
            else overlay_unit
        )
        overlay_present = _require_recorded_path(
            overlay_root,
            uid,
            state.overlay_device,
            state.overlay_inode,
            directory=True,
            mode=0o700,
        )
        if overlay_present:
            for name, device, inode in (
                (manager.OVERLAY_DLL_NAME, state.dll_device, state.dll_inode),
                (
                    manager.OVERLAY_MANIFEST_NAME,
                    state.manifest_device,
                    state.manifest_inode,
                ),
            ):
                _require_recorded_path(
                    overlay_root / name,
                    uid,
                    device,
                    inode,
                    directory=False,
                    mode=0o644,
                )


_INSTALL_CHECKPOINTS = (
    "install_after_preparing_state",
    "install_after_inventory_state",
    "install_after_activating_state",
    "install_after_operator_rename",
    "install_after_operator_state",
    "install_after_overlay_rename",
    "install_after_overlay_state",
    "install_after_staging_rmdir",
    "install_after_installed_state",
)

_QUARANTINE_CHECKPOINTS = (
    "quarantine_after_quarantining_state",
    "quarantine_after_overlay_rename",
    "quarantine_after_overlay_state",
    "quarantine_after_operator_rename",
    "quarantine_after_operator_state",
    "quarantine_after_quarantined_state",
)

_PURGE_CREATED_CHECKPOINTS = (
    "purge_after_purging_state",
    "purge_after_credential_unlink",
    "purge_after_progress_1_state",
    "purge_after_config_unlink",
    "purge_after_progress_2_state",
    "purge_after_config_rmdir",
    "purge_after_progress_3_state",
    "purge_after_operator_rmdir",
    "purge_after_progress_4_state",
    "purge_after_manifest_unlink",
    "purge_after_progress_5_state",
    "purge_after_dll_unlink",
    "purge_after_progress_6_state",
    "purge_after_overlay_rmdir",
    "purge_after_progress_7_state",
    "purge_after_overlay_unit_rmdir",
    "purge_after_progress_8_state",
    "purge_after_quarantine_rmdir",
    "purge_after_final_progress_state",
    "purge_after_state_unlink",
    "purge_after_campaign_rmdir",
)

_PURGE_EXISTING_CHECKPOINTS = tuple(
    checkpoint
    for checkpoint in _PURGE_CREATED_CHECKPOINTS
    if checkpoint
    not in ("purge_after_overlay_unit_rmdir", "purge_after_progress_8_state")
)


def _add_granting_acl(path: Path) -> None:
    try:
        result = subprocess.run(
            ["/bin/chmod", "+a", "everyone allow read", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        fail(EXIT_INTERNAL, "campaign_fixture_acl_setup_failed")
    if result.returncode != 0:
        fail(EXIT_INTERNAL, "campaign_fixture_acl_setup_failed")


def _assert_install(tree: FixtureTree, mods_created: bool) -> None:
    state, _ = manager._read_state(tree.layout, os.geteuid())
    if (
        state.phase != "installed"
        or state.mods_parent_created != mods_created
        or state.flow_kind != tree.flow_kind
        or state.config_sha256 != manager.CONFIG_HASHES[tree.flow_kind]
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_install_state")
    _require_file(
        tree.overlay_root / manager.OVERLAY_DLL_NAME,
        _DLL_DATA,
        0o644,
    )
    _require_file(
        tree.overlay_root / manager.OVERLAY_MANIFEST_NAME,
        _MANIFEST_DATA,
        0o644,
    )
    _require_file(
        tree.config_root / manager.CONFIG_FILE_NAME,
        manager.configuration_bytes(tree.flow_kind),
        0o600,
    )
    credential = tree.config_root / manager.CREDENTIAL_FILE_NAME
    if credential.read_bytes() != _FIXTURE_CREDENTIAL or (credential.stat().st_mode & 0o777) != 0o600:
        fail(EXIT_MISMATCH, "campaign_fixture_credential")
    state_bytes = (tree.state_root / manager.STATE_FILE_NAME).read_bytes()
    if (
        os.fsencode(tree.root) in state_bytes
        or os.fsencode(tree.profile) in state_bytes
        or _FIXTURE_CREDENTIAL in state_bytes
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_state_leak")


def _verify_production_bindings() -> None:
    if manager.CAMPAIGN_ID != "CARD-SELECTION-V1-SMOKE-V1":
        fail(EXIT_MISMATCH, "campaign_fixture_campaign_id")
    actual_artifacts = tuple(
        (spec.name, spec.size, spec.sha256)
        for spec in (
            manager.CANONICAL_ARTIFACTS.dll,
            manager.CANONICAL_ARTIFACTS.manifest,
            manager.CANONICAL_ARTIFACTS.archive,
        )
    )
    if actual_artifacts != _EXPECTED_CANONICAL_ARTIFACTS:
        fail(EXIT_MISMATCH, "campaign_fixture_canonical_artifacts")
    manager._require_production_artifact_parent()
    expected_configs = {
        "cheese": b'{"schema_version":"card_selection_v1_transport_config_v1","enabled":true,"flow_kind":"cheese","bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}',
        "smith": b'{"schema_version":"card_selection_v1_transport_config_v1","enabled":true,"flow_kind":"smith","bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}',
    }
    if manager.CONFIGURATIONS != expected_configs or manager.CONFIG_HASHES != {
        "cheese": "56d2698f87dc4b82e61d3a0eca57ea524c6c3397a0cc082f1500b42a00bccec6",
        "smith": "c78c22d0f4732e89a35bd0a34024cb31daf8a4bbca815157ac4b7a266171d93f",
    }:
        fail(EXIT_MISMATCH, "campaign_fixture_canonical_config")

    profile = Path("/Users/synthetic-campaign-user")
    layout = manager._production_layout(profile)
    expected_overlay = (
        profile
        / "Library"
        / "Application Support"
        / "Steam"
        / "steamapps"
        / "common"
        / "Slay the Spire 2"
        / "SlayTheSpire2.app"
        / "Contents"
        / "MacOS"
        / "mods"
        / "Sts2AgentBridgeCardSelectionV1"
    )
    expected_config = (
        profile
        / "Library"
        / "Application Support"
        / "Sts2AgentBridge"
        / "card_selection_v1"
    )
    if (
        layout.overlay_root != expected_overlay
        or layout.config_root != expected_config
        or layout.state_root
        != profile
        / "Library"
        / "Application Support"
        / "Sts2AgentBridgeCampaign-card-selection-v1-smoke-v1"
        or manager.ARTIFACT_ROOT
        != Path("/private/tmp/sts-card-selection-v1-release")
        or layout.staged_operator != layout.state_root / "staging" / "operator"
        or layout.staged_overlay != layout.state_root / "staging" / "overlay"
        or layout.quarantine_overlay != layout.state_root / "quarantine" / "overlay"
        or layout.quarantine_operator
        != layout.state_root / "quarantine" / "operator"
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_production_layout")


def _full_lifecycle(tree: FixtureTree, mods_created: bool) -> None:
    artifact_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in tree.artifact_root.iterdir()
    }
    payload = _install(tree)
    if payload.get("phase") != "installed" or payload.get("mods_parent_created") != mods_created:
        fail(EXIT_MISMATCH, "campaign_fixture_install_payload")
    _assert_install(tree, mods_created)

    payload = _quarantine(tree)
    if payload.get("phase") != "quarantined":
        fail(EXIT_MISMATCH, "campaign_fixture_quarantine_payload")
    _require_absent(tree.overlay_root, tree.config_root, tree.operator_parent)
    if mods_created:
        _require_absent(tree.mods_parent)
    else:
        _require_file(tree.unrelated_mod, b"unrelated-sentinel", 0o600)

    payload = _purge(tree)
    if payload.get("phase") != "absent" or payload.get("generated_files_removed") != 4:
        fail(EXIT_MISMATCH, "campaign_fixture_purge_payload")
    _require_absent(tree.state_root, tree.operator_parent, tree.overlay_root)
    if mods_created:
        _require_absent(tree.mods_parent)
    else:
        _require_file(tree.unrelated_mod, b"unrelated-sentinel", 0o600)
    after_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in tree.artifact_root.iterdir()
    }
    if after_hashes != artifact_hashes:
        fail(EXIT_MISMATCH, "campaign_fixture_artifact_changed")


def _retained_state(tree: FixtureTree) -> manager.CampaignState | None:
    if _stat_if_present(tree.state_root) is None:
        return None
    state_path = tree.state_root / manager.STATE_FILE_NAME
    if _stat_if_present(state_path) is None:
        return None
    state, _ = manager._read_state_file(tree.layout, os.geteuid())
    return state


def _require_crash(hook: CrashAt, operation: Callable[[], object]) -> None:
    try:
        operation()
    except InjectedCrash:
        pass
    else:
        fail(EXIT_MISMATCH, "campaign_fixture_fault_not_raised")
    if not hook.triggered or hook.target not in hook.observed:
        fail(EXIT_MISMATCH, "campaign_fixture_fault_not_observed")


def _exercise_checkpoint_catalog(root: Path) -> None:
    created = FixtureTree(root / "catalog-created")
    created_recorder = RecordCheckpoints()
    created_filler = CredentialFiller()
    _install(created, created_filler, fault_hook=created_recorder)
    _quarantine(created, fault_hook=created_recorder)
    _purge(created, fault_hook=created_recorder)
    if tuple(created_recorder.observed) != (
        _INSTALL_CHECKPOINTS + _QUARANTINE_CHECKPOINTS + _PURGE_CREATED_CHECKPOINTS
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_checkpoint_catalog")

    existing = FixtureTree(root / "catalog-existing", preexisting_mods=True)
    _install(existing)
    _quarantine(existing)
    existing_recorder = RecordCheckpoints()
    _purge(existing, fault_hook=existing_recorder)
    if tuple(existing_recorder.observed) != _PURGE_EXISTING_CHECKPOINTS:
        fail(EXIT_MISMATCH, "campaign_fixture_checkpoint_catalog")


def _exercise_install_faults(root: Path) -> None:
    for index, checkpoint in enumerate(_INSTALL_CHECKPOINTS):
        tree = FixtureTree(root / f"install-{index}")
        hook = CrashAt(checkpoint, [])
        filler = CredentialFiller()
        _require_crash(
            hook,
            lambda: _install(tree, filler, fault_hook=hook),
        )
        if filler.buffers:
            filler.require_zeroed()
        state = _retained_state(tree)
        if state is None:
            fail(EXIT_MISMATCH, "campaign_fixture_missing_fault_state")
        _assert_recorded_retention(tree, state)
        _expect_failure(
            lambda: _install(tree),
            code="target_exists",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        if checkpoint == "install_after_installed_state":
            if state.phase != "installed":
                fail(EXIT_MISMATCH, "campaign_fixture_fault_phase")
        elif state.phase not in ("preparing", "activating"):
            fail(EXIT_MISMATCH, "campaign_fixture_fault_phase")
        if tree.state_sha256 is not None:
            fail(EXIT_MISMATCH, "campaign_fixture_fault_hash_published")
        for mode in ("quarantine", "purge"):
            _expect_failure(
                lambda mode=mode: manager._run(
                    mode,
                    tree.layout,
                    os.geteuid(),
                    policy=_POLICY,
                ),
                code="missing_state_sha256",
                exit_code=EXIT_INVALID_INVOCATION,
            )


def _exercise_quarantine_faults(root: Path) -> None:
    for index, checkpoint in enumerate(_QUARANTINE_CHECKPOINTS):
        tree = FixtureTree(root / f"quarantine-{index}")
        _install(tree)
        hook = CrashAt(checkpoint, [])
        _require_crash(
            hook,
            lambda: _quarantine(tree, fault_hook=hook),
        )
        state = _retained_state(tree)
        if state is None:
            fail(EXIT_MISMATCH, "campaign_fixture_missing_fault_state")
        _assert_recorded_retention(tree, state)
        if checkpoint == "quarantine_after_quarantined_state":
            if state.phase != "quarantined":
                fail(EXIT_MISMATCH, "campaign_fixture_fault_phase")
        elif state.phase != "quarantining":
            fail(EXIT_MISMATCH, "campaign_fixture_fault_phase")
        _expect_failure(lambda: _quarantine(tree), code="state_hash_mismatch")
        _expect_failure(lambda: _purge(tree), code="state_hash_mismatch")


def _exercise_purge_faults(
    root: Path,
    checkpoints: tuple[str, ...],
    *,
    preexisting_mods: bool,
) -> None:
    label = "existing" if preexisting_mods else "created"
    for index, checkpoint in enumerate(checkpoints):
        tree = FixtureTree(
            root / f"purge-{label}-{index}",
            preexisting_mods=preexisting_mods,
        )
        _install(tree)
        _quarantine(tree)
        hook = CrashAt(checkpoint, [])
        _require_crash(
            hook,
            lambda: _purge(tree, fault_hook=hook),
        )
        state = _retained_state(tree)
        if state is not None:
            if state.phase != "purging":
                fail(EXIT_MISMATCH, "campaign_fixture_fault_phase")
            _assert_recorded_retention(tree, state)
            _expect_failure(lambda: _purge(tree), code="state_hash_mismatch")
        else:
            _expect_failure(lambda: _purge(tree))
        _require_absent(tree.operator_parent, tree.overlay_root)
        if state is None and checkpoint != "purge_after_state_unlink":
            _require_absent(tree.state_root)
        if preexisting_mods:
            _require_file(tree.unrelated_mod, b"unrelated-sentinel", 0o600)
        else:
            _require_absent(tree.mods_parent)


def _exercise_dynamic_mutation_guards(root: Path) -> None:
    activation_first = FixtureTree(root / "activation-first")
    activation_first_foreign = activation_first.layout.staged_overlay / "foreign"

    def mutate_activation_first() -> None:
        activation_first_foreign.write_bytes(b"retain")
        activation_first_foreign.chmod(0o600)

    activation_first_hook = MutateAt(
        "install_after_activating_state",
        mutate_activation_first,
    )
    activation_first_filler = CredentialFiller()
    _expect_failure(
        lambda: _install(
            activation_first,
            activation_first_filler,
            fault_hook=activation_first_hook,
        ),
        code="install_partial",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    activation_first_filler.require_zeroed()
    activation_first_state, _ = manager._read_state(
        activation_first.layout,
        os.geteuid(),
    )
    if (
        not activation_first_hook.triggered
        or activation_first_state.operator_location != "staging"
        or activation_first_state.overlay_location != "staging"
        or not activation_first_foreign.exists()
        or activation_first.operator_parent.exists()
        or activation_first.mods_parent.exists()
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_activation_guard")

    activation_second = FixtureTree(root / "activation-second")
    activation_second_foreign = activation_second.layout.staged_overlay / "foreign"

    def mutate_activation_second() -> None:
        activation_second_foreign.write_bytes(b"retain")
        activation_second_foreign.chmod(0o600)

    activation_second_hook = MutateAt(
        "install_after_operator_state",
        mutate_activation_second,
    )
    activation_second_filler = CredentialFiller()
    _expect_failure(
        lambda: _install(
            activation_second,
            activation_second_filler,
            fault_hook=activation_second_hook,
        ),
        code="install_partial",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    activation_second_filler.require_zeroed()
    activation_second_state, _ = manager._read_state(
        activation_second.layout,
        os.geteuid(),
    )
    if (
        not activation_second_hook.triggered
        or activation_second_state.operator_location != "live"
        or activation_second_state.overlay_location != "staging"
        or not activation_second_foreign.exists()
        or not activation_second.operator_parent.exists()
        or activation_second.mods_parent.exists()
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_activation_guard")

    quarantine_first = FixtureTree(root / "quarantine-first")
    _install(quarantine_first)
    quarantine_first_foreign = quarantine_first.overlay_root / "foreign"

    def mutate_quarantine_first() -> None:
        quarantine_first_foreign.write_bytes(b"retain")
        quarantine_first_foreign.chmod(0o600)

    quarantine_first_hook = MutateAt(
        "quarantine_after_quarantining_state",
        mutate_quarantine_first,
    )
    _expect_failure(
        lambda: _quarantine(
            quarantine_first,
            fault_hook=quarantine_first_hook,
        ),
        code="quarantine_partial",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    quarantine_first_state, _ = manager._read_state(
        quarantine_first.layout,
        os.geteuid(),
    )
    if (
        not quarantine_first_hook.triggered
        or quarantine_first_state.operator_location != "live"
        or quarantine_first_state.overlay_location != "live"
        or not quarantine_first_foreign.exists()
        or any(quarantine_first.quarantine_root.iterdir())
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_quarantine_guard")

    quarantine_second = FixtureTree(root / "quarantine-second")
    _install(quarantine_second)
    quarantine_second_foreign = quarantine_second.operator_parent / "foreign"

    def mutate_quarantine_second() -> None:
        quarantine_second_foreign.write_bytes(b"retain")
        quarantine_second_foreign.chmod(0o600)

    quarantine_second_hook = MutateAt(
        "quarantine_after_overlay_state",
        mutate_quarantine_second,
    )
    _expect_failure(
        lambda: _quarantine(
            quarantine_second,
            fault_hook=quarantine_second_hook,
        ),
        code="quarantine_partial",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    quarantine_second_state, _ = manager._read_state(
        quarantine_second.layout,
        os.geteuid(),
    )
    if (
        not quarantine_second_hook.triggered
        or quarantine_second_state.operator_location != "live"
        or quarantine_second_state.overlay_location != "quarantine"
        or not quarantine_second_foreign.exists()
        or not quarantine_second.layout.quarantine_overlay.exists()
        or quarantine_second.layout.quarantine_operator.exists()
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_quarantine_guard")

    purge_active_early = FixtureTree(root / "purge-active-early")
    _install(purge_active_early)
    _quarantine(purge_active_early)

    def mutate_purge_active_early() -> None:
        purge_active_early.operator_parent.mkdir(mode=0o700)
        purge_active_early.operator_parent.chmod(0o700)

    purge_active_early_hook = MutateAt(
        "purge_after_purging_state",
        mutate_purge_active_early,
    )
    _expect_failure(
        lambda: _purge(
            purge_active_early,
            fault_hook=purge_active_early_hook,
        ),
        code="purge_partial",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    purge_active_early_state = _retained_state(purge_active_early)
    if (
        not purge_active_early_hook.triggered
        or purge_active_early_state is None
        or purge_active_early_state.purge_progress != 0
        or not (
            purge_active_early.layout.quarantine_operator
            / "card_selection_v1"
            / manager.CREDENTIAL_FILE_NAME
        ).exists()
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_purge_active_guard")

    purge_active_late = FixtureTree(root / "purge-active-late")
    _install(purge_active_late)
    _quarantine(purge_active_late)

    def mutate_purge_active_late() -> None:
        purge_active_late.mods_parent.mkdir(mode=0o700)
        purge_active_late.mods_parent.chmod(0o700)

    purge_active_late_hook = MutateAt(
        "purge_after_final_progress_state",
        mutate_purge_active_late,
    )
    _expect_failure(
        lambda: _purge(
            purge_active_late,
            fault_hook=purge_active_late_hook,
        ),
        code="purge_partial",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    purge_active_late_state = _retained_state(purge_active_late)
    if (
        not purge_active_late_hook.triggered
        or purge_active_late_state is None
        or purge_active_late_state.purge_progress != 9
        or not purge_active_late.state_root.exists()
        or purge_active_late.quarantine_root.exists()
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_purge_active_guard")

    purge_extra_early = FixtureTree(root / "purge-extra-early")
    _install(purge_extra_early)
    _quarantine(purge_extra_early)
    purge_extra_early_path = purge_extra_early.quarantine_root / "foreign"

    def mutate_purge_extra_early() -> None:
        purge_extra_early_path.write_bytes(b"retain")
        purge_extra_early_path.chmod(0o600)

    purge_extra_early_hook = MutateAt(
        "purge_after_purging_state",
        mutate_purge_extra_early,
    )
    _expect_failure(
        lambda: _purge(
            purge_extra_early,
            fault_hook=purge_extra_early_hook,
        ),
        code="purge_partial",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    if (
        not purge_extra_early_hook.triggered
        or not purge_extra_early_path.exists()
        or not (
            purge_extra_early.layout.quarantine_operator
            / "card_selection_v1"
            / manager.CREDENTIAL_FILE_NAME
        ).exists()
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_purge_extra_guard")

    purge_extra_mid = FixtureTree(root / "purge-extra-mid")
    _install(purge_extra_mid)
    _quarantine(purge_extra_mid)
    purge_extra_mid_path = purge_extra_mid.quarantine_root / "foreign"

    def mutate_purge_extra_mid() -> None:
        purge_extra_mid_path.write_bytes(b"retain")
        purge_extra_mid_path.chmod(0o600)

    purge_extra_mid_hook = MutateAt(
        "purge_after_progress_4_state",
        mutate_purge_extra_mid,
    )
    _expect_failure(
        lambda: _purge(
            purge_extra_mid,
            fault_hook=purge_extra_mid_hook,
        ),
        code="purge_partial",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    purge_extra_mid_state = _retained_state(purge_extra_mid)
    if (
        not purge_extra_mid_hook.triggered
        or purge_extra_mid_state is None
        or purge_extra_mid_state.purge_progress != 4
        or not purge_extra_mid_path.exists()
        or not (
            purge_extra_mid.layout.quarantine_overlay
            / "Sts2AgentBridgeCardSelectionV1"
            / manager.OVERLAY_MANIFEST_NAME
        ).exists()
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_purge_extra_guard")




def _exercise_csprng_shape_and_freshness() -> None:
    raw_values = [bytes(range(32)), bytes(range(32, 64))]
    raw_buffers: list[bytearray] = []
    closed: list[int] = []
    builtin_bytearray = bytearray

    def allocate(size: int) -> bytearray:
        value = builtin_bytearray(size)
        raw_buffers.append(value)
        return value

    def readv(_descriptor: int, buffers: list[memoryview]) -> int:
        source = raw_values.pop(0)
        buffers[0][:] = source
        return len(source)

    outputs = [builtin_bytearray(64), builtin_bytearray(64)]
    with (
        mock.patch.object(manager, "bytearray", allocate, create=True),
        mock.patch.object(manager.os, "open", return_value=71),
        mock.patch.object(
            manager.os,
            "fstat",
            return_value=SimpleNamespace(st_mode=stat.S_IFCHR | 0o600),
        ),
        mock.patch.object(manager.os, "readv", side_effect=readv),
        mock.patch.object(manager.os, "close", side_effect=closed.append),
    ):
        for output in outputs:
            manager._fill_csprng_hex(output)
    if (
        raw_values
        or closed != [71, 71]
        or len(raw_buffers) != 2
        or any(any(buffer) for buffer in raw_buffers)
        or outputs[0] == outputs[1]
        or any(len(output) != 64 for output in outputs)
        or any(value not in manager.LOWER_HEX for output in outputs for value in output)
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_csprng_shape")
    for output in outputs:
        manager._zero(output)


class _FakeAclFunction:
    def __init__(self, operation: Callable[..., int]) -> None:
        self.operation = operation
        self.argtypes: object = None
        self.restype: object = None

    def __call__(self, *args: object) -> int:
        return self.operation(*args)


class _FakeAclLibrary:
    def __init__(self, tags: list[int], *, free_result: int = 0) -> None:
        self.tags = list(tags)
        self.index = 0
        self.free_calls = 0
        self.acl_get_fd_np = _FakeAclFunction(lambda *_args: 1)
        self.acl_get_entry = _FakeAclFunction(self._get_entry)
        self.acl_get_tag_type = _FakeAclFunction(self._get_tag)
        self.acl_free = _FakeAclFunction(self._free)
        self.free_result = free_result

    def _get_entry(self, _acl: object, _selector: object, output: object) -> int:
        if self.index >= len(self.tags):
            manager.ctypes.set_errno(manager.errno.EINVAL)
            return -1
        output._obj.value = self.index + 1
        return 0

    def _get_tag(self, _entry: object, output: object) -> int:
        output._obj.value = self.tags[self.index]
        self.index += 1
        return 0

    def _free(self, _acl: object) -> int:
        self.free_calls += 1
        return self.free_result


def _exercise_acl_policy() -> None:
    deny_only = _FakeAclLibrary([2] * 169)
    with mock.patch.object(manager.ctypes, "CDLL", return_value=deny_only):
        manager.require_no_granting_acl_fd(7)
    if deny_only.free_calls != 1 or deny_only.index != 169:
        fail(EXIT_MISMATCH, "campaign_fixture_acl_deny_only")

    for label, library, code in (
        ("allow", _FakeAclLibrary([1]), "granting_acl"),
        ("unknown", _FakeAclLibrary([3]), "acl_inspection_failed"),
        ("bounded", _FakeAclLibrary([2] * 170), "acl_inspection_failed"),
        ("free", _FakeAclLibrary([], free_result=-1), "acl_inspection_failed"),
    ):
        with mock.patch.object(manager.ctypes, "CDLL", return_value=library):
            _expect_failure(
                lambda: manager.require_no_granting_acl_fd(7),
                code=code,
                exit_code=EXIT_UNSAFE_BOUNDARY,
            )
        if library.free_calls != 1:
            fail(EXIT_MISMATCH, f"campaign_fixture_acl_{label}_cleanup")



def _expect_client_legacy_stop(tree: FixtureTree) -> None:
    expected = tree.state_sha256
    if expected is None:
        fail(EXIT_MISMATCH, "campaign_fixture_client_state_missing")
    with (
        mock.patch.object(manager.sys, "platform", "darwin"),
        mock.patch.object(manager.os, "geteuid", return_value=501),
        mock.patch.object(
            manager.pwd,
            "getpwuid",
            return_value=mock.Mock(pw_dir=str(tree.profile)),
        ),
        mock.patch.object(manager, "_production_layout", return_value=tree.layout),
        mock.patch.object(manager, "CANONICAL_ARTIFACTS", _POLICY),
        mock.patch.object(
            manager,
            "_read_mutable_file",
            side_effect=AssertionError("credential bytes must remain unread"),
        ),
    ):
        _expect_failure(
            lambda: manager.validate_installed_for_client(expected),
            code="target_exists",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )


def _exercise_item_scope_controls(root: Path) -> None:
    old_operator = FixtureTree(root / "old-operator")
    old_operator.operator_parent.mkdir(mode=0o700)
    legacy_leaf = old_operator.operator_parent / "r0a"
    legacy_leaf.mkdir(mode=0o700)
    sentinel = legacy_leaf / "do-not-read"
    sentinel.write_bytes(b"legacy-operator-sentinel")
    sentinel.chmod(0o600)
    _expect_failure(
        lambda: _install(old_operator),
        code="target_exists",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    _require_file(sentinel, b"legacy-operator-sentinel", 0o600)
    _require_absent(old_operator.state_root, old_operator.overlay_root)

    old_overlay = FixtureTree(root / "old-overlay", preexisting_mods=True)
    legacy_overlay = old_overlay.mods_parent / manager.LEGACY_OVERLAY_ROOT_NAME
    legacy_overlay.mkdir(mode=0o700)
    sentinel = legacy_overlay / "do-not-read"
    sentinel.write_bytes(b"legacy-overlay-sentinel")
    sentinel.chmod(0o600)
    _expect_failure(
        lambda: _install(old_overlay),
        code="target_exists",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    _require_file(sentinel, b"legacy-overlay-sentinel", 0o600)
    _require_absent(old_overlay.state_root, old_overlay.overlay_root)

    old_state = FixtureTree(root / "old-state")
    legacy_state = old_state.application_support / manager.LEGACY_STATE_ROOT_NAME
    legacy_state.mkdir(mode=0o700)
    sentinel = legacy_state / "do-not-read"
    sentinel.write_bytes(b"legacy-state-sentinel")
    sentinel.chmod(0o600)
    _expect_failure(
        lambda: _install(old_state),
        code="target_exists",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    _require_file(sentinel, b"legacy-state-sentinel", 0o600)
    _require_absent(old_state.state_root, old_state.overlay_root)

    item_overlay = FixtureTree(root / "item-overlay", preexisting_mods=True)
    predecessor_overlay = item_overlay.mods_parent / manager.ITEM_OVERLAY_ROOT_NAME
    predecessor_overlay.mkdir(mode=0o700)
    sentinel = predecessor_overlay / "do-not-read"
    sentinel.write_bytes(b"item-overlay-sentinel")
    sentinel.chmod(0o600)
    _expect_failure(
        lambda: _install(item_overlay),
        code="target_exists",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    _require_file(sentinel, b"item-overlay-sentinel", 0o600)
    _require_absent(item_overlay.state_root, item_overlay.overlay_root)

    item_state = FixtureTree(root / "item-state")
    predecessor_state = item_state.application_support / manager.ITEM_STATE_ROOT_NAME
    predecessor_state.mkdir(mode=0o700)
    sentinel = predecessor_state / "do-not-read"
    sentinel.write_bytes(b"item-state-sentinel")
    sentinel.chmod(0o600)
    _expect_failure(
        lambda: _install(item_state),
        code="target_exists",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    _require_file(sentinel, b"item-state-sentinel", 0o600)
    _require_absent(item_state.state_root, item_state.overlay_root)

    late_old_overlay = FixtureTree(root / "late-old-overlay", preexisting_mods=True)
    _install(late_old_overlay)
    legacy_overlay = late_old_overlay.mods_parent / manager.LEGACY_OVERLAY_ROOT_NAME
    legacy_overlay.mkdir(mode=0o700)
    late_overlay_sentinel = legacy_overlay / "do-not-read"
    late_overlay_sentinel.write_bytes(b"late-legacy-overlay-sentinel")
    late_overlay_sentinel.chmod(0o600)
    _expect_client_legacy_stop(late_old_overlay)
    _expect_failure(
        lambda: _quarantine(late_old_overlay),
        code="target_exists",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    state, _ = manager._read_state(late_old_overlay.layout, os.geteuid())
    if (
        state.phase != "installed"
        or any(late_old_overlay.quarantine_root.iterdir())
        or late_overlay_sentinel.read_bytes() != b"late-legacy-overlay-sentinel"
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_late_old_overlay")

    late_old_state = FixtureTree(root / "late-old-state")
    _install(late_old_state)
    legacy_state = late_old_state.application_support / manager.LEGACY_STATE_ROOT_NAME
    legacy_state.mkdir(mode=0o700)
    late_state_sentinel = legacy_state / "do-not-read"
    late_state_sentinel.write_bytes(b"late-legacy-state-sentinel")
    late_state_sentinel.chmod(0o600)
    _expect_client_legacy_stop(late_old_state)
    _expect_failure(
        lambda: _quarantine(late_old_state),
        code="target_exists",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    state, _ = manager._read_state(late_old_state.layout, os.geteuid())
    if (
        state.phase != "installed"
        or any(late_old_state.quarantine_root.iterdir())
        or late_state_sentinel.read_bytes() != b"late-legacy-state-sentinel"
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_late_old_state")

    late_item_overlay = FixtureTree(root / "late-item-overlay", preexisting_mods=True)
    _install(late_item_overlay)
    predecessor_overlay = late_item_overlay.mods_parent / manager.ITEM_OVERLAY_ROOT_NAME
    predecessor_overlay.mkdir(mode=0o700)
    late_overlay_sentinel = predecessor_overlay / "do-not-read"
    late_overlay_sentinel.write_bytes(b"late-item-overlay-sentinel")
    late_overlay_sentinel.chmod(0o600)
    _expect_client_legacy_stop(late_item_overlay)
    _expect_failure(
        lambda: _quarantine(late_item_overlay),
        code="target_exists",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    state, _ = manager._read_state(late_item_overlay.layout, os.geteuid())
    if (
        state.phase != "installed"
        or any(late_item_overlay.quarantine_root.iterdir())
        or late_overlay_sentinel.read_bytes() != b"late-item-overlay-sentinel"
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_late_item_overlay")

    late_item_state = FixtureTree(root / "late-item-state")
    _install(late_item_state)
    predecessor_state = late_item_state.application_support / manager.ITEM_STATE_ROOT_NAME
    predecessor_state.mkdir(mode=0o700)
    late_state_sentinel = predecessor_state / "do-not-read"
    late_state_sentinel.write_bytes(b"late-item-state-sentinel")
    late_state_sentinel.chmod(0o600)
    _expect_client_legacy_stop(late_item_state)
    _expect_failure(
        lambda: _quarantine(late_item_state),
        code="target_exists",
        exit_code=EXIT_UNSAFE_BOUNDARY,
    )
    state, _ = manager._read_state(late_item_state.layout, os.geteuid())
    if (
        state.phase != "installed"
        or any(late_item_state.quarantine_root.iterdir())
        or late_state_sentinel.read_bytes() != b"late-item-state-sentinel"
    ):
        fail(EXIT_MISMATCH, "campaign_fixture_late_item_state")

    wrong_archive = FixtureTree(root / "wrong-archive")
    archive = wrong_archive.artifact_root / _POLICY.archive.name
    archive.rename(wrong_archive.artifact_root / "Sts2AgentBridge-0.8.0.zip")
    _expect_failure(
        lambda: _install(wrong_archive),
        code="unexpected_generated_entry",
        exit_code=EXIT_MISMATCH,
    )
    _require_absent(wrong_archive.state_root, wrong_archive.overlay_root)

    old_schema = FixtureTree(root / "old-schema")
    _install(old_schema)
    config_path = old_schema.config_root / manager.CONFIG_FILE_NAME
    config_path.write_bytes(
        b'{"schema_version":"live_probe_v0_config_v1","enabled":true,'
        b'"bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}'
    )
    config_path.chmod(0o600)
    _expect_failure(
        lambda: _quarantine(old_schema),
        code="file_size_mismatch",
        exit_code=EXIT_MISMATCH,
    )
    state, _ = manager._read_state(old_schema.layout, os.geteuid())
    if state.phase != "installed" or any(old_schema.quarantine_root.iterdir()):
        fail(EXIT_MISMATCH, "campaign_fixture_old_schema_retention")


def _exercise_flow_and_config_immutability(root: Path) -> None:
    transition = FixtureTree(root / "flow-transition")
    _install(transition)
    current, _ = manager._read_state(transition.layout, os.geteuid())
    changed = replace(
        current,
        flow_kind="smith",
        config_sha256=manager.CONFIG_HASHES["smith"],
        phase="quarantining",
        generation=current.generation + 1,
        state_file_device=0,
        state_file_inode=0,
    )
    _expect_failure(
        lambda: manager._atomic_state_update(
            transition.layout,
            os.geteuid(),
            current,
            changed,
        ),
        code="invalid_state_transition",
        exit_code=EXIT_MISMATCH,
    )
    retained, _ = manager._read_state(transition.layout, os.geteuid())
    if retained != current or any(transition.quarantine_root.iterdir()):
        fail(EXIT_MISMATCH, "campaign_fixture_flow_transition_retention")

    state_mutation = FixtureTree(root / "flow-state-mutation")
    _install(state_mutation)
    original_hash = state_mutation.state_sha256
    state_path = state_mutation.state_root / manager.STATE_FILE_NAME
    document = json.loads(state_path.read_text(encoding="ascii"))
    document["flow_kind"] = "smith"
    document["config_sha256"] = manager.CONFIG_HASHES["smith"]
    state_path.write_text(
        json.dumps(document, ensure_ascii=True, separators=(",", ":")),
        encoding="ascii",
    )
    state_path.chmod(0o600)
    _expect_failure(
        lambda: _quarantine(state_mutation),
        code="state_hash_mismatch",
        exit_code=EXIT_MISMATCH,
    )
    if original_hash is None or any(state_mutation.quarantine_root.iterdir()):
        fail(EXIT_MISMATCH, "campaign_fixture_flow_state_mutation")

    config_mutation = FixtureTree(root / "flow-config-mutation")
    _install(config_mutation)
    config_path = config_mutation.config_root / manager.CONFIG_FILE_NAME
    config_path.write_bytes(manager.configuration_bytes("smith"))
    config_path.chmod(0o600)
    _expect_failure(
        lambda: _quarantine(config_mutation),
        code="file_size_mismatch",
        exit_code=EXIT_MISMATCH,
    )
    retained, _ = manager._read_state(config_mutation.layout, os.geteuid())
    if retained.phase != "installed" or any(config_mutation.quarantine_root.iterdir()):
        fail(EXIT_MISMATCH, "campaign_fixture_flow_config_mutation")


def _exercise_client_validation_api(root: Path) -> None:
    installed = FixtureTree(root / "client-api")
    _install(installed)
    expected = installed.state_sha256
    if expected is None:
        fail(EXIT_MISMATCH, "campaign_fixture_client_state_missing")

    with (
        mock.patch.object(manager.sys, "platform", "darwin"),
        mock.patch.object(manager.os, "geteuid", return_value=501),
        mock.patch.object(
            manager.pwd,
            "getpwuid",
            return_value=mock.Mock(pw_dir=str(installed.profile)),
        ),
        mock.patch.object(manager, "_production_layout", return_value=installed.layout),
        mock.patch.object(manager, "CANONICAL_ARTIFACTS", _POLICY),
        mock.patch.object(
            manager,
            "_read_mutable_file",
            side_effect=AssertionError("credential bytes must remain unread"),
        ) as mutable_reader,
    ):
        layout, state = manager.validate_installed_for_client(expected)
    if layout != installed.layout or manager._state_sha256(state) != expected:
        fail(EXIT_MISMATCH, "campaign_fixture_client_api_result")
    if mutable_reader.called:
        fail(EXIT_MISMATCH, "campaign_fixture_client_api_credential_read")

    with mock.patch.object(
        manager.pwd,
        "getpwuid",
        side_effect=AssertionError("identity accessed for malformed hash"),
    ) as identity:
        _expect_failure(
            lambda: manager.validate_installed_for_client("invalid"),
            code="invalid_state_sha256",
            exit_code=EXIT_INVALID_INVOCATION,
        )
    if identity.called:
        fail(EXIT_MISMATCH, "campaign_fixture_client_api_order")

    common = (
        mock.patch.object(manager.sys, "platform", "darwin"),
        mock.patch.object(manager.os, "geteuid", return_value=501),
        mock.patch.object(
            manager.pwd,
            "getpwuid",
            return_value=mock.Mock(pw_dir=str(installed.profile)),
        ),
        mock.patch.object(manager, "_production_layout", return_value=installed.layout),
        mock.patch.object(manager, "CANONICAL_ARTIFACTS", _POLICY),
    )
    with common[0], common[1], common[2], common[3], common[4]:
        _expect_failure(
            lambda: manager.validate_installed_for_client("0" * 64),
            code="state_hash_mismatch",
            exit_code=EXIT_MISMATCH,
        )

    replaced = FixtureTree(root / "client-replaced-config")
    _install(replaced)
    expected = replaced.state_sha256
    if expected is None:
        fail(EXIT_MISMATCH, "campaign_fixture_client_state_missing")
    config_path = replaced.config_root / manager.CONFIG_FILE_NAME
    config_path.unlink()
    config_path.write_bytes(manager.configuration_bytes("cheese"))
    config_path.chmod(0o600)
    with (
        mock.patch.object(manager.sys, "platform", "darwin"),
        mock.patch.object(manager.os, "geteuid", return_value=501),
        mock.patch.object(
            manager.pwd,
            "getpwuid",
            return_value=mock.Mock(pw_dir=str(replaced.profile)),
        ),
        mock.patch.object(manager, "_production_layout", return_value=replaced.layout),
        mock.patch.object(manager, "CANONICAL_ARTIFACTS", _POLICY),
    ):
        _expect_failure(
            lambda: manager.validate_installed_for_client(expected),
            code="generated_identity_mismatch",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )

    wrong_phase = FixtureTree(root / "client-wrong-phase")
    _install(wrong_phase)
    _quarantine(wrong_phase)
    expected = wrong_phase.state_sha256
    if expected is None:
        fail(EXIT_MISMATCH, "campaign_fixture_client_state_missing")
    with (
        mock.patch.object(manager.sys, "platform", "darwin"),
        mock.patch.object(manager.os, "geteuid", return_value=501),
        mock.patch.object(
            manager.pwd,
            "getpwuid",
            return_value=mock.Mock(pw_dir=str(wrong_phase.profile)),
        ),
        mock.patch.object(manager, "_production_layout", return_value=wrong_phase.layout),
        mock.patch.object(manager, "CANONICAL_ARTIFACTS", _POLICY),
    ):
        _expect_failure(
            lambda: manager.validate_installed_for_client(expected),
            code="wrong_phase",
            exit_code=EXIT_MISMATCH,
        )


def operation() -> dict[str, object]:
    checks: list[str] = []
    _verify_production_bindings()
    checks.append("production_bindings")
    with tempfile.TemporaryDirectory(
        prefix="sts-item-v1-campaign-fixtures-",
        dir="/private/tmp",
    ) as temporary:
        root = Path(temporary)

        _exercise_csprng_shape_and_freshness()
        checks.append("csprng_shape_freshness_and_zeroing")
        _exercise_acl_policy()
        checks.append("bounded_deny_only_acl")
        _exercise_item_scope_controls(root)
        checks.append("item_scope_and_legacy_rejection")
        _exercise_flow_and_config_immutability(root)
        checks.append("flow_and_config_immutability")
        _exercise_client_validation_api(root)
        checks.append("client_metadata_validation_api")

        created_mods = FixtureTree(root / "full-created-mods")
        _full_lifecycle(created_mods, True)
        checks.append("full_lifecycle_created_mods")

        existing_mods = FixtureTree(
            root / "full-existing-mods",
            preexisting_mods=True,
            flow_kind="smith",
        )
        _full_lifecycle(existing_mods, False)
        checks.append("full_lifecycle_existing_mods")

        with (
            mock.patch.object(manager.sys, "platform", "darwin"),
            mock.patch.object(manager.os, "geteuid", return_value=501),
            mock.patch.object(
                manager.pwd,
                "getpwuid",
                return_value=mock.Mock(pw_dir="/synthetic-profile"),
            ),
        ):
            if manager._require_identity(Path("/synthetic-profile"), 501) != 501:
                fail(EXIT_MISMATCH, "campaign_fixture_identity_binding")
        with (
            mock.patch.object(manager.sys, "platform", "darwin"),
            mock.patch.object(manager.os, "geteuid", return_value=502),
            mock.patch.object(
                manager.pwd,
                "getpwuid",
                side_effect=AssertionError("pwd accessed before UID rejection"),
            ) as getpwuid,
        ):
            _expect_failure(
                lambda: manager._require_identity(Path("/synthetic-profile"), 502),
                code="effective_uid_mismatch",
                exit_code=EXIT_UNSAFE_BOUNDARY,
            )
            if getpwuid.called:
                fail(EXIT_MISMATCH, "campaign_fixture_identity_access_order")
        with (
            mock.patch.object(
                manager,
                "parse_args",
                return_value=(
                    "install",
                    Path("/synthetic-profile"),
                    501,
                    Path("/private/tmp/not-the-frozen-artifact-root"),
                    None,
                    "cheese",
                ),
            ),
            mock.patch.object(manager, "_require_identity", return_value=501),
            mock.patch.object(
                manager,
                "_run",
                side_effect=AssertionError("run reached with wrong artifact root"),
            ) as run_operation,
        ):
            _expect_failure(
                manager._operation,
                code="artifact_root_mismatch",
                exit_code=EXIT_UNSAFE_BOUNDARY,
            )
            if run_operation.called:
                fail(EXIT_MISMATCH, "campaign_fixture_artifact_root_order")
        checks.append("production_identity_and_artifact_root")

        _expect_failure(
            lambda: manager.parse_args(
                [
                    "--mode",
                    "install",
                    "--user-profile",
                    "/synthetic",
                    "--effective-uid",
                    "501",
                ]
            ),
            code="invalid_invocation",
            exit_code=EXIT_INVALID_INVOCATION,
        )
        _expect_failure(
            lambda: manager.parse_args(
                [
                    "--mode",
                    "purge",
                    "--user-profile",
                    "/synthetic",
                    "--effective-uid",
                    "501",
                    "--artifact-root",
                    "/forbidden",
                ]
            ),
            code="invalid_invocation",
            exit_code=EXIT_INVALID_INVOCATION,
        )
        _expect_failure(
            lambda: manager.parse_args(
                [
                    "--mode",
                    "install",
                    "--user-profile",
                    "/synthetic",
                    "--effective-uid",
                    "501",
                    "--host",
                    "127.0.0.1",
                ]
            ),
            code="invalid_invocation",
            exit_code=EXIT_INVALID_INVOCATION,
        )
        _expect_failure(
            lambda: manager.parse_args(
                [
                    "--user-profile",
                    "/synthetic",
                    "--mode",
                    "quarantine",
                    "--effective-uid",
                    "501",
                    "--expected-state-sha256",
                    "1" * 64,
                ]
            ),
            code="invalid_invocation",
            exit_code=EXIT_INVALID_INVOCATION,
        )
        _expect_failure(
            lambda: manager.parse_args(
                [
                    "--mode",
                    "quarantine",
                    "--user-profile",
                    "/synthetic",
                    "--effective-uid",
                    "501",
                    "--expected-state-sha256",
                    "not-a-hash",
                ]
            ),
            code="invalid_state_sha256",
            exit_code=EXIT_INVALID_INVOCATION,
        )
        if manager.parse_args(
            [
                "--mode",
                "install",
                "--user-profile",
                "/synthetic",
                "--effective-uid",
                "501",
                "--artifact-root",
                "/private/tmp/artifacts",
                "--flow-kind",
                "cheese",
            ]
        ) != (
            "install",
            Path("/synthetic"),
            501,
            Path("/private/tmp/artifacts"),
            None,
            "cheese",
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_install_cli")
        if manager.parse_args(
            [
                "--mode",
                "quarantine",
                "--user-profile",
                "/synthetic",
                "--effective-uid",
                "501",
                "--expected-state-sha256",
                "1" * 64,
            ]
        ) != (
            "quarantine",
            Path("/synthetic"),
            501,
            None,
            "1" * 64,
            None,
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_quarantine_cli")
        checks.append("cli_surface")

        wrong_owner = FixtureTree(root / "wrong-owner")
        _expect_failure(
            lambda: manager._run(
                "install",
                wrong_owner.layout,
                os.geteuid() + 1,
                wrong_owner.artifact_root,
                flow_kind="cheese",
                policy=_POLICY,
                fill_credential=CredentialFiller(),
            ),
            code="owner_mismatch",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        _require_absent(wrong_owner.state_root, wrong_owner.overlay_root)
        checks.append("owner_rejection")

        wrong_mode = FixtureTree(root / "wrong-mode")
        (wrong_mode.artifact_root / _POLICY.dll.name).chmod(0o600)
        _expect_failure(
            lambda: _install(wrong_mode),
            code="mode_mismatch",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        _require_absent(wrong_mode.state_root, wrong_mode.overlay_root)
        checks.append("mode_rejection")

        writable_parent = FixtureTree(root / "writable-parent")
        writable_parent.application_support.chmod(0o777)
        _expect_failure(
            lambda: _install(writable_parent),
            code="unsafe_directory_mode",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        _require_absent(writable_parent.state_root, writable_parent.overlay_root)

        changed_parent = FixtureTree(root / "changed-parent")
        _install(changed_parent)
        changed_parent.macos_root.chmod(0o777)
        _expect_failure(
            lambda: _quarantine(changed_parent),
            code="unsafe_directory_mode",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        changed_parent_state, _ = manager._read_state(
            changed_parent.layout,
            os.geteuid(),
        )
        if (
            changed_parent_state.phase != "installed"
            or any(changed_parent.quarantine_root.iterdir())
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_parent_mode_mutation")
        checks.append("live_parent_mode_rejection")

        acl_parent = FixtureTree(root / "acl-parent")
        _add_granting_acl(acl_parent.application_support)
        _expect_failure(
            lambda: _install(acl_parent),
            code="granting_acl",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        _require_absent(acl_parent.state_root, acl_parent.overlay_root)

        acl_generated = FixtureTree(root / "acl-generated")
        _install(acl_generated)
        _add_granting_acl(
            acl_generated.config_root / manager.CREDENTIAL_FILE_NAME,
        )
        _expect_failure(
            lambda: _quarantine(acl_generated),
            code="granting_acl",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        acl_state, _ = manager._read_state(acl_generated.layout, os.geteuid())
        if (
            acl_state.phase != "installed"
            or not acl_generated.quarantine_root.is_dir()
            or any(acl_generated.quarantine_root.iterdir())
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_acl_mutation")
        checks.append("granting_acl_rejection")

        symlink_case = FixtureTree(root / "symlink")
        symlink_target = symlink_case.root / "symlink-target"
        symlink_target.mkdir(mode=0o700)
        os.symlink(symlink_target, symlink_case.mods_parent)
        _expect_failure(
            lambda: _install(symlink_case),
            code="symlink_target",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        _require_absent(symlink_case.state_root, symlink_case.overlay_root)
        checks.append("symlink_rejection")

        preexisting = FixtureTree(root / "preexisting", preexisting_mods=True)
        preexisting.overlay_root.mkdir(mode=0o700)
        sentinel = preexisting.overlay_root / "do-not-read"
        sentinel.write_bytes(b"sensitive-sentinel")
        sentinel.chmod(0o600)
        _expect_failure(
            lambda: _install(preexisting),
            code="target_exists",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        if sentinel.read_bytes() != b"sensitive-sentinel":
            fail(EXIT_MISMATCH, "campaign_fixture_preexisting_changed")
        checks.append("preexisting_rejection")

        corrupt = FixtureTree(root / "corrupt-artifact")
        corrupt_dll = corrupt.artifact_root / _POLICY.dll.name
        corrupt_bytes = bytearray(corrupt_dll.read_bytes())
        corrupt_bytes[-1] ^= 1
        corrupt_dll.write_bytes(corrupt_bytes)
        corrupt_dll.chmod(0o644)
        _expect_failure(
            lambda: _install(corrupt),
            code="artifact_hash_mismatch",
            exit_code=EXIT_MISMATCH,
        )
        _require_absent(corrupt.state_root, corrupt.overlay_root, corrupt.operator_parent)
        checks.append("corrupt_artifact_rejection")

        prepublish = FixtureTree(root / "prepublish-rollback")
        original_create_state_record = manager._create_state_record

        def fail_state_record(*args: object, **kwargs: object) -> object:
            fail(EXIT_UNSAFE_BOUNDARY, "synthetic_state_publish_failure")

        manager._create_state_record = fail_state_record
        try:
            _expect_failure(
                lambda: _install(prepublish),
                code="synthetic_state_publish_failure",
                exit_code=EXIT_UNSAFE_BOUNDARY,
            )
        finally:
            manager._create_state_record = original_create_state_record
        _require_absent(
            prepublish.state_root,
            prepublish.operator_parent,
            prepublish.overlay_root,
        )

        changed_prepublish = FixtureTree(root / "prepublish-changed")

        def add_foreign_before_failure(
            path: Path,
            *args: object,
            **kwargs: object,
        ) -> object:
            foreign = path.parent / "foreign-entry"
            foreign.write_bytes(b"retain-foreign")
            foreign.chmod(0o600)
            fail(EXIT_UNSAFE_BOUNDARY, "synthetic_state_publish_failure")

        manager._create_state_record = add_foreign_before_failure
        try:
            _expect_failure(
                lambda: _install(changed_prepublish),
                code="install_rollback_incomplete",
                exit_code=EXIT_UNSAFE_BOUNDARY,
            )
        finally:
            manager._create_state_record = original_create_state_record
        foreign_entry = changed_prepublish.state_root / "foreign-entry"
        if foreign_entry.read_bytes() != b"retain-foreign":
            fail(EXIT_MISMATCH, "campaign_fixture_foreign_rollback_deleted")
        checks.append("prepublish_rollback_scope")

        rollback = FixtureTree(root / "install-rollback")
        failing_filler = CredentialFiller(fail_after_fill=True)
        _expect_failure(
            lambda: _install(rollback, failing_filler),
            code="install_partial",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        failing_filler.require_zeroed()
        rollback_state, _ = manager._read_state_file(rollback.layout, os.geteuid())
        if (
            rollback_state.phase != "preparing"
            or rollback_state.operator_location != "unbound"
            or rollback.operator_parent.exists()
            or rollback.overlay_root.exists()
            or not rollback.state_root.exists()
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_prepare_not_retained")
        _expect_failure(
            lambda: manager._read_state(rollback.layout, os.geteuid()),
            code="unbound_generated_tree",
            exit_code=EXIT_MISMATCH,
        )
        _expect_failure(
            lambda: _install(rollback),
            code="target_exists",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        _expect_failure(
            lambda: manager._run(
                "quarantine",
                rollback.layout,
                os.geteuid(),
                policy=_POLICY,
            ),
            code="missing_state_sha256",
            exit_code=EXIT_INVALID_INVOCATION,
        )

        interrupted = FixtureTree(root / "install-interrupted")
        interrupting_filler = InterruptingCredentialFiller()
        try:
            _install(interrupted, interrupting_filler)
        except KeyboardInterrupt:
            pass
        else:
            fail(EXIT_MISMATCH, "campaign_fixture_interrupt_not_raised")
        interrupting_filler.require_zeroed()
        interrupted_state, _ = manager._read_state_file(
            interrupted.layout,
            os.geteuid(),
        )
        if interrupted_state.phase != "preparing":
            fail(EXIT_MISMATCH, "campaign_fixture_interrupt_state")

        interrupted_cli = FixtureTree(root / "install-interrupted-cli")
        interrupted_cli_filler = InterruptingCredentialFiller()
        interrupt_stdout = io.StringIO()
        interrupt_stderr = io.StringIO()
        with (
            contextlib.redirect_stdout(interrupt_stdout),
            contextlib.redirect_stderr(interrupt_stderr),
        ):
            interrupt_exit = run_cli(
                lambda: _install(interrupted_cli, interrupted_cli_filler),
            )
        interrupted_cli_filler.require_zeroed()
        interrupt_payload = json.loads(interrupt_stdout.getvalue())
        if (
            interrupt_exit != EXIT_INTERNAL
            or interrupt_stderr.getvalue() != ""
            or interrupt_payload
            != {"schema_version": 1, "status": "failed", "code": "interrupted"}
            or str(interrupted_cli.root) in interrupt_stdout.getvalue()
            or _FIXTURE_CREDENTIAL.decode("ascii") in interrupt_stdout.getvalue()
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_interrupt_output")
        interrupted_cli_state, _ = manager._read_state_file(
            interrupted_cli.layout,
            os.geteuid(),
        )
        if interrupted_cli_state.phase != "preparing":
            fail(EXIT_MISMATCH, "campaign_fixture_interrupt_state")
        checks.append("install_partial_retention")

        changed_target = FixtureTree(root / "install-changed-target")
        original_validate_installed = manager._validate_installed_sources

        def replace_generated_config(*args: object, **kwargs: object) -> None:
            config_path = changed_target.config_root / manager.CONFIG_FILE_NAME
            config_path.unlink()
            config_path.write_bytes(b"synthetic foreign replacement")
            config_path.chmod(0o600)
            original_validate_installed(*args, **kwargs)

        manager._validate_installed_sources = replace_generated_config
        try:
            _expect_failure(
                lambda: _install(changed_target),
                code="install_partial",
                exit_code=EXIT_UNSAFE_BOUNDARY,
            )
        finally:
            manager._validate_installed_sources = original_validate_installed
        retained_state, _ = manager._read_state(changed_target.layout, os.geteuid())
        if (
            retained_state.phase != "activating"
            or retained_state.operator_location != "live"
            or retained_state.overlay_location != "live"
            or not changed_target.operator_parent.exists()
            or not changed_target.overlay_root.exists()
            or not changed_target.state_root.exists()
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_changed_target_not_retained")

        foreign_child = FixtureTree(root / "install-foreign-child")

        def add_foreign_child(*args: object, **kwargs: object) -> None:
            child = foreign_child.config_root / "foreign-child"
            child.write_bytes(b"retain-foreign-child")
            child.chmod(0o600)
            original_validate_installed(*args, **kwargs)

        manager._validate_installed_sources = add_foreign_child
        try:
            _expect_failure(
                lambda: _install(foreign_child),
                code="install_partial",
                exit_code=EXIT_UNSAFE_BOUNDARY,
            )
        finally:
            manager._validate_installed_sources = original_validate_installed
        retained_foreign_state, _ = manager._read_state(
            foreign_child.layout,
            os.geteuid(),
        )
        if (
            retained_foreign_state.phase != "activating"
            or retained_foreign_state.operator_location != "live"
            or retained_foreign_state.overlay_location != "live"
            or not (foreign_child.config_root / "foreign-child").exists()
            or not (foreign_child.overlay_root / manager.OVERLAY_DLL_NAME).exists()
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_foreign_child_not_retained")
        checks.append("install_changed_target_retention")

        hardlink = FixtureTree(root / "hardlink")
        _install(hardlink)
        credential_path = hardlink.config_root / manager.CREDENTIAL_FILE_NAME
        os.link(credential_path, hardlink.root / "credential-hardlink")
        _expect_failure(
            lambda: _quarantine(hardlink),
            code="link_count_mismatch",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        if (
            not hardlink.overlay_root.exists()
            or not hardlink.quarantine_root.is_dir()
            or any(hardlink.quarantine_root.iterdir())
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_hardlink_mutation")
        checks.append("hardlink_rejection")

        generated_mode = FixtureTree(root / "generated-mode")
        _install(generated_mode)
        (generated_mode.config_root / manager.CONFIG_FILE_NAME).chmod(0o640)
        _expect_failure(
            lambda: _quarantine(generated_mode),
            code="mode_mismatch",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        if not generated_mode.quarantine_root.is_dir() or any(
            generated_mode.quarantine_root.iterdir()
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_mode_mutation")
        checks.append("generated_mode_rejection")

        extra_child = FixtureTree(root / "extra-child")
        _install(extra_child)
        extra = extra_child.overlay_root / "unexpected.txt"
        extra.write_bytes(b"unexpected")
        extra.chmod(0o600)
        _expect_failure(
            lambda: _quarantine(extra_child),
            code="unexpected_generated_entry",
            exit_code=EXIT_MISMATCH,
        )
        if not extra_child.quarantine_root.is_dir() or any(
            extra_child.quarantine_root.iterdir()
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_extra_child_mutation")
        checks.append("extra_child_rejection")

        prepare_failure = FixtureTree(root / "quarantine-prepare-failure")
        _install(prepare_failure)
        original_state_update = manager._atomic_state_update
        update_calls = 0

        def fail_first_state_update(*args: object, **kwargs: object) -> None:
            nonlocal update_calls
            update_calls += 1
            if update_calls == 1:
                fail(EXIT_UNSAFE_BOUNDARY, "synthetic_state_update_failure")
            original_state_update(*args, **kwargs)

        manager._atomic_state_update = fail_first_state_update
        try:
            _expect_failure(
                lambda: _quarantine(prepare_failure),
                code="quarantine_partial",
                exit_code=EXIT_UNSAFE_BOUNDARY,
            )
        finally:
            manager._atomic_state_update = original_state_update
        recovered_state, _ = manager._read_state(prepare_failure.layout, os.geteuid())
        if (
            recovered_state.phase != "installed"
            or not prepare_failure.quarantine_root.is_dir()
            or any(prepare_failure.quarantine_root.iterdir())
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_prepare_not_restored")
        checks.append("quarantine_state_write_rejection")

        partial = FixtureTree(root / "partial-move")
        _install(partial)
        rename_count = 0

        def fail_second_rename(
            source: Path,
            destination: Path,
            uid: int,
            expected_device: int,
            expected_inode: int,
        ) -> None:
            nonlocal rename_count
            rename_count += 1
            if rename_count == 2:
                raise OSError("synthetic second rename failure")
            manager._rename_no_replace(
                source,
                destination,
                uid,
                expected_device,
                expected_inode,
            )

        _expect_failure(
            lambda: _quarantine(partial, fail_second_rename),
            code="quarantine_partial",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        partial_state, _ = manager._read_state(partial.layout, os.geteuid())
        if (
            partial_state.phase != "quarantining"
            or partial_state.overlay_location != "quarantine"
            or partial_state.operator_location != "live"
            or partial.overlay_root.exists()
            or not partial.layout.quarantine_overlay.exists()
            or not partial.config_root.exists()
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_partial_state")
        _expect_failure(lambda: _quarantine(partial), code="state_hash_mismatch")
        _expect_failure(lambda: _purge(partial), code="state_hash_mismatch")
        checks.append("partial_move_retention")

        altered_generation = FixtureTree(root / "altered-generation")
        _install(altered_generation)
        altered_state_path = (
            altered_generation.state_root / manager.STATE_FILE_NAME
        )
        altered_document = json.loads(altered_state_path.read_text(encoding="ascii"))
        altered_document["generation"] = 999
        altered_state_path.write_text(
            json.dumps(
                altered_document,
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            encoding="ascii",
        )
        altered_state_path.chmod(0o600)
        _expect_failure(
            lambda: _quarantine(altered_generation),
            code="invalid_state",
            exit_code=EXIT_MISMATCH,
        )
        if (
            not altered_generation.operator_parent.exists()
            or not altered_generation.overlay_root.exists()
            or any(altered_generation.quarantine_root.iterdir())
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_altered_state_mutation")
        checks.append("state_generation_rejection")

        replaced_state = FixtureTree(root / "replaced-state")
        _install(replaced_state)
        replaced_state_path = replaced_state.state_root / manager.STATE_FILE_NAME
        replacement = replaced_state.root / "state-copy"
        replacement.write_bytes(replaced_state_path.read_bytes())
        replacement.chmod(0o600)
        os.replace(replacement, replaced_state_path)
        _expect_failure(
            lambda: _quarantine(replaced_state),
            code="generated_identity_mismatch",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        if (
            not replaced_state.operator_parent.exists()
            or not replaced_state.overlay_root.exists()
            or any(replaced_state.quarantine_root.iterdir())
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_replaced_state_mutation")
        checks.append("state_inode_replacement_rejection")

        self_bound_state = FixtureTree(root / "self-bound-state")
        _install(self_bound_state)
        accepted_replacement = _replace_with_self_bound_state(self_bound_state)
        if accepted_replacement.phase != "installed":
            fail(EXIT_MISMATCH, "campaign_fixture_self_bound_state_setup")
        _expect_failure(
            lambda: _quarantine(self_bound_state),
            code="state_hash_mismatch",
            exit_code=EXIT_MISMATCH,
        )
        if (
            not self_bound_state.operator_parent.exists()
            or not self_bound_state.overlay_root.exists()
            or any(self_bound_state.quarantine_root.iterdir())
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_state_hash_mutation")

        in_transition_state = FixtureTree(root / "in-transition-state")
        _install(in_transition_state)
        original_atomic_update = manager._atomic_state_update
        replaced_during_update = False

        def replace_before_atomic_update(
            layout: manager.CampaignLayout,
            uid: int,
            predecessor: manager.CampaignState,
            updated: manager.CampaignState,
        ) -> manager.CampaignState:
            nonlocal replaced_during_update
            if not replaced_during_update:
                _replace_with_self_bound_state(in_transition_state)
                replaced_during_update = True
            return original_atomic_update(
                layout,
                uid,
                predecessor,
                updated,
            )

        manager._atomic_state_update = replace_before_atomic_update
        try:
            _expect_failure(
                lambda: _quarantine(in_transition_state),
                code="quarantine_partial",
                exit_code=EXIT_UNSAFE_BOUNDARY,
            )
        finally:
            manager._atomic_state_update = original_atomic_update
        if (
            not replaced_during_update
            or not in_transition_state.operator_parent.exists()
            or not in_transition_state.overlay_root.exists()
            or any(in_transition_state.quarantine_root.iterdir())
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_predecessor_hash_mutation")
        checks.append("state_hash_lineage_rejection")

        interrupted_move = FixtureTree(root / "interrupted-move")
        _install(interrupted_move)
        interrupted_rename_count = 0

        def interrupt_second_rename(
            source: Path,
            destination: Path,
            uid: int,
            expected_device: int,
            expected_inode: int,
        ) -> None:
            nonlocal interrupted_rename_count
            interrupted_rename_count += 1
            if interrupted_rename_count == 2:
                raise KeyboardInterrupt
            manager._rename_no_replace(
                source,
                destination,
                uid,
                expected_device,
                expected_inode,
            )

        move_stdout = io.StringIO()
        move_stderr = io.StringIO()
        with (
            contextlib.redirect_stdout(move_stdout),
            contextlib.redirect_stderr(move_stderr),
        ):
            move_exit = run_cli(
                lambda: _quarantine(interrupted_move, interrupt_second_rename),
            )
        move_payload = json.loads(move_stdout.getvalue())
        interrupted_state, _ = manager._read_state(
            interrupted_move.layout,
            os.geteuid(),
        )
        if (
            move_exit != EXIT_INTERNAL
            or move_stderr.getvalue() != ""
            or move_payload
            != {"schema_version": 1, "status": "failed", "code": "interrupted"}
            or interrupted_state.phase != "quarantining"
            or interrupted_state.overlay_location != "quarantine"
            or interrupted_state.operator_location != "live"
            or not interrupted_move.layout.quarantine_overlay.exists()
            or not interrupted_move.config_root.exists()
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_interrupted_move")
        checks.append("interrupt_sanitization")

        no_replace = FixtureTree(root / "no-replace")
        _install(no_replace)

        def race_destination(
            source: Path,
            destination: Path,
            uid: int,
            expected_device: int,
            expected_inode: int,
        ) -> None:
            destination.mkdir(mode=0o700)
            destination.chmod(0o700)
            manager._rename_no_replace(
                source,
                destination,
                uid,
                expected_device,
                expected_inode,
            )

        _expect_failure(
            lambda: _quarantine(no_replace, race_destination),
            code="quarantine_partial",
            exit_code=EXIT_UNSAFE_BOUNDARY,
        )
        if not no_replace.overlay_root.exists() or any(no_replace.layout.quarantine_overlay.iterdir()):
            fail(EXIT_MISMATCH, "campaign_fixture_rename_overwrite")
        checks.append("exclusive_rename")

        wrong_phase = FixtureTree(root / "wrong-phase")
        _install(wrong_phase)
        _expect_failure(lambda: _purge(wrong_phase), code="wrong_phase")
        _quarantine(wrong_phase)
        _expect_failure(lambda: _quarantine(wrong_phase), code="wrong_phase")
        _purge(wrong_phase)
        _expect_failure(lambda: _purge(wrong_phase), code="missing_path_component")
        checks.append("phase_and_reinvocation")

        fault_root = root / "fault-matrix"
        _exercise_checkpoint_catalog(fault_root)
        checks.append("fault_checkpoint_catalog")
        _exercise_install_faults(fault_root)
        checks.append("install_fault_retention")
        _exercise_quarantine_faults(fault_root)
        checks.append("quarantine_fault_retention")
        _exercise_purge_faults(
            fault_root,
            _PURGE_CREATED_CHECKPOINTS,
            preexisting_mods=False,
        )
        checks.append("purge_created_fault_retention")
        _exercise_purge_faults(
            fault_root,
            _PURGE_EXISTING_CHECKPOINTS,
            preexisting_mods=True,
        )
        checks.append("purge_existing_fault_retention")
        _exercise_dynamic_mutation_guards(fault_root)
        checks.append("dynamic_mutation_guards")

        purge_extra = FixtureTree(root / "purge-extra")
        _install(purge_extra)
        _quarantine(purge_extra)
        purge_sentinel = purge_extra.layout.quarantine_overlay / "unexpected.txt"
        purge_sentinel.write_bytes(b"retain-me")
        purge_sentinel.chmod(0o600)
        _expect_failure(
            lambda: _purge(purge_extra),
            code="unexpected_generated_entry",
            exit_code=EXIT_MISMATCH,
        )
        if purge_sentinel.read_bytes() != b"retain-me":
            fail(EXIT_MISMATCH, "campaign_fixture_purge_extra_deleted")
        checks.append("purge_extra_retention")

        sanitized = FixtureTree(root / "sanitized-output")
        sanitized_filler = CredentialFiller()
        success_output = io.StringIO()
        with contextlib.redirect_stdout(success_output):
            exit_code = run_cli(
                lambda: _install(sanitized, sanitized_filler)
            )
        sanitized_filler.require_zeroed()
        if exit_code != 0:
            fail(EXIT_MISMATCH, "campaign_fixture_sanitized_success")
        failure_output = io.StringIO()
        with contextlib.redirect_stdout(failure_output):
            failure_exit = run_cli(
                lambda: _install(sanitized, CredentialFiller())
            )
        if failure_exit == 0:
            fail(EXIT_MISMATCH, "campaign_fixture_sanitized_failure")
        combined = success_output.getvalue() + failure_output.getvalue()
        if (
            str(sanitized.root) in combined
            or _FIXTURE_CREDENTIAL.decode("ascii") in combined
            or "synthetic-profile" in combined
            or "synthetic credential failure" in combined
        ):
            fail(EXIT_MISMATCH, "campaign_fixture_output_leak")
        for line in combined.splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                fail(EXIT_MISMATCH, "campaign_fixture_non_json_output")
            if not isinstance(payload, dict) or payload.get("schema_version") != 1:
                fail(EXIT_MISMATCH, "campaign_fixture_output_shape")
        _quarantine(sanitized)
        _purge(sanitized)
        checks.append("sanitized_output")

    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "manage_live_campaign_fixtures",
        "checks": checks,
        "check_count": len(checks),
    }


if __name__ == "__main__":
    main(operation)
