"""Run-owned relic records copied into combat, without callbacks or run aliases."""

from copy import deepcopy
from dataclasses import asdict, replace

from game.headless.relics.base import RELICS


def owned(p, name):
    return next((r for r in p.rules.relics if r["definition_id"] == name and not r.get("data", {}).get("_melted")), None)


def memory(p, relic):
    return p.rules.relic_data.setdefault(relic["instance_id"], {})


def has(p, name):
    return owned(p, name) is not None


def increment(relic, threshold):
    relic["counter"] = (relic["counter"] + 1) % threshold
    return relic["counter"] == 0


def install(p, relics, *, room_kind="combat", hp=None, potion_capacity=3, potion_slots=3):
    p.rules.relics = [asdict(r) for r in relics]
    p.rules.relic_data = {r.instance_id: {} for r in relics}
    p.rules.room_kind = room_kind
    p.rules.potion_capacity = potion_capacity
    p.rules.potion_slots = potion_slots
    if hp is not None:
        p.hp = hp
    from game.headless.relics.turns import enter_combat

    enter_combat(p)


def synchronize(state, p):
    records = {r["instance_id"]: r for r in p.rules.relics}
    if set(records) != {r.instance_id for r in state.relics}:
        raise ValueError("Combat relic ownership differs from the run.")
    state.relics[:] = [
        replace(r, counter=records[r.instance_id]["counter"], data=deepcopy(records[r.instance_id]["data"]))
        for r in state.relics
    ]


def tasks(p, event, identity=""):
    return [["relic_hook", r["instance_id"], event, identity] for r in p.rules.relics if not r.get("data", {}).get("_melted")]


def execute(p, instance_id, event, identity):
    relic = next(r for r in p.rules.relics if r["instance_id"] == instance_id)
    if not p.is_alive or relic.get("data", {}).get("_melted"):
        return
    from game.headless.relics.event_content import hook as event_hook
    event_hook(p, relic, event, identity)
    if event in ("before_draw", "after_draw", "before_end", "after_end", "after_side_start"):
        from game.headless.relics.turns import hook
    else:
        from game.headless.relics.plays import hook
    hook(p, relic, event, identity)


def heal(p, amount):
    if p.is_alive:
        p.hp = min(p.max_hp, p.hp + max(0, amount))
        from game.headless.relics.damage import hp_changed

        hp_changed(p)


def validate(records, data, card_ids=()):
    if not isinstance(records, list) or not isinstance(data, dict):
        raise ValueError("Invalid combat relic inventory.")
    ids = []
    for record in records:
        if not isinstance(record, dict) or set(record) != {"definition_id", "instance_id", "counter", "data"}:
            raise ValueError("Invalid combat relic record.")
        name, identity, counter = record["definition_id"], record["instance_id"], record["counter"]
        if not isinstance(name, str) or name not in RELICS or not isinstance(identity, str) or not identity:
            raise ValueError("Unknown combat relic.")
        definition = RELICS[name]
        maximum = max(definition.counter_limit, definition.evolve_after_elites - 1)
        if type(counter) is not int or not 0 <= counter <= maximum:
            raise ValueError("Invalid persistent relic counter.")
        validate_data(name, record["data"])
        ids.append(identity)
        values = data.get(identity)
        schema = MEMORY_FIELDS.get(name, {})
        required = {k for k in schema if k.startswith("turn_")} if not record.get("data", {}).get("_melted") else set()
        if name == "rainbow_ring" and not record.get("data", {}).get("_melted"):
            required.add("rainbow_triggered")
        if name == "demon_tongue" and not record.get("data", {}).get("_melted"):
            required.add("demon_triggered")
        if not isinstance(values, dict) or not required <= set(values) <= set(schema):
            raise ValueError("Invalid transient relic memory fields.")
        for key, value in values.items():
            kind = schema[key]
            if kind == "card":
                valid = isinstance(value, str) and value in card_ids
            elif kind == "bool":
                valid = type(value) is bool
            else:
                valid = type(value) is int and 0 <= value <= kind
            if not valid:
                raise ValueError("Invalid transient relic memory value.")
    if len(set(ids)) != len(ids) or set(data) != set(ids):
        raise ValueError("Unowned or duplicate combat relic state.")


# Only state actually owned by a relic can cross the snapshot boundary.
from game.headless.relics.ancient_content import MEMORY

