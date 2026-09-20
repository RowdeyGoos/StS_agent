"""Overgrowth hallway rules with verified A0 values and move history."""

from game.headless.encounters.randomness import branch

from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy


class CubexConstruct(ScriptedEnemy):
    NAME, HP = "Cubex Construct", (65, 65)
    LOOP_START = 1
    BLAST = Intent("attack", 7, "Repeater Blast", attack_damage=7, attack_count=1, strength_gain=2)
    MOVES = (Intent("buff", 2, "Charge Up", strength_gain=2), BLAST, BLAST,
             Intent("attack", 5, "Expel Blast", attack_damage=5, attack_count=2))

    def __init__(self, rng):
        super().__init__(rng)
        # Native setup calls GainBlock before IsInProgress; that command returns
        # without granting block in the pinned build. Artifact still applies.
        self.statuses.add("artifact", 1)


class SnappingJaxfruit(ScriptedEnemy):
    NAME, HP = "Snapping Jaxfruit", (31, 33)
    MOVES = (Intent("attack", 3, "Energy Orb", attack_damage=3, attack_count=1, strength_gain=2),)


class VineShambler(ScriptedEnemy):
    NAME, HP = "Vine Shambler", (61, 61)
    MOVES = (Intent("attack", 6, "Swipe", attack_damage=6, attack_count=2),
             Intent("attack", 8, "Grasping Vines", attack_damage=8, attack_count=1,
                    status_name="tangled", status_stacks=1),
             Intent("attack", 16, "Chomp", attack_damage=16, attack_count=1))


class SlitheringStrangler(ScriptedEnemy):
    APPLIED_PLAYER_POWERS = ("constrict",)
    NAME, HP = "Slithering Strangler", (53, 55)
    MOVES = (Intent("debuff", 3, "Constrict", status_name="constrict", status_stacks=3),
             Intent("attack_defend", 7, "Thwack", attack_damage=7, attack_count=1, block_gain=5),
             Intent("attack", 12, "Lash", attack_damage=12, attack_count=1))

    def advance_intent(self):
        self._intent_index = branch(self.rng, (1, 2)) if self._intent_index == 0 else 0

    def _possible_next_templates(self):
        return self.MOVES[1:] if self._intent_index == 0 else self.MOVES[:1]


class Inklet(ScriptedEnemy):
    NAME, HP = "Inklet", (11, 17)
    MOVES = (Intent("attack", 3, "Jab", attack_damage=3, attack_count=1),
             Intent("attack", 2, "Whirlwind", attack_damage=2, attack_count=3),
             Intent("attack", 10, "Piercing Gaze", attack_damage=10, attack_count=1))

    def __init__(self, rng, *, middle=False):
        super().__init__(rng)
        self._intent_index = 1 if middle else 0
        self.statuses.add("slippery", 1)

    def advance_intent(self):
        self._intent_index = branch(self.rng, (2, 1)) if self._intent_index == 0 else 0

    def _possible_next_templates(self):
        return self.MOVES[1:] if self._intent_index == 0 else self.MOVES[:1]


class Flyconid(ScriptedEnemy):
    NAME, HP = "Flyconid", (47, 49)
    MOVES = (Intent("debuff", 2, "Vulnerable Spores", status_name="vulnerable", status_stacks=2),
             Intent("attack", 8, "Frail Spores", attack_damage=8, attack_count=1,
                    status_name="frail", status_stacks=2),
             Intent("attack", 11, "Smash", attack_damage=11, attack_count=1))

    def __init__(self, rng):
        super().__init__(rng)
        self.vulnerable_cooldown = 0
        self.frail_cooldown = 0
        self._intent_index = branch(rng, (1, 2))

    @property
    def intent(self):
        if (type(self.vulnerable_cooldown) is not int or not 0 <= self.vulnerable_cooldown <= 3
                or type(self.frail_cooldown) is not int or not 0 <= self.frail_cooldown <= 2):
            raise ValueError("Invalid Flyconid cooldown.")
        return super().intent

    def _next_indices(self):
        vulnerable = 3 if self._intent_index == 0 else max(0, self.vulnerable_cooldown - 1)
        frail = 2 if self._intent_index == 1 else max(0, self.frail_cooldown - 1)
        return vulnerable, frail, tuple(i for i in range(3) if i != self._intent_index
                                      and not (i == 0 and vulnerable) and not (i == 1 and frail))

    def advance_intent(self):
        self.vulnerable_cooldown, self.frail_cooldown, indices = self._next_indices()
        # Native NextFloat(0) still draws; its <=0 test selects the first branch
        # when every cooldown excludes a move (RandomBranchState 100681567).
        self._intent_index = branch(self.rng, indices or (0,))

    def _possible_next_templates(self):
        return tuple(self.MOVES[i] for i in (self._next_indices()[2] or (0,)))
