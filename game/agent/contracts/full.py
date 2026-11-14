"""Version 2 public graph for the complete headless decision surface.

The graph is an immutable, explicitly projected view, never a serialized engine.
Field names describe public mechanics; links alone carry episode-local identities.
The v1 live contract is intentionally unchanged.
"""
from dataclasses import dataclass
import json
import re
from typing import Literal

from .codec import ContractError, _EXACT_WIRE, _read, _read_record, _wire, _wire_fields, _unique_object, _invalid_constant
from .models import RunOutcome

SCHEMA = 'sts_public_decision_v2'
PROFILE = 'full_run_v2'
NAMESPACES = ('card', 'relic', 'potion', 'enemy', 'power', 'orb', 'reward', 'node',
              'option', 'offer', 'cell')
ACTIONS = ('play_card', 'end_turn', 'select_card', 'deselect_card', 'confirm_selection',
           'cancel_selection', 'choose_map_node', 'claim_gold', 'choose_reward_card',
           'skip_reward', 'claim_potion', 'claim_relic', 'leave_rewards', 'rest', 'smith',
           'hatch', 'choose_upgrade', 'leave_rest', 'use_potion', 'discard_potion',
           'buy_shop_item', 'begin_shop_removal', 'choose_shop_removal', 'leave_shop',
           'open_chest', 'claim_treasure_relic', 'leave_treasure', 'choose_event_option',
           'leave_event', 'choose_event_card', 'choose_ancient_relic', 'choose_relic_card',
           'deselect_relic_card', 'confirm_relic_selection', 'choose_relic_reward',
           'lift', 'dig', 'use_rest_relic', 'choose_cook_card', 'deselect_cook_card',
           'confirm_cook', 'choose_extra_reward', 'reroll_card_reward',
           'sacrifice_card_reward', 'continue_act', 'abandon_run', 'open_reward', 'close_reward',
           'open_shop', 'close_shop')
_REF = re.compile(r'(' + '|'.join(NAMESPACES) + r'):[0-9]+\Z')


@dataclass(frozen=True, slots=True)
class Field:
    key: str
    value: str | int | bool | None


@dataclass(frozen=True, slots=True)
class Link:
    key: str
    targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Node:
    kind: str
    definition_id: str
    ref: str | None = None
    fields: tuple[Field, ...] = ()
    links: tuple[Link, ...] = ()
    children: tuple['Node', ...] = ()

    def get(self, key, default=None):
        return next((field.value for field in self.fields if field.key == key), default)

    def linked(self, key):
        return next((link.targets for link in self.links if link.key == key), ())


@dataclass(frozen=True, slots=True)
class Candidate:
    ref: str
    kind: str
    subject: str | None = None
    target: str | None = None


@dataclass(frozen=True, slots=True)
class PublicDecision:
    schema: Literal['sts_public_decision_v2']
    profile: Literal['full_run_v2']
    run: Node
    context: Node
    candidates: tuple[Candidate, ...]


# Exact-type equivalents of codec._wire and of _read_record(..., PublicDecision)
# for the fixed graph records. Any other type defers to the generic code at that
# same position, so output, key order and error precedence are unchanged.
_SCALAR = (str, int, bool, type(None))


def _wire_field(value):
    key = value.key
    key = key if type(key) in _SCALAR else _wire(key)
    item = value.value
    return {'key': key, 'value': item if type(item) in _SCALAR else _wire(item)}


def _wire_link(value):
    key = value.key
    key = key if type(key) in _SCALAR else _wire(key)
    targets = value.targets
    return {'key': key, 'targets': [t if type(t) in _SCALAR else _wire(t) for t in targets]
            if type(targets) is tuple else _wire(targets)}


