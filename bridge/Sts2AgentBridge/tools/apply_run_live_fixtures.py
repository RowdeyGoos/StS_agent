#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import apply_combat_live_fixtures as combat_fixture
import apply_room_live_fixtures as room_fixture
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


def _combat(
    outcome: str = "victory",
    hp: int = 70,
    actions: int = 5,
    max_hp: int = 80,
) -> dict[str, object]:
    return _component(
        "r0e_complete_combat",
        outcome=outcome,
        accepted_action_count=actions,
        final_player={"hp": hp, "max_hp": max_hp},
    )


def _reward(hp: int = 70, max_hp: int = 80) -> dict[str, object]:
    return _component(
        "r0i_reward_resolution",
        before={"player": {"hp": hp, "max_hp": max_hp}},
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


def _room(screen_kind: str, actions: int, ordinal: int = 4) -> dict[str, object]:
    if screen_kind == "rest_site":
        applied = [
            {
                "decision_id": "0" * 64,
                "action_id": "choose:0",
                "basis": "rest_heal",
                "phase": "choose_option",
            },
            {
                "decision_id": "1" * 64,
                "action_id": "proceed",
                "basis": "proceed",
                "phase": "proceed",
            },
        ]
    else:
        applied = [
            {
                "decision_id": "0" * 64,
                "action_id": "choose:0",
                "basis": "event_first_supported",
                "phase": "choose_option",
            },
        ]
    if len(applied) != actions:
        fail(EXIT_MISMATCH, "run_fixture_room_action_count")
    return _component(
        "r0i_room_interaction",
        decision_provider="safe",
        screen_kind=screen_kind,
        room_ordinal=ordinal,
        accepted_action_count=actions,
        actions=applied,
        final={"status": "complete", "screen_kind": screen_kind, "room_ordinal": ordinal},
        routes_checked=5,
    )


def _run_sequence(
    destinations: list[str],
    floor_limit: int,
    *,
    defeat_on_combat: int | None = None,
    preflight_screen: str | None = None,
    preflight_ordinal: int = 4,
    preflight_failure: str | None = None,
    room_screen: str | None = None,
    room_ordinal: int = 4,
    call_log: list[str] | None = None,
    combat_hp: int = 70,
    combat_max_hp: int = 80,
    reward_hp: int = 70,
    reward_max_hp: int = 80,
) -> tuple[dict[str, object], list[str], CredentialLoader]:
    loader = CredentialLoader()
    calls: list[str] = [] if call_log is None else call_log
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
        return _combat(
            hp=combat_hp,
            actions=4 + combat_number,
            max_hp=combat_max_hp,
        )

    def reward_waiter(credential: bytearray, supplied: object) -> int:
        if bytes(credential) != _CREDENTIAL or supplied is not connector:
            fail(EXIT_MISMATCH, "run_fixture_reward_wait_arguments")
        calls.append("reward_wait")
        return 3

    def reward_runner(credential: bytearray, provider: str, supplied: object) -> dict[str, object]:
        if bytes(credential) != _CREDENTIAL or provider != "skip" or supplied is not connector:
            fail(EXIT_MISMATCH, "run_fixture_reward_arguments")
        calls.append("reward")
        return _reward(reward_hp, reward_max_hp)

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

    def room_waiter(
        credential: bytearray,
        expected_screen: str,
        supplied: object,
    ) -> dict[str, object]:
        if bytes(credential) != _CREDENTIAL or supplied is not connector:
            fail(EXIT_MISMATCH, "run_fixture_room_wait_arguments")
        calls.append("room_wait")
        if preflight_failure is not None:
            fail(EXIT_MISMATCH, preflight_failure)
        selected_destination = destinations[map_number - 1]
        expected_from_destination = (
            "rest_site" if selected_destination == "rest_site" else "event"
        )
        if expected_screen != expected_from_destination:
            fail(EXIT_MISMATCH, "run_fixture_room_wait_expectation")
        observed_screen = preflight_screen or expected_from_destination
        return {
            "attempts": 2,
            "screen_kind": observed_screen,
            "room_ordinal": preflight_ordinal,
        }

    def room_runner(credential: bytearray, provider: str, supplied: object) -> dict[str, object]:
        if (
            bytes(credential) != _CREDENTIAL
            or provider != "safe"
            or supplied is not connector
        ):
            fail(EXIT_MISMATCH, "run_fixture_room_arguments")
        calls.append("room")
        selected_destination = destinations[map_number - 1]
        screen_kind = room_screen
        if screen_kind is None:
            screen_kind = "rest_site" if selected_destination == "rest_site" else "event"
        return _room(
            screen_kind,
            2 if screen_kind == "rest_site" else 1,
            room_ordinal,
        )

    try:
        payload = run._run_bounded_run(
            loader,
            connector,  # type: ignore[arg-type]
            "heuristic",
            "skip",
            "first",
            "safe",
            floor_limit,
            combat_runner=combat_runner,  # type: ignore[arg-type]
            reward_waiter=reward_waiter,  # type: ignore[arg-type]
            reward_runner=reward_runner,  # type: ignore[arg-type]
            map_waiter=map_waiter,  # type: ignore[arg-type]
            map_runner=map_runner,  # type: ignore[arg-type]
            room_waiter=room_waiter,  # type: ignore[arg-type]
            room_runner=room_runner,  # type: ignore[arg-type]
            next_combat_waiter=next_waiter,  # type: ignore[arg-type]
        )
    except ToolFailure:
        loader.require_zeroed()
        raise
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
        != {"combat": 18, "reward": 3, "map": 3, "room": 0, "total": 24}
        or payload.get("room_handoff") is not None
        or calls != expected_calls
    ):
        fail(EXIT_MISMATCH, "run_fixture_three_floor_payload")


