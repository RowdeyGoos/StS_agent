"""Combat card factory rules; selected definitions have no mutable instance state."""


def card_pool(catalog, family="ironclad", kind=None):
    # "block" is the legacy representation of a native Skill such as Shrug It Off.
    kinds = ("skill", "block") if kind == "skill" else (kind,)
    return sorted(
        (
            definition
            for definition in catalog.definitions
            if definition.pool == family
            and definition.rarity in ("common", "uncommon", "rare")
            and definition.generate_in_combat
            and (kind is None or definition.levels[0].kind in kinds)
        ),
        key=lambda definition: definition.definition_id,
    )


def select_cards(options, rng, count, *, distinct):
    """Native GetDistinctForCombat shuffles the full pool; GetForCombat replaces.

    NativeRng.sample owns the full-pool shuffle, including count zero. The fixture
    Random adapter retains its original sampling. Neither factory rolls rarity or
    upgrades; those belong to the caller.
    """
    options = list(dict.fromkeys(options))
    if distinct:
        return rng.sample(options, min(count, len(options)))
    if count and not options:
        raise ValueError("No eligible combat generation content.")
    return [rng.choice(options) for _ in range(count)]
