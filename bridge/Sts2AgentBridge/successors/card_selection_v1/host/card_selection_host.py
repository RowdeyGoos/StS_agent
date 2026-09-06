"""Strict controller for the injected card-selection v1 wire service."""

from __future__ import annotations

import json
import math
import time
from typing import Any, Callable

PARENT = "/card-selection-v1/parent"
PARENT_ACTION = "/card-selection-v1/parent/action"
CHILD = "/card-selection-v1/child"
CHILD_ACTION = "/card-selection-v1/child/action"

MAX_BODY = 65536
MAX_READS = 1024
MAX_PARENT_POSTS = 2
MAX_CHILD_POSTS = 10
DEADLINE_SECONDS = 30.0
POLL_SECONDS = 0.05


class TransportFailure(Exception):
    """The sole injected exception classified as a transport failure."""


class _InvalidResponse(Exception):
    pass


class _Stop(Exception):
    def __init__(self, code: str) -> None:
        super().__init__()
        self.code = code


class _Pairs(list[tuple[str, Any]]):
    pass


def _require(value: bool) -> None:
    if not value:
        raise _InvalidResponse()


def _convert(value: Any) -> Any:
    if type(value) is _Pairs:
        result: dict[str, Any] = {}
        for key, item in value:
            _require(type(key) is str and key not in result)
            result[key] = _convert(item)
        return result
    if type(value) is list:
        return [_convert(item) for item in value]
    if type(value) in (str, int, bool) or value is None:
        return value
    raise _InvalidResponse()


def _constant(_: str) -> None:
    raise _InvalidResponse()


def _keys(value: Any, expected: tuple[str, ...]) -> None:
    _require(type(value) is dict and tuple(value) == expected)


def _hex(value: Any, length: int) -> bool:
    return type(value) is str and len(value) == length and all(c in "0123456789abcdef" for c in value)


def _integer(value: Any, maximum: int = 2_147_483_647) -> bool:
    return type(value) is int and 0 <= value <= maximum


def _stable_key(value: Any) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 128
        and all(c.isascii() and (c.isalnum() or c == "_") for c in value)
    )


def _action(value: Any, parent: bool) -> bool:
    if type(value) is not str:
        return False
    if parent:
        return value in ("begin", "proceed")
    if value in ("preview", "confirm"):
        return True
    if not value.startswith("select:"):
        return False
    suffix = value[7:]
    return (
        1 <= len(suffix) <= 2
        and suffix.isascii()
        and suffix.isdecimal()
        and str(int(suffix)) == suffix
        and int(suffix) < 64
    )


def _decode(body: bytearray) -> dict[str, Any]:
    _require(type(body) is bytearray and 0 < len(body) <= MAX_BODY)
    try:
        raw = bytes(body)
        _require(raw.isascii())
        value = _convert(json.loads(raw, object_pairs_hook=_Pairs, parse_constant=_constant))
        _require(type(value) is dict)
        canonical = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
        _require(canonical == raw)
        _require(type(value.get("schema_version")) is int and value["schema_version"] == 1)
        _validate_envelope(value)
        return value
    except _InvalidResponse:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        raise _InvalidResponse() from None


def _common(value: dict[str, Any], version: str) -> None:
    _require(value.get("version") == version)
    _require(_hex(value.get("session_nonce"), 32))
    _require(type(value.get("parent_ordinal")) is int and value["parent_ordinal"] == 1)


def _validate_envelope(value: dict[str, Any]) -> None:
    kind = value.get("kind")
    if kind == "error":
        _keys(value, ("schema_version", "kind", "status", "code"))
        _require(value["status"] == "error" and value["code"] in ("invalid_request", "internal_failure"))
    elif kind == "parent_observation":
        _parent_observation(value)
    elif kind == "parent_resolved":
        _parent_resolved(value)
    elif kind == "parent_receipt":
        _receipt(value, parent=True)
    elif kind == "parent_failure":
        _failure(value, parent=True)
    elif kind == "child_observation":
        _child_observation(value)
    elif kind == "child_resolved":
        _child_resolved(value)
    elif kind == "child_receipt":
        _receipt(value, parent=False)
    elif kind == "child_failure":
        _failure(value, parent=False)
    else:
        raise _InvalidResponse()


