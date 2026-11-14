"""Public card mechanics without a per-definition content allowlist."""
from dataclasses import fields, is_dataclass
from functools import lru_cache
import json

from game.agent.contracts.full import DESCRIPTION_LIMIT, Field, Node, share_description
from .errors import UnsupportedProfile

# Displayed temporary modifiers. Cost provenance/baselines and allocator fields
# are deliberately absent; their only public consequence is the current cost.
CARD_FLAGS = ('is_dupe', 'smog', 'tainted', 'galvanized', 'hexed', 'bound',
              'wither_level', 'extra_damage', 'replay_count',
              'return_next_turn', 'free_until_played', 'free_this_turn',
              'star_free_this_turn', 'free_this_combat', 'sly_this_turn',
              'sly_this_combat', 'retain_this_turn', 'retain_this_combat',
              'all_enemies', 'ethereal_this_combat')


def public_static(value, kind, name):
    """Immutable content-definition values, never live object introspection."""
    entries, children = [], []
    pairs = ((f.name, getattr(value, f.name)) for f in fields(value)) if is_dataclass(value) else ()
    for key, item in pairs:
        if type(item) in (str, int, bool, type(None)):
            entries.append(Field(key, item))
        elif isinstance(item, tuple) and all(type(v) in (str, int, bool, type(None)) for v in item):
            children.append(Node('parameters', key, fields=tuple(Field(str(i), v) for i, v in enumerate(item))))
        else:
            raise UnsupportedProfile('public_mechanic_parameter:' + key)
    return Node(kind, name, fields=tuple(entries), children=tuple(children))


@lru_cache(maxsize=2048)
def _immutable_static(kind, name, parameters):
    entries, children = [], []
    for key, item_type, item in parameters:
        if item_type is tuple:
            children.append(Node('parameters', key, fields=tuple(Field(str(i), v) for i, (_, v) in enumerate(item))))
        else:
            entries.append(Field(key, item))
    return Node(kind, name, fields=tuple(entries), children=tuple(children))


# Descriptions of frozen definition values by object. Card specs and effects
# are the same objects from one observation to the next; each entry keeps and
# confirms its value, and the store is emptied at its limit.
_STATIC_VALUES = {}


def cached_static(value, kind, name):
    """One shared description per distinct frozen definition value.

    Readers of an observation may reuse what they derived from such a
    description the last time they met it, so it is registered on every use.
    """
    key = (id(value), kind, name)
    entry = _STATIC_VALUES.get(key)
    if entry is not None and entry[0] is value:
        return share_description(entry[1])
    params = getattr(type(value), '__dataclass_params__', None)
    if params is not None and params.frozen:
        parameters = []
        # Dataclass equality can ignore fields, and bool compares equal to int.
        # Key every validated public value explicitly, preserving scalar types.
        for field in fields(value):
            item = getattr(value, field.name)
            if type(item) in (str, int, bool, type(None)):
                parameters.append((field.name, type(item), item))
            elif type(item) is tuple and all(type(v) in (str, int, bool, type(None)) for v in item):
                parameters.append((field.name, tuple, tuple((type(v), v) for v in item)))
            else:
                return public_static(value, kind, name)
        # Every field above is an immutable scalar or tuple of scalars, so this
        # frozen value describes the same thing for as long as it lives.
        result = share_description(_immutable_static(kind, name, tuple(parameters)))
        if len(_STATIC_VALUES) >= DESCRIPTION_LIMIT:
            _STATIC_VALUES.clear()
        _STATIC_VALUES[key] = (value, result)
        return result
    return public_static(value, kind, name)


def card_node(card, ref=None, player=None, *, on_table=False):
    return _card_node(card, ref, player, on_table, public_static)


