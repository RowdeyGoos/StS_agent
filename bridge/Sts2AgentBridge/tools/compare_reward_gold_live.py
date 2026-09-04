#!/usr/bin/env python3
"""One transient, bounded gold-claim comparison through the R0i reward client.

This tool deliberately keeps every wire body, control binding, receipt, and
credential in memory.  It has no capture or retention mode.  The canonical
evaluator proposal remains in memory; the returned value is a smaller fixed
allowlist that cannot expose observed player, reward, selection, or boundary
scalars.

Requires Python 3.10+ (the repository-supported interpreter floor).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import time
from typing import Any, Callable

sys.dont_write_bytecode = True

# Direct script execution starts in ``tools``.  The evaluator is a project
# package, so make this explicit instead of depending on an editable install.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import apply_reward_live as reward
import probe_live as probe
from game.analysis import reward_gold_conformance as gold
from game.backends.live import r0i_wire as wire
from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    ToolFailure,
    absolute_path,
    fail,
    main,
)


_DEADLINE_SECONDS = 10.0
_POLL_SECONDS = 0.1
_HARNESS_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
_OUTPUT_SCHEMA = "transient_reward_gold_check_v1"
_ARTIFACT_PIN_KEYS = (
    "harness_sha256",
    "case_spec_sha256",
    "schema_sha256",
    "build_identity_sha256",
    "build_manifest_sha256",
    "bridge_source_sha256",
    "parser_source_sha256",
    "wire_vectors_sha256",
    "headless_contract_sha256",
    "rules_sha256",
    "rules_source_sha256",
    "content_sha256",
)


def parse_args(arguments: list[str] | None = None) -> tuple[str, int]:
    """Parse the sole explicit transient-check invocation form.

    There is intentionally no capture, output-path, provider, or repeat flag.
    """
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 5 or values[0] != "--transient-check":
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    names = ("--user-profile", "--effective-uid")
    parsed: dict[str, str] = {}
    for offset in range(1, len(values), 2):
        name = values[offset]
        if name not in names or name in parsed:
            fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
        parsed[name] = values[offset + 1]
    if set(parsed) != set(names):
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    return parsed["--user-profile"], probe._parse_effective_uid(parsed["--effective-uid"])


def _read(
    label: str,
    route: str,
    credential: bytearray,
    connector: Callable[[], Any],
    deadline: float,
    decision_id: str | None = None,
    action_id: str | None = None,
) -> bytes:
    """Reuse the reward client's bounded transport and zeroing discipline."""
    return reward._read_body(label, route, credential, connector, deadline, decision_id, action_id)


def _reward_decision(body: bytes) -> wire.RewardDecision:
    """Require both the accepted wire DTO and current reward-client checks."""
    try:
        decision = wire.parse_decision(body)
    except (ValueError, TypeError, KeyError, AttributeError):
        fail(EXIT_MISMATCH, "gold_wire_decision_mismatch")
    if type(decision) is not wire.RewardDecision:
        fail(EXIT_MISMATCH, "gold_wire_decision_mismatch")
    if decision.status == "ready":
        # This existing client check additionally enforces the client's strict
        # reward/action shape, bounds, ordering, and advertised-target rules.
        reward._validate_ready(body)
    return decision


def _receipt(body: bytes, binding: wire.BridgeBinding, action_id: str) -> wire.ActionReceipt:
    """Parse and bind one exact accepted reward receipt in memory."""
    try:
        receipt = wire.parse_receipt(body, family="reward", binding=binding)
    except (ValueError, TypeError, KeyError, AttributeError):
        fail(EXIT_MISMATCH, "gold_wire_receipt_mismatch")
    if receipt.action_id != action_id or receipt.status != "accepted" or receipt.mutation_state != "applied":
        fail(EXIT_MISMATCH, "gold_claim_not_accepted")
    # Keep the existing client response binding check as an independent route
    # grammar check; no receipt leaves this function.
    reward._validate_action_response(body, binding.decision_id, action_id)
    return receipt


def _claim_action(pre: wire.RewardDecision) -> str | None:
    actions = [item["action_id"] for item in pre.fields["legal_actions"] if item["kind"] == "claim_gold"]
    if len(actions) != 1 or type(actions[0]) is not str:
        return None
    return actions[0]