def _parent_observation(v: dict[str, Any]) -> None:
    _keys(v, ("schema_version", "kind", "version", "session_nonce", "parent_ordinal", "status", "phase", "parent_kind", "policy", "decision_id", "legal_actions"))
    _common(v, "card_selection_parent_v1")
    _require(type(v["legal_actions"]) is list)
    if v["status"] == "ready":
        _require(v["phase"] in ("initial", "after") and _hex(v["decision_id"], 64))
        expected = "begin" if v["phase"] == "initial" else "proceed"
        _require(v["legal_actions"] == [expected])
        _require((v["parent_kind"], v["policy"]) in (
            ("event", "cheese_gorge_add_two"),
            ("rest", "rest_smith_upgrade_one"),
        ))
        return
    pairs = {
        "waiting": ("initial", "transient", "card_child", "after", "exit"),
        "unsupported": ("unsupported",),
    }
    _require(v["status"] in pairs and v["phase"] in pairs[v["status"]])
    _require(v["parent_kind"] == v["policy"] == v["decision_id"] == "" and v["legal_actions"] == [])


def _parent_resolved(v: dict[str, Any]) -> None:
    _keys(v, ("schema_version", "kind", "version", "session_nonce", "parent_ordinal", "status", "result", "begin_decision_id", "begin_action_id", "proceed_decision_id", "proceed_action_id"))
    _common(v, "card_selection_parent_v1")
    _require(v["status"] == "resolved" and v["result"] == "map_handoff")
    _require(_hex(v["begin_decision_id"], 64) and v["begin_action_id"] == "begin")
    _require(_hex(v["proceed_decision_id"], 64) and v["proceed_action_id"] == "proceed")


def _receipt(v: dict[str, Any], parent: bool) -> None:
    _keys(v, ("schema_version", "kind", "version", "session_nonce", "parent_ordinal", "decision_id", "action_id", "outcome"))
    _common(v, "card_selection_parent_v1" if parent else "card_selection_v1")
    _require(_hex(v["decision_id"], 64) and _action(v["action_id"], parent) and v["outcome"] == "accepted")


def _failure(v: dict[str, Any], parent: bool) -> None:
    _keys(v, ("schema_version", "kind", "version", "session_nonce", "parent_ordinal", "outcome"))
    _common(v, "card_selection_parent_v1" if parent else "card_selection_v1")
    _require(v["outcome"] in ("rejected", "unsupported", "uncertain"))


def _candidate(value: Any) -> None:
    _keys(value, ("slot", "key", "upgrade_level", "visible", "enabled", "selected"))
    _require(_integer(value["slot"], 63) and _stable_key(value["key"]))
    _require(_integer(value["upgrade_level"]))
    _require(all(type(value[key]) is bool for key in ("visible", "enabled", "selected")))


def _history(value: Any) -> None:
    _keys(value, ("decision_id", "action_id", "result"))
    _require(_hex(value["decision_id"], 64) and _action(value["action_id"], False))
    expected = "selected" if value["action_id"].startswith("select:") else "previewed" if value["action_id"] == "preview" else "committed"
    _require(value["result"] == expected)


