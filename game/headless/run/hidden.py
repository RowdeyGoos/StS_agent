"""Resample a restored combat's hidden draw order and future combat randomness.

A frozen combat start otherwise replays one realization of the unknown draw
order, enemy choices, later shuffles and generated content. Resampling keeps
every public fact: hand, pile contents, enemy state, displayed intents and
counters. Cards with a position-setting enchantment conservatively keep their
positions. Each combat RNG stream keeps its owning seed and advances by ordinary
draws, so the result is a reachable state that snapshots and restores normally.
"""
from random import Random

# Imbued cards are arranged at the opening (then autoplayed); Perfect Fit returns
# to the top after a reshuffle. Pinning them never contradicts those rules.
FIXED_POSITION_ENCHANTMENTS = frozenset({'imbued', 'perfect_fit'})
MAX_STREAM_ADVANCE = 1024


def resample_hidden_combat(run, seed):
    """Replace hidden combat randomness in place; the public observation is unchanged."""
    if type(seed) is not int or seed < 0:
        raise ValueError('Hidden-state resampling requires a nonnegative integer seed.')
    combat = getattr(run, 'combat', None)
    streams = getattr(combat, 'native_streams', None)
    if combat is None or not streams:
        raise ValueError('Hidden-state resampling requires an active native combat.')
    rng = Random(seed)
    pile = combat.player.deck.draw_pile
    fixed = {i for i, card in enumerate(pile)
             if card.enchantment is not None and card.enchantment.definition_id in FIXED_POSITION_ENCHANTMENTS}
    # Canonical order first, so the result depends only on the seed, not on the
    # realization being replaced.
    free = sorted((card for i, card in enumerate(pile) if i not in fixed), key=lambda card: card.instance_id)
    rng.shuffle(free)
    remaining = iter(free)
    pile[:] = [pile[i] if i in fixed else next(remaining) for i in range(len(pile))]
    for name in sorted(streams):
        stream = streams[name]
        for _ in range(rng.randrange(1, MAX_STREAM_ADVANCE + 1)):
            stream.next_double()