def _wire_node(value):
    # Read and convert each field in declaration order, exactly as _wire does.
    kind = value.kind
    kind = kind if type(kind) in _SCALAR else _wire(kind)
    definition_id = value.definition_id
    definition_id = definition_id if type(definition_id) in _SCALAR else _wire(definition_id)
    ref = value.ref
    ref = ref if type(ref) in _SCALAR else _wire(ref)
    fields = value.fields
    fields = [_wire_field(v) if type(v) is Field else _wire(v) for v in fields] if type(fields) is tuple else _wire(fields)
    links = value.links
    links = [_wire_link(v) if type(v) is Link else _wire(v) for v in links] if type(links) is tuple else _wire(links)
    children = value.children
    children = ([_wire_node(v) if type(v) is Node else _wire(v) for v in children]
                if type(children) is tuple else _wire(children))
    return {'kind': kind, 'definition_id': definition_id, 'ref': ref,
            'fields': fields, 'links': links, 'children': children}


for _type, _keys in ((Field, ('key', 'value')), (Link, ('key', 'targets')),
                     (Node, ('kind', 'definition_id', 'ref', 'fields', 'links', 'children'))):
    if _wire_fields(_type) != _keys:
        raise RuntimeError('Specialized wire layout differs from its record fields')
_EXACT_WIRE.update({Field: _wire_field, Link: _wire_link, Node: _wire_node})


class _Generic(Exception):
    """Leave this value to the generic schema reader."""


def _clone_node(value, depth):
    # validate() rejects depth > 24; deeper input keeps the generic path.
    if depth > 24:
        raise _Generic
    kind, definition_id, ref = value.kind, value.definition_id, value.ref
    fields, links, children = value.fields, value.links, value.children
    if (type(kind) is not str or type(definition_id) is not str or (ref is not None and type(ref) is not str)
            or type(fields) is not tuple or type(links) is not tuple or type(children) is not tuple):
        raise _Generic
    cloned_fields = []
    for field in fields:
        if type(field) is not Field or type(field.key) is not str or type(field.value) not in _SCALAR:
            raise _Generic
        cloned_fields.append(Field(field.key, field.value))
    cloned_links = []
    for link in links:
        targets = link.targets if type(link) is Link else None
        if type(targets) is not tuple or type(link.key) is not str or any(type(t) is not str for t in targets):
            raise _Generic
        cloned_links.append(Link(link.key, (*targets,)))
    cloned_children = []
    for child in children:
        if type(child) is not Node:
            raise _Generic
        cloned_children.append(_clone_node(child, depth + 1))
    return Node(kind, definition_id, ref, tuple(cloned_fields), tuple(cloned_links), tuple(cloned_children))


def _clone_decision(value):
    """_read_record(value, PublicDecision, '$') for exact-typed input; None defers."""
    try:
        if (type(value) is not PublicDecision or type(value.schema) is not str or value.schema != SCHEMA
                or type(value.profile) is not str or value.profile != PROFILE
                or type(value.run) is not Node or type(value.context) is not Node
                or type(value.candidates) is not tuple):
            raise _Generic
        candidates = []
        for c in value.candidates:
            if (type(c) is not Candidate or type(c.ref) is not str or type(c.kind) is not str
                    or (c.subject is not None and type(c.subject) is not str)
                    or (c.target is not None and type(c.target) is not str)):
                raise _Generic
            candidates.append(Candidate(c.ref, c.kind, c.subject, c.target))
        return PublicDecision(value.schema, value.profile, _clone_node(value.run, 0),
                              _clone_node(value.context, 0), tuple(candidates))
    except (_Generic, AttributeError):
        # Includes hand-built records with unset slots: the generic reader keeps
        # its own field order and error.
        return None


# Descriptions that a producer builds once and places in many observations:
# a card's printed spec and its mechanics. A registered description is an exact
# record tree without references or links that has passed every per-node check
# of validate(). Readers may therefore keep what they derived from it and look
# it up by object; each such reader confirms the object itself, never only its
# id. Registration is an optimisation: an unregistered node is read in full.
# The registry and every reader's store are emptied when they reach the limit,
# which changes no value: a producer registers a description again whenever it
# uses it. An entry with height None records a node that cannot be shared.
_DESCRIPTIONS = {}
DESCRIPTION_LIMIT = 4096


