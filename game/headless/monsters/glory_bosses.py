"""Glory bosses: binding, escalating Withers and genuine death/revival phases."""
from dataclasses import replace
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.interrupts import InterruptibleEnemy
from game.headless.monsters.underdocks_normal import attack
from game.headless.powers.hive import generate
from game.headless.powers.status import StatusCollection


class Aeonglass(ScriptedEnemy):
    NAME, HP = 'Aeonglass', (512, 512)
    MOVES = (attack('Ebb', 26, block_gain=33), attack('Eye Lasers', 11, 2), Intent('buff', 3, 'Increasing Intensity'))

    def __init__(self, rng):
        super().__init__(rng)
        self.statuses.add('artifact', 3)
        self.wither_upgrades = 0
        self.extra_strength = 0
        self.cards_left = 6

    def after_move(self, player, intent):
        if intent.move_name == 'Increasing Intensity':
            for card in player.deck.all_cards():
                if card.definition.definition_id == 'wither': card.combat_state.wither_level += 1
            self.wither_upgrades += 1
            generate(player, 'wither', 'discard_pile', 1)
            self.gain_strength(3 + self.extra_strength)
            self.extra_strength += 1

    def after_player_card(self, player):
        self.cards_left -= 1
        if not self.cards_left:
            generate(player, 'wither', 'hand', 1)
            self.cards_left = 6

    def validate_combat_context(self, player):
        if not 1 <= self.cards_left <= 6 or self.wither_upgrades < 0 or self.extra_strength != self.wither_upgrades:
            raise ValueError('Invalid Aeonglass counters.')


class TorchHeadAmalgam(ScriptedEnemy):
    NAME, HP = 'Torch Head Amalgam', (199, 199)
    MOVES = (attack('Tackle', 18), attack('Tackle 2', 18), attack('Beam', 8, 3),
             attack('Tackle 3', 14), attack('Tackle 4', 14))
    LOOP_START = 2

    def __init__(self, rng):
        super().__init__(rng)
        self.statuses.add('minion', 1)


class Queen(InterruptibleEnemy):
    NAME, HP = 'Queen', (400, 400)
    MOVES = (Intent('debuff', 3, 'Puppet Strings'), Intent('debuff', 99, 'You Are Mine'),
             Intent('buff', 1, 'Burn Bright For Me'), Intent('buff', 2, 'Enrage', strength_gain=2),
             attack('Off With Your Head', 3, 5), attack('Execution', 15))

    def __init__(self, rng):
        super().__init__(rng)
        self.amalgam_died = False
        self.binding = False
        self.bound_draws = 0
        self.bound_played = False

    def on_teammate_death(self, other):
        if isinstance(other, TorchHeadAmalgam):
            self.amalgam_died = True
            if self._intent_index == 2:
                self.capture_interrupted_move()
                self._intent_index = 3

    def next_index(self):
        return (1, 4 if self.amalgam_died else 2, 4 if self.amalgam_died else 2, 4, 5, 3)[self._intent_index]

    def advance_intent(self):
        if not self.move_interrupted: self._intent_index = self.next_index()
    def _possible_next_templates(self): return (self.MOVES[self.next_index()],)

    def after_move(self, player, intent):
        if intent.move_name == 'Puppet Strings':
            if player.statuses.get('artifact'): player.statuses.decrement('artifact')
            else:
                self.binding = True
                player.rules.powers['chains_of_binding'] = 3
        elif intent.move_name == 'You Are Mine':
            for name in ('frail', 'weak', 'vulnerable'): player.apply_status(name, 99, source=self)
        elif intent.move_name == 'Burn Bright For Me':
            for enemy in player.combat_enemies:
                if enemy is not self and enemy.is_alive: enemy.gain_strength(1)
            self.gain_block(20)

    def before_side_start(self, player_side):
        if player_side: self.bound_draws = 0

    def validate_combat_context(self, player):
        super().validate_combat_context(player)
        if not 0 <= self.bound_draws <= 3 or (self.bound_played or self.bound_draws) and not self.binding:
            raise ValueError('Invalid Chains of Binding history.')


