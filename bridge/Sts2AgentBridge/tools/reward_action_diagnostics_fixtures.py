#!/usr/bin/env python3
"""Actual-client, in-memory acceptance gates. No live identity or socket I/O."""
from __future__ import annotations

import json
import socket
import sys
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from unittest.mock import patch

sys.dont_write_bytecode = True

import apply_reward_live as reward
import apply_reward_live_fixtures as factory
import diagnose_reward_live as diagnose
import probe_live as probe
from tool_common import EXIT_MISMATCH, ToolFailure, fail, main

_CREDENTIAL = b"d47a9e30" * 8
_SOURCE = b"b1937a5e" * 4
_ERROR = "EXCEPTION_CANARY_DO_NOT_EMIT"
_IDS = tuple(f"{index + 0xcafe:064x}" for index in range(18))
_ARGS = ["--user-profile", "/synthetic-profile", "--effective-uid", "501",
         "--decision-provider", "first-card"]
_PRIVACY = "diagnostic_cli_privacy_failure"
_WIPING = "diagnostic_response_not_zeroed"
_GET_REWARD = "/probe/v0/public/reward-decision"
_POST_REWARD = "/probe/v0/public/reward-action"


def _require(condition: bool, code: str) -> None:
    if not condition:
        fail(EXIT_MISMATCH, code)


