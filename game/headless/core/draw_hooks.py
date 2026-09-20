"""Ordered late draw listeners, with one serializable boundary per power."""

from game.headless.core.resolution import find, push
from game.headless.powers.colorless import name

POWER_NAMES = frozenset(('automation', 'pagestorm', 'defect_iteration',
                         'corrosive_wave', 'speedster', 'confused', 'chains_of_binding'))


def begin(player, identity, hand_draw):
    # Hellraiser's early hook finishes before native captures late listeners.
    push(player, *[['draw_power', key, identity, hand_draw]
                   for key in player.rules.powers if name(key) in POWER_NAMES],
         ['after_draw_card', identity])


def power(player, key, identity, hand_draw, amount=None):
    r = player.rules
    card = find(player, identity)
    if amount is None:
        amount = r.powers.get(key, 0)
    if card is None or not amount:
        return
    kind = name(key)
    if kind == 'automation':
        r.auxiliaries[key] -= 1
        if not r.auxiliaries[key]:
            r.auxiliaries[key] = 10
            player.gain_energy(amount)
    elif kind == 'pagestorm' and card.spec.ethereal:
        push(player, ['draw', amount, False])
    elif kind == 'defect_iteration' and card.spec.kind == 'status' and r.status_draws_turn <= 1:
        # An earlier listener may have drawn another status while this waits.
        push(player, ['draw', amount, False])
    elif kind == 'corrosive_wave':
        push(player, *[['status', i, 'poison', amount]
                       for i, enemy in enumerate(player.combat_enemies) if enemy.is_alive])
    elif kind == 'speedster' and not hand_draw and r.player_side:
        push(player, ['silent_area_damage', amount])
    elif kind == 'chains_of_binding':
        from game.headless.powers.glory import after_draw
        after_draw(player, card)
    elif kind == 'confused' and (card.cost >= 0 or card.spec.x_cost):
        from game.headless.enchantments.base import randomize_cost
        randomize_cost(card, player.deck)


def remove_power(player, key):
    """Keep captured listener instances when their owner removes a power.

    Corrosive Wave expires while a detached death draw can still be waiting.
    Freeze its last amount at removal, so later reapplication is a new listener.
    """
    r = player.rules
    amount = r.powers.pop(key, None)
    if amount is None:
        return
    queues = [r.tasks, *(hook['tasks'] for hook in r.deferred_hooks)]
    for tasks in queues:
        for task in tasks:
            if task[0] == 'draw_power' and task[1] == key:
                task[:] = ['draw_power_removed', *task[1:], amount]
    for event in r.pending_events:
        task = event['task']
        if task[0] == 'draw_power' and task[1] == key:
            task[:] = ['draw_power_removed', *task[1:], amount]
