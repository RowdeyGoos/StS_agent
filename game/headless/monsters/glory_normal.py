"""Glory hallway moves and source-owned reactive rules at solo A0."""
from dataclasses import replace
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.underdocks_normal import attack
from game.headless.encounters.randomness import branch


class DevotedSculptor(ScriptedEnemy):
    NAME, HP = 'Devoted Sculptor', (162, 162)
    MOVES = (Intent('buff', 9, 'Forbidden Incantation'), attack('Savage', 12))
    LOOP_START = 1

    def __init__(self, rng):
        super().__init__(rng)
        self.ritual = False
        self.ritual_new = False

    def after_move(self, player, intent):
        if intent.move_name == 'Forbidden Incantation': self.ritual = self.ritual_new = True

    def after_side_end(self):
        if self.ritual_new: self.ritual_new = False
        elif self.ritual: self.gain_strength(9)


class FrogKnight(ScriptedEnemy):
    NAME, HP = 'Frog Knight', (191, 191)
    MOVES = (attack('Tongue Lash', 13, status_name='frail', status_stacks=2), attack('Strike Down Evil', 21),
             Intent('buff', 5, 'For the Queen', strength_gain=5), attack('Beetle Charge', 35))

    def __init__(self, rng):
        super().__init__(rng)
        self.charged = False
        self.plating = self.block = self.ascension_value('PlatingAmount', 15)
        self.turns_started = 0

    def start_turn(self):
        super().start_turn()
        if self.turns_started: self.plating = max(0, self.plating - 1)
        self.turns_started += 1

    def after_side_end(self): self.gain_block(self.plating)

    def before_move(self, player):
        if self._intent_index == 3: self.charged = True

    def next_index(self):
        if self._intent_index == 2: return 3 if not self.charged and self.hp < self.max_hp // 2 else 0
        return (1, 2, 0, 0)[self._intent_index]

    def advance_intent(self): self._intent_index = self.next_index()
    def _possible_next_templates(self): return (self.MOVES[self.next_index()],)


class GlobeHead(ScriptedEnemy):
    NAME, HP = 'Globe Head', (148, 148)
    MOVES = (attack('Shocking Slap', 13, status_name='frail', status_stacks=2), attack('Thunder Strike', 6, 3),
             attack('Galvanic Burst', 16, strength_gain=2))

    def after_joining_combat(self, player):
        from game.headless.powers.glory import afflict
        for card in player.deck.all_cards():
            if card.spec.kind == 'power': afflict(card, 'galvanized')

    def after_player_card(self, player):
        if self.is_alive and player.current_card is not None and player.current_card.combat_state.galvanized:
            player.take_damage(6, is_attack=False)


class OwlMagistrate(ScriptedEnemy):
    NAME, HP = 'Owl Magistrate', (231, 231)
    MOVES = (attack('Magistrate Scrutiny', 16), attack('Peck Assault', 4, 6), Intent('buff', 1, 'Judicial Flight'),
             attack('Verdict', 33, status_name='vulnerable', status_stacks=4))

    def __init__(self, rng):
        super().__init__(rng)
        self.soaring = False

    def incoming_attack_multiplier(self): return (1, 2) if self.soaring else (1, 1)

    def after_move(self, player, intent):
        if intent.move_name == 'Judicial Flight': self.soaring = True
        elif intent.move_name == 'Verdict': self.soaring = False


