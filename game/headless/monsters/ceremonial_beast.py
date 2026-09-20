"""Ceremonial Beast: HP-threshold interruption and second-phase Ringing."""

from game.headless.monsters.base import Intent
from game.headless.monsters.interrupts import InterruptibleEnemy


class CeremonialBeast(InterruptibleEnemy):
    NAME, HP = "Ceremonial Beast", (252, 252)
    MOVES = (Intent("buff", 150, "Stamp"),
             Intent("attack", 18, "Plow", attack_damage=18, attack_count=1, strength_gain=2),
             Intent("stun", 0, "Stunned"),
             Intent("debuff", 1, "Beast Cry", status_name="ringing", status_stacks=1),
             Intent("attack", 15, "Stomp", attack_damage=15, attack_count=1),
             Intent("attack", 17, "Crush", attack_damage=17, attack_count=1, strength_gain=3))

    def validate_combat_context(self, player):
        super().validate_combat_context(player)
        if self.is_alive and self.statuses.get("plow") != (150 if self._intent_index == 1 else 0):
            raise ValueError("Plow power differs from the Beast phase.")

    def after_move(self, player, intent):
        if self._intent_index == 0:
            self.statuses.add("plow", 150)

    def on_damage_taken(self, damage, is_attack):
        if damage > 0 and self.is_alive and self.statuses.get("plow") and self.hp <= self.statuses.get("plow"):
            self.statuses.decrement("plow", self.statuses.get("plow"))
            self.capture_interrupted_move()
            from game.headless.powers.necrobinder import TEMP_STRENGTH
            for name in TEMP_STRENGTH:
                self.statuses.decrement(name, self.statuses.get(name))
            self.strength = 0
            self._intent_index = 2

    def advance_intent(self):
        if self.move_interrupted:
            return
        self._intent_index = (1, 1, 3, 4, 5, 3)[self._intent_index]

    def _possible_next_templates(self):
        return (self.MOVES[(1, 1, 3, 4, 5, 3)[self._intent_index]],)
