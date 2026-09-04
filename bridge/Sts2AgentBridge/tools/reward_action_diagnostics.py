"""Closed, capture-off classifications for one reward-action exchange."""
from __future__ import annotations

import json
from typing import Any


_REASONS = frozenset(("accepted", "stale_decision", "invalid_action", "already_applied", "action_limit_reached"))
_RECEIPT_KEYS = ("schema_version", "status", "mutation_state", "decision_id", "action_id", "reason")
_ACTION_KINDS = frozenset(("claim_gold", "open_card", "choose_card", "skip_card", "proceed"))
_CODES = frozenset(("none", "failure", "interrupted", "internal_failure", "invalid_invocation", "invalid_decision_provider", "invalid_effective_uid", "non_absolute_user_profile", "non_canonical_user_profile", "unsafe_identity", "credential_read_failed", "credential_shape", "health_response_mismatch", "manifest_response_mismatch", "reward_not_ready", "reward_response_mismatch", "reward_action_response_mismatch", "reward_action_budget_exhausted", "post_reward_state_timeout", "post_reward_state_unsupported", "reward_decision_not_advanced", "gold_claim_reconciliation_failed", "card_open_reconciliation_failed", "card_choice_reconciliation_failed", "card_skip_reconciliation_failed", "reward_proceed_reconciliation_failed", "reward_revision_mismatch"))
_STAGES = frozenset(("none", "pre_action", "transport", "http_envelope", "receipt", "reconciliation", "internal", "interrupted"))
_CLASSIFICATIONS = frozenset(("none", "action_not_attempted", "transport_deadline", "transport_failure", "transport_receive_mismatch", "transport_empty_response", "transport_other", "http_response_oversize", "http_malformed_envelope", "http_429_rate_limited", "http_503_retryable_backend", "http_500_backend_fault", "receipt_malformed", "receipt_rejected", "receipt_not_exactly_accepted", "reconciliation_failed", "internal_failure", "interrupted"))


class RewardActionDiagnostics:
    """Keep only the fixed, non-identifying facts needed after a failed action."""

    def __init__(self) -> None:
        self.attempted = 0
        self.accepted = 0
        self.reconciled = 0
        self.action_category = "none"
        self.failure_stage = "none"
        self.classification = "none"
        self.receipt: dict[str, object] | None = None

    def attempted_exchange(self, action_category: str) -> None:
        if action_category not in _ACTION_KINDS:
            raise ValueError("action category")
        self.action_category = action_category
        self.receipt = None
        self.failure_stage = "none"
        self.classification = "none"
        if self.attempted < 17:
            self.attempted += 1

    def transport_failure(self, error_code: str) -> None:
        classifications = {
            "probe_transport_timeout": "transport_deadline",
            "reward_action_transport_timeout": "transport_deadline",
            "reward_action_transport_failure": "transport_failure",
            "reward_action_transport_mismatch": "transport_receive_mismatch",
            "reward_action_empty_response": "transport_empty_response",
            "reward_action_response_too_large": "http_response_oversize",
        }
        self._fail("transport" if error_code in classifications and not error_code.endswith("too_large") else "http_envelope", classifications.get(error_code, "transport_other"))

    def inspect_http_response(self, response: bytes | bytearray) -> str | None:
        # These exact classifiers inspect the response while it is still in memory;
        # no correlation value or raw bytes are retained by this object.
        import probe_live as probe

        if probe._is_rate_limited_response(response):
            return "http_429_rate_limited"
        if probe._is_retryable_backend_response(response):
            return "http_503_retryable_backend"
        if probe._is_backend_fault_response(response):
            return "http_500_backend_fault"
        return None

    def http_failure(self, classification: str = "http_malformed_envelope") -> None:
        self._fail("http_envelope", classification)

    def inspect_receipt(self, body: bytes, decision_id: str, action_id: str) -> None:
        self.receipt = _parse_receipt(body, decision_id, action_id)
        if self.receipt is None:
            self._fail("receipt", "receipt_malformed")
            return
        if (
            self.receipt["status"] == "accepted"
            and self.receipt["mutation_state"] == "applied"
            and self.receipt["reason"] == "accepted"
            and self.receipt["decision_binding"] is True
            and self.receipt["action_binding"] is True
        ):
            return
        self._fail("receipt", "receipt_rejected" if self.receipt["status"] == "rejected" else "receipt_not_exactly_accepted")

    def accepted_receipt(self) -> None:
        """Record acceptance only after the production byte-exact validator passes."""
        if self.receipt is not None and self.accepted < self.attempted:
            self.accepted += 1

    def reconciled_action(self) -> None:
        if self.reconciled < self.accepted:
            self.reconciled += 1

    def reconciliation_failure(self) -> None:
        self._fail("reconciliation", "reconciliation_failed")

    def pre_action_failure(self) -> None:
        if self.failure_stage == "none":
            self.action_category = "none"
            self.receipt = None
            self._fail("pre_action", "action_not_attempted")

    def internal_failure(self) -> None:
        self._fail("internal", "internal_failure")

    def interrupted(self) -> None:
        self._fail("interrupted", "interrupted")

    def payload(self, status: str, code: str) -> dict[str, object]:
        valid_counts = all(type(value) is int for value in (self.attempted, self.accepted, self.reconciled)) and 0 <= self.reconciled <= self.accepted <= self.attempted <= 17
        attempted, accepted, reconciled = (self.attempted, self.accepted, self.reconciled) if valid_counts else (0, 0, 0)
        receipt = self.receipt if _safe_receipt(self.receipt) else None
        return {
            "schema_version": 1,
            "status": status if status in ("passed", "failed") else "failed",
            "code": code if code in _CODES else "failure",
            "action_category": self.action_category,
            "failure_stage": self.failure_stage,
            "classification": self.classification,
            "attempted": attempted,
            "accepted": accepted,
            "reconciled": reconciled,
            "receipt": receipt,
        }

    def _fail(self, stage: str, classification: str) -> None:
        if self.failure_stage == "none":
            self.failure_stage = stage if stage in _STAGES else "internal"
            self.classification = classification if classification in _CLASSIFICATIONS else "internal_failure"


