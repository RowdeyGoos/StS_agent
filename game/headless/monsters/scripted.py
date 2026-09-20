"""Small reusable support for content-owned move cycles."""

from game.headless.monsters.base import Enemy, Intent


class ScriptedEnemy(Enemy):
    NAME = ""
    HP = (1, 1)
    MOVES: tuple[Intent, ...] = ()
    LOOP_START = 0

    def __init__(self, rng):
        super().__init__(self.NAME, self.HP[1], rng, min_hp=self.HP[0] if self.HP[0] != self.HP[1] else None)
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


class DeferredMoveEnemy(ScriptedEnemy):
    """Roll roster-dependent moves after the whole enemy side has settled."""

    def __init__(self, rng):
        super().__init__(rng)
        self.move_roll_pending = False

    def advance_intent(self):
        if self.combat_player is not None and self.combat_player.rules.enemy_turn is not None:
            self.move_roll_pending = True
        else:
            self.roll_next_intent()

    def roll_next_intent(self):
        raise NotImplementedError

    def prepare_next_turn(self):
        if self.move_roll_pending:
            self.move_roll_pending = False
            if self.is_alive:
                self.advance_intent()

    def on_combat_state_changed(self, player):
        if not self.is_alive or not player.is_alive or player.combat_is_ending:
            self.move_roll_pending = False

    def validate_combat_context(self, player):
        progress = player.rules.enemy_turn
        completed = False
        if progress is not None and self.is_alive and player.is_alive and not player.combat_is_ending:
            slot = player.combat_enemies.index(self)
            names = {move.move_name for move in self.MOVES}
            completed = any(action['enemy_index'] == slot and action['intent']['move_name'] in names
                            for action in progress['actions'])
            move = progress.get('move')
            if move is not None:
                from game.headless.core.enemy_turn import current_slot
                completed |= (current_slot(progress) == slot and move['stage'] == 'done'
                              and move['intent']['move_name'] in names)
        if self.move_roll_pending != completed:
            raise ValueError('Monster move roll differs from its enemy continuation.')
