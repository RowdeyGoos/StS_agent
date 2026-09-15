"""Combat transformation pools in native declaration order, without replacement state."""

from game.headless.core.content_order import IRONCLADCARDPOOL, COLORLESSCARDPOOL, CURSECARDPOOL

# Frantic Escape and Soot are native statuses, but cannot be generated in combat.
STATUS_ORDER = ("beckon", "burn", "dazed", "debris", "frantic_escape", "infection",
                "wither", "slimed", "soot", "toxic", "void", "wound")


def combat_options(catalog, original):
    definition = original.definition
    if original.spec.kind in ("curse", "status"):
        family = original.spec.kind
    elif original.spec.kind == "quest" or definition.rarity in ("event", "ancient", "token"):
        family = "colorless"
    else:
        family = definition.pool
    order = {"ironclad": IRONCLADCARDPOOL, "colorless": COLORLESSCARDPOOL,
             "curse": CURSECARDPOOL, "status": STATUS_ORDER}.get(family)
    candidates = [d for d in catalog.definitions if d.pool == family
                  and d.generate_in_combat and d.definition_id != definition.definition_id
                  and (family in ("curse", "status") or d.rarity in ("common", "uncommon", "rare"))]
    if order is not None:
        rank = {name: index for index, name in enumerate(order)}
        candidates.sort(key=lambda d: (rank.get(d.definition_id, len(rank)), d.definition_id))
    if not candidates:
        raise ValueError("No eligible combat transformation replacement.")
    return candidates
