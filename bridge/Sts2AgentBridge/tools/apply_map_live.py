#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
import time
from pathlib import Path
from typing import Any, Callable

import probe_live as probe
from decision_providers import get_map_decision_provider, map_provider_names
from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    ToolFailure,
    absolute_path,
    fail,
    main,
)

_APPLY_DEADLINE_SECONDS = 30.0
_POLL_SECONDS = 0.1
_MAP_DECISION_ROUTE = "/probe/v0/public/map-decision"
_MAP_ACTION_ROUTE = "/probe/v0/public/map-action"
_MAP_WAITING = (
    b'{"schema_version":1,"status":"waiting","decision_kind":"map",'
    b'"actionable":false,"decision_id":null,"screen_kind":"unknown",'
    b'"destination":null,"candidates":[],"legal_actions":[]}'
)
_MAP_UNSUPPORTED = _MAP_WAITING.replace(b'"waiting"', b'"unsupported"')
_NODE_KINDS = frozenset(
    ("unknown", "shop", "treasure", "rest_site", "monster", "elite", "boss", "ancient")
)


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
    if parsed["--decision-provider"] not in map_provider_names():
        fail(EXIT_INVALID_INVOCATION, "invalid_decision_provider")
    return (
        parsed["--user-profile"],
        probe._parse_effective_uid(parsed["--effective-uid"]),
        parsed["--decision-provider"],
    )


def _read_body(
    label: str,
    route: str,
    credential: bytearray,
    connector: Callable[[], Any],
    deadline: float,
    decision_id: str | None = None,
    action_id: str | None = None,
) -> bytes:
    response = probe._exchange(
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
        if probe._is_retryable_backend_response(response):
            fail(EXIT_MISMATCH, f"{label}_backend_retryable")
        body = probe._canonical_body(response, label)
        return bytes(body)
    finally:
        if body is not None:
            body.release()
        probe._zero(response)


def _decode_exact(body: bytes, keys: tuple[str, ...]) -> dict[str, object]:
    try:
        root = json.loads(
            body.decode("ascii"),
            object_pairs_hook=probe._unique_object,
            parse_constant=probe._reject_json_constant,
        )
        return probe._validate_exact_keys(root, keys)
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, "map_response_mismatch")


def _candidate(value: object, expected_index: int) -> dict[str, object]:
    candidate = probe._validate_exact_keys(value, ("candidate_index", "col", "row", "kind"))
    if (
        candidate["candidate_index"] != expected_index
        or type(candidate["col"]) is not int
        or not 0 <= candidate["col"] <= 15
        or type(candidate["row"]) is not int
        or not 0 <= candidate["row"] <= 31
        or candidate["kind"] not in _NODE_KINDS
    ):
        raise ValueError("map candidate")
    return candidate


def _validate_ready(body: bytes) -> dict[str, object]:
    try:
        root = _decode_exact(
            body,
            (
                "schema_version",
                "status",
                "decision_kind",
                "actionable",
                "decision_id",
                "screen_kind",
                "destination",
                "candidates",
                "legal_actions",
            ),
        )
        decision_id = root["decision_id"]
        if (
            root["schema_version"] != 1
            or root["status"] != "ready"
            or root["decision_kind"] != "map"
            or root["actionable"] is not True
            or root["screen_kind"] != "map"
            or root["destination"] is not None
            or not isinstance(decision_id, str)
            or len(decision_id) != 64
            or any(ord(value) not in probe._LOWER_HEX for value in decision_id)
        ):
            raise ValueError("map header")

        raw_candidates = root["candidates"]
        raw_actions = root["legal_actions"]
        if (
            not isinstance(raw_candidates, list)
            or not 1 <= len(raw_candidates) <= 8
            or not isinstance(raw_actions, list)
            or len(raw_actions) != len(raw_candidates)
        ):
            raise ValueError("map counts")
        candidates = [_candidate(value, index) for index, value in enumerate(raw_candidates)]
        actions: list[dict[str, object]] = []
        for index, raw_action in enumerate(raw_actions):
            action = probe._validate_exact_keys(
                raw_action,
                ("action_id", "kind", "candidate_index"),
            )
            if action != {
                "action_id": f"select:{index}",
                "kind": "select_map_node",
                "candidate_index": index,
            }:
                raise ValueError("map legal action")
            actions.append(action)
    except (ValueError, TypeError, KeyError):
        fail(EXIT_MISMATCH, "map_response_mismatch")
    return {
        "decision_id": decision_id,
        "screen_kind": "map",
        "candidates": candidates,
        "legal_actions": actions,
    }


