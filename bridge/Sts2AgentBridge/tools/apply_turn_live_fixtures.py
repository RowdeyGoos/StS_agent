#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

sys.dont_write_bytecode = True

import apply_turn_live as apply_turn
import probe_live as probe
from tool_common import EXIT_MISMATCH, ToolFailure, fail, main

_CREDENTIAL = b"0123456789abcdef" * 4
_HEALTH = (
    b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"'
    b"00000000000000000000000000000000"
    b'"}'
)


def _response(body: bytes) -> bytes:
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
        b"Cache-Control: no-store\r\n"
        b"X-Content-Type-Options: nosniff\r\n"
        b"Connection: close\r\n"
        b"\r\n" + body
    )


def _get(route: str) -> bytes:
    return bytes(probe._build_request(route, bytearray(_CREDENTIAL)))


def _post(decision_id: str, action_id: str) -> bytes:
    return bytes(
        probe._build_action_request(
            probe._ACTION_ROUTE,
            bytearray(_CREDENTIAL),
            decision_id,
            action_id,
        )
    )


def _action_body(decision_id: str, action_id: str, *, accepted: bool = True) -> bytes:
    status = "accepted" if accepted else "rejected"
    mutation = "queued" if accepted else "none"
    reason = "accepted" if accepted else "stale_decision"
    return json.dumps(
        {
            "schema_version": 1,
            "status": status,
            "mutation_state": mutation,
            "decision_id": decision_id,
            "action_id": action_id,
            "reason": reason,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")


def _combat(
    decision_id: str,
    round_number: int,
    *,
    hp: int,
    block: int,
    energy: int,
    enemy_hp: int,
    hand: list[dict[str, object]],
    actions: list[dict[str, object]],
) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "status": "ready",
            "decision_kind": "combat",
            "actionable": True,
            "decision_id": decision_id,
            "round": round_number,
            "player": {"hp": hp, "max_hp": 80, "block": block, "energy": energy},
            "enemies": [
                {
                    "index": 0,
                    "id": "NIBBIT",
                    "hp": enemy_hp,
                    "max_hp": 43,
                    "block": 0,
                    "intents": ["attack"],
                }
            ],
            "hand": hand,
            "legal_actions": actions,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")


def _card(
    hand_index: int,
    card_id: str,
    card_type: str,
    cost: str,
    target_type: str,
    playable: bool,
) -> dict[str, object]:
    return {
        "hand_index": hand_index,
        "id": card_id,
        "type": card_type,
        "cost": cost,
        "target_type": target_type,
        "playable": playable,
    }


def _play(hand_index: int, target_index: int | None = None) -> dict[str, object]:
    action_id = f"play:{hand_index}"
    if target_index is not None:
        action_id += f":{target_index}"
    return {
        "action_id": action_id,
        "kind": "play_card",
        "hand_index": hand_index,
        "target_index": target_index,
    }


def _end_turn() -> dict[str, object]:
    return {
        "action_id": "end_turn",
        "kind": "end_turn",
        "hand_index": None,
        "target_index": None,
    }


class _Socket:
    def __init__(self, response: bytes, expected_request: bytes) -> None:
        self.response = response
        self.expected_request = expected_request
        self.offset = 0
        self.closed = False
        self.write_shutdown = False
        self.request_buffers: list[bytearray] = []

    def settimeout(self, value: float) -> None:
        if value <= 0 or value > probe._SOCKET_OPERATION_TIMEOUT_SECONDS:
            fail(EXIT_MISMATCH, "turn_fixture_timeout")

    def sendall(self, request: bytearray) -> None:
        if bytes(request) != self.expected_request:
            fail(EXIT_MISMATCH, "turn_fixture_request")
        self.request_buffers.append(request)

    def shutdown(self, how: int) -> None:
        if how != probe.socket.SHUT_WR or not (self.request_buffers) or self.write_shutdown or self.closed:
            fail(EXIT_MISMATCH, "apply_turn_live_fixture_half_close")
        self.write_shutdown = True

    def recv(self, maximum: int) -> bytes:
        if not self.write_shutdown:
            fail(EXIT_MISMATCH, "apply_turn_live_fixture_receive_before_half_close")
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "turn_fixture_receive_bound")
        if self.offset >= len(self.response):
            return b""
        end = min(self.offset + 19, len(self.response))
        result = self.response[self.offset:end]
        self.offset = end
        return result

    def close(self) -> None:
        self.closed = True


class _Connector:
    def __init__(self, responses: list[bytes], requests: list[bytes]) -> None:
        self.responses = responses
        self.requests = requests
        self.offset = 0
        self.sockets: list[_Socket] = []

    def __call__(self) -> _Socket:
        if self.offset >= len(self.responses):
            fail(EXIT_MISMATCH, "turn_fixture_extra_connection")
        result = _Socket(self.responses[self.offset], self.requests[self.offset])
        self.offset += 1
        self.sockets.append(result)
        return result

    def assert_cleanup(self) -> None:
        if self.offset != len(self.responses):
            fail(EXIT_MISMATCH, "turn_fixture_missing_connection")
        if any(not item.closed for item in self.sockets):
            fail(EXIT_MISMATCH, "turn_fixture_socket_cleanup")
        for item in self.sockets:
            if any(any(request) for request in item.request_buffers):
                fail(EXIT_MISMATCH, "turn_fixture_request_not_zeroed")


def _round_two(decision_id: str, *, hp: int, enemy_hp: int) -> bytes:
    hand = [_card(0, "DEFEND_IRONCLAD", "skill", "1", "self", True)]
    return _combat(
        decision_id,
        2,
        hp=hp,
        block=0,
        energy=3,
        enemy_hp=enemy_hp,
        hand=hand,
        actions=[_play(0), _end_turn()],
    )


def _run_heuristic_turn() -> None:
    decisions = [str(index) * 64 for index in range(5)]
    state0 = _combat(
        decisions[0],
        1,
        hp=80,
        block=5,
        energy=2,
        enemy_hp=43,
        hand=[
            _card(0, "BASH", "attack", "2", "anyenemy", True),
            _card(1, "DEFEND_IRONCLAD", "skill", "1", "self", True),
            _card(2, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True),
            _card(3, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True),
        ],
        actions=[_play(0, 0), _play(1), _play(2, 0), _play(3, 0), _end_turn()],
    )
    state1 = _combat(
        decisions[1],
        1,
        hp=80,
        block=10,
        energy=1,
        enemy_hp=43,
        hand=[
            _card(0, "BASH", "attack", "2", "anyenemy", False),
            _card(1, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True),
            _card(2, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True),
        ],
        actions=[_play(1, 0), _play(2, 0), _end_turn()],
    )
    state2 = _combat(
        decisions[2],
        1,
        hp=80,
        block=10,
        energy=0,
        enemy_hp=37,
        hand=[
            _card(0, "BASH", "attack", "2", "anyenemy", False),
            _card(1, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", False),
        ],
        actions=[_end_turn()],
    )
    state3 = _combat(
        decisions[3],
        1,
        hp=80,
        block=10,
        energy=0,
        enemy_hp=37,
        hand=[],
        actions=[_end_turn()],
    )
    state4 = _round_two(decisions[4], hp=78, enemy_hp=37)
    action_steps = [
        (decisions[0], "play:1", state1),
        (decisions[1], "play:1:0", state2),
        (decisions[2], "end_turn", state3),
    ]
    requests = [
        _get(probe._BASE_ROUTES[0][1]),
        _get(probe._BASE_ROUTES[1][1]),
        _get(probe._COMBAT_ROUTE[0][1]),
    ]
    responses = [_response(_HEALTH), _response(probe._MANIFEST_COMPATIBLE), _response(state0)]
    for decision_id, action_id, following in action_steps:
        requests.extend([_post(decision_id, action_id), _get(probe._COMBAT_ROUTE[0][1])])
        responses.extend([_response(_action_body(decision_id, action_id)), _response(following)])
    requests.append(_get(probe._COMBAT_ROUTE[0][1]))
    responses.append(_response(state4))

    connector = _Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    payload = apply_turn._run_apply_turn(credential, "heuristic", connector)
    transitions = payload.get("transitions")
    if (
        payload.get("status") != "passed"
        or payload.get("milestone") != "r0d_one_turn"
        or payload.get("initial_round") != 1
        or payload.get("final_round") != 2
        or payload.get("accepted_action_count") != 3
        or payload.get("action_limit") != 6
        or payload.get("routes_checked") != 9
        or not isinstance(transitions, list)
        or [transition["applied"]["action_id"] for transition in transitions]
        != ["play:1", "play:1:0", "end_turn"]
    ):
        fail(EXIT_MISMATCH, "turn_fixture_heuristic_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "turn_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _run_first_legal_turn() -> None:
    before_id = "a" * 64
    mid_id = "b" * 64
    after_id = "c" * 64
    before = _combat(
        before_id,
        1,
        hp=80,
        block=0,
        energy=1,
        enemy_hp=43,
        hand=[_card(0, "STRIKE_IRONCLAD", "attack", "1", "anyenemy", True)],
        actions=[_play(0, 0), _end_turn()],
    )
    mid = _combat(
        mid_id,
        1,
        hp=80,
        block=0,
        energy=0,
        enemy_hp=37,
        hand=[],
        actions=[_end_turn()],
    )
    after = _round_two(after_id, hp=68, enemy_hp=37)
    requests = [
        _get(probe._BASE_ROUTES[0][1]),
        _get(probe._BASE_ROUTES[1][1]),
        _get(probe._COMBAT_ROUTE[0][1]),
        _post(before_id, "play:0:0"),
        _get(probe._COMBAT_ROUTE[0][1]),
        _post(mid_id, "end_turn"),
        _get(probe._COMBAT_ROUTE[0][1]),
        _get(probe._COMBAT_ROUTE[0][1]),
    ]
    responses = [
        _response(_HEALTH),
        _response(probe._MANIFEST_COMPATIBLE),
        _response(before),
        _response(_action_body(before_id, "play:0:0")),
        _response(mid),
        _response(_action_body(mid_id, "end_turn")),
        _response(probe._COMBAT_WAITING),
        _response(after),
    ]
    connector = _Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    payload = apply_turn._run_apply_turn(credential, "first-legal", connector)
    if (
        payload.get("accepted_action_count") != 2
        or payload.get("final_round") != 2
        or payload.get("routes_checked") != 7
    ):
        fail(EXIT_MISMATCH, "turn_fixture_first_legal_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "turn_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _reject_action_response() -> None:
    decision_id = "d" * 64
    before = _combat(
        decision_id,
        1,
        hp=80,
        block=0,
        energy=0,
        enemy_hp=43,
        hand=[],
        actions=[_end_turn()],
    )
    requests = [
        _get(probe._BASE_ROUTES[0][1]),
        _get(probe._BASE_ROUTES[1][1]),
        _get(probe._COMBAT_ROUTE[0][1]),
        _post(decision_id, "end_turn"),
    ]
    responses = [
        _response(_HEALTH),
        _response(probe._MANIFEST_COMPATIBLE),
        _response(before),
        _response(_action_body(decision_id, "end_turn", accepted=False)),
    ]
    connector = _Connector(responses, requests)
    credential = bytearray(_CREDENTIAL)
    try:
        apply_turn._run_apply_turn(credential, "heuristic", connector)
    except ToolFailure as failure:
        if failure.exit_code != EXIT_MISMATCH or failure.error_code != "action_response_mismatch":
            fail(EXIT_MISMATCH, "turn_fixture_wrong_rejection")
    else:
        fail(EXIT_MISMATCH, "turn_fixture_unexpected_pass")
    if any(credential):
        fail(EXIT_MISMATCH, "turn_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def operation() -> dict[str, object]:
    _run_heuristic_turn()
    _run_first_legal_turn()
    _reject_action_response()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_turn_live_fixtures",
        "checks": [
            "heuristic_complete_turn",
            "first_legal_complete_turn",
            "rejected_action_response",
        ],
        "check_count": 3,
    }


if __name__ == "__main__":
    main(operation)
