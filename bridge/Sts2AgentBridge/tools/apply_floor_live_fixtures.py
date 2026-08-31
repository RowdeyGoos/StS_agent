#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json

import apply_floor_live as floor
from tool_common import EXIT_INVALID_INVOCATION, EXIT_MISMATCH, ToolFailure, fail, main

_CREDENTIAL = b"0123456789abcdef" * 4


class CredentialLoader:
    def __init__(self) -> None:
        self.values: list[bytearray] = []

    def __call__(self) -> bytearray:
        value = bytearray(_CREDENTIAL)
        self.values.append(value)
        return value

    def require_zeroed(self) -> None:
        if not self.values or any(any(value) for value in self.values):
            fail(EXIT_MISMATCH, "floor_fixture_credential_cleanup")


def _component(milestone: str, **values: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "passed",
        "milestone": milestone,
        **values,
    }


def _map_body(status: str) -> bytes:
    complete = status == "complete"
    candidate = {
        "candidate_index": 0,
        "col": 0,
        "row": 1,
        "kind": "monster",
    }
    return json.dumps(
        {
            "schema_version": 1,
            "status": status,
            "decision_kind": "map",
            "actionable": not complete,
            "decision_id": None if complete else "0" * 64,
            "screen_kind": "room" if complete else "map",
            "destination": candidate if complete else None,
            "candidates": [] if complete else [candidate],
            "legal_actions": []
            if complete
            else [
                {
                    "action_id": "select:0",
                    "kind": "select_map_node",
                    "candidate_index": 0,
                }
            ],
        },
        separators=(",", ":"),
    ).encode("ascii")


def _run_completed_map_transition() -> None:
    credential = bytearray(_CREDENTIAL)
    connector = object()
    responses = iter((_map_body("complete"), _map_body("ready")))
    original_read = floor.map_client._read_body
    original_sleep = floor.time.sleep

    def read_body(
        label: str,
        route: str,
        supplied_credential: bytearray,
        supplied_connector: object,
        deadline: float,
    ) -> bytes:
        del deadline
        if (
            label != "map"
            or route != floor.map_client._MAP_DECISION_ROUTE
            or supplied_credential is not credential
            or supplied_connector is not connector
        ):
            fail(EXIT_MISMATCH, "floor_fixture_completed_map_arguments")
        return next(responses)

    floor.map_client._read_body = read_body  # type: ignore[assignment]
    floor.time.sleep = lambda _: None
    try:
        attempts = floor._wait_for_map_ready(
            credential,
            connector,  # type: ignore[arg-type]
        )
    finally:
        floor.map_client._read_body = original_read
        floor.time.sleep = original_sleep

    if attempts != 2:
        fail(EXIT_MISMATCH, "floor_fixture_completed_map_attempts")


def _run_retryable_map_transition() -> None:
    credential = bytearray(_CREDENTIAL)
    connector = object()
    responses: list[bytes | ToolFailure] = [
        ToolFailure(EXIT_MISMATCH, "map_backend_retryable"),
        _map_body("ready"),
    ]
    original_read = floor.map_client._read_body
    original_sleep = floor.time.sleep

    def read_body(*_: object) -> bytes:
        value = responses.pop(0)
        if isinstance(value, ToolFailure):
            raise value
        return value

    floor.map_client._read_body = read_body  # type: ignore[assignment]
    floor.time.sleep = lambda _: None
    try:
        attempts = floor._wait_for_map_ready(
            credential,
            connector,  # type: ignore[arg-type]
        )
    finally:
        floor.map_client._read_body = original_read
        floor.time.sleep = original_sleep
    if attempts != 2 or responses:
        fail(EXIT_MISMATCH, "floor_fixture_retryable_map_attempts")


