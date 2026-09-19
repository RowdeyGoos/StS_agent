"""Underdocks hallway monsters at A0 (native build 0.107.1)."""
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.encounters.randomness import branch


def attack(name, damage, hits=1, **kwargs):
    return Intent('attack', damage, name, attack_damage=damage, attack_count=hits, **kwargs)


class CorpseSlug(ScriptedEnemy):
    NAME, HP = 'Corpse Slug', (25, 27)
    MOVES = (attack('Whip Slap', 3, 2), attack('Glomp', 8),
             Intent('debuff', 2, 'Goop', status_name='frail', status_stacks=2))

    def __init__(self, rng, *, opening=0):
        super().__init__(rng)
        self._intent_index = opening

    def on_teammate_death(self, other):
        self.gain_strength(4)
        self.stunned = True


class CalcifiedCultist(ScriptedEnemy):
    NAME, HP = 'Calcified Cultist', (38, 41)
    RITUAL = 2
    LOOP_START = 1
    MOVES = (Intent('buff', 0, 'Incantation'), attack('Dark Strike', 9))

    def __init__(self, rng):
        super().__init__(rng)
        self.ritual = 0
        self.ritual_fresh = False

    def after_move(self, player, intent):
        if intent.move_name == 'Incantation':
            self.ritual = self.RITUAL
            self.ritual_fresh = True

    def after_side_end(self):
        if not self.ritual_fresh:
            self.gain_strength(self.ritual)
        self.ritual_fresh = False


class DampCultist(CalcifiedCultist):
    NAME, HP, RITUAL = 'Damp Cultist', (51, 53), 5
    MOVES = (Intent('buff', 0, 'Incantation'), attack('Dark Strike', 1))


class FossilStalker(ScriptedEnemy):
    NAME, HP = 'Fossil Stalker', (51, 53)
    MOVES = (attack('Latch', 12), attack('Tackle', 9, status_name='frail', status_stacks=1),
             attack('Lash', 3, 2))

    def __init__(self, rng):
        super().__init__(rng)
        self.unblocked_hits = 0
        self.repeat_count = 1

    def after_attack_hit(self, player_damage, pet_damage):
        if player_damage > 0 or pet_damage > 0:
            self.unblocked_hits += 1

    def after_move(self, player, intent):
        self.gain_strength(3 * self.unblocked_hits)
        self.unblocked_hits = 0

    def advance_intent(self):
        next_index = branch(self.rng, tuple(i for i in range(3) if i != self._intent_index or self.repeat_count < 2))
        self.repeat_count = self.repeat_count + 1 if next_index == self._intent_index else 1
        self._intent_index = next_index

    def _possible_next_templates(self):
        return tuple(move for i, move in enumerate(self.MOVES)
                     if i != self._intent_index or self.repeat_count < 2)


class HauntedShip(ScriptedEnemy):
    NAME, HP = 'Haunted Ship', (63, 63)
    LOOP_START = 1
    MOVES = (Intent('debuff', 3, 'Haunt', status_name='weak', status_stacks=3,
                    discard_cards=('dazed',) * 5), attack('Swipe', 13), attack('Stomp', 4, 3))


class Seapunk(ScriptedEnemy):
    NAME, HP = 'Seapunk', (44, 46)
    MOVES = (attack('Sea Kick', 11), attack('Spinning Kick', 2, 4),
             Intent('defend', 7, 'Bubble Burp', block_gain=7, strength_gain=1))


class SewerClam(ScriptedEnemy):
    NAME, HP = 'Sewer Clam', (56, 56)
    MOVES = (attack('Jet', 10), Intent('buff', 4, 'Pressurize', strength_gain=4))

    def __init__(self, rng):
        super().__init__(rng)
        self.plating = 8
        self.block = 8
        self.turns_started = 0

    def start_turn(self):
        super().start_turn()
        if self.turns_started:
            self.plating = max(0, self.plating - 1)
        self.turns_started += 1

    def after_side_end(self):
        self.gain_block(self.plating)


class SludgeSpinner(ScriptedEnemy):
    NAME, HP = 'Sludge Spinner', (37, 39)
    MOVES = (attack('Oil Spray', 8, status_name='weak', status_stacks=1),
             attack('Slam', 11), attack('Rage', 6, strength_gain=3))

    def advance_intent(self):
        self._intent_index = branch(self.rng, tuple(i for i in range(3) if i != self._intent_index))

    def _possible_next_templates(self):
        return tuple(m for i, m in enumerate(self.MOVES) if i != self._intent_index)


class Toadpole(ScriptedEnemy):
    NAME, HP = 'Toadpole', (21, 25)
    MOVES = (attack('Spike Spit', 3, 3), attack('Whirl', 7), Intent('buff', 0, 'Spiken'))

    def __init__(self, rng, *, front=False):
        super().__init__(rng)
        self._intent_index = 2 if front else 1
        self.thorns = 0

    def before_move(self, player):
        if self._intent_index == 0:
            self.thorns = max(0, self.thorns - 2)

    def after_move(self, player, intent):
        if intent.move_name == 'Spiken':
            self.thorns += 2

    def before_received_damage(self, *, is_attack, powered, attacker_statuses, pet):
        player = self.combat_player
        if player is None:
            return
        card = player.current_card
        if self.thorns and ((is_attack and powered) or (card is not None and card.definition.definition_id == 'omnislice')):
            if pet:
                from game.headless.core.osty import take_damage
                take_damage(player, self.thorns)
            elif attacker_statuses is player.statuses:
                player.take_damage(self.thorns, is_attack=False, source=self)
