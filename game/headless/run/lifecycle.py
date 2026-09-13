"""Persistent card expiry and relic progression at completed combat boundaries."""

from dataclasses import replace

from game.headless.relics.base import RELICS
from game.headless.run.inventory import add_relic, remove_relic


def after_combat(state, *, won, elite):
    for card in tuple(state.deck):
        if card.definition.combat_lifetime:
            card.combats_seen += 1
            if card.combats_seen >= card.definition.combat_lifetime:
                state.deck.remove(card)
    if won and elite:
        for relic in tuple(state.relics):
            definition = RELICS[relic.definition_id]
            if not definition.evolve_after_elites:
                continue
            counter = relic.counter + 1
            index = state.relics.index(relic)
            if counter < definition.evolve_after_elites:
                state.relics[index] = replace(relic, counter=counter)
            else:
                remove_relic(state, relic.instance_id)
                upgraded = add_relic(state, definition.evolves_into)
                state.relics.remove(upgraded)
                state.relics.insert(index, upgraded)
