#!/usr/bin/env python3
"""Actual-client synthetic gate for the bounded room timeout contract."""
from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import Union
from unittest.mock import patch

sys.dont_write_bytecode = True

import apply_room_live as room
import apply_run_acceptance_live as acceptance
import apply_run_live as run
import probe_live as probe
from tool_common import EXIT_MISMATCH, ToolFailure, fail, main, run_cli


_CREDENTIAL = b"0123456789abcdef" * 4
_D0 = "0" * 64
_D1 = "1" * 64
_MAP_ID = "a" * 64
_ROOM_ORDINAL = 4
_ROOM_ACTION_ROUTE = "/probe/v0/public/room-action"

_HEALTH = (
    b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"'
    b"00000000000000000000000000000000"
    b'"}'
)
_MANIFEST = (
    b'{"schema_version":1,"protocol":"live_probe_v0","bridge_id":"sts2_agent_bridge",'
    b'"bridge_version":"0.8.0","mode":"live_probe_v0","build_compatibility":"compatible",'
    b'"target_build_manifest_id":"sts2-steam-main-build-23811903-macos-universal",'
    b'"target_game_version":"v0.107.1","target_steam_build_id":"23811903","capabilities":'
    b'{"observe_public_screen":true,"observe_decision":true,"apply":true,'
    b'"profile_access":false,"privileged_state":false,"snapshot_restore":false,'
    b'"bridge_filesystem_writes":false,"host_logging":"sanitized_existing_sink",'
    b'"harmony_patches":false,"outbound_network":false,"hot_unload":false}}'
)


def _get(route: str) -> bytes:
    return (
        b"GET "
        + route.encode("ascii")
        + b" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
        + _CREDENTIAL
        + b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
    )


def _post(route: str, decision_id: str, action_id: str) -> bytes:
    return (
        b"POST "
        + route.encode("ascii")
        + b" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "
        + _CREDENTIAL
        + b"\r\nX-Sts2-Decision-Id: "
        + decision_id.encode("ascii")
        + b"\r\nX-Sts2-Action-Id: "
        + action_id.encode("ascii")
        + b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
    )


_GET_HEALTH = _get("/probe/v0/health")
_GET_MANIFEST = _get("/probe/v0/manifest")
_GET_ROOM = _get("/probe/v0/public/room-decision")
_GET_MAP = _get("/probe/v0/public/map-decision")


def _body(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("ascii")


def _http(body: bytes) -> bytes:
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json; charset=utf-8\r\n"
        b"Content-Length: "
        + str(len(body)).encode("ascii")
        + b"\r\nCache-Control: no-store\r\n"
        b"X-Content-Type-Options: nosniff\r\n"
        b"Connection: close\r\n\r\n"
        + body
    )


def _inactive(status: str, screen_kind: str = "unknown", ordinal: int | None = None) -> bytes:
    return _body({
        "schema_version": 1,
        "status": status,
        "decision_kind": "room",
        "actionable": False,
        "decision_id": None,
        "screen_kind": screen_kind,
        "phase": status if status != "waiting" else "unknown",
        "room_ordinal": ordinal,
        "candidates": [],
        "legal_actions": [],
    })


def _candidate(
    index: int,
    kind: str,
    stable_id: str,
    *,
    enabled: bool = True,
    supported: bool = True,
    dangerous: bool = False,
) -> dict[str, object]:
    return {
        "candidate_index": index,
        "action_id": "proceed" if kind == "proceed" else f"choose:{index}",
        "kind": kind,
        "stable_id": stable_id,
        "enabled": enabled,
        "supported": supported,
        "is_proceed": kind == "proceed",
        "is_dangerous": dangerous,
    }


