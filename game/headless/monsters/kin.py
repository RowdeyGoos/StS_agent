"""The Kin boss group; followers are secondary enemies with distinct openings."""

from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy


class KinFollower(ScriptedEnemy):
    NAME, HP = "Kin Follower", (58, 59)
    MOVES = (Intent("attack", 5, "Quick Slash", attack_damage=5, attack_count=1),
             Intent("attack", 2, "Boomerang", attack_damage=2, attack_count=2),
             Intent("buff", 2, "Dance", strength_gain=2))

    def __init__(self, rng, *, starts_with_dance=False):
        super().__init__(rng)
        self._intent_index = 2 if starts_with_dance else 0
        self.statuses.add("minion", 1)


class KinPriest(ScriptedEnemy):
    NAME, HP = "Kin Priest", (190, 190)
    MOVES = (Intent("attack", 8, "Orb of Frailty", attack_damage=8, attack_count=1,
                    status_name="frail", status_stacks=1),
             Intent("attack", 8, "Orb of Weakness", attack_damage=8, attack_count=1,
                    status_name="weak", status_stacks=1),
             Intent("attack", 3, "Beam", attack_damage=3, attack_count=3),
             Intent("buff", 2, "Ritual", strength_gain=2))