def _post_preserves_unrelated_reward_data(pre: wire.RewardDecision, post: wire.RewardDecision,
                                          selected_action_id: str) -> bool:
    """Reject an observation that changes unrelated rewards or candidates.

    This is intentionally a correspondence guard, not a replacement reward
    rule: player scalars are left untouched for the canonical evaluator to
    mark passed or divergent.  The selected reward and its claim candidate are
    the only allowed changes.
    """
    if post.status != "ready" or post.fields["screen_kind"] != "rewards":
        return False
    if post.fields["decision_revision"] != pre.fields["decision_revision"] + 1:
        return False
    selected = next((item for item in pre.fields["legal_actions"] if item["action_id"] == selected_action_id), None)
    if selected is None or selected["kind"] != "claim_gold":
        return False
    slot = selected["reward_slot"]
    before_rewards = list(pre.fields["rewards"])
    after_rewards = list(post.fields["rewards"])
    if type(slot) is not int or not 0 <= slot < len(before_rewards):
        return False
    # The reviewed bridge reader republishes the parent list and suppresses
    # only the selected reward's action.  Do not guess about a UI-removal or
    # reindex variant: such a post remains unobserved until that exact bridge
    # shape is independently reviewed.
    if len(after_rewards) != len(before_rewards):
        return False
    for index, item in enumerate(before_rewards):
        observed = after_rewards[index]
        if index == slot:
            expected = dict(item)
            expected["successfully_selected"] = True
            if observed != expected:
                return False
        elif observed != item:
            return False
    before_other = [item for item in pre.fields["legal_actions"] if item["action_id"] != selected_action_id]
    if list(post.fields["legal_actions"]) != before_other:
        return False
    return True


def _cancelled(cancel: Callable[[], bool]) -> bool:
    value = cancel()
    if type(value) is not bool:
        fail(EXIT_INTERNAL, "invalid_cancellation_callback")
    return value


def _public_result(proposal: dict[str, Any]) -> dict[str, Any]:
    """Project an in-memory named record to the transient output allowlist.

    This is intentionally not a serializable named-conformance record.  In
    particular, it excludes boundaries, selection, capture ordinal, source,
    broader findings, and every observed scalar.  The artifact pins describe
    fixed reviewed code/spec identities rather than transport data.
    """
    pins = proposal["pins"]
    return {
        "schema": _OUTPUT_SCHEMA,
        "case_id": proposal["case_id"],
        "artifact": {key: pins[key] for key in _ARTIFACT_PIN_KEYS},
        "eligibility": dict(proposal["alignment"]),
        "correspondence": proposal["correspondence"],
        "verdicts": [
            {"field": finding["field"], "outcome": finding["outcome"], "code": finding["code"]}
            for finding in proposal["findings"]
        ],
        "omissions": list(proposal["omissions"]),
        "admission": "not_admitted",
    }


def _evaluate_transient(**kwargs: Any) -> dict[str, Any]:
    """Keep the full evaluator record local and return only its safe summary."""
    return _public_result(gold.evaluate_reward_gold(**kwargs))


def _read_ready_post(
    credential: bytearray,
    connector: Callable[[], Any],
    deadline: float,
    cancel: Callable[[], bool],
    pre_binding: wire.BridgeBinding,
) -> tuple[wire.RewardDecision | None, wire.RewardDecision | None, bool]:
    """Read an initial post-state then one stable confirming read, once each."""
    while time.monotonic() < deadline:
        if _cancelled(cancel):
            return None, None, True
        body = _read("reward", probe._REWARD_ROUTE[0][1], credential, connector, deadline)
        decision = _reward_decision(body)
        if decision.status == "waiting":
            time.sleep(_POLL_SECONDS)
            continue
        if decision.status != "ready":
            return decision, None, False
        if decision.binding == pre_binding:
            # A repeated pre-state is not a postcondition.  Keep the one
            # bounded observation window open for a fresh reward boundary.
            time.sleep(_POLL_SECONDS)
            continue
        if _cancelled(cancel):
            return None, None, True
        stable_body = _read("reward", probe._REWARD_ROUTE[0][1], credential, connector, deadline)
        stable = _reward_decision(stable_body)
        return decision, stable, False
    return None, None, False