def _ready(
    decision_id: str,
    screen_kind: str,
    candidates: list[dict[str, object]],
    legal_indexes: list[int],
    *,
    ordinal: int = _ROOM_ORDINAL,
) -> bytes:
    legal = []
    for index in legal_indexes:
        action_id = str(candidates[index]["action_id"])
        legal.append({
            "action_id": action_id,
            "kind": "proceed_room" if action_id == "proceed" else "choose_room_option",
            "candidate_index": index,
        })
    has_proceed = any(item["action_id"] == "proceed" for item in legal)
    phase = "proceed" if has_proceed and len(legal) == 1 else (
        "choose_or_proceed" if has_proceed else "choose_option"
    )
    return _body({
        "schema_version": 1,
        "status": "ready",
        "decision_kind": "room",
        "actionable": True,
        "decision_id": decision_id,
        "screen_kind": screen_kind,
        "phase": phase,
        "room_ordinal": ordinal,
        "candidates": candidates,
        "legal_actions": legal,
    })


def _receipt(decision_id: str, action_id: str) -> bytes:
    return _body({
        "schema_version": 1,
        "status": "accepted",
        "mutation_state": "applied",
        "decision_id": decision_id,
        "action_id": action_id,
        "reason": "accepted",
    })


_WAITING = _inactive("waiting")
_COMPLETE_REST = _inactive("complete", "rest_site", _ROOM_ORDINAL)
_HEAL = _candidate(0, "rest_heal", "HEAL")
_PROCEED = _candidate(0, "proceed", "proceed")


class _Clock:
    def __init__(self, *, sleep_advances: list[float] | None = None) -> None:
        self.value = 100.0
        self._sleep_advances = iter(sleep_advances or ())
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        if seconds != 0.1:
            fail(EXIT_MISMATCH, "room_timeout_fixture_sleep")
        self.sleeps.append(seconds)
        self.value += next(self._sleep_advances, 10.0)

    def advance(self, seconds: float) -> None:
        self.value += seconds


@contextmanager
def _clock(clock: _Clock) -> Iterator[None]:
    old_monotonic, old_sleep = probe.time.monotonic, probe.time.sleep
    probe.time.monotonic, probe.time.sleep = clock.monotonic, clock.sleep
    try:
        yield
    finally:
        probe.time.monotonic, probe.time.sleep = old_monotonic, old_sleep


_TranscriptItem = tuple[Union[bytes, BaseException], bytes, float, float]


class _Socket:
    def __init__(self, item: _TranscriptItem, clock: _Clock) -> None:
        self.response, self.expected, self.recv_advance, self.close_advance = item
        self.clock = clock
        self.offset = 0
        self.closed = False
        self.sent: bytearray | None = None
        self._advanced = False

    def settimeout(self, value: float) -> None:
        if not 0 < value <= probe._SOCKET_OPERATION_TIMEOUT_SECONDS:
            fail(EXIT_MISMATCH, "room_timeout_fixture_socket_timeout")

    def sendall(self, request: bytearray) -> None:
        if bytes(request) != self.expected:
            fail(EXIT_MISMATCH, "room_timeout_fixture_request")
        self.sent = request

    def recv(self, maximum: int) -> bytes:
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "room_timeout_fixture_receive_bound")
        if isinstance(self.response, BaseException):
            raise self.response
        if self.offset >= len(self.response):
            return b""
        if not self._advanced:
            self.clock.advance(self.recv_advance)
            self._advanced = True
        end = min(self.offset + 41, len(self.response))
        chunk = self.response[self.offset:end]
        self.offset = end
        return chunk

    def close(self) -> None:
        if not self.closed:
            self.clock.advance(self.close_advance)
            self.closed = True


class _Connector:
    def __init__(self, transcript: list[_TranscriptItem], clock: _Clock) -> None:
        self.transcript = transcript
        self.clock = clock
        self.index = 0
        self.sockets: list[_Socket] = []

    def __call__(self) -> _Socket:
        if self.index >= len(self.transcript):
            fail(EXIT_MISMATCH, "room_timeout_fixture_unexpected_connection")
        socket = _Socket(self.transcript[self.index], self.clock)
        self.index += 1
        self.sockets.append(socket)
        return socket

    def assert_clean(self, post_count: int) -> None:
        if self.index != len(self.transcript) or any(not socket.closed for socket in self.sockets):
            fail(EXIT_MISMATCH, "room_timeout_fixture_socket_cleanup")
        if any(socket.sent is None or any(socket.sent) for socket in self.sockets):
            fail(EXIT_MISMATCH, "room_timeout_fixture_request_cleanup")
        actual_posts = sum(socket.expected.startswith(b"POST ") for socket in self.sockets)
        if actual_posts != post_count:
            fail(EXIT_MISMATCH, "room_timeout_fixture_post_count")