def _run_unsupported_stops() -> None:
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
        != {"combat": 8, "reward": 1, "map": 1, "room": 0, "total": 10}
        or payload.get("room_handoff") is not None
        or calls[-2:] != ["next_wait", "combat"]
    ):
        fail(EXIT_MISMATCH, "run_fixture_defeat_stop")


def _run_post_combat_player_transition_contract() -> None:
    healed, _, _ = _run_sequence(
        ["shop"],
        1,
        combat_hp=69,
        reward_hp=75,
    )
    if healed.get("completed_floor_count") != 1:
        fail(EXIT_MISMATCH, "run_fixture_post_combat_heal")

    for values in (
        {"combat_hp": 70, "reward_hp": 69},
        {"combat_max_hp": 80, "reward_max_hp": 81},
    ):
        try:
            _run_sequence(["shop"], 1, **values)
        except ToolFailure as failure:
            if (
                failure.exit_code == EXIT_MISMATCH
                and failure.error_code == "run_player_continuity_mismatch"
            ):
                continue
            fail(EXIT_MISMATCH, "run_fixture_wrong_player_transition_failure")
        fail(EXIT_MISMATCH, "run_fixture_player_transition_passed")

    valid = {"hp": 70, "max_hp": 80}
    invalid_pairs: tuple[tuple[object, object], ...] = (
        (None, valid),
        ({}, valid),
        ({"hp": "70", "max_hp": 80}, valid),
        ({"hp": True, "max_hp": 80}, valid),
        ({"hp": -1, "max_hp": 80}, valid),
        ({"hp": 81, "max_hp": 80}, valid),
        ({"hp": 1_000_001, "max_hp": 1_000_001},
         {"hp": 1_000_001, "max_hp": 1_000_001}),
    )
    if any(
        run._has_bounded_post_combat_player_transition(final, reward)
        for final, reward in invalid_pairs
    ):
        fail(EXIT_MISMATCH, "run_fixture_invalid_player_transition")


