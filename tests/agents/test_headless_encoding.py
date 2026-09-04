"""Focused checks for the frozen public ``headless_encoding_v1`` boundary."""

from __future__ import annotations

import json
from dataclasses import replace
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
    RewardChooseCardCandidate,
    ActionRequest,
    HeadlessBinding,
    PublicEvent,
    PublicEventKind,
    RunOutcome,
    canonical_json_bytes,
    combat_card_reference,
    combat_enemy_reference,
    reward_offer_reference,
    reward_reference,
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


@pytest.mark.parametrize(
    "replacement",
    (
        "wrong-version",
        "wrong-fingerprint",
        "bad-width",
        "nan",
        "infinity",
        "out-of-range",
        "bool-coordinate",
        "candidate-count",
        "duplicate-id",
        "noncanonical-id",
        "unhashable-id",
    ),
)
def test_encoded_record_validation_never_leaks_raw_type_errors(replacement: str) -> None:
    valid = encode_policy_view(_views("reward")[0])
    record = valid
    if replacement == "wrong-version":
        record = replace(valid, encoding_version="wrong")
    elif replacement == "wrong-fingerprint":
        record = replace(valid, encoding_fingerprint="0" * 64)
    elif replacement == "bad-width":
        record = replace(valid, entity_rows=((0.0,),))
    elif replacement in {"nan", "infinity", "out-of-range", "bool-coordinate"}:
        value = {"nan": float("nan"), "infinity": float("inf"), "out-of-range": 1.1, "bool-coordinate": True}[replacement]
        record = replace(valid, global_features=(value,) + valid.global_features[1:])
    elif replacement == "candidate-count":
        record = replace(valid, candidate_ids=())
    elif replacement == "duplicate-id":
        record = replace(
            valid,
            candidate_rows=(valid.candidate_rows[0], valid.candidate_rows[0]),
            candidate_ids=(valid.candidate_ids[0], valid.candidate_ids[0]),
        )
    elif replacement == "noncanonical-id":
        record = replace(valid, candidate_ids=("cand." + "z" * 64,) * len(valid.candidate_ids))
    else:
        record = replace(valid, candidate_ids=([],))  # type: ignore[arg-type]
    with pytest.raises(HeadlessEncodingError):
        collate_policy_views((record,))


def test_all_candidate_joins_and_fixture_event_forms_use_encoder_entry_point() -> None:
    views = tuple(view for fixture in ("combat", "reward", "map", "rest", "event") for view in _views(fixture))
    encoded = tuple(encode_policy_view(view) for view in views)
    expected_candidates = {name.removeprefix("candidate_kind.") for name in CANDIDATE_FEATURE_NAMES[:11]}
    assert {candidate.kind.value for view in views for candidate in view.candidates} == expected_candidates
    assert all(len(item.candidate_rows) == len(item.candidate_ids) for item in encoded)
    fixture_events = {event.event_type.value for view in views for event in view.public_events}
    assert fixture_events == {
        "combat.card_played", "combat.turn_ended", "reward.gold_claimed",
        "reward.card_opened", "reward.card_chosen", "reward.card_skipped",
        "reward.proceeded", "map.node_chosen", "room.rest_healed",
        "room.event_option_chosen", "room.proceeded",
    }


