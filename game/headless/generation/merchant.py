"""Native merchant composition and random draw order using existing shop offers."""

from game.headless.core.native_rng import single
from game.headless.core.content_order import IRONCLADCARDPOOL, COLORLESSCARDPOOL, ordered
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.shops.catalog import StockSlot
from game.headless.relics.pools import MERCHANT_COSTS
from game.headless.generation.odds import rarity, RARITIES
from game.headless.generation.relics import pull, roll

TYPES = ("attack", "attack", "skill", "skill", "power")
COST = {"common": 50, "uncommon": 75, "rare": 150}


def card_cost(definition):
    cost = COST[definition.rarity]
    return round(single(cost * single(1.15))) if definition.pool == "colorless" else cost


def native_slots(character="ironclad"):
    result = []
    for kind in TYPES:
        result.append(
            StockSlot(
                "card",
                tuple(
                    (d.definition_id, card_cost(d))
                    for d in DEFAULT_CARDS.definitions
                    if d.pool == character
                    and d.rarity in COST
                    and ("skill" if d.levels[0].kind == "block" else d.levels[0].kind) == kind
                ),
            )
        )
    for rarity in ("uncommon", "rare"):
        result.append(
            StockSlot(
                "card",
                tuple(
                    (d.definition_id, card_cost(d))
                    for d in DEFAULT_CARDS.definitions
                    if d.pool == "colorless" and d.rarity == rarity
                ),
                sale_eligible=False,
            )
        )
    result += [StockSlot("relic", (), 15) for _ in range(3)]
    result += [StockSlot("potion", ()) for _ in range(3)]
    return tuple(result)


SLOTS = native_slots()


def slots_for(state):
    if getattr(state.rng, "native", False):
        from game.headless.characters import character
        return native_slots(character(state))
    from game.headless.shops.catalog import SLOTS as fixture

    from game.headless.characters import character
    from dataclasses import replace
    family = character(state)
    return tuple(replace(slot, items=tuple((d.definition_id, COST[rarity]) for d in DEFAULT_CARDS.definitions
                 if d.pool == family and d.rarity == rarity))
                 for slot, rarity in zip(fixture[:3], COST)) + fixture[3:]


def price(state, base, variation, on_sale=False):
    scale = state.rng.stream("shops").next_float(1 - variation / 100, 1 + variation / 100)
    result = round(single(base * scale))
    return result // 2 if on_sale else result


def card(state, cards, index, excluded):
    from game.headless.characters import character, card_order
    pool = [n for n, _ in native_slots(character(state))[index].items if n not in excluded]
    pool = ordered(pool, (*card_order(character(state)), *COLORLESSCARDPOOL))
    if index < 5:
        rolled = rarity(state, "shop", mode="unchanged")
        start = RARITIES.index(rolled)
        for offset in range(3):
            candidates = [n for n in pool if cards.definition(n).rarity == RARITIES[(start + offset) % 3]]
            if candidates:
                break
    else:
        candidates = pool
    name = state.rng.choice("shops", candidates)
    state.rng.random("rewards")  # native negative-base upgrade check still rolls
    return name, card_cost(cards.definition(name))


def populate(state, cards):
    from game.headless.run.shop import discounted, modify_offer
    from game.headless.potions.pools import generate_many, COSTS
    from game.headless.potions.base import POTIONS
    from game.headless.relics.base import RELICS

    sale = state.rng.randint("shops", 0, 4)
    offers = []

    def append(index, name, base, on_sale=False):
        slot = SLOTS[index]
        cost = price(state, base, slot.variation)
        if on_sale:
            cost = price(state, base, slot.variation, True)
        offer = dict(
            offer_id=f"shop.{state.next_shop_id}.offer.{index}",
            slot=index,
            definition_id=name,
            kind=slot.kind,
            on_sale=on_sale,
            base_price=cost,
            price=discounted(state, cost),
            sold=False,
            generation=0,
            upgrade_level=0,
            enchantment=None,
        )
        if slot.kind == "card":
            modify_offer(state, cards, offer)
        offers.append(offer)

    for i in range(7):
        name, base = card(state, cards, i, {o["definition_id"] for o in offers})
        append(i, name, base, i == sale)
    rarities = (roll(state.rng), roll(state.rng), "shop")
    for i, kind in enumerate(rarities, 7):
        name = pull(state, rarity=kind, back=True, allowed=state.config.shop_relics)
        append(i, name, MERCHANT_COSTS.get(RELICS[name].rarity, 175))
    potions = generate_many(state.config.reward_potions, state.rng, 3, stream="shops")
    for i, name in enumerate(potions, 10):
        append(i, name, COSTS[POTIONS[name].rarity])
    return offers


def restock(state, cards, offer):
    from game.headless.run.shop import modify_offer, discounted
    from game.headless.potions.pools import generate, COSTS
    from game.headless.potions.base import POTIONS
    from game.headless.relics.base import RELICS

    live = [o["definition_id"] for o in state.pending["offers"] if o is not offer and not o["sold"]]
    index = offer["slot"]
    kind = offer["kind"]
    if kind == "card":
        name, base = card(state, cards, index, live)
    elif kind == "relic":
        name = pull(state, back=True, blacklist=live, allowed=state.config.shop_relics)
        base = MERCHANT_COSTS.get(RELICS[name].rarity, 175)
    else:
        name = generate(state.config.reward_potions, state.rng, stream="shops")
        base = COSTS[POTIONS[name].rarity]
    cost = price(state, base, SLOTS[index].variation)
    generation = offer["generation"] + 1
    offer.update(
        definition_id=name,
        sold=False,
        on_sale=False,
        generation=generation,
        offer_id=f"shop.{state.pending['shop_id']}.offer.{index}.refill.{generation}",
        base_price=cost,
        price=discounted(state, cost),
        upgrade_level=0,
        enchantment=None,
    )
    modify_offer(state, cards, offer)
