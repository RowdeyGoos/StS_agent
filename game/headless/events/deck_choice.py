"""One mandatory original-card selection and its verifiable deck result."""

from game.headless.core.snapshots import card_record, restore_card


def empty():
    return {"eligible": [], "originals": [], "selected": None, "result": None}


def prepare(state, data):
    data["originals"] = [card_record(c) for c in state.deck]
    data["eligible"] = [c.instance_id for c in state.deck]


def validate(state, data, cards, *, operation, finished, extra=()):
    originals = data["originals"]
    if not isinstance(originals, list):
        raise ValueError("Invalid event original cards.")
    for record in originals:
        restore_card(record, cards)
    identities = [r["instance_id"] for r in originals]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate event original card.")
    if not finished:
        if (len(identities) < 2 or data["eligible"] != identities
                or data["selected"] is not None or data["result"] is not None
                or originals != [card_record(c) for c in state.deck]):
            raise ValueError("Invalid pending deck choice.")
        return
    selected, result = data["selected"], data["result"]
    expected = list(originals)
    if data["eligible"] != []:
        raise ValueError("Completed choice retains candidates.")
    if not originals:
        if selected is not None or result is not None:
            raise ValueError("Empty selection has a result.")
    else:
        if selected not in identities:
            raise ValueError("Selected card is not an original.")
        index = identities.index(selected)
        if operation == "remove":
            if result is not None: raise ValueError("Removal has a replacement.")
            expected.pop(index)
        else:
            from game.headless.events.transformation import TRANSFORM_POOL, replacement_pool
            restored = restore_card(result, cards)
            source = originals[index]["definition_id"]
            if (restored.instance_id in identities or restored.upgrade_level or restored.combats_seen
                    or restored.definition.definition_id == source
                    or restored.definition.definition_id not in replacement_pool(source, TRANSFORM_POOL)):
                raise ValueError("Invalid event transformation.")
            expected[index] = result
    current = [card_record(c) for c in state.deck if c.instance_id not in extra]
    if current != expected:
        raise ValueError("Event deck result differs from originals.")
