"""Declared game settings and explicit content restrictions for playable routes."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunConfig:
    character: str = "ironclad"
    ascension: int = 0
    reward_cards: tuple[str, ...] = ("pommel_strike", "shrug_it_off", "iron_wave", "body_slam", "armaments", "true_grit", "uppercut")
    reward_potions: tuple[str, ...] = ("fire_potion", "block_potion")

    boss_reward_cards: tuple[str, ...] = ("impervious", "offering", "fiend_fire")
    reward_relics: tuple[str, ...] = ("strawberry", "pear", "mango")
    event_pool: tuple[str, ...] = ("jungle_maze_adventure", "aroma_of_chaos")
    relic_fallback: str | None = None

    def __post_init__(self):
        if self.character != "ironclad" or type(self.ascension) is not int or self.ascension != 0:
            raise ValueError("Only Ironclad Ascension 0 is implemented.")
        if self.relic_fallback not in (None, "circlet"):
            raise ValueError("Unsupported depleted relic pool fallback.")
        from game.headless.events.catalog import EVENTS
        if any(e not in EVENTS for e in self.event_pool):
            raise ValueError("Unsupported restricted event pool.")
        for name in ("reward_cards", "reward_potions", "reward_relics", "boss_reward_cards", "event_pool"):
            values = tuple(getattr(self, name))
            if not values or any(not isinstance(v, str) or not v for v in values) or len(values) != len(set(values)):
                raise ValueError("Reward pools must contain distinct definition IDs.")
            object.__setattr__(self, name, values)
        if len(self.reward_cards) < 3 or len(self.boss_reward_cards) < 3:
            raise ValueError("The slice needs at least three card reward definitions.")
