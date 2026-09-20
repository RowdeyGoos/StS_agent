"""Gather a native autoplay batch before executing any of its card plays."""

OPS = frozenset(('autoplay_collect', 'autoplay_take', 'autoplay_next'))


def begin(p, count, force_exhaust):
    if count <= 0 or p.combat_is_ending:
        return
    r = p.rules
    identity = str(r.autoplay_sequence)
    r.autoplay_sequence += 1
    r.autoplay_batches[identity] = dict(context=r.active_hook, remaining=count,
                                       force_exhaust=force_exhaust, cards=[], stage='collect')
    from game.headless.core.resolution import push
    push(p, ['autoplay_collect', identity])


def execute(p, op, identity):
    from game.headless.core.resolution import push, find, start_play
    batch = p.rules.autoplay_batches[identity]
    if p.combat_is_ending:
        cancel(p, identities=(identity,))
        return
    if op == 'autoplay_collect':
        if batch['remaining'] > 0 and (p.deck.draw_pile or p.deck.discard_pile):
            from game.headless.powers.colorless import ensure_draw
            if ensure_draw(p, ['autoplay_take', identity], hand=False):
                push(p, ['autoplay_take', identity])
            # ensure_draw owns the queued post-shuffle phase when it suspends.
            return
        batch['remaining'], batch['stage'] = 0, 'play'
        push(p, ['autoplay_next', identity])
    elif op == 'autoplay_take':
        if p.deck.draw_pile:
            card = p.deck.draw_pile.pop()
            p.deck.in_play.append(card)
            batch['cards'].append(card.instance_id)
            batch['remaining'] -= 1
            push(p, ['autoplay_collect', identity])
        else:
            batch['remaining'], batch['stage'] = 0, 'play'
            push(p, ['autoplay_next', identity])
    else:
        if not batch['cards']:
            del p.rules.autoplay_batches[identity]
            return
        card = find(p, batch['cards'].pop(0))
        push(p, ['autoplay_next', identity])
        start_play(p, card, auto=True, force_exhaust=batch['force_exhaust'], from_reservation=True)


def cancel(p, *, contexts=None, identities=None):
    """Dispose unplayed reservations without invoking card or exhaust hooks."""
    batches = p.rules.autoplay_batches
    canceled = set()
    for identity, batch in tuple(batches.items()):
        if contexts is not None and batch['context'] not in contexts:
            continue
        if identities is not None and identity not in identities:
            continue
        canceled.update(batch['cards'])
        del batches[identity]
    remaining = {i for batch in batches.values() for i in batch['cards']}
    for card in tuple(p.deck.in_play):
        if card.instance_id in canceled - remaining and card.instance_id not in p.rules.plays:
            p.deck.in_play.remove(card)
            p.deck.discard_pile.append(card)


def validate(r, p, work):
    if type(r.autoplay_sequence) is not int or r.autoplay_sequence < 0 or not isinstance(r.autoplay_batches, dict):
        raise ValueError('Invalid autoplay batch state.')
    reserved = set()
    known = {c.instance_id for c in p.deck.all_cards() if c not in p.deck.offered}
    for identity, batch in r.autoplay_batches.items():
        if (not isinstance(identity, str) or not identity.isdigit() or str(int(identity)) != identity
                or not 0 <= int(identity) < r.autoplay_sequence or not isinstance(batch, dict)
                or set(batch) != {'context', 'remaining', 'force_exhaust', 'cards', 'stage'}):
            raise ValueError('Invalid autoplay batch fields.')
        if (type(batch['context']) is not int or batch['context'] not in work
                or type(batch['remaining']) is not int or batch['remaining'] < 0
                or type(batch['force_exhaust']) is not bool
                or batch['stage'] not in ('collect', 'play')
                or not isinstance(batch['cards'], list)
                or any(not isinstance(i, str) or i not in known for i in batch['cards'])
                or len(batch['cards']) != len(set(batch['cards']))):
            raise ValueError('Invalid autoplay reservation ownership.')
        reserved.update(batch['cards'])
        controls = [(context, task) for context, tasks in work.items() for task in tasks
                    if isinstance(task, list) and len(task) == 2 and isinstance(task[0], str) and task[0] in OPS and task[1] == identity]
        if len(controls) != 1 or controls[0][0] != batch['context']:
            raise ValueError('Autoplay batch requires its owned continuation.')
        op = controls[0][1][0]
        if ((batch['stage'] == 'play') != (op == 'autoplay_next')
                or batch['stage'] == 'play' and batch['remaining'] != 0
                or op == 'autoplay_take' and batch['remaining'] <= 0):
            raise ValueError('Invalid autoplay collection phase.')
    for context, tasks in work.items():
        for task in tasks:
            if isinstance(task, list) and task and isinstance(task[0], str) and task[0] in OPS:
                if len(task) != 2 or not isinstance(task[1], str) or task[1] not in r.autoplay_batches:
                    raise ValueError('Unowned autoplay batch task.')
    if r.autoplay_batches and p.combat_is_ending:
        raise ValueError('Terminal autoplay reservations must be canceled.')
    return reserved
