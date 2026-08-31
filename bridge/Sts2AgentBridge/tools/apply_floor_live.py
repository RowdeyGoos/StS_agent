#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import time
from pathlib import Path
from typing import Any, Callable

import apply_combat_live as combat_client
import apply_map_live as map_client
import apply_reward_live as reward_client
import probe_live as probe
from decision_providers import map_provider_names, provider_names
from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    ToolFailure,
    absolute_path,
    fail,
    main,
)

_PHASE_READY_DEADLINE_SECONDS = 30.0
_POLL_SECONDS = 0.1


def parse_args(arguments: list[str] | None = None) -> tuple[str, int, str, str, str]:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 10:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    allowed = frozenset(
        (
            "--user-profile",
            "--effective-uid",
            "--combat-provider",
            "--reward-provider",
            "--map-provider",
        )
    )
    parsed: dict[str, str] = {}
    for offset in range(0, len(values), 2):
        name = values[offset]
        if name not in allowed or name in parsed:
            fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
        parsed[name] = values[offset + 1]
    if set(parsed) != allowed:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    if parsed["--combat-provider"] not in provider_names():
        fail(EXIT_INVALID_INVOCATION, "invalid_combat_provider")
    if parsed["--reward-provider"] not in reward_client._PROVIDERS:
        fail(EXIT_INVALID_INVOCATION, "invalid_reward_provider")
    if parsed["--map-provider"] not in map_provider_names():
        fail(EXIT_INVALID_INVOCATION, "invalid_map_provider")
    return (
        parsed["--user-profile"],
        probe._parse_effective_uid(parsed["--effective-uid"]),
        parsed["--combat-provider"],
        parsed["--reward-provider"],
        parsed["--map-provider"],
    )


def _wait_for_reward_ready(
    credential: bytearray,
    connector: Callable[[], Any],
) -> int:
    deadline = time.monotonic() + _PHASE_READY_DEADLINE_SECONDS
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        body = reward_client._read_body(
            "reward",
            probe._REWARD_ROUTE[0][1],
            credential,
            connector,
            deadline,
        )
        if body == reward_client._REWARD_WAITING:
            time.sleep(_POLL_SECONDS)
            continue
        if body == reward_client._REWARD_UNSUPPORTED:
            fail(EXIT_MISMATCH, "reward_state_unsupported")
        reward_client._validate_ready(body)
        return attempts
    fail(EXIT_MISMATCH, "reward_ready_timeout")


def _wait_for_map_ready(
    credential: bytearray,
    connector: Callable[[], Any],
) -> int:
    deadline = time.monotonic() + _PHASE_READY_DEADLINE_SECONDS
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        body = map_client._read_body(
            "map",
            map_client._MAP_DECISION_ROUTE,
            credential,
            connector,
            deadline,
        )
        if body == map_client._MAP_WAITING:
            time.sleep(_POLL_SECONDS)
            continue
        if body == map_client._MAP_UNSUPPORTED:
            fail(EXIT_MISMATCH, "map_state_unsupported")
        try:
            map_client._validate_ready(body)
        except ToolFailure as failure:
            if failure.error_code != "map_response_mismatch":
                raise
            # The accepted destination from the previous floor can remain
            # observable briefly while the next map decision is materialized.
            # Accept only the strict completed-map shape as a transient state.
            map_client._validate_complete(body)
            time.sleep(_POLL_SECONDS)
            continue
        return attempts
    fail(EXIT_MISMATCH, "map_ready_timeout")


def _with_credential(
    credential_loader: Callable[[], bytearray],
    operation: Callable[..., object],
    *arguments: object,
) -> object:
    credential = credential_loader()
    try:
        return operation(credential, *arguments)
    finally:
        probe._zero(credential)


def _require_component(
    value: object,
    milestone: str,
    code: str,
) -> dict[str, object]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("status") != "passed"
        or value.get("milestone") != milestone
    ):
        fail(EXIT_MISMATCH, code)
    return value


def _run_floor(
    credential_loader: Callable[[], bytearray],
    connector: Callable[[], Any],
    combat_provider: str,
    reward_provider: str,
    map_provider: str,
    *,
    combat_runner: Callable[[bytearray, str, Callable[[], Any]], dict[str, object]] =
        combat_client._run_apply_combat,
    reward_waiter: Callable[[bytearray, Callable[[], Any]], int] = _wait_for_reward_ready,
    reward_runner: Callable[[bytearray, str, Callable[[], Any]], dict[str, object]] =
        reward_client._run_apply_reward,
    map_waiter: Callable[[bytearray, Callable[[], Any]], int] = _wait_for_map_ready,
    map_runner: Callable[[bytearray, str, Callable[[], Any]], dict[str, object]] =
        map_client._run_apply_map,
) -> dict[str, object]:
    combat = _require_component(
        _with_credential(credential_loader, combat_runner, combat_provider, connector),
        "r0e_complete_combat",
        "floor_combat_result_mismatch",
    )
    if combat.get("outcome") != "victory":
        fail(EXIT_MISMATCH, "floor_combat_not_victory")

    reward_wait_attempts = _with_credential(
        credential_loader,
        reward_waiter,
        connector,
    )
    if type(reward_wait_attempts) is not int or reward_wait_attempts < 1:
        fail(EXIT_INTERNAL, "internal_failure")
    reward = _require_component(
        _with_credential(credential_loader, reward_runner, reward_provider, connector),
        "r0i_reward_resolution",
        "floor_reward_result_mismatch",
    )

    final_player = combat.get("final_player")
    reward_before = reward.get("before")
    reward_player = reward_before.get("player") if isinstance(reward_before, dict) else None
    if (
        not isinstance(final_player, dict)
        or not isinstance(reward_player, dict)
        or final_player.get("hp") != reward_player.get("hp")
        or final_player.get("max_hp") != reward_player.get("max_hp")
    ):
        fail(EXIT_MISMATCH, "floor_player_continuity_mismatch")

    map_wait_attempts = _with_credential(
        credential_loader,
        map_waiter,
        connector,
    )
    if type(map_wait_attempts) is not int or map_wait_attempts < 1:
        fail(EXIT_INTERNAL, "internal_failure")
    map_result = _require_component(
        _with_credential(credential_loader, map_runner, map_provider, connector),
        "r0g_map_selection",
        "floor_map_result_mismatch",
    )

    return {
        "schema_version": 1,
        "status": "passed",
        "milestone": "r0h_one_floor",
        "providers": {
            "combat": combat_provider,
            "reward": reward_provider,
            "map": map_provider,
        },
        "phases": ["combat_victory", "reward_resolved", "map_node_selected"],
        "readiness": {
            "reward_attempts": reward_wait_attempts,
            "map_attempts": map_wait_attempts,
        },
        "combat": combat,
        "reward": reward,
        "map": map_result,
    }


def _operation() -> dict[str, object]:
    profile_value, supplied_uid, combat_provider, reward_provider, map_provider = parse_args()
    user_profile: Path = absolute_path(profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)

    def credential_loader() -> bytearray:
        return probe._load_fixed_credential(user_profile, uid)

    return _run_floor(
        credential_loader,
        probe._literal_loopback_connector,
        combat_provider,
        reward_provider,
        map_provider,
    )


def operation() -> dict[str, object]:
    try:
        return _operation()
    except ToolFailure:
        raise
    except Exception:
        fail(EXIT_INTERNAL, "internal_failure")


if __name__ == "__main__":
    main(operation)
