"""Owned, serializable selections shared by card and power continuations."""

from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.resolution import push, find, move_out, drain


def begin(p, source, cards, *, operation="move", destination="hand", minimum=1, maximum=1, free=""):
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
    p.deck.offered[:] = [c for c in p.deck.offered if c.instance_id in selected]
    trailing = [["draw", len(s["selected"]), False]] if s["operation"] == "discard_redraw" else []
    push(p, *[["selected", i, s["operation"], s["destination"], s["free"]] for i in s["selected"]], *trailing)
    # Resolution can be invoked from a nested choice. Its outer drain owns work.
    if not p._resolving:
        drain(p)


def resolve(p, identity, operation, destination, free):
    card = find(p, identity)
    if card is None or p.combat_is_ending:
        p.deck.offered.clear()
        return
    if operation == "free_combat":
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
        move_out(p, card)
        if free and (free != "free_until_played" or card.spec.cost >= 0):
            setattr(card.combat_state, free, True)
        if destination == "hand" and len(p.hand) >= 10:
            destination = "discard_pile"
        getattr(p.deck, destination).append(card)
