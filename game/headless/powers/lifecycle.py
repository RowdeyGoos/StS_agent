"""Implemented power hooks at explicit combat boundaries."""

from game.headless.powers.status import TERRITORIAL


def after_owner_side_turn_end(owner):
    if owner.is_alive:
        amount = owner.statuses.get(TERRITORIAL)
        if amount:
            owner.gain_strength(amount)
