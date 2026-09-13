"""Bygone Effigy's fixed awakening and per-card Slow counter."""

from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy


class BygoneEffigy(ScriptedEnemy):
    NAME, HP = "Bygone Effigy", (127, 127)
    LOOP_START = 2
    MOVES = (Intent("buff", 0, "Sleep"), Intent("buff", 10, "Wake", strength_gain=10),
             Intent("attack", 13, "Slash", attack_damage=13, attack_count=1))

    def __init__(self, rng):
        super().__init__(rng)
        self.statuses.add("slow", 1)
        self.slow_count = 0

    @property
    def intent(self):
        if type(self.slow_count) is not int or self.slow_count < 0:
            raise ValueError("Invalid Slow card count.")
        return super().intent

    def incoming_attack_multiplier(self):
        return (10 + self.slow_count, 10) if self.statuses.get("slow") else (1, 1)

    def after_player_card(self, player):
        if self.statuses.get("slow"):
            self.slow_count += 1

    def start_turn(self):
        super().start_turn()
        self.slow_count = 0