def _run_safe_room_handoffs() -> None:
    rest, rest_calls, _ = _run_sequence(["rest_site"], 1)
    rest_handoff = rest.get("room_handoff")
    rest_room = rest_handoff.get("room") if isinstance(rest_handoff, dict) else None
    if (
        rest.get("completed_floor_count") != 1
        or rest.get("providers")
        != {"combat": "heuristic", "reward": "skip", "map": "first", "room": "safe"}
        or rest.get("termination")
        != {
            "reason": "room_handoff_complete",
            "after_floor": 1,
            "destination_kind": "rest_site",
        }
        or not isinstance(rest_handoff, dict)
        or rest_handoff.get("expected_screen_kind") != "rest_site"
        or rest_handoff.get("preflight")
        != {"attempts": 2, "screen_kind": "rest_site", "room_ordinal": 4}
        or rest_handoff.get("map_attempts") != 4
        or not isinstance(rest_room, dict)
        or rest_room.get("screen_kind") != "rest_site"
        or rest.get("action_totals")
        != {"combat": 5, "reward": 1, "map": 1, "room": 2, "total": 9}
        or rest_calls
        != [
            "combat",
            "reward_wait",
            "reward",
            "map_wait",
            "map",
            "room_wait",
            "room",
            "map_wait",
        ]
    ):
        fail(EXIT_MISMATCH, "run_fixture_rest_handoff")

    event, event_calls, _ = _run_sequence(["ancient"], 1)
    event_handoff = event.get("room_handoff")
    event_room = event_handoff.get("room") if isinstance(event_handoff, dict) else None
    if (
        event.get("termination")
        != {
            "reason": "room_handoff_complete",
            "after_floor": 1,
            "destination_kind": "ancient",
        }
        or not isinstance(event_handoff, dict)
        or event_handoff.get("expected_screen_kind") != "event"
        or event_handoff.get("preflight")
        != {"attempts": 2, "screen_kind": "event", "room_ordinal": 4}
        or not isinstance(event_room, dict)
        or event_room.get("screen_kind") != "event"
        or event.get("action_totals")
        != {"combat": 5, "reward": 1, "map": 1, "room": 1, "total": 8}
        or event_calls[-3:] != ["room_wait", "room", "map_wait"]
        or "next_wait" in event_calls
    ):
        fail(EXIT_MISMATCH, "run_fixture_event_handoff")

    unknown, unknown_calls, _ = _run_sequence(["unknown"], 1)
    unknown_handoff = unknown.get("room_handoff")
    unknown_room = (
        unknown_handoff.get("room") if isinstance(unknown_handoff, dict) else None
    )
    if (
        unknown.get("termination")
        != {
            "reason": "room_handoff_complete",
            "after_floor": 1,
            "destination_kind": "unknown",
        }
        or not isinstance(unknown_handoff, dict)
        or unknown_handoff.get("expected_screen_kind") != "event"
        or not isinstance(unknown_room, dict)
        or unknown_room.get("screen_kind") != "event"
        or unknown_calls[-3:] != ["room_wait", "room", "map_wait"]
    ):
        fail(EXIT_MISMATCH, "run_fixture_unknown_event_handoff")


def _continuation(handoff: object) -> dict[str, object]:
    if not isinstance(handoff, dict):
        fail(EXIT_MISMATCH, "run_fixture_missing_room_handoff")
    return handoff


def _run_room_continuations() -> None:
    rest, rest_calls, _ = _run_sequence(["rest_site", "monster"], 2)
    rest_handoff = _continuation(rest.get("room_handoff"))
    rest_next_combat = rest_handoff.get("next_combat")
    if (
        rest.get("completed_floor_count") != 1
        or rest.get("terminal_combat") is not None
        or rest.get("termination")
        != {
            "reason": "room_continuation_complete",
            "after_floor": 1,
            "destination_kind": "monster",
        }
        or rest_handoff.get("destination_kind") != "rest_site"
        or rest_handoff.get("expected_screen_kind") != "rest_site"
        or rest_handoff.get("preflight")
        != {"attempts": 2, "screen_kind": "rest_site", "room_ordinal": 4}
        or rest_handoff.get("map_attempts") != 4
        or rest_handoff.get("post_room_map") != _map("monster")
        or rest_handoff.get("next_combat_attempts") != 2
        or not isinstance(rest_next_combat, dict)
        or rest_next_combat.get("outcome") != "victory"
        or rest.get("action_totals")
        != {"combat": 11, "reward": 1, "map": 2, "room": 2, "total": 16}
        or rest_calls
        != [
            "combat",
            "reward_wait",
            "reward",
            "map_wait",
            "map",
            "room_wait",
            "room",
            "map_wait",
            "map",
            "next_wait",
            "combat",
        ]
    ):
        fail(EXIT_MISMATCH, "run_fixture_rest_continuation")

    event, event_calls, _ = _run_sequence(["ancient", "monster"], 3)
    event_handoff = _continuation(event.get("room_handoff"))
    event_next_combat = event_handoff.get("next_combat")
    if (
        event.get("termination")
        != {
            "reason": "room_continuation_complete",
            "after_floor": 1,
            "destination_kind": "monster",
        }
        or event_handoff.get("destination_kind") != "ancient"
        or event_handoff.get("expected_screen_kind") != "event"
        or event_handoff.get("post_room_map") != _map("monster")
        or event_handoff.get("next_combat_attempts") != 2
        or not isinstance(event_next_combat, dict)
        or event_next_combat.get("outcome") != "victory"
        or event.get("action_totals")
        != {"combat": 11, "reward": 1, "map": 2, "room": 1, "total": 15}
        or event_calls[-4:] != ["map_wait", "map", "next_wait", "combat"]
    ):
        fail(EXIT_MISMATCH, "run_fixture_event_continuation")


