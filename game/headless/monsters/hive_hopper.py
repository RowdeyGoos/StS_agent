"""Thieving Hopper owns an inert stolen card until death or escape."""
from game.headless.monsters.base import Intent
from game.headless.monsters.interrupts import InterruptibleEnemy
from game.headless.monsters.underdocks_normal import attack
from game.headless.core.native_rng import NativeRng


class ThievingHopper(InterruptibleEnemy):
    NAME, HP = 'Thieving Hopper', (79, 79)
    MOVES = (attack('Thievery', 17), Intent('buff', 5, 'Flutter'), attack('Hat Trick', 21),
             attack('Nab', 14), Intent('escape', 0, 'Escape'), Intent('stun', 0, 'Stunned'))

    def __init__(self, rng):
        super().__init__(rng)
        self.flutter = 0
        self.stolen_id = ''
        self.escaped = False
        self.loot_returned = False
        self.after_stun = 4
        self.escape_countdown = 5

    def incoming_attack_multiplier(self):
        return (1, 2) if self.flutter else (1, 1)

    def before_move(self, player):
        if self._intent_index != 0:
            return
        draw = list(player.deck.draw_pile)
        if isinstance(player.deck.generation_rng, NativeRng):
            draw.reverse()
        cards = [c for c in draw + player.deck.discard_pile if c.instance_id in player.deck.original_ids]
        def priority(card):
            if card.enchantment is not None and card.enchantment.definition_id == 'imbued':
                return 3
            rarity = card.definition.rarity
            if rarity == 'uncommon':
                return 0
            if rarity in ('common', 'rare', 'event'):
                return 1
            if rarity in ('basic', 'quest'):
                return 2
            return 3 if rarity == 'ancient' else 4
        if cards:
            best = min(map(priority, cards))
            card = player.deck.generation_rng.choice([c for c in cards if priority(c) == best])
            from game.headless.core.resolution import move_out
            move_out(player, card)
            player.deck.sequestered.append(card)
            self.stolen_id = card.instance_id

    def after_received_damage(self, damage, *, is_attack, powered, attacker_statuses, pet):
        if self.flutter and damage > 0 and is_attack and powered:
            self.flutter -= 1
            if not self.flutter and self.is_alive:
                self.capture_interrupted_move()
                self.after_stun = min(4, self._intent_index + 1)
                self._intent_index = 5

    def after_move(self, player, intent):
        if intent.move_name == 'Flutter':
            self.flutter = 5
        elif intent.move_name == 'Escape':
            self.escaped = True
            self.hp = 0

    def on_combat_state_changed(self, player):
        if not self.is_alive and not self.escaped:
            self.loot_returned = True

    def advance_intent(self):
        if not self.move_interrupted:
            self._intent_index = self.after_stun if self._intent_index == 5 else min(4, self._intent_index + 1)

    def _possible_next_templates(self):
        return (self.MOVES[self.after_stun if self._intent_index == 5 else min(4, self._intent_index + 1)],)

    def after_side_end(self):
        self.escape_countdown = max(1, self.escape_countdown - 1)

    def validate_combat_context(self, player):
        super().validate_combat_context(player)
        if (not 0 <= self.flutter <= 5 or not 1 <= self.escape_countdown <= 5 or not 0 <= self.after_stun <= 4
                or self.escaped and (self.is_alive or self.loot_returned)
                or self.loot_returned and self.is_alive
                or self.stolen_id and self.stolen_id not in {c.instance_id for c in player.deck.sequestered}):
            raise ValueError('Invalid Hopper theft or flight state.')