def _description_height(node):
    """Height of a subtree that validate() accepts at any depth it fits, else None."""
    if node.ref is not None or node.links or not node.kind or not node.definition_id:
        return None
    keys = [field.key for field in node.fields]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        return None
    if any(type(field.value) is str and _REF.fullmatch(field.value) for field in node.fields):
        return None
    height = 0
    for child in node.children:
        below = _description_height(child)
        if below is None:
            return None
        height = max(height, below + 1)
    return height


def share_description(node):
    """Register an immutable description that recurs across observations; returns `node`.

    A producer calls this each time it places the description, so that a
    description still in use is registered again after the registry was emptied.
    """
    entry = _DESCRIPTIONS.get(id(node))
    if entry is None or entry[0] is not node:
        if len(_DESCRIPTIONS) >= DESCRIPTION_LIMIT:
            _DESCRIPTIONS.clear()
        _DESCRIPTIONS[id(node)] = (node, _description_height(node)
                                   if type(node) is Node and _exact_node(node, 0) else None)
    return node


def shared_height(node):
    """Height of `node` if this very object is a registered description, else None."""
    entry = _DESCRIPTIONS.get(id(node))
    return entry[1] if entry is not None and entry[0] is node else None


def remember(store, node, *values):
    """Keep what a reader derived from a shared description, within the registry's bound."""
    if len(store) >= DESCRIPTION_LIMIT:
        store.clear()
    store[id(node)] = (node, *values)


def _exact_node(value, depth):
    """True exactly when _clone_node(value, depth) returns an equal copy."""
    if depth > 24:
        return False
    shared = _DESCRIPTIONS.get(id(value))
    if shared is not None and shared[0] is value and shared[1] is not None:
        # Checked record by record when it was registered; only its depth varies.
        return depth + shared[1] <= 24
    fields, links, children = value.fields, value.links, value.children
    if (type(value.kind) is not str or type(value.definition_id) is not str
            or (value.ref is not None and type(value.ref) is not str)
            or type(fields) is not tuple or type(links) is not tuple or type(children) is not tuple):
        return False
    for field in fields:
        if type(field) is not Field or type(field.key) is not str or type(field.value) not in _SCALAR:
            return False
    for link in links:
        targets = link.targets if type(link) is Link else None
        if type(targets) is not tuple or type(link.key) is not str or any(type(t) is not str for t in targets):
            return False
    for child in children:
        if type(child) is not Node or not _exact_node(child, depth + 1):
            return False
    return True


