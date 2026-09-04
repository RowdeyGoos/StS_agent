#!/usr/bin/env python3
"""Synthetic, capture-off fixture gate for bounded-run acceptance summaries."""
from __future__ import annotations

import copy
import io
import json
import sys
from array import array
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import apply_combat_live as combat_client
import apply_combat_live_fixtures as combat_fixture
import apply_run_acceptance_live as live
import apply_run_elite_wire_fixtures as elite_wire
import apply_run_entry_wire_fixtures as entry_wire
import apply_run_wire_fixtures as run_wire
import verify_room_acceptance as acceptance
from tool_common import EXIT_INTERNAL, EXIT_MISMATCH, ToolFailure, fail, run_cli


class _ExplosiveEquality:
    def __eq__(self, other: object) -> bool:
        del other
        raise RuntimeError("RAW-CANARY")

    def __hash__(self) -> int:
        raise RuntimeError("RAW-CANARY")


class _HostileValues(dict[object, object]):
    def values(self) -> object:
        raise RuntimeError("RAW-CANARY")


def _encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _expect_failure(operation: object, code: str, exit_code: int = EXIT_MISMATCH) -> None:
    try:
        operation()  # type: ignore[operator]
    except ToolFailure as failure:
        if failure.exit_code == exit_code and failure.error_code == code:
            return
    fail(EXIT_MISMATCH, "run_acceptance_fixture_wrong_failure")


def _summary(payload: dict[str, object]) -> dict[str, object]:
    return acceptance.summarize_run_acceptance_result(payload)


def _entry_map(kind: str, limit: int) -> dict[str, object]:
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    entry_wire._map(transcript, "7" * 64, kind)
    result, connector, _ = entry_wire._run(transcript, "map", limit)
    connector.require_complete(1)
    return result


def _default_defeat() -> dict[str, object]:
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    entry_wire._combat_defeat(transcript, "a" * 64)
    result, connector, _ = entry_wire._run(transcript, None, 1)
    connector.require_complete(1)
    return result


def _entry_reward() -> dict[str, object]:
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    entry_wire._reward(transcript)
    entry_wire._add(transcript, entry_wire.map_client._MAP_WAITING, entry_wire._GET_MAP)
    entry_wire._add(
        transcript, entry_wire._map_ready("5" * 64, "shop"), entry_wire._GET_MAP
    )
    entry_wire._map(transcript, "6" * 64, "shop")
    result, connector, _ = entry_wire._run(transcript, "reward", 1)
    connector.require_complete(3)
    return result


def _reward_complete(gold: int, deck_count: int) -> bytes:
    reward_fixture = entry_wire.reward_fixture
    return reward_fixture._body(
        {
            "schema_version": 1,
            "status": "complete",
            "decision_kind": "reward",
            "actionable": False,
            "decision_id": None,
            "screen_kind": "map",
            "player": reward_fixture._player(gold, deck_count),
            "rewards": [],
            "legal_actions": [],
        }
    )


def _child_reward_result() -> dict[str, object]:
    reward_fixture = entry_wire.reward_fixture
    first_id, second_id = "1" * 64, "2" * 64
    child = reward_fixture._child(first_id, 1)
    parent = reward_fixture._parent(second_id, 2, deck_count=11)
    parent["rewards"] = []
    parent["legal_actions"] = [parent["legal_actions"][-1]]
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    entry_wire._base(transcript)
    entry_wire._add(transcript, reward_fixture._body(child), entry_wire._GET_REWARD)
    entry_wire._add(
        transcript,
        entry_wire._receipt(first_id, "choose:0"),
        entry_wire._post(entry_wire._REWARD_POST, first_id, "choose:0"),
    )
    entry_wire._add(transcript, reward_fixture._body(parent), entry_wire._GET_REWARD)
    entry_wire._add(
        transcript,
        entry_wire._receipt(second_id, "proceed"),
        entry_wire._post(entry_wire._REWARD_POST, second_id, "proceed"),
    )
    entry_wire._add(transcript, _reward_complete(99, 11), entry_wire._GET_REWARD)
    connector = entry_wire._Connector(transcript)
    credential = bytearray(entry_wire._CREDENTIAL)
    with entry_wire._clock():
        result = entry_wire.reward_client._run_apply_reward(
            credential, "first-card", connector
        )
    connector.require_complete(2)
    if any(credential):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_child_reward_credential")
    return result


