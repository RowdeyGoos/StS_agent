"""Independently specified synthetic gold cases; no live transport or captures."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from game.analysis import conformance_evidence as evidence
from game.analysis import reward_gold_conformance as gold
from game.backends.live import r0i_wire as wire
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import DecisionPhase, PublicReferenceKind, PublicScope
from game.engine.headless_state import NodeKind, WorldState
from game.engine.reward_rules import REWARD_RULES_FINGERPRINT, RewardRules


HARNESS = "9" * 64  # Synthetic test identity, never a reviewed live harness.
PRE_ID, POST_ID = "1" * 64, "2" * 64


def decision(*, post=False, amount=25, gold_value=None, hp=47, max_hp=83,
             deck_count=7, revision=None, identity=None, rewards=None, actions=None):
    # Expected outcomes are explicit literals, never generated with RewardRules.
    if gold_value is None:
        gold_value = ({25: 44, 35: 54}.get(amount, 63) if post else 19)
    if rewards is None:
        rewards = [{"reward_slot": 0, "reward_index": 3, "kind": "gold",
                    "successfully_selected": post, "gold_amount": amount,
                    "cards": [], "card_selection_can_skip": False}]
    if actions is None:
        actions = ([] if post else [{"action_id": "claim:0", "kind": "claim_gold",
                                    "reward_slot": 0, "card_slot": None}])
        actions += [{"action_id": "proceed", "kind": "proceed", "reward_slot": None, "card_slot": None}]
    dto = wire.RewardDecision("reward", "ready", True,
                             wire.BridgeBinding(wire.PROTOCOL, identity or (POST_ID if post else PRE_ID)), {
        "decision_revision": revision if revision is not None else (8 if post else 7),
        "screen_kind": "rewards",
        "player": {"hp": hp, "max_hp": max_hp, "gold": gold_value, "deck_count": deck_count},
        "rewards": rewards, "legal_actions": actions,
    })
    return wire.parse_decision(wire.encode_decision(dto))


def receipt(pre=None, **changes):
    pre = pre or decision()
    return replace(wire.ActionReceipt("reward", pre.binding, "claim:0", "accepted", "applied", "accepted"), **changes)


def window(pre, post, **changes):
    return replace(gold.ClaimWindow(pre.binding, post.binding, 1, True, True, True, False, False), **changes)


def evaluate(pre=None, post=None, **kwargs):
    pre = pre or decision()
    post = post or decision(post=True)
    args = dict(pre=pre, selected_action_id="claim:0", post=post, receipt=receipt(pre),
                window=window(pre, post), harness_sha256=HARNESS)
    args.update(kwargs)
    return gold.evaluate_reward_gold(**args)


def outcomes(result):
    return {f["field"]: f["outcome"] for f in result["findings"]}


def assert_uncompared(result, correspondence):
    assert result["correspondence"] == correspondence
    assert set(outcomes(result).values()) == {"unobserved"}
    evidence.parse_record(evidence.canonical_json(result), expected_pins=evidence.pins_for_harness(HARNESS))


@pytest.mark.parametrize("amount,post_gold", [(25, 44), (35, 54)])
def test_independent_positive_cases_run_production(amount, post_gold, monkeypatch):
    calls = []
    actual_apply = RewardRules.apply

    def traced_apply(self, world, request):
        calls.append((world.current_hp, world.max_hp, world.gold, len(world.master_deck)))
        return actual_apply(self, world, request)

    monkeypatch.setattr(RewardRules, "apply", traced_apply)
    result = evaluate(decision(amount=amount), decision(post=True, amount=amount, gold_value=post_gold))
    assert calls == [(47, 83, 19, 7)]
    assert result["alignment"] == {"status": "eligible", "code": "eligible_prestate"}
    assert result["correspondence"] == "bound_one_claim"
    assert set(outcomes(result).values()) == {"passed"}
    assert result["broader_comparison"] == "not_evaluated"
    assert result["source"]["origin"] == "synthetic"
    assert result["admission"] == "not_admitted"


@pytest.mark.parametrize("change,field", [
    ({"gold_value": 43}, "gold_delta"), ({"gold_value": 19}, "gold_delta"),
    ({"hp": 46}, "hp_preserved"), ({"max_hp": 84}, "max_hp_preserved"),
    ({"deck_count": 8}, "deck_count_preserved"),
])
def test_independent_negative_post_cases(change, field):
    result = evaluate(post=decision(post=True, **change))
    assert outcomes(result) == {name: "divergent" if name == field else "passed" for name in evidence.FIELD_NAMES}


@pytest.mark.parametrize("amount", [0, 24, 26, 34, 36, 100])
def test_unsupported_amount_never_constructs_rules(amount, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unaligned pre-state constructed a production scenario")
    monkeypatch.setattr(gold, "production_gold_projection", forbidden)
    pre = decision(amount=amount)
    result = evaluate(pre, decision(post=True, amount=amount))
    assert result["alignment"]["code"] == "unsupported_gold_amount"
    assert set(outcomes(result).values()) == {"unobserved"}
    assert gold.reward_gold_eligibility(pre, "claim:0")["alignment"] == result["alignment"]


def test_ambiguous_unclaimed_gold_even_with_explicit_selected_action():
    pre = decision()
    rewards = [dict(r) for r in pre.fields["rewards"]]
    rewards.append({**rewards[0], "reward_slot": 1, "reward_index": 4, "gold_amount": 35})
    actions = [dict(a) for a in pre.fields["legal_actions"]]
    actions.insert(1, {"action_id": "claim:1", "kind": "claim_gold", "reward_slot": 1, "card_slot": None})
    result = evaluate(decision(rewards=rewards, actions=actions))
    assert result["alignment"]["code"] == "ambiguous_or_absent_gold"
    assert set(outcomes(result).values()) == {"unobserved"}


@pytest.mark.parametrize("action_id", [None, "proceed", "claim:1", "SECRET_INVALID_ACTION"])
def test_unadvertised_or_non_gold_selection_is_unaligned(action_id):
    result = evaluate(selected_action_id=action_id)
    assert result["alignment"]["code"] == "selection_not_aligned"
    assert set(outcomes(result).values()) == {"unobserved"}
    assert "SECRET" not in evidence.canonical_json(result)


@pytest.mark.parametrize("changes", [{"max_hp": 100001}, {"deck_count": 129}, {"gold_value": 999999976}])
def test_unrepresentable_public_prestate_is_unaligned(changes):
    result = evaluate(decision(**changes))
    assert result["alignment"]["code"] == "unrepresentable_prestate"
    assert set(outcomes(result).values()) == {"unobserved"}


@pytest.mark.parametrize("changes", [
    {"binding": wire.BridgeBinding(wire.PROTOCOL, "3" * 64)}, {"action_id": "proceed"},
])
def test_wrong_receipt_binding(changes):
    assert_uncompared(evaluate(receipt=receipt(**changes)), "receipt_binding_mismatch")


def test_receipt_rejection_and_missing_receipt():
    assert_uncompared(evaluate(receipt=receipt(status="rejected", mutation_state="none", reason="stale_decision")), "receipt_rejected")
    assert_uncompared(evaluate(receipt=None), "uncertain")


def test_absent_post_and_pre():
    args = dict(pre=decision(), selected_action_id="claim:0", receipt=receipt(), post=None, harness_sha256=HARNESS)
    assert_uncompared(gold.evaluate_reward_gold(**args), "post_not_observed")
    result = gold.evaluate_reward_gold(**{**args, "pre": None, "receipt": None})
    assert result["alignment"]["status"] == "unobserved"
    assert_uncompared(result, "not_checked")
    with pytest.raises(evidence.EvidenceError, match="post_without_pre"):
        gold.evaluate_reward_gold(**{**args, "pre": None, "post": decision(post=True)})


@pytest.mark.parametrize("status", ["waiting", "unsupported", "complete"])
def test_inactive_post_is_not_a_bound_reward_post(status):
    post = wire.RewardDecision("reward", status, False, None, {
        "screen_kind": "map" if status == "complete" else "unknown",
        "player": dict(decision(post=True).fields["player"]) if status == "complete" else None,
        "rewards": [], "legal_actions": [],
    })
    assert_uncompared(evaluate(post=post), "post_not_observed")


@pytest.mark.parametrize("post,code", [
    (decision(post=True, revision=7), "stale_post"),
    (decision(post=True, revision=6), "stale_post"),
    (decision(post=True, identity=PRE_ID), "stale_post"),
    (decision(post=True, revision=9), "intervening_action"),
])
def test_stale_or_skipped_revision(post, code):
    assert_uncompared(evaluate(post=post), code)


@pytest.mark.parametrize("changes,code", [
    ({"stable_post": False}, "uncertain"), ({"post_after_receipt": False}, "uncertain"),
    ({"accepted_claim_count": 0}, "uncertain"), ({"uncertain": True}, "uncertain"),
    ({"no_intervening_action": False}, "intervening_action"), ({"cancelled": True}, "cancelled"),
    ({"pre_binding": None}, "uncertain"), ({"post_binding": None}, "uncertain"),
])
def test_temporal_assertions_fail_closed(changes, code):
    assert_uncompared(evaluate(window=window(decision(), decision(post=True), **changes)), code)


def test_repeated_equal_post_does_not_supply_temporal_proof():
    assert_uncompared(evaluate(window=None), "intervening_action")


def test_swapped_boundaries_cannot_pass():
    pre, post = decision(), decision(post=True)
    result = evaluate(post, pre, receipt=receipt(pre), window=window(pre, post))
    assert_uncompared(result, "receipt_binding_mismatch")
    assert result["alignment"]["status"] == "unaligned"
    sanitized_post = evaluate()["boundaries"]["post"]
    with pytest.raises(evidence.EvidenceError, match="swapped_boundary"):
        gold.production_gold_projection(sanitized_post, 25)


def test_pre_only_setup_and_frozen_scaffold(monkeypatch):
    calls = []
    create = WorldState.create

    def tracked_create(**kwargs):
        world = create(**kwargs)
        calls.append((deepcopy(kwargs), world.to_private_dict()))
        return world

    monkeypatch.setattr(WorldState, "create", tracked_create)
    first = evaluate()
    second = evaluate(post=decision(post=True, hp=9, max_hp=100, deck_count=2, gold_value=700))
    assert calls[0] == calls[1]
    kwargs = calls[0][0]
    assert kwargs["seed"] == 0 and kwargs["deck_definition_ids"] == ("strike",) * 7
    assert kwargs["map_node_definitions"] == (("floor_01_combat", NodeKind.COMBAT),)
    assert first["alignment"] == second["alignment"]
    assert outcomes(second)["gold_delta"] == "divergent"
    assert list(inspect.signature(gold.production_gold_projection).parameters) == ["pre", "selected_amount"]
    with pytest.raises(TypeError):
        gold.production_gold_projection(first["boundaries"]["pre"], 25, post=second["boundaries"]["post"])


@pytest.mark.parametrize("amount", [25, 35])
@pytest.mark.parametrize("seed,deck,node_defs,sequence,ordinal", [
    (0, ("strike",) * 7, (("floor_01_combat", NodeKind.COMBAT),), 0, 0),
    (91, ("defend",) * 7, (("synthetic_rest", NodeKind.REST),), 12, 21),
    (4096, ("bash", "strike", "defend", "bash", "defend", "strike", "bash"),
     (("synthetic_a", NodeKind.COMBAT), ("synthetic_b", NodeKind.REST)), 32, 45),
])
def test_transfer_independent_of_synthetic_scaffold(amount, seed, deck, node_defs, sequence, ordinal):
    world = WorldState.create(seed=seed, current_hp=47, max_hp=83, gold=19,
                             deck_definition_ids=deck, map_node_definitions=node_defs,
                             content_fingerprint=CONTENT_FINGERPRINT,
                             rules_fingerprint=REWARD_RULES_FINGERPRINT, phase=DecisionPhase.REWARD)
    scope = PublicScope(ordinal, ordinal, {kind.value: ordinal for kind in PublicReferenceKind})
    local = gold._run_claim(world, table_id={25: "combat_reward_basic", 35: "combat_reward_sequence"}[amount],
                            sequence=sequence, scope=scope)
    assert local == gold.GoldTransfer(amount, amount, True, True, True)
    normalized = evaluate(decision(amount=amount), decision(post=True, amount=amount))["boundaries"]["pre"]
    assert local == gold.production_gold_projection(normalized, amount)


def test_rule_output_is_compared_not_a_copied_addition(monkeypatch):
    real_apply = RewardRules.apply

    def altered_transition(self, world, request):
        transition = real_apply(self, world, request)
        # Mutate the returned public projection only, as a test-local fault.
        observation = transition.next_decision.observation
        data = dict(observation.data)
        data["player"] = {**data["player"], "gold": 42}
        return SimpleNamespace(result=transition.result, next_decision=SimpleNamespace(
            observation=SimpleNamespace(data=data)))

    monkeypatch.setattr(RewardRules, "apply", altered_transition)
    assert outcomes(evaluate())["gold_delta"] == "divergent"


def test_broader_divergence_survives_a_narrow_match():
    result = evaluate(broader_comparison="divergent")
    assert set(outcomes(result).values()) == {"passed"}
    assert result["broader_comparison"] == "divergent"
    assert result["omissions"] == list(evidence.OMISSIONS)


def test_live_proposal_requires_external_review_and_contains_no_control_data():
    result = evaluate(origin="transient_live", capture_ordinal=3)
    body = evidence.canonical_json(result)
    assert result["boundaries"]["pre"]["ordinal"] == 6
    assert result["boundaries"]["post"]["ordinal"] == 7
    for secret in (PRE_ID, POST_ID, "claim:0", "decision_revision", "reward_index", "authorization"):
        assert secret not in body
    with pytest.raises(evidence.EvidenceError, match="unreviewed_live_origin"):
        evidence.parse_record(body, expected_pins=evidence.pins_for_harness(HARNESS))
    assert result["admission"] == "not_admitted"


def test_card_identity_and_other_reward_shapes_do_not_condition_setup():
    card = {"reward_slot": 1, "reward_index": 8, "kind": "card",
            "successfully_selected": False, "gold_amount": None,
            "cards": ["SECRET_CARD_IDENTITY"], "card_selection_can_skip": True}
    open_card = {"action_id": "open:1", "kind": "open_card", "reward_slot": 1, "card_slot": None}
    states = []
    for is_post in (False, True):
        base = decision(post=is_post)
        states.append(decision(post=is_post, rewards=[dict(base.fields["rewards"][0]), card],
                               actions=[dict(a) for a in base.fields["legal_actions"][:-1]]
                               + [open_card, dict(base.fields["legal_actions"][-1])]))
    result = evaluate(*states)
    assert set(outcomes(result).values()) == {"passed"}
    assert "SECRET" not in evidence.canonical_json(result)
    assert result["broader_comparison"] == "not_evaluated"


@pytest.mark.parametrize("amount,before,after", [(25, 0, 25), (35, 999999965, 1000000000)])
def test_representable_scalar_edges(amount, before, after):
    result = evaluate(decision(amount=amount, gold_value=before, hp=1, max_hp=100000, deck_count=128),
                      decision(post=True, amount=amount, gold_value=after, hp=1, max_hp=100000, deck_count=128))
    assert set(outcomes(result).values()) == {"passed"}


def test_frozen_spec_and_production_import_boundary():
    assert evidence.CASE_SPEC_SHA256 == "41ced248e52ca27e42d6318d63568f271edd605be3365afffd92c5e78a896a28"
    assert evidence.SCHEMA_SHA256 == "b797e69c160179795d3ed3cab9c66b0aabc4e4bd535af36c5a9d72349c428380"
    assert sha256(evidence.canonical_json(evidence.GOLD_CASE_SPEC).encode("ascii")).hexdigest() == evidence.CASE_SPEC_SHA256
    source = Path(gold.__file__).read_text()
    assert "from tests" not in source and "import tests" not in source


@pytest.mark.parametrize("kwargs", [{"accepted_claim_count": True}, {"accepted_claim_count": 2},
                                    {"stable_post": 1}, {"pre_binding": "SECRET"}])
def test_invalid_window_values(kwargs):
    with pytest.raises(evidence.EvidenceError, match="invalid_claim_window"):
        gold.ClaimWindow(**kwargs)


def test_invalid_dto_and_receipt_fail_with_fixed_diagnostics():
    pre = decision()
    malformed = replace(pre, fields={**pre.fields, "secret": "SECRET"})
    with pytest.raises(evidence.EvidenceError, match="^invalid_reward_decision$"):
        evaluate(pre=malformed)
    with pytest.raises(evidence.EvidenceError, match="^invalid_reward_receipt$"):
        evaluate(receipt=receipt(mutation_state="queued"))
