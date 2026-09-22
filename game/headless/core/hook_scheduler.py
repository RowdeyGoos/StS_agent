"""Death hooks run to completion or first choice, then resume in player FIFO order.

Only the synchronous call stack is local. Every hook that survives a drain owns
plain saved work and a context ID; card piles always retain their actual contents.
"""

from dataclasses import asdict

from game.headless.core.selection import PendingCardPlay


def paused(p):
    return p.rules.selection is not None or p.pending_play is not None


def capture(p):
    r = p.rules
    return dict(
        context=r.active_hook,
        tasks=r.tasks,
        selection=r.selection,
        pending=None if p.pending_play is None else asdict(p.pending_play),
    )


def activate(p, hook):
    r = p.rules
    r.active_hook, r.tasks, r.selection = hook["context"], hook["tasks"], hook["selection"]
    p.pending_play = None if hook["pending"] is None else PendingCardPlay(**hook["pending"])
    if r.selection is not None and (r.selection["source"] == "stratagem" or "whitelist" in r.selection):
        from game.headless.core.piles import stratagem_cards

        s = r.selection
        s["candidates"] = [
            c.instance_id
            for c in stratagem_cards(p)
            if "whitelist" not in s or c.instance_id in s["whitelist"]
        ]
        s["maximum"] = min(s["maximum"], len(s["candidates"]))
        s["minimum"] = min(s["minimum"], s["maximum"])
        # The native command already passed its automatic-selection precheck.
        # Its subsequently activated screen completes empty, but not singleton.
        if not s["candidates"]:
            r.selection = None
    if r.selection is not None:
        from game.headless.core.choices import refresh_hand_selection
        refresh_hand_selection(p)
        if not r.selection["candidates"]:
            r.selection = None
    if p.pending_play is not None and not p.pending_options():
        p.pending_play = None


def cancel_deferred(p):
    r = p.rules
    canceled = {h["context"] for h in r.deferred_hooks}
    from game.headless.core.autoplay import cancel as cancel_autoplay
    cancel_autoplay(p, contexts=canceled)
    # Combat cleanup disposes interrupted plays without firing further hooks.
    for card in tuple(p.deck.in_play):
        frame = r.plays.get(card.instance_id)
        if frame is not None and frame["context"] in canceled:
            p.deck.in_play.remove(card)
            getattr(p.deck, frame["destination"]).append(card)
            del r.plays[card.instance_id]
    for hook in r.deferred_hooks:
        selection = hook["selection"]
        if selection:
            candidates = set(selection["candidates"])
            p.deck.offered[:] = [c for c in p.deck.offered if c.instance_id not in candidates]
    r.pending_events[:] = [event for event in r.pending_events if event['context'] not in canceled]
    r.deferred_hooks.clear()


def run(p, execute):
    r = p.rules
    parents = []
    while True:
        if paused(p):
            from game.headless.relics.ancient_state import auto_select
            if auto_select(p):
                continue
            if not parents:
                return
            r.deferred_hooks.append(capture(p))
            r.selection = p.pending_play = None
            r.active_hook, r.tasks = parents.pop()
            continue
        if r.tasks:
            task = r.tasks.pop(0)
            if task[0] == "death_hook":
                if p.combat_is_ending:
                    continue
                parents.append((r.active_hook, r.tasks))
                r.hook_sequence += 1
                r.active_hook = r.hook_sequence
                r.tasks = [["energy", 1], ["draw", 1, False]]
            else:
                execute(p, task)
            continue
        if parents:
            r.active_hook, r.tasks = parents.pop()
            continue
        r.active_hook = 0
        if p.combat_is_ending:
            cancel_deferred(p)
        if not r.deferred_hooks or p._defer_death_hooks or r.enemy_turn is not None:
            return
        activate(p, r.deferred_hooks.pop(0))


def advance_side_start(p, tasks):
    """Side-start listeners finish even when player setup has reached a choice.

    Park that already-visible decision. Reactive Horn choices discovered here
    join its deferred FIFO; side-start effects have no resolving card source.
    """
    if not tasks:
        return
    from game.headless.core.resolution import execute
    r = p.rules
    parked = capture(p)
    deferred, resolving = r.deferred_hooks, p._resolving
    r.hook_sequence += 1
    r.active_hook = r.hook_sequence
    from game.headless.core.resolution import requires_receipt
    for task in tasks:
        if requires_receipt(task[0]):
            event = next(e for e in r.pending_events if e == dict(context=parked['context'], task=task))
            event['context'] = r.active_hook
    r.tasks, r.selection, r.deferred_hooks = list(tasks), None, []
    p.pending_play, p._resolving = None, True
    try:
        run(p, execute)
        discovered = ([capture(p)] if paused(p) else []) + r.deferred_hooks
    finally:
        r.active_hook, r.tasks, r.selection = parked['context'], parked['tasks'], parked['selection']
        p.pending_play = None if parked['pending'] is None else PendingCardPlay(**parked['pending'])
        r.deferred_hooks, p._resolving = deferred, resolving
    r.deferred_hooks.extend(discovered)
    if p.combat_is_ending:
        cancel_terminal_work(p)
        return
    from game.headless.core.choices import refresh_hand_selection
    refresh_hand_selection(p)


def cancel_terminal_work(p):
    """Dispose interrupted setup after side-start reactions end combat."""
    r = p.rules
    from game.headless.core.autoplay import cancel as cancel_autoplay
    cancel_autoplay(p)
    for card in tuple(p.deck.in_play):
        frame = r.plays[card.instance_id]
        p.deck.in_play.remove(card)
        getattr(p.deck, frame['destination']).append(card)
    p.deck.offered.clear()
    r.plays.clear()
    r.tasks.clear()
    r.pending_events.clear()
    r.deferred_hooks.clear()
    r.selection = p.pending_play = None
    r.active_hook = 0
    r.end_hand_remaining.clear()


def finish_enemy_work(p):
    """Queue a later setup/reaction choice behind earlier detached death hooks."""
    from game.headless.core.resolution import drain
    r = p.rules
    if p.combat_is_ending:
        cancel_terminal_work(p)
        return
    if r.enemy_turn is not None:
        return  # A blocking enemy choice must finish its move first.
    if r.deferred_hooks and paused(p):
        previous = r.active_hook
        if not previous:
            r.hook_sequence += 1
            r.active_hook = r.hook_sequence
            for frame in (*r.plays.values(), *r.autoplay_batches.values()):
                if frame['context'] == previous:
                    frame['context'] = r.active_hook
            for event in r.pending_events:
                if event['context'] == previous:
                    event['context'] = r.active_hook
        r.deferred_hooks.append(capture(p))
        r.tasks, r.selection, p.pending_play = [], None, None
        activate(p, r.deferred_hooks.pop(0))
    drain(p)
