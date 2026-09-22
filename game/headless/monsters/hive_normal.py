"""Hive hallway rules, transcribed from native 0.107.1 at solo A0."""
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.interrupts import InterruptibleEnemy
from game.headless.monsters.underdocks_normal import attack, Toadpole
from game.headless.encounters.randomness import branch


class BowlbugEgg(ScriptedEnemy):
    NAME, HP = 'Bowlbug Egg', (21, 22)
    MOVES = (attack('Bite', 7, block_gain=7),)


class BowlbugNectar(ScriptedEnemy):
    NAME, HP = 'Bowlbug Nectar', (35, 38)
    MOVES = (attack('Thrash', 3), Intent('buff', 15, 'Buff', strength_gain=15), attack('Thrash', 3))
    LOOP_START = 2


class BowlbugSilk(ScriptedEnemy):
    NAME, HP = 'Bowlbug Silk', (40, 43)
    MOVES = (Intent('debuff', 1, 'Spit', status_name='weak', status_stacks=1), attack('Thrash', 4, 2))


class BowlbugRock(ScriptedEnemy):
    NAME, HP = 'Bowlbug Rock', (45, 48)
    MOVES = (attack('Headbutt', 15), Intent('stun', 0, 'Dizzy'))

    def __init__(self, rng):
        super().__init__(rng)
        self.off_balance = False

    def after_attack_blocked(self, fully_blocked):
        if fully_blocked:
            self.off_balance = True

    def advance_intent(self):
        self._intent_index = int(self._intent_index == 0 and self.off_balance)

    def _possible_next_templates(self):
        return self.MOVES if self._intent_index == 0 else self.MOVES[:1]

    def after_move(self, player, intent):
        if intent.move_name == 'Dizzy':
            self.off_balance = False


class Chomper(ScriptedEnemy):
    NAME, HP = 'Chomper', (60, 64)
    MOVES = (attack('Clamp', 8, 2), Intent('shuffle', 3, 'Screech', discard_cards=('dazed',) * 3))

    def __init__(self, rng, *, scream_first=False):
        super().__init__(rng)
        self._intent_index = int(scream_first)
        self.statuses.add('artifact', 2)


class Exoskeleton(ScriptedEnemy):
    NAME, HP = 'Exoskeleton', (24, 28)
    MOVES = (attack('Skitter', 1, 3), attack('Mandibles', 8), Intent('buff', 2, 'Enrage', strength_gain=2))

    def __init__(self, rng, *, opening=0):
        super().__init__(rng)
        self._intent_index = branch(self.rng, (0, 1)) if opening == 3 else opening

    def damage_amount(self, *args, **kwargs):
        return min(9, super().damage_amount(*args, **kwargs))

    def advance_intent(self):
        self._intent_index = 2 if self._intent_index == 1 else branch(self.rng, tuple(i for i in (0, 1) if i != self._intent_index))

    def _possible_next_templates(self):
        return (self.MOVES[2],) if self._intent_index == 1 else tuple(m for i, m in enumerate(self.MOVES[:2]) if i != self._intent_index)


class HunterKiller(ScriptedEnemy):
    NAME, HP = 'Hunter Killer', (121, 121)
    MOVES = (Intent('debuff', 1, 'Tenderizing Goop'), attack('Bite', 17), attack('Puncture', 7, 3))

    def __init__(self, rng):
        super().__init__(rng)
        self.repeats = 0

    def after_move(self, player, intent):
        if intent.move_name == 'Tenderizing Goop':
            from game.headless.powers.hive import debuff
            debuff(player, 'tender', 1)

    def advance_intent(self):
        candidates = tuple(i for i in (1, 2) if i != self._intent_index or (i == 2 and self.repeats < 2))
        next_index = branch(self.rng, candidates)
        self.repeats = self.repeats + 1 if self._intent_index == next_index else 1
        self._intent_index = next_index

    def _possible_next_templates(self):
        return tuple(self.MOVES[i] for i in (1, 2) if i != self._intent_index or (i == 2 and self.repeats < 2))


