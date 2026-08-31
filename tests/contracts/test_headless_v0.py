from __future__ import annotations

from copy import deepcopy
from dataclasses import fields

import pytest

from game.contracts.headless_v0 import (
    COMPATIBILITY_CLASS,
    CONTRACT_FINGERPRINT,
    CONTRACT_VERSION,
    ActionRequest,
    BackendCapabilities,
    BackendManifest,
    CombatEndTurnCandidate,
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
    PolicyView,
    PublicEvent,
    PublicObservation,
    RewardChooseCardCandidate,
    RewardClaimGoldCandidate,
    RewardOpenCardRewardCandidate,
    RewardProceedCandidate,
    RewardSkipCardCandidate,
    RoomEventOptionCandidate,
    RoomProceedCandidate,
    RoomRestHealCandidate,
    Transition,
    TransitionReason,
    TransitionResult,
    candidate_from_dict,
    candidate_to_dict,
    canonical_json,
)


BACKEND_FINGERPRINT = "a" * 64
CONTENT_FINGERPRINT = "b" * 64
RULES_FINGERPRINT = "c" * 64
EVIDENCE_FINGERPRINT = "d" * 64


def _combat_observation(*, current_hp: int = 61) -> PublicObservation:
    return PublicObservation(
        phase=DecisionPhase.COMBAT,
        data={
            "turn": 2,
            "player": {
                "hp": current_hp,
                "max_hp": 80,
                "block": 3,
                "energy": 2,
                "strength": 0,
                "statuses": {"vulnerable": 0, "shrink": 0},
            },
            "enemies": [
                {
                    "entity_id": "enemy:jaw_worm:0",
                    "name": "jaw_worm",
                    "hp": 37,
                    "max_hp": 40,
                    "block": 0,
                    "alive": True,
                    "intent": {
                        "kind": "attack",
                        "value": 11,
                        "move_name": "Chomp",
                        "attack_damage": 11,
                        "attack_count": 1,
                    },
                }
            ],
            "hand": [
                {
                    "card_instance_id": "card:0",
                    "card_definition_id": "strike",
                    "cost": 1,
                    "upgraded": False,
                }
            ],
            "draw_pile_size": 4,
            "discard_pile_size": 0,
            "exhaust_pile_size": 0,
            "terminal": False,
        },
    )


def _combat_event(*, delta: int = -6) -> PublicEvent:
    return PublicEvent(
        sequence=0,
        event_type="card_played",
        phase=DecisionPhase.COMBAT,
        data={
            "card_instance_id": "card:0",
            "target_entity_id": "enemy:jaw_worm:0",
            "delta": delta,
        },
    )


def _combat_candidates(*, card_instance_id: str = "card:0") -> tuple:
    return (
        CombatEndTurnCandidate(candidate_id="candidate:end_turn"),
        CombatPlayCardCandidate(
            candidate_id="candidate:play:card:0:enemy:jaw_worm:0",
            card_instance_id=card_instance_id,
            target_entity_id="enemy:jaw_worm:0",
        ),
    )


def _decision(
    *,
    sequence: int = 7,
    observation: PublicObservation | None = None,
    candidates: tuple | None = None,
    events: tuple[PublicEvent, ...] | None = None,
    status: DecisionStatus = DecisionStatus.ACTIONABLE,
    content_fingerprint: str = CONTENT_FINGERPRINT,
    run_id: str = "run:fixture:001",
) -> DecisionState:
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
        phase=DecisionPhase.COMBAT,
        observation=observation or _combat_observation(),
        candidates=(
            _combat_candidates()
            if candidates is None and status is DecisionStatus.ACTIONABLE
            else candidates or ()
        ),
        public_events=(_combat_event(),) if events is None else events,
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
        capabilities=BackendCapabilities(
            deterministic_reset=True,
            counterfactual_stepping=True,
            fixture_playback=True,
            snapshot_restore=False,
            live_truth=False,
            legacy_shaped_reward_diagnostics=False,
        ),
        supported_phases=(DecisionPhase.COMBAT,),
        unsupported_phases=(DecisionPhase.MAP, DecisionPhase.REWARD, DecisionPhase.ROOM),
        evidence=(
            ComponentEvidence(
                component="fixture",
                label=EvidenceLabel.STRUCTURAL_FIXTURE,
                version="fixture_v1",
                fingerprint=EVIDENCE_FINGERPRINT,
            ),
        ),
    )


