"""Owned orb instances, ordered slots and resumable channel/evoke commands."""

from game.headless.core.resolution import push

KINDS = ('lightning', 'frost', 'dark', 'plasma', 'glass')


def add_slots(p, amount):
    p.rules.orb_slots = min(10, p.rules.orb_slots + amount)


def remove_slots(p, amount):
    r = p.rules
    r.orb_slots = max(0, r.orb_slots - amount)
    del r.orb_order[r.orb_slots:]


def count(p, kind=None):
    return sum(kind is None or p.rules.orbs[i]['kind'] == kind for i in p.rules.orb_order)


def distinct(p):
    return len({p.rules.orbs[i]['kind'] for i in p.rules.orb_order})


def phase(p, side):
    # Keep physical identities even when a later reaction removes an orb.
    push(p, *[['orb_trigger', i, 'passive', None] for i in tuple(p.rules.orb_order)
              if (p.rules.orbs[i]['kind'] == 'plasma') == (side == 'start')])


def value(p, orb, mode):
    kind, stored = orb['kind'], orb['value']
    focus = p.rules.powers.get('focus', 0)
    if kind == 'plasma':
        return 1 if mode == 'passive' else 2
    if kind == 'dark':
        return max(0, 6 + focus) if mode == 'passive' else stored
    if kind == 'glass':
        return max(0, stored + focus) * (1 if mode == 'passive' else 2)
    return max(0, ({'lightning': (3, 8), 'frost': (2, 5)}[kind][mode != 'passive']) + focus)


def execute(p, op, args):
    if p.combat_is_ending:
        return
    r = p.rules
    if op == 'orb_channel':
        kind, = args
        if kind == 'random':
            kind = p.deck.orb_rng.choice(KINDS)
        # The current owner is Ironclad (native BaseOrbSlotCount == 0).
        if r.orb_slots == 0:
            add_slots(p, 1)
        push(p, *([['orb_evoke', False, True]] if len(r.orb_order) >= r.orb_slots else []), ['orb_insert', kind])
    elif op == 'orb_insert':
        kind, = args
        identity = f'orb.{len(r.orbs)}'
        r.orbs[identity] = {'kind': kind, 'value': 6 if kind == 'dark' else 4 if kind == 'glass' else 0}
        r.orb_order.append(identity)
    elif op == 'orb_evoke':
        last, dequeue = args
        if r.orb_order:
            identity = r.orb_order[-1 if last else 0]
            if dequeue:
                r.orb_order.remove(identity)
            push(p, ['orb_trigger', identity, 'evoke', None])
    elif op == 'orb_phase':
        phase(p, args[0])
    elif op == 'orb_front_passive':
        if r.orb_order:
            push(p, ['orb_trigger', r.orb_order[0], 'passive', None])
    elif op == 'orb_trigger':
        identity, mode, target = args
        orb = r.orbs[identity]
        kind, amount = orb['kind'], value(p, orb, mode)
        if kind == 'dark' and mode == 'passive':
            orb['value'] += amount
        elif kind == 'plasma':
            p.gain_energy(amount)
        elif kind == 'frost':
            p.gain_block(amount)
        else:
            living = [i for i, e in enumerate(p.combat_enemies or ()) if e.is_alive]
            if kind == 'glass':
                if amount <= 0:
                    return
                if mode == 'passive':
                    orb['value'] = max(0, orb['value'] - 1)
                targets = living
            elif kind == 'dark':
                targets = [min(living, key=lambda i: p.combat_enemies[i].hp)] if living else []
            else:
                targets = ([p.deck.target_rng.choice(living)] if target is None else [target]) if living else []
            push(p, *[['orb_damage', identity, slot, amount] for slot in targets],
                 *([['orb_thunder', identity, slot] for slot in targets] if mode == 'evoke' and kind == 'lightning' else []))
    elif op == 'orb_damage':
        _, slot, amount = args
        if p.combat_enemies[slot].is_alive:
            p.combat_enemies[slot].take_damage(amount, is_attack=False)
    elif op == 'orb_thunder':
        _, slot = args
        amount = r.powers.get('thunder', 0)
        if amount and p.combat_enemies[slot].is_alive:
            p.combat_enemies[slot].take_damage(amount, is_attack=False)
    else:
        raise ValueError('Unknown orb continuation.')


def clear(p):
    """Native confirmed death removes the active queue and its capacity."""
    p.rules.orb_order.clear()
    p.rules.orb_slots = 0
