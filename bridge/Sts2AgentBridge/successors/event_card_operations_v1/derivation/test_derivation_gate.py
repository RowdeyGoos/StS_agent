#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Callable
import types


def _load_gate():
    path = Path(__file__).with_name("check_derivation.py")
    module = types.ModuleType("event_card_operations_derivation_gate")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


gate = _load_gate()
DerivationError = gate.DerivationError
MAXIMUM_EDITS = gate.MAXIMUM_EDITS
verify = gate.verify


SUITE = "event_card_operations_v1_derivation_tests"


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class Fixture:
    def __init__(self, outer: Path) -> None:
        self.root = outer / "source"
        self.root.mkdir()
        (self.root / "records").mkdir()
        self.manifest_path = outer / "manifest.json"
        self._write("original.txt", b"abc\n")
        self._write("derived.txt", b"axc\n")
        self._write("copy-original.txt", b"same\n")
        self._write("copy-linked.txt", b"same\n")
        self._write("direct.txt", b"direct\n")
        self._write("authored.txt", b"authored\n")
        self._write("authority.txt", b"authority\n")
        self.record: dict[str, Any] = {
            "schema_version": 1,
            "name": "sample",
            "original_path": "original.txt",
            "original_sha256": _sha(b"abc\n"),
            "derived_path": "derived.txt",
            "derived_sha256": _sha(b"axc\n"),
            "edits": [{"offset": 1, "old": "b", "new": "x"}],
        }
        self.manifest: dict[str, Any] = {
            "schema_version": 1,
            "suite": "event_card_operations_v1_derivation",
            "derived_records": [],
            "identical_copies": [{
                "name": "copy",
                "original_path": "copy-original.txt",
                "linked_path": "copy-linked.txt",
                "sha256": _sha(b"same\n"),
            }],
            "direct_inputs": [{"name": "direct", "path": "direct.txt", "sha256": _sha(b"direct\n")}],
            "authored_outputs": [{"name": "authored", "path": "authored.txt", "sha256": _sha(b"authored\n")}],
            "external_authorities": [{
                "name": "authority",
                "path": "authority.txt",
                "sha256": _sha(b"authority\n"),
                "authority": "synthetic authority",
            }],
            "pending": [{"name": "future", "reason": "not available"}],
        }
        self.flush_record()

    def _write(self, relative: str, value: bytes) -> None:
        (self.root / relative).write_bytes(value)

    def flush_record(self) -> None:
        data = (json.dumps(self.record, separators=(",", ":")) + "\n").encode()
        self._write("records/sample.json", data)
        self.manifest["derived_records"] = [{
            "name": "sample",
            "record_path": "records/sample.json",
            "record_sha256": _sha(data),
        }]
        self.flush_manifest()

    def flush_manifest(self) -> None:
        self.manifest_path.write_bytes((json.dumps(self.manifest, separators=(",", ":")) + "\n").encode())


def _reject(action: Callable[[Fixture], None]) -> None:
    with tempfile.TemporaryDirectory(dir="/private/tmp", prefix="event-card-derive-") as temporary:
        fixture = Fixture(Path(temporary))
        action(fixture)
        try:
            verify(fixture.root, fixture.manifest_path)
        except DerivationError:
            return
        raise AssertionError("fixture unexpectedly passed")


def check_valid() -> None:
    with tempfile.TemporaryDirectory(dir="/private/tmp", prefix="event-card-derive-") as temporary:
        fixture = Fixture(Path(temporary))
        if verify(fixture.root, fixture.manifest_path) != 14:
            raise AssertionError("unexpected check count")


def check_original_identity() -> None:
    _reject(lambda fixture: fixture._write("original.txt", b"abd\n"))


def check_derived_identity() -> None:
    _reject(lambda fixture: fixture._write("derived.txt", b"ayc\n"))


def check_record_identity() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture._write("records/sample.json", b"{}\n")
    _reject(mutate)


def check_old_bytes() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.record["edits"][0]["old"] = "z"
        fixture.flush_record()
    _reject(mutate)


def check_overlapping_edits() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.record["edits"] = [
            {"offset": 1, "old": "bc", "new": "x"},
            {"offset": 2, "old": "c", "new": "y"},
        ]
        fixture.flush_record()
    _reject(mutate)


def check_excessive_edits() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.record["edits"] = [{"offset": 0, "old": "", "new": "x"}] * (MAXIMUM_EDITS + 1)
        fixture.flush_record()
    _reject(mutate)


def check_path_escape() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.record["original_path"] = "../original.txt"
        fixture.flush_record()
    _reject(mutate)


def check_absolute_path() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.record["derived_path"] = "/private/tmp/derived.txt"
        fixture.flush_record()
    _reject(mutate)


def check_noncanonical_alias() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.record["original_path"] = "./original.txt"
        fixture.flush_record()
    _reject(mutate)


