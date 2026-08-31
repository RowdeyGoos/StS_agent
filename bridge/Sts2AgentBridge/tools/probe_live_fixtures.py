#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

sys.dont_write_bytecode = True

from collections.abc import Callable

import probe_live as probe
from tool_common import (
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    ToolFailure,
    fail,
    main,
)

_FIXTURE_CREDENTIAL = b"0123456789abcdef" * 4
_FIXTURE_HEALTH = (
    b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"'
    b"00000000000000000000000000000000"
    b'"}'
)
_FIXTURE_MANIFEST = probe._MANIFEST_COMPATIBLE
_FIXTURE_LOCKED_MANIFEST = _FIXTURE_MANIFEST.replace(
    b'"build_compatibility":"compatible"',
    b'"build_compatibility":"incompatible_locked"',
).replace(b'"observe_public_screen":true', b'"observe_public_screen":false')
_FIXTURE_COMBAT = (
    b'{"schema_version":1,"status":"ready","decision_kind":"combat","actionable":true,'
    b'"decision_id":"0000000000000000000000000000000000000000000000000000000000000000","round":1,'
    b'"player":{"hp":72,"max_hp":80,"block":0,"energy":3},'
    b'"enemies":[{"index":0,"id":"CULTIST","hp":48,"max_hp":48,"block":0,"intents":["attack"]}],'
    b'"hand":[{"hand_index":0,"id":"STRIKE_IRONCLAD","type":"attack","cost":"1","target_type":"anyenemy","playable":true},'
    b'{"hand_index":1,"id":"DEFEND_IRONCLAD","type":"skill","cost":"1","target_type":"self","playable":true}],'
    b'"legal_actions":[{"action_id":"play:0:0","kind":"play_card","hand_index":0,"target_index":0},'
    b'{"action_id":"play:1","kind":"play_card","hand_index":1,"target_index":null},'
    b'{"action_id":"end_turn","kind":"end_turn","hand_index":null,"target_index":null}]}'
)


def _response(body: bytes) -> bytes:
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json; charset=utf-8\r\n"
        + b"Content-Length: "
        + str(len(body)).encode("ascii")
        + b"\r\n"
        b"Cache-Control: no-store\r\n"
        b"X-Content-Type-Options: nosniff\r\n"
        b"Connection: close\r\n"
        b"\r\n"
        + body
    )


def _request(route: str) -> bytes:
    return (
        b"GET "
        + route.encode("ascii")
        + b" HTTP/1.1\r\n"
        b"Host: 127.0.0.1:43117\r\n"
        b"Authorization: Bearer "
        + _FIXTURE_CREDENTIAL
        + b"\r\n"
        b"Accept: application/json\r\n"
        b"Connection: close\r\n"
        b"\r\n"
    )


class _FixtureSocket:
    def __init__(self, response: bytes, route: str) -> None:
        self._response = response
        self._offset = 0
        self._route = route
        self.closed = False
        self.timeouts: list[float] = []
        self.request_buffers: list[bytearray] = []

    def settimeout(self, value: float) -> None:
        if value <= 0 or value > probe._SOCKET_OPERATION_TIMEOUT_SECONDS:
            fail(EXIT_MISMATCH, "probe_fixture_timeout_bound")
        self.timeouts.append(value)

    def sendall(self, request: bytearray) -> None:
        if request != _request(self._route):
            fail(EXIT_MISMATCH, "probe_fixture_request_bytes")
        self.request_buffers.append(request)

    def recv(self, maximum: int) -> bytes:
        if maximum != probe._RECEIVE_CHUNK_BYTES:
            fail(EXIT_MISMATCH, "probe_fixture_receive_bound")
        if self._offset >= len(self._response):
            return b""
        fragment = min(17, maximum, len(self._response) - self._offset)
        result = self._response[self._offset : self._offset + fragment]
        self._offset += fragment
        return result

    def close(self) -> None:
        self.closed = True


class _FixtureConnector:
    def __init__(self, responses: list[bytes], routes: tuple[tuple[str, str], ...] | None = None) -> None:
        self._responses = responses
        self._routes = probe._BASE_ROUTES + probe._SCREEN_ROUTE if routes is None else routes
        self._offset = 0
        self.sockets: list[_FixtureSocket] = []

    def __call__(self) -> _FixtureSocket:
        if self._offset >= len(self._responses):
            fail(EXIT_MISMATCH, "probe_fixture_extra_connection")
        route = self._routes[self._offset][1]
        fixture_socket = _FixtureSocket(self._responses[self._offset], route)
        self._offset += 1
        self.sockets.append(fixture_socket)
        return fixture_socket

    def assert_cleanup(self) -> None:
        if not self.sockets or any(not fixture_socket.closed for fixture_socket in self.sockets):
            fail(EXIT_MISMATCH, "probe_fixture_socket_cleanup")
        if any(not fixture_socket.timeouts for fixture_socket in self.sockets):
            fail(EXIT_MISMATCH, "probe_fixture_timeout_missing")
        for fixture_socket in self.sockets:
            for request in fixture_socket.request_buffers:
                if any(request):
                    fail(EXIT_MISMATCH, "probe_fixture_request_not_zeroed")


