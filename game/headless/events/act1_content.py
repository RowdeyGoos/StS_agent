"""Remaining pinned Overgrowth and Act 1 shared event branches."""

from game.headless.events.steps import StepEvent, eligible

DEFINITIONS = (
    StepEvent(
        "luminous_choir",
        (
            ("reach_into_the_flesh", (("select", "remove", 2, "", 0), ("card", "spore_mind"))),
            ("offer_tribute", (("spend", "$price"), ("relic", "random"))),
        ),
    ),
    StepEvent(
        "unrest_site",
        (
            ("rest", (("heal", "$heal"), ("card", "poor_sleep"))),
            ("kill", (("max_hp", -8), ("relic", "random"))),
        ),
    ),
    StepEvent(
        "wood_carvings",
        (
            ("bird", (("select", "transform_basic", 1, "peck", 0),)),
            ("snake", (("select", "enchant", 1, "slither", 1),)),
            ("torus", (("select", "transform_basic", 1, "toric_toughness", 0),)),
        ),
    ),
    StepEvent(
        "brain_leech",
        (
            ("share_knowledge", (("cards", "ironclad", "any", "any", 5, 1, False, False),)),
            ("rip", (("damage", 5), ("cards", "colorless", "any", "any", 3, 1, True, False))),
        ),
    ),
    StepEvent(
        "room_full_of_cheese",
        (
            ("gorge", (("cards", "ironclad", "common", "any", 8, 2, False, False),)),
            ("search", (("damage", 14), ("relic", "chosen_cheese"))),
        ),
    ),
    StepEvent(
        "self_help_book",
        (
            ("read_the_back", (("select", "enchant", 1, "sharp", 2),)),
            ("read_passage", (("select", "enchant", 1, "nimble", 2),)),
            ("read_entire_book", (("select", "enchant", 1, "swift", 2),)),
            ("skip_book", ()),
        ),
    ),
    StepEvent(
        "tea_master",
        (
            ("bone_tea", (("spend", 50), ("relic", "bone_tea"))),
            ("ember_tea", (("spend", 150), ("relic", "ember_tea"))),
            ("tea_of_discourtesy", (("relic", "tea_of_discourtesy"),)),
        ),
    ),
    StepEvent("the_future_of_potions", ()),
    StepEvent(
        "the_legends_were_true",
        (("nab_the_map", (("card", "spoils_map"),)), ("slowly_find_an_exit", (("damage", 8), ("potion",)))),
    ),
    StepEvent(
        "this_or_that",
        (
            ("plain", (("damage", 6), ("gold", "$gold"))),
            ("ornate", (("relic", "random"), ("card", "clumsy"))),
        ),
    ),
)


def variables(name, rng, state):
    if name == "luminous_choir":
        return {"price": 149 - rng.randint("event.luminous_choir", 0, 49)}
    if name == "unrest_site":
        return {"heal": state.max_hp - state.hp}
    if name == "this_or_that":
        return {"gold": rng.randint("event.this_or_that", 41, 68)}
    if name == "the_future_of_potions":
        from game.headless.potions.base import POTIONS

        offers = []
        for item in state.potions:
            if item is None:
                continue
            rarity = POTIONS[item.definition_id].rarity
            family = ("attack", "skill") if rarity in ("common", "token") else ("attack", "skill", "power")
            offers.append(
                dict(
                    instance_id=item.instance_id,
                    definition_id=item.definition_id,
                    rarity={"event": "rare", "token": "common"}.get(rarity, rarity),
                    kind=rng.choice("event.future_potions", family),
                )
            )
        return {"trades": offers}
    return {}


def offered_options(definition, values, state):
    name = definition.definition_id
    if name == "the_future_of_potions":
        return [f"trade_{i}" for i in range(min(3, len(values["trades"])))]
    choices = []
    for option, operations in definition.branches:
        if option == "skip_book":
            continue
        if option == "offer_tribute" and state.gold < values["price"]:
            continue
        if name == "tea_master" and option != "tea_of_discourtesy" and state.gold < operations[0][1]:
            continue
        if name == "self_help_book" or option == "snake":
            _, mode, _, enchantment, _ = operations[0]
            if not eligible(state, mode, enchantment):
                continue
        choices.append(option)
    return choices or (["skip_book"] if name == "self_help_book" else [])


def plan(definition, data):
    if data["choice"] is None:
        return []
    if definition.definition_id == "the_future_of_potions":
        item = data["variables"]["trades"][int(data["choice"].removeprefix("trade_"))]
        return [
            ["discard_potion", item["instance_id"]],
            ["cards", "ironclad", item["rarity"], item["kind"], 3, 1, True, True],
        ]
    return [
        [data["variables"][v[1:]] if isinstance(v, str) and v.startswith("$") else v for v in op]
        for op in dict(definition.branches)[data["choice"]]
    ]


def allowed(name, c):
    if name == "luminous_choir":
        return c["gold"] >= 149 and c.get("available_relics", True)
    if name == "unrest_site":
        return c.get("hp", 0) * 100 <= c.get("max_hp", 1) * 70
    if name == "wood_carvings":
        return c.get("removable_basics", 0) > 0
    if name == "tea_master":
        return c["gold"] >= 150
    if name == "the_future_of_potions":
        return c.get("potion_count", 0) >= 2
    if name == "the_legends_were_true":
        return c["transformable_cards"] > 0 and c.get("hp", 0) >= 10
    return True
