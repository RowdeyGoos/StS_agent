"""Pinned rarity membership, excluding event/Ancient/starter items from ordinary loot."""

from game.headless.relics.base import RELICS

ORDINARY_RELICS = tuple(name for name, d in RELICS.items() if d.rarity in ("common", "uncommon", "rare"))
SHOP_RELICS = tuple(
    name
    for name, d in RELICS.items()
    if d.rarity in ("common", "uncommon", "rare", "shop") and name not in ("old_coin", "the_courier")
)
MERCHANT_COSTS = {"common": 175, "uncommon": 225, "rare": 275, "shop": 200}


def shop_items(state, slot):
    if slot.kind != "relic" or state.config is None:
        return slot.items
    return tuple((name, MERCHANT_COSTS[RELICS[name].rarity]) for name in state.config.shop_relics)


def treasure_pool(state):
    from game.headless.treasure.catalog import ORDINARY_CHEST

    return ORDINARY_CHEST.relic_pool if state.config is None else state.config.reward_relics
