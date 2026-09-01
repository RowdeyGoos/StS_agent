"""Structural-fixture coverage for reduced reward rules."""

from __future__ import annotations

import pytest

from game.content.reduced_v0 import CONTENT_FINGERPRINT, REWARD_TABLES
from game.contracts.headless_v0 import (
    ActionRequest,
    ContractValidationError,
    DecisionPhase,
    HeadlessBinding,
    MAX_PUBLIC_COUNTER,
    PublicEventKind,
    PublicReferenceKind,
    PublicScope,
    TransitionReason,
    TransitionResult,
)
from game.engine.headless_state import NodeKind, WorldState
from game.engine.reward_rules import RewardRuleError, RewardRules
from game.engine.snapshots import WorldSnapshotCodec


RULES_FINGERPRINT = "a" * 64
BACKEND_FINGERPRINT = "b" * 64


def _scope(*, decision: int = 0) -> PublicScope:
    return PublicScope(
        history_ordinal=0,
        decision_ordinal=decision,
        reveal_ordinals={kind.value: 0 for kind in PublicReferenceKind},
    )


def _world(seed: int = 41) -> WorldState:
    return WorldState.create(
        seed=seed,
        current_hp=67,
        max_hp=80,
        gold=12,
        deck_definition_ids=("strike", "defend", "bash"),
        map_node_definitions=(("floor_01_combat", NodeKind.COMBAT),),
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_fingerprint=RULES_FINGERPRINT,
        phase=DecisionPhase.REWARD,
    )


def _rules() -> RewardRules:
    return RewardRules(backend_fingerprint=BACKEND_FINGERPRINT)


def _request(decision, predicate):
    candidate = next(item for item in decision.candidates if predicate(item))
    return ActionRequest(HeadlessBinding.for_candidate(decision, candidate.candidate_id))


def _candidate_kinds(decision) -> set[str]:
    return {candidate.kind.value for candidate in decision.candidates}


def test_reward_sequence_exposes_all_and_only_legal_candidates_and_mutates_persistent_state() -> None:
    world = _world()
    rules = _rules()
    initial = rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=9,
        public_scope=_scope(decision=4),
    )

    assert _candidate_kinds(initial) == {"reward.claim_gold", "reward.open_card_reward"}
    assert world.rng_stream_counters() == {
        "combat_launch": 0,
        "event_effect": 0,
        "reward_offer": 0,
    }

    claimed = rules.apply(world, _request(initial, lambda item: item.kind.value == "reward.claim_gold"))
    assert claimed.result is TransitionResult.ACCEPTED
    assert claimed.public_events[0].event_type is PublicEventKind.REWARD_GOLD_CLAIMED
    assert world.gold == 37
    assert _candidate_kinds(claimed.next_decision) == {"reward.open_card_reward"}

    opened = rules.apply(
        world,
        _request(claimed.next_decision, lambda item: item.kind.value == "reward.open_card_reward"),
    )
    assert opened.public_events[0].data == {"offer_count": 3}
    assert _candidate_kinds(opened.next_decision) == {
        "reward.choose_card",
        "reward.skip_card",
    }
    assert world.rng_stream_counters() == {
        "combat_launch": 0,
        "event_effect": 0,
        "reward_offer": 1,
    }
    assert {offer["card_definition_id"] for offer in opened.next_decision.observation.data["rewards"][1]["offers"]} == {
        "strike",
        "defend",
        "bash",
    }

    chosen = rules.apply(
        world,
        _request(opened.next_decision, lambda item: item.kind.value == "reward.choose_card"),
    )
    assert chosen.public_events[0].event_type is PublicEventKind.REWARD_CARD_CHOSEN
    assert len(world.master_deck) == 4
    assert world.master_deck[-1].definition_id in {"strike", "defend", "bash"}
    assert world.master_deck[-1].instance_id.endswith("00000003")
    assert _candidate_kinds(chosen.next_decision) == {"reward.proceed"}

    proceeded = rules.apply(
        world,
        _request(chosen.next_decision, lambda item: item.kind.value == "reward.proceed"),
    )
    assert proceeded.next_decision.status.value == "waiting"
    assert proceeded.next_decision.candidates == ()
    assert proceeded.public_events[0].event_type is PublicEventKind.REWARD_PROCEEDED


