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
    prefix, maximum = ("buy:relic:" if value.startswith("buy:relic:") else "buy:potion:" if value.startswith("buy:potion:") else "buy:card:", 31) if flow == "shop" else ("choose:", 7)
    if flow=="shop" and value.startswith("discard:"):prefix,maximum="discard:",7
    if flow=="shop" and value.startswith("remove:"):prefix,maximum="remove:",511
    suffix = value[len(prefix):]
    return value.startswith(prefix) and 1 <= len(suffix) <= (3 if maximum==511 else 2) and suffix.isascii() and suffix.isdecimal() and str(int(suffix)) == suffix and int(suffix) <= maximum


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
        require(value.get("protocol") == "room_flows_v1" and value.get("version") == ("shop_v6" if flow=="shop" else flow + "_v1") and value.get("flow_kind") == flow)
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
    keys(v, COMMON + ("phase", "decision_id", "player", "offers", "removal_candidates", "legal_actions", "prior_results"))
    require(v["status"] in ("ready", "waiting", "unsupported", "complete"))
    keys(v["player"], ("gold", "deck_count", "potion_slots", "relics"))
    slots=v["player"]["potion_slots"]
    relics=v["player"]["relics"]
    require(type(relics) is list and len(relics)<=128 and all(stable_key(r) for r in relics))
    require(type(slots) is list and len(slots)<=8 and all(p is None or stable_key(p) for p in slots))
    require(integer(v["player"]["gold"]) and integer(v["player"]["deck_count"], 512))
    require(type(v["offers"]) is list and len(v["offers"]) <= 32)
    require(type(v["legal_actions"]) is list and len(v["legal_actions"]) <= 105)
    require(type(v["prior_results"]) is list and len(v["prior_results"]) <= 1)
    for p in v["prior_results"]:
        keys(p, ("flow_kind", "session_nonce", "parent_ordinal", "decision_id", "action_id", "kind", "result"))
        require(p["flow_kind"] == "shop" and p["session_nonce"] == v["session_nonce"])
        require(type(p["parent_ordinal"]) is int and p["parent_ordinal"] == 1)
        require(hex_id(p["decision_id"], 64) and action("shop", p["action_id"]) and p["result"] == "reconciled")
        require(p["kind"] == ("leave" if p["action_id"] == "leave" else "inventory_close" if p["action_id"] == "inventory:close" else "purchase_potion" if p["action_id"].startswith("buy:potion:") else "discard_potion" if p["action_id"].startswith("discard:") else "remove_card" if p["action_id"].startswith("remove:") else "purchase_relic" if p["action_id"].startswith("buy:relic:") else "purchase_card"))
    if v["status"] != "ready":
        require(v["decision_id"] == "" and v["offers"] == [] and v["removal_candidates"] == [] and v["legal_actions"] == [])
        if v["status"] != "complete":
            require(v["player"] == {"gold": 0, "deck_count": 0, "potion_slots": [], "relics": []})
        phases = {"waiting": ("unknown", "purchase_waiting", "close_waiting", "leave_waiting"), "unsupported": ("unknown",), "complete": ("complete",)}
        require(v["phase"] in phases[v["status"]])
        if v["status"] == "complete":
            require(len(v["prior_results"]) == 1 and v["prior_results"][0]["action_id"] == "leave")
        return
    require(v["phase"] in ("inventory_browse", "room_ready_to_leave") and hex_id(v["decision_id"], 64))
    last = -1
    possible = []
    for o in v["offers"]:
        keys(o, ("slot", "kind", "key", "displayed_price", "affordable", "enabled", "supported", "potion_capacity_gain"))
        require(integer(o["slot"], 31) and o["slot"] > last and o["kind"] in ("card", "relic", "potion", "removal", "unknown") and stable_key(o["key"]))
        require(integer(o["displayed_price"]) and all(type(o[k]) is bool for k in ("affordable", "enabled", "supported")))
        require(o["affordable"] == (v["player"]["gold"] >= o["displayed_price"]) and (not o["supported"] or o["kind"] in ("card", "potion", "relic", "removal")))
        require(type(o["potion_capacity_gain"]) is int and o["potion_capacity_gain"] in (0,2))
        require(o["potion_capacity_gain"]==0 or (o["kind"]=="relic" and o["key"]=="POTION_BELT" and o["supported"]))
        if shop_offer_legal(o,v["player"]):
            possible.append("buy:" + o["kind"] + ":" + str(o["slot"]))
        last = o["slot"]
    require(type(v["removal_candidates"]) is list and len(v["removal_candidates"])<=64)
    removals=[o for o in v["offers"] if o["kind"]=="removal"]
    require(len(removals)<=1)
    require(not v["removal_candidates"] or (removals and removals[0]["supported"]))
    last=-1
    for c in v["removal_candidates"]:
        keys(c,("deck_slot","key","upgrade_level"))
        require(integer(c["deck_slot"],511) and last<c["deck_slot"]<v["player"]["deck_count"] and stable_key(c["key"]) and integer(c["upgrade_level"]))
        last=c["deck_slot"]
    possible+=shop_removals(v)+shop_discards(v)
    if v["phase"] == "room_ready_to_leave":
        require(v["offers"] == [] and v["removal_candidates"] == [] and v["legal_actions"] == ["leave"])
    else:
        require(v["legal_actions"] in (possible + ["inventory:close"], ["inventory:close"]))
    require(v["decision_id"] == shop_digest(v))


