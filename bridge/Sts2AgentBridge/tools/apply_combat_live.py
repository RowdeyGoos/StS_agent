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

_COMBAT_DEADLINE_SECONDS = 300.0
_POLL_SECONDS = 0.1
_MAX_ROUNDS_OBSERVED = 12
_MAX_ACCEPTED_ACTIONS = 48
_MAX_STALE_RETRIES = 24


def parse_args(arguments: list[str] | None = None) -> tuple[str, int, str]:
    return action_client.parse_args(arguments)


def _read_initial_decision(
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
    if body.startswith(probe._COMBAT_COMPLETE_PREFIX):
        fail(EXIT_MISMATCH, "combat_already_complete")
    with memoryview(body) as view:
        return probe._validate_combat(view, decision_provider)


def _poll_after_action(
    credential: bytearray,
    decision_provider: str,
    previous_decision_id: str,
    connector: Callable[[], Any],
    deadline: float,
    required_round: int | None = None,
) -> tuple[str, dict[str, object]]:
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
            if body.startswith(probe._COMBAT_COMPLETE_PREFIX):
                return "complete", probe._validate_combat_terminal(view)
            candidate = probe._validate_combat(view, decision_provider)
        if candidate["decision_id"] != previous_decision_id:
            if required_round is None:
                return "ready", candidate
            candidate_round = int(candidate["round"])
            if candidate_round == required_round:
                return "ready", candidate
            if candidate_round > required_round:
                fail(EXIT_MISMATCH, "post_action_round_overshoot")
        time.sleep(_POLL_SECONDS)
    fail(EXIT_MISMATCH, "post_action_state_timeout")


def _read_after_rejection(
    credential: bytearray,
    decision_provider: str,
    connector: Callable[[], Any],
    deadline: float,
) -> tuple[str, dict[str, object]]:
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
            fail(EXIT_MISMATCH, "post_rejection_state_unsupported")
        with memoryview(body) as view:
            if body.startswith(probe._COMBAT_COMPLETE_PREFIX):
                return "complete", probe._validate_combat_terminal(view)
            return "ready", probe._validate_combat(view, decision_provider)
    fail(EXIT_MISMATCH, "post_rejection_state_timeout")


def _enemy_hp(decision: dict[str, object]) -> int:
    enemies = decision["enemies"]
    if not isinstance(enemies, list):
        fail(EXIT_INTERNAL, "internal_failure")
    return sum(int(enemy["hp"]) for enemy in enemies)


def _terminal_result(
    decision_provider: str,
    initial_round: int,
    action_trace: list[dict[str, object]],
    terminal: dict[str, object],
) -> dict[str, object]:
    terminal_player = terminal["player"]
    if not isinstance(terminal_player, dict):
        fail(EXIT_INTERNAL, "internal_failure")
    final_round = int(terminal["round"])
    final_round_count = final_round - initial_round + 1
    if final_round_count < 1 or final_round_count > _MAX_ROUNDS_OBSERVED:
        fail(EXIT_MISMATCH, "combat_round_limit_reached")
    return {
        "schema_version": 1,
        "status": "passed",
        "milestone": "r0e_complete_combat",
        "decision_provider": decision_provider,
        "outcome": terminal["outcome"],
        "initial_round": initial_round,
        "final_round": final_round,
        "rounds_observed": final_round_count,
        "accepted_action_count": len(action_trace),
        "action_limit": _MAX_ACCEPTED_ACTIONS,
        "round_limit": _MAX_ROUNDS_OBSERVED,
        "final_player": terminal_player,
        "final_enemies": terminal["enemies"],
        "actions": action_trace,
    }


def _run_apply_combat(
    credential: bytearray,
    decision_provider: str,
    connector: Callable[[], Any],
) -> dict[str, object]:
    deadline = time.monotonic() + _COMBAT_DEADLINE_SECONDS
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

        current = _read_initial_decision(
            credential,
            decision_provider,
            connector,
            deadline,
        )
        initial_round = int(current["round"])
        action_trace: list[dict[str, object]] = []

        stale_retries = 0
        while len(action_trace) < _MAX_ACCEPTED_ACTIONS:
            step = len(action_trace) + 1
            current_round = int(current["round"])
            rounds_observed = current_round - initial_round + 1
            if rounds_observed < 1 or rounds_observed > _MAX_ROUNDS_OBSERVED:
                fail(EXIT_MISMATCH, "combat_round_limit_reached")

            recommendation = current["recommendation"]
            if not isinstance(recommendation, dict):
                fail(EXIT_MISMATCH, "invalid_provider_selection")
            action_kind = recommendation.get("kind")
            if action_kind not in ("play_card", "end_turn"):
                fail(EXIT_MISMATCH, "invalid_provider_selection")

            player = current["player"]
            if not isinstance(player, dict):
                fail(EXIT_INTERNAL, "internal_failure")
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
            action_outcome = action_client._classify_action_response(
                action_body,
                decision_id,
                action_id,
            )
            if action_outcome == "stale_decision":
                stale_retries += 1
                if stale_retries > _MAX_STALE_RETRIES:
                    fail(EXIT_MISMATCH, "stale_action_retry_limit_reached")
                time.sleep(_POLL_SECONDS)
                following_kind, following = _read_after_rejection(
                    credential,
                    decision_provider,
                    connector,
                    deadline,
                )
                if following_kind == "complete":
                    # A previously accepted action can finish asynchronously
                    # after a later decision has already gone stale. Attribute
                    # terminal completion only when this invocation has an
                    # accepted action in its immutable trace.
                    if not action_trace:
                        fail(EXIT_MISMATCH, "terminal_after_rejected_action")
                    return _terminal_result(
                        decision_provider,
                        initial_round,
                        action_trace,
                        following,
                    )
                current = following
                continue
            if action_outcome == "invalid_action":
                fail(EXIT_MISMATCH, "action_rejected_invalid")
            if action_outcome == "action_limit_reached":
                fail(EXIT_MISMATCH, "bridge_action_limit_reached")
            if action_outcome not in ("accepted", "already_applied"):
                fail(EXIT_INTERNAL, "internal_failure")

            stale_retries = 0
            following_kind, following = _poll_after_action(
                credential,
                decision_provider,
                decision_id,
                connector,
                deadline,
                current_round + 1 if action_kind == "end_turn" else None,
            )

            trace_item: dict[str, object] = {
                "step": step,
                "round": current_round,
                "action_id": action_id,
                "card_id": recommendation.get("card_id"),
                "basis": recommendation.get("basis"),
                "player_hp_before": int(player["hp"]),
                "enemy_hp_before": _enemy_hp(current),
            }
            if following_kind == "complete":
                terminal_player = following["player"]
                if not isinstance(terminal_player, dict):
                    fail(EXIT_INTERNAL, "internal_failure")
                trace_item["player_hp_after"] = int(terminal_player["hp"])
                trace_item["enemy_hp_after"] = _enemy_hp(following)
                action_trace.append(trace_item)
                return _terminal_result(
                    decision_provider,
                    initial_round,
                    action_trace,
                    following,
                )

            following_round = int(following["round"])
            if action_kind == "end_turn":
                if following_round != current_round + 1:
                    fail(EXIT_MISMATCH, "round_did_not_advance_once")
            elif following_round != current_round:
                fail(EXIT_MISMATCH, "round_advanced_without_end_turn")

            following_player = following["player"]
            if not isinstance(following_player, dict):
                fail(EXIT_INTERNAL, "internal_failure")
            trace_item["player_hp_after"] = int(following_player["hp"])
            trace_item["enemy_hp_after"] = _enemy_hp(following)
            action_trace.append(trace_item)
            current = following

        fail(EXIT_MISMATCH, "combat_action_limit_reached")
    finally:
        probe._zero(credential)


def _operation() -> dict[str, object]:
    user_profile_value, supplied_uid, provider = parse_args()
    user_profile: Path = absolute_path(user_profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)
    credential = probe._load_fixed_credential(user_profile, uid)
    try:
        return _run_apply_combat(credential, provider, probe._literal_loopback_connector)
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
