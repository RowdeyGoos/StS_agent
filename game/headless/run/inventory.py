"""Shared acquisition/removal rules with run-owned item identities."""

from game.headless.potions.base import POTIONS, PotionInstance
from game.headless.relics.base import RELICS, RelicInstance


def add_relic(state, definition_id: str, *, cards=None):
    # Acquisition may generate nested choices; failures roll back the complete
    # owned state, including RNG, resources and both identity allocators.
    from copy import deepcopy
    before = deepcopy(state)
    try:
        return _add_relic(state, definition_id, cards=cards)
    except Exception:
        state.__dict__.clear()
        state.__dict__.update(before.__dict__)
        raise


def _add_relic(state, definition_id: str, *, cards=None):
    if definition_id not in RELICS or (not RELICS[definition_id].stackable and not RELICS[definition_id].allow_duplicates and any(r.definition_id == definition_id for r in state.relics)):
        raise ValueError("Unsupported or already owned relic.")
    if RELICS[definition_id].pickup_max_hp and (state.phase.value == "combat" or state.hp <= 0):
        raise ValueError("Max-HP relic pickup requires a living run outside combat.")
    if RELICS[definition_id].pickup_transform is not None:
        if state.phase.value == "combat" or state.hp <= 0:
            raise ValueError("This relic pickup requires a living run outside combat.")
        if cards is None:
            from game.headless.cards.catalog import DEFAULT_CARDS
            cards = DEFAULT_CARDS
        cards.definition(RELICS[definition_id].pickup_transform[1])
    from game.headless.cards.catalog import DEFAULT_CARDS
    from game.headless.relics.neow import available, drain
    cards = cards or DEFAULT_CARDS
    if not available(definition_id, cards):
        raise ValueError("Relic requires card pools absent from this content catalog.")
    relic = RelicInstance(definition_id, state.allocate_item_id(), data={"treasures": 0} if definition_id == "silver_crucible" else {})
    state.relics.append(relic)
    RELICS[definition_id].after_obtained(state, cards=cards)
    from game.headless.relics.run_rules import pickup
    pickup(state, relic, cards)
    drain(state, cards)
    if not state.hp:
        from game.headless.run.state import RunPhase
        state.phase = RunPhase.DEFEAT
        state.pending = None
        state.relic_work.clear()
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
