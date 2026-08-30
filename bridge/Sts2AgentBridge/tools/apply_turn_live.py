#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import time
from pathlib import Path
from typing import Any, Callable

import apply_one_live as action_client
import probe_live as probe
from tool_common import (
    EXIT_INTERNAL,
    EXIT_MISMATCH,
    ToolFailure,
    absolute_path,
    fail,
    main,
)

_TURN_DEADLINE_SECONDS = 45.0
_POLL_SECONDS = 0.1
_MAX_ACCEPTED_ACTIONS = 6


def parse_args(arguments: list[str] | None = None) -> tuple[str, int, str]:
    return action_client.parse_args(arguments)


def _read_ready_decision(
    credential: bytearray,
    decision_provider: str,
    connector: Callable[[], Any],
    deadline: float,
) -> dict[str, object]:
    body = action_client._read_body(
        "decision",
        probe._COMBAT_ROUTE[0][1],
        credential,
        connector,
        deadline,
    )
    if body == probe._COMBAT_WAITING:
        fail(EXIT_MISMATCH, "combat_not_ready")
    if body == probe._COMBAT_UNSUPPORTED:
        fail(EXIT_MISMATCH, "combat_state_unsupported")
    with memoryview(body) as view:
        return probe._validate_combat(view, decision_provider)


def _poll_next_decision(
    credential: bytearray,
    decision_provider: str,
    previous_decision_id: str,
    connector: Callable[[], Any],
    deadline: float,
    required_round: int | None = None,
) -> dict[str, object]:
    while time.monotonic() < deadline:
        body = action_client._read_body(
            "decision",
            probe._COMBAT_ROUTE[0][1],
            credential,
            connector,
            deadline,
        )
        if body == probe._COMBAT_WAITING:
            time.sleep(_POLL_SECONDS)
            continue
        if body == probe._COMBAT_UNSUPPORTED:
            fail(EXIT_MISMATCH, "post_action_state_unsupported")
        with memoryview(body) as view:
            candidate = probe._validate_combat(view, decision_provider)
        if candidate["decision_id"] != previous_decision_id:
            if required_round is None:
                return candidate
            candidate_round = int(candidate["round"])
            if candidate_round == required_round:
                return candidate
            if candidate_round > required_round:
                fail(EXIT_MISMATCH, "post_action_round_overshoot")
        time.sleep(_POLL_SECONDS)
    fail(EXIT_MISMATCH, "post_action_state_timeout")


def _run_apply_turn(
    credential: bytearray,
    decision_provider: str,
    connector: Callable[[], Any],
) -> dict[str, object]:
    deadline = time.monotonic() + _TURN_DEADLINE_SECONDS
    try:
        health = action_client._read_body(
            "health",
            probe._BASE_ROUTES[0][1],
            credential,
            connector,
            deadline,
        )
        with memoryview(health) as body:
            probe._validate_health(body)
        manifest = action_client._read_body(
            "manifest",
            probe._BASE_ROUTES[1][1],
            credential,
            connector,
            deadline,
        )
        with memoryview(manifest) as body:
            probe._validate_manifest(body)

        initial = _read_ready_decision(
            credential,
            decision_provider,
            connector,
            deadline,
        )
        initial_round = int(initial["round"])
        current = initial
        transitions: list[dict[str, object]] = []

        for step in range(1, _MAX_ACCEPTED_ACTIONS + 1):
            recommendation = current["recommendation"]
            if not isinstance(recommendation, dict):
                fail(EXIT_MISMATCH, "invalid_provider_selection")
            action_kind = recommendation.get("kind")
            if action_kind not in ("play_card", "end_turn"):
                fail(EXIT_MISMATCH, "invalid_provider_selection")

            decision_id = str(current["decision_id"])
            action_id = str(recommendation.get("action_id"))
            action_body = action_client._read_body(
                "action",
                probe._ACTION_ROUTE,
                credential,
                connector,
                deadline,
                decision_id,
                action_id,
            )
            action_client._validate_action_response(action_body, decision_id, action_id)
            following = _poll_next_decision(
                credential,
                decision_provider,
                decision_id,
                connector,
                deadline,
                initial_round + 1 if action_kind == "end_turn" else None,
            )
            transitions.append(
                {
                    "step": step,
                    "before": current,
                    "applied": recommendation,
                    "after": following,
                }
            )

            following_round = int(following["round"])
            if action_kind == "end_turn":
                if following_round != initial_round + 1:
                    fail(EXIT_MISMATCH, "round_did_not_advance_once")
                return {
                    "schema_version": 1,
                    "status": "passed",
                    "milestone": "r0d_one_turn",
                    "decision_provider": decision_provider,
                    "initial_round": initial_round,
                    "final_round": following_round,
                    "accepted_action_count": len(transitions),
                    "action_limit": _MAX_ACCEPTED_ACTIONS,
                    "transitions": transitions,
                    "routes_checked": 3 + 2 * len(transitions),
                }
            if following_round != initial_round:
                fail(EXIT_MISMATCH, "round_advanced_without_end_turn")
            current = following

        fail(EXIT_MISMATCH, "end_turn_not_selected_within_limit")
    finally:
        probe._zero(credential)


def _operation() -> dict[str, object]:
    user_profile_value, supplied_uid, provider = parse_args()
    user_profile: Path = absolute_path(user_profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)
    credential = probe._load_fixed_credential(user_profile, uid)
    try:
        return _run_apply_turn(credential, provider, probe._literal_loopback_connector)
    finally:
        probe._zero(credential)


def operation() -> dict[str, object]:
    try:
        return _operation()
    except ToolFailure:
        raise
    except Exception:
        fail(EXIT_INTERNAL, "internal_failure")


if __name__ == "__main__":
    main(operation)