def test_opaque_reference_reallocation_changes_ids_not_public_features() -> None:
    def make_view(scope: PublicScope) -> PolicyView:
        enemy_ref = combat_enemy_reference(scope, "simple_enemy", 0)
        card_ref = combat_card_reference(scope, "strike", 0)
        observation = PublicObservation(
            DecisionPhase.COMBAT,
            {
                "turn": 1,
                "player": {"hp": 10, "max_hp": 10, "block": 0, "energy": 1, "energy_per_turn": 1, "strength": 0, "statuses": {"shrink": 0, "vulnerable": 0}},
                "enemies": [{"enemy_ref": enemy_ref, "enemy_definition_id": "simple_enemy", "hp": 5, "max_hp": 5, "block": 0, "strength": 0, "alive": True, "statuses": {"shrink": 0, "vulnerable": 0}, "intent": {"kind": "attack", "attack_count": 1, "attack_damage": 1, "block_gain": 0, "strength_gain": 0, "status_kind": "none", "status_stacks": 0, "slimed_added": 0}}],
                "hand": [{"card_ref": card_ref, "card_definition_id": "strike", "cost": 1, "upgraded": False}],
                "draw_pile_size": 0, "discard_pile_size": 0, "exhaust_pile_size": 0,
                "terminal": False, "outcome": "ongoing",
            },
            scope,
        )
        return PolicyView(DecisionStatus.ACTIONABLE, DecisionPhase.COMBAT, observation, (CombatPlayCardCandidate(scope.decision_scope, card_ref, enemy_ref), CombatEndTurnCandidate(scope.decision_scope)), ())

    first_scope = PublicScope(0, 0, {kind: 0 for kind in ("card", "enemy", "reward", "offer", "node", "option")})
    second_scope = PublicScope(2, 2, {kind: 2 for kind in ("card", "enemy", "reward", "offer", "node", "option")})
    first_view, second_view = make_view(first_scope), make_view(second_scope)
    first, second = encode_policy_view(first_view), encode_policy_view(second_view)
    assert first.candidate_ids != second.candidate_ids
    assert [candidate.kind.value for candidate in first_view.candidates] == [
        "combat.play_card", "combat.end_turn",
    ]
    assert [candidate.kind.value for candidate in second_view.candidates] == [
        "combat.end_turn", "combat.play_card",
    ]
    assert first.candidate_ids == tuple(candidate.candidate_id for candidate in first_view.candidates)
    assert second.candidate_ids == tuple(candidate.candidate_id for candidate in second_view.candidates)
    assert [CANDIDATE_FEATURE_NAMES[row[:11].index(1.0)] for row in first.candidate_rows] == [
        "candidate_kind.combat.play_card", "candidate_kind.combat.end_turn",
    ]
    assert [CANDIDATE_FEATURE_NAMES[row[:11].index(1.0)] for row in second.candidate_rows] == [
        "candidate_kind.combat.end_turn", "candidate_kind.combat.play_card",
    ]
    assert first.global_features == second.global_features
    assert first.entity_rows == second.entity_rows
    assert first.public_event_rows == second.public_event_rows
    assert sorted(first.candidate_rows) == sorted(second.candidate_rows)


def test_terminal_and_resolved_events_and_128_event_sequence_encode() -> None:
    combat = _views("combat")[0]
    events = tuple(
        PublicEvent(index, PublicEventKind.COMBAT_TURN_ENDED, DecisionPhase.COMBAT, {})
        for index in range(128)
    )
    waiting = PolicyView(DecisionStatus.WAITING, DecisionPhase.COMBAT, combat.observation, (), events)
    encoded = encode_policy_view(waiting)
    assert len(encoded.public_event_rows) == 128
    assert encoded.public_event_rows[-1][PUBLIC_EVENT_FEATURE_NAMES.index("sequence")] == 1.0
    resolved = PublicEvent(0, PublicEventKind.COMBAT_RESOLVED, DecisionPhase.COMBAT, {"outcome": "victory"})
    assert encode_policy_view(PolicyView(DecisionStatus.WAITING, DecisionPhase.COMBAT, combat.observation, (), (resolved,))).public_event_rows[0][PUBLIC_EVENT_FEATURE_NAMES.index("outcome.victory")] == 1.0
    terminal_observation = PublicObservation(DecisionPhase.TERMINAL, {"outcome": RunOutcome.VICTORY.value, "player": {"hp": 1, "max_hp": 1, "gold": 0, "deck_size": 0}}, combat.observation.public_scope)
    terminated = PublicEvent(0, PublicEventKind.RUN_TERMINATED, DecisionPhase.TERMINAL, {"outcome": RunOutcome.VICTORY.value})
    terminal = PolicyView(DecisionStatus.TERMINAL, DecisionPhase.TERMINAL, terminal_observation, (), (terminated,))
    assert encode_policy_view(terminal).public_event_rows[0][PUBLIC_EVENT_FEATURE_NAMES.index("outcome.victory")] == 1.0


def test_nested_reward_rows_and_candidates_have_no_extra_aggregate_cap() -> None:
    scope = PublicScope(0, 0, {kind: 0 for kind in ("card", "enemy", "reward", "offer", "node", "option")})
    rewards = []
    candidates = []
    for reward_index in range(2):
        reward_ref = reward_reference(scope, "card", reward_index)
        offers = []
        for offer_index in range(128):
            offer_ref = reward_offer_reference(scope, reward_ref, "strike", offer_index)
            offers.append({"offer_ref": offer_ref, "card_definition_id": "strike", "upgraded": False})
            candidates.append(RewardChooseCardCandidate(scope.decision_scope, reward_ref, offer_ref, "strike"))
        rewards.append({"reward_ref": reward_ref, "kind": "card", "amount": 0, "claimed": False, "opened": True, "can_skip": False, "offers": offers})
    observation = PublicObservation(DecisionPhase.REWARD, {"player": {"hp": 1, "max_hp": 1, "gold": 1_000_000_000, "deck_size": 128}, "can_proceed": False, "rewards": rewards}, scope)
    encoded = encode_policy_view(PolicyView(DecisionStatus.ACTIONABLE, DecisionPhase.REWARD, observation, tuple(candidates), ()))
    assert len(encoded.entity_rows) == 258
    assert len(encoded.candidate_rows) == 256
