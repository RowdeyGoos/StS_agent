"""Hive summons, hatching and persistent illusion slots."""
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy, DeferredMoveEnemy
from game.headless.monsters.underdocks_normal import attack
from game.headless.monsters.underdocks_summons import append_child
from game.headless.monsters.fogmog import EyeWithTeeth
from game.headless.monsters.interrupts import InterruptibleEnemy
from game.headless.encounters.randomness import branch
from game.headless.powers.status import StatusCollection


class ToughEgg(ScriptedEnemy):
    NAME, HP = 'Tough Egg', (14, 18)
    MOVES = (Intent('summon', 1, 'Hatch'), attack('Nibble', 4))
    LOOP_START = 1

    def __init__(self, rng, *, position=1):
        super().__init__(rng)
        self.position = position
        self.statuses.add('minion', 1)

    @property
    def turn_order(self):
        return self.position

    def after_move(self, player, intent):
        if intent.move_name == 'Hatch':
            # Native NextInt's upper bound is exclusive here (unlike initial HP).
            self.max_hp = self.hp = player.deck.niche_rng.randrange(self.ascension_value('HatchlingMinHp', 19), self.ascension_value('HatchlingMaxHp', 22))
            self.name = 'Hatchling'
            self.strength = 0
            self.statuses = StatusCollection()
            self.statuses.add('minion', 1)


class Ovicopter(DeferredMoveEnemy):
    turn_order = 6
    NAME, HP = 'Ovicopter', (124, 130)
    MOVES = (Intent('summon', 3, 'Lay Eggs'), attack('Smash', 16),
             attack('Tenderizer', 7, status_name='vulnerable', status_stacks=2),
             Intent('buff', 3, 'Nutritional Paste', strength_gain=3))

    def after_move(self, player, intent):
        if intent.move_name == 'Lay Eggs':
            used = {e.position for e in player.combat_enemies if isinstance(e, ToughEgg) and e.is_alive}
            for position in sorted(set(range(1, 6)) - used, reverse=True)[:3]:
                append_child(ToughEgg, self, player, position=position)

    def roll_next_intent(self):
        count = sum(e.is_alive for e in self.combat_player.combat_enemies) if self.combat_player else 1
        self._intent_index = (0 if count <= 3 else 3) if self._intent_index == 2 else (2 if self._intent_index == 1 else 1)

    def _possible_next_templates(self):
        if self._intent_index == 2:
            count = sum(e.is_alive for e in self.combat_player.combat_enemies) if self.combat_player else 1
            return (self.MOVES[0 if count <= 3 else 3],)
        return (self.MOVES[2 if self._intent_index == 1 else 1],)


class Parafright(EyeWithTeeth, InterruptibleEnemy):
    turn_order = 0
    NAME, HP = 'Parafright', (21, 21)
    MOVES = (attack('Slam', 16), Intent('heal', 21, 'Revive'))

    def on_damage_taken(self, damage, is_attack):
        if not self.is_alive:
            self.capture_interrupted_move()
            for name in tuple(self.statuses.as_dict()):
                if name not in ('minion', 'illusion', 'artifact', 'mangle', 'dark_shackles', 'crush_under', 'dying_star', 'monarchs_gaze_strength_down'):
                    self.statuses.decrement(name, self.statuses.get(name))
            self._intent_index = 1

    def validate_combat_context(self, player):
        EyeWithTeeth.validate_combat_context(self, player)
        InterruptibleEnemy.validate_combat_context(self, player)


class TheObscura(ScriptedEnemy):
    turn_order = 1
    NAME, HP = 'The Obscura', (123, 123)
    MOVES = (Intent('summon', 1, 'Illusion'), attack('Piercing Gaze', 10),
             Intent('buff', 3, 'Wail'), attack('Hardening Strike', 6, block_gain=6))

    def after_move(self, player, intent):
        if intent.move_name == 'Illusion':
            append_child(Parafright, self, player)
        elif intent.move_name == 'Wail':
            for enemy in player.combat_enemies:
                if enemy.is_alive:
                    enemy.gain_strength(3)

    def advance_intent(self):
        self._intent_index = branch(self.rng, tuple(i for i in (1, 2, 3) if i != self._intent_index))

    def _possible_next_templates(self):
        return tuple(self.MOVES[i] for i in (1, 2, 3) if i != self._intent_index)
