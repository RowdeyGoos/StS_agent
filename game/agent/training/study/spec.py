"""Frozen, orthogonal study factors and explicit mechanical feature channels."""
from dataclasses import asdict, dataclass
import hashlib
import json

SCHEMA = 'sts_combat_feature_study_v1'
HISTORY = 'sts_observed_combat_history_v1'
ARCHITECTURES = ('graph', 'pooled_mlp', 'attention', 'flat_mlp')
COMPACT_ARCHITECTURES = ('compact_pooled_mlp', 'hierarchical_pooled_mlp')
RICHNESS = ('basic', 'mechanics', 'context')
ABLATIONS = ('card', 'powers', 'intent', 'items', 'piles', 'enemy_history', 'turn_context', 'threat')
ROLES = ('player', 'enemy', 'card', 'potion', 'relic', 'selection')
PILES = ('hand', 'draw', 'discard', 'exhaust', 'in_play', 'offered', 'sequestered')
# These are mechanical categories, never fitted content names or class-name IDs.
STATUSES = ('strength', 'dexterity', 'weak', 'vulnerable', 'frail', 'poison', 'intangible',
            'artifact', 'thorns', 'ritual', 'plating', 'no_draw', 'no_block', 'retain_hand',
            'energy_next_turn', 'draw_next_turn', 'temporary_strength', 'block_gains',
            'slow_damage_percent', 'hardened_shell_remaining', 'slippery', 'shrink',
            'territorial', 'mangle', 'demise', 'dark_shackles')
INTENTS = ('attack', 'defend', 'buff', 'debuff', 'shuffle', 'stun', 'sleep', 'escape', 'unknown')
KINDS = ('damage', 'block', 'draw', 'energy', 'heal', 'hp_loss', 'status', 'select',
         'exhaust', 'upgrade', 'generate_card', 'generate_potion', 'retain', 'unknown')
TRIGGERS = ('play', 'combat_start', 'turn_start', 'before_draw', 'after_draw', 'before_end',
            'after_end', 'attack_card_played', 'skill_card_played', 'power_card_played',
            'card_played', 'exhaust', 'hp_loss', 'victory', 'pickup', 'unknown')
TARGETS = ('self', 'enemy', 'all_enemies', 'random_enemy', 'hand', 'draw_pile', 'discard_pile',
           'exhaust_pile', 'deck', 'selected_hand_cards', 'unknown')
EXPRESSIONS = ('base', 'fixed', 'x', 'plays', 'exhaust', 'draw_pile', 'vulnerable',
               'hp_loss', 'debuffs', 'strikes', 'block', 'unknown')
EFFECT_SLOTS = 8


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    richness: str = 'context'
    identities: bool = False
    ablations: tuple[str, ...] = ()
    entities: int = 128
    candidates: int = 2048
    history: str = HISTORY
    schema: str = SCHEMA

    def __post_init__(self):
        if (self.schema != SCHEMA or self.history != HISTORY or self.richness not in RICHNESS
                or type(self.identities) is not bool or type(self.ablations) is not tuple
                or len(set(self.ablations)) != len(self.ablations)
                or not set(self.ablations) <= set(ABLATIONS)
                or type(self.entities) is not int or not 8 <= self.entities <= 2048
                or type(self.candidates) is not int or not 1 <= self.candidates <= 2048):
            raise ValueError('Invalid frozen study feature specification')
        if self.ablations and (self.identities or self.richness != 'context'):
            raise ValueError('Study ablations require the rich no-vocabulary parent')

    def enabled(self, group):
        levels = dict(card=0, intent=0, powers=1, items=1, piles=1,
                      enemy_history=2, turn_context=2, threat=2)
        return group not in self.ablations and RICHNESS.index(self.richness) >= levels[group]

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != set(cls.__dataclass_fields__):
            raise ValueError('Unsupported study feature fields')
        return cls(**{**value, 'ablations': tuple(value['ablations'])})