def _child_observation(v: dict[str, Any]) -> None:
    _keys(v, ("schema_version", "kind", "version", "session_nonce", "parent_ordinal", "status", "phase", "operation", "commit_mode", "min_select", "max_select", "decision_id", "candidates", "selected_slots", "legal_actions", "prior_results"))
    _common(v, "card_selection_v1")
    for name, maximum in (("candidates", 64), ("selected_slots", 8), ("legal_actions", 65), ("prior_results", 10)):
        _require(type(v[name]) is list and len(v[name]) <= maximum)
    for result in v["prior_results"]:
        _history(result)
    if v["status"] != "ready":
        pairs = {"waiting": ("selecting", "submitted", "transient"), "unsupported": ("unsupported",)}
        _require(v["status"] in pairs and v["phase"] in pairs[v["status"]])
        _require(v["operation"] == v["commit_mode"] == v["decision_id"] == "")
        _require(type(v["min_select"]) is int and v["min_select"] == 0)
        _require(type(v["max_select"]) is int and v["max_select"] == 0)
        _require(v["candidates"] == v["selected_slots"] == v["legal_actions"] == [])
        return
    _require(v["phase"] in ("selecting", "preview"))
    _require(v["operation"] in ("add", "remove", "upgrade", "transform"))
    _require(v["commit_mode"] in ("auto_at_max", "explicit_confirm", "preview_confirm"))
    _require(_integer(v["min_select"], 8) and _integer(v["max_select"], 8))
    _require(1 <= v["min_select"] <= v["max_select"] and _hex(v["decision_id"], 64))
    _require(1 <= len(v["candidates"]) <= 64 and len(v["legal_actions"]) >= 1)
    slots: set[int] = set()
    selected: set[int] = set()
    for candidate in v["candidates"]:
        _candidate(candidate)
        _require(candidate["slot"] not in slots)
        slots.add(candidate["slot"])
        if candidate["selected"]:
            selected.add(candidate["slot"])
    _require(all(type(slot) is int for slot in v["selected_slots"]))
    _require(len(set(v["selected_slots"])) == len(v["selected_slots"]) and set(v["selected_slots"]) == selected)
    _require(len(selected) <= v["max_select"])
    expected_selected = {int(item["action_id"][7:]) for item in v["prior_results"] if item["result"] == "selected"}
    _require(selected == expected_selected)
    _require(all(type(action) is str and _action(action, False) for action in v["legal_actions"]))
    _require(len(set(v["legal_actions"])) == len(v["legal_actions"]))
    selections = [
        "select:" + str(candidate["slot"])
        for candidate in v["candidates"]
        if v["phase"] == "selecting" and candidate["visible"] and candidate["enabled"]
        and not candidate["selected"] and len(selected) < v["max_select"]
    ]
    actual_selections = [action for action in v["legal_actions"] if action.startswith("select:")]
    _require(actual_selections == selections)
    if "preview" in v["legal_actions"]:
        _require(v["phase"] == "selecting" and v["commit_mode"] == "preview_confirm" and v["min_select"] <= len(selected) <= v["max_select"])
    if "confirm" in v["legal_actions"]:
        _require(v["min_select"] <= len(selected) <= v["max_select"])
        _require((v["phase"], v["commit_mode"]) in (("selecting", "explicit_confirm"), ("preview", "preview_confirm")))
    _require(not (v["min_select"] == v["max_select"] and len(selected) < v["min_select"] and "confirm" in v["legal_actions"]))


def _child_resolved(v: dict[str, Any]) -> None:
    _keys(v, ("schema_version", "kind", "version", "session_nonce", "parent_ordinal", "status", "phase", "operation", "selected_cards", "prior_results"))
    _common(v, "card_selection_v1")
    _require(v["status"] == "resolved" and v["phase"] == "complete")
    _require(v["operation"] in ("add", "remove", "upgrade", "transform"))
    _require(type(v["selected_cards"]) is list and 1 <= len(v["selected_cards"]) <= 8)
    _require(type(v["prior_results"]) is list and 1 <= len(v["prior_results"]) <= 10)
    slots: set[int] = set()
    for card in v["selected_cards"]:
        _candidate(card)
        _require(card["selected"] and card["slot"] not in slots)
        slots.add(card["slot"])
    for result in v["prior_results"]:
        _history(result)
    selected = {int(item["action_id"][7:]) for item in v["prior_results"] if item["result"] == "selected"}
    _require(slots == selected)