def _card_reward_result() -> dict[str, object]:
    reward_fixture = entry_wire.reward_fixture
    ids = [str(index) * 64 for index in range(4)]
    initial = reward_fixture._parent(ids[0], 0)
    after_gold = reward_fixture._parent(ids[1], 1, gold=113)
    after_gold["rewards"] = after_gold["rewards"][1:]
    for slot, reward in enumerate(after_gold["rewards"]):
        reward["reward_slot"] = slot
    after_gold["legal_actions"] = [
        {
            "action_id": "open:0",
            "kind": "open_card",
            "reward_slot": 0,
            "card_slot": None,
        },
        {
            "action_id": "proceed",
            "kind": "proceed",
            "reward_slot": None,
            "card_slot": None,
        },
    ]
    child = reward_fixture._child(ids[2], 2, gold=113)
    after_card = reward_fixture._parent(ids[3], 3, gold=113, deck_count=11)
    after_card["rewards"] = [after_card["rewards"][-1]]
    after_card["rewards"][0]["reward_slot"] = 0
    after_card["legal_actions"] = [after_card["legal_actions"][-1]]
    states = (initial, after_gold, child, after_card)
    actions = ("claim:0", "open:0", "choose:0", "proceed")
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    entry_wire._base(transcript)
    entry_wire._add(
        transcript, reward_fixture._body(states[0]), entry_wire._GET_REWARD
    )
    for index, action_id in enumerate(actions):
        entry_wire._add(
            transcript,
            entry_wire._receipt(ids[index], action_id),
            entry_wire._post(entry_wire._REWARD_POST, ids[index], action_id),
        )
        next_body = (
            reward_fixture._body(states[index + 1])
            if index + 1 < len(states)
            else _reward_complete(113, 11)
        )
        entry_wire._add(transcript, next_body, entry_wire._GET_REWARD)
    connector = entry_wire._Connector(transcript)
    credential = bytearray(entry_wire._CREDENTIAL)
    with entry_wire._clock():
        result = entry_wire.reward_client._run_apply_reward(
            credential, "first-card", connector
        )
    connector.require_complete(4)
    if any(credential):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_card_reward_credential")
    return result


def _stale_terminal_combat() -> dict[str, object]:
    turn = combat_fixture.turn_fixture
    probe = combat_fixture.probe
    first_id, stale_id = "6" * 64, "7" * 64
    before = turn._combat(
        first_id,
        1,
        hp=80,
        block=0,
        energy=1,
        enemy_hp=6,
        hand=[
            turn._card(
                0, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True
            )
        ],
        actions=[turn._play(0, 0), turn._end_turn()],
    )
    resolving = turn._combat(
        stale_id,
        1,
        hp=80,
        block=0,
        energy=0,
        enemy_hp=0,
        hand=[],
        actions=[turn._end_turn()],
    )
    requests = [
        turn._get(probe._BASE_ROUTES[0][1]),
        turn._get(probe._BASE_ROUTES[1][1]),
        turn._get(probe._COMBAT_ROUTE[0][1]),
        turn._post(first_id, "play:0:0"),
        turn._get(probe._COMBAT_ROUTE[0][1]),
        turn._post(stale_id, "end_turn"),
        turn._get(probe._COMBAT_ROUTE[0][1]),
    ]
    responses = [
        turn._response(combat_fixture._HEALTH),
        turn._response(probe._MANIFEST_COMPATIBLE),
        turn._response(before),
        turn._response(turn._action_body(first_id, "play:0:0")),
        turn._response(resolving),
        turn._response(turn._action_body(stale_id, "end_turn", accepted=False)),
        turn._response(combat_fixture._terminal("victory", 1, hp=80, enemies=[])),
    ]
    connector = turn._Connector(responses, requests)
    credential = bytearray(combat_fixture._CREDENTIAL)
    result = combat_client._run_apply_combat(credential, "heuristic", connector)
    connector.assert_cleanup()
    if any(credential):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_stale_credential")
    return result


def _default_elite() -> dict[str, object]:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    elite_wire._combat_victory(transcript, "a")
    elite_wire._add_reward_then_map(transcript, "3" * 64, "elite", reward_id="4" * 64, revision=0)
    elite_wire._add(transcript, elite_wire._next_combat_ready("7" * 64), entry_wire._GET_COMBAT)
    elite_wire._combat_victory(transcript, "b")
    elite_wire._add_reward_then_map(transcript, "5" * 64, "shop", reward_id="6" * 64, revision=0)
    result, connector, _ = elite_wire._run(transcript, entry_phase="combat", floor_limit=2)
    connector.require_used_clean(sum(request.startswith(b"POST ") for _, request in transcript))
    return result


