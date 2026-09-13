"""Potion rarity draws shared by combat generation, rewards and merchants."""

from game.headless.potions.base import POTIONS

ORDINARY_POTIONS = tuple(k for k, d in POTIONS.items() if d.rarity in ("common", "uncommon", "rare"))
COSTS = {"common": 50, "uncommon": 75, "rare": 100}


def generate(pool, rng, *, stream=None, in_combat=False, blacklist=()):
    available = [k for k in pool if k not in blacklist and (not in_combat or POTIONS[k].in_combat_generation)]
    if not available:
        raise ValueError("Potion pool has no eligible definitions.")
    # Explicit small fixture pools retain their authored uniform sampling.
    if set(pool) != set(ORDINARY_POTIONS):
        return rng.choice(available) if stream is None else rng.choice(stream, available)
    roll = rng.random() if stream is None else rng.random(stream)
    rarity = "rare" if roll <= 0.10 else "uncommon" if roll <= 0.35 else "common"
    eligible = [k for k in available if POTIONS[k].rarity == rarity]
    return rng.choice(eligible) if stream is None else rng.choice(stream, eligible)


def generate_many(pool, rng, count, *, stream=None):
    if set(pool) != set(ORDINARY_POTIONS):
        return [generate(pool, rng, stream=stream) for _ in range(count)]
    available = list(pool)
    result = []
    for _ in range(count):
        roll = rng.random() if stream is None else rng.random(stream)
        rarity = "rare" if roll <= 0.10 else "uncommon" if roll <= 0.35 else "common"
        eligible = [k for k in available if POTIONS[k].rarity == rarity]
        name = rng.choice(eligible) if stream is None else rng.choice(stream, eligible)
        result.append(name)
        available.remove(name)
    return result
