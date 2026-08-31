from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
import inspect

import pytest

from game.contracts.headless_v0 import (
    COMPATIBILITY_CLASS,
    CONTRACT_FINGERPRINT,
    CONTRACT_VERSION,
    ActionRequest,
    BackendCapabilities,
    BackendManifest,
    CombatEndTurnCandidate,
    CombatOutcome,
    CombatPlayCardCandidate,
    ComponentEvidence,
    ContractValidationError,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    DuplicateFieldError,
    EvidenceLabel,
    HeadlessBinding,
    MapChooseNodeCandidate,
    NodeKind,
    PolicyView,
    PublicEvent,
    PublicEventKind,
    PublicObservation,
    PublicReferenceKind,
    PublicScope,
    RewardChooseCardCandidate,
    RewardClaimGoldCandidate,
    RewardKind,
    RewardOpenCardRewardCandidate,
    RewardProceedCandidate,
    RewardSkipCardCandidate,
    RoomEffectKind,
    RoomEventOptionCandidate,
    RoomKind,
    RoomOptionKind,
    RoomProceedCandidate,
    RoomRestHealCandidate,
    RunOutcome,
    Transition,
    TransitionReason,
    TransitionResult,
    candidate_from_dict,
    candidate_to_dict,
    canonical_json,
    combat_card_reference,
    combat_enemy_reference,
    map_node_reference,
    reward_offer_reference,
    reward_reference,
    room_option_reference,
)


BACKEND_FINGERPRINT = "a" * 64
CONTENT_FINGERPRINT = "b" * 64
RULES_FINGERPRINT = "c" * 64
EVIDENCE_FINGERPRINT = "d" * 64


def _scope(
    *,
    history: int = 3,
    decision: int = 7,
    **reveal_overrides: int,
) -> PublicScope:
    reveals = {kind.value: 0 for kind in PublicReferenceKind}
    reveals.update(reveal_overrides)
    return PublicScope(history, decision, reveals)


def _run_player(*, hp: int = 61) -> dict[str, object]:
    return {"hp": hp, "max_hp": 80, "gold": 99, "deck_size": 10}


def _combat_data(*, hp: int = 61, scope: PublicScope | None = None) -> dict[str, object]:
    selected_scope = scope or _scope()
    enemy_ref = combat_enemy_reference(selected_scope, "jaw_worm", 0)
    card_ref = combat_card_reference(selected_scope, "strike", 0)
    return {
        "turn": 2,
        "player": {
            "hp": hp,
            "max_hp": 80,
            "block": 3,
            "energy": 2,
            "energy_per_turn": 3,
            "strength": 0,
            "statuses": {"vulnerable": 0, "shrink": 0},
        },
        "enemies": [
            {
                "enemy_ref": enemy_ref,
                "enemy_definition_id": "jaw_worm",
                "hp": 37,
                "max_hp": 40,
                "block": 0,
                "strength": 0,
                "statuses": {"vulnerable": 0, "shrink": 0},
                "intent": {
                    "kind": "attack",
                    "attack_damage": 11,
                    "attack_count": 1,
                    "block_gain": 0,
                    "strength_gain": 0,
                    "status_kind": "none",
                    "status_stacks": 0,
                    "slimed_added": 0,
                },
                "alive": True,
            }
        ],
        "hand": [
            {
                "card_ref": card_ref,
                "card_definition_id": "strike",
                "cost": 1,
                "upgraded": False,
            }
        ],
        "draw_pile_size": 4,
        "discard_pile_size": 0,
        "exhaust_pile_size": 0,
        "terminal": False,
        "outcome": "ongoing",
    }


def _combat_observation(
    *,
    hp: int = 61,
    scope: PublicScope | None = None,
) -> PublicObservation:
    selected_scope = scope or _scope()
    return PublicObservation(
        DecisionPhase.COMBAT,
        _combat_data(hp=hp, scope=selected_scope),
        selected_scope,
    )


def _combat_candidates(
    scope: PublicScope | None = None,
) -> tuple[CombatEndTurnCandidate, CombatPlayCardCandidate]:
    selected_scope = scope or _scope()
    decision_scope = selected_scope.decision_scope
    return (
        CombatEndTurnCandidate(decision_scope),
        CombatPlayCardCandidate(
            decision_scope=decision_scope,
            card_ref=combat_card_reference(selected_scope, "strike", 0),
            target_ref=combat_enemy_reference(selected_scope, "jaw_worm", 0),
        ),
    )


def _combat_event(*, sequence: int = 0) -> PublicEvent:
    return PublicEvent(
        sequence=sequence,
        event_type=PublicEventKind.COMBAT_CARD_PLAYED,
        phase=DecisionPhase.COMBAT,
        data={
            "card_definition_id": "strike",
            "target_enemy_definition_id": "jaw_worm",
        },
    )


def _reward_data(
    *,
    opened: bool = True,
    scope: PublicScope | None = None,
) -> dict[str, object]:
    selected_scope = scope or _scope()
    gold_ref = reward_reference(selected_scope, RewardKind.GOLD, 0)
    card_ref = reward_reference(selected_scope, RewardKind.CARD, 1)
    offers = []
    if opened:
        offers = [
            {
                "offer_ref": reward_offer_reference(
                    selected_scope,
                    card_ref,
                    "strike",
                    0,
                ),
                "card_definition_id": "strike",
                "upgraded": False,
            }
        ]
    return {
        "player": _run_player(),
        "rewards": [
            {
                "reward_ref": gold_ref,
                "kind": "gold",
                "claimed": False,
                "opened": False,
                "amount": 25,
                "offers": [],
                "can_skip": False,
            },
            {
                "reward_ref": card_ref,
                "kind": "card",
                "claimed": False,
                "opened": opened,
                "amount": 0,
                "offers": offers,
                "can_skip": opened,
            },
        ],
        "can_proceed": True,
    }


