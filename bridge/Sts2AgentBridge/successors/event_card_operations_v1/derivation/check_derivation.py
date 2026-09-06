#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any


SCHEMA_VERSION = 1
SUITE = "event_card_operations_v1_derivation"
MAXIMUM_FILE_BYTES = 1024 * 1024
MAXIMUM_MANIFEST_BYTES = 256 * 1024
MAXIMUM_RECORDS = 32
MAXIMUM_EDITS = 256
MAXIMUM_COLLECTION_ENTRIES = 64
MAXIMUM_TOTAL_BYTES = 8 * 1024 * 1024


class DerivationError(ValueError):
    pass


class _ReadBudget:
    def __init__(self) -> None:
        self.remaining = MAXIMUM_TOTAL_BYTES

    def reserve(self, size: int) -> None:
        if size > self.remaining:
            raise DerivationError("total size")
        self.remaining -= size


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _exact_dict(value: Any, keys: list[str]) -> dict[str, Any]:
    if type(value) is not dict or list(value) != keys:
        raise DerivationError("invalid object")
    return value


def _relative(value: Any) -> PurePosixPath:
    if type(value) is not str or not value or len(value) > 512 or "\\" in value:
        raise DerivationError("invalid path")
    path = PurePosixPath(value)
    if value != path.as_posix() or path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise DerivationError("invalid path")
    return path


