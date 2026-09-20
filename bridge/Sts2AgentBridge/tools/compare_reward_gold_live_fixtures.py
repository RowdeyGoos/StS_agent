#!/usr/bin/env python3
"""Python 3.10+ mocked CLI, privacy, and one-claim transport acceptance gates.

Every client execution runs inside captured CLI stdout/stderr. Identity,
credential loading and the socket connector are replaced before execution.
All canaries and transcripts are synthetic and remain in memory.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
import json
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True

import compare_reward_gold_live as adapter
import probe_live as probe
from game.analysis import conformance_evidence as evidence
from tool_common import EXIT_INVALID_INVOCATION, EXIT_MISMATCH, ToolFailure, fail, main, run_cli


_PRE_ID, _POST_ID = "a" * 64, "b" * 64
_CREDENTIAL_CANARY = "d47a9e30" * 8
_SOURCE_CANARY = "b1937a5e" * 4
_ERROR_CANARY = "SYNTHETIC_TRANSPORT_ERROR_CANARY"
_CANARIES = (_CREDENTIAL_CANARY, _SOURCE_CANARY, _ERROR_CANARY, _PRE_ID, _POST_ID)
_HEALTH = ("GET", "/probe/v0/health")
_MANIFEST = ("GET", "/probe/v0/manifest")
_DECISION = ("GET", "/probe/v0/public/reward-decision")
_CLAIM = ("POST", "/probe/v0/public/reward-action")
_PRE_ROUTES = (_HEALTH, _MANIFEST, _DECISION)
_CLAIM_ROUTES = (*_PRE_ROUTES, _CLAIM)
_COMPLETE_ROUTES = (*_CLAIM_ROUTES, _DECISION, _DECISION)
_PRIVACY_FAILURE = "gold_adapter_cli_privacy_failure"


def _require(condition: bool, code: str) -> None:
    if not condition:
        fail(EXIT_MISMATCH, code)


def _body(value: dict) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("ascii")


def _http(body: bytes) -> bytes:
    return (b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: "
            + str(len(body)).encode("ascii")
            + b"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n" + body)


def _health() -> bytes:
    return _http(_body({"schema_version": 1, "lifecycle_state": "running", "correlation_id": _SOURCE_CANARY}))


def _decision(identity: str = _PRE_ID, revision: int = 7, *, selected: bool = False,
              hp: int = 47, max_hp: int = 83, gold: int = 19, deck_count: int = 7,
              amount: int = 25, duplicate_gold: bool = False,
              extra_change: bool = False, extra_claimed_gold: bool = False) -> bytes:
    rewards = [
        {"reward_slot": 0, "reward_index": 3, "kind": "gold", "successfully_selected": selected,
         "gold_amount": amount, "cards": [], "card_selection_can_skip": False},
        {"reward_slot": 1, "reward_index": 4, "kind": "card", "successfully_selected": False,
         "gold_amount": None, "cards": [_SOURCE_CANARY], "card_selection_can_skip": True},
    ]
    if duplicate_gold or extra_claimed_gold:
        rewards.append({"reward_slot": 2, "reward_index": 5, "kind": "gold",
                        "successfully_selected": extra_claimed_gold, "gold_amount": 35,
                        "cards": [], "card_selection_can_skip": False})
    if extra_change:
        rewards[1]["cards"] = ["OTHER_SYNTHETIC_CARD"]
    actions = ([] if selected else [
        {"action_id": "claim:0", "kind": "claim_gold", "reward_slot": 0, "card_slot": None}])
    actions += [{"action_id": "open:1", "kind": "open_card", "reward_slot": 1, "card_slot": None},
                {"action_id": "proceed", "kind": "proceed", "reward_slot": None, "card_slot": None}]
    return _http(_body({"schema_version": 1, "status": "ready", "decision_kind": "reward", "actionable": True,
                        "decision_id": identity, "decision_revision": revision, "screen_kind": "rewards",
                        "player": {"hp": hp, "max_hp": max_hp, "gold": gold, "deck_count": deck_count},
                        "rewards": rewards, "legal_actions": actions}))


def _receipt(**changes: object) -> bytes:
    return _http(_body({"schema_version": 1, "status": "accepted", "mutation_state": "applied",
                        "decision_id": _PRE_ID, "action_id": "claim:0", "reason": "accepted", **changes}))


def _base() -> list[bytes]:
    post = _decision(_POST_ID, 8, selected=True, gold=44)
    return [_health(), _http(probe._MANIFEST_COMPATIBLE), _decision(), _receipt(), post, post]


class _Socket:
    def __init__(self, transcript: _Transcript, ordinal: int, response: bytes) -> None:
        self.transcript, self.ordinal, self.response = transcript, ordinal, response
        self.closed = False
        self.write_shutdown = False
        self.request_buffer: bytearray | None = None

    def settimeout(self, value: float) -> None:
        _require(0 < value <= probe._SOCKET_OPERATION_TIMEOUT_SECONDS, "gold_fixture_timeout_bound")

    def sendall(self, data: bytearray) -> None:
        self.request_buffer = data
        self.transcript.sent.append(bytes(data))
        if self.ordinal == 3 and self.transcript.fault == "post_send":
            raise OSError(_ERROR_CANARY)

    def shutdown(self, how: int) -> None:
        if how != probe.socket.SHUT_WR or not (self.request_buffer is not None) or self.write_shutdown or self.closed:
            fail(EXIT_MISMATCH, "compare_reward_gold_live_fixture_half_close")
        self.write_shutdown = True

    def recv(self, amount: int) -> bytes:
        if not self.write_shutdown:
            fail(EXIT_MISMATCH, "compare_reward_gold_live_fixture_receive_before_half_close")
        # Maintained mutations happen during the FIRST actual recv, once per
        # complete CLI execution, before any adapter result can be returned.
        if not self.transcript.first_recv:
            self.transcript.first_recv = True
            if self.transcript.leak is not None:
                source, stream_name = self.transcript.leak
                if source == "credential":
                    value = self.transcript.sent[-1].split(b"Authorization: Bearer ", 1)[1].split(b"\r\n", 1)[0].decode("ascii")
                    _require(value == _CREDENTIAL_CANARY, "gold_fixture_credential_injection")
                else:
                    _require(_SOURCE_CANARY.encode("ascii") in self.response, "gold_fixture_source_injection")
                    value = _SOURCE_CANARY
                print(value, file=sys.stdout if stream_name == "stdout" else sys.stderr)
                self.transcript.leak_count += 1
        if self.ordinal == 3 and self.transcript.fault == "post_recv":
            raise OSError(_ERROR_CANARY)
        response, self.response = self.response[:amount], self.response[amount:]
        return response

    def close(self) -> None:
        self.closed = True


class _Transcript:
    def __init__(self, responses: list[bytes], *, fault: str | None = None,
                 leak: tuple[str, str] | None = None) -> None:
        self.responses, self.fault, self.leak = responses, fault, leak
        self.credential = bytearray(_CREDENTIAL_CANARY.encode("ascii"))
        self.sent: list[bytes] = []
        self.sockets: list[_Socket] = []
        self.first_recv = False
        self.leak_count = 0

    def connect(self) -> _Socket:
        ordinal = len(self.sockets)
        _require(ordinal < len(self.responses), "gold_fixture_unexpected_request")
        socket = _Socket(self, ordinal, self.responses[ordinal])
        self.sockets.append(socket)
        return socket


@dataclass
class _Run:
    exit_code: int
    payload: dict


def _privacy_gate(stdout: str, stderr: str) -> dict:
    # Check the exact values injected above on BOTH streams, before parsing
    # JSON. A leak is a fixed fixture failure, never a canary-bearing message.
    _require(not any(value in stdout or value in stderr for value in _CANARIES), _PRIVACY_FAILURE)
    _require(stderr == "", _PRIVACY_FAILURE)
    try:
        payload = json.loads(stdout)
    except (ValueError, TypeError):
        fail(EXIT_MISMATCH, _PRIVACY_FAILURE)
    _require(type(payload) is dict, _PRIVACY_FAILURE)
    if payload.get("status") == "failed":
        _require(set(payload) == {"schema_version", "status", "code"}, _PRIVACY_FAILURE)
    else:
        _require(set(payload) == {"schema", "case_id", "artifact", "eligibility", "correspondence",
                                  "verdicts", "omissions", "admission"}, _PRIVACY_FAILURE)
        _require(payload["schema"] == "transient_reward_gold_check_v1"
                 and payload["case_id"] == evidence.CASE_ID
                 and payload["admission"] == "not_admitted", _PRIVACY_FAILURE)
        _require(payload["artifact"] == {**evidence.FROZEN_PINS, "harness_sha256": adapter._HARNESS_SHA256},
                 _PRIVACY_FAILURE)
        _require(set(payload["eligibility"]) == {"status", "code"}, _PRIVACY_FAILURE)
        _require([item["field"] for item in payload["verdicts"]] == list(evidence.FIELD_NAMES), _PRIVACY_FAILURE)
        _require(all(set(item) == {"field", "outcome", "code"} for item in payload["verdicts"]), _PRIVACY_FAILURE)
        _require(all((item["outcome"], item["code"]) in {
            ("passed", "equal"), ("divergent", "different"), ("unobserved", "not_compared")
        } for item in payload["verdicts"]), _PRIVACY_FAILURE)
        _require(payload["omissions"] == list(evidence.OMISSIONS), _PRIVACY_FAILURE)
    return payload


def _run(transcript: _Transcript, routes: tuple = _COMPLETE_ROUTES, *,
         cancel_after_requests: int | None = None) -> _Run:
    """Execute the actual CLI operation under capture, then enforce all gates."""
    stdout, stderr = StringIO(), StringIO()
    original_runner = adapter.run_transient_gold_comparison

    def runner(credential: bytearray, connector: Callable) -> dict:
        return original_runner(credential, connector, cancelled=lambda: (
            cancel_after_requests is not None and len(transcript.sent) >= cancel_after_requests))

    # No _operation substitution and no precomputed result: argument parsing,
    # identity/credential seams, transport, parsing, evaluation and CLI emission
    # all execute while both streams are captured.
    with patch.object(sys, "argv", ["compare_reward_gold_live.py", "--transient-check",
                                   "--user-profile", "/synthetic-user", "--effective-uid", "123"]), \
            patch.object(probe, "_require_identity", return_value=123), \
            patch.object(probe, "_load_fixed_credential", return_value=transcript.credential), \
            patch.object(probe, "_literal_loopback_connector", side_effect=transcript.connect), \
            patch.object(adapter, "run_transient_gold_comparison", side_effect=runner), \
            redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(adapter.operation)

    _require(transcript.credential == bytearray(64), "gold_fixture_credential_not_zeroed")
    _require(all(socket.closed for socket in transcript.sockets), "gold_fixture_socket_not_closed")
    _require(all(socket.request_buffer is not None and not any(socket.request_buffer)
                 for socket in transcript.sockets), "gold_fixture_request_not_zeroed")
    observed_routes = tuple(tuple(request.split(b"\r\n", 1)[0].decode("ascii").split(" ")[:2])
                            for request in transcript.sent)
    _require(observed_routes == routes and len(transcript.sockets) == len(routes), "gold_fixture_request_order")
    _require(sum(method == "POST" for method, _ in observed_routes) <= 1, "gold_fixture_post_budget")
    for request in transcript.sent:
        _require(b"Authorization: Bearer " + _CREDENTIAL_CANARY.encode("ascii") in request,
                 "gold_fixture_credential_injection")
        if request.startswith(b"POST "):
            _require(b"X-Sts2-Decision-Id: " + _PRE_ID.encode("ascii") + b"\r\n" in request
                     and b"X-Sts2-Action-Id: claim:0\r\n" in request, "gold_fixture_claim_binding")
    return _Run(exit_code, _privacy_gate(stdout.getvalue(), stderr.getvalue()))


def _failure(transcript: _Transcript, routes: tuple, code: str,
             exit_code: int = EXIT_MISMATCH) -> None:
    result = _run(transcript, routes)
    _require(result.exit_code == exit_code and result.payload == {
        "schema_version": 1, "status": "failed", "code": code}, "gold_fixture_wrong_failure")


def operation() -> dict[str, object]:
    checks: list[str] = []
    positive = _run(_Transcript(_base()))
    _require(positive.exit_code == 0 and positive.payload["correspondence"] == "bound_one_claim"
             and {item["outcome"] for item in positive.payload["verdicts"]} == {"passed"}, "gold_fixture_positive")
    checks.append("complete_cli_privacy_and_request_binding")

    for source in ("credential", "source"):
        for stream in ("stdout", "stderr"):
            transcript = _Transcript(_base(), leak=(source, stream))
            try:
                _run(transcript)
            except ToolFailure as error:
                _require(error.exit_code == EXIT_MISMATCH and error.error_code == _PRIVACY_FAILURE
                         and transcript.leak_count == 1, "gold_fixture_mutation_wrong_failure")
            else:
                fail(EXIT_MISMATCH, "gold_fixture_mutation_not_detected")
            checks.append("first_recv_" + source + "_" + stream + "_leak_rejected")

    # Exact error canary is present in the rejected source body; this runs the
    # same CLI gate as the passing case and the four maintained leak mutations.
    responses = _base()
    responses[2] = _http(_body({"detail": _ERROR_CANARY}))
    _failure(_Transcript(responses), _PRE_ROUTES, "gold_wire_decision_mismatch")
    checks.append("error_source_canary")

    receipt_cases = (
        (_http(_body({"detail": _ERROR_CANARY})), "gold_wire_receipt_mismatch"),
        (_receipt(status="rejected", mutation_state="none", reason="stale_decision"), "gold_claim_not_accepted"),
        (_receipt(decision_id="c" * 64), "gold_wire_receipt_mismatch"),
        (_receipt(action_id="proceed"), "gold_claim_not_accepted"),
        (_receipt(mutation_state="queued"), "gold_wire_receipt_mismatch"),
    )
    for index, (receipt, code) in enumerate(receipt_cases):
        responses = _base()
        responses[3] = receipt
        _failure(_Transcript(responses), _CLAIM_ROUTES, code)
        checks.append("receipt_rejection_" + str(index))
    for fault in ("post_send", "post_recv"):
        _failure(_Transcript(_base(), fault=fault), _CLAIM_ROUTES, "reward_action_transport_failure")
        checks.append(fault + "_one_attempt_no_followup")

    for count in (0, 3, 4, 5, 6):
        result = _run(_Transcript(_base()), _COMPLETE_ROUTES[:count], cancel_after_requests=count)
        _require(result.exit_code == 0 and result.payload["correspondence"] == "cancelled", "gold_fixture_cancellation")
        checks.append("cancel_after_" + str(count) + "_requests")

    for pre, expected in ((_decision(amount=24), "unsupported_gold_amount"),
                          (_decision(duplicate_gold=True), "ambiguous_or_absent_gold")):
        responses = _base()
        responses[2] = pre
        result = _run(_Transcript(responses), _PRE_ROUTES)
        _require(result.payload["eligibility"]["code"] == expected, "gold_fixture_eligibility")
        checks.append(expected)

    responses = _base()
    responses.insert(4, _decision())
    result = _run(_Transcript(responses), (*_CLAIM_ROUTES, _DECISION, _DECISION, _DECISION))
    _require(result.payload["correspondence"] == "bound_one_claim", "gold_fixture_fresh_post")
    checks.append("stale_then_fresh_post")

    responses = _base()
    responses[4:] = [_http(adapter.reward._REWARD_WAITING), _http(adapter.reward._REWARD_UNSUPPORTED)]
    result = _run(_Transcript(responses))
    _require(result.payload["correspondence"] == "post_not_observed", "gold_fixture_missing_post")
    checks.append("missing_post")

    for index, changes in enumerate(({"extra_change": True}, {"amount": 35},
                                     {"extra_claimed_gold": True}, {"revision": 9})):
        post = _decision(_POST_ID, selected=True, gold=44, **{"revision": 8, **changes})
        responses = _base()
        responses[4:] = [post, post]
        result = _run(_Transcript(responses))
        _require(result.payload["correspondence"] != "bound_one_claim"
                 and {item["outcome"] for item in result.payload["verdicts"]} == {"unobserved"}, "gold_fixture_post_projection")
        checks.append("post_projection_" + str(index))

    for changes, field in (({"hp": 46}, "hp_preserved"), ({"max_hp": 84}, "max_hp_preserved"),
                           ({"deck_count": 8}, "deck_count_preserved"), ({"gold": 43}, "gold_delta")):
        post = _decision(_POST_ID, 8, selected=True, **{"gold": 44, **changes})
        responses = _base()
        responses[4:] = [post, post]
        result = _run(_Transcript(responses))
        _require({item["field"] for item in result.payload["verdicts"] if item["outcome"] == "divergent"} == {field},
                 "gold_fixture_divergent_scalar")
        checks.append(field + "_divergent")

    responses = _base()
    responses[4] = _http(_body({"detail": _ERROR_CANARY}))
    _failure(_Transcript(responses), (*_CLAIM_ROUTES, _DECISION), "gold_wire_decision_mismatch")
    checks.append("invalid_post")
    with patch.object(adapter, "_DEADLINE_SECONDS", 0.0):
        _failure(_Transcript([]), (), "probe_transport_timeout")
    checks.append("deadline_before_transport")
    for arguments in ([], ["--transient-check", "--capture", "x", "--effective-uid", "1"],
                      ["--transient-check", "--user-profile", "x", "--effective-uid", "01"]):
        try:
            adapter.parse_args(arguments)
        except ToolFailure as error:
            _require(error.exit_code == EXIT_INVALID_INVOCATION, "gold_fixture_invocation")
        else:
            fail(EXIT_MISMATCH, "gold_fixture_invocation")
    checks.append("invalid_invocations")
    return {"status": "passed", "fixture": "compare_reward_gold_live", "checks": len(checks), "checked": checks}


if __name__ == "__main__":
    main(operation)
