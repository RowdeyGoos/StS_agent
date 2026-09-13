"""Construction helper for explicit base/upgrade card definitions."""

from dataclasses import replace
from game.headless.cards.base import CardDefinition, CardSpec


def define(
    identity,
    name,
    cost,
    kind,
    rarity,
    effects,
    *,
    damage=0,
    upgraded_damage=None,
    block=0,
    upgraded_block=None,
    draw=0,
    upgraded_draw=None,
    upgraded_cost=None,
    target=None,
    exhaust=False,
    upgraded_exhaust=None,
    innate=False,
    strike=False,
    x=False,
    generate=True,
    pool="ironclad",
    retain=False,
    upgraded_retain=None,
    base_innate=False,
    defend=False,
):
    base = CardSpec(
        name,
        cost,
        kind,
        base_damage=damage,
        block_gain=block,
        draw_count=draw,
        uses_target=kind == "attack" if target is None else target,
        exhausts=exhaust,
        x_cost=x,
        innate=base_innate,
        retain=retain,
    )
    upgrade = replace(
        base,
        name=name + "+",
        cost=cost if upgraded_cost is None else upgraded_cost,
        base_damage=damage if upgraded_damage is None else upgraded_damage,
        block_gain=block if upgraded_block is None else upgraded_block,
        draw_count=draw if upgraded_draw is None else upgraded_draw,
        exhausts=exhaust if upgraded_exhaust is None else upgraded_exhaust,
        innate=innate or base_innate,
        retain=retain if upgraded_retain is None else upgraded_retain,
    )
    return CardDefinition(
        identity,
        (base, upgrade),
        effects,
        rarity=rarity,
        pool=pool,
        strike=strike,
        defend=defend,
        generate_in_combat=generate,
    )
