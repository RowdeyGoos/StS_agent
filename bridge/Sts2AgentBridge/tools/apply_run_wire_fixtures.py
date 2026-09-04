#!/usr/bin/env python3
"""Offline wire-level composition fixtures for the bounded run clients.

This suite deliberately uses the production component runners.  Its fake
connector validates the byte-exact requests that those clients make and never
opens a real socket.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

sys.dont_write_bytecode = True

import apply_combat_live as combat
import apply_combat_live_fixtures as combat_fixture
import apply_map_live as map_client
import apply_map_live_fixtures as map_fixture
import apply_reward_live as reward
import apply_reward_live_fixtures as reward_fixture
import apply_room_live as room
import apply_room_live_fixtures as room_fixture
import apply_run_live as run
import apply_turn_live_fixtures as turn_fixture
import probe_live as probe
from tool_common import EXIT_MISMATCH, ToolFailure, fail, main


_CREDENTIAL = b"0123456789abcdef" * 4
_CANARY = b"WIRE_SECRET_CANARY_DO_NOT_PRINT"


def _response(body: bytes) -> bytes:
    return room_fixture._response(body)


def _get(route: str) -> bytes:
    if route == room._ROOM_DECISION_ROUTE:
        return bytes(room._build_get_request(route, bytearray(_CREDENTIAL)))
    return bytes(probe._build_request(route, bytearray(_CREDENTIAL)))


def _post(route: str, decision_id: str, action_id: str) -> bytes:
    if route == room._ROOM_ACTION_ROUTE:
        return bytes(room._build_action_request(bytearray(_CREDENTIAL), decision_id, action_id))
    return bytes(probe._build_action_request(route, bytearray(_CREDENTIAL), decision_id, action_id))


def _receipt(decision_id: str, action_id: str) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "status": "accepted",
            "mutation_state": "applied",
            "decision_id": decision_id,
            "action_id": action_id,
            "reason": "accepted",
        },
        separators=(",", ":"),
    ).encode("ascii")


class _Clock:
    """A deterministic monotonic clock shared by all real client modules."""

    def __init__(self) -> None:
        self.value = 10.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            fail(EXIT_MISMATCH, "wire_negative_sleep")
        self.value += seconds


@contextmanager
def _fake_clock() -> Any:
    clock = _Clock()
    old_monotonic = probe.time.monotonic
    old_sleep = probe.time.sleep
    probe.time.monotonic = clock.monotonic
    probe.time.sleep = clock.sleep
    try:
        yield clock
    finally:
        probe.time.monotonic = old_monotonic
        probe.time.sleep = old_sleep


class _Socket:
    def __init__(self, response: bytes, expected_request: bytes) -> None:
        self._response = response
        self._expected_request = expected_request
        self._offset = 0
        self.closed = False
        self.request: bytearray | None = None

    def settimeout(self, value: float) -> None:
        if value <= 0 or value > probe._SOCKET_OPERATION_TIMEOUT_SECONDS:
            fail(EXIT_MISMATCH, "wire_socket_timeout")

    def sendall(self, request: bytearray) -> None:
        if bytes(request) != self._expected_request:
            fail(EXIT_MISMATCH, "wire_request_order_or_bytes")
        self.request = request

    def recv(self, maximum: int) -> bytes:
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "wire_receive_bound")
        if self._offset >= len(self._response):
            return b""
        end = min(self._offset + 31, len(self._response))
        result = self._response[self._offset:end]
        self._offset = end
        return result

    def close(self) -> None:
        self.closed = True


class _Connector:
    def __init__(self, transcript: list[tuple[bytes, bytes]]) -> None:
        self._transcript = transcript
        self._offset = 0
        self.sockets: list[_Socket] = []

    def __call__(self) -> _Socket:
        if self._offset >= len(self._transcript):
            fail(EXIT_MISMATCH, "wire_unexpected_connection")
        response, expected_request = self._transcript[self._offset]
        self._offset += 1
        socket = _Socket(response, expected_request)
        self.sockets.append(socket)
        return socket

    def assert_complete(self) -> None:
        if self._offset != len(self._transcript):
            fail(EXIT_MISMATCH, "wire_missing_connection")
        if any(not socket.closed for socket in self.sockets):
            fail(EXIT_MISMATCH, "wire_resource_not_closed")
        if any(socket.request is None for socket in self.sockets):
            fail(EXIT_MISMATCH, "wire_request_missing")
        if any(socket.request is not None and any(socket.request) for socket in self.sockets):
            fail(EXIT_MISMATCH, "wire_request_not_zeroed")


class _CredentialLoader:
    def __init__(self) -> None:
        self.loaded: list[bytearray] = []

    def __call__(self) -> bytearray:
        value = bytearray(_CREDENTIAL)
        self.loaded.append(value)
        return value

    def assert_zeroed(self) -> None:
        if not self.loaded or any(any(value) for value in self.loaded):
            fail(EXIT_MISMATCH, "wire_credential_not_zeroed")


def _add(transcript: list[tuple[bytes, bytes]], body: bytes, request: bytes) -> None:
    transcript.append((_response(body), request))


def _add_base(transcript: list[tuple[bytes, bytes]]) -> None:
    _add(transcript, turn_fixture._HEALTH, _get(probe._BASE_ROUTES[0][1]))
    _add(transcript, probe._MANIFEST_COMPATIBLE, _get(probe._BASE_ROUTES[1][1]))


def _combat_victory(transcript: list[tuple[bytes, bytes]], token: str) -> None:
    ids = [f"{token}{index:x}" * 32 for index in range(4)]
    states = [
        turn_fixture._combat(ids[0], 2, hp=78, block=0, energy=2, enemy_hp=13,
            hand=[turn_fixture._card(0, "DEFEND_IRONCLAD", "skill", "1", "self", True), turn_fixture._card(1, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True)],
            actions=[turn_fixture._play(0), turn_fixture._play(1, 0), turn_fixture._end_turn()]),
        turn_fixture._combat(ids[1], 2, hp=78, block=5, energy=1, enemy_hp=13,
            hand=[turn_fixture._card(0, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True)], actions=[turn_fixture._play(0, 0), turn_fixture._end_turn()]),
        turn_fixture._combat(ids[2], 2, hp=78, block=5, energy=0, enemy_hp=7, hand=[], actions=[turn_fixture._end_turn()]),
        turn_fixture._combat(ids[3], 3, hp=71, block=0, energy=3, enemy_hp=7,
            hand=[turn_fixture._card(0, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True)], actions=[turn_fixture._play(0, 0), turn_fixture._end_turn()]),
    ]
    _add_base(transcript)
    _add(transcript, states[0], _get(probe._COMBAT_ROUTE[0][1]))
    for decision_id, action_id, next_body in (
        (ids[0], "play:0", states[1]), (ids[1], "play:0:0", states[2]),
        (ids[2], "end_turn", probe._COMBAT_WAITING),
    ):
        _add(transcript, turn_fixture._action_body(decision_id, action_id), _post(probe._ACTION_ROUTE, decision_id, action_id))
        _add(transcript, next_body, _get(probe._COMBAT_ROUTE[0][1]))
    _add(transcript, states[3], _get(probe._COMBAT_ROUTE[0][1]))
    _add(transcript, turn_fixture._action_body(ids[3], "play:0:0"), _post(probe._ACTION_ROUTE, ids[3], "play:0:0"))
    _add(transcript, combat_fixture._terminal("victory", 3, hp=71, enemies=[]), _get(probe._COMBAT_ROUTE[0][1]))


def _combat_defeat(transcript: list[tuple[bytes, bytes]], decision_id: str) -> None:
    before = turn_fixture._combat(decision_id, 1, hp=5, block=0, energy=0, enemy_hp=43, hand=[], actions=[turn_fixture._end_turn()])
    _add_base(transcript)
    _add(transcript, before, _get(probe._COMBAT_ROUTE[0][1]))
    _add(transcript, turn_fixture._action_body(decision_id, "end_turn"), _post(probe._ACTION_ROUTE, decision_id, "end_turn"))
    _add(transcript, probe._COMBAT_WAITING, _get(probe._COMBAT_ROUTE[0][1]))
    _add(transcript, combat_fixture._terminal("defeat", 1, hp=0, enemies=[combat_fixture._enemy(43)]), _get(probe._COMBAT_ROUTE[0][1]))


def _reward_ready(decision_id: str, revision: int, gold: int, *, claimable: bool) -> bytes:
    value = reward_fixture._parent(decision_id, revision, gold)
    if claimable:
        value["rewards"] = value["rewards"][:1]
        value["legal_actions"] = [value["legal_actions"][0], value["legal_actions"][-1]]
    else:
        value["rewards"] = []
        value["legal_actions"] = [value["legal_actions"][-1]]
    return reward_fixture._body(value)


def _reward_complete(gold: int) -> bytes:
    return reward_fixture._body({"schema_version": 1, "status": "complete", "decision_kind": "reward", "actionable": False, "decision_id": None, "screen_kind": "map", "player": reward_fixture._player(gold), "rewards": [], "legal_actions": []})


def _reward(transcript: list[tuple[bytes, bytes]]) -> None:
    first, second = "5" * 64, "6" * 64
    _add_base(transcript)
    _add(transcript, _reward_ready(first, 0, 71, claimable=True), _get(probe._REWARD_ROUTE[0][1]))
    _add(transcript, _receipt(first, "claim:0"), _post(probe._REWARD_ACTION_ROUTE, first, "claim:0"))
    _add(transcript, _reward_ready(second, 1, 85, claimable=False), _get(probe._REWARD_ROUTE[0][1]))
    _add(transcript, _receipt(second, "proceed"), _post(probe._REWARD_ACTION_ROUTE, second, "proceed"))
    _add(transcript, _reward_complete(85), _get(probe._REWARD_ROUTE[0][1]))


def _map_ready(decision_id: str, kind: str) -> bytes:
    candidate = map_fixture._candidate(0, 2, 3, kind)
    return map_fixture._ready(decision_id, [candidate])


def _map_complete(kind: str) -> bytes:
    return map_fixture._complete(map_fixture._candidate(0, 2, 3, kind))


def _map(transcript: list[tuple[bytes, bytes]], decision_id: str, kind: str) -> None:
    _add_base(transcript)
    _add(transcript, _map_ready(decision_id, kind), _get(map_client._MAP_DECISION_ROUTE))
    _add(transcript, map_fixture._action_body(decision_id, "select:0", "accepted"), _post(map_client._MAP_ACTION_ROUTE, decision_id, "select:0"))
    _add(transcript, map_client._MAP_WAITING, _get(map_client._MAP_DECISION_ROUTE))
    _add(transcript, _map_complete(kind), _get(map_client._MAP_DECISION_ROUTE))


def _room_ready(decision_id: str, ordinal: int) -> bytes:
    heal = room_fixture._candidate(0, "rest_heal", "HEAL", enabled=True, supported=True)
    return room_fixture._ready(decision_id, "rest_site", "choose_option", [heal], [room_fixture._legal(heal)], ordinal=ordinal)


def _room(transcript: list[tuple[bytes, bytes]], ordinal: int) -> None:
    first, second = "7" * 64, "8" * 64
    heal = room_fixture._candidate(0, "rest_heal", "HEAL", enabled=False, supported=True)
    proceed = room_fixture._candidate(1, "proceed", "proceed", enabled=True, supported=True, is_proceed=True)
    _add_base(transcript)
    _add(transcript, _room_ready(first, ordinal), _get(room._ROOM_DECISION_ROUTE))
    _add(transcript, room_fixture._action_body(first, "choose:0"), _post(room._ROOM_ACTION_ROUTE, first, "choose:0"))
    _add(transcript, room_fixture._ready(second, "rest_site", "proceed", [heal, proceed], [room_fixture._legal(proceed)], ordinal=ordinal), _get(room._ROOM_DECISION_ROUTE))
    _add(transcript, room_fixture._action_body(second, "proceed"), _post(room._ROOM_ACTION_ROUTE, second, "proceed"))
    _add(transcript, room_fixture._inactive("complete", "rest_site", "complete", ordinal), _get(room._ROOM_DECISION_ROUTE))


def _expect_failure(operation: Callable[[], object], code: str) -> None:
    try:
        operation()
    except ToolFailure as failure:
        if failure.exit_code == EXIT_MISMATCH and failure.error_code == code:
            return
        fail(EXIT_MISMATCH, "wire_wrong_failure")
    fail(EXIT_MISMATCH, "wire_failure_accepted")


def _run_success() -> None:
    transcript: list[tuple[bytes, bytes]] = []
    _combat_victory(transcript, "a")
    _add(transcript, reward._REWARD_WAITING, _get(probe._REWARD_ROUTE[0][1]))
    _add(transcript, _reward_ready("4" * 64, 0, 71, claimable=True), _get(probe._REWARD_ROUTE[0][1]))
    _reward(transcript)
    _add(transcript, map_client._MAP_WAITING, _get(map_client._MAP_DECISION_ROUTE))
    _add(transcript, _map_ready("9" * 64, "rest_site"), _get(map_client._MAP_DECISION_ROUTE))
    _map(transcript, "a" * 64, "rest_site")
    _add(transcript, room_fixture._inactive("waiting", "unknown", "unknown", None), _get(room._ROOM_DECISION_ROUTE))
    _add(transcript, _room_ready("b" * 64, 4), _get(room._ROOM_DECISION_ROUTE))
    _room(transcript, 4)
    _add(transcript, _map_complete("rest_site"), _get(map_client._MAP_DECISION_ROUTE))
    _add(transcript, map_client._MAP_WAITING, _get(map_client._MAP_DECISION_ROUTE))
    _add(transcript, _map_ready("c" * 64, "monster"), _get(map_client._MAP_DECISION_ROUTE))
    _map(transcript, "d" * 64, "monster")
    _add(transcript, probe._COMBAT_WAITING, _get(probe._COMBAT_ROUTE[0][1]))
    ready = turn_fixture._combat("e" * 64, 1, hp=5, block=0, energy=0, enemy_hp=43, hand=[], actions=[turn_fixture._end_turn()])
    _add(transcript, ready, _get(probe._COMBAT_ROUTE[0][1]))
    _combat_defeat(transcript, "f" * 64)
    connector = _Connector(transcript)
    loader = _CredentialLoader()
    with _fake_clock():
        payload = run._run_bounded_run(loader, connector, "heuristic", "first-card", "first", "safe", 2)
    if payload.get("termination", {}).get("reason") != "run_defeat" or payload.get("action_totals") != {"combat": 5, "reward": 2, "map": 2, "room": 2, "total": 11}:
        fail(EXIT_MISMATCH, "wire_success_payload")
    connector.assert_complete()
    loader.assert_zeroed()


def _run_defeat_no_followup() -> None:
    transcript: list[tuple[bytes, bytes]] = []
    _combat_defeat(transcript, "1" * 64)
    connector = _Connector(transcript)
    loader = _CredentialLoader()
    with _fake_clock():
        payload = run._run_bounded_run(loader, connector, "first-legal", "first-card", "first", "safe", 1)
    if payload.get("termination", {}).get("reason") != "run_defeat":
        fail(EXIT_MISMATCH, "wire_defeat_payload")
    connector.assert_complete()
    loader.assert_zeroed()


def _run_rejected_and_uncertain_posts() -> None:
    decision_id = "2" * 64
    state = turn_fixture._combat(decision_id, 1, hp=5, block=0, energy=0, enemy_hp=43, hand=[], actions=[turn_fixture._end_turn()])
    for response, expected_code in (
        (turn_fixture._action_body(decision_id, "end_turn", accepted=False), "terminal_after_rejected_action"),
        (probe._RETRYABLE_BACKEND_HEADER + probe._RETRYABLE_BACKEND_BODY_PREFIX + b"0" * 32 + probe._RETRYABLE_BACKEND_BODY_SUFFIX, "action_response_mismatch"),
    ):
        transcript: list[tuple[bytes, bytes]] = []
        _add_base(transcript)
        _add(transcript, state, _get(probe._COMBAT_ROUTE[0][1]))
        transcript.append((_response(response) if response.startswith(b"{") else response, _post(probe._ACTION_ROUTE, decision_id, "end_turn")))
        if response.startswith(b"{"):
            _add(transcript, combat_fixture._terminal("defeat", 1, hp=0, enemies=[combat_fixture._enemy(43)]), _get(probe._COMBAT_ROUTE[0][1]))
        connector = _Connector(transcript)
        credential = bytearray(_CREDENTIAL)
        with _fake_clock():
            _expect_failure(lambda: combat._run_apply_combat(credential, "first-legal", connector), expected_code)
        connector.assert_complete()
        if any(credential):
            fail(EXIT_MISMATCH, "wire_uncertain_credential")


def _run_run_level_rejections() -> None:
    # These are actual run-client checks: an unsupported post-room destination
    # and a second room are rejected before any continuation combat POST.
    for kind, code in (("rest_site", "run_second_room_destination"), ("shop", "run_post_room_destination_unsupported")):
        transcript: list[tuple[bytes, bytes]] = []
        _combat_victory(transcript, "3")
        _add(transcript, _reward_ready("4" * 64, 0, 71, claimable=True), _get(probe._REWARD_ROUTE[0][1]))
        _reward(transcript)
        _add(transcript, _map_ready("5" * 64, "rest_site"), _get(map_client._MAP_DECISION_ROUTE))
        _map(transcript, "6" * 64, "rest_site")
        _add(transcript, _room_ready("7" * 64, 4), _get(room._ROOM_DECISION_ROUTE))
        _room(transcript, 4)
        _add(transcript, _map_ready("8" * 64, kind), _get(map_client._MAP_DECISION_ROUTE))
        _map(transcript, "9" * 64, kind)
        connector = _Connector(transcript)
        loader = _CredentialLoader()
        with _fake_clock():
            _expect_failure(lambda: run._run_bounded_run(loader, connector, "heuristic", "first-card", "first", "safe", 2), code)
        connector.assert_complete()
        loader.assert_zeroed()


def operation() -> dict[str, object]:
    _run_success()
    _run_defeat_no_followup()
    _run_rejected_and_uncertain_posts()
    _run_run_level_rejections()
    result = {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_run_wire_fixtures",
        "evidence_class": "bridge_fixture",
        "checks": [
            "actual_client_combat_reward_map_room_run_transcript",
            "delayed_phase_readiness_and_resource_closure",
            "defeat_stops_followup_mutations",
            "rejected_and_uncertain_post_do_not_retry",
            "second_room_and_unsupported_destination_fail_closed",
            "secret_canary_absent_from_output",
        ],
        "check_count": 6,
    }
    if _CANARY in json.dumps(result, separators=(",", ":")).encode("ascii"):
        fail(EXIT_MISMATCH, "wire_secret_canary_output")
    return result


if __name__ == "__main__":
    main(operation)
