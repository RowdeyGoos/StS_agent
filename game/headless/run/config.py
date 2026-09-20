"""Declared game settings and explicit content restrictions for playable routes."""

from dataclasses import dataclass
from game.headless.cards.pools import REWARD_CARDS, RARE_CARDS


@dataclass(frozen=True, slots=True)
class RunConfig:
    character: str = "ironclad"
    ascension: int = 0
    reward_cards: tuple[str, ...] = REWARD_CARDS
    reward_potions: tuple[str, ...] = ("fire_potion", "block_potion")

    boss_reward_cards: tuple[str, ...] = RARE_CARDS
    reward_relics: tuple[str, ...] = ("strawberry", "pear", "mango")
    shop_relics: tuple[str, ...] = ("strawberry", "pear", "mango")
    event_pool: tuple[str, ...] = ("jungle_maze_adventure", "aroma_of_chaos")
    relic_fallback: str | None = None
    act: str = "overgrowth"
    campaign: tuple[str, ...] = ()

    @property
    def first_act(self):
        return self.campaign[0] if self.campaign else self.act

    def __post_init__(self):
        object.__setattr__(self, 'campaign', tuple(self.campaign))
        if self.campaign not in ((), ('overgrowth', 'hive'), ('underdocks', 'hive'), ('overgrowth', 'hive', 'glory'), ('underdocks', 'hive', 'glory')):
            raise ValueError('Unsupported campaign sequence.')
        if self.campaign and self.act not in self.campaign:
            raise ValueError('Current act is outside the declared campaign.')
        if self.act not in ("overgrowth", "underdocks", "hive", "glory"):
            raise ValueError("Unsupported Act 1 location.")
        from game.headless.core.ascension import validate
        validate(self.ascension)
        if self.character != "ironclad":
            raise ValueError("Only Ironclad runs are implemented.")
        if self.relic_fallback not in (None, "circlet"):
            raise ValueError("Unsupported depleted relic pool fallback.")
        from game.headless.events.catalog import EVENTS
        if any(e not in EVENTS for e in self.event_pool):
            raise ValueError("Unsupported restricted event pool.")
        for name in ("reward_cards", "reward_potions", "reward_relics", "boss_reward_cards", "event_pool", "shop_relics"):
            values = tuple(getattr(self, name))
            if not values or any(not isinstance(v, str) or not v for v in values) or len(values) != len(set(values)):
                raise ValueError("Reward pools must contain distinct definition IDs.")
            object.__setattr__(self, name, values)
        from game.headless.relics.pools import SHOP_RELICS
        if any(name not in SHOP_RELICS for name in self.shop_relics):
            raise ValueError("Unsupported merchant relic pool.")
        if len(self.reward_cards) < 3 or len(self.boss_reward_cards) < 3:
            raise ValueError("The slice needs at least three card reward definitions.")