def channels(richness):
    """Ablations keep their parent's dimensions; richness removes whole blocks."""
    columns = []
    def number(group, name):
        columns.extend((group, name + '.' + suffix) for suffix in ('known', 'scaled', 'log'))
    def category(group, name, values):
        columns.extend((group, name + '=' + v) for v in values)
    category('base', 'role', ROLES)
    category('base', 'pile', PILES)
    for key in ('hp', 'max_hp', 'block', 'energy', 'stars', 'alive', 'infinite_hp',
                'slot', 'position', 'minimum', 'maximum', 'selected', 'eligible', 'manual_confirmation', 'selection_source'):
        number('base', key)
    category('base', 'selection.operation', ('exhaust', 'upgrade', 'discard', 'move', 'retain',
             'topdeck', 'copy', 'transform', 'unknown'))
    category('base', 'selection.destination', TARGETS)
    category('base', 'selection.cost_modifier', ('', 'free_until_played', 'free_this_turn', 'free_this_combat', 'unknown'))
    for pile in PILES:
        number('base', 'count.' + pile)
    from game.agent.contracts.full import ACTIONS
    for action in ACTIONS:
        number('base', 'actions.' + action)
    category('card', 'card_type', ('attack', 'skill', 'power', 'status', 'curse', 'unknown'))
    for key in ('damage', 'card_block', 'draw', 'uses_target', 'all_enemies', 'hits'):
        number('card', key)
    for key in ('damage', 'hits'):
        number('intent', 'intent.' + key)
    category('intent', 'intent', INTENTS)
    if richness in ('mechanics', 'context'):
        from game.agent.headless.full_cards import CARD_FLAGS
        for key in (*CARD_FLAGS, 'permanent_damage', 'permanent_block', 'upgrade_level',
                    'exhausts', 'ethereal', 'end_turn_damage', 'end_turn_hp_loss', 'innate',
                    'x_cost', 'retain', 'eternal', 'sly', 'star_x', 'damage_equals_player_block'):
            number('card', 'card.' + key)
        # The same typed operands represent card, potion and relic mechanics.
        for group in ('mechanics',):
            number(group, group + '.description_complete')
            for slot in range(EFFECT_SLOTS):
                prefix = f'{group}.effect.{slot}.'
                category(group, prefix + 'kind', KINDS)
                category(group, prefix + 'trigger', TRIGGERS)
                category(group, prefix + 'target', TARGETS)
                category(group, prefix + 'status', (*STATUSES, 'unknown'))
                category(group, prefix + 'expression', EXPRESSIONS)
                category(group, prefix + 'hit_expression', EXPRESSIONS)
                category(group, prefix + 'operation', ('exhaust', 'upgrade', 'discard', 'move', 'retain', 'copy', 'unknown'))
                category(group, prefix + 'mode', ('choose', 'random', 'all', 'unknown'))
                category(group, prefix + 'destination', TARGETS)
                category(group, prefix + 'duration', ('turn', 'combat', 'permanent', 'until_played', 'unknown'))
                for key in ('present', 'amount', 'hits', 'factor', 'every', 'turn', 'uses',
                            'minimum', 'maximum', 'triggered', 'extra_damage', 'complete'):
                    number(group, prefix + key)
        for key in (*STATUSES, 'unknown_stacks', 'unknown_types'):
            number('powers', 'power.' + key)
        category('items', 'item.status', ('active', 'normal', 'disabled', 'unavailable_on_attachment', 'unknown'))
        for key in ('counter', 'display_counter', 'show_counter', 'wax', 'melted', 'remaining_combats'):
            number('items', 'item.' + key)
    if richness == 'context':
        for slot in range(3):
            for key in ('present', 'damage', 'hits', 'age', 'phase_observed'):
                number('enemy_history', f'history.{slot}.' + key)
            category('enemy_history', f'history.{slot}.intent', INTENTS)
        number('enemy_history', 'history.complete')
        for key in ('plays', 'attacks', 'skills', 'zero_cost_attacks', 'energy_spent', 'status_draws',
                    'round', 'act', 'floor', 'gold', 'ascension'):
            number('turn_context', 'turn.' + key)
        for key in ('pressure', 'unblocked', 'pressure_hp_ratio', 'displayed_lethal',
                    'living_enemies', 'enemy_hp', 'enemy_block'):
            number('threat', 'threat.' + key)
    return tuple(columns)


@dataclass(frozen=True, slots=True)
class StudyArchitecture:
    hidden_size: int
    kind: str
    features: dict
    catalog: dict
    message_layers: int = 2
    schema: str = SCHEMA

    def __post_init__(self):
        if (self.schema != SCHEMA or self.kind not in ARCHITECTURES + COMPACT_ARCHITECTURES or self.message_layers != 2
                or type(self.hidden_size) is not int or not 8 <= self.hidden_size <= 1024
                or self.kind == 'attention' and self.hidden_size % 4):
            raise ValueError('Invalid study architecture')
        object.__setattr__(self, 'features', FeatureSpec.from_dict(self.features).to_dict())
        if self.kind in COMPACT_ARCHITECTURES and self.features['identities']:
            raise ValueError('Compact study encoders currently require no content vocabulary')
        from ..catalog import PublicCatalog
        PublicCatalog.from_dict(self.catalog)

    def identity(self, vocabulary):
        spec = FeatureSpec.from_dict(self.features)
        if self.kind in COMPACT_ARCHITECTURES:
            from .compact import layout_binding
            return SCHEMA + ':' + digest(dict(features=spec.to_dict(),
                compact=layout_binding(spec.richness), catalog=self.catalog,
                vocabulary=vocabulary.to_dict(), history=HISTORY))
        return SCHEMA + ':' + digest(dict(features=spec.to_dict(), columns=channels(spec.richness),
            catalog=self.catalog, vocabulary=vocabulary.to_dict(), history=HISTORY))
