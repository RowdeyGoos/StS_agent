"""Relic selections reuse owned offered cards and the shared choice continuation."""

from game.headless.cards.colorless_effects import pool, create
from game.headless.core.choices import begin


def offer(p, relic, *, colorless):
    choices = pool(p, "colorless" if colorless else "ironclad")
    p.deck.generation_rng.shuffle(choices)
    cards = [create(p, d, destination="offered") for d in choices[:3]]
    begin(p, relic["instance_id"], cards, minimum=0, maximum=1)
