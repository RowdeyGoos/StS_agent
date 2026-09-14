"""Native stream ownership behind the existing random-service interface.

Known native consumers share streams. Native startup consumes UpFront in game
order; explicitly authored compatibility profiles retain their fixture domains.
"""

from game.headless.core.native_rng import NativeRng, deterministic_hash

SCHEMA = "sts2_native_streams_v1"
ALIASES = {
    "reward_offer": "rewards",
    "reward_gold": "rewards",
    "potion_drop": "rewards",
    "reward_potion": "rewards",
    "reward_relic": "rewards",
    "relic.card_reward": "rewards",
    "relic.potion_reward": "rewards",
    "relic.power_reward": "rewards",
    "relic.reward": "rewards",
    "relic.lava_rock": "rewards",
    "relic.rare_card": "rewards",
    "relic.bundles": "rewards",
    "relic.neow_rewards": "rewards",
    "event.card_reward": "rewards",
    "event.relic": "rewards",
    "shop.stock": "shops",
    "shop.prices": "shops",
    "shop.potion": "shops",
    "treasure.relic": "treasure_room_relics",
    "treasure.gold": "rewards",
    "act1.unknown": "unknown_map_point",
    "act1.map": "act_1_map",
    "ancient.neow": "event:NEOW",
    "relic.curse": "niche",
    "relic.reward_enchantment": "niche",
    "card.transform": "transformations",
    "event.morphic_transform": "niche",
    "relic.pickup": "niche",
    "relic.potion_generation": "rewards",
}
COMBAT_STREAMS = (
    "shuffle",
    "combat_card_selection",
    "combat_targets",
    "combat_card_generation",
    "combat_potion_generation",
    "combat_energy_costs",
    "monster_ai",
    "niche",
)


class NativeRandomService:
    native = True

    def __init__(self, seed):
        if type(seed) not in (int, str):
            raise ValueError("Native run seed must be integer or text.")
        self._seed = seed
        self.root_seed = deterministic_hash(str(seed))
        self._streams = {}
        self.active_event = None

    @property
    def seed(self):
        return self._seed

    @property
    def stream_names(self):
        return tuple(sorted(self._streams))

    def _name(self, name):
        if not isinstance(name, str) or not name:
            raise ValueError("Invalid stream name.")
        if name in ALIASES:
            return ALIASES[name]
        if name.startswith("event.") and self.active_event is not None:
            return "event:" + self.active_event.upper()
        return name

    def stream(self, name):
        name = self._name(name)
        if name not in self._streams:
            salt = name.split(":", 1)[1] if name.startswith(("event:", "relic:")) else name
            self._streams[name] = NativeRng((self.root_seed + deterministic_hash(salt)) & 0xFFFFFFFF)
        return self._streams[name]

    def begin_event(self, name):
        self.active_event = name
        self._streams.pop("event:" + name.upper(), None)

    def request_count(self, name):
        rng = self._streams.get(self._name(name))
        return 0 if rng is None else rng.counter

    def randint(self, name, low, high):
        return self.stream(name).randint(low, high)

    def choice(self, name, values):
        if not values:
            raise ValueError("No eligible random choices.")
        return self.stream(name).choice(values)

    def random(self, name):
        return self.stream(name).next_float()

    def double(self, name):
        return self.stream(name).next_double()

    def shuffle(self, name, values):
        return self.stream(name).shuffle(values)

    def snapshot(self):
        return {
            "schema": SCHEMA,
            "seed": self.seed,
            "active_event": self.active_event,
            "streams": {n: r.getstate() for n, r in sorted(self._streams.items())},
        }

    def restore(self, data):
        if (
            not isinstance(data, dict)
            or set(data) != {"schema", "seed", "active_event", "streams"}
            or data["schema"] != SCHEMA
        ):
            raise ValueError("Invalid native random service snapshot.")
        trial = NativeRandomService(data["seed"])
        if data["active_event"] is not None and (
            not isinstance(data["active_event"], str) or not data["active_event"]
        ):
            raise ValueError("Invalid active event RNG owner.")
        trial.active_event = data["active_event"]
        if not isinstance(data["streams"], dict):
            raise ValueError("Invalid native streams.")
        for name, record in data["streams"].items():
            if trial._name(name) != name:
                raise ValueError("Aliased native streams must have one owner.")
            rng = trial.stream(name)
            seed = rng.seed
            rng.setstate(record)
            if rng.seed != seed:
                raise ValueError("Native stream seed differs from its owner.")
        self.__dict__.update(trial.__dict__)


def bind_combat(service, combat):
    """Check duplicate snapshot views, then restore the owning run/combat aliases."""
    deck = combat.player.deck
    bindings = {
        "monster_ai": combat.rng,
        "niche": deck.niche_rng,
        "shuffle": deck.rng,
        "combat_card_selection": deck.selection_rng,
        "combat_targets": deck.target_rng,
        "combat_card_generation": deck.generation_rng,
        "combat_potion_generation": deck.potion_rng,
        "combat_energy_costs": deck.energy_rng,
    }
    for name, rng in bindings.items():
        if name not in service._streams or rng.getstate() != service._streams[name].getstate():
            raise ValueError("Combat RNG differs from its owning run stream.")
    if len({id(r) for r in bindings.values()}) != len(bindings):
        raise ValueError("Independent combat domains cannot alias.")
    from game.headless.monsters.overgrowth import SimpleEnemy
    if any(type(enemy) is not SimpleEnemy and enemy.rng is not combat.rng for enemy in combat.enemies):
        raise ValueError("Enemy AI must use its owning combat stream.")
    service._streams.update(bindings)
    combat.native_streams = bindings
