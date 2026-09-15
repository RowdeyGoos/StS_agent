"""Pile command hooks shared by draws, potions and generated card choices."""

from game.headless.core.native_rng import NativeRng


def stratagem_cards(player):
    cards = list(player.deck.draw_pile)
    if isinstance(player.deck.rng, NativeRng):
        # Native grid orders by rarity/model ID; ties retain top-first pile order.
        cards.reverse()
        rarity = {
            "basic": 1,
            "common": 2,
            "uncommon": 3,
            "rare": 4,
            "ancient": 5,
            "event": 6,
            "token": 7,
            "status": 8,
            "curse": 9,
            "quest": 10,
        }
        cards.sort(key=lambda c: (rarity.get(c.definition.rarity, 0), c.definition.definition_id))
    return cards


def shuffle(player, *, include_hand=False):
    from game.headless.core.resolution import push
    from game.headless.relics.combat import tasks

    player.deck.shuffle_piles(include_hand=include_hand)
    # Native listeners visit creature powers before that player's relics.
    choice = [["shuffle_choice"]] if player.rules.powers.get("stratagem") else []
    push(player, *choice, *tasks(player, "shuffle"))


def choose_after_shuffle(player):
    from game.headless.core.choices import begin

    count = player.rules.powers.get("stratagem", 0)
    if count and not player.combat_is_ending:
        cards = stratagem_cards(player)
        if count >= len(cards) and isinstance(player.deck.rng, NativeRng):
            # FromCombatPile bypasses the selector sort when every card is taken.
            cards = list(reversed(player.deck.draw_pile))
        begin(player, "stratagem", cards, minimum=count, maximum=count)


def after_generated_entry(player, card, *, is_clone=False):
    # Offered cards are not hook listeners. Apply entry effects only when the
    # fresh instance enters a combat pile; ordinary pile moves/clones skip this.
    from game.headless.powers.silent import entered
    entered(player, card, is_clone=is_clone)
    if not is_clone and card.definition.definition_id == "stomp":
        card.combat_state.cost_change -= player.rules.attacks_finished
