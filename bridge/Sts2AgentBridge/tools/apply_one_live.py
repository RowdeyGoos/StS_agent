#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import time
from pathlib import Path
from typing import Any, Callable

import probe_live as probe
from decision_providers import provider_names
from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    ToolFailure,
    absolute_path,
    fail,
    main,
)

_APPLY_DEADLINE_SECONDS = 15.0
_POLL_SECONDS = 0.1


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
    if provider not in provider_names():
        fail(EXIT_INVALID_INVOCATION, "invalid_decision_provider")
    return (
        parsed["--user-profile"],
        probe._parse_effective_uid(parsed["--effective-uid"]),
        provider,
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
        body = probe._canonical_body(response, label)
        return bytes(body)
    finally:
        if body is not None:
            body.release()
        probe._zero(response)


def _validate_action_response(body: bytes, decision_id: str, action_id: str) -> None:
    if _classify_action_response(body, decision_id, action_id) != "accepted":
        fail(EXIT_MISMATCH, "action_response_mismatch")


def _classify_action_response(body: bytes, decision_id: str, action_id: str) -> str:
    prefix = (
        b'{"schema_version":1,"status":"'
    )
    identity = (
        b'","decision_id":"'
        + decision_id.encode("ascii")
        + b'","action_id":"'
        + action_id.encode("ascii")
        + b'","reason":"'
    )
    accepted = (
        b'{"schema_version":1,"status":"accepted","mutation_state":"queued",'
        b'"decision_id":"'
        + decision_id.encode("ascii")
        + b'","action_id":"'
        + action_id.encode("ascii")
        + b'","reason":"accepted"}'
    )
    if body == accepted:
        return "accepted"
    for reason in (
        "stale_decision",
        "invalid_action",
        "already_applied",
        "action_limit_reached",
    ):
        rejected = (
            prefix
            + b'rejected","mutation_state":"none'
            + identity
            + reason.encode("ascii")
            + b'"}'
        )
        if body == rejected:
            return reason
    fail(EXIT_MISMATCH, "action_response_mismatch")


def _run_apply_one(
    credential: bytearray,
    decision_provider: str,
    connector: Callable[[], Any],
) -> dict[str, object]:
    deadline = time.monotonic() + _APPLY_DEADLINE_SECONDS
    try:
        health = _read_body("health", probe._BASE_ROUTES[0][1], credential, connector, deadline)
        with memoryview(health) as body:
            probe._validate_health(body)
        manifest = _read_body("manifest", probe._BASE_ROUTES[1][1], credential, connector, deadline)
        with memoryview(manifest) as body:
            probe._validate_manifest(body)

        before_body = _read_body("decision", probe._COMBAT_ROUTE[0][1], credential, connector, deadline)
        with memoryview(before_body) as body:
            before = probe._validate_combat(body, decision_provider)
        recommendation = before["recommendation"]
        if not isinstance(recommendation, dict) or recommendation.get("kind") != "play_card":
            fail(EXIT_MISMATCH, "no_applicable_play_card")
        decision_id = str(before["decision_id"])
        action_id = str(recommendation["action_id"])

        action_body = _read_body(
            "action",
            probe._ACTION_ROUTE,
            credential,
            connector,
            deadline,
            decision_id,
            action_id,
        )
        _validate_action_response(action_body, decision_id, action_id)

        after: dict[str, object] | None = None
        while time.monotonic() < deadline:
            observed = _read_body(
                "decision",
                probe._COMBAT_ROUTE[0][1],
                credential,
                connector,
                deadline,
            )
            if observed == probe._COMBAT_WAITING:
                time.sleep(_POLL_SECONDS)
                continue
            if observed == probe._COMBAT_UNSUPPORTED:
                fail(EXIT_MISMATCH, "post_action_state_unsupported")
            with memoryview(observed) as body:
                candidate = probe._validate_combat(body, decision_provider)
            if candidate["decision_id"] != decision_id:
                after = candidate
                break
            time.sleep(_POLL_SECONDS)
        if after is None:
            fail(EXIT_MISMATCH, "post_action_state_timeout")

        return {
            "schema_version": 1,
            "status": "passed",
            "milestone": "r0c_one_action",
            "decision_provider": decision_provider,
            "applied": recommendation,
            "before": before,
            "after": after,
            "routes_checked": 5,
        }
    finally:
        probe._zero(credential)


def _operation() -> dict[str, object]:
    user_profile_value, supplied_uid, provider = parse_args()
    user_profile: Path = absolute_path(user_profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)
    credential = probe._load_fixed_credential(user_profile, uid)
    try:
        return _run_apply_one(credential, provider, probe._literal_loopback_connector)
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