def _terminal_decision(*, events: tuple[PublicEvent, ...] = ()) -> DecisionState:
    return DecisionState.create(
        backend_id="fixture_backend",
        backend_version="1.0.0",
        backend_fingerprint=BACKEND_FINGERPRINT,
        content_version="fixture_content_v1",
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_version="fixture_rules_v1",
        rules_fingerprint=RULES_FINGERPRINT,
        run_id="run:fixture:001",
        decision_sequence=8,
        status=DecisionStatus.TERMINAL,
        phase=DecisionPhase.TERMINAL,
        observation=PublicObservation(
            phase=DecisionPhase.TERMINAL,
            data={
                "outcome": "victory",
                "player": {"hp": 61, "max_hp": 80},
                "summary": "fixture complete",
            },
        ),
        public_events=events,
    )


ALL_CANDIDATES = (
    CombatPlayCardCandidate("c0", "card:0", "enemy:0"),
    CombatEndTurnCandidate("c1"),
    RewardClaimGoldCandidate("c2", 25),
    RewardOpenCardRewardCandidate("c3", "reward:0"),
    RewardChooseCardCandidate("c4", "reward:0", "offer:0", "strike"),
    RewardSkipCardCandidate("c5", "reward:0"),
    RewardProceedCandidate("c6"),
    MapChooseNodeCandidate("c7", "node:0"),
    RoomRestHealCandidate("c8", 18),
    RoomEventOptionCandidate("c9", "option:0"),
    RoomProceedCandidate("c10"),
)


def test_contract_identity_and_canonical_json_vectors_are_stable() -> None:
    assert CONTRACT_VERSION == "headless_v0"
    assert COMPATIBILITY_CLASS == "exact_contract_fingerprint"
    assert CONTRACT_FINGERPRINT == (
        "61f9fffee143b32d473c45c94ea2c038ddb2abbe2b227dd8d1b48d7e6969f18f"
    )
    assert canonical_json({"z": 0, "a": "é", "list": [True, None]}) == (
        '{"a":"é","list":[true,null],"z":0}'
    )
    assert _decision().decision_hash == (
        "c75078b065929a45eb060f307cc5c894aee2573bcc6567b0621623176690d037"
    )


def test_manifest_round_trip_and_exact_compatibility_identity() -> None:
    manifest = _manifest()
    assert BackendManifest.from_json(manifest.to_json()) == manifest
    assert manifest.contract_fingerprint == CONTRACT_FINGERPRINT
    assert manifest.compatibility_class == COMPATIBILITY_CLASS

    incompatible = deepcopy(manifest.to_dict())
    incompatible["contract_fingerprint"] = "0" * 64
    with pytest.raises(ContractValidationError, match="incompatible"):
        BackendManifest.from_dict(incompatible)


def test_all_typed_candidate_codecs_round_trip_without_positional_identity() -> None:
    for candidate in ALL_CANDIDATES:
        encoded = candidate_to_dict(candidate)
        assert candidate_from_dict(encoded) == candidate
        assert "index" not in encoded
        assert "position" not in encoded
        assert "slot" not in encoded

    play = candidate_to_dict(ALL_CANDIDATES[0])
    assert play["card_instance_id"] == "card:0"
    assert play["target_entity_id"] == "enemy:0"
    assert candidate_to_dict(ALL_CANDIDATES[7])["map_node_id"] == "node:0"


