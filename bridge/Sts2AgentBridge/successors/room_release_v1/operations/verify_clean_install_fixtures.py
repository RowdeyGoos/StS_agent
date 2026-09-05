#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tool_common as common
import verify_clean_install as verifier


_MANIFEST_SHA256 = "9b361b08e3e99de5322d24811c24497c37662ded1c9e5623a2b4e9cc9ab38812"


def _fail(code: str) -> None:
    common.fail(common.EXIT_MISMATCH, code)


def _require(value: bool, code: str) -> None:
    if not value:
        _fail(code)


def _expect_failure(operation: Callable[[], object], expected: str) -> None:
    try:
        operation()
    except common.ToolFailure as failure:
        _require(
            failure.exit_code == common.EXIT_MISMATCH and failure.error_code == expected,
            "clean_install_fixture_wrong_failure",
        )
        return
    _fail("clean_install_fixture_unexpected_pass")


def _release_package() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "package" / "release_package.py"
    spec = importlib.util.spec_from_file_location("verified_room_release_package", path)
    if spec is None or spec.loader is None:
        _fail("clean_install_fixture_release_import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _projection(root: Path) -> tuple[int, str]:
    rows: list[tuple[bytes, str]] = []
    for path in root.rglob("*"):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            rows.append((relative.encode("utf-8"), relative))
    digest = hashlib.sha256()
    for _, relative in sorted(rows):
        data = (root / relative).read_bytes()
        digest.update(
            f"{hashlib.sha256(data).hexdigest()}  {relative}\n".encode("utf-8")
        )
    return len(rows), digest.hexdigest()


def _write_package(path: Path, dll: bytes, manifest: bytes) -> bytes:
    with zipfile.ZipFile(
        path,
        mode="x",
        compression=zipfile.ZIP_STORED,
        allowZip64=False,
        strict_timestamps=True,
    ) as archive:
        for name, data in (
            (
                "Sts2AgentBridgeRoomFlowsV1/Sts2AgentBridgeRoomFlowsV1.dll",
                dll,
            ),
            (
                "Sts2AgentBridgeRoomFlowsV1/Sts2AgentBridgeRoomFlowsV1.json",
                manifest,
            ),
        ):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = (0o100644 << 16)
            archive.writestr(info, data)
    return path.read_bytes()


class _Fixture:
    def __init__(
        self, root: Path, dll: bytes, manifest: bytes, package_data: bytes
    ) -> None:
        self.root = root
        self.dll = dll
        self.manifest = manifest
        self.install = root / "install"
        self.install.mkdir()
        (self.install / "base").mkdir()
        (self.install / "base" / "a.bin").write_bytes(b"alpha")
        (self.install / "base" / "b.bin").write_bytes(b"beta")
        self.count, self.base_sha256 = _projection(self.install)

        self.target_manifest = root / "target-manifest.json"
        target = {
            "manifest_id": "synthetic-room-release-target",
            "identity": {
                "installation_tree": {
                    "regular_file_count": self.count,
                    "sha256": self.base_sha256,
                }
            },
        }
        self.target_manifest.write_bytes(
            json.dumps(target, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )

        self.package = root / "package.zip"
        self.package.write_bytes(package_data)
        self.package_data = package_data

    def arguments(self, mode: str, package: Path | None = None) -> list[str]:
        values = [
            "verify_clean_install.py",
            "--install-root",
            str(self.install),
            "--target-manifest",
            str(self.target_manifest),
            "--mode",
            mode,
        ]
        if package is not None:
            values.extend(["--package", str(package)])
        return values

    @contextlib.contextmanager
    def patch(self, arguments: list[str]) -> object:
        values = {
            "TARGET_MANIFEST_SHA256": hashlib.sha256(
                self.target_manifest.read_bytes()
            ).hexdigest(),
            "TARGET_MANIFEST_ID": "synthetic-room-release-target",
            "EXPECTED_BASE_COUNT": self.count,
            "EXPECTED_BASE_SHA256": self.base_sha256,
            "OVERLAY_DLL_SIZE": len(self.dll),
            "OVERLAY_DLL_SHA256": hashlib.sha256(self.dll).hexdigest(),
            "OVERLAY_MANIFEST_SIZE": len(self.manifest),
            "OVERLAY_MANIFEST_SHA256": hashlib.sha256(self.manifest).hexdigest(),
            "PACKAGE_SIZE": len(self.package_data),
            "PACKAGE_SHA256": hashlib.sha256(self.package_data).hexdigest(),
        }
        with mock.patch.multiple(verifier, **values), mock.patch.object(
            sys, "argv", arguments
        ):
            yield

    def install_overlay(self, manifest: bytes | None = None) -> None:
        directory = self.install / verifier.OVERLAY_PREFIX.rstrip("/")
        directory.mkdir(parents=True)
        (directory / "Sts2AgentBridgeRoomFlowsV1.dll").write_bytes(self.dll)
        (directory / "Sts2AgentBridgeRoomFlowsV1.json").write_bytes(
            self.manifest if manifest is None else manifest
        )


def _run(fixture: _Fixture, mode: str, package: Path | None = None) -> dict[str, object]:
    with fixture.patch(fixture.arguments(mode, package)):
        return verifier.operation()


def operation() -> dict[str, object]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    arguments = parser.parse_args()
    candidate_path = common.absolute_path(arguments.candidate, "candidate")
    candidate = common.require_regular_file(
        candidate_path, "candidate", max_bytes=64 * 1024 * 1024
    )
    package_module = _release_package()
    canonical_files = package_module.canonical_files(candidate)
    release_manifest = canonical_files[package_module.MANIFEST_NAME]
    package_data = canonical_files[package_module.ZIP_NAME]

    checks: list[str] = []
    _require(
        common.CANONICAL_MANIFEST == release_manifest
        and len(release_manifest) == 344
        and hashlib.sha256(release_manifest).hexdigest() == _MANIFEST_SHA256,
        "clean_install_fixture_manifest_identity",
    )
    checks.append("accepted_manifest_identity")

    with tempfile.TemporaryDirectory(
        prefix="room-release-clean-install.", dir="/private/tmp"
    ) as temporary:
        fixture = _Fixture(
            Path(temporary), candidate, release_manifest, package_data
        )
        result = _run(fixture, "base")
        _require(
            result
            == {
                "schema_version": 1,
                "status": "passed",
                "mode": "base",
                "base_file_count": fixture.count,
                "base_sha256": fixture.base_sha256,
                "overlay_count": 0,
            },
            "clean_install_fixture_base_result",
        )
        checks.append("synthetic_base_passes")

    with tempfile.TemporaryDirectory(
        prefix="room-release-clean-install.", dir="/private/tmp"
    ) as temporary:
        fixture = _Fixture(
            Path(temporary), candidate, release_manifest, package_data
        )
        fixture.install_overlay()
        result = _run(fixture, "overlay", fixture.package)
        _require(
            result.get("status") == "passed"
            and result.get("mode") == "overlay"
            and result.get("base_file_count") == fixture.count
            and result.get("base_sha256") == fixture.base_sha256
            and result.get("overlay_count") == 2,
            "clean_install_fixture_overlay_result",
        )
        checks.append("synthetic_overlay_passes")

    with tempfile.TemporaryDirectory(
        prefix="room-release-clean-install.", dir="/private/tmp"
    ) as temporary:
        fixture = _Fixture(
            Path(temporary), candidate, release_manifest, package_data
        )
        mutated = bytearray(common.CANONICAL_MANIFEST)
        mutated[mutated.index(b"Room Flows V1")] ^= 1
        bad_package = fixture.root / "bad-package.zip"
        bad_data = _write_package(bad_package, candidate, bytes(mutated))
        fixture.package_data = bad_data
        fixture.package = bad_package
        with fixture.patch(fixture.arguments("overlay", bad_package)):
            _expect_failure(verifier.operation, "manifest_not_canonical")
        checks.append("package_manifest_mutation_rejected")

    with tempfile.TemporaryDirectory(
        prefix="room-release-clean-install.", dir="/private/tmp"
    ) as temporary:
        fixture = _Fixture(
            Path(temporary), candidate, release_manifest, package_data
        )
        fixture.install_overlay(common.CANONICAL_MANIFEST[:-1] + b" ")
        _expect_failure(
            lambda: _run(fixture, "overlay", fixture.package), "overlay_content"
        )
        checks.append("installed_overlay_mutation_rejected")

    with tempfile.TemporaryDirectory(
        prefix="room-release-clean-install.", dir="/private/tmp"
    ) as temporary:
        fixture = _Fixture(
            Path(temporary), candidate, release_manifest, package_data
        )
        (fixture.install / "base" / "a.bin").write_bytes(b"changed")
        _expect_failure(lambda: _run(fixture, "base"), "base_projection")
        checks.append("base_projection_mutation_rejected")

    with tempfile.TemporaryDirectory(
        prefix="room-release-clean-install.", dir="/private/tmp"
    ) as temporary:
        fixture = _Fixture(
            Path(temporary), candidate, release_manifest, package_data
        )
        expected = hashlib.sha256(fixture.target_manifest.read_bytes()).hexdigest()
        fixture.target_manifest.write_bytes(fixture.target_manifest.read_bytes() + b"\n")
        with fixture.patch(fixture.arguments("base")), mock.patch.object(
            verifier, "TARGET_MANIFEST_SHA256", expected
        ):
            _expect_failure(verifier.operation, "target_manifest_hash")
        checks.append("target_manifest_mutation_rejected")

    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "verify_clean_install_fixtures",
        "check_count": len(checks),
    }


if __name__ == "__main__":
    common.main(operation)
