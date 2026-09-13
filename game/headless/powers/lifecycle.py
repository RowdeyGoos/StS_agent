"""Implemented power hooks at explicit combat boundaries."""

from game.headless.powers.status import TERRITORIAL


def after_owner_side_turn_end(owner):
    if owner.is_alive:
        if hasattr(owner, "power_sources"):
            amount = owner.statuses.get("constrict")
            if amount:
                owner.take_damage(amount, is_attack=False)
            for name in ("tangled", "ringing"):
                owner.statuses.decrement(name, owner.statuses.get(name))
        amount = owner.statuses.get(TERRITORIAL)
        if amount:
            owner.gain_strength(amount)
