"""Pinned rarity membership, excluding event/Ancient/starter items from ordinary loot."""

from game.headless.relics.base import RELICS
from game.headless.relics.eligibility import SHOP_EXCLUDED

ORDINARY_RELICS = tuple(name for name, d in RELICS.items() if d.rarity in ("common", "uncommon", "rare"))
SHOP_RELICS = tuple(
    name
    for name, d in RELICS.items()
    if d.rarity in ("common", "uncommon", "rare", "shop") and name not in SHOP_EXCLUDED
)
MERCHANT_COSTS = {"common": 175, "uncommon": 225, "rare": 275, "shop": 200}


def shop_items(state, slot):
    from game.headless.potions.pools import ORDINARY_POTIONS, COSTS
    from game.headless.potions.base import POTIONS
    if slot.kind == 'potion' and state.config is not None and state.config.reward_potions == ORDINARY_POTIONS:
        return tuple((name, COSTS[POTIONS[name].rarity]) for name in ORDINARY_POTIONS)
    if slot.kind != "relic" or state.config is None:
        return slot.items
    return tuple((name, MERCHANT_COSTS[RELICS[name].rarity]) for name in state.config.shop_relics)


def treasure_pool(state):
    from game.headless.treasure.catalog import ORDINARY_CHEST

    return ORDINARY_CHEST.relic_pool if state.config is None else state.config.reward_relics