def test_same_seed_has_the_same_opened_offer_order_and_only_reward_stream_changes() -> None:
    first, second = _world(8), _world(8)
    first_rules, second_rules = _rules(), _rules()
    first_decision = first_rules.begin(first, reward_table_id="combat_reward_sequence", decision_sequence=0, public_scope=_scope())
    second_decision = second_rules.begin(second, reward_table_id="combat_reward_sequence", decision_sequence=0, public_scope=_scope())

    first_opened = first_rules.apply(first, _request(first_decision, lambda item: item.kind.value == "reward.open_card_reward"))
    second_opened = second_rules.apply(second, _request(second_decision, lambda item: item.kind.value == "reward.open_card_reward"))

    first_offers = first_opened.next_decision.observation.data["rewards"][1]["offers"]
    second_offers = second_opened.next_decision.observation.data["rewards"][1]["offers"]
    assert first_offers == second_offers
    assert [offer["card_definition_id"] for offer in first_offers] != list(
        REWARD_TABLES[1].card_definition_ids
    )
    assert first.rng_stream_counters() == second.rng_stream_counters() == {
        "combat_launch": 0,
        "event_effect": 0,
        "reward_offer": 1,
    }


def test_skip_resolves_only_the_card_reward_and_preserves_the_master_deck() -> None:
    world = _world(12)
    rules = _rules()
    decision = rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    opened = rules.apply(
        world,
        _request(decision, lambda item: item.kind.value == "reward.open_card_reward"),
    )
    deck_before_skip = world.master_deck
    skipped = rules.apply(
        world,
        _request(opened.next_decision, lambda item: item.kind.value == "reward.skip_card"),
    )

    assert skipped.public_events[0].event_type is PublicEventKind.REWARD_CARD_SKIPPED
    assert world.master_deck == deck_before_skip
    assert _candidate_kinds(skipped.next_decision) == {"reward.claim_gold"}


def test_invalid_and_stale_actions_are_fully_atomic() -> None:
    world = _world()
    rules = _rules()
    decision = rules.begin(world, reward_table_id="combat_reward_basic", decision_sequence=2, public_scope=_scope())
    before = world.to_private_dict()
    invalid = ActionRequest(
        HeadlessBinding(
            run_id=decision.run_id,
            decision_sequence=decision.decision_sequence,
            decision_hash=decision.decision_hash,
            candidate_id="cand." + "f" * 64,
        )
    )
    invalid_transition = rules.apply(world, invalid)
    assert invalid_transition.result is TransitionResult.REJECTED
    assert invalid_transition.reason is TransitionReason.INVALID_CANDIDATE
    assert world.to_private_dict() == before

    claim = _request(decision, lambda item: item.kind.value == "reward.claim_gold")
    accepted = rules.apply(world, claim)
    before_stale = world.to_private_dict()
    stale = rules.apply(world, claim)
    assert stale.result is TransitionResult.STALE
    assert stale.reason is TransitionReason.STALE_BINDING
    assert stale.next_decision == accepted.next_decision
    assert world.to_private_dict() == before_stale


def test_snapshot_restore_continues_opened_offer_and_allocator_exactly() -> None:
    world = _world(99)
    rules = _rules()
    decision = rules.begin(world, reward_table_id="combat_reward_basic", decision_sequence=5, public_scope=_scope())
    opened = rules.apply(world, _request(decision, lambda item: item.kind.value == "reward.open_card_reward"))
    codec = WorldSnapshotCodec(CONTENT_FINGERPRINT, RULES_FINGERPRINT)
    restored = codec.loads(codec.dumps(world))

    original_next = rules.apply(world, _request(opened.next_decision, lambda item: item.kind.value == "reward.choose_card"))
    restored_decision = rules.decision(restored)
    restored_next = rules.apply(restored, _request(restored_decision, lambda item: item.kind.value == "reward.choose_card"))

    assert restored_next.next_decision == original_next.next_decision
    assert restored.to_private_dict() == world.to_private_dict()
    assert restored.rng_stream_counters() == world.rng_stream_counters() == {
        "combat_launch": 0,
        "event_effect": 0,
        "reward_offer": 1,
    }


