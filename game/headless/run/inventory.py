"""Shared acquisition/removal rules with run-owned item identities."""

from game.headless.potions.base import POTIONS, PotionInstance
from game.headless.relics.base import RELICS, RelicInstance


def add_relic(state, definition_id: str):
    if definition_id not in RELICS or (not RELICS[definition_id].stackable and any(r.definition_id == definition_id for r in state.relics)):
        raise ValueError("Unsupported or already owned relic.")
    if RELICS[definition_id].pickup_max_hp and (state.phase.value == "combat" or state.hp <= 0):
        raise ValueError("Max-HP relic pickup requires a living run outside combat.")
    relic = RelicInstance(definition_id, state.allocate_item_id())
    state.relics.append(relic)
    RELICS[definition_id].after_obtained(state)
    return relic


def remove_relic(state, instance_id: str):
    for relic in state.relics:
        if relic.instance_id == instance_id:
            state.relics.remove(relic)
            return relic
    raise ValueError("Relic is not owned by this run.")


def add_potion(state, definition_id: str):
    if definition_id not in POTIONS or None not in state.potions:
        raise ValueError("Unsupported potion or no empty potion slot.")
    slot = state.potions.index(None)
    potion = PotionInstance(definition_id, state.allocate_item_id())
    state.potions[slot] = potion
    return potion


def potion_slot(state, instance_id: str) -> int:
    for slot, potion in enumerate(state.potions):
        if potion is not None and potion.instance_id == instance_id:
            return slot
    raise ValueError("Potion is not owned by this run.")


def discard_potion(state, instance_id: str):
    slot = potion_slot(state, instance_id)
    potion = state.potions[slot]
    state.potions[slot] = None
    return potion
