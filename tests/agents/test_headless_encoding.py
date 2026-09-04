"""Focused checks for the frozen public ``headless_encoding_v1`` boundary."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from game.agents.headless_encoding import (
    CANDIDATE_FEATURE_NAMES,
    ENCODING_FINGERPRINT,
    ENTITY_FEATURE_NAMES,
    GLOBAL_FEATURE_NAMES,
    PUBLIC_EVENT_FEATURE_NAMES,
    CollatedPolicyBatch,
    EncodedPolicyView,
    HeadlessEncodingError,
    collate_policy_views,
    encode_policy_view,
    encoding_schema,
)
from game.backends.headless.fixture_backend import FixtureBackend
from game.contracts.headless_v0 import (
    CombatEndTurnCandidate,
    CombatPlayCardCandidate,
    CombatOutcome,
    DecisionPhase,
    DecisionStatus,
    PolicyView,
    PublicObservation,
    PublicScope,
    ActionRequest,
    HeadlessBinding,
    canonical_json_bytes,
    combat_card_reference,
    combat_enemy_reference,
)


def _views(fixture_id: str) -> tuple[PolicyView, ...]:
    backend = FixtureBackend()
    decision = backend.reset(fixture_id)
    result = []
    while True:
        result.append(decision.policy_view())
        if not decision.candidates:
            return tuple(result)
        request = ActionRequest(HeadlessBinding.for_candidate(decision, decision.candidates[0].candidate_id))
        decision = backend.apply(request).next_decision


def test_schema_is_exact_embedded_copy_and_dimensions_are_frozen() -> None:
    schema_path = Path("docs/research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert encoding_schema() == schema
    assert ENCODING_FINGERPRINT == sha256(
        b"headless_encoding_v1.schema.v1" + bytes((0,)) + canonical_json_bytes(schema)
    ).hexdigest()


def test_schema_accessor_is_mutation_isolated() -> None:
    first = encoding_schema()
    first["global_feature_names"][0] = "corrupted"
    assert encoding_schema()["global_feature_names"][0] == "status.actionable"
    assert tuple(map(len, (GLOBAL_FEATURE_NAMES, ENTITY_FEATURE_NAMES, PUBLIC_EVENT_FEATURE_NAMES, CANDIDATE_FEATURE_NAMES))) == (47, 90, 78, 557)


@pytest.mark.parametrize("fixture_id", ("combat", "reward", "map", "rest", "event", "unsupported"))
def test_fixture_views_encode_every_supported_phase_and_status(fixture_id: str) -> None:
    encoded = tuple(encode_policy_view(view) for view in _views(fixture_id))
    assert all(item.encoding_fingerprint == ENCODING_FINGERPRINT for item in encoded)
    assert all(len(item.global_features) == 47 for item in encoded)
    assert all(len(row) == 90 for item in encoded for row in item.entity_rows)
    assert all(len(row) == 78 for item in encoded for row in item.public_event_rows)
    assert all(len(row) == 557 for item in encoded for row in item.candidate_rows)
    assert all(len(item.candidate_rows) == len(item.candidate_ids) for item in encoded)
    assert all(not item.candidate_rows for item, view in zip(encoded, _views(fixture_id)) if view.status is not DecisionStatus.ACTIONABLE)


def test_unknown_semantic_identifier_uses_explicit_unknown_bucket() -> None:
    scope = PublicScope(0, 0, {kind: 0 for kind in ("card", "enemy", "reward", "offer", "node", "option")})
    enemy_id = "simple_enemy"
    card_id = "novel_public_card"
    enemy_ref = combat_enemy_reference(scope, enemy_id, 0)
    card_ref = combat_card_reference(scope, card_id, 0)
    observation = PublicObservation(
        DecisionPhase.COMBAT,
        {
            "turn": 1,
            "player": {"hp": 10, "max_hp": 10, "block": 0, "energy": 1, "energy_per_turn": 1, "strength": 0, "statuses": {"shrink": 0, "vulnerable": 0}},
            "enemies": [{"enemy_ref": enemy_ref, "enemy_definition_id": enemy_id, "hp": 5, "max_hp": 5, "block": 0, "strength": 0, "alive": True, "statuses": {"shrink": 0, "vulnerable": 0}, "intent": {"kind": "attack", "attack_count": 1, "attack_damage": 1, "block_gain": 0, "strength_gain": 0, "status_kind": "none", "status_stacks": 0, "slimed_added": 0}}],
            "hand": [{"card_ref": card_ref, "card_definition_id": card_id, "cost": 1, "upgraded": False}],
            "draw_pile_size": 0, "discard_pile_size": 0, "exhaust_pile_size": 0,
            "terminal": False, "outcome": CombatOutcome.ONGOING.value,
        },
        scope,
    )
    play = CombatPlayCardCandidate(scope.decision_scope, card_ref, enemy_ref)
    view = PolicyView(DecisionStatus.ACTIONABLE, DecisionPhase.COMBAT, observation, (play, CombatEndTurnCandidate(scope.decision_scope)), ())
    encoded = encode_policy_view(view)
    unknown = ENTITY_FEATURE_NAMES.index("card_definition.__unknown__")
    assert encoded.entity_rows[1][unknown] == 1.0
    row = encoded.candidate_rows[encoded.candidate_ids.index(play.candidate_id)]
    assert row[11 + 1 + unknown] == 1.0


def test_collation_preserves_order_and_excludes_padding_from_masks() -> None:
    combat = encode_policy_view(_views("combat")[0])
    unsupported = encode_policy_view(_views("unsupported")[0])
    batch = collate_policy_views((unsupported, combat))
    assert isinstance(batch, CollatedPolicyBatch)
    assert batch.global_features.dtype == np.float32
    assert batch.entity_mask.dtype == np.bool_
    assert batch.candidate_ids == (unsupported.candidate_ids, combat.candidate_ids)
    assert batch.candidate_mask[0].sum() == 0
    assert batch.candidate_mask[1].sum() == len(combat.candidate_rows)
    assert np.all(batch.candidate_features[0] == 0.0)


def test_waiting_view_encodes_context_but_never_candidates() -> None:
    actionable = _views("combat")[0]
    waiting = PolicyView(
        DecisionStatus.WAITING,
        actionable.phase,
        actionable.observation,
        (),
        actionable.public_events,
    )
    encoded = encode_policy_view(waiting)
    assert encoded.global_features[GLOBAL_FEATURE_NAMES.index("status.waiting")] == 1.0
    assert encoded.candidate_rows == ()
    assert encoded.candidate_ids == ()


def test_empty_batch_and_malformed_records_fail_closed() -> None:
    empty = collate_policy_views(())
    assert empty.global_features.shape == (0, 47)
    assert empty.entity_features.shape == (0, 0, 90)
    assert empty.public_event_features.shape == (0, 0, 78)
    assert empty.candidate_features.shape == (0, 0, 557)
    valid = encode_policy_view(_views("combat")[0])
    malformed = EncodedPolicyView(
        valid.encoding_version, valid.encoding_fingerprint, valid.global_features,
        valid.entity_rows, valid.public_event_rows, valid.candidate_rows,
        ("cand." + "z" * 64,) * len(valid.candidate_rows),
    )
    with pytest.raises(HeadlessEncodingError):
        collate_policy_views((malformed,))
