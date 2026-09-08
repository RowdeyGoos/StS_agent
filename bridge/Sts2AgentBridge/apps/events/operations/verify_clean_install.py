#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import stat
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tool_common import (
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    absolute_path,
    fail,
    inspect_canonical_zip,
    main,
    require_directory,
    require_regular_file,
    sha256_bytes,
)

TARGET_MANIFEST_SHA256 = "ea9046a6a66e2388be3fb1db4e287e0982ae1b3772bec28546a40ef48c23b470"
TARGET_MANIFEST_ID = "sts2-steam-main-build-23811903-macos-universal"
EXPECTED_BASE_COUNT = 429
EXPECTED_BASE_SHA256 = "d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0"

OVERLAY_DLL = "SlayTheSpire2.app/Contents/MacOS/mods/Sts2AgentBridgeGenericEventV10/Sts2AgentBridgeGenericEventV10.dll"
OVERLAY_MANIFEST = "SlayTheSpire2.app/Contents/MacOS/mods/Sts2AgentBridgeGenericEventV10/Sts2AgentBridgeGenericEventV10.json"
OVERLAY_PREFIX = "SlayTheSpire2.app/Contents/MacOS/mods/Sts2AgentBridgeGenericEventV10/"


OVERLAY_DLL_SIZE = 385024
OVERLAY_DLL_SHA256 = "cf8c0023386609dcf8dcd802ddf4f8ce50e3323575b6455cc3301b2653f14272"
OVERLAY_MANIFEST_SIZE = 354
OVERLAY_MANIFEST_SHA256 = "306a2737ce330a409847b30b62bf20c4162a2bd6e08b5f657539607f593817a3"
PACKAGE_SIZE = 385814
PACKAGE_SHA256 = "14e9d365e2308ca7f8899925739fa64c7b01bfeec426034625a4fe2403dc9e8f"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--target-manifest", required=True)
    parser.add_argument("--mode", required=True, choices=("base", "overlay"))
    parser.add_argument("--package")
    return parser.parse_args()


def load_target_manifest(path: Path) -> None:
    data = require_regular_file(path, "target_manifest", max_bytes=4 * 1024 * 1024)
    if sha256_bytes(data) != TARGET_MANIFEST_SHA256:
        fail(EXIT_MISMATCH, "target_manifest_hash")
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, "target_manifest_json")
    if document.get("manifest_id") != TARGET_MANIFEST_ID:
        fail(EXIT_MISMATCH, "target_manifest_id")
    installation = document.get("identity", {}).get("installation_tree", {})
    if installation.get("regular_file_count") != EXPECTED_BASE_COUNT:
        fail(EXIT_MISMATCH, "target_manifest_count")
    if installation.get("sha256") != EXPECTED_BASE_SHA256:
        fail(EXIT_MISMATCH, "target_manifest_projection")


def enumerate_regular_files(root: Path) -> list[tuple[str, Path]]:
    records: list[tuple[str, Path]] = []
    pending: list[tuple[str, Path]] = [("", root)]
    while pending:
        relative_directory, directory = pending.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            fail(EXIT_UNSAFE_BOUNDARY, "unreadable_install_directory")
        for entry in entries:
            relative = f"{relative_directory}/{entry.name}" if relative_directory else entry.name
            if "\n" in relative or "\r" in relative or "\\" in relative:
                fail(EXIT_UNSAFE_BOUNDARY, "unsafe_install_name")
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError:
                fail(EXIT_UNSAFE_BOUNDARY, "unstable_install_entry")
            path = Path(entry.path)
            if stat.S_ISLNK(metadata.st_mode):
                fail(EXIT_UNSAFE_BOUNDARY, "install_symlink")
            if stat.S_ISDIR(metadata.st_mode):
                pending.append((relative, path))
            elif stat.S_ISREG(metadata.st_mode):
                records.append((relative, path))
            else:
                fail(EXIT_UNSAFE_BOUNDARY, "special_install_entry")
    records.sort(key=lambda record: record[0].encode("utf-8"))
    return records


def hash_stable_file(path: Path) -> str:
    try:
        before = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "unreadable_install_file")
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, "invalid_install_file")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        after = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "unreadable_install_file")
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_identity != after_identity:
        fail(EXIT_UNSAFE_BOUNDARY, "changing_install_file")
    return digest.hexdigest()


def operation() -> dict[str, object]:
    args = parse_args()
    install_root = absolute_path(args.install_root, "install_root")
    target_manifest = absolute_path(args.target_manifest, "target_manifest")
    require_directory(install_root, "install_root")
    load_target_manifest(target_manifest)

    expected_overlay: dict[str, bytes] = {}
    if args.mode == "base":
        if args.package is not None:
            fail(EXIT_INVALID_INVOCATION, "package_in_base_mode")
    else:
        if args.package is None:
            fail(EXIT_INVALID_INVOCATION, "missing_overlay_package")
        package = absolute_path(args.package, "package")
        package_data = require_regular_file(package, "package", max_bytes=PACKAGE_SIZE)
        if len(package_data) != PACKAGE_SIZE or sha256_bytes(package_data) != PACKAGE_SHA256:
            fail(EXIT_MISMATCH, "package_identity")
        dll_data, manifest_data = inspect_canonical_zip(package)
        if (
            len(dll_data) != OVERLAY_DLL_SIZE
            or sha256_bytes(dll_data) != OVERLAY_DLL_SHA256
            or len(manifest_data) != OVERLAY_MANIFEST_SIZE
            or sha256_bytes(manifest_data) != OVERLAY_MANIFEST_SHA256
        ):
            fail(EXIT_MISMATCH, "overlay_identity")
        expected_overlay = {
            OVERLAY_DLL: dll_data,
            OVERLAY_MANIFEST: manifest_data,
        }

    files = enumerate_regular_files(install_root)
    projection = hashlib.sha256()
    base_count = 0
    overlay_count = 0
    seen_overlay: set[str] = set()

    for relative, path in files:
        if relative.startswith(OVERLAY_PREFIX):
            if args.mode != "overlay" or relative not in expected_overlay:
                fail(EXIT_MISMATCH, "unexpected_overlay_entry")
            actual = require_regular_file(path, "overlay_entry")
            if actual != expected_overlay[relative]:
                fail(EXIT_MISMATCH, "overlay_content")
            seen_overlay.add(relative)
            overlay_count += 1
            continue

        file_hash = hash_stable_file(path)
        projection.update(f"{file_hash}  {relative}\n".encode("utf-8"))
        base_count += 1

    if args.mode == "overlay" and seen_overlay != set(expected_overlay):
        fail(EXIT_MISMATCH, "missing_overlay_entry")
    if base_count != EXPECTED_BASE_COUNT:
        fail(EXIT_MISMATCH, "base_file_count")
    base_hash = projection.hexdigest()
    if base_hash != EXPECTED_BASE_SHA256:
        fail(EXIT_MISMATCH, "base_projection")

    return {
        "schema_version": 1,
        "status": "passed",
        "mode": args.mode,
        "base_file_count": base_count,
        "base_sha256": base_hash,
        "overlay_count": overlay_count,
    }


if __name__ == "__main__":
    main(operation)
