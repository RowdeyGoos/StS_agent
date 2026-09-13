"""Phrog's death creates four primary Wrigglers before victory is possible."""

from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy


class Wriggler(ScriptedEnemy):
    NAME, HP = "Wriggler", (17, 21)
    MOVES = (Intent("stun", 0, "Spawned"),
             Intent("attack", 6, "Bite", attack_damage=6, attack_count=1),
             Intent("shuffle", 1, "Wriggle", discard_cards=("infection",), strength_gain=2))

    def __init__(self, rng, *, starts_with_wriggle=False, start_stunned=True):
        super().__init__(rng)
        self.opening = 2 if starts_with_wriggle else 1
        self._intent_index = 0 if start_stunned else self.opening

    @property
    def intent(self):
        if type(self.opening) is not int or self.opening not in (1, 2):
            raise ValueError("Invalid Wriggler opening.")
        return super().intent

    def advance_intent(self):
        self._intent_index = self.opening if self._intent_index == 0 else 3 - self._intent_index

    def _possible_next_templates(self):
        return (self.MOVES[self.opening if self._intent_index == 0 else 3 - self._intent_index],)


class PhrogParasite(ScriptedEnemy):
    NAME, HP = "Phrog Parasite", (61, 64)
    MOVES = (Intent("shuffle", 3, "Infect", discard_cards=("infection",) * 3),
             Intent("attack", 4, "Lash", attack_damage=4, attack_count=4))

    def __init__(self, rng):
        super().__init__(rng)
        self.statuses.add("infested", 4)
        self.spawned = False
        self.first_child_slot = -1

    def on_damage_taken(self, damage, is_attack):
        if self.combat_player is not None:
            self.on_combat_state_changed(self.combat_player)

    def on_combat_state_changed(self, player):
        if self.is_alive or self.spawned or not self.statuses.get("infested"):
            return
        self.spawned = True
        self.first_child_slot = len(player.combat_enemies)
        for index in range(4):
            child = Wriggler(self.rng, starts_with_wriggle=index % 2 == 1)
            child.combat_player = player
            player.combat_enemies.append(child)

    def validate_combat_context(self, player):
        if self.is_alive:
            if self.spawned or self.first_child_slot != -1:
                raise ValueError("Living Phrog cannot already have spawned its parasites.")
        else:
            children = player.combat_enemies[self.first_child_slot:self.first_child_slot + 4]
            if (not self.spawned or self.first_child_slot <= player.combat_enemies.index(self)
                    or len(children) != 4 or any(not isinstance(child, Wriggler) for child in children)):
                raise ValueError("Dead Phrog requires its four owned parasite slots.")
