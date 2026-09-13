"""Plain entry conditions retained for replaying native event eligibility."""


def entry_conditions(state):
    # Implemented deck cards have no Eternal/removal restriction. New content
    # with those rules must extend this count along with transformation legality.
    from game.headless.relics.base import RELICS
    pet = any(RELICS[r.definition_id].adds_pet for r in state.relics) or any(c.definition.definition_id == "byrdonis_egg" for c in state.deck)
    return {"event_pet": pet, "gold": state.gold, "transformable_cards": len(state.deck), "floor": len(state.visited_nodes) + 1}


def validate_conditions(conditions):
    if (not isinstance(conditions, dict) or set(conditions) - {"event_pet"} not in ({"gold", "transformable_cards"}, {"gold", "transformable_cards", "floor"})
            or any(type(v) is not int or v < 0 for k,v in conditions.items() if k != "event_pet")
            or "event_pet" in conditions and type(conditions["event_pet"]) is not bool):
        raise ValueError("Invalid event entry conditions.")


def is_allowed(definition, conditions):
    validate_conditions(conditions)
    predicate = getattr(definition, "is_allowed", None)
    return True if predicate is None else predicate(conditions)
