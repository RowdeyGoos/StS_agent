"""Fixed, capture-off host stages for one bounded room client invocation."""
from __future__ import annotations


_STAGES = frozenset(
    (
        "not_entered",
        "context_validation",
        "health_read",
        "manifest_read",
        "room_read",
        "room_validation",
        "room_waiting",
        "action_exchange",
        "action_receipt",
        "post_action",
        "complete",
    )
)
_OBSERVATION_STATUSES = frozenset(
    ("none", "ready", "waiting", "unsupported", "complete")
)
_READY_KINDS = frozenset(("none", "rest_site", "event"))
_ACTION_CATEGORIES = frozenset(
    ("none", "rest_heal", "rest_proceed", "event_choice")
)
_RECORD_KEYS = (
    "stage",
    "last_observation_status",
    "last_ready_kind",
    "action_exchange_attempt_count",
    "accepted_receipt_count",
    "last_attempted_action",
    "last_accepted_action",
    "completion_confirmed",
)
_SETUP_STAGES = frozenset(("context_validation", "health_read", "manifest_read"))
_EXCHANGE_STAGES = frozenset(("action_exchange", "action_receipt"))


def _valid_action_for_kind(action: str, ready_kind: str) -> bool:
    return (
        ready_kind == "rest_site" and action in ("rest_heal", "rest_proceed")
    ) or (ready_kind == "event" and action == "event_choice")


def validate_room_stage_record(value: object) -> dict[str, object]:
    """Return the exact safe record, rejecting malformed or inconsistent state."""
    if type(value) is not dict or tuple(value) != _RECORD_KEYS:
        raise ValueError("room diagnostic shape")
    stage = value["stage"]
    observation = value["last_observation_status"]
    ready_kind = value["last_ready_kind"]
    attempts = value["action_exchange_attempt_count"]
    accepted = value["accepted_receipt_count"]
    attempted_action = value["last_attempted_action"]
    accepted_action = value["last_accepted_action"]
    completed = value["completion_confirmed"]
    if (
        type(stage) is not str
        or stage not in _STAGES
        or type(observation) is not str
        or observation not in _OBSERVATION_STATUSES
        or type(ready_kind) is not str
        or ready_kind not in _READY_KINDS
        or type(attempts) is not int
        or type(accepted) is not int
        or not 0 <= accepted <= attempts <= 12
        or attempts - accepted not in (0, 1)
        or type(attempted_action) is not str
        or attempted_action not in _ACTION_CATEGORIES
        or type(accepted_action) is not str
        or accepted_action not in _ACTION_CATEGORIES
        or type(completed) is not bool
        or (attempts == 0) != (attempted_action == "none")
        or (accepted == 0) != (accepted_action == "none")
        or (
            attempts == accepted
            and attempts > 0
            and attempted_action != accepted_action
        )
    ):
        raise ValueError("room diagnostic value")
    all_defaults = (
        observation == "none"
        and ready_kind == "none"
        and attempts == 0
        and accepted == 0
        and attempted_action == "none"
        and accepted_action == "none"
        and completed is False
    )
    if stage == "not_entered" and not all_defaults:
        raise ValueError("room diagnostic not entered")
    if stage in _SETUP_STAGES and not all_defaults:
        raise ValueError("room diagnostic setup")
    if observation == "ready" and ready_kind == "none":
        raise ValueError("room diagnostic ready kind")
    if observation == "none" and ready_kind != "none":
        raise ValueError("room diagnostic unobserved kind")
    replacement_ready = stage == "room_validation" and observation == "ready"
    if attempts > 0 and not replacement_ready and (
        ready_kind == "none"
        or not _valid_action_for_kind(attempted_action, ready_kind)
        or (
            accepted > 0
            and not _valid_action_for_kind(accepted_action, ready_kind)
        )
    ):
        raise ValueError("room diagnostic action kind")
    if stage == "room_waiting" and (
        observation != "waiting" or attempts != accepted or completed
    ):
        raise ValueError("room diagnostic waiting")
    if stage in ("room_read", "room_validation") and (
        attempts != accepted or completed
    ):
        raise ValueError("room diagnostic read")
    if stage in _EXCHANGE_STAGES and (
        observation != "ready"
        or attempts != accepted + 1
        or ready_kind == "none"
        or not _valid_action_for_kind(attempted_action, ready_kind)
        or (
            accepted > 0
            and not _valid_action_for_kind(accepted_action, ready_kind)
        )
        or completed
    ):
        raise ValueError("room diagnostic exchange")
    if stage == "post_action" and (
        observation != "ready"
        or attempts == 0
        or attempts != accepted
        or attempted_action != accepted_action
        or ready_kind == "none"
        or not _valid_action_for_kind(attempted_action, ready_kind)
        or completed
    ):
        raise ValueError("room diagnostic post action")
    if completed != (stage == "complete"):
        raise ValueError("room diagnostic completion flag")
    if stage == "complete" and (
        observation != "complete"
        or accepted < 1
        or attempts != accepted
        or attempted_action != accepted_action
        or ready_kind == "none"
        or not _valid_action_for_kind(attempted_action, ready_kind)
    ):
        raise ValueError("room diagnostic complete")
    return {key: value[key] for key in _RECORD_KEYS}


