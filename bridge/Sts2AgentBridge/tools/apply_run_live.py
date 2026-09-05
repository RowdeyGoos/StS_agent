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
import apply_room_live as room_client
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
_ACT_BOUNDARY_KINDS = frozenset(("boss",))
_COMBAT_DESTINATION_KINDS = frozenset(("monster", "elite"))
_ROOM_KINDS_BY_DESTINATION = {
    "rest_site": "rest_site",
    "ancient": "event",
    "unknown": "event",
}


def parse_args(
    arguments: list[str] | None = None,
) -> tuple[str, int, str, str, str, str, int, str]:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) not in (14, 16):
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    allowed = frozenset(
        (
            "--user-profile",
            "--effective-uid",
            "--combat-provider",
            "--reward-provider",
            "--map-provider",
            "--room-provider",
            "--floor-limit",
            "--entry-phase",
        )
    )
    parsed: dict[str, str] = {}
    for offset in range(0, len(values), 2):
        name = values[offset]
        if name not in allowed or name in parsed:
            fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
        parsed[name] = values[offset + 1]
    required = allowed - {"--entry-phase"}
    if set(parsed) not in (required, allowed):
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    if parsed["--combat-provider"] not in provider_names():
        fail(EXIT_INVALID_INVOCATION, "invalid_combat_provider")
    if parsed["--reward-provider"] not in reward_client._PROVIDERS:
        fail(EXIT_INVALID_INVOCATION, "invalid_reward_provider")
    if parsed["--map-provider"] not in map_provider_names():
        fail(EXIT_INVALID_INVOCATION, "invalid_map_provider")
    if parsed["--room-provider"] != room_client._ROOM_PROVIDER:
        fail(EXIT_INVALID_INVOCATION, "invalid_room_provider")
    floor_limit_text = parsed["--floor-limit"]
    if floor_limit_text not in tuple(str(value) for value in range(1, _MAXIMUM_FLOORS + 1)):
        fail(EXIT_INVALID_INVOCATION, "invalid_floor_limit")
    entry_phase = parsed.get("--entry-phase", "combat")
    if entry_phase not in ("combat", "reward", "map"):
        fail(EXIT_INVALID_INVOCATION, "invalid_entry_phase")
    return (
        parsed["--user-profile"],
        probe._parse_effective_uid(parsed["--effective-uid"]),
        parsed["--combat-provider"],
        parsed["--reward-provider"],
        parsed["--map-provider"],
        parsed["--room-provider"],
        int(floor_limit_text),
        entry_phase,
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


def _wait_for_room_ready(
    credential: bytearray,
    expected_screen_kind: str,
    connector: Callable[[], Any],
    *,
    body_reader: Callable[..., bytes] = room_client._read_body,
) -> dict[str, object]:
    if expected_screen_kind not in _ROOM_KINDS_BY_DESTINATION.values():
        fail(EXIT_INTERNAL, "internal_failure")
    deadline = time.monotonic() + room_client._ROOM_DEADLINE_SECONDS
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        body = body_reader(
            "room",
            room_client._ROOM_DECISION_ROUTE,
            credential,
            connector,
            deadline,
        )
        decision = room_client._validate_room(body)
        status = decision["status"]
        if status == "waiting":
            time.sleep(_POLL_SECONDS)
            continue
        if status == "unsupported":
            fail(EXIT_MISMATCH, "run_room_state_unsupported")
        if status == "complete":
            # A completed decision may be residue from the prior room while map
            # travel activates the expected room; only a ready body proves it.
            time.sleep(_POLL_SECONDS)
            continue
        if status != "ready":
            fail(EXIT_MISMATCH, "run_room_not_ready")
        if decision["screen_kind"] != expected_screen_kind:
            fail(EXIT_MISMATCH, "run_room_kind_mismatch")
        return {
            "attempts": attempts,
            "screen_kind": decision["screen_kind"],
            "room_ordinal": decision["room_ordinal"],
        }
    fail(EXIT_MISMATCH, "run_room_ready_timeout")


def _with_credential(
    credential_loader: Callable[[], bytearray],
    operation: Callable[..., object],
    *arguments: object,
    **keyword_arguments: object,
) -> object:
    credential = credential_loader()
    try:
        return operation(credential, *arguments, **keyword_arguments)
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
    room_provider: str,
    floor_limit: int,
    floors: list[dict[str, object]],
    terminal_combat: dict[str, object] | None,
    readiness: list[dict[str, int]],
    room_handoff: dict[str, object] | None,
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
    room_actions = 0
    if room_handoff is not None:
        room = room_handoff.get("room")
        accepted_action_count = (
            room.get("accepted_action_count") if isinstance(room, dict) else None
        )
        if type(accepted_action_count) is not int or accepted_action_count < 1:
            fail(EXIT_INTERNAL, "internal_failure")
        room_actions = accepted_action_count
        if room_handoff.get("post_room_map") is not None:
            map_actions += 1
        continuation_combat = room_handoff.get("next_combat")
        if continuation_combat is not None and continuation_combat is not terminal_combat:
            if not isinstance(continuation_combat, dict):
                fail(EXIT_INTERNAL, "internal_failure")
            continuation_actions = continuation_combat.get("accepted_action_count")
            if type(continuation_actions) is not int or continuation_actions < 1:
                fail(EXIT_INTERNAL, "internal_failure")
            combat_actions += continuation_actions
    return {
        "schema_version": 1,
        "status": "passed",
        "milestone": "r0i_bounded_run",
        "providers": {
            "combat": combat_provider,
            "reward": reward_provider,
            "map": map_provider,
            "room": room_provider,
        },
        "floor_limit": floor_limit,
        "completed_floor_count": len(floors),
        "action_totals": {
            "combat": combat_actions,
            "reward": reward_actions,
            "map": map_actions,
            "room": room_actions,
            "total": combat_actions + reward_actions + map_actions + room_actions,
        },
        "readiness": readiness,
        "floors": floors,
        "terminal_combat": terminal_combat,
        "room_handoff": room_handoff,
        "termination": termination,
    }


def _entry_result(
    combat_provider: str,
    reward_provider: str,
    map_provider: str,
    room_provider: str,
    floor_limit: int,
    entry_phase: str,
    entry_prefix: dict[str, object],
    floors: list[dict[str, object]],
    terminal_combat: dict[str, object] | None,
    readiness: list[dict[str, int]],
    room_handoff: dict[str, object] | None,
    termination: dict[str, object],
) -> dict[str, object]:
    base = _result(
        combat_provider,
        reward_provider,
        map_provider,
        room_provider,
        floor_limit,
        floors,
        terminal_combat,
        readiness,
        room_handoff,
        termination,
    )
    action_totals = base.get("action_totals")
    if not isinstance(action_totals, dict):
        fail(EXIT_INTERNAL, "internal_failure")
    reward_actions = 0
    prefix_reward = entry_prefix.get("reward")
    if prefix_reward is not None:
        applied = prefix_reward.get("applied") if isinstance(prefix_reward, dict) else None
        if not isinstance(applied, list):
            fail(EXIT_INTERNAL, "internal_failure")
        reward_actions = len(applied)
    for name in ("combat", "reward", "map", "room", "total"):
        if type(action_totals.get(name)) is not int:
            fail(EXIT_INTERNAL, "internal_failure")
    action_totals = dict(action_totals)
    action_totals["reward"] += reward_actions
    action_totals["map"] += 1
    action_totals["total"] += reward_actions + 1
    return {
        "schema_version": 1,
        "status": "passed",
        "milestone": "r0i_bounded_run_entry",
        "providers": {
            "combat": combat_provider,
            "reward": reward_provider,
            "map": map_provider,
            "room": room_provider,
        },
        "floor_limit": floor_limit,
        "entry_phase": entry_phase,
        "processed_floor_count": action_totals["map"],
        "completed_floor_count": len(floors),
        "action_totals": action_totals,
        "readiness": readiness,
        "floors": floors,
        "terminal_combat": terminal_combat,
        "room_handoff": room_handoff,
        "termination": termination,
        "entry_prefix": entry_prefix,
    }


def _destination_kind(map_result: dict[str, object]) -> str:
    after = map_result.get("after")
    destination = after.get("destination") if isinstance(after, dict) else None
    kind = destination.get("kind") if isinstance(destination, dict) else None
    if not isinstance(kind, str) or kind not in map_client._NODE_KINDS:
        fail(EXIT_MISMATCH, "run_map_destination_mismatch")
    return kind


def _has_bounded_post_combat_player_transition(
    final_player: object,
    reward_player: object,
) -> bool:
    if not isinstance(final_player, dict) or not isinstance(reward_player, dict):
        return False
    final_hp = final_player.get("hp")
    final_max_hp = final_player.get("max_hp")
    reward_hp = reward_player.get("hp")
    reward_max_hp = reward_player.get("max_hp")
    if not all(
        probe._is_bounded_nonnegative_integer(value)
        for value in (final_hp, final_max_hp, reward_hp, reward_max_hp)
    ):
        return False
    return (
        final_max_hp > 0
        and final_max_hp == reward_max_hp
        and 0 <= final_hp <= reward_hp <= reward_max_hp
    )


def _run_bounded_run(
    credential_loader: Callable[[], bytearray],
    connector: Callable[[], Any],
    combat_provider: str,
    reward_provider: str,
    map_provider: str,
    room_provider: str,
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
    room_waiter: Callable[
        [bytearray, str, Callable[[], Any]], dict[str, object]
    ] = _wait_for_room_ready,
    room_runner: Callable[..., dict[str, object]] =
        room_client._run_apply_room,
    next_combat_waiter: Callable[[bytearray, str, Callable[[], Any]], int] =
        _wait_for_next_combat_ready,
    entry_phase: str = "combat",
    room_diagnostics: object = None,
) -> dict[str, object]:
    if type(floor_limit) is not int or not 1 <= floor_limit <= _MAXIMUM_FLOORS:
        fail(EXIT_INTERNAL, "internal_failure")
    if entry_phase not in ("combat", "reward", "map"):
        fail(EXIT_INTERNAL, "internal_failure")

    floors: list[dict[str, object]] = []
    readiness: list[dict[str, int]] = []
    entry_prefix: dict[str, object] | None = None
    processed_floor_count = 0
    pending_destination_kind: str | None = None
    pending_after_floor = 0

    def result(
        terminal_combat: dict[str, object] | None,
        room_handoff: dict[str, object] | None,
        termination: dict[str, object],
    ) -> dict[str, object]:
        if entry_prefix is None:
            return _result(
                combat_provider,
                reward_provider,
                map_provider,
                room_provider,
                floor_limit,
                floors,
                terminal_combat,
                readiness,
                room_handoff,
                termination,
            )
        if processed_floor_count > floor_limit:
            fail(EXIT_INTERNAL, "internal_failure")
        entry_result = _entry_result(
            combat_provider,
            reward_provider,
            map_provider,
            room_provider,
            floor_limit,
            entry_phase,
            entry_prefix,
            floors,
            terminal_combat,
            readiness,
            room_handoff,
            termination,
        )
        if entry_result.get("processed_floor_count") != processed_floor_count:
            fail(EXIT_INTERNAL, "internal_failure")
        return entry_result

    if entry_phase != "combat":
        prefix_reward: dict[str, object] | None = None
        map_attempts = 0
        if entry_phase == "reward":
            prefix_reward = _require_component(
                _with_credential(
                    credential_loader,
                    reward_runner,
                    reward_provider,
                    connector,
                ),
                "r0i_reward_resolution",
                "run_reward_result_mismatch",
            )
            observed = _with_credential(credential_loader, map_waiter, connector)
            if type(observed) is not int or observed < 1:
                fail(EXIT_INTERNAL, "internal_failure")
            map_attempts = observed
        prefix_map = _require_component(
            _with_credential(
                credential_loader,
                map_runner,
                map_provider,
                connector,
            ),
            "r0g_map_selection",
            "run_map_result_mismatch",
        )
        pending_destination_kind = _destination_kind(prefix_map)
        pending_after_floor = 1
        processed_floor_count = 1
        entry_prefix = {
            "floor_number": 1,
            "destination_kind": pending_destination_kind,
            "observed_phases": (
                ["reward", "map"] if entry_phase == "reward" else ["map"]
            ),
            "unavailable_phases": (
                ["combat"] if entry_phase == "reward" else ["combat", "reward"]
            ),
            "combat": None,
            "reward": prefix_reward,
            "map": prefix_map,
            "readiness": {
                "next_combat_attempts": 0,
                "reward_attempts": 0,
                "map_attempts": map_attempts,
            },
        }

    floor_number = 1 if entry_phase == "combat" else 2
    while True:
        if pending_destination_kind is not None:
            kind = pending_destination_kind
            expected_room_kind = _ROOM_KINDS_BY_DESTINATION.get(kind)
            if expected_room_kind is not None:
                room_preflight = _with_credential(
                    credential_loader,
                    room_waiter,
                    expected_room_kind,
                    connector,
                )
                if (
                    not isinstance(room_preflight, dict)
                    or set(room_preflight) != {"attempts", "screen_kind", "room_ordinal"}
                    or type(room_preflight.get("attempts")) is not int
                    or int(room_preflight["attempts"]) < 1
                    or type(room_preflight.get("room_ordinal")) is not int
                    or not 0 <= int(room_preflight["room_ordinal"]) <= 999
                ):
                    fail(EXIT_MISMATCH, "run_room_preflight_mismatch")
                if room_preflight.get("screen_kind") != expected_room_kind:
                    fail(EXIT_MISMATCH, "run_room_kind_mismatch")
                room_arguments = {
                    "expected_context": (
                        expected_room_kind,
                        room_preflight["room_ordinal"],
                    )
                }
                if room_diagnostics is not None:
                    room_arguments["diagnostics"] = room_diagnostics
                room = _require_component(
                    _with_credential(
                        credential_loader,
                        room_runner,
                        room_provider,
                        connector,
                        **room_arguments,
                    ),
                    "r0i_room_interaction",
                    "run_room_result_mismatch",
                )
                if room.get("decision_provider") != room_provider:
                    fail(EXIT_MISMATCH, "run_room_provider_mismatch")
                if (
                    room.get("screen_kind") != room_preflight["screen_kind"]
                    or room.get("room_ordinal") != room_preflight["room_ordinal"]
                ):
                    fail(EXIT_MISMATCH, "run_room_reconciliation_mismatch")
                post_room_map_attempts = _with_credential(
                    credential_loader,
                    map_waiter,
                    connector,
                )
                if (
                    type(post_room_map_attempts) is not int
                    or post_room_map_attempts < 1
                ):
                    fail(EXIT_INTERNAL, "internal_failure")
                room_handoff = {
                    "after_floor": pending_after_floor,
                    "destination_kind": kind,
                    "expected_screen_kind": expected_room_kind,
                    "preflight": room_preflight,
                    "room": room,
                    "map_attempts": post_room_map_attempts,
                }
                if processed_floor_count == floor_limit:
                    return result(
                        None,
                        room_handoff,
                        _termination(
                            "room_handoff_complete",
                            pending_after_floor,
                            kind,
                        ),
                    )
                post_room_map = _require_component(
                    _with_credential(
                        credential_loader,
                        map_runner,
                        map_provider,
                        connector,
                    ),
                    "r0g_map_selection",
                    "run_post_room_map_result_mismatch",
                )
                processed_floor_count += 1
                post_room_kind = _destination_kind(post_room_map)
                room_handoff["post_room_map"] = post_room_map
                if post_room_kind in _ROOM_KINDS_BY_DESTINATION:
                    fail(EXIT_MISMATCH, "run_second_room_destination")
                if post_room_kind not in _COMBAT_DESTINATION_KINDS:
                    fail(EXIT_MISMATCH, "run_post_room_destination_unsupported")
                next_combat_attempts = _with_credential(
                    credential_loader,
                    next_combat_waiter,
                    combat_provider,
                    connector,
                )
                if type(next_combat_attempts) is not int or next_combat_attempts < 1:
                    fail(EXIT_INTERNAL, "internal_failure")
                next_combat = _require_component(
                    _with_credential(
                        credential_loader,
                        combat_runner,
                        combat_provider,
                        connector,
                    ),
                    "r0e_complete_combat",
                    "run_next_combat_result_mismatch",
                )
                next_combat_outcome = next_combat.get("outcome")
                if next_combat_outcome not in ("victory", "defeat"):
                    fail(EXIT_MISMATCH, "run_combat_outcome_mismatch")
                room_handoff["next_combat_attempts"] = next_combat_attempts
                room_handoff["next_combat"] = next_combat
                if next_combat_outcome == "defeat":
                    return result(
                        next_combat,
                        room_handoff,
                        _termination(
                            "run_defeat",
                            pending_after_floor,
                            None,
                        ),
                    )
                return result(
                    None,
                    room_handoff,
                    _termination(
                        "room_continuation_complete",
                        pending_after_floor,
                        post_room_kind,
                    ),
                )

            if processed_floor_count == floor_limit:
                return result(
                    None,
                    None,
                    _termination(
                        "floor_limit_reached",
                        pending_after_floor,
                        kind,
                    ),
                )
            if kind not in _COMBAT_DESTINATION_KINDS:
                reason = (
                    "act_boundary_reached"
                    if kind in _ACT_BOUNDARY_KINDS
                    else "unsupported_destination_kind"
                )
                return result(
                    None,
                    None,
                    _termination(reason, pending_after_floor, kind),
                )
            pending_destination_kind = None

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
            return result(
                combat,
                None,
                _termination("run_defeat", floor_number - 1, None),
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
        if not _has_bounded_post_combat_player_transition(final_player, reward_player):
            fail(EXIT_MISMATCH, "run_player_continuity_mismatch")

        map_attempts = _with_credential(credential_loader, map_waiter, connector)
        if type(map_attempts) is not int or map_attempts < 1:
            fail(EXIT_INTERNAL, "internal_failure")
        map_result = _require_component(
            _with_credential(credential_loader, map_runner, map_provider, connector),
            "r0g_map_selection",
            "run_map_result_mismatch",
        )
        processed_floor_count += 1
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
        pending_destination_kind = kind
        pending_after_floor = floor_number
        floor_number += 1


def _operation(*, room_diagnostics: object = None) -> dict[str, object]:
    (
        profile_value,
        supplied_uid,
        combat_provider,
        reward_provider,
        map_provider,
        room_provider,
        floor_limit,
        entry_phase,
    ) = parse_args()
    user_profile: Path = absolute_path(profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)

    def credential_loader() -> bytearray:
        return probe._load_fixed_credential(user_profile, uid)

    if room_diagnostics is None:
        return _run_bounded_run(
            credential_loader,
            probe._literal_loopback_connector,
            combat_provider,
            reward_provider,
            map_provider,
            room_provider,
            floor_limit,
            entry_phase=entry_phase,
        )
    return _run_bounded_run(
        credential_loader,
        probe._literal_loopback_connector,
        combat_provider,
        reward_provider,
        map_provider,
        room_provider,
        floor_limit,
        entry_phase=entry_phase,
        room_diagnostics=room_diagnostics,
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
