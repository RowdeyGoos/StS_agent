"""Offline-only acceptance for H4-LIVE-DIFF-02. No live evidence promotion."""

from collections import Counter
from dataclasses import asdict, replace
import json

import pytest

from game.backends.live import r0i_wire as wire
from game.contracts.headless_v0 import ContractValidationError, PublicObservation

from common_public_subset import (
    Boundary, COMMON_SUBSET, OMISSIONS, compare_case, normalize_headless,
    normalize_wire, typed,
)
from fixture_identity import IDENTITY_PATH, ROOT, current_identities, verify_identities
from synthetic_cases import combat_body, fixture_bodies, make_cases, map_body, setup_backend


CASES = make_cases()
EXPECTED = {
    "combat_defend_common_vitals": "passed",
    "combat_defend_hp_divergence": "divergent",
    "combat_queued_without_post": "unobserved",
    "combat_to_reward_structural_gap": "divergent",
    "rest_reward.claim_gold": "divergent",
    "rest_reward.open_card_reward": "divergent",
    "rest_reward.choose_card": "divergent",
    "rest_reward_proceed_map_gap": "divergent",
    "rest_map_event_category_gap": "divergent",
    "rest_room_action": "passed",
    "rest_optional_proceed_gap": "divergent",
    "rest_proceed_to_combat_map": "passed",
    "map_monster_no_post_capture": "unobserved",
    "event_reward.claim_gold": "divergent",
    "event_reward.open_card_reward": "divergent",
    "event_reward.skip_card": "divergent",
    "event_reward_proceed_map_gap": "divergent",
    "event_map_event_category_gap": "divergent",
    "event_room_action": "divergent",
}


@pytest.fixture(scope="module", autouse=True)
def require_frozen_offline_inputs():
    # This gate also runs when a single named comparison test is selected.
    verify_identities(json.loads(IDENTITY_PATH.read_text()))


def compare(case):
    return compare_case(case.wire_pre, case.headless_pre, case.wire_post, case.headless_post)


def test_frozen_build_wire_rules_content_and_body_identities():
    verify_identities(json.loads(IDENTITY_PATH.read_text()))
    assert {b.family for c in CASES for b in (c.wire_pre, c.headless_pre)} == set(COMMON_SUBSET)
    assert {c.name: c.expected for c in CASES} == EXPECTED
    assert Counter(compare(c).outcome for c in CASES) == {"passed": 3, "divergent": 14, "unobserved": 2}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_named_synthetic_cases(case):
    result = compare(case)
    assert result.outcome == EXPECTED[case.name]
    assert result.evidence == "structural_fixture"
    assert result.live_capture == "unobserved"
    assert result.omissions
    assert all(x in result.omissions for x in OMISSIONS["all"])


def test_all_supported_action_kinds_are_compared():
    assert {c.headless_pre.selected_action[0] for c in CASES} == {
        "play_card", "end_turn", "claim_gold", "open_card_reward", "choose_card",
        "skip_card", "proceed", "choose_node", "rest_heal", "event_option",
    }
    assert any(c.headless_pre.family == "reward" and c.headless_pre.selected_action == ("proceed",) for c in CASES)
    assert any(c.headless_pre.family == "room" and c.headless_pre.selected_action == ("proceed",) for c in CASES)


def test_repeated_seeded_cases_and_diagnostics_are_deterministic():
    assert CASES == make_cases()
    assert [asdict(compare(c)) for c in CASES] == [asdict(compare(c)) for c in make_cases()]
    for body in fixture_bodies().values():
        assert wire.encode_decision(wire.parse_decision(body)) == body


def test_minimized_hp_divergence_reports_only_field_path():
    result = compare(next(c for c in CASES if c.name == "combat_defend_hp_divergence"))
    assert [(f.path, f.reason) for f in result.findings if f.outcome == "divergent"] == [
        ("post.player.hp", "typed_value_mismatch")
    ]
    assert all(set(asdict(f)) == {"path", "outcome", "reason"} for f in result.findings)