def _entry_room_handoff() -> dict[str, object]:
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    entry_wire._map(transcript, "b" * 64, "rest_site")
    entry_wire._add(transcript, entry_wire._room_ready("c" * 64, 4), entry_wire._GET_ROOM)
    entry_wire._room(transcript, 4)
    entry_wire._add(transcript, entry_wire._map_complete("rest_site"), entry_wire._GET_MAP)
    entry_wire._add(transcript, entry_wire.map_client._MAP_WAITING, entry_wire._GET_MAP)
    entry_wire._add(transcript, entry_wire._map_ready("d" * 64, "monster"), entry_wire._GET_MAP)
    result, connector, _ = entry_wire._run(transcript, "map", 1)
    connector.require_complete(3)
    return result


def _post_room_elite_victory() -> dict[str, object]:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    elite_wire._combat_victory(transcript, "c")
    elite_wire._add_reward_then_map(transcript, "9" * 64, "rest_site", reward_id="a" * 64, revision=0)
    elite_wire._add(transcript, entry_wire._room_ready("b" * 64, 4), entry_wire._GET_ROOM)
    entry_wire._room(transcript, 4)
    elite_wire._add(transcript, entry_wire._map_complete("rest_site"), entry_wire._GET_MAP)
    elite_wire._add(transcript, entry_wire.map_client._MAP_WAITING, entry_wire._GET_MAP)
    elite_wire._add(transcript, elite_wire._map_ready("c" * 64, "elite"), entry_wire._GET_MAP)
    elite_wire._map(transcript, "c" * 64, "elite")
    elite_wire._add(transcript, elite_wire._next_combat_ready("e" * 64), entry_wire._GET_COMBAT)
    elite_wire._combat_victory(transcript, "d")
    result, connector, _ = elite_wire._run(transcript, entry_phase="combat")
    connector.require_used_clean(sum(request.startswith(b"POST ") for _, request in transcript))
    return result


def _post_room_final_slot_defeat() -> dict[str, object]:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    elite_wire._combat_victory(transcript, "6")
    elite_wire._add_reward_then_map(
        transcript, "1" * 64, "elite", reward_id="2" * 64, revision=0
    )
    elite_wire._add(
        transcript, elite_wire._next_combat_ready("3" * 64), entry_wire._GET_COMBAT
    )
    elite_wire._combat_victory(transcript, "7")
    elite_wire._add_reward_then_map(
        transcript, "4" * 64, "rest_site", reward_id="5" * 64, revision=0
    )
    elite_wire._add(
        transcript, entry_wire._room_ready("6" * 64, 4), entry_wire._GET_ROOM
    )
    entry_wire._room(transcript, 4)
    elite_wire._add(
        transcript, entry_wire._map_complete("rest_site"), entry_wire._GET_MAP
    )
    elite_wire._add(transcript, entry_wire.map_client._MAP_WAITING, entry_wire._GET_MAP)
    elite_wire._add(
        transcript, elite_wire._map_ready("7" * 64, "elite"), entry_wire._GET_MAP
    )
    elite_wire._map(transcript, "7" * 64, "elite")
    elite_wire._add(
        transcript, elite_wire._next_combat_ready("8" * 64), entry_wire._GET_COMBAT
    )
    elite_wire._combat_defeat(transcript, "9" * 64)
    result, connector, _ = elite_wire._run(
        transcript, entry_phase="combat", floor_limit=3
    )
    connector.require_used_clean(
        sum(request.startswith(b"POST ") for _, request in transcript)
    )
    return result


def _relabel_map_destination(value: dict[str, object], kind: str) -> None:
    value["before"]["candidates"][0]["kind"] = kind
    value["applied"]["node_kind"] = kind
    value["after"]["destination"]["kind"] = kind