def _expect_post_room_failure(destination: str, expected_code: str) -> None:
    calls: list[str] = []
    try:
        _run_sequence(["rest_site", destination], 2, call_log=calls)
    except ToolFailure as failure:
        if (
            failure.exit_code == EXIT_MISMATCH
            and failure.error_code == expected_code
            and calls.count("room_wait") == 1
            and calls.count("room") == 1
            and calls.count("map") == 2
            and "next_wait" not in calls
        ):
            return
        fail(EXIT_MISMATCH, "run_fixture_wrong_post_room_failure")
    fail(EXIT_MISMATCH, "run_fixture_post_room_failure_passed")


def _run_room_continuation_fail_closed() -> None:
    _expect_post_room_failure("rest_site", "run_second_room_destination")
    _expect_post_room_failure("shop", "run_post_room_destination_unsupported")
    _expect_post_room_failure("boss", "run_post_room_destination_unsupported")


def _run_room_continuation_terminal_and_cap() -> None:
    capped, capped_calls, _ = _run_sequence(["rest_site"], 1)
    if (
        capped.get("termination")
        != {
            "reason": "room_handoff_complete",
            "after_floor": 1,
            "destination_kind": "rest_site",
        }
        or capped.get("action_totals")
        != {"combat": 5, "reward": 1, "map": 1, "room": 2, "total": 9}
        or capped_calls[-3:] != ["room_wait", "room", "map_wait"]
        or capped_calls.count("map") != 1
        or "next_wait" in capped_calls
    ):
        fail(EXIT_MISMATCH, "run_fixture_room_continuation_cap")

    defeated, defeated_calls, _ = _run_sequence(
        ["rest_site", "monster"],
        2,
        defeat_on_combat=2,
    )
    defeated_handoff = _continuation(defeated.get("room_handoff"))
    if (
        defeated.get("completed_floor_count") != 1
        or defeated.get("termination")
        != {"reason": "run_defeat", "after_floor": 1, "destination_kind": None}
        or not isinstance(defeated.get("terminal_combat"), dict)
        or defeated_handoff.get("next_combat") != defeated.get("terminal_combat")
        or defeated.get("action_totals")
        != {"combat": 8, "reward": 1, "map": 2, "room": 2, "total": 13}
        or defeated_calls[-2:] != ["next_wait", "combat"]
    ):
        fail(EXIT_MISMATCH, "run_fixture_room_continuation_defeat")


def _expect_room_failure(
    destination: str,
    expected_code: str,
    *,
    preflight_screen: str | None = None,
    preflight_failure: str | None = None,
    room_screen: str | None = None,
    room_ordinal: int = 4,
    expect_room_call: bool,
) -> None:
    calls: list[str] = []
    try:
        _run_sequence(
            [destination],
            3,
            preflight_screen=preflight_screen,
            preflight_failure=preflight_failure,
            room_screen=room_screen,
            room_ordinal=room_ordinal,
            call_log=calls,
        )
    except ToolFailure as failure:
        if (
            failure.exit_code == EXIT_MISMATCH
            and failure.error_code == expected_code
            and ("room" in calls) is expect_room_call
            and "room_wait" in calls
        ):
            return
        fail(EXIT_MISMATCH, "run_fixture_wrong_room_failure")
    fail(EXIT_MISMATCH, "run_fixture_room_failure_passed")