def _parse_receipt(body: bytes, expected_decision: str, expected_action: str) -> dict[str, object] | None:
    try:
        root = json.loads(body.decode("ascii"), object_pairs_hook=_unique_object)
        if not isinstance(root, dict) or tuple(root) != _RECEIPT_KEYS:
            return None
        if json.dumps(root, ensure_ascii=True, separators=(",", ":")).encode("ascii") != body:
            return None
        if type(root["schema_version"]) is not int or root["schema_version"] != 1 or root["status"] not in ("accepted", "rejected"):
            return None
        if root["mutation_state"] not in ("applied", "none") or root["reason"] not in _REASONS:
            return None
        if root["status"] == "accepted" and (root["mutation_state"], root["reason"]) != ("applied", "accepted"):
            return None
        if root["status"] == "rejected" and (root["mutation_state"] != "none" or root["reason"] == "accepted"):
            return None
        decision = root["decision_id"]
        action = root["action_id"]
        return {
            "status": root["status"],
            "mutation_state": root["mutation_state"],
            "reason": root["reason"],
            "decision_binding": decision == expected_decision if _valid_id(decision) else None,
            "action_binding": action == expected_action if _valid_action(action) else None,
        }
    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError, RecursionError):
        return None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _valid_action(value: object) -> bool:
    if value in ("skip_card", "proceed"):
        return True
    return isinstance(value, str) and (
        len(value) == 7 and value.startswith("claim:") and value[-1] in "01234567"
        or len(value) == 6 and value.startswith("open:") and value[-1] in "01234567"
        or len(value) == 8 and value.startswith("choose:") and value[-1] in "01234"
    )


def _safe_receipt(value: object) -> bool:
    return isinstance(value, dict) and set(value) == {"status", "mutation_state", "reason", "decision_binding", "action_binding"} and value["status"] in ("accepted", "rejected") and value["mutation_state"] in ("applied", "none") and value["reason"] in _REASONS and (type(value["decision_binding"]) is bool or value["decision_binding"] is None) and (type(value["action_binding"]) is bool or value["action_binding"] is None)
