"""Validate colorless power instances and owned selection records."""

from game.headless.powers.colorless import NAMES, INSTANCED, name
from game.headless.powers.ironclad import POWER_NAMES


def valid_power(key, sequence):
    if not isinstance(key, str):
        return False
    from game.headless.potions.powers import NAMES as POTION_POWERS
    from game.headless.powers.silent import NAMES as SILENT_POWERS
    from game.headless.powers.regent import NAMES as REGENT_POWERS, INSTANCED as REGENT_INSTANCED
    from game.headless.powers.necrobinder import NAMES as NECRO_POWERS
    from game.headless.powers.defect import NAMES as DEFECT_POWERS
    if key in DEFECT_POWERS:
        return True
    if key in NECRO_POWERS:
        return True
    if key in REGENT_POWERS - REGENT_INSTANCED:
        return True
    if key in POWER_NAMES or key in NAMES - INSTANCED or key in POTION_POWERS or key in SILENT_POWERS:
        return True
    parts = key.split(":")
    return (
        len(parts) == 2
        and parts[0] in INSTANCED | REGENT_INSTANCED | {"nightmare"}
        and parts[1].isdigit()
        and str(int(parts[1])) == parts[1]
        and int(parts[1]) < sequence
    )


def validate_selection(r, p, *, deferred=False, shared_offers=False):
    from game.headless.potions.base import POTIONS

    if (
        r.potion_slots > r.potion_capacity
        or not isinstance(r.potion_pool, list)
        or not r.potion_pool
        or any(x not in POTIONS for x in r.potion_pool)
        or len(r.potion_pool) != len(set(r.potion_pool))
        or not isinstance(r.potions_generated, list)
        or len(r.potions_generated) + r.potion_slots > r.potion_capacity
        or any(x not in r.potion_pool and x != "potion_shaped_rock" for x in r.potions_generated)
    ):
        raise ValueError("Invalid combat potion state.")
    expected_aux = {"crimson_mantle", "inferno", "block_gains"}
    if "summon_next_turn" in r.powers:
        expected_aux.add("summon_next_turn")
    if "feral" in r.powers:
        expected_aux.add("feral")
    if "outbreak" in r.powers:
        expected_aux.add("outbreak")
    for key in r.powers:
        if key.startswith(("monologue:", "orbit:")) or key == "void_form":
            expected_aux.add(key)
        if name(key) in ("automation", "panache", "the_bomb", "toric_toughness"):
            expected_aux.add(key)
        if name(key) == "panache":
            expected_aux.add(key + ".ready")
    if set(r.auxiliaries) - expected_aux:
        raise ValueError("Unowned auxiliary power counter.")
    for key in r.powers:
        kind = name(key)
        if kind in ("automation", "panache", "the_bomb"):
            maximum = {"automation": 10, "panache": 5, "the_bomb": 3}[kind]
            if key not in r.auxiliaries or not 1 <= r.auxiliaries[key] <= maximum:
                raise ValueError("Invalid power timer.")
        if kind == "toric_toughness" and (key not in r.auxiliaries or not 1 <= r.powers[key] <= 2):
            raise ValueError("Invalid Toric Toughness instance.")
        if kind == "panache" and r.auxiliaries.get(key + ".ready") not in (0, 1):
            raise ValueError("Invalid Panache activation.")
    s = r.selection
    if s is None:
        if p.deck.offered and not shared_offers:
            raise ValueError("Unowned offered cards.")
        return
    fields = {"source", "candidates", "selected", "operation", "destination", "minimum", "maximum", "free"}
    if not isinstance(s, dict) or set(s) - {"whitelist"} != fields:
        raise ValueError("Invalid selection fields.")
    from game.headless.core.necrobinder_snapshots import CHOICES as NECRO_CHOICES, validate_selection as nec_selection
    from game.headless.core.regent_snapshots import CHOICES as REGENT_CHOICES, validate_selection as regent_selection
    if (
        s["operation"] not in NECRO_CHOICES and s["operation"] not in REGENT_CHOICES and s["operation"] not in ("move", "transform", "exhaust", "discard_redraw", "free_combat", "discard", "hand_trick", "nightmare", "well_laid_plans")
        or s["destination"] not in ("hand", "draw_pile")
        or s["free"] not in ("", "free_this_turn", "free_until_played")
        or any(type(s[k]) is not int for k in ("minimum", "maximum"))
    ):
        raise ValueError("Invalid selection operation.")
    for field in ("candidates", "selected"):
        if (
            not isinstance(s[field], list)
            or any(not isinstance(i, str) for i in s[field])
            or len(s[field]) != len(set(s[field]))
        ):
            raise ValueError("Invalid selected identities.")
    if (
        not 0 <= s["minimum"] <= s["maximum"] <= len(s["candidates"])
        or not s["maximum"]
        or len(s["selected"]) > s["maximum"]
        or not set(s["selected"]) <= set(s["candidates"])
    ):
        raise ValueError("Invalid selection bounds.")
    if s["operation"] in NECRO_CHOICES:
        nec_selection(r, p, s, deferred=deferred)
        return
    if s["operation"] in REGENT_CHOICES:
        regent_selection(r, p, s, deferred=deferred)
        return
    from game.headless.core.silent_snapshots import CHOICES, validate_selection as silent_selection
    if s["operation"] in CHOICES:
        silent_selection(r, p, s, deferred=deferred)
        return
    if s["source"] in r.potion_uses:
        if "whitelist" in s:
            raise ValueError("Potion choice cannot own a sampled card filter.")
        from game.headless.potions.selections import validate
        validate(r, p, s, r.potion_uses[s["source"]]["definition_id"])
        return
    source = next((c for c in p.deck.in_play if c.instance_id == s["source"]), None)
    if source is None:
        relic = next((v for v in r.relics if v["instance_id"] == s["source"]), None)
        if relic is not None:
            operation = relic["definition_id"]
            if operation not in ("gambling_chip", "toolbox") or r.round_number != 1:
                raise ValueError("Invalid relic selection source.")
        else:
            if s["source"] not in ("entropy", "stratagem") or not r.powers.get(s["source"]):
                raise ValueError("Unowned selection source.")
            operation = s["source"]
    else:
        frame = r.plays.get(source.instance_id)
        index = frame.get("effect_index") if isinstance(frame, dict) else None
        if type(index) is not int or not 0 <= index < len(source.definition.effects):
            raise ValueError("Invalid selection effect.")
        operation = getattr(source.definition.effects[index], "operation", None)
    settings = {
        "gambling_chip": ("hand", "discard_redraw", "hand", ""),
        "toolbox": ("offered", "move", "hand", ""),
        "entropy": ("hand", "transform", "hand", ""),
        "stratagem": ("draw_pile", "move", "hand", ""),
        "purity": ("hand", "exhaust", "hand", ""),
        "thinking_ahead": ("hand", "move", "draw_pile", ""),
        "secret_technique": ("draw_pile", "move", "hand", ""),
        "secret_weapon": ("draw_pile", "move", "hand", ""),
        "seeker_strike": ("draw_pile", "move", "hand", ""),
        "discovery": ("offered", "move", "hand", "free_until_played"),
        "splash": ("offered", "move", "hand", "free_this_turn"),
    }
    if operation not in settings:
        raise ValueError("Unsupported choice source.")
    pile, effect, destination, free = settings[operation]
    if (s["operation"], s["destination"], s["free"]) != (effect, destination, free):
        raise ValueError("Choice semantics differ from source.")
    whitelist = s.get("whitelist")
    if operation == "seeker_strike":
        if (not isinstance(whitelist, list) or not 1 <= len(whitelist) <= 3
                or any(not isinstance(i, str) for i in whitelist)
                or len(whitelist) != len(set(whitelist))
                or not set(whitelist) <= p.deck._allocated_ids
                or source.instance_id in whitelist
                or not set(s["candidates"]) <= set(whitelist)):
            raise ValueError("Invalid sampled tutor whitelist.")
    elif "whitelist" in s:
        raise ValueError("Choice source does not own a sampled filter.")
    available = getattr(p.deck, pile)
    deferred_live = deferred and operation in ("stratagem", "seeker_strike")
    if deferred_live:
        if not set(s["candidates"]) <= p.deck._allocated_ids or s["selected"]:
            raise ValueError("Invalid deferred live selection.")
    elif not set(s["candidates"]) <= {c.instance_id for c in available}:
        raise ValueError("Selection references a foreign pile.")
    candidates = [c.instance_id for c in available]
    if operation in ("secret_technique", "secret_weapon"):
        kinds = ("skill", "block") if operation == "secret_technique" else ("attack",)
        candidates = [c.instance_id for c in available if c.spec.kind in kinds]
    if operation in ("stratagem", "seeker_strike"):
        from game.headless.core.piles import stratagem_cards
        candidates = [c.instance_id for c in stratagem_cards(p)
                      if whitelist is None or c.instance_id in whitelist]
    if not deferred_live and s["candidates"] != candidates:
        raise ValueError("Selection differs from eligible cards.")
    expected_max = (
        len(s["candidates"]) if operation == "gambling_chip" else
        r.powers[operation]
        if operation in ("entropy", "stratagem")
        else (5 if source.upgraded else 3) if operation == "purity" else 1
    )
    expected_max = min(expected_max, len(s["candidates"]))
    expected_min = 0 if operation in ("purity", "discovery", "splash", "gambling_chip", "toolbox") else expected_max
    if (s["minimum"], s["maximum"]) != (expected_min, expected_max):
        raise ValueError("Choice limits differ from source.")
    if operation in ("secret_technique", "secret_weapon"):
        kinds = ("skill", "block") if operation == "secret_technique" else ("attack",)
        if any(c.spec.kind not in kinds for c in available if c.instance_id in s["candidates"]):
            raise ValueError("Ineligible tutor card.")
    if pile == "offered" and not shared_offers and set(s["candidates"]) != {c.instance_id for c in p.deck.offered}:
        raise ValueError("Offer ownership mismatch.")
