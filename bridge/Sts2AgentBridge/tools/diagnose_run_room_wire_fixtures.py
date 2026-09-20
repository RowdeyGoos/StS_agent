#!/usr/bin/env python3
"""Independent actual-client fixtures for the composed room diagnostic."""
from __future__ import annotations

import copy
import io
import json
import sys
from contextlib import ExitStack, nullcontext, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Optional, Union
from unittest.mock import patch

sys.dont_write_bytecode = True

import apply_run_acceptance_live as acceptance
import apply_room_live as room_client
import diagnose_run_room_live as diagnostic
import probe_live as probe
import room_stage_diagnostics as stage_model
from tool_common import (
    EXIT_INTERNAL,
    EXIT_MISMATCH,
    ToolFailure,
    fail,
    main,
    run_cli,
)


_CREDENTIAL = b"0123456789abcdef" * 4
_SOURCE = b"feedface" * 4
_EXCEPTION = "ROOM_DIAGNOSTIC_EXCEPTION_CANARY"
_PROFILE = "/synthetic-room-diagnostic-profile"
_ROOM_ORDINAL = 4
_IDS = tuple(f"{0xD1A600 + index:064x}" for index in range(12))
_ARGS = [
    "--user-profile", _PROFILE,
    "--effective-uid", "501",
    "--combat-provider", "first-legal",
    "--reward-provider", "first-card",
    "--map-provider", "first",
    "--room-provider", "safe",
    "--floor-limit", "1",
    "--entry-phase", "map",
]

_HEALTH_ROUTE = "/probe/v0/health"
_MANIFEST_ROUTE = "/probe/v0/manifest"
_MAP_ROUTE = "/probe/v0/public/map-decision"
_MAP_ACTION_ROUTE = "/probe/v0/public/map-action"
_ROOM_ROUTE = "/probe/v0/public/room-decision"
_ROOM_ACTION_ROUTE = "/probe/v0/public/room-action"
_DIAGNOSTIC_KEYS = (
    "schema_version", "status", "milestone", "code", "room", "run_acceptance"
)
_ROOM_KEYS = (
    "stage", "last_observation_status", "last_ready_kind",
    "action_exchange_attempt_count", "accepted_receipt_count",
    "last_attempted_action", "last_accepted_action", "completion_confirmed",
)

