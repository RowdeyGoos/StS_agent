#!/usr/bin/env python3
from __future__ import annotations

import argparse
import stat
import zipfile
from pathlib import Path

from tool_common import (
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    PACKAGE_ENTRIES,
    ToolFailure,
    ZIP_EXTERNAL_ATTR,
    ZIP_TIMESTAMP,
    absolute_path,
    fail,
    inspect_canonical_zip,
    main,
    require_directory,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--canonical-package", required=True)
    result.add_argument("--work-root", required=True)
    return result


def write_fixture(
    path: Path,
    entries: list[tuple[str, bytes, int, int]],
    *,
    archive_comment: bytes = b"",
) -> None:
    try:
        with zipfile.ZipFile(path, mode="x", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
            archive.comment = archive_comment
            for name, data, external_attr, compression in entries:
                info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
                info.compress_type = compression
                info.create_system = 3
                info.external_attr = external_attr
                archive.writestr(info, data)
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "fixture_write")


def assert_rejected(path: Path, expected_code: str) -> None:
    try:
        inspect_canonical_zip(path)
    except ToolFailure as failure:
        if failure.exit_code == EXIT_MISMATCH and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "fixture_wrong_rejection")
    fail(EXIT_MISMATCH, "fixture_unexpected_pass")


def operation() -> dict[str, object]:
    args = parser().parse_args()
    canonical = absolute_path(args.canonical_package, "canonical_package")
    work_root = absolute_path(args.work_root, "work_root")
    require_directory(work_root, "work_root", empty=True)
    dll_data, manifest_data = inspect_canonical_zip(canonical)
    regular = ZIP_EXTERNAL_ATTR
    stored = zipfile.ZIP_STORED
    deflated = zipfile.ZIP_DEFLATED
    canonical_entries = [
        (PACKAGE_ENTRIES[0], dll_data, regular, stored),
        (PACKAGE_ENTRIES[1], manifest_data, regular, stored),
    ]

    fixtures: list[tuple[str, str, list[tuple[str, bytes, int, int]], bytes]] = [
        (
            "extra-json",
            "package_extra_manifest",
            canonical_entries + [("Sts2AgentBridge/extra.json", b"{}", regular, stored)],
            b"",
        ),
        (
            "secondary-dll",
            "package_secondary_dll",
            canonical_entries + [("Sts2AgentBridge/Extra.dll", b"MZ", regular, stored)],
            b"",
        ),
        (
            "copied-game-assembly",
            "package_game_assembly",
            canonical_entries + [("Sts2AgentBridge/sts2.dll", b"MZ", regular, stored)],
            b"",
        ),
        (
            "traversal",
            "package_traversal_entry",
            canonical_entries + [("../escape.json", b"{}", regular, stored)],
            b"",
        ),
        (
            "symlink",
            "package_symlink_entry",
            [
                (PACKAGE_ENTRIES[0], b"target", (stat.S_IFLNK | 0o777) << 16, stored),
                (PACKAGE_ENTRIES[1], manifest_data, regular, stored),
            ],
            b"",
        ),
        (
            "compression",
            "compressed_entry",
            [
                (PACKAGE_ENTRIES[0], dll_data, regular, deflated),
                (PACKAGE_ENTRIES[1], manifest_data, regular, stored),
            ],
            b"",
        ),
        (
            "archive-comment",
            "archive_comment",
            canonical_entries,
            b"forbidden",
        ),
    ]

    for name, expected_code, entries, comment in fixtures:
        path = work_root / f"{name}.zip"
        write_fixture(path, entries, archive_comment=comment)
        assert_rejected(path, expected_code)

    return {
        "schema_version": 1,
        "status": "passed",
        "fixture_count": len(fixtures),
    }


if __name__ == "__main__":
    main(operation)
