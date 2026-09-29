"""Versioned policy restrictions over complete public legal candidates.

These rules never dispatch, change game legality, reorder candidates or inspect
engine state. The canonical decision remains the source of every command.
"""
from game.agent.contracts import full as f

ALL_LEGAL = 'all_legal_v1'
COMMIT_SINGLE_CARD = 'commit_single_card_v1'
COMMIT_CARD_SELECTION = 'commit_card_selection_v1'
POLICIES = (ALL_LEGAL, COMMIT_SINGLE_CARD, COMMIT_CARD_SELECTION)


def validate_policy(name):
    if type(name) is not str or name not in POLICIES:
        raise ValueError('Unsupported policy-action version')
    return name


def action_mask(decision, policy=ALL_LEGAL):
    """Return policy permission in the original public candidate order.

The original singleton policy requires a preceding public select witness. The
broader commitment policy treats selected cards as committed members,
including on attachment. Neither policy changes order or dispatches confirmation.
Unrecognized shapes retain their complete legal support.
    """
    validate_policy(policy)
    if type(decision) is not f.PublicDecision:
        raise ValueError('Policy actions require a public decision')
    allowed = (True,) * len(decision.candidates)
    if policy == ALL_LEGAL:
        return allowed
    if policy == COMMIT_CARD_SELECTION:
        return _commit_selection(decision, allowed)
    context = decision.context
    if context.kind == 'relic_choice' and context.definition_id == 'select':
        selection = context
        choose, undo, confirm = 'choose_relic_card', 'deselect_relic_card', 'confirm_relic_selection'
    elif context.kind in ('combat', 'rest'):
        selections = [n for n in f.walk(context) if n.kind == 'selection']
        if len(selections) != 1:
            return allowed
        selection = selections[0]
        choose, undo, confirm = 'select_card', 'deselect_card', 'confirm_selection'
    else:
        return allowed
    if (type(selection.get('minimum')) is not int or type(selection.get('maximum')) is not int or
            selection.get('minimum') != 1 or selection.get('maximum') != 1 or
            selection.get('manual_confirmation', True) is not True):
        return allowed
    selected = selection.linked('selected')
    if len(selected) != 1 or len(decision.candidates) != 2:
        return allowed
    by_kind = {a.kind: a for a in decision.candidates}
    if (set(by_kind) != {undo, confirm} or by_kind[undo].subject != selected[0] or
            by_kind[undo].target is not None or by_kind[confirm].subject is not None or
            by_kind[confirm].target is not None):
        return allowed
    histories = [n for n in decision.run.children if n.kind == 'history']
    if len(histories) != 1 or not histories[0].children:
        return allowed
    last = histories[0].children[-1]
    if (last.kind != 'history_event' or last.definition_id != choose or
            last.linked('history_subject') != selected or last.linked('history_target')):
        return allowed
    return tuple(a.kind == confirm for a in decision.candidates)


def _commit_selection(decision, unrestricted):
    """Remove undo only on known deferred selectors with complete public choices.

From an empty selector, every ordered subset remains reachable by choosing its
members in that order and then confirming. Preselected attachments deliberately
commit their inherited members too, retaining native slot ordering. No history
or hidden engine state is needed.
    """
    context = decision.context
    extras = set()
    if context.kind == 'combat':
        selections = [n for n in f.walk(context) if n.kind == 'selection']
        if len(selections) != 1 or selections[0].get('manual_confirmation') is not True:
            return unrestricted
        selection = selections[0]
        choose, undo, confirm = 'select_card', 'deselect_card', 'confirm_selection'
        options = selection.linked('options')
    elif context.kind == 'relic_choice' and context.definition_id == 'select':
        selection = context
        choose, undo, confirm = 'choose_relic_card', 'deselect_relic_card', 'confirm_relic_selection'
        options = selection.linked('options')
    elif context.kind == 'rest' and context.get('stage') == 'cook':
        if (context.get('minimum'), context.get('maximum')) != (2, 2):
            return unrestricted
        selection = context
        choose, undo, confirm = 'choose_cook_card', 'deselect_cook_card', 'confirm_cook'
        options = selection.linked('options')
        extras = {'cancel_selection', 'use_potion', 'discard_potion'}
    elif context.kind == 'relic_choice' and context.definition_id == 'card_grid':
        if (context.get('manual_confirmation') is not True or len(context.children) != 1 or
                context.children[0].kind != 'reward' or context.children[0].definition_id != 'card_grid'):
            return unrestricted
        selection = context
        # Sea Glass uses the same command for adding and removing an offer.
        choose = undo = 'choose_relic_reward'
        confirm = 'confirm_relic_selection'
        options = tuple(n.ref for n in context.children[0].children if n.kind == 'card')
        if (context.get('minimum'), context.get('maximum')) != (0, len(options)):
            return unrestricted
    else:
        return unrestricted
    minimum, maximum = selection.get('minimum'), selection.get('maximum')
    selected = selection.linked('selected')
    if (selection.get('manual_confirmation', True) is not True or
            type(minimum) is not int or type(maximum) is not int or
            not 0 <= minimum <= maximum <= len(options) or len(selected) > maximum or
            len(set(options)) != len(options) or len(set(selected)) != len(selected) or
            any(ref is None for ref in options) or not set(selected) <= set(options)):
        return unrestricted
    # Check the selector's complete pick/undo/confirm support before filtering;
    # never manufacture confirmation or turn an unknown shape into a dead end.
    expected = {(undo, ref, None) for ref in selected}
    if len(selected) < maximum:
        expected.update((choose, ref, None) for ref in options if ref not in selected)
    if len(selected) >= minimum:
        expected.add((confirm, None, None))
    actual = {(a.kind, a.subject, a.target) for a in decision.candidates if a.kind not in extras}
    if actual != expected:
        return unrestricted
    return tuple(not (a.kind == undo and a.subject in selected) for a in decision.candidates)
