"""Plain entry conditions retained for replaying native event eligibility."""


def entry_conditions(state):
    from game.headless.relics.base import RELICS
    pet = any(RELICS[r.definition_id].adds_pet for r in state.relics) or any(c.definition.definition_id == "byrdonis_egg" for c in state.deck)
    return {"hp": state.hp, "max_hp": state.max_hp, "potion_count": sum(p is not None for p in state.potions),
            "removable_basics": sum(c.definition.rarity == "basic" and not c.spec.eternal for c in state.deck),
            "available_relics": any(r not in {v.definition_id for v in state.relics} for r in state.config.reward_relics) if state.config else True,
            "event_pet": pet, "gold": state.gold, "transformable_cards": sum(not c.spec.eternal for c in state.deck), "floor": len(state.visited_nodes) + 1}


def validate_conditions(conditions):
    if (not isinstance(conditions, dict) or set(conditions) - {"event_pet", "hp", "max_hp", "potion_count", "removable_basics", "available_relics"} not in ({"gold", "transformable_cards"}, {"gold", "transformable_cards", "floor"})
            or any(type(v) is not int or v < 0 for k,v in conditions.items() if k not in ("event_pet", "available_relics"))
            or any(k in conditions and type(conditions[k]) is not bool for k in ("event_pet", "available_relics"))):
        raise ValueError("Invalid event entry conditions.")


def is_allowed(definition, conditions):
    validate_conditions(conditions)
    predicate = getattr(definition, "is_allowed", None)
    return True if predicate is None else predicate(conditions)
