"""Implemented power hooks at explicit combat boundaries."""

from game.headless.powers.status import TERRITORIAL


def after_owner_side_turn_end(owner):
    if owner.is_alive:
        if not hasattr(owner, "rules"):
            owner.statuses.decrement("shrink")
            if owner.statuses.get("demise"):
                block = owner.block
                owner.block = 0
                owner.take_damage(owner.statuses.get("demise"), is_attack=False)
                owner.block = block
            owner.statuses.decrement("mangle", owner.statuses.get("mangle"))
            for key in ("dark_shackles", "crush_under", "dying_star", "monarchs_gaze_strength_down"):
                owner.statuses.decrement(key, owner.statuses.get(key))
        if hasattr(owner, "power_sources"):
            amount = owner.statuses.get("constrict")
            if amount:
                owner.take_damage(amount, is_attack=False)
            for name in ("tangled", "ringing"):
                owner.statuses.decrement(name, owner.statuses.get(name))
        amount = owner.statuses.get(TERRITORIAL)
        if amount:
            owner.gain_strength(amount)
