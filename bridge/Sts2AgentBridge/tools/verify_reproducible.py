#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
from pathlib import Path

from tool_common import (
    EXIT_INTERNAL,
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    absolute_path,
    fail,
    main,
    require_directory,
    require_executable_file,
    require_regular_file,
    sha256_bytes,
)

EXPECTED_PARITY_SDK = "9.0.303"
ARCHIVE_NAME = "Sts2AgentBridge-0.8.0.zip"
IGNORED_DIRECTORY_NAMES = frozenset(("bin", "obj", "__pycache__"))
IGNORED_FILE_NAMES = frozenset((".DS_Store",))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--source-root", required=True)
    result.add_argument("--dotnet", required=True)
    result.add_argument("--game-data-dir", required=True)
    result.add_argument("--work-root-a", required=True)
    result.add_argument("--work-root-b", required=True)
    result.add_argument("--output-dir", required=True)
    return result


def is_within(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath((str(path), str(parent))) == str(parent)
    except ValueError:
        return False


def validate_distinct_roots(paths: dict[str, Path]) -> None:
    items = tuple(paths.items())
    for index, (left_name, left) in enumerate(items):
        for right_name, right in items[index + 1 :]:
            if left == right or is_within(left, right) or is_within(right, left):
                fail(
                    EXIT_UNSAFE_BOUNDARY,
                    f"overlapping_{left_name}_{right_name}",
                )


def copy_source_tree(source: Path, destination: Path) -> None:
    try:
        destination.mkdir(mode=0o700)
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "copy_destination")

    pending: list[tuple[Path, Path]] = [(source, destination)]
    while pending:
        source_directory, destination_directory = pending.pop()
        try:
            entries = sorted(source_directory.iterdir(), key=lambda value: os.fsencode(value.name))
        except OSError:
            fail(EXIT_UNSAFE_BOUNDARY, "source_enumeration")

        for entry in entries:
            try:
                metadata = entry.lstat()
            except OSError:
                fail(EXIT_UNSAFE_BOUNDARY, "source_metadata")
            if stat.S_ISLNK(metadata.st_mode):
                fail(EXIT_UNSAFE_BOUNDARY, "source_symlink")

            target = destination_directory / entry.name
            if stat.S_ISDIR(metadata.st_mode):
                if entry.name in IGNORED_DIRECTORY_NAMES:
                    continue
                try:
                    target.mkdir(mode=0o700)
                except OSError:
                    fail(EXIT_UNSAFE_BOUNDARY, "copy_directory")
                pending.append((entry, target))
                continue

            if not stat.S_ISREG(metadata.st_mode):
                fail(EXIT_UNSAFE_BOUNDARY, "source_special_file")
            if entry.name in IGNORED_FILE_NAMES:
                continue
            if metadata.st_size > 64 * 1024 * 1024:
                fail(EXIT_UNSAFE_BOUNDARY, "source_file_oversize")
            try:
                shutil.copyfile(entry, target, follow_symlinks=False)
                os.chmod(target, 0o600)
            except OSError:
                fail(EXIT_UNSAFE_BOUNDARY, "source_copy")


def run_checked(
    command: list[str],
    cwd: Path,
    log_path: Path,
    *,
    timeout: int = 600,
) -> None:
    environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout,
        )
        log_path.write_bytes(completed.stdout)
    except subprocess.TimeoutExpired:
        fail(EXIT_MISMATCH, "reproducibility_timeout")
    except OSError:
        fail(EXIT_INTERNAL, "reproducibility_process")
    if completed.returncode != 0:
        fail(EXIT_MISMATCH, "reproducibility_subgate")


