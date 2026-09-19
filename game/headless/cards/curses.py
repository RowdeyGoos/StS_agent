"""Curse catalog, modifier eligibility, and explicit hand effects."""

from game.headless.cards.base import CardDefinition, CardSpec

MODIFIER_CURSES = (
    "clumsy",
    "debt",
    "decay",
    "doubt",
    "guilty",
    "injury",
    "normality",
    "regret",
    "shame",
    "writhe",
)
DEFINITIONS = tuple(
    CardDefinition(
        name,
        (CardSpec(name.replace("_", " ").title(), -1, "curse", uses_target=False, innate=name == "writhe"),),
        (),
        rarity="curse",
        pool="curse",
    )
    for name in ("debt", "decay", "doubt", "normality", "regret", "shame", "writhe")
)

SPECIAL_CURSES = ("ascenders_bane", "bad_luck", "curse_of_the_bell", "enthralled", "folly")
ALL_CURSES = (*MODIFIER_CURSES, *SPECIAL_CURSES, "greed", "poor_sleep", "spore_mind")
DEFINITIONS += tuple(
    CardDefinition(
        name,
        (
            CardSpec(
                name.replace("_", " ").title(),
                2 if name == "enthralled" else -1,
                "curse",
                uses_target=False,
                eternal=True,
                innate=name == "folly",
                ethereal=name in ("ascenders_bane", "folly"),
            ),
        ),
        (),
        rarity="curse",
        pool="curse",
    )
    for name in SPECIAL_CURSES
)
END_HAND_CURSES = ("debt", "decay", "doubt", "regret", "shame", "bad_luck")


def can_play(player, card=None, *, auto=False):
    from game.headless.relics.combat import owned, memory
    choker = owned(player, "velvet_choker")
    if choker and memory(player, choker).get("turn_plays", 0) >= 6:
        return False
    from game.headless.powers.silent import can_play as silent_can_play
    if card is not None and not silent_can_play(player, card):
        return False
    if card is not None and card.definition.definition_id == 'high_five':
        from game.headless.core.osty import alive
        if not alive(player):
            return False
    held = {c.definition.definition_id for c in player.hand}
    return (player.cards_played_this_turn < 3 or "normality" not in held) and (
        auto
        or "enthralled" not in held
        or (card is not None and card.definition.definition_id == "enthralled")
    )


def end_in_hand(player, card):
    if card not in player.hand or player.combat_is_ending:
        return
    name = card.definition.definition_id
    if name == "debt":
        r = player.rules
        r.gold_lost += min(10, max(0, r.gold_available + r.gold_gained - r.gold_lost))
    elif name == "decay":
        player.take_damage(2, is_attack=False)
    elif name == "bad_luck":
        player.lose_hp(13)
    elif name == "regret":
        player.lose_hp(player.rules.end_turn_hand_size)
    elif name in ("doubt", "shame"):
        if player.statuses.get("artifact"):
            player.statuses.decrement("artifact")
        else:
            player.apply_status("weak" if name == "doubt" else "frail", 1)
    elif card.spec.end_turn_damage:
        player.take_damage(card.spec.end_turn_damage, is_attack=False)
    elif card.spec.end_turn_hp_loss:
        from game.headless.powers.damage import resolve_unblocked_damage
        player.lose_hp(resolve_unblocked_damage(player.statuses, card.spec.end_turn_hp_loss))
