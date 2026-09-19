"""Plain entry conditions retained for replaying native event eligibility."""


def entry_conditions(state):
    from game.headless.relics.base import RELICS
    pet = any(RELICS[r.definition_id].adds_pet for r in state.relics) or any(c.definition.definition_id == "byrdonis_egg" for c in state.deck)
    from game.headless.events.social import tradable
    from game.headless.enchantments.base import can_enchant
    return {"act_index": state.act_index, "basic_strikes": sum(c.definition.strike and c.definition.rarity == "basic" and not c.spec.eternal for c in state.deck),
            "basic_defends": sum(c.definition.defend and c.definition.rarity == "basic" and not c.spec.eternal for c in state.deck),
            "tradable_relics": len(tradable(state)), "foul_potions": sum(p is not None and p.definition_id == "foul_potion" for p in state.potions),
            "lantern_keys": sum(c.definition.definition_id == "lantern_key" for c in state.deck),
            **{f"enchant_{name}": sum(can_enchant(c, name) for c in state.deck) for name in ("perfect_fit", "souls_power", "spiral")},
            "hp": state.hp, "max_hp": state.max_hp, "potion_count": sum(p is not None for p in state.potions),
            "removable_basics": sum(c.definition.rarity == "basic" and not c.spec.eternal for c in state.deck),
            "available_relics": any(r not in {v.definition_id for v in state.relics} for r in state.config.reward_relics) if state.config else True,
            "event_pet": pet, "gold": state.gold, "transformable_cards": sum(not c.spec.eternal for c in state.deck), "floor": len(state.visited_nodes) + 1}


def validate_conditions(conditions):
    if (not isinstance(conditions, dict) or set(conditions) - {"event_pet", "hp", "max_hp", "potion_count", "removable_basics", "available_relics", "act_index", "basic_strikes", "basic_defends", "tradable_relics", "foul_potions", "lantern_keys", "enchant_perfect_fit", "enchant_souls_power", "enchant_spiral"} not in ({"gold", "transformable_cards"}, {"gold", "transformable_cards", "floor"})
            or any(type(v) is not int or v < 0 for k,v in conditions.items() if k not in ("event_pet", "available_relics"))
            or any(k in conditions and type(conditions[k]) is not bool for k in ("event_pet", "available_relics"))):
        raise ValueError("Invalid event entry conditions.")


def is_allowed(definition, conditions):
    validate_conditions(conditions)
    predicate = getattr(definition, "is_allowed", None)
    return True if predicate is None else predicate(conditions)