def _card_node(card, ref, player, on_table, static):
    spec = card.spec
    view = player
    if player is not None and not on_table and player.rules.powers.get('void_form'):
        # The rules' action-cost helper is pile-agnostic for Void Form. Native
        # preview applies that power only in Hand/Play. Use a shallow read view,
        # preserving every other cost layer without mutating the engine.
        from copy import copy
        view = copy(player)
        view.rules = copy(player.rules)
        view.rules.powers = {k: v for k, v in player.rules.powers.items() if k != 'void_form'}
    energy = view.card_cost(card) if view is not None else spec.cost
    stars = view.star_cost(card) if view is not None else spec.star_cost
    values = [Field('upgrade_level', card.upgrade_level), Field('energy', energy),
              Field('stars', stars), Field('rarity', card.definition.rarity),
              Field('pool', card.definition.pool), Field('permanent_damage', card.permanent_damage),
              Field('permanent_block', card.permanent_block)]
    children = [static(spec, 'spec', 'card_spec')]
    children.extend(static(effect, 'mechanic', type(effect).__name__) for effect in card.definition.effects)
    if card.enchantment is not None:
        children.append(static(card.enchantment, 'enchantment', card.enchantment.definition_id))
    if card.event_data:
        # Tinker Time's chosen kind/rider is printed on this created card.
        if set(card.event_data) - {'kind', 'rider'}:
            raise UnsupportedProfile('public_event_card_modifier')
        children.append(Node('modifier', 'mad_science', fields=tuple(Field(k, v) for k, v in sorted(card.event_data.items()))))
    for name in CARD_FLAGS:
        value = getattr(card.combat_state, name)
        if value:
            values.append(Field(name, value))
    return Node('card', card.definition.definition_id, ref, tuple(values), children=tuple(children))


def signature(card, player=None):
    # Only the exact projected description determines multiset ordering.
    return _signature(card_node(card, player=player))


def _signature(value):
    from game.agent.contracts.codec import _wire
    return json.dumps(_wire(value), sort_keys=True, separators=(',', ':'))


# Sort keys of card descriptions, reused across observations: the same
# descriptions recur from one step to the next. Bounded by wholesale clearing,
# which changes no value.
_SIGNATURES = {}
_SIGNATURE_LIMIT = 4096


def _reused_signature(value):
    """_signature(value) for a description built by card_node, without repeating its JSON.

    Such a description has exact strings, scalar field values and no links;
    for anything else a reused answer may differ from the codec's result or
    error, and the observation's own validation still decides.

    The key states every scalar with its exact type, because True == 1 in
    Python while their JSON differs. Children are identified by object: each
    entry retains its description, so a child's identity cannot be reused while
    the entry lives, and an equal key means the very same immutable children.
    A child that is rebuilt for every observation only misses.
    """
    key = (value.kind, value.definition_id, value.ref, value.links,
           tuple((field.key, field.value.__class__, field.value) for field in value.fields),
           tuple(map(id, value.children)))
    entry = _SIGNATURES.get(key)
    if entry is None:
        if len(_SIGNATURES) >= _SIGNATURE_LIMIT:
            _SIGNATURES.clear()
        entry = _SIGNATURES[key] = (value, _signature(value))
    return entry[1]


class CardViews:
    """Reuse descriptions only during one synchronous, read-only projection.

    Private object identities are cache keys, never ordering keys or public data.
    Retain their owners to prevent id reuse, including temporary modified specs.
    Discard the cache before the engine can act or a new observation is built.
    """

    def __init__(self, player=None):
        self.player = player
        self._cards, self._signatures, self._static_values = {}, {}, {}

    def _static(self, value, kind, name):
        key = (id(value), kind, name)
        if key not in self._static_values:
            self._static_values[key] = (value, cached_static(value, kind, name))
        return self._static_values[key][1]

    def card(self, card, ref=None, *, on_table=False):
        key = (id(card), on_table)
        if key not in self._cards:
            self._cards[key] = (card, _card_node(card, None, self.player, on_table, self._static))
        value = self._cards[key][1]
        return value if ref is None else Node(value.kind, value.definition_id, ref,
                                              value.fields, value.links, value.children)

    def signature(self, card):
        key = id(card)
        if key not in self._signatures:
            self._signatures[key] = _reused_signature(self.card(card))
        return self._signatures[key]
