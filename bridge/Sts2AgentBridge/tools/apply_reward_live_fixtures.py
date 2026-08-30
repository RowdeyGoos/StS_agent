#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
from collections.abc import Callable

import apply_reward_live as reward
from tool_common import EXIT_INVALID_INVOCATION, EXIT_MISMATCH, ToolFailure, fail, main

_DECISION_ZERO = "0" * 64
_DECISION_ONE = "1" * 64


def _player(gold: int = 99, deck_count: int = 10) -> dict[str, int]:
    return {"hp": 80, "max_hp": 80, "gold": gold, "deck_count": deck_count}


def _parent(
    decision_id: str = _DECISION_ZERO,
    revision: int = 0,
    gold: int = 99,
    deck_count: int = 10,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "ready",
        "decision_kind": "reward",
        "actionable": True,
        "decision_id": decision_id,
        "decision_revision": revision,
        "screen_kind": "rewards",
        "player": _player(gold, deck_count),
        "rewards": [
            {
                "reward_slot": 0,
                "reward_index": 0,
                "kind": "gold",
                "successfully_selected": False,
                "gold_amount": 14,
                "cards": [],
                "card_selection_can_skip": False,
            },
            {
                "reward_slot": 1,
                "reward_index": 1,
                "kind": "card",
                "successfully_selected": False,
                "gold_amount": None,
                "cards": ["ANGER", "BASH"],
                "card_selection_can_skip": True,
            },
            {
                "reward_slot": 2,
                "reward_index": 2,
                "kind": "unsupported",
                "successfully_selected": False,
                "gold_amount": None,
                "cards": [],
                "card_selection_can_skip": False,
            },
        ],
        "legal_actions": [
            {
                "action_id": "claim:0",
                "kind": "claim_gold",
                "reward_slot": 0,
                "card_slot": None,
            },
            {
                "action_id": "open:1",
                "kind": "open_card",
                "reward_slot": 1,
                "card_slot": None,
            },
            {
                "action_id": "proceed",
                "kind": "proceed",
                "reward_slot": None,
                "card_slot": None,
            },
        ],
    }


def _child(
    decision_id: str = _DECISION_ONE,
    revision: int = 1,
    gold: int = 99,
    deck_count: int = 10,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "ready",
        "decision_kind": "reward",
        "actionable": True,
        "decision_id": decision_id,
        "decision_revision": revision,
        "screen_kind": "card_reward",
        "player": _player(gold, deck_count),
        "rewards": [
            {
                "reward_slot": 0,
                "reward_index": 1,
                "kind": "card",
                "successfully_selected": False,
                "gold_amount": None,
                "cards": ["ANGER", "BASH"],
                "card_selection_can_skip": True,
            }
        ],
        "legal_actions": [
            {
                "action_id": "choose:0",
                "kind": "choose_card",
                "reward_slot": None,
                "card_slot": 0,
            },
            {
                "action_id": "choose:1",
                "kind": "choose_card",
                "reward_slot": None,
                "card_slot": 1,
            },
            {
                "action_id": "skip_card",
                "kind": "skip_card",
                "reward_slot": None,
                "card_slot": None,
            },
        ],
    }


def _body(value: dict[str, object]) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("ascii")


def _expect_failure(operation: Callable[[], object], code: str) -> None:
    try:
        operation()
    except ToolFailure as failure:
        if failure.exit_code == EXIT_MISMATCH and failure.error_code == code:
            return
        fail(EXIT_MISMATCH, "reward_fixture_wrong_failure")
    fail(EXIT_MISMATCH, "reward_fixture_unexpected_pass")


def _expect_invocation_failure(arguments: list[str], code: str) -> None:
    try:
        reward.parse_args(arguments)
    except ToolFailure as failure:
        if failure.exit_code == EXIT_INVALID_INVOCATION and failure.error_code == code:
            return
        fail(EXIT_MISMATCH, "reward_fixture_wrong_invocation_failure")
    fail(EXIT_MISMATCH, "reward_fixture_invocation_passed")


def operation() -> dict[str, object]:
    parent = reward._validate_ready(_body(_parent()))
    child = reward._validate_ready(_body(_child()))
    if reward._choose_action(parent, "first-card")["action_id"] != "claim:0":
        fail(EXIT_MISMATCH, "reward_fixture_gold_priority")
    if reward._choose_action(child, "first-card")["action_id"] != "choose:0":
        fail(EXIT_MISMATCH, "reward_fixture_first_card")
    if reward._choose_action(child, "skip-card")["action_id"] != "skip_card":
        fail(EXIT_MISMATCH, "reward_fixture_skip_card")

    after_gold_value = _parent(_DECISION_ONE, 1, gold=113)
    after_gold_value["rewards"] = after_gold_value["rewards"][1:]
    for reward_slot, projected_reward in enumerate(after_gold_value["rewards"]):
        projected_reward["reward_slot"] = reward_slot
    after_gold_value["legal_actions"] = [
        {
            "action_id": "open:0",
            "kind": "open_card",
            "reward_slot": 0,
            "card_slot": None,
        },
        {
            "action_id": "proceed",
            "kind": "proceed",
            "reward_slot": None,
            "card_slot": None,
        },
    ]
    after_gold = reward._validate_ready(_body(after_gold_value))
    reward._validate_transition(parent, after_gold, parent["legal_actions"][0])
    reward._validate_transition(
        child,
        reward._validate_ready(_body(_parent("2" * 64, 2, deck_count=11))),
        child["legal_actions"][0],
    )

    malformed = _parent()
    malformed["legal_actions"][0]["action_id"] = "claim:8"
    _expect_failure(
        lambda: reward._validate_ready(_body(malformed)),
        "reward_response_mismatch",
    )
    wrong_delta = _parent(_DECISION_ONE, 1, gold=112)
    _expect_failure(
        lambda: reward._validate_transition(
            parent,
            reward._validate_ready(_body(wrong_delta)),
            parent["legal_actions"][0],
        ),
        "gold_claim_reconciliation_failed",
    )

    base = [
        "--user-profile",
        "/synthetic-profile",
        "--effective-uid",
        "501",
        "--decision-provider",
        "first-card",
    ]
    if reward.parse_args(base) != ("/synthetic-profile", 501, "first-card"):
        fail(EXIT_MISMATCH, "reward_fixture_parse")
    invalid = list(base)
    invalid[-1] = "unknown"
    _expect_invocation_failure(invalid, "invalid_decision_provider")

    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_reward_live_fixtures",
        "checks": [
            "strict_parent_and_child_contract",
            "gold_first_provider",
            "choose_and_skip_provider",
            "state_reconciliation",
            "malformed_fail_closed",
            "provider_surface",
        ],
        "check_count": 6,
    }


if __name__ == "__main__":
    main(operation)
