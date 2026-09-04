"""Closed, privacy-bounded consumer contract for one conditional reward check.

This module neither captures data nor runs rules. Hashes check consistency, not
authenticity. SourceReview and AdmissionReview are trusted coordinator inputs:
never construct them from a case/corpus being loaded. Their binding checks cannot
authenticate a dishonest caller. No record changes backend evidence labels.
"""

from __future__ import annotations

from dataclasses import dataclass, InitVar
from hashlib import sha256
import json
import re
from typing import Any, Mapping


SCHEMA = "named_conformance_v1"
CASE_ID = "reward_gold_claim_v1"
MAX_RECORD_BYTES = 65_536
FIELD_NAMES = ("selected_gold_amount", "gold_delta", "hp_preserved",
               "max_hp_preserved", "deck_count_preserved")
CANDIDATE_CATEGORIES = ("claim_gold", "open_card", "choose_card", "skip_card", "proceed")
OMISSIONS = (
    "world_state_correspondence", "reward_generation_distribution",
    "card_definition_and_instance_identity", "map_identity_and_history",
    "rng_and_seed_correspondence", "control_and_receipt_identifiers",
    "timing_and_intervening_action_proof_from_scalars", "backend_fidelity_promotion",
    "raw_bodies_and_raw_body_hashes", "arbitrary_text_and_credentials",
    "profile_save_and_live_seed_data",
)
SCALAR_ALLOWLIST = (
    "family", "status", "screen", "player.hp", "player.max_hp", "player.gold",
    "player.deck_count", "selection.category", "selection.amount",
    "rewards.category", "rewards.claimed", "rewards.amount", "rewards.offer_count",
    "candidate_categories", "capture_ordinal", "boundary.role", "boundary.ordinal",
    "fixed_validation_codes", "reviewed_identity_pins",
)
GOLD_CASE_SPEC = {
    "schema": SCHEMA,
    "case_id": CASE_ID,
    "claim": "conditional_gold_transfer_only",
    "allowed_gold_amounts": [25, 35],
    "table_by_amount": {"25": "combat_reward_basic", "35": "combat_reward_sequence"},
    "copied_pre_fields": ["hp", "max_hp", "gold", "deck_count"],
    "headless_scalar_bounds": {
        "hp_min": 1, "hp_max": "max_hp", "max_hp_max": 100000,
        "gold_min": 0, "gold_plus_selected_amount_max": 1000000000,
        "deck_count_min": 1, "deck_count_max": 128,
    },
    "preconditions": ["ready_rewards_screen", "unique_advertised_unclaimed_gold",
                      "closed_amount_set", "headless_scalar_bounds",
                      "fresh_bound_post_after_one_accepted_claim"],
    "scaffold": {
        "classification": "synthetic_not_live_reconstruction",
        "deck_definition": "strike", "deck_upgraded": False,
        "map_nodes": [["floor_01_combat", "combat"]],
        "rng_seed": 0, "decision_sequence": 0, "history_ordinal": 0,
        "decision_ordinal": 0, "reveal_ordinals": "all_zero",
        "control_identity": "locally_derived_only",
        "reward_session": "fresh_unopened",
    },
    "alignment_inputs": "pre_state_and_selected_pre_amount_only",
    "post_state_setup": "forbidden",
    "scaffold_independence_checks": ["deck_definitions", "map_nodes", "rng_seed", "local_control_scope"],
    "compared_fields": list(FIELD_NAMES),
    "scalar_allowlist": list(SCALAR_ALLOWLIST),
    "omissions": list(OMISSIONS),
    "retention_authority": "none",
}


