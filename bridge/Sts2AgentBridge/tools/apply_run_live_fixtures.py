#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import apply_combat_live_fixtures as combat_fixture
import apply_run_live as run
import apply_turn_live_fixtures as turn_fixture
import probe_live as probe
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
            fail(EXIT_MISMATCH, "run_fixture_credential_cleanup")


def _component(milestone: str, **values: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "passed",
        "milestone": milestone,
        **values,
    }


def _combat(outcome: str = "victory", hp: int = 70, actions: int = 5) -> dict[str, object]:
    return _component(
        "r0e_complete_combat",
        outcome=outcome,
        accepted_action_count=actions,
        final_player={"hp": hp, "max_hp": 80},
    )


def _reward(hp: int = 70) -> dict[str, object]:
    return _component(
        "r0i_reward_resolution",
        before={"player": {"hp": hp, "max_hp": 80}},
        applied=[{"action_id": "proceed"}],
    )


def _map(kind: str) -> dict[str, object]:
    return _component(
        "r0g_map_selection",
        after={
            "destination": {
                "candidate_index": 0,
                "col": 1,
                "row": 1,
                "kind": kind,
            }
        },
    )


def _run_sequence(
    destinations: list[str],
    floor_limit: int,
    *,
    defeat_on_combat: int | None = None,
) -> tuple[dict[str, object], list[str], CredentialLoader]:
    loader = CredentialLoader()
    calls: list[str] = []
    combat_number = 0
    map_number = 0
    connector = object()

    def next_waiter(credential: bytearray, provider: str, supplied: object) -> int:
        if bytes(credential) != _CREDENTIAL or provider != "heuristic" or supplied is not connector:
            fail(EXIT_MISMATCH, "run_fixture_next_wait_arguments")
        calls.append("next_wait")
        return 2

    def combat_runner(credential: bytearray, provider: str, supplied: object) -> dict[str, object]:
        nonlocal combat_number
        if bytes(credential) != _CREDENTIAL or provider != "heuristic" or supplied is not connector:
            fail(EXIT_MISMATCH, "run_fixture_combat_arguments")
        combat_number += 1
        calls.append("combat")
        if defeat_on_combat == combat_number:
            return _combat("defeat", 0, 3)
        return _combat(actions=4 + combat_number)

    def reward_waiter(credential: bytearray, supplied: object) -> int:
        if bytes(credential) != _CREDENTIAL or supplied is not connector:
            fail(EXIT_MISMATCH, "run_fixture_reward_wait_arguments")
        calls.append("reward_wait")
        return 3

    def reward_runner(credential: bytearray, provider: str, supplied: object) -> dict[str, object]:
        if bytes(credential) != _CREDENTIAL or provider != "skip" or supplied is not connector:
            fail(EXIT_MISMATCH, "run_fixture_reward_arguments")
        calls.append("reward")
        return _reward()

    def map_waiter(credential: bytearray, supplied: object) -> int:
        if bytes(credential) != _CREDENTIAL or supplied is not connector:
            fail(EXIT_MISMATCH, "run_fixture_map_wait_arguments")
        calls.append("map_wait")
        return 4

    def map_runner(credential: bytearray, provider: str, supplied: object) -> dict[str, object]:
        nonlocal map_number
        if bytes(credential) != _CREDENTIAL or provider != "first" or supplied is not connector:
            fail(EXIT_MISMATCH, "run_fixture_map_arguments")
        calls.append("map")
        kind = destinations[map_number]
        map_number += 1
        return _map(kind)

    payload = run._run_bounded_run(
        loader,
        connector,  # type: ignore[arg-type]
        "heuristic",
        "skip",
        "first",
        floor_limit,
        combat_runner=combat_runner,  # type: ignore[arg-type]
        reward_waiter=reward_waiter,  # type: ignore[arg-type]
        reward_runner=reward_runner,  # type: ignore[arg-type]
        map_waiter=map_waiter,  # type: ignore[arg-type]
        map_runner=map_runner,  # type: ignore[arg-type]
        next_combat_waiter=next_waiter,  # type: ignore[arg-type]
    )
    loader.require_zeroed()
    return payload, calls, loader


def _run_three_floor_success() -> None:
    payload, calls, _ = _run_sequence(["monster", "monster", "shop"], 3)
    expected_calls = [
        "combat",
        "reward_wait",
        "reward",
        "map_wait",
        "map",
        "next_wait",
        "combat",
        "reward_wait",
        "reward",
        "map_wait",
        "map",
        "next_wait",
        "combat",
        "reward_wait",
        "reward",
        "map_wait",
        "map",
    ]
    if (
        payload.get("milestone") != "r0i_bounded_run"
        or payload.get("completed_floor_count") != 3
        or payload.get("termination")
        != {"reason": "floor_limit_reached", "after_floor": 3, "destination_kind": "shop"}
        or payload.get("action_totals")
        != {"combat": 18, "reward": 3, "map": 3, "total": 24}
        or calls != expected_calls
    ):
        fail(EXIT_MISMATCH, "run_fixture_three_floor_payload")


