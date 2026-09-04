#!/usr/bin/env python3
"""Offline privacy and failure-classification fixtures for diagnose_reward_live."""
from __future__ import annotations

import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

sys.dont_write_bytecode = True

import apply_reward_live as reward
import apply_reward_live_fixtures as reward_fixture
import diagnose_reward_live as diagnose
import probe_live as probe
from reward_action_diagnostics import RewardActionDiagnostics
from tool_common import EXIT_MISMATCH, ToolFailure, fail, main


_CREDENTIAL = b"d47a9e30" * 8
_SOURCE = b"b1937a5e" * 4
_ERROR = "EXCEPTION_CANARY_DO_NOT_EMIT"
_DECISION = "a" * 64
_PRIVACY_FAILURE = "diagnostic_cli_privacy_failure"


def _require(condition: bool, code: str) -> None:
    if not condition:
        fail(EXIT_MISMATCH, code)


def _http(body: bytes) -> bytes:
    return (probe._CANONICAL_HEADER_PREFIX + str(len(body)).encode("ascii")
            + probe._CANONICAL_HEADER_SUFFIX + body)


def _health() -> bytes:
    return _http(b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"' + _SOURCE + b'"}')


def _ready() -> bytes:
    value = reward_fixture._parent(_DECISION, 0)
    value["rewards"] = []
    value["legal_actions"] = [value["legal_actions"][-1]]
    return _http(reward_fixture._body(value))


def _complete() -> bytes:
    return _http(reward_fixture._body({
        "schema_version": 1, "status": "complete", "decision_kind": "reward",
        "actionable": False, "decision_id": None, "screen_kind": "map",
        "player": reward_fixture._player(), "rewards": [], "legal_actions": [],
    }))


def _receipt(**changes: object) -> bytes:
    value = {"schema_version": 1, "status": "accepted", "mutation_state": "applied",
             "decision_id": _DECISION, "action_id": "proceed", "reason": "accepted"}
    value.update(changes)
    return _http(json.dumps(value, separators=(",", ":")).encode("ascii"))


def _rejection(reason: str) -> bytes:
    return _receipt(status="rejected", mutation_state="none", reason=reason)


def _known_http(kind: str) -> bytes:
    if kind == "429":
        return probe._RATE_LIMITED_HEADER + probe._RATE_LIMITED_BODY_PREFIX + _SOURCE + probe._RATE_LIMITED_BODY_SUFFIX
    if kind == "503_retryable":
        return probe._RETRYABLE_BACKEND_HEADER + probe._RETRYABLE_BACKEND_BODY_PREFIX + _SOURCE + probe._RETRYABLE_BACKEND_BODY_SUFFIX
    return probe._BACKEND_FAULT_HEADER + probe._BACKEND_FAULT_BODY_PREFIX + _SOURCE + probe._BACKEND_FAULT_BODY_SUFFIX


class _Socket:
    def __init__(self, transcript: "_Transcript", response: bytes) -> None:
        self.transcript, self.response = transcript, response
        self.request: bytearray | None = None
        self.closed = False

    def settimeout(self, value: float) -> None:
        _require(0 < value <= probe._SOCKET_OPERATION_TIMEOUT_SECONDS, "diagnostic_timeout_bound")

    def sendall(self, request: bytearray) -> None:
        self.request = request
        expected = ((b"GET /probe/v0/health ", b"GET /probe/v0/manifest ",
                     b"GET /probe/v0/public/reward-decision ", b"POST /probe/v0/public/reward-action ")
                    + (b"GET /probe/v0/public/reward-decision ",))[len(self.transcript.sockets) - 1]
        _require(bytes(request).startswith(expected), "diagnostic_request_route")
        _require(b"Authorization: Bearer " + _CREDENTIAL + b"\r\n" in request, "diagnostic_request_credential")
        if request.startswith(b"POST "):
            _require(b"X-Sts2-Decision-Id: " + _DECISION.encode("ascii") + b"\r\nX-Sts2-Action-Id: proceed\r\n" in request, "diagnostic_request_binding")
        self.transcript.sent.append(bytes(request))
        if self.transcript.send_failure and len(self.transcript.sockets) == 4:
            raise OSError(_ERROR)

    def recv(self, maximum: int) -> bytes:
        if not self.transcript.first_receive:
            self.transcript.first_receive = True
            if self.transcript.leak is not None and self.transcript.leak[0] == "credential":
                _require(self.request is not None and _CREDENTIAL in self.request, "diagnostic_credential_injection")
                print(_CREDENTIAL.decode("ascii"), file=sys.stdout if self.transcript.leak[1] == "stdout" else sys.stderr)
            elif self.transcript.leak is not None:
                print(_SOURCE.decode("ascii"), file=sys.stdout if self.transcript.leak[1] == "stdout" else sys.stderr)
        if self.transcript.receive_failure and len(self.transcript.sockets) == 4:
            raise TimeoutError(_ERROR)
        if self.transcript.interrupt and len(self.transcript.sockets) == 4:
            raise KeyboardInterrupt()
        result, self.response = self.response[:maximum], self.response[maximum:]
        return result

    def close(self) -> None:
        self.closed = True


