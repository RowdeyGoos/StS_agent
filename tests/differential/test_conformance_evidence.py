"""Offline contract/admission fixtures only; no real capture or transport."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from game.analysis import conformance_evidence as evidence
from game.content.reduced_v0 import CONTENT_FINGERPRINT, REWARD_TABLES
from game.contracts.headless_v0 import (
    ActionRequest, ContractValidationError, DecisionPhase, HeadlessBinding,
    PublicReferenceKind, PublicScope,
)
from game.engine.headless_state import NodeKind, WorldState
from game.engine.reward_rules import REWARD_RULES_FINGERPRINT, RewardRuleError, RewardRules


PINS = evidence.pins_for_harness("a" * 64)  # Explicit synthetic harness identity.


def digest(value):
    return sha256(evidence.canonical_json(value).encode("ascii")).hexdigest()


def boundary(role="pre", amount=25):
    post = role == "post"
    return {
        "role": role, "ordinal": int(post), "family": "reward",
        "status": "ready", "screen": "rewards",
        "player": {"hp": 60, "max_hp": 80, "gold": amount if post else 0, "deck_count": 10},
        "rewards": [{"category": "gold", "claimed": post, "amount": amount, "offer_count": 0}],
        "candidate_categories": ["proceed"] if post else ["claim_gold", "proceed"],
    }


def case(amount=25):
    pre = boundary(amount=amount)
    return {
        "schema": evidence.SCHEMA, "case_id": evidence.CASE_ID, "pins": dict(PINS),
        "source": {"origin": "synthetic", "capture_ordinal": 0},
        "boundaries": {"pre": pre, "post": boundary("post", amount)},
        "selection": {"category": "claim_gold", "amount": amount},
        "alignment": evidence.alignment_for(pre, amount), "correspondence": "bound_one_claim",
        "findings": [{"field": field, "outcome": "passed", "code": "equal"} for field in evidence.FIELD_NAMES],
        "broader_comparison": "not_evaluated", "omissions": list(evidence.OMISSIONS),
        "admission": "not_admitted",
    }


def unobserved(value):
    for finding in value["findings"]:
        finding.update(outcome="unobserved", code="not_compared")
    return value


def parse(value, **kwargs):
    return evidence.parse_record(evidence.canonical_json(value), expected_pins=PINS, **kwargs)


def source_review(value):
    # A test-local stand-in for a separately reviewed external manifest. Never
    # provide this self-derived helper in production corpus/admission code.
    return evidence.SourceReview(value["source"]["origin"], digest(value), digest(PINS),
                                 "b" * 64 if value["source"]["origin"] == "retained_live" else None)


def test_case_spec_and_identity_inventory_are_frozen():
    spec = json.loads(Path(__file__).with_name("reward_gold_case_spec.json").read_text())
    assert spec == evidence.GOLD_CASE_SPEC
    assert digest(spec) == evidence.CASE_SPEC_SHA256 == "41ced248e52ca27e42d6318d63568f271edd605be3365afffd92c5e78a896a28"
    assert evidence.SCHEMA_SHA256 == "b797e69c160179795d3ed3cab9c66b0aabc4e4bd535af36c5a9d72349c428380"
    assert {table.gold_amount: table.table_id for table in REWARD_TABLES} == {
        int(k): v for k, v in spec["table_by_amount"].items()
    }
    from fixture_identity import current_identities
    ids = current_identities()
    assert PINS["build_identity_sha256"] == ids["build"]["identity_sha256"]
    assert PINS["build_manifest_sha256"] == ids["build"]["manifest_sha256"]
    assert PINS["bridge_source_sha256"] == ids["bridge"]["source_inventory_sha256"]
    assert PINS["parser_source_sha256"] == ids["source_sha256"]["game/backends/live/r0i_wire.py"]
    assert PINS["wire_vectors_sha256"] == ids["wire"]["vector_inventory_sha256"]
    assert PINS["headless_contract_sha256"] == ids["headless"]["contract_fingerprint"]
    assert PINS["rules_sha256"] == ids["headless"]["reward_rules_fingerprint"]
    assert PINS["rules_source_sha256"] == ids["source_sha256"]["game/engine/reward_rules.py"]
    assert PINS["content_sha256"] == ids["headless"]["content_fingerprint"]


@pytest.mark.parametrize("amount", [25, 35])
def test_roundtrip_never_promotes_synthetic_findings(amount):
    value = case(amount)
    record = parse(value)
    assert record.to_dict() == value
    assert record.sha256 == digest(value)
    assert parse(record.to_dict()) == record
    detached = record.to_dict()
    detached["source"]["origin"] = "live"
    assert record.to_dict()["source"]["origin"] == "synthetic"
    assert record.to_dict()["admission"] == "not_admitted"


@pytest.mark.parametrize("path", [
    (), ("pins",), ("source",), ("boundaries",), ("boundaries", "pre"),
    ("boundaries", "pre", "player"), ("boundaries", "pre", "rewards", 0),
    ("selection",), ("alignment",), ("findings", 0),
])
def test_closed_fields_and_secret_safe_errors(path):
    value = case()
    target = value
    for key in path:
        target = target[key]
    target["secret_canary"] = "credential_and_raw_payload_canary"
    with pytest.raises(evidence.EvidenceError) as error:
        parse(value)
    assert "canary" not in str(error.value)


@pytest.mark.parametrize("fragment", ['"schema":"named_conformance_v1"', '"hp":60', '"claimed":false'])
def test_duplicate_json_fields_reject_at_every_depth(fragment):
    body = evidence.canonical_json(case()).replace(fragment, fragment + "," + fragment, 1)
    with pytest.raises(evidence.EvidenceError, match="duplicate_field"):
        evidence.parse_record(body, expected_pins=PINS)


@pytest.mark.parametrize("path", [
    ("source", "capture_ordinal"), ("boundaries", "pre", "ordinal"),
    ("boundaries", "pre", "player", "hp"), ("boundaries", "pre", "player", "gold"),
    ("boundaries", "pre", "player", "deck_count"),
    ("boundaries", "pre", "rewards", 0, "amount"),
    ("boundaries", "pre", "rewards", 0, "offer_count"), ("selection", "amount"),
])
def test_bool_is_not_integer(path):
    value = case()
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = True
    with pytest.raises(evidence.EvidenceError, match="invalid_integer"):
        parse(value)


@pytest.mark.parametrize("key", list(PINS))
def test_changed_pins_cannot_be_blessed_from_the_record(key):
    value = case()
    value["pins"][key] = "f" * 64
    with pytest.raises(evidence.EvidenceError):
        parse(value)
    if key != "harness_sha256":
        with pytest.raises(evidence.EvidenceError):
            evidence.parse_record(evidence.canonical_json(value), expected_pins=value["pins"])


def test_missing_swapped_and_stale_boundaries():
    value = case()
    del value["boundaries"]["post"]
    with pytest.raises(evidence.EvidenceError, match="missing_boundary"):
        parse(value)
    value = case()
    value["boundaries"]["pre"], value["boundaries"]["post"] = value["boundaries"]["post"], value["boundaries"]["pre"]
    with pytest.raises(evidence.EvidenceError, match="swapped_boundary"):
        parse(value)
    value = case()
    value["boundaries"]["post"]["ordinal"] = 0
    with pytest.raises(evidence.EvidenceError, match="swapped_boundary"):
        parse(value)
    value = case()
    value["boundaries"]["post"] = None
    with pytest.raises(evidence.EvidenceError, match="missing_stable_post"):
        parse(value)
    value["correspondence"] = "post_not_observed"
    assert parse(unobserved(value)).to_dict()["alignment"]["status"] == "eligible"


def test_absence_is_explicit_and_never_a_pass():
    value = unobserved(case())
    value["boundaries"] = {"pre": None, "post": None}
    value["selection"]["amount"] = None
    value["alignment"] = evidence.alignment_for(None, None)
    value["correspondence"] = "not_checked"
    assert parse(value).to_dict()["alignment"]["status"] == "unobserved"


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p["rewards"].append(deepcopy(p["rewards"][0])), "ambiguous_or_absent_gold"),
    (lambda p: p["candidate_categories"].insert(0, "claim_gold"), "ambiguous_or_absent_gold"),
    (lambda p: p["rewards"][0].update(claimed=True), "ambiguous_or_absent_gold"),
    (lambda p: p.update(screen="card_reward"), "unsupported_pre_boundary"),
    (lambda p: p["player"].update(deck_count=129), "unrepresentable_prestate"),
    (lambda p: p["player"].update(max_hp=100001), "unrepresentable_prestate"),
    (lambda p: p["player"].update(gold=999999976), "unrepresentable_prestate"),
])
def test_unsupported_alignment_cannot_be_claimed(mutation, code):
    value = case()
    mutation(value["boundaries"]["pre"])
    expected = evidence.alignment_for(value["boundaries"]["pre"], 25)
    assert expected == {"status": "unaligned", "code": code}
    with pytest.raises(evidence.EvidenceError, match="unsupported_alignment"):
        parse(value)
    value["alignment"] = expected
    with pytest.raises(evidence.EvidenceError, match="ineligible_field_claim"):
        parse(value)
    parse(unobserved(value))


@pytest.mark.parametrize("amount", [0, 24, 26, 34, 36, 100])
def test_closed_amount_set(amount):
    value = case(amount)
    assert value["alignment"]["code"] == "unsupported_gold_amount"
    parse(unobserved(value))


@pytest.mark.parametrize("origin", ["live", "transient_live", "retained_live"])
def test_live_strings_and_hashes_do_not_create_provenance(origin):
    value = case()
    value["source"]["origin"] = origin
    with pytest.raises(evidence.EvidenceError):
        parse(value)
    with pytest.raises(evidence.EvidenceError):
        evidence.NamedConformanceRecord(evidence.canonical_json(value))
    with pytest.raises(evidence.EvidenceError):
        parse(value, source_review=digest(value))


def test_external_source_review_binds_exact_origin_case_and_pins():
    value = case()
    value["source"]["origin"] = "retained_live"
    review = source_review(value)
    assert parse(value, source_review=review).to_dict()["admission"] == "not_admitted"
    for changed in (replace(review, record_sha256="c" * 64),
                    replace(review, pins_sha256="c" * 64),
                    evidence.SourceReview("transient_live", review.record_sha256, review.pins_sha256, None)):
        with pytest.raises(evidence.EvidenceError, match="source_review_mismatch"):
            parse(value, source_review=changed)
    with pytest.raises(evidence.EvidenceError, match="synthetic_source_substitution"):
        parse(case(), source_review=review)
    with pytest.raises(evidence.EvidenceError, match="invalid_identity"):
        replace(review, capture_manifest_sha256=None)


def test_separate_independent_retained_admission_and_no_backend_changes():
    value = case()
    value["source"]["origin"] = "retained_live"
    source = source_review(value)
    record = parse(value, source_review=source)
    review = evidence.AdmissionReview(source, record.sha256, "d" * 64)
    admitted = evidence.admit_record(record, expected_pins=PINS, review=review)
    assert admitted["scope"] == "conditional_gold_transfer_only"
    assert admitted["capture_manifest_sha256"] == "b" * 64
    assert admitted["admission"] == "differential_verified"
    assert record.to_dict()["admission"] == "not_admitted"
    with pytest.raises(evidence.EvidenceError, match="independent_admission_review_required"):
        evidence.admit_record(record, expected_pins=PINS, review=source)
    with pytest.raises(evidence.EvidenceError, match="admission_review_mismatch"):
        evidence.admit_record(record, expected_pins=PINS, review=replace(review, reviewed_record_sha256="e" * 64))
    value["source"]["origin"] = "transient_live"
    transient = source_review(value)
    parse(value, source_review=transient)
    with pytest.raises(evidence.EvidenceError, match="retained_review_required"):
        evidence.AdmissionReview(transient, digest(value), "d" * 64)


@pytest.mark.parametrize("mode", ["divergent", "unobserved", "unaligned", "uncertain"])
def test_independent_source_review_alone_cannot_admit_nonpassing_case(mode):
    value = case()
    value["source"]["origin"] = "retained_live"
    if mode in ("divergent", "unobserved"):
        value["findings"][0].update(outcome=mode, code="different" if mode == "divergent" else "not_compared")
    elif mode == "unaligned":
        value["selection"]["amount"] = 35
        value["alignment"] = evidence.alignment_for(value["boundaries"]["pre"], 35)
        unobserved(value)
    else:
        value["correspondence"] = "uncertain"
        unobserved(value)
    source = source_review(value)
    record = parse(value, source_review=source)
    with pytest.raises(evidence.EvidenceError, match="case_not_admissible"):
        evidence.admit_record(record, expected_pins=PINS,
                              review=evidence.AdmissionReview(source, record.sha256, "d" * 64))


def test_self_promotion_duplicate_findings_and_omission_changes_reject():
    for key, replacement in (("admission", "differential_verified"),
                             ("findings", [case()["findings"][0]] * 5),
                             ("omissions", [])):
        value = case()
        value[key] = replacement
        with pytest.raises(evidence.EvidenceError):
            parse(value)


@pytest.mark.parametrize("code", ["receipt_binding_mismatch", "receipt_rejected", "stale_post",
                                 "intervening_action", "uncertain", "cancelled"])
def test_unproven_correspondence_cannot_pass_fields(code):
    value = case()
    value["correspondence"] = code
    with pytest.raises(evidence.EvidenceError, match="ineligible_field_claim"):
        parse(value)
    parse(unobserved(value))


def test_prestate_alignment_never_consumes_poststate_or_scaffold_overrides():
    value = case()
    expected = deepcopy(value["alignment"])
    value["boundaries"]["post"]["player"].update(hp=1, gold=800, deck_count=45)
    unobserved(value)
    assert parse(value).to_dict()["alignment"] == expected
    value["scaffold"] = {"gold": 800}
    with pytest.raises(evidence.EvidenceError, match="invalid_record_fields"):
        parse(value)


def test_reward_normalization_is_a_multiset_not_a_control_identity_channel():
    value = case()
    rewards = value["boundaries"]["pre"]["rewards"]
    rewards.append({"category": "card", "claimed": False, "amount": None, "offer_count": 3})
    rewards.sort(key=evidence.canonical_json)
    value["boundaries"]["pre"]["candidate_categories"] = ["claim_gold", "open_card", "proceed"]
    parse(value)
    rewards.reverse()
    with pytest.raises(evidence.EvidenceError, match="noncanonical_reward_multiset"):
        parse(value)
    rewards.sort(key=evidence.canonical_json)
    rewards[0]["reward_index"] = 1
    with pytest.raises(evidence.EvidenceError, match="invalid_reward_fields"):
        parse(value)


@pytest.mark.parametrize("amount,deck_count,max_hp,gold,eligible", [
    (25, 1, 80, 0, True), (35, 128, 100000, 999999965, True),
    (25, 129, 80, 0, False), (25, 1, 100001, 0, False),
    (25, 1, 80, 999999976, False),
])
def test_scaffold_eligibility_against_actual_production_rules(amount, deck_count, max_hp, gold, eligible):
    pre = boundary(amount=amount)
    pre["player"].update(deck_count=deck_count, max_hp=max_hp, gold=gold)
    assert (evidence.alignment_for(pre, amount)["status"] == "eligible") is eligible
    world = WorldState.create(
        seed=0, current_hp=pre["player"]["hp"], max_hp=max_hp, gold=gold,
        deck_definition_ids=("strike",) * deck_count,
        map_node_definitions=(("floor_01_combat", NodeKind.COMBAT),),
        content_fingerprint=CONTENT_FINGERPRINT, rules_fingerprint=REWARD_RULES_FINGERPRINT,
        phase=DecisionPhase.REWARD,
    )
    rules = RewardRules()
    scope = PublicScope(0, 0, {kind.value: 0 for kind in PublicReferenceKind})
    def begin():
        return rules.begin(world, reward_table_id=evidence.GOLD_CASE_SPEC["table_by_amount"][str(amount)],
                           decision_sequence=0, public_scope=scope)
    if not eligible:
        with pytest.raises((RewardRuleError, ContractValidationError)):
            begin()
        return
    decision = begin()
    selected = next(c for c in decision.candidates if c.kind.value == "reward.claim_gold")
    transition = rules.apply(world, ActionRequest(HeadlessBinding.for_candidate(decision, selected.candidate_id)))
    assert transition.next_decision.observation.data["player"]["gold"] == gold + amount
    assert len(world.master_deck) == deck_count


@pytest.mark.parametrize("bad", [0, -1, True, 1.0])
def test_invalid_deck_scalars_reject(bad):
    value = case()
    value["boundaries"]["pre"]["player"]["deck_count"] = bad
    with pytest.raises(evidence.EvidenceError):
        parse(value)


def test_byte_limit_and_non_json_values():
    for body in (" " * (evidence.MAX_RECORD_BYTES + 1), '{"schema":NaN}', '{"schema":Infinity}', "not json", b"\xff"):
        with pytest.raises(evidence.EvidenceError):
            evidence.parse_record(body, expected_pins=PINS)