def _run_success() -> None:
    loader = CredentialLoader()
    calls: list[str] = []
    connector = object()

    def combat_runner(credential: bytearray, provider: str, supplied: object) -> dict[str, object]:
        if bytes(credential) != _CREDENTIAL or provider != "heuristic" or supplied is not connector:
            fail(EXIT_MISMATCH, "floor_fixture_combat_arguments")
        calls.append("combat")
        return _component(
            "r0e_complete_combat",
            outcome="victory",
            final_player={"hp": 71, "max_hp": 80},
        )

    def reward_waiter(credential: bytearray, supplied: object) -> int:
        if bytes(credential) != _CREDENTIAL or supplied is not connector:
            fail(EXIT_MISMATCH, "floor_fixture_reward_wait_arguments")
        calls.append("reward_wait")
        return 3

    def reward_runner(credential: bytearray, provider: str, supplied: object) -> dict[str, object]:
        if bytes(credential) != _CREDENTIAL or provider != "skip" or supplied is not connector:
            fail(EXIT_MISMATCH, "floor_fixture_reward_arguments")
        calls.append("reward")
        return _component(
            "r0i_reward_resolution",
            before={"player": {"hp": 71, "max_hp": 80}},
        )

    def map_waiter(credential: bytearray, supplied: object) -> int:
        if bytes(credential) != _CREDENTIAL or supplied is not connector:
            fail(EXIT_MISMATCH, "floor_fixture_map_wait_arguments")
        calls.append("map_wait")
        return 2

    def map_runner(credential: bytearray, provider: str, supplied: object) -> dict[str, object]:
        if bytes(credential) != _CREDENTIAL or provider != "first" or supplied is not connector:
            fail(EXIT_MISMATCH, "floor_fixture_map_arguments")
        calls.append("map")
        return _component(
            "r0g_map_selection",
            applied={"action_id": "select:0", "node_kind": "monster"},
        )

    payload = floor._run_floor(
        loader,
        connector,  # type: ignore[arg-type]
        "heuristic",
        "skip",
        "first",
        combat_runner=combat_runner,  # type: ignore[arg-type]
        reward_waiter=reward_waiter,  # type: ignore[arg-type]
        reward_runner=reward_runner,  # type: ignore[arg-type]
        map_waiter=map_waiter,  # type: ignore[arg-type]
        map_runner=map_runner,  # type: ignore[arg-type]
    )
    if (
        payload.get("milestone") != "r0h_one_floor"
        or payload.get("phases")
        != ["combat_victory", "reward_resolved", "map_node_selected"]
        or payload.get("readiness") != {"reward_attempts": 3, "map_attempts": 2}
        or calls != ["combat", "reward_wait", "reward", "map_wait", "map"]
    ):
        fail(EXIT_MISMATCH, "floor_fixture_success_payload")
    loader.require_zeroed()


def _expect_floor_failure(
    expected_code: str,
    combat: dict[str, object],
    reward: dict[str, object],
) -> None:
    loader = CredentialLoader()
    later_called = False

    def combat_runner(*_: object) -> dict[str, object]:
        return combat

    def reward_waiter(*_: object) -> int:
        return 1

    def reward_runner(*_: object) -> dict[str, object]:
        return reward

    def forbidden(*_: object) -> object:
        nonlocal later_called
        later_called = True
        return {}

    try:
        floor._run_floor(
            loader,
            forbidden,  # type: ignore[arg-type]
            "heuristic",
            "skip",
            "first",
            combat_runner=combat_runner,  # type: ignore[arg-type]
            reward_waiter=reward_waiter,  # type: ignore[arg-type]
            reward_runner=reward_runner,  # type: ignore[arg-type]
            map_waiter=forbidden,  # type: ignore[arg-type]
            map_runner=forbidden,  # type: ignore[arg-type]
        )
    except ToolFailure as failure:
        if failure.exit_code != EXIT_MISMATCH or failure.error_code != expected_code:
            fail(EXIT_MISMATCH, "floor_fixture_wrong_failure")
    else:
        fail(EXIT_MISMATCH, "floor_fixture_unexpected_pass")
    if later_called:
        fail(EXIT_MISMATCH, "floor_fixture_fail_stop")
    loader.require_zeroed()


def _expect_invocation_failure(arguments: list[str], expected_code: str) -> None:
    try:
        floor.parse_args(arguments)
    except ToolFailure as failure:
        if failure.exit_code == EXIT_INVALID_INVOCATION and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "floor_fixture_wrong_invocation_failure")
    fail(EXIT_MISMATCH, "floor_fixture_invocation_passed")


def operation() -> dict[str, object]:
    _run_success()
    _run_completed_map_transition()
    _run_retryable_map_transition()
    _expect_floor_failure(
        "floor_combat_not_victory",
        _component(
            "r0e_complete_combat",
            outcome="defeat",
            final_player={"hp": 0, "max_hp": 80},
        ),
        {},
    )
    _expect_floor_failure(
        "floor_player_continuity_mismatch",
        _component(
            "r0e_complete_combat",
            outcome="victory",
            final_player={"hp": 71, "max_hp": 80},
        ),
        _component(
            "r0i_reward_resolution",
            before={"player": {"hp": 70, "max_hp": 80}},
        ),
    )

    base = [
        "--user-profile",
        "/synthetic-profile",
        "--effective-uid",
        "501",
        "--combat-provider",
        "heuristic",
        "--reward-provider",
        "skip",
        "--map-provider",
        "first",
    ]
    if floor.parse_args(base) != ("/synthetic-profile", 501, "heuristic", "skip", "first"):
        fail(EXIT_MISMATCH, "floor_fixture_parse")
    invalid_combat = list(base)
    invalid_combat[5] = "unknown"
    _expect_invocation_failure(invalid_combat, "invalid_combat_provider")
    invalid_reward = list(base)
    invalid_reward[7] = "choose"
    _expect_invocation_failure(invalid_reward, "invalid_reward_provider")
    invalid_map = list(base)
    invalid_map[9] = "unknown"
    _expect_invocation_failure(invalid_map, "invalid_map_provider")

    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_floor_live_fixtures",
        "checks": [
            "one_floor_sequence",
            "completed_map_transition",
            "retryable_map_transition",
            "combat_defeat_fail_stop",
            "player_continuity_fail_stop",
            "provider_surface",
        ],
        "check_count": 6,
    }


if __name__ == "__main__":
    main(operation)