def _run_room_stops() -> None:
    unsupported, unsupported_calls, _ = _run_sequence(["shop"], 3)
    if (
        unsupported.get("completed_floor_count") != 1
        or unsupported.get("termination")
        != {
            "reason": "unsupported_destination_kind",
            "after_floor": 1,
            "destination_kind": "shop",
        }
        or "next_wait" in unsupported_calls
    ):
        fail(EXIT_MISMATCH, "run_fixture_unsupported_stop")

    boundary, boundary_calls, _ = _run_sequence(["boss"], 3)
    if (
        boundary.get("termination")
        != {"reason": "act_boundary_reached", "after_floor": 1, "destination_kind": "boss"}
        or "next_wait" in boundary_calls
    ):
        fail(EXIT_MISMATCH, "run_fixture_boundary_stop")


def _run_defeat_stop() -> None:
    payload, calls, _ = _run_sequence(["monster"], 3, defeat_on_combat=2)
    if (
        payload.get("completed_floor_count") != 1
        or payload.get("termination")
        != {"reason": "run_defeat", "after_floor": 1, "destination_kind": None}
        or payload.get("action_totals")
        != {"combat": 8, "reward": 1, "map": 1, "total": 10}
        or calls[-2:] != ["next_wait", "combat"]
    ):
        fail(EXIT_MISMATCH, "run_fixture_defeat_stop")


def _run_cached_terminal_wait() -> None:
    decision_id = "a" * 64
    ready = turn_fixture._combat(
        decision_id,
        1,
        hp=70,
        block=0,
        energy=3,
        enemy_hp=43,
        hand=[],
        actions=[turn_fixture._end_turn()],
    )
    bodies = [
        combat_fixture._terminal("victory", 2, hp=70, enemies=[]),
        probe._COMBAT_WAITING,
        ready,
    ]

    def body_reader(*_: object) -> bytes:
        if not bodies:
            fail(EXIT_MISMATCH, "run_fixture_extra_combat_read")
        return bodies.pop(0)

    previous_poll = run._POLL_SECONDS
    run._POLL_SECONDS = 0.0
    credential = bytearray(_CREDENTIAL)
    try:
        attempts = run._wait_for_next_combat_ready(
            credential,
            "heuristic",
            object,  # type: ignore[arg-type]
            body_reader=body_reader,
        )
    finally:
        run._POLL_SECONDS = previous_poll
        probe._zero(credential)
    if attempts != 3 or bodies:
        fail(EXIT_MISMATCH, "run_fixture_cached_terminal_wait")

    def unsupported_reader(*_: object) -> bytes:
        return probe._COMBAT_UNSUPPORTED

    unsupported_credential = bytearray(_CREDENTIAL)
    try:
        run._wait_for_next_combat_ready(
            unsupported_credential,
            "heuristic",
            object,  # type: ignore[arg-type]
            body_reader=unsupported_reader,
        )
    except ToolFailure as failure:
        if failure.exit_code == EXIT_MISMATCH and failure.error_code == "next_combat_state_unsupported":
            probe._zero(unsupported_credential)
            return
    finally:
        probe._zero(unsupported_credential)
    fail(EXIT_MISMATCH, "run_fixture_unsupported_combat_wait")


def _expect_invocation_failure(arguments: list[str], expected_code: str) -> None:
    try:
        run.parse_args(arguments)
    except ToolFailure as failure:
        if failure.exit_code == EXIT_INVALID_INVOCATION and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "run_fixture_wrong_invocation_failure")
    fail(EXIT_MISMATCH, "run_fixture_invocation_passed")


def _run_parse_contract() -> None:
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
        "--floor-limit",
        "3",
    ]
    if run.parse_args(base) != (
        "/synthetic-profile",
        501,
        "heuristic",
        "skip",
        "first",
        3,
    ):
        fail(EXIT_MISMATCH, "run_fixture_parse")
    invalid_limit = list(base)
    invalid_limit[-1] = "4"
    _expect_invocation_failure(invalid_limit, "invalid_floor_limit")
    invalid_reward = list(base)
    invalid_reward[7] = "choose"
    _expect_invocation_failure(invalid_reward, "invalid_reward_provider")


def operation() -> dict[str, object]:
    _run_three_floor_success()
    _run_room_stops()
    _run_defeat_stop()
    _run_cached_terminal_wait()
    _run_parse_contract()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_run_live_fixtures",
        "checks": [
            "three_floor_sequence",
            "room_kind_stops",
            "defeat_stop",
            "cached_terminal_wait",
            "provider_and_floor_limit_surface",
            "credential_cleanup",
        ],
        "check_count": 6,
    }


if __name__ == "__main__":
    main(operation)
