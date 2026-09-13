"""Plain entry conditions retained for replaying native event eligibility."""


def entry_conditions(state):
    # Implemented deck cards have no Eternal/removal restriction. New content
    # with those rules must extend this count along with transformation legality.
    return {"gold": state.gold, "transformable_cards": len(state.deck), "floor": len(state.visited_nodes) + 1}


def validate_conditions(conditions):
    if (not isinstance(conditions, dict) or set(conditions) not in ({"gold", "transformable_cards"}, {"gold", "transformable_cards", "floor"})
            or any(type(v) is not int or v < 0 for v in conditions.values())):
        raise ValueError("Invalid event entry conditions.")


def is_allowed(definition, conditions):
    validate_conditions(conditions)
    predicate = getattr(definition, "is_allowed", None)
    return True if predicate is None else predicate(conditions)