class EvidenceError(ValueError):
    """Fixed diagnostics only; never echo supplied text or payload values."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


CASE_SPEC_SHA256 = sha256(canonical_json(GOLD_CASE_SPEC).encode("ascii")).hexdigest()
SCHEMA_SHA256 = sha256(canonical_json({
    "schema": SCHEMA, "case_spec_sha256": CASE_SPEC_SHA256,
    "sections": ["schema", "case_id", "pins", "source", "boundaries", "selection",
                 "alignment", "correspondence", "findings", "broader_comparison",
                 "omissions", "admission"],
    "source": ["origin", "capture_ordinal"],
    "origins": ["synthetic", "transient_live", "retained_live"],
    "source_review": "out_of_band_record_and_pins_binding",
    "admission_review": "separate_retained_capture_and_effect_review",
    "missing_boundary": "explicit_null_never_absent_key",
    "boundary_ordinals": "two_times_capture_ordinal_then_plus_one",
    "json": "closed_duplicate_rejecting_type_exact_v1",
}).encode("ascii")).hexdigest()
# Reviewed repository identities at cc2060c. These are declarations, not an
# automatic inventory refresh and not evidence that an installed binary matches.
FROZEN_PINS = {
    "build_identity_sha256": "a0f7f8f57621122e4c246372115783909f4bb97f4b4eb7e57340428143d4c4cf",
    "build_manifest_sha256": "ea9046a6a66e2388be3fb1db4e287e0982ae1b3772bec28546a40ef48c23b470",
    "bridge_source_sha256": "a0ca37bb2d0ad36fcb68eafe5163ac8174074b0e6f861c69c2ac357873f75f2a",
    "parser_source_sha256": "3733748ed4cd1a328c519c2aebed0e646cad35792d1cd18b28fd7c21e4e58fb8",
    "wire_vectors_sha256": "8dfc1e1e2571e66ea5a9652b1c45a80500209dc1b26b4a6bbfe87a44eb1ea1fe",
    "headless_contract_sha256": "e5ab4c29f0c077178d543b36e24494d3ec8d0d62528f44becf6f13eae7dee1b3",
    "rules_sha256": "c843a1711d22036f0d6b4db25c1b3977cf1d5038dba82ffbf628554f2b9fc327",
    "rules_source_sha256": "2896d098e0a6e4273094766b8b85b657bb539ef9317582cf7c46e0b3bb09f727",
    "content_sha256": "fe771ea0f82c114d1d6a6389a44b169525c047914d955ce49d6db54e2472230f",
    "case_spec_sha256": CASE_SPEC_SHA256,
    "schema_sha256": SCHEMA_SHA256,
}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EvidenceError(code)


def _keys(value: Any, keys: tuple | set, code: str) -> None:
    _require(type(value) is dict and set(value) == set(keys), code)


def _enum(value: Any, values: tuple, code: str) -> None:
    _require(type(value) is str and value in values, code)


def _integer(value: Any, minimum: int = 0, maximum: int = 2**63 - 1) -> None:
    _require(type(value) is int and minimum <= value <= maximum, "invalid_integer")


def _digest(value: Any) -> None:
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             "invalid_identity")


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_field")
        result[key] = value
    return result


def _load(body: str | bytes) -> dict:
    _require(type(body) in (str, bytes), "invalid_json")
    try:
        raw = body.encode("ascii") if type(body) is str else body
        _require(len(raw) <= MAX_RECORD_BYTES, "record_too_large")
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: _require(False, "invalid_json"))
    except EvidenceError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise EvidenceError("invalid_json") from None
    _require(type(value) is dict, "invalid_record")
    return value


def pins_for_harness(harness_sha256: str) -> dict:
    """Bind a separately reviewed harness identity; does not review that harness."""
    _digest(harness_sha256)
    return {**FROZEN_PINS, "harness_sha256": harness_sha256, "schema": SCHEMA}


def _pins(pins: Any) -> None:
    _keys(pins, {*FROZEN_PINS, "harness_sha256", "schema"}, "invalid_pins")
    for key, expected in FROZEN_PINS.items():
        _require(type(pins[key]) is str and pins[key] == expected, "changed_pin")
    _enum(pins["schema"], (SCHEMA,), "changed_schema")
    _digest(pins["harness_sha256"])


def _boundary(value: Any, role: str, ordinal: int) -> None:
    _keys(value, ("role", "ordinal", "family", "status", "screen", "player",
                  "rewards", "candidate_categories"), "invalid_boundary_fields")
    _enum(value["role"], (role,), "swapped_boundary")
    _integer(value["ordinal"])
    _require(value["ordinal"] == ordinal, "swapped_boundary")
    _enum(value["family"], ("reward",), "invalid_family")
    _enum(value["status"], ("ready", "waiting", "unsupported", "complete"), "invalid_status")
    _enum(value["screen"], ("rewards", "card_reward", "unknown", "map"), "invalid_screen")
    player = value["player"]
    if value["status"] in ("ready", "complete"):
        _keys(player, ("hp", "max_hp", "gold", "deck_count"), "invalid_player_fields")
        for name in player:
            _integer(player[name], 0 if name == "gold" else 1)
        _require(player["hp"] <= player["max_hp"], "invalid_player")
        _require(value["screen"] in (("rewards", "card_reward") if value["status"] == "ready" else ("map",)), "invalid_screen")
    else:
        _require(player is None and value["screen"] == "unknown", "invalid_inactive_boundary")
    rewards = value["rewards"]
    _require(type(rewards) is list and len(rewards) <= 8, "invalid_rewards")
    for reward in rewards:
        _keys(reward, ("category", "claimed", "amount", "offer_count"), "invalid_reward_fields")
        _enum(reward["category"], ("gold", "card", "unsupported"), "invalid_reward_category")
        _require(type(reward["claimed"]) is bool, "invalid_claimed_flag")
        _integer(reward["offer_count"], maximum=5)
        if reward["category"] == "gold":
            _integer(reward["amount"])
            _require(reward["offer_count"] == 0, "invalid_gold_reward")
        else:
            _require(reward["amount"] is None, "invalid_reward_amount")
            _require(reward["offer_count"] >= 1 if reward["category"] == "card"
                     else reward["offer_count"] == 0, "invalid_reward_offer_count")
    _require(rewards == sorted(rewards, key=canonical_json), "noncanonical_reward_multiset")
    candidates = value["candidate_categories"]
    _require(type(candidates) is list and len(candidates) <= 16, "invalid_candidates")
    for category in candidates:
        _enum(category, CANDIDATE_CATEGORIES, "invalid_candidate_category")
    _require(candidates == sorted(candidates), "noncanonical_candidate_multiset")
    if value["status"] != "ready":
        _require(not rewards and not candidates, "invalid_inactive_boundary")


def alignment_for(pre: dict | None, selected_amount: int | None) -> dict:
    """Pre-state eligibility only. Does not certify a receipt or post-state."""
    if pre is None:
        return {"status": "unobserved", "code": "pre_not_observed"}
    _require(type(pre) is dict and "ordinal" in pre, "invalid_boundary_fields")
    _boundary(pre, "pre", pre["ordinal"])
    if selected_amount is not None:
        _integer(selected_amount)
    code = "eligible_prestate"
    if pre["status"] != "ready" or pre["screen"] != "rewards":
        code = "unsupported_pre_boundary"
    else:
        gold = [r for r in pre["rewards"] if r["category"] == "gold" and not r["claimed"]]
        if len(gold) != 1 or pre["candidate_categories"].count("claim_gold") != 1:
            code = "ambiguous_or_absent_gold"
        elif selected_amount is None or selected_amount != gold[0]["amount"]:
            code = "selection_not_aligned"
        elif selected_amount not in (25, 35):
            code = "unsupported_gold_amount"
        else:
            p = pre["player"]
            if p["max_hp"] > 100_000 or p["gold"] + selected_amount > 1_000_000_000 or p["deck_count"] > 128:
                code = "unrepresentable_prestate"
    return {"status": "eligible" if code == "eligible_prestate" else "unaligned", "code": code}


_CORRESPONDENCE = ("not_checked", "bound_one_claim", "receipt_rejected",
                   "receipt_binding_mismatch", "post_not_observed", "stale_post",
                   "intervening_action", "uncertain", "cancelled")


def _validate(value: dict) -> None:
    _keys(value, ("schema", "case_id", "pins", "source", "boundaries", "selection",
                  "alignment", "correspondence", "findings", "broader_comparison",
                  "omissions", "admission"), "invalid_record_fields")
    _enum(value["schema"], (SCHEMA,), "invalid_schema")
    _enum(value["case_id"], (CASE_ID,), "invalid_case")
    _pins(value["pins"])
    source = value["source"]
    _keys(source, ("origin", "capture_ordinal"), "invalid_source_fields")
    _enum(source["origin"], ("synthetic", "transient_live", "retained_live"), "invalid_origin")
    _integer(source["capture_ordinal"])
    _keys(value["boundaries"], ("pre", "post"), "missing_boundary")
    pre, post = (value["boundaries"][key] for key in ("pre", "post"))
    for role, boundary, delta in (("pre", pre, 0), ("post", post, 1)):
        if boundary is not None:
            _boundary(boundary, role, source["capture_ordinal"] * 2 + delta)
    _require(pre is not None or post is None, "post_without_pre")
    _keys(value["selection"], ("category", "amount"), "invalid_selection_fields")
    _enum(value["selection"]["category"], ("claim_gold",), "invalid_selection")
    amount = value["selection"]["amount"]
    if amount is not None:
        _integer(amount)
    _keys(value["alignment"], ("status", "code"), "invalid_alignment_fields")
    _require(value["alignment"] == alignment_for(pre, amount), "unsupported_alignment")
    _enum(value["correspondence"], _CORRESPONDENCE, "invalid_correspondence")
    if value["correspondence"] == "bound_one_claim":
        _require(pre is not None and post is not None and post["status"] == "ready"
                 and post["screen"] == "rewards", "missing_stable_post")
    findings = value["findings"]
    _require(type(findings) is list and len(findings) == len(FIELD_NAMES), "invalid_findings")
    comparable = value["alignment"]["status"] == "eligible" and value["correspondence"] == "bound_one_claim"
    for field, finding in zip(FIELD_NAMES, findings):
        _keys(finding, ("field", "outcome", "code"), "invalid_finding_fields")
        _enum(finding["field"], (field,), "duplicate_or_unknown_finding")
        _enum(finding["outcome"], ("passed", "divergent", "unobserved"), "invalid_finding_outcome")
        expected_code = {"passed": "equal", "divergent": "different", "unobserved": "not_compared"}[finding["outcome"]]
        _enum(finding["code"], (expected_code,), "invalid_finding_code")
        _require(comparable or finding["outcome"] == "unobserved", "ineligible_field_claim")
    _enum(value["broader_comparison"], ("not_evaluated", "passed", "divergent", "unobserved"), "invalid_broader_comparison")
    _require(value["omissions"] == list(OMISSIONS), "changed_omissions")
    _enum(value["admission"], ("not_admitted",), "self_promoted_evidence")


@dataclass(frozen=True)
class NamedConformanceRecord:
    """Immutable canonical data, never an authenticity or admission token."""

    document_json: str
    source_review: InitVar[SourceReview | None] = None

    def __post_init__(self, source_review: SourceReview | None) -> None:
        value = _load(self.document_json)
        _validate(value)
        object.__setattr__(self, "document_json", canonical_json(value))
        _check_source(value, self.sha256, source_review)

    def to_dict(self) -> dict:
        return _load(self.document_json)

    @property
    def sha256(self) -> str:
        """Digest of sanitized record only; never hash full wire bodies here."""
        return sha256(self.document_json.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class SourceReview:
    """Out-of-band coordinator assertion; not loadable from untrusted JSON.

    Retained origin requires a separately reviewed capture manifest identity.
    Transient review attests only observation; it can never admit fidelity.
    """

    origin: str
    record_sha256: str
    pins_sha256: str
    capture_manifest_sha256: str | None

    def __post_init__(self) -> None:
        _enum(self.origin, ("transient_live", "retained_live"), "invalid_review_origin")
        _digest(self.record_sha256)
        _digest(self.pins_sha256)
        if self.origin == "retained_live":
            _digest(self.capture_manifest_sha256)
        else:
            _require(self.capture_manifest_sha256 is None, "unexpected_capture_manifest")


def _check_source(value: dict, record_sha256: str, source_review: SourceReview | None) -> None:
    source = value["source"]
    if source["origin"] == "synthetic":
        _require(source_review is None, "synthetic_source_substitution")
    else:
        _require(type(source_review) is SourceReview, "unreviewed_live_origin")
        _require(source_review.origin == source["origin"]
                 and source_review.record_sha256 == record_sha256
                 and source_review.pins_sha256 == sha256(canonical_json(value["pins"]).encode("ascii")).hexdigest(),
                 "source_review_mismatch")


def parse_record(body: str | bytes, *, expected_pins: Mapping[str, Any],
                 source_review: SourceReview | None = None) -> NamedConformanceRecord:
    """Validate a case against caller-anchored pins and independent provenance."""
    record = NamedConformanceRecord(body, source_review)
    _require(isinstance(expected_pins, Mapping), "invalid_pins")
    expected = dict(expected_pins)
    _pins(expected)
    _require(record.to_dict()["pins"] == expected, "changed_pin")
    return record


@dataclass(frozen=True)
class AdmissionReview:
    """Independent review of actual replay/effect findings, not just origin."""

    source: SourceReview
    reviewed_record_sha256: str
    review_manifest_sha256: str

    def __post_init__(self) -> None:
        _require(type(self.source) is SourceReview and self.source.origin == "retained_live", "retained_review_required")
        _digest(self.reviewed_record_sha256)
        _digest(self.review_manifest_sha256)


def admit_record(record: NamedConformanceRecord, *, expected_pins: Mapping[str, Any],
                 review: AdmissionReview) -> dict:
    """Return a separate named admission; never edit the evidence or capabilities.

    This is a coordinator-only trust seam, not a review engine or permission to
    collect/retain data. Callers must supply independently reviewed identities.
    """
    _require(type(review) is AdmissionReview, "independent_admission_review_required")
    validated = parse_record(record.document_json, expected_pins=expected_pins, source_review=review.source)
    value = validated.to_dict()
    _require(review.reviewed_record_sha256 == validated.sha256, "admission_review_mismatch")
    _require(value["alignment"]["status"] == "eligible"
             and value["correspondence"] == "bound_one_claim"
             and all(f["outcome"] == "passed" for f in value["findings"]), "case_not_admissible")
    return {"schema": SCHEMA, "case_id": CASE_ID, "record_sha256": validated.sha256,
            "capture_manifest_sha256": review.source.capture_manifest_sha256,
            "review_manifest_sha256": review.review_manifest_sha256,
            "admission": "differential_verified", "scope": "conditional_gold_transfer_only"}
