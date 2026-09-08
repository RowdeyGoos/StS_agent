"""Strict child-only card_transform_v1 parser; derived from frozen card host helpers."""
from __future__ import annotations
from typing import Any

class _InvalidResponse(Exception):
    pass


def _require(value: bool) -> None:
    if not value:
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
        return False
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


def _common(value: dict[str, Any], version: str) -> None:
    _require(value.get("version") == version)
    _require(_hex(value.get("session_nonce"), 32))
    _require(type(value.get("parent_ordinal")) is int and value["parent_ordinal"] == 1)


def _validate_envelope(value: dict[str, Any]) -> None:
    _require(type(value) is dict and type(value.get("schema_version")) is int and value["schema_version"] == 1)
    kind = value.get("kind")
    if kind == "child_observation": _child_observation(value)
    elif kind == "child_resolved": _child_resolved(value)
    elif kind == "child_receipt": _receipt(value)
    elif kind == "child_failure": _failure(value)
    else: raise _InvalidResponse()


def _receipt(v: dict[str, Any]) -> None:
    _keys(v, ("schema_version", "kind", "version", "session_nonce", "parent_ordinal", "decision_id", "action_id", "outcome"))
    _common(v, "card_transform_v1")
    _require(_hex(v["decision_id"], 64) and _action(v["action_id"], False) and v["outcome"] == "accepted")


def _failure(v: dict[str, Any]) -> None:
    _keys(v, ("schema_version", "kind", "version", "session_nonce", "parent_ordinal", "outcome"))
    _common(v, "card_transform_v1")
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
    _common(v, "card_transform_v1")
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
    _require(v["operation"] == "transform")
    _require(v["commit_mode"] in ("auto_at_max", "explicit_confirm", "preview_confirm"))
    _require(_integer(v["min_select"], 8) and _integer(v["max_select"], 8))
    _require(1 <= v["min_select"] == v["max_select"] and v["commit_mode"] == "preview_confirm" and _hex(v["decision_id"], 64))
    _require(v["max_select"] < len(v["candidates"]) <= 64 and len(v["legal_actions"]) >= 1)
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
    _common(v, "card_transform_v1")
    _require(v["status"] == "resolved" and v["phase"] == "complete")
    _require(v["operation"] == "transform")
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
