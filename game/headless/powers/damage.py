"""Implemented power rules after block and before HP loss."""

from game.headless.powers.status import SLIPPERY


def resolve_unblocked_damage(statuses, amount):
    if amount > 0 and statuses.get(SLIPPERY):
        statuses.decrement(SLIPPERY)
        return min(amount, 1)
    return amount
