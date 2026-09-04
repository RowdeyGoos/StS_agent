#!/usr/bin/env python3
"""Capture-off checks for the reviewed inspection-map room boundary."""
from __future__ import annotations

import json
import math
import time
from collections.abc import Callable

import apply_room_live as room
import apply_map_live as map_client
import apply_reward_live as reward_client
import apply_run_live as run_client
import probe_live as probe
from decision_providers import get_map_decision_provider, map_provider_names, provider_names
from tool_common import EXIT_INTERNAL, EXIT_MISMATCH, ToolFailure, fail

_ACKNOWLEDGED = "acknowledged"
_MAXIMUM_ACKNOWLEDGEMENT_SECONDS = 45.0


def _validated_snapshot(snapshot: object, code: str) -> dict[str, object]:
    if type(snapshot) is not bytes:
        fail(EXIT_MISMATCH, code)
    try:
        return room._validate_room(snapshot)
    except ToolFailure:
        fail(EXIT_MISMATCH, code)


def _original_action(snapshot: object) -> tuple[str, str]:
    decision = _validated_snapshot(snapshot, "original_snapshot_mismatch")
    if (
        decision["status"] != "ready"
        or decision["screen_kind"] != "rest_site"
        or decision["phase"] not in ("choose_option", "choose_or_proceed")
    ):
        fail(EXIT_MISMATCH, "original_snapshot_not_actionable")
    legal = decision["legal_actions"]
    candidates = decision["candidates"]
    if not isinstance(legal, list) or not isinstance(candidates, list):
        fail(EXIT_INTERNAL, "internal_failure")
    legal_ids = {item["action_id"] for item in legal if isinstance(item, dict)}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        action_id = candidate.get("action_id")
        if (
            candidate.get("kind") == "rest_heal"
            and candidate.get("enabled") is True
            and candidate.get("supported") is True
            and candidate.get("is_dangerous") is False
            and isinstance(action_id, str)
            and action_id in legal_ids
        ):
            decision_id = decision.get("decision_id")
            if isinstance(decision_id, str):
                return decision_id, action_id
    fail(EXIT_MISMATCH, "original_snapshot_safe_action_missing")


def _require_inspection_suppressed(snapshot: object) -> None:
    if _validated_snapshot(snapshot, "inspection_snapshot_mismatch")["status"] != "waiting":
        fail(EXIT_MISMATCH, "inspection_actions_not_suppressed")


def _stale_receipt(decision_id: str, action_id: str) -> bytes:
    return (
        b'{"schema_version":1,"status":"rejected","mutation_state":"none",'
        b'"decision_id":"' + decision_id.encode("ascii") + b'","action_id":"'
        + action_id.encode("ascii") + b'","reason":"stale_decision"}'
    )


def _callback(label: str, operation: Callable[..., object], *arguments: object) -> object:
    try:
        return operation(*arguments)
    except BaseException:
        fail(EXIT_INTERNAL, f"{label}_callback_failure")


def _clock_value(clock: Callable[[], float]) -> float:
    value = _callback("clock", clock)
    number = _finite_number(value, "clock_callback_failure")
    if number < 0:
        fail(EXIT_INTERNAL, "clock_callback_failure")
    return number


def _finite_number(value: object, code: str) -> float:
    if type(value) not in (int, float):
        fail(EXIT_INTERNAL, code)
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        fail(EXIT_INTERNAL, code)
    if not math.isfinite(number):
        fail(EXIT_INTERNAL, code)
    return number


def verify_inspection_map_rejection(
    original_snapshot: bytes,
    inspection_snapshot_reader: Callable[[], bytes],
    acknowledge: Callable[[float], object],
    stale_action_sender: Callable[[str, str], bytes],
    *,
    clock: Callable[[], float] = time.monotonic,
    acknowledgement_seconds: float = _MAXIMUM_ACKNOWLEDGEMENT_SECONDS,
    cleanup: Callable[[], None] | None = None,
) -> dict[str, object]:
    """Verify one original rest-heal action becomes stale after inspection.

    Hooks are trusted, bounded, cooperative callbacks: they must return promptly
    and must not log or retain raw data. ``acknowledge(deadline)`` receives the
    absolute deadline in the supplied clock's units and must bound any operator
    wait to it. An immediate acknowledgement after direct UI inspection is also
    supported. Checks reject late returns but cannot preempt a hanging hook,
    including cleanup; this function creates no background worker or service.

    Raised callback failures become fixed codes. The original snapshot and
    receipt are held only in memory and never included in verifier output.
    """
    receipt = bytearray()
    primary_failure = False
    try:
        timeout = _finite_number(acknowledgement_seconds, "invalid_acknowledgement_timeout")
        if not 0 < timeout <= _MAXIMUM_ACKNOWLEDGEMENT_SECONDS:
            fail(EXIT_INTERNAL, "invalid_acknowledgement_timeout")
        decision_id, action_id = _original_action(original_snapshot)
        previous_time = _clock_value(clock)
        deadline = previous_time + timeout
        if not math.isfinite(deadline):
            fail(EXIT_INTERNAL, "clock_callback_failure")

        def check_deadline() -> None:
            nonlocal previous_time
            current_time = _clock_value(clock)
            if current_time < previous_time:
                fail(EXIT_INTERNAL, "clock_callback_failure")
            previous_time = current_time
            if current_time >= deadline:
                fail(EXIT_MISMATCH, "operator_acknowledgement_timeout")

        check_deadline()
        acknowledged = _callback("acknowledgement", acknowledge, deadline)
        check_deadline()
        if type(acknowledged) is not str or acknowledged != _ACKNOWLEDGED:
            fail(EXIT_MISMATCH, "operator_acknowledgement_invalid")
        inspected = _callback("inspection_snapshot", inspection_snapshot_reader)
        check_deadline()
        if type(inspected) is bytes and not inspected:
            fail(EXIT_MISMATCH, "inspection_snapshot_eof")
        _require_inspection_suppressed(inspected)
        check_deadline()
        sent = _callback("stale_action", stale_action_sender, decision_id, action_id)
        check_deadline()
        if type(sent) is not bytes:
            fail(EXIT_MISMATCH, "stale_receipt_mismatch")
        receipt.extend(sent)
        if bytes(receipt) != _stale_receipt(decision_id, action_id):
            fail(EXIT_MISMATCH, "stale_receipt_mismatch")
        return {
            "schema_version": 1, "status": "passed",
            "code": "inspection_map_stale_rejection_verified",
            "acknowledgement_count": 1, "stale_action_attempt_count": 1,
        }
    except BaseException:
        primary_failure = True
        raise
    finally:
        for index in range(len(receipt)):
            receipt[index] = 0
        if cleanup is not None:
            try:
                cleanup()
            except BaseException:
                if not primary_failure:
                    fail(EXIT_INTERNAL, "cleanup_callback_failure")


