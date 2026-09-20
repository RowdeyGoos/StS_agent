"""Underdocks boss cycles, sleep, Intangible and the final steam explosion."""
from dataclasses import replace
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.interrupts import InterruptibleEnemy
from game.headless.monsters.underdocks_normal import attack, SewerClam


class LagavulinMatriarch(SewerClam):
    NAME, HP = 'Lagavulin Matriarch', (222, 222)
    MOVES = (Intent('sleep', 0, 'Sleep'), attack('Slash', 19), attack('Disembowel', 9, 2),
             attack('Slash and Guard', 12, block_gain=12), Intent('debuff', 2, 'Soul Siphon'))
    LOOP_START = 1

    def __init__(self, rng):
        super().__init__(rng)
        self.plating = self.block = 12
        self.asleep = 3

    def on_damage_taken(self, damage, is_attack):
        if damage > 0 and self.asleep and self.is_alive:
            self.asleep = self.plating = 0
            self._intent_index = 1
            self.stunned = True

    def advance_intent(self):
        if self._intent_index == 0:
            # The turn-end decrement happens after move selection.
            self._intent_index = 0 if self.asleep > 1 else 1
        else:
            ScriptedEnemy.advance_intent(self)

    def after_side_end(self):
        if self.asleep == 1:
            self.plating = 0
        super().after_side_end()
        self.asleep = max(0, self.asleep - 1)

    def after_move(self, player, intent):
        if intent.move_name == 'Soul Siphon':
            from game.headless.powers.underdocks import stat_loss
            stat_loss(player, 'strength', 2)
            stat_loss(player, 'dexterity', 2)
            self.gain_strength(2)


class SoulFysh(ScriptedEnemy):
    NAME, HP = 'Soul Fysh', (211, 211)
    MOVES = (Intent('shuffle', 2, 'Beckon'), attack('De-Gas', 16),
             attack('Gaze', 7, discard_cards=('beckon',)), Intent('buff', 0, 'Fade'),
             attack('Scream', 13, status_name='vulnerable', status_stacks=3))

    def __init__(self, rng):
        super().__init__(rng)
        self.intangible = 0

    def damage_amount(self, *args, **kwargs):
        amount = super().damage_amount(*args, **kwargs)
        return min(1, amount) if self.intangible else amount

    def modify_unblocked_damage(self, amount):
        return min(1, amount) if self.intangible else amount

    def after_move(self, player, intent):
        if intent.move_name == 'Fade':
            self.intangible += 2
        elif intent.move_name == 'Beckon':
            from game.headless.cards.colorless_effects import catalog
            from game.headless.core.piles import after_generated_entry
            for pile in ('draw_pile', 'discard_pile'):
                card = catalog(player).create('beckon')
                player.deck._ensure_identity(card)
                if pile == 'draw_pile':
                    from game.headless.core.native_rng import NativeRng
                    position = player.deck.rng.randrange(len(player.deck.draw_pile) + 1)
                    if isinstance(player.deck.rng, NativeRng):
                        position = len(player.deck.draw_pile) - position
                    player.deck.draw_pile.insert(position, card)
                else:
                    player.deck.discard_pile.append(card)
                after_generated_entry(player, card)

    def after_side_end(self):
        self.intangible = max(0, self.intangible - 1)


class WaterfallGiant(InterruptibleEnemy):
    NAME, HP = 'Waterfall Giant', (240, 240)
    MOVES = (Intent('buff', 0, 'Pressurize'), attack('Stomp', 15, status_name='weak', status_stacks=1),
             attack('Ram', 10), Intent('heal', 10, 'Siphon'), attack('Pressure Gun', 20),
             attack('Pressure Up', 13), Intent('stun', 0, 'About to Blow'), attack('Explode', 1))

    def __init__(self, rng):
        super().__init__(rng)
        self.pressure_gun = 20
        self.steam = 0
        self.explosion_damage = 0
        self.about_to_blow = False
        self.exploded = False

    @property
    def prevents_combat_end(self):
        return bool(self.steam and not self.exploded)

    @property
    def intent(self):
        template = self.MOVES[self._intent_index]
        if self._intent_index in (4, 7):
            damage = self.pressure_gun if self._intent_index == 4 else self.explosion_damage
            template = replace(template, value=damage, attack_damage=damage)
        return self._resolve_intent(template)

    def on_combat_state_changed(self, player):
        if self.hp == 0 and self.steam and not self.about_to_blow:
            from game.headless.core.resolution import push
            task = ['monster_death', player.combat_enemies.index(self)]
            if task not in player.rules.tasks:
                push(player, task)

    @property
    def death_pending(self):
        return self.hp == 0 and bool(self.steam) and not self.about_to_blow

    def resolve_death(self, player):
        if not self.death_pending:
            raise ValueError("Unowned monster death continuation.")
        self.capture_interrupted_move()
        self.about_to_blow = True
        self.max_hp = self.hp = 999999999
        self._intent_index = 6

    def on_damage_taken(self, damage, is_attack):
        if self.combat_player is not None:
            self.on_combat_state_changed(self.combat_player)

    def after_move(self, player, intent):
        if intent.move_name == 'About to Blow':
            self.explosion_damage = self.steam
            self.steam = 0
        elif intent.move_name == 'Explode':
            self.exploded = True
            self.hp = 0
        else:
            self.steam += 15 if intent.move_name == 'Pressurize' else 3
            if intent.move_name == 'Siphon':
                self.hp = min(self.max_hp, self.hp + 10)
            elif intent.move_name == 'Pressure Gun':
                self.pressure_gun += 5

    def advance_intent(self):
        # A lethal reaction during another move must still perform the stun move.
        if self._intent_index == 6 and self.steam:
            return
        self._intent_index = 1 if self._intent_index == 5 else min(7, self._intent_index + 1)

    def validate_combat_context(self, player):
        super().validate_combat_context(player)
        if self.move_interrupted and not self.about_to_blow:
            raise ValueError("Interrupted Giant has no eruption.")
        if (self.steam < 0 or self.explosion_damage < 0 or self.pressure_gun < 20
                or self.about_to_blow != (self.max_hp == 999999999)
                or self.about_to_blow != (self._intent_index >= 6)):
            raise ValueError('Invalid steam eruption phase.')
