"""Fogmog's summoned illusion retains its slot through repeated revival."""

from game.headless.encounters.randomness import summon
from game.headless.core.native_rng import NativeRng, single

from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy


class EyeWithTeeth(ScriptedEnemy):
    NAME, HP = "Eye With Teeth", (6, 6)
    MOVES = (Intent("shuffle", 3, "Distract", discard_cards=("dazed",) * 3),
             Intent("heal", 6, "Revive"))

    def __init__(self, rng):
        super().__init__(rng)
        self.statuses.add("illusion", 1)
        self.statuses.add("minion", 1)

    @property
    def can_take_turn(self):
        return self.is_alive or self._intent_index == 1

    def on_damage_taken(self, damage, is_attack):
        if not self.is_alive and self.statuses.get("illusion"):
            for name in ("weak", "vulnerable", "frail", "slow", "constrict", "tangled", "ringing", "shrink"):
                self.statuses.decrement(name, self.statuses.get(name))
            self._intent_index = 1

    def validate_combat_context(self, player):
        active = any(e.is_alive and not e.statuses.get("minion") for e in player.combat_enemies)
        if active and (self.is_alive == (self._intent_index == 1)):
            raise ValueError("An active illusion revives exactly while it is dead.")

    def take_damage(self, amount, **kwargs):
        if not self.is_alive:
            return 0
        return super().take_damage(amount, **kwargs)

    def after_move(self, player, intent):
        if self._intent_index == 1:
            self.hp = self.max_hp

    def advance_intent(self):
        self._intent_index = 0

    def _possible_next_templates(self):
        return self.MOVES[:1]


class Fogmog(ScriptedEnemy):
    NAME, HP = "Fogmog", (74, 74)
    SWIPE = Intent("attack", 8, "Swipe", attack_damage=8, attack_count=1, strength_gain=1)
    MOVES = (Intent("summon", 1, "Illusion"), SWIPE, SWIPE,
             Intent("attack", 14, "Headbutt", attack_damage=14, attack_count=1))

    def after_move(self, player, intent):
        if self._intent_index == 0:
            child = summon(EyeWithTeeth, self, player)
            child.combat_player = player
            player.combat_enemies.append(child)

    def advance_intent(self):
        if self._intent_index == 1:
            roll = self.rng.random()
            self._intent_index = 2 if (roll <= single(0.4) if isinstance(self.rng, NativeRng) else roll < 0.4) else 3
        else:
            self._intent_index = (1, 2, 3, 1)[self._intent_index]

    def _possible_next_templates(self):
        return self.MOVES[2:] if self._intent_index == 1 else (self.MOVES[(1, 2, 3, 1)[self._intent_index]],)