class _Credentials:
    def __init__(self) -> None:
        self.values: list[bytearray] = []

    def __call__(self) -> bytearray:
        value = bytearray(_CREDENTIAL)
        self.values.append(value)
        return value

    def assert_zeroed(self) -> None:
        if not self.values or any(any(value) for value in self.values):
            fail(EXIT_MISMATCH, "room_timeout_fixture_credential_cleanup")


def _item(
    body: Union[bytes, BaseException],
    request: bytes,
    *,
    recv_advance: float = 0.0,
    close_advance: float = 0.0,
) -> _TranscriptItem:
    response = body if isinstance(body, BaseException) else _http(body)
    return response, request, recv_advance, close_advance


def _base(*, close_advances: tuple[float, float] = (0.0, 0.0)) -> list[_TranscriptItem]:
    return [
        _item(_HEALTH, _GET_HEALTH, close_advance=close_advances[0]),
        _item(_MANIFEST, _GET_MANIFEST, close_advance=close_advances[1]),
    ]


def _expect_room_failure(
    transcript: list[_TranscriptItem],
    code: str,
    *,
    clock: _Clock | None = None,
    post_count: int = 0,
) -> None:
    active_clock = clock or _Clock()
    connector = _Connector(transcript, active_clock)
    credential = bytearray(_CREDENTIAL)
    with _clock(active_clock):
        try:
            room._run_apply_room(credential, "safe", connector)
        except ToolFailure as failure:
            if failure.exit_code != EXIT_MISMATCH or failure.error_code != code:
                fail(EXIT_MISMATCH, "room_timeout_fixture_wrong_failure")
        else:
            fail(EXIT_MISMATCH, "room_timeout_fixture_unexpected_pass")
    if any(credential):
        fail(EXIT_MISMATCH, "room_timeout_fixture_credential_cleanup")
    connector.assert_clean(post_count)


def _waiting_timeout(body_prefix: list[_TranscriptItem], post_count: int) -> None:
    transcript = body_prefix + [_item(_WAITING, _GET_ROOM) for _ in range(3)]
    _expect_room_failure(
        transcript,
        "room_interaction_timeout",
        post_count=post_count,
    )


def _canonical_waiting_timeouts() -> int:
    _waiting_timeout(_base(), 0)

    heal = _ready(_D0, "rest_site", [_HEAL], [0])
    _waiting_timeout(
        _base()
        + [
            _item(heal, _GET_ROOM),
            _item(_receipt(_D0, "choose:0"), _post(_ROOM_ACTION_ROUTE, _D0, "choose:0")),
        ],
        1,
    )

    proceed = _ready(_D0, "rest_site", [_PROCEED], [0])
    _waiting_timeout(
        _base()
        + [
            _item(proceed, _GET_ROOM),
            _item(_receipt(_D0, "proceed"), _post(_ROOM_ACTION_ROUTE, _D0, "proceed")),
        ],
        1,
    )

    blocked = _candidate(
        0,
        "event_option",
        "EVENT.DANGEROUS",
        enabled=False,
        supported=False,
        dangerous=True,
    )
    safe = _candidate(1, "event_option", "EVENT.SAFE")
    first = _ready(_D0, "event", [blocked, safe], [1])
    second_choice = _candidate(0, "event_option", "EVENT.CONTINUE")
    second = _ready(_D1, "event", [second_choice], [0])
    _expect_room_failure(
        _base()
        + [
            _item(first, _GET_ROOM),
            _item(_receipt(_D0, "choose:1"), _post(_ROOM_ACTION_ROUTE, _D0, "choose:1")),
            _item(_WAITING, _GET_ROOM),
            _item(second, _GET_ROOM),
            _item(_receipt(_D1, "choose:0"), _post(_ROOM_ACTION_ROUTE, _D1, "choose:0")),
            _item(_WAITING, _GET_ROOM),
            _item(_WAITING, _GET_ROOM),
        ],
        "room_interaction_timeout",
        post_count=2,
    )
    return 4


