"""Shared relic-aware resource validation for scripted event continuations."""

from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
from game.headless.relics.base import RelicInstance
from game.headless.relics import run_rules

RESOURCE_RELICS = frozenset(
    (
        "tungsten_rod",
        "lizard_tail",
        "bowler_hat",
        "dragon_fruit",
        "book_of_five_rings",
        "lucky_fysh",
        "regal_pillow",
        "stone_humidifier",
        "tiny_mailbox",
    )
)


def capture(state):
    relics = [asdict(r) for r in state.relics if r.definition_id in RESOURCE_RELICS]
    return {"hp": state.hp, "max_hp": state.max_hp, "gold": state.gold, "relics": relics} if relics else None


def expected(state, pending, effects=()):
    context = pending.get("resources")
    if context is None:
        data = pending["data"]
        values = {
            "hp": data.get("initial_hp", state.hp),
            "max_hp": data.get("initial_max_hp", state.max_hp),
            "gold": data.get("initial_gold", state.gold),
            "relics": [],
        }
    else:
        if not isinstance(context, dict) or set(context) != {"hp", "max_hp", "gold", "relics"}:
            raise ValueError("Invalid event resource context.")
        values = deepcopy(context)
        if (
            any(type(values[k]) is not int for k in ("hp", "max_hp", "gold"))
            or not 0 < values["hp"] <= values["max_hp"]
            or values["gold"] < 0
        ):
            raise ValueError("Invalid event entry resources.")
        if not isinstance(values["relics"], list):
            raise ValueError("Invalid event resource relics.")
        values["relics"] = [RelicInstance(**record) for record in values["relics"]]
        ids = []
        for relic in values["relics"]:
            if relic.definition_id not in RESOURCE_RELICS or type(relic.counter) is not int:
                raise ValueError("Invalid event resource modifier.")
            current = next((r for r in state.relics if r.instance_id == relic.instance_id), None)
            if current is None or current.definition_id != relic.definition_id:
                raise ValueError("Unowned event resource modifier.")
            ids.append(relic.instance_id)
        from game.headless.relics.base import RELICS
        from game.headless.relics.combat import validate_data

        for relic in values["relics"]:
            if not 0 <= relic.counter <= RELICS[relic.definition_id].counter_limit:
                raise ValueError("Invalid event entry relic counter.")
            validate_data(relic.definition_id, relic.data)
        if set(ids) != {r.instance_id for r in state.relics if r.definition_id in RESOURCE_RELICS}:
            raise ValueError("Event resource modifiers are incomplete.")
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicated event resource modifier.")
        for field in ("hp", "max_hp", "gold"):
            key = "initial_" + field
            if key in pending["data"] and pending["data"][key] != values[field]:
                raise ValueError("Event entry resource copies disagree.")
    result = SimpleNamespace(**values)
    for operation, amount in effects:
        if operation == "damage":
            run_rules.damage(result, amount)
        elif operation == "gold":
            run_rules.gain_gold(result, amount)
        elif operation == "max_hp":
            run_rules.max_hp(result, amount)
        elif operation == "heal":
            run_rules.heal(result, amount)
        elif operation == "spend_gold":
            result.gold = max(0, result.gold - amount)
        elif operation == "lose_all_gold":
            result.gold = 0
        elif operation == "cards_added":
            for _ in range(amount):
                run_rules.after_card_added(result)
        elif operation == "rest_bonus":
            if run_rules.has(result, "stone_humidifier"):
                run_rules.max_hp(result, 5)
        else:
            raise ValueError("Unknown event resource operation.")
    return result


def validate(state, pending, effects=()):
    result = expected(state, pending, effects)
    if (state.hp, state.max_hp, state.gold) != (result.hp, result.max_hp, result.gold):
        raise ValueError("Event resources differ from their relic-modified effects.")
    if pending.get("resources") is not None:
        for relic in result.relics:
            current = next(r for r in state.relics if r.instance_id == relic.instance_id)
            if current.counter != relic.counter:
                raise ValueError("Event relic counter differs from its effects.")


def valid_new_card(state, card):
    from game.headless.cards.base import Card
    from game.headless.enchantments.base import record

    fresh = run_rules.modify_new_card(state, Card(card.definition))
    return card.upgrade_level == fresh.upgrade_level and record(card) == record(fresh)