@pytest.mark.parametrize("left,right", [(1, True), (1, "1"), (None, 0), (None, "null"), ((), None), ((1,), (True,))])
def test_no_scalar_or_nested_type_coercion(left, right):
    case = CASES[0]
    a = replace(case.wire_pre, fields={**case.wire_pre.fields, "hand_count": left})
    b = replace(case.headless_pre, fields={**case.headless_pre.fields, "hand_count": right})
    result = compare_case(a, b, case.wire_post, case.headless_post)
    assert next(f for f in result.findings if f.path == "pre.hand_count").outcome == "divergent"
    assert typed(left) != typed(right)


@pytest.mark.parametrize("value", [None, 0, False, "", ()])
def test_absent_field_is_unobserved_not_a_null_zero_false_or_empty_default(value):
    case = CASES[0]
    missing = replace(case.wire_pre, fields={k: v for k, v in case.wire_pre.fields.items() if k != "hand_count"})
    present = replace(case.headless_pre, fields={**case.headless_pre.fields, "hand_count": value})
    result = compare_case(missing, present, case.wire_post, case.headless_post)
    assert result.outcome == "unobserved"
    assert next(f for f in result.findings if f.path == "pre.hand_count").reason == "field_absent"
    assert compare_case(missing, missing, case.wire_post, case.headless_post).outcome == "unobserved"


def test_candidate_bag_keeps_multiplicity_and_discards_order():
    dto = combat_body()
    shuffled = replace(dto, fields={**dto.fields, "legal_actions": tuple(reversed(dto.fields["legal_actions"]))})
    assert normalize_wire(dto, "play:0") == normalize_wire(shuffled, "play:0")
    assert normalize_wire(dto).fields["candidate_bag"].count(("play_card", False)) == 3
    case = CASES[0]
    smaller = replace(case.wire_pre, fields={**case.wire_pre.fields, "candidate_bag": (("play_card", False), ("play_card", True), ("end_turn",))})
    assert compare_case(smaller, case.headless_pre, case.wire_post, case.headless_post).outcome == "divergent"
    assert any("multiple advertised" in s for s in compare(case).omissions)


def test_selected_action_must_be_advertised_and_category_mismatch_is_visible():
    with pytest.raises(ValueError, match="not advertised"):
        normalize_wire(combat_body(), "play:9")
    backend = setup_backend()
    try:
        with pytest.raises(ValueError, match="not advertised"):
            normalize_headless(backend.observe().policy_view(), "not-advertised")
    finally:
        backend.close()
    case = CASES[0]
    other_action = normalize_wire(combat_body(), "end_turn")
    result = compare_case(other_action, case.headless_pre, case.wire_post, case.headless_post)
    assert next(f for f in result.findings if f.path == "action").outcome == "divergent"


def test_duplicate_wire_actions_reject_before_bagging():
    dto = combat_body()
    dto = replace(dto, fields={**dto.fields, "legal_actions": (*dto.fields["legal_actions"], dto.fields["legal_actions"][0])})
    with pytest.raises(ValueError, match="duplicate"):
        normalize_wire(dto)


def test_control_identity_is_neither_compared_nor_invented():
    dto = combat_body()
    other = replace(dto, binding=wire.BridgeBinding(wire.PROTOCOL, "f" * 64))
    assert normalize_wire(dto, "play:0") == normalize_wire(other, "play:0")
    backend = setup_backend()
    try:
        decision = backend.observe()
        with pytest.raises(TypeError, match="PolicyView"):
            normalize_headless(decision)
        a = normalize_headless(decision.policy_view())
        backend.reset({"scenario_id": "simple__starter", "content_fingerprint": current_identities()["headless"]["content_fingerprint"],
                       "game_seed": 7, "backend_settings": {"initial_hp": 60, "combat_settings": {"enemy_max_hp": 1}}})
        assert a == normalize_headless(backend.observe().policy_view())
        normalized = repr(a)
        for private in (decision.run_id, decision.decision_hash, decision.candidates[0].candidate_id):
            assert private not in normalized
    finally:
        backend.close()
    for boundary in (normalize_wire(dto), normalize_wire(map_body())):
        assert not {"run_id", "decision_id", "sequence", "decision_hash", "snapshot"} & set(boundary.fields)