def _map_data(*, scope: PublicScope | None = None) -> dict[str, object]:
    selected_scope = scope or _scope()
    combat_ref = map_node_reference(selected_scope, NodeKind.COMBAT, 0)
    rest_ref = map_node_reference(selected_scope, NodeKind.REST, 1)
    return {
        "player": _run_player(),
        "current_node_ref": combat_ref,
        "nodes": [
            {
                "node_ref": combat_ref,
                "kind": "combat",
                "available": False,
                "visited": True,
            },
            {
                "node_ref": rest_ref,
                "kind": "rest",
                "available": True,
                "visited": False,
            },
        ],
        "edges": [{"source_node_ref": combat_ref, "target_node_ref": rest_ref}],
        "visited_node_refs": [combat_ref],
    }


def _room_data(
    *,
    room_kind: RoomKind = RoomKind.REST,
    scope: PublicScope | None = None,
) -> dict[str, object]:
    selected_scope = scope or _scope()
    option_kind = (
        RoomOptionKind.REST_HEAL
        if room_kind is RoomKind.REST
        else RoomOptionKind.EVENT_OPTION
    )
    effect = RoomEffectKind.HEAL if room_kind is RoomKind.REST else RoomEffectKind.GAIN_GOLD
    amount = 18 if room_kind is RoomKind.REST else 25
    return {
        "player": _run_player(),
        "room_kind": room_kind.value,
        "options": [
            {
                "option_ref": room_option_reference(
                    selected_scope,
                    room_kind,
                    option_kind,
                    0,
                ),
                "kind": option_kind.value,
                "effect": effect.value,
                "amount": amount,
                "enabled": True,
            }
        ],
        "can_proceed": True,
    }


def _observation(
    phase: DecisionPhase,
    scope: PublicScope | None = None,
) -> PublicObservation:
    selected_scope = scope or _scope()
    data = {
        DecisionPhase.COMBAT: _combat_data(scope=selected_scope),
        DecisionPhase.REWARD: _reward_data(scope=selected_scope),
        DecisionPhase.MAP: _map_data(scope=selected_scope),
        DecisionPhase.ROOM: _room_data(scope=selected_scope),
        DecisionPhase.TERMINAL: {"outcome": "victory", "player": _run_player()},
        DecisionPhase.UNSUPPORTED: {"reason_code": "unsupported_phase"},
    }[phase]
    return PublicObservation(phase, data, selected_scope)


def _decision(
    *,
    sequence: int = 7,
    observation: PublicObservation | None = None,
    candidates: tuple | None = None,
    events: tuple[PublicEvent, ...] | None = None,
    status: DecisionStatus = DecisionStatus.ACTIONABLE,
    phase: DecisionPhase = DecisionPhase.COMBAT,
    content_fingerprint: str = CONTENT_FINGERPRINT,
    run_id: str = "run:fixture:001",
) -> DecisionState:
    selected_observation = observation or _observation(
        phase,
        _scope(decision=sequence),
    )
    selected_candidates = candidates
    if selected_candidates is None:
        selected_candidates = (
            _combat_candidates(selected_observation.public_scope)
            if status is DecisionStatus.ACTIONABLE and phase is DecisionPhase.COMBAT
            else ()
        )
    selected_events = (_combat_event(),) if events is None else events
    return DecisionState.create(
        backend_id="fixture_backend",
        backend_version="1.0.0",
        backend_fingerprint=BACKEND_FINGERPRINT,
        content_version="fixture_content_v1",
        content_fingerprint=content_fingerprint,
        rules_version="fixture_rules_v1",
        rules_fingerprint=RULES_FINGERPRINT,
        run_id=run_id,
        decision_sequence=sequence,
        status=status,
        phase=phase,
        observation=selected_observation,
        candidates=selected_candidates,
        public_events=selected_events,
    )


def _terminal_decision(*, events: tuple[PublicEvent, ...] = ()) -> DecisionState:
    return _decision(
        sequence=8,
        status=DecisionStatus.TERMINAL,
        phase=DecisionPhase.TERMINAL,
        events=events,
    )


def _manifest() -> BackendManifest:
    return BackendManifest(
        backend_id="fixture_backend",
        backend_version="1.0.0",
        backend_fingerprint=BACKEND_FINGERPRINT,
        content_version="fixture_content_v1",
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_version="fixture_rules_v1",
        rules_fingerprint=RULES_FINGERPRINT,
        capabilities=BackendCapabilities(True, True, True, False, False, False),
        supported_phases=(DecisionPhase.COMBAT,),
        unsupported_phases=(DecisionPhase.MAP, DecisionPhase.REWARD, DecisionPhase.ROOM),
        evidence=(
            ComponentEvidence(
                "fixture",
                EvidenceLabel.STRUCTURAL_FIXTURE,
                "fixture_v1",
                EVIDENCE_FINGERPRINT,
            ),
        ),
    )


