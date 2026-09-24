"""Versioned public tree vocabulary and bounded padded tensor layout.

Field/type IDs are append-only within a format version. Content names use exact
UTF-8 bytes, not hashes or a vocabulary tied to a private engine catalog.
"""
from dataclasses import dataclass, fields

FORMAT_VERSION = 1
INTEGER_MAX = 2**31 - 1

# Zero is reserved for padding / no link in every indexed table.
FIELDS = (
    'run', 'context', 'character', 'ascension', 'act', 'floor', 'hp', 'max_hp',
    'gold', 'deck', 'relics', 'potions', 'map', 'history', 'status', 'value',
    'ref', 'definition_id', 'upgrade_level', 'cost', 'values', 'modifiers',
    'origin', 'energy', 'energy_x', 'stars', 'stars_x', 'key', 'amount',
    'counters', 'index', 'potion', 'kind', 'damage', 'hits', 'block', 'powers',
    'intents', 'creature', 'passive', 'evoke', 'sovereign_blades', 'osty',
    'orb_slots', 'orbs', 'row', 'column', 'next_nodes', 'current', 'nodes',
    'coverage', 'events', 'subject', 'target', 'round', 'resources', 'enemies',
    'piles', 'count', 'cards', 'order', 'combat', 'source', 'pile', 'options',
    'selected', 'minimum', 'maximum', 'manual_confirmation', 'cancelable',
    'presentation', 'relic', 'resolved', 'entries', 'reachable',
)
NAMESPACES = ('card', 'relic', 'potion', 'enemy', 'power', 'orb', 'reward', 'node')
ACTIONS = ('play_card', 'end_turn', 'select_card', 'deselect_card',
           'confirm_selection', 'cancel_selection', 'claim_reward', 'open_card_reward',
           'choose_reward_card', 'skip_reward', 'leave_rewards', 'choose_map_node')
OUTCOMES = ('victory', 'defeat', 'abandoned', 'truncated')
REASONS = ('none', 'decision_budget', 'time_budget', 'slice_complete', 'act_complete', 'external_stop')

# nodes columns: parent (one-based), field ID, sibling position, type, payload.
OBJECT, ARRAY, NULL, BOOLEAN, INTEGER, TEXT, REFERENCE = range(1, 8)


class EncodingError(ValueError):
    """Malformed/version-mismatched tensors, never a game outcome."""


class CapacityError(EncodingError):
    """The public decision does not fit this explicitly bounded profile."""

    def __init__(self, dimension, required, capacity):
        self.dimension, self.required, self.capacity = dimension, required, capacity
        super().__init__(f'Encoding capacity exceeded: {dimension} requires {required}, limit {capacity}')


@dataclass(frozen=True, slots=True)
class EncodingProfile:
    """Fixed per-environment spaces; changing any capacity changes layout identity.

    A reachable 128-card deck plus its 128 combat copies uses 7,316 public tree
    nodes before history. The default leaves room for targets, selection and
    bounded history; this is a finite slice profile, not an unlimited-run claim.
    """
    nodes: int = 16384
    references: int = 512
    strings: int = 512
    string_bytes: int = 96
    candidates: int = 256

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or not 1 <= value <= INTEGER_MAX:
                raise ValueError(f'{field.name} must be a positive bounded integer')

    @property
    def layout(self):
        return (FORMAT_VERSION, self.nodes, self.references, self.strings,
                self.string_bytes, self.candidates)

    @property
    def identity(self):
        return 'sts_public_graph_v1:' + ':'.join(map(str, self.layout[1:]))


DEFAULT_PROFILE = EncodingProfile()
