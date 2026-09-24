"""Allowlisted public card previews for the first adapter slice.

No reflection over CardState, effect records or continuation dictionaries. New
dynamic mechanisms need a public preview here before they become ready inputs.
"""
from dataclasses import replace

from game.agent import contracts as c
from game.headless.cards import effects as e
from game.headless.cards.operations import Attack, Power, ChoosePileCard, CardOperation, value
from game.headless.cards.silent_effects import Silent
from game.headless.cards.regent_effects import Regent
from game.headless.cards.necrobinder_effects import Necro
from game.headless.cards.defect_effects import Defect
from game.headless.cards.orb_effects import Channel
from game.headless.cards.osty_effects import OstyAttack
from game.headless.powers.status import modify_attack_damage_for_statuses
from .errors import UnsupportedProfile


def counters(values):
    return tuple(c.Counter(key, int(amount)) for key, amount in sorted(values.items()))


def preview(card, player=None, *, on_table=True):
    """A ref-free public descriptor; also the only canonical sorting key."""
    spec = card.spec
    if spec.kind == 'curse':
        raise UnsupportedProfile('curse_variables')
    if player is None and (spec.x_cost or spec.star_x):
        raise UnsupportedProfile('outside_combat_x_cost')
    values = {}
    preview_player = player if on_table else None
    for name in ('end_turn_damage', 'end_turn_hp_loss'):
        if getattr(spec, name):
            values[name] = getattr(spec, name)
    modifiers = {name: 1 for name in ('exhausts', 'ethereal', 'innate', 'retain', 'eternal', 'sly')
                 if getattr(spec, name)}
    for name in ('smog', 'tainted', 'galvanized', 'hexed', 'bound', 'wither_level', 'dampened_levels'):
        if getattr(card.combat_state, name):
            modifiers[name] = int(getattr(card.combat_state, name))
    # Enchantment-specific dynamic variables are not yet mapped. Never quietly
    # report an empty modifier list for an enchanted card.
    if card.enchantment is not None:
        raise UnsupportedProfile('card_enchantment')
    if card.event_data:
        raise UnsupportedProfile('card_event_variables')
    for effect in card.definition.effects:
        if type(effect) in (e.DealDamage, Attack):
            if type(effect) is Attack and (effect.expression != 'base' or effect.hit_expression != 'fixed'):
                raise UnsupportedProfile('card_damage_expression')
            if spec.damage_equals_player_block:
                raise UnsupportedProfile('card_damage_expression')
            damage = spec.base_damage + card.combat_state.extra_damage
            if preview_player is not None:
                damage = modify_attack_damage_for_statuses(
                    max(0, damage + player.rules.powers.get('vigor', 0)), {},
                    player.statuses, player.strength)
            values['damage'] = damage
            values['hits'] = value(card, effect.hits, effect.upgraded_hits) if type(effect) is Attack else 1
            if type(effect) is Attack and effect.fatal_max_hp:
                values['max_hp'] = value(card, effect.fatal_max_hp, effect.upgraded_max_hp)
        elif type(effect) is e.GainBlock:
            values['block'] = player.block_amount(spec.block_gain, powered=True) if preview_player else spec.block_gain
        elif type(effect) is e.DrawCards:
            values['draw'] = spec.draw_count
        elif type(effect) is e.ApplyTargetStatus:
            values[spec.applies_status_name] = spec.applies_status_stacks
        elif type(effect) is Power:
            values[effect.name] = value(card, effect.amount, effect.upgraded_amount)
        elif type(effect) is ChoosePileCard:
            values['select'] = 1
        elif type(effect) is CardOperation and effect.operation == 'choose_discard_to_hand':
            values['select_maximum'] = value(card, effect.amount, effect.upgraded_amount)
        elif type(effect) is Regent and effect.operation == 'blade':
            damage = spec.base_damage + card.combat_state.extra_damage
            values['damage'] = (modify_attack_damage_for_statuses(
                max(0, damage + player.rules.powers.get('vigor', 0)), {}, player.statuses, player.strength)
                if preview_player else damage)
            values['hits'] = 1
        elif type(effect) is Regent and effect.operation == 'parry':
            # Blade's Parry is a power-trigger hook, not another printed amount.
            pass
        elif type(effect) in (Silent, Regent, Necro, Defect):
            keys = {Silent: {'discard': 'discard'}, Regent: {'stars': 'stars', 'forge': 'forge'},
                    Necro: {'summon': 'summon'}, Defect: {'evoke': 'evoke'}}
            if effect.operation not in keys[type(effect)]:
                raise UnsupportedProfile('card_operation')
            values[keys[type(effect)][effect.operation]] = value(card, effect.amount, effect.upgraded_amount)
        elif type(effect) is Channel and effect.count == 'fixed' and effect.kind != 'random':
            values['channel_' + effect.kind] = value(card, effect.amount, effect.upgraded_amount)
        elif (type(effect) is OstyAttack and effect.expression == 'unleash' and
              effect.hits == 'one' and not effect.after and not effect.random):
            values['damage'] = effect.damage(player, card) if player else spec.base_damage
        else:
            raise UnsupportedProfile('card_effect')
    energy = (player.card_cost(card) if player else spec.cost) if spec.cost >= 0 or spec.x_cost else None
    stars = (player.star_cost(card) if player else max(0, spec.star_cost)) if spec.star_cost >= 0 or spec.star_x else None
    cost = c.Cost(c.not_applicable() if energy is None else c.known(energy), spec.x_cost,
                  c.not_applicable() if stars is None else c.known(stars), spec.star_x)
    return c.Card('card:0', card.definition.definition_id, card.upgrade_level, cost,
                  c.known(counters(values)), c.known(counters(modifiers)), c.not_applicable())


def signature(card, player=None, *, on_table=True):
    # Contract serialization is unnecessary here; tuples compare without private
    # card IDs, draw indexes, raw instance counters or RNG state.
    p = preview(card, player, on_table=on_table)
    return (p.definition_id, p.upgrade_level, p.cost.energy.status, p.cost.energy.value or 0,
            p.cost.energy_x, p.cost.stars.status, p.cost.stars.value or 0, p.cost.stars_x,
            tuple((v.key, v.amount) for v in p.values.value),
            tuple((v.key, v.amount) for v in p.modifiers.value))


def project(card, ref, player=None, *, combat=False, on_table=True):
    # An engine original_ids association does not prove a publicly distinguishable
    # deck original. Until such a public observation is available, say unknown.
    return replace(preview(card, player, on_table=on_table), ref=ref,
                   origin=c.unknown() if combat else c.not_applicable())


def resources(card):
    """Resource applicability from public card mechanics, including off-class cards."""
    result = set()
    if card.spec.star_cost >= 0 or card.spec.star_x:
        result.add('regent')
    for effect in card.definition.effects:
        if type(effect) is Regent:
            result.add('regent')
        elif type(effect) in (Necro, OstyAttack):
            result.add('necrobinder')
        elif type(effect) in (Channel, Defect):
            result.add('defect')
    return result
