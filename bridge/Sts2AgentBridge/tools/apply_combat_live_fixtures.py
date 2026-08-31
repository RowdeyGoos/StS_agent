#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

sys.dont_write_bytecode = True

import apply_combat_live as apply_combat
import apply_turn_live_fixtures as turn_fixture
import probe_live as probe
from tool_common import EXIT_MISMATCH, ToolFailure, fail, main

_CREDENTIAL = turn_fixture._CREDENTIAL
_HEALTH = turn_fixture._HEALTH


def _terminal(
    outcome: str,
    round_number: int,
    *,
    hp: int,
    enemies: list[dict[str, object]],
) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "status": "complete",
            "decision_kind": "combat",
            "actionable": False,
            "decision_id": None,
            "round": round_number,
            "player": {"hp": hp, "max_hp": 80, "block": 0, "energy": 0},
            "enemies": enemies,
            "hand": [],
            "legal_actions": [],
            "outcome": outcome,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")


def _enemy(hp: int) -> dict[str, object]:
    return {
        "index": 0,
        "id": "NIBBIT",
        "hp": hp,
        "max_hp": 43,
        "block": 0,
        "intents": ["attack"],
    }


def _run_victory() -> None:
    ids = [character * 64 for character in "abcd"]
    state0 = turn_fixture._combat(
        ids[0],
        2,
        hp=78,
        block=0,
        energy=2,
        enemy_hp=13,
        hand=[
            turn_fixture._card(0, "DEFEND_IRONCLAD", "skill", "1", "self", True),
            turn_fixture._card(1, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True),
        ],
        actions=[turn_fixture._play(0), turn_fixture._play(1, 0), turn_fixture._end_turn()],
    )
    state1 = turn_fixture._combat(
        ids[1],
        2,
        hp=78,
        block=5,
        energy=1,
        enemy_hp=13,
        hand=[turn_fixture._card(0, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True)],
        actions=[turn_fixture._play(0, 0), turn_fixture._end_turn()],
    )
    state2 = turn_fixture._combat(
        ids[2],
        2,
        hp=78,
        block=5,
        energy=0,
        enemy_hp=7,
        hand=[],
        actions=[turn_fixture._end_turn()],
    )
    state3 = turn_fixture._combat(
        ids[3],
        3,
        hp=71,
        block=0,
        energy=3,
        enemy_hp=7,
        hand=[turn_fixture._card(0, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True)],
        actions=[turn_fixture._play(0, 0), turn_fixture._end_turn()],
    )
    requests = [
        turn_fixture._get(probe._BASE_ROUTES[0][1]),
        turn_fixture._get(probe._BASE_ROUTES[1][1]),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._post(ids[0], "play:0"),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._post(ids[1], "play:0:0"),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._post(ids[2], "end_turn"),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._post(ids[3], "play:0:0"),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
    ]
    responses = [
        turn_fixture._response(_HEALTH),
        turn_fixture._response(probe._MANIFEST_COMPATIBLE),
        turn_fixture._response(state0),
        turn_fixture._response(turn_fixture._action_body(ids[0], "play:0")),
        turn_fixture._response(state1),
        turn_fixture._response(turn_fixture._action_body(ids[1], "play:0:0")),
        turn_fixture._response(state2),
        turn_fixture._response(turn_fixture._action_body(ids[2], "end_turn")),
        turn_fixture._response(probe._COMBAT_WAITING),
        turn_fixture._response(state3),
        turn_fixture._response(turn_fixture._action_body(ids[3], "play:0:0")),
        turn_fixture._response(_terminal("victory", 3, hp=71, enemies=[])),
    ]
    connector = turn_fixture._Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    payload = apply_combat._run_apply_combat(credential, "heuristic", connector)
    actions = payload.get("actions")
    if (
        payload.get("status") != "passed"
        or payload.get("milestone") != "r0e_complete_combat"
        or payload.get("outcome") != "victory"
        or payload.get("initial_round") != 2
        or payload.get("final_round") != 3
        or payload.get("rounds_observed") != 2
        or payload.get("accepted_action_count") != 4
        or not isinstance(actions, list)
        or [item["action_id"] for item in actions]
        != ["play:0", "play:0:0", "end_turn", "play:0:0"]
    ):
        fail(EXIT_MISMATCH, "combat_fixture_victory_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "combat_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _run_defeat() -> None:
    decision_id = "e" * 64
    before = turn_fixture._combat(
        decision_id,
        1,
        hp=5,
        block=0,
        energy=0,
        enemy_hp=43,
        hand=[],
        actions=[turn_fixture._end_turn()],
    )
    requests = [
        turn_fixture._get(probe._BASE_ROUTES[0][1]),
        turn_fixture._get(probe._BASE_ROUTES[1][1]),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._post(decision_id, "end_turn"),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
    ]
    responses = [
        turn_fixture._response(_HEALTH),
        turn_fixture._response(probe._MANIFEST_COMPATIBLE),
        turn_fixture._response(before),
        turn_fixture._response(turn_fixture._action_body(decision_id, "end_turn")),
        turn_fixture._response(probe._COMBAT_WAITING),
        turn_fixture._response(_terminal("defeat", 1, hp=0, enemies=[_enemy(43)])),
    ]
    connector = turn_fixture._Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    payload = apply_combat._run_apply_combat(credential, "first-legal", connector)
    if (
        payload.get("outcome") != "defeat"
        or payload.get("accepted_action_count") != 1
        or payload.get("final_player", {}).get("hp") != 0
    ):
        fail(EXIT_MISMATCH, "combat_fixture_defeat_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "combat_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _run_stale_terminal_completion() -> None:
    first_id = "6" * 64
    stale_id = "7" * 64
    before = turn_fixture._combat(
        first_id,
        1,
        hp=80,
        block=0,
        energy=1,
        enemy_hp=6,
        hand=[turn_fixture._card(0, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True)],
        actions=[turn_fixture._play(0, 0), turn_fixture._end_turn()],
    )
    resolving = turn_fixture._combat(
        stale_id,
        1,
        hp=80,
        block=0,
        energy=0,
        enemy_hp=0,
        hand=[],
        actions=[turn_fixture._end_turn()],
    )
    requests = [
        turn_fixture._get(probe._BASE_ROUTES[0][1]),
        turn_fixture._get(probe._BASE_ROUTES[1][1]),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._post(first_id, "play:0:0"),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._post(stale_id, "end_turn"),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
    ]
    responses = [
        turn_fixture._response(_HEALTH),
        turn_fixture._response(probe._MANIFEST_COMPATIBLE),
        turn_fixture._response(before),
        turn_fixture._response(turn_fixture._action_body(first_id, "play:0:0")),
        turn_fixture._response(resolving),
        turn_fixture._response(
            turn_fixture._action_body(stale_id, "end_turn", accepted=False)
        ),
        turn_fixture._response(_terminal("victory", 1, hp=80, enemies=[])),
    ]
    connector = turn_fixture._Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    payload = apply_combat._run_apply_combat(credential, "heuristic", connector)
    if (
        payload.get("outcome") != "victory"
        or payload.get("accepted_action_count") != 1
        or [item["action_id"] for item in payload.get("actions", [])]
        != ["play:0:0"]
    ):
        fail(EXIT_MISMATCH, "combat_fixture_stale_terminal_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "combat_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _reject_unattributed_stale_terminal() -> None:
    decision_id = "8" * 64
    before = turn_fixture._combat(
        decision_id,
        1,
        hp=80,
        block=0,
        energy=0,
        enemy_hp=1,
        hand=[],
        actions=[turn_fixture._end_turn()],
    )
    requests = [
        turn_fixture._get(probe._BASE_ROUTES[0][1]),
        turn_fixture._get(probe._BASE_ROUTES[1][1]),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._post(decision_id, "end_turn"),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
    ]
    responses = [
        turn_fixture._response(_HEALTH),
        turn_fixture._response(probe._MANIFEST_COMPATIBLE),
        turn_fixture._response(before),
        turn_fixture._response(
            turn_fixture._action_body(decision_id, "end_turn", accepted=False)
        ),
        turn_fixture._response(_terminal("victory", 1, hp=80, enemies=[])),
    ]
    connector = turn_fixture._Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    try:
        apply_combat._run_apply_combat(credential, "heuristic", connector)
    except ToolFailure as failure:
        if (
            failure.exit_code != EXIT_MISMATCH
            or failure.error_code != "terminal_after_rejected_action"
        ):
            fail(EXIT_MISMATCH, "combat_fixture_wrong_unattributed_failure")
    else:
        fail(EXIT_MISMATCH, "combat_fixture_unattributed_terminal_accepted")
    if any(credential):
        fail(EXIT_MISMATCH, "combat_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _reject_false_victory() -> None:
    decision_id = "f" * 64
    before = turn_fixture._combat(
        decision_id,
        1,
        hp=80,
        block=0,
        energy=0,
        enemy_hp=43,
        hand=[],
        actions=[turn_fixture._end_turn()],
    )
    requests = [
        turn_fixture._get(probe._BASE_ROUTES[0][1]),
        turn_fixture._get(probe._BASE_ROUTES[1][1]),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
        turn_fixture._post(decision_id, "end_turn"),
        turn_fixture._get(probe._COMBAT_ROUTE[0][1]),
    ]
    responses = [
        turn_fixture._response(_HEALTH),
        turn_fixture._response(probe._MANIFEST_COMPATIBLE),
        turn_fixture._response(before),
        turn_fixture._response(turn_fixture._action_body(decision_id, "end_turn")),
        turn_fixture._response(_terminal("victory", 1, hp=80, enemies=[_enemy(43)])),
    ]
    connector = turn_fixture._Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    try:
        apply_combat._run_apply_combat(credential, "heuristic", connector)
    except ToolFailure as failure:
        if failure.exit_code != EXIT_MISMATCH or failure.error_code != "combat_terminal_response_mismatch":
            fail(EXIT_MISMATCH, "combat_fixture_wrong_false_victory_failure")
    else:
        fail(EXIT_MISMATCH, "combat_fixture_false_victory_accepted")
    if any(credential):
        fail(EXIT_MISMATCH, "combat_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def operation() -> dict[str, object]:
    _run_victory()
    _run_defeat()
    _run_stale_terminal_completion()
    _reject_unattributed_stale_terminal()
    _reject_false_victory()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_combat_live_fixtures",
        "checks": [
            "bounded_victory",
            "bounded_defeat",
            "attributed_stale_terminal",
            "unattributed_stale_terminal_rejected",
            "false_terminal_rejected",
        ],
        "check_count": 5,
    }


if __name__ == "__main__":
    main(operation)
