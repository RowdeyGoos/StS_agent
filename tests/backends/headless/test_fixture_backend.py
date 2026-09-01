from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from shutil import copytree

import pytest

from game.backends.headless.fixture_backend import FixtureBackend, FixtureSnapshot
from game.contracts.headless_v0 import (
    ActionRequest,
    DecisionPhase,
    DecisionStatus,
    HeadlessBinding,
    TransitionReason,
    TransitionResult,
    canonical_json,
)


FIXTURES = Path(__file__).parents[2] / "fixtures" / "headless_v0"


def _request_for_first_candidate(backend: FixtureBackend) -> ActionRequest:
    decision = backend.observe()
    return ActionRequest(HeadlessBinding.for_candidate(decision, decision.candidates[0].candidate_id))


def _copy_corpus(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "headless_v0"
    copytree(FIXTURES, root)
    return root


def _write_json(path: Path, value: object) -> None:
    path.write_text(canonical_json(value), encoding="utf-8")


def _rehash(root: Path) -> None:
    manifest = json.loads((root / "manifest.json").read_text())
    for fixture_id in manifest["fixtures"]:
        payload = json.loads((root / f"{fixture_id}.json").read_text())
        manifest["fixtures"][fixture_id] = sha256(canonical_json(payload).encode()).hexdigest()
    _write_json(root / "manifest.json", manifest)


@pytest.mark.parametrize(
    ("fixture_id", "status", "phase"),
    (
        ("combat", DecisionStatus.TERMINAL, DecisionPhase.TERMINAL),
        ("reward", DecisionStatus.TERMINAL, DecisionPhase.TERMINAL),
        ("map", DecisionStatus.TERMINAL, DecisionPhase.TERMINAL),
        ("rest", DecisionStatus.TERMINAL, DecisionPhase.TERMINAL),
        ("event", DecisionStatus.TERMINAL, DecisionPhase.TERMINAL),
        ("unsupported", DecisionStatus.UNSUPPORTED, DecisionPhase.UNSUPPORTED),
    ),
)
def test_synthetic_fixture_routes_are_deterministic(
    fixture_id: str,
    status: DecisionStatus,
    phase: DecisionPhase,
) -> None:
    backend = FixtureBackend()
    first = backend.reset({"fixture_id": fixture_id})
    assert FixtureBackend().reset(fixture_id) == first
    replay = backend.reset(fixture_id)
    assert first.run_id != replay.run_id
    while backend.observe().status is DecisionStatus.ACTIONABLE:
        transition = backend.apply(_request_for_first_candidate(backend))
        assert transition.result is TransitionResult.ACCEPTED
    assert backend.observe().status is status
    assert backend.observe().phase is phase


def test_rejects_unadvertised_candidate_and_stale_binding() -> None:
    backend = FixtureBackend()
    decision = backend.reset("combat")
    rejected = backend.apply(
        ActionRequest(
            HeadlessBinding(
                decision.run_id,
                decision.decision_sequence,
                decision.decision_hash,
                "cand." + "0" * 64,
            )
        )
    )
    assert rejected.result is TransitionResult.REJECTED
    assert rejected.reason is TransitionReason.INVALID_CANDIDATE
    assert backend.observe() == decision
    request = _request_for_first_candidate(backend)
    assert backend.apply(request).result is TransitionResult.ACCEPTED
    stale = backend.apply(request)
    assert stale.result is TransitionResult.STALE
    assert stale.reason is TransitionReason.STALE_BINDING


def test_cursor_snapshot_restore_replays_exact_decision() -> None:
    backend = FixtureBackend()
    backend.reset("reward")
    snapshot = backend.snapshot()
    expected = backend.observe()
    backend.apply(_request_for_first_candidate(backend))
    assert backend.restore(snapshot) == expected


def test_reset_stales_prior_binding_and_preserves_history_within_a_route() -> None:
    backend = FixtureBackend()
    first = backend.reset("combat")
    request = _request_for_first_candidate(backend)
    second = backend.apply(request).next_decision
    assert second.observation.public_scope.history_ordinal == first.observation.public_scope.history_ordinal
    assert second.observation.public_scope.decision_ordinal == first.observation.public_scope.decision_ordinal + 1
    assert set(second.observation.public_scope.reveal_ordinals.values()) == {1}
    reset = backend.reset("combat")
    assert reset.observation.public_scope.history_ordinal != first.observation.public_scope.history_ordinal
    assert backend.apply(request).result is TransitionResult.STALE


def test_snapshots_are_provenance_bound_issued_and_atomic() -> None:
    backend = FixtureBackend()
    backend.reset("combat")
    snapshot = backend.snapshot()
    current = backend.observe()
    with pytest.raises(ValueError):
        backend.restore(FixtureSnapshot(snapshot.corpus_fingerprint, snapshot.backend_fingerprint, "combat", snapshot.run_generation, 99))
    assert backend.observe() == current
    with pytest.raises(ValueError):
        FixtureBackend().restore(snapshot)
    assert backend.apply(_request_for_first_candidate(backend)).result is TransitionResult.ACCEPTED
    assert backend.restore(snapshot) == current
    assert backend.reset("combat").decision_sequence == 0
    with pytest.raises(ValueError):
        backend.restore(snapshot)
    backend.close()
    with pytest.raises(RuntimeError):
        backend.restore(snapshot)
    assert backend.reset("combat").status is DecisionStatus.ACTIONABLE


def test_snapshot_rejects_a_different_valid_corpus(tmp_path: Path) -> None:
    source = FixtureBackend()
    source.reset("combat")
    snapshot = source.snapshot()
    root = _copy_corpus(tmp_path)
    combat = json.loads((root / "combat.json").read_text())
    combat["steps"][0]["action"] = "combat.end_turn"
    _write_json(root / "combat.json", combat)
    _rehash(root)
    other = FixtureBackend(root)
    other.reset("combat")
    with pytest.raises(ValueError, match="different corpus"):
        other.restore(snapshot)


@pytest.mark.parametrize("bad_cursor", (True, 1.0, -1))
def test_snapshot_rejects_non_integer_or_negative_cursor(bad_cursor: object) -> None:
    with pytest.raises(ValueError):
        FixtureSnapshot("a" * 64, "b" * 64, "combat", 1, bad_cursor)  # type: ignore[arg-type]


def test_constructor_rejects_bad_routes_action_links_and_unsafe_fixture_ids(tmp_path: Path) -> None:
    root = _copy_corpus(tmp_path)
    combat = json.loads((root / "combat.json").read_text())
    combat["steps"][0]["routes"] = {"wrong": 1}
    _write_json(root / "combat.json", combat)
    _rehash(root)
    with pytest.raises(ValueError):
        FixtureBackend(root)

    root = _copy_corpus(tmp_path / "unfinished")
    combat = json.loads((root / "combat.json").read_text())
    combat["steps"][-1] = {
        "action": "combat.end_turn",
        "phase": "combat",
        "routes": {"recorded": 3},
        "status": "actionable",
    }
    _write_json(root / "combat.json", combat)
    _rehash(root)
    with pytest.raises(ValueError, match="end at a terminal"):
        FixtureBackend(root)

    root = _copy_corpus(tmp_path / "room")
    rest = json.loads((root / "rest.json").read_text())
    rest["steps"][0]["room_kind"] = "event"
    _write_json(root / "rest.json", rest)
    _rehash(root)
    with pytest.raises(ValueError):
        FixtureBackend(root)

    root = _copy_corpus(tmp_path / "again")
    combat = json.loads((root / "combat.json").read_text())
    combat["steps"][0]["routes"] = {"recorded": True}
    _write_json(root / "combat.json", combat)
    _rehash(root)
    with pytest.raises(ValueError):
        FixtureBackend(root)

    root = _copy_corpus(tmp_path / "phase")
    combat = json.loads((root / "combat.json").read_text())
    combat["steps"][0]["phase"] = "reward"
    _write_json(root / "combat.json", combat)
    _rehash(root)
    with pytest.raises(ValueError):
        FixtureBackend(root)

    root = _copy_corpus(tmp_path / "traversal")
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["fixtures"]["../escape"] = manifest["fixtures"].pop("combat")
    _write_json(root / "manifest.json", manifest)
    with pytest.raises(ValueError):
        FixtureBackend(root)


def test_constructor_rejects_manifest_symlinks_and_uses_bounded_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _copy_corpus(tmp_path)
    outside = tmp_path / "outside-manifest.json"
    outside.write_bytes((root / "manifest.json").read_bytes())
    (root / "manifest.json").unlink()
    (root / "manifest.json").symlink_to(outside)
    with pytest.raises(ValueError, match="symlinks"):
        FixtureBackend(root)

    root = _copy_corpus(tmp_path / "bounded")
    (root / "manifest.json").write_bytes(b" " * 20_000)
    original_open = Path.open
    requested_sizes: list[int] = []

    class BoundedSource:
        def __init__(self, source: object) -> None:
            self._source = source

        def __enter__(self) -> "BoundedSource":
            return self

        def __exit__(self, *args: object) -> None:
            self._source.close()  # type: ignore[union-attr]

        def read(self, size: int = -1) -> bytes:
            requested_sizes.append(size)
            return self._source.read(size)  # type: ignore[union-attr]

    def bounded_open(path: Path, *args: object, **kwargs: object) -> BoundedSource:
        return BoundedSource(original_open(path, *args, **kwargs))

    monkeypatch.setattr(Path, "open", bounded_open)
    with pytest.raises(ValueError):
        FixtureBackend(root)
    assert requested_sizes == [16_385]


def test_constructor_rejects_empty_oversized_and_mutable_corpora(tmp_path: Path) -> None:
    root = _copy_corpus(tmp_path)
    _write_json(root / "manifest.json", {"fixtures": {}, "schema": "headless_v0_fixture_corpus_v1"})
    with pytest.raises(ValueError):
        FixtureBackend(root)

    root = _copy_corpus(tmp_path / "large")
    (root / "manifest.json").write_bytes(b" " * 20_000)
    with pytest.raises(ValueError):
        FixtureBackend(root)

    root = _copy_corpus(tmp_path / "immutable")
    backend = FixtureBackend(root)
    with pytest.raises(TypeError):
        backend._fixtures["combat"]["steps"][0]["status"] = "terminal"  # type: ignore[index]
    original = backend.reset("combat")
    payload = json.loads((root / "combat.json").read_text())
    payload["steps"][0]["action"] = "combat.end_turn"
    _write_json(root / "combat.json", payload)
    assert backend.observe() == original
    with pytest.raises(ValueError):
        backend.reset("not-a-fixture")
    assert backend.observe() == original


def test_manifest_is_truthful_and_corpus_hashes_are_frozen() -> None:
    backend = FixtureBackend()
    capabilities = backend.manifest().capabilities
    assert capabilities.deterministic_reset and capabilities.fixture_playback
    assert not capabilities.counterfactual_stepping
    assert not capabilities.live_truth
    assert capabilities.snapshot_restore
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for fixture_id, expected_hash in manifest["fixtures"].items():
        payload = json.loads((FIXTURES / f"{fixture_id}.json").read_text())
        assert sha256(canonical_json(payload).encode("utf-8")).hexdigest() == expected_hash
