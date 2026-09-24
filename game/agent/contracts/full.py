"""Version 2 public graph for the complete headless decision surface.

The graph is an immutable, explicitly projected view, never a serialized engine.
Field names describe public mechanics; links alone carry episode-local identities.
The v1 live contract is intentionally unchanged.
"""
from dataclasses import dataclass
import json
import re
from typing import Literal

from .codec import ContractError, _read, _wire, _unique_object, _invalid_constant
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
           'sacrifice_card_reward', 'continue_act', 'abandon_run', 'open_reward', 'close_reward')
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


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def validate(decision):
    definitions, links = {}, []
    def visit(node, depth=0):
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


def dumps(value):
    return json.dumps(to_dict(value), sort_keys=True, separators=(',', ':'), allow_nan=False)


def loads(text):
    try:
        return from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant))
    except (TypeError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ContractError('Invalid public JSON') from error