class RoomStageDiagnostics:
    """Store only bounded primitives describing the current host room stage."""

    def __init__(self) -> None:
        self.stage = "not_entered"
        self.last_observation_status = "none"
        self.last_ready_kind = "none"
        self.action_exchange_attempt_count = 0
        self.accepted_receipt_count = 0
        self.last_attempted_action = "none"
        self.last_accepted_action = "none"
        self.completion_confirmed = False

    def enter_context_validation(self) -> None:
        self._require_stage("not_entered")
        self.stage = "context_validation"

    def begin_health_read(self) -> None:
        self._require_stage("context_validation")
        self.stage = "health_read"

    def begin_manifest_read(self) -> None:
        self._require_stage("health_read")
        self.stage = "manifest_read"

    def begin_room_read(self) -> None:
        self._require_stage("manifest_read", "room_waiting", "post_action")
        self.stage = "room_read"

    def begin_room_validation(self) -> None:
        self._require_stage("room_read")
        self.stage = "room_validation"

    def validated_observation(self, status: str, ready_kind: str = "none") -> None:
        self._require_stage("room_validation")
        if type(status) is not str or status not in _OBSERVATION_STATUSES - {"none"}:
            raise ValueError("room diagnostic observation")
        if type(ready_kind) is not str or ready_kind not in _READY_KINDS:
            raise ValueError("room diagnostic ready kind")
        if status == "ready":
            if ready_kind == "none":
                raise ValueError("room diagnostic ready kind")
            self.last_ready_kind = ready_kind
        elif ready_kind != "none":
            raise ValueError("room diagnostic inactive kind")
        self.last_observation_status = status

    def mark_room_waiting(self) -> None:
        self._require_stage("room_validation")
        if self.last_observation_status != "waiting":
            raise ValueError("room diagnostic waiting")
        self.stage = "room_waiting"

    def begin_action_exchange(self, action_category: str) -> None:
        self._require_stage("room_validation")
        if (
            self.last_observation_status != "ready"
            or type(action_category) is not str
            or action_category not in _ACTION_CATEGORIES - {"none"}
            or not _valid_action_for_kind(action_category, self.last_ready_kind)
            or self.action_exchange_attempt_count >= 12
            or self.action_exchange_attempt_count != self.accepted_receipt_count
        ):
            raise ValueError("room diagnostic action exchange")
        self.action_exchange_attempt_count += 1
        self.last_attempted_action = action_category
        self.stage = "action_exchange"

    def begin_action_receipt(self) -> None:
        self._require_stage("action_exchange")
        self.stage = "action_receipt"

    def accept_receipt(self) -> None:
        self._require_stage("action_receipt")
        if self.accepted_receipt_count + 1 != self.action_exchange_attempt_count:
            raise ValueError("room diagnostic receipt count")
        self.accepted_receipt_count += 1
        self.last_accepted_action = self.last_attempted_action

    def mark_post_action(self) -> None:
        self._require_stage("action_receipt")
        if self.accepted_receipt_count != self.action_exchange_attempt_count:
            raise ValueError("room diagnostic post action")
        self.stage = "post_action"

    def mark_complete(self) -> None:
        self._require_stage("room_validation")
        if (
            self.last_observation_status != "complete"
            or self.accepted_receipt_count < 1
            or self.accepted_receipt_count != self.action_exchange_attempt_count
        ):
            raise ValueError("room diagnostic complete")
        self.completion_confirmed = True
        self.stage = "complete"

    def record(self) -> dict[str, object]:
        return validate_room_stage_record(
            {
                "stage": self.stage,
                "last_observation_status": self.last_observation_status,
                "last_ready_kind": self.last_ready_kind,
                "action_exchange_attempt_count": self.action_exchange_attempt_count,
                "accepted_receipt_count": self.accepted_receipt_count,
                "last_attempted_action": self.last_attempted_action,
                "last_accepted_action": self.last_accepted_action,
                "completion_confirmed": self.completion_confirmed,
            }
        )

    def _require_stage(self, *allowed: str) -> None:
        if type(self.stage) is not str or self.stage not in allowed:
            raise ValueError("room diagnostic transition")
