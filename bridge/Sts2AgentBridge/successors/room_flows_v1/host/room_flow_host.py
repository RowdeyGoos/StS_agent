"""Bounded shop/event controllers over injected exchange; no I/O or retained text."""
from __future__ import annotations

import hashlib
import json
import struct
import time
from typing import Any, Callable

GET = "/probe/room-flows-v1/public/decision"
POST = "/probe/room-flows-v1/public/action"
COMMON = ("schema_version", "protocol", "version", "flow_kind", "session_nonce", "parent_ordinal", "status")
MAX_BODY = 65536
MAX_READS = 1024
SECONDS = 30.0


class InvalidResponse(Exception):
    pass


class Stop(Exception):
    def __init__(self, code: str):
        self.code = code


def require(value: bool) -> None:
    if not value:
        raise InvalidResponse()


def integer(value: Any, maximum: int = 2147483647) -> bool:
    return type(value) is int and 0 <= value <= maximum


def hex_id(value: Any, size: int) -> bool:
    return type(value) is str and len(value) == size and all(c in "0123456789abcdef" for c in value)


def stable_key(value: Any) -> bool:
    return type(value) is str and 1 <= len(value) <= 128 and all(c.isascii() and (c.isalnum() or c == "_") for c in value)


def action(flow: str, value: Any) -> bool:
    if type(value) is not str:
        return False
    if flow == "shop" and value in ("inventory:close", "leave"):
        return True
    prefix, maximum = ("buy:card:", 31) if flow == "shop" else ("choose:", 7)
    suffix = value[len(prefix):]
    return value.startswith(prefix) and 1 <= len(suffix) <= 2 and suffix.isascii() and suffix.isdecimal() and str(int(suffix)) == suffix and int(suffix) <= maximum


def keys(value: Any, expected: tuple[str, ...]) -> None:
    require(type(value) is dict and tuple(value) == expected)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def _constant(_: str) -> None:
    raise InvalidResponse()


