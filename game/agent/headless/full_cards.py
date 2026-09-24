"""Public card mechanics without a per-definition content allowlist."""
from dataclasses import fields, is_dataclass
import json

from game.agent.contracts.full import Field, Node
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


def card_node(card, ref=None, player=None, *, on_table=False):
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
    children = [public_static(spec, 'spec', 'card_spec')]
    children.extend(public_static(effect, 'mechanic', type(effect).__name__) for effect in card.definition.effects)
    if card.enchantment is not None:
        children.append(public_static(card.enchantment, 'enchantment', card.enchantment.definition_id))
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
    from game.agent.contracts.codec import _wire
    return json.dumps(_wire(card_node(card, player=player)), sort_keys=True, separators=(',', ':'))
