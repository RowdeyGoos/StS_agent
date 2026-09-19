"""Owned, serializable selections shared by card and power continuations."""

from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.resolution import push, find, move_out, drain


def begin(p, source, cards, *, operation="move", destination="hand", minimum=1, maximum=1, free="", whitelist=None):
    ids = [c.instance_id for c in cards]
    if not ids:
        return
    maximum = min(maximum, len(ids))
    minimum = min(minimum, maximum)
    p.rules.selection = dict(
        source=source,
        candidates=ids,
        selected=[],
        operation=operation,
        destination=destination,
        minimum=minimum,
        maximum=maximum,
        free=free,
    )
    if whitelist is not None:
        p.rules.selection["whitelist"] = list(whitelist)
    if minimum == len(ids):
        p.rules.selection["selected"] = ids.copy()
        confirm(p)


def actions(p):
    s = p.rules.selection
    selected = s["selected"]
    result = [ChooseCombatCard(i) for i in s["candidates"] if i in selected or len(selected) < s["maximum"]]
    if len(selected) >= s["minimum"]:
        result.append(ConfirmCombatSelection())
    return tuple(result)


def toggle(p, identity):
    s = p.rules.selection
    if ChooseCombatCard(identity) not in actions(p):
        raise ValueError("Illegal combat selection.")
    if identity in s["selected"]:
        s["selected"].remove(identity)
    else:
        s["selected"].append(identity)


def confirm(p):
    s = p.rules.selection
    if len(s["selected"]) < s["minimum"]:
        raise ValueError("Selection is incomplete.")
    p.rules.selection = None
    selected = set(s["selected"])
    candidates = set(s["candidates"])
    p.deck.offered[:] = [c for c in p.deck.offered if c.instance_id not in candidates or c.instance_id in selected]
    if s["operation"] in ("discard", "discard_redraw"):
        from game.headless.core.discard import discard_and_draw
        discard_and_draw(p, [find(p, i) for i in s["selected"]], draw=len(s["selected"]) if s["operation"] == "discard_redraw" else 0)
    else:
        push(p, *[["selected", i, s["operation"], s["destination"], s["free"]] for i in s["selected"]])
    # Resolution can be invoked from a nested choice. Its outer drain owns work.
    if not p._resolving:
        drain(p)


def resolve(p, identity, operation, destination, free):
    card = find(p, identity)
    if card is None or p.combat_is_ending:
        p.deck.offered.clear()
        return
    if operation.startswith("nec_"):
        from game.headless.cards.necrobinder_effects import selected
        selected(p, card, operation)
    elif operation.startswith("regent_"):
        from game.headless.cards.regent_effects import selected
        selected(p, card, operation)
    elif operation in ("hand_trick", "nightmare", "well_laid_plans"):
        from game.headless.powers.silent import selected
        selected(p, card, operation)
    elif operation == "free_combat":
        card.combat_state.free_this_combat = True
        card.combat_state.turn_cost_override = None
    elif operation == "exhaust":
        push(p, ["exhaust", identity])
    elif operation == "discard_redraw":
        move_out(p, card)
        p.deck.discard_card(card)
    elif operation == "transform":
        from game.headless.cards.colorless_effects import transform

        transform(p, card)
    else:
        generated = card in p.deck.offered
        move_out(p, card)
        if free == "free_this_turn":
            from game.headless.core.card_costs import free_this_turn
            free_this_turn(card)
        elif free and (free != "free_until_played" or card.spec.cost >= 0):
            setattr(card.combat_state, free, True)
        if destination == "hand" and len(p.hand) >= 10:
            destination = "discard_pile"
        getattr(p.deck, destination).append(card)
        if generated:
            from game.headless.core.piles import after_generated_entry
            after_generated_entry(p, card)


def refresh_hand_selection(p):
    """Native hand selectors include newly entered, eligible card holders."""
    s = p.rules.selection
    if s is None:
        return
    operation = s['operation']
    if operation.startswith('nec_'):
        op = operation.removeprefix('nec_')
        if op in ('sculpting_strike', 'snap', 'transfigure'):
            from game.headless.cards.necrobinder_effects import choice_settings
            cards, count = choice_settings(p, op)
            s['candidates'] = [c.instance_id for c in cards]
            s['selected'] = [i for i in s['selected'] if i in s['candidates']]
            s['maximum'] = s['minimum'] = min(count, len(cards))
        return
    if operation.startswith('regent_'):
        op = operation.removeprefix('regent_').removesuffix('_up')
        if op in ('begone', 'guards', 'topdeck', 'heirloom_hammer', 'decisions_decisions', 'tyranny'):
            from game.headless.cards.regent_effects import choice_settings
            cards = list(p.hand) if op == 'tyranny' else choice_settings(p, op)[0]
            s['candidates'] = [c.instance_id for c in cards]
            s['selected'] = [i for i in s['selected'] if i in s['candidates']]
            s['maximum'] = min(s['maximum'], len(cards))
            s['minimum'] = min(s['minimum'], s['maximum'])
        return
    hand_ops = {'discard', 'discard_redraw', 'hand_trick', 'nightmare', 'well_laid_plans', 'transform', 'exhaust'}
    if operation not in hand_ops and not (operation == 'move' and s['destination'] == 'draw_pile'):
        return
    cards = list(p.hand)
    if operation == 'hand_trick':
        cards = [c for c in cards if c.spec.kind in ('skill', 'block') and not c.spec.sly]
    elif operation == 'well_laid_plans':
        cards = [c for c in cards if not c.spec.retain]
    s['candidates'] = [c.instance_id for c in cards]
    s['selected'] = [identity for identity in s['selected'] if identity in s['candidates']]
    # Keep the command's original prefs; a new card does not increase a fixed
    # discard/retain count and reaching a singleton does not bypass the open UI.
    s['maximum'] = min(s['maximum'], len(cards))
    s['minimum'] = min(s['minimum'], s['maximum'])
