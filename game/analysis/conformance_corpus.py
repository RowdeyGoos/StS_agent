"""Offline-only, privacy-bounded storage for named conformance records.

The codec deliberately accepts only the closed sanitized records from
``conformance_evidence``.  It neither captures live data nor creates source or
admission reviews.  In particular, caller-provided manifest and source-review
bindings are required again when a corpus is reloaded.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

from . import conformance_evidence as evidence


CORPUS_SCHEMA = "named_conformance_corpus_v1"
MANIFEST_FILENAME = "manifest.json"
MAX_CASES = 16
MAX_CASE_BYTES = evidence.MAX_RECORD_BYTES
MAX_CORPUS_BYTES = 1_048_576
MAX_CAPTURE_ORDINAL = 999_999
_CORPUS_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_RETAINABLE_ORIGINS = ("synthetic", "retained_live")


class CorpusError(ValueError):
    """Fixed diagnostics only; never include caller text or stored content."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CorpusError(code)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def _digest(value: str | bytes) -> str:
    raw = value.encode("ascii") if type(value) is str else value
    return sha256(raw).hexdigest()


def _check_digest(value: Any, code: str = "invalid_identity") -> str:
    _require(type(value) is str and _DIGEST.fullmatch(value) is not None, code)
    return value


def _check_corpus_name(value: Any) -> str:
    _require(type(value) is str and _CORPUS_NAME.fullmatch(value) is not None,
             "invalid_corpus_name")
    return value


def _output_root(value: str | Path) -> Path:
    _require(isinstance(value, (str, Path)), "invalid_output_root")
    root = Path(value)
    _require(root.exists() and root.is_dir() and not root.is_symlink(),
             "invalid_output_root")
    return root.resolve(strict=True)


def _corpus_path(output_root: str | Path, corpus_name: str, *, must_exist: bool) -> Path:
    root = _output_root(output_root)
    name = _check_corpus_name(corpus_name)
    path = root / name
    _require(path.parent == root, "path_escape")
    if must_exist:
        _require(path.exists() and path.is_dir() and not path.is_symlink(), "missing_corpus")
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError:
            raise CorpusError("path_escape") from None
        return resolved
    _require(not path.exists() and not path.is_symlink(), "output_exists")
    return path


def _case_filename(ordinal: int) -> str:
    _require(type(ordinal) is int and 0 <= ordinal <= MAX_CAPTURE_ORDINAL,
             "invalid_capture_ordinal")
    return f"case-{ordinal:06d}.json"


def _read_regular_at(directory_fd: int, filename: str, maximum: int) -> bytes:
    """Read at most ``maximum`` bytes without dereferencing a final symlink."""
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(filename, flags, dir_fd=directory_fd)
    except OSError:
        raise CorpusError("invalid_corpus_file") from None
    try:
        _require(stat.S_ISREG(os.fstat(descriptor).st_mode), "invalid_corpus_file")
        with os.fdopen(descriptor, "rb") as handle:
            raw = handle.read(maximum + 1)
    except CorpusError:
        os.close(descriptor)
        raise
    except OSError:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise CorpusError("invalid_corpus_file") from None
    _require(len(raw) <= maximum, "corpus_too_large")
    return raw


