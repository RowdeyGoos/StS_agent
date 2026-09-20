"""Native rarity rolls and persistent front/back relic grab bags (solo)."""

from game.headless.core.native_rng import single
from game.headless.core.content_order import SHAREDRELICPOOL, IRONCLADRELICPOOL
from game.headless.relics.base import RELICS

RARITIES = ("common", "uncommon", "rare", "shop")


def populate(rng):
    result = {}
    # Native run setup populates shared first, then player, from one UpFront RNG.
    for owner, pool in (("shared", SHAREDRELICPOOL), ("player", (*SHAREDRELICPOOL, *IRONCLADRELICPOOL))):
        bags = {}
        for name in pool:
            rarity = RELICS[name].rarity
            if owner == "player" and rarity not in RARITIES:
                continue
            bags.setdefault(rarity, []).append(name)
        for bag in bags.values():
            rng.shuffle("up_front", bag)
        result[owner] = bags
    return result


def validate(data):
    if not isinstance(data, dict) or set(data) != {"shared", "player"}:
        raise ValueError("Invalid relic bags.")
    for owner, bags in data.items():
        if not isinstance(bags, dict):
            raise ValueError("Invalid relic rarity bags.")
        seen = []
        for rarity, bag in bags.items():
            if rarity not in (*RARITIES, "event", "ancient") or owner == "player" and rarity not in RARITIES:
                raise ValueError("Invalid relic bag rarity.")
            if not isinstance(bag, list) or any(n not in RELICS or RELICS[n].rarity != rarity for n in bag):
                raise ValueError("Invalid relic bag membership.")
            if owner == "shared" and any(n not in SHAREDRELICPOOL for n in bag):
                raise ValueError("Nonshared relic in shared bag.")
            seen += bag
        if len(seen) != len(set(seen)):
            raise ValueError("Repeated relic in grab bag.")


def roll(rng, stream="rewards"):
    value = rng.random(stream)
    return "common" if value < single(0.5) else "uncommon" if value < single(0.83) else "rare"


def remove(state, name):
    if state.relic_bags is not None:
        for bags in state.relic_bags.values():
            for bag in bags.values():
                if name in bag:
                    bag.remove(name)


def pull(state, *, rarity=None, back=False, blacklist=(), stream="rewards", allowed=None, owner="player"):
    if owner not in ("player", "shared"):
        raise ValueError("Invalid relic bag owner.")
    rarity = rarity or roll(state.rng, stream)
    order = ("shop", "common", "uncommon", "rare")
    if rarity not in order:
        raise ValueError("Invalid relic draw rarity.")
    owned = {r.definition_id for r in state.relics}
    allowed = set(allowed) if allowed is not None else set(RELICS)
    bags = state.relic_bags[owner]
    from game.headless.relics.eligibility import allowed_in_run
    # GetAvailableDeque removes globally disallowed relics from ALL rarities.
    # Caller-only exclusions stay in place, including when falling to a later rarity.
    for bag in bags.values():
        bag[:] = [n for n in bag if n not in owned and allowed_in_run(state, n)]
    for kind in order[order.index(rarity) :]:
        bag = bags.get(kind, [])
        indices = range(len(bag) - 1, -1, -1) if back else range(len(bag))
        for i in indices:
            name = bag[i]
            if name in blacklist or name not in allowed:
                continue
            bag.pop(i)
            # Player offers also remove the shared copy. Chest offers consume
            # only the shared bag; acquisition later removes both owned copies.
            if owner == "player":
                for values in state.relic_bags["shared"].values():
                    if name in values:
                        values.remove(name)
            return name
    return "circlet"