@pytest.mark.parametrize("key", ["authorization_token", "rng_state", "future_offers", "profile_path", "run_id"])
def test_private_unknown_fields_reject_on_both_input_boundaries(key):
    dto = combat_body()
    with pytest.raises(wire.R0iWireError):
        normalize_wire(replace(dto, fields={**dto.fields, key: "synthetic-private-canary"}))
    backend = setup_backend()
    try:
        observation = backend.observe().observation
        with pytest.raises(ContractValidationError):
            PublicObservation(observation.phase, {**observation.data, key: "synthetic-private-canary"}, observation.public_scope)
    finally:
        backend.close()


def test_audit_and_control_dtos_are_not_public_boundaries():
    dto = combat_body()
    control = wire.ControlAction(dto.binding, "play:0", "synthetic-control-canary")
    vector = ROOT / "bridge/Sts2AgentBridge/contracts/live_probe_v0/vectors/combat_receipt_accepted.json"
    receipt = wire.parse_receipt(vector.read_bytes(), family="combat")
    assert receipt.mutation_state == "queued"
    for item in (control, receipt):
        with pytest.raises(wire.R0iWireError):
            normalize_wire(item)
        with pytest.raises(TypeError):
            normalize_headless(item)
    result = compare(next(c for c in CASES if c.name == "combat_queued_without_post"))
    assert result.outcome == "unobserved"


def test_room_heal_pass_does_not_claim_hp_effect_or_map_identity():
    case = next(c for c in CASES if c.name == "rest_room_action")
    assert set(case.wire_pre.fields) == {"status", "room_kind", "candidate_bag"}
    assert set(case.headless_pre.fields) == set(case.wire_pre.fields)
    assert any("heal/effect amounts" in s for s in compare(case).omissions)
    assert "player.hp" not in case.wire_post.fields
    assert set(normalize_wire(map_body()).fields) == {"status", "destination_kinds", "candidate_bag"}


def test_inactive_and_endpoint_complete_are_not_synthesized_headless_boundaries():
    vectors = ROOT / "bridge/Sts2AgentBridge/contracts/live_probe_v0/vectors"
    for family in COMMON_SUBSET:
        for status in ("waiting", "unsupported", "complete"):
            boundary = normalize_wire(wire.parse_decision((vectors / f"{family}_decision_{status}.json").read_bytes()))
            assert boundary.fields == {"status": status}
            assert boundary.selected_action is None
            assert compare_case(boundary, boundary, None, None).outcome == "unobserved"
    case = CASES[0]
    different = Boundary("terminal", {"status": "terminal"}, None, 0)
    assert compare_case(case.wire_pre, case.headless_pre, case.wire_post, different).outcome == "divergent"


@pytest.mark.parametrize("section,key", [
    ("build", "identity_sha256"), ("bridge", "source_inventory_sha256"),
    ("wire", "vector_inventory_sha256"),
    ("wire", "bridge_version"), ("wire", "schema_version"),
    ("headless", "contract_fingerprint"), ("headless", "rules_fingerprint"),
    ("headless", "content_fingerprint"), ("headless", "backend_fingerprint"),
])
def test_identity_drift_fails_closed(section, key):
    expected = json.loads(IDENTITY_PATH.read_text())
    expected[section][key] = True if key == "schema_version" else "changed"
    with pytest.raises(ValueError, match="identity mismatch"):
        verify_identities(expected)


def test_fixture_and_report_labels_cannot_be_promoted_by_success():
    identities = current_identities()
    assert {e["label"] for e in identities["headless"]["component_evidence"]} == {"structural_fixture", "combat_v0"}
    for case in CASES:
        report = json.dumps(asdict(compare(case)))
        assert "differential_verified" not in report
        assert "live_observed" not in report
    for label in ("differential_verified", "live_observed"):
        expected = json.loads(IDENTITY_PATH.read_text())
        expected["evidence"] = label
        with pytest.raises(ValueError, match="identity mismatch"):
            verify_identities(expected)
