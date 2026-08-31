"""Conformance tests for decision-scoped legacy combat candidate mapping."""

from __future__ import annotations

import pytest

from game.backends.headless.combat_candidates import (
    CombatCandidateError,
    CombatCandidateMapping,
    InvalidCombatCandidateError,
    StaleCombatCandidateError,
    bind_combat_candidate,
    decode_combat_action_request,
    finalize_combat_candidate_mapping,
    generate_combat_candidates,
)
from game.backends.headless.combat_projection import (
    CARD_DEFINITION_IDS,
    ENEMY_DEFINITION_IDS,
    project_combat_observation,
)
from game.contracts.headless_v0 import (
    ActionRequest,
    CombatPlayCardCandidate,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    HeadlessBinding,
    PublicReferenceKind,
    PublicScope,
)
from game.simulation.card import Card, DefendCard, StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy


_FINGERPRINTS = {
    "backend_fingerprint": "a" * 64,
    "content_fingerprint": "b" * 64,
    "rules_fingerprint": "c" * 64,
}


def _scope(*, decision_ordinal: int = 1) -> PublicScope:
    return PublicScope(
        history_ordinal=0,
        decision_ordinal=decision_ordinal,
        reveal_ordinals={kind.value: 0 for kind in PublicReferenceKind},
    )


def _combat_decision(
    environment: CombatEnv,
    scope: PublicScope,
    *,
    sequence: int = 1,
    run_id: str = "run:combat:fixture",
) -> tuple[DecisionState, CombatCandidateMapping]:
    mapping = generate_combat_candidates(environment, scope)
    observation = project_combat_observation(environment.get_observation(), scope)
    decision = DecisionState.create(
        backend_id="combat_v0",
        backend_version="1.0.0",
        content_version="combat_v0",
        rules_version="combat_v0",
        run_id=run_id,
        decision_sequence=sequence,
        status=DecisionStatus.ACTIONABLE,
        phase=DecisionPhase.COMBAT,
        observation=observation,
        candidates=mapping.candidates,
        **_FINGERPRINTS,
    )
    return decision, finalize_combat_candidate_mapping(decision, mapping)


def _semantic_actions(mapping: CombatCandidateMapping) -> dict[str, tuple[object, ...]]:
    candidates = mapping.candidates
    return {
        candidate.candidate_id: mapping.action_for(candidate.candidate_id)
        for candidate in candidates
    }