def test_decision_request_and_transition_json_round_trip() -> None:
    decision = _decision()
    assert DecisionState.from_json(decision.to_json()) == decision

    binding = HeadlessBinding.for_candidate(decision, "candidate:end_turn")
    request = ActionRequest(binding=binding)
    assert ActionRequest.from_json(request.to_json()) == request

    transition = Transition(
        result=TransitionResult.ACCEPTED,
        reason=TransitionReason.ACCEPTED,
        binding=binding,
        public_events=(_combat_event(),),
        next_decision=_terminal_decision(events=(_combat_event(),)),
    )
    assert Transition.from_json(transition.to_json()) == transition
    assert "reward" not in transition.to_dict()


def test_binding_is_bound_to_run_sequence_hash_and_advertised_candidate() -> None:
    decision = _decision()
    binding = HeadlessBinding.for_candidate(decision, "candidate:end_turn")
    assert binding.run_id == decision.run_id
    assert binding.decision_sequence == decision.decision_sequence
    assert binding.decision_hash == decision.decision_hash
    assert binding.candidate_id == "candidate:end_turn"

    with pytest.raises(ContractValidationError, match="not advertised"):
        HeadlessBinding.for_candidate(decision, "candidate:missing")


def test_candidate_order_is_canonical_and_not_durable_identity() -> None:
    ordered = _combat_candidates()
    reversed_decision = _decision(candidates=tuple(reversed(ordered)))
    forward_decision = _decision(candidates=ordered)
    assert reversed_decision.decision_hash == forward_decision.decision_hash
    assert reversed_decision.to_json() == forward_decision.to_json()
    assert tuple(item.candidate_id for item in reversed_decision.candidates) == tuple(
        sorted(item.candidate_id for item in ordered)
    )


def test_decision_hash_binds_decision_public_candidate_event_and_versions() -> None:
    baseline = _decision().decision_hash
    variants = (
        _decision(sequence=8),
        _decision(observation=_combat_observation(current_hp=60)),
        _decision(candidates=_combat_candidates(card_instance_id="card:replacement")),
        _decision(events=(_combat_event(delta=-7),)),
        _decision(content_fingerprint="e" * 64),
        _decision(status=DecisionStatus.WAITING, candidates=()),
    )
    assert all(variant.decision_hash != baseline for variant in variants)


def test_decision_hash_tampering_and_duplicate_candidate_ids_fail_closed() -> None:
    encoded = deepcopy(_decision().to_dict())
    encoded["observation"]["data"]["player"]["hp"] = 1
    with pytest.raises(ContractValidationError, match="hash does not match"):
        DecisionState.from_dict(encoded)

    duplicate = CombatEndTurnCandidate("candidate:end_turn")
    with pytest.raises(ContractValidationError, match="must be unique"):
        _decision(candidates=(duplicate, duplicate))


def test_unknown_and_duplicate_json_fields_fail_closed_at_every_boundary() -> None:
    manifest = _manifest().to_dict()
    manifest["unknown"] = True
    with pytest.raises(ContractValidationError, match="unknown field"):
        BackendManifest.from_dict(manifest)

    capabilities = _manifest().to_dict()
    capabilities["capabilities"]["unknown"] = True
    with pytest.raises(ContractValidationError, match="unknown field"):
        BackendManifest.from_dict(capabilities)

    decision = _decision().to_dict()
    decision["candidates"][0]["legacy_index"] = 0
    with pytest.raises(ContractValidationError, match="unknown field"):
        DecisionState.from_dict(decision)

    with pytest.raises(DuplicateFieldError, match="Duplicate JSON field"):
        BackendManifest.from_json('{"backend_id":"a","backend_id":"b"}')

    request = ActionRequest(HeadlessBinding.for_candidate(_decision(), "candidate:end_turn"))
    duplicated_binding = request.to_json().replace(
        '"candidate_id":"candidate:end_turn"',
        '"candidate_id":"candidate:end_turn","candidate_id":"candidate:end_turn"',
    )
    with pytest.raises(DuplicateFieldError, match="Duplicate JSON field"):
        ActionRequest.from_json(duplicated_binding)


