"""Closed, project-authored content for the first reduced headless run.

This is a structural fixture, not a representation of target-game content or
probabilities.  It deliberately references the accepted ``combat_v0``
scenario adapter rather than defining another encounter registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Callable, Mapping

from game.backends.headless.scenarios import SUPPORTED_SCENARIOS, scenario_from_id
from game.simulation.card import (
    BashCard,
    BodySlamCard,
    Card,
    DefendCard,
    IronWaveCard,
    PommelStrikeCard,
    ShrugItOffCard,
    SlimedCard,
    StrikeCard,
)


CONTENT_VERSION = "reduced_content_v0"
CONTENT_EVIDENCE = "structural_fixture"

CardFactory = Callable[[], Card]


def create_strike_card() -> Card:
    return StrikeCard()


def create_defend_card() -> Card:
    return DefendCard()


def create_bash_card() -> Card:
    return BashCard()


def create_pommel_strike_card() -> Card:
    return PommelStrikeCard()


def create_shrug_it_off_card() -> Card:
    return ShrugItOffCard()


def create_iron_wave_card() -> Card:
    return IronWaveCard()


def create_body_slam_card() -> Card:
    return BodySlamCard()


def create_slimed_card() -> Card:
    return SlimedCard()


# Values are top-level functions so a worker may safely pickle the materializer
# and never needs to deserialize arbitrary callables from content payloads.
_CARD_FACTORY_REFERENCES: Mapping[str, CardFactory] = MappingProxyType({
    "strike": create_strike_card,
    "defend": create_defend_card,
    "bash": create_bash_card,
    "pommel_strike": create_pommel_strike_card,
    "shrug_it_off": create_shrug_it_off_card,
    "iron_wave": create_iron_wave_card,
    "body_slam": create_body_slam_card,
    "slimed": create_slimed_card,
})
# The public registry and its internal lookup are the same immutable mapping.
CARD_FACTORY_REFERENCES: Mapping[str, CardFactory] = _CARD_FACTORY_REFERENCES


def _require_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string.")
    return value


def _require_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return value


@dataclass(frozen=True, slots=True)
class CardDefinition:
    """A serializable reference to one supported combat-card factory."""

    definition_id: str
    card_name: str
    factory_id: str

    def __post_init__(self) -> None:
        _require_identifier(self.definition_id, "definition_id")
        _require_identifier(self.card_name, "card_name")
        if self.factory_id not in CARD_FACTORY_REFERENCES:
            raise ValueError(f"Unsupported card factory: {self.factory_id!r}.")

    def to_dict(self) -> dict[str, str]:
        return {
            "definition_id": self.definition_id,
            "card_name": self.card_name,
            "factory_id": self.factory_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CardDefinition":
        if not isinstance(payload, Mapping):
            raise ValueError("Card definition payload must be an object.")
        fields = {"definition_id", "card_name", "factory_id"}
        if set(payload) != fields:
            raise ValueError("Card definition fields must be exact.")
        return cls(
            definition_id=payload["definition_id"],
            card_name=payload["card_name"],
            factory_id=payload["factory_id"],
        )


SUPPORTED_CARD_DEFINITIONS: tuple[CardDefinition, ...] = (
    CardDefinition("strike", "Strike", "strike"),
    CardDefinition("defend", "Defend", "defend"),
    CardDefinition("bash", "Bash", "bash"),
    CardDefinition("pommel_strike", "Pommel Strike", "pommel_strike"),
    CardDefinition("shrug_it_off", "Shrug It Off", "shrug_it_off"),
    CardDefinition("iron_wave", "Iron Wave", "iron_wave"),
    CardDefinition("body_slam", "Body Slam", "body_slam"),
    # Supported for combat materialization only; it is not a persistent reward.
    CardDefinition("slimed", "Slimed", "slimed"),
)
_CARD_DEFINITIONS_BY_ID = {item.definition_id: item for item in SUPPORTED_CARD_DEFINITIONS}
# Persistent reward choices are deliberately closed and exclude generated/status
# cards such as Slimed even though combat can materialize them.
REWARDABLE_CARD_DEFINITION_IDS = frozenset(
    {
        "strike",
        "defend",
        "bash",
        "pommel_strike",
        "shrug_it_off",
        "iron_wave",
        "body_slam",
    }
)


def card_definition_from_dict(payload: Mapping[str, Any]) -> CardDefinition:
    """Decode one closed card definition and reject unregistered variants."""
    definition = CardDefinition.from_dict(payload)
    expected = _CARD_DEFINITIONS_BY_ID.get(definition.definition_id)
    if expected != definition:
        raise ValueError(f"Unsupported card definition: {definition.definition_id!r}.")
    return definition


def materialize_card_definition(definition: CardDefinition | Mapping[str, Any]) -> Card:
    """Build one deterministic ``combat_v0`` card from a closed definition."""
    if isinstance(definition, Mapping):
        definition = card_definition_from_dict(definition)
    if not isinstance(definition, CardDefinition):
        raise TypeError("definition must be a CardDefinition or JSON object.")
    expected = _CARD_DEFINITIONS_BY_ID.get(definition.definition_id)
    if expected != definition:
        raise ValueError(f"Unsupported card definition: {definition.definition_id!r}.")
    card = CARD_FACTORY_REFERENCES[definition.factory_id]()
    if card.name != definition.card_name:
        raise RuntimeError("Card factory does not match its closed definition.")
    return card


@dataclass(frozen=True, slots=True)
class MapNodeTemplate:
    node_id: str
    kind: str
    next_node_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier(self.node_id, "node_id")
        if self.kind not in {"combat", "rest", "event", "terminal"}:
            raise ValueError(f"Unsupported map node kind: {self.kind!r}.")
        if len(set(self.next_node_ids)) != len(self.next_node_ids):
            raise ValueError("Map node targets must be unique.")
        for node_id in self.next_node_ids:
            _require_identifier(node_id, "next_node_ids item")

    def to_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "kind": self.kind, "next_node_ids": list(self.next_node_ids)}


@dataclass(frozen=True, slots=True)
class MapTemplate:
    template_id: str
    nodes: tuple[MapNodeTemplate, ...]

    def __post_init__(self) -> None:
        _require_identifier(self.template_id, "template_id")
        if not self.nodes:
            raise ValueError("Map template must contain nodes.")
        ids = {node.node_id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Map node IDs must be unique.")
        if "start" not in ids:
            raise ValueError("Map template must have a start node.")
        for node in self.nodes:
            if not set(node.next_node_ids) <= ids:
                raise ValueError("Map node references an unknown target.")

    def to_dict(self) -> dict[str, Any]:
        return {"template_id": self.template_id, "nodes": [node.to_dict() for node in self.nodes]}


MAP_TEMPLATES: tuple[MapTemplate, ...] = (
    MapTemplate(
        "two_combat_rest",
        (
            MapNodeTemplate("start", "combat", ("rest_1", "event_1")),
            MapNodeTemplate("rest_1", "rest", ("combat_2",)),
            MapNodeTemplate("event_1", "event", ("combat_2",)),
            MapNodeTemplate("combat_2", "combat", ("finish",)),
            MapNodeTemplate("finish", "terminal", ()),
        ),
    ),
    MapTemplate(
        "short_rest_path",
        (
            MapNodeTemplate("start", "combat", ("rest_1",)),
            MapNodeTemplate("rest_1", "rest", ("finish",)),
            MapNodeTemplate("finish", "terminal", ()),
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class RewardTable:
    table_id: str
    gold_amount: int
    card_definition_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier(self.table_id, "table_id")
        _require_positive_int(self.gold_amount, "gold_amount")
        if not self.card_definition_ids:
            raise ValueError("Reward table must offer cards.")
        if not set(self.card_definition_ids) <= REWARDABLE_CARD_DEFINITION_IDS:
            raise ValueError("Reward table references unsupported persistent cards.")

    def to_dict(self) -> dict[str, Any]:
        return {"table_id": self.table_id, "gold_amount": self.gold_amount, "card_definition_ids": list(self.card_definition_ids)}


REWARD_TABLES: tuple[RewardTable, ...] = (
    RewardTable("combat_reward_basic", 25, ("strike", "defend", "bash")),
    RewardTable("combat_reward_sequence", 35, ("pommel_strike", "shrug_it_off", "iron_wave", "body_slam")),
)


@dataclass(frozen=True, slots=True)
class RestHealParameters:
    heal_amount: int

    def __post_init__(self) -> None:
        _require_positive_int(self.heal_amount, "heal_amount")

    def to_dict(self) -> dict[str, int]:
        return {"heal_amount": self.heal_amount}


REST_HEAL_PARAMETERS = RestHealParameters(heal_amount=15)


@dataclass(frozen=True, slots=True)
class SafeEventDefinition:
    event_id: str
    option_id: str
    effect_kind: str
    amount: int

    def __post_init__(self) -> None:
        _require_identifier(self.event_id, "event_id")
        _require_identifier(self.option_id, "option_id")
        if self.effect_kind not in {"heal", "gain_gold", "lose_hp"}:
            raise ValueError(f"Unsupported safe event effect: {self.effect_kind!r}.")
        _require_positive_int(self.amount, "amount")

    def to_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "option_id": self.option_id, "effect_kind": self.effect_kind, "amount": self.amount}


SAFE_EVENT_DEFINITIONS: tuple[SafeEventDefinition, ...] = (
    SafeEventDefinition("quiet_cache", "take_gold", "gain_gold", 20),
    SafeEventDefinition("cool_spring", "recover", "heal", 8),
)

# Content makes ordered references to the existing accepted scenario adapter;
# it intentionally does not duplicate its registry.
SCENARIO_REFERENCES: tuple[str, ...] = ("simple__starter", "nibbit__starter")
if not set(SCENARIO_REFERENCES) <= set(SUPPORTED_SCENARIOS):
    raise RuntimeError("Reduced content references unavailable combat scenarios.")


def resolve_scenario_reference(scenario_id: str):
    """Resolve a declared scenario through the accepted scenario adapter."""
    if scenario_id not in SCENARIO_REFERENCES:
        raise ValueError(f"Unsupported reduced-content scenario: {scenario_id!r}.")
    return scenario_from_id(scenario_id)


def content_manifest() -> dict[str, Any]:
    """Return the canonical, JSON-safe closed content manifest (without hash)."""
    return {
        "content_version": CONTENT_VERSION,
        "evidence": CONTENT_EVIDENCE,
        "cards": [item.to_dict() for item in SUPPORTED_CARD_DEFINITIONS],
        "scenario_references": list(SCENARIO_REFERENCES),
        "map_templates": [item.to_dict() for item in MAP_TEMPLATES],
        "reward_tables": [item.to_dict() for item in REWARD_TABLES],
        "rest_heal": REST_HEAL_PARAMETERS.to_dict(),
        "safe_events": [item.to_dict() for item in SAFE_EVENT_DEFINITIONS],
        "unsupported_content": ["shops", "potions", "upgrades", "procedural_maps", "broad_events"],
    }


def canonical_content_json() -> str:
    return json.dumps(content_manifest(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


CONTENT_FINGERPRINT = sha256(canonical_content_json().encode("utf-8")).hexdigest()


def manifest_with_fingerprint() -> dict[str, Any]:
    """Return the manifest with its stable SHA-256 fingerprint attached."""
    result = content_manifest()
    result["content_fingerprint"] = CONTENT_FINGERPRINT
    return result
