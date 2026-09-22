"""Vantom's verified A0 opening and four-move cycle."""

from game.headless.monsters.base import Enemy, Intent
from game.headless.powers.status import SLIPPERY


class Vantom(Enemy):
    MOVES = (
        Intent("attack", 7, "Ink Blot", attack_damage=7, attack_count=1),
        Intent("attack", 6, "Inky Lance", attack_damage=6, attack_count=2),
        Intent("attack", 26, "Dismember", attack_damage=26, attack_count=1,
               discard_cards=("wound",) * 3),
        Intent("buff", 2, "Prepare", strength_gain=2),
    )

    def __init__(self, rng):
        super().__init__("Vantom", 173, rng)
        self._intent_index = 0
        self.statuses.add(SLIPPERY, self.ascension_value('SlipperyAmt', 8))

    @property
    def intent(self):
        if type(self._intent_index) is not int or not 0 <= self._intent_index < len(self.MOVES):
            raise ValueError("Invalid Vantom move index.")
        return self._resolve_intent(self.MOVES[self._intent_index])

    def advance_intent(self):
        self._intent_index = (self._intent_index + 1) % len(self.MOVES)

    def _behavior_phase_index(self):
        return self._intent_index

    def _behavior_phase_count(self):
        return len(self.MOVES)

    def _possible_next_templates(self):
        return (self.MOVES[(self._intent_index + 1) % len(self.MOVES)],)
