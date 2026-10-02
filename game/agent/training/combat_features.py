"""Optional combat channels derived only from the canonical public graph.

These are descriptions, not an effect simulator: card numbers are printed spec
values and incoming damage is displayed intent pressure, not predicted HP loss.
Unlisted mechanics remain available in the unchanged generic graph.
"""
import hashlib
import json
import math

import numpy as np

GRAPH = 'sts_graph_actor_critic_v1'
COMBAT = 'sts_combat_graph_actor_critic_v1'
from .action_features import REPRESENTATIONS as ACTION_REPRESENTATIONS
COMBAT_REPRESENTATIONS = (COMBAT, *ACTION_REPRESENTATIONS)
REPRESENTATIONS = (GRAPH, *COMBAT_REPRESENTATIONS)
SCHEMA = 'sts_public_combat_channels_v1'

DIRECT = ('hp', 'max_hp', 'block', 'energy', 'stars', 'strength', 'round',
          'upgrade_level', 'extra_damage', 'replay_count', 'alive', 'infinite_hp',
          'minimum', 'maximum', 'amount', 'count')
SPEC = ('base_damage', 'block_gain', 'draw_count', 'damage_equals_player_block',
        'applies_status_stacks', 'exhausts', 'uses_target', 'ethereal',
        'end_turn_damage', 'end_turn_hp_loss', 'innate', 'x_cost', 'retain',
        'eternal', 'sly', 'star_x')
POWERS = ('vulnerable', 'weak', 'frail', 'dexterity', 'poison', 'slippery',
          'intangible', 'artifact', 'thorns', 'ritual', 'plating', 'strength',
          'slow_damage_percent', 'hardened_shell_remaining')
DERIVED = ('displayed_damage', 'displayed_hits', 'attack_intents',
           'unknown_attacks', 'unblocked_displayed_damage', 'hp_fraction')
CHANNELS = (*DIRECT, *('spec.' + k for k in SPEC),
            *('power.' + k for k in POWERS), *DERIVED)
ROLES = ('player', 'enemy', 'hand_card', 'potion', 'selection')
WIDTH = len(CHANNELS) * 3


def feature_identity(vocabulary, representation):
    if representation not in REPRESENTATIONS:
        raise ValueError('Unsupported feature representation')
    if representation == GRAPH:
        return vocabulary.identity
    payload = [SCHEMA, vocabulary.identity, CHANNELS, ROLES,
               'known,number/100,signed_log1p;public_children_v1']
    if representation in ACTION_REPRESENTATIONS:
        from .action_features import SCHEMA as action_schema, CHANNELS as action_channels
        payload.extend((action_schema, representation, action_channels,
                        'candidate_order;known,number/100,signed_log1p;zero_withheld_channels'))
        return action_schema + ':' + hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest()
    return SCHEMA + ':' + hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest()


def _pressure(node):
    attacks = [c for c in node.children if c.kind == 'intent' and c.definition_id == 'attack']
    known = [c for c in attacks if type(c.get('damage')) is int and type(c.get('hits')) is int]
    return {'displayed_damage': sum(c.get('damage') * c.get('hits') for c in known),
            'displayed_hits': sum(c.get('hits') for c in known),
            'attack_intents': len(attacks), 'unknown_attacks': len(attacks) - len(known)}


def channels(nodes, parents):
    """Preserve node order and derive roles from structure, never opaque IDs."""
    values = np.zeros((len(nodes), WIDTH), dtype=np.float32)
    roles = np.full(len(nodes), -1, dtype=np.int64)
    roots = []
    for index, node in enumerate(nodes):
        root = index if parents[index] < 0 else roots[parents[index]]
        roots.append(root)
        current_combat = root != 0 and nodes[root].kind == 'combat'
        data = {field.key: field.value for field in node.fields if field.key in DIRECT}
        parent = nodes[parents[index]] if parents[index] >= 0 else None
        if current_combat and index == root:
            roles[index] = 0
            enemies = [enemy for group in node.children if group.kind == 'enemies'
                       for enemy in group.children if enemy.kind == 'enemy' and enemy.get('alive')]
            # Some fixtures use direct enemy children; both are public trees.
            enemies += [c for c in node.children if c.kind == 'enemy' and c.get('alive')]
            pressure = [_pressure(enemy) for enemy in enemies]
            data.update({key: sum(p[key] for p in pressure)
                         for key in ('displayed_damage', 'displayed_hits', 'attack_intents', 'unknown_attacks')})
            if type(node.get('block')) is int:
                data['unblocked_displayed_damage'] = max(0, data['displayed_damage'] - node.get('block'))
        elif current_combat and node.kind == 'enemy' and parent is not None and (
                parent.kind == 'enemies' or parents[index] == root):
            roles[index] = 1
            data.update(_pressure(node))
        elif node.kind == 'card':
            if current_combat and parent is not None and parents[parents[index]] == root and (
                    parent.kind, parent.definition_id) in (('pile', 'hand'), ('hand', 'hand')):
                roles[index] = 2
            for spec in node.children:
                if spec.kind == 'spec':
                    data.update({'spec.' + field.key: field.value for field in spec.fields if field.key in SPEC})
        elif node.kind == 'potion':
            # Owned slots and an active combat choice source, never shop offers.
            if parent is not None and ((root == 0 and parent.kind == 'potion_slot') or
                                       (current_combat and parents[index] == root)):
                roles[index] = 3
        elif current_combat and node.kind == 'selection' and parents[index] == root:
            roles[index] = 4
        if node.kind in ('combat', 'enemy'):
            powers = [c for c in node.children if c.kind in ('power', 'power_counter')]
            powers += [c for group in node.children if group.kind == 'powers'
                       for c in group.children if c.kind in ('power', 'power_counter')]
            # Missing a named power means zero only on a fully visible creature.
            for power in POWERS:
                matches = [c.get('amount') for c in powers if c.definition_id == power]
                if all(type(v) in (int, bool) for v in matches):
                    data['power.' + power] = sum(matches)
        hp, maximum = node.get('hp'), node.get('max_hp')
        if type(hp) is int and type(maximum) is int and maximum > 0:
            data['hp_fraction'] = hp / maximum
        for column, name in enumerate(CHANNELS):
            value = data.get(name)
            if type(value) in (int, bool, float):
                values[index, 3 * column:3 * column + 3] = (
                    1., float(value) / 100., math.copysign(math.log1p(abs(value)), value))
    values.flags.writeable = roles.flags.writeable = False
    return values, roles
