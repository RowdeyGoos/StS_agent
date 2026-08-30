#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import time
from pathlib import Path
from typing import Any, Callable

import apply_combat_live as combat_client
import apply_floor_live as floor_client
import apply_map_live as map_client
import apply_reward_live as reward_client
import apply_one_live as action_client
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

_MAXIMUM_FLOORS = 3
_NEXT_COMBAT_READY_DEADLINE_SECONDS = 30.0
_POLL_SECONDS = 0.1
_ACT_BOUNDARY_KINDS = frozenset(("boss", "ancient"))


def parse_args(
    arguments: list[str] | None = None,
) -> tuple[str, int, str, str, str, int]:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 12:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    allowed = frozenset(
        (
            "--user-profile",
            "--effective-uid",
            "--combat-provider",
            "--reward-provider",
            "--map-provider",
            "--floor-limit",
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
    floor_limit_text = parsed["--floor-limit"]
    if floor_limit_text not in tuple(str(value) for value in range(1, _MAXIMUM_FLOORS + 1)):
        fail(EXIT_INVALID_INVOCATION, "invalid_floor_limit")
    return (
        parsed["--user-profile"],
        probe._parse_effective_uid(parsed["--effective-uid"]),
        parsed["--combat-provider"],
        parsed["--reward-provider"],
        parsed["--map-provider"],
        int(floor_limit_text),
    )


def _wait_for_next_combat_ready(
    credential: bytearray,
    decision_provider: str,
    connector: Callable[[], Any],
    *,
    body_reader: Callable[..., bytes] = action_client._read_body,
) -> int:
    deadline = time.monotonic() + _NEXT_COMBAT_READY_DEADLINE_SECONDS
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        body = body_reader(
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
            fail(EXIT_MISMATCH, "next_combat_state_unsupported")
        with memoryview(body) as view:
            if body.startswith(probe._COMBAT_COMPLETE_PREFIX):
                probe._validate_combat_terminal(view)
                time.sleep(_POLL_SECONDS)
                continue
            probe._validate_combat(view, decision_provider)
        return attempts
    fail(EXIT_MISMATCH, "next_combat_ready_timeout")


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


def _termination(reason: str, after_floor: int, destination_kind: str | None) -> dict[str, object]:
    return {
        "reason": reason,
        "after_floor": after_floor,
        "destination_kind": destination_kind,
    }


def _result(
    combat_provider: str,
    reward_provider: str,
    map_provider: str,
    floor_limit: int,
    floors: list[dict[str, object]],
    terminal_combat: dict[str, object] | None,
    readiness: list[dict[str, int]],
    termination: dict[str, object],
) -> dict[str, object]:
    combat_actions = sum(
        int(item["combat"].get("accepted_action_count", 0))
        for item in floors
        if isinstance(item.get("combat"), dict)
    )
    if terminal_combat is not None:
        combat_actions += int(terminal_combat.get("accepted_action_count", 0))
    reward_actions = 0
    for floor in floors:
        reward = floor.get("reward")
        applied = reward.get("applied") if isinstance(reward, dict) else None
        if not isinstance(applied, list):
            fail(EXIT_INTERNAL, "internal_failure")
        reward_actions += len(applied)
    map_actions = len(floors)
    return {
        "schema_version": 1,
        "status": "passed",
        "milestone": "r0i_bounded_run",
        "providers": {
            "combat": combat_provider,
            "reward": reward_provider,
            "map": map_provider,
        },
        "floor_limit": floor_limit,
        "completed_floor_count": len(floors),
        "action_totals": {
            "combat": combat_actions,
            "reward": reward_actions,
            "map": map_actions,
            "total": combat_actions + reward_actions + map_actions,
        },
        "readiness": readiness,
        "floors": floors,
        "terminal_combat": terminal_combat,
        "termination": termination,
    }


def _destination_kind(map_result: dict[str, object]) -> str:
    after = map_result.get("after")
    destination = after.get("destination") if isinstance(after, dict) else None
    kind = destination.get("kind") if isinstance(destination, dict) else None
    if not isinstance(kind, str) or kind not in map_client._NODE_KINDS:
        fail(EXIT_MISMATCH, "run_map_destination_mismatch")
    return kind


def _run_bounded_run(
    credential_loader: Callable[[], bytearray],
    connector: Callable[[], Any],
    combat_provider: str,
    reward_provider: str,
    map_provider: str,
    floor_limit: int,
    *,
    combat_runner: Callable[[bytearray, str, Callable[[], Any]], dict[str, object]] =
        combat_client._run_apply_combat,
    reward_waiter: Callable[[bytearray, Callable[[], Any]], int] =
        floor_client._wait_for_reward_ready,
    reward_runner: Callable[[bytearray, str, Callable[[], Any]], dict[str, object]] =
        reward_client._run_apply_reward,
    map_waiter: Callable[[bytearray, Callable[[], Any]], int] =
        floor_client._wait_for_map_ready,
    map_runner: Callable[[bytearray, str, Callable[[], Any]], dict[str, object]] =
        map_client._run_apply_map,
    next_combat_waiter: Callable[[bytearray, str, Callable[[], Any]], int] =
        _wait_for_next_combat_ready,
) -> dict[str, object]:
    if type(floor_limit) is not int or not 1 <= floor_limit <= _MAXIMUM_FLOORS:
        fail(EXIT_INTERNAL, "internal_failure")

    floors: list[dict[str, object]] = []
    readiness: list[dict[str, int]] = []
    for floor_number in range(1, floor_limit + 1):
        next_combat_attempts = 0
        if floor_number > 1:
            observed = _with_credential(
                credential_loader,
                next_combat_waiter,
                combat_provider,
                connector,
            )
            if type(observed) is not int or observed < 1:
                fail(EXIT_INTERNAL, "internal_failure")
            next_combat_attempts = observed

        combat = _require_component(
            _with_credential(credential_loader, combat_runner, combat_provider, connector),
            "r0e_complete_combat",
            "run_combat_result_mismatch",
        )
        outcome = combat.get("outcome")
        if outcome == "defeat":
            return _result(
                combat_provider,
                reward_provider,
                map_provider,
                floor_limit,
                floors,
                combat,
                readiness,
                _termination("run_defeat", len(floors), None),
            )
        if outcome != "victory":
            fail(EXIT_MISMATCH, "run_combat_outcome_mismatch")

        reward_attempts = _with_credential(credential_loader, reward_waiter, connector)
        if type(reward_attempts) is not int or reward_attempts < 1:
            fail(EXIT_INTERNAL, "internal_failure")
        reward = _require_component(
            _with_credential(credential_loader, reward_runner, reward_provider, connector),
            "r0i_reward_resolution",
            "run_reward_result_mismatch",
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
            fail(EXIT_MISMATCH, "run_player_continuity_mismatch")

        map_attempts = _with_credential(credential_loader, map_waiter, connector)
        if type(map_attempts) is not int or map_attempts < 1:
            fail(EXIT_INTERNAL, "internal_failure")
        map_result = _require_component(
            _with_credential(credential_loader, map_runner, map_provider, connector),
            "r0g_map_selection",
            "run_map_result_mismatch",
        )
        kind = _destination_kind(map_result)
        ready = {
            "next_combat_attempts": next_combat_attempts,
            "reward_attempts": reward_attempts,
            "map_attempts": map_attempts,
        }
        readiness.append(ready)
        floors.append(
            {
                "floor_number": floor_number,
                "destination_kind": kind,
                "combat": combat,
                "reward": reward,
                "map": map_result,
            }
        )

        if floor_number == floor_limit:
            return _result(
                combat_provider,
                reward_provider,
                map_provider,
                floor_limit,
                floors,
                None,
                readiness,
                _termination("floor_limit_reached", floor_number, kind),
            )
        if kind == "monster":
            continue
        if kind in _ACT_BOUNDARY_KINDS:
            reason = "act_boundary_reached"
        else:
            reason = "unsupported_destination_kind"
        return _result(
            combat_provider,
            reward_provider,
            map_provider,
            floor_limit,
            floors,
            None,
            readiness,
            _termination(reason, floor_number, kind),
        )

    fail(EXIT_INTERNAL, "internal_failure")


def _operation() -> dict[str, object]:
    (
        profile_value,
        supplied_uid,
        combat_provider,
        reward_provider,
        map_provider,
        floor_limit,
    ) = parse_args()
    user_profile: Path = absolute_path(profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)

    def credential_loader() -> bytearray:
        return probe._load_fixed_credential(user_profile, uid)

    return _run_bounded_run(
        credential_loader,
        probe._literal_loopback_connector,
        combat_provider,
        reward_provider,
        map_provider,
        floor_limit,
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
