"""Run-owned potion consumption, including outside combat and automatic revival."""

from dataclasses import asdict
from game.headless.potions.base import POTIONS
from game.headless.run.actions import UsePotion
from game.headless.run.state import RunPhase
from game.headless.run.inventory import potion_slot, add_potion


def actions(engine):
    state, combat = engine.state, engine.combat
    for item in state.potions:
        if item is None:
            continue
        definition = POTIONS[item.definition_id]
        if definition.usage == "automatic":
            continue
        if combat is None:
            if definition.usage != "anytime":
                continue
            if item.definition_id == "foul_potion" and not (
                state.pending and state.pending.get("kind") == "shop"
            ):
                continue
        targets = [i for i, e in enumerate(combat.enemies) if e.is_alive] if definition.targeted else [None]
        for target in targets:
            yield UsePotion(item.instance_id, target)


def use(engine, action):
    state, combat = engine.state, engine.combat
    slot = potion_slot(state, action.instance_id)
    item = state.potions[slot]
    before = [None if p is None else asdict(p) for p in state.potions]
    state.potions[slot] = None
    if combat is not None:
        p = combat.player
        p.rules.potions = [None if v is None else asdict(v) for v in state.potions]
        p.rules.potion_slots = state.potions.count(None)
        from game.headless.potions.combat import start

        start(p, item, action.target_slot)
        return combat.resolve_external_effect()
    from game.headless.relics.run_rules import heal, gain_gold, max_hp

    if item.definition_id == "blood_potion":
        heal(state, state.max_hp * 20 // 100)
    elif item.definition_id == "fruit_juice":
        max_hp(state, 5)
    elif item.definition_id == "entropic_brew":
        from game.headless.potions.pools import generate

        pool = state.config.reward_potions if state.config else ("fire_potion", "block_potion")
        while None in state.potions:
            add_potion(state, generate(pool, state.rng, stream="combat.potion_generation"))
    elif item.definition_id == "foul_potion":
        gain_gold(state, 100)
    else:
        raise ValueError("Potion cannot be used outside combat.")
    from game.headless.events.potion_context import record

    record(state, before, item.definition_id)


def prevent_death(state):
    if state.hp > 0:
        return
    for slot, item in enumerate(getattr(state, "potions", ())):
        if item is not None and item.definition_id == "fairy_in_a_bottle":
            state.potions[slot] = None
            state.hp = max(1, state.max_hp * 30 // 100)
            return
