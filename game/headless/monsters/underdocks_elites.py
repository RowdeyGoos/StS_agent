"""Underdocks elites and their damage-triggered rules."""
from dataclasses import replace
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.interrupts import InterruptibleEnemy
from game.headless.monsters.underdocks_normal import attack


class PhantasmalGardener(ScriptedEnemy):
    TRACKS_CARD_ATTACKS = True
    NAME, HP = 'Phantasmal Gardener', (26, 31)
    MOVES = (attack('Bite', 5), attack('Lash', 7), attack('Flail', 1, 3),
             Intent('buff', 2, 'Enlarge', strength_gain=2))

    def __init__(self, rng, *, opening=0):
        super().__init__(rng)
        self._intent_index = opening
        self.skittish_used = False

    def after_received_damage(self, damage, *, is_attack, powered, attacker_statuses, pet):
        player = self.combat_player
        card = player.current_card if player is not None else None
        frame = player.rules.plays.get(card.instance_id, {}) if card is not None else {}
        if is_attack and 'enemy_attack' in frame:
            frame['enemy_attack'].setdefault(str(player.combat_enemies.index(self)), damage)

    def after_card_attack(self, frame):
        damage = frame.get('enemy_attack', {}).get(str(self.combat_player.combat_enemies.index(self)), 0)
        if self.is_alive and not self.skittish_used and damage > 0:
            self.gain_block(self.ascension_value('SkittishAmount', 6))
            self.skittish_used = True

    def after_player_side_end(self):
        self.skittish_used = False


class SkulkingColony(ScriptedEnemy):
    NAME, HP = 'Skulking Colony', (75, 75)
    MOVES = (attack('Zoom', 14), attack('Zoom', 14),
             attack('Inertia', 9, strength_gain=2), attack('Piercing Stabs', 7, 2))

    def __init__(self, rng):
        super().__init__(rng)
        self.shell_damage = 0

    def modify_unblocked_damage(self, amount):
        return min(amount, max(0, 20 - self.shell_damage))

    def after_received_damage(self, damage, **kwargs):
        self.shell_damage += damage

    def before_side_start(self, player_side):
        self.shell_damage = 0

    def validate_combat_context(self, player):
        if self.shell_damage < 0:
            raise ValueError('Invalid Hardened Shell damage.')


class TerrorEel(InterruptibleEnemy):
    NAME, HP = 'Terror Eel', (140, 140)
    MOVES = (attack('Crash', 16), attack('Thrash', 3, 3),
             Intent('debuff', 99, 'Terror', status_name='vulnerable', status_stacks=99))

    def __init__(self, rng):
        super().__init__(rng)
        self.shriek = True
        self.vigor = 0

    @property
    def intent(self):
        template = self.MOVES[self._intent_index]
        if template.attack_count:
            template = replace(template, value=template.value + self.vigor,
                               attack_damage=template.attack_damage + self.vigor)
        return self._resolve_intent(template)

    def on_damage_taken(self, damage, is_attack):
        if self.is_alive and damage > 0 and self.hp <= self.ascension_value('ShriekAmount', 70) and self.shriek:
            self.capture_interrupted_move()
            self.shriek = False
            self.stunned = True
            self._intent_index = 2

    def after_move(self, player, intent):
        if intent.attack_count:
            self.vigor = 0
        if intent.move_name == 'Thrash':
            self.vigor += 6

    def advance_intent(self):
        if self.stunned:
            return
        self._intent_index = 0 if self._intent_index in (1, 2) else 1

    def _possible_next_templates(self):
        return (self.MOVES[0 if self._intent_index in (1, 2) else 1],)

    def validate_combat_context(self, player):
        super().validate_combat_context(player)
        if self.move_interrupted and (self.shriek or not self.stunned or self._intent_index != 2):
            raise ValueError('Interrupted Eel has no Shriek.')
