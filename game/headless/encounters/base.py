"""Encounter composition and room reward metadata share one definition."""

from dataclasses import dataclass
from game.headless.monsters.base import EncounterFactory


@dataclass(frozen=True, slots=True)
class EncounterDefinition:
    factory: EncounterFactory
    room_kind: str = "combat"
    gold_range: tuple[int, int] = (10, 20)
    gives_relic: bool = False
    event_id: str | None = None
    act: int = 1

    def __call__(self, rng):
        return self.factory(rng)
