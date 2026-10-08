"""Versioned public input transformations shared by planning and learning.

These views never change recorded observations, current cards or legal actions.
They contain no engine bindings and can be used by any public producer.
"""
from dataclasses import replace
import hashlib

RAW = 'public_observation_v1'
DETACHED_HISTORY = 'detached_combat_history_cards_v1'
VIEWS = (RAW, DETACHED_HISTORY)


def validate_view(view, *, action_policy=None):
    if type(view) is not str or view not in VIEWS:
        raise ValueError('Unsupported public input view')
    if view == DETACHED_HISTORY and action_policy == 'commit_single_card_v1':
        # That legacy restriction needs the historical selected-card link this
        # view removes. Never silently widen its checkpoint's action support.
        raise ValueError('Detached public input view is incompatible with commit_single_card_v1')
    return view


def apply_view(value, view=RAW):
    validate_view(view)
    if view == RAW:
        return value
    children = []
    for node in value.run.children:
        if node.kind == 'history':
            events = []
            for event in node.children:
                links = tuple(replace(link, targets=tuple(ref for ref in link.targets if not ref.startswith('card:')))
                    if link.key == 'history_subject' and event.definition_id in ('play_card', 'select_card')
                    and any(ref.startswith('card:') for ref in link.targets) else link for link in event.links)
                events.append(replace(event, links=links) if any(a is not b for a, b in zip(links, event.links)) else event)
            if any(a is not b for a, b in zip(events, node.children)):
                node = replace(node, children=tuple(events))
        children.append(node)
    if all(a is b for a, b in zip(children, value.run.children)):
        return value
    return replace(value, run=replace(value.run, children=tuple(children)))


def planning_view(value):
    """A past card action does not identify a current physical duplicate."""
    return apply_view(value, DETACHED_HISTORY)


class PlanningViewPolicy:
    """Compare a legacy checkpoint on the same input view as direct search."""
    input_view = DETACHED_HISTORY

    def __init__(self, base):
        validate_view(self.input_view, action_policy=base.model.action_policy)
        self.base = base
        self.identity = 'sts_planning_view_v1:' + hashlib.sha256(
            (base.identity + ':' + self.input_view).encode()).hexdigest()

    def __getattr__(self, name):
        return getattr(self.base, name)

    def __call__(self, decision):
        return self.base(planning_view(decision))

    def probabilities(self, decision):
        return self.base.probabilities(planning_view(decision))
