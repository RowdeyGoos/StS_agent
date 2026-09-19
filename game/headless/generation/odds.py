"""Pinned A0 float32 rarity/potion odds and native reward draw order."""

from game.headless.core.native_rng import single

RARITIES = ("common", "uncommon", "rare")
BASE = {"combat": (0.03, 0.37), "elite": (0.10, 0.40), "boss": (1.0, 0.0), "shop": (0.09, 0.37)}


def initial():
    return {"card_offset": single(-0.05), "potion_chance": single(0.4)}


def validate(data):
    import math

    if not isinstance(data, dict) or set(data) != {"card_offset", "potion_chance"}:
        raise ValueError("Invalid generation odds.")
    for key, value in data.items():
        if type(value) is not float or not math.isfinite(value) or single(value) != value:
            raise ValueError("Generation odds must be finite float32 values.")
    if not single(-0.05) <= data["card_offset"] <= single(0.4):
        raise ValueError("Invalid rarity offset.")
    # Forced potion rewards can drive this below zero; native has no clamp.
    if data["potion_chance"] > single(1.1):
        raise ValueError("Invalid potion odds.")


def rarity(state, kind="combat", *, mode="changing"):
    rare, uncommon = map(single, BASE[kind])
    roll = state.rng.random("rewards")
    if mode == "base":
        return "rare" if roll < rare else "uncommon" if roll < uncommon else "common"
    offset = 0.0 if kind == "boss" and mode == "changing" else state.generation_odds["card_offset"]
    threshold = single(rare + offset)
    result = "rare" if roll < threshold else "uncommon" if roll < single(uncommon + threshold) else "common"
    if mode == "changing":
        state.generation_odds["card_offset"] = (
            single(-0.05)
            if result == "rare"
            else min(single(state.generation_odds["card_offset"] + single(0.01)), single(0.4))
        )
    return result


def potion_drop(state, kind, *, forced=False):
    odds = state.generation_odds
    threshold = single(odds["potion_chance"] + (single(0.125) if kind == "elite" else 0.0))
    result = state.rng.random("rewards") < threshold or forced
    odds["potion_chance"] = single(odds["potion_chance"] + single(-0.1 if result else 0.1))
    return result


def card_offers(
    state,
    cards,
    pool,
    count=3,
    *,
    kind="combat",
    mode="changing",
    uniform=False,
    upgrade_roll=True,
    stream="rewards",
    blacklist=(),
):
    from game.headless.core.content_order import IRONCLADCARDPOOL, COLORLESSCARDPOOL, CURSECARDPOOL, ordered

    from game.headless.generation.foreign import ORDINARY

    pool = ordered(
        [n for n in pool if n not in blacklist], (*IRONCLADCARDPOOL, *COLORLESSCARDPOOL, *CURSECARDPOOL, *(n for names in ORDINARY.values() for n in names))
    )
    pool = list(dict.fromkeys(pool))
    offers = []
    upgraded = []
    for _ in range(min(count, len(pool))):
        if uniform:
            eligible = [n for n in pool if cards.definition(n).rarity not in ("basic", "ancient")]
        else:
            rolled = rarity(state, kind, mode=mode)
            start = RARITIES.index(rolled)
            for i in range(3):
                selected = RARITIES[(start + i) % 3]
                eligible = [n for n in pool if cards.definition(n).rarity == selected]
                if eligible:
                    break
        if not eligible:
            raise ValueError("Card reward has no eligible rarity.")
        name = state.rng.choice(stream, eligible)
        pool.remove(name)
        offers.append(name)
        if upgrade_roll:
            roll = state.rng.random(stream)
            # A0 Act1 base chance0; native <= still upgrades exact zero.
            threshold = 0.0 if cards.definition(name).rarity == "rare" else getattr(state, "act_index", 0) * .25
            if roll <= threshold and len(cards.definition(name).levels) > 1:
                upgraded.append(name)
    return offers, upgraded