class _Transcript:
    def __init__(self, action_response: bytes, after: bytes | None = None, *,
                 send_failure: bool = False, receive_failure: bool = False,
                 interrupt: bool = False, leak: tuple[str, str] | None = None) -> None:
        self.responses = [_health(), _http(probe._MANIFEST_COMPATIBLE), _ready(), action_response]
        if after is not None:
            self.responses.append(after)
        self.send_failure, self.receive_failure = send_failure, receive_failure
        self.interrupt, self.leak, self.first_receive = interrupt, leak, False
        self.credential = bytearray(_CREDENTIAL)
        self.sockets: list[_Socket] = []
        self.sent: list[bytes] = []

    def connect(self) -> _Socket:
        _require(len(self.sockets) < len(self.responses), "diagnostic_unexpected_connection")
        socket = _Socket(self, self.responses[len(self.sockets)])
        self.sockets.append(socket)
        return socket


def _run(transcript: _Transcript) -> tuple[int, dict[str, object], str, str]:
    stdout, stderr = StringIO(), StringIO()
    with patch.object(sys, "argv", ["diagnose_reward_live.py", "--user-profile", "/synthetic",
                                     "--effective-uid", "501", "--decision-provider", "first-card"]), \
            patch.object(probe, "_require_identity", return_value=501), \
            patch.object(probe, "_load_fixed_credential", return_value=transcript.credential), \
            patch.object(probe, "_literal_loopback_connector", side_effect=transcript.connect), \
            redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = diagnose.main()
    _require(transcript.credential == bytearray(len(_CREDENTIAL)), "diagnostic_credential_not_zeroed")
    _require(all(socket.closed for socket in transcript.sockets), "diagnostic_socket_not_closed")
    _require(all(socket.request is not None and not any(socket.request) for socket in transcript.sockets), "diagnostic_request_not_zeroed")
    _require(sum(request.startswith(b"POST ") for request in transcript.sent) == 1, "diagnostic_post_count")
    return exit_code, _privacy_gate(stdout.getvalue(), stderr.getvalue()), stdout.getvalue(), stderr.getvalue()


def _privacy_gate(stdout: str, stderr: str) -> dict[str, object]:
    _require(not any(value in stdout or value in stderr for value in (_CREDENTIAL.decode("ascii"), _SOURCE.decode("ascii"), _ERROR)), _PRIVACY_FAILURE)
    _require(stderr == "", _PRIVACY_FAILURE)
    try:
        return json.loads(stdout)
    except (ValueError, TypeError):
        fail(EXIT_MISMATCH, _PRIVACY_FAILURE)


def _check_failure(action: bytes, stage: str, classification: str, *, after: bytes | None = None,
                   accepted: int = 0, reconciled: int = 0) -> None:
    code, payload, _stdout, _stderr = _run(_Transcript(action, after))
    _require(code == 4 and payload["status"] == "failed", "diagnostic_failure_exit")
    _require(payload["failure_stage"] == stage and payload["classification"] == classification, "diagnostic_classification")
    _require(payload["attempted"] == 1 and payload["accepted"] == accepted and payload["reconciled"] == reconciled, "diagnostic_counter")
    _require(set(payload) == {"schema_version", "status", "code", "action_category", "failure_stage", "classification", "attempted", "accepted", "reconciled", "receipt"}, "diagnostic_shape")