def check_symlink_ancestor() -> None:
    def mutate(fixture: Fixture) -> None:
        (fixture.root / "real").mkdir()
        (fixture.root / "real" / "authored.txt").write_bytes(b"authored\n")
        (fixture.root / "linked").symlink_to(fixture.root / "real", target_is_directory=True)
        fixture.manifest["authored_outputs"][0]["path"] = "linked/authored.txt"
        fixture.flush_manifest()
    _reject(mutate)


def check_authored_identity() -> None:
    _reject(lambda fixture: fixture._write("authored.txt", b"changed\n"))


def check_direct_identity() -> None:
    _reject(lambda fixture: fixture._write("direct.txt", b"changed\n"))


def check_authority_identity() -> None:
    _reject(lambda fixture: fixture._write("authority.txt", b"changed\n"))


def check_copy_identity() -> None:
    _reject(lambda fixture: fixture._write("copy-linked.txt", b"changed\n"))


def check_duplicate_output() -> None:
    def mutate(fixture: Fixture) -> None:
        second = dict(fixture.record)
        second["name"] = "second"
        data = (json.dumps(second, separators=(",", ":")) + "\n").encode()
        fixture._write("records/second.json", data)
        fixture.manifest["derived_records"].append({
            "name": "second", "record_path": "records/second.json", "record_sha256": _sha(data),
        })
        fixture.flush_manifest()
    _reject(mutate)


def check_duplicate_property() -> None:
    def mutate(fixture: Fixture) -> None:
        data = fixture.manifest_path.read_text()
        fixture.manifest_path.write_text(data.replace('"suite":', '"suite":"duplicate","suite":', 1))
    _reject(mutate)


def check_unexpected_property() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.manifest["extra"] = True
        fixture.flush_manifest()
    _reject(mutate)


def check_pending_collision() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.manifest["pending"][0]["name"] = "sample"
        fixture.flush_manifest()
    _reject(mutate)


def check_output_classification_collision() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.manifest["authored_outputs"][0]["path"] = "derived.txt"
        fixture.manifest["authored_outputs"][0]["sha256"] = _sha(b"axc\n")
        fixture.flush_manifest()
    _reject(mutate)


def check_derived_as_direct_input() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.manifest["direct_inputs"][0]["path"] = "derived.txt"
        fixture.manifest["direct_inputs"][0]["sha256"] = _sha(b"axc\n")
        fixture.flush_manifest()
    _reject(mutate)


def check_derived_as_authority() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture.manifest["external_authorities"][0]["path"] = "derived.txt"
        fixture.manifest["external_authorities"][0]["sha256"] = _sha(b"axc\n")
        fixture.flush_manifest()
    _reject(mutate)


def check_derived_as_later_original() -> None:
    def mutate(fixture: Fixture) -> None:
        fixture._write("second-derived.txt", b"ayc\n")
        second = {
            "schema_version": 1,
            "name": "second",
            "original_path": "derived.txt",
            "original_sha256": _sha(b"axc\n"),
            "derived_path": "second-derived.txt",
            "derived_sha256": _sha(b"ayc\n"),
            "edits": [{"offset": 1, "old": "x", "new": "y"}],
        }
        data = (json.dumps(second, separators=(",", ":")) + "\n").encode()
        fixture._write("records/second.json", data)
        fixture.manifest["derived_records"].append({
            "name": "second", "record_path": "records/second.json", "record_sha256": _sha(data),
        })
        fixture.flush_manifest()
    _reject(mutate)


def check_aggregate_budget() -> None:
    original = gate.MAXIMUM_TOTAL_BYTES
    try:
        gate.MAXIMUM_TOTAL_BYTES = 30
        _reject(lambda fixture: None)
    finally:
        gate.MAXIMUM_TOTAL_BYTES = original


def main() -> int:
    checks = [
        check_valid,
        check_original_identity,
        check_derived_identity,
        check_record_identity,
        check_old_bytes,
        check_overlapping_edits,
        check_excessive_edits,
        check_path_escape,
        check_absolute_path,
        check_noncanonical_alias,
        check_symlink_ancestor,
        check_authored_identity,
        check_direct_identity,
        check_authority_identity,
        check_copy_identity,
        check_duplicate_output,
        check_duplicate_property,
        check_unexpected_property,
        check_pending_collision,
        check_output_classification_collision,
        check_derived_as_direct_input,
        check_derived_as_authority,
        check_derived_as_later_original,
        check_aggregate_budget,
    ]
    try:
        for check in checks:
            check()
    except Exception:
        print(json.dumps({"schema_version": 1, "status": "failed", "suite": SUITE, "check_count": 0}, separators=(",", ":")))
        return 1
    print(json.dumps({"schema_version": 1, "status": "passed", "suite": SUITE, "check_count": len(checks)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