def _all_candidates() -> tuple:
    scope = _scope()
    decision_scope = scope.decision_scope
    gold_ref = reward_reference(scope, RewardKind.GOLD, 0)
    card_reward_ref = reward_reference(scope, RewardKind.CARD, 1)
    offer_ref = reward_offer_reference(scope, card_reward_ref, "strike", 0)
    rest_ref = room_option_reference(
        scope,
        RoomKind.REST,
        RoomOptionKind.REST_HEAL,
        0,
    )
    event_ref = room_option_reference(
        scope,
        RoomKind.EVENT,
        RoomOptionKind.EVENT_OPTION,
        0,
    )
    return (
        CombatPlayCardCandidate(
            decision_scope,
            combat_card_reference(scope, "strike", 0),
            combat_enemy_reference(scope, "jaw_worm", 0),
        ),
        CombatEndTurnCandidate(decision_scope),
        RewardClaimGoldCandidate(decision_scope, gold_ref, 25),
        RewardOpenCardRewardCandidate(decision_scope, card_reward_ref),
        RewardChooseCardCandidate(decision_scope, card_reward_ref, offer_ref, "strike"),
        RewardSkipCardCandidate(decision_scope, card_reward_ref),
        RewardProceedCandidate(decision_scope),
        MapChooseNodeCandidate(decision_scope, map_node_reference(scope, NodeKind.REST, 1)),
        RoomRestHealCandidate(decision_scope, rest_ref, 18),
        RoomEventOptionCandidate(decision_scope, event_ref),
        RoomProceedCandidate(decision_scope),
    )


def test_contract_identity_and_canonical_vectors_are_stable() -> None:
    assert CONTRACT_VERSION == "headless_v0"
    assert COMPATIBILITY_CLASS == "exact_contract_fingerprint"
    assert CONTRACT_FINGERPRINT == (
        "e5ab4c29f0c077178d543b36e24494d3ec8d0d62528f44becf6f13eae7dee1b3"
    )
    assert canonical_json({"z": 0, "a": "é", "list": [True, None]}) == (
        '{"a":"é","list":[true,null],"z":0}'
    )
    assert _decision().decision_hash == (
        "cb7a5954ff05cdd282acca77ab6b0dc3653b7e6ee28e293e0a0a44e97917b424"
    )


def test_manifest_decision_request_and_transition_round_trip() -> None:
    manifest = _manifest()
    assert BackendManifest.from_json(manifest.to_json()) == manifest
    decision = _decision()
    assert DecisionState.from_json(decision.to_json()) == decision
    binding = HeadlessBinding.for_candidate(decision, decision.candidates[0].candidate_id)
    request = ActionRequest(binding)
    assert ActionRequest.from_json(request.to_json()) == request
    resolved = PublicEvent(
        0,
        PublicEventKind.COMBAT_RESOLVED,
        DecisionPhase.COMBAT,
        {"outcome": "victory"},
    )
    transition = Transition(
        TransitionResult.ACCEPTED,
        TransitionReason.ACCEPTED,
        binding,
        (resolved,),
        _terminal_decision(events=(resolved,)),
    )
    assert Transition.from_json(transition.to_json()) == transition
    assert "reward" not in transition.to_dict()


def test_all_candidate_codecs_derive_ids_from_public_semantics() -> None:
    for candidate in _all_candidates():
        encoded = candidate_to_dict(candidate)
        assert candidate_from_dict(encoded) == candidate
        assert candidate.candidate_id.startswith("cand.")
        assert set(encoded).isdisjoint({"index", "slot", "position", "private_state"})
    assert len({candidate.candidate_id for candidate in _all_candidates()}) == 11


def test_candidate_id_tampering_and_arbitrary_constructor_text_fail() -> None:
    candidate = _combat_candidates()[1]
    encoded = candidate_to_dict(candidate)
    encoded["candidate_id"] = "cand." + "0" * 64
    with pytest.raises(ContractValidationError, match="not canonically derived"):
        candidate_from_dict(encoded)
    with pytest.raises(TypeError):
        CombatEndTurnCandidate(candidate_id="candidate:hidden-bit-1")


def test_public_reference_factories_have_only_explicit_public_basis() -> None:
    assert tuple(inspect.signature(combat_card_reference).parameters) == (
        "scope",
        "card_definition_id",
        "presentation_ordinal",
    )
    scope = _scope()
    with pytest.raises(TypeError):
        combat_card_reference(scope, "strike", 0, private_state="secret")
    assert combat_card_reference(scope, "strike", 0) == combat_card_reference(
        scope, "strike", 0
    )
    assert combat_card_reference(scope, "strike", 0) != combat_card_reference(
        scope, "defend", 0
    )


def test_equal_public_different_private_inputs_cannot_change_policy_or_hash() -> None:
    def project(private_state: object) -> tuple[PublicObservation, tuple]:
        del private_state
        return _combat_observation(), _combat_candidates()

    observation_a, candidates_a = project({"rng_state": 1, "raw_card_id": "secret-a"})
    observation_b, candidates_b = project({"rng_state": 2, "raw_card_id": "secret-b"})
    decision_a = _decision(observation=observation_a, candidates=candidates_a)
    decision_b = _decision(observation=observation_b, candidates=candidates_b)
    assert decision_a.policy_view() == decision_b.policy_view()
    assert decision_a.decision_hash == decision_b.decision_hash
    assert tuple(item.candidate_id for item in candidates_a) == tuple(
        item.candidate_id for item in candidates_b
    )


def test_candidate_identity_binds_public_decision_scope_and_semantics() -> None:
    first_scope = _scope(decision=7)
    next_scope = _scope(decision=8)
    first = CombatEndTurnCandidate(first_scope.decision_scope)
    same = CombatEndTurnCandidate(first_scope.decision_scope)
    next_decision = CombatEndTurnCandidate(next_scope.decision_scope)
    assert first.candidate_id == same.candidate_id
    assert first.candidate_id != next_decision.candidate_id