def _completion_before_deadline() -> None:
    clock = _Clock(sleep_advances=[29.999])
    transcript = _base() + [
        _item(_ready(_D0, "rest_site", [_HEAL], [0]), _GET_ROOM),
        _item(_receipt(_D0, "choose:0"), _post(_ROOM_ACTION_ROUTE, _D0, "choose:0")),
        _item(_ready(_D1, "rest_site", [_PROCEED], [0]), _GET_ROOM),
        _item(_receipt(_D1, "proceed"), _post(_ROOM_ACTION_ROUTE, _D1, "proceed")),
        _item(_WAITING, _GET_ROOM),
        _item(_COMPLETE_REST, _GET_ROOM),
    ]
    connector = _Connector(transcript, clock)
    credential = bytearray(_CREDENTIAL)
    with _clock(clock):
        result = room._run_apply_room(credential, "safe", connector)
    if (
        result.get("status") != "passed"
        or result.get("accepted_action_count") != 2
        or result.get("routes_checked") != 8
        or clock.value >= 130.0
    ):
        fail(EXIT_MISMATCH, "room_timeout_fixture_delayed_completion")
    if any(credential):
        fail(EXIT_MISMATCH, "room_timeout_fixture_credential_cleanup")
    connector.assert_clean(2)


def _decision_replay_after_waiting() -> None:
    ready = _ready(_D0, "rest_site", [_HEAL], [0])
    _expect_room_failure(
        _base()
        + [
            _item(ready, _GET_ROOM),
            _item(_receipt(_D0, "choose:0"), _post(_ROOM_ACTION_ROUTE, _D0, "choose:0")),
            _item(_WAITING, _GET_ROOM),
            _item(ready, _GET_ROOM),
        ],
        "room_decision_replayed",
        post_count=1,
    )


def _ordinal_mismatches_after_action() -> int:
    first = _ready(_D0, "rest_site", [_HEAL], [0])
    prefix = _base() + [
        _item(first, _GET_ROOM),
        _item(_receipt(_D0, "choose:0"), _post(_ROOM_ACTION_ROUTE, _D0, "choose:0")),
    ]
    _expect_room_failure(
        prefix
        + [
            _item(_WAITING, _GET_ROOM),
            _item(_ready(_D1, "rest_site", [_PROCEED], [0], ordinal=5), _GET_ROOM),
        ],
        "room_transition_mismatch",
        post_count=1,
    )
    _expect_room_failure(
        prefix + [_item(_inactive("complete", "rest_site", 5), _GET_ROOM)],
        "room_completion_mismatch",
        post_count=1,
    )
    return 2


def _run_preflight_timeout() -> None:
    clock = _Clock()
    transcript = [_item(_WAITING, _GET_ROOM) for _ in range(3)]
    connector = _Connector(transcript, clock)
    credentials = _Credentials()
    with _clock(clock):
        try:
            run._with_credential(
                credentials,
                run._wait_for_room_ready,
                "rest_site",
                connector,
            )
        except ToolFailure as failure:
            if (
                failure.exit_code != EXIT_MISMATCH
                or failure.error_code != "run_room_ready_timeout"
            ):
                fail(EXIT_MISMATCH, "room_timeout_fixture_preflight_failure")
        else:
            fail(EXIT_MISMATCH, "room_timeout_fixture_preflight_pass")
    credentials.assert_zeroed()
    connector.assert_clean(0)