_HEALTH = (
    b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"'
    + _SOURCE
    + b'"}'
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


def _require(condition: bool, code: str) -> None:
    if not condition:
        fail(EXIT_MISMATCH, code)


def _body(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("ascii")


def _http(body: bytes) -> bytes:
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
        b"Cache-Control: no-store\r\n"
        b"X-Content-Type-Options: nosniff\r\n"
        b"Connection: close\r\n\r\n" + body
    )


def _request(route: str, decision: Optional[str] = None,
             action: Optional[str] = None) -> bytes:
    method = "GET" if decision is None else "POST"
    result = (
        f"{method} {route} HTTP/1.1\r\n"
        "Host: 127.0.0.1:43117\r\n"
        "Authorization: Bearer "
    ).encode("ascii") + _CREDENTIAL + b"\r\n"
    if decision is not None:
        result += (
            f"X-Sts2-Decision-Id: {decision}\r\n"
            f"X-Sts2-Action-Id: {action}\r\n"
        ).encode("ascii")
    return result + b"Accept: application/json\r\nConnection: close\r\n\r\n"


_GET_HEALTH = _request(_HEALTH_ROUTE)
_GET_MANIFEST = _request(_MANIFEST_ROUTE)
_GET_MAP = _request(_MAP_ROUTE)
_GET_ROOM = _request(_ROOM_ROUTE)


def _map_candidate(kind: str) -> dict[str, object]:
    return {"candidate_index": 0, "col": 2, "row": 3, "kind": kind}


def _map_ready(decision: str, kind: str) -> bytes:
    candidate = _map_candidate(kind)
    return _body({
        "schema_version": 1,
        "status": "ready",
        "decision_kind": "map",
        "actionable": True,
        "decision_id": decision,
        "screen_kind": "map",
        "destination": None,
        "candidates": [candidate],
        "legal_actions": [
            {"action_id": "select:0", "kind": "select_map_node", "candidate_index": 0}
        ],
    })


def _map_complete(kind: str) -> bytes:
    return _body({
        "schema_version": 1,
        "status": "complete",
        "decision_kind": "map",
        "actionable": False,
        "decision_id": None,
        "screen_kind": "room",
        "destination": _map_candidate(kind),
        "candidates": [],
        "legal_actions": [],
    })


_MAP_WAITING = _body({
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


def _room_candidate(index: int, kind: str, stable_id: str, *,
                    enabled: bool = True, supported: bool = True,
                    dangerous: bool = False) -> dict[str, object]:
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


def _room_ready(decision: str, screen_kind: str,
                candidates: list[dict[str, object]], legal_indexes: list[int],
                *, ordinal: int = _ROOM_ORDINAL) -> bytes:
    legal = []
    for index in legal_indexes:
        action_id = str(candidates[index]["action_id"])
        legal.append({
            "action_id": action_id,
            "kind": "proceed_room" if action_id == "proceed" else "choose_room_option",
            "candidate_index": index,
        })
    has_proceed = any(item["action_id"] == "proceed" for item in legal)
    phase = (
        "proceed" if has_proceed and len(legal) == 1
        else "choose_or_proceed" if has_proceed
        else "choose_option"
    )
    return _body({
        "schema_version": 1,
        "status": "ready",
        "decision_kind": "room",
        "actionable": True,
        "decision_id": decision,
        "screen_kind": screen_kind,
        "phase": phase,
        "room_ordinal": ordinal,
        "candidates": candidates,
        "legal_actions": legal,
    })


def _room_inactive(status: str, *, screen_kind: str = "unknown",
                   ordinal: Optional[int] = None) -> bytes:
    return _body({
        "schema_version": 1,
        "status": status,
        "decision_kind": "room",
        "actionable": False,
        "decision_id": None,
        "screen_kind": screen_kind,
        "phase": "unknown" if status == "waiting" else status,
        "room_ordinal": ordinal,
        "candidates": [],
        "legal_actions": [],
    })


_ROOM_WAITING = _room_inactive("waiting")


def _receipt(decision: str, action: str, *, status: str = "accepted",
             reason: str = "accepted", decision_override: Optional[str] = None,
             action_override: Optional[str] = None) -> bytes:
    return _body({
        "schema_version": 1,
        "status": status,
        "mutation_state": "applied" if status == "accepted" else "none",
        "decision_id": decision if decision_override is None else decision_override,
        "action_id": action if action_override is None else action_override,
        "reason": reason,
    })


@dataclass
class Exchange:
    expected: bytes
    response: Union[bytes, BaseException]
    recv_advance: float = 0.0
    close_advance: float = 0.0
    fail_after_first_chunk: bool = False


class Clock:
    def __init__(self, sleep_advance: float = 10.0) -> None:
        self.now = 100.0
        self.sleep_advance = sleep_advance

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        _require(seconds in (0.1, 1.0), "room_diagnostic_fixture_sleep")
        self.now += self.sleep_advance if seconds == 0.1 else seconds


class Transcript:
    def __init__(self, exchanges: list[Exchange], *,
                 leak: Optional[tuple[str, str]] = None,
                 sleep_advance: float = 10.0) -> None:
        self.exchanges = exchanges
        self.leak = leak
        self.clock = Clock(sleep_advance)
        self.index = 0
        self.sockets: list[Socket] = []
        self.credentials: list[bytearray] = []
        self.response_buffers: list[bytearray] = []
        self.receiving = False
        self.first_receive = True
        self.posts = 0

    def credential(self, *_: object) -> bytearray:
        value = bytearray(_CREDENTIAL)
        self.credentials.append(value)
        return value

    def connect(self) -> "Socket":
        _require(self.index < len(self.exchanges), "room_diagnostic_unexpected_followup")
        exchange = self.exchanges[self.index]
        self.index += 1
        if isinstance(exchange.response, BaseException) and not exchange.expected:
            raise exchange.response
        socket = Socket(self, exchange)
        self.sockets.append(socket)
        return socket

    def assert_clean(self, expected_posts: int) -> None:
        _require(self.index == len(self.exchanges), "room_diagnostic_transcript_not_exhausted")
        _require(all(item.closed for item in self.sockets), "room_diagnostic_socket_not_closed")
        _require(
            all(item.request is not None and not any(item.request) for item in self.sockets),
            "room_diagnostic_request_not_zeroed",
        )
        _require(self.credentials and all(not any(value) for value in self.credentials),
                 "room_diagnostic_credential_not_zeroed")
        _require(all(not any(value) for value in self.response_buffers),
                 "room_diagnostic_response_not_zeroed")
        _require(self.posts == expected_posts, "room_diagnostic_post_count")


class Socket:
    def __init__(self, transcript: Transcript, exchange: Exchange) -> None:
        self.transcript = transcript
        self.exchange = exchange
        self.offset = 0
        self.receives = 0
        self.request: Optional[bytearray] = None
        self.closed = False
        self.write_shutdown = False
        self.advanced = False

    def settimeout(self, value: float) -> None:
        _require(0 < value <= probe._SOCKET_OPERATION_TIMEOUT_SECONDS,
                 "room_diagnostic_timeout_bound")

    def sendall(self, request: bytearray) -> None:
        self.request = request
        _require(bytes(request) == self.exchange.expected, "room_diagnostic_exact_request")
        self.transcript.posts += request.startswith(b"POST ")

    def shutdown(self, how: int) -> None:
        if how != probe.socket.SHUT_WR or not (self.request is not None) or self.write_shutdown or self.closed:
            fail(EXIT_MISMATCH, "diagnose_run_room_wire_fixture_half_close")
        self.write_shutdown = True

    def recv(self, maximum: int) -> bytes:
        if not self.write_shutdown:
            fail(EXIT_MISMATCH, "diagnose_run_room_wire_fixture_receive_before_half_close")
        owner = self.transcript
        _require(maximum == probe._RECEIVE_CHUNK_BYTES, "room_diagnostic_receive_bound")
        if isinstance(self.exchange.response, BaseException):
            raise self.exchange.response
        if self.exchange.fail_after_first_chunk and self.receives == 1:
            raise KeyboardInterrupt
        if self.offset >= len(self.exchange.response):
            owner.receiving = False
            return b""
        if not self.advanced:
            owner.clock.now += self.exchange.recv_advance
            self.advanced = True
        end = min(self.offset + 67, len(self.exchange.response))
        chunk = self.exchange.response[self.offset:end]
        self.offset = end
        self.receives += 1
        owner.receiving = True
        if owner.first_receive:
            owner.first_receive = False
            if owner.leak is not None:
                source, stream = owner.leak
                value = _CREDENTIAL if source == "credential" else _SOURCE
                print(value.decode("ascii"),
                      file=sys.stdout if stream == "stdout" else sys.stderr)
        return chunk

    def close(self) -> None:
        if not self.closed:
            self.transcript.clock.now += self.exchange.close_advance
            self.closed = True


def _exchange(request: bytes, body: Union[bytes, BaseException], *,
              recv_advance: float = 0.0, close_advance: float = 0.0,
              fail_after_first_chunk: bool = False) -> Exchange:
    response = body if isinstance(body, BaseException) else _http(body)
    return Exchange(request, response, recv_advance, close_advance, fail_after_first_chunk)


def _base(*, health_close: float = 0.0,
          manifest_close: float = 0.0) -> list[Exchange]:
    return [
        _exchange(_GET_HEALTH, _HEALTH, close_advance=health_close),
        _exchange(_GET_MANIFEST, _MANIFEST, close_advance=manifest_close),
    ]


def _map_prefix(kind: str) -> list[Exchange]:
    decision = _IDS[0]
    return _base() + [
        _exchange(_GET_MAP, _map_ready(decision, kind)),
        _exchange(
            _request(_MAP_ACTION_ROUTE, decision, "select:0"),
            _receipt(decision, "select:0"),
        ),
        _exchange(_GET_MAP, _MAP_WAITING),
        _exchange(_GET_MAP, _map_complete(kind)),
    ]


def _room_preflight(screen_kind: str = "rest_site", *,
                    ordinal: int = _ROOM_ORDINAL) -> list[Exchange]:
    candidate = _room_candidate(0, "rest_heal", "HEAL") if screen_kind == "rest_site" else _room_candidate(0, "event_option", "EVENT.SAFE")
    return [_exchange(_GET_ROOM, _room_ready(_IDS[1], screen_kind, [candidate], [0], ordinal=ordinal))]


def _rest_ready(decision: str, action: str = "heal", *,
                ordinal: int = _ROOM_ORDINAL) -> bytes:
    if action == "heal":
        candidates = [_room_candidate(0, "rest_heal", "HEAL")]
        legal = [0]
    else:
        candidates = [
            _room_candidate(0, "rest_heal", "HEAL", enabled=False),
            _room_candidate(1, "proceed", "proceed"),
        ]
        legal = [1]
    return _room_ready(decision, "rest_site", candidates, legal, ordinal=ordinal)


def _event_ready(decision: str, *, second: bool = False,
                 ordinal: int = _ROOM_ORDINAL) -> bytes:
    if second:
        candidates = [_room_candidate(0, "event_option", "EVENT.CONTINUE")]
        legal = [0]
    else:
        candidates = [
            _room_candidate(0, "event_option", "EVENT.DANGEROUS",
                            enabled=False, supported=False, dangerous=True),
            _room_candidate(1, "event_option", "EVENT.SAFE"),
        ]
        legal = [1]
    return _room_ready(decision, "event", candidates, legal, ordinal=ordinal)


def _room_record(stage: str, status: str = "none", kind: str = "none",
                 attempts: int = 0, accepted: int = 0,
                 attempted_action: str = "none", accepted_action: str = "none",
                 complete: bool = False) -> dict[str, object]:
    return {
        "stage": stage,
        "last_observation_status": status,
        "last_ready_kind": kind,
        "action_exchange_attempt_count": attempts,
        "accepted_receipt_count": accepted,
        "last_attempted_action": attempted_action,
        "last_accepted_action": accepted_action,
        "completion_confirmed": complete,
    }


def _expected_failure(code: str, room_record: Optional[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "failed",
        "milestone": "r0i_run_room_diagnostic",
        "code": code,
        "room": room_record,
        "run_acceptance": None,
    }


def _invoke(module: object, transcript: Transcript,
            *, args: Optional[list[str]] = None) -> tuple[int, dict[str, object]]:
    stdout, stderr = io.StringIO(), io.StringIO()

    class TrackedBytearray(bytearray):
        def extend(self, value: object) -> None:
            if transcript.receiving:
                transcript.receiving = False
                if not any(self is item for item in transcript.response_buffers):
                    transcript.response_buffers.append(self)
            super().extend(value)

    with ExitStack() as stack:
        stack.enter_context(patch.object(sys, "argv", [getattr(module, "__name__", "diagnostic"), *(args or _ARGS)]))
        identity = stack.enter_context(patch.object(probe, "_require_identity", return_value=501))
        loader = stack.enter_context(patch.object(probe, "_load_fixed_credential", side_effect=transcript.credential))
        connector = stack.enter_context(patch.object(probe, "_literal_loopback_connector", side_effect=transcript.connect))
        stack.enter_context(patch.object(probe, "bytearray", TrackedBytearray, create=True))
        stack.enter_context(patch.object(probe.time, "monotonic", side_effect=transcript.clock.monotonic))
        stack.enter_context(patch.object(probe.time, "sleep", side_effect=transcript.clock.sleep))
        stack.enter_context(redirect_stdout(stdout))
        stack.enter_context(redirect_stderr(stderr))
        exit_code = (
            run_cli(module.operation)
            if module is acceptance
            else module.main()
        )
    _require(identity.called, "room_diagnostic_identity_not_called")
    _require(loader.called, "room_diagnostic_credential_not_loaded")
    _require(connector.call_count == transcript.index, "room_diagnostic_connector_count")
    output = stdout.getvalue()
    forbidden = (
        _CREDENTIAL.decode("ascii"), _SOURCE.decode("ascii"), _EXCEPTION,
        _PROFILE, "EVENT.SAFE", "EVENT.CONTINUE", "HEAL", *_IDS,
    )
    _require(stderr.getvalue() == "", "room_diagnostic_unexpected_stderr")
    _require(not any(value in output for value in forbidden), "room_diagnostic_output_privacy")
    try:
        payload = json.loads(output)
    except (TypeError, ValueError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, "room_diagnostic_output_json")
    _require(type(payload) is dict, "room_diagnostic_output_object")
    _require(
        output == json.dumps(payload, separators=(",", ":")) + "\n",
        "room_diagnostic_output_canonical",
    )
    if module is diagnostic:
        _require(tuple(payload) == _DIAGNOSTIC_KEYS, "room_diagnostic_output_shape")
        room = payload["room"]
        _require(
            room is None or type(room) is dict and tuple(room) == _ROOM_KEYS,
            "room_diagnostic_room_shape",
        )
    return exit_code, payload


def _execute(exchanges: list[Exchange], expected: dict[str, object], *,
             expected_exit: int = EXIT_MISMATCH, expected_posts: int = 1,
             leak: Optional[tuple[str, str]] = None) -> None:
    transcript = Transcript(exchanges, leak=leak)
    exit_code, payload = _invoke(diagnostic, transcript)
    _require(exit_code == expected_exit, "room_diagnostic_exit")
    _require(payload == expected, "room_diagnostic_payload")
    transcript.assert_clean(expected_posts)


def _room_start(screen_kind: str = "rest_site", *,
                ordinal: int = _ROOM_ORDINAL) -> list[Exchange]:
    destination = "rest_site" if screen_kind == "rest_site" else "ancient"
    return _map_prefix(destination) + _room_preflight(screen_kind, ordinal=ordinal) + _base()


def _waiting_timeout(prefix: list[Exchange]) -> list[Exchange]:
    return prefix + [_exchange(_GET_ROOM, _ROOM_WAITING) for _ in range(3)]


def _initial_and_setup_stages() -> int:
    _execute(
        _map_prefix("rest_site")
        + [_exchange(_GET_ROOM, _ROOM_WAITING) for _ in range(3)],
        _expected_failure("run_room_ready_timeout", _room_record("not_entered")),
    )
    _execute(
        _waiting_timeout(_room_start()),
        _expected_failure(
            "room_interaction_timeout",
            _room_record("room_waiting", status="waiting"),
        ),
    )
    _execute(
        _map_prefix("rest_site")
        + _room_preflight()
        + _base(health_close=15.0, manifest_close=15.0),
        _expected_failure(
            "room_interaction_timeout",
            _room_record("manifest_read"),
        ),
    )
    return 3


def _first_action_failures() -> int:
    decision = _IDS[2]
    ready = _rest_ready(decision)
    post = _request(_ROOM_ACTION_ROUTE, decision, "choose:0")
    exchange_record = _room_record(
        "action_exchange", "ready", "rest_site", 1, 0, "rest_heal", "none"
    )
    _execute(
        _room_start() + [
            _exchange(_GET_ROOM, ready),
            _exchange(post, OSError(_EXCEPTION)),
        ],
        _expected_failure("room_action_transport_failure", exchange_record),
        expected_posts=2,
    )
    receipt_record = _room_record(
        "action_receipt", "ready", "rest_site", 1, 0, "rest_heal", "none"
    )
    malformed = b'{"schema_version":1,"status":"unknown"}'
    wrong_bound = _receipt(decision, "choose:0", decision_override=_IDS[9])
    rejected = _receipt(
        decision, "choose:0", status="rejected", reason="stale_decision"
    )
    for body, code in (
        (malformed, "room_action_response_mismatch"),
        (wrong_bound, "room_action_response_mismatch"),
        (rejected, "room_action_stale_decision"),
    ):
        _execute(
            _room_start() + [
                _exchange(_GET_ROOM, ready),
                _exchange(post, body),
            ],
            _expected_failure(code, receipt_record),
            expected_posts=2,
        )
    return 4


def _accepted_rest_stages() -> int:
    heal_id = _IDS[2]
    heal_post = _request(_ROOM_ACTION_ROUTE, heal_id, "choose:0")
    heal_prefix = _room_start() + [
        _exchange(_GET_ROOM, _rest_ready(heal_id)),
        _exchange(heal_post, _receipt(heal_id, "choose:0"), close_advance=30.0),
    ]
    _execute(
        heal_prefix,
        _expected_failure(
            "room_interaction_timeout",
            _room_record(
                "post_action", "ready", "rest_site", 1, 1,
                "rest_heal", "rest_heal",
            ),
        ),
        expected_posts=2,
    )

    heal_waiting = _room_start() + [
        _exchange(_GET_ROOM, _rest_ready(heal_id)),
        _exchange(heal_post, _receipt(heal_id, "choose:0")),
    ]
    _execute(
        _waiting_timeout(heal_waiting),
        _expected_failure(
            "room_interaction_timeout",
            _room_record(
                "room_waiting", "waiting", "rest_site", 1, 1,
                "rest_heal", "rest_heal",
            ),
        ),
        expected_posts=2,
    )

    proceed_id = _IDS[3]
    proceed_post = _request(_ROOM_ACTION_ROUTE, proceed_id, "proceed")
    proceed_prefix = _room_start() + [
        _exchange(_GET_ROOM, _rest_ready(proceed_id, "proceed")),
        _exchange(proceed_post, _receipt(proceed_id, "proceed")),
    ]
    _execute(
        _waiting_timeout(proceed_prefix),
        _expected_failure(
            "room_interaction_timeout",
            _room_record(
                "room_waiting", "waiting", "rest_site", 1, 1,
                "rest_proceed", "rest_proceed",
            ),
        ),
        expected_posts=2,
    )
    return 3


def _accepted_event_stages() -> int:
    first_id, second_id = _IDS[4], _IDS[5]
    first = [
        _exchange(_GET_ROOM, _event_ready(first_id)),
        _exchange(
            _request(_ROOM_ACTION_ROUTE, first_id, "choose:1"),
            _receipt(first_id, "choose:1"),
        ),
    ]
    _execute(
        _waiting_timeout(_room_start("event") + first),
        _expected_failure(
            "room_interaction_timeout",
            _room_record(
                "room_waiting", "waiting", "event", 1, 1,
                "event_choice", "event_choice",
            ),
        ),
        expected_posts=2,
    )
    second = [
        _exchange(_GET_ROOM, _event_ready(second_id, second=True)),
        _exchange(
            _request(_ROOM_ACTION_ROUTE, second_id, "choose:0"),
            _receipt(second_id, "choose:0"),
        ),
    ]
    _execute(
        _waiting_timeout(_room_start("event") + first + second),
        _expected_failure(
            "room_interaction_timeout",
            _room_record(
                "room_waiting", "waiting", "event", 2, 2,
                "event_choice", "event_choice",
            ),
        ),
        expected_posts=3,
    )
    return 2


def _replay_and_context_failures() -> int:
    decision = _IDS[2]
    heal = [
        _exchange(_GET_ROOM, _rest_ready(decision)),
        _exchange(
            _request(_ROOM_ACTION_ROUTE, decision, "choose:0"),
            _receipt(decision, "choose:0"),
        ),
    ]
    _execute(
        _room_start() + heal + [_exchange(_GET_ROOM, _rest_ready(decision))],
        _expected_failure(
            "room_decision_replayed",
            _room_record(
                "room_validation", "ready", "rest_site", 1, 1,
                "rest_heal", "rest_heal",
            ),
        ),
        expected_posts=2,
    )
    _execute(
        _room_start() + heal + [
            _exchange(_GET_ROOM, _event_ready(_IDS[4]))
        ],
        _expected_failure(
            "room_expected_context_mismatch",
            _room_record(
                "room_validation", "ready", "event", 1, 1,
                "rest_heal", "rest_heal",
            ),
        ),
        expected_posts=2,
    )
    _execute(
        _room_start()[:-2] + _base() + [
            _exchange(_GET_ROOM, _rest_ready(decision, ordinal=5))
        ],
        _expected_failure(
            "room_expected_context_mismatch",
            _room_record("room_validation", "ready", "rest_site"),
        ),
    )
    _execute(
        _room_start() + heal + [
            _exchange(
                _GET_ROOM,
                _room_inactive("complete", screen_kind="rest_site", ordinal=5),
            )
        ],
        _expected_failure(
            "room_completion_mismatch",
            _room_record(
                "room_validation", "complete", "rest_site", 1, 1,
                "rest_heal", "rest_heal",
            ),
        ),
        expected_posts=2,
    )
    return 4


def _cancellation_and_internal_failure() -> int:
    decision = _IDS[2]
    action_request = _request(_ROOM_ACTION_ROUTE, decision, "choose:0")
    _execute(
        _room_start() + [
            _exchange(_GET_ROOM, _rest_ready(decision)),
            _exchange(
                action_request,
                _receipt(decision, "choose:0"),
                fail_after_first_chunk=True,
            ),
        ],
        _expected_failure(
            "interrupted",
            _room_record(
                "action_exchange", "ready", "rest_site", 1, 0,
                "rest_heal", "none",
            ),
        ),
        expected_exit=EXIT_INTERNAL,
        expected_posts=2,
    )
    accepted = _room_start() + [
        _exchange(_GET_ROOM, _rest_ready(decision)),
        _exchange(action_request, _receipt(decision, "choose:0")),
        _exchange(_GET_ROOM, _ROOM_WAITING, fail_after_first_chunk=True),
    ]
    _execute(
        accepted,
        _expected_failure(
            "interrupted",
            _room_record(
                "room_read", "ready", "rest_site", 1, 1,
                "rest_heal", "rest_heal",
            ),
        ),
        expected_exit=EXIT_INTERNAL,
        expected_posts=2,
    )
    _execute(
        _room_start() + [
            _exchange(_GET_ROOM, _rest_ready(decision)),
            _exchange(action_request, RuntimeError(_EXCEPTION)),
        ],
        _expected_failure(
            "internal_failure",
            _room_record(
                "action_exchange", "ready", "rest_site", 1, 0,
                "rest_heal", "none",
            ),
        ),
        expected_exit=EXIT_INTERNAL,
        expected_posts=2,
    )
    return 3


def _successful_room_transcript() -> list[Exchange]:
    heal_id, proceed_id = _IDS[2], _IDS[3]
    return (
        _room_start()
        + [
            _exchange(_GET_ROOM, _rest_ready(heal_id)),
            _exchange(
                _request(_ROOM_ACTION_ROUTE, heal_id, "choose:0"),
                _receipt(heal_id, "choose:0"),
            ),
            _exchange(_GET_ROOM, _rest_ready(proceed_id, "proceed")),
            _exchange(
                _request(_ROOM_ACTION_ROUTE, proceed_id, "proceed"),
                _receipt(proceed_id, "proceed"),
            ),
            _exchange(
                _GET_ROOM,
                _room_inactive(
                    "complete", screen_kind="rest_site", ordinal=_ROOM_ORDINAL
                ),
            ),
            _exchange(_GET_MAP, _map_complete("rest_site")),
            _exchange(_GET_MAP, _MAP_WAITING),
            _exchange(_GET_MAP, _map_ready(_IDS[6], "monster")),
        ]
    )


def _success_parity() -> int:
    baseline_transcript = Transcript(_successful_room_transcript())
    baseline_exit, baseline = _invoke(acceptance, baseline_transcript)
    _require(baseline_exit == 0, "room_diagnostic_baseline_exit")
    baseline_transcript.assert_clean(3)

    diagnostic_transcript = Transcript(
        _successful_room_transcript(), leak=("credential", "stdout")
    )
    diagnostic_exit, result = _invoke(diagnostic, diagnostic_transcript)
    _require(diagnostic_exit == 0, "room_diagnostic_success_exit")
    _require(result == {
        "schema_version": 1,
        "status": "passed",
        "milestone": "r0i_run_room_diagnostic",
        "code": "none",
        "room": _room_record(
            "complete", "complete", "rest_site", 2, 2,
            "rest_proceed", "rest_proceed", True,
        ),
        "run_acceptance": baseline,
    }, "room_diagnostic_success_parity")
    diagnostic_transcript.assert_clean(3)

    no_room = _map_prefix("shop")
    no_room_baseline_transcript = Transcript(copy.deepcopy(no_room))
    no_room_exit, no_room_baseline = _invoke(acceptance, no_room_baseline_transcript)
    _require(no_room_exit == 0, "room_diagnostic_no_room_baseline_exit")
    no_room_baseline_transcript.assert_clean(1)
    no_room_diagnostic_transcript = Transcript(
        copy.deepcopy(no_room), leak=("source", "stderr")
    )
    no_room_diagnostic_exit, no_room_result = _invoke(
        diagnostic, no_room_diagnostic_transcript
    )
    _require(no_room_diagnostic_exit == 0, "room_diagnostic_no_room_exit")
    _require(no_room_result == {
        "schema_version": 1,
        "status": "passed",
        "milestone": "r0i_run_room_diagnostic",
        "code": "none",
        "room": _room_record("not_entered"),
        "run_acceptance": no_room_baseline,
    }, "room_diagnostic_no_room_parity")
    no_room_diagnostic_transcript.assert_clean(1)
    return 2


def _mutations_are_rejected() -> int:
    def get_instead(credential: bytearray, decision: str,
                    action: str) -> bytearray:
        del decision, action
        return room_client._build_get_request(_ROOM_ROUTE, credential)

    transcript = Transcript(_successful_room_transcript())
    with patch.object(room_client, "_build_action_request", side_effect=get_instead):
        exit_code, payload = _invoke(diagnostic, transcript)
    _require(
        exit_code == EXIT_INTERNAL
        and payload["status"] == "failed"
        and payload["code"] == "internal_failure"
        and payload["run_acceptance"] is None,
        "room_diagnostic_get_mutant_survived",
    )
    _require(transcript.index == 11, "room_diagnostic_get_mutant_followup")
    _require(all(item.closed for item in transcript.sockets),
             "room_diagnostic_get_mutant_socket")
    _require(all(item.request is not None and not any(item.request)
                 for item in transcript.sockets),
             "room_diagnostic_get_mutant_request")
    _require(all(not any(value) for value in transcript.credentials),
             "room_diagnostic_get_mutant_credential")
    _require(all(not any(value) for value in transcript.response_buffers),
             "room_diagnostic_get_mutant_response")

    transcript = Transcript(_successful_room_transcript())
    def corrupt_count(owner: object) -> None:
        owner.accepted_receipt_count = 2

    with patch.object(stage_model.RoomStageDiagnostics, "accept_receipt", corrupt_count):
        exit_code, payload = _invoke(diagnostic, transcript)
    _require(
        exit_code == EXIT_INTERNAL
        and payload == _expected_failure("internal_failure", None),
        "room_diagnostic_count_mutant_survived",
    )
    _require(transcript.index == 11, "room_diagnostic_count_mutant_followup")
    _require(all(item.closed for item in transcript.sockets),
             "room_diagnostic_count_mutant_socket")
    _require(all(item.request is not None and not any(item.request)
                 for item in transcript.sockets),
             "room_diagnostic_count_mutant_request")
    _require(all(not any(value) for value in transcript.credentials),
             "room_diagnostic_count_mutant_credential")
    _require(all(not any(value) for value in transcript.response_buffers),
             "room_diagnostic_count_mutant_response")

    original_complete = stage_model.RoomStageDiagnostics.mark_complete

    def wrong_category(owner: object) -> None:
        original_complete(owner)
        owner.last_accepted_action = "event_choice"

    transcript = Transcript(_successful_room_transcript())
    with patch.object(stage_model.RoomStageDiagnostics, "mark_complete", wrong_category):
        exit_code, payload = _invoke(diagnostic, transcript)
    _require(
        exit_code == EXIT_INTERNAL
        and payload == _expected_failure("internal_failure", None),
        "room_diagnostic_category_mutant_survived",
    )
    _require(
        transcript.index == len(transcript.exchanges),
        "room_diagnostic_category_mutant_followup",
    )
    _require(all(item.closed for item in transcript.sockets),
             "room_diagnostic_category_mutant_socket")
    _require(all(not any(value) for value in transcript.credentials),
             "room_diagnostic_category_mutant_credential")
    _require(all(not any(value) for value in transcript.response_buffers),
             "room_diagnostic_category_mutant_response")

    transcript = Transcript(
        _successful_room_transcript(), leak=("credential", "stdout")
    )
    try:
        with patch.object(
            diagnostic, "redirect_stdout", side_effect=lambda _sink: nullcontext()
        ):
            _invoke(diagnostic, transcript)
    except ToolFailure as failure:
        _require(
            failure.exit_code == EXIT_MISMATCH
            and failure.error_code == "room_diagnostic_output_privacy",
            "room_diagnostic_privacy_mutant_wrong_failure",
        )
    else:
        fail(EXIT_MISMATCH, "room_diagnostic_privacy_mutant_survived")
    transcript.assert_clean(3)
    return 4


def operation() -> dict[str, object]:
    check_count = _initial_and_setup_stages()
    check_count += _first_action_failures()
    check_count += _accepted_rest_stages()
    check_count += _accepted_event_stages()
    check_count += _replay_and_context_failures()
    check_count += _cancellation_and_internal_failure()
    check_count += _success_parity()
    check_count += _mutations_are_rejected()
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "diagnose_run_room_wire_fixtures",
        "check_count": check_count,
    }


if __name__ == "__main__":
    main(operation)
