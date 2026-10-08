"""Ephemeral, visible combat reveals and hypothetical conditional proposals.

The recording owner observes only cards leaving the hidden draw order, visible
generated offers, and displayed random costs. It never records a seed, a random
number, an instance identity, or the remaining draw order. Recording is passive;
conditioning is used exclusively on newly constructed hypothetical engines.
Neither owner is a snapshot field or a game rule.
"""
from contextlib import contextmanager
from copy import deepcopy
from math import log
from random import Random

from game.headless.draw_knowledge import InconsistentKnowledge


class CombatReveals:
    def __init__(self, expected=None, *, seed=0):
        self.expected = None if expected is None else validate_reveals(expected)
        self.events = []
        self.log_likelihood = 0.
        self.rng = Random(seed)

    def _next(self, kind, value):
        if len(self.events) >= 4096:
            raise ValueError('Combat reveal journal capacity exceeded')
        if self.expected is not None:
            index = len(self.events)
            if index >= len(self.expected) or self.expected[index]['kind'] != kind:
                raise InconsistentKnowledge('Unexpected combat reveal')
            value = self.expected[index]['value']
        self.events.append(dict(kind=kind, value=deepcopy(value)))
        return value

    def card(self, card, kind):
        actual = [card.definition.definition_id, card.upgrade_level]
        if self._next(kind, actual) != actual:
            raise InconsistentKnowledge('Revealed card differs')

    def generated(self, options, selected, *, distinct):
        names = [d.definition_id for d in selected]
        wanted = self._next('generated_cards', names)
        pool = {d.definition_id: d for d in options}
        if len(wanted) != len(selected):
            raise InconsistentKnowledge('Generated count differs')
        result = []
        for name in wanted:
            if name not in pool:
                raise InconsistentKnowledge('Generated card is ineligible')
            self.log_likelihood -= log(len(pool))
            result.append(pool[name])
            if distinct:
                del pool[name]
        return result

    def cost(self, actual, visible):
        # A displayed zero under Corruption does not reveal the hidden setter.
        # Sum the probability of every raw roll with that same public result.
        wanted = self._next('random_cost', visible[actual])
        eligible = [i for i, value in enumerate(visible) if value == wanted]
        if not eligible:
            raise InconsistentKnowledge('Displayed random cost is impossible')
        self.log_likelihood += log(len(eligible) / len(visible))
        return actual if self.expected is None else self.rng.choice(eligible)

    def potion(self, actual, probabilities):
        wanted = self._next('generated_potion', actual)
        probability = probabilities.get(wanted, 0.)
        if probability <= 0:
            raise InconsistentKnowledge('Generated potion is ineligible')
        self.log_likelihood += log(probability)
        return wanted

    def finish(self):
        if self.expected is not None and len(self.events) != len(self.expected):
            raise InconsistentKnowledge('Missing combat reveals')


def validate_reveals(events):
    if not isinstance(events, (list, tuple)) or len(events) > 4096:
        raise ValueError('Invalid combat reveal journal')
    for event in events:
        if not isinstance(event, dict) or set(event) != {'kind', 'value'}:
            raise ValueError('Invalid combat reveal')
        kind, value = event['kind'], event['value']
        if kind in ('draw', 'autoplay_top'):
            valid = (isinstance(value, (list, tuple)) and len(value) == 2 and
                     type(value[0]) is str and bool(value[0]) and type(value[1]) is int and value[1] >= 0)
        elif kind == 'generated_cards':
            valid = isinstance(value, (list, tuple)) and len(value) <= 128 and all(type(n) is str and n for n in value)
        elif kind == 'random_cost':
            valid = type(value) is int and 0 <= value < 2**31
        elif kind == 'generated_potion':
            valid = type(value) is str and bool(value)
        else:
            valid = False
        if not valid:
            raise ValueError('Invalid combat reveal value')
    return [dict(kind=e['kind'], value=list(e['value']) if isinstance(e['value'], (list, tuple))
                 else e['value']) for e in events]


@contextmanager
def combat_reveals(combat, journal=None):
    """Attach a bounded observer for exactly one synchronous combat command."""
    journal = CombatReveals() if journal is None else journal
    if combat is None:
        yield journal
        return
    deck = combat.player.deck
    owners = (deck, deck.generation_rng, deck.energy_rng, deck.potion_rng)
    # Fixture streams can alias; never install twice on one owner.
    with reveal_owners(owners, journal):
        yield journal


@contextmanager
def reveal_owners(owners, journal):
    unique = {id(owner): owner for owner in owners}.values()
    if any(hasattr(owner, 'combat_reveals') for owner in unique):
        raise ValueError('A combat reveal observer already owns this command')
    try:
        for owner in unique:
            owner.combat_reveals = journal
        yield journal
    finally:
        for owner in unique:
            del owner.combat_reveals


@contextmanager
def run_reveals(run, journal=None):
    """Observe an existing combat or a combat created by this run command."""
    journal = CombatReveals() if journal is None else journal
    if run.combat is not None:
        with combat_reveals(run.combat, journal):
            yield journal
        return
    if hasattr(run, '_combat_reveals'):
        raise ValueError('A run reveal observer already owns this command')
    run._combat_reveals = journal
    try:
        yield journal
    finally:
        del run._combat_reveals


def observe_random_cost(card, deck, setter, maximum=4):
    """Observe the displayed result after the ordinary cost setter has run.

    The setter's four possibilities are evaluated through the existing cost
    rule. Recording preserves the actual roll; a hypothetical proposal samples
    uniformly within the observed equivalence class, using its own randomness.
    """
    journal = getattr(deck.energy_rng, 'combat_reveals', None)
    if journal is None or deck.owner is None:
        return
    from game.headless.powers.ironclad import card_cost
    state, attribute = card.combat_state, setter + '_cost_override'
    actual = getattr(state, attribute)
    visible = []
    try:
        for value in range(maximum):
            setattr(state, attribute, value)
            visible.append(card_cost(deck.owner, card))
    finally:
        setattr(state, attribute, actual)
    setattr(state, attribute, journal.cost(actual, visible))