def operation() -> dict[str, object]:
    checks: list[str] = []
    code, payload, _stdout, _stderr = _run(_Transcript(_receipt(), _complete()))
    _require(code == 0 and payload["status"] == "passed" and payload["attempted"] == payload["accepted"] == payload["reconciled"] == 1, "diagnostic_positive")
    checks.append("sanitized_success_shape")
    recorder = RewardActionDiagnostics()
    recorder.attempted_exchange("claim_gold")
    prior_receipt = _receipt(action_id="claim:0")
    recorder.inspect_receipt(prior_receipt[prior_receipt.find(b"\r\n\r\n") + 4:], _DECISION, "claim:0")
    recorder.accepted_receipt()
    recorder.attempted_exchange("proceed")
    _require(recorder.receipt is None and recorder.action_category == "proceed" and recorder.failure_stage == "none", "diagnostic_attempt_reset")
    checks.append("per_attempt_receipt_reset")

    for reason in ("stale_decision", "invalid_action", "already_applied", "action_limit_reached"):
        _check_failure(_rejection(reason), "receipt", "receipt_rejected")
        checks.append("canonical_rejection_" + reason)
    _check_failure(_receipt(decision_id="b" * 64), "receipt", "receipt_not_exactly_accepted")
    _code, unknown_binding, _stdout, _stderr = _run(_Transcript(_receipt(decision_id="not-a-control-id", action_id="not-an-action")))
    _require(unknown_binding["receipt"] == {"status": "accepted", "mutation_state": "applied", "reason": "accepted", "decision_binding": None, "action_binding": None}, "diagnostic_unknown_binding")
    _check_failure(_http(b"{}"), "receipt", "receipt_malformed")
    checks.extend(("wrong_binding", "malformed_binding_unknown", "malformed_receipt"))

    for kind, classification in (("429", "http_429_rate_limited"), ("503_retryable", "http_503_retryable_backend"), ("500_fault", "http_500_backend_fault")):
        _check_failure(_known_http(kind), "http_envelope", classification)
        checks.append("known_" + kind)
    _check_failure(b"HTTP/1.1 200 nope\r\n\r\n{}", "http_envelope", "http_malformed_envelope")
    _check_failure(b"x" * (probe._MAXIMUM_RESPONSE_BYTES + 1), "http_envelope", "http_response_oversize")
    checks.extend(("malformed_http", "oversize_http"))

    post_send = _run(_Transcript(_receipt(), send_failure=True))[1]
    post_receive = _run(_Transcript(_receipt(), receive_failure=True))[1]
    _require((post_send["failure_stage"], post_send["classification"]) == ("transport", "transport_failure"), "diagnostic_send_failure")
    _require((post_receive["failure_stage"], post_receive["classification"]) == ("transport", "transport_failure"), "diagnostic_receive_failure")
    checks.extend(("transport_send", "transport_receive_deadline"))

    _check_failure(_receipt(), "reconciliation", "reconciliation_failed", after=_http(b"{}"), accepted=1)
    checks.append("accepted_receipt_unreconciled_prefix")
    code, payload, _stdout, _stderr = _run(_Transcript(_receipt(), interrupt=True))
    _require(code == 5 and payload["failure_stage"] == "interrupted" and payload["attempted"] == 1, "diagnostic_interruption")
    checks.append("cancellation_cleanup")
    for source in ("credential", "source"):
        for stream in ("stdout", "stderr"):
            try:
                _run(_Transcript(_receipt(), leak=(source, stream)))
            except ToolFailure as failure:
                _require(failure.error_code == _PRIVACY_FAILURE, "diagnostic_leak_wrong_failure")
                checks.append("first_receive_" + source + "_" + stream + "_leak_rejected")
            else:
                fail(EXIT_MISMATCH, "diagnostic_leak_mutation_accepted")
    return {"schema_version": 1, "status": "passed", "suite": "reward_action_diagnostics_fixtures", "checks": checks, "check_count": len(checks)}


if __name__ == "__main__":
    main(operation)