def _responses(screen: bytes) -> list[bytes]:
    return [
        _response(_FIXTURE_HEALTH),
        _response(_FIXTURE_MANIFEST),
        _response(screen),
    ]


def _run_success(expected_screen: str, screen: bytes) -> None:
    connector = _FixtureConnector(_responses(screen))
    credential = bytearray(_FIXTURE_CREDENTIAL)
    payload = probe._run_probe(credential, expected_screen, connector)
    if (
        payload.get("status") != "passed"
        or payload.get("screen_kind") != expected_screen
        or payload.get("routes_checked") != 3
    ):
        fail(EXIT_MISMATCH, "probe_fixture_positive_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "probe_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _run_combat_success() -> None:
    routes = probe._BASE_ROUTES + probe._COMBAT_ROUTE
    connector = _FixtureConnector(
        [
            _response(_FIXTURE_HEALTH),
            _response(_FIXTURE_MANIFEST),
            _response(_FIXTURE_COMBAT),
        ],
        routes,
    )
    credential = bytearray(_FIXTURE_CREDENTIAL)
    payload = probe._run_probe(credential, "combat", connector)
    combat = payload.get("combat")
    recommendation = combat.get("recommendation") if isinstance(combat, dict) else None
    if (
        payload.get("status") != "passed"
        or payload.get("screen_kind") != "combat"
        or payload.get("routes_checked") != 3
        or not isinstance(recommendation, dict)
        or recommendation.get("action_id") != "play:1"
        or recommendation.get("basis") != "incoming_attack"
    ):
        fail(EXIT_MISMATCH, "probe_fixture_combat_payload")
    if any(credential):
        fail(EXIT_MISMATCH, "probe_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _expect_failure(
    expected_screen: str,
    responses: list[bytes],
    expected_code: str,
) -> None:
    connector = _FixtureConnector(responses)
    credential = bytearray(_FIXTURE_CREDENTIAL)
    try:
        probe._run_probe(credential, expected_screen, connector)
    except ToolFailure as failure:
        if failure.exit_code != EXIT_MISMATCH or failure.error_code != expected_code:
            fail(EXIT_MISMATCH, "probe_fixture_wrong_rejection")
    else:
        fail(EXIT_MISMATCH, "probe_fixture_unexpected_pass")
    if any(credential):
        fail(EXIT_MISMATCH, "probe_fixture_credential_not_zeroed")
    connector.assert_cleanup()


def _expect_invocation_failure(operation: Callable[[], object], expected_code: str) -> None:
    try:
        operation()
    except ToolFailure as failure:
        if failure.exit_code == EXIT_INVALID_INVOCATION and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "probe_fixture_wrong_invocation_rejection")
    fail(EXIT_MISMATCH, "probe_fixture_invocation_unexpected_pass")


def _validated_combat(body: bytes, decision_provider: str = "heuristic") -> dict[str, object]:
    view = memoryview(body)
    try:
        return probe._validate_combat(view, decision_provider)
    finally:
        view.release()


def _expect_combat_validation_failure(body: bytes, expected_code: str) -> None:
    try:
        _validated_combat(body)
    except ToolFailure as failure:
        if failure.exit_code == EXIT_MISMATCH and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "probe_fixture_wrong_combat_rejection")
    fail(EXIT_MISMATCH, "probe_fixture_combat_unexpected_pass")


class _InvalidCombatProvider:
    def choose(
        self,
        enemies: list[dict[str, object]],
        hand: list[dict[str, object]],
        actions: list[dict[str, object]],
    ) -> dict[str, object]:
        del enemies, hand, actions
        return {
            "action_id": "end_turn",
            "kind": "play_card",
            "hand_index": 0,
            "target_index": 0,
            "card_id": None,
            "basis": "fixture",
        }