def summarize_room_result(result: object) -> dict[str, object]:
    required = {
        "schema_version", "status", "milestone", "decision_provider", "screen_kind",
        "room_ordinal", "accepted_action_count", "actions", "final", "routes_checked",
    }
    if not isinstance(result, dict) or set(result) != required:
        fail(EXIT_MISMATCH, "room_result_mismatch")
    action_count = result["accepted_action_count"]
    route_count = result["routes_checked"]
    actions = result["actions"]
    screen_kind = result["screen_kind"]
    if (
        type(result["schema_version"]) is not int
        or result["schema_version"] != 1 or result["status"] != "passed"
        or result["milestone"] != "r0i_room_interaction" or result["decision_provider"] != "safe"
        or screen_kind not in ("rest_site", "event")
        or type(result["room_ordinal"]) is not int or not 0 <= result["room_ordinal"] <= 999
        or type(action_count) is not int or not 1 <= action_count <= room._MAXIMUM_ACCEPTED_ACTIONS
        or not isinstance(actions, list) or len(actions) != action_count
        or type(route_count) is not int or route_count < 3 + 2 * action_count
    ):
        fail(EXIT_MISMATCH, "room_result_mismatch")
    seen: set[str] = set()
    for action in actions:
        if not isinstance(action, dict) or set(action) != {"decision_id", "action_id", "basis", "phase"}:
            fail(EXIT_MISMATCH, "room_result_mismatch")
        decision_id, action_id = action["decision_id"], action["action_id"]
        basis, phase = action["basis"], action["phase"]
        if (
            not isinstance(decision_id, str) or not room._canonical_decision_id(decision_id)
            or decision_id in seen or not isinstance(action_id, str)
            or not room._canonical_action_id(action_id)
            or (
                action_id != "proceed"
                and (
                    not action_id.startswith("choose:")
                    or not action_id[7:].isdigit()
                    or not 0 <= int(action_id[7:]) <= 7
                )
            )
            or phase not in ("choose_option", "proceed", "choose_or_proceed")
        ):
            fail(EXIT_MISMATCH, "room_result_mismatch")
        seen.add(decision_id)
        valid = (
            basis == "rest_heal"
            and screen_kind == "rest_site"
            and action_id != "proceed"
            and phase in ("choose_option", "choose_or_proceed")
        ) or (
            basis == "proceed"
            and screen_kind == "rest_site"
            and action_id == "proceed"
            and phase == "proceed"
        ) or (
            basis == "event_first_supported"
            and screen_kind == "event"
            and action_id != "proceed"
            and phase == "choose_option"
        )
        if not valid:
            fail(EXIT_MISMATCH, "room_result_mismatch")
    try:
        final = room._validate_room(json.dumps(result["final"], ensure_ascii=True, separators=(",", ":")).encode("ascii"))
    except (ToolFailure, TypeError, ValueError):
        fail(EXIT_MISMATCH, "room_result_mismatch")
    if final["status"] != "complete" or final["screen_kind"] != screen_kind or final["room_ordinal"] != result["room_ordinal"]:
        fail(EXIT_MISMATCH, "room_result_mismatch")
    return {"code": "room_result_valid", "accepted_action_count": action_count, "route_count": route_count}


def summarize_run_result(result: object) -> dict[str, object]:
    """Summarize accepted R0I-COMPOSE-09 output without validating its history.

    Only the selected schema/count fields are checked. Nested component results
    and their reconciliation are not validated here, so even complete current
    client output remains explicitly ``run_result_unvalidated``.
    """
    if not isinstance(result, dict):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    floor_count, action_totals, readiness = result.get("completed_floor_count"), result.get("action_totals"), result.get("readiness")
    if (
        type(result.get("schema_version")) is not int
        or result.get("schema_version") != 1 or result.get("status") != "passed"
        or result.get("milestone") != "r0i_bounded_run" or type(floor_count) is not int
        or not 0 <= floor_count <= 3 or not isinstance(readiness, list) or not isinstance(action_totals, dict)
    ):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    counts = tuple(action_totals.get(name) for name in ("combat", "reward", "map", "room", "total"))
    if any(type(value) is not int or value < 0 for value in counts):
        fail(EXIT_MISMATCH, "run_result_mismatch")
    combat, reward, map_actions, room_actions, total = counts
    if total != combat + reward + map_actions + room_actions:
        fail(EXIT_MISMATCH, "run_result_mismatch")
    return {"code": "run_result_unvalidated", "completed_floor_count": floor_count, "readiness_count": len(readiness), "action_count": total}


