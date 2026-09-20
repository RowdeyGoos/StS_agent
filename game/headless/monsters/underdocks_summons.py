"""Underdocks summons retain stable combat slots, AI history and stolen loot."""
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.underdocks_normal import attack
from game.headless.encounters.randomness import summon
from game.headless.core.native_rng import NativeRng, single


def append_child(kind, parent, player, **kwargs):
    child = summon(kind, parent, player, **kwargs)
    child.combat_player = player
    player.combat_enemies.append(child)
    child.after_joining_combat(player)
    return child


class TwoTailedRat(ScriptedEnemy):
    NAME, HP = 'Two-Tailed Rat', (17, 21)
    MOVES = (attack('Scratch', 8), attack('Disease Bite', 6),
             Intent('debuff', 1, 'Screech', status_name='frail', status_stacks=1),
             Intent('summon', 1, 'Call for Backup'))

    def __init__(self, rng, *, opening=-1, position=4):
        super().__init__(rng)
        self._intent_index = max(0, opening)
        self.needs_opening = opening == -1
        self.position = position
        self.summon_delay = 2
        self.summon_count = 0
        self.summoned_once = False
        self.screech_cooldown = 0

    def after_joining_combat(self, player):
        if self.needs_opening:
            self._intent_index = self.choose_move(initial=True)
            self.needs_opening = False

    def can_summon(self):
        player = self.combat_player
        if player is None or self.summon_delay > 0 or self.summon_count >= 3:
            return False
        rats = [e for e in player.combat_enemies if isinstance(e, TwoTailedRat) and e.is_alive]
        return len(rats) < 5 and not any(e is not self and e._intent_index == 3 for e in rats)

    def weights(self, *, initial=False):
        can_summon = self.can_summon()
        weights = [single(1 / 12) if can_summon else 1.0] * 3 + [0.75 if can_summon else 0.0]
        if not initial:
            weights[self._intent_index] = 0.0
        if self.screech_cooldown:
            weights[2] = 0.0
        if self.summoned_once:
            weights[3] = 0.0
        return weights

    def choose_move(self, *, initial=False):
        weights = self.weights(initial=initial)
        total = 0.0
        for weight in weights:
            total = single(total + weight)
        roll = self.rng.next_float(0, total) if isinstance(self.rng, NativeRng) else self.rng.random() * total
        for index, weight in enumerate(weights):
            roll = single(roll - weight) if isinstance(self.rng, NativeRng) else roll - weight
            if roll <= 0:
                return index
        return 3

    def before_move(self, player):
        if self._intent_index != 3:
            self.summon_delay -= 1

    def after_move(self, player, intent):
        if intent.move_name != 'Call for Backup':
            return
        self.summoned_once = True
        rats = [e for e in player.combat_enemies if isinstance(e, TwoTailedRat) and e.is_alive]
        free = [i for i in range(5) if all(e.position != i for e in rats)]
        if free:
            append_child(TwoTailedRat, self, player, position=free[-1])
        rats = [e for e in player.combat_enemies if isinstance(e, TwoTailedRat) and e.is_alive]
        count = max(e.summon_count + 1 for e in rats)
        for rat in rats:
            rat.summon_count = count

    def advance_intent(self):
        self.screech_cooldown = 3 if self._intent_index == 2 else max(0, self.screech_cooldown - 1)
        self._intent_index = self.choose_move()

    def _possible_next_templates(self):
        return tuple(self.MOVES[i] for i, weight in enumerate(self.weights()) if weight)

    def validate_combat_context(self, player):
        if not 0 <= self.position < 5 or not 0 <= self.summon_count <= 3 or not 0 <= self.screech_cooldown <= 3:
            raise ValueError('Invalid rat summon history.')
        if self.is_alive and any(e is not self and isinstance(e, TwoTailedRat) and e.is_alive and e.position == self.position for e in player.combat_enemies):
            raise ValueError('Duplicate living rat position.')


