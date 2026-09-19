"""Ownership validation for saved death-hook continuations."""

from copy import copy

from game.headless.core.choice_snapshots import validate_selection


def groups(r, p):
    if (
        type(r.hook_sequence) is not int
        or r.hook_sequence < 0
        or type(r.active_hook) is not int
        or not 0 <= r.active_hook <= r.hook_sequence
        or not isinstance(r.deferred_hooks, list)
    ):
        raise ValueError("Invalid hook scheduler state.")
    work = {r.active_hook: r.tasks}
    for hook in r.deferred_hooks:
        if not isinstance(hook, dict) or set(hook) != {"context", "tasks", "selection", "pending"}:
            raise ValueError("Invalid deferred hook fields.")
        identity = hook["context"]
        if (
            type(identity) is not int
            or not 0 < identity <= r.hook_sequence
            or identity in work
            or (hook["selection"] is None) == (hook["pending"] is None)
        ):
            raise ValueError("Invalid queued hook identity or choice.")
        work[identity] = hook["tasks"]
    if any(not isinstance(tasks, list) for tasks in work.values()):
        raise ValueError("Invalid hook work queue.")
    if (r.active_hook or r.deferred_hooks) and (
        p.combat_is_ending or not any(v["definition_id"] == "gremlin_horn" for v in r.relics)
    ):
        raise ValueError("Unowned or canceled hook work.")
    return work


def validate_choices(r, p):
    contexts = [dict(context=r.active_hook, selection=r.selection, pending=None)] + r.deferred_hooks
    offered = {c.instance_id for c in p.deck.offered}
    owned_offers = set()
    for hook in contexts:
        view = copy(r)
        view.selection, view.active_hook = hook["selection"], hook["context"]
        validate_selection(view, p, deferred=hook in r.deferred_hooks, shared_offers=bool(r.deferred_hooks))
        if hook["selection"]:
            selection = hook["selection"]
            if hook in r.deferred_hooks and selection["selected"]:
                raise ValueError("Queued selection has not accepted input.")
            frame = r.plays.get(selection["source"])
            if frame is not None and frame.get("context") != hook["context"]:
                raise ValueError("Selection belongs to a different play context.")
            ids = set(hook["selection"]["candidates"]) & offered
            if owned_offers & ids:
                raise ValueError("Offered card belongs to multiple choices.")
            owned_offers |= ids
        pending = hook["pending"]
        if pending is not None:
            from game.headless.cards.effects import SelectHandCard
            from game.headless.cards.operations import ChoosePileCard

            if not isinstance(pending, dict) or set(pending) != {"effect_index", "target_slot"}:
                raise ValueError("Invalid deferred card choice.")
            card = next(
                (
                    c
                    for c in reversed(p.deck.in_play)
                    if r.plays.get(c.instance_id, {}).get("context") == hook["context"]
                ),
                None,
            )
            if card is None:
                raise ValueError("Deferred selector has no owning card.")
            frame = r.plays[card.instance_id]
            index = pending["effect_index"]
            if (
                type(index) is not int
                or not 0 <= index < len(card.definition.effects)
                or index != frame["effect_index"]
                or pending["target_slot"] != frame["target"]
            ):
                raise ValueError("Deferred selector differs from its play.")
            effect = card.definition.effects[index]
            if not isinstance(effect, (SelectHandCard, ChoosePileCard)) or effect.mode_for(card) != "choose":
                raise ValueError("Deferred effect cannot request a card choice.")
    if owned_offers != offered:
        raise ValueError("Unowned offered cards.")

def validate_pending(r, work):
    """Every queued summon/damage must have one unconsumed event in its context."""
    from game.headless.core.resolution import requires_receipt
    if not isinstance(r.pending_events, list):
        raise ValueError('Invalid pending reactive events.')
    expected = [dict(context=context, task=task) for context, tasks in work.items()
                for task in tasks if isinstance(task, list) and task and isinstance(task[0], str) and requires_receipt(task[0])]
    for event in r.pending_events:
        if not isinstance(event, dict) or set(event) != {'context', 'task'} or type(event['context']) is not int or event not in expected:
            raise ValueError('Unowned or consumed reactive event.')
        expected.remove(event)
    if expected:
        raise ValueError('reactive command has no pending producing event.')