def _exact_decision(value):
    """True exactly when _clone_decision(value) returns an equal copy, not None."""
    try:
        if (type(value) is not PublicDecision or type(value.schema) is not str or value.schema != SCHEMA
                or type(value.profile) is not str or value.profile != PROFILE
                or type(value.run) is not Node or type(value.context) is not Node
                or type(value.candidates) is not tuple):
            return False
        for c in value.candidates:
            if (type(c) is not Candidate or type(c.ref) is not str or type(c.kind) is not str
                    or (c.subject is not None and type(c.subject) is not str)
                    or (c.target is not None and type(c.target) is not str)):
                return False
        return _exact_node(value.run, 0) and _exact_node(value.context, 0)
    except AttributeError:
        return False


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def validate(decision):
    definitions, links = {}, []
    def visit(node, depth=0):
        shared = _DESCRIPTIONS.get(id(node))
        if shared is not None and shared[0] is node and shared[1] is not None and depth + shared[1] <= 24:
            # A registered description has no reference or link and passed the
            # checks below when it was registered; a too-deep one is read in full.
            return
        if depth > 24 or not node.kind or not node.definition_id:
            raise ContractError('Invalid public graph node')
        if node.ref is not None:
            if not _REF.fullmatch(node.ref) or node.ref in definitions:
                raise ContractError('Invalid or duplicate entity reference')
            definitions[node.ref] = node
        for entries in (node.fields, node.links):
            keys = [entry.key for entry in entries]
            if any(not key for key in keys) or len(keys) != len(set(keys)):
                raise ContractError('Duplicate or empty public field')
        for field in node.fields:
            if isinstance(field.value, str) and _REF.fullmatch(field.value):
                raise ContractError('References must use public links')
        links.extend(node.links)
        for child in node.children:
            visit(child, depth + 1)
    visit(decision.run)
    visit(decision.context)
    if decision.run.kind != 'run' or not decision.candidates:
        raise ContractError('A ready decision needs a run and legal candidates')
    for link in links:
        if any(not _REF.fullmatch(ref) for ref in link.targets):
            raise ContractError('Malformed public link')
        if link.key not in ('history_subject', 'history_target') and any(ref not in definitions for ref in link.targets):
            raise ContractError('Unresolved public link')
    seen, semantic = set(), set()
    for action in decision.candidates:
        if (not re.fullmatch(r'action:[0-9]+', action.ref) or action.ref in seen
                or action.kind not in ACTIONS):
            raise ContractError('Invalid public candidate')
        seen.add(action.ref)
        if any(ref is not None and ref not in definitions for ref in (action.subject, action.target)):
            raise ContractError('Candidate argument is not a public entity')
        key = (action.kind, action.subject, action.target)
        if key in semantic:
            raise ContractError('Ambiguous public candidate')
        semantic.add(key)


def from_dict(value):
    if type(value) is dict and value.get('schema') == 'sts_run_outcome_v1':
        from .codec import from_dict as legacy
        return legacy(value)
    if type(value) is not dict or value.get('schema') != SCHEMA:
        raise ContractError('Unsupported full-run schema')
    result = _read(value, PublicDecision, '$')
    validate(result)
    return result


def to_dict(value):
    if isinstance(value, RunOutcome):
        from .codec import to_dict as legacy
        return legacy(value)
    if type(value) is not PublicDecision:
        raise ContractError('Expected a full-run public decision')
    wire = _wire(value)
    from_dict(wire)
    return wire


def require_ready(value):
    to_dict(value)


@dataclass(frozen=True, slots=True, init=False, eq=False)
class PreparedPublic:
    """One owned, validated public value for cooperating in-process consumers.

    The parsed value is canonical and deeply immutable, even if the input used
    mutable record objects. Wire copies belong to their caller. This owner never
    carries an engine, dispatch binding or private state, and is not a wire type.
    """
    _value: PublicDecision | RunOutcome

    def __init__(self, value):
        if type(value) is PublicDecision:
            canonical = _clone_decision(value)
            if canonical is None:
                canonical = _read_record(value, PublicDecision, '$')
            validate(canonical)
        else:
            canonical = from_dict(to_dict(value))
        object.__setattr__(self, '_value', canonical)

    @classmethod
    def adopt(cls, value):
        """Own a decision its producer has just built, without copying it.

        Only for a producer that hands the value over and never writes to it
        again. A graph of exact records is already canonical and immutable, so
        it is checked as the constructor checks its copy and then kept as it
        is: `owner.value is value`. Any other input takes the constructor,
        with the same result and the same errors.
        """
        if not _exact_decision(value):
            return cls(value)
        validate(value)
        owner = object.__new__(cls)
        object.__setattr__(owner, '_value', value)
        return owner

    @property
    def value(self):
        return self._value

    def require(self, value):
        if value is not self._value:
            raise ContractError('Prepared observation does not belong to this decision')

    def wire_for(self, value):
        self.require(value)
        # Materialize only when a wire consumer needs it. Canonical field order
        # and fresh containers preserve ownership without a retained dict tree.
        return _wire(self._value)


def dumps(value):
    return json.dumps(to_dict(value), sort_keys=True, separators=(',', ':'), allow_nan=False)


def loads(text):
    try:
        return from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant))
    except (TypeError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ContractError('Invalid public JSON') from error