def test_public_reference_lifetimes_preserve_continuity_and_prevent_reuse() -> None:
    first = _scope(
        decision=7,
        card=4,
        enemy=3,
        node=2,
        offer=8,
        option=6,
        reward=5,
    )
    continued = _scope(
        decision=8,
        card=4,
        enemy=3,
        node=2,
        offer=8,
        option=6,
        reward=5,
    )
    assert combat_card_reference(first, "strike", 0) == combat_card_reference(
        continued, "strike", 0
    )
    assert reward_reference(first, RewardKind.CARD, 0) == reward_reference(
        continued, RewardKind.CARD, 0
    )
    first_reward_ref = reward_reference(first, RewardKind.CARD, 0)
    continued_reward_ref = reward_reference(continued, RewardKind.CARD, 0)
    assert reward_offer_reference(
        first, first_reward_ref, "strike", 0
    ) == reward_offer_reference(
        continued, continued_reward_ref, "strike", 0
    )
    assert combat_enemy_reference(first, "jaw_worm", 0) == combat_enemy_reference(
        continued, "jaw_worm", 0
    )
    assert map_node_reference(first, NodeKind.REST, 0) == map_node_reference(
        continued, NodeKind.REST, 0
    )
    assert room_option_reference(
        first, RoomKind.REST, RoomOptionKind.REST_HEAL, 0
    ) == room_option_reference(
        continued, RoomKind.REST, RoomOptionKind.REST_HEAL, 0
    )

    next_card_reveal = _scope(
        decision=8, card=5, enemy=3, node=2, offer=8, option=6, reward=5
    )
    next_enemy_reveal = _scope(
        decision=8, card=4, enemy=4, node=2, offer=8, option=6, reward=5
    )
    next_node_reveal = _scope(
        decision=8, card=4, enemy=3, node=3, offer=8, option=6, reward=5
    )
    next_offer_reveal = _scope(
        decision=8, card=4, enemy=3, node=2, offer=9, option=6, reward=5
    )
    next_reward_reveal = _scope(
        decision=8, card=4, enemy=3, node=2, offer=8, option=6, reward=6
    )
    next_option_reveal = _scope(
        decision=8, card=4, enemy=3, node=2, offer=8, option=7, reward=5
    )
    assert combat_card_reference(first, "strike", 0) != combat_card_reference(
        next_card_reveal, "strike", 0
    )
    assert reward_reference(first, RewardKind.CARD, 0) != reward_reference(
        next_reward_reveal, RewardKind.CARD, 0
    )
    assert combat_enemy_reference(first, "jaw_worm", 0) != combat_enemy_reference(
        next_enemy_reveal, "jaw_worm", 0
    )
    assert map_node_reference(first, NodeKind.REST, 0) != map_node_reference(
        next_node_reveal, NodeKind.REST, 0
    )
    assert reward_offer_reference(
        first, first_reward_ref, "strike", 0
    ) != reward_offer_reference(
        next_offer_reveal,
        reward_reference(next_offer_reveal, RewardKind.CARD, 0),
        "strike",
        0,
    )
    assert room_option_reference(
        first, RoomKind.REST, RoomOptionKind.REST_HEAL, 0
    ) != room_option_reference(
        next_option_reveal, RoomKind.REST, RoomOptionKind.REST_HEAL, 0
    )


def test_public_history_scope_prevents_alias_reuse_across_histories() -> None:
    first = _scope(history=3, decision=7, enemy=2)
    restarted = _scope(history=4, decision=0, enemy=2)
    assert combat_enemy_reference(first, "jaw_worm", 0) != combat_enemy_reference(
        restarted, "jaw_worm", 0
    )


def test_public_scope_codec_is_exact_and_rejects_private_or_opaque_fields() -> None:
    scope = _scope()
    assert PublicScope.from_dict(scope.to_dict()) == scope

    missing_reveal = scope.to_dict()
    del missing_reveal["reveal_ordinals"][PublicReferenceKind.CARD.value]
    with pytest.raises(ContractValidationError, match="missing field"):
        PublicScope.from_dict(missing_reveal)

    private_top_level = scope.to_dict()
    private_top_level["run_id"] = "private-run"
    with pytest.raises(ContractValidationError, match="unknown field"):
        PublicScope.from_dict(private_top_level)

    private_reveal = scope.to_dict()
    private_reveal["reveal_ordinals"]["rng_state"] = 1
    with pytest.raises(ContractValidationError):
        PublicScope.from_dict(private_reveal)

    boolean_ordinal = scope.to_dict()
    boolean_ordinal["decision_ordinal"] = True
    with pytest.raises(ContractValidationError):
        PublicScope.from_dict(boolean_ordinal)


def test_candidate_scope_must_match_its_public_observation() -> None:
    observation = _combat_observation(scope=_scope(decision=7))
    wrong_scope = _scope(decision=8)
    with pytest.raises(ContractValidationError, match="decision_scope does not match"):
        _decision(
            observation=observation,
            candidates=(CombatEndTurnCandidate(wrong_scope.decision_scope),),
        )


def test_candidate_order_is_canonical_and_semantic() -> None:
    candidates = _combat_candidates()
    forward = _decision(candidates=candidates)
    reverse = _decision(candidates=tuple(reversed(candidates)))
    assert forward.decision_hash == reverse.decision_hash
    assert forward.to_json() == reverse.to_json()
    assert tuple(item.candidate_id for item in reverse.candidates) == tuple(
        sorted(item.candidate_id for item in candidates)
    )


@pytest.mark.parametrize("phase", tuple(DecisionPhase))
def test_every_phase_observation_round_trips_with_exact_schema(phase: DecisionPhase) -> None:
    observation = _observation(phase)
    assert PublicObservation.from_dict(observation.to_dict()) == observation