def build_one(
    source_copy: Path,
    dotnet: Path,
    game_data_dir: Path,
    work_root: Path,
) -> tuple[bytes, bytes, bytes]:
    gate_work = work_root / "gate-work"
    build_output = work_root / "build-output"
    try:
        gate_work.mkdir(mode=0o700)
        build_output.mkdir(mode=0o700)
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "work_root_write")

    run_checked(
        [
            "/usr/bin/python3",
            str(source_copy / "tools" / "run_gate.py"),
            "build",
            "--source-root",
            str(source_copy),
            "--dotnet",
            str(dotnet),
            "--sdk-role",
            "parity",
            "--game-data-dir",
            str(game_data_dir),
            "--work-root",
            str(gate_work),
            "--output-dir",
            str(build_output),
        ],
        source_copy,
        work_root / "build-gate.log",
    )

    dll_path = build_output / "Sts2AgentBridge.dll"
    manifest_path = source_copy / "package" / "Sts2AgentBridge.json"
    package_path = work_root / ARCHIVE_NAME
    dll_data = require_regular_file(dll_path, "dll", max_bytes=64 * 1024 * 1024)
    manifest_data = require_regular_file(manifest_path, "manifest", max_bytes=64 * 1024)
    run_checked(
        [
            "/usr/bin/python3",
            str(source_copy / "tools" / "build_package.py"),
            "--dll",
            str(dll_path),
            "--manifest",
            str(manifest_path),
            "--output",
            str(package_path),
        ],
        source_copy,
        work_root / "package-gate.log",
    )
    package_data = require_regular_file(package_path, "package", max_bytes=64 * 1024 * 1024)
    return dll_data, manifest_data, package_data


def write_output(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        fail(EXIT_UNSAFE_BOUNDARY, "output_exists")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    if temporary.exists() or temporary.is_symlink():
        fail(EXIT_UNSAFE_BOUNDARY, "temporary_output_exists")
    try:
        temporary.write_bytes(data)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "output_write")
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def operation() -> dict[str, object]:
    args = parser().parse_args()
    source_root = absolute_path(args.source_root, "source_root")
    dotnet = absolute_path(args.dotnet, "dotnet")
    game_data_dir = absolute_path(args.game_data_dir, "game_data_dir")
    work_root_a = absolute_path(args.work_root_a, "work_root_a")
    work_root_b = absolute_path(args.work_root_b, "work_root_b")
    output_dir = absolute_path(args.output_dir, "output_dir")

    require_directory(source_root, "source_root")
    require_executable_file(dotnet, "dotnet")
    require_directory(game_data_dir, "game_data_dir")
    require_directory(work_root_a, "work_root_a", empty=True)
    require_directory(work_root_b, "work_root_b", empty=True)
    require_directory(output_dir, "output_dir", empty=True)
    validate_distinct_roots(
        {
            "source_root": source_root,
            "game_data_dir": game_data_dir,
            "work_root_a": work_root_a,
            "work_root_b": work_root_b,
            "output_dir": output_dir,
        }
    )

    source_a = work_root_a / "source"
    source_b = work_root_b / "source"
    copy_source_tree(source_root, source_a)
    copy_source_tree(source_root, source_b)
    artifacts_a = build_one(source_a, dotnet, game_data_dir, work_root_a)
    artifacts_b = build_one(source_b, dotnet, game_data_dir, work_root_b)
    if artifacts_a != artifacts_b:
        fail(EXIT_MISMATCH, "non_reproducible_artifacts")

    dll_data, manifest_data, package_data = artifacts_a
    write_output(output_dir / "Sts2AgentBridge.dll", dll_data)
    write_output(output_dir / "Sts2AgentBridge.json", manifest_data)
    write_output(output_dir / ARCHIVE_NAME, package_data)
    return {
        "schema_version": 1,
        "status": "passed",
        "sdk_version": EXPECTED_PARITY_SDK,
        "dll_sha256": sha256_bytes(dll_data),
        "manifest_sha256": sha256_bytes(manifest_data),
        "package_sha256": sha256_bytes(package_data),
    }


if __name__ == "__main__":
    main(operation)