class GasBomb(ScriptedEnemy):
    NAME, HP = 'Gas Bomb', (7, 7)
    MOVES = (attack('Explode', 8),)

    def __init__(self, rng, *, position=0):
        super().__init__(rng)
        self.position = position
        self.statuses.add('minion', 1)

    @property
    def turn_order(self):
        return self.position

    def validate_combat_context(self, player):
        if not 0 <= self.position < 5 or (self.is_alive and any(
                isinstance(e, GasBomb) and e is not self and e.is_alive and e.position == self.position
                for e in player.combat_enemies)):
            raise ValueError('Invalid Gas Bomb position.')

    def after_move(self, player, intent):
        self.take_unblockable_damage(self.hp)


class LivingFog(ScriptedEnemy):
    turn_order = 5
    NAME, HP = 'Living Fog', (80, 80)
    LOOP_START = 1
    MOVES = (attack('Advanced Gas', 8), attack('Bloat', 5), attack('Super Gas Blast', 8))

    def before_move(self, player):
        if self._intent_index == 1 and sum(isinstance(e, GasBomb) and e.is_alive for e in player.combat_enemies) < 5:
            occupied = {e.position for e in player.combat_enemies if isinstance(e, GasBomb) and e.is_alive}
            position = next(i for i in range(5) if i not in occupied)
            append_child(GasBomb, self, player, position=position)

    def after_move(self, player, intent):
        if intent.move_name == 'Advanced Gas':
            from game.headless.powers.underdocks import apply_smoggy
            apply_smoggy(player)


class SneakyGremlin(ScriptedEnemy):
    NAME, HP = 'Sneaky Gremlin', (10, 14)
    LOOP_START = 1
    MOVES = (Intent('stun', 0, 'Spawned'), attack('Tackle', 9))


class FatGremlin(ScriptedEnemy):
    NAME, HP = 'Fat Gremlin', (13, 17)
    LOOP_START = 1
    MOVES = (Intent('stun', 0, 'Spawned'), Intent('escape', 0, 'Flee'))

    def __init__(self, rng):
        super().__init__(rng)
        self.escaped = False
        self.stolen_gold = 0
        self.loot_returned = False

    @property
    def is_alive(self):
        return self.hp > 0 and not self.escaped

    def after_move(self, player, intent):
        if intent.move_name == 'Flee':
            self.escaped = True

    def on_combat_state_changed(self, player):
        if self.hp == 0 and not self.escaped:
            self.loot_returned = True


class GremlinMerc(ScriptedEnemy):
    NAME, HP = 'Gremlin Merc', (47, 49)
    MOVES = (attack('Gimme', 7, 2), attack('Double Smash', 6, 2), attack('Hehe', 8))

    def __init__(self, rng):
        super().__init__(rng)
        self.spawned = False
        self.stolen_gold = 0
        self.first_child_slot = -1

    @property
    def prevents_combat_end(self):
        return not self.spawned

    def after_move(self, player, intent):
        if player.is_alive:
            rules = player.rules
            stolen = min(20, rules.gold_available + rules.gold_gained - rules.gold_lost)
            rules.gold_lost += stolen
            self.stolen_gold += stolen
            if intent.move_name == 'Double Smash':
                player.apply_status('weak', 2, source=self)
            elif intent.move_name == 'Hehe':
                self.gain_strength(2)

    def on_combat_state_changed(self, player):
        if self.hp == 0 and not self.spawned:
            from game.headless.core.resolution import push
            task = ['monster_death', player.combat_enemies.index(self)]
            if task not in player.rules.tasks:
                push(player, task)

    @property
    def death_pending(self):
        return self.hp == 0 and not self.spawned

    def resolve_death(self, player):
        if not self.death_pending:
            raise ValueError("Unowned monster death continuation.")
        self.spawned = True
        self.first_child_slot = len(player.combat_enemies)
        append_child(SneakyGremlin, self, player)
        fat = append_child(FatGremlin, self, player)
        fat.stolen_gold = self.stolen_gold

    def validate_combat_context(self, player):
        if self.stolen_gold < 0 or self.is_alive and self.spawned:
            raise ValueError('Invalid Gremlin Merc state.')
        if self.spawned:
            children = player.combat_enemies[self.first_child_slot:self.first_child_slot + 2]
            if len(children) != 2 or not isinstance(children[0], SneakyGremlin) or not isinstance(children[1], FatGremlin) or children[1].stolen_gold != self.stolen_gold:
                raise ValueError('Missing Merc children or stolen gold.')