# The run result is deliberately validated here, rather than by a live wrapper:
# this module owns no transport or controller semantics and never returns nested
# client material.  Keep these allowlists local to the result contract so a
# future producer addition requires an explicit acceptance-validator review.
_RUN_MILESTONES = frozenset(("r0i_bounded_run", "r0i_bounded_run_entry"))
_DESTINATION_KINDS = frozenset(
    ("unknown", "shop", "treasure", "rest_site", "monster", "elite", "boss", "ancient")
)
_COMBAT_DESTINATION_KINDS = frozenset(("monster", "elite"))
_ROOM_DESTINATION_KINDS = frozenset(("rest_site", "ancient", "unknown"))
_TERMINATION_REASONS = frozenset(
    (
        "floor_limit_reached",
        "act_boundary_reached",
        "unsupported_destination_kind",
        "run_defeat",
        "room_handoff_complete",
        "room_continuation_complete",
    )
)
_ACTION_TOTAL_NAMES = ("combat", "reward", "map", "room", "total")
_KNOWN_PRODUCTION_FAILURE_CODES = frozenset(
    (
        "invalid_invocation", "invalid_combat_provider", "invalid_reward_provider",
        "invalid_map_provider", "invalid_room_provider", "invalid_floor_limit",
        "invalid_entry_phase", "run_combat_result_mismatch", "run_reward_result_mismatch",
        "run_map_result_mismatch", "run_map_destination_mismatch", "run_combat_outcome_mismatch",
        "run_player_continuity_mismatch", "run_room_result_mismatch", "run_room_provider_mismatch",
        "run_room_reconciliation_mismatch", "run_room_preflight_mismatch", "run_room_kind_mismatch",
        "run_room_state_unsupported", "run_room_not_ready", "run_room_ready_timeout",
        "run_post_room_map_result_mismatch", "run_post_room_destination_unsupported",
        "run_second_room_destination", "run_next_combat_result_mismatch", "next_combat_state_unsupported",
        "next_combat_ready_timeout", "internal_failure", "invalid_effective_uid",
        "non_absolute_user_profile", "non_canonical_user_profile",
        "unsupported_platform", "effective_uid_mismatch", "user_identity_unavailable",
        "user_profile_mismatch", "unsafe_user_profile", "missing_credential_component",
        "acl_check_failed", "granting_acl", "missing_path_component", "symlink_path_component",
        "non_directory_credential_component", "missing_credential_file", "non_regular_credential_file",
        "credential_owner", "credential_directory_mode", "credential_link_count", "credential_file_mode",
        "credential_shape", "credential_read_failed", "changing_credential_file", "safe_open_unsupported",
        "health_response_mismatch", "manifest_response_mismatch", "combat_terminal_response_mismatch",
        "decision_envelope_mismatch", "decision_identity_mismatch", "decision_player_mismatch",
        "decision_enemies_mismatch", "decision_hand_mismatch", "decision_legal_actions_mismatch",
        "decision_provider_result_mismatch",
        "combat_not_ready", "combat_state_unsupported", "combat_already_complete",
        "combat_round_limit_reached", "combat_action_limit_reached", "invalid_provider_selection",
        "post_action_state_unsupported", "post_action_state_timeout", "post_action_round_overshoot",
        "post_rejection_state_unsupported", "post_rejection_state_timeout", "stale_action_retry_limit_reached",
        "terminal_after_rejected_action", "action_rejected_invalid", "bridge_action_limit_reached",
        "round_did_not_advance_once", "round_advanced_without_end_turn", "action_response_mismatch",
        "reward_state_unsupported", "reward_action_response_mismatch", "reward_response_mismatch",
        "reward_ready_timeout", "map_state_unsupported", "map_ready_timeout",
        "reward_complete_response_mismatch", "reward_provider_no_action", "reward_not_ready",
        "card_reward_not_skippable",
        "reward_action_budget_exhausted", "post_reward_state_unsupported", "post_reward_state_timeout",
        "reward_decision_not_advanced", "gold_claim_reconciliation_failed", "card_open_reconciliation_failed",
        "card_choice_reconciliation_failed", "card_skip_reconciliation_failed", "reward_proceed_reconciliation_failed",
        "reward_unknown_transition", "reward_revision_mismatch", "map_response_mismatch",
        "map_complete_response_mismatch", "map_action_response_mismatch", "map_not_ready",
        "map_action_stale_decision", "map_action_invalid_action", "map_action_already_applied",
        "map_action_action_limit_reached", "map_rate_limited", "map_backend_retryable", "map_backend_fault",
        "map_action_rate_limited", "map_action_backend_retryable", "map_action_backend_fault",
        "post_map_state_unsupported", "post_map_state_timeout", "map_destination_mismatch",
        "room_response_mismatch", "room_state_unsupported", "room_not_ready", "room_completion_mismatch",
        "room_action_response_mismatch", "room_action_limit_reached", "room_expected_context_mismatch",
        "room_transition_mismatch", "room_decision_replayed", "room_interaction_timeout", "no_safe_room_action",
        "room_expected_context_invalid", "room_action_stale_decision", "room_action_invalid_action",
        "room_action_already_applied", "room_action_action_limit_reached",
        "map_action_transport_failure", "reward_action_transport_failure", "room_action_transport_failure",
        "action_transport_failure", "decision_transport_failure", "health_transport_failure",
        "manifest_transport_failure", "reward_transport_failure", "map_transport_failure", "room_transport_failure",
        "health_transport_timeout", "manifest_transport_timeout", "decision_transport_timeout",
        "action_transport_timeout", "reward_transport_timeout", "reward_action_transport_timeout",
        "map_transport_timeout", "map_action_transport_timeout", "room_transport_timeout", "room_action_transport_timeout",
        "health_transport_mismatch", "manifest_transport_mismatch", "decision_transport_mismatch",
        "action_transport_mismatch", "reward_transport_mismatch", "reward_action_transport_mismatch",
        "map_transport_mismatch", "map_action_transport_mismatch", "room_transport_mismatch", "room_action_transport_mismatch",
        "health_response_too_large", "manifest_response_too_large", "decision_response_too_large",
        "action_response_too_large", "reward_response_too_large", "reward_action_response_too_large",
        "map_response_too_large", "map_action_response_too_large", "room_response_too_large", "room_action_response_too_large",
        "health_empty_response", "manifest_empty_response", "decision_empty_response", "action_empty_response",
        "reward_empty_response", "reward_action_empty_response", "map_empty_response", "map_action_empty_response",
        "room_empty_response", "room_action_empty_response",
        "decision_response_mismatch", "probe_transport_timeout",
        "health_rate_limited", "health_backend_retryable", "health_backend_fault",
        "manifest_rate_limited", "manifest_backend_retryable", "manifest_backend_fault",
    )
)
_KNOWN_PRODUCTION_FAILURE_CODES |= frozenset(
    f"{label}_{suffix}"
    for label in (
        "health", "manifest", "decision", "action", "reward", "reward_action",
        "map", "map_action", "room", "room_action",
    )
    for suffix in (
        "transport_timeout", "transport_mismatch", "response_too_large",
        "empty_response", "transport_failure", "response_mismatch",
    )
)
_KNOWN_PRODUCTION_FAILURE_CODES |= frozenset(
    f"{label}_{suffix}"
    for label in ("health", "manifest", "map", "map_action")
    for suffix in ("rate_limited", "backend_retryable", "backend_fault")
)
_KNOWN_PRODUCTION_FAILURE_CODES |= frozenset(
    f"{label}_{reason}"
    for label in ("map_action", "room_action")
    for reason in ("stale_decision", "invalid_action", "already_applied", "action_limit_reached")
)