def _pairs(pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(type(key) is str and key not in result, "duplicate_field")
        result[key] = value
    return result


def _write_exclusive_at(directory_fd: int, filename: str, body: str) -> None:
    """Create a private child through an already anchored directory handle."""
    raw = body.encode("ascii")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(filename, flags, 0o600, dir_fd=directory_fd)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise CorpusError("output_exists") from None
    except OSError:
        raise CorpusError("corpus_write_failed") from None


def _open_new_corpus(root: Path, corpus_name: str) -> tuple[int, int]:
    """Make and retain a private corpus directory without following replacements."""
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    try:
        root_fd = os.open(root, flags)
        os.mkdir(corpus_name, 0o700, dir_fd=root_fd)
        corpus_fd = os.open(corpus_name, flags, dir_fd=root_fd)
    except FileExistsError:
        try:
            os.close(root_fd)
        except (UnboundLocalError, OSError):
            pass
        raise CorpusError("output_exists") from None
    except OSError:
        try:
            os.close(root_fd)
        except (UnboundLocalError, OSError):
            pass
        raise CorpusError("corpus_write_failed") from None
    _require(stat.S_ISDIR(os.fstat(corpus_fd).st_mode), "corpus_write_failed")
    return root_fd, corpus_fd


def _open_existing_corpus(root: Path, corpus_name: str) -> tuple[int, int]:
    """Open an existing corpus through its trusted parent, never a path race."""
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    try:
        root_fd = os.open(root, flags)
        corpus_fd = os.open(corpus_name, flags, dir_fd=root_fd)
    except OSError:
        try:
            os.close(root_fd)
        except (UnboundLocalError, OSError):
            pass
        raise CorpusError("missing_corpus") from None
    _require(stat.S_ISDIR(os.fstat(corpus_fd).st_mode), "missing_corpus")
    return root_fd, corpus_fd


def _assert_directory_binding(root_fd: int, corpus_name: str, corpus_fd: int) -> None:
    """Reject a renamed/replaced destination before admitting its final marker."""
    try:
        named = os.stat(corpus_name, dir_fd=root_fd, follow_symlinks=False)
        opened = os.fstat(corpus_fd)
    except OSError:
        raise CorpusError("output_replaced") from None
    _require(stat.S_ISDIR(named.st_mode)
             and (named.st_dev, named.st_ino) == (opened.st_dev, opened.st_ino),
             "output_replaced")


def _source_header(body: str | bytes) -> dict[str, Any]:
    """Read only enough closed JSON to select a caller-supplied review.

    The complete evidence validation remains in ``parse_record`` below.  This
    small preflight exists solely because live provenance reviews are external
    inputs keyed by capture ordinal.
    """
    _require(type(body) in (str, bytes), "invalid_record")
    try:
        raw = body.encode("ascii") if type(body) is str else body
        _require(len(raw) <= MAX_CASE_BYTES, "case_too_large")
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: _require(False, "invalid_json"))
    except CorpusError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise CorpusError("invalid_json") from None
    _require(type(value) is dict, "invalid_record")
    return value


def _review_for(record_value: dict[str, Any], source_reviews: Mapping[int, evidence.SourceReview] | None,
                *, seen_reviews: set[int]) -> evidence.SourceReview | None:
    _require(type(record_value) is dict and type(record_value.get("source")) is dict,
             "invalid_source_fields")
    source = record_value["source"]
    _require(set(source) == {"origin", "capture_ordinal"}
             and type(source["capture_ordinal"]) is int
             and source["origin"] in ("synthetic", "transient_live", "retained_live"),
             "invalid_source_fields")
    ordinal = source["capture_ordinal"]
    origin = source["origin"]
    review = None if source_reviews is None else source_reviews.get(ordinal)
    if review is not None:
        _require(type(review) is evidence.SourceReview, "invalid_source_review")
        seen_reviews.add(ordinal)
    if origin == "synthetic":
        _require(review is None, "synthetic_source_substitution")
    else:
        _require(review is not None, "unreviewed_live_origin")
    return review


@dataclass(frozen=True)
class CorpusCase:
    """One manifest-bound sanitized record; never a raw capture."""

    ordinal: int
    filename: str
    origin: str
    record_sha256: str

    def __post_init__(self) -> None:
        _case_filename(self.ordinal)
        _require(self.filename == _case_filename(self.ordinal), "swapped_case")
        _require(self.origin in _RETAINABLE_ORIGINS,
                 "invalid_origin")
        _check_digest(self.record_sha256)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "filename": self.filename,
            "origin": self.origin,
            "record_sha256": self.record_sha256,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "CorpusCase":
        _require(type(value) is dict and set(value) == {"ordinal", "filename", "origin", "record_sha256"},
                 "invalid_case_manifest")
        return cls(value["ordinal"], value["filename"], value["origin"], value["record_sha256"])