class TestSubject(InterruptibleEnemy):
    NAME, HP = 'Test Subject', (100, 100)
    MOVES = (attack('Bite', 20), attack('Skull Bash', 14, status_name='vulnerable', status_stacks=1),
             Intent('heal', 200, 'Respawn'), attack('Multi Claw', 10, 3), attack('Phase3 Lacerate', 10, 3),
             attack('Big Pounce', 45), Intent('shuffle', 3, 'Burning Growl', discard_cards=('burn',) * 3, strength_gain=2))

    def __init__(self, rng):
        super().__init__(rng)
        self.respawns = 0
        self.reviving = False
        self.extra_claws = 0
        self.nemesis_intangible = False
        self.stab_hits = 0

    @property
    def prevents_combat_end(self): return self.respawns < 2
    @property
    def can_take_turn(self): return self.is_alive or self.reviving

    @property
    def intent(self):
        template = self.MOVES[self._intent_index]
        if self._intent_index == 3: template = replace(template, attack_count=3 + self.extra_claws)
        return self._resolve_intent(template)

    def damage_amount(self, *args, **kwargs):
        amount = super().damage_amount(*args, **kwargs)
        return min(1, amount) if self.nemesis_intangible else amount

    def modify_unblocked_damage(self, amount): return min(1, amount) if self.nemesis_intangible else amount

    def on_combat_state_changed(self, player):
        if not self.is_alive and self.respawns < 2 and not self.reviving:
            self.capture_interrupted_move()
            self.reviving = True
            self._intent_index = 2
            self.strength = self.block = 0
            self.statuses = StatusCollection()

    def before_move(self, player): self.stab_hits = 0

    def after_attack_hit(self, player_damage, pet_damage):
        if self.respawns == 1 and player_damage > 0: self.stab_hits += 1

    def after_attack(self, player, intent):
        count, self.stab_hits = self.stab_hits, 0
        if count and player.is_alive: generate(player, 'wound', 'discard_pile', count)

    def after_move(self, player, intent):
        if intent.move_name == 'Respawn':
            self.respawns += 1
            self.max_hp = self.hp = (100, 200, 300)[self.respawns]
            self.reviving = False
        elif intent.move_name == 'Multi Claw': self.extra_claws += 1

    def next_index(self):
        return (1, 0, 3 if self.respawns < 2 else 4, 3, 5, 6, 4)[self._intent_index]

    def advance_intent(self):
        if not self.move_interrupted: self._intent_index = self.next_index()
    def _possible_next_templates(self): return (self.MOVES[self.next_index()],)

    def after_player_card(self, player):
        if self.respawns == 0 and player.current_card is not None and player.current_card.spec.kind in ('skill', 'block'):
            self.gain_strength(2)

    def after_side_end(self):
        if self.respawns == 2: self.nemesis_intangible = not self.nemesis_intangible

    def validate_combat_context(self, player):
        super().validate_combat_context(player)
        if (not 0 <= self.respawns <= 2 or self.extra_claws < 0 or self.stab_hits < 0
                or (self.respawns < 2 and not self.is_alive and not self.reviving)
                or self.reviving != (self._intent_index == 2) or self.reviving and self.is_alive
                or self.nemesis_intangible and self.respawns != 2
                or self.max_hp != (100, 200, 300)[self.respawns]):
            raise ValueError('Invalid Test Subject revival state.')
        allowed = ({0, 1, 2}, {2, 3}, {4, 5, 6})[self.respawns]
        if self._intent_index not in allowed: raise ValueError('Test Subject move differs from its form.')
        if self.stab_hits:
            progress = player.rules.enemy_turn
            from game.headless.core.enemy_turn import current_slot
            if progress is None or progress['move'] is None or progress['move']['stage'] != 'hits' or current_slot(progress) != player.combat_enemies.index(self) or self.stab_hits > progress['move']['hit']:
                raise ValueError('Unowned Painful Stabs results.')