@pytest.mark.parametrize(
    "phase,bad_field",
    (
        (DecisionPhase.COMBAT, "behavior_state"),
        (DecisionPhase.COMBAT, "possible_next_move_names"),
        (DecisionPhase.COMBAT, "enemy"),
        (DecisionPhase.COMBAT, "action_mask"),
        (DecisionPhase.COMBAT, "shaped_reward"),
        (DecisionPhase.COMBAT, "projected_damage"),
        (DecisionPhase.COMBAT, "trajectory"),
        (DecisionPhase.COMBAT, "episode_diagnostic"),
        (DecisionPhase.COMBAT, "model_tensor"),
        (DecisionPhase.COMBAT, "encoded_observation"),
        (DecisionPhase.COMBAT, "rng_state"),
        (DecisionPhase.COMBAT, "snapshot_key"),
        (DecisionPhase.COMBAT, "control_token"),
        (DecisionPhase.COMBAT, "audit_record"),
        (DecisionPhase.COMBAT, "action_receipt"),
        (DecisionPhase.COMBAT, "hand_index"),
        (DecisionPhase.REWARD, "hidden_offers"),
        (DecisionPhase.MAP, "node_index"),
        (DecisionPhase.ROOM, "option_slot"),
        (DecisionPhase.TERMINAL, "future_outcome"),
        (DecisionPhase.UNSUPPORTED, "reason"),
    ),
)
def test_exact_phase_schemas_reject_unknown_policy_fields(
    phase: DecisionPhase,
    bad_field: str,
) -> None:
    scope = _scope()
    data = deepcopy(_observation(phase, scope).to_dict()["data"])
    data[bad_field] = "private"
    with pytest.raises(ContractValidationError, match="unknown field"):
        PublicObservation(phase, data, scope)


@pytest.mark.parametrize("alias", ("HP", "Hp", "max-hp", "maxHp"))
def test_raw_key_aliases_are_rejected(alias: str) -> None:
    scope = _scope()
    data = _combat_data()
    data["player"][alias] = data["player"].pop("hp")
    with pytest.raises(ContractValidationError):
        PublicObservation(DecisionPhase.COMBAT, data, scope)


@pytest.mark.parametrize("value", (True, False, 1.5, -1, 100_001))
def test_hp_requires_bounded_integer_not_bool_or_float(value: object) -> None:
    scope = _scope()
    data = _combat_data()
    data["player"]["hp"] = value
    with pytest.raises(ContractValidationError):
        PublicObservation(DecisionPhase.COMBAT, data, scope)


def test_combat_cross_fields_and_canonical_references_fail_closed() -> None:
    scope = _scope()
    data = _combat_data()
    data["enemies"][0]["alive"] = False
    with pytest.raises(ContractValidationError, match="alive"):
        PublicObservation(DecisionPhase.COMBAT, data, scope)
    data = _combat_data()
    data["terminal"] = True
    with pytest.raises(ContractValidationError, match="inconsistent"):
        PublicObservation(DecisionPhase.COMBAT, data, scope)
    data = _combat_data()
    data["hand"][0]["card_ref"] = combat_card_reference(scope, "defend", 0)
    with pytest.raises(ContractValidationError, match="canonically derived"):
        PublicObservation(DecisionPhase.COMBAT, data, scope)
    data = _combat_data()
    data["enemies"][0]["intent"]["kind"] = "oracle_advice"
    with pytest.raises(ContractValidationError):
        PublicObservation(DecisionPhase.COMBAT, data, scope)


def test_actionable_combat_observation_cannot_be_empty_or_terminal() -> None:
    scope = _scope()
    with pytest.raises(ContractValidationError):
        PublicObservation(DecisionPhase.COMBAT, {}, scope)
    data = _combat_data()
    data["enemies"] = []
    with pytest.raises(ContractValidationError, match="must contain"):
        PublicObservation(DecisionPhase.COMBAT, data, scope)
    data = _combat_data()
    data["terminal"] = True
    data["outcome"] = CombatOutcome.VICTORY.value
    data["enemies"][0]["hp"] = 0
    data["enemies"][0]["alive"] = False
    observation = PublicObservation(DecisionPhase.COMBAT, data, scope)
    with pytest.raises(ContractValidationError, match="cannot be terminal"):
        _decision(observation=observation)


@pytest.mark.parametrize(
    "phase,field,value",
    (
        (DecisionPhase.REWARD, "kind", "private_reward"),
        (DecisionPhase.MAP, "kind", "shop_secret"),
        (DecisionPhase.ROOM, "room_kind", "unknown"),
        (DecisionPhase.TERMINAL, "outcome", "future_victory"),
        (DecisionPhase.UNSUPPORTED, "reason_code", "arbitrary_text"),
    ),
)
def test_finite_coarse_enums_reject_unknown_values(
    phase: DecisionPhase,
    field: str,
    value: str,
) -> None:
    scope = _scope()
    data = deepcopy(_observation(phase, scope).to_dict()["data"])
    if phase is DecisionPhase.REWARD:
        data["rewards"][0][field] = value
    elif phase is DecisionPhase.MAP:
        data["nodes"][0][field] = value
    else:
        data[field] = value
    with pytest.raises(ContractValidationError):
        PublicObservation(phase, data, scope)


