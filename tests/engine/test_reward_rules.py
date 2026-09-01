"""Structural-fixture coverage for reduced reward rules."""

from __future__ import annotations

from copy import deepcopy

import pytest

from game.content.reduced_v0 import CONTENT_FINGERPRINT, CONTENT_VERSION, REWARD_TABLES
from game.contracts.headless_v0 import (
    ActionRequest,
    ContractValidationError,
    DecisionPhase,
    HeadlessBinding,
    MAX_PUBLIC_COUNTER,
    PublicEvent,
    PublicEventKind,
    PublicReferenceKind,
    PublicScope,
    TransitionReason,
    TransitionResult,
)
from game.engine.headless_state import NodeKind, PendingDecision, WorldState
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


def _replace_pending_context(world: WorldState, update, *, decision_kind: str | None = None) -> None:
    assert world.pending_decision is not None
    pending = world.pending_decision.to_dict()
    context = deepcopy(pending["private_context"])
    update(context)
    world.pending_decision = PendingDecision(
        decision_kind or pending["decision_kind"],
        pending["sequence"],
        context,
    )


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


@pytest.mark.parametrize(
    "action_order",
    (
        ("reward.claim_gold", "reward.open_card_reward", "reward.choose_card", "reward.proceed"),
        ("reward.claim_gold", "reward.open_card_reward", "reward.skip_card", "reward.proceed"),
        ("reward.open_card_reward", "reward.claim_gold", "reward.choose_card", "reward.proceed"),
        ("reward.open_card_reward", "reward.claim_gold", "reward.skip_card", "reward.proceed"),
        ("reward.open_card_reward", "reward.choose_card", "reward.claim_gold", "reward.proceed"),
        ("reward.open_card_reward", "reward.skip_card", "reward.claim_gold", "reward.proceed"),
    ),
)
def test_all_legal_reward_orders_restore_at_every_boundary(action_order: tuple[str, ...]) -> None:
    world = _world(303)
    rules = _rules()
    decision = rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=4,
        public_scope=_scope(decision=11),
    )
    codec = WorldSnapshotCodec(CONTENT_FINGERPRINT, RULES_FINGERPRINT)

    world = codec.loads(codec.dumps(world))
    decision = rules.decision(world)
    for kind in action_order:
        transition = rules.apply(
            world,
            _request(decision, lambda item, selected=kind: item.kind.value == selected),
        )
        decision = transition.next_decision
        world = codec.loads(codec.dumps(world))
        assert rules.decision(world) == decision

    assert decision.status.value == "waiting"
    assert world.gold == 37
    expected_deck_size = 4 if "reward.choose_card" in action_order else 3
    assert len(world.master_deck) == expected_deck_size


def test_begin_rejects_non_reward_or_pending_world_without_mutation() -> None:
    world = _world()
    world.phase = DecisionPhase.COMBAT
    rules = _rules()
    before = world.to_private_dict()
    with pytest.raises(RewardRuleError):
        rules.begin(world, reward_table_id="combat_reward_basic", decision_sequence=0, public_scope=_scope())
    assert world.to_private_dict() == before


def test_reward_rules_bind_the_fixed_reduced_content_version_and_fingerprint() -> None:
    with pytest.raises(RewardRuleError, match="fixed reduced content version"):
        RewardRules(backend_fingerprint=BACKEND_FINGERPRINT, content_version="fabricated_v0")

    world = _world()
    world.content_fingerprint = "c" * 64
    before = world.to_private_dict()
    with pytest.raises(RewardRuleError, match="fixed reduced content fingerprint"):
        _rules().begin(
            world,
            reward_table_id="combat_reward_basic",
            decision_sequence=0,
            public_scope=_scope(),
        )

    assert world.to_private_dict() == before
    assert RewardRules(backend_fingerprint=BACKEND_FINGERPRINT).content_version == CONTENT_VERSION


@pytest.mark.parametrize("decision_ordinal", [MAX_PUBLIC_COUNTER - 3, MAX_PUBLIC_COUNTER])
def test_begin_rejects_public_scope_without_a_complete_reward_budget(decision_ordinal: int) -> None:
    world = _world()
    rules = _rules()
    before = world.to_private_dict()

    with pytest.raises(RewardRuleError, match="scope budget"):
        rules.begin(
            world,
            reward_table_id="combat_reward_basic",
            decision_sequence=0,
            public_scope=_scope(decision=decision_ordinal),
        )

    assert world.to_private_dict() == before
    assert world.rng_stream_counters()["reward_offer"] == 0


