"""Pickle-friendly combat-environment factories shared by project CLIs."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from .core import CombatEnv
from .enemy import (
    Enemy,
    FuzzyWurmCrawler,
    Nibbit,
    ShrinkerBeetle,
    SimpleEnemy,
    build_overgrowth_easy_encounter,
    build_overgrowth_hard_v1_encounter,
    build_overgrowth_mawler_encounter,
    build_overgrowth_nibbits_encounter,
    build_overgrowth_shrinker_fuzzy_encounter,
    build_overgrowth_slimes_encounter,
)

SUPPORTED_TRAINING_ENCOUNTER_SETS: tuple[str, ...] = (
    "simple",
    "overgrowth_easy",
    "overgrowth_hard_v1",
)
SUPPORTED_FIXED_ENCOUNTERS: tuple[str, ...] = (
    "simple",
    "nibbit",
    "slimes",
    "shrinker_beetle",
    "fuzzy_wurm_crawler",
    "mawler",
    "nibbits",
    "shrinker_fuzzy",
)
SUPPORTED_ENCOUNTERS: tuple[str, ...] = tuple(
    dict.fromkeys(
        (*SUPPORTED_TRAINING_ENCOUNTER_SETS, *SUPPORTED_FIXED_ENCOUNTERS)
    )
)


def _build_nibbit_encounter(rng: Random) -> list[Enemy]:
    return [Nibbit(rng)]


def _build_shrinker_beetle_encounter(rng: Random) -> list[Enemy]:
    return [ShrinkerBeetle(rng)]


def _build_fuzzy_wurm_crawler_encounter(rng: Random) -> list[Enemy]:
    return [FuzzyWurmCrawler(rng)]


_FIXED_ENCOUNTER_FACTORIES = {
    "nibbit": _build_nibbit_encounter,
    "slimes": build_overgrowth_slimes_encounter,
    "shrinker_beetle": _build_shrinker_beetle_encounter,
    "fuzzy_wurm_crawler": _build_fuzzy_wurm_crawler_encounter,
    "mawler": build_overgrowth_mawler_encounter,
    "nibbits": build_overgrowth_nibbits_encounter,
    "shrinker_fuzzy": build_overgrowth_shrinker_fuzzy_encounter,
}


@dataclass(frozen=True, slots=True)
class CombatEnvFactory:
    """Create identically configured environments in local or worker processes."""

    encounter_set: str = "overgrowth_easy"
    enemy_hp: int = 40
    player_hp: int = 80
    cards_per_turn: int = 5
    hp_loss_penalty_scale: float = 1.0
    incoming_damage_shaping_scale: float = 0.0
    record_trajectory: bool = False

    def __call__(self) -> CombatEnv:
        if self.encounter_set == "simple":
            return CombatEnv(
                player_max_hp=self.player_hp,
                cards_per_turn=self.cards_per_turn,
                enemy_factory=_SimpleEnemyFactory(self.enemy_hp),
                hp_loss_penalty_scale=self.hp_loss_penalty_scale,
                incoming_damage_shaping_scale=self.incoming_damage_shaping_scale,
                record_trajectory=self.record_trajectory,
            )
        if self.encounter_set in {"overgrowth_easy", "overgrowth_hard_v1"}:
            encounter_factory = (
                build_overgrowth_easy_encounter
                if self.encounter_set == "overgrowth_easy"
                else build_overgrowth_hard_v1_encounter
            )
            return CombatEnv(
                player_max_hp=self.player_hp,
                cards_per_turn=self.cards_per_turn,
                encounter_factory=encounter_factory,
                max_enemy_count=3,
                hp_loss_penalty_scale=self.hp_loss_penalty_scale,
                incoming_damage_shaping_scale=self.incoming_damage_shaping_scale,
                record_trajectory=self.record_trajectory,
            )
        if self.encounter_set in _FIXED_ENCOUNTER_FACTORIES:
            return CombatEnv(
                player_max_hp=self.player_hp,
                cards_per_turn=self.cards_per_turn,
                encounter_factory=_FIXED_ENCOUNTER_FACTORIES[self.encounter_set],
                max_enemy_count=3,
                hp_loss_penalty_scale=self.hp_loss_penalty_scale,
                incoming_damage_shaping_scale=self.incoming_damage_shaping_scale,
                record_trajectory=self.record_trajectory,
            )
        raise ValueError(f"Unsupported encounter set: {self.encounter_set!r}")


@dataclass(frozen=True, slots=True)
class _SimpleEnemyFactory:
    max_hp: int

    def __call__(self) -> SimpleEnemy:
        return SimpleEnemy(max_hp=self.max_hp)