def _transport_failures() -> int:
    timeout_clock = _Clock()
    _expect_room_failure(
        _base()
        + [_item(_WAITING, _GET_ROOM, recv_advance=4.0)],
        "room_transport_timeout",
        clock=timeout_clock,
    )
    _expect_room_failure(
        _base() + [_item(TimeoutError("synthetic"), _GET_ROOM)],
        "room_transport_failure",
    )
    return 2


def _health_manifest_share_deadline() -> None:
    _expect_room_failure(
        _base(close_advances=(15.0, 15.0)),
        "room_interaction_timeout",
    )


def _map_ready() -> bytes:
    candidate = {"candidate_index": 0, "col": 2, "row": 3, "kind": "rest_site"}
    return _body({
        "schema_version": 1,
        "status": "ready",
        "decision_kind": "map",
        "actionable": True,
        "decision_id": _MAP_ID,
        "screen_kind": "map",
        "destination": None,
        "candidates": [candidate],
        "legal_actions": [
            {"action_id": "select:0", "kind": "select_map_node", "candidate_index": 0}
        ],
    })


def _map_complete() -> bytes:
    return _body({
        "schema_version": 1,
        "status": "complete",
        "decision_kind": "map",
        "actionable": False,
        "decision_id": None,
        "screen_kind": "room",
        "destination": {"candidate_index": 0, "col": 2, "row": 3, "kind": "rest_site"},
        "candidates": [],
        "legal_actions": [],
    })


def _acceptance_wrapper_real_timeout() -> None:
    map_waiting = _body({
        "schema_version": 1,
        "status": "waiting",
        "decision_kind": "map",
        "actionable": False,
        "decision_id": None,
        "screen_kind": "unknown",
        "destination": None,
        "candidates": [],
        "legal_actions": [],
    })
    room_ready = _ready(_D0, "rest_site", [_HEAL], [0])
    transcript = _base() + [
        _item(_map_ready(), _GET_MAP),
        _item(_receipt(_MAP_ID, "select:0"), _post("/probe/v0/public/map-action", _MAP_ID, "select:0")),
        _item(map_waiting, _GET_MAP),
        _item(_map_complete(), _GET_MAP),
        _item(room_ready, _GET_ROOM),
    ] + _base() + [
        _item(room_ready, _GET_ROOM),
        _item(_receipt(_D0, "choose:0"), _post(_ROOM_ACTION_ROUTE, _D0, "choose:0")),
        _item(_WAITING, _GET_ROOM),
        _item(_WAITING, _GET_ROOM),
        _item(_WAITING, _GET_ROOM),
    ]
    clock = _Clock()
    connector = _Connector(transcript, clock)
    credentials = _Credentials()
    invocations = 0

    def actual_run() -> dict[str, object]:
        nonlocal invocations
        invocations += 1
        with _clock(clock):
            return run._run_bounded_run(
                credentials,
                connector,
                "first-legal",
                "first-card",
                "elite",
                "safe",
                3,
                entry_phase="map",
            )

    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        patch.object(acceptance.run, "operation", side_effect=actual_run),
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        exit_code = run_cli(acceptance.operation)
    expected = '{"schema_version":1,"status":"failed","code":"room_interaction_timeout"}\n'
    if (
        invocations != 1
        or exit_code != EXIT_MISMATCH
        or stdout.getvalue() != expected
        or stderr.getvalue() != ""
        or "milestone" in stdout.getvalue()
        or "accepted" in stdout.getvalue()
    ):
        fail(EXIT_MISMATCH, "room_timeout_fixture_acceptance_output")
    credentials.assert_zeroed()
    connector.assert_clean(2)


def operation() -> dict[str, object]:
    check_count = _canonical_waiting_timeouts()
    _completion_before_deadline()
    check_count += 1
    _decision_replay_after_waiting()
    check_count += 1
    check_count += _ordinal_mismatches_after_action()
    _run_preflight_timeout()
    check_count += 1
    check_count += _transport_failures()
    _health_manifest_share_deadline()
    check_count += 1
    _acceptance_wrapper_real_timeout()
    check_count += 1
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_room_timeout_fixtures",
        "check_count": check_count,
    }


if __name__ == "__main__":
    main(operation)