def _summary(status: str, code: str | None, counts: dict[str, int]) -> dict[str, Any]:
    result: dict[str, Any] = {"schema_version": 1, "status": status}
    if code is not None:
        result["code"] = code
    result.update(counts)
    return result


class _Controller:
    def __init__(self, request: Callable[[str, str, bytearray | None], bytearray], clock: Callable[[], float], sleep: Callable[[float], None]) -> None:
        self.request = request
        self.clock = clock
        self.sleep = sleep
        initial = clock()
        if type(initial) not in (int, float) or not math.isfinite(initial):
            raise ValueError("invalid clock")
        self._last_time = float(initial)
        self.deadline = self._last_time + DEADLINE_SECONDS
        self.nonce: str | None = None
        self.parent_policy: tuple[str, str] | None = None
        self.parent_accepted: list[tuple[str, str]] = []
        self.child_accepted: list[tuple[str, str]] = []
        self.child_history = 0
        self.child_shape: list[tuple[int, str, int]] | None = None
        self.child_operation: str | None = None
        self.child_bounds: tuple[int, int] | None = None
        self.child_resolved = False
        self._reads = 0
        self.counts = {
            "parent_attempted": 0,
            "parent_accepted": 0,
            "parent_reconciled": 0,
            "child_attempted": 0,
            "child_accepted": 0,
            "child_reconciled": 0,
        }

    def now(self) -> float:
        value = self.clock()
        if type(value) not in (int, float) or not math.isfinite(value) or value < self._last_time:
            raise ValueError("invalid clock")
        self._last_time = float(value)
        return self._last_time

    def budget(self) -> None:
        if self.now() >= self.deadline:
            raise _Stop("deadline_exceeded")

    def call(self, method: str, path: str, decision: str | None = None, action: str | None = None) -> dict[str, Any]:
        self.budget()
        if method == "GET":
            if self._reads >= MAX_READS:
                raise _Stop("read_limit_reached")
            self._reads += 1
            body = None
        else:
            key = "parent_attempted" if path == PARENT_ACTION else "child_attempted"
            cap = MAX_PARENT_POSTS if key == "parent_attempted" else MAX_CHILD_POSTS
            if self.counts[key] >= cap:
                raise _Stop("action_limit_reached")
            self.counts[key] += 1  # reservation before transport
            _require(decision is not None and action is not None)
            body = bytearray(json.dumps({"decision_id": decision, "action_id": action}, separators=(",", ":")).encode("ascii"))
        response: bytearray | None = None
        try:
            response = self.request(method, path, body)
            self.budget()
            value = _decode(response)
            nonce = value.get("session_nonce")
            if nonce is not None:
                if self.nonce is None:
                    self.nonce = nonce
                _require(nonce == self.nonce)
            if value["kind"] == "error":
                raise _Stop("internal_failure" if value["code"] == "internal_failure" else "invalid_request")
            return value
        finally:
            if type(body) is bytearray:
                body[:] = b"\0" * len(body)
            if type(response) is bytearray:
                response[:] = b"\0" * len(response)

    def pause(self) -> None:
        self.budget()
        self.sleep(min(POLL_SECONDS, self.deadline - self.now()))
        self.budget()

    def accepted(self, ready: dict[str, Any], path: str, action: str, parent: bool) -> None:
        prior = self.parent_accepted + self.child_accepted
        _require(all(decision != ready["decision_id"] for decision, _ in prior))
        _require(action in ready["legal_actions"])
        value = self.call("POST", path, ready["decision_id"], action)
        expected_kind = "parent_receipt" if parent else "child_receipt"
        if value["kind"] in ("parent_failure", "child_failure"):
            raise _Stop({"rejected": "action_rejected", "unsupported": "unsupported_state", "uncertain": "action_uncertain"}[value["outcome"]])
        _require(value["kind"] == expected_kind and value["decision_id"] == ready["decision_id"] and value["action_id"] == action)
        pair = (value["decision_id"], value["action_id"])
        (self.parent_accepted if parent else self.child_accepted).append(pair)
        key = "parent_accepted" if parent else "child_accepted"
        self.counts[key] += 1

    def validate_parent(self, value: dict[str, Any]) -> None:
        if value["kind"] == "parent_failure":
            raise _Stop("unsupported_state")
        _require(value["kind"] in ("parent_observation", "parent_resolved"))
        if value["kind"] == "parent_observation" and value["status"] == "unsupported":
            raise _Stop("unsupported_state")

    def validate_child(self, value: dict[str, Any]) -> None:
        if value["kind"] == "child_failure":
            raise _Stop("unsupported_state")
        _require(value["kind"] in ("child_observation", "child_resolved"))
        if value["kind"] == "child_observation" and value["status"] == "unsupported":
            raise _Stop("unsupported_state")
        history = value["prior_results"]
        _require(len(history) >= self.child_history and len(history) <= len(self.child_accepted))
        for index, item in enumerate(history):
            decision, action = self.child_accepted[index]
            _require(item["decision_id"] == decision and item["action_id"] == action)
        if value["kind"] == "child_observation" and value["status"] == "ready":
            _require(len(history) == len(self.child_accepted))
            pair = (value["operation"], value["commit_mode"])
            if self.parent_policy == ("event", "cheese_gorge_add_two"):
                _require(pair == ("add", "auto_at_max") and value["min_select"] == value["max_select"] == 2 and len(value["candidates"]) == 8)
            elif self.parent_policy == ("rest", "rest_smith_upgrade_one"):
                _require(pair == ("upgrade", "preview_confirm") and value["min_select"] == value["max_select"] == 1)
            else:
                raise _InvalidResponse()
            shape = [(item["slot"], item["key"], item["upgrade_level"]) for item in value["candidates"]]
            if self.child_shape is None:
                self.child_shape = shape
                self.child_operation = value["operation"]
                self.child_bounds = (value["min_select"], value["max_select"])
            _require(shape == self.child_shape and value["operation"] == self.child_operation and (value["min_select"], value["max_select"]) == self.child_bounds)
        elif value["kind"] == "child_observation" and value["status"] == "waiting":
            _require(self.child_shape is not None and len(self.child_accepted) > 0)
        if value["kind"] == "child_resolved":
            _require(value["operation"] == self.child_operation and len(history) == len(self.child_accepted))
            _require(self.child_bounds is not None and self.child_bounds[0] <= len(value["selected_cards"]) <= self.child_bounds[1])
            _require(self.child_shape is not None)
            by_slot = {slot: (key, level) for slot, key, level in self.child_shape}
            for card in value["selected_cards"]:
                _require(by_slot.get(card["slot"]) == (card["key"], card["upgrade_level"]))
            _require(self.child_accepted)
            if self.parent_policy == ("rest", "rest_smith_upgrade_one"):
                _require(self.child_accepted[-1][1] == "confirm")
            elif self.parent_policy == ("event", "cheese_gorge_add_two"):
                _require(self.child_accepted[-1][1].startswith("select:") and len(value["selected_cards"]) == 2)
            else:
                raise _InvalidResponse()
            self.child_resolved = True
        self.counts["child_reconciled"] += len(history) - self.child_history
        self.child_history = len(history)

    def run(self) -> None:
        initial: dict[str, Any] | None = None
        while initial is None:
            value = self.call("GET", PARENT)
            self.validate_parent(value)
            _require(value["kind"] == "parent_observation")
            if value["status"] == "waiting":
                _require(value["phase"] == "initial")
                self.pause()
            else:
                _require(value["status"] == "ready" and value["phase"] == "initial")
                self.parent_policy = (value["parent_kind"], value["policy"])
                initial = value
        self.accepted(initial, PARENT_ACTION, "begin", parent=True)

        admitted = False
        while not admitted:
            value = self.call("GET", PARENT)
            self.validate_parent(value)
            _require(value["kind"] == "parent_observation" and value["status"] == "waiting")
            if value["phase"] == "card_child":
                admitted = True
                self.counts["parent_reconciled"] = 1
            else:
                _require(value["phase"] == "transient")
                self.pause()

        while not self.child_resolved:
            value = self.call("GET", CHILD)
            self.validate_child(value)
            if value["kind"] == "child_resolved":
                break
            if value["status"] == "waiting":
                self.pause()
                continue
            _require(value["status"] == "ready")
            selected = len(value["selected_slots"])
            choices = [item for item in value["legal_actions"] if item.startswith("select:")]
            if selected < value["max_select"]:
                _require(choices)
                action = choices[0]
            elif "preview" in value["legal_actions"]:
                action = "preview"
            elif "confirm" in value["legal_actions"]:
                _require(not (value["min_select"] == value["max_select"] == 2 and selected == 1))
                action = "confirm"
            else:
                raise _InvalidResponse()
            self.accepted(value, CHILD_ACTION, action, parent=False)

        after: dict[str, Any] | None = None
        while after is None:
            value = self.call("GET", PARENT)
            self.validate_parent(value)
            _require(value["kind"] == "parent_observation")
            if value["status"] == "waiting":
                _require(value["phase"] == "after")
                self.pause()
            else:
                _require(value["status"] == "ready" and value["phase"] == "after")
                _require((value["parent_kind"], value["policy"]) == self.parent_policy)
                after = value
        self.accepted(after, PARENT_ACTION, "proceed", parent=True)

        while True:
            value = self.call("GET", PARENT)
            self.validate_parent(value)
            if value["kind"] == "parent_resolved":
                _require(len(self.parent_accepted) == 2 and self.child_resolved)
                _require((value["begin_decision_id"], value["begin_action_id"]) == self.parent_accepted[0])
                _require((value["proceed_decision_id"], value["proceed_action_id"]) == self.parent_accepted[1])
                self.counts["parent_reconciled"] = 2
                return
            _require(value["kind"] == "parent_observation" and value["status"] == "waiting" and value["phase"] == "exit")
            self.pause()