def test_map_reward_and_room_cross_links_fail_closed() -> None:
    scope = _scope()
    reward_data = _reward_data()
    reward_data["rewards"][1]["offers"][0]["offer_ref"] = reward_offer_reference(
        scope,
        reward_data["rewards"][1]["reward_ref"],
        "defend",
        0,
    )
    with pytest.raises(ContractValidationError, match="canonically derived"):
        PublicObservation(DecisionPhase.REWARD, reward_data, scope)
    map_data = _map_data()
    map_data["edges"][0]["target_node_ref"] = map_node_reference(
        scope, NodeKind.EVENT, 2
    )
    with pytest.raises(ContractValidationError, match="unresolved"):
        PublicObservation(DecisionPhase.MAP, map_data, scope)
    map_data = _map_data()
    map_data["nodes"][1]["visited"] = True
    map_data["visited_node_refs"] = [
        map_data["nodes"][1]["node_ref"],
        map_data["nodes"][0]["node_ref"],
    ]
    with pytest.raises(ContractValidationError, match="inconsistent"):
        PublicObservation(DecisionPhase.MAP, map_data, scope)
    room_data = _room_data()
    room_data["options"][0]["effect"] = RoomEffectKind.GAIN_GOLD.value
    with pytest.raises(ContractValidationError, match="canonical rest"):
        PublicObservation(DecisionPhase.ROOM, room_data, scope)


def test_candidate_references_must_resolve_in_same_observation() -> None:
    scope = _scope()
    with pytest.raises(ContractValidationError, match="card_ref does not resolve"):
        _decision(
            candidates=(
                CombatPlayCardCandidate(
                    scope.decision_scope,
                    combat_card_reference(scope, "defend", 0),
                    combat_enemy_reference(scope, "jaw_worm", 0),
                ),
            )
        )
    with pytest.raises(ContractValidationError, match="target_ref does not resolve"):
        _decision(
            candidates=(
                CombatPlayCardCandidate(
                    scope.decision_scope,
                    combat_card_reference(scope, "strike", 0),
                    combat_enemy_reference(scope, "jaw_worm", 1),
                ),
            )
        )


def test_reward_map_and_room_candidate_links_are_validated() -> None:
    scope = _scope()
    decision_scope = scope.decision_scope
    reward_observation = PublicObservation(
        DecisionPhase.REWARD, _reward_data(scope=scope), scope
    )
    reward_ref = reward_reference(scope, RewardKind.CARD, 1)
    offer_ref = reward_offer_reference(scope, reward_ref, "strike", 0)
    _decision(
        phase=DecisionPhase.REWARD,
        observation=reward_observation,
        candidates=(
            RewardChooseCardCandidate(
                decision_scope, reward_ref, offer_ref, "strike"
            ),
        ),
        events=(),
    )
    with pytest.raises(ContractValidationError, match="does not match its offer"):
        _decision(
            phase=DecisionPhase.REWARD,
            observation=reward_observation,
            candidates=(
                RewardChooseCardCandidate(
                    decision_scope, reward_ref, offer_ref, "defend"
                ),
            ),
            events=(),
        )
    map_observation = PublicObservation(DecisionPhase.MAP, _map_data(scope=scope), scope)
    with pytest.raises(ContractValidationError, match="not available"):
        _decision(
            phase=DecisionPhase.MAP,
            observation=map_observation,
            candidates=(
                MapChooseNodeCandidate(
                    decision_scope,
                    map_node_reference(scope, NodeKind.COMBAT, 0),
                ),
            ),
            events=(),
        )
    room_observation = PublicObservation(
        DecisionPhase.ROOM, _room_data(scope=scope), scope
    )
    with pytest.raises(ContractValidationError, match="does not match its option"):
        _decision(
            phase=DecisionPhase.ROOM,
            observation=room_observation,
            candidates=(
                RoomEventOptionCandidate(
                    decision_scope,
                    room_option_reference(
                        scope,
                        RoomKind.REST,
                        RoomOptionKind.REST_HEAL,
                        0,
                    ),
                ),
            ),
            events=(),
        )


def _all_events() -> tuple[PublicEvent, ...]:
    return (
        _combat_event(sequence=0),
        PublicEvent(1, PublicEventKind.COMBAT_TURN_ENDED, DecisionPhase.COMBAT, {}),
        PublicEvent(
            2,
            PublicEventKind.COMBAT_RESOLVED,
            DecisionPhase.COMBAT,
            {"outcome": "victory"},
        ),
        PublicEvent(3, PublicEventKind.REWARD_GOLD_CLAIMED, DecisionPhase.REWARD, {"amount": 25}),
        PublicEvent(
            4,
            PublicEventKind.REWARD_CARD_OPENED,
            DecisionPhase.REWARD,
            {"offer_count": 1},
        ),
        PublicEvent(
            5,
            PublicEventKind.REWARD_CARD_CHOSEN,
            DecisionPhase.REWARD,
            {"card_definition_id": "strike", "upgraded": False},
        ),
        PublicEvent(6, PublicEventKind.REWARD_CARD_SKIPPED, DecisionPhase.REWARD, {}),
        PublicEvent(7, PublicEventKind.REWARD_PROCEEDED, DecisionPhase.REWARD, {}),
        PublicEvent(8, PublicEventKind.MAP_NODE_CHOSEN, DecisionPhase.MAP, {"node_kind": "rest"}),
        PublicEvent(9, PublicEventKind.ROOM_REST_HEALED, DecisionPhase.ROOM, {"amount": 18}),
        PublicEvent(
            10,
            PublicEventKind.ROOM_EVENT_OPTION_CHOSEN,
            DecisionPhase.ROOM,
            {"effect": "gain_gold", "amount": 25},
        ),
        PublicEvent(11, PublicEventKind.ROOM_PROCEEDED, DecisionPhase.ROOM, {}),
        PublicEvent(
            12,
            PublicEventKind.RUN_TERMINATED,
            DecisionPhase.TERMINAL,
            {"outcome": RunOutcome.VICTORY.value},
        ),
    )


