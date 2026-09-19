"""Immutable orb-channel recipes; random choices resolve one channel at a time."""

from dataclasses import dataclass
from game.headless.cards.operations import value
from game.headless.core.resolution import push


@dataclass(frozen=True, slots=True)
class Channel:
    kind: str
    amount: int = 1
    upgraded_amount: int | None = None
    count: str = 'fixed'

    def apply(self, card, p, target):
        amount = value(card, self.amount, self.upgraded_amount)
        if self.count == 'x':
            amount = p.rules.plays[card.instance_id]['x'] + int(card.upgraded)
        elif self.count == 'enemies':
            amount = sum(e.is_alive for e in p.combat_enemies or ())
        elif self.count == 'history':
            amount = sum(o['kind'] == self.kind for o in p.rules.orbs.values())
        if not p.combat_is_ending:
            push(p, *[['orb_channel', self.kind] for _ in range(amount)])
