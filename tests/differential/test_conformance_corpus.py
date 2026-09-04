"""Synthetic-only tests for the named conformance retention codec."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import pytest

from game.analysis import conformance_corpus as corpus
from game.analysis import conformance_evidence as evidence


PINS = evidence.pins_for_harness("a" * 64)


def boundary(role: str, ordinal: int, amount: int = 25) -> dict:
    post = role == "post"
    return {
        "role": role, "ordinal": ordinal, "family": "reward", "status": "ready", "screen": "rewards",
        "player": {"hp": 60, "max_hp": 80, "gold": amount if post else 0, "deck_count": 10},
        "rewards": [{"category": "gold", "claimed": post, "amount": amount, "offer_count": 0}],
        "candidate_categories": ["proceed"] if post else ["claim_gold", "proceed"],
    }


def record(ordinal: int = 0, origin: str = "synthetic") -> dict:
    pre = boundary("pre", ordinal * 2)
    return {
        "schema": evidence.SCHEMA, "case_id": evidence.CASE_ID, "pins": dict(PINS),
        "source": {"origin": origin, "capture_ordinal": ordinal},
        "boundaries": {"pre": pre, "post": boundary("post", ordinal * 2 + 1)},
        "selection": {"category": "claim_gold", "amount": 25},
        "alignment": evidence.alignment_for(pre, 25), "correspondence": "bound_one_claim",
        "findings": [{"field": field, "outcome": "passed", "code": "equal"} for field in evidence.FIELD_NAMES],
        "broader_comparison": "not_evaluated", "omissions": list(evidence.OMISSIONS), "admission": "not_admitted",
    }


def body(value: dict) -> str:
    return evidence.canonical_json(value)


def source_review(value: dict) -> evidence.SourceReview:
    record_digest = sha256(body(value).encode("ascii")).hexdigest()
    pins_digest = sha256(evidence.canonical_json(PINS).encode("ascii")).hexdigest()
    return evidence.SourceReview(value["source"]["origin"], record_digest, pins_digest,
                                 "b" * 64 if value["source"]["origin"] == "retained_live" else None)


def test_exact_deterministic_synthetic_output_and_caller_anchored_reload(tmp_path: Path):
    values = [record(2), record(0)]
    destination, manifest_hash = corpus.write_corpus(tmp_path, "synthetic", [body(item) for item in values], expected_pins=PINS)
    assert destination == tmp_path / "synthetic"
    assert (destination / "case-000000.json").read_text() == body(record(0))
    assert (destination / "case-000002.json").read_text() == body(record(2))
    manifest = corpus.CorpusManifest((
        corpus.CorpusCase(0, "case-000000.json", "synthetic", sha256(body(record(0)).encode("ascii")).hexdigest()),
        corpus.CorpusCase(2, "case-000002.json", "synthetic", sha256(body(record(2)).encode("ascii")).hexdigest()),
    ), sha256(evidence.canonical_json(PINS).encode("ascii")).hexdigest())
    expected_manifest = evidence.canonical_json(manifest.to_dict())
    assert (destination / "manifest.json").read_text() == expected_manifest
    assert manifest_hash == sha256(expected_manifest.encode("ascii")).hexdigest()
    loaded = corpus.load_corpus(tmp_path, "synthetic", expected_manifest_sha256=manifest_hash, expected_pins=PINS)
    assert [item.to_dict() for item in loaded] == [record(0), record(2)]


@pytest.mark.parametrize("name", ["../escape", "/absolute", "UPPER", "a/child", "a.b"])
def test_output_path_escapes_reject(tmp_path: Path, name: str):
    with pytest.raises(corpus.CorpusError):
        corpus.write_corpus(tmp_path, name, [body(record())], expected_pins=PINS)


def test_exclusive_output_and_incomplete_directory_cannot_be_loaded(tmp_path: Path):
    destination = tmp_path / "partial"
    destination.mkdir()
    (destination / "case-000000.json").write_text(body(record()))
    with pytest.raises(corpus.CorpusError, match="missing_corpus|invalid_corpus_file"):
        corpus.load_corpus(tmp_path, "partial", expected_manifest_sha256="a" * 64, expected_pins=PINS)
    with pytest.raises(corpus.CorpusError, match="output_exists"):
        corpus.write_corpus(tmp_path, "partial", [body(record())], expected_pins=PINS)


def test_rejects_changed_pins_truncated_swapped_and_duplicate_cases(tmp_path: Path):
    destination, manifest_hash = corpus.write_corpus(tmp_path, "cases", [body(record(0)), body(record(1))], expected_pins=PINS)
    changed = dict(PINS)
    changed["rules_sha256"] = "f" * 64
    with pytest.raises(corpus.CorpusError, match="changed_pin"):
        corpus.load_corpus(tmp_path, "cases", expected_manifest_sha256=manifest_hash, expected_pins=changed)
    (destination / "case-000001.json").unlink()
    with pytest.raises(corpus.CorpusError):
        corpus.load_corpus(tmp_path, "cases", expected_manifest_sha256=manifest_hash, expected_pins=PINS)
    destination, manifest_hash = corpus.write_corpus(tmp_path, "swapped", [body(record(0)), body(record(1))], expected_pins=PINS)
    first = (destination / "case-000000.json").read_bytes()
    second = (destination / "case-000001.json").read_bytes()
    (destination / "case-000000.json").write_bytes(second)
    (destination / "case-000001.json").write_bytes(first)
    with pytest.raises(corpus.CorpusError, match="swapped_case"):
        corpus.load_corpus(tmp_path, "swapped", expected_manifest_sha256=manifest_hash, expected_pins=PINS)
    with pytest.raises(corpus.CorpusError, match="duplicate_case"):
        corpus.write_corpus(tmp_path, "duplicate", [body(record(0)), body(record(0))], expected_pins=PINS)


def test_manifest_anchor_and_final_marker_are_required(tmp_path: Path):
    destination, manifest_hash = corpus.write_corpus(tmp_path, "anchor", [body(record())], expected_pins=PINS)
    with pytest.raises(corpus.CorpusError, match="manifest_hash_mismatch"):
        corpus.load_corpus(tmp_path, "anchor", expected_manifest_sha256="b" * 64, expected_pins=PINS)
    manifest = corpus.CorpusManifest.from_dict(json.loads((destination / "manifest.json").read_text()))
    altered = manifest.to_dict()
    altered["finalized"] = False
    (destination / "manifest.json").write_text(evidence.canonical_json(altered))
    altered_hash = sha256(evidence.canonical_json(altered).encode("ascii")).hexdigest()
    with pytest.raises(corpus.CorpusError, match="missing_final_manifest"):
        corpus.load_corpus(tmp_path, "anchor", expected_manifest_sha256=altered_hash, expected_pins=PINS)


def test_manifest_extra_or_duplicate_fields_and_unlisted_partial_case_reject(tmp_path: Path):
    destination, manifest_hash = corpus.write_corpus(tmp_path, "closed", [body(record())], expected_pins=PINS)
    (destination / "partial.json").write_text(body(record(1)))
    with pytest.raises(corpus.CorpusError, match="unexpected_corpus_file"):
        corpus.load_corpus(tmp_path, "closed", expected_manifest_sha256=manifest_hash, expected_pins=PINS)
    (destination / "partial.json").unlink()
    raw = (destination / "manifest.json").read_text()
    duplicate = raw.replace('"schema":"named_conformance_corpus_v1"',
                            '"schema":"named_conformance_corpus_v1","schema":"named_conformance_corpus_v1"', 1)
    (destination / "manifest.json").write_text(duplicate)
    duplicate_hash = sha256(duplicate.encode("ascii")).hexdigest()
    with pytest.raises(corpus.CorpusError, match="duplicate_field"):
        corpus.load_corpus(tmp_path, "closed", expected_manifest_sha256=duplicate_hash, expected_pins=PINS)


def test_retained_origin_requires_external_review_and_cannot_be_replaced_by_synthetic(tmp_path: Path):
    retained = record(0, "retained_live")
    review = source_review(retained)
    destination, manifest_hash = corpus.write_corpus(tmp_path, "retained", [body(retained)], expected_pins=PINS,
                                                      source_reviews={0: review})
    with pytest.raises(corpus.CorpusError, match="unreviewed_live_origin"):
        corpus.load_corpus(tmp_path, "retained", expected_manifest_sha256=manifest_hash, expected_pins=PINS)
    synthetic = record(0)
    (destination / "case-000000.json").write_text(body(synthetic))
    with pytest.raises(corpus.CorpusError):
        corpus.load_corpus(tmp_path, "retained", expected_manifest_sha256=manifest_hash, expected_pins=PINS,
                           source_reviews={0: review})


def test_transient_live_observation_is_never_a_replayable_corpus(tmp_path: Path):
    transient = record(0, "transient_live")
    with pytest.raises(corpus.CorpusError, match="transient_source_not_retainable"):
        corpus.write_corpus(tmp_path, "transient", [body(transient)], expected_pins=PINS,
                             source_reviews={0: source_review(transient)})


def test_no_secret_canary_or_extra_fields_can_enter_records_or_errors(tmp_path: Path):
    value = record()
    value["secret_canary"] = "raw_payload_credential_canary"
    with pytest.raises(corpus.CorpusError) as error:
        corpus.write_corpus(tmp_path, "canary", [body(value)], expected_pins=PINS)
    assert "canary" not in str(error.value)
    clean = record()
    with pytest.raises(corpus.CorpusError) as error:
        corpus.write_corpus(tmp_path, "review", [body(clean)], expected_pins=PINS,
                             source_reviews={0: source_review({**clean, "source": {"origin": "transient_live", "capture_ordinal": 0}})})
    assert "canary" not in str(error.value)


def test_case_and_corpus_ceilings_are_explicit(tmp_path: Path):
    assert corpus.MAX_CASES == 16
    assert corpus.MAX_CASE_BYTES == evidence.MAX_RECORD_BYTES
    assert corpus.MAX_CORPUS_BYTES == 1_048_576
    records = [body(record(index)) for index in range(corpus.MAX_CASES + 1)]
    with pytest.raises(corpus.CorpusError, match="invalid_case_count"):
        corpus.write_corpus(tmp_path, "too-many", records, expected_pins=PINS)


def test_case_read_is_bounded_before_an_oversized_file_is_materialized(tmp_path: Path):
    destination, manifest_hash = corpus.write_corpus(tmp_path, "bounded", [body(record())], expected_pins=PINS)
    with (destination / "case-000000.json").open("ab") as handle:
        handle.write(b" " * (corpus.MAX_CASE_BYTES + 1))
    with pytest.raises(corpus.CorpusError, match="corpus_too_large"):
        corpus.load_corpus(tmp_path, "bounded", expected_manifest_sha256=manifest_hash, expected_pins=PINS)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="named pipes are unavailable on this platform")
def test_writerless_fifo_case_rejects_in_a_bounded_subprocess(tmp_path: Path):
    destination, manifest_hash = corpus.write_corpus(tmp_path, "fifo", [body(record())], expected_pins=PINS)
    case_path = destination / "case-000000.json"
    case_path.unlink()
    os.mkfifo(case_path, 0o600)
    script = """