def test_finite_event_catalog_round_trips_every_event() -> None:
    for event in _all_events():
        assert PublicEvent.from_dict(event.to_dict()) == event


@pytest.mark.parametrize("event_type", ("rngstate", "oracle_advice", "future.outcome"))
def test_unknown_or_private_event_types_fail(event_type: str) -> None:
    with pytest.raises(ContractValidationError):
        PublicEvent(0, event_type, DecisionPhase.COMBAT, {})


def test_event_phase_payload_fields_and_types_are_exact() -> None:
    with pytest.raises(ContractValidationError, match="phase does not match"):
        PublicEvent(0, PublicEventKind.COMBAT_TURN_ENDED, DecisionPhase.REWARD, {})
    with pytest.raises(ContractValidationError, match="missing field"):
        PublicEvent(0, PublicEventKind.COMBAT_CARD_PLAYED, DecisionPhase.COMBAT, {})
    with pytest.raises(ContractValidationError, match="unknown field"):
        PublicEvent(
            0,
            PublicEventKind.COMBAT_TURN_ENDED,
            DecisionPhase.COMBAT,
            {"private_string": "secret"},
        )
    with pytest.raises(ContractValidationError):
        PublicEvent(
            0,
            PublicEventKind.REWARD_GOLD_CLAIMED,
            DecisionPhase.REWARD,
            {"amount": True},
        )


def test_event_sequences_are_canonical_zero_based_and_contiguous() -> None:
    with pytest.raises(ContractValidationError, match="zero"):
        _decision(events=(_combat_event(sequence=1),))
    with pytest.raises(ContractValidationError, match="zero"):
        _decision(events=(_combat_event(sequence=0), _combat_event(sequence=2)))


def test_missing_nested_fields_and_boolean_integer_aliases_fail() -> None:
    scope = _scope()
    data = _combat_data()
    del data["enemies"][0]["intent"]["attack_count"]
    with pytest.raises(ContractValidationError, match="missing field"):
        PublicObservation(DecisionPhase.COMBAT, data, scope)
    data = _combat_data()
    data["hand"][0]["cost"] = True
    with pytest.raises(ContractValidationError):
        PublicObservation(DecisionPhase.COMBAT, data, scope)
    data = _combat_data()
    data["hand"][0]["card_instance_id"] = "raw-private-card-id"
    with pytest.raises(ContractValidationError, match="unknown field"):
        PublicObservation(DecisionPhase.COMBAT, data, scope)
    data = _combat_data()
    data["enemies"][0]["enemy_index"] = 0
    with pytest.raises(ContractValidationError, match="unknown field"):
        PublicObservation(DecisionPhase.COMBAT, data, scope)


def test_policy_view_constructor_cannot_bypass_reference_linkage() -> None:
    observation = _combat_observation()
    candidate = CombatPlayCardCandidate(
        observation.public_scope.decision_scope,
        "pub.card." + "0" * 64,
        combat_enemy_reference(observation.public_scope, "jaw_worm", 0),
    )
    with pytest.raises(ContractValidationError, match="card_ref does not resolve"):
        PolicyView(
            DecisionStatus.ACTIONABLE,
            DecisionPhase.COMBAT,
            observation,
            (candidate,),
            (),
        )


def test_unpaired_surrogates_normalize_to_contract_validation_errors() -> None:
    surrogate = chr(0xD800)
    with pytest.raises(ContractValidationError, match="surrogate"):
        canonical_json({"value": surrogate})
    with pytest.raises(ContractValidationError, match="surrogate"):
        canonical_json({surrogate: "value"})
    with pytest.raises(ContractValidationError, match="surrogate"):
        BackendManifest.from_json('{"backend_id":"\\ud800"}')
    with pytest.raises(ContractValidationError):
        combat_card_reference(_scope(), "strike" + surrogate, 0)


def test_hash_binds_public_candidate_event_decision_and_versions() -> None:
    baseline = _decision().decision_hash
    scope = _scope()
    variants = (
        _decision(sequence=8),
        _decision(observation=_combat_observation(hp=60)),
        _decision(candidates=(CombatEndTurnCandidate(scope.decision_scope),)),
        _decision(
            events=(
                PublicEvent(
                    0,
                    PublicEventKind.COMBAT_TURN_ENDED,
                    DecisionPhase.COMBAT,
                    {},
                ),
            )
        ),
        _decision(content_fingerprint="e" * 64),
        _decision(status=DecisionStatus.WAITING, candidates=()),
    )
    assert all(item.decision_hash != baseline for item in variants)


def test_hash_tampering_duplicate_candidates_unknown_and_duplicate_json_fail() -> None:
    encoded = deepcopy(_decision().to_dict())
    encoded["observation"]["data"]["player"]["hp"] = 1
    with pytest.raises(ContractValidationError, match="hash does not match"):
        DecisionState.from_dict(encoded)
    duplicate = CombatEndTurnCandidate(_scope().decision_scope)
    with pytest.raises(ContractValidationError, match="must be unique"):
        _decision(candidates=(duplicate, duplicate))
    manifest = _manifest().to_dict()
    manifest["unknown"] = True
    with pytest.raises(ContractValidationError, match="unknown field"):
        BackendManifest.from_dict(manifest)
    with pytest.raises(DuplicateFieldError):
        BackendManifest.from_json('{"backend_id":"a","backend_id":"b"}')


def test_policy_view_contains_only_public_data_and_is_deeply_immutable() -> None:
    view = _decision().policy_view()
    assert isinstance(view, PolicyView)
    assert {item.name for item in fields(PolicyView)} == {
        "status",
        "phase",
        "observation",
        "candidates",
        "public_events",
    }
    for forbidden in ("decision_hash", "run_id", "backend_fingerprint", "rng_state"):
        assert not hasattr(view, forbidden)
    with pytest.raises(TypeError):
        view.observation.data["player"]["hp"] = 0