def run_card_selection(
    request: Callable[[str, str, bytearray | None], bytearray],
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    controller: _Controller | None = None
    try:
        controller = _Controller(request, clock, sleep)
        controller.run()
        return _summary("passed", None, controller.counts)
    except _Stop as stop:
        counts = controller.counts if controller is not None else {
            "parent_attempted": 0, "parent_accepted": 0, "parent_reconciled": 0,
            "child_attempted": 0, "child_accepted": 0, "child_reconciled": 0,
        }
        return _summary("failed", stop.code, counts)
    except TransportFailure:
        counts = controller.counts if controller is not None else {
            "parent_attempted": 0, "parent_accepted": 0, "parent_reconciled": 0,
            "child_attempted": 0, "child_accepted": 0, "child_reconciled": 0,
        }
        return _summary("failed", "transport_failure", counts)
    except _InvalidResponse:
        counts = controller.counts if controller is not None else {
            "parent_attempted": 0, "parent_accepted": 0, "parent_reconciled": 0,
            "child_attempted": 0, "child_accepted": 0, "child_reconciled": 0,
        }
        return _summary("failed", "invalid_response", counts)
    except Exception:
        counts = controller.counts if controller is not None else {
            "parent_attempted": 0, "parent_accepted": 0, "parent_reconciled": 0,
            "child_attempted": 0, "child_accepted": 0, "child_reconciled": 0,
        }
        return _summary("failed", "internal_failure", counts)