@pytest.mark.parametrize(
    "forbidden_field",
    (
        "behavior_state",
        "arbitrary_policy_key",
        "enemy_index",
        "enemy_slot",
        "card_position",
        "control_token",
        "audit_receipt",
        "rng_state",
        "snapshot_key",
        "future_outcome",
        "hidden_offer",
        "debug_trace",
        "diagnostic_value",
        "shaped_reward",
        "action_mask",
    ),
)
def test_policy_observation_recursively_rejects_unapproved_semantics(
    forbidden_field: str,
) -> None:
    with pytest.raises(ContractValidationError):
        PublicObservation(
            phase=DecisionPhase.COMBAT,
            data={"player": {"hp": 61, forbidden_field: 1}},
        )


def test_phase_schema_rejects_other_phase_and_arbitrary_top_level_fields() -> None:
    with pytest.raises(ContractValidationError, match="outside the phase schema"):
        PublicObservation(phase=DecisionPhase.MAP, data={"hand": []})
    with pytest.raises(ContractValidationError, match="outside the phase schema"):
        PublicObservation(phase=DecisionPhase.COMBAT, data={"arbitrary": 1})


def test_public_events_reject_forbidden_event_semantics_and_payloads() -> None:
    with pytest.raises(ContractValidationError, match="forbidden public semantics"):
        PublicEvent(0, "rng_advanced", DecisionPhase.COMBAT, {})
    with pytest.raises(ContractValidationError, match="forbidden policy field"):
        PublicEvent(0, "card_played", DecisionPhase.COMBAT, {"debug_trace": "x"})


def test_policy_view_has_only_public_decision_data_and_is_immutable() -> None:
    decision = _decision()
    view = decision.policy_view()
    assert isinstance(view, PolicyView)
    assert {item.name for item in fields(PolicyView)} == {
        "status",
        "phase",
        "observation",
        "candidates",
        "public_events",
    }
    assert not hasattr(view, "decision_hash")
    assert not hasattr(view, "run_id")
    assert not hasattr(view, "backend_fingerprint")
    with pytest.raises(TypeError):
        view.observation.data["player"]["hp"] = 0


def test_non_json_floats_wrong_phase_candidates_and_event_order_fail_closed() -> None:
    with pytest.raises(ContractValidationError, match="floating-point"):
        PublicObservation(DecisionPhase.COMBAT, {"player": {"hp": 1.5}})
    with pytest.raises(ContractValidationError, match="does not match"):
        _decision(candidates=(MapChooseNodeCandidate("candidate:map", "node:0"),))
    with pytest.raises(ContractValidationError, match="strictly increasing"):
        _decision(events=(_combat_event(), _combat_event()))


def test_transition_result_reason_sequence_and_event_rules_fail_closed() -> None:
    decision = _decision()
    binding = HeadlessBinding.for_candidate(decision, "candidate:end_turn")
    with pytest.raises(ContractValidationError, match="combination is invalid"):
        Transition(
            result=TransitionResult.ACCEPTED,
            reason=TransitionReason.REJECTED_BY_RULES,
            binding=binding,
            public_events=(),
            next_decision=_terminal_decision(),
        )
    with pytest.raises(ContractValidationError, match="must advance"):
        Transition(
            result=TransitionResult.ACCEPTED,
            reason=TransitionReason.ACCEPTED,
            binding=binding,
            public_events=(_combat_event(),),
            next_decision=_decision(sequence=7),
        )
    with pytest.raises(ContractValidationError, match="events must equal"):
        Transition(
            result=TransitionResult.ACCEPTED,
            reason=TransitionReason.ACCEPTED,
            binding=binding,
            public_events=(),
            next_decision=_terminal_decision(events=(_combat_event(),)),
        )


