"""Bounded generic event controller; transport and public decision policy are injected."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from types import MappingProxyType, ModuleType
from typing import Any, Callable, Mapping

DECISION_ROUTE = '/probe/generic-event-v7/public/decision'
ACTION_ROUTE = '/probe/generic-event-v7/public/action'
VERSION = 'generic_event_v7'
_FIELDS = ('parent_attempted', 'parent_accepted', 'parent_reconciled',
           'child_episodes', 'child_attempted', 'child_accepted', 'child_reconciled')
_PARENT = ('status', 'phase', 'decision_id', 'candidates', 'legal_actions',
           'prior_results', *_FIELDS, 'total_attempted', 'effects', 'completed_card_children', 'completed_item_children')
_CHILD = ('ordinal', 'parent_decision_id', 'parent_action_id', 'kind', 'contract_version', 'operation',
          'min_select', 'max_select', 'commit_mode', 'domain_count')
_ITEM_CHILD = _CHILD[:5] + ('offer_count',)
_ACTIVE: ContextVar[Any] = ContextVar('generic_event_active', default=None)


class TransportFailure(Exception):
    """Transport did not provide a definitive response. No action is retried."""


class _Stop(Exception):
    def __init__(self, code: str):
        self.code = code


def _require(condition: bool) -> None:
    if not condition:
        raise _Stop('invalid_response')


def _keys(v: Any, expected: tuple[str, ...]) -> None:
    _require(type(v) is dict and tuple(v) == expected)


def _hex(v: Any, length: int) -> bool:
    return type(v) is str and len(v) == length and all(c in '0123456789abcdef' for c in v)


def _integer(v: Any, maximum: int) -> bool:
    return type(v) is int and 0 <= v <= maximum


def _parent_action(v: Any) -> bool:
    return type(v) is str and v in tuple(f'choose:{i}' for i in range(8))


def _freeze(v: Any) -> Any:
    if type(v) is dict:
        return MappingProxyType({k: _freeze(x) for k, x in v.items()})
    if type(v) is list:
        return tuple(_freeze(x) for x in v)
    return v


@dataclass(frozen=True)
class DecisionView:
    kind: str
    payload: Mapping[str, Any]
    child: Mapping[str, Any] | None


def first_legal(view: DecisionView) -> str:
    """Deterministic fixture policy; callers explicitly choose their policy."""
    return view.payload['legal_actions'][0]


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for k, v in rows:
        _require(k not in result)
        result[k] = v
    return result


def _tree(v: Any, depth: int = 0) -> None:
    _require(depth <= 12)
    if type(v) is dict:
        _require(len(v) <= 64)
        for key, item in v.items():
            _require(type(key) is str)
            _tree(item, depth + 1)
    elif type(v) is list:
        _require(len(v) <= 128)
        for item in v:
            _tree(item, depth + 1)
    else:
        _require(v is None or type(v) in (str, int, bool))
        if type(v) is str:
            _require(len(v) <= 4096)
            v.encode('utf-8', errors='strict')


def _decode(body: Any) -> dict[str, Any]:
    _require(type(body) is bytearray and 0 < len(body) <= 65536)
    try:
        v = json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=_pairs)
        _tree(v)
        _keys(v, ('schema_version', 'protocol', 'session_nonce', 'kind', 'parent', 'child', 'payload'))
        _require(type(v['schema_version']) is int and v['schema_version'] == 1)
        _require(v['protocol'] == VERSION and _hex(v['session_nonce'], 32))
        _require(v['kind'] in ('decision', 'action', 'error'))
        if v['child'] is not None:
            c = v['child']
            _keys(c, _ITEM_CHILD if c.get('kind') == 'item' else _CHILD)
            _require(_integer(c['ordinal'], 4) and c['ordinal'] >= 1)
            _require(_hex(c['parent_decision_id'], 64) and _parent_action(c['parent_action_id']))
            if c['kind'] == 'item':
                _require(type(c['offer_count']) is int and 1 <= c['offer_count'] <= 8 and
                         c['contract_version'] == ('item_v1' if c['offer_count']==1 else 'item_set_v1'))
            else:
                _require(c['kind'] == 'card_selection' and c['contract_version'] ==
                         ('card_remove_v2' if c['operation'] == 'remove' else ('card_enchant_v2' if c['max_select']>1 else 'card_enchant_v1') if c['operation'] == 'enchant' else 'card_transform_v2' if c['operation'] == 'transform' else 'card_selection_v1'))
                _require((c['operation'] in ('upgrade', 'remove', 'transform', 'enchant') and c['commit_mode'] == 'preview_confirm') or
                         (c['operation'] == 'add' and c['commit_mode'] in ('auto_at_max', 'explicit_confirm')))
                _require(type(c['min_select']) is int and type(c['max_select']) is int and
                         1 <= c['min_select'] <= c['max_select'] <= 8)
                _require(_integer(c['domain_count'], 64) and c['domain_count'] > c['max_select'])
                if c['operation'] == 'enchant':
                    _require(c['min_select'] == c['max_select'])
                if c['operation'] == 'upgrade':
                    _require(c['min_select'] == c['max_select'])
        return v
    except _Stop:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise _Stop('invalid_response') from None


def _load_card() -> Any:
    path = Path(__file__).absolute().parents[2] / 'cards/host/card_selection_host.py'
    for ancestor in (path, *path.parents):
        _require(not ancestor.is_symlink())
    _require(path.is_file() and path.stat().st_size <= 65536)
    source = path.read_bytes()
    _require(hashlib.sha256(source).hexdigest() == 'aa517a36ddab784c629f07b887f077f8f73700314ede821b80fb6ef0c9ee8c80')
    module = ModuleType('_generic_event_frozen_card_host')
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def _load_transform() -> Any:
    path = Path(__file__).absolute().parent / 'card_transform_host.py'
    for ancestor in (path, *path.parents):
        _require(not ancestor.is_symlink())
    _require(path.is_file() and path.stat().st_size <= 65536)
    module = ModuleType('_generic_event_transform_host')
    module.__file__ = str(path)
    source = path.read_bytes()
    _require(hashlib.sha256(source).hexdigest() == 'cf5b42f4cc5d412e46e6e46dc7fcf93eb9bf512b5fab1307b1d87d13f33f67ba')
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def _load_item() -> Any:
    path = Path(__file__).absolute().parents[2] / 'item_wire/host/item_host.py'
    for ancestor in (path, *path.parents):
        _require(not ancestor.is_symlink())
    _require(path.is_file() and path.stat().st_size <= 65536)
    source = path.read_bytes()
    _require(hashlib.sha256(source).hexdigest() == 'e3dd05b828a2c88acfd02dcc1b89d907cafb11e53a7af23c031976a436b38364')
    module = ModuleType('_generic_event_frozen_item_host')
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


class _Controller:
    def __init__(self, request: Callable, provider: Callable, clock: Callable, sleep: Callable):
        self.request, self.provider, self.clock, self.sleep = request, provider, clock, sleep
        self.counts = dict.fromkeys(_FIELDS, 0)
        self.native = dict.fromkeys(_FIELDS, 0)
        self.interfered = False
        self.last_time = float('-inf')
        self.deadline = self.now() + 30.0
        self.reads = 0
        self.nonce = None
        self.used: set[str] = set()
        self.parent_receipts: list[tuple[str, str]] = []
        self.parent_history: list[dict[str, Any]] = []
        self.last_proceed = False
        self.child = None
        self.child_done = False
        self.child_receipts: list[tuple[str, str]] = []
        self.child_history: list[dict[str, Any]] = []
        self.child_shape = None
        self.item_set_history = []
        self.enchantment = None
        self.preview_seen = False
        self.child_parents: set[tuple[str, str]] = set()
        self.completed_children: set[tuple[str, str]] = set()
        self.completed_items: set[tuple[str, str]] = set()
        self.effects = 'none_attempted'
        self.card = _load_card()
        self.transform = _load_transform()
        self.item = _load_item()

    def now(self) -> float:
        value = self.clock()
        if type(value) not in (float, int) or not math.isfinite(value) or value < self.last_time:
            raise _Stop('internal_failure')
        self.last_time = float(value)
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
                lineage = None
            else:
                if len(self.child_receipts) >= (self.child['offer_count'] if self.child['kind'] == 'item' else 10):
                    raise _Stop('action_limit')
                self.counts['child_attempted'] += 1
                lineage = {k: self.child[k] for k in _CHILD[:3]}
            self.effects = 'unverified'
            body = bytearray(json.dumps({'decision_id': decision, 'action_id': action, 'child': lineage}, separators=(',', ':')).encode('ascii'))
            route = ACTION_ROUTE
        try:
            response = self.request(method, route, body)
            self.budget()
            v = _decode(response)
            if self.nonce is None:
                self.nonce = v['session_nonce']
            _require(v['session_nonce'] == self.nonce)
            if v['kind'] == 'error':
                _require(v['parent'] is None and v['child'] is None)
                _keys(v['payload'], ('code',))
                _require(v['payload']['code'] in ('invalid_request', 'internal_failure', 'unsupported'))
                raise _Stop('unsupported_state' if v['payload']['code'] == 'unsupported' else v['payload']['code'])
            _require(v['kind'] == ('decision' if method == 'GET' else 'action'))
            return v
        finally:
            for buffer in (body, response):
                if type(buffer) is bytearray:
                    buffer[:] = b'\0' * len(buffer)

    def parent_read(self, p: Any) -> str:
        _keys(p, _PARENT)
        _require(p['status'] in ('ready', 'waiting', 'child', 'unsupported', 'complete'))
        phases = {'ready': ('choose_option', 'proceed'), 'waiting': ('waiting',),
                  'child': ('child',), 'unsupported': ('unsupported',), 'complete': ('map_handoff',)}
        _require(p['phase'] in phases[p['status']])
        _require(p['effects'] in ('none_attempted', 'unverified', 'card_effect_verified', 'item_effect_verified'))
        _require(_integer(p['completed_card_children'], 4) and
                 p['completed_card_children'] == len(self.completed_children) - len(self.completed_items) and
                 _integer(p['completed_item_children'], 4) and p['completed_item_children'] == len(self.completed_items))
        _require(type(p['candidates']) is list and len(p['candidates']) <= 8)
        _require(type(p['legal_actions']) is list and len(p['legal_actions']) <= 8)
        _require(type(p['prior_results']) is list and len(p['prior_results']) <= 12)
        history = p['prior_results']
        _require(len(self.parent_history) <= len(history) <= len(self.parent_receipts))
        _require(history[:len(self.parent_history)] == self.parent_history)
        for i, row in enumerate(history):
            _keys(row, ('decision_id', 'action_id', 'result'))
            _require((row['decision_id'], row['action_id']) == self.parent_receipts[i])
            _require(row['result'] in ('option_transition', 'child_completed', 'map_handoff'))
            owner = self.parent_receipts[i]
            if row['result'] == 'child_completed':
                _require(owner in self.child_parents and (i < len(self.parent_history) or self.child_done))
            if row['result'] == 'map_handoff':
                _require(i == len(self.parent_receipts) - 1 and self.last_proceed and p['status'] == 'complete')
            if row['result'] == 'option_transition':
                _require(owner not in self.child_parents and not (i == len(self.parent_receipts) - 1 and self.last_proceed))
        completed_history = [(row['decision_id'], row['action_id']) for row in history
                             if row['result'] == 'child_completed']
        _require(len(set(completed_history)) == len(completed_history) and
                 set(completed_history) <= self.completed_children)
        unreconciled = self.completed_children - set(completed_history)
        _require(len(unreconciled) <= 1 and (not unreconciled or
                 p['status'] == 'unsupported' and self.parent_receipts and
                 unreconciled == {self.parent_receipts[-1]}))
        for key in _FIELDS:
            maximum = 12 if key.startswith('parent_') else 4 if key == 'child_episodes' else 40
            _require(_integer(p[key], maximum) and p[key] >= self.native[key])
            # The parent snapshot precedes ReadChild; child reconciliation may lag once.
            upper = len(history) if key == 'parent_reconciled' else self.counts[key] + (1 if key == 'child_episodes' else 0)
            _require(p[key] <= upper)
        _require(p['parent_reconciled'] == len(history) and
                 p['completed_card_children'] + p['completed_item_children'] <= p['child_episodes'])
        _require((p['effects'] == 'none_attempted') == (p['total_attempted'] == 0))
        if p['effects'] in ('card_effect_verified', 'item_effect_verified'):
            _require(self.parent_receipts and self.parent_receipts[-1] in self.completed_children and
                     ((self.parent_receipts[-1] in self.completed_items) == (p['effects'] == 'item_effect_verified')))
        _require(p['parent_accepted'] <= p['parent_attempted'] and p['parent_reconciled'] <= p['parent_accepted'])
        _require(p['child_reconciled'] <= p['child_accepted'] <= p['child_attempted'])
        _require(_integer(p['total_attempted'], 52) and p['total_attempted'] == p['parent_attempted'] + p['child_attempted'])
        _require(p['parent_attempted'] == self.counts['parent_attempted'] and p['parent_accepted'] == self.counts['parent_accepted'])
        _require(p['child_attempted'] == self.counts['child_attempted'] and p['child_accepted'] == self.counts['child_accepted'])
        self.native = {key: p[key] for key in _FIELDS}
        if p['status'] == 'ready':
            _require(_hex(p['decision_id'], 64) and 1 <= len(p['candidates']) <= 8)
            _require(len(history) == len(self.parent_receipts))
            expected = []
            stable_ids = set()
            for i, candidate in enumerate(p['candidates']):
                _keys(candidate, ('index', 'action_id', 'stable_id', 'rendered_text', 'enabled', 'is_dangerous', 'is_proceed', 'discovery'))
                _require(type(candidate['index']) is int and candidate['index'] == i and candidate['action_id'] == f'choose:{i}')
                stable = candidate['stable_id']
                _require(type(stable) is str and 1 <= len(stable) <= 96 and all(' ' <= c <= '~' for c in stable) and stable not in stable_ids)
                stable_ids.add(stable)
                text = candidate['rendered_text']
                _require(type(text) is str and 1 <= len(text.encode('utf-8')) <= 1024 and
                         all(c in '\n\t' or not (ord(c) < 32 or 127 <= ord(c) <= 159) for c in text))
                _require(all(type(candidate[k]) is bool for k in ('enabled', 'is_dangerous', 'is_proceed')))
                _require(candidate['discovery'] == ('none' if candidate['is_proceed'] else 'deferred'))
                _require(candidate['is_proceed'] == (p['phase'] == 'proceed'))
                if candidate['enabled'] and not candidate['is_dangerous']:
                    expected.append(candidate['action_id'])
            _require(p['legal_actions'] == expected and len(expected) >= 1)
            if p['phase'] == 'proceed':
                _require(len(p['candidates']) == 1)
        else:
            _require(p['decision_id'] == '' and p['candidates'] == [] and p['legal_actions'] == [])
        self.counts['parent_reconciled'] = len(history)
        self.parent_history = history
        self.effects = p['effects']
        return p['status']

    def lineage(self, c: Any) -> None:
        if c is None:
            _require(self.child is None or self.child_done)
            if self.child is not None:
                self.child = None
                self.child_done = False
            return
        _require(self.parent_receipts and not self.last_proceed)
        owner = (c['parent_decision_id'], c['parent_action_id'])
        _require(owner == self.parent_receipts[-1])
        if self.child is None:
            _require(owner not in self.child_parents and c['ordinal'] == self.counts['child_episodes'] + 1)
            _require(len(self.parent_history) < len(self.parent_receipts))
            self.child_parents.add(owner)
            self.counts['child_episodes'] += 1
            self.child = c
            self.child_receipts = []
            self.child_history = []
            self.child_shape = None
            self.item_set_history = []
            self.enchantment = None
            self.preview_seen = False
            self.child_done = False
        _require(self.child == c and not self.child_done)

    def card_parse(self, p: Any) -> None:
        _require(type(p) is dict and type(p.get('schema_version')) is int and p['schema_version'] == 1)
        try:
            if self.child is not None and self.child['operation'] == 'remove':
                self.removal_parse(p)
            elif self.child is not None and self.child['operation'] == 'enchant':
                self.enchant_parse(p)
            else:
                (self.transform if self.child is not None and self.child['operation'] == 'transform' else self.card)._validate_envelope(p)
        except Exception:
            raise _Stop('invalid_response') from None
        _require(p.get('session_nonce') == self.nonce)

    def removal_parse(self, p: dict[str, Any]) -> None:
        _require(p.get('version') == 'card_remove_v2')
        normalized = dict(p)
        normalized['version'] = 'card_selection_v1'
        if p.get('kind') == 'child_resolved':
            _require(tuple(p)[-1] == 'parent_additions' and p.get('operation') == 'remove')
            additions = normalized.pop('parent_additions')
            _keys(additions, ('status', 'cards'))
            _require(additions['status'] == 'unverified' and type(additions['cards']) is list and len(additions['cards']) <= 1)
            for card in additions['cards']:
                _keys(card, ('key', 'upgrade_level', 'enchantment'))
                _require(self.transform._stable_key(card['key']) and self.transform._integer(card['upgrade_level']))
                if card['enchantment'] is not None:
                    e = card['enchantment']
                    _keys(e, ('key', 'amount'))
                    _require(self.transform._stable_key(e['key']) and self.transform._integer(e['amount']) and e['amount'] > 0)
        self.card._validate_envelope(normalized)

    def enchant_parse(self, p: dict[str, Any]) -> None:
        # The version owns fixed cardinality and exact enchantment metadata.
        # Reuse only the common selection envelope validation after normalization.
        _require(p.get('version') == self.child['contract_version'])
        normalized = dict(p)
        normalized['version'] = 'card_transform_v2'
        if p.get('kind') in ('child_observation', 'child_resolved'):
            _require(tuple(p)[-1] == 'enchantment')
            effect = normalized.pop('enchantment')
            if p.get('status') in ('ready', 'resolved'):
                _require(p.get('operation') == 'enchant' and type(effect) is dict and
                         tuple(effect) == ('key', 'amount') and self.transform._stable_key(effect['key']) and
                         type(effect['amount']) is int and 1 <= effect['amount'] <= 2_147_483_647)
                normalized['operation'] = 'transform'
                if p['kind'] == 'child_observation':
                    _require(p['min_select'] == p['max_select'] == self.child['max_select'] and p['commit_mode'] == 'preview_confirm')
                else:
                    _require(len(p['selected_cards']) == self.child['max_select'])
                if self.enchantment is None:
                    _require(p['kind'] == 'child_observation' and p['phase'] == 'selecting')
                    self.enchantment = dict(effect)
                _require(effect == self.enchantment)
            else:
                _require(effect is None)
        self.transform._validate_envelope(normalized)

    def child_read(self, p: Any) -> str:
        if self.child['kind'] == 'item':
            return self.item_set_read(p) if self.child['offer_count']>1 else self.item_read(p)
        self.card_parse(p)
        _require(p['kind'] in ('child_observation', 'child_resolved'))
        status = p['status']
        history = p['prior_results']
        _require(len(self.child_history) <= len(history) <= len(self.child_receipts))
        _require(history[:len(self.child_history)] == self.child_history)
        for i, row in enumerate(history):
            _require((row['decision_id'], row['action_id']) == self.child_receipts[i])
        if status in ('ready', 'resolved'):
            _require(len(history) == len(self.child_receipts))
        operation = self.child['operation']
        mode = self.child['commit_mode']
        minimum, maximum = self.child['min_select'], self.child['max_select']
        actions = [action for _, action in self.child_receipts]
        selections = [int(action[7:]) for action in actions if action.startswith('select:')]
        selected_set = set(selections)
        _require(len(selected_set) == len(selections) <= maximum and
                 actions.count('preview') <= 1 and actions.count('confirm') <= 1)
        if mode != 'preview_confirm':
            _require('preview' not in actions and not self.preview_seen)
        if mode == 'auto_at_max':
            _require('confirm' not in actions)
        if 'preview' in actions:
            preview_at = actions.index('preview')
            _require(minimum <= preview_at <= maximum and
                     all(action.startswith('select:') for action in actions[:preview_at]) and
                     all(action == 'confirm' for action in actions[preview_at + 1:]))
        if 'confirm' in actions:
            _require(actions[-1] == 'confirm' and
                     (self.preview_seen if mode == 'preview_confirm' else mode == 'explicit_confirm') and
                     minimum <= len(selections) <= maximum)
        if status == 'ready':
            _require('confirm' not in actions)
            _require((p['operation'], p['min_select'], p['max_select'], p['commit_mode']) ==
                     (operation, minimum, maximum, self.child['commit_mode']))
            _require(len(p['candidates']) == self.child['domain_count'])
            _require(len(p['selected_slots']) == len(selected_set) and
                     len(set(p['selected_slots'])) == len(p['selected_slots']) and
                     set(p['selected_slots']) == selected_set)
            shape = [(c['slot'], c['key'], c['upgrade_level']) for c in p['candidates']]
            _require([slot for slot, _, _ in shape] == list(range(len(shape))))
            if self.child_shape is None:
                self.child_shape = shape
            _require(shape == self.child_shape)
            if mode != 'preview_confirm':
                _require(p['phase'] == 'selecting')
                if mode == 'auto_at_max':
                    _require(len(selections) < maximum)
            elif p['phase'] == 'preview':
                _require(minimum <= len(selections) <= maximum)
                if (operation in ('remove', 'transform') or operation in ('upgrade', 'enchant') and maximum > 1) and 'preview' not in actions:
                    _require(len(selections) == maximum)
                self.preview_seen = True
            else:
                _require(not self.preview_seen and 'preview' not in actions)
                if operation in ('remove', 'transform') or operation in ('upgrade', 'enchant') and maximum > 1:
                    _require(len(selections) < maximum)
        elif status == 'resolved':
            _require(self.child_shape is not None and minimum <= len(selections) <= maximum)
            if mode == 'auto_at_max':
                _require(len(selections) == maximum and actions[-1].startswith('select:'))
            else:
                _require(actions[-1] == 'confirm' and
                         (self.preview_seen if mode == 'preview_confirm' else mode == 'explicit_confirm'))
            _require(p['operation'] == operation and len(p['selected_cards']) == len(selected_set))
            resolved_slots = [c['slot'] for c in p['selected_cards']]
            _require(len(set(resolved_slots)) == len(resolved_slots) and set(resolved_slots) == selected_set)
            for c in p['selected_cards']:
                _require(c['selected'] is True and
                         (c['slot'], c['key'], c['upgrade_level']) in self.child_shape)
            owner = (self.child['parent_decision_id'], self.child['parent_action_id'])
            _require(owner not in self.completed_children and len(self.completed_children) < 4)
            self.completed_children.add(owner)
            self.child_done = True
        self.counts['child_reconciled'] += len(history) - len(self.child_history)
        self.child_history = history
        return status

    def complete_item(self) -> None:
        owner = (self.child['parent_decision_id'], self.child['parent_action_id'])
        _require(owner not in self.completed_children and len(self.completed_children) < 4)
        self.completed_children.add(owner)
        self.completed_items.add(owner)
        self.child_done = True

    def item_set_read(self, p: Any) -> str:
        _keys(p, ('version', 'session_nonce', 'status', 'offer_count', 'collected', 'current'))
        _require(p['version'] == 'item_set_v1' and p['session_nonce'] == self.nonce and
                 type(p['offer_count']) is int and p['offer_count'] == self.child['offer_count'])
        history = p['collected']
        _require(type(history) is list and len(self.item_set_history) <= len(history) <= min(p['offer_count'], len(self.item_set_history)+1) and
                 history[:len(self.item_set_history)] == self.item_set_history)
        if len(history) > len(self.item_set_history):
            _require(self.item_read(history[-1]) == 'resolved')
            self.item_set_history = list(history)
            self.child_shape = None
        status, current = p['status'], p['current']
        _require(status in ('ready', 'waiting', 'unsupported', 'resolved'))
        if status == 'resolved':
            _require(current is None and len(history) == p['offer_count'] == len(self.child_receipts))
            self.complete_item()
        elif status == 'ready':
            _require(len(history) < p['offer_count'] and self.item_read(current) == 'ready')
        elif current is not None:
            _require(status == 'waiting' and self.item_read(current) == 'waiting')
        return status

    def item_parse(self, p: Any) -> None:
        buffer = bytearray(json.dumps(p, separators=(',', ':'), ensure_ascii=True).encode('ascii'))
        try:
            self.item._decode_response(buffer)
        except Exception:
            raise _Stop('invalid_response') from None
        finally:
            buffer[:] = b'\0' * len(buffer)
        _require(p['session_nonce'] == self.nonce)

    def item_read(self, p: Any) -> str:
        self.item_parse(p)
        status = p['status']
        _require(status in ('ready', 'waiting', 'unsupported', 'resolved'))
        if status == 'ready':
            _require(len(self.child_receipts) == len(self.item_set_history) and len(p['offers']) == 1)
            _require(self.child['offer_count']==1 or p['offers'][0]['index']==len(self.item_set_history))
            shape = (p['offers'], p['potion_slots'], p['legal_actions'], p['decision_id'])
            _require(self.child_shape is None or self.child_shape == shape)
            self.child_shape = shape
        elif status == 'resolved':
            _require(len(self.child_receipts) == len(self.item_set_history)+1 and self.child_shape is not None)
            offer = self.child_shape[0][0]
            _require((p['decision_id'], p['action_id']) == self.child_receipts[len(self.item_set_history)] and
                     p['action_id'] == f"collect:{offer['index']}" and
                     (p['offer_index'], p['kind'], p['key'], p['result']) ==
                     (offer['index'], offer['kind'], offer['key'], 'collected'))
            self.counts['child_reconciled'] += 1
            if self.child['offer_count'] == 1:
                self.complete_item()
        return status

    def replay_key(self, decision: str) -> Any:
        if self.child is not None and self.child['kind'] == 'item':
            return tuple(self.child[k] for k in ('parent_decision_id', 'parent_action_id', 'ordinal', 'contract_version')) + (decision,)
        return decision

    def choose(self, p: dict[str, Any]) -> None:
        if self.reads >= 2048:
            raise _Stop('read_limit')
        decision = p['decision_id']
        key = self.replay_key(decision)
        _require(key not in self.used)
        self.used.add(key)
        self.budget()
        try:
            action = self.provider(DecisionView('parent' if self.child is None else self.child['kind'], _freeze(p), _freeze(self.child)))
        except Exception:
            raise _Stop('reentrant_provider' if self.interfered else 'provider_failed') from None
        self.budget()
        if type(action) is not str or action not in p['legal_actions']:
            raise _Stop('invalid_provider')
        if self.child is None:
            candidate = next(c for c in p['candidates'] if c['action_id'] == action)
            self.last_proceed = candidate['is_proceed']
        response = self.call('POST', decision, action)
        _require(response['parent'] is None and response['child'] == self.child)
        receipt = response['payload']
        if self.child is None:
            _keys(receipt, ('version', 'session_nonce', 'decision_id', 'action_id', 'outcome'))
            _require(receipt['version'] == VERSION and receipt['session_nonce'] == self.nonce)
            _require((receipt['decision_id'], receipt['action_id']) == (decision, action))
        elif self.child['kind'] == 'item':
            self.item_parse(receipt)
            _require(receipt['status'] in ('accepted', 'rejected', 'unsupported', 'uncertain'))
            if receipt['status'] == 'accepted':
                _require((receipt['decision_id'], receipt['action_id']) == (decision, action))
        else:
            self.card_parse(receipt)
            _require(receipt['kind'] in ('child_receipt', 'child_failure'))
            if receipt['kind'] == 'child_receipt':
                _require((receipt['decision_id'], receipt['action_id']) == (decision, action))
        outcome = receipt['status'] if self.child is not None and self.child['kind'] == 'item' else receipt['outcome']
        _require(outcome in ('accepted', 'rejected', 'unsupported', 'uncertain', 'stale_decision', 'illegal_action', 'budget_exhausted'))
        if outcome != 'accepted':
            raise _Stop('uncertain_action' if outcome == 'uncertain' else 'unsupported_state')
        if self.child is None:
            self.parent_receipts.append((decision, action))
            self.counts['parent_accepted'] += 1
        else:
            self.child_receipts.append((decision, action))
            self.counts['child_accepted'] += 1

    def run(self) -> dict[str, Any]:
        while True:
            response = self.call('GET')
            p = response['parent']
            status = self.parent_read(p)
            if status == 'unsupported':
                raise _Stop('unsupported_state')
            self.lineage(response['child'])
            _require(self.native['child_episodes'] == self.counts['child_episodes'])
            if self.child is not None:
                _require(status == 'child')
                status = self.child_read(response['payload'])
                if status == 'resolved':
                    continue
                p = response['payload']
                if self.child['kind']=='item' and self.child['offer_count']>1 and status=='ready':
                    p = p['current']
            else:
                _require(response['payload'] is None and status != 'child')
                if status == 'complete':
                    _require(self.last_proceed and self.parent_receipts and len(self.parent_history) == len(self.parent_receipts))
                    _require(self.counts['parent_reconciled'] == self.counts['parent_accepted'])
                    self.effects = response['parent']['effects']
                    return self.summary('resolved', None)
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

    def summary(self, status: str, code: str | None) -> dict[str, Any]:
        return {'schema_version': 1, 'status': status, **self.counts,
                'total_attempted': self.counts['parent_attempted'] + self.counts['child_attempted'],
                'reads': self.reads, 'effects': self.effects,
                'completed_card_children': len(self.completed_children) - len(self.completed_items),
                'completed_item_children': len(self.completed_items), 'code': code}


def run_event(request: Callable, *, provider: Callable, clock: Callable = time.monotonic,
              sleep: Callable = time.sleep) -> dict[str, Any]:
    """Run one flow; stop on uncertainty, invalid input, budget exhaustion or map handoff."""
    active = _ACTIVE.get()
    empty = {'schema_version': 1, 'status': 'failed', **dict.fromkeys(_FIELDS, 0),
             'total_attempted': 0, 'reads': 0, 'effects': 'none_attempted', 'completed_card_children': 0, 'completed_item_children': 0}
    if active is not None:
        active.interfered = True
        return {**empty, 'code': 'reentrant_provider'}
    controller = None
    token = None
    try:
        if not callable(provider):
            raise _Stop('invalid_provider')
        controller = _Controller(request, provider, clock, sleep)
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
    return controller.summary('failed', code) if controller is not None else {**empty, 'code': code}
