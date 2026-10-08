"""Potion rarity draws shared by combat generation, rewards and merchants."""

from game.headless.potions.base import POTIONS
from game.headless.core.native_rng import single

from game.headless.characters import CHARACTERS, potion_pool
FOREIGN_POTIONS = frozenset(n for c,d in CHARACTERS.items() if c != "ironclad" for n in d.potion_pool)
ORDINARY_POTIONS = tuple(k for k, d in POTIONS.items() if k not in FOREIGN_POTIONS and d.rarity in ("common", "uncommon", "rare"))


def is_ordinary(pool):
    return any(set(pool) == set(potion_pool(c)) for c in CHARACTERS)


def native_order(pool):
    from game.headless.core.content_order import SHAREDPOTIONPOOL, ordered
    return ordered(pool, (*(n for d in CHARACTERS.values() for n in d.potion_pool), *SHAREDPOTIONPOOL))
COSTS = {"common": 50, "uncommon": 75, "rare": 100}


def unlocked_order(pool, rng):
    """Native character-then-shared definition order for direct uniform draws."""
    from game.headless.core.content_order import SHAREDPOTIONPOOL, ordered
    from game.headless.core.native_rng import NativeRng
    if getattr(rng, "native", False) or isinstance(rng, NativeRng):
        return native_order(pool)
    return list(pool)


def generate(pool, rng, *, stream=None, in_combat=False, blacklist=(), revealed=False):
    from game.headless.core.content_order import SHAREDPOTIONPOOL, ordered
    from game.headless.core.native_rng import NativeRng
    if getattr(rng, "native", False) or isinstance(rng, NativeRng):
        pool = native_order(pool)
    available = [k for k in pool if k not in blacklist and (not in_combat or POTIONS[k].in_combat_generation)]
    if not available:
        raise ValueError("Potion pool has no eligible definitions.")
    # Explicit small fixture pools retain their authored uniform sampling.
    if not is_ordinary(pool):
        actual = rng.choice(available) if stream is None else rng.choice(stream, available)
        probabilities = {k: 1 / len(available) for k in available}
        journal = getattr(rng, 'combat_reveals', None) if stream is None and revealed else None
        return actual if journal is None else journal.potion(actual, probabilities)
    roll = rng.random() if stream is None else rng.random(stream)
    rarity = "rare" if roll <= single(0.10) else "uncommon" if roll <= single(0.35) else "common"
    eligible = [k for k in available if POTIONS[k].rarity == rarity]
    actual = rng.choice(eligible) if stream is None else rng.choice(stream, eligible)
    journal = getattr(rng, 'combat_reveals', None) if stream is None and revealed else None
    if journal is None:
        return actual
    probabilities = _generation_probabilities(available, rng)
    return journal.potion(actual, probabilities)


def _generation_probabilities(available, rng):
    """The same rarity thresholds as generate(), including binary32 rounding."""
    from collections import Counter
    from game.headless.core.native_rng import NativeRng
    from math import ceil
    from struct import pack, unpack

    def cumulative(threshold):
        value = single(threshold)
        if not isinstance(rng, NativeRng):
            # random.Random.random is uniform on the 53-bit binary grid.
            return (int(value * 2**53) + 1) / 2**53
        bits = unpack('<I', pack('<f', value))[0]
        following = unpack('<f', pack('<I', bits + 1))[0]
        boundary = ((value + following) / 2) * 2**53
        # Ties round to the even binary32 mantissa.
        return (ceil(boundary) + int(boundary.is_integer() and bits % 2 == 0)) / 2**53

    rare, uncommon = cumulative(.10), cumulative(.35)
    weights = dict(rare=rare, uncommon=uncommon-rare, common=1-uncommon)
    counts = Counter(POTIONS[k].rarity for k in available)
    return {k: weights[POTIONS[k].rarity] / counts[POTIONS[k].rarity] for k in available}


def generate_many(pool, rng, count, *, stream=None, in_combat=False, blacklist=()):
    if not is_ordinary(pool):
        return [generate(pool, rng, stream=stream, in_combat=in_combat, blacklist=blacklist) for _ in range(count)]
    from game.headless.core.content_order import SHAREDPOTIONPOOL, ordered
    from game.headless.core.native_rng import NativeRng
    available = native_order(pool) if getattr(rng,"native",False) or isinstance(rng,NativeRng) else list(pool)
    available = [k for k in available if k not in blacklist and (not in_combat or POTIONS[k].in_combat_generation)]
    result = []
    for _ in range(count):
        roll = rng.random() if stream is None else rng.random(stream)
        rarity = "rare" if roll <= single(0.10) else "uncommon" if roll <= single(0.35) else "common"
        eligible = [k for k in available if POTIONS[k].rarity == rarity]
        name = rng.choice(eligible) if stream is None else rng.choice(stream, eligible)
        result.append(name)
        available.remove(name)
    return result
