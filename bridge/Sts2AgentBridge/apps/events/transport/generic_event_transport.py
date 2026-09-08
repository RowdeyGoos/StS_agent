"""One credential lease and one frozen generic event controller at a fixed loopback endpoint."""
from __future__ import annotations

import json
import math
import socket
import time
from typing import Any, Callable

from components.events.host.generic_event_host import (
    DECISION_ROUTE, ACTION_ROUTE, TransportFailure, run_event, first_legal,
)

_ENDPOINT = ("127.0.0.1", 43117)
_LOWER_HEX = frozenset(b"0123456789abcdef")
_HEADER_CAP = 1024
_BODY_CAP = 65536
_CHUNK_CAP = 1024
_INTERVAL = 0.05
_CONTROLLER_SECONDS = 30.0
_EXCHANGE_SECONDS = 3.0
_IO_SECONDS = 1.0
_RESPONSE_PREFIX = b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: "
_RESPONSE_MIDDLE = b"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nX-Sts2-Native-Diagnostic: "
_RESPONSE_SUFFIX = b"\r\nConnection: close\r\n\r\n"
_DIAGNOSTICS = {
    b"none": "none",
    b"parent_ready": "parent_ready",
    b"parent_unavailable": "parent_unavailable",
    b"parent_waiting": "parent_waiting",
    b"pending_binding_failed": "pending_binding_failed",
    b"pending_ownership": "pending_ownership",
    b"pending_context": "pending_context",
    b"pending_task_failed": "pending_task_failed",
    b"pending_chosen_entry": "pending_chosen_entry",
    b"pending_chosen_task": "pending_chosen_task",
    b"pending_chosen_completion": "pending_chosen_completion",
    b"pending_request_task": "pending_request_task",
    b"pending_screen": "pending_screen",
    b"pending_selectorless_request": "pending_selectorless_request",
    b"pending_overlay": "pending_overlay",
    b"pending_deck": "pending_deck",
    b"pending_offers": "pending_offers",
    b"pending_proceed": "pending_proceed",
    b"prepare_binding": "prepare_binding",
    b"prepare_screen": "prepare_screen",
    b"prepare_external_selector": "prepare_external_selector",
    b"prepare_deck": "prepare_deck",
    b"prepare_foreground": "prepare_foreground",
    b"prepare_family": "prepare_family",
    b"prepare_grid_node": "prepare_grid_node",
    b"prepare_grid_state": "prepare_grid_state",
    b"prepare_holders": "prepare_holders",
    b"prepare_candidates": "prepare_candidates",
    b"prepare_geometry": "prepare_geometry",
    b"prepare_preview_nodes": "prepare_preview_nodes",
    b"prepare_preview_state": "prepare_preview_state",
    b"prepare_confirm": "prepare_confirm",
    b"child_ready": "child_ready",
    b"map_ready": "map_ready",
    b"capture_disposed": "capture_disposed",
    b"capture_exception": "capture_exception",
    b"diagnostic_unavailable": "diagnostic_unavailable",
    b"candidate_expected_null": "candidate_expected_null",
    b"candidate_expected_duplicate": "candidate_expected_duplicate",
    b"candidate_displayed_null": "candidate_displayed_null",
    b"candidate_unexpected_model": "candidate_unexpected_model",
    b"candidate_displayed_duplicate": "candidate_displayed_duplicate",
    b"candidate_model_null": "candidate_model_null",
    b"candidate_card_null": "candidate_card_null",
    b"candidate_hitbox_null": "candidate_hitbox_null",
    b"candidate_highlight_null": "candidate_highlight_null",
    b"candidate_card_type": "candidate_card_type",
    b"candidate_card_invalid": "candidate_card_invalid",
    b"candidate_hitbox_type": "candidate_hitbox_type",
    b"candidate_hitbox_invalid": "candidate_hitbox_invalid",
    b"candidate_highlight_type": "candidate_highlight_type",
    b"candidate_highlight_invalid": "candidate_highlight_invalid",
    b"candidate_material_null": "candidate_material_null",
    b"candidate_material_kind": "candidate_material_kind",
    b"candidate_material_type": "candidate_material_type",
    b"candidate_material_invalid": "candidate_material_invalid",
    b"candidate_stable_key": "candidate_stable_key",
    b"candidate_domain_count": "candidate_domain_count",
    b"candidate_domain_bounds": "candidate_domain_bounds",
    b"candidate_snapshot_count": "candidate_snapshot_count",
    b"candidate_holder_identity": "candidate_holder_identity",
    b"candidate_holder_type": "candidate_holder_type",
    b"candidate_holder_invalid": "candidate_holder_invalid",
    b"candidate_model_identity": "candidate_model_identity",
    b"candidate_card_identity": "candidate_card_identity",
    b"candidate_hitbox_identity": "candidate_hitbox_identity",
    b"candidate_highlight_identity": "candidate_highlight_identity",
    b"candidate_material_identity": "candidate_material_identity",
    b"candidate_key_changed": "candidate_key_changed",
    b"candidate_level_changed": "candidate_level_changed",
    b"candidate_shader_read": "candidate_shader_read",
    b"candidate_highlight_unsettled": "candidate_highlight_unsettled",
    b"candidate_initially_selected": "candidate_initially_selected",
    b"candidate_holder_invisible": "candidate_holder_invisible",
    b"candidate_card_invisible": "candidate_card_invisible",
    b"candidate_hitbox_invisible": "candidate_hitbox_invisible",
    b"candidate_enabled_read": "candidate_enabled_read",
    b"candidate_none_enabled": "candidate_none_enabled",
    b"geometry_candidate_count": "geometry_candidate_count",
    b"geometry_scroll_missing": "geometry_scroll_missing",
    b"geometry_scroll_invalid": "geometry_scroll_invalid",
    b"geometry_scroll_invisible": "geometry_scroll_invisible",
    b"geometry_scroll_size": "geometry_scroll_size",
    b"geometry_scroll_position": "geometry_scroll_position",
    b"geometry_grid_size": "geometry_grid_size",
    b"geometry_card_size": "geometry_card_size",
    b"geometry_y_offset": "geometry_y_offset",
    b"geometry_columns": "geometry_columns",
    b"geometry_scroll_height_mismatch": "geometry_scroll_height_mismatch",
    b"geometry_scroll_position_mismatch": "geometry_scroll_position_mismatch",
    b"geometry_clip_search_invalid": "geometry_clip_search_invalid",
    b"geometry_clip_search_cycle": "geometry_clip_search_cycle",
    b"geometry_clip_search_depth": "geometry_clip_search_depth",
    b"geometry_clip_missing": "geometry_clip_missing",
    b"geometry_clip_rect": "geometry_clip_rect",
    b"geometry_canvas_invalid": "geometry_canvas_invalid",
    b"geometry_chain_invalid": "geometry_chain_invalid",
    b"geometry_chain_non_canvas": "geometry_chain_non_canvas",
    b"geometry_chain_cycle": "geometry_chain_cycle",
    b"geometry_chain_depth": "geometry_chain_depth",
    b"geometry_chain_unreached": "geometry_chain_unreached",
    b"geometry_top_level": "geometry_top_level",
    b"geometry_canvas_mismatch": "geometry_canvas_mismatch",
    b"geometry_transform": "geometry_transform",
    b"geometry_node_rect": "geometry_node_rect",
    b"geometry_control_rect": "geometry_control_rect",
    b"geometry_clip_changed": "geometry_clip_changed",
    b"geometry_parent_changed": "geometry_parent_changed",
    b"geometry_transform_changed": "geometry_transform_changed",
    b"geometry_node_clip_changed": "geometry_node_clip_changed",
    b"geometry_rect_changed": "geometry_rect_changed",
    b"geometry_mask_count": "geometry_mask_count",
    b"geometry_initially_selected": "geometry_initially_selected",
    b"geometry_candidate_invisible": "geometry_candidate_invisible",
    b"geometry_none_eligible": "geometry_none_eligible",
}
_BODY_PREFIX = b'{"decision_id":"'
_BODY_MIDDLE = b'","action_id":"'
_BODY_SUFFIX = b'"}'