class LouseProgenitor(ScriptedEnemy):
    NAME, HP = 'Louse Progenitor', (134, 136)
    MOVES = (attack('Web Cannon', 9, status_name='frail', status_stacks=2),
             Intent('defend', 14, 'Curl and Grow', block_gain=14, strength_gain=5), attack('Pounce', 14))

    def __init__(self, rng):
        super().__init__(rng)
        self.curl_up = True
        self.curl_card = ''

    def after_received_damage(self, damage, *, is_attack, powered, attacker_statuses, pet):
        p = self.combat_player
        card = p.current_card if p is not None else None
        if self.is_alive and self.curl_up and is_attack and powered and card is not None and not self.curl_card:
            self.curl_card = card.instance_id

    def after_player_card(self, player):
        card = player.current_card
        if self.is_alive and card is not None and card.instance_id == self.curl_card:
            self.gain_block(self.ascension_value('CurlBlock', 14))
            self.curl_up = False
            self.curl_card = ''

    def on_damage_taken(self, damage, is_attack):
        if not self.is_alive:
            self.curl_card = ''

    def validate_combat_context(self, player):
        if self.curl_card and (not self.curl_up or self.curl_card not in player.rules.plays):
            raise ValueError('Unowned Curl Up card.')


class Myte(ScriptedEnemy):
    NAME, HP = 'Myte', (61, 67)
    MOVES = (Intent('shuffle', 2, 'Toxic'), attack('Bite', 13), attack('Suck', 4, strength_gain=2))

    def __init__(self, rng, *, opening=0):
        super().__init__(rng)
        self._intent_index = opening

    def after_move(self, player, intent):
        if intent.move_name == 'Toxic':
            from game.headless.powers.hive import generate
            generate(player, 'toxic', 'hand', 2)


class SpinyToad(Toadpole):
    NAME, HP = 'Spiny Toad', (116, 119)
    MOVES = (Intent('buff', 5, 'Protruding Spikes'), attack('Spike Explosion', 23), attack('Tongue Lash', 17))

    def __init__(self, rng):
        super().__init__(rng)
        self._intent_index = 0

    def before_move(self, player):
        pass

    def after_move(self, player, intent):
        if intent.move_name == 'Protruding Spikes':
            self.thorns += 5
        elif intent.move_name == 'Spike Explosion':
            self.thorns = max(0, self.thorns - 5)


class Tunneler(InterruptibleEnemy):
    NAME, HP = 'Tunneler', (87, 87)
    MOVES = (attack('Bite', 13), Intent('defend', 32, 'Burrow', block_gain=32), attack('Below', 23), Intent('stun', 0, 'Dizzy'))

    def __init__(self, rng):
        super().__init__(rng)
        self.burrowed = False
        self.block_before_hit = 0

    def start_turn(self):
        if not self.burrowed:
            super().start_turn()

    def before_received_damage(self, **kwargs):
        self.block_before_hit = self.block

    def after_received_damage(self, damage, **kwargs):
        if self.burrowed and self.block_before_hit > 0 and self.block == 0:
            self.capture_interrupted_move()
            self.burrowed = False
            self._intent_index = 3
        self.block_before_hit = 0

    def on_combat_state_changed(self, player):
        if self.is_alive and self.burrowed and self.block == 0:
            self.capture_interrupted_move()
            self.burrowed = False
            self._intent_index = 3

    def _possible_next_templates(self):
        return (self.MOVES[(1, 2, 2, 0)[self._intent_index]],)

    def after_move(self, player, intent):
        if intent.move_name == 'Burrow':
            self.burrowed = True

    def advance_intent(self):
        if not self.move_interrupted:
            self._intent_index = (1, 2, 2, 0)[self._intent_index]


class SlumberingBeetle(InterruptibleEnemy):
    NAME, HP = 'Slumbering Beetle', (86, 86)
    MOVES = (Intent('sleep', 0, 'Snore'), attack('Roll Out', 16, strength_gain=2), Intent('stun', 0, 'Wake Up'))

    def __init__(self, rng):
        super().__init__(rng)
        self.slumber = 3
        self.plating = self.block = self.ascension_value('PlatingAmount', 15)
        self.turns_started = 0

    def start_turn(self):
        super().start_turn()
        if self.turns_started:
            self.plating = max(0, self.plating - 1)
        self.turns_started += 1

    def after_received_damage(self, damage, **kwargs):
        if damage > 0 and self.slumber:
            self.slumber -= 1
            if not self.slumber and self.is_alive:
                self.capture_interrupted_move()
                self._intent_index = 2

    def after_move(self, player, intent):
        if intent.move_name == 'Wake Up':
            self.plating = 0

    def after_side_end(self):
        self.gain_block(self.plating)
        if self.slumber:
            self.slumber -= 1
            if not self.slumber:
                self.plating = 0
                self._intent_index = 1

    def _possible_next_templates(self):
        return self.MOVES[:2] if self._intent_index == 0 else (self.MOVES[1],)

    def advance_intent(self):
        if not self.move_interrupted and self._intent_index == 2:
            self._intent_index = 1
