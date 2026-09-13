"""Primitive effects for the existing small synthetic event content."""


def apply_effect(state, effect: str, amount: int) -> int:
    if effect not in ("heal", "gain_gold", "lose_hp") or type(amount) is not int or amount < 0:
        raise ValueError("Unsupported event effect.")
    if effect == "heal":
        applied = min(amount, state.max_hp - state.hp)
        state.hp += applied
    elif effect == "gain_gold":
        applied = amount
        from game.headless.relics.run_rules import gain_gold
        applied = gain_gold(state, applied)
    else:
        from game.headless.relics.run_rules import damage
        applied = damage(state, amount)
    return applied
