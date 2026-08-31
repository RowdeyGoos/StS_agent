from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from game.backends.headless.fixture_backend import FixtureBackend
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
    replay = backend.reset(fixture_id)
    assert first == replay
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
