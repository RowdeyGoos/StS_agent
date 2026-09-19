"""Glory elites: native branch limits and temporary card effects."""
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.underdocks_normal import attack
from game.headless.encounters.randomness import branch


class FlailKnight(ScriptedEnemy):
    NAME, HP = 'Flail Knight', (101, 101)
    MOVES = (Intent('buff', 3, 'War Chant', strength_gain=3), attack('Flail', 9, 2), attack('Ram', 15))
    LIMITS = (1, 2, 2)

    def __init__(self, rng):
        super().__init__(rng)
        self._intent_index = 2
        self.repeats = 1

    def next_indices(self):
        return tuple(i for i in range(len(self.MOVES)) if i != self._intent_index or self.repeats < self.LIMITS[i])

    def advance_intent(self):
        index = branch(self.rng, self.next_indices())
        self.repeats = self.repeats + 1 if index == self._intent_index else 1
        self._intent_index = index

    def _possible_next_templates(self): return tuple(self.MOVES[i] for i in self.next_indices())

    def validate_combat_context(self, player):
        if not 1 <= self.repeats <= self.LIMITS[self._intent_index]: raise ValueError('Invalid move repeat history.')


class SpectralKnight(FlailKnight):
    NAME, HP = 'Spectral Knight', (93, 93)
    MOVES = (Intent('debuff', 2, 'Hex'), attack('Soul Slash', 15), attack('Soul Flame', 3, 3))
    LIMITS = (1, 2, 1)

    def __init__(self, rng):
        super().__init__(rng)
        self._intent_index = 0
        self.hex_active = False

    def next_indices(self):
        return (1,) if self._intent_index == 0 else tuple(i for i in (1, 2) if i != self._intent_index or self.repeats < self.LIMITS[i])

    def advance_intent(self):
        if self._intent_index == 0:
            self._intent_index, self.repeats = 1, 1
        else: super().advance_intent()

    def after_move(self, player, intent):
        if intent.move_name == 'Hex':
            if player.statuses.get('artifact'):
                player.statuses.decrement('artifact')
                return
            if any(getattr(e, 'hex_active', False) for e in player.combat_enemies): return
            self.hex_active = True
            from game.headless.powers.glory import afflict
            for card in player.deck.all_cards(): afflict(card, 'hexed')

    def on_combat_state_changed(self, player):
        if self.hex_active and not self.is_alive:
            self.hex_active = False
            for card in player.deck.all_cards(): card.combat_state.hexed = False


class MagiKnight(ScriptedEnemy):
    NAME, HP = 'Magi Knight', (82, 82)
    MOVES = (attack('Power Shield', 6, block_gain=5), Intent('debuff', 1, 'Dampen'), attack('Ram', 10),
             Intent('defend', 5, 'Prep', block_gain=5), attack('Magic Bomb', 35))
    LOOP_START = 2

    def __init__(self, rng):
        super().__init__(rng)
        self.dampen_active = False

    def after_move(self, player, intent):
        if intent.move_name == 'Dampen':
            existing = any(getattr(e, 'dampen_active', False) for e in player.combat_enemies)
            if not existing and player.statuses.get('artifact'):
                player.statuses.decrement('artifact')
                return
            self.dampen_active = True
            if not existing:
                for card in player.deck.all_cards():
                    if card.upgrade_level:
                        card.combat_state.dampened_levels = card.upgrade_level
                        card.upgrade_level = 0

    def on_combat_state_changed(self, player):
        if not self.is_alive and self.dampen_active:
            self.dampen_active = False
            if not any(getattr(e, 'dampen_active', False) for e in player.combat_enemies):
                for card in player.deck.all_cards():
                    for _ in range(card.combat_state.dampened_levels):
                        if card.upgrade_level + 1 < len(card.definition.levels): card.upgrade()
                    card.combat_state.dampened_levels = 0


class MechaKnight(ScriptedEnemy):
    NAME, HP = 'Mecha Knight', (300, 300)
    MOVES = (attack('Charge', 25), Intent('shuffle', 4, 'Flamethrower'),
             Intent('defend', 15, 'Windup', block_gain=15, strength_gain=5), attack('Heavy Cleave', 35))
    LOOP_START = 1

    def __init__(self, rng):
        super().__init__(rng)
        self.statuses.add('artifact', 3)

    def after_move(self, player, intent):
        if intent.move_name == 'Flamethrower':
            from game.headless.powers.hive import generate
            generate(player, 'burn', 'hand', 4)


class SoulNexus(FlailKnight):
    NAME, HP = 'Soul Nexus', (234, 234)
    MOVES = (attack('Soul Burn', 29), attack('Maelstrom', 6, 4), attack('Drain Life', 18))
    LIMITS = (1, 1, 1)

    def __init__(self, rng):
        super().__init__(rng)
        self._intent_index = 0

    def after_move(self, player, intent):
        if intent.move_name == 'Drain Life':
            player.apply_status('vulnerable', 2, source=self)
            player.apply_status('weak', 2, source=self)