from game.analysis import conformance_corpus as corpus
from game.analysis import conformance_evidence as evidence
import sys
try:
    corpus.load_corpus(sys.argv[1], "fifo", expected_manifest_sha256=sys.argv[2],
                       expected_pins=evidence.pins_for_harness("a" * 64))
except corpus.CorpusError as error:
    print(error)
    raise SystemExit(0)
raise SystemExit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), manifest_hash],
        check=False, capture_output=True, text=True, timeout=2,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "invalid_corpus_file"


def test_aggregate_ceiling_is_preflighted_for_write_and_mirrored_by_load(tmp_path: Path, monkeypatch):
    value = record()
    case_body = body(value)
    manifest = corpus.CorpusManifest((
        corpus.CorpusCase(0, "case-000000.json", "synthetic", sha256(case_body.encode("ascii")).hexdigest()),
    ), sha256(evidence.canonical_json(PINS).encode("ascii")).hexdigest())
    exact_total = len(case_body.encode("ascii")) + len(evidence.canonical_json(manifest.to_dict()).encode("ascii"))
    monkeypatch.setattr(corpus, "MAX_CORPUS_BYTES", exact_total)
    _destination, manifest_hash = corpus.write_corpus(tmp_path, "exact", [case_body], expected_pins=PINS)
    assert corpus.load_corpus(tmp_path, "exact", expected_manifest_sha256=manifest_hash, expected_pins=PINS)
    monkeypatch.setattr(corpus, "MAX_CORPUS_BYTES", exact_total - 1)
    with pytest.raises(corpus.CorpusError, match="corpus_too_large"):
        corpus.write_corpus(tmp_path, "short", [case_body], expected_pins=PINS)