def test_near_maximum_scope_finishes_without_a_dead_end() -> None:
    world = _world()
    rules = _rules()
    decision = rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(decision=MAX_PUBLIC_COUNTER - 4),
    )
    opened = rules.apply(
        world,
        _request(decision, lambda item: item.kind.value == "reward.open_card_reward"),
    )
    assert _candidate_kinds(opened.next_decision) == {"reward.claim_gold", "reward.choose_card", "reward.skip_card"}
    skipped = rules.apply(
        world,
        _request(opened.next_decision, lambda item: item.kind.value == "reward.skip_card"),
    )
    claimed = rules.apply(
        world,
        _request(skipped.next_decision, lambda item: item.kind.value == "reward.claim_gold"),
    )
    proceeded = rules.apply(
        world,
        _request(claimed.next_decision, lambda item: item.kind.value == "reward.proceed"),
    )

    assert proceeded.next_decision.status.value == "waiting"
    assert proceeded.next_decision.observation.public_scope.decision_ordinal == MAX_PUBLIC_COUNTER


def test_begin_rejects_gold_reward_that_cannot_be_publicly_projected() -> None:
    world = _world()
    world.gold = MAX_PUBLIC_COUNTER - 10
    rules = _rules()
    before = world.to_private_dict()

    with pytest.raises(RewardRuleError, match="gold reward"):
        rules.begin(
            world,
            reward_table_id="combat_reward_basic",
            decision_sequence=0,
            public_scope=_scope(),
        )

    assert world.to_private_dict() == before


def test_exhausted_card_allocator_omits_choose_but_retains_skip_completion() -> None:
    world = _world()
    world.identity_allocator.next_card_ordinal = 100_000_000
    assert world.identity_allocator.can_allocate_card_id() is False
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

    assert _candidate_kinds(opened.next_decision) == {"reward.claim_gold", "reward.skip_card"}
    skipped = rules.apply(
        world,
        _request(opened.next_decision, lambda item: item.kind.value == "reward.skip_card"),
    )
    claimed = rules.apply(
        world,
        _request(skipped.next_decision, lambda item: item.kind.value == "reward.claim_gold"),
    )
    proceeded = rules.apply(
        world,
        _request(claimed.next_decision, lambda item: item.kind.value == "reward.proceed"),
    )

    assert proceeded.next_decision.status.value == "waiting"
    assert world.identity_allocator.next_card_ordinal == 100_000_000


@pytest.mark.parametrize(
    "event",
    (
        PublicEvent(
            0,
            PublicEventKind.REWARD_GOLD_CLAIMED,
            DecisionPhase.REWARD,
            {"amount": 25},
        ),
        PublicEvent(
            0,
            PublicEventKind.REWARD_CARD_OPENED,
            DecisionPhase.REWARD,
            {"offer_count": 3},
        ),
        PublicEvent(
            0,
            PublicEventKind.REWARD_CARD_CHOSEN,
            DecisionPhase.REWARD,
            {"card_definition_id": "strike", "upgraded": False},
        ),
        PublicEvent(0, PublicEventKind.REWARD_CARD_SKIPPED, DecisionPhase.REWARD, {}),
        PublicEvent(0, PublicEventKind.REWARD_PROCEEDED, DecisionPhase.REWARD, {}),
    ),
)
def test_tampered_last_reward_event_cannot_contradict_initial_reward_flags(event: PublicEvent) -> None:
    world = _world()
    rules = _rules()
    rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    _replace_pending_context(
        world,
        lambda context: context.__setitem__("public_events", [event.to_dict()]),
    )

    with pytest.raises(RewardRuleError):
        rules.decision(world)


def test_tampered_reward_event_payload_and_empty_event_state_fail_closed() -> None:
    world = _world()
    rules = _rules()
    rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    world.gold += 25
    _replace_pending_context(
        world,
        lambda context: context.update(
            gold_claimed=True,
            public_events=[
                PublicEvent(
                    0,
                    PublicEventKind.REWARD_GOLD_CLAIMED,
                    DecisionPhase.REWARD,
                    {"amount": 26},
                ).to_dict()
            ],
        ),
    )
    with pytest.raises(RewardRuleError, match="Gold-claimed"):
        rules.decision(world)

    world = _world()
    rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    world.gold += 25
    _replace_pending_context(
        world,
        lambda context: context.__setitem__("gold_claimed", True),
    )
    with pytest.raises(RewardRuleError, match="no public event"):
        rules.decision(world)


