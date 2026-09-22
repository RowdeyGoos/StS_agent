"""Explicit discards have history and Sly; ordinary pile movement does not."""

from game.headless.core.resolution import push, move_out


def discard_and_draw(player, cards, *, draw=0):
    from game.headless.powers.silent import is_sly
    # CardCmd.DiscardAndDraw captures the selected order and Sly eligibility,
    # completes the discard hooks, draws, then autoplays the captured cards.
    cards = tuple(cards)
    sly = [c.instance_id for c in cards if is_sly(c)]
    from game.headless.relics.combat import tasks
    hooks = []
    for card in cards:
        move_out(player, card)
        player.deck.discard_card(card)
        player.rules.discarded_turn += 1
        hooks.extend(tasks(player, "discard", card.instance_id))
    push(player, *hooks, ['draw', draw, False], *[['autoplay', identity, False] for identity in sly])
