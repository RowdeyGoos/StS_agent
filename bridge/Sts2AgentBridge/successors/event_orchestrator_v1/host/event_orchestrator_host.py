"""One bounded event flow with an explicitly supplied decision provider."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time
from types import MappingProxyType, ModuleType
from typing import Any, Callable, Mapping

DECISION_ROUTE = '/probe/event-orchestrator-v1/public/decision'
ACTION_ROUTE = '/probe/event-orchestrator-v1/public/action'
_VERSION = 'event_orchestrator_v1'
_FIELDS = ('parent_attempted', 'parent_accepted', 'option_transitions_observed',
           'parent_exits_reconciled', 'child_episodes_started', 'child_episodes_completed',
           'item_episodes_completed', 'card_episodes_completed', 'child_attempted',
           'child_accepted', 'child_reconciled')
_ACTIVE: ContextVar[Any] = ContextVar('event_orchestrator_active', default=None)


class TransportFailure(Exception):
    """Explicit injected transport failure; a failed action is never retried."""


class _Stop(Exception):
    def __init__(self, code: str):
        self.code = code


def _require(condition: bool) -> None:
    if not condition:
        raise _Stop('invalid_response')


def _keys(value: Any, keys: tuple[str, ...]) -> None:
    _require(type(value) is dict and tuple(value) == keys)


def _hex(value: Any, length: int) -> bool:
    return type(value) is str and len(value) == length and all(c in '0123456789abcdef' for c in value)


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if type(value) is list:
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class DecisionView:
    kind: str
    payload: Mapping[str, Any]
    child: Mapping[str, Any] | None


def first_legal(view: DecisionView) -> str:
    """Explicit deterministic fixture provider; no strategic inference."""
    return view.payload['legal_actions'][0]


def _load_frozen(relative: str, digest: str, name: str) -> Any:
    path = Path(__file__).absolute().parents[2] / relative
    for ancestor in (path, *path.parents):
        _require(not ancestor.is_symlink())
    _require(path.is_file() and path.stat().st_size <= 65536)
    source = path.read_bytes()
    _require(len(source) <= 65536 and hashlib.sha256(source).hexdigest() == digest)
    module = ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in rows:
        _require(key not in result)
        result[key] = value
    return result


def _tree(value: Any, depth: int = 0) -> None:
    _require(depth <= 12)
    if type(value) is dict:
        for v in value.values():
            _tree(v, depth + 1)
    elif type(value) is list:
        for v in value:
            _tree(v, depth + 1)
    else:
        _require(value is None or type(value) in (str, int, bool))
        if type(value) is str:
            value.encode('utf-8', errors='strict')


def _decode(body: Any) -> dict[str, Any]:
    _require(type(body) is bytearray and 0 < len(body) <= 65536)
    try:
        value = json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=_pairs)
        _tree(value)
        _require(json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii') == bytes(body))
        _keys(value, ('schema_version', 'protocol', 'session_nonce', 'child', 'payload'))
        _require(type(value['schema_version']) is int and value['schema_version'] == 1)
        _require(value['protocol'] == _VERSION and _hex(value['session_nonce'], 32))
        _require(type(value['payload']) is dict)
        if value['child'] is not None:
            c = value['child']
            _keys(c, ('kind', 'child_ordinal', 'parent_decision_id', 'parent_action_id'))
            _require(c['kind'] in ('item', 'card_selection') and type(c['child_ordinal']) is int and 1 <= c['child_ordinal'] <= 4)
            _require(_hex(c['parent_decision_id'], 64) and c['parent_action_id'] in tuple(f'choose:{i}' for i in range(8)))
        return value
    except _Stop:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise _Stop('invalid_response') from None


def _projection(v: dict[str, Any], *, text: bool) -> str:
    out = bytearray()
    def integer(n: int) -> None:
        out.extend(struct.pack('>I', n))
    def string(s: str) -> None:
        b = s.encode('utf-8'); integer(len(b)); out.extend(b)
    string(_VERSION); string(v['session_nonce']); string(v['phase']); integer(len(v['candidates']))
    for c in v['candidates']:
        integer(c['candidate_index']); string(c['action_id']); string(c['stable_id'])
        if text:
            string(c['rendered_text'])
        out.extend((int(c['enabled']), int(c['is_dangerous']), int(c['is_proceed'])))
        string(c['child_policy'])
    if text:
        integer(len(v['legal_actions']))
        for action in v['legal_actions']:
            string(action)
    try:
        return hashlib.sha256(out).hexdigest()
    finally:
        out[:] = b'\0' * len(out)


class _Controller:
    def __init__(self, request: Callable, provider: Callable, clock: Callable, sleep: Callable):
        self.request, self.provider, self.clock, self.sleep = request, provider, clock, sleep
        self.counts = dict.fromkeys(_FIELDS, 0)
        self.interfered = False
        self.last_time = float('-inf')
        self.deadline = self.now() + 30.0
        self.reads = 0
        self.nonce = None
        self.used: set[str] = set()
        self.reserved: set[str] = set()
        self.structures: set[str] = set()
        self.last_parent: tuple[str, str] | None = None
        self.parent_phase: str | None = None
        self.parent_policy: str | None = None
        self.parent_structure: str | None = None
        self.prior_seen: dict[str, Any] | None = None
        self.transition_seen = False
        self.child_window = False
        self.child: dict[str, Any] | None = None
        self.completed_child: dict[str, Any] | None = None
        self.child_done = False
        self.child_accepted: list[tuple[str, str]] = []
        self.child_history = 0
        self.child_shape = None
        self.item_offer = None
        self.card = _load_frozen('card_selection_v1/host/card_selection_host.py', 'aa517a36ddab784c629f07b887f077f8f73700314ede821b80fb6ef0c9ee8c80', '_event_frozen_card_host')
        self.item = _load_frozen('item_wire_v1/host/item_host.py', 'e3dd05b828a2c88acfd02dcc1b89d907cafb11e53a7af23c031976a436b38364', '_event_frozen_item_host')

    def now(self) -> float:
        n = self.clock()
        if type(n) not in (float, int) or not math.isfinite(n) or n < self.last_time:
            raise _Stop('internal_failure')
        self.last_time = float(n)
        return self.last_time

    def budget(self) -> None:
        if self.interfered:
            raise _Stop('reentrant_provider')
        if self.now() >= self.deadline:
            raise _Stop('deadline_exceeded')

    def call(self, method: str, decision: str | None = None, action: str | None = None) -> dict[str, Any]:
        self.budget()
        body = response = None
        if method == 'GET':
            if self.reads >= 2048:
                raise _Stop('read_limit')
            self.reads += 1
            route = DECISION_ROUTE
        else:
            if self.counts['parent_attempted'] + self.counts['child_attempted'] >= 52:
                raise _Stop('action_limit')
            if self.child is None:
                if self.counts['parent_attempted'] >= 12:
                    raise _Stop('action_limit')
                self.counts['parent_attempted'] += 1
            else:
                if len(self.child_accepted) >= (1 if self.child['kind'] == 'item' else 10):
                    raise _Stop('action_limit')
                self.counts['child_attempted'] += 1
            route = ACTION_ROUTE
            body = bytearray(json.dumps({'decision_id': decision, 'action_id': action, 'child': self.child}, separators=(',', ':')).encode('ascii'))
        try:
            response = self.request(method, route, body)
            self.budget()
            value = _decode(response)
            if self.nonce is None:
                self.nonce = value['session_nonce']
            _require(self.nonce == value['session_nonce'])
            p = value['payload']
            if p.get('kind') == 'error':
                _keys(p, ('schema_version', 'kind', 'status', 'code'))
                _require(value['child'] is None and type(p['schema_version']) is int and p['schema_version'] == 1 and p['status'] == 'error' and p['code'] in ('invalid_request', 'internal_failure', 'unsupported'))
                raise _Stop('unsupported_state' if p['code'] == 'unsupported' else 'internal_failure' if p['code'] == 'internal_failure' else 'invalid_response')
            _require(p.get('session_nonce') == self.nonce)
            return value
        finally:
            for buf in (body, response):
                if type(buf) is bytearray:
                    buf[:] = b'\0' * len(buf)

    def common_parent(self, p: dict[str, Any]) -> None:
        _require(type(p['schema_version']) is int and p['schema_version'] == 1 and p['version'] == _VERSION and p['session_nonce'] == self.nonce and type(p['parent_ordinal']) is int and p['parent_ordinal'] == 1)

    def prior(self, p: dict[str, Any], *, resolved: bool = False) -> None:
        prior = p['prior_result']
        if prior is None:
            _require(self.prior_seen is None and not resolved)
            return
        _keys(prior, ('decision_id', 'action_id', 'result', 'child'))
        _require(self.last_parent == (prior['decision_id'], prior['action_id']))
        result = prior['result']
        _require(result in ('option_transition', 'child_completed', 'map_handoff'))
        if result == 'child_completed':
            _require(self.completed_child is not None and prior['child'] == self.completed_child)
        else:
            _require(prior['child'] is None and self.completed_child is None)
        if result == 'option_transition':
            self.child_window = False
        _require((result == 'map_handoff') == resolved)
        if self.prior_seen is not None:
            _require(prior == self.prior_seen)
        self.prior_seen = prior

    def parent_read(self, p: dict[str, Any]) -> str:
        common = ('schema_version', 'kind', 'version', 'session_nonce', 'parent_ordinal')
        if p.get('kind') == 'parent_resolved':
            _keys(p, common + ('status', 'phase', 'decision_id', 'action_id', 'result', 'prior_result'))
            self.common_parent(p)
            _require((p['status'], p['phase'], p['result']) == ('resolved', 'complete', 'map_handoff'))
            _require(self.last_parent == (p['decision_id'], p['action_id']) and self.parent_phase == 'proceed')
            self.prior(p, resolved=True)
            self.counts['parent_exits_reconciled'] = 1
            return 'resolved'
        _keys(p, common + ('status', 'phase', 'decision_id', 'candidates', 'legal_actions', 'child', 'prior_result'))
        self.common_parent(p)
        _require(p['kind'] == 'parent_observation' and p['child'] is None)
        status = p['status']
        _require((status, p['phase']) in (('ready', 'choose_option'), ('ready', 'proceed'), ('waiting', 'waiting'), ('unsupported', 'unsupported')))
        _require(type(p['candidates']) is list and type(p['legal_actions']) is list)
        self.prior(p)
        if status != 'ready':
            _require(p['decision_id'] == '' and p['candidates'] == p['legal_actions'] == [])
            return status
        _require(_hex(p['decision_id'], 64) and 1 <= len(p['candidates']) <= 8)
        stable = set()
        legal = []
        for i, c in enumerate(p['candidates']):
            _keys(c, ('candidate_index', 'action_id', 'stable_id', 'rendered_text', 'enabled', 'is_dangerous', 'is_proceed', 'child_policy'))
            _require(type(c['candidate_index']) is int and c['candidate_index'] == i and c['action_id'] == f'choose:{i}')
            key, text = c['stable_id'], c['rendered_text']
            _require(type(key) is str and 1 <= len(key) <= 96 and all(' ' <= ch <= '~' for ch in key) and key not in stable)
            stable.add(key)
            _require(type(text) is str and 1 <= len(text.encode('utf-8')) <= 1024 and all(ch == '\n' or (ord(ch) >= 32 and not 127 <= ord(ch) <= 159) for ch in text))
            _require(all(type(c[k]) is bool for k in ('enabled', 'is_dangerous', 'is_proceed')))
            _require(c['child_policy'] in ('', 'item_reward', 'cheese_gorge_add_two'))
            if not c['is_proceed']:
                _require(c['child_policy'] == ('cheese_gorge_add_two' if key == 'ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE' else 'item_reward'))
            if c['enabled'] and not c['is_dangerous'] and key not in self.reserved and self.counts['parent_attempted'] < 12:
                legal.append(c['action_id'])
        if p['phase'] == 'proceed':
            _require(len(p['candidates']) == 1 and p['candidates'][0]['stable_id'] == 'PROCEED' and p['candidates'][0]['is_proceed'] and not p['candidates'][0]['is_dangerous'] and p['candidates'][0]['child_policy'] == '')
        else:
            _require(not any(c['is_proceed'] for c in p['candidates']))
        _require(p['legal_actions'] == legal and len(legal) > 0 and p['decision_id'] == _projection(p, text=True))
        structural = _projection(p, text=False)
        _require(structural not in self.structures)
        if self.last_parent is not None:
            _require(self.prior_seen is not None and structural != self.parent_structure)
            if not self.transition_seen:
                if self.prior_seen['result'] == 'option_transition':
                    self.counts['option_transitions_observed'] += 1
                self.transition_seen = True
        self.child_window = False
        return status

    def child_parse(self, p: dict[str, Any]) -> Any:
        buf = bytearray(json.dumps(p, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii'))
        try:
            if self.child['kind'] == 'card_selection':
                return self.card._decode(buf)
            return self.item._decode_response(buf)
        except (self.card._InvalidResponse, self.item._InvalidResponse):
            raise _Stop('invalid_response') from None
        finally:
            buf[:] = b'\0' * len(buf)

    def child_read(self, p: dict[str, Any]) -> str:
        parsed = self.child_parse(p)
        status = p.get('status')
        _require(status in ('ready', 'waiting', 'unsupported', 'resolved'))
        if self.child['kind'] == 'item':
            if status == 'ready':
                _require(not self.child_accepted and self.item_offer is None)
            elif status == 'resolved':
                _require(len(self.child_accepted) == 1 and self.child_accepted[0] == (parsed.decision_id, parsed.action_id) and self.item_offer is not None)
                _require((parsed.offer_index, parsed.kind, parsed.key) == self.item_offer)
            return status
        _require(p['kind'] in ('child_observation', 'child_resolved'))
        history = p['prior_results']
        _require(self.child_history <= len(history) <= len(self.child_accepted))
        for i, row in enumerate(history):
            _require((row['decision_id'], row['action_id']) == self.child_accepted[i])
        if status in ('ready', 'resolved'):
            _require(len(history) == len(self.child_accepted))
        if status == 'ready':
            _require((p['operation'], p['commit_mode'], p['min_select'], p['max_select']) == ('add', 'auto_at_max', 2, 2) and len(p['candidates']) == 8)
            shape = [(c['slot'], c['key'], c['upgrade_level']) for c in p['candidates']]
            if self.child_shape is None:
                self.child_shape = shape
            _require(shape == self.child_shape)
        elif status == 'resolved':
            _require(self.child_shape is not None and p['operation'] == 'add' and len(p['selected_cards']) == len(self.child_accepted) == 2)
            for c in p['selected_cards']:
                _require((c['slot'], c['key'], c['upgrade_level']) in self.child_shape)
        elif status == 'waiting':
            _require(self.child_shape is not None and len(self.child_accepted) > 0)
        self.counts['child_reconciled'] += len(history) - self.child_history
        self.child_history = len(history)
        return status

    def choose(self, p: dict[str, Any]) -> None:
        if self.reads >= 2048:
            raise _Stop('read_limit')
        decision = p['decision_id']
        _require(decision not in self.used)
        self.used.add(decision)  # provider is invoked at most once, even on failure
        self.budget()
        view = DecisionView('parent' if self.child is None else self.child['kind'], _freeze(p), _freeze(self.child))
        try:
            action = self.provider(view)
        except Exception:
            if self.interfered:
                raise _Stop('reentrant_provider') from None
            raise _Stop('provider_failed') from None
        self.budget()
        if type(action) is not str or action not in p['legal_actions']:
            raise _Stop('invalid_provider')
        if self.child is None:
            candidate = next(c for c in p['candidates'] if c['action_id'] == action)
            self.reserved.add(candidate['stable_id'])
            self.parent_phase, self.parent_policy = p['phase'], candidate['child_policy']
            self.parent_structure = _projection(p, text=False)
            self.structures.add(self.parent_structure)
        elif self.child['kind'] == 'item':
            offer = next(c for c in p['offers'] if f"collect:{c['index']}" == action)
            self.item_offer = (offer['index'], offer['kind'], offer['key'])
        receipt = self.call('POST', decision, action)
        _require(receipt['child'] == self.child)
        r = receipt['payload']
        if self.child is None:
            common = ('schema_version', 'kind', 'version', 'session_nonce', 'parent_ordinal')
            if r.get('kind') == 'parent_failure':
                _keys(r, common + ('status', 'code')); self.common_parent(r)
                _require(r['status'] == 'failed' and r['code'] in ('rejected', 'uncertain', 'unsupported'))
                raise _Stop('unsupported_state')
            _keys(r, common + ('status', 'decision_id', 'action_id')); self.common_parent(r)
            _require(r['kind'] == 'parent_receipt' and r['status'] == 'accepted' and (r['decision_id'], r['action_id']) == (decision, action))
            self.last_parent = (decision, action)
            self.prior_seen = None; self.transition_seen = False; self.completed_child = None
            self.child_window = self.parent_phase == 'choose_option'
            self.counts['parent_accepted'] += 1
        else:
            self.child_parse(r)
            status = r.get('status') if self.child['kind'] == 'item' else r.get('outcome')
            if status in ('unsupported', 'uncertain', 'rejected'):
                raise _Stop('unsupported_state')
            _require(status == 'accepted' and (r.get('decision_id'), r.get('action_id')) == (decision, action))
            if self.child['kind'] == 'card_selection':
                _require(r['kind'] == 'child_receipt')
            self.child_accepted.append((decision, action)); self.counts['child_accepted'] += 1

    def run(self) -> dict[str, Any]:
        while True:
            envelope = self.call('GET'); p, c = envelope['payload'], envelope['child']
            if c is None:
                if self.child is not None:
                    _require(self.child_done)
                    self.completed_child = self.child
                    self.child = None
                status = self.parent_read(p)
                if status == 'resolved':
                    return {'schema_version': 1, 'status': 'passed', **self.counts}
            else:
                if self.child is None:
                    _require(self.child_window and self.last_parent == (c['parent_decision_id'], c['parent_action_id']))
                    _require(c['child_ordinal'] == self.counts['child_episodes_started'] + 1)
                    _require((self.parent_policy, c['kind']) in (('item_reward', 'item'), ('cheese_gorge_add_two', 'card_selection')))
                    self.child = c; self.child_window = False; self.child_done = False
                    self.child_accepted = []; self.child_history = 0; self.child_shape = None; self.item_offer = None
                    self.counts['child_episodes_started'] += 1
                _require(c == self.child and not self.child_done)
                status = self.child_read(p)
                if status == 'resolved':
                    self.child_done = True
                    self.counts['child_episodes_completed'] += 1
                    self.counts['item_episodes_completed' if c['kind'] == 'item' else 'card_episodes_completed'] += 1
                    if c['kind'] == 'item':
                        self.counts['child_reconciled'] += 1
                    continue
            if status == 'unsupported':
                raise _Stop('unsupported_state')
            if status == 'ready':
                self.choose(p)
            else:
                self.budget()
                remaining = self.deadline - self.now()
                if remaining <= 0:
                    raise _Stop('deadline_exceeded')
                self.sleep(min(0.05, remaining))
                self.budget()


def run_event(request: Callable, *, provider: Callable, clock: Callable = time.monotonic, sleep: Callable = time.sleep) -> dict[str, Any]:
    """Drive one event. Transport and provider bodies are never retained in the summary."""
    counts = dict.fromkeys(_FIELDS, 0)
    active = _ACTIVE.get()
    if active is not None:
        active.interfered = True
        return {'schema_version': 1, 'status': 'failed', **counts, 'code': 'reentrant_provider'}
    controller = None
    token = None
    try:
        if not callable(provider):
            raise _Stop('invalid_provider')
        controller = _Controller(request, provider, clock, sleep)
        counts = controller.counts
        token = _ACTIVE.set(controller)
        return controller.run()
    except _Stop as stop:
        code = stop.code
    except TransportFailure:
        code = 'transport_failure'
    except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
        code = 'invalid_response'
    except Exception:
        code = 'internal_failure'
    finally:
        if token is not None:
            _ACTIVE.reset(token)
    return {'schema_version': 1, 'status': 'failed', **counts, 'code': code}