def _hex_digest(value: Any) -> str:
    if type(value) is not str or len(value) != 64:
        raise DerivationError("invalid digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise DerivationError("invalid digest")
    return value


def _no_link_ancestors(path: Path) -> None:
    current = path
    chain: list[Path] = []
    while True:
        chain.append(current)
        if current.parent == current:
            break
        current = current.parent
    for component in reversed(chain):
        try:
            mode = component.lstat().st_mode
        except OSError as error:
            raise DerivationError("invalid path") from error
        if stat.S_ISLNK(mode):
            raise DerivationError("linked path")


def _read_regular(path: Path, maximum: int, budget: _ReadBudget | None = None) -> bytes:
    _no_link_ancestors(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise DerivationError("invalid file") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0 or before.st_size > maximum:
            raise DerivationError("invalid file")
        if budget is not None:
            budget.reserve(before.st_size)
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            try:
                chunk = os.read(descriptor, min(65536, remaining))
            except InterruptedError:
                continue
            if not chunk:
                raise DerivationError("short file")
            chunks.append(chunk)
            remaining -= len(chunk)
        try:
            extra = os.read(descriptor, 1)
        except InterruptedError:
            extra = os.read(descriptor, 1)
        if extra:
            raise DerivationError("growing file")
        after = os.fstat(descriptor)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if identity_before != identity_after:
            raise DerivationError("changed file")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _source_file(root: Path, relative: Any, budget: _ReadBudget) -> tuple[Path, bytes]:
    path = _relative(relative)
    candidate = root.joinpath(*path.parts)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise DerivationError("escaped path") from error
    return candidate, _read_regular(candidate, MAXIMUM_FILE_BYTES, budget)


def _load_json(data: bytes) -> Any:
    try:
        text = data.decode("utf-8")
        if text.startswith("\ufeff"):
            raise DerivationError("invalid json")
        return json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DerivationError("invalid json") from error


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DerivationError("duplicate property")
        result[key] = value
    return result


def _apply_record(root: Path, record: dict[str, Any], budget: _ReadBudget) -> int:
    _exact_dict(record, [
        "schema_version", "name", "original_path", "original_sha256",
        "derived_path", "derived_sha256", "edits",
    ])
    if record["schema_version"] != SCHEMA_VERSION:
        raise DerivationError("record schema")
    if type(record["name"]) is not str or not record["name"] or len(record["name"]) > 80:
        raise DerivationError("record name")
    original_path, original = _source_file(root, record["original_path"], budget)
    derived_path, derived = _source_file(root, record["derived_path"], budget)
    if original_path == derived_path:
        raise DerivationError("same source")
    if _sha256(original) != _hex_digest(record["original_sha256"]):
        raise DerivationError("original identity")
    if _sha256(derived) != _hex_digest(record["derived_sha256"]):
        raise DerivationError("derived identity")

    edits = record["edits"]
    if type(edits) is not list or not edits or len(edits) > MAXIMUM_EDITS:
        raise DerivationError("invalid edits")
    rebuilt = bytearray()
    cursor = 0
    checks = 3
    for edit in edits:
        _exact_dict(edit, ["offset", "old", "new"])
        offset = edit["offset"]
        if type(offset) is not int or offset < cursor or offset > len(original):
            raise DerivationError("invalid offset")
        if type(edit["old"]) is not str or type(edit["new"]) is not str:
            raise DerivationError("invalid edit text")
        old = edit["old"].encode("utf-8")
        new = edit["new"].encode("utf-8")
        if old == new or len(old) + len(new) > MAXIMUM_FILE_BYTES:
            raise DerivationError("invalid edit")
        end = offset + len(old)
        if end > len(original) or original[offset:end] != old:
            raise DerivationError("edit source mismatch")
        rebuilt.extend(original[cursor:offset])
        rebuilt.extend(new)
        cursor = end
        checks += 1
    rebuilt.extend(original[cursor:])
    if bytes(rebuilt) != derived:
        raise DerivationError("reconstruction mismatch")
    return checks + 1


def _claim_path(path_roles: dict[str, str], value: Any, role: str) -> str:
    canonical = _relative(value).as_posix()
    if canonical in path_roles:
        raise DerivationError("path role collision")
    path_roles[canonical] = role
    return canonical


def verify(source_root: Path, manifest_path: Path) -> int:
    if not source_root.is_absolute():
        raise DerivationError("source root must be absolute")
    _no_link_ancestors(source_root)
    if not source_root.is_dir():
        raise DerivationError("invalid source root")

    budget = _ReadBudget()
    manifest = _load_json(_read_regular(manifest_path, MAXIMUM_MANIFEST_BYTES, budget))
    _exact_dict(manifest, [
        "schema_version", "suite", "derived_records", "identical_copies",
        "direct_inputs", "authored_outputs", "external_authorities", "pending",
    ])
    if manifest["schema_version"] != SCHEMA_VERSION or manifest["suite"] != SUITE:
        raise DerivationError("manifest identity")

    derived_records = manifest["derived_records"]
    identical_copies = manifest["identical_copies"]
    direct_inputs = manifest["direct_inputs"]
    authored_outputs = manifest["authored_outputs"]
    external_authorities = manifest["external_authorities"]
    pending = manifest["pending"]
    for collection in (derived_records, identical_copies, direct_inputs, authored_outputs, external_authorities, pending):
        if type(collection) is not list or len(collection) > MAXIMUM_COLLECTION_ENTRIES:
            raise DerivationError("invalid collection")
    if not derived_records or len(derived_records) > MAXIMUM_RECORDS:
        raise DerivationError("invalid record count")

    checks = 1
    seen_names: set[str] = set()
    path_roles: dict[str, str] = {}
    for reference in derived_records:
        _exact_dict(reference, ["name", "record_path", "record_sha256"])
        name = reference["name"]
        if type(name) is not str or not name or name in seen_names:
            raise DerivationError("duplicate record")
        seen_names.add(name)
        record_name = _claim_path(path_roles, reference["record_path"], "record")
        record_path, record_bytes = _source_file(source_root, record_name, budget)
        if _sha256(record_bytes) != _hex_digest(reference["record_sha256"]):
            raise DerivationError("record identity")
        record = _load_json(record_bytes)
        if type(record) is not dict or record.get("name") != name:
            raise DerivationError("record binding")
        _claim_path(path_roles, record.get("original_path"), "original")
        _claim_path(path_roles, record.get("derived_path"), "derived")
        checks += 2 + _apply_record(source_root, record, budget)
        if record_path == manifest_path:
            raise DerivationError("recursive manifest")

    for copy in identical_copies:
        _exact_dict(copy, ["name", "original_path", "linked_path", "sha256"])
        name = copy["name"]
        if type(name) is not str or not name or name in seen_names:
            raise DerivationError("duplicate name")
        seen_names.add(name)
        original_name = _claim_path(path_roles, copy["original_path"], "copy_original")
        linked_name = _claim_path(path_roles, copy["linked_path"], "copy_output")
        _, original = _source_file(source_root, original_name, budget)
        _, linked = _source_file(source_root, linked_name, budget)
        digest = _hex_digest(copy["sha256"])
        if original != linked or _sha256(original) != digest:
            raise DerivationError("copy identity")
        checks += 2

    for collection, kind in (
        (direct_inputs, "direct"),
        (authored_outputs, "authored"),
        (external_authorities, "authority"),
    ):
        for entry in collection:
            required = ["name", "path", "sha256"] if kind != "authority" else ["name", "path", "sha256", "authority"]
            _exact_dict(entry, required)
            name = entry["name"]
            if type(name) is not str or not name or name in seen_names:
                raise DerivationError("duplicate name")
            seen_names.add(name)
            entry_path = _claim_path(path_roles, entry["path"], kind)
            _, data = _source_file(source_root, entry_path, budget)
            if _sha256(data) != _hex_digest(entry["sha256"]):
                raise DerivationError("pinned identity")
            if kind == "authority" and (type(entry["authority"]) is not str or not entry["authority"]):
                raise DerivationError("invalid authority")
            checks += 1

    pending_names: set[str] = set()
    for entry in pending:
        _exact_dict(entry, ["name", "reason"])
        name = entry["name"]
        reason = entry["reason"]
        if type(name) is not str or not name or name in pending_names or name in seen_names:
            raise DerivationError("invalid pending")
        if type(reason) is not str or not reason or len(reason) > 256:
            raise DerivationError("invalid pending")
        pending_names.add(name)
        checks += 1

    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    arguments = parser.parse_args()
    root = Path(arguments.source_root)
    manifest = Path(__file__).with_name("derivation_manifest.json")
    try:
        checks = verify(root, manifest)
    except (DerivationError, OSError, TypeError, KeyError):
        return 1
    print(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "suite": SUITE,
        "check_count": checks,
    }, separators=(",", ":"), sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
