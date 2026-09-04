#!/usr/bin/env python3
"""Literal wire transcripts for explicit bounded run phase entry.

The production run and component clients are exercised unchanged.  This file
only supplies a deterministic clock and a connector whose requests are exact
byte oracles; it is not a second run-state implementation.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

import apply_combat_live_fixtures as combat_fixture
import apply_map_live as map_client
import apply_map_live_fixtures as map_fixture
import apply_reward_live as reward_client
import apply_reward_live_fixtures as reward_fixture
import apply_room_live as room_client
import apply_room_live_fixtures as room_fixture
import apply_run_live as run
import apply_turn_live_fixtures as turn_fixture
import probe_live as probe
from tool_common import EXIT_MISMATCH, ToolFailure, fail, main, run_cli


_CREDENTIAL = b"0123456789abcdef" * 4
_CANARY = b"ENTRY_WIRE_CANARY_DO_NOT_PRINT"
_TOOLS = Path(__file__).resolve().parent
_BASE_COMMIT = "8212886"


def _http(body: bytes) -> bytes:
    return room_fixture._response(body)


_GET_HEALTH = (
    b"GET /probe/v0/health HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
)
_GET_MANIFEST = (
    b"GET /probe/v0/manifest HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
)
_GET_COMBAT = (
    b"GET /probe/v0/public/combat-decision HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
)
_GET_REWARD = (
    b"GET /probe/v0/public/reward-decision HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
)
_GET_MAP = (
    b"GET /probe/v0/public/map-decision HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
)
_GET_ROOM = (
    b"GET /probe/v0/public/room-decision HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
)


def _post(prefix: bytes, decision_id: str, action_id: str) -> bytes:
    return (
        prefix
        + decision_id.encode("ascii")
        + b"\r\nX-Sts2-Action-Id: "
        + action_id.encode("ascii")
        + b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
    )


_COMBAT_POST = (
    b"POST /probe/v0/public/combat-action HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nX-Sts2-Decision-Id: "
)
_REWARD_POST = (
    b"POST /probe/v0/public/reward-action HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nX-Sts2-Decision-Id: "
)
_MAP_POST = (
    b"POST /probe/v0/public/map-action HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nX-Sts2-Decision-Id: "
)
_ROOM_POST = (
    b"POST /probe/v0/public/room-action HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
    b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    b"\r\nX-Sts2-Decision-Id: "
)


def _receipt(decision_id: str, action_id: str) -> bytes:
    return json.dumps({"schema_version": 1, "status": "accepted", "mutation_state": "applied", "decision_id": decision_id, "action_id": action_id, "reason": "accepted"}, separators=(",", ":")).encode("ascii")


class _Clock:
    def __init__(self) -> None:
        self.value = 10.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            fail(EXIT_MISMATCH, "entry_wire_negative_sleep")
        self.value += seconds


@contextmanager
def _clock() -> Any:
    clock = _Clock()
    old_monotonic, old_sleep = probe.time.monotonic, probe.time.sleep
    probe.time.monotonic, probe.time.sleep = clock.monotonic, clock.sleep
    try:
        yield clock
    finally:
        probe.time.monotonic, probe.time.sleep = old_monotonic, old_sleep


class _Socket:
    def __init__(self, response: bytes | TimeoutError, expected: bytes) -> None:
        self.response, self.expected, self.offset = response, expected, 0
        self.closed = False
        self.sent: bytearray | None = None

    def settimeout(self, value: float) -> None:
        if value <= 0 or value > probe._SOCKET_OPERATION_TIMEOUT_SECONDS:
            fail(EXIT_MISMATCH, "entry_wire_socket_timeout")

    def sendall(self, value: bytearray) -> None:
        if bytes(value) != self.expected:
            fail(EXIT_MISMATCH, "entry_wire_request_order_or_bytes")
        self.sent = value

    def recv(self, maximum: int) -> bytes:
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "entry_wire_receive_bound")
        if isinstance(self.response, TimeoutError):
            raise self.response
        if self.offset >= len(self.response):
            return b""
        end = min(self.offset + 29, len(self.response))
        value = self.response[self.offset:end]
        self.offset = end
        return value

    def close(self) -> None:
        self.closed = True


class _Connector:
    def __init__(self, transcript: list[tuple[bytes | TimeoutError, bytes]]) -> None:
        self.transcript, self.index, self.sockets = transcript, 0, []

    def __call__(self) -> _Socket:
        if self.index == len(self.transcript):
            fail(EXIT_MISMATCH, "entry_wire_unexpected_connection")
        response, expected = self.transcript[self.index]
        self.index += 1
        socket = _Socket(response, expected)
        self.sockets.append(socket)
        return socket

    def require_complete(self, post_count: int) -> None:
        if self.index != len(self.transcript) or any(not item.closed for item in self.sockets):
            fail(EXIT_MISMATCH, "entry_wire_socket_closure")
        if any(item.sent is None or any(item.sent) for item in self.sockets):
            fail(EXIT_MISMATCH, "entry_wire_sent_buffer_cleanup")
        if sum(item.expected.startswith(b"POST ") for item in self.sockets) != post_count:
            fail(EXIT_MISMATCH, "entry_wire_post_count")


class _Credentials:
    def __init__(self) -> None:
        self.values: list[bytearray] = []

    def __call__(self) -> bytearray:
        value = bytearray(_CREDENTIAL)
        self.values.append(value)
        return value

    def require_zeroed(self) -> None:
        if not self.values or any(any(value) for value in self.values):
            fail(EXIT_MISMATCH, "entry_wire_credential_cleanup")


def _add(items: list[tuple[bytes | TimeoutError, bytes]], body: bytes, request: bytes) -> None:
    items.append((_http(body), request))


def _base(items: list[tuple[bytes | TimeoutError, bytes]]) -> None:
    _add(items, turn_fixture._HEALTH, _GET_HEALTH)
    _add(items, probe._MANIFEST_COMPATIBLE, _GET_MANIFEST)


def _map_ready(decision_id: str, kind: str) -> bytes:
    return map_fixture._ready(decision_id, [map_fixture._candidate(0, 2, 3, kind)])


def _map_complete(kind: str) -> bytes:
    return map_fixture._complete(map_fixture._candidate(0, 2, 3, kind))


def _map(items: list[tuple[bytes | TimeoutError, bytes]], decision_id: str, kind: str) -> None:
    _base(items)
    _add(items, _map_ready(decision_id, kind), _GET_MAP)
    _add(items, map_fixture._action_body(decision_id, "select:0", "accepted"), _post(_MAP_POST, decision_id, "select:0"))
    _add(items, map_client._MAP_WAITING, _GET_MAP)
    _add(items, _map_complete(kind), _GET_MAP)


def _reward_ready(decision_id: str, revision: int, gold: int, claimable: bool) -> bytes:
    parent = reward_fixture._parent(decision_id, revision, gold)
    if claimable:
        parent["rewards"] = parent["rewards"][:1]
        parent["legal_actions"] = [parent["legal_actions"][0], parent["legal_actions"][-1]]
    else:
        parent["rewards"] = []
        parent["legal_actions"] = [parent["legal_actions"][-1]]
    return reward_fixture._body(parent)


def _reward_complete(gold: int) -> bytes:
    return reward_fixture._body({"schema_version": 1, "status": "complete", "decision_kind": "reward", "actionable": False, "decision_id": None, "screen_kind": "map", "player": reward_fixture._player(gold), "rewards": [], "legal_actions": []})


def _reward(items: list[tuple[bytes | TimeoutError, bytes]]) -> None:
    first, second = "1" * 64, "2" * 64
    _base(items)
    _add(items, _reward_ready(first, 0, 71, True), _GET_REWARD)
    _add(items, _receipt(first, "claim:0"), _post(_REWARD_POST, first, "claim:0"))
    _add(items, _reward_ready(second, 1, 85, False), _GET_REWARD)
    _add(items, _receipt(second, "proceed"), _post(_REWARD_POST, second, "proceed"))
    _add(items, _reward_complete(85), _GET_REWARD)


def _combat_defeat(items: list[tuple[bytes | TimeoutError, bytes]], decision_id: str) -> None:
    state = turn_fixture._combat(decision_id, 1, hp=5, block=0, energy=0, enemy_hp=43, hand=[], actions=[turn_fixture._end_turn()])
    _base(items)
    _add(items, state, _GET_COMBAT)
    _add(items, turn_fixture._action_body(decision_id, "end_turn"), _post(_COMBAT_POST, decision_id, "end_turn"))
    _add(items, probe._COMBAT_WAITING, _GET_COMBAT)
    _add(items, combat_fixture._terminal("defeat", 1, hp=0, enemies=[combat_fixture._enemy(43)]), _GET_COMBAT)


def _room_ready(decision_id: str, ordinal: int) -> bytes:
    candidate = room_fixture._candidate(0, "rest_heal", "HEAL", enabled=True, supported=True)
    return room_fixture._ready(decision_id, "rest_site", "choose_option", [candidate], [room_fixture._legal(candidate)], ordinal=ordinal)


def _room(items: list[tuple[bytes | TimeoutError, bytes]], ordinal: int) -> None:
    first, second = "3" * 64, "4" * 64
    heal = room_fixture._candidate(0, "rest_heal", "HEAL", enabled=False, supported=True)
    proceed = room_fixture._candidate(1, "proceed", "proceed", enabled=True, supported=True, is_proceed=True)
    _base(items)
    _add(items, _room_ready(first, ordinal), _GET_ROOM)
    _add(items, room_fixture._action_body(first, "choose:0"), _post(_ROOM_POST, first, "choose:0"))
    _add(items, room_fixture._ready(second, "rest_site", "proceed", [heal, proceed], [room_fixture._legal(proceed)], ordinal=ordinal), _GET_ROOM)
    _add(items, room_fixture._action_body(second, "proceed"), _post(_ROOM_POST, second, "proceed"))
    _add(items, room_fixture._inactive("complete", "rest_site", "complete", ordinal), _GET_ROOM)


def _expect(operation: Callable[[], object], code: str) -> None:
    try:
        operation()
    except ToolFailure as error:
        if error.exit_code == EXIT_MISMATCH and error.error_code == code:
            return
        fail(EXIT_MISMATCH, "entry_wire_wrong_failure")
    fail(EXIT_MISMATCH, "entry_wire_unexpected_success")


def _run(transcript: list[tuple[bytes | TimeoutError, bytes]], entry_phase: str | None, limit: int) -> tuple[dict[str, object], _Connector, _Credentials]:
    connector, credentials = _Connector(transcript), _Credentials()
    with _clock():
        arguments = (credentials, connector, "first-legal", "first-card", "first", "safe", limit)
        result = (
            run._run_bounded_run(*arguments)
            if entry_phase is None
            else run._run_bounded_run(*arguments, entry_phase=entry_phase)
        )
    credentials.require_zeroed()
    return result, connector, credentials


def _combat_equivalence_and_defeat() -> None:
    def execute(phase: str | None) -> tuple[dict[str, object], _Connector]:
        transcript: list[tuple[bytes | TimeoutError, bytes]] = []
        _combat_defeat(transcript, "a" * 64)
        result, connector, _ = _run(transcript, phase, 1)
        connector.require_complete(1)
        return result, connector

    omitted, _ = execute(None)
    explicit, _ = execute("combat")
    if omitted != explicit or omitted.get("termination") != {"reason": "run_defeat", "after_floor": 0, "destination_kind": None}:
        fail(EXIT_MISMATCH, "entry_wire_combat_equivalence")


def _reward_and_map_prefixes() -> None:
    reward_transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    _reward(reward_transcript)
    _add(reward_transcript, map_client._MAP_WAITING, _GET_MAP)
    _add(reward_transcript, _map_ready("5" * 64, "shop"), _GET_MAP)
    _map(reward_transcript, "6" * 64, "shop")
    reward_result, reward_connector, _ = _run(reward_transcript, "reward", 1)
    if reward_result.get("entry_prefix", {}).get("readiness") != {"next_combat_attempts": 0, "reward_attempts": 0, "map_attempts": 2} or reward_result.get("action_totals") != {"combat": 0, "reward": 2, "map": 1, "room": 0, "total": 3}:
        fail(EXIT_MISMATCH, "entry_wire_reward_prefix_accounting")
    reward_connector.require_complete(3)

    map_transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    _map(map_transcript, "7" * 64, "shop")
    map_result, map_connector, _ = _run(map_transcript, "map", 1)
    if map_result.get("entry_prefix", {}).get("observed_phases") != ["map"] or map_result.get("processed_floor_count") != 1 or map_result.get("action_totals") != {"combat": 0, "reward": 0, "map": 1, "room": 0, "total": 1}:
        fail(EXIT_MISMATCH, "entry_wire_map_prefix_accounting")
    map_connector.require_complete(1)


def _later_combat_and_room_binding() -> None:
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    _map(transcript, "8" * 64, "monster")
    _add(transcript, probe._COMBAT_WAITING, _GET_COMBAT)
    _add(transcript, probe._COMBAT_WAITING, _GET_COMBAT)
    ready = turn_fixture._combat("9" * 64, 1, hp=5, block=0, energy=0, enemy_hp=43, hand=[], actions=[turn_fixture._end_turn()])
    _add(transcript, ready, _GET_COMBAT)
    _combat_defeat(transcript, "a" * 64)
    result, connector, _ = _run(transcript, "map", 2)
    if result.get("termination", {}).get("reason") != "run_defeat" or connector.index != len(transcript):
        fail(EXIT_MISMATCH, "entry_wire_delayed_combat")
    connector.require_complete(2)

    room_transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    _map(room_transcript, "b" * 64, "rest_site")
    _add(room_transcript, _room_ready("c" * 64, 4), _GET_ROOM)
    _room(room_transcript, 4)
    _add(room_transcript, _map_complete("rest_site"), _GET_MAP)
    _add(room_transcript, map_client._MAP_WAITING, _GET_MAP)
    _add(room_transcript, _map_ready("d" * 64, "monster"), _GET_MAP)
    room_result, room_connector, _ = _run(room_transcript, "map", 1)
    handoff = room_result.get("room_handoff")
    if not isinstance(handoff, dict) or handoff.get("preflight") != {"attempts": 1, "screen_kind": "rest_site", "room_ordinal": 4}:
        fail(EXIT_MISMATCH, "entry_wire_room_context")
    room_connector.require_complete(3)


def _room_preflight_context_mismatch() -> None:
    transcript: list[tuple[bytes | TimeoutError, bytes]] = []
    _map(transcript, "f" * 64, "rest_site")
    _add(transcript, _room_ready("a" * 64, 4), _GET_ROOM)
    _base(transcript)
    _add(transcript, _room_ready("b" * 64, 5), _GET_ROOM)
    connector, credentials = _Connector(transcript), _Credentials()
    with _clock():
        _expect(
            lambda: run._run_bounded_run(
                credentials,
                connector,
                "first-legal",
                "first-card",
                "first",
                "safe",
                1,
                entry_phase="map",
            ),
            "room_expected_context_mismatch",
        )
    credentials.require_zeroed()
    connector.require_complete(1)


def _unsupported_and_post_failures() -> None:
    for kind, expected in (("boss", "act_boundary_reached"),):
        transcript: list[tuple[bytes | TimeoutError, bytes]] = []
        _map(transcript, "d" * 64, kind)
        result, connector, _ = _run(transcript, "map", 2)
        if result.get("termination", {}).get("reason") != expected:
            fail(EXIT_MISMATCH, "entry_wire_unsupported_destination")
        connector.require_complete(1)

    decision = "e" * 64
    for response, expected in ((map_fixture._action_body(decision, "select:0", "stale_decision"), "map_action_stale_decision"), (TimeoutError(_CANARY.decode("ascii")), "map_action_transport_failure")):
        transcript = []
        _base(transcript)
        _add(transcript, _map_ready(decision, "monster"), _GET_MAP)
        transcript.append((response if isinstance(response, TimeoutError) else _http(response), _post(_MAP_POST, decision, "select:0")))
        connector, credentials = _Connector(transcript), _Credentials()
        with _clock():
            _expect(lambda: run._run_bounded_run(credentials, connector, "first-legal", "first-card", "first", "safe", 2, entry_phase="map"), expected)
        credentials.require_zeroed()
        connector.require_complete(1)


def _entry_body_failures() -> None:
    cases = (("reward", reward_client._REWARD_WAITING, "reward_not_ready"), ("reward", reward_client._REWARD_UNSUPPORTED, "reward_not_ready"), ("reward", b"{}", "reward_response_mismatch"), ("reward", _reward_complete(71), "reward_response_mismatch"), ("map", map_client._MAP_WAITING, "map_not_ready"), ("map", map_client._MAP_UNSUPPORTED, "map_not_ready"), ("map", b"{}", "map_response_mismatch"), ("map", _map_complete("shop"), "map_response_mismatch"))
    for phase, body, expected in cases:
        transcript: list[tuple[bytes | TimeoutError, bytes]] = []
        _base(transcript)
        request = _GET_REWARD if phase == "reward" else _GET_MAP
        _add(transcript, body + (_CANARY if body == b"{}" else b""), request)
        connector, credentials = _Connector(transcript), _Credentials()
        with _clock():
            _expect(lambda: run._run_bounded_run(credentials, connector, "first-legal", "first-card", "first", "safe", 1, entry_phase=phase), expected)
        credentials.require_zeroed()
        connector.require_complete(0)


def _negative_control() -> None:
    source = subprocess.run(["git", "show", f"{_BASE_COMMIT}:bridge/Sts2AgentBridge/tools/apply_run_live.py"], cwd=_TOOLS.parent.parent.parent, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10).stdout
    if not source or b"--entry-phase" in source:
        fail(EXIT_MISMATCH, "entry_wire_negative_control_source")
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("phase_entry_base", loader=None))
    exec(compile(source, f"{_BASE_COMMIT}:apply_run_live.py", "exec"), module.__dict__)
    try:
        module._run_bounded_run(lambda: bytearray(_CREDENTIAL), lambda: None, "first-legal", "first-card", "first", "safe", 1, entry_phase="map")
    except TypeError as error:
        if "entry_phase" not in str(error):
            fail(EXIT_MISMATCH, "entry_wire_negative_control_wrong_failure")
        return
    fail(EXIT_MISMATCH, "entry_wire_negative_control_accepted")


def _redacted(operation: Callable[[], dict[str, object]]) -> dict[str, object]:
    result: dict[str, object] | None = None

    def invoke() -> dict[str, object]:
        nonlocal result
        result = operation()
        return result

    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(invoke)
    if exit_code != 0 or stderr.getvalue() or _CANARY in (stdout.getvalue() + stderr.getvalue()).encode("ascii", "strict") or _CREDENTIAL in (stdout.getvalue() + stderr.getvalue()).encode("ascii", "strict"):
        fail(EXIT_MISMATCH, "entry_wire_output_privacy")
    if result is None:
        fail(EXIT_MISMATCH, "entry_wire_missing_result")
    return result


def operation() -> dict[str, object]:
    _combat_equivalence_and_defeat()
    _reward_and_map_prefixes()
    _later_combat_and_room_binding()
    _room_preflight_context_mismatch()
    _unsupported_and_post_failures()
    _entry_body_failures()
    _negative_control()
    return {"schema_version": 1, "status": "passed", "suite": "apply_run_entry_wire_fixtures", "check_count": 8}


if __name__ == "__main__":
    main(lambda: _redacted(operation))