def shop_offer_legal(o, player):
    return (o["kind"]!="removal" and o["supported"] and o["enabled"] and o["affordable"]
            and (o["kind"]!="potion" or None in player["potion_slots"])
            and (o["kind"]!="relic" or (len(player["relics"])<128 and o["key"] not in player["relics"]
                 and len(player["potion_slots"])+o["potion_capacity_gain"]<=8)))


def shop_discards(v):
    actions=[a for a in v['legal_actions'] if type(a) is str and a.startswith('discard:')]
    slots=v['player']['potion_slots']
    require(len(actions)<=8 and actions==sorted(set(actions)))
    for a in actions:require(action('shop',a) and slots and None not in slots and int(a[-1])<len(slots))
    return actions


def shop_removals(v):
    offers=[o for o in v["offers"] if o["kind"]=="removal" and o["supported"] and o["enabled"] and o["affordable"]]
    return ["remove:"+str(c["deck_slot"]) for c in v["removal_candidates"]] if len(offers)==1 else []


def shop_digest(v: dict[str, Any]) -> str:
    parts = []
    def s(x: str) -> None:
        parts.extend((str(len(x)), ":", x, ";"))
    def n(x: int) -> None:
        parts.extend((str(x), ";"))
    for x in ("shop_v6", "shop", v["session_nonce"]):
        s(x)
    n(1); s(v["phase"]); n(v["player"]["gold"]); n(v["player"]["deck_count"])
    n(len(v["player"]["potion_slots"]))
    for potion in v["player"]["potion_slots"]: s(potion or "")
    n(len(v["player"]["relics"]))
    for relic in v["player"]["relics"]: s(relic)
    n(len(v["offers"]))
    for o in v["offers"]:
        n(o["slot"]); s(o["kind"]); s(o["key"]); n(o["displayed_price"])
        for key in ("affordable", "enabled", "supported"):
            n(int(o[key]))
        n(o["potion_capacity_gain"])
    n(len(v["removal_candidates"]))
    for c in v["removal_candidates"]: n(c["deck_slot"]); s(c["key"]); n(c["upgrade_level"])
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
        if self.attempted + self.child_attempted > (18 if self.flow=="shop" else 13):
            raise Stop("action_limit_reached")
        return self.exchange(method, route, decision, action_id, min(deadline, self.deadline))

    def call(self, method="GET", decision=None, action_id=None):
        body = None
        try:
            self.budget()
            if method == "POST":
                if self.attempted >= (18 if self.flow == "shop" else 12):
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

    def shop(self, buy_card, max_purchases, gold_reserve, purchase_policy, removal_policy, potion_policy):
        pending, completed, bought, closed = None, None, 0, False
        discarded_slots=set()
        removal_done=False
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
                purchases = ["buy:" + o["kind"] + ":" + str(o["slot"]) for o in v["offers"]
                             if shop_offer_legal(o,v["player"])]
                require(v["legal_actions"] == ([] if bought>=8 else purchases+shop_removals(v)+shop_discards(v)) + ["inventory:close"])
                purchases=["buy:"+o["kind"]+":"+str(o["slot"]) for o in v["offers"]
                           if "buy:"+o["kind"]+":"+str(o["slot"]) in purchases
                           and (purchase_policy=="all" or (purchase_policy=="cards-and-potions" and o["kind"] in ("card","potion")) or purchase_policy==o["kind"]+"s")
                           and v["player"]["gold"]-o["displayed_price"]>=gold_reserve]
                selected = purchases[0] if buy_card and bought<max_purchases and purchases else "inventory:close"
                removals=shop_removals(v)
                removal_offer=next((o for o in v["offers"] if o["kind"]=="removal"),None)
                if buy_card and bought<max_purchases and removal_policy=="first" and not removal_done and removals and v["player"]["gold"]-removal_offer["displayed_price"]>=gold_reserve:
                    selected=removals[0];removal_done=True;bought+=1
                if selected=="inventory:close" and buy_card and bought<max_purchases and potion_policy=="replace-first" and purchase_policy in ("potions","cards-and-potions","all"):
                    affordable_potion=any(o['kind']=='potion' and o['supported'] and o['enabled'] and o['affordable'] and v['player']['gold']-o['displayed_price']>=gold_reserve for o in v['offers'])
                    discards=[a for a in shop_discards(v) if int(a[-1]) not in discarded_slots]
                    if affordable_potion and discards:selected=discards[0];discarded_slots.add(int(selected[-1]))
                if selected.startswith("buy:"):
                    bought+=1
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


def run_flow(flow, exchange, *, item_host=None, buy_card=True, max_purchases=1, gold_reserve=0, purchase_policy="cards", removal_policy="skip", potion_policy="skip-full", clock=time.monotonic, sleep=time.sleep):
    """One activation, one 30s outer deadline; caller supplies the pinned item host."""
    if flow not in ("shop", "event") or type(buy_card) is not bool or type(max_purchases) is not int or not 0<=max_purchases<=8 or type(gold_reserve) is not int or not 0<=gold_reserve<=2147483647 or purchase_policy not in ("cards","potions","cards-and-potions","relics","all") or removal_policy not in ("skip","first") or potion_policy not in ("skip-full","replace-first"):
        raise ValueError("Invalid flow configuration.")
    controller = Controller(flow, exchange, clock, sleep)
    try:
        if flow == "shop":
            controller.shop(buy_card, max_purchases, gold_reserve, purchase_policy, removal_policy, potion_policy)
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
