#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
import time
from pathlib import Path
from typing import Any, Callable

import probe_live as probe
from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    ToolFailure,
    absolute_path,
    fail,
    main,
)

_ROOM_DECISION_ROUTE = "/probe/v0/public/room-decision"
_ROOM_ACTION_ROUTE = "/probe/v0/public/room-action"
_ROOM_PROVIDER = "safe"
_ROOM_DEADLINE_SECONDS = 30.0
_POLL_SECONDS = 0.1
_MAXIMUM_ACCEPTED_ACTIONS = 12
_MAXIMUM_CANDIDATES = 8
_MAXIMUM_STABLE_ID_LENGTH = 96
_LOWER_HEX_CHARACTERS = frozenset("0123456789abcdef")


def parse_args(arguments: list[str] | None = None) -> tuple[str, int, str]:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 6:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    allowed = frozenset(("--user-profile", "--effective-uid", "--decision-provider"))
    parsed: dict[str, str] = {}
    for offset in range(0, len(values), 2):
        name = values[offset]
        if name not in allowed or name in parsed:
            fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
        parsed[name] = values[offset + 1]
    if set(parsed) != allowed:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    provider = parsed["--decision-provider"]
    if provider != _ROOM_PROVIDER:
        fail(EXIT_INVALID_INVOCATION, "invalid_decision_provider")
    return (
        parsed["--user-profile"],
        probe._parse_effective_uid(parsed["--effective-uid"]),
        provider,
    )


def _canonical_decision_id(value: str) -> bool:
    return len(value) == 64 and all(character in _LOWER_HEX_CHARACTERS for character in value)


def _canonical_action_id(value: str) -> bool:
    return value == "proceed" or (
        len(value) == 8
        and value.startswith("choose:")
        and value[7] in "01234567"
    )


