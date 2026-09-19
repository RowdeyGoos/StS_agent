"""Validate event branch cursors and suspended owned selections."""

from types import SimpleNamespace
from game.headless.core.snapshots import card_record, restore_card


def validate(definition, pending, state, cards, *, defeated=False):
    data = pending["data"]
    if not isinstance(data, dict) or set(data) != {
        "choice",
        "cursor",
        "active",
        "receipts",
        "eligible",
        "variables",
        "options",
        "originals",
        "checkpoint",
    }:
        raise ValueError("Invalid event continuation fields.")
    from game.headless.events.checkpoint import capture

    if data["checkpoint"] != capture(state, data):
        raise ValueError("Event state differs from its last successful command.")
    context = pending.get("resources")
    if not isinstance(context, dict) or set(context) != {"hp", "max_hp", "gold", "relics", "potions"}:
        raise ValueError("Invalid event entry resources.")
    if (
        any(type(context[k]) is not int for k in ("hp", "max_hp", "gold"))
        or not 0 < context["hp"] <= context["max_hp"]
        or context["gold"] < 0
    ):
        raise ValueError("Invalid event entry amounts.")
    original = restore_records(data["originals"], state, cards)
    from game.headless.events.potion_context import inventory

    initial = SimpleNamespace(**context)
    initial.deck = original
    initial.potions = inventory(state, context["potions"])
    values = data["variables"]
    name = definition.definition_id
    if not isinstance(values, dict):
        raise ValueError("Invalid event variables.")
    keys = {
        "luminous_choir": {"price"},
        "unrest_site": {"heal"},
        "this_or_that": {"gold"},
        "the_future_of_potions": {"trades"},
    }.get(name, set())
    if set(values) != keys:
        raise ValueError("Unexpected event variables.")
    for k, low, high in [("price", 100, 149), ("gold", 41, 68), ("heal", 0, context["max_hp"])]:
        if k in values and (type(values[k]) is not int or not low <= values[k] <= high):
            raise ValueError("Invalid event amount.")
    if name == "unrest_site" and values["heal"] != context["max_hp"] - context["hp"]:
        raise ValueError("Unrest healing differs from entry.")
    if name == "the_future_of_potions":
        from game.headless.potions.base import POTIONS

        items = [p for p in initial.potions if p is not None]
        if not isinstance(values["trades"], list) or len(values["trades"]) != len(items):
            raise ValueError("Invalid potion trades.")
        for row, item in zip(values["trades"], items):
            rarity = POTIONS[item.definition_id].rarity
            if (
                not isinstance(row, dict)
                or set(row) != {"instance_id", "definition_id", "rarity", "kind"}
                or row["instance_id"] != item.instance_id
                or row["definition_id"] != item.definition_id
                or row["rarity"] != {"token": "common", "event": "rare"}.get(rarity, rarity)
                or row["kind"]
                not in (
                    ("attack", "skill") if rarity in ("common", "token") else ("attack", "skill", "power")
                )
            ):
                raise ValueError("Potion trade differs from its bottle.")
    from game.headless.events.act1_content import offered_options

    if data["options"] != offered_options(definition, values, initial):
        raise ValueError("Event options differ from entry.")
    if data["choice"] is not None and data["choice"] not in data["options"]:
        raise ValueError("Unknown event branch.")
    plan = definition.plan(data)
    cursor = data["cursor"]
    if (
        type(cursor) is not int
        or not 0 <= cursor <= len(plan)
        or not isinstance(data["receipts"], list)
        or len(data["receipts"]) != cursor
    ):
        raise ValueError("Invalid event cursor.")
    for op, receipt in zip(plan, data["receipts"]):
        if (
            not isinstance(receipt, dict)
            or set(receipt) != {"operation", "result"}
            or receipt["operation"] != op
        ):
            raise ValueError("Event receipt differs from its branch.")
        result = receipt["result"]
        if op[0] in ("damage", "gold", "spend", "heal", "max_hp") and result is not None:
            raise ValueError("Unexpected event result.")
        if op[0] == "card":
            if result is None and defeated:
                continue
            restored = restore_records([result], state, cards)[0]
            if restored.definition.definition_id != op[1]:
                raise ValueError("Wrong event card result.")
        if op[0] == "relic":
            from game.headless.relics.base import RELICS

            if (
                not isinstance(result, dict)
                or set(result) != {"definition_id", "instance_id"}
                or result["definition_id"] not in RELICS
            ):
                raise ValueError("Invalid event relic result.")
            if op[1] != "random" and result["definition_id"] != op[1]:
                raise ValueError("Wrong event relic.")
            check_id(result["instance_id"], "run.item.", state.next_item_id)
    active = data["active"]
    stage = pending["stage"]
    if defeated:
        if state.hp or stage != "defeated":
            raise ValueError("Invalid defeated event.")
        return
    if data["choice"] is None:
        if stage != "options" or cursor or active is not None or data["eligible"]:
            raise ValueError("Invalid initial event choice.")
        return
    if state.relic_work:
        if stage != "relic_work" or active is not None:
            raise ValueError("Event bypasses relic acquisition.")
        return
    if cursor == len(plan):
        if stage != "resolved" or active is not None or data["eligible"]:
            raise ValueError("Invalid resolved event.")
        return
    if not isinstance(active, dict):
        raise ValueError("Missing active event work.")
    op = plan[cursor]
    if op[0] == "select":
        if stage != "select_card" or set(active) != {
            "candidates",
            "selected",
            "originals",
            "results",
            "count",
        }:
            raise ValueError("Invalid event selection.")
        original = restore_records(active["originals"], state, cards)
        from game.headless.events.steps import eligible

        candidates = [c.instance_id for c in eligible(SimpleNamespace(deck=original), op[1], op[3])]
        selected = active["selected"]
        if (
            active["candidates"] != candidates
            or not isinstance(selected, list)
            or len(selected) != len(set(selected))
            or any(i not in candidates for i in selected)
            or active["count"] != min(op[2], len(candidates))
            or not len(selected) < active["count"]
            or len(active["results"]) != len(selected)
            or data["eligible"] != [i for i in candidates if i not in selected]
        ):
            raise ValueError("Invalid event selection bounds.")
        expected = list(active["originals"])
        for identity, result in zip(selected, active["results"]):
            index = next(i for i, r in enumerate(expected) if r["instance_id"] == identity)
            if op[1] == "remove":
                if result is not None:
                    raise ValueError("Removal retained a card.")
                expected.pop(index)
            else:
                restore_records([result], state, cards)
                expected[index] = result
        if expected != [card_record(c) for c in state.deck]:
            raise ValueError("Event selection deck changed.")
    elif op[0] == "cards":
        from game.headless.relics.reward_alternatives import validate_marker
        validate_marker(state, active)
        if stage != "card_rewards" or set(active) - {"rerolled"} != {
            "offers",
            "modifiers",
            "selected",
            "results",
            "count",
            "optional",
        }:
            raise ValueError("Invalid event card reward.")
        offers = active["offers"]
        if (
            not isinstance(offers, list)
            or not offers
            or len(offers) > op[4]
            or len(offers) != len(set(offers))
            or set(active["modifiers"]) != set(offers)
            or active["count"] != min(op[5], len(offers))
            or active["optional"] is not op[6]
        ):
            raise ValueError("Invalid event reward bounds.")
        for n in offers:
            d = cards.definition(n)
            if d.rarity not in (("common", "uncommon", "rare") if op[2] == "any" else (op[2],)) or (
                op[3] != "any" and d.levels[0].kind != op[3]
            ):
                raise ValueError("Wrong event reward content.")
            if d.pool != op[1] and not (
                op[6] and op[1] != "colorless" and d.pool in ("ironclad","silent","regent","necrobinder","defect") and any(r.definition_id == "prismatic_gem" for r in state.relics)
            ) and not (
                d.pool == "colorless"
                and name not in ("the_future_of_potions",)
                and any(r.definition_id == "dingy_rug" for r in state.relics)
            ):
                raise ValueError("Wrong event reward pool.")
            modifier = active["modifiers"][n]
            probe = cards.create(n, upgrade_level=modifier["upgrade_level"])
            from game.headless.enchantments.base import restore, validate as validate_enchantment

            probe.enchantment = restore(modifier["enchantment"])
            validate_enchantment(probe, permanent=True)
            if op[7] and len(d.levels) > 1 and not probe.upgrade_level:
                raise ValueError("Future reward lost its upgrade.")
        selected = active["selected"]
        if (
            not isinstance(selected, list)
            or len(selected) != len(set(selected))
            or any(type(i) is not int or not 0 <= i < len(offers) for i in selected)
            or not len(selected) < active["count"]
            or len(active["results"]) != len(selected)
        ):
            raise ValueError("Invalid selected event rewards.")
        for i, result in zip(selected, active["results"]):
            c = restore_records([result], state, cards)[0]
            if c.definition.definition_id != offers[i] or result not in [card_record(c) for c in state.deck]:
                raise ValueError("Event reward is not owned.")
    elif op[0] == "potion":
        from game.headless.potions.pools import ORDINARY_POTIONS

        if (
            stage != "potion_rewards"
            or set(active) != {"definition_id"}
            or active["definition_id"] not in ORDINARY_POTIONS
        ):
            raise ValueError("Invalid event potion reward.")
    else:
        raise ValueError("Event stopped on automatic work.")


def check_id(value, prefix, limit):
    suffix = value.removeprefix(prefix) if isinstance(value, str) else ""
    if not suffix.isdecimal() or value != f"{prefix}{int(suffix)}" or int(suffix) >= limit:
        raise ValueError("Unowned event identity.")


def restore_records(records, state, cards):
    if not isinstance(records, list):
        raise ValueError("Invalid event cards.")
    result = [restore_card(r, cards) for r in records]
    ids = [c.instance_id for c in result]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicated event card.")
    for i in ids:
        check_id(i, "run.card.", state.next_card_id)
    return result
