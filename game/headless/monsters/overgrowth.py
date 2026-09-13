"""Implemented reduced encounter enemies; native parity is incomplete."""

from random import Random
from types import MappingProxyType
from game.headless.monsters.base import Enemy, Intent


class SimpleEnemy(Enemy):
    """Single deterministic enemy used for early smoke tests."""

    INTENT_CYCLE: tuple[Intent, ...] = (
        Intent(kind="attack", value=6, move_name="Strike", attack_damage=6, attack_count=1),
        Intent(kind="defend", value=6, move_name="Defend", block_gain=6),
        Intent(kind="attack", value=8, move_name="Heavy Strike", attack_damage=8, attack_count=1),
    )

    def __init__(self, max_hp: int = 40, rng: Random | None = None) -> None:
        super().__init__(name="SimpleEnemy", max_hp=max_hp, rng=rng)
        self._intent_index = 0

    @property
    def intent(self) -> Intent:
        """Return the current deterministic intent."""
        return self._resolve_intent(self.INTENT_CYCLE[self._intent_index])

    def advance_intent(self) -> None:
        """Advance to the next intent in the repeating cycle."""
        self._intent_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)

    def _behavior_phase_index(self) -> int:
        return self._intent_index

    def _behavior_phase_count(self) -> int:
        return len(self.INTENT_CYCLE)

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        next_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)
        return (self.INTENT_CYCLE[next_index],)


class Nibbit(Enemy):
    """Solo Nibbit from the Overgrowth easy encounter pool."""

    INTENT_CYCLE: tuple[Intent, ...] = (
        Intent(kind="attack", value=12, move_name="Butt", attack_damage=12, attack_count=1),
        Intent(
            kind="attack_defend",
            value=6,
            move_name="Hesitant Slice",
            attack_damage=6,
            attack_count=1,
            block_gain=5,
        ),
        Intent(kind="buff", value=2, move_name="Hiss", strength_gain=2),
    )

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Nibbit", max_hp=rng.randint(42, 46), rng=rng)
        self._intent_index = 0

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self.INTENT_CYCLE[self._intent_index])

    def advance_intent(self) -> None:
        self._intent_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)

    def _behavior_phase_index(self) -> int:
        return self._intent_index

    def _behavior_phase_count(self) -> int:
        return len(self.INTENT_CYCLE)

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        next_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)
        return (self.INTENT_CYCLE[next_index],)


class ShrinkerBeetle(Enemy):
    """Shrinker Beetle from the Overgrowth easy encounter pool."""

    OPENING_INTENT = Intent(
        kind="debuff",
        value=1,
        move_name="Shrinker",
        status_name="shrink",
        status_stacks=1,
    )
    CHOMP = Intent(kind="attack", value=7, move_name="Chomp", attack_damage=7, attack_count=1)
    STOMP = Intent(kind="attack", value=13, move_name="Stomp", attack_damage=13, attack_count=1)

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Shrinker Beetle", max_hp=rng.randint(38, 40), rng=rng)
        self._used_opening = False
        self._post_opening_index = 0

    @property
    def intent(self) -> Intent:
        if not self._used_opening:
            return self._resolve_intent(self.OPENING_INTENT)
        return self._resolve_intent((self.CHOMP, self.STOMP)[self._post_opening_index])

    def advance_intent(self) -> None:
        if not self._used_opening:
            self._used_opening = True
            self._post_opening_index = 0
            return
        self._post_opening_index = 1 - self._post_opening_index

    def _behavior_phase_index(self) -> int:
        if not self._used_opening:
            return 0
        return 1 + self._post_opening_index

    def _behavior_phase_count(self) -> int:
        return 3

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        if not self._used_opening:
            return (self.CHOMP,)
        next_template = self.STOMP if self._post_opening_index == 0 else self.CHOMP
        return (next_template,)


class FuzzyWurmCrawler(Enemy):
    """Fuzzy Wurm Crawler from the Overgrowth easy encounter pool."""

    INTENT_CYCLE: tuple[Intent, ...] = (
        Intent(kind="attack", value=4, move_name="Acid Goop", attack_damage=4, attack_count=1),
        Intent(kind="buff", value=7, move_name="Inhale", strength_gain=7),
        Intent(kind="attack", value=4, move_name="Acid Goop", attack_damage=4, attack_count=1),
    )

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Fuzzy Wurm Crawler", max_hp=rng.randint(55, 57), rng=rng)
        self._intent_index = 0

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self.INTENT_CYCLE[self._intent_index])

    def advance_intent(self) -> None:
        self._intent_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)

    def _behavior_phase_index(self) -> int:
        return self._intent_index

    def _behavior_phase_count(self) -> int:
        return len(self.INTENT_CYCLE)

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        next_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)
        return (self.INTENT_CYCLE[next_index],)


