"""Byrdonis, the first supported Overgrowth elite at Ascension 0."""

from random import Random
from game.headless.monsters.base import Enemy, Intent
from game.headless.powers.status import TERRITORIAL


class Byrdonis(Enemy):
    MOVES = (
        Intent("attack", 3, "Peck", attack_damage=3, attack_count=3),
        Intent("attack", 17, "Swoop", attack_damage=17, attack_count=1),
    )

    def __init__(self, rng: Random):
        super().__init__("Byrdonis", 84, rng, min_hp=81)
        self._intent_index = 1
        self.statuses.add(TERRITORIAL, 1)

    @property
    def intent(self):
        if self._intent_index not in (0, 1):
            raise ValueError("Invalid Byrdonis move index.")
        return self._resolve_intent(self.MOVES[self._intent_index])

    def advance_intent(self):
        self._intent_index = 1 - self._intent_index

    def _behavior_phase_index(self):
        return self._intent_index

    def _behavior_phase_count(self):
        return 2

    def _possible_next_templates(self):
        return (self.MOVES[1 - self._intent_index],)
