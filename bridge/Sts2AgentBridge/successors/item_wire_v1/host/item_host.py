"""Strict, connector-free item_probe_v1 parser and one-action controller."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Callable, Optional


_PROTOCOL = "item_probe_v1"
_VERSION = "item_v1"
_GET_ROUTE = "/probe/item-v1/public/item-decision"
_POST_ROUTE = "/probe/item-v1/public/item-action"
_DEADLINE_SECONDS = 15.0
_POLL_SECONDS = 0.1
_MAX_READS = 256
_MAX_BODY_BYTES = 4096
_MAX_OFFERS = 8
_MAX_POTION_SLOTS = 8
_MAX_REWARD_INDEX = 255
_MAX_KEY_LENGTH = 128

_COMMON_KEYS = (
    "schema_version",
    "protocol",
    "version",
    "session_nonce",
    "surface_ordinal",
    "status",
)


class TransportFailure(Exception):
    """The sole exchange exception classified as a transport failure."""


class _InvalidResponse(Exception):
    pass


class _Stop(Exception):
    def __init__(self, code: str) -> None:
        super().__init__()
        self.code = code


class _ObjectPairs(list[tuple[str, Any]]):
    pass


@dataclass(frozen=True)
class _Offer:
    index: int
    kind: str
    key: str
    enabled: bool


@dataclass(frozen=True)
class _Response:
    status: str
    session_nonce: str
    decision_id: Optional[str] = None
    action_id: Optional[str] = None
    offers: tuple[_Offer, ...] = ()
    potion_slots: tuple[Optional[str], ...] = ()
    legal_actions: tuple[str, ...] = ()
    offer_index: Optional[int] = None
    kind: Optional[str] = None
    key: Optional[str] = None
    result: Optional[str] = None
    code: Optional[str] = None


def _is_ascii(value: str) -> bool:
    return all(ord(character) < 128 for character in value)


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        type(value) is str
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_stable_key(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= _MAX_KEY_LENGTH
        and all(
            "A" <= character <= "Z"
            or "a" <= character <= "z"
            or "0" <= character <= "9"
            or character == "_"
            for character in value
        )
    )


def _convert_json(value: Any) -> Any:
    if type(value) is _ObjectPairs:
        result: dict[str, Any] = {}
        for key, item in value:
            if type(key) is not str or key in result:
                raise _InvalidResponse()
            result[key] = _convert_json(item)
        return result
    if type(value) is list:
        return [_convert_json(item) for item in value]
    if type(value) in (str, int, bool) or value is None:
        return value
    raise _InvalidResponse()


def _walk_ascii(value: Any) -> None:
    if type(value) is dict:
        for key, item in value.items():
            if not _is_ascii(key):
                raise _InvalidResponse()
            _walk_ascii(item)
        return
    if type(value) is list:
        for item in value:
            _walk_ascii(item)
        return
    if type(value) is str and not _is_ascii(value):
        raise _InvalidResponse()


def _decode_response(body: bytearray) -> _Response:
    if len(body) > _MAX_BODY_BYTES:
        raise _InvalidResponse()
    raw = bytes(body)
    if any(value >= 128 for value in raw):
        raise _InvalidResponse()
    try:
        decoded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_ObjectPairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(_InvalidResponse()),
        )
        value = _convert_json(decoded)
        _walk_ascii(value)
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except _InvalidResponse:
        raise
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise _InvalidResponse() from None
    if canonical != raw or type(value) is not dict:
        raise _InvalidResponse()
    return _validate_response(value)


def _exact_keys(value: dict[str, Any], suffix: tuple[str, ...] = ()) -> None:
    if tuple(value) != _COMMON_KEYS + suffix:
        raise _InvalidResponse()


def _validate_common(value: dict[str, Any]) -> tuple[str, str]:
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise _InvalidResponse()
    if type(value.get("protocol")) is not str or value["protocol"] != _PROTOCOL:
        raise _InvalidResponse()
    if type(value.get("version")) is not str or value["version"] != _VERSION:
        raise _InvalidResponse()
    nonce = value.get("session_nonce")
    if not _is_lower_hex(nonce, 32):
        raise _InvalidResponse()
    if type(value.get("surface_ordinal")) is not int or value["surface_ordinal"] != 1:
        raise _InvalidResponse()
    status = value.get("status")
    if type(status) is not str:
        raise _InvalidResponse()
    return nonce, status


def _parse_action(value: object) -> Optional[int]:
    if type(value) is not str or not value.startswith("collect:"):
        return None
    digits = value[8:]
    if not digits or (len(digits) > 1 and digits[0] == "0"):
        return None
    if not all("0" <= character <= "9" for character in digits):
        return None
    index = int(digits)
    if index > _MAX_REWARD_INDEX or value != f"collect:{index}":
        return None
    return index


def _append_string(parts: list[str], value: str) -> None:
    parts.extend((str(len(value)), ":", value, ";"))


def _append_integer(parts: list[str], value: int) -> None:
    parts.extend((str(value), ";"))


def _decision_digest(
    nonce: str,
    offers: tuple[_Offer, ...],
    potion_slots: tuple[Optional[str], ...],
    legal_actions: tuple[str, ...],
) -> str:
    parts: list[str] = []
    _append_string(parts, _VERSION)
    _append_string(parts, nonce)
    _append_integer(parts, 1)
    _append_integer(parts, len(offers))
    for offer in offers:
        _append_integer(parts, offer.index)
        _append_string(parts, offer.kind)
        _append_string(parts, offer.key)
        _append_integer(parts, 1 if offer.enabled else 0)
    _append_integer(parts, len(potion_slots))
    for slot in potion_slots:
        _append_integer(parts, 0 if slot is None else 1)
        if slot is not None:
            _append_string(parts, slot)
    _append_integer(parts, len(legal_actions))
    for action in legal_actions:
        _append_string(parts, action)
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()


def _validate_ready(value: dict[str, Any], nonce: str) -> _Response:
    _exact_keys(value, ("decision_id", "offers", "potion_slots", "legal_actions"))
    decision_id = value["decision_id"]
    if not _is_lower_hex(decision_id, 64):
        raise _InvalidResponse()
    raw_offers = value["offers"]
    if type(raw_offers) is not list or not 1 <= len(raw_offers) <= _MAX_OFFERS:
        raise _InvalidResponse()
    offers: list[_Offer] = []
    previous = -1
    for raw_offer in raw_offers:
        if type(raw_offer) is not dict or tuple(raw_offer) != ("index", "kind", "key", "enabled"):
            raise _InvalidResponse()
        index = raw_offer["index"]
        kind = raw_offer["kind"]
        key = raw_offer["key"]
        enabled = raw_offer["enabled"]
        if type(index) is not int or not 0 <= index <= _MAX_REWARD_INDEX or index <= previous:
            raise _InvalidResponse()
        if type(kind) is not str or kind not in ("potion", "relic"):
            raise _InvalidResponse()
        if not _is_stable_key(key) or type(enabled) is not bool:
            raise _InvalidResponse()
        offers.append(_Offer(index, kind, key, enabled))
        previous = index

    raw_slots = value["potion_slots"]
    if type(raw_slots) is not list or len(raw_slots) > _MAX_POTION_SLOTS:
        raise _InvalidResponse()
    slots: list[Optional[str]] = []
    for slot in raw_slots:
        if slot is not None and not _is_stable_key(slot):
            raise _InvalidResponse()
        slots.append(slot)

    raw_actions = value["legal_actions"]
    if type(raw_actions) is not list or not 1 <= len(raw_actions) <= _MAX_OFFERS:
        raise _InvalidResponse()
    actions: list[str] = []
    for action in raw_actions:
        if _parse_action(action) is None:
            raise _InvalidResponse()
        actions.append(action)

    has_empty_slot = any(slot is None for slot in slots)
    expected_actions = [
        f"collect:{offer.index}"
        for offer in offers
        if offer.enabled and (offer.kind == "relic" or has_empty_slot)
    ]
    if actions != expected_actions:
        raise _InvalidResponse()
    frozen_offers = tuple(offers)
    frozen_slots = tuple(slots)
    frozen_actions = tuple(actions)
    if decision_id != _decision_digest(nonce, frozen_offers, frozen_slots, frozen_actions):
        raise _InvalidResponse()
    return _Response(
        "ready",
        nonce,
        decision_id=decision_id,
        offers=frozen_offers,
        potion_slots=frozen_slots,
        legal_actions=frozen_actions,
    )


def _validate_response(value: dict[str, Any]) -> _Response:
    nonce, status = _validate_common(value)
    if status in ("waiting", "unsupported", "rejected", "uncertain"):
        _exact_keys(value)
        return _Response(status, nonce)
    if status == "ready":
        return _validate_ready(value, nonce)
    if status == "accepted":
        _exact_keys(value, ("decision_id", "action_id"))
        if not _is_lower_hex(value["decision_id"], 64) or _parse_action(value["action_id"]) is None:
            raise _InvalidResponse()
        return _Response(
            status,
            nonce,
            decision_id=value["decision_id"],
            action_id=value["action_id"],
        )
    if status == "resolved":
        _exact_keys(
            value,
            ("decision_id", "action_id", "offer_index", "kind", "key", "result"),
        )
        action_index = _parse_action(value["action_id"])
        offer_index = value["offer_index"]
        if (
            not _is_lower_hex(value["decision_id"], 64)
            or action_index is None
            or type(offer_index) is not int
            or not 0 <= offer_index <= _MAX_REWARD_INDEX
            or action_index != offer_index
            or type(value["kind"]) is not str
            or value["kind"] not in ("potion", "relic")
            or not _is_stable_key(value["key"])
            or type(value["result"]) is not str
            or value["result"] != "collected"
        ):
            raise _InvalidResponse()
        return _Response(
            status,
            nonce,
            decision_id=value["decision_id"],
            action_id=value["action_id"],
            offer_index=offer_index,
            kind=value["kind"],
            key=value["key"],
            result=value["result"],
        )
    if status == "error":
        _exact_keys(value, ("code",))
        if type(value["code"]) is not str or value["code"] not in (
            "invalid_request",
            "internal_failure",
        ):
            raise _InvalidResponse()
        return _Response(status, nonce, code=value["code"])
    raise _InvalidResponse()


def _failure(code: str) -> dict[str, object]:
    return {"schema_version": 1, "status": "failed", "code": code}


class _Controller:
    def __init__(
        self,
        exchange: Callable[[str, str, Optional[str], Optional[str], float], bytearray],
        clock: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> None:
        self._exchange = exchange
        self._clock = clock
        self._sleep = sleep
        self._deadline = clock() + _DEADLINE_SECONDS
        self._reads = 0
        self._attempted = 0
        self._accepted = 0
        self._reconciled = 0
        self._nonce: Optional[str] = None

    def _deadline_reached(self) -> bool:
        return self._clock() >= self._deadline

    def _call(
        self,
        method: str,
        route: str,
        decision_id: Optional[str],
        action_id: Optional[str],
        *,
        read: bool,
    ) -> _Response:
        if self._deadline_reached():
            raise _Stop("deadline_exceeded")
        if read:
            if self._reads >= _MAX_READS:
                raise _Stop("read_limit_reached")
            self._reads += 1
        else:
            self._attempted = 1

        body: object = None
        try:
            try:
                body = self._exchange(method, route, decision_id, action_id, self._deadline)
            except TransportFailure:
                raise _Stop("transport_failure") from None
            except (KeyboardInterrupt, SystemExit, GeneratorExit):
                raise
            except Exception:
                raise _Stop("internal_failure") from None

            if self._deadline_reached():
                raise _Stop("deadline_exceeded")
            if type(body) is not bytearray:
                raise _Stop("invalid_response")
            try:
                return _decode_response(body)
            except _InvalidResponse:
                raise _Stop("invalid_response") from None
        finally:
            if type(body) is bytearray:
                body[:] = b"\x00" * len(body)

    def _read(self) -> _Response:
        return self._call("GET", _GET_ROUTE, None, None, read=True)

    def _apply(self, decision_id: str, action_id: str) -> _Response:
        return self._call(
            "POST",
            _POST_ROUTE,
            decision_id,
            action_id,
            read=False,
        )

    def _bind_nonce(self, response: _Response) -> None:
        if self._nonce is None:
            self._nonce = response.session_nonce
        elif response.session_nonce != self._nonce:
            raise _Stop("invalid_response")

    def _pause(self) -> None:
        now = self._clock()
        if now >= self._deadline:
            raise _Stop("deadline_exceeded")
        self._sleep(min(_POLL_SECONDS, self._deadline - now))
        if self._deadline_reached():
            raise _Stop("deadline_exceeded")

    @staticmethod
    def _fixed_status(response: _Response) -> None:
        if response.status == "unsupported":
            raise _Stop("unsupported_state")
        if response.status == "error":
            raise _Stop("internal_failure")

    def run(self) -> dict[str, object]:
        while True:
            response = self._read()
            self._bind_nonce(response)
            self._fixed_status(response)
            if response.status == "waiting":
                if self._reads >= _MAX_READS:
                    raise _Stop("read_limit_reached")
                self._pause()
                continue
            if response.status != "ready":
                raise _Stop("invalid_response")
            ready = response
            break

        if self._reads >= _MAX_READS:
            raise _Stop("read_limit_reached")
        action_id = ready.legal_actions[0]
        action_index = _parse_action(action_id)
        if action_index is None:
            raise _Stop("invalid_response")
        selected = next((offer for offer in ready.offers if offer.index == action_index), None)
        if selected is None:
            raise _Stop("invalid_response")

        receipt = self._apply(ready.decision_id or "", action_id)
        self._bind_nonce(receipt)
        self._fixed_status(receipt)
        if receipt.status == "rejected":
            raise _Stop("action_rejected")
        if receipt.status == "uncertain":
            raise _Stop("action_uncertain")
        if (
            receipt.status != "accepted"
            or receipt.decision_id != ready.decision_id
            or receipt.action_id != action_id
        ):
            raise _Stop("invalid_response")
        self._accepted = 1

        while True:
            response = self._read()
            self._bind_nonce(response)
            self._fixed_status(response)
            if response.status == "waiting":
                if self._reads >= _MAX_READS:
                    raise _Stop("read_limit_reached")
                self._pause()
                continue
            if response.status != "resolved":
                raise _Stop("invalid_response")
            if (
                response.decision_id != ready.decision_id
                or response.action_id != action_id
                or response.offer_index != selected.index
                or response.kind != selected.kind
                or response.key != selected.key
                or response.result != "collected"
            ):
                raise _Stop("invalid_response")
            self._reconciled = 1
            return {
                "schema_version": 1,
                "status": "passed",
                "milestone": "item_v1_collection",
                "item_kind": selected.kind,
                "attempted": self._attempted,
                "accepted": self._accepted,
                "reconciled": self._reconciled,
            }


def run_collection(
    exchange: Callable[[str, str, Optional[str], Optional[str], float], bytearray],
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Run one bounded collection using an injected request/response exchange."""

    try:
        return _Controller(exchange, clock, sleep).run()
    except _Stop as failure:
        return _failure(failure.code)
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        raise
    except Exception:
        return _failure("internal_failure")
