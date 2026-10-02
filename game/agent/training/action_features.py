"""Candidate-aligned public action previews, separate from the canonical graph."""
import math

import numpy as np

from game.headless.combat_preview import DamagePreview, PublicCombatPreview

CONTROL = 'sts_combat_action_control_actor_critic_v1'
DAMAGE = 'sts_combat_action_damage_actor_critic_v1'
STACKS = 'sts_combat_action_stacks_actor_critic_v1'
REPRESENTATIONS = (CONTROL, DAMAGE, STACKS)
SCHEMA = 'sts_public_vantom_action_preview_v1'
CHANNELS = ('hp_removed', 'block_removed', 'slippery_removed')
WIDTH = 3 * len(CHANNELS)


def mode(representation):
    return REPRESENTATIONS.index(representation) + 1 if representation in REPRESENTATIONS else 0


def _fields(node):
    return {v.key: v.value for v in node.fields}


def _powers(node):
    result = {}
    for child in node.children:
        if child.kind in ('power', 'power_counter'):
            if child.definition_id in result or child.children or type(child.get('amount')) is not int:
                return {'unsupported_power_description': 1}
            result[child.definition_id] = child.get('amount')
    return result


def _card(node):
    base = _fields(node)
    fixed = ('upgrade_level', 'energy', 'stars', 'permanent_damage', 'permanent_block')
    spec = next((n for n in node.children if n.kind == 'spec'), None)
    if spec is None or any(type(base.get(key)) is not int for key in fixed):
        return None
    enchantment = next((n for n in node.children if n.kind == 'enchantment'), None)
    if any(n.kind not in ('spec', 'mechanic', 'enchantment') for n in node.children):
        return None
    mechanics = []
    for n in node.children:
        if n.kind == 'mechanic':
            parameters = _fields(n)
            for child in n.children:
                if child.kind != 'parameters':
                    return None
                parameters[child.definition_id] = tuple(field.value for field in child.fields)
            mechanics.append((n.definition_id, parameters))
    return dict(ref=node.ref, definition_id=node.definition_id,
                **{key: base[key] for key in fixed}, spec=_fields(spec),
                mechanics=mechanics,
                flags={k: v for k, v in base.items() if k not in (*fixed, 'pool', 'rarity')},
                enchantment=_fields(enchantment) if enchantment else None)


def public_context(decision):
    """Only allow listed public fields across the engine-owned preview boundary."""
    root = decision.context
    if root.kind != 'combat':
        return None
    fields = _fields(root)
    required = ('hp', 'max_hp', 'block', 'energy', 'strength', 'round')
    if any(type(fields.get(k)) is not int for k in required):
        return None
    if any(sum(n.kind == kind for n in root.children) != 1 for kind in ('powers', 'enemies', 'resources')):
        return None
    powers = next((n for n in root.children if n.kind == 'powers'), None)
    enemies = next((n for n in root.children if n.kind == 'enemies'), None)
    resources = next((n for n in root.children if n.kind == 'resources'), None)
    if powers is None or enemies is None or resources is None:
        return None
    piles = {}
    names = dict(hand='hand', draw='draw_pile', discard='discard_pile', exhaust='exhaust_pile')
    required_piles = {'hand', 'draw', 'discard', 'exhaust', 'in_play', 'offered', 'sequestered'}
    observed_piles = [n.definition_id for n in root.children if n.kind == 'pile' and n.definition_id != 'powers']
    if set(observed_piles) != required_piles or len(observed_piles) != len(required_piles):
        return None
    if any(n.kind != 'enemy' or type(n.get('alive')) is not bool or
           any(type(n.get(k)) is not int for k in ('hp', 'max_hp', 'block')) for n in enemies.children):
        return None
    for node in root.children:
        if node.kind == 'pile':
            # Observed detached power descriptions are not a current owned pile.
            if node.definition_id == 'powers':
                continue
            cards = [_card(n) for n in node.children]
            if any(c is None for c in cards):
                return None
            piles[names.get(node.definition_id, node.definition_id)] = cards
    if sum(n.kind == 'relics' for n in decision.run.children) != 1:
        return None
    relics = next((n for n in decision.run.children if n.kind == 'relics'), None)
    if relics is None:
        return None
    return dict(character=decision.run.get('character'), player={k: fields[k] for k in required},
        powers=_powers(powers), piles=piles,
        selection=any(n.kind == 'selection' for n in root.children),
        resources=bool(resources.children), stars=resources.get('stars', 0),
        enemies=[dict(definition_id=n.definition_id, ref=n.ref, hp=n.get('hp'), max_hp=n.get('max_hp'),
                      alive=n.get('alive'), block=n.get('block'), powers=_powers(n)) for n in enemies.children],
        relics=[dict(definition_id=n.definition_id, melted=n.get('melted', False),
                     show_counter=n.get('show_counter'), display_counter=n.get('display_counter'),
                     status=n.get('status')) for n in relics.children])


def previews(decision):
    context = public_context(decision)
    predictor = PublicCombatPreview(context)
    target = context['enemies'][0]['ref'] if context and len(context['enemies']) == 1 else None
    return {action.ref: (predictor.action(action.subject, action.target)
            if action.kind == 'play_card' and (action.target is None or action.target == target)
            else DamagePreview(reason='action_kind_or_target')) for action in decision.candidates}


def channels(decision, candidate_refs, representation):
    value = np.zeros((len(candidate_refs), WIDTH), dtype=np.float32)
    selected = mode(representation)
    if not selected:
        raise ValueError('Unsupported action preview representation')
    if selected > 1:
        predicted = previews(decision)
        for row, ref in enumerate(candidate_refs):
            preview = predicted[ref]
            if preview.known:
                for col, name in enumerate(CHANNELS[:2 if selected == 2 else 3]):
                    number = getattr(preview, name)
                    value[row, 3 * col:3 * col + 3] = (
                        1., number / 100., math.copysign(math.log1p(abs(number)), number))
    value.flags.writeable = False
    return value