@dataclass(frozen=True)
class CorpusManifest:
    """Final marker for one complete corpus directory."""

    cases: tuple[CorpusCase, ...]
    pins_sha256: str

    def __post_init__(self) -> None:
        _require(1 <= len(self.cases) <= MAX_CASES, "invalid_case_count")
        _check_digest(self.pins_sha256)
        ordinals = tuple(case.ordinal for case in self.cases)
        _require(ordinals == tuple(sorted(ordinals)) and len(set(ordinals)) == len(ordinals),
                 "duplicate_or_unsorted_case")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CORPUS_SCHEMA,
            "case_spec_sha256": evidence.CASE_SPEC_SHA256,
            "evidence_schema_sha256": evidence.SCHEMA_SHA256,
            "pins_sha256": self.pins_sha256,
            "cases": [case.to_dict() for case in self.cases],
            "finalized": True,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "CorpusManifest":
        _require(type(value) is dict and set(value) == {
            "schema", "case_spec_sha256", "evidence_schema_sha256", "pins_sha256", "cases", "finalized",
        }, "invalid_manifest_fields")
        _require(value["schema"] == CORPUS_SCHEMA, "invalid_corpus_schema")
        _require(value["case_spec_sha256"] == evidence.CASE_SPEC_SHA256
                 and value["evidence_schema_sha256"] == evidence.SCHEMA_SHA256,
                 "changed_schema")
        _require(value["finalized"] is True, "missing_final_manifest")
        _require(type(value["cases"]) is list, "invalid_case_manifest")
        return cls(tuple(CorpusCase.from_dict(case) for case in value["cases"]), value["pins_sha256"])


def _load_manifest(corpus_fd: int, expected_manifest_sha256: str) -> CorpusManifest:
    _check_digest(expected_manifest_sha256)
    raw = _read_regular_at(corpus_fd, MANIFEST_FILENAME, MAX_CORPUS_BYTES)
    _require(_digest(raw) == expected_manifest_sha256, "manifest_hash_mismatch")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: _require(False, "invalid_manifest"))
    except CorpusError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise CorpusError("invalid_manifest") from None
    manifest = CorpusManifest.from_dict(value)
    _require(raw == _canonical_json(manifest.to_dict()).encode("ascii"), "noncanonical_manifest")
    return manifest


def _check_directory_contents(corpus_fd: int, manifest: CorpusManifest) -> None:
    """A complete corpus has exactly its sanitized cases and final marker."""
    try:
        names = set(os.listdir(corpus_fd))
    except OSError:
        raise CorpusError("invalid_corpus_file") from None
    expected = {MANIFEST_FILENAME, *(case.filename for case in manifest.cases)}
    _require(names == expected, "unexpected_corpus_file")