def test_single_enemy_maps_all_legal_actions_once_and_decodes_exact_tuples() -> None:
    environment = CombatEnv(
        deck_factory=lambda: [DefendCard(), StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        cards_per_turn=2,
    )
    environment.reset(seed=3)
    decision, mapping = _combat_decision(environment, _scope())

    assert set(_semantic_actions(mapping).values()) == set(environment.get_legal_actions())
    assert len(mapping.candidates) == len(environment.get_legal_actions())
    assert all(
        candidate.decision_scope == decision.observation.public_scope.decision_scope
        for candidate in mapping.candidates
    )
    projected_card_refs = {
        card["card_ref"] for card in decision.observation.data["hand"]
    }
    projected_enemy_refs = {
        enemy["enemy_ref"] for enemy in decision.observation.data["enemies"]
    }
    assert all(
        candidate.card_ref in projected_card_refs
        for candidate in mapping.candidates
        if isinstance(candidate, CombatPlayCardCandidate)
    )
    assert all(
        candidate.target_ref in projected_enemy_refs
        for candidate in mapping.candidates
        if isinstance(candidate, CombatPlayCardCandidate)
        and candidate.target_ref is not None
    )

    plays = [candidate for candidate in mapping.candidates if isinstance(candidate, CombatPlayCardCandidate)]
    assert len(plays) == 2
    assert next(candidate for candidate in plays if candidate.target_ref is None)
    assert next(candidate for candidate in plays if candidate.target_ref is not None)
    for candidate in mapping.candidates:
        request = bind_combat_candidate(decision, mapping, candidate.candidate_id)
        assert decode_combat_action_request(decision, mapping, request) == mapping.action_for(
            candidate.candidate_id
        )


def test_multi_enemy_maps_zero_and_one_target_plays_without_duplicate_candidates() -> None:
    environment = CombatEnv(
        deck_factory=lambda: [DefendCard(), StrikeCard()],
        encounter_factory=lambda _rng: [SimpleEnemy(max_hp=8), SimpleEnemy(max_hp=9)],
        cards_per_turn=2,
        max_enemy_count=2,
    )
    environment.reset(seed=4)
    decision, mapping = _combat_decision(environment, _scope())

    assert set(_semantic_actions(mapping).values()) == set(environment.get_legal_actions())
    assert len(mapping.candidates) == len(environment.get_legal_actions()) == 4
    plays = [candidate for candidate in mapping.candidates if isinstance(candidate, CombatPlayCardCandidate)]
    assert len([candidate for candidate in plays if candidate.target_ref is None]) == 1
    assert len([candidate for candidate in plays if candidate.target_ref is not None]) == 2
    assert all(
        decode_combat_action_request(
            decision,
            mapping,
            bind_combat_candidate(decision, mapping, candidate.candidate_id),
        )
        in environment.get_legal_actions()
        for candidate in mapping.candidates
    )


def test_legal_action_list_reordering_does_not_change_semantic_candidate_mapping() -> None:
    class ReorderedCombatEnv(CombatEnv):
        def get_legal_actions(self):
            return list(reversed(super().get_legal_actions()))

    kwargs = {
        "deck_factory": lambda: [DefendCard(), StrikeCard()],
        "encounter_factory": lambda _rng: [SimpleEnemy(max_hp=8), SimpleEnemy(max_hp=9)],
        "cards_per_turn": 2,
        "max_enemy_count": 2,
    }
    standard = CombatEnv(**kwargs)
    reordered = ReorderedCombatEnv(**kwargs)
    standard.reset(seed=4)
    reordered.reset(seed=4)

    standard_mapping = generate_combat_candidates(standard, _scope())
    reordered_mapping = generate_combat_candidates(reordered, _scope())

    assert _semantic_actions(standard_mapping) == _semantic_actions(reordered_mapping)
    assert standard_mapping.candidates == reordered_mapping.candidates


def test_requests_reject_stale_unadvertised_and_tampered_candidate_ids() -> None:
    environment = CombatEnv(
        deck_factory=lambda: [StrikeCard()], cards_per_turn=1
    )
    environment.reset(seed=5)
    decision, mapping = _combat_decision(environment, _scope(), sequence=4)
    candidate_id = mapping.candidates[0].candidate_id
    request = bind_combat_candidate(decision, mapping, candidate_id)

    stale = ActionRequest(
        HeadlessBinding(
            run_id=request.binding.run_id,
            decision_sequence=request.binding.decision_sequence + 1,
            decision_hash=request.binding.decision_hash,
            candidate_id=candidate_id,
        )
    )
    with pytest.raises(StaleCombatCandidateError):
        decode_combat_action_request(decision, mapping, stale)

    tampered = ActionRequest(
        HeadlessBinding(
            run_id=request.binding.run_id,
            decision_sequence=request.binding.decision_sequence,
            decision_hash=request.binding.decision_hash,
            candidate_id="cand." + "0" * 64,
        )
    )
    with pytest.raises(InvalidCombatCandidateError):
        decode_combat_action_request(decision, mapping, tampered)

    next_scope = _scope(decision_ordinal=2)
    next_decision, next_mapping = _combat_decision(
        environment, next_scope, sequence=5
    )
    with pytest.raises(StaleCombatCandidateError):
        decode_combat_action_request(next_decision, next_mapping, request)


def test_mapping_rejects_cross_run_reuse_with_identical_public_candidate_ids() -> None:
    def make_environment() -> CombatEnv:
        environment = CombatEnv(
            deck_factory=lambda: [DefendCard(), StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=20),
            cards_per_turn=2,
        )
        environment.reset(seed=3)
        return environment

    scope = _scope()
    decision_a, mapping_a = _combat_decision(
        make_environment(), scope, run_id="run:combat:a"
    )
    decision_b, mapping_b = _combat_decision(
        make_environment(), scope, run_id="run:combat:b"
    )
    assert tuple(candidate.candidate_id for candidate in mapping_a.candidates) == tuple(
        candidate.candidate_id for candidate in mapping_b.candidates
    )

    request_b = bind_combat_candidate(
        decision_b,
        mapping_b,
        mapping_b.candidates[0].candidate_id,
    )
    with pytest.raises(StaleCombatCandidateError, match="does not bind"):
        decode_combat_action_request(decision_b, mapping_a, request_b)
    with pytest.raises(StaleCombatCandidateError, match="already finalized"):
        finalize_combat_candidate_mapping(decision_a, mapping_a)


def test_closed_projection_registries_reject_unknown_legacy_card_and_enemy() -> None:
    class UnknownCard(Card):
        def __init__(self) -> None:
            super().__init__("Unknown Card", 1)

        def play(self, player, enemy) -> None:
            del player, enemy

    class UncheckedLegalActionsEnv(CombatEnv):
        def get_legal_actions(self):
            return [("end_turn",), ("play", 0)]

    unknown_card_env = UncheckedLegalActionsEnv(
        deck_factory=lambda: [UnknownCard()],
        cards_per_turn=1,
    )
    unknown_card_env.reset(seed=0)
    with pytest.raises(CombatCandidateError, match="closed projection registry"):
        generate_combat_candidates(unknown_card_env, _scope())

    unknown_enemy_env = CombatEnv(
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        cards_per_turn=1,
    )
    unknown_enemy_env.reset(seed=0)
    assert unknown_enemy_env.enemies is not None
    unknown_enemy_env.enemies[0].name = "Unknown Enemy"
    with pytest.raises(CombatCandidateError, match="closed projection registry"):
        generate_combat_candidates(unknown_enemy_env, _scope())


def test_mapping_copies_candidate_sequence_and_joins_projection_content_ids() -> None:
    environment = CombatEnv(
        deck_factory=lambda: [DefendCard(), StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        cards_per_turn=2,
    )
    environment.reset(seed=3)
    generated = generate_combat_candidates(environment, _scope())
    mutable_candidates = list(generated.candidates)
    mapping = CombatCandidateMapping(
        decision_scope=generated.decision_scope,
        candidates=mutable_candidates,
        _actions_by_candidate_id={
            candidate.candidate_id: generated.action_for(candidate.candidate_id)
            for candidate in generated.candidates
        },
    )
    mutable_candidates.clear()

    assert isinstance(mapping.candidates, tuple)
    assert len(mapping.candidates) == len(generated.candidates)
    assert set(CARD_DEFINITION_IDS.values()) >= {
        card["card_definition_id"]
        for card in project_combat_observation(
            environment.get_observation(),
            _scope(),
        ).data["hand"]
    }
    assert ENEMY_DEFINITION_IDS["SimpleEnemy"] == "simple_enemy"