def _build_get_request(route: str, credential: bytearray) -> bytearray:
    allowed = tuple(value for _, value in probe._BASE_ROUTES) + (_ROOM_DECISION_ROUTE,)
    if route not in allowed:
        fail(EXIT_INTERNAL, "internal_failure")
    if not probe._credential_is_canonical(credential):
        fail(EXIT_MISMATCH, "credential_shape")
    request = bytearray()
    request.extend(b"GET ")
    request.extend(route.encode("ascii"))
    request.extend(b" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer ")
    request.extend(credential)
    request.extend(b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n")
    return request


def _build_action_request(
    credential: bytearray,
    decision_id: str,
    action_id: str,
) -> bytearray:
    if not _canonical_decision_id(decision_id) or not _canonical_action_id(action_id):
        fail(EXIT_INTERNAL, "internal_failure")
    if not probe._credential_is_canonical(credential):
        fail(EXIT_MISMATCH, "credential_shape")
    request = bytearray()
    request.extend(b"POST ")
    request.extend(_ROOM_ACTION_ROUTE.encode("ascii"))
    request.extend(b" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer ")
    request.extend(credential)
    request.extend(b"\r\nX-Sts2-Decision-Id: ")
    request.extend(decision_id.encode("ascii"))
    request.extend(b"\r\nX-Sts2-Action-Id: ")
    request.extend(action_id.encode("ascii"))
    request.extend(b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n")
    return request


def _exchange(
    label: str,
    route: str,
    credential: bytearray,
    connector: Callable[[], Any],
    deadline: float,
    decision_id: str | None = None,
    action_id: str | None = None,
) -> bytearray:
    client: Any | None = None
    request = bytearray()
    response = bytearray()
    try:
        if time.monotonic() >= deadline:
            fail(EXIT_MISMATCH, "room_transport_timeout")
        client = connector()
        connection_deadline = min(
            deadline,
            time.monotonic() + probe._CONNECTION_DEADLINE_SECONDS,
        )
        if decision_id is None and action_id is None:
            request = _build_get_request(route, credential)
        elif decision_id is not None and action_id is not None and route == _ROOM_ACTION_ROUTE:
            request = _build_action_request(credential, decision_id, action_id)
        else:
            fail(EXIT_INTERNAL, "internal_failure")
        probe._set_bounded_timeout(client, connection_deadline, label)
        client.sendall(request)
        while True:
            probe._set_bounded_timeout(client, connection_deadline, label)
            chunk = client.recv(probe._RECEIVE_CHUNK_BYTES)
            if not isinstance(chunk, (bytes, bytearray, memoryview)):
                fail(EXIT_MISMATCH, f"{label}_transport_mismatch")
            if not chunk:
                break
            if len(chunk) > probe._RECEIVE_CHUNK_BYTES:
                fail(EXIT_MISMATCH, f"{label}_transport_mismatch")
            if len(response) + len(chunk) > probe._MAXIMUM_RESPONSE_BYTES:
                fail(EXIT_MISMATCH, f"{label}_response_too_large")
            response.extend(chunk)
        if not response:
            fail(EXIT_MISMATCH, f"{label}_empty_response")
        return response
    except ToolFailure:
        probe._zero(response)
        raise
    except (OSError, TimeoutError):
        probe._zero(response)
        fail(EXIT_MISMATCH, f"{label}_transport_failure")
    finally:
        probe._zero(request)
        if client is not None:
            try:
                client.close()
            except OSError:
                pass


def _read_body(
    label: str,
    route: str,
    credential: bytearray,
    connector: Callable[[], Any],
    deadline: float,
    decision_id: str | None = None,
    action_id: str | None = None,
) -> bytes:
    response = _exchange(
        label,
        route,
        credential,
        connector,
        deadline,
        decision_id,
        action_id,
    )
    body: memoryview | None = None
    try:
        body = probe._canonical_body(response, label)
        return bytes(body)
    finally:
        if body is not None:
            body.release()
        probe._zero(response)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> object:
    raise ValueError("non-finite number")


def _exact_object(value: object, keys: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(value, dict) or tuple(value) != keys:
        raise ValueError("unexpected object shape")
    return value


def _bounded_ordinal(value: object) -> bool:
    return type(value) is int and 0 <= value <= 999


def _public_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= _MAXIMUM_STABLE_ID_LENGTH
        and value.isascii()
        and all(" " <= character <= "~" for character in value)
    )


def _validate_room(body: bytes) -> dict[str, object]:
    try:
        decoded = body.decode("ascii")
        root = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
        root = _exact_object(
            root,
            (
                "schema_version",
                "status",
                "decision_kind",
                "actionable",
                "decision_id",
                "screen_kind",
                "phase",
                "room_ordinal",
                "candidates",
                "legal_actions",
            ),
        )
        status = root["status"]
        screen_kind = root["screen_kind"]
        if (
            type(root["schema_version"]) is not int
            or root["schema_version"] != 1
            or status not in ("waiting", "unsupported", "ready", "complete")
            or root["decision_kind"] != "room"
            or screen_kind not in ("unknown", "rest_site", "event")
            or not isinstance(root["candidates"], list)
            or not isinstance(root["legal_actions"], list)
        ):
            raise ValueError("room header")

        if status != "ready":
            expected_phase = status if status in ("unsupported", "complete") else "unknown"
            if (
                root["actionable"] is not False
                or root["decision_id"] is not None
                or root["phase"] != expected_phase
                or root["candidates"] != []
                or root["legal_actions"] != []
            ):
                raise ValueError("inactive room decision")
            if status == "waiting":
                if screen_kind != "unknown" or root["room_ordinal"] is not None:
                    raise ValueError("waiting room decision")
            elif status == "complete":
                if screen_kind == "unknown" or not _bounded_ordinal(root["room_ordinal"]):
                    raise ValueError("complete room decision")
            elif (
                (screen_kind == "unknown" and root["room_ordinal"] is not None)
                or (
                    screen_kind != "unknown"
                    and not _bounded_ordinal(root["room_ordinal"])
                )
            ):
                raise ValueError("unsupported room decision")
            return root

        decision_id = root["decision_id"]
        if (
            root["actionable"] is not True
            or not isinstance(decision_id, str)
            or not _canonical_decision_id(decision_id)
            or screen_kind == "unknown"
            or root["phase"] not in ("choose_option", "proceed", "choose_or_proceed")
            or not _bounded_ordinal(root["room_ordinal"])
            or not 1 <= len(root["candidates"]) <= _MAXIMUM_CANDIDATES
            or not 1 <= len(root["legal_actions"]) <= _MAXIMUM_CANDIDATES
        ):
            raise ValueError("ready room decision")

        validated_candidates: list[dict[str, object]] = []
        candidate_action_ids: set[str] = set()
        eligible_actions: set[str] = set()
        for expected_index, raw_candidate in enumerate(root["candidates"]):
            candidate = _exact_object(
                raw_candidate,
                (
                    "candidate_index",
                    "action_id",
                    "kind",
                    "stable_id",
                    "enabled",
                    "supported",
                    "is_proceed",
                    "is_dangerous",
                ),
            )
            kind = candidate["kind"]
            action = candidate["action_id"]
            if (
                type(candidate["candidate_index"]) is not int
                or candidate["candidate_index"] != expected_index
                or not isinstance(action, str)
                or not _canonical_action_id(action)
                or action in candidate_action_ids
                or kind not in ("rest_heal", "rest_unsupported", "event_option", "proceed")
                or not _public_string(candidate["stable_id"])
                or type(candidate["enabled"]) is not bool
                or type(candidate["supported"]) is not bool
                or type(candidate["is_proceed"]) is not bool
                or type(candidate["is_dangerous"]) is not bool
            ):
                raise ValueError("room candidate")
            if kind == "proceed":
                if (
                    action != "proceed"
                    or screen_kind != "rest_site"
                    or candidate["stable_id"] != "proceed"
                    or candidate["enabled"] is not True
                    or candidate["supported"] is not True
                    or candidate["is_proceed"] is not True
                    or candidate["is_dangerous"] is not False
                ):
                    raise ValueError("proceed candidate")
            elif (
                action != f"choose:{expected_index}"
                or kind.startswith("rest_") != (screen_kind == "rest_site")
                or (kind == "event_option") != (screen_kind == "event")
            ):
                raise ValueError("choice candidate")
            if kind == "rest_heal" and (
                candidate["supported"] is not True
                or candidate["is_proceed"] is not False
                or candidate["is_dangerous"] is not False
            ):
                raise ValueError("rest heal candidate")
            if kind == "rest_unsupported" and (
                candidate["supported"] is not False
                or candidate["is_proceed"] is not False
                or candidate["is_dangerous"] is not False
            ):
                raise ValueError("unsupported rest candidate")
            if kind == "event_option" and (
                candidate["is_proceed"] is not False
                or candidate["supported"] is candidate["is_dangerous"]
            ):
                raise ValueError("event candidate safety")
            if candidate["is_dangerous"] and candidate["enabled"]:
                raise ValueError("enabled dangerous candidate")
            candidate_action_ids.add(action)
            if candidate["enabled"] and candidate["supported"]:
                eligible_actions.add(action)
            validated_candidates.append(candidate)

        legal_ids: set[str] = set()
        for raw_action in root["legal_actions"]:
            legal = _exact_object(raw_action, ("action_id", "kind", "candidate_index"))
            action_id = legal["action_id"]
            candidate_index = legal["candidate_index"]
            if (
                not isinstance(action_id, str)
                or action_id in legal_ids
                or action_id not in eligible_actions
                or type(candidate_index) is not int
                or candidate_index < 0
                or candidate_index >= len(validated_candidates)
                or validated_candidates[candidate_index]["action_id"] != action_id
            ):
                raise ValueError("legal room action")
            expected_kind = "proceed_room" if action_id == "proceed" else "choose_room_option"
            if legal["kind"] != expected_kind:
                raise ValueError("legal room action kind")
            legal_ids.add(action_id)
        if legal_ids != eligible_actions:
            raise ValueError("legal room action set")

        has_proceed = "proceed" in legal_ids
        expected_phase = (
            "proceed" if has_proceed and len(legal_ids) == 1
            else "choose_or_proceed" if has_proceed
            else "choose_option"
        )
        if root["phase"] != expected_phase:
            raise ValueError("room phase")
        return root
    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, "room_response_mismatch")


def _select_action(decision: dict[str, object]) -> dict[str, object]:
    candidates = decision["candidates"]
    legal_actions = decision["legal_actions"]
    if not isinstance(candidates, list) or not isinstance(legal_actions, list):
        fail(EXIT_INTERNAL, "internal_failure")
    legal_ids = {str(value["action_id"]) for value in legal_actions if isinstance(value, dict)}
    screen_kind = decision["screen_kind"]
    if screen_kind == "rest_site":
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("kind") == "rest_heal" and candidate.get("action_id") in legal_ids:
                return {"action_id": candidate["action_id"], "basis": "rest_heal"}
        if "proceed" in legal_ids:
            return {"action_id": "proceed", "basis": "proceed"}
    elif screen_kind == "event":
        for candidate in candidates:
            if (
                isinstance(candidate, dict)
                and candidate.get("kind") == "event_option"
                and candidate.get("is_dangerous") is False
                and candidate.get("action_id") in legal_ids
            ):
                return {"action_id": candidate["action_id"], "basis": "event_first_supported"}
    fail(EXIT_MISMATCH, "no_safe_room_action")


def _validate_action_response(body: bytes, decision_id: str, action_id: str) -> None:
    accepted = (
        b'{"schema_version":1,"status":"accepted","mutation_state":"queued",'
        b'"decision_id":"' + decision_id.encode("ascii") +
        b'","action_id":"' + action_id.encode("ascii") +
        b'","reason":"accepted"}'
    )
    if body == accepted:
        return
    for reason in (
        "stale_decision",
        "invalid_action",
        "already_applied",
        "action_limit_reached",
    ):
        rejected = (
            b'{"schema_version":1,"status":"rejected","mutation_state":"none",'
            b'"decision_id":"' + decision_id.encode("ascii") +
            b'","action_id":"' + action_id.encode("ascii") +
            b'","reason":"' + reason.encode("ascii") + b'"}'
        )
        if body == rejected:
            fail(EXIT_MISMATCH, f"room_action_{reason}")
    fail(EXIT_MISMATCH, "room_action_response_mismatch")


def _run_apply_room(
    credential: bytearray,
    decision_provider: str,
    connector: Callable[[], Any],
) -> dict[str, object]:
    deadline = time.monotonic() + _ROOM_DEADLINE_SECONDS
    route_count = 0
    actions: list[dict[str, object]] = []
    first_screen_kind: str | None = None
    first_room_ordinal: int | None = None
    try:
        health = _read_body("health", probe._BASE_ROUTES[0][1], credential, connector, deadline)
        route_count += 1
        with memoryview(health) as body:
            probe._validate_health(body)
        manifest = _read_body("manifest", probe._BASE_ROUTES[1][1], credential, connector, deadline)
        route_count += 1
        with memoryview(manifest) as body:
            probe._validate_manifest(body)

        while time.monotonic() < deadline:
            room_body = _read_body("room", _ROOM_DECISION_ROUTE, credential, connector, deadline)
            route_count += 1
            decision = _validate_room(room_body)
            status = decision["status"]
            if status == "waiting":
                time.sleep(_POLL_SECONDS)
                continue
            if status == "unsupported":
                fail(EXIT_MISMATCH, "room_state_unsupported")
            if status == "complete":
                if not actions:
                    fail(EXIT_MISMATCH, "room_not_ready")
                if (
                    decision["screen_kind"] != first_screen_kind
                    or decision["room_ordinal"] != first_room_ordinal
                ):
                    fail(EXIT_MISMATCH, "room_completion_mismatch")
                return {
                    "schema_version": 1,
                    "status": "passed",
                    "milestone": "r0i_room_interaction",
                    "decision_provider": decision_provider,
                    "screen_kind": first_screen_kind,
                    "room_ordinal": first_room_ordinal,
                    "accepted_action_count": len(actions),
                    "actions": actions,
                    "final": decision,
                    "routes_checked": route_count,
                }

            if len(actions) >= _MAXIMUM_ACCEPTED_ACTIONS:
                fail(EXIT_MISMATCH, "room_action_limit_reached")
            if first_screen_kind is None:
                first_screen_kind = str(decision["screen_kind"])
                first_room_ordinal = int(decision["room_ordinal"])
            elif (
                decision["screen_kind"] != first_screen_kind
                or decision["room_ordinal"] != first_room_ordinal
            ):
                fail(EXIT_MISMATCH, "room_transition_mismatch")

            decision_id = str(decision["decision_id"])
            if any(item["decision_id"] == decision_id for item in actions):
                fail(EXIT_MISMATCH, "room_decision_replayed")
            recommendation = _select_action(decision)
            action_id = str(recommendation["action_id"])
            action_body = _read_body(
                "room_action",
                _ROOM_ACTION_ROUTE,
                credential,
                connector,
                deadline,
                decision_id,
                action_id,
            )
            route_count += 1
            _validate_action_response(action_body, decision_id, action_id)
            actions.append({
                "decision_id": decision_id,
                "action_id": action_id,
                "basis": recommendation["basis"],
                "phase": decision["phase"],
            })
        fail(EXIT_MISMATCH, "room_interaction_timeout")
    finally:
        probe._zero(credential)


def _operation() -> dict[str, object]:
    user_profile_value, supplied_uid, provider = parse_args()
    user_profile: Path = absolute_path(user_profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)
    credential = probe._load_fixed_credential(user_profile, uid)
    try:
        return _run_apply_room(credential, provider, probe._literal_loopback_connector)
    finally:
        probe._zero(credential)


def operation() -> dict[str, object]:
    try:
        return _operation()
    except ToolFailure:
        raise
    except Exception:
        fail(EXIT_INTERNAL, "internal_failure")


if __name__ == "__main__":
    main(operation)