def decode(body: bytearray, flow: str) -> dict[str, Any]:
    require(type(body) is bytearray and 0 < len(body) <= MAX_BODY)
    try:
        raw = bytes(body)
        require(raw.isascii())
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
        require(json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii") == raw)
        require(type(value) is dict)
        require(type(value.get("schema_version")) is int and value["schema_version"] == 1)
        require(value.get("protocol") == "room_flows_v1" and value.get("version") == flow + "_v1" and value.get("flow_kind") == flow)
        require(hex_id(value.get("session_nonce"), 32))
        require(type(value.get("parent_ordinal")) is int and value["parent_ordinal"] == 1)
        status = value.get("status")
        if status == "accepted":
            keys(value, COMMON + ("decision_id", "action_id"))
            require(hex_id(value["decision_id"], 64) and action(flow, value["action_id"]))
        elif status in ("rejected", "uncertain"):
            keys(value, COMMON)
        elif status == "error":
            keys(value, COMMON + ("code",))
            require(value["code"] in ("invalid_request", "internal_failure"))
        elif status == "unsupported" and tuple(value) == COMMON:
            pass  # Fixed apply failure, distinct from an observation.
        elif flow == "shop":
            _shop(value)
        elif status == "resolved":
            keys(value, COMMON + ("decision_id", "action_id", "result"))
            require(hex_id(value["decision_id"], 64) and action(flow, value["action_id"]) and value["result"] == "map_handoff")
        else:
            _event(value)
        return value
    except InvalidResponse:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        raise InvalidResponse() from None


def _shop(v: dict[str, Any]) -> None:
    keys(v, COMMON + ("phase", "decision_id", "player", "offers", "legal_actions", "prior_results"))
    require(v["status"] in ("ready", "waiting", "unsupported", "complete"))
    keys(v["player"], ("gold", "deck_count"))
    require(integer(v["player"]["gold"]) and integer(v["player"]["deck_count"], 512))
    require(type(v["offers"]) is list and len(v["offers"]) <= 32)
    require(type(v["legal_actions"]) is list and len(v["legal_actions"]) <= 33)
    require(type(v["prior_results"]) is list and len(v["prior_results"]) <= 1)
    for p in v["prior_results"]:
        keys(p, ("flow_kind", "session_nonce", "parent_ordinal", "decision_id", "action_id", "kind", "result"))
        require(p["flow_kind"] == "shop" and p["session_nonce"] == v["session_nonce"])
        require(type(p["parent_ordinal"]) is int and p["parent_ordinal"] == 1)
        require(hex_id(p["decision_id"], 64) and action("shop", p["action_id"]) and p["result"] == "reconciled")
        require(p["kind"] == ("leave" if p["action_id"] == "leave" else "inventory_close" if p["action_id"] == "inventory:close" else "purchase_card"))
    if v["status"] != "ready":
        require(v["decision_id"] == "" and v["offers"] == [] and v["legal_actions"] == [])
        if v["status"] != "complete":
            require(v["player"] == {"gold": 0, "deck_count": 0})
        phases = {"waiting": ("unknown", "purchase_waiting", "close_waiting", "leave_waiting"), "unsupported": ("unknown",), "complete": ("complete",)}
        require(v["phase"] in phases[v["status"]])
        if v["status"] == "complete":
            require(len(v["prior_results"]) == 1 and v["prior_results"][0]["action_id"] == "leave")
        return
    require(v["phase"] in ("inventory_browse", "room_ready_to_leave") and hex_id(v["decision_id"], 64))
    last = -1
    possible = []
    for o in v["offers"]:
        keys(o, ("slot", "kind", "key", "displayed_price", "affordable", "enabled", "supported"))
        require(integer(o["slot"], 31) and o["slot"] > last and o["kind"] in ("card", "relic", "potion", "removal", "unknown") and stable_key(o["key"]))
        require(integer(o["displayed_price"]) and all(type(o[k]) is bool for k in ("affordable", "enabled", "supported")))
        require(o["affordable"] == (v["player"]["gold"] >= o["displayed_price"]) and (not o["supported"] or o["kind"] == "card"))
        if o["supported"] and o["enabled"] and o["affordable"]:
            possible.append("buy:card:" + str(o["slot"]))
        last = o["slot"]
    if v["phase"] == "room_ready_to_leave":
        require(v["offers"] == [] and v["legal_actions"] == ["leave"])
    else:
        require(v["legal_actions"] in (possible + ["inventory:close"], ["inventory:close"]))
    require(v["decision_id"] == shop_digest(v))


def shop_digest(v: dict[str, Any]) -> str:
    parts = []
    def s(x: str) -> None:
        parts.extend((str(len(x)), ":", x, ";"))
    def n(x: int) -> None:
        parts.extend((str(x), ";"))
    for x in ("shop_v1", "shop", v["session_nonce"]):
        s(x)
    n(1); s(v["phase"]); n(v["player"]["gold"]); n(v["player"]["deck_count"]); n(len(v["offers"]))
    for o in v["offers"]:
        n(o["slot"]); s(o["kind"]); s(o["key"]); n(o["displayed_price"])
        for key in ("affordable", "enabled", "supported"):
            n(int(o[key]))
    n(len(v["legal_actions"]))
    for a in v["legal_actions"]:
        s(a)
    n(len(v["prior_results"]))
    for p in v["prior_results"]:
        for key in ("decision_id", "action_id", "kind", "result"):
            s(p[key])
    return hashlib.sha256("".join(parts).encode("ascii")).hexdigest()


def _event(v: dict[str, Any]) -> None:
    keys(v, COMMON + ("phase", "decision_id", "candidates", "legal_actions"))
    require(v["status"] in ("ready", "waiting", "unsupported", "item_child"))
    require(type(v["candidates"]) is list and len(v["candidates"]) <= 8)
    require(type(v["legal_actions"]) is list and len(v["legal_actions"]) <= 8)
    if v["status"] != "ready":
        require(v["decision_id"] == "" and v["candidates"] == [] and v["legal_actions"] == [])
        require(v["phase"] == {"waiting": "waiting", "unsupported": "unknown", "item_child": "item_child"}[v["status"]])
        return
    require(v["phase"] in ("choose_option", "proceed") and hex_id(v["decision_id"], 64))
    ids, eligible = set(), []
    for index, c in enumerate(v["candidates"]):
        keys(c, ("candidate_index", "action_id", "stable_id", "rendered_text", "enabled", "is_dangerous", "is_proceed"))
        require(type(c["candidate_index"]) is int and c["candidate_index"] == index and c["action_id"] == f"choose:{index}")
        key, text = c["stable_id"], c["rendered_text"]
        require(type(key) is str and 1 <= len(key) <= 96 and all(32 <= ord(ch) <= 126 for ch in key) and key not in ids)
        require(type(text) is str and 1 <= len(text.encode("utf-8")) <= 1024 and all(ch == "\n" or ord(ch) >= 32 and not 127 <= ord(ch) <= 159 for ch in text))
        require(all(type(c[k]) is bool for k in ("enabled", "is_dangerous", "is_proceed")))
        ids.add(key)
        if c["enabled"] and not c["is_dangerous"]:
            eligible.append(c["action_id"])
    require(len(v["legal_actions"]) >= 1 and v["legal_actions"] == [a for a in eligible if a in v["legal_actions"]])
    if v["phase"] == "proceed":
        require(len(v["candidates"]) == 1 and v["candidates"][0]["stable_id"] == "PROCEED" and v["candidates"][0]["is_proceed"] and v["legal_actions"] == ["choose:0"])
    else:
        require(all(not c["is_proceed"] for c in v["candidates"]))
    require(v["decision_id"] == event_digest(v))


def event_digest(v: dict[str, Any]) -> str:
    return _event_digest(v, include_text=True)


def event_transition_digest(v: dict[str, Any]) -> str:
    return _event_digest(v, include_text=False)


def _event_digest(v: dict[str, Any], *, include_text: bool) -> str:
    parts = []
    def n(x: int) -> None:
        parts.append(struct.pack(">i", x))
    def s(x: str) -> None:
        b = x.encode("utf-8"); n(len(b)); parts.append(b)
    for x in ("event_v1", "event", v["session_nonce"]):
        s(x)
    n(1); s(v["phase"]); n(len(v["candidates"]))
    for c in v["candidates"]:
        n(c["candidate_index"])
        for k in (("action_id", "stable_id", "rendered_text") if include_text else ("action_id", "stable_id")):
            s(c[k])
        parts.append(bytes(int(c[k]) for k in ("enabled", "is_dangerous", "is_proceed")))
    actions = v["legal_actions"] if include_text else [
        c["action_id"] for c in v["candidates"] if c["enabled"] and not c["is_dangerous"]]
    n(len(actions))
    for a in actions:
        s(a)
    return hashlib.sha256(b"".join(parts)).hexdigest()


class Controller:
    def __init__(self, flow: str, exchange: Callable, clock: Callable, sleep: Callable):
        self.flow, self.exchange, self.clock, self.sleep = flow, exchange, clock, sleep
        self.deadline = clock() + SECONDS
        self.nonce = None
        self.reads = self.attempted = self.accepted = self.reconciled = 0
        self.child_attempted = self.child_accepted = self.child_reconciled = self.transitions = 0

    def budget(self) -> None:
        if self.clock() >= self.deadline:
            raise Stop("deadline_exceeded")

    def raw(self, method, route, decision, action_id, deadline):
        self.budget()
        if method == "GET":
            if self.reads >= MAX_READS:
                raise Stop("read_limit_reached")
            self.reads += 1
        if self.attempted + self.child_attempted > 13:
            raise Stop("action_limit_reached")
        return self.exchange(method, route, decision, action_id, min(deadline, self.deadline))

    def call(self, method="GET", decision=None, action_id=None):
        body = None
        try:
            self.budget()
            if method == "POST":
                if self.attempted >= (3 if self.flow == "shop" else 12):
                    raise Stop("action_limit_reached")
                self.attempted += 1
            body = self.raw(method, GET if method == "GET" else POST, decision, action_id, self.deadline)
            self.budget()
            v = decode(body, self.flow)
            if self.nonce is None:
                self.nonce = v["session_nonce"]
            require(v["session_nonce"] == self.nonce)
            if v["status"] in ("unsupported", "uncertain", "rejected", "error"):
                raise Stop({"unsupported": "unsupported_state", "uncertain": "action_uncertain", "rejected": "action_rejected", "error": "internal_failure"}[v["status"]])
            return v
        finally:
            if type(body) is bytearray:
                body[:] = b"\0" * len(body)

    def pause(self, seconds=0.1):
        self.budget()
        self.sleep(min(seconds, self.deadline - self.clock()))
        self.budget()

    def receipt(self, ready, action_id):
        v = self.call("POST", ready["decision_id"], action_id)
        require(v["status"] == "accepted" and v["decision_id"] == ready["decision_id"] and v["action_id"] == action_id)
        self.accepted += 1
        return (v["decision_id"], v["action_id"])

    def shop(self, buy_card):
        pending, completed, bought, closed = None, None, False, False
        while True:
            v = self.call()
            require("prior_results" in v)
            prior = v["prior_results"]
            if prior:
                pair = (prior[0]["decision_id"], prior[0]["action_id"])
                require(pair == pending or pair == completed)
                if pair == pending:
                    self.reconciled += 1; completed, pending = pending, None
                    if pair[1] == "inventory:close":
                        closed = True
            if v["status"] == "complete":
                require(pending is None and completed is not None and completed[1] == "leave" and closed)
                return
            if v["status"] == "waiting":
                self.pause(); continue
            require(v["status"] == "ready" and pending is None)
            if v["phase"] == "room_ready_to_leave":
                require(closed); selected = "leave"
            else:
                require(not closed)
                purchases = ["buy:card:" + str(o["slot"]) for o in v["offers"]
                             if o["supported"] and o["enabled"] and o["affordable"]]
                require(v["legal_actions"] == ([] if bought else purchases) + ["inventory:close"])
                if bought:
                    purchases = []
                selected = purchases[0] if buy_card and not bought and purchases else "inventory:close"
                if selected.startswith("buy:"):
                    bought = True
            pending = self.receipt(v, selected)

    def event(self, item_host):
        reserved, child_used, last, phase = set(), False, None, None
        transition_pending = False
        accepted_transition = None
        while True:
            v = self.call()
            if v["status"] == "resolved":
                require(phase == "proceed" and last == (v["decision_id"], v["action_id"]))
                self.reconciled = 1
                return
            if v["status"] == "waiting":
                self.pause(); continue
            if v["status"] == "item_child":
                require(not child_used and last is not None and phase == "choose_option")
                child_used = True
                child_decision = None
                def child_exchange(method, route, decision, action_id, deadline):
                    nonlocal child_decision
                    self.budget()
                    if method == "POST":
                        require(self.child_attempted == 0)
                        self.child_attempted += 1
                    body = self.raw(method, route, decision, action_id, deadline)
                    try:
                        self.budget()
                        # Pure parser reuse at its pinned frozen source; no transport ownership changes.
                        parsed = item_host._decode_response(body)
                        require(parsed.session_nonce == self.nonce)
                        if parsed.status == "ready":
                            child_decision = parsed
                        if method == "POST" and parsed.status == "accepted":
                            require(child_decision is not None and decision == child_decision.decision_id and action_id in child_decision.legal_actions)
                            require(parsed.decision_id == decision and parsed.action_id == action_id)
                            self.child_accepted = 1
                        return body  # Frozen host owns/zeros the returned buffer.
                    except BaseException:
                        if type(body) is bytearray:
                            body[:] = b"\0" * len(body)
                        raise
                result = item_host.run_collection(child_exchange, clock=self.clock, sleep=self.pause)
                self.budget()
                if result.get("status") != "passed":
                    raise Stop("item_child_failed")
                require(result.get("attempted") == 1 and result.get("accepted") == 1 and result.get("reconciled") == 1 and self.child_accepted == 1)
                self.child_reconciled = 1
                continue
            require(v["status"] == "ready" and phase != "proceed")
            legal = v["legal_actions"]
            by_action = {c["action_id"]: c for c in v["candidates"]}
            expected = [c["action_id"] for c in v["candidates"]
                        if c["enabled"] and not c["is_dangerous"] and c["stable_id"] not in reserved]
            require(legal == expected)
            if transition_pending:
                require(last is not None and accepted_transition is not None and
                        event_transition_digest(v) != accepted_transition)
                self.transitions += 1
                transition_pending = False
            selected = legal[0]; candidate = by_action[selected]
            reserved.add(candidate["stable_id"])
            phase = v["phase"]
            last = self.receipt(v, selected)
            accepted_transition = event_transition_digest(v)
            transition_pending = phase == "choose_option"

    def summary(self, status, code=None):
        result = {"schema_version": 1, "status": status, "flow_kind": self.flow,
                  "attempted": self.attempted, "accepted": self.accepted, "reconciled": self.reconciled,
                  "child_attempted": self.child_attempted, "child_accepted": self.child_accepted,
                  "child_reconciled": self.child_reconciled, "option_transitions_observed": self.transitions}
        if code is not None:
            result["code"] = code
        return result


def run_flow(flow, exchange, *, item_host=None, buy_card=True, clock=time.monotonic, sleep=time.sleep):
    """One activation, one 30s outer deadline; caller supplies the pinned item host."""
    if flow not in ("shop", "event") or type(buy_card) is not bool:
        raise ValueError("Invalid flow configuration.")
    controller = Controller(flow, exchange, clock, sleep)
    try:
        if flow == "shop":
            controller.shop(buy_card)
        else:
            if item_host is None:
                raise Stop("item_host_unavailable")
            controller.event(item_host)
        return controller.summary("passed")
    except Stop as error:
        return controller.summary("failed", error.code)
    except InvalidResponse:
        return controller.summary("failed", "invalid_response")
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        raise
    except Exception:
        return controller.summary("failed", "internal_failure")
