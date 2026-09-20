"""Ordered persistent hooks at a victorious combat boundary."""

from dataclasses import replace

from game.headless.relics.base import RELICS
from game.headless.run.inventory import add_relic, remove_relic


def after_combat(state, *, won, elite, cards=None, improvement=0, selection_rng=None, room_kind=None):
    # Native pending loss emits CombatEnded without either gameplay hook pass.
    if not won:
        return
    for card in tuple(state.deck):
        if card.definition.combat_lifetime:
            card.combats_seen += 1
            if card.combats_seen >= card.definition.combat_lifetime:
                state.deck.remove(card)
    # Run-deck hooks precede combat powers, which precede relic inventory hooks.
    choices = [c for c in state.deck if c.upgrade_level + 1 < len(c.definition.levels)]
    for _ in range(min(len(choices), improvement)):
        card = selection_rng.choice(choices)
        choices.remove(card)
        card.upgrade()
    from game.headless.relics import ancient_state, run_rules
    if cards is None:
        from game.headless.cards.catalog import DEFAULT_CARDS
        cards = DEFAULT_CARDS
    kind = room_kind or ('elite' if elite else 'combat')
    # Capture eligibility once. Toy Box may melt a later listener, but that
    # listener still receives this pass; the fresh victory pass excludes it.
    listeners = tuple(r for r in state.relics if not r.data.get('_melted'))
    for relic in listeners:
        run_rules.after_combat_relic(state, relic, room_kind=kind)
        ancient_state.after_combat(state, cards, relics=(relic,))
    run_rules.victory(state, room_kind=kind)


def evolve_relic(state, relic):
    definition = RELICS[relic.definition_id]
    if not definition.evolve_after_elites:
        return
    counter = relic.counter + 1
    index = state.relics.index(relic)
    if counter < definition.evolve_after_elites:
        state.relics[index] = replace(relic, counter=counter)
    else:
        remove_relic(state, relic.instance_id)
        upgraded = add_relic(state, definition.evolves_into)
        state.relics.remove(upgraded)
        state.relics.insert(index, upgraded)