def _validate_complete(body: bytes) -> dict[str, object]:
    try:
        root = _decode_exact(
            body,
            (
                "schema_version",
                "status",
                "decision_kind",
                "actionable",
                "decision_id",
                "screen_kind",
                "destination",
                "candidates",
                "legal_actions",
            ),
        )
        if (
            root["schema_version"] != 1
            or root["status"] != "complete"
            or root["decision_kind"] != "map"
            or root["actionable"] is not False
            or root["decision_id"] is not None
            or root["screen_kind"] != "room"
            or root["candidates"] != []
            or root["legal_actions"] != []
        ):
            raise ValueError("map completion")
        destination_raw = probe._validate_exact_keys(
            root["destination"],
            ("candidate_index", "col", "row", "kind"),
        )
        index = destination_raw["candidate_index"]
        if type(index) is not int or not 0 <= index <= 7:
            raise ValueError("destination index")
        destination = _candidate(destination_raw, index)
    except (ValueError, TypeError, KeyError):
        fail(EXIT_MISMATCH, "map_complete_response_mismatch")
    return {"screen_kind": "room", "destination": destination}


def _validate_action(body: bytes, decision_id: str, action_id: str) -> None:
    accepted = (
        b'{"schema_version":1,"status":"accepted","mutation_state":"applied",'
        b'"decision_id":"'
        + decision_id.encode("ascii")
        + b'","action_id":"'
        + action_id.encode("ascii")
        + b'","reason":"accepted"}'
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
            b'"decision_id":"'
            + decision_id.encode("ascii")
            + b'","action_id":"'
            + action_id.encode("ascii")
            + b'","reason":"'
            + reason.encode("ascii")
            + b'"}'
        )
        if body == rejected:
            fail(EXIT_MISMATCH, f"map_action_{reason}")
    fail(EXIT_MISMATCH, "map_action_response_mismatch")


def _run_apply_map(
    credential: bytearray,
    decision_provider: str,
    connector: Callable[[], Any],
) -> dict[str, object]:
    deadline = time.monotonic() + _APPLY_DEADLINE_SECONDS
    route_count = 0

    def read(
        label: str,
        route: str,
        decision_id: str | None = None,
        action_id: str | None = None,
    ) -> bytes:
        nonlocal route_count
        body = _read_body(
            label,
            route,
            credential,
            connector,
            deadline,
            decision_id,
            action_id,
        )
        route_count += 1
        return body

    try:
        health = read("health", probe._BASE_ROUTES[0][1])
        with memoryview(health) as body:
            probe._validate_health(body)
        manifest = read("manifest", probe._BASE_ROUTES[1][1])
        with memoryview(manifest) as body:
            probe._validate_manifest(body)

        before_body = read("map", _MAP_DECISION_ROUTE)
        if before_body in (_MAP_WAITING, _MAP_UNSUPPORTED):
            fail(EXIT_MISMATCH, "map_not_ready")
        before = _validate_ready(before_body)
        provider = get_map_decision_provider(decision_provider)
        selected = provider.choose(
            list(before["candidates"]),
            list(before["legal_actions"]),
        )
        decision_id = str(before["decision_id"])
        action_id = str(selected["action_id"])

        action_body = read(
            "map_action",
            _MAP_ACTION_ROUTE,
            decision_id,
            action_id,
        )
        _validate_action(action_body, decision_id, action_id)

        after: dict[str, object] | None = None
        while time.monotonic() < deadline:
            observed = read("map", _MAP_DECISION_ROUTE)
            if observed == _MAP_WAITING:
                time.sleep(_POLL_SECONDS)
                continue
            if observed == _MAP_UNSUPPORTED:
                fail(EXIT_MISMATCH, "post_map_state_unsupported")
            after = _validate_complete(observed)
            break
        if after is None:
            fail(EXIT_MISMATCH, "post_map_state_timeout")

        selected_destination = {
            "candidate_index": selected["candidate_index"],
            "col": selected["col"],
            "row": selected["row"],
            "kind": selected["node_kind"],
        }
        if after["destination"] != selected_destination:
            fail(EXIT_MISMATCH, "map_destination_mismatch")

        return {
            "schema_version": 1,
            "status": "passed",
            "milestone": "r0g_map_selection",
            "decision_provider": decision_provider,
            "applied": selected,
            "before": before,
            "after": after,
            "routes_checked": route_count,
        }
    finally:
        probe._zero(credential)


def _operation() -> dict[str, object]:
    user_profile_value, supplied_uid, provider = parse_args()
    user_profile: Path = absolute_path(user_profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)
    credential = probe._load_fixed_credential(user_profile, uid)
    try:
        return _run_apply_map(credential, provider, probe._literal_loopback_connector)
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