def _result_contracts() -> None:
    stale_terminal = _stale_terminal_combat()
    acceptance._component(stale_terminal, "r0e_complete_combat")
    acceptance._component(_child_reward_result(), "r0i_reward_resolution")
    acceptance._component(_card_reward_result(), "r0i_reward_resolution")
    detached_trace = copy.deepcopy(stale_terminal)
    detached_trace["actions"][0]["player_hp_after"] = 79
    detached_trace["actions"][0]["enemy_hp_before"] = 6_000_000
    acceptance._component(detached_trace, "r0e_complete_combat")
    elite_result = _default_elite()
    first_floor = elite_result["floors"][0]
    if (
        first_floor["reward"]["before"]["player"]["hp"]
        <= first_floor["combat"]["final_player"]["hp"]
    ):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_bounded_healing_missing")
    entry_results = (
        (_default_defeat(), "combat"),
        (_entry_reward(), "reward"),
        (_entry_map("shop", 1), "map"),
    )
    for entry_result, entry_phase in entry_results:
        if _summary(entry_result)["entry_phase"] != entry_phase:
            fail(EXIT_MISMATCH, "run_acceptance_fixture_entry_phase")
    results = [
        (entry_results[0][0], "run_defeat"),
        (_entry_map("shop", 1), "floor_limit_reached"),
        (_entry_map("shop", 2), "unsupported_destination_kind"),
        (_entry_map("boss", 2), "act_boundary_reached"),
        (entry_results[1][0], "floor_limit_reached"),
        (elite_result, "floor_limit_reached"),
        (_entry_room_handoff(), "room_handoff_complete"),
        (_post_room_elite_victory(), "room_continuation_complete"),
        (_post_room_final_slot_defeat(), "run_defeat"),
    ]
    for result, reason in results:
        summary = _summary(result)
        if summary["termination"]["reason"] != reason or set(summary) != {
            "schema_version", "status", "milestone", "source_milestone", "entry_phase",
            "processed_floor_count", "completed_floor_count", "action_totals", "termination",
            "terminal_combat_outcome",
        }:
            fail(EXIT_MISMATCH, "run_acceptance_fixture_actual_result")