def _expect_invalid_provider_result() -> None:
    original_provider_factory = probe.get_decision_provider
    try:
        probe.get_decision_provider = lambda _: _InvalidCombatProvider()
        _expect_combat_validation_failure(
            _FIXTURE_COMBAT,
            "decision_provider_result_mismatch",
        )
    finally:
        probe.get_decision_provider = original_provider_factory


def operation() -> dict[str, object]:
    checks: list[str] = []

    rate_limited = (
        probe._RATE_LIMITED_HEADER
        + probe._RATE_LIMITED_BODY_PREFIX
        + b"0" * 32
        + probe._RATE_LIMITED_BODY_SUFFIX
    )
    if (
        not probe._is_rate_limited_response(rate_limited)
        or probe._is_rate_limited_response(rate_limited.replace(b"429", b"503", 1))
        or probe._is_rate_limited_response(
            rate_limited.replace(b"Retry-After: 1", b"Retry-After: 2", 1)
        )
        or probe._is_rate_limited_response(
            rate_limited.replace(b'"retryable":true', b'"retryable":false', 1)
        )
        or probe._is_rate_limited_response(rate_limited[:-3] + b"XYZ")
    ):
        fail(EXIT_MISMATCH, "probe_fixture_rate_limited_classifier")
    checks.append("rate_limited_classifier")

    retryable = (
        probe._RETRYABLE_BACKEND_HEADER
        + probe._RETRYABLE_BACKEND_BODY_PREFIX
        + b"0" * 32
        + probe._RETRYABLE_BACKEND_BODY_SUFFIX
    )
    if (
        not probe._is_retryable_backend_response(retryable)
        or probe._is_retryable_backend_response(retryable.replace(b"503", b"500", 1))
        or probe._is_retryable_backend_response(
            retryable.replace(b'"retryable":true', b'"retryable":false', 1)
        )
        or probe._is_retryable_backend_response(retryable[:-3] + b"XYZ")
    ):
        fail(EXIT_MISMATCH, "probe_fixture_retryable_backend_classifier")
    checks.append("retryable_backend_classifier")

    backend_fault = (
        probe._BACKEND_FAULT_HEADER
        + probe._BACKEND_FAULT_BODY_PREFIX
        + b"0" * 32
        + probe._BACKEND_FAULT_BODY_SUFFIX
    )
    if (
        not probe._is_backend_fault_response(backend_fault)
        or probe._is_backend_fault_response(backend_fault.replace(b"500", b"503", 1))
        or probe._is_backend_fault_response(
            backend_fault.replace(b'"retryable":false', b'"retryable":true', 1)
        )
        or probe._is_backend_fault_response(backend_fault[:-3] + b"XYZ")
    ):
        fail(EXIT_MISMATCH, "probe_fixture_backend_fault_classifier")
    checks.append("backend_fault_classifier")

    _run_success("main_menu", probe._SCREEN_MAIN_MENU)
    checks.append("success_main_menu")
    _run_success("settings", probe._SCREEN_SETTINGS)
    checks.append("success_settings")
    _run_combat_success()
    checks.append("success_combat_recommendation")

    combat_summary = _validated_combat(_FIXTURE_COMBAT)
    expected_combat_summary = {
        "decision_id": "0" * 64,
        "round": 1,
        "player": {"hp": 72, "max_hp": 80, "block": 0, "energy": 3},
        "enemies": [
            {
                "index": 0,
                "id": "CULTIST",
                "hp": 48,
                "max_hp": 48,
                "block": 0,
                "intents": ["attack"],
            }
        ],
        "hand": [
            {
                "hand_index": 0,
                "id": "STRIKE_IRONCLAD",
                "type": "attack",
                "cost": "1",
                "target_type": "anyenemy",
                "playable": True,
            },
            {
                "hand_index": 1,
                "id": "DEFEND_IRONCLAD",
                "type": "skill",
                "cost": "1",
                "target_type": "self",
                "playable": True,
            },
        ],
        "legal_action_count": 3,
        "legal_actions": [
            {"action_id": "play:0:0", "kind": "play_card", "hand_index": 0, "target_index": 0},
            {"action_id": "play:1", "kind": "play_card", "hand_index": 1, "target_index": None},
            {"action_id": "end_turn", "kind": "end_turn", "hand_index": None, "target_index": None},
        ],
        "recommendation": {
            "action_id": "play:1",
            "kind": "play_card",
            "hand_index": 1,
            "target_index": None,
            "card_id": "DEFEND_IRONCLAD",
            "basis": "incoming_attack",
        },
    }
    if (
        combat_summary != expected_combat_summary
        or json.dumps(combat_summary, separators=(",", ":"), sort_keys=True).encode("ascii")
        != json.dumps(expected_combat_summary, separators=(",", ":"), sort_keys=True).encode("ascii")
    ):
        fail(EXIT_MISMATCH, "probe_fixture_combat_normalization")
    checks.append("combat_normalization_unchanged")

    _expect_combat_validation_failure(b"{", "decision_envelope_mismatch")
    checks.append("combat_envelope_malformed_json")
    _expect_combat_validation_failure(
        _FIXTURE_COMBAT.replace(b'}]}', b'}],"unexpected":0}', 1),
        "decision_envelope_mismatch",
    )
    checks.append("combat_envelope_unknown_field")
    _expect_combat_validation_failure(
        _FIXTURE_COMBAT.replace(b'"status":"ready"', b'"status":"ready","status":"ready"', 1),
        "decision_envelope_mismatch",
    )
    checks.append("combat_envelope_duplicate_field")
    _expect_combat_validation_failure(
        _FIXTURE_COMBAT.replace(b'"round":1', b'"round":0', 1),
        "decision_identity_mismatch",
    )
    checks.append("combat_identity")
    _expect_combat_validation_failure(
        _FIXTURE_COMBAT.replace(b'"energy":3', b'"energy":-1', 1),
        "decision_player_mismatch",
    )
    checks.append("combat_player")
    _expect_combat_validation_failure(
        _FIXTURE_COMBAT.replace(b'"intents":["attack"]}', b'"intents":["attack"],"unexpected":0}', 1),
        "decision_enemies_mismatch",
    )
    checks.append("combat_enemies_unknown_field")
    _expect_combat_validation_failure(
        _FIXTURE_COMBAT.replace(b'"playable":true}', b'"playable":true,"unexpected":0}', 1),
        "decision_hand_mismatch",
    )
    checks.append("combat_hand_unknown_field")
    _expect_combat_validation_failure(
        _FIXTURE_COMBAT.replace(b'"action_id":"play:1"', b'"action_id":"play:0:0"', 1),
        "decision_legal_actions_mismatch",
    )
    checks.append("combat_legal_actions_duplicate_identity")
    _expect_invalid_provider_result()
    checks.append("combat_provider_result")

    reordered_header = _response(_FIXTURE_HEALTH).replace(
        b"Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n",
        b"X-Content-Type-Options: nosniff\r\nCache-Control: no-store\r\n",
    )
    _expect_failure("main_menu", [reordered_header], "health_response_mismatch")
    checks.append("malformed_header")

    truncated_health = _response(_FIXTURE_HEALTH)[:-1]
    _expect_failure("main_menu", [truncated_health], "health_response_mismatch")
    checks.append("truncated_body")

    oversized = b"x" * (probe._MAXIMUM_RESPONSE_BYTES + 1)
    _expect_failure("main_menu", [oversized], "health_response_too_large")
    checks.append("oversized_response")

    _expect_failure(
        "main_menu",
        [_response(_FIXTURE_HEALTH), _response(b"{}")],
        "manifest_response_mismatch",
    )
    checks.append("malformed_manifest")

    _expect_failure(
        "main_menu",
        [_response(_FIXTURE_HEALTH), _response(_FIXTURE_LOCKED_MANIFEST)],
        "manifest_response_mismatch",
    )
    checks.append("locked_mode")

    _expect_failure(
        "main_menu",
        _responses(probe._SCREEN_SETTINGS),
        "screen_mismatch",
    )
    checks.append("wrong_screen")

    malformed_screen = b'{"schema_version":1,"screen_kind":"main_menu"}'
    _expect_failure(
        "main_menu",
        _responses(malformed_screen),
        "screen_response_mismatch",
    )
    checks.append("malformed_screen")

    base_arguments = [
        "--user-profile",
        "/synthetic-profile",
        "--effective-uid",
        "501",
        "--expected-screen",
        "main_menu",
    ]
    _expect_invocation_failure(
        lambda: probe.parse_args(base_arguments + ["--host", "127.0.0.1"]),
        "invalid_invocation",
    )
    checks.append("host_override_rejected")
    _expect_invocation_failure(
        lambda: probe.parse_args(base_arguments + ["--route", "/probe/v0/health"]),
        "invalid_invocation",
    )
    checks.append("route_override_rejected")
    _expect_invocation_failure(
        lambda: probe.parse_args(base_arguments[:-1] + ["unknown"]),
        "invalid_expected_screen",
    )
    checks.append("unknown_screen_rejected")

    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "probe_live_fixtures",
        "checks": checks,
        "check_count": len(checks),
    }


if __name__ == "__main__":
    main(operation)
