"""Restricted authored stock with native A0 base costs and price variation bands.

Stock slots and discrete basis-point draws are project-authored, not native shop
pool/RNG parity. Prices round to even before the card sale's integer halving.
"""

from game.headless.cards.catalog import DEFAULT_CARDS
from dataclasses import asdict, dataclass
from game.headless.cards.pools import COMMON_CARDS, UNCOMMON_CARDS, RARE_CARDS

SHOP_ID = "supported_merchant_v3"


@dataclass(frozen=True, slots=True)
class StockSlot:
    kind: str
    items: tuple[tuple[str, int], ...]
    variation: int = 5
    sale_eligible: bool = True


SLOTS = (
    StockSlot("card", tuple((c, 50) for c in COMMON_CARDS)),
    StockSlot("card", tuple((c, 75) for c in UNCOMMON_CARDS)),
    StockSlot("card", tuple((c, 150) for c in RARE_CARDS)),
    StockSlot("card", tuple((d.definition_id, 86) for d in DEFAULT_CARDS.definitions if d.pool == "colorless" and d.rarity == "uncommon"), sale_eligible=False),
    StockSlot("card", tuple((d.definition_id, 172) for d in DEFAULT_CARDS.definitions if d.pool == "colorless" and d.rarity == "rare"), sale_eligible=False),
    StockSlot("relic", (("strawberry", 175), ("pear", 225), ("mango", 275)), 15),
    StockSlot("potion", (("fire_potion", 50),)),
    StockSlot("potion", (("block_potion", 50),)),
)


def price(base_cost, scale, on_sale=False):
    rounded = round(base_cost * scale / 10000)
    return rounded // 2 if on_sale else rounded


def fingerprint():
    # JSON primitives even before serialization, for exact installed continuation.
    return {"catalog_id": SHOP_ID, "slots": [
        {**asdict(s), "items": [list(item) for item in s.items]} for s in SLOTS]}
