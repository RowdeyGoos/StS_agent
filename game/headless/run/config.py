"""Declared game settings and explicit content restrictions for the first slice."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunConfig:
    character: str = "ironclad"
    ascension: int = 0
    reward_cards: tuple[str, ...] = ("pommel_strike", "shrug_it_off", "iron_wave", "body_slam")
    reward_potions: tuple[str, ...] = ("fire_potion", "block_potion")

    def __post_init__(self):
        if self.character != "ironclad" or type(self.ascension) is not int or self.ascension != 0:
            raise ValueError("Only Ironclad Ascension 0 is implemented.")
        for name in ("reward_cards", "reward_potions"):
            values = tuple(getattr(self, name))
            if not values or any(not isinstance(v, str) or not v for v in values) or len(values) != len(set(values)):
                raise ValueError("Reward pools must contain distinct definition IDs.")
            object.__setattr__(self, name, values)
        if len(self.reward_cards) < 3:
            raise ValueError("The slice needs at least three card reward definitions.")
