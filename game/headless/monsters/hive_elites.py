"""Hive elite powers and the Decimillipede's simultaneous-death condition."""
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.interrupts import InterruptibleEnemy
from game.headless.monsters.underdocks_normal import attack
from game.headless.encounters.randomness import branch
from game.headless.powers.status import StatusCollection


class Entomancer(ScriptedEnemy):
    NAME, HP = 'Entomancer', (145, 145)
    MOVES = (attack('Bees', 3, 7), attack('Spear', 18), Intent('buff', 1, 'Pheromone Spit'))

    def __init__(self, rng):
        super().__init__(rng)
        self.personal_hive = 1

    def after_move(self, player, intent):
        if intent.move_name == 'Pheromone Spit':
            self.gain_strength(1 if self.personal_hive < 3 else 2)
            self.personal_hive = min(3, self.personal_hive + 1)

    def after_received_damage(self, damage, *, is_attack, powered, attacker_statuses, pet):
        p = self.combat_player
        if self.is_alive and p is not None and is_attack and powered and (pet or attacker_statuses is p.statuses):
            from game.headless.powers.hive import generate
            generate(p, 'dazed', 'draw_pile', self.personal_hive, random_position=True)


class InfestedPrism(ScriptedEnemy):
    NAME, HP = 'Infested Prism', (161, 161)
    MOVES = (attack('Jab', 15), attack('Radiate', 11, block_gain=11), attack('Whirlwind', 5, 3), attack('Pulsate', 8, block_gain=20))

    def __init__(self, rng):
        super().__init__(rng)
        self.vital_spark = 2

    def after_joining_combat(self, player):
        for card in player.deck.all_cards():
            if card.spec.kind in ('skill', 'block'):
                card.combat_state.tainted = True

    def after_move(self, player, intent):
        if intent.move_name == 'Pulsate':
            self.vital_spark += 2

    def after_player_card(self, player):
        card = player.current_card
        if card is not None and card.combat_state.tainted:
            from game.headless.powers.hive import debuff
            debuff(player, 'tainted', self.vital_spark)

    def on_combat_state_changed(self, player):
        if not self.is_alive:
            for card in player.deck.all_cards():
                card.combat_state.tainted = False


class DecimillipedeSegment(InterruptibleEnemy):
    NAME, HP = 'Decimillipede Segment', (40, 46)
    MOVES = (attack('Writhe', 5, 2), attack('Bulk', 6, strength_gain=2),
             attack('Constrict', 8, status_name='weak', status_stacks=1),
             Intent('stun', 0, 'Dead'), Intent('heal', 25, 'Reattach'))

    def __init__(self, rng, *, opening=0):
        super().__init__(rng)
        self._intent_index = opening
        self.reviving = False
        self.hp_adjusted = False

    def after_joining_combat(self, player):
        if self.hp_adjusted:
            return
        hp = self.max_hp + self.max_hp % 2
        others = [e.max_hp for e in player.combat_enemies if e is not self]
        while hp in others:
            hp += 2
            if hp > 46:
                hp = 40
        self.max_hp = self.hp = hp
        self.hp_adjusted = True

    @property
    def can_take_turn(self):
        return self.is_alive or self.reviving

    @property
    def allows_fatal(self):
        return self.combat_player is None or not any(e is not self and isinstance(e, DecimillipedeSegment) and e.is_alive for e in self.combat_player.combat_enemies)

    def on_combat_state_changed(self, player):
        if not self.is_alive and not self.reviving and not self.allows_fatal:
            self.capture_interrupted_move()
            self.reviving = True
            self._intent_index = 3
            self.strength = 0
            self.statuses = StatusCollection()

    def on_damage_taken(self, damage, is_attack):
        if self.combat_player is not None:
            self.on_combat_state_changed(self.combat_player)

    def after_move(self, player, intent):
        if intent.move_name == 'Reattach' and not self.allows_fatal:
            self.hp = min(self.max_hp, self.hp + 25)
            self.reviving = False

    def advance_intent(self):
        if self.move_interrupted:
            return
        self._intent_index = branch(self.rng, (0, 1, 2)) if self._intent_index == 4 else (2, 0, 1, 4)[self._intent_index]

    def _possible_next_templates(self):
        return self.MOVES[:3] if self._intent_index == 4 else (self.MOVES[(2, 0, 1, 4)[self._intent_index]],)

    def prepare_next_turn(self):
        # Native RollMove prepares forced Dead after the complete enemy side,
        # including deaths during another creature's move or the Doom boundary.
        if self.reviving and self._intent_index == 3:
            self._intent_index = 4

    def validate_combat_context(self, player):
        super().validate_combat_context(player)
        if (self.reviving and (self.is_alive or self._intent_index not in (3, 4))) or (self.is_alive and self._intent_index >= 3):
            raise ValueError('Invalid Decimillipede revival.')


class DecimillipedeSegmentFront(DecimillipedeSegment):
    pass


class DecimillipedeSegmentMiddle(DecimillipedeSegment):
    pass


class DecimillipedeSegmentBack(DecimillipedeSegment):
    pass
