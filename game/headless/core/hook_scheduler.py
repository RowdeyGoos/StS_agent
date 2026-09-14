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
    if p.pending_play is not None and not p.pending_options():
        p.pending_play = None


def cancel_deferred(p):
    r = p.rules
    canceled = {h["context"] for h in r.deferred_hooks}
    # Combat cleanup disposes interrupted plays without firing further hooks.
    for card in tuple(p.deck.in_play):
        frame = r.plays[card.instance_id]
        if frame["context"] in canceled:
            p.deck.in_play.remove(card)
            getattr(p.deck, frame["destination"]).append(card)
            del r.plays[card.instance_id]
    for hook in r.deferred_hooks:
        selection = hook["selection"]
        if selection:
            candidates = set(selection["candidates"])
            p.deck.offered[:] = [c for c in p.deck.offered if c.instance_id not in candidates]
    r.deferred_hooks.clear()


def run(p, execute):
    r = p.rules
    parents = []
    while True:
        if paused(p):
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
        if not r.deferred_hooks:
            return
        activate(p, r.deferred_hooks.pop(0))
