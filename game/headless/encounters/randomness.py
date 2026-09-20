"""Encounter-local composition and run-owned creature HP/AI sources."""

from game.headless.core.native_rng import NativeRng, deterministic_hash, single


class MonsterConstruction:
    """Short-lived constructor inputs; only the AI RNG is retained by monsters."""

    def __init__(self, ai, hp, existing=()):
        self.ai = ai
        self.hp = hp
        self.used_hp = [enemy.max_hp for enemy in existing if enemy.is_alive]

    def initial_hp(self, low, high):
        eligible = [value for value in range(low, high + 1) if value not in self.used_hp]
        value = self.hp.choice(eligible) if eligible else self.hp.randint(low, high)
        self.used_hp.append(value)
        return value

    def __getattr__(self, name):
        return getattr(self.ai, name)


class EncounterRandom:
    def __init__(self, root_seed, floor, native_id, ai, hp):
        self.composition = NativeRng((root_seed + floor + deterministic_hash(native_id)) & 0xFFFFFFFF)
        self.monster = MonsterConstruction(ai, hp)

    def __getattr__(self, name):
        return getattr(self.composition, name)


def create(kind, rng, **kwargs):
    return kind(rng.monster if isinstance(rng, EncounterRandom) else rng, **kwargs)


def summon(kind, parent, player, **kwargs):
    rng = parent.rng
    if isinstance(rng, NativeRng):
        rng = MonsterConstruction(rng, player.deck.niche_rng, player.combat_enemies)
        # Native AfterDeath summons run before the dying parent is removed.
        # Earlier dead stable slots have already left the native creature list.
        if not parent.is_alive:
            rng.used_hp.append(parent.max_hp)
    enemy = kind(rng, **kwargs)
    from game.headless.relics.combat import has, owned, memory
    if has(player, "philosophers_stone"):
        enemy.strength += 1
    coat = owned(player, "fur_coat")
    if coat and memory(player, coat).get("active"):
        enemy.hp = 1
    return enemy


def branch(rng, values):
    """Equal-weight native RandomBranchState: float roll and <= cumulative weight."""
    source = rng.ai if isinstance(rng, MonsterConstruction) else rng
    if not isinstance(source, NativeRng):
        return source.choice(values)
    roll = source.next_float(0, len(values))
    for index, value in enumerate(values):
        if roll <= single(index + 1):
            return value
    return values[-1]
