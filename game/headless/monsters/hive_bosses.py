"""Hive bosses: an owned curse choice, Sandpit and the two Kaiser Crab arms."""
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.monsters.underdocks_normal import attack


class KnowledgeDemon(ScriptedEnemy):
    NAME, HP = 'Knowledge Demon', (379, 379)
    MOVES = (Intent('debuff', 1, 'Curse of Knowledge'), attack('Slap', 17),
             attack('Knowledge Overwhelming', 8, 3), attack('Ponder', 11, strength_gain=2))
    CURSES = ('mind_rot', 'sloth', 'waste_away')

    def __init__(self, rng):
        super().__init__(rng)
        self.curses_chosen = 0
        self.choice_pending = False

    def after_move(self, player, intent):
        if intent.move_name == 'Curse of Knowledge':
            from game.headless.cards.colorless_effects import catalog
            from game.headless.core.choices import begin
            cards = [catalog(player).create(n) for n in ('disintegration', self.CURSES[self.curses_chosen])]
            for card in cards:
                player.deck._ensure_identity(card)
            player.deck.offered.extend(cards)
            self.choice_pending = True
            begin(player, f'monster.{player.combat_enemies.index(self)}', cards, operation='hive_knowledge')
        elif intent.move_name == 'Ponder':
            self.hp = min(self.max_hp, self.hp + 30)

    def advance_intent(self):
        self._intent_index = 1 if self._intent_index == 3 and self.curses_chosen >= 3 else (self._intent_index + 1) % 4

    def _possible_next_templates(self):
        index = 1 if self._intent_index == 3 and self.curses_chosen >= 3 else (self._intent_index + 1) % 4
        return (self.MOVES[index],)

    def validate_combat_context(self, player):
        if not 0 <= self.curses_chosen <= 3 or (self.choice_pending and (self.curses_chosen == 3 or self._intent_index != 0)):
            raise ValueError('Invalid Knowledge Demon curse round.')
        if self.choice_pending:
            s = player.rules.selection
            if s is None or s['source'] != f'monster.{player.combat_enemies.index(self)}' or s['operation'] != 'hive_knowledge':
                raise ValueError('Knowledge Demon choice has no owner.')


class TheInsatiable(ScriptedEnemy):
    NAME, HP = 'The Insatiable', (321, 321)
    MOVES = (Intent('shuffle', 6, 'Liquify Ground'), attack('Thrash', 8, 2), attack('Lunging Bite', 28),
             Intent('buff', 2, 'Salivate', strength_gain=2), attack('Thrash', 8, 2))
    LOOP_START = 1

    def __init__(self, rng):
        super().__init__(rng)
        self.sandpit = 0
        self.liquified = False

    def after_move(self, player, intent):
        if intent.move_name == 'Liquify Ground':
            from game.headless.powers.hive import generate
            self.sandpit = 4
            self.liquified = True
            generate(player, 'frantic_escape', 'draw_pile', 3, random_position=True)
            generate(player, 'frantic_escape', 'discard_pile', 3, random_position=True)

    def validate_combat_context(self, player):
        if self.sandpit < 0 or (not self.liquified and self.sandpit):
            raise ValueError('Invalid Sandpit counter.')


class CrabArm(ScriptedEnemy):
    SIDE = 0

    def __init__(self, rng):
        super().__init__(rng)
        self.rage = True

    def on_teammate_death(self, other):
        if self.rage:
            self.gain_strength(6)
            self.gain_block(99)
            self.rage = False
        p = self.combat_player
        if p is not None and p.rules.powers.get('surrounded'):
            p.rules.auxiliaries['surrounded'] = self.SIDE


class Crusher(CrabArm):
    NAME, HP, SIDE = 'Crusher', (209, 209), 1
    MOVES = (attack('Thrash', 12), attack('Enlarging Strike', 4),
             attack('Bug Sting', 6, 2, status_name='weak', status_stacks=2),
             Intent('buff', 2, 'Adapt', strength_gain=2), attack('Guarded Strike', 12, block_gain=18))

    def after_move(self, player, intent):
        if intent.move_name == 'Bug Sting':
            player.apply_status('frail', 2, source=self)


class Rocket(CrabArm):
    NAME, HP, SIDE = 'Rocket', (199, 199), 0
    MOVES = (attack('Targeting Reticle', 3), attack('Precision Beam', 18),
             Intent('buff', 2, 'Charge Up', strength_gain=2), attack('Laser', 31), Intent('sleep', 0, 'Recharge'))

    def after_joining_combat(self, player):
        from game.headless.powers.hive import debuff
        debuff(player, 'surrounded', 1)
        if player.rules.powers.get('surrounded'):
            player.rules.auxiliaries['surrounded'] = 0
