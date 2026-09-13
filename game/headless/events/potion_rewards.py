"""Owned optional potion bundles shared by event content."""

from game.headless.potions.base import POTIONS
from game.headless.run.inventory import add_potion


def generate(rng, pool, count):
    if not pool or any(name not in POTIONS for name in pool):
        raise ValueError("Unsupported event potion pool.")
    from game.headless.potions.pools import generate_many
    return [{"definition_id": name, "claimed_id": None} for name in generate_many(pool, rng, count, stream="event.potions")]


def options(pending):
    return tuple(f"claim_potion_{i}" for i, r in enumerate(pending["data"]["rewards"]) if r["claimed_id"] is None) + ("finish_rewards",)


def choose(state, pending, option_id):
    if option_id == "finish_rewards":
        pending["stage"] = "resolved"
        return
    index = int(option_id.removeprefix("claim_potion_"))
    reward = pending["data"]["rewards"][index]
    if reward["claimed_id"] is not None:
        raise ValueError("Potion already claimed.")
    potion = add_potion(state, reward["definition_id"])
    reward["claimed_id"] = potion.instance_id


def validate(state, records, pool, count):
    if not isinstance(records, list) or len(records) != count:
        raise ValueError("Invalid event potion bundle.")
    claimed = []
    for record in records:
        if (not isinstance(record, dict) or set(record) != {"definition_id", "claimed_id"}
                or record["definition_id"] not in pool):
            raise ValueError("Invalid event potion offer.")
        identity = record["claimed_id"]
        if identity is None:
            continue
        if not isinstance(identity, str) or not identity.startswith("run.item."):
            raise ValueError("Invalid claimed potion ID.")
        suffix = identity.removeprefix("run.item.")
        if not suffix.isdecimal() or str(int(suffix)) != suffix or int(suffix) >= state.next_item_id:
            raise ValueError("Unallocated event potion ID.")
        if any(r.instance_id == identity for r in state.relics):
            raise ValueError("Event potion ID belongs to a relic.")
        owned = next((p for p in state.potions if p is not None and p.instance_id == identity), None)
        if owned is not None and owned.definition_id != record["definition_id"]:
            raise ValueError("Claimed potion differs from inventory.")
        claimed.append(identity)
    if len(claimed) != len(set(claimed)):
        raise ValueError("Potion offers share an item identity.")