def _zero(value: bytearray) -> None:
    value[:] = b"\0" * len(value)


def _failure(diagnostic: str = "none") -> dict[str, object]:
    return {"schema_version": 1, "status": "failed", "code": "internal_failure",
            **dict.fromkeys(("parent_attempted", "parent_accepted", "parent_reconciled", "child_episodes",
                             "child_attempted", "child_accepted", "child_reconciled", "total_attempted", "reads"), 0),
            "effects": "none_attempted", "completed_card_children": 0, "completed_item_children": 0, "last_response_diagnostic": diagnostic}


def _canonical_credential(value: object) -> bool:
    return type(value) is bytearray and len(value) == 64 and all(c in _LOWER_HEX for c in value)


def _identifier(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _parent_action(value: object) -> bool:
    return type(value) is str and value in tuple("choose:" + str(i) for i in range(8))


def _child_action(value: object) -> bool:
    return type(value) is str and (value in ("preview", "confirm") or value in tuple("select:" + str(i) for i in range(64)) or value in tuple("collect:" + str(i) for i in range(256)))


def _build_request(method: str, route: str, body: bytearray | None,
                   credential: bytearray) -> bytearray:
    request = bytearray()
    try:
        if type(method) is not str or type(route) is not str or not _canonical_credential(credential):
            raise ValueError()
        fields: dict[str, Any] = {}
        child = None
        if method == "GET" and route == DECISION_ROUTE:
            if body is not None:
                raise ValueError()
        elif method == "POST" and route == ACTION_ROUTE:
            if type(body) is not bytearray or not 1 <= len(body) <= 512:
                raise ValueError()
            fields = json.loads(body)
            if (type(fields) is not dict or list(fields) != ["decision_id", "action_id", "child"] or
                    not _identifier(fields["decision_id"]) or
                    body != json.dumps(fields, separators=(",", ":")).encode("ascii")):
                raise ValueError()
            child = fields["child"]
            if child is None:
                if not _parent_action(fields["action_id"]):
                    raise ValueError()
            elif (type(child) is not dict or list(child) != ["ordinal", "parent_decision_id", "parent_action_id"] or
                  type(child["ordinal"]) is not int or not 1 <= child["ordinal"] <= 4 or
                  not _identifier(child["parent_decision_id"]) or not _parent_action(child["parent_action_id"]) or
                  not _child_action(fields["action_id"])):
                raise ValueError()
        else:
            raise ValueError()
        request.extend((method + " " + route + " HTTP/1.1\r\n").encode("ascii"))
        request.extend(b"Host: 127.0.0.1:43117\r\nAuthorization: Bearer ")
        request.extend(credential)
        request.extend(b"\r\nAccept: application/json\r\n")
        if method == "POST":
            request.extend(("X-Sts2-Decision-Id: " + fields["decision_id"] + "\r\nX-Sts2-Action-Id: " + fields["action_id"] + "\r\n").encode("ascii"))
            if child is not None:
                request.extend(("X-Sts2-Child-Ordinal: " + str(child["ordinal"]) + "\r\nX-Sts2-Parent-Decision-Id: " + child["parent_decision_id"] + "\r\nX-Sts2-Parent-Action-Id: " + child["parent_action_id"] + "\r\n").encode("ascii"))
        request.extend(b"Connection: close\r\n\r\n")
        if len(request) > _HEADER_CAP:
            raise ValueError()
        return request
    except BaseException:
        _zero(request)
        raise
    finally:
        if type(body) is bytearray:
            _zero(body)


class _MonotonicClock:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._last: float | None = None

    def __call__(self) -> float:
        value = self._clock()
        if (type(value) not in (int, float) or not math.isfinite(value) or
                self._last is not None and value < self._last):
            raise TransportFailure() from None
        self._last = float(value)
        return self._last


def _remaining(clock: Callable[[], float], deadline: float) -> float:
    value = deadline - clock()
    if not math.isfinite(value) or value <= 0:
        raise TransportFailure() from None
    return value


def _timeout(client: Any, clock: Callable[[], float], deadline: float) -> None:
    client.settimeout(min(_IO_SECONDS, _remaining(clock, deadline)))
    _remaining(clock, deadline)


def _parse_header(value: bytearray, offset: int) -> tuple[int, str]:
    start = len(_RESPONSE_PREFIX)
    end = value.find(_RESPONSE_MIDDLE, start, offset)
    diagnostic_end = offset - len(_RESPONSE_SUFFIX)
    diagnostic_start = end + len(_RESPONSE_MIDDLE)
    if (offset > _HEADER_CAP or not value.startswith(_RESPONSE_PREFIX) or
            not value.endswith(_RESPONSE_SUFFIX, 0, offset) or not 1 <= end - start <= 5 or
            end - start > 1 and value[start] == 48 or
            not 1 <= diagnostic_end - diagnostic_start <= 33):
        raise TransportFailure() from None
    diagnostic = _DIAGNOSTICS.get(bytes(value[diagnostic_start:diagnostic_end]))
    if diagnostic is None:
        raise TransportFailure() from None
    count = 0
    for index in range(start, end):
        c = value[index]
        if not 48 <= c <= 57:
            raise TransportFailure() from None
        count = count * 10 + c - 48
    if not 1 <= count <= _BODY_CAP:
        raise TransportFailure() from None
    return offset + count, diagnostic


def _new_socket() -> socket.socket:
    return socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def _perform_exchange(request: bytearray, factory: Callable[[], Any],
                      clock: Callable[[], float], host_deadline: float) -> tuple[bytearray, str]:
    response, chunk, result = bytearray(), bytearray(_CHUNK_CAP), bytearray()
    client: Any | None = None
    transferred = False
    failure_active = False
    try:
        now = clock()
        deadline = min(host_deadline, now + _EXCHANGE_SECONDS)
        _remaining(clock, deadline)
        client = factory()
        _timeout(client, clock, deadline)
        client.connect(_ENDPOINT)
        _remaining(clock, deadline)
        _timeout(client, clock, deadline)
        client.sendall(request)
        _remaining(clock, deadline)
        _timeout(client, clock, deadline)
        client.shutdown(socket.SHUT_WR)
        _remaining(clock, deadline)
        offset: int | None = None
        expected: int | None = None
        diagnostic = "none"
        while True:
            _timeout(client, clock, deadline)
            count = client.recv_into(chunk, _CHUNK_CAP)
            _remaining(clock, deadline)
            if type(count) is not int or not 0 <= count <= _CHUNK_CAP:
                raise TransportFailure() from None
            if count == 0:
                break
            if len(response) + count > _HEADER_CAP + _BODY_CAP:
                raise TransportFailure() from None
            view = memoryview(chunk)[:count]
            try:
                response.extend(view)
            finally:
                view.release()
                _zero(chunk)
            if offset is None:
                separator = response.find(b"\r\n\r\n")
                if separator >= 0:
                    offset = separator + 4
                    expected, diagnostic = _parse_header(response, offset)
                elif len(response) >= _HEADER_CAP:
                    raise TransportFailure() from None
            if expected is not None and len(response) > expected:
                raise TransportFailure() from None
        if offset is None or expected is None or len(response) != expected:
            raise TransportFailure() from None
        closing, client = client, None
        closing.close()
        _remaining(clock, deadline)
        view = memoryview(response)[offset:]
        try:
            result.extend(view)
        finally:
            view.release()
        transferred = True
        return result, diagnostic
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        failure_active = True
        raise
    except TransportFailure:
        failure_active = True
        raise
    except (OSError, TimeoutError):
        failure_active = True
        raise TransportFailure() from None
    except Exception:
        failure_active = True
        raise
    finally:
        _zero(request)
        _zero(response)
        _zero(chunk)
        if not transferred:
            _zero(result)
        if client is not None:
            try:
                client.close()
            except (KeyboardInterrupt, SystemExit, GeneratorExit):
                _zero(result)
                raise
            except (OSError, TimeoutError):
                if not failure_active:
                    _zero(result)
                    raise TransportFailure() from None
            except Exception:
                if not failure_active:
                    _zero(result)
                    raise


class _AuthenticatedExchange:
    def __init__(self, credential: bytearray, factory: Callable[[], Any],
                 clock: Callable[[], float], sleep: Callable[[float], None]) -> None:
        self._credential, self._factory, self._clock, self._sleep = credential, factory, clock, sleep
        now = clock()
        self._deadline = now + _CONTROLLER_SECONDS
        if not math.isfinite(self._deadline) or self._deadline <= now:
            raise TransportFailure() from None
        self._not_before = now
        self._failed = False
        self._active = False
        self.last_response_diagnostic = "none"

    def __call__(self, method: str, route: str, body: bytearray | None) -> bytearray:
        request = bytearray()
        try:
            if self._failed or self._active:
                raise TransportFailure() from None
            self._active = True
            request = _build_request(method, route, body, self._credential)
            now = self._clock()
            if now >= self._deadline:
                raise TransportFailure() from None
            if now < self._not_before:
                if self._not_before >= self._deadline:
                    raise TransportFailure() from None
                self._sleep(self._not_before - now)
                now = self._clock()
                if now < self._not_before or now >= self._deadline:
                    raise TransportFailure() from None
            self._not_before = now + _INTERVAL
            result, diagnostic = _perform_exchange(request, self._factory, self._clock, self._deadline)
            if self._failed:
                _zero(result)
                raise TransportFailure() from None
            self.last_response_diagnostic = diagnostic
            return result
        except BaseException:
            self._failed = True
            raise
        finally:
            self._active = False
            _zero(request)
            if type(body) is bytearray:
                _zero(body)


class _LivePolicy:
    def __init__(self):
        self._initial = True

    def __call__(self, view):
        if self._initial:
            self._initial = False
            if (view.kind != "parent" or len(view.payload["candidates"]) != 2 or
                    "choose:0" not in view.payload["legal_actions"]):
                raise ValueError("Initial campaign options unavailable.")
            return "choose:0"
        return first_legal(view)


def _run_with_socket_factory(credential: bytearray,
                             factory: Callable[[], Any], *, clock: Callable[[], float],
                             sleep: Callable[[float], None], provider: Callable | None = None) -> dict[str, object]:
    exchange: _AuthenticatedExchange | None = None
    try:
        if not _canonical_credential(credential):
            return _failure()
        timer = _MonotonicClock(clock)
        exchange = _AuthenticatedExchange(credential, factory, timer, sleep)
        return {**run_event(exchange, provider=_LivePolicy() if provider is None else provider, clock=timer, sleep=sleep),
                "last_response_diagnostic": exchange.last_response_diagnostic}
    except Exception:
        return _failure(exchange.last_response_diagnostic if exchange is not None else "none")
    finally:
        if type(credential) is bytearray:
            _zero(credential)


def run_authenticated_generic_event(credential: bytearray, *,
                                     clock: Callable[[], float] = time.monotonic,
                                     sleep: Callable[[float], None] = time.sleep) -> dict[str, object]:
    """Run the frozen host once; the fixed campaign policy selects the initial option."""
    return _run_with_socket_factory(credential, _new_socket, clock=clock, sleep=sleep)