def test_forged_gold_flag_and_event_without_gold_mutation_fails_closed() -> None:
    world = _world()
    rules = _rules()
    rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    baseline_gold = world.gold
    gold_event = PublicEvent(
        0,
        PublicEventKind.REWARD_GOLD_CLAIMED,
        DecisionPhase.REWARD,
        {"amount": 25},
    ).to_dict()
    _replace_pending_context(
        world,
        lambda context: context.update(
            gold_claimed=True,
            public_events=[gold_event],
        ),
    )

    with pytest.raises(RewardRuleError, match="Persistent gold"):
        rules.decision(world)
    assert world.gold == baseline_gold


def test_tampered_proceeded_kind_and_multiple_last_events_fail_closed() -> None:
    world = _world()
    rules = _rules()
    decision = rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    claimed = rules.apply(
        world,
        _request(decision, lambda item: item.kind.value == "reward.claim_gold"),
    )
    opened = rules.apply(
        world,
        _request(claimed.next_decision, lambda item: item.kind.value == "reward.open_card_reward"),
    )
    skipped = rules.apply(
        world,
        _request(opened.next_decision, lambda item: item.kind.value == "reward.skip_card"),
    )
    rules.apply(
        world,
        _request(skipped.next_decision, lambda item: item.kind.value == "reward.proceed"),
    )
    _replace_pending_context(
        world,
        lambda context: context.__setitem__(
            "public_events",
            [PublicEvent(0, PublicEventKind.REWARD_CARD_SKIPPED, DecisionPhase.REWARD, {}).to_dict()],
        ),
    )
    with pytest.raises(RewardRuleError, match="Proceeded"):
        rules.decision(world)

    world = _world()
    rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    gold_event = PublicEvent(
        0,
        PublicEventKind.REWARD_GOLD_CLAIMED,
        DecisionPhase.REWARD,
        {"amount": 25},
    ).to_dict()
    _replace_pending_context(
        world,
        lambda context: context.__setitem__("public_events", [gold_event, gold_event]),
    )
    with pytest.raises(RewardRuleError):
        rules.decision(world)


def test_forged_chosen_state_without_open_rng_or_card_mutation_fails_closed() -> None:
    world = _world()
    rules = _rules()
    rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    deck_before = world.master_deck
    allocator_before = world.identity_allocator.to_dict()
    rng_before = world.rng.snapshot()
    chosen_event = PublicEvent(
        0,
        PublicEventKind.REWARD_CARD_CHOSEN,
        DecisionPhase.REWARD,
        {"card_definition_id": "strike", "upgraded": False},
    ).to_dict()
    _replace_pending_context(
        world,
        lambda context: context.update(
            card_opened=True,
            card_claimed=True,
            card_resolution="chosen",
            chosen_card_definition_id="strike",
            offers=list(REWARD_TABLES[0].card_definition_ids),
            public_events=[chosen_event],
        ),
    )

    with pytest.raises(RewardRuleError):
        rules.decision(world)
    assert world.master_deck == deck_before
    assert world.identity_allocator.to_dict() == allocator_before
    assert world.rng.snapshot() == rng_before


def test_forged_skipped_state_without_opening_shuffle_fails_closed() -> None:
    world = _world()
    rules = _rules()
    rules.begin(
        world,
        reward_table_id="combat_reward_basic",
        decision_sequence=0,
        public_scope=_scope(),
    )
    deck_before = world.master_deck
    allocator_before = world.identity_allocator.to_dict()
    rng_before = world.rng.snapshot()
    skipped_event = PublicEvent(
        0,
        PublicEventKind.REWARD_CARD_SKIPPED,
        DecisionPhase.REWARD,
        {},
    ).to_dict()
    _replace_pending_context(
        world,
        lambda context: context.update(
            card_opened=True,
            card_claimed=True,
            card_resolution="skipped",
            offers=list(REWARD_TABLES[0].card_definition_ids),
            public_events=[skipped_event],
        ),
    )

    with pytest.raises(RewardRuleError):
        rules.decision(world)
    assert world.master_deck == deck_before
    assert world.identity_allocator.to_dict() == allocator_before
    assert world.rng.snapshot() == rng_before


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
