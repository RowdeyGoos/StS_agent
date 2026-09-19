"""Bind an interrupted enemy move to its serialized execution continuation."""
from dataclasses import asdict
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy


class InterruptibleEnemy(ScriptedEnemy):
    def __init__(self, rng):
        super().__init__(rng)
        self.move_interrupted = False
        self.interrupted_intent = Intent('stun', 0)

    def capture_interrupted_move(self):
        p = self.combat_player
        progress = p.rules.enemy_turn if p is not None else None
        if progress and progress['slot'] == p.combat_enemies.index(self) and progress['move'] is not None:
            self.interrupted_intent = Intent(**progress['move']['intent'])
            self.move_interrupted = True

    def continuation_intent(self):
        return self.interrupted_intent if self.move_interrupted else self.intent

    def finish_move(self):
        self.move_interrupted = False
        self.interrupted_intent = Intent('stun', 0)

    def validate_combat_context(self, player):
        if self.move_interrupted:
            progress = player.rules.enemy_turn
            if (not progress or progress['slot'] != player.combat_enemies.index(self)
                    or progress['move'] is None or progress['move']['hit'] <= 0
                    or asdict(Intent(**progress['move']['intent'])) != asdict(self.interrupted_intent)):
                raise ValueError('Unowned interrupted monster move.')
        elif self.interrupted_intent != Intent('stun', 0):
            raise ValueError('Stale interrupted monster move.')
