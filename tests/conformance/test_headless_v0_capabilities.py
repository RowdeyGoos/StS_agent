"""Capability and evidence-claim conformance across accepted headless backends."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from game.backends.headless.combat_v0_backend import (
    BACKEND_FINGERPRINT as COMBAT_BACKEND_FINGERPRINT,
    RULES_FINGERPRINT as COMBAT_RULES_FINGERPRINT,
    CombatV0Backend,
)
from game.backends.headless.fixture_backend import FixtureBackend
from game.backends.headless.reduced_run_backend import (
    BACKEND_FINGERPRINT,
    RULES_FINGERPRINT,
    SNAPSHOT_FINGERPRINT,
    HeadlessRunConfig,
    ReducedRunBackend,
    ReducedRunBackendError,
)
from game.backends.headless.scenarios import scenario_from_id
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import (
    CONTRACT_FINGERPRINT,
    ActionRequest,
    BackendManifest,
    CandidateKind,
    DecisionPhase,
    DecisionState,
    EvidenceLabel,
    HeadlessBinding,
    TransitionReason,
    TransitionResult,
)


_ACCEPTED_CONTRACT_FINGERPRINT = "e5ab4c29f0c077178d543b36e24494d3ec8d0d62528f44becf6f13eae7dee1b3"
_ACCEPTED_BACKEND_FINGERPRINT = "cab0ed8cfe70a6fe3013f366592360ba8570bb362c8d0dffd2156cd8d3d001c3"
_ACCEPTED_RULES_FINGERPRINT = "71c5859d41a62dcd9013720635f59dab2fbe57198d48c685150e1e5873127c5a"
_ACCEPTED_SNAPSHOT_FINGERPRINT = "5f1880a3e22db87fbf8f7dc37c9987db9b48cdc142a760dd2e60a2cded48db4c"

_ACCEPTED_EVIDENCE = {
    "headless.fixture": (
        {
            "component": "fixture_corpus",
            "label": "structural_fixture",
            "version": "v1",
            "fingerprint": "d9cc190fa89a371eaa4e2245ca3ef80472312b738492e6a2d2215f9fb24dc8a4",
        },
        {
            "component": "fixture_playback",
            "label": "structural_fixture",
            "version": "v1",
            "fingerprint": "a760b1d1d02a833927fdeaec687cdfb9a12045ecbfc44ec07d35dbe27c6411f0",
        },
    ),
    "combat_v0": (
        {
            "component": "backend",
            "label": "combat_v0",
            "version": "combat_v0_backend_v1",
            "fingerprint": "65e8a6d3ee1d815bb0e07c8b104a7e51ecce41514d58e2bc188fb1ed64f8fdfe",
        },
        {
            "component": "content",
            "label": "structural_fixture",
            "version": "reduced_content_v0",
            "fingerprint": "fe771ea0f82c114d1d6a6389a44b169525c047914d955ce49d6db54e2472230f",
        },
        {
            "component": "projection",
            "label": "combat_v0",
            "version": "combat_v0_public_projection_v1",
            "fingerprint": "083cdcbf18d4481be689b1e6ea1d9b7d270b2cf9ab92e96a821e971ec018a56a",
        },
        {
            "component": "rules",
            "label": "combat_v0",
            "version": "legacy_combat_v0",
            "fingerprint": "9d046f9fa1f1051f465e3a8a8122896e2b55ddd63fe2ddc7e5178b7d7ac1c780",
        },
    ),
    "reduced_headless": (
        {
            "component": "combat_backend",
            "label": "combat_v0",
            "version": "combat_v0_backend_v1",
            "fingerprint": "65e8a6d3ee1d815bb0e07c8b104a7e51ecce41514d58e2bc188fb1ed64f8fdfe",
        },
        {
            "component": "combat_projection",
            "label": "combat_v0",
            "version": "combat_v0_public_projection_v1",
            "fingerprint": "083cdcbf18d4481be689b1e6ea1d9b7d270b2cf9ab92e96a821e971ec018a56a",
        },
        {
            "component": "combat_rules",
            "label": "combat_v0",
            "version": "legacy_combat_v0",
            "fingerprint": "9d046f9fa1f1051f465e3a8a8122896e2b55ddd63fe2ddc7e5178b7d7ac1c780",
        },
        {
            "component": "composer",
            "label": "structural_fixture",
            "version": "reduced_headless_v3",
            "fingerprint": "cab0ed8cfe70a6fe3013f366592360ba8570bb362c8d0dffd2156cd8d3d001c3",
        },
        {
            "component": "content",
            "label": "structural_fixture",
            "version": "reduced_content_v0",
            "fingerprint": "fe771ea0f82c114d1d6a6389a44b169525c047914d955ce49d6db54e2472230f",
        },
        {
            "component": "map",
            "label": "structural_fixture",
            "version": "reduced_map_rules_v0",
            "fingerprint": "6ab912d069ccb8224c9a9c387946aaf52d1b88b3a6e4924e68d9e280060fba5e",
        },
        {
            "component": "reward",
            "label": "structural_fixture",
            "version": "reduced_reward_rules_v4",
            "fingerprint": "c843a1711d22036f0d6b4db25c1b3977cf1d5038dba82ffbf628554f2b9fc327",
        },
        {
            "component": "room",
            "label": "structural_fixture",
            "version": "reduced_room_rules_v0",
            "fingerprint": "ed97167333934f3e98409d8c4e4cf9393f3b3fcc58ce21f23b54bc72859a94b4",
        },
        {
            "component": "snapshot",
            "label": "structural_fixture",
            "version": "reduced_headless_snapshot_v3",
            "fingerprint": "5f1880a3e22db87fbf8f7dc37c9987db9b48cdc142a760dd2e60a2cded48db4c",
        },
        {
            "component": "state",
            "label": "structural_fixture",
            "version": "reduced_world_state_v0",
            "fingerprint": "62f27941ece933f760244b5dbbcbbaf6bbc4a7a0f16bfcc428e936aa8bc8b4e3",
        },
    ),
}


def _config(**settings: Any) -> HeadlessRunConfig:
    return HeadlessRunConfig(
        scenario_id="simple__starter",
        content_fingerprint=CONTENT_FINGERPRINT,
        game_seed=41,
        backend_settings=settings,
    )


def _request(decision: DecisionState, candidate_id: str) -> ActionRequest:
    return ActionRequest(HeadlessBinding.for_candidate(decision, candidate_id))


def test_exact_accepted_contract_and_h3_fingerprints_are_consumed() -> None:
    assert CONTRACT_FINGERPRINT == _ACCEPTED_CONTRACT_FINGERPRINT
    assert BACKEND_FINGERPRINT == _ACCEPTED_BACKEND_FINGERPRINT
    assert RULES_FINGERPRINT == _ACCEPTED_RULES_FINGERPRINT
    assert SNAPSHOT_FINGERPRINT == _ACCEPTED_SNAPSHOT_FINGERPRINT

    manifest = ReducedRunBackend().manifest()
    assert manifest.contract_fingerprint == _ACCEPTED_CONTRACT_FINGERPRINT
    assert manifest.backend_fingerprint == _ACCEPTED_BACKEND_FINGERPRINT
    assert manifest.rules_fingerprint == _ACCEPTED_RULES_FINGERPRINT
    assert next(item for item in manifest.evidence if item.component == "snapshot").fingerprint == _ACCEPTED_SNAPSHOT_FINGERPRINT


def test_fixture_manifest_distinguishes_playback_from_counterfactual_execution() -> None:
    backend = FixtureBackend()
    manifest = backend.manifest()
    assert manifest.capabilities.deterministic_reset is True
    assert manifest.capabilities.fixture_playback is True
    assert manifest.capabilities.snapshot_restore is True
    assert manifest.capabilities.counterfactual_stepping is False
    assert manifest.capabilities.live_truth is False
    assert manifest.capabilities.legacy_shaped_reward_diagnostics is False
    assert {item.component: item.label for item in manifest.evidence} == {
        "fixture_corpus": EvidenceLabel.STRUCTURAL_FIXTURE,
        "fixture_playback": EvidenceLabel.STRUCTURAL_FIXTURE,
    }

    for fixture_id in ("combat", "reward", "map", "rest", "event"):
        decision = backend.reset(fixture_id)
        while decision.candidates:
            assert len(decision.candidates) == 1
            decision = backend.apply(
                _request(decision, decision.candidates[0].candidate_id)
            ).next_decision


def test_combat_manifest_claims_only_combat_v0_counterfactual_behavior() -> None:
    backend = CombatV0Backend()
    manifest = backend.manifest()
    assert manifest.backend_fingerprint == COMBAT_BACKEND_FINGERPRINT
    assert manifest.rules_fingerprint == COMBAT_RULES_FINGERPRINT
    assert manifest.supported_phases == (DecisionPhase.COMBAT,)
    assert manifest.unsupported_phases == (
        DecisionPhase.MAP,
        DecisionPhase.REWARD,
        DecisionPhase.ROOM,
    )
    assert manifest.capabilities.deterministic_reset is True
    assert manifest.capabilities.counterfactual_stepping is True
    assert manifest.capabilities.fixture_playback is False
    assert manifest.capabilities.snapshot_restore is True
    assert manifest.capabilities.live_truth is False
    assert manifest.capabilities.legacy_shaped_reward_diagnostics is True
    assert {item.component: item.label for item in manifest.evidence} == {
        "backend": EvidenceLabel.COMBAT_V0,
        "content": EvidenceLabel.STRUCTURAL_FIXTURE,
        "projection": EvidenceLabel.COMBAT_V0,
        "rules": EvidenceLabel.COMBAT_V0,
    }

    decision = backend.reset(
        scenario_from_id("simple__starter", seed=43, enemy_max_hp=20)
    )
    transition = backend.apply(_request(decision, decision.candidates[0].candidate_id))
    assert transition.result is TransitionResult.ACCEPTED
    diagnostics = backend.last_legacy_diagnostics
    assert diagnostics is not None
    assert diagnostics["evidence"] == EvidenceLabel.COMBAT_V0.value
    assert "legacy_shaped_reward" in diagnostics
    assert "shaped_reward" not in transition.next_decision.to_json()


def test_reduced_manifest_is_component_addressable_and_never_promotes_live_truth() -> None:
    manifest = ReducedRunBackend().manifest()
    assert manifest.supported_phases == (
        DecisionPhase.COMBAT,
        DecisionPhase.MAP,
        DecisionPhase.REWARD,
        DecisionPhase.ROOM,
    )
    assert manifest.unsupported_phases == ()
    assert manifest.capabilities.deterministic_reset is True
    assert manifest.capabilities.counterfactual_stepping is True
    assert manifest.capabilities.fixture_playback is False
    assert manifest.capabilities.snapshot_restore is True
    assert manifest.capabilities.live_truth is False
    assert manifest.capabilities.legacy_shaped_reward_diagnostics is False

    labels = {item.component: item.label for item in manifest.evidence}
    assert labels == {
        "combat_backend": EvidenceLabel.COMBAT_V0,
        "combat_projection": EvidenceLabel.COMBAT_V0,
        "combat_rules": EvidenceLabel.COMBAT_V0,
        "composer": EvidenceLabel.STRUCTURAL_FIXTURE,
        "content": EvidenceLabel.STRUCTURAL_FIXTURE,
        "map": EvidenceLabel.STRUCTURAL_FIXTURE,
        "reward": EvidenceLabel.STRUCTURAL_FIXTURE,
        "room": EvidenceLabel.STRUCTURAL_FIXTURE,
        "snapshot": EvidenceLabel.STRUCTURAL_FIXTURE,
        "state": EvidenceLabel.STRUCTURAL_FIXTURE,
    }
    assert tuple(labels) == tuple(sorted(labels))
    assert set(labels.values()) == {
        EvidenceLabel.COMBAT_V0,
        EvidenceLabel.STRUCTURAL_FIXTURE,
    }


@pytest.mark.parametrize("backend", (FixtureBackend(), CombatV0Backend(), ReducedRunBackend()))
def test_no_headless_manifest_contains_live_or_differential_evidence(backend: object) -> None:
    manifest = backend.manifest()  # type: ignore[attr-defined]
    assert BackendManifest.from_json(manifest.to_json()) == manifest
    assert tuple(item.to_dict() for item in manifest.evidence) == _ACCEPTED_EVIDENCE[
        manifest.backend_id
    ]
    assert manifest.capabilities.live_truth is False
    assert not {
        EvidenceLabel.LIVE_OBSERVED,
        EvidenceLabel.BRIDGE_FIXTURE,
        EvidenceLabel.DIFFERENTIAL_VERIFIED,
    } & {item.label for item in manifest.evidence}
    assert all("live" not in item.component for item in manifest.evidence)


@pytest.mark.parametrize(
    ("backend", "configuration", "snapshot_component"),
    (
        (FixtureBackend(), "combat", "fixture_playback"),
        (
            CombatV0Backend(),
            scenario_from_id("simple__starter", seed=47, enemy_max_hp=12),
            "backend",
        ),
        (ReducedRunBackend(), _config(combat_settings={"enemy_max_hp": 6}), "snapshot"),
    ),
    ids=("fixture", "combat_v0", "reduced"),
)
def test_each_snapshot_capability_has_bound_evidence_and_exact_restore(
    backend: object, configuration: object, snapshot_component: str
) -> None:
    manifest = backend.manifest()  # type: ignore[attr-defined]
    assert manifest.capabilities.snapshot_restore is True
    assert snapshot_component in {item.component for item in manifest.evidence}
    decision = backend.reset(configuration)  # type: ignore[attr-defined]
    snapshot = deepcopy(backend.snapshot())  # type: ignore[attr-defined]
    backend.apply(_request(decision, decision.candidates[0].candidate_id))  # type: ignore[attr-defined]
    assert backend.restore(snapshot) == decision  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("factory", "configuration"),
    (
        (
            CombatV0Backend,
            scenario_from_id("simple__starter", seed=53, enemy_max_hp=20),
        ),
        (ReducedRunBackend, _config(combat_settings={"enemy_max_hp": 20})),
    ),
    ids=("combat_v0", "reduced"),
)
def test_counterfactual_capability_produces_distinct_accepted_branches(
    factory: type[Any], configuration: object
) -> None:
    backend = factory()
    decision = backend.reset(configuration)
    snapshot = deepcopy(backend.snapshot())
    end_turn = next(
        item for item in decision.candidates if item.kind is CandidateKind.COMBAT_END_TURN
    )
    play = next(
        item for item in decision.candidates if item.kind is CandidateKind.COMBAT_PLAY_CARD
    )

    branches = []
    for candidate in (end_turn, play):
        fork = factory()
        restored = fork.restore(deepcopy(snapshot))
        matching = next(
            item for item in restored.candidates if item.candidate_id == candidate.candidate_id
        )
        transition = fork.apply(_request(restored, matching.candidate_id))
        assert transition.result is TransitionResult.ACCEPTED
        branches.append(transition.next_decision.to_json())
    assert branches[0] != branches[1]


def test_unsupported_configuration_and_features_fail_closed() -> None:
    combat = CombatV0Backend()
    with pytest.raises(ValueError, match="Configuration mapping"):
        combat.reset({"phase": "reward"})

    reduced = ReducedRunBackend()
    baseline = reduced.reset(_config(combat_settings={"enemy_max_hp": 6}))
    with pytest.raises(ReducedRunBackendError):
        reduced.reset(
            {
                **_config().to_dict(),
                "backend_settings": {"shop_support": True},
            }
        )
    assert reduced.observe() == baseline

    fixture = FixtureBackend()
    decision = fixture.reset("combat")
    before = fixture.snapshot()
    invalid = ActionRequest(
        HeadlessBinding(
            decision.run_id,
            decision.decision_sequence,
            decision.decision_hash,
            "cand." + "0" * 64,
        )
    )
    transition = fixture.apply(invalid)
    assert transition.result is TransitionResult.REJECTED
    assert transition.reason is TransitionReason.INVALID_CANDIDATE
    assert fixture.snapshot() == before