class Mawler(Enemy):
    """Solo Mawler from the first partial Overgrowth hard benchmark."""

    CLAW = Intent(
        kind="attack",
        value=4,
        move_name="Claw",
        attack_damage=4,
        attack_count=2,
    )
    RIP_AND_TEAR = Intent(
        kind="attack",
        value=14,
        move_name="Rip and Tear",
        attack_damage=14,
        attack_count=1,
    )
    ROAR = Intent(
        kind="debuff",
        value=3,
        move_name="Roar",
        status_name="vulnerable",
        status_stacks=3,
    )
    MOVE_TEMPLATES: tuple[Intent, ...] = (CLAW, RIP_AND_TEAR, ROAR)

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Mawler", max_hp=72, rng=rng)
        self._current_intent = self.CLAW
        self._roar_used = False

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self._current_intent)

    def advance_intent(self) -> None:
        if self._current_intent.move_name == self.ROAR.move_name:
            self._roar_used = True
        self._current_intent = self.rng.choice(self._candidate_templates())

    def _candidate_templates(self) -> tuple[Intent, ...]:
        return tuple(
            template
            for template in self.MOVE_TEMPLATES
            if template.move_name != self._current_intent.move_name
            and not (self._roar_used and template.move_name == self.ROAR.move_name)
        )

    def _behavior_phase_index(self) -> int:
        if self._roar_used:
            return 3 if self._current_intent.move_name == self.CLAW.move_name else 4
        if self._current_intent.move_name == self.CLAW.move_name:
            return 0
        if self._current_intent.move_name == self.RIP_AND_TEAR.move_name:
            return 1
        return 2

    def _behavior_phase_count(self) -> int:
        return 5

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        return self._candidate_templates()


class LeafSlimeSmall(Enemy):
    """Small Leaf Slime from Overgrowth."""

    SNAPSHOT_FIELD_TYPES = MappingProxyType({"_last_move_name": (str, type(None))})

    TACKLE = Intent(kind="attack", value=3, move_name="Tackle", attack_damage=3, attack_count=1)
    GOOP = Intent(kind="shuffle", value=1, move_name="Goop", slimed_added=1)

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Leaf Slime (S)", max_hp=rng.randint(11, 15), rng=rng)
        self._last_move_name: str | None = None
        self._current_intent = self._choose_next_template()

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self._current_intent)

    def advance_intent(self) -> None:
        self._last_move_name = self._current_intent.move_name
        self._current_intent = self._choose_next_template()

    def _choose_next_template(self) -> Intent:
        # Native random branches roll even when repeat restrictions leave only
        # one available move. Python sampling is not native seed parity.
        roll = self.rng.random()
        if self._last_move_name is None:
            return self.TACKLE if roll < 0.5 else self.GOOP
        return self.GOOP if self._last_move_name == self.TACKLE.move_name else self.TACKLE

    def _behavior_phase_index(self) -> int:
        return 0 if self._current_intent.move_name == self.TACKLE.move_name else 1

    def _behavior_phase_count(self) -> int:
        return 2

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        next_template = (
            self.GOOP
            if self._current_intent.move_name == self.TACKLE.move_name
            else self.TACKLE
        )
        return (next_template,)


class LeafSlimeMedium(Enemy):
    """Medium Leaf Slime from Overgrowth."""

    INTENT_CYCLE: tuple[Intent, ...] = (
        Intent(kind="shuffle", value=2, move_name="Sticky Shot", slimed_added=2),
        Intent(kind="attack", value=8, move_name="Clump Shot", attack_damage=8, attack_count=1),
    )

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Leaf Slime (M)", max_hp=rng.randint(32, 35), rng=rng)
        self._intent_index = 0

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self.INTENT_CYCLE[self._intent_index])

    def advance_intent(self) -> None:
        self._intent_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)

    def _behavior_phase_index(self) -> int:
        return self._intent_index

    def _behavior_phase_count(self) -> int:
        return len(self.INTENT_CYCLE)

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        next_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)
        return (self.INTENT_CYCLE[next_index],)


class TwigSlimeSmall(Enemy):
    """Small Twig Slime from Overgrowth."""

    TACKLE = Intent(kind="attack", value=4, move_name="Tackle", attack_damage=4, attack_count=1)

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Twig Slime (S)", max_hp=rng.randint(7, 11), rng=rng)

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self.TACKLE)

    def advance_intent(self) -> None:
        return

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        return (self.TACKLE,)


class TwigSlimeMedium(Enemy):
    """Medium Twig Slime from Overgrowth."""

    STICKY_SHOT = Intent(kind="shuffle", value=1, move_name="Sticky Shot", slimed_added=1)
    CHOMP = Intent(kind="attack", value=11, move_name="Chomp", attack_damage=11, attack_count=1)

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Twig Slime (M)", max_hp=rng.randint(26, 28), rng=rng)
        self._current_intent = self.STICKY_SHOT
        self._consecutive_attacks = 0

    @property
    def intent(self) -> Intent:
        if (self._consecutive_attacks not in (0, 1, 2)
                or self._current_intent not in (self.STICKY_SHOT, self.CHOMP)
                or (self._current_intent == self.STICKY_SHOT) != (self._consecutive_attacks == 0)):
            raise ValueError("Invalid Twig Slime move/repeat state.")
        return self._resolve_intent(self._current_intent)

    def advance_intent(self) -> None:
        roll = self.rng.random()
        if self._current_intent.move_name == self.STICKY_SHOT.move_name:
            self._consecutive_attacks = 1
            self._current_intent = self.CHOMP
            return
        if self._consecutive_attacks < 2 and roll < 0.5:
            self._consecutive_attacks += 1
            self._current_intent = self.CHOMP
        else:
            self._consecutive_attacks = 0
            self._current_intent = self.STICKY_SHOT

    def _behavior_phase_index(self) -> int:
        return self._consecutive_attacks

    def _behavior_phase_count(self) -> int:
        return 3

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        if self._current_intent.move_name == self.STICKY_SHOT.move_name:
            return (self.CHOMP,)
        if self._consecutive_attacks == 2:
            return (self.STICKY_SHOT,)
        return (self.CHOMP, self.STICKY_SHOT)