def write_corpus(output_root: str | Path, corpus_name: str, record_bodies: Sequence[str | bytes], *,
                 expected_pins: Mapping[str, Any],
                 source_reviews: Mapping[int, evidence.SourceReview] | None = None) -> tuple[Path, str]:
    """Create one new complete corpus and return its directory and manifest hash.

    Every input must already be a sanitized named-conformance record.  Reviews
    are supplied by the caller and are never serialized into the corpus.
    """
    _require(isinstance(expected_pins, Mapping), "invalid_pins")
    _require(isinstance(record_bodies, Sequence) and not isinstance(record_bodies, (str, bytes)),
             "invalid_records")
    _require(1 <= len(record_bodies) <= MAX_CASES, "invalid_case_count")
    _require(source_reviews is None or isinstance(source_reviews, Mapping), "invalid_source_review")
    expected = dict(expected_pins)
    seen_reviews: set[int] = set()
    prepared: list[tuple[CorpusCase, str]] = []
    seen_ordinals: set[int] = set()
    for body in record_bodies:
        provisional = _source_header(body)
        review = _review_for(provisional, source_reviews, seen_reviews=seen_reviews)
        try:
            record = evidence.parse_record(body, expected_pins=expected, source_review=review)
        except evidence.EvidenceError as error:
            raise CorpusError(str(error)) from None
        value = record.to_dict()
        ordinal = value["source"]["capture_ordinal"]
        _require(value["source"]["origin"] != "transient_live", "transient_source_not_retainable")
        _require(ordinal not in seen_ordinals, "duplicate_case")
        seen_ordinals.add(ordinal)
        document = record.document_json
        _require(len(document.encode("ascii")) <= MAX_CASE_BYTES, "case_too_large")
        prepared.append((CorpusCase(ordinal, _case_filename(ordinal), value["source"]["origin"], record.sha256), document))
    _require(source_reviews is None or set(source_reviews) == seen_reviews, "unexpected_source_review")
    prepared.sort(key=lambda item: item[0].ordinal)
    manifest = CorpusManifest(tuple(item[0] for item in prepared), _digest(evidence.canonical_json(expected)))
    root = _output_root(output_root)
    name = _check_corpus_name(corpus_name)
    destination = _corpus_path(root, name, must_exist=False)
    manifest_body = _canonical_json(manifest.to_dict())
    total_bytes = len(manifest_body.encode("ascii")) + sum(
        len(document.encode("ascii")) for _case, document in prepared
    )
    _require(total_bytes <= MAX_CORPUS_BYTES, "corpus_too_large")
    root_fd, corpus_fd = _open_new_corpus(root, name)
    try:
        for case, document in prepared:
            _write_exclusive_at(corpus_fd, case.filename, document)
        # This is deliberately last: its finalized marker is the completion gate.
        _assert_directory_binding(root_fd, name, corpus_fd)
        _write_exclusive_at(corpus_fd, MANIFEST_FILENAME, manifest_body)
        _assert_directory_binding(root_fd, name, corpus_fd)
    finally:
        os.close(corpus_fd)
        os.close(root_fd)
    return destination, _digest(manifest_body)


def load_corpus(output_root: str | Path, corpus_name: str, *, expected_manifest_sha256: str,
                expected_pins: Mapping[str, Any],
                source_reviews: Mapping[int, evidence.SourceReview] | None = None) -> tuple[evidence.NamedConformanceRecord, ...]:
    """Reload a complete corpus only against caller-anchored identities/reviews."""
    _require(isinstance(expected_pins, Mapping), "invalid_pins")
    _require(source_reviews is None or isinstance(source_reviews, Mapping), "invalid_source_review")
    root = _output_root(output_root)
    name = _check_corpus_name(corpus_name)
    root_fd, corpus_fd = _open_existing_corpus(root, name)
    try:
        manifest = _load_manifest(corpus_fd, expected_manifest_sha256)
        _check_directory_contents(corpus_fd, manifest)
        expected = dict(expected_pins)
        _require(manifest.pins_sha256 == _digest(evidence.canonical_json(expected)), "changed_pin")
        total_bytes = len(_canonical_json(manifest.to_dict()).encode("ascii"))
        seen_reviews: set[int] = set()
        records: list[evidence.NamedConformanceRecord] = []
        for case in manifest.cases:
            raw = _read_regular_at(corpus_fd, case.filename, MAX_CASE_BYTES)
            total_bytes += len(raw)
            _require(total_bytes <= MAX_CORPUS_BYTES, "corpus_too_large")
            provisional = _source_header(raw)
            review = _review_for(provisional, source_reviews, seen_reviews=seen_reviews)
            try:
                record = evidence.parse_record(raw, expected_pins=expected, source_review=review)
            except evidence.EvidenceError as error:
                raise CorpusError(str(error)) from None
            value = record.to_dict()
            _require(value["source"]["capture_ordinal"] == case.ordinal
                     and value["source"]["origin"] == case.origin
                     and record.sha256 == case.record_sha256, "swapped_case")
            _require(raw == record.document_json.encode("ascii"), "noncanonical_case")
            records.append(record)
        _require(source_reviews is None or set(source_reviews) == seen_reviews, "unexpected_source_review")
        _assert_directory_binding(root_fd, name, corpus_fd)
        return tuple(records)
    finally:
        os.close(corpus_fd)
        os.close(root_fd)
