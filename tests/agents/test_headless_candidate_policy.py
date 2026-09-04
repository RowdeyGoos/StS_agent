"""Contract tests for the narrow ``H6-CANDIDATE-POLICY-06`` consumer."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from game.agents.headless_candidate_policy import (
    MODEL_FINGERPRINT,
    CandidatePolicyConfig,
    CandidatePolicyError,
    HeadlessCandidatePolicy,
)
from game.agents.headless_encoding import collate_policy_views, encode_policy_view
from game.backends.headless.fixture_backend import FixtureBackend
from game.contracts.headless_v0 import (
    ActionRequest,
    CombatEndTurnCandidate,
    CombatPlayCardCandidate,
    CombatOutcome,
    DecisionPhase,
    DecisionStatus,
    HeadlessBinding,
    PolicyView,
    PublicObservation,
    PublicScope,
    combat_card_reference,
    combat_enemy_reference,
)


def _fixture_views(fixture_id: str) -> tuple[PolicyView, ...]:
    backend = FixtureBackend()
    decision = backend.reset(fixture_id)
    result = []
    while True:
        result.append(decision.policy_view())
        if not decision.candidates:
            return tuple(result)
        decision = backend.apply(ActionRequest(HeadlessBinding.for_candidate(decision, decision.candidates[0].candidate_id))).next_decision


def _three_candidate_view(scope: PublicScope, *, reverse: bool) -> PolicyView:
    enemy_ref = combat_enemy_reference(scope, "simple_enemy", 0)
    cards = []
    candidates = []
    for index, definition in enumerate(("strike", "defend")):
        card_ref = combat_card_reference(scope, definition, index)
        cards.append({"card_ref": card_ref, "card_definition_id": definition, "cost": 1, "upgraded": False})
        candidates.append(CombatPlayCardCandidate(scope.decision_scope, card_ref, enemy_ref))
    candidates.append(CombatEndTurnCandidate(scope.decision_scope))
    if reverse:
        candidates.reverse()
    observation = PublicObservation(
        DecisionPhase.COMBAT,
        {
            "turn": 1,
            "player": {"hp": 10, "max_hp": 10, "block": 0, "energy": 1, "energy_per_turn": 1, "strength": 0, "statuses": {"shrink": 0, "vulnerable": 0}},
            "enemies": [{"enemy_ref": enemy_ref, "enemy_definition_id": "simple_enemy", "hp": 5, "max_hp": 5, "block": 0, "strength": 0, "alive": True, "statuses": {"shrink": 0, "vulnerable": 0}, "intent": {"kind": "attack", "attack_count": 1, "attack_damage": 1, "block_gain": 0, "strength_gain": 0, "status_kind": "none", "status_stacks": 0, "slimed_added": 0}}],
            "hand": cards,
            "draw_pile_size": 0,
            "discard_pile_size": 0,
            "exhaust_pile_size": 0,
            "terminal": False,
            "outcome": CombatOutcome.ONGOING.value,
        },
        scope,
    )
    return PolicyView(DecisionStatus.ACTIONABLE, DecisionPhase.COMBAT, observation, tuple(candidates), ())


def test_forward_masks_padding_handles_empty_axes_and_has_finite_gradients() -> None:
    actionable = encode_policy_view(_three_candidate_view(PublicScope(0, 0, {kind: 0 for kind in ("card", "enemy", "reward", "offer", "node", "option")}), reverse=False))
    waiting = replace(actionable, entity_rows=(), public_event_rows=(), candidate_rows=(), candidate_ids=())
    batch = collate_policy_views((waiting, actionable))
    policy = HeadlessCandidatePolicy(CandidatePolicyConfig(hidden_size=16))
    logits = policy(batch)
    probabilities = policy.probabilities(batch)
    assert logits.shape == probabilities.shape == (2, 3)
    assert torch.equal(logits[0], torch.zeros(3))
    assert torch.equal(probabilities[0], torch.zeros(3))
    assert torch.equal(logits[~torch.as_tensor(batch.candidate_mask)], torch.zeros_like(logits[~torch.as_tensor(batch.candidate_mask)]))
    assert torch.isfinite(logits).all() and torch.isfinite(probabilities).all()
    assert torch.allclose(probabilities[1].sum(), torch.tensor(1.0))
    logits[1].sum().backward()
    assert all(parameter.grad is not None and torch.isfinite(parameter.grad).all() for parameter in policy.parameters())
    assert policy.select_candidate_ids(batch)[0] is None


def test_empty_batch_and_independently_empty_entity_event_candidate_axes_are_exact() -> None:
    policy = HeadlessCandidatePolicy(CandidatePolicyConfig(hidden_size=16))
    empty = collate_policy_views(())
    assert policy(empty).shape == (0, 0)
    assert policy.probabilities(empty).shape == (0, 0)
    assert policy.select_candidate_ids(empty) == ()
    source = encode_policy_view(_fixture_views("combat")[0])
    independently_empty = collate_policy_views((replace(source, entity_rows=(), public_event_rows=(), candidate_rows=(), candidate_ids=()),))
    assert independently_empty.entity_features.shape == (1, 0, 90)
    assert independently_empty.public_event_features.shape == (1, 0, 78)
    assert independently_empty.candidate_features.shape == (1, 0, 557)
    assert policy(independently_empty).shape == (1, 0)
    assert policy.select_candidate_ids(independently_empty) == (None,)


def test_candidate_permutation_and_entity_event_pooling_are_equivariant() -> None:
    torch.manual_seed(17)
    policy = HeadlessCandidatePolicy(CandidatePolicyConfig(hidden_size=16))
    source = encode_policy_view(_three_candidate_view(PublicScope(0, 0, {kind: 0 for kind in ("card", "enemy", "reward", "offer", "node", "option")}), reverse=False))
    # Duplicate only public rows to exercise a genuinely nontrivial independent pool permutation.
    pooled = replace(source, entity_rows=(source.entity_rows[0], source.entity_rows[-1]), public_event_rows=((0.0,) * 78, (1.0,) + (0.0,) * 77))
    original = collate_policy_views((pooled,))
    order = np.array([2, 0, 1])
    permuted = replace(
        original,
        entity_features=original.entity_features[:, ::-1].copy(),
        public_event_features=original.public_event_features[:, ::-1].copy(),
        candidate_features=original.candidate_features[:, order].copy(),
        candidate_mask=original.candidate_mask[:, order].copy(),
        candidate_ids=(tuple(original.candidate_ids[0][index] for index in order),),
    )
    first, second = policy(original).detach(), policy(permuted).detach()
    assert torch.allclose(second[0], first[0, torch.as_tensor(order)])
    first_id, second_id = policy.select_candidate_ids(original)[0], policy.select_candidate_ids(permuted)[0]
    assert first_id == original.candidate_ids[0][int(torch.argmax(first[0]))]
    assert second_id == permuted.candidate_ids[0][int(torch.argmax(second[0]))]


def test_valid_opaque_reference_reallocation_preserves_semantic_scores_and_own_id_alignment() -> None:
    zeroes = {kind: 0 for kind in ("card", "enemy", "reward", "offer", "node", "option")}
    twos = {kind: 2 for kind in zeroes}
    first = collate_policy_views((encode_policy_view(_three_candidate_view(PublicScope(0, 0, zeroes), reverse=False)),))
    second = collate_policy_views((encode_policy_view(_three_candidate_view(PublicScope(2, 2, twos), reverse=True)),))
    policy = HeadlessCandidatePolicy(CandidatePolicyConfig(hidden_size=16))
    first_pairs = sorted((tuple(row), score) for row, score in zip(first.candidate_features[0], policy(first)[0].detach().tolist()))
    second_pairs = sorted((tuple(row), score) for row, score in zip(second.candidate_features[0], policy(second)[0].detach().tolist()))
    assert first.candidate_ids != second.candidate_ids
    assert first_pairs == pytest.approx(second_pairs)
    for batch in (first, second):
        selected = policy.select_candidate_ids(batch)[0]
        assert selected == batch.candidate_ids[0][int(torch.argmax(policy(batch)[0]))]


def test_rejects_bad_masks_features_and_pinned_serialization() -> None:
    policy = HeadlessCandidatePolicy(CandidatePolicyConfig(hidden_size=16))
    source = encode_policy_view(_fixture_views("combat")[0])
    batch = collate_policy_views((replace(source, candidate_rows=(), candidate_ids=()), source))
    bad_padding = replace(batch, candidate_features=batch.candidate_features.copy())
    bad_padding.candidate_features[0, 0] = 1.0
    with pytest.raises(CandidatePolicyError):
        policy(bad_padding)
    payload = policy.checkpoint_payload()
    restored = HeadlessCandidatePolicy.from_checkpoint_payload(deepcopy(payload))
    assert restored.model_fingerprint == MODEL_FINGERPRINT
    assert restored.config_fingerprint == policy.config_fingerprint
    for key, value in (("encoding_fingerprint", "0" * 64), ("config_fingerprint", "0" * 64)):
        changed = deepcopy(payload)
        changed[key] = value
        with pytest.raises(CandidatePolicyError):
            HeadlessCandidatePolicy.from_checkpoint_payload(changed)
    malformed = deepcopy(payload)
    state_key = next(iter(malformed["state_dict"]))
    malformed["state_dict"][state_key] = torch.zeros((1,))
    with pytest.raises(CandidatePolicyError):
        HeadlessCandidatePolicy.from_checkpoint_payload(malformed)


def test_module_imports_from_this_worktree() -> None:
    import game.agents.headless_candidate_policy as module

    assert Path(module.__file__).resolve().is_relative_to(Path.cwd())