def run_transient_gold_comparison(
    credential: bytearray,
    connector: Callable[[], Any],
    *,
    cancelled: Callable[[], bool] = lambda: False,
    harness_sha256: str = _HARNESS_SHA256,
) -> dict[str, Any]:
    """Perform at most one eligible claim and return a fixed safe summary.

    A caller must supply the existing bounded connector and credential.  The
    function never retries a POST.  It may make bounded GETs only to discover a
    ready pre-state and to obtain one fresh plus one stable post-state.
    """
    deadline = time.monotonic() + _DEADLINE_SECONDS
    pre: wire.RewardDecision | None = None
    post: wire.RewardDecision | None = None
    receipt: wire.ActionReceipt | None = None
    action_id: str | None = None
    window = gold.ClaimWindow()
    try:
        if _cancelled(cancelled):
            return _evaluate_transient(pre=None, selected_action_id=None, receipt=None, post=None,
                                       harness_sha256=harness_sha256,
                                       window=gold.ClaimWindow(cancelled=True), origin="transient_live")
        # These reuse the existing authenticated HTTP client and do not expose
        # their values in the proposal.
        health = _read("health", probe._BASE_ROUTES[0][1], credential, connector, deadline)
        with memoryview(health) as body:
            probe._validate_health(body)
        manifest = _read("manifest", probe._BASE_ROUTES[1][1], credential, connector, deadline)
        with memoryview(manifest) as body:
            probe._validate_manifest(body)

        pre_body = _read("reward", probe._REWARD_ROUTE[0][1], credential, connector, deadline)
        pre = _reward_decision(pre_body)
        if pre.status != "ready" or pre.binding is None:
            return _evaluate_transient(pre=pre, selected_action_id=None, receipt=None, post=None,
                                       harness_sha256=harness_sha256, window=window, origin="transient_live")
        action_id = _claim_action(pre)
        eligibility = gold.reward_gold_eligibility(pre, action_id)
        if action_id is None or eligibility["alignment"]["status"] != "eligible" or _cancelled(cancelled):
            cancelled_window = gold.ClaimWindow(cancelled=True) if _cancelled(cancelled) else window
            return _evaluate_transient(pre=pre, selected_action_id=action_id, receipt=None, post=None,
                                       harness_sha256=harness_sha256, window=cancelled_window,
                                       origin="transient_live")

        receipt_body = _read("reward_action", probe._REWARD_ACTION_ROUTE, credential, connector, deadline,
                             pre.binding.decision_id, action_id)
        receipt = _receipt(receipt_body, pre.binding, action_id)
        post_candidate, stable_candidate, was_cancelled = _read_ready_post(
            credential, connector, deadline, cancelled, pre.binding)
        if was_cancelled:
            window = gold.ClaimWindow(pre.binding, None, 1, False, False, False, False, True)
        elif _cancelled(cancelled):
            # Cancellation remains authoritative through the final stable read;
            # do not certify a bound claim after the caller has withdrawn it.
            window = gold.ClaimWindow(pre.binding, None, 1, False, False, False, False, True)
        elif (post_candidate is not None and stable_candidate is not None
              and post_candidate == stable_candidate
              and _post_preserves_unrelated_reward_data(pre, post_candidate, action_id)):
            post = post_candidate
            # This assertion is grounded in this adapter's one-POST timeline,
            # receipt binding, revision step, strict transition validation, and
            # a second identical post read.  The evaluator still treats the
            # assertion—not stable reads alone—as its causality input.
            window = gold.ClaimWindow(pre.binding, post.binding, 1, True, True, True, False, False)
        else:
            post = post_candidate
            window = gold.ClaimWindow(pre.binding, None if post is None else post.binding, 1,
                                      post is not None, False, False, True, False)
        return _evaluate_transient(pre=pre, selected_action_id=action_id, receipt=receipt, post=post,
                                   harness_sha256=harness_sha256, window=window, origin="transient_live")
    finally:
        probe._zero(credential)


def _operation() -> dict[str, Any]:
    user_profile_value, supplied_uid = parse_args()
    user_profile = absolute_path(user_profile_value, "user_profile")
    uid = probe._require_identity(user_profile, supplied_uid)
    credential = probe._load_fixed_credential(user_profile, uid)
    return run_transient_gold_comparison(credential, probe._literal_loopback_connector)


def operation() -> dict[str, Any]:
    try:
        return _operation()
    except ToolFailure:
        raise
    except Exception:
        fail(EXIT_INTERNAL, "internal_failure")


if __name__ == "__main__":
    main(operation)
