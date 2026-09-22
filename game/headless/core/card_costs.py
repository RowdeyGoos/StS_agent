"""Chronology of owned absolute local cost setters and their expiration."""


def mark_setter(state, kind):
    state.cost_discount_baselines[kind] = state.until_played_discount
    for existing in ('combat', 'turn', 'played'):
        if getattr(state, existing + '_cost_override') is not None and existing not in state.cost_override_order:
            state.cost_override_order.append(existing)
    state.cost_override_order.remove(kind)
    state.cost_override_order.append(kind)


def until_played(card, cost):
    v = card.combat_state
    v.played_cost_override = cost
    v.played_cost_baselines = [v.cost_change, v.turn_cost_change, v.combat_cost_change]
    mark_setter(v, 'played')


def latest(state):
    active = [k for k in state.cost_override_order if getattr(state, k + '_cost_override') is not None]
    # Older setters/fixtures without a chronology retain the existing precedence.
    for key in ('combat', 'turn', 'played'):
        if getattr(state, key + '_cost_override') is not None and key not in active:
            active.append(key)
    return active[-1] if active else None


def validate(values):
    discounts = values['cost_discount_baselines']
    if not isinstance(discounts, dict) or any(k not in ('combat', 'turn', 'played') or type(v) is not int or not 0 <= v <= values['until_played_discount'] for k,v in discounts.items()):
        raise ValueError('Invalid cost discount baselines.')
    cost = values['played_cost_override']
    baseline = values['played_cost_baselines']
    order = values['cost_override_order']
    if cost is not None and (type(cost) is not int or cost != 0):
        raise ValueError('Invalid until-played local cost.')
    if not isinstance(baseline, list) or len(baseline) != 3 or any(type(n) is not int for n in baseline):
        raise ValueError('Invalid until-played cost baselines.')
    if not isinstance(order, list) or any(k not in ('combat', 'turn', 'played') for k in order) or len(set(order)) != len(order):
        raise ValueError('Invalid local cost setter order.')

    active = {k for k in ('combat', 'turn', 'played') if values[k + '_cost_override'] is not None}
    if len(active) > 1 and not active <= set(order):
        raise ValueError('Missing active local cost setter order.')


def free_this_turn(card):
    """Native SetToFreeThisTurn: energy until play/end, Stars until turn end."""
    v = card.combat_state
    v.turn_cost_override = 0
    v.turn_cost_until_played = True
    v.override_turn_baseline = v.cost_change + v.turn_cost_change
    v.override_combat_baseline = v.combat_cost_change
    v.free_this_turn = False
    v.star_free_this_turn = True
    mark_setter(v, 'turn')
