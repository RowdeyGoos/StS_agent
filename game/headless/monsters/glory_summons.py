"""Glory replacement lives and Fabricator's stable, ordered summon slots."""
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.underdocks_normal import attack
from game.headless.monsters.underdocks_summons import append_child
from game.headless.encounters.randomness import branch


class Axebot(ScriptedEnemy):
    NAME, HP = 'Axebot', (70, 78)
    MOVES = (Intent('defend', 10, 'Boot Up', block_gain=10), attack('Hammer Uppercut', 12), attack('One Two', 9, 2))

    def __init__(self, rng, *, stock=2, replacement=False):
        super().__init__(rng)
        self.stock = stock
        self.replaced = False
        self.child_slot = -1
        self._intent_index = 0 if replacement else 1

    @property
    def prevents_combat_end(self): return not self.is_alive and self.stock > 0 and not self.replaced

    def on_combat_state_changed(self, player):
        if not self.is_alive and self.stock > 0 and not self.replaced:
            from game.headless.core.resolution import push
            task = ['monster_death', player.combat_enemies.index(self)]
            if task not in player.rules.tasks:
                push(player, task)

    @property
    def death_pending(self):
        return not self.is_alive and self.stock > 0 and not self.replaced

    def resolve_death(self, player):
        if not self.death_pending:
            raise ValueError('Unowned Axebot replacement.')
        self.replaced = True
        self.child_slot = len(player.combat_enemies)
        append_child(Axebot, self, player, stock=self.stock - 1, replacement=True)

    def after_move(self, player, intent):
        if intent.move_name == 'Boot Up': self.gain_strength(3 * (2 - self.stock))
        elif intent.move_name == 'Hammer Uppercut':
            player.apply_status('weak', 2, source=self)
            player.apply_status('frail', 2, source=self)

    def advance_intent(self): self._intent_index = 2 if self._intent_index == 1 else 1
    def _possible_next_templates(self): return (self.MOVES[2 if self._intent_index == 1 else 1],)

    def validate_combat_context(self, player):
        if not 0 <= self.stock <= 2 or self.replaced and self.is_alive:
            raise ValueError('Invalid Axebot stock.')
        if self.replaced:
            slot = player.combat_enemies.index(self)
            if not slot < self.child_slot < len(player.combat_enemies):
                raise ValueError('Missing Axebot replacement.')
            child = player.combat_enemies[self.child_slot]
            if not isinstance(child, Axebot) or child.stock != self.stock - 1:
                raise ValueError('Invalid Axebot replacement stock.')
        elif self.child_slot != -1:
            raise ValueError('Unexpected Axebot replacement receipt.')


class Bot(ScriptedEnemy):
    def __init__(self, rng, *, position=0):
        super().__init__(rng)
        self.position = position
        self.statuses.add('minion', 1)

    @property
    def turn_order(self): return self.position

    def validate_combat_context(self, player):
        if self.position not in (0, 1, 3, 4): raise ValueError('Invalid Fabricator bot slot.')
        if self.is_alive and any(e is not self and isinstance(e, Bot) and e.is_alive and e.position == self.position for e in player.combat_enemies):
            raise ValueError('Duplicate living Fabricator slot.')


class Zapbot(Bot):
    NAME, HP = 'Zapbot', (18, 23)
    MOVES = (attack('Zap', 14),)
    def after_side_end(self): self.gain_strength(2)


class Stabbot(Bot):
    NAME, HP = 'Stabbot', (18, 23)
    MOVES = (attack('Stab', 11, status_name='frail', status_stacks=1),)


class Guardbot(Bot):
    NAME, HP = 'Guardbot', (16, 20)
    MOVES = (Intent('defend', 15, 'Guard'),)
    def after_move(self, player, intent):
        for enemy in player.combat_enemies:
            if isinstance(enemy, Fabricator) and enemy.is_alive: enemy.gain_block(15)


class Noisebot(Bot):
    NAME, HP = 'Noisebot', (18, 23)
    MOVES = (Intent('shuffle', 2, 'Noise'),)
    def after_move(self, player, intent):
        from game.headless.powers.hive import generate
        generate(player, 'dazed', 'discard_pile', 1)
        generate(player, 'dazed', 'draw_pile', 1, random_position=True)


class Fabricator(ScriptedEnemy):
    NAME, HP = 'Fabricator', (150, 150)
    MOVES = (Intent('summon', 2, 'Fabricate'), attack('Fabricating Strike', 18), attack('Disintegrate', 11))
    turn_order = 2

    def __init__(self, rng):
        super().__init__(rng)
        self.last_spawn = ''
        self._intent_index = branch(self.rng, (0, 1))

    def spawn(self, player, kinds):
        used = {e.position for e in player.combat_enemies if isinstance(e, Bot) and e.is_alive}
        free = [i for i in (0, 1, 3, 4) if i not in used]
        if not free: return
        kind = self.rng.choice([k for k in kinds if k.__name__ != self.last_spawn])
        self.last_spawn = kind.__name__
        append_child(kind, self, player, position=free[0])

    def after_move(self, player, intent):
        if intent.move_name == 'Fabricate': self.spawn(player, (Guardbot, Noisebot))
        if intent.move_name in ('Fabricate', 'Fabricating Strike'): self.spawn(player, (Zapbot, Stabbot))

    def next_indices(self):
        return (2,) if self.combat_player is not None and sum(e.is_alive for e in self.combat_player.combat_enemies) >= 4 else (0, 1)

    def advance_intent(self):
        choices = self.next_indices()
        self._intent_index = choices[0] if choices == (2,) else branch(self.rng, choices)

    def _possible_next_templates(self): return tuple(self.MOVES[i] for i in self.next_indices())

    def validate_combat_context(self, player):
        if self.last_spawn not in ('', 'Guardbot', 'Noisebot', 'Zapbot', 'Stabbot'): raise ValueError('Invalid Fabricator history.')