class ScrollOfBiting(ScriptedEnemy):
    NAME, HP = 'Scroll of Biting', (30, 37)
    MOVES = (attack('Chomp', 14), attack('Chew', 5, 2), Intent('buff', 2, 'More Teeth', strength_gain=2))

    def __init__(self, rng, *, opening=0):
        super().__init__(rng)
        self._intent_index = opening
        self.repeats = 1

    def next_indices(self):
        return (2,) if self._intent_index == 0 else (1,) if self._intent_index == 2 else ((0, 1) if self.repeats < 2 else (0,))

    def advance_intent(self):
        choices = self.next_indices()
        index = branch(self.rng, choices) if self._intent_index == 1 else choices[0]
        self.repeats = self.repeats + 1 if index == self._intent_index else 1
        self._intent_index = index

    def _possible_next_templates(self): return tuple(self.MOVES[i] for i in self.next_indices())

    def after_attack_hit(self, player_damage, pet_damage):
        # Thorns can remove the owner and its Paper Cuts before AfterDamageGiven.
        if self.is_alive and player_damage > 0:
            p = self.combat_player
            raw_max = p.max_hp - 2
            if p.hp > raw_max: p.lose_hp(p.hp - raw_max)
            maximum = max(1, raw_max)
            p.rules.max_hp_gained += maximum - p.max_hp
            p.max_hp = maximum
            p.hp = min(p.hp, p.max_hp)


class SlimedBerserker(ScriptedEnemy):
    NAME, HP = 'Slimed Berserker', (261, 261)
    MOVES = (Intent('shuffle', 10, 'Vomit Ichor', slimed_added=10), attack('Furious Pummeling', 4, 4),
             Intent('debuff', 3, 'Leeching Hug'), attack('Smother', 30))

    def after_move(self, player, intent):
        if intent.move_name == 'Leeching Hug':
            player.apply_status('weak', 3)  # Native has no applier for this debuff.
            self.gain_strength(3)


class TheLost(ScriptedEnemy):
    NAME, HP = 'The Lost', (93, 93)
    MOVES = (Intent('debuff', 2, 'Debilitating Smog'), attack('Eye Lasers', 4, 2))
    STAT = 'strength'

    def __init__(self, rng):
        super().__init__(rng)
        self.stolen = 0
        self.returned = False

    def after_move(self, player, intent):
        if self._intent_index == 0:
            from game.headless.powers.underdocks import stat_loss
            blocked = bool(player.statuses.get('artifact'))
            stat_loss(player, self.STAT, 2)
            if not blocked: self.stolen += 2
            if self.STAT == 'strength': self.gain_strength(2)
            else:
                self.gain_block(max(0, 8 + self.dexterity))
                self.dexterity += 2

    def on_combat_state_changed(self, player):
        if not self.is_alive and not self.returned:
            self.returned = True
            if self.STAT == 'strength': player.strength += self.stolen
            else: player.rules.powers['dexterity'] = player.rules.powers.get('dexterity', 0) + self.stolen


class TheForgotten(TheLost):
    NAME, HP = 'The Forgotten', (106, 106)
    MOVES = (Intent('debuff', 2, 'Miasma'), attack('Dread', 13))
    STAT = 'dexterity'

    def __init__(self, rng):
        super().__init__(rng)
        self.dexterity = 0

    @property
    def intent(self):
        template = self.MOVES[self._intent_index]
        if self._intent_index == 1: template = replace(template, attack_damage=13 + self.dexterity)
        return self._resolve_intent(template)


class LivingShield(ScriptedEnemy):
    NAME, HP = 'Living Shield', (55, 55)
    MOVES = (attack('Shield Slam', 6), attack('Smash', 16, strength_gain=3))

    def before_side_start(self, player_side):
        if player_side and self.is_alive and self.combat_player is not None:
            for enemy in self.combat_player.combat_enemies:
                if isinstance(enemy, TurretOperator) and enemy.is_alive: enemy.gain_block(25)

    def before_extra_side_start(self):
        pass  # Native Rampart excludes extra player turns.

    def next_index(self):
        if self._intent_index == 1: return 1
        return 0 if self.combat_player is None or any(e is not self and e.is_alive for e in self.combat_player.combat_enemies) else 1

    def advance_intent(self): self._intent_index = self.next_index()
    def _possible_next_templates(self): return (self.MOVES[self.next_index()],)


class TurretOperator(ScriptedEnemy):
    NAME, HP = 'Turret Operator', (41, 41)
    MOVES = (attack('Unload', 3, 5), attack('Unload 2', 3, 5), Intent('buff', 1, 'Reload', strength_gain=1))
