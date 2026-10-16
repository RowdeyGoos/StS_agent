"""One public semantic projection for every study actor, critic and replay.

Canonical observations stay lossless and unchanged. Network arrays are a
declared lossy mechanical view; strings and physical identity spellings never
enter the no-vocabulary arrays, including their ordering.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import math
import numpy as np

from game.agent.contracts import full as f
from game.agent.encoding.full import FullRunEncoder
from game.agent.action_policy import action_mask, validate_policy
from game.agent.input_views import RAW
from ..catalog import PublicCatalog, Entry, public_catalog
from .history import PublicHistory, current_combat_context, enemies, intent
from .spec import (FeatureSpec, ROLES, PILES, STATUSES, KINDS, TRIGGERS, TARGETS,
                   EXPRESSIONS, EFFECT_SLOTS, channels)


@lru_cache(maxsize=1)
def study_catalog():
    """Static rules only; no snapshots, demonstrations or held-out cases."""
    from game.headless.cards.catalog import DEFAULT_CARDS
    original = public_catalog()
    types = {d.definition_id: d.levels[0].kind for d in DEFAULT_CARDS.definitions}
    entries = tuple(Entry(e.kind, e.definition_id, e.coverage,
        e.fields + (f.Field('catalog.card_type', types[e.definition_id]),)) if e.kind == 'card' else e
        for e in original.entries)
    names = set(original.names) | {'catalog.card_type'} | set(types.values())
    return PublicCatalog(tuple(sorted(names)), entries)


@dataclass(frozen=True, slots=True)
class StudyFeatures:
    vocabulary: str
    feature_identity: str
    values: np.ndarray
    identities: np.ndarray
    parents: np.ndarray
    candidates: np.ndarray
    candidate_refs: tuple[str, ...]
    policy_mask: tuple[bool, ...]
    legal_mask: tuple[bool, ...]
    action_policy: str
    capacity: int
    graph: object = None
    input_view: str = RAW

    @property
    def nbytes(self):
        return sum(a.nbytes for a in (self.values, self.identities, self.parents, self.candidates))

    def for_rollout(self):
        return replace(self, graph=None)


class Row:
    def __init__(self, indexes):
        self.indexes = indexes
        self.values = np.zeros(len(indexes), dtype=np.float32)

    def number(self, key, value):
        i = self.indexes.get(key + '.known')
        if i is not None and type(value) in (bool, int, float) and math.isfinite(value):
            self.values[i:i+3] = (1, float(value) / 100, math.copysign(math.log1p(abs(value)), value))

    def category(self, key, value):
        i = self.indexes.get(key + '=' + str(value), self.indexes.get(key + '=unknown'))
        if i is not None:
            self.values[i] = 1


def _upgraded(node, key, level):
    alternate = node.get('upgraded_' + key)
    return alternate if level and alternate is not None else node.get(key)


def _card_effect(node, level, spec=None):
    names = dict(DealDamage='damage', Attack='damage', RandomEnemyAttack='damage', GainBlock='block',
                 DrawCards='draw', GainEnergy='energy', LoseHp='hp_loss', ApplyTargetStatus='status',
                 Power='status', SelectHandCard='select', ChoosePileCard='select')
    kind = names.get(node.definition_id, 'unknown')
    if node.definition_id == 'CardOperation':
        kind = {'energy': 'energy', 'heal': 'heal', 'hp_loss': 'hp_loss',
                'random_exhaust': 'exhaust', 'choose_discard_to_hand': 'select'}.get(node.get('operation'), 'unknown')
    status = node.get('name')
    operation = node.get('operation') if kind == 'select' else None
    mode = _upgraded(node, 'mode', level)
    expression = node.get('expression', 'fixed')
    amount = _upgraded(node, 'amount', level)
    if spec is not None:
        if node.definition_id in ('Attack','DealDamage','RandomEnemyAttack'):
            amount = spec.get('base_damage') if amount is None else amount
        elif node.definition_id == 'GainBlock':
            amount = spec.get('block_gain')
        elif node.definition_id == 'DrawCards':
            amount = spec.get('draw_count')
        elif node.definition_id == 'ApplyTargetStatus':
            amount, status = spec.get('applies_status_stacks'), spec.get('applies_status_name')
        if node.definition_id == 'DealDamage':
            expression = 'block' if spec.get('damage_equals_player_block') else 'base'
    complete = (kind != 'unknown' and (kind != 'status' or status in STATUSES)
                and expression in EXPRESSIONS and expression != 'unknown'
                and (kind != 'select' or operation in ('exhaust', 'upgrade', 'discard', 'move', 'retain', 'copy')
                     or node.definition_id == 'ChoosePileCard'))
    target = ('all_enemies' if node.get('all_enemies') else
              'random_enemy' if node.definition_id == 'RandomEnemyAttack' else
              'enemy' if node.get('target') is True or kind in ('damage', 'status') and spec and spec.get('uses_target') else
              node.get('pile', 'hand' if kind == 'select' else 'self'))
    represented = {'amount', 'upgraded_amount', 'hits', 'upgraded_hits', 'factor', 'upgraded_factor',
        'expression', 'hit_expression', 'name', 'target', 'pile', 'all_enemies', 'operation', 'mode',
        'upgraded_mode', 'destination', 'minimum', 'maximum'}
    if any(v.value not in (None, False, 0, '') and v.key not in represented for v in node.fields):
        complete = False
    return dict(kind=kind, trigger='play', amount=amount,
                hits=(_upgraded(node, 'hits', level) or 1) if kind == 'damage' else None,
                factor=1 if expression=='block' and node.definition_id=='DealDamage' else _upgraded(node, 'factor', level),
                expression=expression, hit_expression=node.get('hit_expression', 'fixed'), operation=operation, mode=mode,
                minimum=node.get('minimum'), maximum=node.get('maximum'),
                triggered=node.get('triggered'), extra_damage=node.get('extra_damage'),
                destination=node.get('destination'), status=status, target=target, complete=complete)


def _item_effects(entry):
    values = {v.key.removeprefix('catalog.'): v.value for v in entry.fields}
    rules = {}
    for key, value in values.items():
        parts = key.split('.')
        if len(parts) >= 3 and parts[0] in ('rule', 'effect') and parts[1].isdigit():
            rules.setdefault(int(parts[1]), {})['.'.join(parts[2:])] = value
    result = []
    for _, rule in sorted(rules.items()):
        # Potion positional operands have authored kind-specific semantics.
        kind = rule.get('kind', 'unknown')
        original_kind = kind
        status = rule.get('status')
        if kind in STATUSES:
            kind, status = 'status', kind
        if entry.kind == 'potion':
            amount = rule.get('arg.0')
            original_kind = kind
            if kind in ('status', 'power', 'temporary', 'all_status') and type(amount) is str:
                status, amount = amount, rule.get('arg.1')
                kind = 'status'
            kind = {'area': 'damage', 'heal_percent': 'heal', 'upgrade_hand': 'upgrade',
                    'fill': 'generate_potion', 'exhaust_hand': 'exhaust'}.get(kind, kind)
            rule = dict(rule, amount=amount, trigger='play',
                target='all_enemies' if original_kind in ('area', 'all_status') else
                    'enemy' if values.get('targeted') else 'self',
                duration='turn' if original_kind == 'temporary' else 'combat')
        represented = {'kind', 'trigger', 'target', 'amount', 'hits', 'factor', 'every', 'turn', 'uses',
                       'minimum', 'maximum', 'status', 'expression', 'operation', 'mode', 'destination', 'duration'}
        complete = (kind in KINDS and kind != 'unknown' and (kind != 'status' or status in STATUSES)
                    and all(k in represented for k in rule)
                    and rule.get('trigger') in TRIGGERS and rule.get('target', 'self') in TARGETS
                    and original_kind != 'heal_percent')
        result.append(dict(rule, kind=kind if kind in KINDS else 'unknown', status=status,
                           complete=complete))
    return result


class StudyEncoder:
    def __init__(self, vocabulary, architecture, *, action_policy):
        self.vocabulary, self.architecture = vocabulary, architecture
        self.spec = FeatureSpec.from_dict(architecture.features)
        self.action_policy, self.input_view = validate_policy(action_policy), RAW
        self.identity = architecture.identity(vocabulary)
        self.public = FullRunEncoder()
        self.indexes = {name: i for i, (_, name) in enumerate(channels(self.spec.richness))}
        self.names = {n: i+1 for i, n in enumerate(vocabulary.names)}
        catalog = PublicCatalog.from_dict(architecture.catalog)
        self.catalog = {(e.kind, e.definition_id): e for e in catalog.entries}
        self.history = PublicHistory({e.definition_id: next(v.value for v in e.fields if v.key == 'catalog.card_type')
                                     for e in catalog.entries if e.kind == 'card'}, self.catalog)

    def effects(self, row, effects, *, complete):
        if len(effects) > EFFECT_SLOTS:
            raise ValueError('Study effect-slot overflow; never clip mechanics')
        row.number('mechanics.description_complete', complete and all(e['complete'] for e in effects))
        for i, effect in enumerate(effects):
            prefix = f'mechanics.effect.{i}.'
            row.number(prefix + 'present', True)
            for key in ('kind', 'trigger', 'target', 'status', 'expression', 'hit_expression', 'duration', 'operation', 'mode', 'destination'):
                if key in effect:
                    row.category(prefix + key, effect[key])
            for key in ('amount', 'hits', 'factor', 'every', 'turn', 'uses', 'minimum', 'maximum', 'triggered', 'extra_damage', 'complete'):
                row.number(prefix + key, effect.get(key))

    def card(self, row, node):
        spec = next((n for n in node.children if n.kind == 'spec'), None)
        row.number('energy', node.get('energy'))
        row.number('stars', node.get('stars'))
        if spec is None:
            return
        row.category('card_type', 'skill' if spec.get('kind') == 'block' else spec.get('kind'))
        if not self.spec.enabled('card'):
            return
        for target, source in (('damage', 'base_damage'), ('card_block', 'block_gain'), ('draw', 'draw_count'), ('uses_target', 'uses_target')):
            row.number(target, spec.get(source))
        mechanics = [n for n in node.children if n.kind in ('mechanic', 'enchantment', 'modifier')]
        attacks = [n for n in mechanics if n.definition_id in ('Attack', 'RandomEnemyAttack', 'DealDamage')]
        hits = 0
        for effect in attacks:
            if effect.get('hit_expression', 'fixed') != 'fixed':
                hits = None
                break
            hits += _upgraded(effect, 'hits', node.get('upgrade_level')) or 1
        row.number('hits', hits)
        row.number('all_enemies', bool(node.get('all_enemies')) or any(n.get('all_enemies') for n in attacks))
        if self.spec.richness != 'basic':
            from game.agent.headless.full_cards import CARD_FLAGS
            for key in CARD_FLAGS:
                row.number('card.' + key, node.get(key, 0))
            for v in (*node.fields, *spec.fields):
                row.number('card.' + v.key, v.value)
            self.effects(row, [_card_effect(n, node.get('upgrade_level'), spec) for n in mechanics], complete=True)

    def powers(self, row, owner):
        if not self.spec.enabled('powers'):
            return
        values = {s: 0 for s in STATUSES}
        unknown, types = 0, 0
        values['strength'] = owner.get('strength', 0)
        for power in f.walk(owner):
            if power is not owner and power.kind in ('enemy', 'card'):
                continue
            if power.kind not in ('power', 'power_counter'):
                continue
            amount = power.get('amount')
            if power.definition_id in values:
                values[power.definition_id] += amount if type(amount) in (int, bool) else 0
            else:
                unknown += amount if type(amount) in (int, bool) else 0
                types += 1
        for key, value in dict(values, unknown_stacks=unknown, unknown_types=types).items():
            if 'turn_context' in self.spec.ablations and key in ('block_gains', 'slow_damage_percent'):
                continue
            row.number('power.' + key, value)

    def _rows(self, decision):
        if decision.context.kind != 'combat':
            raise ValueError('Study supports combat and its nested choices only')
        self.history.require_current(decision)
        context = current_combat_context(decision)
        entries, refs = [], {}
        def add(role, node, *, pile=None, position=None):
            row = Row(self.indexes)
            row.category('role', role)
            if pile:
                row.category('pile', pile)
            if position is not None:
                row.number('position', position)
            for key in ('hp', 'max_hp', 'block', 'alive', 'infinite_hp', 'slot'):
                row.number(key, node.get(key))
            entries.append((row, node, role))
            return row
        player = add('player', context)
        for key in ('energy', 'stars'):
            value = context.get(key)
            if value is None:
                value = next((n.get(key) for n in context.children if n.kind == 'resources'), None)
            player.number(key, value)
        power_owner = f.Node('player', 'player', fields=context.fields,
                            children=tuple(n for n in context.children if n.kind == 'powers'))
        self.powers(player, power_owner)
        selection = next((n for n in context.children if n.kind == 'selection'), None)
        options, selected = set(selection.linked('options') if selection else ()), set(selection.linked('selected') if selection else ())
        source_refs = set(selection.linked('source') if selection else ())
        sources = [n for n in (*f.walk(context), *f.walk(decision.run)) if n.ref in source_refs]
        selection_group = ('card' if any(n.kind == 'card' for n in sources) else
                           'items' if any(n.kind in ('potion', 'relic') for n in sources) else
                           'powers' if any(n.kind in ('power', 'power_counter') for n in sources) else None)
        if selection:
            row = add('selection', selection)
            for key in ('minimum', 'maximum', 'manual_confirmation'):
                row.number(key, selection.get(key))
            row.number('selected', len(selected))
            if (selection_group is None and not set(self.spec.ablations) & {'card', 'items', 'powers'}
                    or selection_group is not None and selection_group not in self.spec.ablations):
                row.category('selection.operation', selection.definition_id)
                row.category('selection.destination', selection.get('destination'))
                row.category('selection.cost_modifier', selection.get('cost_modifier'))
        for pile in (n for n in context.children if n.kind == 'pile'):
            if pile.definition_id == 'powers' and 'powers' in self.spec.ablations:
                continue
            player.number('count.' + pile.definition_id, pile.get('count'))
            for position, card in enumerate(pile.children):
                # Offered choices and subjects remain represented even when
                # hidden-pile composition is removed. Only public options count.
                if (pile.definition_id not in ('hand', 'offered', 'in_play') and
                        not self.spec.enabled('piles') and card.ref not in options | source_refs):
                    continue
                row = add('card', card, pile=pile.definition_id,
                          position=position if pile.definition_id == 'hand' else None)
                self.card(row, card)
                row.number('eligible', card.ref in options)
                row.number('selected', card.ref in selected)
                row.number('selection_source', card.ref in source_refs)
        for enemy in sorted(enemies(decision), key=lambda n: n.get('slot')):
            row = add('enemy', enemy)
            self.powers(row, enemy)
            if self.spec.enabled('intent'):
                profile = intent(enemy)
                for icon in profile['icons']:
                    row.category('intent', icon)
                if profile['present']:
                    for key in ('damage', 'hits'):
                        row.number('intent.' + key, profile[key])
            if self.spec.enabled('enemy_history'):
                profiles = self.history.profiles.get(enemy.get('slot'), ())
                row.number('history.complete', self.history.complete or len(profiles) == 3)
                for i, profile in enumerate(profiles):
                    for key, value in dict(profile, age=self.history.round-profile['round']).items():
                        if key == 'icons':
                            for icon in value:
                                row.category(f'history.{i}.intent', icon)
                        else:
                            if key == 'phase_observed' and 'items' in self.spec.ablations:
                                continue
                            row.number(f'history.{i}.' + key, value)
        groups = [n for n in decision.run.children if n.kind in ('potions', 'relics')]
        groups += [n for n in decision.context.children if n.kind in ('potion', 'relic')]
        item_refs = set()
        for group in groups:
            for node in f.walk(group):
                if node.kind not in ('potion', 'relic'):
                    continue
                if node.ref in item_refs:
                    continue
                item_refs.add(node.ref)
                row = add(node.kind, node)
                if self.spec.enabled('items'):
                    entry = self.catalog.get((node.kind, node.definition_id))
                    self.effects(row, _item_effects(entry) if entry else [], complete=bool(entry and entry.coverage == 'structured'))
                    for value in node.fields:
                        if 'turn_context' not in self.spec.ablations or value.key in ('wax', 'melted', 'remaining_combats'):
                            row.number('item.' + value.key, value.value)
                    if 'turn_context' not in self.spec.ablations:
                        row.category('item.status', node.get('status'))
        for action in f.ACTIONS:
            player.number('actions.' + action, sum(a.kind == action for a in decision.candidates))
        if self.spec.enabled('turn_context'):
            for key, value in self.history.counts.items():
                # Completeness itself can reveal repeat/auto-play mechanics.
                # Remove this derived path along with its source family.
                if set(self.spec.ablations) & {'card', 'powers', 'items'}:
                    continue
                player.number('turn.' + key, value)
            player.number('turn.round', decision.context.get('round'))
            for key in ('act', 'floor', 'gold', 'ascension'):
                player.number('turn.' + key, decision.run.get(key))
        if self.spec.enabled('threat'):
            living = [n for n in enemies(decision) if n.get('alive')]
            player.number('threat.living_enemies', len(living))
            for key in ('hp', 'block'):
                values = [n.get(key) for n in living]
                player.number('threat.enemy_' + key, sum(values) if all(type(v) is int for v in values) else None)
            if self.spec.enabled('intent'):
                profiles = [intent(n) for n in living]
                pressure = sum(p['damage'] for p in profiles) if all(p['present'] and p['damage'] is not None for p in profiles) else None
                hp, block = decision.context.get('hp'), decision.context.get('block')
                unblocked = max(0, pressure - block) if pressure is not None and type(block) is int else None
                player.number('threat.pressure', pressure)
                player.number('threat.unblocked', unblocked)
                player.number('threat.pressure_hp_ratio', pressure/hp if pressure is not None and type(hp) is int and hp > 0 else None)
                player.number('threat.displayed_lethal', unblocked >= hp if unblocked is not None and type(hp) is int and hp > 0 else None)
        # Identity-independent sorting even though the canonical draw pile uses
        # definition names. Equal semantic rows have equal network meaning.
        entries = entries[:1] + sorted(entries[1:], key=lambda e: (ROLES.index(e[2]), e[0].values.tobytes(),
            e[1].definition_id if self.spec.identities else ''))
        for i, (_, node, _) in enumerate(entries):
            if node.ref:
                refs[node.ref] = i
        for row, node, role in entries:
            row.number('selection_source', node.ref in source_refs or role == 'player' and
                       any(n.kind in ('power', 'power_counter') for n in sources))
        return entries, refs

    def encode(self, decision):
        mapping = self.public.pack(decision)
        return self._encode(decision, mapping)

    def encode_inference(self, decision):
        owner = f.PreparedPublic(decision)
        mapping = self.public.mapping_prepared(owner.value, owner)
        return self._encode(decision, mapping).for_rollout()

    def _encode(self, decision, mapping):
        entries, refs = self._rows(decision)
        if len(entries) > self.spec.entities or len(mapping.candidate_refs) > self.spec.candidates:
            raise ValueError('Study padding capacity overflow; never clip entities or candidates')
        by_ref = {a.ref: a for a in decision.candidates}
        permissions = dict(zip((a.ref for a in decision.candidates), action_mask(decision, self.action_policy)))
        candidates = []
        for ref in mapping.candidate_refs:
            action = by_ref[ref]
            for operand in (action.subject, action.target):
                if operand is not None and operand not in refs:
                    raise ValueError('Study candidate operand has no semantic entity')
            candidates.append((f.ACTIONS.index(action.kind), refs.get(action.subject, -1), refs.get(action.target, -1)))
        identities = [self.names.get(n.definition_id, 0) if self.spec.identities and role in ('card', 'enemy', 'potion', 'relic') else 0
                      for _, n, role in entries]
        selection = next((n for n in decision.context.children if n.kind == 'selection'), None)
        source_ref = next(iter(selection.linked('source')), None) if selection else None
        parents = [-1] + [refs.get(source_ref, 0) if role == 'selection' else 0 for _, _, role in entries[1:]]
        return StudyFeatures(self.vocabulary.identity, self.identity,
            np.stack([r.values for r, _, _ in entries]), np.asarray(identities, dtype=np.int64),
            np.asarray(parents, dtype=np.int64), np.asarray(candidates, dtype=np.int64),
            mapping.candidate_refs, tuple(permissions[r] for r in mapping.candidate_refs),
            (True,)*len(candidates), self.action_policy, self.spec.entities, mapping)
