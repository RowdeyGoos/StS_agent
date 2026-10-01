"""Versioned policy restrictions over complete public legal candidates.

These rules never dispatch, change game legality, reorder candidates or inspect
engine state. The canonical decision remains the source of every command.
"""
from game.agent.contracts import full as f

ALL_LEGAL = 'all_legal_v1'
COMMIT_SINGLE_CARD = 'commit_single_card_v1'
COMMIT_CARD_SELECTION = 'commit_card_selection_v1'
COMMIT_DECISIONS = 'commit_decisions_v1'
POLICIES = (ALL_LEGAL, COMMIT_SINGLE_CARD, COMMIT_CARD_SELECTION, COMMIT_DECISIONS)


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
    if policy in (COMMIT_CARD_SELECTION, COMMIT_DECISIONS):
        allowed = _commit_selection(decision, allowed)
        return _commit_reward_navigation(decision, allowed) if policy == COMMIT_DECISIONS else allowed
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


def _commit_reward_navigation(decision, unrestricted):
    """Allow inspection once per reward between actual gameplay commands.

Only a public previous close and current open witness remove close. Navigation among other
rewards does not reset it; any non-navigation command does, including rerolls.
Unknown modal shapes and incomplete attachment histories remain unrestricted.
    """
    context = decision.context
    if context.kind != 'rewards' and not (context.kind == 'event' and context.get('stage') == 'event_rewards'):
        return unrestricted
    closes = [a for a in decision.candidates if a.kind == 'close_reward']
    if len(closes) != 1 or closes[0].target is not None:
        return unrestricted
    close = closes[0]
    rewards = [n for n in context.children if n.kind == 'reward' and n.ref == close.subject]
    if (len(rewards) != 1 or rewards[0].definition_id != 'card' or
            rewards[0].get('resolved') is not False or rewards[0].get('presentation') != 'choice'):
        return unrestricted
    reward = rewards[0]
    offers = {n.ref for n in reward.children if n.kind == 'card'}
    if not offers or None in offers or len(offers) != len(reward.children):
        return unrestricted
    alternatives = [a for a in decision.candidates if a.kind in ('reroll_card_reward', 'sacrifice_card_reward')]
    if any(a.subject != reward.ref or a.target is not None for a in alternatives):
        return unrestricted
    choices = [a for a in decision.candidates if a != close and a not in alternatives]
    if context.kind == 'rewards':
        picks = [a for a in choices if a.kind in ('choose_reward_card', 'choose_extra_reward')]
        skips = [a for a in choices if a.kind == 'skip_reward' and a.target is None]
        if (len(skips) != 1 or len(picks) != len(offers) or len({a.kind for a in picks}) != 1 or
                {a.target for a in picks} != offers or any(a.subject != reward.ref for a in choices) or
                len(choices) != len(picks) + len(skips)):
            return unrestricted
    else:
        # Event batches expose explicit option labels as well as offer targets.
        index = [n for n in context.children if n.kind == 'reward'].index(reward)
        labels = {n.ref: n.definition_id for n in context.children if n.kind == 'option'}
        expected = {(f'reward_{index}_{i}', n.ref) for i, n in enumerate(reward.children)} | {(f'skip_{index}', None)}
        if (any(a.kind != 'choose_event_option' for a in choices) or len(choices) != len(expected) or
                {(labels.get(a.subject), a.target) for a in choices} != expected):
            return unrestricted
    histories = [n for n in decision.run.children if n.kind == 'history']
    if len(histories) != 1 or not histories[0].children:
        return unrestricted
    history = histories[0].children
    last = history[-1]
    if (last.kind != 'history_event' or last.definition_id != 'open_reward' or
            last.linked('history_subject') != (reward.ref,) or last.linked('history_target')):
        return unrestricted
    for event in reversed(history[:-1]):
        if event.kind != 'history_event' or event.definition_id not in ('open_reward', 'close_reward'):
            break
        subject = event.linked('history_subject')
        if len(subject) != 1 or event.linked('history_target'):
            return unrestricted
        if event.definition_id == 'close_reward' and subject == (reward.ref,):
            return tuple(ok and a != close for a, ok in zip(decision.candidates, unrestricted))
    return unrestricted