MEMORY_FIELDS = {
    "history_course": {"last_card": "card", "last_turn": 2**31-1, "replay": "card"},
    **MEMORY,
    **{n: {"turn_attacks": 2**31 - 1} for n in ("kunai", "kusarigama", "ornamental_fan", "shuriken")},
    **{n: {"used": "bool"} for n in ("ruined_helmet", "centennial_puzzle", "permafrost", "burning_sticks")},
    "letter_opener": {"turn_skills": 2**31 - 1},
    "rainbow_ring": {
        "turn_attacks": 2**31 - 1,
        "turn_skills": 2**31 - 1,
        "turn_powers": 2**31 - 1,
        "rainbow_triggered": "bool",
    },
    "beating_remnant": {"turn_damage": 2**31 - 1},
    "demon_tongue": {"demon_triggered": "bool"},
    "self_forming_clay": {"next_block": 2**31 - 1},
    "red_skull": {"strength_applied": "bool"},
    "belt_buckle": {"dexterity_applied": "bool"},
    "bronze_scales": {"thorns": 3},
    "lava_lamp": {"damaged": "bool"},
    "pen_nib": {"attack_to_double": "card"},
    "vambrace": {"triggering_card": "card", "used": "bool"},
    "unsettling_lamp": {"triggering_card": "card", "used": "bool"},
    "orichalcum": {"orichalcum_ready": "bool"},
    "fake_orichalcum": {"orichalcum_ready": "bool"},
    "reptile_trinket": {"temporary_strength": 2**31 - 1},
    "joss_paper": {"ethereal_exhausts": 2**31 - 1},
}

COMBAT_RELICS = frozenset(
    (
        "akabeko",
        "anchor",
        "art_of_war",
        "bag_of_marbles",
        "bag_of_preparation",
        "beating_remnant",
        "bellows",
        "belt_buckle",
        "blood_vial",
        "bread",
        "brimstone",
        "bronze_scales",
        "burning_sticks",
        "candelabra",
        "captains_wheel",
        "centennial_puzzle",
        "chandelier",
        "charons_ashes",
        "chemical_x",
        "cloak_clasp",
        "demon_tongue",
        "festive_popper",
        "gambling_chip",
        "game_piece",
        "ghost_seed",
        "girya",
        "gorget",
        "gremlin_horn",
        "happy_flower",
        "horn_cleat",
        "ice_cream",
        "intimidating_helmet",
        "joss_paper",
        "kunai",
        "kusarigama",
        "lantern",
        "lava_lamp",
        "letter_opener",
        "lizard_tail",
        "mercury_hourglass",
        "miniature_cannon",
        "mummified_hand",
        "mystic_lighter",
        "nunchaku",
        "oddly_smooth_stone",
        "orichalcum",
        "ornamental_fan",
        "paper_phrog",
        "parrying_shield",
        "pen_nib",
        "pendulum",
        "permafrost",
        "pocketwatch",
        "rainbow_ring",
        "razor_tooth",
        "red_mask",
        "red_skull",
        "reptile_trinket",
        "ringing_triangle",
        "ripple_basin",
        "ruined_helmet",
        "screaming_flagon",
        "self_forming_clay",
        "shuriken",
        "sling_of_courage",
        "sparkling_rouge",
        "stone_calendar",
        "stone_cracker",
        "strike_dummy",
        "sturdy_clamp",
        "the_abacus",
        "toolbox",
        "tungsten_rod",
        "tuning_fork",
        "unceasing_top",
        "unsettling_lamp",
        "vajra",
        "vambrace",
        "venerable_tea_set",
        "very_hot_cocoa",
        "vexing_puzzlebox",
    )
)


def gain_gold(p, amount):
    if has(p, "ectoplasm"):
        return
    if has(p, "bowler_hat"):
        amount = amount * 5 // 4
    p.rules.gold_gained += amount
    if amount and has(p, "dragon_fruit"):
        p.max_hp += 1
        p.rules.max_hp_gained += 1
        heal(p, 1)


def validate_data(name, data):
    from game.headless.relics.ancient_state import validate_data as ancient_validate
    data = ancient_validate(name, data)
    expected = {"treasures"} if name == "silver_crucible" else set()
    if (
        not isinstance(data, dict)
        or set(data) != expected
        or any(type(v) is not int or v < 0 for v in data.values())
    ):
        raise ValueError("Invalid persistent relic data.")
