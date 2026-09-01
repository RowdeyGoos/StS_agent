"""Private persistent state for the provisional reduced headless run.

The types in this module are engine-owned continuation state.  They are not
public observations, policy inputs, or representations of a live-game save.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any

from game.contracts.headless_v0 import (
    CONTRACT_FINGERPRINT,
    CombatOutcome,
    DecisionPhase,
    NodeKind,
    RunOutcome,
)
from game.engine.random_service import (
    RANDOM_SERVICE_SCHEMA,
    RANDOM_SERVICE_SNAPSHOT_VERSION,
    GameRandomService,
)


WORLD_STATE_SCHEMA = "reduced_world_state_v0"
WORLD_STATE_VERSION = 1
WORLD_SEMANTIC_KEY_VERSION = "reduced_world_state_v0.semantic_key.v1"
COMBAT_HANDOFF_VERSION = "reduced_world_state_v0.combat_handoff.v1"
RNG_STREAM_MAP_VERSION = "reduced_world_state_v0.rng_stream_map.v1"

COMBAT_LAUNCH_STREAM = "combat_launch"
REWARD_OFFER_STREAM = "reward_offer"
EVENT_EFFECT_STREAM = "event_effect"
WORLD_RNG_STREAMS = MappingProxyType(
    {
        "combat_launch": COMBAT_LAUNCH_STREAM,
        "event_effect": EVENT_EFFECT_STREAM,
        "reward_offer": REWARD_OFFER_STREAM,
    }
)

_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SEMANTIC_ID_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_ALLOCATED_ID_PATTERN = re.compile(
    r"(?P<kind>run|card|map)\.(?P<namespace>[0-9a-f]{16})\.(?P<ordinal>[0-9]{8})\Z"
)
_PRIVATE_JSON_SCALAR_TYPES = (str, int, bool, type(None))
_MAX_COMBAT_SEED = (1 << 63) - 1
_IDENTITY_CAPACITY = 100_000_000


class StateValidationError(ValueError):
    """Raised when private state or a combat handoff is invalid."""


def _validate_integer(value: Any, path: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StateValidationError(f"{path} must be an integer.")
    if minimum is not None and value < minimum:
        raise StateValidationError(f"{path} must be at least {minimum}.")
    return value


def _validate_identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise StateValidationError(f"{path} must be a non-empty opaque identifier.")
    return value


def _validate_semantic_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SEMANTIC_ID_PATTERN.fullmatch(value) is None:
        raise StateValidationError(f"{path} must be a lower-case semantic ID.")
    return value


def _validate_fingerprint(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise StateValidationError(f"{path} must be a lower-case SHA-256 digest.")
    return value


def _validate_unicode(value: str, path: str) -> str:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise StateValidationError(f"{path} cannot contain an unpaired surrogate.")
    return value


def _freeze_private_json(value: Any, path: str = "payload") -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise StateValidationError(f"{path} keys must be strings.")
            _validate_unicode(key, f"{path} key")
            frozen[key] = _freeze_private_json(item, f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_private_json(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if not isinstance(value, _PRIVATE_JSON_SCALAR_TYPES) or isinstance(value, float):
        raise StateValidationError(f"{path} must contain only JSON-safe primitives.")
    if isinstance(value, str):
        _validate_unicode(value, path)
    return value


def _thaw_private_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_private_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_private_json(item) for item in value]
    return value


def canonical_private_json(value: Mapping[str, Any]) -> str:
    """Serialize private engine data with stable, integer-only JSON rules."""
    frozen = _freeze_private_json(value)
    return json.dumps(
        _thaw_private_json(frozen),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _domain_hash(domain: str, value: Mapping[str, Any]) -> str:
    payload = f"{domain}\0{canonical_private_json(value)}".encode("utf-8")
    return sha256(payload).hexdigest()


_STATE_SCHEMA_DESCRIPTOR = {
    "schema": WORLD_STATE_SCHEMA,
    "version": WORLD_STATE_VERSION,
    "semantic_key_version": WORLD_SEMANTIC_KEY_VERSION,
    "combat_handoff_version": COMBAT_HANDOFF_VERSION,
    "rng_stream_map_version": RNG_STREAM_MAP_VERSION,
    "rng_streams": dict(WORLD_RNG_STREAMS),
    "rng_compatibility": {
        "schema": RANDOM_SERVICE_SCHEMA,
        "snapshot_version": RANDOM_SERVICE_SNAPSHOT_VERSION,
    },
    "fields": (
        "active_combat_launch_key",
        "automatic_queue",
        "content_fingerprint",
        "contract_fingerprint",
        "current_hp",
        "current_node_id",
        "gold",
        "identity_allocator",
        "map_nodes",
        "master_deck",
        "max_hp",
        "node_history",
        "pending_decision",
        "phase",
        "rng",
        "rules_fingerprint",
        "run_id",
        "terminal_result",
    ),
}
WORLD_STATE_FINGERPRINT = _domain_hash(
    "reduced_world_state_v0.schema.v1", _STATE_SCHEMA_DESCRIPTOR
)


def _identity_namespace(seed: int) -> str:
    return sha256(f"reduced_world_state_v0.identity\0{seed}".encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class StableIdAllocator:
    """Sole allocator and structural validator for durable reduced-run IDs."""

    namespace: str
    next_run_ordinal: int = 0
    next_card_ordinal: int = 0
    next_map_ordinal: int = 0
    run_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or re.fullmatch(
            r"[0-9a-f]{16}", self.namespace
        ) is None:
            raise StateValidationError("identity_allocator.namespace is invalid.")
        for name in ("next_run_ordinal", "next_card_ordinal", "next_map_ordinal"):
            value = _validate_integer(getattr(self, name), f"identity_allocator.{name}", minimum=0)
            if value > _IDENTITY_CAPACITY:
                raise StateValidationError(f"identity_allocator.{name} is exhausted.")
        if self.run_id is None:
            if self.next_run_ordinal != 0:
                raise StateValidationError(
                    "An allocator without a run must have a zero run counter."
                )
        else:
            if self.next_run_ordinal != 1:
                raise StateValidationError(
                    "The one-run allocator must have run counter exactly one."
                )
            self.validate_run_id(self.run_id)

    @classmethod
    def for_seed(cls, seed: int) -> "StableIdAllocator":
        _validate_integer(seed, "seed")
        return cls(namespace=_identity_namespace(seed))

    def _allocate(self, kind: str, counter_name: str) -> str:
        ordinal = getattr(self, counter_name)
        if ordinal >= _IDENTITY_CAPACITY:
            raise StateValidationError(f"{kind} identity space is exhausted.")
        identifier = f"{kind}.{self.namespace}.{ordinal:08d}"
        setattr(self, counter_name, ordinal + 1)
        return identifier

    def allocate_run_id(self) -> str:
        if self.run_id is not None or self.next_run_ordinal != 0:
            raise StateValidationError("This allocator already owns a run ID.")
        self.run_id = self._allocate("run", "next_run_ordinal")
        return self.run_id

    def allocate_card_id(self) -> str:
        self._require_run()
        return self._allocate("card", "next_card_ordinal")

    def allocate_map_id(self) -> str:
        self._require_run()
        return self._allocate("map", "next_map_ordinal")

    def _require_run(self) -> None:
        if self.run_id is None:
            raise StateValidationError("A run ID must be allocated first.")

    def _validate_allocated(self, value: Any, kind: str, next_ordinal: int) -> str:
        identifier = _validate_identifier(value, f"{kind}_id")
        match = _ALLOCATED_ID_PATTERN.fullmatch(identifier)
        if (
            match is None
            or match.group("kind") != kind
            or match.group("namespace") != self.namespace
        ):
            raise StateValidationError(f"{kind}_id was not allocated by this state kernel.")
        ordinal = int(match.group("ordinal"))
        if ordinal >= next_ordinal:
            raise StateValidationError(f"{kind}_id has not been allocated yet.")
        return identifier

    def validate_run_id(self, value: Any) -> str:
        identifier = self._validate_allocated(value, "run", self.next_run_ordinal)
        if self.run_id is None or identifier != self.run_id:
            raise StateValidationError("run_id does not identify this run.")
        return identifier

    def validate_card_id(self, value: Any) -> str:
        return self._validate_allocated(value, "card", self.next_card_ordinal)

    def validate_map_id(self, value: Any) -> str:
        return self._validate_allocated(value, "map", self.next_map_ordinal)

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "next_card_ordinal": self.next_card_ordinal,
            "next_map_ordinal": self.next_map_ordinal,
            "next_run_ordinal": self.next_run_ordinal,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StableIdAllocator":
        _require_fields(
            value,
            {
                "namespace",
                "next_card_ordinal",
                "next_map_ordinal",
                "next_run_ordinal",
                "run_id",
            },
            "identity_allocator",
        )
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class PersistentCardInstance:
    instance_id: str
    definition_id: str
    upgraded: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.instance_id, "card.instance_id")
        _validate_semantic_id(self.definition_id, "card.definition_id")
        if not isinstance(self.upgraded, bool):
            raise StateValidationError("card.upgraded must be a boolean.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "instance_id": self.instance_id,
            "upgraded": self.upgraded,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PersistentCardInstance":
        _require_fields(value, {"definition_id", "instance_id", "upgraded"}, "card")
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class MapNodeInstance:
    instance_id: str
    definition_id: str
    node_kind: NodeKind

    def __post_init__(self) -> None:
        _validate_identifier(self.instance_id, "map_node.instance_id")
        _validate_semantic_id(self.definition_id, "map_node.definition_id")
        try:
            normalized = NodeKind(self.node_kind)
        except (TypeError, ValueError) as error:
            raise StateValidationError("map_node.node_kind is invalid.") from error
        object.__setattr__(self, "node_kind", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "instance_id": self.instance_id,
            "node_kind": self.node_kind.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MapNodeInstance":
        _require_fields(value, {"definition_id", "instance_id", "node_kind"}, "map_node")
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class PendingDecision:
    decision_kind: str
    sequence: int
    private_context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_semantic_id(self.decision_kind, "pending_decision.decision_kind")
        _validate_integer(self.sequence, "pending_decision.sequence", minimum=0)
        object.__setattr__(
            self,
            "private_context",
            _freeze_private_json(self.private_context, "pending_decision.private_context"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_kind": self.decision_kind,
            "private_context": _thaw_private_json(self.private_context),
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PendingDecision":
        _require_fields(
            value,
            {"decision_kind", "private_context", "sequence"},
            "pending_decision",
        )
        context = value["private_context"]
        if not isinstance(context, Mapping):
            raise StateValidationError("pending_decision.private_context must be an object.")
        return cls(
            decision_kind=value["decision_kind"],
            sequence=value["sequence"],
            private_context=context,
        )


@dataclass(frozen=True, slots=True)
class AutomaticTransition:
    transition_kind: str
    private_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_semantic_id(self.transition_kind, "automatic_transition.transition_kind")
        object.__setattr__(
            self,
            "private_payload",
            _freeze_private_json(self.private_payload, "automatic_transition.private_payload"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "private_payload": _thaw_private_json(self.private_payload),
            "transition_kind": self.transition_kind,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AutomaticTransition":
        _require_fields(
            value,
            {"private_payload", "transition_kind"},
            "automatic_transition",
        )
        payload = value["private_payload"]
        if not isinstance(payload, Mapping):
            raise StateValidationError("automatic_transition.private_payload must be an object.")
        return cls(value["transition_kind"], payload)


@dataclass(frozen=True, slots=True)
class TerminalResult:
    outcome: RunOutcome
    reason: str

    def __post_init__(self) -> None:
        try:
            normalized = RunOutcome(self.outcome)
        except (TypeError, ValueError) as error:
            raise StateValidationError("terminal_result.outcome is invalid.") from error
        object.__setattr__(self, "outcome", normalized)
        _validate_semantic_id(self.reason, "terminal_result.reason")

    def to_dict(self) -> dict[str, str]:
        return {"outcome": self.outcome.value, "reason": self.reason}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TerminalResult":
        _require_fields(value, {"outcome", "reason"}, "terminal_result")
        return cls(value["outcome"], value["reason"])


@dataclass(frozen=True, slots=True)
class CombatLaunchSpec:
    run_id: str
    scenario_id: str
    combat_seed: int
    current_hp: int
    max_hp: int
    combat_settings: Mapping[str, Any]
    ordered_deck: tuple[PersistentCardInstance, ...]
    handoff_version: str = COMBAT_HANDOFF_VERSION

    def __post_init__(self) -> None:
        if self.handoff_version != COMBAT_HANDOFF_VERSION:
            raise StateValidationError("Unsupported combat handoff version.")
        _validate_identifier(self.run_id, "combat_launch.run_id")
        _validate_semantic_id(self.scenario_id, "combat_launch.scenario_id")
        current_hp = _validate_integer(self.current_hp, "combat_launch.current_hp", minimum=1)
        max_hp = _validate_integer(self.max_hp, "combat_launch.max_hp", minimum=1)
        if current_hp > max_hp:
            raise StateValidationError("combat_launch.current_hp cannot exceed max_hp.")
        seed = _validate_integer(self.combat_seed, "combat_launch.combat_seed", minimum=0)
        if seed > _MAX_COMBAT_SEED:
            raise StateValidationError("combat_launch.combat_seed is outside the supported range.")
        object.__setattr__(
            self,
            "combat_settings",
            _freeze_private_json(self.combat_settings, "combat_launch.combat_settings"),
        )
        deck = tuple(self.ordered_deck)
        if not deck or any(not isinstance(card, PersistentCardInstance) for card in deck):
            raise StateValidationError(
                "combat_launch.ordered_deck must contain persistent card instances."
            )
        if len({card.instance_id for card in deck}) != len(deck):
            raise StateValidationError("combat_launch.ordered_deck contains duplicate IDs.")
        object.__setattr__(self, "ordered_deck", deck)

    def to_dict(self) -> dict[str, Any]:
        return {
            "combat_seed": self.combat_seed,
            "combat_settings": _thaw_private_json(self.combat_settings),
            "current_hp": self.current_hp,
            "handoff_version": self.handoff_version,
            "max_hp": self.max_hp,
            "ordered_deck": [card.to_dict() for card in self.ordered_deck],
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CombatLaunchSpec":
        _require_fields(
            value,
            {
                "combat_seed",
                "combat_settings",
                "current_hp",
                "handoff_version",
                "max_hp",
                "ordered_deck",
                "run_id",
                "scenario_id",
            },
            "combat_launch",
        )
        settings = value["combat_settings"]
        deck = value["ordered_deck"]
        if not isinstance(settings, Mapping):
            raise StateValidationError("combat_launch.combat_settings must be an object.")
        if not isinstance(deck, list) or not all(isinstance(item, Mapping) for item in deck):
            raise StateValidationError("combat_launch.ordered_deck must be an array of objects.")
        return cls(
            run_id=value["run_id"],
            scenario_id=value["scenario_id"],
            combat_seed=value["combat_seed"],
            current_hp=value["current_hp"],
            max_hp=value["max_hp"],
            combat_settings=settings,
            ordered_deck=tuple(PersistentCardInstance.from_dict(item) for item in deck),
            handoff_version=value["handoff_version"],
        )

    def to_json(self) -> str:
        return canonical_private_json(self.to_dict())

    @classmethod
    def from_json(cls, text: str | bytes | bytearray) -> "CombatLaunchSpec":
        return cls.from_dict(_load_private_object(text))

    def semantic_key(self) -> str:
        return _domain_hash("reduced_world_state_v0.combat_launch.v1", self.to_dict())


@dataclass(frozen=True, slots=True)
class CombatResolution:
    run_id: str
    launch_key: str
    outcome: CombatOutcome
    final_hp: int
    replay_reference: str
    handoff_version: str = COMBAT_HANDOFF_VERSION

    def __post_init__(self) -> None:
        if self.handoff_version != COMBAT_HANDOFF_VERSION:
            raise StateValidationError("Unsupported combat handoff version.")
        _validate_identifier(self.run_id, "combat_resolution.run_id")
        _validate_fingerprint(self.launch_key, "combat_resolution.launch_key")
        try:
            outcome = CombatOutcome(self.outcome)
        except (TypeError, ValueError) as error:
            raise StateValidationError("combat_resolution.outcome is invalid.") from error
        if outcome is CombatOutcome.ONGOING:
            raise StateValidationError("A combat resolution cannot be ongoing.")
        object.__setattr__(self, "outcome", outcome)
        final_hp = _validate_integer(self.final_hp, "combat_resolution.final_hp", minimum=0)
        if outcome is CombatOutcome.DEFEAT and final_hp != 0:
            raise StateValidationError("A defeat resolution must have zero final HP.")
        if outcome is CombatOutcome.VICTORY and final_hp == 0:
            raise StateValidationError("A victory resolution must retain positive HP.")
        _validate_identifier(self.replay_reference, "combat_resolution.replay_reference")

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_hp": self.final_hp,
            "handoff_version": self.handoff_version,
            "launch_key": self.launch_key,
            "outcome": self.outcome.value,
            "replay_reference": self.replay_reference,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CombatResolution":
        _require_fields(
            value,
            {
                "final_hp",
                "handoff_version",
                "launch_key",
                "outcome",
                "replay_reference",
                "run_id",
            },
            "combat_resolution",
        )
        return cls(**dict(value))

    def to_json(self) -> str:
        return canonical_private_json(self.to_dict())

    @classmethod
    def from_json(cls, text: str | bytes | bytearray) -> "CombatResolution":
        return cls.from_dict(_load_private_object(text))


@dataclass(slots=True)
class WorldState:
    """Minimal authoritative persistent state for one reduced run."""

    content_fingerprint: str
    rules_fingerprint: str
    identity_allocator: StableIdAllocator
    run_id: str
    current_hp: int
    max_hp: int
    gold: int
    master_deck: tuple[PersistentCardInstance, ...]
    phase: DecisionPhase
    map_nodes: tuple[MapNodeInstance, ...]
    current_node_id: str | None
    node_history: tuple[str, ...]
    pending_decision: PendingDecision | None
    terminal_result: TerminalResult | None
    automatic_queue: tuple[AutomaticTransition, ...]
    rng: GameRandomService
    active_combat_launch_key: str | None = None
    contract_fingerprint: str = CONTRACT_FINGERPRINT
    schema: str = WORLD_STATE_SCHEMA
    state_version: int = WORLD_STATE_VERSION

    def __post_init__(self) -> None:
        self.master_deck = tuple(self.master_deck)
        self.map_nodes = tuple(self.map_nodes)
        self.node_history = tuple(self.node_history)
        self.automatic_queue = tuple(self.automatic_queue)
        try:
            self.phase = DecisionPhase(self.phase)
        except (TypeError, ValueError) as error:
            raise StateValidationError("world.phase is invalid.") from error
        self.validate()

    @classmethod
    def create(
        cls,
        *,
        seed: int,
        current_hp: int,
        max_hp: int,
        gold: int,
        deck_definition_ids: Sequence[str],
        map_node_definitions: Sequence[tuple[str, NodeKind]],
        content_fingerprint: str,
        rules_fingerprint: str,
        phase: DecisionPhase = DecisionPhase.COMBAT,
    ) -> "WorldState":
        rng = GameRandomService(seed)
        allocator = StableIdAllocator.for_seed(seed)
        run_id = allocator.allocate_run_id()
        cards = tuple(
            PersistentCardInstance(allocator.allocate_card_id(), definition_id)
            for definition_id in deck_definition_ids
        )
        nodes = tuple(
            MapNodeInstance(allocator.allocate_map_id(), definition_id, node_kind)
            for definition_id, node_kind in map_node_definitions
        )
        return cls(
            content_fingerprint=content_fingerprint,
            rules_fingerprint=rules_fingerprint,
            identity_allocator=allocator,
            run_id=run_id,
            current_hp=current_hp,
            max_hp=max_hp,
            gold=gold,
            master_deck=cards,
            phase=phase,
            map_nodes=nodes,
            current_node_id=None,
            node_history=(),
            pending_decision=None,
            terminal_result=None,
            automatic_queue=(),
            rng=rng,
            active_combat_launch_key=None,
        )

    def validate(self) -> None:
        if self.schema != WORLD_STATE_SCHEMA:
            raise StateValidationError("World state schema identity is incompatible.")
        state_version = _validate_integer(self.state_version, "world.state_version", minimum=0)
        if state_version != WORLD_STATE_VERSION:
            raise StateValidationError("World state schema identity is incompatible.")
        if self.contract_fingerprint != CONTRACT_FINGERPRINT:
            raise StateValidationError("World state contract fingerprint is incompatible.")
        try:
            self.phase = DecisionPhase(self.phase)
        except (TypeError, ValueError) as error:
            raise StateValidationError("world.phase is invalid.") from error
        self.master_deck = tuple(self.master_deck)
        self.map_nodes = tuple(self.map_nodes)
        self.node_history = tuple(self.node_history)
        self.automatic_queue = tuple(self.automatic_queue)
        _validate_fingerprint(self.content_fingerprint, "world.content_fingerprint")
        _validate_fingerprint(self.rules_fingerprint, "world.rules_fingerprint")
        if not isinstance(self.identity_allocator, StableIdAllocator):
            raise StateValidationError("world.identity_allocator has the wrong type.")
        if not isinstance(self.rng, GameRandomService):
            raise StateValidationError("world.rng has the wrong type.")
        if self.identity_allocator.namespace != _identity_namespace(self.rng.seed):
            raise StateValidationError("Identity namespace does not match the world RNG seed.")
        if (
            self.identity_allocator.run_id != self.run_id
            or self.identity_allocator.next_run_ordinal != 1
        ):
            raise StateValidationError(
                "World run ID does not match the one-run identity allocator."
            )
        self.identity_allocator.validate_run_id(self.run_id)
        current_hp = _validate_integer(self.current_hp, "world.current_hp", minimum=0)
        max_hp = _validate_integer(self.max_hp, "world.max_hp", minimum=1)
        if current_hp > max_hp:
            raise StateValidationError("world.current_hp cannot exceed max_hp.")
        _validate_integer(self.gold, "world.gold", minimum=0)
        if not self.master_deck:
            raise StateValidationError("world.master_deck must not be empty.")
        if any(not isinstance(card, PersistentCardInstance) for card in self.master_deck):
            raise StateValidationError("world.master_deck has an invalid card.")
        card_ids = [card.instance_id for card in self.master_deck]
        if len(set(card_ids)) != len(card_ids):
            raise StateValidationError("world.master_deck contains duplicate card IDs.")
        for card_id in card_ids:
            self.identity_allocator.validate_card_id(card_id)
        if any(not isinstance(node, MapNodeInstance) for node in self.map_nodes):
            raise StateValidationError("world.map_nodes has an invalid node.")
        map_ids = [node.instance_id for node in self.map_nodes]
        if len(set(map_ids)) != len(map_ids):
            raise StateValidationError("world.map_nodes contains duplicate node IDs.")
        for map_id in map_ids:
            self.identity_allocator.validate_map_id(map_id)
        known_map_ids = set(map_ids)
        if self.current_node_id is not None:
            current_node_id = self.identity_allocator.validate_map_id(self.current_node_id)
            if current_node_id not in known_map_ids:
                raise StateValidationError("world.current_node_id is not a known map node.")
        for node_id in self.node_history:
            validated_node_id = self.identity_allocator.validate_map_id(node_id)
            if validated_node_id not in known_map_ids:
                raise StateValidationError(
                    "world.node_history references an unknown map node."
                )
        if self.pending_decision is not None and not isinstance(
            self.pending_decision, PendingDecision
        ):
            raise StateValidationError("world.pending_decision has the wrong type.")
        if self.terminal_result is not None and not isinstance(
            self.terminal_result, TerminalResult
        ):
            raise StateValidationError("world.terminal_result has the wrong type.")
        if (self.phase is DecisionPhase.TERMINAL) != (self.terminal_result is not None):
            raise StateValidationError("Terminal phase and terminal result must match.")
        if any(not isinstance(item, AutomaticTransition) for item in self.automatic_queue):
            raise StateValidationError("world.automatic_queue has an invalid transition.")
        if self.active_combat_launch_key is not None:
            _validate_fingerprint(
                self.active_combat_launch_key,
                "world.active_combat_launch_key",
            )
            if self.phase is not DecisionPhase.COMBAT:
                raise StateValidationError(
                    "An active combat launch requires the combat phase."
                )

    def add_card(self, definition_id: str, *, upgraded: bool = False) -> PersistentCardInstance:
        self.validate()
        _validate_semantic_id(definition_id, "card.definition_id")
        if not isinstance(upgraded, bool):
            raise StateValidationError("card.upgraded must be a boolean.")
        card = PersistentCardInstance(
            self.identity_allocator.allocate_card_id(), definition_id, upgraded
        )
        self.master_deck += (card,)
        self.validate()
        return card

    def add_map_node(self, definition_id: str, node_kind: NodeKind) -> MapNodeInstance:
        self.validate()
        _validate_semantic_id(definition_id, "map_node.definition_id")
        try:
            normalized_node_kind = NodeKind(node_kind)
        except (TypeError, ValueError) as error:
            raise StateValidationError("map_node.node_kind is invalid.") from error
        node = MapNodeInstance(
            self.identity_allocator.allocate_map_id(), definition_id, normalized_node_kind
        )
        self.map_nodes += (node,)
        self.validate()
        return node

    def rng_stream_counters(self) -> dict[str, int]:
        return {
            logical_name: self.rng.request_count(stream_name)
            for logical_name, stream_name in WORLD_RNG_STREAMS.items()
        }

    def create_combat_launch(
        self,
        scenario_id: str,
        *,
        combat_settings: Mapping[str, Any] | None = None,
    ) -> CombatLaunchSpec:
        self.validate()
        if self.phase is not DecisionPhase.COMBAT:
            raise StateValidationError("Combat can only launch from the combat phase.")
        if self.current_hp <= 0:
            raise StateValidationError("Combat cannot launch with zero HP.")
        if self.active_combat_launch_key is not None:
            raise StateValidationError("A combat launch is already active.")
        _validate_semantic_id(scenario_id, "combat_launch.scenario_id")
        settings = {} if combat_settings is None else combat_settings
        _freeze_private_json(settings, "combat_launch.combat_settings")
        combat_seed = self.rng.randint(COMBAT_LAUNCH_STREAM, 0, _MAX_COMBAT_SEED)
        launch = CombatLaunchSpec(
            run_id=self.run_id,
            scenario_id=scenario_id,
            combat_seed=combat_seed,
            current_hp=self.current_hp,
            max_hp=self.max_hp,
            combat_settings=settings,
            ordered_deck=self.master_deck,
        )
        self.active_combat_launch_key = launch.semantic_key()
        return launch

    def validate_combat_launch(self, launch: CombatLaunchSpec) -> None:
        if not isinstance(launch, CombatLaunchSpec):
            raise StateValidationError("launch has the wrong type.")
        self.validate()
        if self.phase is not DecisionPhase.COMBAT:
            raise StateValidationError("World is not at a combat boundary.")
        if launch.run_id != self.run_id:
            raise StateValidationError("Combat launch belongs to another run.")
        if launch.current_hp != self.current_hp or launch.max_hp != self.max_hp:
            raise StateValidationError("Combat launch HP does not match persistent state.")
        if launch.ordered_deck != self.master_deck:
            raise StateValidationError("Combat launch deck does not match persistent state.")
        if self.active_combat_launch_key is None:
            raise StateValidationError("No combat launch is active.")
        if launch.semantic_key() != self.active_combat_launch_key:
            raise StateValidationError("Combat launch does not match the active issued launch.")

    def apply_combat_resolution(
        self,
        launch: CombatLaunchSpec,
        resolution: CombatResolution,
    ) -> None:
        """Apply the slice's sole combat-produced persistent delta: final HP."""
        self.validate_combat_launch(launch)
        if not isinstance(resolution, CombatResolution):
            raise StateValidationError("resolution has the wrong type.")
        if resolution.run_id != self.run_id:
            raise StateValidationError("Combat resolution belongs to another run.")
        if resolution.launch_key != launch.semantic_key():
            raise StateValidationError("Combat resolution does not bind to this launch.")
        if resolution.final_hp > self.max_hp:
            raise StateValidationError("Combat resolution final HP exceeds persistent max HP.")
        self.current_hp = resolution.final_hp
        self.active_combat_launch_key = None
        self.validate()

    def to_private_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "active_combat_launch_key": self.active_combat_launch_key,
            "automatic_queue": [item.to_dict() for item in self.automatic_queue],
            "content_fingerprint": self.content_fingerprint,
            "contract_fingerprint": self.contract_fingerprint,
            "current_hp": self.current_hp,
            "current_node_id": self.current_node_id,
            "gold": self.gold,
            "identity_allocator": self.identity_allocator.to_dict(),
            "map_nodes": [node.to_dict() for node in self.map_nodes],
            "master_deck": [card.to_dict() for card in self.master_deck],
            "max_hp": self.max_hp,
            "node_history": list(self.node_history),
            "pending_decision": (
                None if self.pending_decision is None else self.pending_decision.to_dict()
            ),
            "phase": self.phase.value,
            "rng": self.rng.snapshot(),
            "rules_fingerprint": self.rules_fingerprint,
            "run_id": self.run_id,
            "schema": self.schema,
            "state_version": self.state_version,
            "terminal_result": (
                None if self.terminal_result is None else self.terminal_result.to_dict()
            ),
        }

    @classmethod
    def from_private_dict(cls, value: Mapping[str, Any]) -> "WorldState":
        fields = {
            "active_combat_launch_key",
            "automatic_queue",
            "content_fingerprint",
            "contract_fingerprint",
            "current_hp",
            "current_node_id",
            "gold",
            "identity_allocator",
            "map_nodes",
            "master_deck",
            "max_hp",
            "node_history",
            "pending_decision",
            "phase",
            "rng",
            "rules_fingerprint",
            "run_id",
            "schema",
            "state_version",
            "terminal_result",
        }
        _require_fields(value, fields, "world")
        allocator = value["identity_allocator"]
        cards = value["master_deck"]
        nodes = value["map_nodes"]
        history = value["node_history"]
        queue = value["automatic_queue"]
        rng_snapshot = value["rng"]
        if not isinstance(allocator, Mapping) or not isinstance(rng_snapshot, Mapping):
            raise StateValidationError("World allocator and RNG must be objects.")
        for name, collection in (
            ("master_deck", cards),
            ("map_nodes", nodes),
            ("automatic_queue", queue),
        ):
            if not isinstance(collection, list) or not all(
                isinstance(item, Mapping) for item in collection
            ):
                raise StateValidationError(f"world.{name} must be an array of objects.")
        if not isinstance(history, list) or not all(isinstance(item, str) for item in history):
            raise StateValidationError("world.node_history must be an array of IDs.")
        pending_value = value["pending_decision"]
        terminal_value = value["terminal_result"]
        if pending_value is not None and not isinstance(pending_value, Mapping):
            raise StateValidationError("world.pending_decision must be null or an object.")
        if terminal_value is not None and not isinstance(terminal_value, Mapping):
            raise StateValidationError("world.terminal_result must be null or an object.")
        rng = GameRandomService(seed=0)
        try:
            rng.restore(rng_snapshot)
        except ValueError as error:
            raise StateValidationError("world.rng snapshot is invalid.") from error
        return cls(
            content_fingerprint=value["content_fingerprint"],
            rules_fingerprint=value["rules_fingerprint"],
            identity_allocator=StableIdAllocator.from_dict(allocator),
            run_id=value["run_id"],
            current_hp=value["current_hp"],
            max_hp=value["max_hp"],
            gold=value["gold"],
            master_deck=tuple(PersistentCardInstance.from_dict(item) for item in cards),
            phase=value["phase"],
            map_nodes=tuple(MapNodeInstance.from_dict(item) for item in nodes),
            current_node_id=value["current_node_id"],
            node_history=tuple(history),
            pending_decision=(
                None if pending_value is None else PendingDecision.from_dict(pending_value)
            ),
            terminal_result=(
                None if terminal_value is None else TerminalResult.from_dict(terminal_value)
            ),
            automatic_queue=tuple(AutomaticTransition.from_dict(item) for item in queue),
            rng=rng,
            active_combat_launch_key=value["active_combat_launch_key"],
            contract_fingerprint=value["contract_fingerprint"],
            schema=value["schema"],
            state_version=value["state_version"],
        )

    def semantic_key(self) -> str:
        return _domain_hash(WORLD_SEMANTIC_KEY_VERSION, self.to_private_dict())


def _require_fields(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    if not isinstance(value, Mapping):
        raise StateValidationError(f"{path} must be an object.")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise StateValidationError(
            f"{path} fields do not match the schema; missing={missing}, extra={extra}."
        )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StateValidationError(f"Duplicate JSON field: {key!r}.")
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise StateValidationError(f"Floating-point JSON is not supported: {value!r}.")


def _reject_constant(value: str) -> None:
    raise StateValidationError(f"Non-finite JSON is not supported: {value!r}.")


def _load_private_object(text: str | bytes | bytearray) -> dict[str, Any]:
    if not isinstance(text, (str, bytes, bytearray)):
        raise StateValidationError("JSON input must be text or bytes.")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise StateValidationError("Invalid private-state JSON.") from error
    if not isinstance(value, dict):
        raise StateValidationError("Private-state JSON root must be an object.")
    _freeze_private_json(value)
    return value