def test_binding_is_bound_to_current_derived_candidate() -> None:
    decision = _decision()
    candidate_id = decision.candidates[0].candidate_id
    binding = HeadlessBinding.for_candidate(decision, candidate_id)
    assert binding.candidate_id == candidate_id
    assert binding.decision_hash == decision.decision_hash
    with pytest.raises(ContractValidationError, match="not advertised"):
        HeadlessBinding.for_candidate(decision, "cand." + "0" * 64)
    with pytest.raises(ContractValidationError, match="derived candidate"):
        HeadlessBinding(
            decision.run_id,
            decision.decision_sequence,
            decision.decision_hash,
            "candidate:hidden-bit-1",
        )


def test_transition_result_reason_sequence_and_event_rules_fail_closed() -> None:
    decision = _decision()
    binding = HeadlessBinding.for_candidate(decision, decision.candidates[0].candidate_id)
    with pytest.raises(ContractValidationError, match="combination is invalid"):
        Transition(
            TransitionResult.ACCEPTED,
            TransitionReason.REJECTED_BY_RULES,
            binding,
            decision.public_events,
            _terminal_decision(events=decision.public_events),
        )
    with pytest.raises(ContractValidationError, match="must advance"):
        Transition(
            TransitionResult.ACCEPTED,
            TransitionReason.ACCEPTED,
            binding,
            decision.public_events,
            decision,
        )
    with pytest.raises(ContractValidationError, match="events must equal"):
        Transition(
            TransitionResult.ACCEPTED,
            TransitionReason.ACCEPTED,
            binding,
            (),
            _terminal_decision(events=decision.public_events),
        )


def test_stale_accepts_prior_sequence_wrong_hash_and_wrong_run() -> None:
    prior = _decision()
    prior_binding = HeadlessBinding.for_candidate(prior, prior.candidates[0].candidate_id)
    current = _decision(sequence=8)
    assert Transition(
        TransitionResult.STALE,
        TransitionReason.STALE_BINDING,
        prior_binding,
        current.public_events,
        current,
    ).next_decision is current
    wrong_hash = HeadlessBinding(
        current.run_id,
        current.decision_sequence,
        "0" * 64,
        current.candidates[0].candidate_id,
    )
    Transition(
        TransitionResult.STALE,
        TransitionReason.STALE_BINDING,
        wrong_hash,
        current.public_events,
        current,
    )
    wrong_run_decision = _decision(sequence=8, run_id="run:wrong:001")
    wrong_run = HeadlessBinding.for_candidate(
        wrong_run_decision,
        wrong_run_decision.candidates[0].candidate_id,
    )
    Transition(
        TransitionResult.STALE,
        TransitionReason.STALE_BINDING,
        wrong_run,
        current.public_events,
        current,
    )


def test_stale_rejects_exact_identity_and_candidate_mismatch_alone() -> None:
    current = _decision()
    scope = current.observation.public_scope
    exact = HeadlessBinding.for_candidate(current, current.candidates[0].candidate_id)
    with pytest.raises(ContractValidationError, match="identity that differs"):
        Transition(
            TransitionResult.STALE,
            TransitionReason.STALE_BINDING,
            exact,
            current.public_events,
            current,
        )
    missing_candidate = CombatPlayCardCandidate(
        scope.decision_scope,
        combat_card_reference(scope, "defend", 0),
        combat_enemy_reference(scope, "jaw_worm", 0),
    ).candidate_id
    advertised = {item.candidate_id for item in current.candidates[:1]}
    assert missing_candidate not in advertised
    binding = HeadlessBinding(
        current.run_id,
        current.decision_sequence,
        current.decision_hash,
        missing_candidate,
    )
    with pytest.raises(ContractValidationError, match="identity that differs"):
        Transition(
            TransitionResult.STALE,
            TransitionReason.STALE_BINDING,
            binding,
            current.public_events,
            current,
        )


def test_rejected_is_nonmutating_and_classifies_missing_candidate() -> None:
    current = _decision()
    scope = current.observation.public_scope
    advertised = HeadlessBinding.for_candidate(current, current.candidates[0].candidate_id)
    rejected = Transition(
        TransitionResult.REJECTED,
        TransitionReason.REJECTED_BY_RULES,
        advertised,
        current.public_events,
        current,
    )
    assert rejected.next_decision is current
    newer = _decision(sequence=8)
    with pytest.raises(ContractValidationError, match="bound authoritative identity"):
        Transition(
            TransitionResult.REJECTED,
            TransitionReason.REJECTED_BY_RULES,
            advertised,
            newer.public_events,
            newer,
        )
    missing = CombatPlayCardCandidate(
        scope.decision_scope,
        combat_card_reference(scope, "defend", 0),
        combat_enemy_reference(scope, "jaw_worm", 0),
    ).candidate_id
    missing_binding = HeadlessBinding(
        current.run_id,
        current.decision_sequence,
        current.decision_hash,
        missing,
    )
    invalid = Transition(
        TransitionResult.REJECTED,
        TransitionReason.INVALID_CANDIDATE,
        missing_binding,
        current.public_events,
        current,
    )
    assert invalid.reason is TransitionReason.INVALID_CANDIDATE
    with pytest.raises(ContractValidationError, match="requires invalid_candidate"):
        Transition(
            TransitionResult.REJECTED,
            TransitionReason.REJECTED_BY_RULES,
            missing_binding,
            current.public_events,
            current,
        )
