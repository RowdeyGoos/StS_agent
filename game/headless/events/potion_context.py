"""Potion use between event decisions, replayed at its resource boundary."""

from dataclasses import asdict
from game.headless.potions.base import POTIONS, PotionInstance


def position(pending):
    if pending["definition_id"] == "slippery_bridge":
        return len(pending["data"]["offers"]) - 1
    if pending["definition_id"] == "tablet_of_truth" and pending["data"]["choice"] != "smash":
        return pending["data"]["count"]
    return 0 if pending["stage"] in ("options", "select_card") else 999


def record(state, before, definition_id=None):
    pending = state.pending
    if pending is None or pending.get("kind") != "scripted_event":
        return
    pending.setdefault("potion_changes", []).append(
        {
            "position": position(pending),
            "definition_id": definition_id,
            "before": before,
            "after": [None if p is None else asdict(p) for p in state.potions],
        }
    )


def inventory(state, records):
    if not isinstance(records, list) or len(records) != state.potion_capacity:
        raise ValueError("Invalid event potion inventory.")
    ids = []
    for record in records:
        if record is None:
            continue
        if (
            not isinstance(record, dict)
            or set(record) != {"definition_id", "instance_id"}
            or record["definition_id"] not in POTIONS
        ):
            raise ValueError("Invalid event potion record.")
        identity = record["instance_id"]
        suffix = identity.removeprefix("run.item.") if isinstance(identity, str) else ""
        if (
            not suffix.isdecimal()
            or identity != f"run.item.{int(suffix)}"
            or int(suffix) >= state.next_item_id
            or identity in ids
            or any(r.instance_id == identity for r in state.relics)
        ):
            raise ValueError("Unowned event potion.")
        ids.append(identity)
    return [None if r is None else PotionInstance(**r) for r in records]


def apply_at(result, state, pending, index):
    from game.headless.relics.run_rules import heal, max_hp

    changes = pending.get("potion_changes", [])
    if not isinstance(changes, list):
        raise ValueError("Invalid event potion history.")
    previous = -1
    consumed = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"position", "definition_id", "before", "after"}:
            raise ValueError("Invalid event potion change.")
        at = change["position"]
        if type(at) is not int or not previous <= at <= position(pending):
            raise ValueError("Invalid event potion boundary.")
        previous = at
        before, after = inventory(state, change["before"]), inventory(state, change["after"])
        name = change["definition_id"]
        if name not in (None, "blood_potion", "fruit_juice", "entropic_brew"):
            raise ValueError("Invalid event potion use.")
        if any(p is not None and p.instance_id in consumed for p in before):
            raise ValueError("Event potion history reuses a removed bottle.")
        transitions(before, after, name, state)
        consumed.update(
            {p.instance_id for p in before if p is not None} - {p.instance_id for p in after if p is not None}
        )
        if at != index:
            continue
        if hasattr(result, "potions") and result.potions != before:
            raise ValueError("Event potion inventories do not form an owned chain.")
        # The ordinary event effects between boundaries can consume a Fairy;
        # claim/discard commands then establish the next owned inventory.
        if name == "blood_potion":
            heal(result, result.max_hp * 20 // 100)
        elif name == "fruit_juice":
            max_hp(result, 5)
        result.potions = after


def transitions(before, after, name, state):
    old = {p.instance_id: p for p in before if p is not None}
    new = {p.instance_id: p for p in after if p is not None}
    removed, added = set(old) - set(new), set(new) - set(old)
    if any(old[i] != new[i] or before.index(old[i]) != after.index(new[i]) for i in old.keys() & new.keys()):
        raise ValueError("Event potion survivors changed.")
    if name is None:
        if len(removed) + len(added) != 1:
            raise ValueError("Event potion claim/discard must change one slot.")
    elif len(removed) != 1 or old[next(iter(removed))].definition_id != name:
        raise ValueError("Event potion use must consume one matching bottle.")
    elif name != "entropic_brew" and added:
        raise ValueError("Event potion use cannot create items.")
    elif name == "entropic_brew":
        pool = state.config.reward_potions if state.config else ("fire_potion", "block_potion")
        if None in after or any(new[i].definition_id not in pool for i in added):
            raise ValueError("Invalid Entropic Brew refill.")
