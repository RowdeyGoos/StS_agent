"""Explicit discards have history and Sly; ordinary pile movement does not."""

from game.headless.core.resolution import push, move_out


def discard_and_draw(player, cards, *, draw=0):
    from game.headless.powers.silent import is_sly
    # CardCmd.DiscardAndDraw captures the selected order and Sly eligibility,
    # completes the discard hooks, draws, then autoplays the captured cards.
    cards = tuple(c for c in cards if c in player.hand)
    sly = [c.instance_id for c in cards if is_sly(c)]
    for card in cards:
        move_out(player, card)
        player.deck.discard_card(card)
        player.rules.discarded_turn += 1
    push(player, ['draw', draw, False], *[['autoplay', identity, False] for identity in sly])
