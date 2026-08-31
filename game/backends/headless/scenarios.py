"""Serializable named scenarios for the legacy combat backend.

This module is deliberately a small adapter around :class:`CombatEnvFactory`.
It does not add combat content or expose arbitrary Python factories.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import math
from typing import Any, ClassVar, Mapping

from game.simulation.deck_presets import SUPPORTED_DECKS
from game.simulation.env_factory import (
    SUPPORTED_ENCOUNTERS,
    CombatEnvFactory,
)

SCENARIO_SCHEMA = "combat_v0_scenario_v1"
SCENARIO_EVIDENCE = "combat_v0"

# These are stable, human-readable entry points for the closed factory surface.
# The descriptor remains useful for custom parameter values, while scenario IDs
# prevent callers from inventing combat factories or content.
SUPPORTED_SCENARIOS: tuple[str, ...] = tuple(
    f"{encounter}__{deck}"
    for encounter in SUPPORTED_ENCOUNTERS
    for deck in SUPPORTED_DECKS
)
_SCENARIO_IDS = frozenset(SUPPORTED_SCENARIOS)
_DEFAULT_ENEMY_HP = 40


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string.")
    return value


def _require_int(value: Any, name: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive.")
    return value


def _require_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number.")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be a finite, non-negative number.")
    return result


@dataclass(frozen=True, slots=True)
class CombatScenario:
    """A JSON-safe, deterministic configuration for one combat episode."""

    scenario_id: str
    encounter: str
    deck: str = "starter"
    player_max_hp: int = 80
    enemy_max_hp: int = _DEFAULT_ENEMY_HP
    cards_per_turn: int = 5
    hp_loss_penalty_scale: float = 1.0
    incoming_damage_shaping_scale: float = 0.0
    record_trajectory: bool = False
    seed: int = 0

    schema: ClassVar[str] = SCENARIO_SCHEMA
    evidence: ClassVar[str] = SCENARIO_EVIDENCE

    def __post_init__(self) -> None:
        scenario_id = _require_string(self.scenario_id, "scenario_id")
        encounter = _require_string(self.encounter, "encounter")
        deck = _require_string(self.deck, "deck")
        if scenario_id not in _SCENARIO_IDS:
            raise ValueError(f"Unsupported scenario_id: {scenario_id!r}.")
        if encounter not in SUPPORTED_ENCOUNTERS:
            raise ValueError(f"Unsupported encounter: {encounter!r}.")
        if deck not in SUPPORTED_DECKS:
            raise ValueError(f"Unsupported deck: {deck!r}.")
        if scenario_id != f"{encounter}__{deck}":
            raise ValueError("scenario_id must match encounter and deck.")
        _require_int(self.player_max_hp, "player_max_hp", positive=True)
        _require_int(self.enemy_max_hp, "enemy_max_hp", positive=True)
        _require_int(self.cards_per_turn, "cards_per_turn", positive=True)
        _require_number(self.hp_loss_penalty_scale, "hp_loss_penalty_scale")
        _require_number(
            self.incoming_damage_shaping_scale,
            "incoming_damage_shaping_scale",
        )
        if not isinstance(self.record_trajectory, bool):
            raise ValueError("record_trajectory must be a boolean.")
        _require_int(self.seed, "seed")
        if encounter != "simple" and self.enemy_max_hp != _DEFAULT_ENEMY_HP:
            raise ValueError("enemy_max_hp is only configurable for the simple encounter.")

    def to_dict(self) -> dict[str, Any]:
        """Return the strict JSON object representation of this descriptor."""
        result = asdict(self)
        result["schema"] = self.schema
        result["evidence"] = self.evidence
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CombatScenario":
        """Decode a descriptor and reject unknown or missing fields."""
        if not isinstance(payload, Mapping):
            raise ValueError("Scenario payload must be an object.")
        expected = {field.name for field in fields(cls)} | {"schema", "evidence"}
        unknown = set(payload) - expected
        missing = expected - set(payload)
        if unknown:
            raise ValueError(f"Unknown scenario fields: {sorted(unknown)!r}.")
        if missing:
            raise ValueError(f"Missing scenario fields: {sorted(missing)!r}.")
        if payload["schema"] != SCENARIO_SCHEMA:
            raise ValueError(f"Unsupported scenario schema: {payload['schema']!r}.")
        if payload["evidence"] != SCENARIO_EVIDENCE:
            raise ValueError(f"Unsupported scenario evidence: {payload['evidence']!r}.")
        values = {field.name: payload[field.name] for field in fields(cls)}
        return cls(**values)

    def build(self):
        """Construct and seed a fresh existing ``CombatEnv`` instance."""
        factory = CombatEnvFactory(
            encounter_set=self.encounter,
            enemy_hp=self.enemy_max_hp,
            player_hp=self.player_max_hp,
            cards_per_turn=self.cards_per_turn,
            hp_loss_penalty_scale=self.hp_loss_penalty_scale,
            incoming_damage_shaping_scale=self.incoming_damage_shaping_scale,
            record_trajectory=self.record_trajectory,
            deck=self.deck,
        )
        environment = factory()
        environment.reset(seed=self.seed)
        return environment


def scenario_from_id(scenario_id: str, **overrides: Any) -> CombatScenario:
    """Create a named scenario, optionally replacing validated settings."""
    _require_string(scenario_id, "scenario_id")
    if scenario_id not in _SCENARIO_IDS:
        raise ValueError(f"Unsupported scenario_id: {scenario_id!r}.")
    encounter, deck = scenario_id.split("__", 1)
    values: dict[str, Any] = {
        "scenario_id": scenario_id,
        "encounter": encounter,
        "deck": deck,
    }
    values.update(overrides)
    return CombatScenario(**values)


def build_scenario(scenario: CombatScenario) -> Any:
    """Build a scenario after requiring the descriptor's concrete type."""
    if not isinstance(scenario, CombatScenario):
        raise TypeError("scenario must be a CombatScenario.")
    return scenario.build()