def test_begin_rejects_non_reward_or_pending_world_without_mutation() -> None:
    world = _world()
    world.phase = DecisionPhase.COMBAT
    rules = _rules()
    before = world.to_private_dict()
    with pytest.raises(RewardRuleError):
        rules.begin(world, reward_table_id="combat_reward_basic", decision_sequence=0, public_scope=_scope())
    assert world.to_private_dict() == before


def test_open_at_maximum_public_decision_ordinal_restores_rng_and_pending_state() -> None:
    world = _world()
    rules = _rules()
    decision = rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(decision=MAX_PUBLIC_COUNTER),
    )
    before = world.to_private_dict()

    with pytest.raises(ContractValidationError):
        rules.apply(
            world,
            _request(decision, lambda item: item.kind.value == "reward.open_card_reward"),
        )

    assert world.to_private_dict() == before
    assert world.rng_stream_counters()["reward_offer"] == 0


def test_choose_at_maximum_public_decision_ordinal_restores_allocator_and_deck() -> None:
    world = _world()
    rules = _rules()
    decision = rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(decision=MAX_PUBLIC_COUNTER - 1),
    )
    opened = rules.apply(
        world,
        _request(decision, lambda item: item.kind.value == "reward.open_card_reward"),
    )
    before = world.to_private_dict()

    with pytest.raises(ContractValidationError):
        rules.apply(
            world,
            _request(opened.next_decision, lambda item: item.kind.value == "reward.choose_card"),
        )

    assert world.to_private_dict() == before
    assert len(world.master_deck) == 3
    assert world.identity_allocator.next_card_ordinal == 3


def test_claim_that_exceeds_the_public_gold_bound_restores_world_exactly() -> None:
    world = _world()
    world.gold = MAX_PUBLIC_COUNTER - 10
    rules = _rules()
    decision = rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    before = world.to_private_dict()

    with pytest.raises(ContractValidationError):
        rules.apply(
            world,
            _request(decision, lambda item: item.kind.value == "reward.claim_gold"),
        )

    assert world.to_private_dict() == before


def test_forced_post_mutation_validation_failure_restores_world_exactly(monkeypatch) -> None:
    world = _world()
    rules = _rules()
    decision = rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    before = world.to_private_dict()
    original_validate = WorldState.validate
    baseline_gold = world.gold
    observed_mutated_world = False

    def fail_after_current_validation(self):
        nonlocal observed_mutated_world
        result = original_validate(self)
        if self is world and self.gold != baseline_gold:
            observed_mutated_world = True
            raise RuntimeError("forced post-mutation validation failure")
        return result

    monkeypatch.setattr(WorldState, "validate", fail_after_current_validation)
    with pytest.raises(RuntimeError, match="forced post-mutation"):
        rules.apply(
            world,
            _request(decision, lambda item: item.kind.value == "reward.claim_gold"),
        )

    assert world.to_private_dict() == before
    assert observed_mutated_world


def test_forced_begin_decision_failure_restores_pending_state(monkeypatch) -> None:
    world = _world()
    rules = _rules()
    before = world.to_private_dict()

    def fail_begin_projection(self, current_world):
        del self, current_world
        raise RuntimeError("forced begin projection failure")

    monkeypatch.setattr(RewardRules, "decision", fail_begin_projection)
    with pytest.raises(RuntimeError, match="forced begin projection"):
        rules.begin(
            world,
            reward_table_id="combat_reward_basic",
            decision_sequence=0,
            public_scope=_scope(),
        )

    assert world.to_private_dict() == before
