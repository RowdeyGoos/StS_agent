"""Small reusable support for content-owned move cycles."""

from game.headless.monsters.base import Enemy, Intent


class ScriptedEnemy(Enemy):
    NAME = ""
    HP = (1, 1)
    MOVES: tuple[Intent, ...] = ()
    LOOP_START = 0

    def __init__(self, rng):
        super().__init__(self.NAME, self.HP[0] if self.HP[0] == self.HP[1] else rng.randint(*self.HP), rng)
        self._intent_index = 0

    @property
    def intent(self):
        if type(self._intent_index) is not int or not 0 <= self._intent_index < len(self.MOVES):
            raise ValueError("Invalid monster move index.")
        return self._resolve_intent(self.MOVES[self._intent_index])

    def advance_intent(self):
        self._intent_index += 1
        if self._intent_index == len(self.MOVES):
            self._intent_index = self.LOOP_START

    def _behavior_phase_index(self):
        return self._intent_index

    def _behavior_phase_count(self):
        return len(self.MOVES)

    def _possible_next_templates(self):
        index = self._intent_index + 1
        return (self.MOVES[index if index < len(self.MOVES) else self.LOOP_START],)