def test_writer_uses_private_permissions_and_no_follow_directory_anchor(tmp_path: Path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    original_mkdir = corpus.os.mkdir

    def replace_after_create(name, mode=0o777, *, dir_fd=None):
        result = original_mkdir(name, mode, dir_fd=dir_fd)
        if name == "raced":
            os.rmdir(tmp_path / name)
            os.symlink(outside, tmp_path / name)
        return result

    monkeypatch.setattr(corpus.os, "mkdir", replace_after_create)
    with pytest.raises(corpus.CorpusError, match="corpus_write_failed"):
        corpus.write_corpus(tmp_path, "raced", [body(record())], expected_pins=PINS)
    assert list(outside.iterdir()) == []
    monkeypatch.setattr(corpus.os, "mkdir", original_mkdir)
    destination, _manifest_hash = corpus.write_corpus(tmp_path, "private", [body(record())], expected_pins=PINS)
    assert stat.S_IMODE(destination.stat().st_mode) == 0o700
    assert stat.S_IMODE((destination / "case-000000.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((destination / "manifest.json").stat().st_mode) == 0o600


def test_loader_rejects_a_replaced_corpus_symlink_and_partial_writes_lack_marker(tmp_path: Path, monkeypatch):
    destination, manifest_hash = corpus.write_corpus(tmp_path, "reload", [body(record())], expected_pins=PINS)
    outside = tmp_path / "external"
    outside.mkdir()
    shutil.rmtree(destination)
    os.symlink(outside, destination)
    with pytest.raises(corpus.CorpusError, match="missing_corpus"):
        corpus.load_corpus(tmp_path, "reload", expected_manifest_sha256=manifest_hash, expected_pins=PINS)

    original_write = corpus._write_exclusive_at

    def fail_second(directory_fd, filename, payload):
        if filename == "case-000001.json":
            raise corpus.CorpusError("injected_write_failure")
        original_write(directory_fd, filename, payload)

    monkeypatch.setattr(corpus, "_write_exclusive_at", fail_second)
    with pytest.raises(corpus.CorpusError, match="injected_write_failure"):
        corpus.write_corpus(tmp_path, "interrupted", [body(record(0)), body(record(1))], expected_pins=PINS)
    assert not (tmp_path / "interrupted" / "manifest.json").exists()
