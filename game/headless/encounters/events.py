"""Native event encounters, excluded from ordinary map encounter queues."""

from game.headless.monsters.phrog_parasite import Wriggler


def dense_vegetation(rng):
    return [Wriggler(rng, starts_with_wriggle=index % 2 == 1, start_stunned=False)
            for index in range(4)]
