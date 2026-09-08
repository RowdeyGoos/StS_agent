"""One bounded authenticated transport for every bridge capability; no retries."""
from __future__ import annotations

import json
import re
import socket
import time

ROUTES = {
    "/probe/v0/health": False, "/probe/v0/manifest": False, "/probe/v0/public/screen": False,
    **{f"/probe/v0/public/{family}-{operation}": operation == "action"
       for family in ("combat", "reward", "map", "room") for operation in ("decision", "action")},
    "/probe/item-v1/public/item-decision": False, "/probe/item-v1/public/item-action": True,
    "/probe/room-flows-v1/public/decision": False, "/probe/room-flows-v1/public/action": True,
    "/card-selection-v1/parent": False, "/card-selection-v1/parent/action": True,
    "/card-selection-v1/child": False, "/card-selection-v1/child/action": True,
    "/probe/generic-event-v7/public/decision": False, "/probe/generic-event-v7/public/action": True,
}


def require(value, code):
    if not value:
        raise ValueError(code)


def build_request(method: str, route: str, body: bytearray | None, token: bytearray) -> bytearray:
    require(route in ROUTES and method == ("POST" if ROUTES[route] else "GET"), "route")
    require(re.fullmatch(b"[0-9a-f]{64}", token), "credential")
    fields = ""
    if method == "POST":
        require(isinstance(body, (bytes, bytearray)) and 1 <= len(body) <= 1024, "action_body")
        value = json.loads(body)
        expected = {"decision_id", "action_id"}
        event = route == "/probe/generic-event-v7/public/action"
        if event:
            expected.add("child")
        require(type(value) is dict and set(value) == expected, "action_fields")
        require(type(value["decision_id"]) is str and re.fullmatch("[0-9a-f]{64}", value["decision_id"]), "decision")
        require(type(value["action_id"]) is str and (re.fullmatch(r"[a-z_]+(?::[0-9]{1,3}){0,2}", value["action_id"]) or
                route == "/probe/room-flows-v1/public/action" and re.fullmatch(r"(?:buy:card:(?:[0-9]|[12][0-9]|3[01])|inventory:close)", value["action_id"])), "action")
        fields = "X-Sts2-Decision-Id: " + value["decision_id"] + "\r\nX-Sts2-Action-Id: " + value["action_id"] + "\r\n"
        child = value.get("child")
        if child is not None:
            require(event and type(child) is dict and set(child) == {"ordinal", "parent_decision_id", "parent_action_id"}, "child")
            require(type(child["ordinal"]) is int and 1 <= child["ordinal"] <= 4, "ordinal")
            require(type(child["parent_decision_id"]) is str and re.fullmatch("[0-9a-f]{64}", child["parent_decision_id"]), "parent_decision")
            require(type(child["parent_action_id"]) is str and re.fullmatch("choose:[0-7]", child["parent_action_id"]), "parent_action")
            fields += f"X-Sts2-Child-Ordinal: {child['ordinal']}\r\nX-Sts2-Parent-Decision-Id: {child['parent_decision_id']}\r\nX-Sts2-Parent-Action-Id: {child['parent_action_id']}\r\n"
    else:
        require(body is None, "read_body")
    result = bytearray((method + " " + route + " HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer ").encode())
    result.extend(token)
    result.extend(("\r\nAccept: application/json\r\n" + fields + "Connection: close\r\n\r\n").encode("ascii"))
    require(len(result) <= 4096, "request_limit")
    return result


def parse_response(response: bytearray, *, event: bool) -> bytearray:
    offset = response.find(b"\r\n\r\n")
    require(0 < offset < 1024, "response_header")
    lines = response[:offset].split(b"\r\n")
    require(len(lines) == (7 if event else 6) and lines[0] == b"HTTP/1.1 200 OK" and
            lines[1] == b"Content-Type: application/json; charset=utf-8" and
            lines[3:5] == [b"Cache-Control: no-store", b"X-Content-Type-Options: nosniff"] and
            lines[-1] == b"Connection: close", "response_shape")
    require(lines[2].startswith(b"Content-Length: "), "response_length")
    count = lines[2][16:]
    require(re.fullmatch(b"[1-9][0-9]{0,4}", count) and int(count) <= 65536 and len(response) - offset - 4 == int(count), "response_length")
    if event:
        require(re.fullmatch(b"X-Sts2-Native-Diagnostic: [a-z_]{1,33}", lines[5]), "diagnostic")
    result = response[offset + 4:]
    try:
        json.loads(result)
        return result
    except BaseException:
        result[:] = b"\0" * len(result)
        raise


class BridgeClient:
    def __init__(self, credential: bytearray, *, connector=None, clock=time.monotonic):
        require(type(credential) is bytearray and re.fullmatch(b"[0-9a-f]{64}", credential), "credential")
        self._credential, self._clock = credential, clock
        self._connector = connector or (lambda: socket.create_connection(("127.0.0.1", 43117), timeout=2))
        self._failed, self._requests = False, 0

    def exchange(self, method, route, body=None, *, deadline=None):
        require(not self._failed and self._requests < 16896, "client_stopped")
        self._requests += 1
        request, response = bytearray(), bytearray()
        client = None
        try:
            request = build_request(method, route, body, self._credential)
            until = min(self._clock() + 2, deadline if deadline is not None else float("inf"))
            client = self._connector()
            client.settimeout(max(0.001, until - self._clock()))
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)
            while True:
                remaining = until - self._clock()
                require(remaining > 0, "transport_timeout")
                client.settimeout(remaining)
                chunk = client.recv(8192)
                if not chunk:
                    break
                response.extend(chunk)
                require(len(response) <= 66560, "response_limit")
            return parse_response(response, event=route.startswith("/probe/generic-event-v7/"))
        except BaseException:
            self._failed = True
            raise
        finally:
            request[:] = b"\0" * len(request)
            response[:] = b"\0" * len(response)
            if client is not None:
                try:
                    client.close()
                except BaseException:
                    self._failed = True
                    raise

    def item_exchange(self, method, route, decision, action, deadline):
        body = None if method == "GET" else bytearray(json.dumps({"decision_id": decision, "action_id": action}, separators=(",", ":")).encode())
        try:
            return self.exchange(method, route, body, deadline=deadline)
        finally:
            if body is not None:
                body[:] = b"\0" * len(body)

    def close(self):
        self._failed = True
        self._credential[:] = b"\0" * len(self._credential)
