"""Pinned relic acquisition predicates; pool membership is a separate concern."""

# RelicModel.IsBeforeAct3TreasureChest and its 17 overrides (0.107.1).
BEFORE_ACT3_CHEST = frozenset(
    (
        "amethyst_aubergine",
        "book_of_five_rings",
        "bowler_hat",
        "dragon_fruit",
        "frozen_egg",
        "girya",
        "juzu_bracelet",
        "lasting_candy",
        "lucky_fysh",
        "meal_ticket",
        "molten_egg",
        "old_coin",
        "planisphere",
        "shovel",
        "toxic_egg",
        "white_beast_statue",
        "white_star",
    )
)
SHOP_EXCLUDED = frozenset(
    (
        "amethyst_aubergine",
        "bowler_hat",
        "lucky_fysh",
        "old_coin",
        "the_courier",
    )
)


def is_allowed(name, *, total_floor, prior_runs=9999, character="ironclad", player_count=1):
    """Evaluate explicit inputs, without RNG, inventory mutation or save access.

    Defaults mirror UnlockState.all and the supported solo character. Boundary
    inputs are useful for native conformance; they do not enable later-act play.
    """
    if name in BEFORE_ACT3_CHEST and total_floor >= (41 if player_count == 1 else 38):
        return False
    if name == "lasting_candy" and character == "ironclad" and prior_runs == 0:
        return False
    if name == "massive_scroll":
        return player_count > 1
    if name in ("silver_crucible", "winged_boots"):
        return player_count == 1
    return True


def allowed_in_run(state, name):
    # The only generated profile is solo Ironclad, all unlocked/all seen.
    # Act 1's entered nodes are below the floor-41 cutoff; startup is floor zero.
    from game.headless.characters import character
    return is_allowed(name, total_floor=state.visited_room_count, character=character(state))
