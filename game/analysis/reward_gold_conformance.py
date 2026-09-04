"""Offline conditional gold-transfer comparison against actual RewardRules.

Wire DTOs and control bindings are transient inputs. Returned dictionaries are
sanitized *proposals*, not reviewed evidence: use conformance_evidence.parse_record
with caller-anchored pins and an external SourceReview for any live origin.
This module never creates reviews, captures data, writes files, or admits fidelity.
The synthetic scaffold is not a reconstruction of the observed world.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game.analysis import conformance_evidence as evidence
from game.backends.live import r0i_wire as wire
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import (
    ActionRequest, DecisionPhase, HeadlessBinding, PublicReferenceKind,
    PublicScope, RewardClaimGoldCandidate, TransitionResult,
)
from game.engine.headless_state import NodeKind, WorldState
from game.engine.reward_rules import REWARD_RULES_FINGERPRINT, RewardRules


@dataclass(frozen=True)
class ClaimWindow:
    """Adapter assertion about one observation window, kept only in memory.

    The adapter must bind these to the actual observed snapshots and establish
    order, stability, one accepted claim, and absence of intervening actions.
    Repeated equal GETs alone do not establish this. Defaults cannot pass.
    This is a trusted collection seam, not proof derived from scalar values.
    """

    pre_binding: wire.BridgeBinding | None = field(default=None, repr=False)
    post_binding: wire.BridgeBinding | None = field(default=None, repr=False)
    accepted_claim_count: int = 0
    post_after_receipt: bool = False
    stable_post: bool = False
    no_intervening_action: bool = False
    uncertain: bool = True
    cancelled: bool = False

    def __post_init__(self) -> None:
        if (type(self.accepted_claim_count) is not int
                or not 0 <= self.accepted_claim_count <= 1):
            raise evidence.EvidenceError("invalid_claim_window")
        for flag in (self.post_after_receipt, self.stable_post,
                     self.no_intervening_action, self.uncertain, self.cancelled):
            if type(flag) is not bool:
                raise evidence.EvidenceError("invalid_claim_window")
        for binding in (self.pre_binding, self.post_binding):
            if binding is not None and type(binding) is not wire.BridgeBinding:
                raise evidence.EvidenceError("invalid_claim_window")


@dataclass(frozen=True)
class GoldTransfer:
    """Only the five preregistered outputs of a local production transition."""

    selected_gold_amount: int
    gold_delta: int
    hp_preserved: bool
    max_hp_preserved: bool
    deck_count_preserved: bool


def _run_claim(world: WorldState, *, table_id: str, sequence: int,
               scope: PublicScope) -> GoldTransfer:
    rules = RewardRules()
    before = (world.gold, world.current_hp, world.max_hp, len(world.master_deck))
    decision = rules.begin(world, reward_table_id=table_id,
                           decision_sequence=sequence, public_scope=scope)
    candidates = [c for c in decision.candidates if type(c) is RewardClaimGoldCandidate]
    if len(candidates) != 1:
        raise evidence.EvidenceError("production_gold_not_unique")
    selected = candidates[0]
    transition = rules.apply(world, ActionRequest(
        HeadlessBinding.for_candidate(decision, selected.candidate_id)))
    if transition.result is not TransitionResult.ACCEPTED:
        raise evidence.EvidenceError("production_claim_not_accepted")
    player = transition.next_decision.observation.data["player"]
    return GoldTransfer(selected.amount, player["gold"] - before[0],
                        player["hp"] == before[1], player["max_hp"] == before[2],
                        player["deck_size"] == before[3])


def production_gold_projection(pre: dict, selected_amount: int) -> GoldTransfer:
    """Run the fixed scaffold from eligible sanitized PRE state only.

    No post-state, world override, seed, card identity, or control identity is
    accepted. Ineligible inputs raise a fixed diagnostic; evaluate_reward_gold
    reports their alignment without invoking this helper.
    """
    if evidence.alignment_for(pre, selected_amount)["status"] != "eligible":
        raise evidence.EvidenceError("ineligible_production_prestate")
    if (CONTENT_FINGERPRINT != evidence.FROZEN_PINS["content_sha256"]
            or REWARD_RULES_FINGERPRINT != evidence.FROZEN_PINS["rules_sha256"]):
        raise evidence.EvidenceError("changed_rule_contract")
    spec = evidence.GOLD_CASE_SPEC
    scaffold = spec["scaffold"]
    player = pre["player"]
    world = WorldState.create(
        seed=scaffold["rng_seed"], current_hp=player["hp"],
        max_hp=player["max_hp"], gold=player["gold"],
        deck_definition_ids=(scaffold["deck_definition"],) * player["deck_count"],
        map_node_definitions=tuple((name, NodeKind(kind)) for name, kind in scaffold["map_nodes"]),
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_fingerprint=REWARD_RULES_FINGERPRINT, phase=DecisionPhase.REWARD,
    )
    scope = PublicScope(scaffold["history_ordinal"], scaffold["decision_ordinal"],
                        {kind.value: 0 for kind in PublicReferenceKind})
    return _run_claim(world, table_id=spec["table_by_amount"][str(selected_amount)],
                      sequence=scaffold["decision_sequence"], scope=scope)


def _checked_decision(decision: wire.RewardDecision | None) -> wire.RewardDecision | None:
    if decision is None:
        return None
    if type(decision) is not wire.RewardDecision or decision.family != "reward":
        raise evidence.EvidenceError("invalid_reward_decision")
    try:
        # DTO construction alone does not validate the closed wire shape.
        return wire.parse_decision(wire.encode_decision(decision))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise evidence.EvidenceError("invalid_reward_decision") from None


def _boundary(decision: wire.RewardDecision | None, role: str, ordinal: int) -> dict | None:
    if decision is None:
        return None
    data = decision.fields
    return {
        "role": role, "ordinal": ordinal, "family": "reward",
        "status": decision.status, "screen": data["screen_kind"],
        "player": None if data["player"] is None else {
            key: data["player"][key] for key in ("hp", "max_hp", "gold", "deck_count")},
        "rewards": sorted([{
            "category": r["kind"], "claimed": r["successfully_selected"],
            "amount": r["gold_amount"], "offer_count": len(r["cards"]),
        } for r in data["rewards"]], key=evidence.canonical_json),
        "candidate_categories": sorted(a["kind"] for a in data["legal_actions"]),
    }


def _selected_amount(pre: wire.RewardDecision | None, action_id: str | None) -> int | None:
    if action_id is not None and type(action_id) is not str:
        raise evidence.EvidenceError("invalid_selection")
    if pre is not None:
        selected = [a for a in pre.fields["legal_actions"] if a["action_id"] == action_id]
        if len(selected) == 1 and selected[0]["kind"] == "claim_gold":
            return pre.fields["rewards"][selected[0]["reward_slot"]]["gold_amount"]
    return None


def reward_gold_eligibility(pre: wire.RewardDecision | None,
                            selected_action_id: str | None) -> dict:
    """Pre-POST alignment check for an explicitly selected advertised action.

    Only selection scalars and fixed alignment codes are returned. This grants
    no authority to act and makes no assertion about a future post-state.
    """
    pre = _checked_decision(pre)
    amount = _selected_amount(pre, selected_action_id)
    return {"selection": {"category": "claim_gold", "amount": amount},
            "alignment": evidence.alignment_for(_boundary(pre, "pre", 0), amount)}


def _correspondence(pre: wire.RewardDecision | None, post: wire.RewardDecision | None,
                    action_id: str | None, receipt: wire.ActionReceipt | None,
                    window: ClaimWindow) -> str:
    if window.cancelled:
        return "cancelled"
    if pre is None:
        return "not_checked"
    if receipt is None:
        return "uncertain"
    if type(receipt) is not wire.ActionReceipt or receipt.family != "reward":
        raise evidence.EvidenceError("invalid_reward_receipt")
    try:
        wire.parse_receipt(wire.encode_receipt(receipt), family="reward")
    except (ValueError, TypeError, KeyError, AttributeError):
        raise evidence.EvidenceError("invalid_reward_receipt") from None
    if receipt.binding != pre.binding or receipt.action_id != action_id:
        return "receipt_binding_mismatch"
    if receipt.status != "accepted":
        return "receipt_rejected"
    if post is None or post.status != "ready" or post.fields["screen_kind"] != "rewards":
        return "post_not_observed"
    if (post.binding == pre.binding
            or post.fields["decision_revision"] <= pre.fields["decision_revision"]):
        return "stale_post"
    if post.fields["decision_revision"] != pre.fields["decision_revision"] + 1:
        return "intervening_action"
    if not window.no_intervening_action:
        return "intervening_action"
    if (window.uncertain or window.accepted_claim_count != 1
            or not window.post_after_receipt or not window.stable_post
            or window.pre_binding != pre.binding or window.post_binding != post.binding):
        return "uncertain"
    return "bound_one_claim"


def evaluate_reward_gold(*, pre: wire.RewardDecision | None,
                         selected_action_id: str | None,
                         receipt: wire.ActionReceipt | None,
                         post: wire.RewardDecision | None,
                         harness_sha256: str,
                         window: ClaimWindow | None = None,
                         capture_ordinal: int = 0,
                         origin: str = "synthetic",
                         broader_comparison: str = "not_evaluated") -> dict[str, Any]:
    """Return an unreviewed named_conformance_v1 proposal with fixed findings.

    Selection must name the uniquely advertised, unclaimed pre-state gold.
    Alignment/setup never use post-state. Wire IDs/revisions, receipt bindings,
    cards and the ClaimWindow never enter the result. Broader findings remain
    with their existing caller-owned report; pass its fixed aggregate here when
    available, otherwise leave the explicit not_evaluated default.

    origin declares a proposed source, not an authenticated one. A live proposal
    must pass parse_record with an independently supplied SourceReview before
    use as evidence. No self-derived review or automatic admission occurs here.
    """
    if type(capture_ordinal) is not int or not 0 <= capture_ordinal <= (2**63 - 2) // 2:
        raise evidence.EvidenceError("invalid_capture_ordinal")
    if type(origin) is not str or origin not in ("synthetic", "transient_live", "retained_live"):
        raise evidence.EvidenceError("invalid_origin")
    if type(broader_comparison) is not str or broader_comparison not in (
            "not_evaluated", "passed", "divergent", "unobserved"):
        raise evidence.EvidenceError("invalid_broader_comparison")
    if selected_action_id is not None and type(selected_action_id) is not str:
        raise evidence.EvidenceError("invalid_selection")
    if window is None:
        window = ClaimWindow()
    if type(window) is not ClaimWindow:
        raise evidence.EvidenceError("invalid_claim_window")
    pre = _checked_decision(pre)
    before = _boundary(pre, "pre", 2 * capture_ordinal)
    amount = _selected_amount(pre, selected_action_id)
    alignment = evidence.alignment_for(before, amount)
    # Compute the production side before even checking correspondence or reading
    # the post player. The helper's signature makes post-conditioned setup impossible.
    expected = production_gold_projection(before, amount) if alignment["status"] == "eligible" else None
    post = _checked_decision(post)
    if pre is None and post is not None:
        raise evidence.EvidenceError("post_without_pre")
    after = _boundary(post, "post", 2 * capture_ordinal + 1)
    correspondence = _correspondence(pre, post, selected_action_id, receipt, window)
    equalities = None
    if expected is not None and correspondence == "bound_one_claim":
        left, right = before["player"], after["player"]
        equalities = (
            expected.selected_gold_amount == amount,
            expected.gold_delta == right["gold"] - left["gold"],
            expected.hp_preserved and right["hp"] == left["hp"],
            expected.max_hp_preserved and right["max_hp"] == left["max_hp"],
            expected.deck_count_preserved and right["deck_count"] == left["deck_count"],
        )
    findings = []
    for index, name in enumerate(evidence.FIELD_NAMES):
        outcome = "unobserved" if equalities is None else "passed" if equalities[index] else "divergent"
        findings.append({"field": name, "outcome": outcome,
                         "code": {"unobserved": "not_compared", "passed": "equal", "divergent": "different"}[outcome]})
    result = {
        "schema": evidence.SCHEMA, "case_id": evidence.CASE_ID,
        "pins": evidence.pins_for_harness(harness_sha256),
        "source": {"origin": "synthetic", "capture_ordinal": capture_ordinal},
        "boundaries": {"pre": before, "post": after},
        "selection": {"category": "claim_gold", "amount": amount},
        "alignment": alignment, "correspondence": correspondence, "findings": findings,
        "broader_comparison": broader_comparison, "omissions": list(evidence.OMISSIONS),
        "admission": "not_admitted",
    }
    # Check shape/semantics without fabricating provenance assertions. Only the
    # proposal returned below has the requested origin; it still needs review.
    evidence.parse_record(evidence.canonical_json(result), expected_pins=result["pins"])
    result["source"]["origin"] = origin
    return result
