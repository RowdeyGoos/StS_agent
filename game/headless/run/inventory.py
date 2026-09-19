"""Shared acquisition/removal rules with run-owned item identities."""

from game.headless.potions.base import POTIONS, PotionInstance
from game.headless.relics.base import RELICS, RelicInstance


def add_relic(state, definition_id: str, *, cards=None, allow_dead=False, card_pool=None):
    # Acquisition may generate nested choices; failures roll back the complete
    # owned state, including RNG, resources and both identity allocators.
    from copy import deepcopy
    before = deepcopy(state)
    try:
        return _add_relic(state, definition_id, cards=cards, allow_dead=allow_dead, card_pool=card_pool)
    except Exception:
        state.__dict__.clear()
        state.__dict__.update(before.__dict__)
        raise


def _add_relic(state, definition_id: str, *, cards=None, allow_dead=False, card_pool=None):
    if definition_id not in RELICS or (not RELICS[definition_id].stackable and not RELICS[definition_id].allow_duplicates and any(r.definition_id == definition_id for r in state.relics)):
        raise ValueError("Unsupported or already owned relic.")
    if RELICS[definition_id].pickup_max_hp and (state.phase.value == "combat" or state.hp <= 0 and not allow_dead):
        raise ValueError("Max-HP relic pickup requires a living run outside combat.")
    if RELICS[definition_id].pickup_transform is not None:
        if state.phase.value == "combat" or state.hp <= 0 and not allow_dead:
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
    data = {"treasures": 0} if definition_id == "silver_crucible" else {}
    if card_pool is not None:
        if definition_id != 'sea_glass' or card_pool not in ('ironclad','silent','regent','necrobinder','defect'):
            raise ValueError('Only Sea Glass accepts a character card pool.')
        data['family'] = card_pool
    relic = RelicInstance(definition_id, state.allocate_item_id(), data=data)
    state.relics.append(relic)
    if getattr(state.rng, "native", False):
        from game.headless.generation.relics import remove
        remove(state, definition_id)
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


def add_potion(state, definition_id: str, *, slot=None):
    from game.headless.relics.run_rules import has
    if definition_id not in POTIONS:
        raise ValueError("Unsupported potion.")
    if has(state, "sozu"):
        return None
    if None not in state.potions:
        raise ValueError("Unsupported potion or no empty potion slot.")
    slot = state.potions.index(None) if slot is None else slot
    if type(slot) is not int or not 0 <= slot < len(state.potions) or state.potions[slot] is not None:
        raise ValueError("Potion slot is unavailable.")
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
