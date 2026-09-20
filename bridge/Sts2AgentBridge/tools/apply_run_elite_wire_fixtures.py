#!/usr/bin/env python3
"""Actual-client fake-transport gate for bounded elite continuation.

This suite deliberately drives the production bounded-run and granular clients
through literal request transcripts.  It does not reproduce run orchestration:
the only oracle state is the exact request sequence and bounded result shape.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

import apply_map_live as map_client
import apply_map_live_fixtures as map_fixture
import apply_reward_live as reward_client
import apply_room_live_fixtures as room_fixture
import apply_run_entry_wire_fixtures as entry_fixture
import apply_run_live as run
import apply_run_wire_fixtures as run_wire_fixture
import apply_turn_live_fixtures as turn_fixture
import probe_live as probe
from tool_common import EXIT_MISMATCH, ToolFailure, fail, main, run_cli


_CANARY = b"ELITE_WIRE_CANARY_DO_NOT_PRINT"
_CREDENTIAL = entry_fixture._CREDENTIAL
_TOOLS = Path(__file__).resolve().parent
_BASE_COMMIT = "42a3c4e"


def _http(body: bytes) -> bytes:
    return room_fixture._response(body)


class _Socket:
    def __init__(self, response: bytes | BaseException, expected: bytes) -> None:
        self.response = response
        self.expected = expected
        self.offset = 0
        self.closed = False
        self.write_shutdown = False
        self.sent: bytearray | None = None

    def settimeout(self, value: float) -> None:
        if value <= 0 or value > probe._SOCKET_OPERATION_TIMEOUT_SECONDS:
            fail(EXIT_MISMATCH, "elite_wire_socket_timeout")

    def sendall(self, value: bytearray) -> None:
        if bytes(value) != self.expected:
            fail(EXIT_MISMATCH, "elite_wire_request_order_or_bytes")
        self.sent = value

    def shutdown(self, how: int) -> None:
        if how != probe.socket.SHUT_WR or not (self.sent is not None) or self.write_shutdown or self.closed:
            fail(EXIT_MISMATCH, "apply_run_elite_wire_fixture_half_close")
        self.write_shutdown = True

    def recv(self, maximum: int) -> bytes:
        if not self.write_shutdown:
            fail(EXIT_MISMATCH, "apply_run_elite_wire_fixture_receive_before_half_close")
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "elite_wire_receive_bound")
        if isinstance(self.response, BaseException):
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
    def __init__(self, transcript: list[tuple[bytes | BaseException, bytes]]) -> None:
        self.transcript = transcript
        self.index = 0
        self.sockets: list[_Socket] = []

    def __call__(self) -> _Socket:
        if self.index == len(self.transcript):
            fail(EXIT_MISMATCH, "elite_wire_unexpected_connection")
        response, expected = self.transcript[self.index]
        self.index += 1
        socket = _Socket(response, expected)
        self.sockets.append(socket)
        return socket

    def require_used_clean(self, post_count: int, *, complete: bool = True) -> None:
        if (complete and self.index != len(self.transcript)) or any(
            not item.closed for item in self.sockets
        ):
            fail(EXIT_MISMATCH, "elite_wire_socket_closure")
        if any(item.sent is None or any(item.sent) for item in self.sockets):
            fail(EXIT_MISMATCH, "elite_wire_sent_buffer_cleanup")
        if sum(item.expected.startswith(b"POST ") for item in self.sockets) != post_count:
            fail(EXIT_MISMATCH, "elite_wire_post_count")


class _Credentials:
    def __init__(self) -> None:
        self.values: list[bytearray] = []

    def __call__(self) -> bytearray:
        value = bytearray(_CREDENTIAL)
        self.values.append(value)
        return value

    def require_zeroed(self) -> None:
        if not self.values or any(any(value) for value in self.values):
            fail(EXIT_MISMATCH, "elite_wire_credential_cleanup")


def _add(
    transcript: list[tuple[bytes | BaseException, bytes]], body: bytes, request: bytes
) -> None:
    transcript.append((_http(body), request))


def _map(
    transcript: list[tuple[bytes | BaseException, bytes]], decision_id: str, kind: str
) -> None:
    entry_fixture._map(transcript, decision_id, kind)


def _reward(transcript: list[tuple[bytes | BaseException, bytes]]) -> None:
    entry_fixture._reward(transcript)


def _combat_defeat(
    transcript: list[tuple[bytes | BaseException, bytes]], decision_id: str
) -> None:
    entry_fixture._combat_defeat(transcript, decision_id)


def _combat_victory(
    transcript: list[tuple[bytes | BaseException, bytes]], token: str
) -> None:
    # The shared wire fixture supplies real granular combat bodies and exact
    # literal requests; this gate invokes the same production combat runner.
    run_wire_fixture._combat_victory(transcript, token)


def _reward_ready(
    decision_id: str, revision: int, gold: int, *, claimable: bool = True
) -> bytes:
    return run_wire_fixture._reward_ready(
        decision_id, revision, gold, claimable=claimable
    )


def _map_ready(decision_id: str, kind: str) -> bytes:
    return entry_fixture._map_ready(decision_id, kind)


def _next_combat_ready(decision_id: str) -> bytes:
    return turn_fixture._combat(
        decision_id,
        1,
        hp=5,
        block=0,
        energy=0,
        enemy_hp=43,
        hand=[],
        actions=[turn_fixture._end_turn()],
    )


def _run(
    transcript: list[tuple[bytes | BaseException, bytes]],
    *,
    entry_phase: str = "map",
    floor_limit: int = 3,
    runner: Callable[..., dict[str, object]] = run._run_bounded_run,
) -> tuple[dict[str, object], _Connector, _Credentials]:
    connector, credentials = _Connector(transcript), _Credentials()
    with entry_fixture._clock():
        result = runner(
            credentials,
            connector,
            "first-legal",
            "first-card",
            "elite",
            "safe",
            floor_limit,
            entry_phase=entry_phase,
        )
    credentials.require_zeroed()
    return result, connector, credentials


def _expect(operation: Callable[[], object], code: str) -> None:
    try:
        operation()
    except ToolFailure as error:
        if error.exit_code == EXIT_MISMATCH and error.error_code == code:
            return
        fail(EXIT_MISMATCH, "elite_wire_wrong_failure")
    fail(EXIT_MISMATCH, "elite_wire_unexpected_success")


def _add_reward_then_map(
    transcript: list[tuple[bytes | BaseException, bytes]],
    map_id: str,
    kind: str,
    *,
    reward_id: str,
    revision: int,
) -> None:
    _add(transcript, _reward_ready(reward_id, revision, 71), entry_fixture._GET_REWARD)
    _reward(transcript)
    _add(transcript, _map_ready(map_id, kind), entry_fixture._GET_MAP)
    _map(transcript, map_id, kind)


def _prefix_elite_defeat() -> None:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    _map(transcript, "1" * 64, "elite")
    _add(transcript, _next_combat_ready("3" * 64), entry_fixture._GET_COMBAT)
    _combat_defeat(transcript, "2" * 64)
    result, connector, _ = _run(transcript)
    if result.get("termination") != {
        "reason": "run_defeat",
        "after_floor": 1,
        "destination_kind": None,
    } or result.get("entry_prefix", {}).get("destination_kind") != "elite":
        fail(EXIT_MISMATCH, "elite_wire_prefix_defeat_result")
    connector.require_used_clean(2)


def _default_elite_victory_reward_continuation() -> None:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    _combat_victory(transcript, "a")
    _add_reward_then_map(
        transcript, "3" * 64, "elite", reward_id="4" * 64, revision=0
    )
    _add(transcript, _next_combat_ready("7" * 64), entry_fixture._GET_COMBAT)
    _combat_victory(transcript, "b")
    _add_reward_then_map(
        transcript, "5" * 64, "shop", reward_id="6" * 64, revision=0
    )
    result, connector, _ = _run(transcript, entry_phase="combat", floor_limit=2)
    if (
        result.get("termination")
        != {"reason": "floor_limit_reached", "after_floor": 2, "destination_kind": "shop"}
        or result.get("completed_floor_count") != 2
        or result.get("action_totals", {}).get("reward") != 4
    ):
        fail(EXIT_MISMATCH, "elite_wire_victory_reward_continuation")
    connector.require_used_clean(14)


def _reward_prefix_elite_defeat() -> None:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    _reward(transcript)
    _add(transcript, _map_ready("7" * 64, "elite"), entry_fixture._GET_MAP)
    _map(transcript, "7" * 64, "elite")
    _add(transcript, _next_combat_ready("9" * 64), entry_fixture._GET_COMBAT)
    _combat_defeat(transcript, "8" * 64)
    result, connector, _ = _run(transcript, entry_phase="reward")
    if (
        result.get("entry_prefix", {}).get("observed_phases") != ["reward", "map"]
        or result.get("termination", {}).get("reason") != "run_defeat"
    ):
        fail(EXIT_MISMATCH, "elite_wire_reward_prefix_result")
    connector.require_used_clean(4)


def _post_room_elite_defeat() -> None:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    _combat_victory(transcript, "c")
    _add_reward_then_map(
        transcript, "9" * 64, "rest_site", reward_id="a" * 64, revision=0
    )
    _add(transcript, entry_fixture._room_ready("b" * 64, 4), entry_fixture._GET_ROOM)
    entry_fixture._room(transcript, 4)
    _add(transcript, entry_fixture._map_complete("rest_site"), entry_fixture._GET_MAP)
    _add(transcript, map_client._MAP_WAITING, entry_fixture._GET_MAP)
    _add(transcript, _map_ready("c" * 64, "elite"), entry_fixture._GET_MAP)
    _map(transcript, "c" * 64, "elite")
    _add(transcript, _next_combat_ready("e" * 64), entry_fixture._GET_COMBAT)
    _combat_defeat(transcript, "d" * 64)
    result, connector, _ = _run(transcript, entry_phase="combat")
    handoff = result.get("room_handoff")
    if (
        result.get("termination", {}).get("reason") != "run_defeat"
        or not isinstance(handoff, dict)
        or handoff.get("post_room_map", {}).get("after", {}).get("destination", {}).get("kind") != "elite"
        or handoff.get("next_combat", {}).get("outcome") != "defeat"
    ):
        fail(EXIT_MISMATCH, "elite_wire_post_room_result")
    connector.require_used_clean(11)


def _elite_reward_failures() -> None:
    for body, code in (
        (reward_client._REWARD_UNSUPPORTED, "reward_state_unsupported"),
        (b"{}" + _CANARY, "reward_response_mismatch"),
    ):
        transcript: list[tuple[bytes | BaseException, bytes]] = []
        _map(transcript, "e" * 64, "elite")
        _add(transcript, _next_combat_ready("0" * 64), entry_fixture._GET_COMBAT)
        _combat_victory(transcript, "d")
        _add(transcript, body, entry_fixture._GET_REWARD)
        connector, credentials = _Connector(transcript), _Credentials()
        with entry_fixture._clock():
            _expect(
                lambda: run._run_bounded_run(
                    credentials,
                    connector,
                    "first-legal",
                    "first-card",
                    "elite",
                    "safe",
                    3,
                    entry_phase="map",
                ),
                code,
            )
        credentials.require_zeroed()
        connector.require_used_clean(5)


def _elite_receipt_failures() -> None:
    decision = "f" * 64
    for response, code in (
        (map_fixture._action_body(decision, "select:0", "stale_decision"), "map_action_stale_decision"),
        (map_fixture._action_body(decision, "select:0", "invalid_action"), "map_action_invalid_action"),
        (TimeoutError(_CANARY.decode("ascii")), "map_action_transport_failure"),
    ):
        transcript: list[tuple[bytes | BaseException, bytes]] = []
        entry_fixture._base(transcript)
        _add(transcript, _map_ready(decision, "elite"), entry_fixture._GET_MAP)
        expected = entry_fixture._post(entry_fixture._MAP_POST, decision, "select:0")
        transcript.append((response if isinstance(response, BaseException) else _http(response), expected))
        connector, credentials = _Connector(transcript), _Credentials()
        with entry_fixture._clock():
            _expect(
                lambda: run._run_bounded_run(
                    credentials,
                    connector,
                    "first-legal",
                    "first-card",
                    "elite",
                    "safe",
                    3,
                    entry_phase="map",
                ),
                code,
            )
        credentials.require_zeroed()
        connector.require_used_clean(1)


def _elite_cancellation_stops_mutation() -> None:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    _map(transcript, "0" * 64, "elite")
    transcript.append((KeyboardInterrupt(), entry_fixture._GET_COMBAT))
    connector, credentials = _Connector(transcript), _Credentials()
    with entry_fixture._clock():
        try:
            run._run_bounded_run(
                credentials,
                connector,
                "first-legal",
                "first-card",
                "elite",
                "safe",
                3,
                entry_phase="map",
            )
        except KeyboardInterrupt:
            pass
        else:
            fail(EXIT_MISMATCH, "elite_wire_cancellation_accepted")
    credentials.require_zeroed()
    connector.require_used_clean(1)


def _load_base_runner() -> Callable[..., dict[str, object]]:
    completed = subprocess.run(
        [
            "git",
            "show",
            f"{_BASE_COMMIT}:bridge/Sts2AgentBridge/tools/apply_run_live.py",
        ],
        cwd=_TOOLS.parent.parent.parent,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    source = completed.stdout
    if completed.returncode != 0 or not source or b"_COMBAT_DESTINATION_KINDS" in source:
        fail(EXIT_MISMATCH, "elite_wire_base_source")
    spec = importlib.util.spec_from_loader("elite_base_run", loader=None)
    if spec is None:
        fail(EXIT_MISMATCH, "elite_wire_base_module")
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, f"{_BASE_COMMIT}:apply_run_live.py", "exec"), module.__dict__)
    runner = module.__dict__.get("_run_bounded_run")
    if not callable(runner):
        fail(EXIT_MISMATCH, "elite_wire_base_runner")
    return runner


def _base_rejects_same_elite_transcript() -> None:
    transcript: list[tuple[bytes | BaseException, bytes]] = []
    _map(transcript, "1" * 64, "elite")
    _add(transcript, _next_combat_ready("3" * 64), entry_fixture._GET_COMBAT)
    _combat_defeat(transcript, "2" * 64)
    result, connector, _ = _run(transcript, runner=_load_base_runner())
    if result.get("termination") != {
        "reason": "unsupported_destination_kind",
        "after_floor": 1,
        "destination_kind": "elite",
    }:
        fail(EXIT_MISMATCH, "elite_wire_base_accepted")
    # The frozen runner must stop immediately after the reconciled map result;
    # it must not inspect or mutate the queued fresh-combat continuation.
    if connector.index != 6:
        fail(EXIT_MISMATCH, "elite_wire_base_request_order")
    connector.require_used_clean(1, complete=False)


def _redacted(operation: Callable[[], dict[str, object]]) -> dict[str, object]:
    result: dict[str, object] | None = None

    def invoke() -> dict[str, object]:
        nonlocal result
        result = operation()
        return result

    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(invoke)
    output = (stdout.getvalue() + stderr.getvalue()).encode("ascii", "strict")
    if (
        exit_code != 0
        or stderr.getvalue()
        or _CANARY in output
        or _CREDENTIAL in output
        or result is None
    ):
        fail(EXIT_MISMATCH, "elite_wire_output_privacy")
    return result


def operation() -> dict[str, object]:
    _prefix_elite_defeat()
    _default_elite_victory_reward_continuation()
    _reward_prefix_elite_defeat()
    _post_room_elite_defeat()
    _elite_reward_failures()
    _elite_receipt_failures()
    _elite_cancellation_stops_mutation()
    _base_rejects_same_elite_transcript()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "apply_run_elite_wire_fixtures",
        "check_count": 8,
    }


if __name__ == "__main__":
    main(lambda: _redacted(operation))