def test_stale_transition_accepts_prior_sequence_current_authority() -> None:
    decision = _decision()
    binding = HeadlessBinding.for_candidate(decision, "candidate:end_turn")
    current = _decision(sequence=8)
    transition = Transition(
        result=TransitionResult.STALE,
        reason=TransitionReason.STALE_BINDING,
        binding=binding,
        public_events=current.public_events,
        next_decision=current,
    )
    assert transition.next_decision is current


def test_stale_transition_accepts_wrong_hash_at_same_sequence() -> None:
    current = _decision()
    binding = HeadlessBinding(
        run_id=current.run_id,
        decision_sequence=current.decision_sequence,
        decision_hash="0" * 64,
        candidate_id="candidate:end_turn",
    )
    transition = Transition(
        result=TransitionResult.STALE,
        reason=TransitionReason.STALE_BINDING,
        binding=binding,
        public_events=current.public_events,
        next_decision=current,
    )
    assert transition.next_decision.decision_hash != binding.decision_hash


def test_stale_transition_accepts_wrong_run() -> None:
    current = _decision()
    wrong_run_decision = _decision(run_id="run:wrong:001")
    binding = HeadlessBinding.for_candidate(
        wrong_run_decision,
        "candidate:end_turn",
    )
    transition = Transition(
        result=TransitionResult.STALE,
        reason=TransitionReason.STALE_BINDING,
        binding=binding,
        public_events=current.public_events,
        next_decision=current,
    )
    assert transition.next_decision.run_id != binding.run_id


def test_stale_transition_rejects_exact_binding_identity() -> None:
    current = _decision()
    binding = HeadlessBinding.for_candidate(current, "candidate:end_turn")
    with pytest.raises(ContractValidationError, match="identity that differs"):
        Transition(
            result=TransitionResult.STALE,
            reason=TransitionReason.STALE_BINDING,
            binding=binding,
            public_events=current.public_events,
            next_decision=current,
        )


def test_rejected_transition_requires_same_authoritative_identity() -> None:
    decision = _decision()
    binding = HeadlessBinding.for_candidate(decision, "candidate:end_turn")
    rejected = Transition(
        result=TransitionResult.REJECTED,
        reason=TransitionReason.REJECTED_BY_RULES,
        binding=binding,
        public_events=decision.public_events,
        next_decision=decision,
    )
    assert rejected.next_decision is decision

    current = _decision(sequence=8)
    with pytest.raises(ContractValidationError, match="bound authoritative identity"):
        Transition(
            result=TransitionResult.REJECTED,
            reason=TransitionReason.REJECTED_BY_RULES,
            binding=binding,
            public_events=current.public_events,
            next_decision=current,
        )
    with pytest.raises(ContractValidationError, match="cannot use that reason"):
        Transition(
            result=TransitionResult.REJECTED,
            reason=TransitionReason.INVALID_CANDIDATE,
            binding=binding,
            public_events=decision.public_events,
            next_decision=decision,
        )


def test_unadvertised_current_candidate_is_invalid_not_stale() -> None:
    current = _decision()
    binding = HeadlessBinding(
        run_id=current.run_id,
        decision_sequence=current.decision_sequence,
        decision_hash=current.decision_hash,
        candidate_id="candidate:missing",
    )
    rejected = Transition(
        result=TransitionResult.REJECTED,
        reason=TransitionReason.INVALID_CANDIDATE,
        binding=binding,
        public_events=current.public_events,
        next_decision=current,
    )
    assert rejected.reason is TransitionReason.INVALID_CANDIDATE

    with pytest.raises(ContractValidationError, match="identity that differs"):
        Transition(
            result=TransitionResult.STALE,
            reason=TransitionReason.STALE_BINDING,
            binding=binding,
            public_events=current.public_events,
            next_decision=current,
        )
    with pytest.raises(ContractValidationError, match="requires invalid_candidate"):
        Transition(
            result=TransitionResult.REJECTED,
            reason=TransitionReason.REJECTED_BY_RULES,
            binding=binding,
            public_events=current.public_events,
            next_decision=current,
        )