def _body(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("ascii")


def _http(body: bytes) -> bytes:
    return (b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\n"
            b"Content-Length: " + str(len(body)).encode("ascii")
            + b"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
            b"Connection: close\r\n\r\n" + body)


def _request(route: str, decision: str | None = None, action: str | None = None) -> bytes:
    # Independent literal oracle: never call a production request builder here.
    result = (("GET " if decision is None else "POST ") + route
              + " HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer ").encode("ascii")
    result += _CREDENTIAL + b"\r\n"
    if decision is not None:
        result += ("X-Sts2-Decision-Id: " + decision + "\r\nX-Sts2-Action-Id: "
                   + str(action) + "\r\n").encode("ascii")
    return result + b"Accept: application/json\r\nConnection: close\r\n\r\n"


def _ready(index: int = 0, *, gold: bool = False) -> bytes:
    value = factory._parent(_IDS[index], index, gold=99 + 14 * index)
    value["rewards"] = value["rewards"][:1] if gold else []
    value["legal_actions"] = ([value["legal_actions"][0]] if gold else []) + [value["legal_actions"][-1]]
    return _http(_body(value))


def _complete() -> bytes:
    return _http(_body({
        "schema_version": 1, "status": "complete", "decision_kind": "reward",
        "actionable": False, "decision_id": None, "screen_kind": "map",
        "player": factory._player(), "rewards": [], "legal_actions": [],
    }))


def _receipt_body(index: int = 0, action: str = "proceed", **changes: object) -> bytes:
    value = {"schema_version": 1, "status": "accepted", "mutation_state": "applied",
             "decision_id": _IDS[index], "action_id": action, "reason": "accepted"}
    value.update(changes)
    return _body(value)


def _known_http(kind: str) -> bytes:
    if kind == "429":
        return probe._RATE_LIMITED_HEADER + probe._RATE_LIMITED_BODY_PREFIX + _SOURCE + probe._RATE_LIMITED_BODY_SUFFIX
    if kind == "503":
        return probe._RETRYABLE_BACKEND_HEADER + probe._RETRYABLE_BACKEND_BODY_PREFIX + _SOURCE + probe._RETRYABLE_BACKEND_BODY_SUFFIX
    return probe._BACKEND_FAULT_HEADER + probe._BACKEND_FAULT_BODY_PREFIX + _SOURCE + probe._BACKEND_FAULT_BODY_SUFFIX


@dataclass
class Exchange:
    request: bytes
    response: bytes
    connect_error: BaseException | None = None
    send_error: BaseException | None = None
    recv_error: BaseException | None = None
    close_error: BaseException | None = None
    expire: bool = False


def _base(*, gold: bool = False) -> list[Exchange]:
    return [
        Exchange(_request("/probe/v0/health"), _http(
            b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"' + _SOURCE + b'"}')),
        Exchange(_request("/probe/v0/manifest"), _http(probe._MANIFEST_COMPATIBLE)),
        Exchange(_request(_GET_REWARD), _ready(gold=gold)),
    ]


def _one(response: bytes | None = None, *, after: bytes | None = None,
         **fault: object) -> list[Exchange]:
    result = _base() + [Exchange(_request(_POST_REWARD, _IDS[0], "proceed"),
                                _http(_receipt_body()) if response is None else response, **fault)]
    if after is not None:
        result.append(Exchange(_request(_GET_REWARD), after))
    return result


class Transcript:
    def __init__(self, exchanges: list[Exchange], leak: tuple[str, str] | None = None) -> None:
        self.exchanges, self.leak = exchanges, leak
        self.credential = bytearray(_CREDENTIAL)
        self.sockets: list[Socket] = []
        self.response_buffers: list[bytearray] = []
        self.response_canaries: set[int] = set()
        self.connects = 0
        self.posts = 0
        self.now = 100.0
        self.receiving = False
        self.first_receive = True
        self.leak_count = 0
        self.errors: list[str] = []

    def check(self, condition: bool, code: str) -> None:
        if not condition:
            # Keep fixture assertions outside the CLI's ordinary-error sanitizer.
            self.errors.append(code)
            fail(EXIT_MISMATCH, code)

    def connect(self) -> "Socket":
        self.receiving = False
        self.check(self.connects < len(self.exchanges), "diagnostic_extra_exchange")
        exchange = self.exchanges[self.connects]
        self.connects += 1
        if exchange.connect_error is not None:
            raise exchange.connect_error
        socket = Socket(self, exchange)
        self.sockets.append(socket)
        return socket


class Socket:
    def __init__(self, transcript: Transcript, exchange: Exchange) -> None:
        self.transcript, self.exchange = transcript, exchange
        self.offset = 0
        self.receives = 0
        self.request: bytearray | None = None
        self.closed = False

    def settimeout(self, value: float) -> None:
        self.transcript.check(0 < value <= 1.0, "diagnostic_timeout_bound")

    def sendall(self, request: bytearray) -> None:
        self.request = request
        self.transcript.check(request == self.exchange.request, "diagnostic_exact_request")
        self.transcript.posts += request.startswith(b"POST ")
        if self.exchange.send_error is not None:
            raise self.exchange.send_error

    def shutdown(self, how: int) -> None:
        self.transcript.check(how == socket.SHUT_WR and self.request is not None, "diagnostic_write_shutdown")

    def recv(self, maximum: int) -> bytes:
        owner = self.transcript
        owner.check(maximum == 1024, "diagnostic_receive_bound")
        if owner.first_receive:
            owner.first_receive = False
            if owner.leak is not None:
                source, stream = owner.leak
                if source == "credential":
                    owner.check(self.request is not None and _CREDENTIAL in self.request, "diagnostic_credential_injection")
                    value = _CREDENTIAL
                else:
                    owner.check(_SOURCE in self.exchange.response, "diagnostic_source_injection")
                    value = _SOURCE
                print(value.decode("ascii"), file=sys.stdout if stream == "stdout" else sys.stderr)
                owner.leak_count += 1
        if self.receives and self.exchange.recv_error is not None:
            raise self.exchange.recv_error
        chunk = self.exchange.response[self.offset:self.offset + maximum]
        self.offset += len(chunk)
        self.receives += 1
        owner.receiving = bool(chunk)
        if self.exchange.expire and chunk:
            owner.now += 4.0
        return chunk

    def close(self) -> None:
        self.closed = True
        if self.exchange.close_error is not None:
            raise self.exchange.close_error


def _privacy_gate(stdout: str, stderr: str) -> dict[str, object]:
    forbidden = (_CREDENTIAL.decode("ascii"), _SOURCE.decode("ascii"), _ERROR,
                 "/synthetic-profile", "claim:0", *_IDS)
    _require(not any(value in stdout or value in stderr for value in forbidden), _PRIVACY)
    _require(stderr == "", "diagnostic_unexpected_stderr")
    # A missing canary guard must NOT pass the leak mutation through JSON failure.
    try:
        payload = json.loads(stdout)
    except (ValueError, TypeError):
        fail(EXIT_MISMATCH, "diagnostic_invalid_output_json")
    _require(type(payload) is dict and set(payload) == {
        "schema_version", "status", "code", "action_category", "failure_stage",
        "classification", "attempted", "accepted", "reconciled", "receipt",
    }, "diagnostic_output_shape")
    _require(type(payload["schema_version"]) is int and payload["schema_version"] == 1,
             "diagnostic_output_version")
    _require(payload["status"] in ("passed", "failed")
             and payload["action_category"] in ("none", "claim_gold", "collect_item", "discard_potion", "claim_special_card", "open_card", "choose_card", "skip_card", "proceed"),
             "diagnostic_output_enum")
    _require(payload["code"] in {
        "none", "failure", "interrupted", "internal_failure", "invalid_invocation",
        "invalid_decision_provider", "unsafe_identity", "reward_action_response_mismatch",
        "reward_action_response_too_large", "reward_action_empty_response",
        "reward_action_transport_failure", "reward_action_transport_timeout",
        "reward_action_transport_mismatch", "reward_response_mismatch",
        "reward_action_budget_exhausted", "special_card_claim_reconciliation_failed", "item_claim_reconciliation_failed", "potion_inventory_full", "potion_replacement_unavailable", "potion_discard_reconciliation_failed", "unresolved_reward",
    }, "diagnostic_output_code")
    stage_classes = {
        "none": {"none"}, "pre_action": {"action_not_attempted"},
        "transport": {"transport_deadline", "transport_failure", "transport_receive_mismatch",
                      "transport_empty_response", "transport_other"},
        "http_envelope": {"http_malformed_envelope", "http_response_oversize",
                          "http_429_rate_limited", "http_503_retryable_backend", "http_500_backend_fault"},
        "receipt": {"receipt_malformed", "receipt_rejected", "receipt_not_exactly_accepted"},
        "reconciliation": {"reconciliation_failed"},
        "interrupted": {"interrupted"}, "internal": {"internal_failure"},
    }
    _require(payload["failure_stage"] in stage_classes
             and payload["classification"] in stage_classes[payload["failure_stage"]],
             "diagnostic_output_stage")
    _require(all(type(payload[name]) is int for name in ("attempted", "accepted", "reconciled"))
             and 0 <= payload["reconciled"] <= payload["accepted"] <= payload["attempted"] <= 17,
             "diagnostic_output_counts")
    receipt = payload["receipt"]
    if receipt is not None:
        _require(type(receipt) is dict and set(receipt) == {
            "status", "mutation_state", "reason", "decision_binding", "action_binding",
        }, "diagnostic_output_receipt")
        _require((receipt["status"], receipt["mutation_state"], receipt["reason"]) in {
            ("accepted", "applied", "accepted"),
            *(("rejected", "none", reason) for reason in
              ("stale_decision", "invalid_action", "already_applied", "action_limit_reached")),
        } and all(receipt[name] is None or type(receipt[name]) is bool
                  for name in ("decision_binding", "action_binding")), "diagnostic_output_receipt_values")
    return payload


def _run(transcript: Transcript, *, args: list[str] | None = None,
         identity_error: ToolFailure | None = None, disable_response_wipe: bool = False,
         expected_escape: BaseException | None = None) -> tuple[int, dict[str, object]]:
    stdout, stderr = StringIO(), StringIO()
    original_zero = probe._zero
    escaped: BaseException | None = None
    exit_code = -1

    class TrackedBytearray(bytearray):
        def extend(self, value: object) -> None:
            if transcript.receiving:
                transcript.receiving = False
                if not any(self is prior for prior in transcript.response_buffers):
                    transcript.response_buffers.append(self)
            super().extend(value)
            if any(self is prior for prior in transcript.response_buffers) and _SOURCE in self:
                transcript.response_canaries.add(transcript.connects - 1)

    def zero(value: bytearray) -> None:
        if disable_response_wipe and any(value is prior for prior in transcript.response_buffers):
            return
        original_zero(value)

    with ExitStack() as stack:
        # All live hooks are replaced before ANY invocation, including invalid CLI.
        stack.enter_context(patch.object(sys, "argv", ["diagnose_reward_live.py", *(_ARGS if args is None else args)]))
        identity = stack.enter_context(patch.object(probe, "_require_identity", return_value=501, side_effect=identity_error))
        loader = stack.enter_context(patch.object(probe, "_load_fixed_credential", return_value=transcript.credential))
        connector = stack.enter_context(patch.object(probe, "_literal_loopback_connector", side_effect=transcript.connect))
        stack.enter_context(patch.object(probe, "bytearray", TrackedBytearray, create=True))
        stack.enter_context(patch.object(probe, "_zero", side_effect=zero))
        stack.enter_context(patch.object(probe.time, "monotonic", side_effect=lambda: transcript.now))
        stack.enter_context(patch.object(probe.time, "sleep", side_effect=lambda duration: setattr(transcript, "now", transcript.now + duration)))
        stack.enter_context(redirect_stdout(stdout))
        stack.enter_context(redirect_stderr(stderr))
        try:
            exit_code = diagnose.main()
        except BaseException as error:
            escaped = error
        finally:
            if loader.called:
                _require(not any(transcript.credential), "diagnostic_credential_not_zeroed")
        if not transcript.exchanges:
            _require(not loader.called and not connector.called, "diagnostic_no_io")
            if args is not None:
                _require(not identity.called, "diagnostic_invalid_cli_identity")
    _require(not transcript.errors, transcript.errors[0] if transcript.errors else "diagnostic_fixture_error")
    _require(transcript.connects == len(transcript.exchanges), "diagnostic_exchange_transcript_not_exhausted")
    _require(all(socket.closed for socket in transcript.sockets), "diagnostic_socket_not_closed")
    _require(all(socket.request is not None and not any(socket.request) for socket in transcript.sockets),
             "diagnostic_request_not_zeroed")
    expected_posts = sum(exchange.request.startswith(b"POST ") and exchange.connect_error is None
                         for exchange in transcript.exchanges)
    _require(transcript.posts == expected_posts, "diagnostic_post_count")
    _require(all(not any(value) for value in transcript.response_buffers), _WIPING)
    for index, exchange in enumerate(transcript.exchanges):
        if exchange.recv_error is not None and _SOURCE in exchange.response:
            _require(index in transcript.response_canaries, "diagnostic_partial_canary_not_received")
    if expected_escape is not None:
        _require(escaped is expected_escape and stdout.getvalue() == stderr.getvalue() == "",
                 "diagnostic_exception_propagation")
        return exit_code, {}
    if escaped is not None:
        raise escaped
    return exit_code, _privacy_gate(stdout.getvalue(), stderr.getvalue())


def _check(exchanges: list[Exchange], *, counts: tuple[int, int, int] = (1, 0, 0),
           stage: str = "receipt", classification: str = "receipt_malformed",
           code: str = "reward_action_response_mismatch", exit_code: int = 4,
           receipt: dict[str, object] | None = None, action: str = "proceed") -> None:
    result_code, payload = _run(Transcript(exchanges))
    _require(result_code == exit_code and payload == {
        "schema_version": 1, "status": "passed" if exit_code == 0 else "failed",
        "code": code, "action_category": action, "failure_stage": stage,
        "classification": classification, "attempted": counts[0], "accepted": counts[1],
        "reconciled": counts[2], "receipt": receipt,
    }, "diagnostic_expected_result")


def _receipt_facts(reason: str = "accepted", decision: bool | None = True,
                   action: bool | None = True) -> dict[str, object]:
    return {"status": "accepted" if reason == "accepted" else "rejected",
            "mutation_state": "applied" if reason == "accepted" else "none",
            "reason": reason, "decision_binding": decision, "action_binding": action}


def _gold_chain(actions: int) -> list[Exchange]:
    result = _base(gold=True)
    for index in range(actions):
        result += [
            Exchange(_request(_POST_REWARD, _IDS[index], "claim:0"),
                     _http(_receipt_body(index, "claim:0"))),
            Exchange(_request(_GET_REWARD), _ready(index + 1, gold=True)),
        ]
    return result


def _must_fail_at(operation: object, code: str) -> None:
    try:
        operation()
    except ToolFailure as failure:
        _require(failure.exit_code == 4 and failure.error_code == code, "diagnostic_mutant_wrong_failure")
    else:
        fail(EXIT_MISMATCH, "diagnostic_mutant_survived")


def operation() -> dict[str, object]:
    checks: list[str] = []
    _check(_one(after=_complete()), counts=(1, 1, 1), stage="none", classification="none",
           code="none", exit_code=0, receipt=_receipt_facts())
    checks.append("exact_success_request_receipt_and_mutable_cleanup")
    special = factory._parent(_IDS[0], 0)
    special["schema_version"] = 2
    special["rewards"] = [{"reward_slot": 0, "reward_index": 4, "kind": "special_card",
        "successfully_selected": False, "gold_amount": None, "cards": ["LANTERN_KEY"], "card_selection_can_skip": False}]
    special["legal_actions"] = [{"action_id": "take:0", "kind": "claim_special_card", "reward_slot": 0, "card_slot": None}, special["legal_actions"][-1]]
    exchanges = _base()
    exchanges[-1] = Exchange(_request(_GET_REWARD), _http(_body(special)))
    exchanges.append(Exchange(_request(_POST_REWARD, _IDS[0], "take:0"), _known_http("429")))
    _check(exchanges, stage="http_envelope", classification="http_429_rate_limited", action="claim_special_card")
    after = json.loads(_body(special))
    after["decision_id"] = _IDS[1]
    after["decision_revision"] = 1
    after["rewards"][0]["successfully_selected"] = True
    after["legal_actions"] = [after["legal_actions"][-1]]
    # Native acceptance without the expected deck increment must retain both
    # receipt bindings and the specific reconciliation failure.
    _check(exchanges[:-1] + [Exchange(_request(_POST_REWARD, _IDS[0], "take:0"), _http(_receipt_body(0, "take:0"))),
        Exchange(_request(_GET_REWARD), _http(_body(after)))], counts=(1,1,0), stage="reconciliation",
        classification="reconciliation_failed", code="special_card_claim_reconciliation_failed",
        receipt=_receipt_facts(), action="claim_special_card")
    checks.append("special_card_action_diagnostics")
    item = factory._parent(_IDS[0], 0)
    item["schema_version"] = 3
    item["rewards"] = [{"reward_slot": 0, "reward_index": 0, "kind": "potion",
        "successfully_selected": False, "gold_amount": None, "cards": [], "card_selection_can_skip": False, "item_key": "POTION"}]
    item["legal_actions"] = [{"action_id": "collect:0", "kind": "collect_item", "reward_slot": 0, "card_slot": None}, item["legal_actions"][-1]]
    exchanges = _base()
    exchanges[-1] = Exchange(_request(_GET_REWARD), _http(_body(item)))
    _check(exchanges + [Exchange(_request(_POST_REWARD, _IDS[0], "collect:0"), _known_http("429"))],
        stage="http_envelope", classification="http_429_rate_limited", action="collect_item")
    after = json.loads(_body(item))
    after["decision_id"] = _IDS[1]
    after["decision_revision"] = 1
    after["rewards"][0]["successfully_selected"] = True
    after["rewards"][0]["item_key"] = "OTHER"
    after["legal_actions"] = [after["legal_actions"][-1]]
    _check(exchanges + [Exchange(_request(_POST_REWARD, _IDS[0], "collect:0"), _http(_receipt_body(0, "collect:0"))),
        Exchange(_request(_GET_REWARD), _http(_body(after)))], counts=(1,1,0), stage="reconciliation",
        classification="reconciliation_failed", code="item_claim_reconciliation_failed",
        receipt=_receipt_facts(), action="collect_item")
    full = json.loads(_body(item))
    full["legal_actions"] = full["legal_actions"][-1:]
    _check(exchanges[:-1] + [Exchange(_request(_GET_REWARD), _http(_body(full)))],
        counts=(0,0,0), stage="pre_action", classification="action_not_attempted", code="potion_inventory_full", action="none")
    checks.append("item_action_diagnostics")
    for reason in ("stale_decision", "invalid_action", "already_applied", "action_limit_reached"):
        _check(_one(_http(_receipt_body(status="rejected", mutation_state="none", reason=reason))),
               classification="receipt_rejected", receipt=_receipt_facts(reason))
        checks.append("canonical_" + reason)
    for changes, facts in (
        ({"decision_id": _IDS[1]}, _receipt_facts(decision=False)),
        ({"action_id": "claim:0"}, _receipt_facts(action=False)),
        ({"decision_id": "malformed", "action_id": 12}, _receipt_facts(decision=None, action=None)),
        ({"decision_id": None, "action_id": None}, _receipt_facts(decision=None, action=None)),
    ):
        _check(_one(_http(_receipt_body(**changes))),
               classification="receipt_not_exactly_accepted", receipt=facts)
    checks.append("wrong_and_unknown_bindings")
    valid = _receipt_body()
    malformed = [
        _receipt_body(schema_version=True), _receipt_body(schema_version=1.0),
        valid.replace(b'{"schema_version":1,', b'{"schema_version":1,"schema_version":1,'),
        valid[:-1] + b',"extra":true}', b" " + valid,
        _body(dict(reversed(list(json.loads(valid).items())))),
        b"[" * 1500 + b"0" + b"]" * 1500, b"{}", b"not-json",
        _receipt_body(mutation_state="queued"),
    ]
    for body in malformed:
        _check(_one(_http(body)))
    checks.append("ten_strict_malformed_receipts")
    for kind, category in (("429", "http_429_rate_limited"),
                           ("503", "http_503_retryable_backend"), ("500", "http_500_backend_fault")):
        _check(_one(_known_http(kind)), stage="http_envelope", classification=category)
    checks.append("exact_429_503_500_no_retry")
    for response in (b"HTTP/1.1 200 nope\r\n\r\n{}", _http(valid).replace(b"Content-Length:", b"content-length:"),
                     _http(valid).replace(str(len(valid)).encode("ascii"), b"999", 1),
                     b"HTTP/1.1 200 OK\r\n"):
        _check(_one(response), stage="http_envelope", classification="http_malformed_envelope")
    for response in (_http(b"x" * 4097), b"x" * 8193):
        _check(_one(response), stage="http_envelope", classification="http_response_oversize",
               code="reward_action_response_too_large")
    _check(_one(b""), stage="transport", classification="transport_empty_response",
           code="reward_action_empty_response")
    checks.append("malformed_partial_length_empty_oversize_http")

    partial = b"HTTP/1.1 200 " + _SOURCE + b"\r\n"
    for fault in ({"connect_error": OSError(_ERROR)}, {"send_error": OSError(_ERROR)},
                  {"recv_error": OSError(_ERROR)}, {"recv_error": TimeoutError(_ERROR)}):
        _check(_one(partial, **fault), stage="transport", classification="transport_failure",
               code="reward_action_transport_failure")
    _check(_one(partial, expire=True), stage="transport", classification="transport_deadline",
           code="reward_action_transport_timeout")
    _check(_one(partial, recv_error=ToolFailure(4, "reward_action_transport_mismatch")),
           stage="transport", classification="transport_receive_mismatch", code="reward_action_transport_mismatch")
    for exchanges in (_one(partial, recv_error=KeyboardInterrupt()),
                      _one(close_error=KeyboardInterrupt())):
        _check(exchanges, stage="interrupted", classification="interrupted",
               code="interrupted", exit_code=5)
    for exchanges in (_one(partial, recv_error=RuntimeError(_ERROR)),
                      _one(close_error=RuntimeError(_ERROR)),
                      _one(partial, recv_error=OSError(_ERROR), close_error=RuntimeError(_ERROR))):
        _check(exchanges, stage="internal", classification="internal_failure",
               code="internal_failure", exit_code=5)
    for location in ("recv_error", "close_error"):
        error = SystemExit(37)
        _run(Transcript(_one(partial, **{location: error})), expected_escape=error)
    _check(_one(after=_complete(), close_error=OSError(_ERROR)), counts=(1, 1, 1),
           stage="none", classification="none", code="none", exit_code=0, receipt=_receipt_facts())
    checks.append("transport_deadline_partial_exception_cancellation_close_cleanup")

    first = _gold_chain(1)
    _check(first + [Exchange(_request(_POST_REWARD, _IDS[1], "claim:0"), _known_http("429"))],
           counts=(2, 1, 1), stage="http_envelope", classification="http_429_rate_limited",
           action="claim_gold")
    _check(first + [
        Exchange(_request(_POST_REWARD, _IDS[1], "claim:0"), _http(_receipt_body(1, "claim:0"))),
        Exchange(_request(_GET_REWARD), _http(b"{}")),
    ], counts=(2, 2, 1), stage="reconciliation", classification="reconciliation_failed",
        code="reward_response_mismatch", receipt=_receipt_facts(), action="claim_gold")
    _check(_gold_chain(17), counts=(17, 17, 17), stage="pre_action",
           classification="action_not_attempted", code="reward_action_budget_exhausted", action="none")
    checks.append("actual_multi_action_prefixes_and_17_cap")

    for args in ([], _ARGS + ["--capture", "/synthetic-profile"],
                 [*_ARGS[:-1], "invalid"]):
        result_code, payload = _run(Transcript([]), args=args)
        _require(result_code == 2 and payload["attempted"] == payload["accepted"] == payload["reconciled"] == 0
                 and payload["failure_stage"] == "pre_action", "diagnostic_invalid_cli")
    result_code, payload = _run(Transcript([]), identity_error=ToolFailure(3, "unsafe_identity"))
    _require(result_code == 3 and payload["code"] == "unsafe_identity"
             and payload["attempted"] == payload["accepted"] == payload["reconciled"] == 0,
             "diagnostic_unsafe_identity_exit")
    result_code, payload = _run(Transcript([]), identity_error=ToolFailure(3, _ERROR))
    _require(result_code == 3 and payload["code"] == "failure", "diagnostic_unknown_error_redaction")
    checks.append("no_io_invalid_cli_and_unsafe_identity")
    for source in ("credential", "source"):
        for stream in ("stdout", "stderr"):
            transcript = Transcript(_one(after=_complete()), (source, stream))
            _must_fail_at(lambda: _run(transcript), _PRIVACY)
            _require(transcript.leak_count == 1, "diagnostic_leak_not_exercised")
    checks.append("four_first_receive_privacy_gate_mutations")
    original_require = _require

    def bypass_canary_guard(condition: bool, code: str) -> None:
        if code != _PRIVACY:
            original_require(condition, code)

    # Removing just the canary assertion must make the leak test itself fail,
    # rather than allowing JSON parsing or stderr validation to stand in for it.
    with patch.object(sys.modules[__name__], "_require", side_effect=bypass_canary_guard):
        _must_fail_at(
            lambda: _must_fail_at(
                lambda: _run(Transcript(_one(after=_complete()), ("credential", "stdout"))),
                _PRIVACY,
            ),
            "diagnostic_mutant_wrong_failure",
        )
    checks.append("disabled_privacy_guard_mutant_rejected")
    _must_fail_at(lambda: _run(Transcript(_one(partial, recv_error=KeyboardInterrupt())),
                              disable_response_wipe=True), _WIPING)
    checks.append("disabled_http_response_wipe_mutant_rejected")
    with patch.object(probe, "_build_action_request",
                      side_effect=lambda route, credential, decision, action: probe._build_request(_GET_REWARD, credential)):
        _must_fail_at(lambda: _run(Transcript(_one())), "diagnostic_exact_request")
    checks.append("post_replaced_by_get_mutant_rejected")
    return {"schema_version": 1, "status": "passed", "suite": "reward_action_diagnostics_fixtures",
            "checks": checks, "check_count": len(checks)}


if __name__ == "__main__":
    main(operation)
