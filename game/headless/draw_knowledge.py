"""Conditional draws in hypothetical worlds, using the ordinary pile rules.

This optional owner belongs to a planner-created world, never to the real game.
It represents a uniform permutation of physical cards between known ends. It
does not implement card effects, infer observations, or read a gameplay seed.
The engine's normal RNG calls still run; proposals have independent randomness.
"""
from dataclasses import dataclass, field
import math
from random import Random


class InconsistentKnowledge(ValueError):
    """A proposed world cannot produce the supplied partial observation."""


def card_kind(card):
    return card.definition.definition_id, card.upgrade_level


@dataclass
class DrawKnowledge:
    # Nearest end first. These are identities in a *hypothetical* engine only.
    top: list[str] = field(default_factory=list)
    bottom: list[str] = field(default_factory=list)
    expected: list[tuple[str, int]] | None = None
    log_likelihood: float = 0.
    consumed: int = 0
    rng: Random = field(default_factory=lambda: Random(0), repr=False)

    def condition(self, draws, seed):
        self.expected = None if draws is None else list(draws)
        self.log_likelihood, self.consumed, self.rng = 0., 0, Random(seed)

    def shuffled(self, deck):
        self.top.clear()
        self.bottom.clear()

    def placed(self, card, *, bottom=False):
        identity = card.instance_id
        if identity in self.top or identity in self.bottom:
            raise InconsistentKnowledge('Repeated known placement')
        (self.bottom if bottom else self.top).insert(0, identity)

    def removed(self, card):
        for end in (self.top, self.bottom):
            if card.instance_id in end:
                end.remove(card.instance_id)

    def inserted(self, card, index, previous_size):
        """Retain known ends after this particle's sampled random insertion.

        An insertion in the unknown middle leaves a uniform unknown bag. One
        inside a constrained end becomes part of that particle's ordered end;
        different particles retain different hypotheses about the position.
        """
        if index > previous_size - len(self.top):
            self.top.insert(previous_size - index, card.instance_id)
        elif index < len(self.bottom):
            self.bottom.insert(index, card.instance_id)

    def arranged(self, *, top, bottom):
        """Track rule-owned opening arrangements, in nearest-end order."""
        moved = {card.instance_id for card in (*top, *bottom)}
        self.top = [card.instance_id for card in top] + [i for i in self.top if i not in moved]
        self.bottom = [card.instance_id for card in bottom] + [i for i in self.bottom if i not in moved]

    def _parts(self, deck):
        cards = {c.instance_id: c for c in deck.draw_pile}
        known = self.top + self.bottom
        if len(cards) != len(deck.draw_pile) or len(set(known)) != len(known) or any(i not in cards for i in known):
            raise InconsistentKnowledge('Known draw constraints differ from the pile')
        return cards, [c for c in deck.draw_pile if c.instance_id not in known]

    def materialize(self, deck):
        cards, unknown = self._parts(deck)
        # The previous sampled permutation carries no evidence. Canonicalizing
        # before shuffling also makes fixed-seed sampling independent of it.
        unknown.sort(key=lambda c: c.instance_id)
        self.rng.shuffle(unknown)
        deck.draw_pile[:] = ([cards[i] for i in self.bottom] + unknown +
                             [cards[i] for i in reversed(self.top)])

    def before_draw(self, deck):
        cards, unknown = self._parts(deck)
        known = self.top[0] if self.top else self.bottom[-1] if not unknown and self.bottom else None
        if self.expected is not None:
            if self.consumed >= len(self.expected):
                raise InconsistentKnowledge('Unobserved extra draw')
            target = self.expected[self.consumed]
            if known is not None:
                if card_kind(cards[known]) != target:
                    raise InconsistentKnowledge('Observed draw contradicts known placement')
                selected = cards[known]
            else:
                matching = [c for c in unknown if card_kind(c) == target]
                if not matching:
                    raise InconsistentKnowledge('Observed card absent from unknown draw bag')
                self.log_likelihood += math.log(len(matching) / len(unknown))
                # Preserve distinct copies and their full mutable state. The
                # caller still checks the entire successor after coarse guidance.
                selected = self.rng.choice(sorted(matching, key=lambda c: c.instance_id))
            deck.draw_pile.remove(selected)
            deck.draw_pile.append(selected)
        elif known is not None and deck.draw_pile[-1].instance_id != known:
            raise InconsistentKnowledge('Materialized pile violates known placement')
        self.consumed += 1
        if self.top:
            self.top.pop(0)
        elif not unknown and self.bottom:
            self.bottom.pop()

    def finish(self):
        if self.expected is not None and self.consumed != len(self.expected):
            raise InconsistentKnowledge('Missing observed draw')
        self.expected = None


@dataclass
class HPKnowledge:
    expected: tuple[int, ...]
    consumed: int = 0
    log_likelihood: float = 0.

    def condition(self, eligible):
        if self.consumed >= len(self.expected) or self.expected[self.consumed] not in eligible:
            raise InconsistentKnowledge('Observed initial HP is outside the eligible prior')
        value = self.expected[self.consumed]
        self.consumed += 1
        self.log_likelihood -= math.log(len(eligible))
        return value

    def finish(self):
        if self.consumed != len(self.expected):
            raise InconsistentKnowledge('Observed roster differs from construction')