def _integer(value: object, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return value


def _exact_dict(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return value


def _component(value: object, milestone: str) -> dict[str, object]:
    if (
        not isinstance(value, dict)
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != 1
        or value.get("status") != "passed"
        or value.get("milestone") != milestone
    ):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    schemas = {
        "r0e_complete_combat": {
            "schema_version", "status", "milestone", "decision_provider", "outcome",
            "initial_round", "final_round", "rounds_observed", "accepted_action_count",
            "action_limit", "round_limit", "final_player", "final_enemies", "actions",
        },
        "r0i_reward_resolution": {
            "schema_version", "status", "milestone", "decision_provider", "applied",
            "claimed_gold", "selected_cards", "before", "after", "routes_checked",
        },
        "r0g_map_selection": {
            "schema_version", "status", "milestone", "decision_provider", "applied",
            "before", "after", "routes_checked",
        },
        "r0i_room_interaction": {
            "schema_version", "status", "milestone", "decision_provider", "screen_kind",
            "room_ordinal", "accepted_action_count", "actions", "final", "routes_checked",
        },
    }
    if set(value) != schemas[milestone]:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if type(value["decision_provider"]) is not str or not value["decision_provider"]:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if milestone == "r0e_complete_combat":
        initial = _integer(value["initial_round"], 1, 1_000_000)
        final = _integer(value["final_round"], initial, 1_000_000)
        player = value["final_player"]
        enemies = value["final_enemies"]
        actions = value["actions"]
        if (
            value["outcome"] not in ("victory", "defeat")
            or _integer(value["rounds_observed"], 1, 12) != final - initial + 1
            or _integer(value["action_limit"], 1) != 48
            or _integer(value["round_limit"], 1) != 12
            or not isinstance(value["final_player"], dict)
            or not isinstance(value["final_enemies"], list)
            or not isinstance(value["actions"], list)
            or len(value["actions"]) != _integer(value["accepted_action_count"], 1, 48)
            or set(value["final_player"]) != {"hp", "max_hp", "block", "energy"}
            or any(not probe._is_bounded_nonnegative_integer(player[name]) for name in player)
            or player["max_hp"] < 1
            or player["hp"] > player["max_hp"]
            or (value["outcome"] == "victory" and (player["hp"] < 1 or enemies))
            or (value["outcome"] == "defeat" and player["hp"] != 0)
            or any(
                not isinstance(action, dict)
                or set(action) != {"step", "round", "action_id", "card_id", "basis", "player_hp_before", "enemy_hp_before", "player_hp_after", "enemy_hp_after"}
                or type(action["step"]) is not int
                or action["step"] != index
                or type(action["round"]) is not int
                or not 1 <= action["round"] - initial + 1 <= 12
                or action["round"] > 1_000_000
                or not probe._is_public_string(action["action_id"])
                or (action["card_id"] is not None and not probe._is_public_string(action["card_id"]))
                or action["basis"] not in ("first_legal", "no_safe_card", "incoming_attack", "no_visible_attack")
                or any(not probe._is_bounded_nonnegative_integer(action[name]) for name in ("player_hp_before", "player_hp_after"))
                or any(
                    type(action[name]) is not int or not 0 <= action[name] <= 6_000_000
                    for name in ("enemy_hp_before", "enemy_hp_after")
                )
                for index, action in enumerate(actions, 1)
            )
            or any(
                not isinstance(enemy, dict)
                or set(enemy) != {"index", "id", "hp", "max_hp", "block", "intents"}
                or type(enemy["index"]) is not int
                or enemy["index"] != index
                or not probe._is_public_string(enemy["id"])
                or any(not probe._is_bounded_nonnegative_integer(enemy[name]) for name in ("hp", "max_hp", "block"))
                or enemy["max_hp"] < 1 or not 1 <= enemy["hp"] <= enemy["max_hp"]
                or not isinstance(enemy["intents"], list) or len(enemy["intents"]) > 8
                or any(not probe._is_public_string(intent) for intent in enemy["intents"])
                for index, enemy in enumerate(enemies)
            )
            or len(enemies) > 6
            or value["decision_provider"] not in provider_names()
            or (
                value["decision_provider"] == "first-legal"
                and any(action["basis"] != "first_legal" for action in actions)
            )
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        for action in actions:
            parts = action["action_id"].split(":")
            if action["action_id"] == "end_turn":
                valid_action_id = (
                    action["card_id"] is None
                    and (
                        value["decision_provider"] != "heuristic"
                        or action["basis"] == "no_safe_card"
                    )
                )
            else:
                valid_action_id = (
                    len(parts) in (2, 3)
                    and parts[0] == "play"
                    and len(parts[1]) == 1
                    and parts[1] in "0123456789"
                    and (
                        len(parts) == 2
                        or (len(parts[2]) == 1 and parts[2] in "012345")
                    )
                    and action["card_id"] is not None
                    and (
                        value["decision_provider"] != "heuristic"
                        or action["basis"] in ("incoming_attack", "no_visible_attack")
                    )
                )
            if not valid_action_id:
                fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        terminal_body = json.dumps(
            {
                "schema_version": 1, "status": "complete", "decision_kind": "combat",
                "actionable": False, "decision_id": None, "round": final,
                "player": player, "enemies": enemies, "hand": [], "legal_actions": [],
                "outcome": value["outcome"],
            },
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
        try:
            with memoryview(terminal_body) as body:
                terminal = probe._validate_combat_terminal(body)
        except (ToolFailure, TypeError, ValueError, UnicodeEncodeError):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        expected_terminal = {
            "status": "complete", "round": final, "outcome": value["outcome"],
            "player": player, "enemies": enemies,
        }
        if terminal != expected_terminal:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif milestone == "r0i_reward_resolution":
        applied = value["applied"]
        before, after = value["before"], value["after"]
        if (
            value["decision_provider"] not in reward_client._PROVIDERS
            or not isinstance(applied, list)
            or not 1 <= len(applied) <= 17
            or not probe._is_bounded_nonnegative_integer(value["claimed_gold"])
            or not isinstance(value["selected_cards"], list)
            or not isinstance(value["before"], dict)
            or not isinstance(value["after"], dict)
            or _integer(value["routes_checked"], 3) != 3 + 2 * len(applied)
            or any(
                not isinstance(action, dict)
                or set(action) != {"action_id", "kind", "decision_revision", "chosen_card"}
                or not probe._is_public_string(action["action_id"])
                or type(action["kind"]) is not str
                or not probe._is_bounded_nonnegative_integer(action["decision_revision"])
                for action in applied
            )
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if (
            set(before) != {"decision_id", "decision_revision", "screen_kind", "player", "rewards", "legal_actions"}
            or set(after) != {"screen_kind", "player"}
            or before["screen_kind"] not in ("rewards", "card_reward")
            or after["screen_kind"] != "map"
            or not isinstance(before["rewards"], list)
            or not isinstance(before["legal_actions"], list)
            or any(
                not isinstance(item, dict)
                or set(item) != {"reward_slot", "reward_index", "kind", "successfully_selected", "gold_amount", "cards", "card_selection_can_skip"}
                or type(item["reward_slot"]) is not int
                or item["reward_slot"] != index
                for index, item in enumerate(before["rewards"])
            )
            or any(
                not isinstance(item, dict)
                or set(item) != {"action_id", "kind", "reward_slot", "card_slot"}
                for item in before["legal_actions"]
            )
            or any(not probe._is_public_string(card) for card in value["selected_cards"])
            or any(
                action["kind"] not in ("claim_gold", "open_card", "choose_card", "skip_card", "proceed")
                or (action["chosen_card"] is not None and not probe._is_public_string(action["chosen_card"]))
                for action in applied
            )
            or value["selected_cards"] != [action["chosen_card"] for action in applied if action["chosen_card"] is not None]
            or any(
                (action["kind"] == "claim_gold" and (not action["action_id"].startswith("claim:") or action["chosen_card"] is not None))
                or (action["kind"] == "open_card" and (not action["action_id"].startswith("open:") or action["chosen_card"] is not None))
                or (action["kind"] == "choose_card" and (not action["action_id"].startswith("choose:") or action["chosen_card"] is None))
                or (action["kind"] == "skip_card" and (action["action_id"] != "skip_card" or action["chosen_card"] is not None))
                or (action["kind"] == "proceed" and (action["action_id"] != "proceed" or action["chosen_card"] is not None))
                for action in applied
            )
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        try:
            ready_body = json.dumps({
                "schema_version": 1, "status": "ready", "decision_kind": "reward", "actionable": True,
                "decision_id": before["decision_id"], "decision_revision": before["decision_revision"],
                "screen_kind": before["screen_kind"], "player": before["player"],
                "rewards": before["rewards"], "legal_actions": before["legal_actions"],
            }, ensure_ascii=True, separators=(",", ":")).encode("ascii")
            complete_body = json.dumps({
                "schema_version": 1, "status": "complete", "decision_kind": "reward", "actionable": False,
                "decision_id": None, "screen_kind": after["screen_kind"], "player": after["player"],
                "rewards": [], "legal_actions": [],
            }, ensure_ascii=True, separators=(",", ":")).encode("ascii")
            validated_before = reward_client._validate_ready(ready_body)
            validated_after = reward_client._validate_complete(complete_body)
        except (ToolFailure, KeyError, TypeError, ValueError, UnicodeEncodeError):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if (
            validated_before != before
            or validated_after != after
            or after["player"]["gold"] != before["player"]["gold"] + value["claimed_gold"]
            or any(applied[index]["decision_revision"] != before["decision_revision"] + index for index in range(len(applied)))
            or after["player"]["hp"] != before["player"]["hp"]
            or after["player"]["max_hp"] != before["player"]["max_hp"]
            or after["player"]["deck_count"] != before["player"]["deck_count"] + len(value["selected_cards"])
            or applied[-1]["kind"] != "proceed"
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        try:
            expected_first = reward_client._choose_action(before, str(value["decision_provider"]))
            expected_first_card = (
                before["rewards"][0]["cards"][int(expected_first["card_slot"])]
                if expected_first["kind"] == "choose_card"
                else None
            )
            expected_first_gold = (
                int(
                    before["rewards"][int(expected_first["reward_slot"])][
                        "gold_amount"
                    ]
                )
                if expected_first["kind"] == "claim_gold"
                else None
            )
        except (ToolFailure, IndexError, KeyError, TypeError, ValueError):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        claim_count = sum(action["kind"] == "claim_gold" for action in applied)
        if (
            applied[0]["action_id"] != expected_first["action_id"]
            or applied[0]["kind"] != expected_first["kind"]
            or (
                expected_first_card is not None
                and applied[0]["chosen_card"] != expected_first_card
            )
            or (
                expected_first_gold is not None
                and (
                    value["claimed_gold"] < expected_first_gold
                    or (
                        claim_count == 1
                        and value["claimed_gold"] != expected_first_gold
                    )
                )
            )
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        child_phase = before["screen_kind"] == "card_reward"
        child_kind = "choose_card" if value["decision_provider"] == "first-card" else "skip_card"
        for index, action in enumerate(applied):
            kind = action["kind"]
            action_id = action["action_id"]
            if kind in ("claim_gold", "open_card"):
                parts = action_id.split(":")
                valid_grammar = (
                    not child_phase
                    and len(parts) == 2
                    and parts[0] == ("claim" if kind == "claim_gold" else "open")
                    and len(parts[1]) == 1
                    and parts[1] in "01234567"
                )
            elif kind in ("choose_card", "skip_card"):
                parts = action_id.split(":")
                valid_grammar = child_phase and kind == child_kind and (
                    (kind == "skip_card" and action_id == "skip_card")
                    or (
                        kind == "choose_card"
                        and len(parts) == 2
                        and parts[0] == "choose"
                        and len(parts[1]) == 1
                        and parts[1] in "01234"
                    )
                )
            else:
                valid_grammar = not child_phase and kind == "proceed" and action_id == "proceed"
            if not valid_grammar or (kind == "proceed") != (index == len(applied) - 1):
                fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
            if kind == "open_card":
                child_phase = True
            elif kind in ("choose_card", "skip_card"):
                child_phase = False
    elif milestone == "r0g_map_selection":
        applied, after = value["applied"], value["after"]
        before = value["before"]
        if (
            value["decision_provider"] not in map_provider_names()
            or not isinstance(applied, dict)
            or set(applied) != {"action_id", "kind", "candidate_index", "col", "row", "node_kind", "basis"}
            or not isinstance(value["before"], dict)
            or not isinstance(after, dict)
            or _integer(value["routes_checked"], 5) < 5
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if (
            set(before) != {"decision_id", "screen_kind", "candidates", "legal_actions"}
            or before["screen_kind"] != "map"
            or set(after) != {"screen_kind", "destination"}
            or after["screen_kind"] != "room"
            or not isinstance(before["candidates"], list)
            or not isinstance(before["legal_actions"], list)
            or any(
                not isinstance(item, dict)
                or set(item) != {"candidate_index", "col", "row", "kind"}
                or type(item["candidate_index"]) is not int
                or item["candidate_index"] != index
                for index, item in enumerate(before["candidates"])
            )
            or any(
                not isinstance(item, dict)
                or set(item) != {"action_id", "kind", "candidate_index"}
                or type(item["candidate_index"]) is not int
                or item["candidate_index"] != index
                for index, item in enumerate(before["legal_actions"])
            )
            or applied["kind"] != "select_map_node"
            or applied["basis"] not in ("first_reachable", "combat_continuation", "room_coverage", "elite_continuation")
            or applied["basis"] != {"first": "first_reachable", "combat": "combat_continuation", "coverage": "room_coverage", "elite": "elite_continuation"}.get(value["decision_provider"])
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        candidates = before["candidates"]
        legal_actions = before["legal_actions"]
        try:
            ready_body = json.dumps({
                "schema_version": 1, "status": "ready", "decision_kind": "map", "actionable": True,
                "decision_id": before["decision_id"], "screen_kind": before["screen_kind"],
                "destination": None, "candidates": before["candidates"], "legal_actions": before["legal_actions"],
            }, ensure_ascii=True, separators=(",", ":")).encode("ascii")
            complete_body = json.dumps({
                "schema_version": 1, "status": "complete", "decision_kind": "map", "actionable": False,
                "decision_id": None, "screen_kind": after["screen_kind"], "destination": after["destination"],
                "candidates": [], "legal_actions": [],
            }, ensure_ascii=True, separators=(",", ":")).encode("ascii")
            validated_before = map_client._validate_ready(ready_body)
            validated_after = map_client._validate_complete(complete_body)
        except (ToolFailure, KeyError, TypeError, ValueError, UnicodeEncodeError):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if (
            validated_before != before
            or validated_after != after
            or not probe._is_public_string(applied["action_id"])
            or not all(probe._is_bounded_nonnegative_integer(applied[name]) for name in ("candidate_index", "col", "row"))
            or applied["candidate_index"] >= len(candidates)
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        selected = candidates[applied["candidate_index"]]
        expected_selection = get_map_decision_provider(
            str(value["decision_provider"])
        ).choose(candidates, legal_actions)
        if (
            applied != expected_selection
            or applied["action_id"] != f"select:{applied['candidate_index']}"
            or any(applied[name] != selected[source] for name, source in (("col", "col"), ("row", "row"), ("node_kind", "kind")))
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    else:
        if (
            value["screen_kind"] not in ("rest_site", "event")
            or _integer(value["room_ordinal"], 0, 999) < 0
            or not isinstance(value["actions"], list)
            or len(value["actions"]) != _integer(value["accepted_action_count"], 1, 12)
            or not isinstance(value["final"], dict)
            or _integer(value["routes_checked"], 3) < 3
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return value


def _component_actions(value: object, milestone: str, maximum: int) -> int:
    return _integer(_component(value, milestone).get("accepted_action_count"), 1, maximum)


def _destination_from_map(value: object) -> str:
    map_result = _component(value, "r0g_map_selection")
    after = map_result.get("after")
    destination = after.get("destination") if isinstance(after, dict) else None
    kind = destination.get("kind") if isinstance(destination, dict) else None
    applied = map_result["applied"]
    if (
        type(kind) is not str
        or kind not in _DESTINATION_KINDS
        or not isinstance(destination, dict)
        or set(destination) != {"candidate_index", "col", "row", "kind"}
        or not isinstance(applied, dict)
        or any(type(applied[name]) is not int for name in ("candidate_index", "col", "row"))
        or applied.get("node_kind") != kind
        or any(applied.get(name) != destination.get(name) for name in ("candidate_index", "col", "row"))
        or any(type(applied[name]) is not str or not applied[name] for name in ("action_id", "kind", "basis"))
    ):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return kind


def _reward_actions(value: object) -> int:
    applied = _component(value, "r0i_reward_resolution").get("applied")
    if not isinstance(applied, list) or len(applied) > 17:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return len(applied)


def _readiness(value: object, *, requires_next_combat: bool) -> None:
    item = _exact_dict(value, {"next_combat_attempts", "reward_attempts", "map_attempts"})
    for name in item:
        _integer(item[name])
    next_combat = _integer(item["next_combat_attempts"])
    if (
        (requires_next_combat and next_combat < 1)
        or (not requires_next_combat and next_combat != 0)
        or _integer(item["reward_attempts"]) < 1
        or _integer(item["map_attempts"]) < 1
    ):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")


def _terminal_outcome(value: object) -> tuple[dict[str, object] | None, str | None, int]:
    if value is None:
        return None, None, 0
    terminal = _component(value, "r0e_complete_combat")
    outcome = terminal.get("outcome")
    if outcome not in ("victory", "defeat"):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return terminal, outcome, _component_actions(terminal, "r0e_complete_combat", 48)


def _room_handoff(value: object) -> tuple[dict[str, object] | None, int, int, int, str | None, dict[str, object] | None]:
    """Return room, combat, and map contributions plus continuation facts."""
    if value is None:
        return None, 0, 0, 0, None, None
    if not isinstance(value, dict):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    required = {"after_floor", "destination_kind", "expected_screen_kind", "preflight", "room", "map_attempts"}
    optional = {"post_room_map", "next_combat_attempts", "next_combat"}
    if set(value) not in (required, required | optional):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    after_floor = _integer(value["after_floor"], 1, 3)
    kind = value["destination_kind"]
    screen = value["expected_screen_kind"]
    if type(kind) is not str or kind not in _DESTINATION_KINDS or screen not in ("rest_site", "event"):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if (kind == "rest_site" and screen != "rest_site") or (kind in ("ancient", "unknown") and screen != "event") or kind not in ("rest_site", "ancient", "unknown"):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    preflight = _exact_dict(value["preflight"], {"attempts", "screen_kind", "room_ordinal"})
    if _integer(preflight["attempts"], 1) < 1 or preflight["screen_kind"] != screen:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    _integer(preflight["room_ordinal"], 0, 999)
    room_result = _component(value["room"], "r0i_room_interaction")
    try:
        summarize_room_result(room_result)
    except ToolFailure:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    room_actions = _component_actions(room_result, "r0i_room_interaction", 12)
    if room_result.get("screen_kind") != screen or room_result.get("room_ordinal") != preflight["room_ordinal"]:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    _integer(value["map_attempts"], 1)
    if set(value) == required:
        return value, room_actions, 0, 0, None, None
    post_map = value["post_room_map"]
    next_combat = value["next_combat"]
    if post_map is None or next_combat is None:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    post_kind = _destination_from_map(post_map)
    if post_kind not in ("monster", "elite"):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    _integer(value.get("next_combat_attempts"), 1)
    continuation = _component(next_combat, "r0e_complete_combat")
    continuation_actions = _component_actions(continuation, "r0e_complete_combat", 48)
    outcome = continuation.get("outcome")
    if outcome not in ("victory", "defeat"):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return value, room_actions, 1, continuation_actions, post_kind, continuation


def _summarize_run_acceptance_result(result: object) -> dict[str, object]:
    """Validate a bounded-run result and return its minimal safe aggregate.

    The input is retained only while this function executes.  The returned
    dictionary intentionally cannot contain provider names, nested component
    records, identities, payloads, hashes, or arbitrary producer text.
    """
    if not isinstance(result, dict):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    milestone = result.get("milestone")
    if type(milestone) is not str or milestone not in _RUN_MILESTONES:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    common = {
        "schema_version", "status", "milestone", "providers", "floor_limit",
        "completed_floor_count", "action_totals", "readiness", "floors",
        "terminal_combat", "room_handoff", "termination",
    }
    entry_only = {"entry_phase", "processed_floor_count", "entry_prefix"}
    expected = common | (entry_only if milestone == "r0i_bounded_run_entry" else set())
    if (
        set(result) != expected
        or type(result.get("schema_version")) is not int
        or result.get("schema_version") != 1
        or result.get("status") != "passed"
    ):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    floor_limit = _integer(result["floor_limit"], 1, 3)
    providers = _exact_dict(result["providers"], {"combat", "reward", "map", "room"})
    if (
        any(type(item) is not str for item in providers.values())
        or providers["combat"] not in provider_names()
        or providers["reward"] not in reward_client._PROVIDERS
        or providers["map"] not in map_provider_names()
        or providers["room"] != room._ROOM_PROVIDER
    ):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    floors = result["floors"]
    readiness = result["readiness"]
    if not isinstance(floors, list) or not isinstance(readiness, list) or len(readiness) != len(floors):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    completed = _integer(result["completed_floor_count"], 0, floor_limit)
    if completed != len(floors):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    expected_floor = 1 if milestone == "r0i_bounded_run" else 2
    selected_destinations: dict[int, str] = {}
    combat_actions = reward_actions = 0
    for floor, ready in zip(floors, readiness):
        item = _exact_dict(floor, {"floor_number", "destination_kind", "combat", "reward", "map"})
        if _integer(item["floor_number"], 1, 3) != expected_floor:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        expected_floor += 1
        kind = item["destination_kind"]
        if type(kind) is not str or kind not in _DESTINATION_KINDS or _destination_from_map(item["map"]) != kind:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        selected_destinations[int(item["floor_number"])] = kind
        combat = _component(item["combat"], "r0e_complete_combat")
        if combat.get("outcome") != "victory" or combat.get("decision_provider") != providers["combat"]:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        combat_actions += _component_actions(combat, "r0e_complete_combat", 48)
        reward = _component(item["reward"], "r0i_reward_resolution")
        reward_before = reward.get("before")
        reward_player = (
            reward_before.get("player")
            if isinstance(reward_before, dict)
            else None
        )
        if (
            reward.get("decision_provider") != providers["reward"]
            or _component(item["map"], "r0g_map_selection").get(
                "decision_provider"
            ) != providers["map"]
            or not run_client._has_bounded_post_combat_player_transition(
                combat.get("final_player"), reward_player
            )
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        reward_actions += len(reward["applied"])
        _readiness(ready, requires_next_combat=int(item["floor_number"]) > 1)

    prefix_reward_actions = 0
    prefix_map_actions = 0
    processed: int
    entry_phase = "combat"
    if milestone == "r0i_bounded_run_entry":
        entry_phase = result["entry_phase"]
        prefix = _exact_dict(
            result["entry_prefix"],
            {"floor_number", "destination_kind", "observed_phases", "unavailable_phases", "combat", "reward", "map", "readiness"},
        )
        if entry_phase not in ("reward", "map") or _integer(prefix["floor_number"], 1, 1) != 1:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        prefix_kind = prefix["destination_kind"]
        if type(prefix_kind) is not str or prefix_kind not in _DESTINATION_KINDS or _destination_from_map(prefix["map"]) != prefix_kind:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if _component(prefix["map"], "r0g_map_selection").get("decision_provider") != providers["map"]:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        selected_destinations[1] = prefix_kind
        if prefix["combat"] is not None:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        expected_observed = ["reward", "map"] if entry_phase == "reward" else ["map"]
        expected_unavailable = ["combat"] if entry_phase == "reward" else ["combat", "reward"]
        if prefix["observed_phases"] != expected_observed or prefix["unavailable_phases"] != expected_unavailable:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if entry_phase == "reward":
            if _component(prefix["reward"], "r0i_reward_resolution").get("decision_provider") != providers["reward"]:
                fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
            prefix_reward_actions = _reward_actions(prefix["reward"])
        elif prefix["reward"] is not None:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        prefix_ready = _exact_dict(prefix["readiness"], {"next_combat_attempts", "reward_attempts", "map_attempts"})
        if _integer(prefix_ready["next_combat_attempts"]) != 0:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if entry_phase == "reward" and (
            _integer(prefix_ready["reward_attempts"]) != 0
            or _integer(prefix_ready["map_attempts"], 1) < 1
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if entry_phase == "map" and (
            _integer(prefix_ready["reward_attempts"]) != 0
            or _integer(prefix_ready["map_attempts"]) != 0
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        prefix_map_actions = 1
        processed = _integer(result["processed_floor_count"], 1, floor_limit)
    else:
        processed = 0

    handoff, room_actions, handoff_maps, continuation_actions, handoff_kind, continuation = _room_handoff(result["room_handoff"])
    terminal, terminal_outcome, terminal_actions = _terminal_outcome(result["terminal_combat"])
    if terminal is not None and terminal.get("decision_provider") != providers["combat"]:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if handoff is not None:
        if _component(handoff["room"], "r0i_room_interaction").get("decision_provider") != providers["room"]:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if handoff.get("post_room_map") is not None and _component(handoff["post_room_map"], "r0g_map_selection").get("decision_provider") != providers["map"]:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if continuation is not None and continuation.get("decision_provider") != providers["combat"]:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if terminal is not None and continuation is not None:
        if terminal != continuation or terminal_outcome != continuation.get("outcome") or terminal_actions != continuation_actions:
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        terminal_actions = 0  # The terminal is the same accepted continuation action trace.
    computed_map_actions = len(floors) + prefix_map_actions + handoff_maps
    if milestone == "r0i_bounded_run":
        processed = computed_map_actions
    if processed != computed_map_actions or processed > floor_limit:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    selection_count = len(selected_destinations)
    if (
        set(selected_destinations) != set(range(1, selection_count + 1))
        or any(
            selected_destinations[index] not in _COMBAT_DESTINATION_KINDS
            for index in range(1, selection_count)
        )
        or (
            handoff is not None
            and (
                selection_count < 1
                or handoff.get("after_floor") != selection_count
                or handoff.get("destination_kind")
                != selected_destinations[selection_count]
            )
        )
    ):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    totals = _exact_dict(result["action_totals"], set(_ACTION_TOTAL_NAMES))
    computed = {
        "combat": combat_actions + continuation_actions + terminal_actions,
        "reward": reward_actions + prefix_reward_actions,
        "map": computed_map_actions,
        "room": room_actions,
    }
    computed["total"] = sum(computed.values())
    if any(_integer(totals[name]) != computed[name] for name in _ACTION_TOTAL_NAMES):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    termination = _exact_dict(result["termination"], {"reason", "after_floor", "destination_kind"})
    reason, after_floor, destination = termination["reason"], _integer(termination["after_floor"], 0, floor_limit), termination["destination_kind"]
    if (
        type(reason) is not str
        or reason not in _TERMINATION_REASONS
        or (destination is not None and (type(destination) is not str or destination not in _DESTINATION_KINDS))
    ):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if reason == "run_defeat":
        normal_defeat = continuation is None
        if destination is not None or terminal_outcome != "defeat":
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if normal_defeat and (
            handoff is not None
            or after_floor != processed
            or processed >= floor_limit
            or selection_count != processed
            or (
                after_floor > 0
                and selected_destinations.get(after_floor)
                not in _COMBAT_DESTINATION_KINDS
            )
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
        if not normal_defeat and (
            handoff is None
            or terminal != continuation
            or after_floor != handoff.get("after_floor")
            or selection_count != after_floor
            or processed != after_floor + 1
            or after_floor >= floor_limit
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif terminal is not None:
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    if reason == "floor_limit_reached":
        if (
            handoff is not None
            or destination is None
            or destination in _ROOM_DESTINATION_KINDS
            or after_floor != floor_limit
            or processed != floor_limit
            or selection_count != processed
            or destination != selected_destinations.get(after_floor)
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif reason == "act_boundary_reached":
        if (
            handoff is not None
            or terminal is not None
            or destination != "boss"
            or after_floor != processed
            or processed >= floor_limit
            or selection_count != processed
            or destination != selected_destinations.get(after_floor)
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif reason == "unsupported_destination_kind":
        if (
            handoff is not None
            or terminal is not None
            or destination not in ("shop", "treasure")
            or after_floor != processed
            or processed >= floor_limit
            or selection_count != processed
            or destination != selected_destinations.get(after_floor)
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif reason == "room_handoff_complete":
        if (
            handoff is None
            or continuation is not None
            or destination != handoff.get("destination_kind")
            or after_floor != handoff.get("after_floor")
            or after_floor != processed
            or processed != floor_limit
            or selection_count != processed
            or destination != selected_destinations.get(after_floor)
            or (destination == "rest_site" and handoff.get("expected_screen_kind") != "rest_site")
            or (destination in ("ancient", "unknown") and handoff.get("expected_screen_kind") != "event")
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    elif reason == "room_continuation_complete":
        if (
            handoff is None
            or continuation is None
            or continuation.get("outcome") != "victory"
            or destination != handoff_kind
            or after_floor != handoff.get("after_floor")
            or selection_count != after_floor
            or after_floor + 1 != processed
            or after_floor >= floor_limit
        ):
            fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
    return {
        "schema_version": 1,
        "status": "passed",
        "milestone": "r0i_bounded_run_acceptance",
        "source_milestone": milestone,
        "entry_phase": entry_phase,
        "processed_floor_count": processed,
        "completed_floor_count": completed,
        "action_totals": computed,
        "termination": {"reason": reason, "after_floor": after_floor, "destination_kind": destination},
        "terminal_combat_outcome": terminal_outcome,
    }


def summarize_run_acceptance_result(result: object) -> dict[str, object]:
    """Fail closed with one public code for every malformed summary record."""
    try:
        return _summarize_run_acceptance_result(result)
    except ToolFailure:
        raise
    except (KeyError, TypeError, ValueError, OverflowError):
        fail(EXIT_MISMATCH, "run_acceptance_result_mismatch")