def _run_room_fail_closed() -> None:
    _expect_room_failure(
        "rest_site",
        "run_room_kind_mismatch",
        preflight_screen="event",
        expect_room_call=False,
    )
    _expect_room_failure(
        "ancient",
        "run_room_state_unsupported",
        preflight_failure="run_room_state_unsupported",
        expect_room_call=False,
    )
    _expect_room_failure(
        "rest_site",
        "run_room_reconciliation_mismatch",
        room_screen="event",
        expect_room_call=True,
    )
    _expect_room_failure(
        "rest_site",
        "run_room_reconciliation_mismatch",
        room_ordinal=5,
        expect_room_call=True,
    )


def _expect_room_preflight_failure(
    body: bytes,
    expected_screen_kind: str,
    expected_code: str,
) -> None:
    def body_reader(*_: object) -> bytes:
        return body

    credential = bytearray(_CREDENTIAL)
    try:
        run._wait_for_room_ready(
            credential,
            expected_screen_kind,
            object,  # type: ignore[arg-type]
            body_reader=body_reader,
        )
    except ToolFailure as failure:
        if failure.exit_code == EXIT_MISMATCH and failure.error_code == expected_code:
            probe._zero(credential)
            return
        fail(EXIT_MISMATCH, "run_fixture_wrong_room_preflight_failure")
    finally:
        probe._zero(credential)
    fail(EXIT_MISMATCH, "run_fixture_room_preflight_failure_passed")


def _run_room_preflight_contract() -> None:
    heal = room_fixture._candidate(
        0,
        "rest_heal",
        "HEAL",
        enabled=True,
        supported=True,
    )
    ready_rest = room_fixture._ready(
        room_fixture._DECISION_ZERO,
        "rest_site",
        "choose_option",
        [heal],
        [room_fixture._legal(heal)],
    )
    bodies = [
        room_fixture._inactive("waiting", "unknown", "unknown", None),
        ready_rest,
    ]

    def body_reader(*_: object) -> bytes:
        if not bodies:
            fail(EXIT_MISMATCH, "run_fixture_extra_room_preflight_read")
        return bodies.pop(0)

    previous_poll = run._POLL_SECONDS
    run._POLL_SECONDS = 0.0
    credential = bytearray(_CREDENTIAL)
    try:
        observed = run._wait_for_room_ready(
            credential,
            "rest_site",
            object,  # type: ignore[arg-type]
            body_reader=body_reader,
        )
    finally:
        run._POLL_SECONDS = previous_poll
        probe._zero(credential)
    if observed != {"attempts": 2, "screen_kind": "rest_site", "room_ordinal": 4}:
        fail(EXIT_MISMATCH, "run_fixture_room_preflight_ready")

    event = room_fixture._candidate(
        0,
        "event_option",
        "EVENT.SAFE",
        enabled=True,
        supported=True,
    )
    ready_event = room_fixture._ready(
        room_fixture._DECISION_ZERO,
        "event",
        "choose_option",
        [event],
        [room_fixture._legal(event)],
    )
    _expect_room_preflight_failure(
        ready_event,
        "rest_site",
        "run_room_kind_mismatch",
    )
    _expect_room_preflight_failure(
        room_fixture._UNSUPPORTED_EVENT,
        "event",
        "run_room_state_unsupported",
    )