def _malformed_and_privacy() -> None:
    result = _default_elite()
    for mutate in (
        lambda value: value.update({"canary": "RAW-SECRET"}),
        lambda value: value["action_totals"].update({"total": 1}),
        lambda value: value["floors"][0].update({"destination_kind": "monster"}),
        lambda value: value["termination"].update({"destination_kind": None}),
        lambda value: value.update({"completed_floor_count": True}),
        lambda value: value.update({"milestone": []}),
        lambda value: value["termination"].update({"reason": []}),
        lambda value: value["floors"][0]["combat"].update({"final_player": {}}),
        lambda value: value["floors"][0]["combat"]["final_player"].update({"hp": -9}),
        lambda value: value["floors"][0]["combat"]["actions"][0].update({"raw_canary": "CANARY"}),
        lambda value: value["floors"][0]["reward"]["before"]["rewards"][0].update({"cards": [{"raw_canary": "SYNTHETIC"}]}),
        lambda value: value["floors"][0]["reward"].update({"claimed_gold": -1}),
        lambda value: value["floors"][0]["map"]["before"]["candidates"][0].update({"kind": "CANARY"}),
        lambda value: value["providers"].update({"combat": "CANARY"}),
    ):
        malformed = copy.deepcopy(result)
        mutate(malformed)
        _expect_failure(lambda: _summary(malformed), "run_acceptance_result_mismatch")
    canary = copy.deepcopy(result)
    canary["floors"][0]["combat"]["raw_canary"] = "CANARY-PROVIDER"
    _expect_failure(lambda: _summary(canary), "run_acceptance_result_mismatch")
    room_at_cap = _entry_room_handoff()
    room_at_cap["floor_limit"] = 3
    _expect_failure(lambda: _summary(room_at_cap), "run_acceptance_result_mismatch")
    post_room = _post_room_elite_victory()
    post_room["room_handoff"]["post_room_map"]["applied"]["node_kind"] = "shop"
    post_room["room_handoff"]["post_room_map"]["after"]["destination"]["kind"] = "shop"
    post_room["termination"]["destination_kind"] = "shop"
    _expect_failure(lambda: _summary(post_room), "run_acceptance_result_mismatch")
    floor_with_room = _default_elite()
    floor_with_room["room_handoff"] = copy.deepcopy(_entry_room_handoff()["room_handoff"])
    _expect_failure(lambda: _summary(floor_with_room), "run_acceptance_result_mismatch")
    relabeled_room = _entry_room_handoff()
    relabeled_room["room_handoff"]["destination_kind"] = "ancient"
    _expect_failure(lambda: _summary(relabeled_room), "run_acceptance_result_mismatch")
    relabeled_continuation = _post_room_elite_victory()
    relabeled_continuation["termination"]["reason"] = "unsupported_destination_kind"
    _expect_failure(lambda: _summary(relabeled_continuation), "run_acceptance_result_mismatch")
    defeat_after_shop = _entry_map("shop", 2)
    defeat_after_shop["termination"] = {"reason": "run_defeat", "after_floor": 1, "destination_kind": None}
    defeat_after_shop["terminal_combat"] = copy.deepcopy(_default_defeat()["terminal_combat"])
    defeat_after_shop["action_totals"]["combat"] = 1
    defeat_after_shop["action_totals"]["total"] += 1
    _expect_failure(lambda: _summary(defeat_after_shop), "run_acceptance_result_mismatch")
    leaf_mutations = (
        (_default_elite, lambda value: value["floors"][0]["combat"]["actions"][0].update({"step": True})),
        (_default_defeat, lambda value: value["terminal_combat"]["final_enemies"][0].update({"hp": -1})),
        (_default_defeat, lambda value: value["terminal_combat"]["final_enemies"][0].update({"index": False})),
        (_default_defeat, lambda value: value["terminal_combat"]["final_enemies"][0].update({"id": {"raw": "CANARY"}})),
        (_default_defeat, lambda value: value["terminal_combat"]["actions"][0].update({"step": 0})),
        (_default_defeat, lambda value: value["terminal_combat"]["actions"][0].update({"basis": "CANARY"})),
        (_default_elite, lambda value: value["floors"][0]["reward"]["before"].update({"decision_id": "CANARY"})),
        (_default_elite, lambda value: value["floors"][0]["reward"]["after"]["player"].update({"gold": -1})),
        (_default_elite, lambda value: value["floors"][0]["reward"]["before"]["legal_actions"][0].update({"kind": "CANARY"})),
        (_default_elite, lambda value: value["floors"][0]["reward"]["applied"][0].update({"decision_revision": -1})),
        (_default_elite, lambda value: value["floors"][0]["reward"].update({"selected_cards": [{"raw": "CANARY"}]})),
        (_default_elite, lambda value: value["floors"][0]["reward"]["before"]["rewards"][0].update({"reward_slot": False})),
        (_default_elite, lambda value: value["floors"][0]["map"]["before"]["candidates"][0].update({"col": -1})),
        (_default_elite, lambda value: value["floors"][0]["map"]["before"]["candidates"][0].update({"candidate_index": False})),
        (_default_elite, lambda value: value["floors"][0]["map"]["before"]["legal_actions"][0].update({"candidate_index": False})),
        (_default_elite, lambda value: value["floors"][0]["map"]["before"]["legal_actions"][0].update({"action_id": "CANARY"})),
        (_default_elite, lambda value: value["floors"][0]["map"]["applied"].update({"basis": "CANARY"})),
        (_entry_room_handoff, lambda value: value["room_handoff"]["room"]["actions"][0].update({"basis": "CANARY"})),
        (_entry_room_handoff, lambda value: value["room_handoff"]["room"]["final"].update({"raw_canary": "CANARY"})),
    )
    for factory, mutate in leaf_mutations:
        malformed = factory()
        mutate(malformed)
        _expect_failure(lambda malformed=malformed: _summary(malformed), "run_acceptance_result_mismatch")
    for mutate in (
        lambda value: value.update({"decision_provider": "CANARY"}),
        lambda value: value["actions"][0].update({"action_id": "play:00:0"}),
        lambda value: value["actions"][0].update({"basis": "no_safe_card"}),
        lambda value: value["actions"][0].update({"enemy_hp_before": 6_000_001}),
    ):
        malformed_combat = _stale_terminal_combat()
        mutate(malformed_combat)
        _expect_failure(
            lambda malformed_combat=malformed_combat: acceptance._component(
                malformed_combat, "r0e_complete_combat"
            ),
            "run_acceptance_result_mismatch",
        )
    malformed_reward = copy.deepcopy(result["floors"][0]["reward"])
    malformed_reward["applied"][-1].update(
        {"action_id": "claim:0", "kind": "claim_gold"}
    )
    _expect_failure(
        lambda: acceptance._component(malformed_reward, "r0i_reward_resolution"),
        "run_acceptance_result_mismatch",
    )
    wrong_map_choice = copy.deepcopy(result["floors"][0]["map"])
    wrong_map_choice["before"]["candidates"][0]["kind"] = "monster"
    wrong_map_choice["before"]["candidates"].append(
        {"candidate_index": 1, "col": 3, "row": 3, "kind": "elite"}
    )
    wrong_map_choice["before"]["legal_actions"].append(
        {"action_id": "select:1", "kind": "select_map_node", "candidate_index": 1}
    )
    wrong_map_choice["applied"]["node_kind"] = "monster"
    wrong_map_choice["after"]["destination"]["kind"] = "monster"
    _expect_failure(
        lambda: acceptance._component(wrong_map_choice, "r0g_map_selection"),
        "run_acceptance_result_mismatch",
    )
    wrong_room_phase = _entry_room_handoff()
    wrong_room_phase["room_handoff"]["room"]["actions"][-1][
        "phase"
    ] = "choose_or_proceed"
    _expect_failure(
        lambda: _summary(wrong_room_phase),
        "run_acceptance_result_mismatch",
    )
    wrong_first_card = _child_reward_result()
    wrong_first_card["applied"][0]["chosen_card"] = "BASH"
    wrong_first_card["selected_cards"][0] = "BASH"
    _expect_failure(
        lambda: acceptance._component(
            wrong_first_card, "r0i_reward_resolution"
        ),
        "run_acceptance_result_mismatch",
    )
    wrong_sole_claim = _card_reward_result()
    wrong_sole_claim["claimed_gold"] = 15
    wrong_sole_claim["after"]["player"]["gold"] = 114
    _expect_failure(
        lambda: acceptance._component(
            wrong_sole_claim, "r0i_reward_resolution"
        ),
        "run_acceptance_result_mismatch",
    )
    intermediate_noncombat = _default_elite()
    intermediate_noncombat["floors"][0]["destination_kind"] = "shop"
    _relabel_map_destination(intermediate_noncombat["floors"][0]["map"], "shop")
    _expect_failure(
        lambda: _summary(intermediate_noncombat),
        "run_acceptance_result_mismatch",
    )
    discontinuous_player = _default_elite()
    discontinuous_player["floors"][0]["reward"]["before"]["player"]["hp"] = 1
    discontinuous_player["floors"][0]["reward"]["after"]["player"]["hp"] = 1
    _expect_failure(
        lambda: _summary(discontinuous_player),
        "run_acceptance_result_mismatch",
    )
    room_at_floor_limit = _default_elite()
    final_floor = room_at_floor_limit["floors"][-1]
    final_floor["destination_kind"] = "rest_site"
    _relabel_map_destination(final_floor["map"], "rest_site")
    room_at_floor_limit["termination"]["destination_kind"] = "rest_site"
    _expect_failure(
        lambda: _summary(room_at_floor_limit),
        "run_acceptance_result_mismatch",
    )
    normal_defeat_at_cap = _default_elite()
    final_floor = normal_defeat_at_cap["floors"][-1]
    final_floor["destination_kind"] = "elite"
    _relabel_map_destination(final_floor["map"], "elite")
    normal_defeat_at_cap["terminal_combat"] = copy.deepcopy(
        _default_defeat()["terminal_combat"]
    )
    normal_defeat_at_cap["termination"] = {
        "reason": "run_defeat",
        "after_floor": 2,
        "destination_kind": None,
    }
    normal_defeat_at_cap["action_totals"]["combat"] += 1
    normal_defeat_at_cap["action_totals"]["total"] += 1
    _expect_failure(
        lambda: _summary(normal_defeat_at_cap),
        "run_acceptance_result_mismatch",
    )
    wrong_room_initiator = _post_room_elite_victory()
    wrong_room_initiator["floors"][0]["destination_kind"] = "elite"
    _relabel_map_destination(
        wrong_room_initiator["floors"][0]["map"], "elite"
    )
    _expect_failure(
        lambda: _summary(wrong_room_initiator),
        "run_acceptance_result_mismatch",
    )
    cap_handoff = copy.deepcopy(_entry_room_handoff()["room_handoff"])
    continuation_handoff = _post_room_elite_victory()["room_handoff"]
    optional_names = ("post_room_map", "next_combat_attempts", "next_combat")
    for mask in range(1, 7):
        malformed_handoff = copy.deepcopy(cap_handoff)
        for bit, name in enumerate(optional_names):
            if mask & (1 << bit):
                malformed_handoff[name] = copy.deepcopy(continuation_handoff[name])
        _expect_failure(
            lambda malformed_handoff=malformed_handoff: acceptance._room_handoff(
                malformed_handoff
            ),
            "run_acceptance_result_mismatch",
        )
    null_continuation = copy.deepcopy(cap_handoff)
    null_continuation.update({name: None for name in optional_names})
    _expect_failure(
        lambda: acceptance._room_handoff(null_continuation),
        "run_acceptance_result_mismatch",
    )
    wrong_continuation_floor = _post_room_final_slot_defeat()
    wrong_continuation_floor["termination"]["after_floor"] = 1
    _expect_failure(
        lambda: _summary(wrong_continuation_floor),
        "run_acceptance_result_mismatch",
    )


