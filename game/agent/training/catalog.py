"""Frozen public content knowledge for learned features, never live game state.

Definitions describe possible content, not which content a run will encounter.
Checkpoints carry their own copy; inference does not consult today's catalogs.
These descriptors are printed/base mechanics, not predicted action outcomes.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json

from game.agent.contracts import full as f

SCHEMA = 'sts_public_feature_catalog_v1'
ENTITY_KINDS = frozenset(('card', 'potion', 'relic', 'enemy', 'power',
                          'power_counter', 'enchantment', 'orb'))
COVERAGE = ('identity', 'public_observation', 'partial', 'structured')


@dataclass(frozen=True, slots=True)
class Entry:
    kind: str
    definition_id: str
    coverage: str = 'identity'
    fields: tuple[f.Field, ...] = ()


@dataclass(frozen=True, slots=True)
class PublicCatalog:
    names: tuple[str, ...]
    entries: tuple[Entry, ...]

    def __post_init__(self):
        def name(value):
            return type(value) is str and len(value.encode('utf-8')) <= 256
        if (type(self.names) is not tuple or len(self.names) > 65536 or
                any(not name(n) for n in self.names) or self.names != tuple(sorted(set(self.names))) or
                type(self.entries) is not tuple or len(self.entries) > 10000):
            raise ValueError('Invalid public feature catalog')
        keys = []
        required = set()
        for entry in self.entries:
            if (type(entry) is not Entry or not name(entry.kind) or not entry.kind or
                    not name(entry.definition_id) or not entry.definition_id or
                    entry.coverage not in COVERAGE or type(entry.fields) is not tuple or len(entry.fields) > 256):
                raise ValueError('Invalid public catalog entry')
            keys.append((entry.kind, entry.definition_id))
            required.update((entry.kind, entry.definition_id))
            field_keys = []
            for field in entry.fields:
                if (type(field) is not f.Field or not name(field.key) or
                        not field.key.startswith('catalog.') or type(field.value) not in (str, int, bool, type(None)) or
                        type(field.value) is str and not name(field.value) or
                        type(field.value) is int and not -(2**63) <= field.value < 2**63):
                    raise ValueError('Invalid public catalog field')
                field_keys.append(field.key)
                required.add(field.key)
                if type(field.value) is str:
                    required.add(field.value)
            if field_keys != sorted(set(field_keys)):
                raise ValueError('Unordered or duplicate public catalog fields')
        if keys != sorted(set(keys)) or not required <= set(self.names):
            raise ValueError('Incomplete or duplicate public catalog names')

    def to_dict(self):
        return dict(schema=SCHEMA, names=list(self.names), entries=[dict(
            kind=e.kind, definition_id=e.definition_id, coverage=e.coverage,
            fields=[dict(key=v.key, value=v.value) for v in e.fields]) for e in self.entries])

    @classmethod
    def from_dict(cls, value):
        if (type(value) is not dict or set(value) != {'schema', 'names', 'entries'} or
                value['schema'] != SCHEMA or type(value['names']) is not list or type(value['entries']) is not list):
            raise ValueError('Unsupported public feature catalog')
        entries = []
        for entry in value['entries']:
            if (type(entry) is not dict or set(entry) != {'kind', 'definition_id', 'coverage', 'fields'} or
                    type(entry['fields']) is not list or any(type(v) is not dict or
                    set(v) != {'key', 'value'} for v in entry['fields'])):
                raise ValueError('Invalid public catalog entry fields')
            entries.append(Entry(entry['kind'], entry['definition_id'], entry['coverage'],
                                 tuple(f.Field(**v) for v in entry['fields'])))
        return cls(tuple(value['names']), tuple(entries))

    @property
    def identity(self):
        data = json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        return SCHEMA + ':' + hashlib.sha256(data.encode()).hexdigest()


def _entry(kind, name, coverage='identity', **values):
    return Entry(kind, name, coverage, tuple(f.Field('catalog.' + key, value)
                                           for key, value in sorted(values.items())))


@lru_cache(maxsize=1)
def public_catalog():
    """Enumerate only explicit immutable registries and public card descriptions.

    No campaign construction, monster instantiation, snapshot, dataset or private
    object traversal is needed. The cached result is recursively immutable.
    """
    from game.headless.cards.catalog import DEFAULT_CARDS
    from game.headless.potions.base import POTIONS
    from game.headless.potions.selections import SETTINGS
    from game.headless.relics.base import RELICS
    from game.headless.monsters.catalog import DEFAULT_MONSTERS
    from game.headless.enchantments.base import ENCHANTMENTS
    from game.headless.core.orbs import KINDS
    from game.headless.characters import CHARACTERS
    from game.headless.events.catalog import EVENTS
    from game.headless.encounters.catalog import ENCOUNTERS
    from game.headless.powers.status import SUPPORTED_STATUS_NAMES
    from game.headless.powers.ironclad import POWER_NAMES
    from game.headless.powers import colorless, silent, regent, necrobinder, defect, hive
    from game.headless.potions import powers as potion_powers
    from game.agent.headless.full_cards import CARD_FLAGS, card_node
    from game.agent.headless.full_projection import ENEMY_COUNTERS
    from game.agent.headless.full_relics import WRAPPED
    from .relic_features import fields as relic_fields

    names = set(f.NAMESPACES) | set(f.ACTIONS) | set(CHARACTERS) | set(EVENTS) | set(ENCOUNTERS)
    names.update(CARD_FLAGS)
    names.update(('run', 'combat', 'deck', 'pile', 'hand', 'draw', 'discard', 'exhaust',
                  'in_play', 'offered', 'sequestered', 'powers', 'enemies', 'resources',
                  'relics', 'potions', 'potion_slot', 'map', 'history', 'selection',
                  'hp', 'max_hp', 'block', 'energy', 'round', 'stars', 'strength',
                  'amount', 'count', 'alive', 'slot', 'order', 'canonical', 'visible',
                  'normal', 'active', 'disabled', 'show_counter', 'display_counter',
                  'status', 'wax', 'melted', 'infinite_hp', 'orb_slots', 'passive', 'evoke',
                  'history_event', 'history_subject', 'history_target'))
    entries = []
    for definition in DEFAULT_CARDS.definitions:
        entries.append(_entry('card', definition.definition_id, 'public_observation'))
        for level in range(len(definition.levels)):
            card = DEFAULT_CARDS.create(definition.definition_id, upgrade_level=level)
            for node in f.walk(card_node(card)):
                names.update((node.kind, node.definition_id))
                names.update(v.key for v in node.fields)
                names.update(v.value for v in node.fields if type(v.value) is str)
    for name, potion in POTIONS.items():
        values = dict(rarity=potion.rarity, usage=potion.usage, targeted=potion.targeted)
        for i, effect in enumerate(potion.effects):
            values[f'effect.{i}.kind'] = effect[0]
            # Typed positional operands preserve every immutable authored value.
            for j, value in enumerate(effect[1:]):
                values[f'effect.{i}.arg.{j}'] = value
        if name in SETTINGS:
            pile, operation, free, optional, all_cards = SETTINGS[name]
            values.update(selection_pile=pile, selection_operation=operation,
                          selection_cost_modifier=free, selection_optional=optional,
                          selection_all_eligible=all_cards)
            if operation == 'move':
                values['selection_destination'] = 'hand'
        entries.append(_entry('potion', name, 'structured', **values))
    for name, relic in RELICS.items():
        values = dict(rarity=relic.rarity)
        # Only nonzero declared mechanics: absence is not a claim of no effect.
        for key in ('victory_heal', 'pickup_max_hp', 'pickup_gold', 'combat_strength'):
            if getattr(relic, key):
                values[key] = getattr(relic, key)
        if relic.evolve_after_elites:
            values.update(evolve_after_elites=relic.evolve_after_elites, evolves_into=relic.evolves_into)
        if relic.adds_pet:
            values['adds_pet'] = True
        if relic.pickup_transform:
            values.update(pickup_transform_from=relic.pickup_transform[0], pickup_transform_to=relic.pickup_transform[1])
        if name in WRAPPED:
            values['display_counter_period'] = WRAPPED[name]
        values.update(relic_fields(name))
        values['description_complete'] = False
        entries.append(_entry('relic', name, 'partial' if len(values) > 2 else 'identity', **values))
    powers = set(SUPPORTED_STATUS_NAMES) | set(POWER_NAMES)
    for module in (colorless, silent, regent, necrobinder, defect, hive, potion_powers):
        powers.update(module.NAMES)
    powers.update(('nightmare', 'dampen', 'hex', 'self_forming_clay', 'diamond_diadem'))
    counters = set(ENEMY_COUNTERS) | powers | {'hardened_shell_remaining', 'slow_damage_percent',
                                             'crimson_mantle', 'inferno', 'block_gains'}
    for kind, identifiers in (('enemy', DEFAULT_MONSTERS), ('enchantment', ENCHANTMENTS),
                              ('orb', KINDS), ('power', powers), ('power_counter', counters)):
        entries.extend(_entry(kind, name) for name in sorted(identifiers))
    for entry in entries:
        names.update((entry.kind, entry.definition_id))
        names.update(v.key for v in entry.fields)
        names.update(v.value for v in entry.fields if type(v.value) is str)
    return PublicCatalog(tuple(sorted(names)), tuple(sorted(entries, key=lambda e: (e.kind, e.definition_id))))