def _run_room_preflight_delayed_activation() -> None:
    event = room_fixture._candidate(
        0,
        "event_option",
        "EVENT.SAFE",
        enabled=True,
        supported=True,
    )
    ready_event = room_fixture._ready(
        room_fixture._DECISION_ZERO,
        "event",
        "choose_option",
        [event],
        [room_fixture._legal(event)],
        ordinal=4,
    )
    rest_complete = room_fixture._inactive("complete", "rest_site", "complete", 3)
    waiting = room_fixture._inactive("waiting", "unknown", "unknown", None)

    def assert_preflight(
        expected_screen_kind: str,
        values: list[bytes],
        expected_ordinal: int,
    ) -> None:
        route = room_fixture._get(room_fixture.room._ROOM_DECISION_ROUTE)
        connector = room_fixture._Connector(
            [room_fixture._response(value) for value in values],
            [route for _ in values],
        )
        previous_poll = run._POLL_SECONDS
        run._POLL_SECONDS = 0.0
        credential = bytearray(_CREDENTIAL)
        try:
            observed = run._wait_for_room_ready(
                credential,
                expected_screen_kind,
                connector,
            )
        finally:
            run._POLL_SECONDS = previous_poll
            probe._zero(credential)
        if observed != {
            "attempts": len(values),
            "screen_kind": expected_screen_kind,
            "room_ordinal": expected_ordinal,
        }:
            fail(EXIT_MISMATCH, "run_fixture_delayed_room_preflight")
        connector.assert_cleanup()

    assert_preflight("event", [rest_complete, waiting, ready_event], 4)

    heal = room_fixture._candidate(
        0,
        "rest_heal",
        "HEAL",
        enabled=True,
        supported=True,
    )
    ready_rest = room_fixture._ready(
        room_fixture._DECISION_ONE,
        "rest_site",
        "choose_option",
        [heal],
        [room_fixture._legal(heal)],
        ordinal=8,
    )
    event_complete = room_fixture._inactive("complete", "event", "complete", 7)
    assert_preflight("rest_site", [event_complete, ready_rest], 8)

    def complete_reader(*_: object) -> bytes:
        return room_fixture._COMPLETE_EVENT

    monotonic_values = iter((0.0, 0.0, run.room_client._ROOM_DEADLINE_SECONDS + 1.0))
    previous_monotonic = run.time.monotonic
    run.time.monotonic = lambda: next(monotonic_values)
    timeout_credential = bytearray(_CREDENTIAL)
    try:
        run._wait_for_room_ready(
            timeout_credential,
            "event",
            object,  # type: ignore[arg-type]
            body_reader=complete_reader,
        )
    except ToolFailure as failure:
        if failure.exit_code != EXIT_MISMATCH or failure.error_code != "run_room_ready_timeout":
            fail(EXIT_MISMATCH, "run_fixture_wrong_delayed_room_timeout")
    else:
        fail(EXIT_MISMATCH, "run_fixture_delayed_room_timeout_passed")
    finally:
        run.time.monotonic = previous_monotonic
        probe._zero(timeout_credential)


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
        "--room-provider",
        "safe",
        "--floor-limit",
        "3",
    ]
    if run.parse_args(base) != (
        "/synthetic-profile",
        501,
        "heuristic",
        "skip",
        "first",
        "safe",
        3,
    ):
        fail(EXIT_MISMATCH, "run_fixture_parse")
    invalid_limit = list(base)
    invalid_limit[-1] = "4"
    _expect_invocation_failure(invalid_limit, "invalid_floor_limit")
    invalid_reward = list(base)
    invalid_reward[7] = "choose"
    _expect_invocation_failure(invalid_reward, "invalid_reward_provider")
    invalid_room = list(base)
    invalid_room[11] = "unknown"
    _expect_invocation_failure(invalid_room, "invalid_room_provider")


def operation() -> dict[str, object]:
    _run_three_floor_success()
    _run_unsupported_stops()
    _run_defeat_stop()
    _run_post_combat_player_transition_contract()
    _run_safe_room_handoffs()
    _run_room_continuations()
    _run_room_continuation_fail_closed()
    _run_room_continuation_terminal_and_cap()
    _run_room_fail_closed()
    _run_room_preflight_contract()
    _run_room_preflight_delayed_activation()
    _run_cached_terminal_wait()
    _run_parse_contract()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_run_live_fixtures",
        "checks": [
            "three_floor_sequence",
            "unsupported_destination_stops",
            "defeat_stop",
            "bounded_post_combat_player_transition",
            "rest_and_event_room_handoffs",
            "rest_and_event_room_continuations",
            "post_room_unsupported_and_second_room_fail_closed",
            "post_room_cap_and_terminal_combat",
            "room_mismatch_and_unsupported_fail_closed",
            "read_only_room_preflight_contract",
            "delayed_room_preflight_activation",
            "cached_terminal_wait",
            "provider_and_floor_limit_surface",
            "credential_cleanup",
        ],
        "check_count": 14,
    }


if __name__ == "__main__":
    main(operation)