def _in_process_operation_and_fixed_failures() -> None:
    result = _default_defeat()
    with patch.object(live.run, "operation", return_value=result) as operation:
        summary = live.operation()
    if operation.call_count != 1 or summary != _summary(result):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_in_process_operation")
    for argument_count in (14, 16):
        arguments = [f"argument-{index}" for index in range(argument_count)]
        def delegated() -> dict[str, object]:
            if sys.argv[1:] != arguments:
                fail(EXIT_MISMATCH, "run_acceptance_fixture_argument_delegation")
            return result
        with patch.object(sys, "argv", ["apply_run_acceptance_live.py", *arguments]), patch.object(live.run, "operation", side_effect=delegated):
            live.operation()
    buffered = copy.deepcopy(result)
    mutable_canary = bytearray(b"RAW-CANARY")
    buffered["fixture_buffer"] = mutable_canary
    with patch.object(live.run, "operation", return_value=buffered):
        _expect_failure(live.operation, "run_acceptance_result_mismatch")
    if any(mutable_canary):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_buffer_cleanup")
    with patch.object(live.run, "operation", side_effect=RuntimeError("RAW-CANARY")):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    if len(acceptance._KNOWN_PRODUCTION_FAILURE_CODES) != 192:
        fail(EXIT_MISMATCH, "run_acceptance_fixture_failure_code_closure")
    for known in acceptance._KNOWN_PRODUCTION_FAILURE_CODES:
        with patch.object(
            live.run,
            "operation",
            side_effect=ToolFailure(EXIT_MISMATCH, known),
        ):
            _expect_failure(live.operation, known)
    known = "run_map_result_mismatch"
    for exit_code in (2, 3, 5):
        with patch.object(live.run, "operation", side_effect=ToolFailure(exit_code, known)):
            _expect_failure(live.operation, known, exit_code)
    for exit_code, code in (
        (1, known),
        (6, known),
        (EXIT_INTERNAL, "run_acceptance_result_mismatch"),
        (4.0, "run_acceptance_result_mismatch"),
        (_ExplosiveEquality(), "run_acceptance_result_mismatch"),
        (EXIT_MISMATCH, _ExplosiveEquality()),
    ):
        with patch.object(live.run, "operation", side_effect=ToolFailure(exit_code, code)):
            _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    elite_wire._map(transcript, "e" * 64, "elite")
    elite_wire._add(transcript, elite_wire._next_combat_ready("0" * 64), entry_wire._GET_COMBAT)
    elite_wire._combat_victory(transcript, "d")
    elite_wire._add(transcript, elite_wire.reward_client._REWARD_UNSUPPORTED, entry_wire._GET_REWARD)
    connector, credentials = elite_wire._Connector(transcript), elite_wire._Credentials()
    def actual_failure() -> dict[str, object]:
        with entry_wire._clock():
            return elite_wire.run._run_bounded_run(credentials, connector, "first-legal", "first-card", "elite", "safe", 3, entry_phase="map")
    with patch.object(live.run, "operation", side_effect=actual_failure):
        _expect_failure(live.operation, "reward_state_unsupported")
    credentials.require_zeroed()
    connector.require_used_clean(5)
    decision = "f" * 64
    for response, code in (
        (elite_wire.map_fixture._action_body(decision, "select:0", "stale_decision"), "map_action_stale_decision"),
        (elite_wire.map_fixture._action_body(decision, "select:0", "invalid_action"), "map_action_invalid_action"),
        (TimeoutError("SYNTHETIC-CANARY"), "map_action_transport_failure"),
    ):
        receipt_transcript: list[tuple[bytes | BaseException, bytes]] = []
        entry_wire._base(receipt_transcript)
        elite_wire._add(receipt_transcript, elite_wire._map_ready(decision, "elite"), entry_wire._GET_MAP)
        expected = entry_wire._post(entry_wire._MAP_POST, decision, "select:0")
        receipt_transcript.append((response if isinstance(response, BaseException) else elite_wire._http(response), expected))
        receipt_connector, receipt_credentials = elite_wire._Connector(receipt_transcript), elite_wire._Credentials()
        def actual_receipt_failure() -> dict[str, object]:
            with entry_wire._clock():
                return elite_wire.run._run_bounded_run(receipt_credentials, receipt_connector, "first-legal", "first-card", "elite", "safe", 3, entry_phase="map")
        with patch.object(live.run, "operation", side_effect=actual_receipt_failure):
            _expect_failure(live.operation, code)
        receipt_credentials.require_zeroed()
        receipt_connector.require_used_clean(1)
    with patch.object(live.run, "operation", side_effect=ToolFailure(EXIT_MISMATCH, "SYNTHETIC-ARBITRARY-CANARY")):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    with patch.object(live.run, "operation", side_effect=ToolFailure(EXIT_MISMATCH, ["SYNTHETIC-CANARY"])):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    with patch.object(live.run, "operation", side_effect=KeyboardInterrupt):
        try:
            live.operation()
        except KeyboardInterrupt:
            pass
        else:
            fail(EXIT_MISMATCH, "run_acceptance_fixture_interrupt_swallowed")
    with patch.object(live.run, "operation", side_effect=SystemExit("SYNTHETIC-CANARY")):
        _expect_failure(live.operation, "run_acceptance_callback_failure", EXIT_INTERNAL)
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(live.run, "operation", side_effect=RuntimeError("RAW-CANARY")), redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(live.operation)
    if (
        exit_code != EXIT_INTERNAL
        or stdout.getvalue() != '{"schema_version":1,"status":"failed","code":"run_acceptance_callback_failure"}\n'
        or stderr.getvalue() != ""
        or "CANARY" in stdout.getvalue()
    ):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_fixed_failure_output")
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(live.run, "operation", side_effect=SystemExit("SYNTHETIC-CANARY")), redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(live.operation)
    if exit_code != EXIT_INTERNAL or "CANARY" in stdout.getvalue() + stderr.getvalue():
        fail(EXIT_MISMATCH, "run_acceptance_fixture_system_exit_output")
    view_backing = bytearray(b"RAW-MEMORYVIEW-CANARY")
    writable_view = memoryview(view_backing)
    view_result = copy.deepcopy(result)
    view_result["fixture_view"] = writable_view
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(live.run, "operation", return_value=view_result), redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(live.operation)
    writable_view.release()
    if (
        exit_code != EXIT_MISMATCH
        or stdout.getvalue()
        != '{"schema_version":1,"status":"failed","code":"run_acceptance_result_mismatch"}\n'
        or stderr.getvalue() != ""
        or any(view_backing)
        or "CANARY" in stdout.getvalue()
    ):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_memoryview_cleanup")
    nested_backing = bytearray(b"RAW-NESTED-CANARY")
    nested_view = memoryview(nested_backing).toreadonly()
    cycle: list[object] = []
    cycle.extend((cycle, nested_view))
    hostile_result = copy.deepcopy(result)
    hostile_result["fixture_hostile"] = _HostileValues({"cycle": cycle})
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(live.run, "operation", return_value=hostile_result), redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(live.operation)
    nested_view.release()
    if (
        exit_code != EXIT_MISMATCH
        or stderr.getvalue() != ""
        or any(nested_backing)
        or "CANARY" in stdout.getvalue()
    ):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_nested_cleanup")
    released_backing = bytearray(b"RAW-RELEASED-CANARY")
    released_view = memoryview(released_backing)
    released_view.release()
    released_result = copy.deepcopy(result)
    released_result["fixture_released"] = released_view
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(live.run, "operation", return_value=released_result), redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(live.operation)
    if (
        exit_code != EXIT_MISMATCH
        or stderr.getvalue() != ""
        or "CANARY" in stdout.getvalue()
    ):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_released_view")
    failed_cleanup_view = memoryview(array("B", range(8)))[::2]
    failed_cleanup_result = copy.deepcopy(result)
    failed_cleanup_result["fixture_noncontiguous"] = failed_cleanup_view
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(live.run, "operation", return_value=failed_cleanup_result), redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(live.operation)
    failed_cleanup_view.release()
    if (
        exit_code != EXIT_INTERNAL
        or stdout.getvalue()
        != '{"schema_version":1,"status":"failed","code":"run_acceptance_callback_failure"}\n'
        or stderr.getvalue() != ""
        or "CANARY" in stdout.getvalue()
    ):
        fail(EXIT_MISMATCH, "run_acceptance_fixture_failed_cleanup")
    interrupted_view = memoryview(array("B", range(8)))[::2]
    interrupted_result = copy.deepcopy(result)
    interrupted_result["fixture_noncontiguous"] = interrupted_view
    with patch.object(live.run, "operation", return_value=interrupted_result), patch.object(
        live, "summarize_run_acceptance_result", side_effect=KeyboardInterrupt
    ):
        try:
            live.operation()
        except KeyboardInterrupt:
            pass
        else:
            fail(EXIT_MISMATCH, "run_acceptance_fixture_cleanup_interrupt")
    interrupted_view.release()


def operation() -> dict[str, object]:
    _result_contracts()
    _malformed_and_privacy()
    _in_process_operation_and_fixed_failures()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_run_acceptance_live_fixtures",
        "check_count": 3,
    }


if __name__ == "__main__":
    from tool_common import main
    main(operation)
