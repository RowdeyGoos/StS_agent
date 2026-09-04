#!/usr/bin/env python3
"""Fully mocked acceptance checks for the transient gold-comparison adapter."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

sys.dont_write_bytecode = True

import compare_reward_gold_live as adapter
import probe_live as probe
from game.analysis import conformance_evidence as evidence
from tool_common import EXIT_INVALID_INVOCATION, EXIT_MISMATCH, ToolFailure, fail, main, run_cli


_PRE_ID, _POST_ID = "a" * 64, "b" * 64
_SECRET = "SECRET_CREDENTIAL_CANARY"


def _body(value: dict) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("ascii")


def _http(body: bytes) -> bytes:
    return (b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: "
            + str(len(body)).encode("ascii")
            + b"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n" + body)


def _health() -> bytes:
    return _http(b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"' + b"0" * 32 + b'"}')


def _manifest() -> bytes:
    return _http(probe._MANIFEST_COMPATIBLE)


def _decision(identity: str, revision: int, *, selected: bool = False, hp: int = 47,
              gold: int = 19, deck_count: int = 7, amount: int = 25,
              duplicate_gold: bool = False, extra_change: bool = False,
              extra_claimed_gold: bool = False, card_name: str = "CARD") -> bytes:
    rewards = [
        {"reward_slot": 0, "reward_index": 3, "kind": "gold", "successfully_selected": selected,
         "gold_amount": amount, "cards": [], "card_selection_can_skip": False},
        {"reward_slot": 1, "reward_index": 4, "kind": "card", "successfully_selected": False,
         "gold_amount": None, "cards": [card_name], "card_selection_can_skip": True},
    ]
    if duplicate_gold:
        rewards.append({"reward_slot": 2, "reward_index": 5, "kind": "gold", "successfully_selected": False,
                        "gold_amount": 35, "cards": [], "card_selection_can_skip": False})
    if extra_claimed_gold:
        rewards.append({"reward_slot": 2, "reward_index": 5, "kind": "gold", "successfully_selected": True,
                        "gold_amount": 35, "cards": [], "card_selection_can_skip": False})
    if extra_change:
        rewards[1]["cards"] = ["OTHER"]
    actions = ([{"action_id": "claim:0", "kind": "claim_gold", "reward_slot": 0, "card_slot": None}]
               if not selected else [])
    actions += [{"action_id": "open:1", "kind": "open_card", "reward_slot": 1, "card_slot": None},
                {"action_id": "proceed", "kind": "proceed", "reward_slot": None, "card_slot": None}]
    return _http(_body({"schema_version": 1, "status": "ready", "decision_kind": "reward", "actionable": True,
                        "decision_id": identity, "decision_revision": revision, "screen_kind": "rewards",
                        "player": {"hp": hp, "max_hp": 83, "gold": gold, "deck_count": deck_count},
                        "rewards": rewards, "legal_actions": actions}))


def _receipt() -> bytes:
    return _http(_body({"schema_version": 1, "status": "accepted", "mutation_state": "applied",
                        "decision_id": _PRE_ID, "action_id": "claim:0", "reason": "accepted"}))


class _Socket:
    def __init__(self, response: bytes, log: list[bytes]) -> None:
        self.response, self.log, self.closed = response, log, False
    def settimeout(self, value: float) -> None:
        return None
    def sendall(self, data: bytes | bytearray) -> None:
        self.log.append(bytes(data))
    def recv(self, amount: int) -> bytes:
        response, self.response = self.response[:amount], self.response[amount:]
        return response
    def close(self) -> None:
        self.closed = True


def _run(responses: list[bytes], *, cancelled: Callable[[], bool] = lambda: False) -> tuple[dict, list[bytes], list[_Socket]]:
    sent: list[bytes] = []
    sockets: list[_Socket] = []
    remaining = iter(responses)
    def connector() -> _Socket:
        socket = _Socket(next(remaining), sent)
        sockets.append(socket)
        return socket
    result = adapter.run_transient_gold_comparison(bytearray(b"a" * 64), connector, cancelled=cancelled,
                                                   harness_sha256="9" * 64)
    return result, sent, sockets


def _expect_failure(call: Callable[[], object], code: str) -> None:
    try:
        call()
    except ToolFailure as error:
        if error.exit_code == EXIT_MISMATCH and error.error_code == code:
            return
    fail(EXIT_MISMATCH, "gold_adapter_wrong_failure")


def _capture_cli(operation: Callable[[], dict]) -> tuple[int, str, str]:
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(operation)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _contains_forbidden_key(value: object, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return any(key in forbidden or _contains_forbidden_key(item, forbidden)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_key(item, forbidden) for item in value)
    return False


def operation() -> dict[str, object]:
    base = [_health(), _manifest(), _decision(_PRE_ID, 7, card_name=_SECRET), _receipt(),
            _decision(_POST_ID, 8, selected=True, gold=44, card_name=_SECRET),
            _decision(_POST_ID, 8, selected=True, gold=44, card_name=_SECRET)]
    result, sent, sockets = _run(base)
    if result["correspondence"] != "bound_one_claim" or {item["outcome"] for item in result["verdicts"]} != {"passed"}:
        fail(EXIT_MISMATCH, "gold_adapter_positive")
    if sum(request.startswith(b"POST ") for request in sent) != 1:
        fail(EXIT_MISMATCH, "gold_adapter_post_count")
    if [request.split(b" ", 2)[1] for request in sent] != [b"/probe/v0/health", b"/probe/v0/manifest", b"/probe/v0/public/reward-decision", b"/probe/v0/public/reward-action", b"/probe/v0/public/reward-decision", b"/probe/v0/public/reward-decision"]:
        fail(EXIT_MISMATCH, "gold_adapter_request_order")
    if not all(item.closed for item in sockets):
        fail(EXIT_MISMATCH, "gold_adapter_resource_closure")
    if _SECRET in evidence.canonical_json(result):
        fail(EXIT_MISMATCH, "gold_adapter_secret_output")
    if set(result) != {"schema", "case_id", "artifact", "eligibility", "correspondence", "verdicts", "omissions", "admission"}:
        fail(EXIT_MISMATCH, "gold_adapter_output_shape")
    forbidden = ("boundaries", "selection", "source", "capture_ordinal", "broader_comparison", "findings")
    if _contains_forbidden_key(result, set(forbidden)):
        fail(EXIT_MISMATCH, "gold_adapter_output_leak")
    original_operation = adapter._operation
    try:
        adapter._operation = lambda: result
        cli_exit, cli_stdout, cli_stderr = _capture_cli(adapter.operation)
    finally:
        adapter._operation = original_operation
    if cli_exit != 0 or _SECRET in cli_stdout or _SECRET in cli_stderr:
        fail(EXIT_MISMATCH, "gold_adapter_cli_secret_output")
    original_projection = adapter._public_result
    try:
        adapter._public_result = lambda proposal: {**proposal, "transport_secret": _SECRET}
        _, leaked_stdout, leaked_stderr = _capture_cli(
            lambda: _run([_health(), _manifest(), _decision(_PRE_ID, 7, card_name=_SECRET), _receipt(),
                           _decision(_POST_ID, 8, selected=True, gold=44, card_name=_SECRET),
                           _decision(_POST_ID, 8, selected=True, gold=44, card_name=_SECRET)])[0]
        )
    finally:
        adapter._public_result = original_projection
    if _SECRET not in leaked_stdout or _SECRET in leaked_stderr:
        fail(EXIT_MISMATCH, "gold_adapter_privacy_mutation_not_detected")
    error_exit, error_stdout, error_stderr = _capture_cli(
        lambda: _run([_health(), _manifest(), _http(b'{"detail":"SECRET_TRANSPORT_ERROR_CANARY"}')])[0]
    )
    if error_exit != EXIT_MISMATCH or _SECRET in error_stdout or _SECRET in error_stderr:
        fail(EXIT_MISMATCH, "gold_adapter_error_secret_output")

    delayed, delayed_sent, _ = _run([_health(), _manifest(), _decision(_PRE_ID, 7), _receipt(),
                                     _decision(_PRE_ID, 7), _decision(_POST_ID, 8, selected=True, gold=44),
                                     _decision(_POST_ID, 8, selected=True, gold=44)])
    if delayed["correspondence"] != "bound_one_claim" or sum(request.startswith(b"POST ") for request in delayed_sent) != 1:
        fail(EXIT_MISMATCH, "gold_adapter_fresh_post")

    invalid, invalid_sent, _ = _run([_health(), _manifest(), _decision(_PRE_ID, 7, amount=24)])
    if invalid["eligibility"]["status"] != "unaligned" or any(request.startswith(b"POST ") for request in invalid_sent):
        fail(EXIT_MISMATCH, "gold_adapter_ineligible_post")
    duplicate, duplicate_sent, _ = _run([_health(), _manifest(), _decision(_PRE_ID, 7, duplicate_gold=True)])
    if duplicate["eligibility"]["code"] != "ambiguous_or_absent_gold" or any(request.startswith(b"POST ") for request in duplicate_sent):
        fail(EXIT_MISMATCH, "gold_adapter_duplicate_post")

    missing, missing_sent, _ = _run([_health(), _manifest(), _decision(_PRE_ID, 7), _receipt(),
                                     _http(adapter.reward._REWARD_WAITING), _http(adapter.reward._REWARD_UNSUPPORTED)])
    if missing["correspondence"] != "post_not_observed" or sum(request.startswith(b"POST ") for request in missing_sent) != 1:
        fail(EXIT_MISMATCH, "gold_adapter_missing_post")
    uncertain, _, _ = _run([_health(), _manifest(), _decision(_PRE_ID, 7), _receipt(),
                             _decision(_POST_ID, 8, selected=True, gold=44, extra_change=True),
                             _decision(_POST_ID, 8, selected=True, gold=44, extra_change=True)])
    if uncertain["correspondence"] != "intervening_action":
        fail(EXIT_MISMATCH, "gold_adapter_unrelated_change")
    for post in (
        _decision(_POST_ID, 8, selected=True, gold=44, amount=35),
        _decision(_POST_ID, 8, selected=True, gold=44, extra_claimed_gold=True),
    ):
        rejected, _, _ = _run([_health(), _manifest(), _decision(_PRE_ID, 7), _receipt(), post, post])
        if rejected["correspondence"] == "bound_one_claim":
            fail(EXIT_MISMATCH, "gold_adapter_post_projection")

    divergent, _, _ = _run([_health(), _manifest(), _decision(_PRE_ID, 7), _receipt(),
                             _decision(_POST_ID, 8, selected=True, hp=46, gold=44),
                             _decision(_POST_ID, 8, selected=True, hp=46, gold=44)])
    if {item["field"] for item in divergent["verdicts"] if item["outcome"] == "divergent"} != {"hp_preserved"}:
        fail(EXIT_MISMATCH, "gold_adapter_divergent_scalar")

    cancel_calls = iter((False, False, True))
    cancelled, cancel_sent, cancel_sockets = _run([_health(), _manifest(), _decision(_PRE_ID, 7), _receipt()],
                                                   cancelled=lambda: next(cancel_calls, True))
    if cancelled["correspondence"] != "cancelled" or sum(request.startswith(b"POST ") for request in cancel_sent) != 1 or not all(item.closed for item in cancel_sockets):
        fail(EXIT_MISMATCH, "gold_adapter_cancellation")
    final_cancel_calls = iter((False, False, False, False, True))
    final_cancel, _, _ = _run([_health(), _manifest(), _decision(_PRE_ID, 7), _receipt(),
                               _decision(_POST_ID, 8, selected=True, gold=44),
                               _decision(_POST_ID, 8, selected=True, gold=44)],
                              cancelled=lambda: next(final_cancel_calls, True))
    if final_cancel["correspondence"] != "cancelled":
        fail(EXIT_MISMATCH, "gold_adapter_final_cancellation")
    _expect_failure(lambda: _run([_health(), _manifest(), _decision(_PRE_ID, 7), _receipt(), _http(b"{}")]), "gold_wire_decision_mismatch")
    original_deadline = adapter._DEADLINE_SECONDS
    try:
        adapter._DEADLINE_SECONDS = 0.0
        _expect_failure(lambda: _run([]), "probe_transport_timeout")
    finally:
        adapter._DEADLINE_SECONDS = original_deadline
    for arguments in ([], ["--transient-check", "--capture", "x", "--effective-uid", "1"], ["--transient-check", "--user-profile", "x", "--effective-uid", "01"]):
        try:
            adapter.parse_args(arguments)
        except ToolFailure as error:
            if error.exit_code == EXIT_INVALID_INVOCATION:
                continue
        fail(EXIT_MISMATCH, "gold_adapter_invocation")
    return {"status": "passed", "fixture": "compare_reward_gold_live", "checks": 19}


if __name__ == "__main__":
    main(operation)
