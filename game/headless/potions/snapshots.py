"""Validate consumed-potion ownership and interrupted effect continuations."""

from game.headless.potions.base import POTIONS


def validate(r, p):
    if not isinstance(r.potions, list) or (r.potions and len(r.potions) != r.potion_capacity):
        raise ValueError("Invalid combat potion inventory.")
    ids = []
    for item in r.potions:
        if item is not None:
            if (
                not isinstance(item, dict)
                or set(item) != {"definition_id", "instance_id"}
                or item["definition_id"] not in POTIONS
                or not isinstance(item["instance_id"], str)
                or not item["instance_id"]
            ):
                raise ValueError("Invalid potion instance.")
            ids.append(item["instance_id"])
    if len(ids) != len(set(ids)) or not isinstance(r.potion_uses, dict) or len(r.potion_uses) > 1:
        raise ValueError("Duplicate potion identity.")
    for identity, frame in r.potion_uses.items():
        if (
            not isinstance(identity, str)
            or not identity
            or identity in ids
            or not isinstance(frame, dict)
            or set(frame) != {"definition_id", "target", "effect_index"}
            or frame["definition_id"] not in POTIONS
        ):
            raise ValueError("Invalid active potion use.")
        definition = POTIONS[frame["definition_id"]]
        index, slot = frame["effect_index"], frame["target"]
        if type(index) is not int or not 0 <= index < len(definition.effects):
            raise ValueError("Invalid potion effect cursor.")
        if definition.targeted:
            if type(slot) is not int or not 0 <= slot < len(p.combat_enemies):
                raise ValueError("Invalid potion target.")
        elif slot is not None:
            raise ValueError("Unexpected potion target.")
        control = [t for t in r.tasks if t[0] in ("potion_effect", "potion_finish") and t[1] == identity]
        expected = [["potion_effect", identity, i] for i in range(index + 1, len(definition.effects))] + [
            ["potion_finish", identity]
        ]
        if control != expected or r.tasks[-len(expected) :] != expected:
            raise ValueError("Missing or repeated potion continuation.")
        if r.selection is not None and r.selection["source"] == identity:
            if definition.effects[index][0] not in ("select", "offer"):
                raise ValueError("Potion cursor does not own a selector.")
    for task in r.tasks:
        if task[0] in ("potion_effect", "potion_finish", "potion_status"):
            if len(task) < 2 or task[1] not in r.potion_uses:
                raise ValueError("Unowned potion work.")
        if task[0] == "potion_status":
            if len(task) != 5:
                raise ValueError("Invalid potion status work.")
            _, identity, slot, status, amount = task
            frame = r.potion_uses[identity]
            effect = POTIONS[frame["definition_id"]].effects[frame["effect_index"]]
            if (
                type(slot) is not int
                or not 0 <= slot < len(p.combat_enemies)
                or effect[0] not in ("status", "all_status")
                or (status, amount) != effect[1:]
                or (effect[0] == "status" and slot != frame["target"])
            ):
                raise ValueError("Potion status differs from its source.")
