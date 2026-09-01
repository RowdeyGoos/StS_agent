"""Composed structural backend for the first reduced headless run.

This module owns only composition.  Combat, reward, map, room, persistent
state, and snapshot semantics remain with their accepted producers.  The
composer gives those private component lifecycles one authenticated public
``headless_v0`` envelope and never promotes structural fixtures to live truth.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields
from hashlib import sha256
from typing import Any, Mapping, Sequence

from game.backends.headless.combat_v0_backend import (
    BACKEND_FINGERPRINT as COMBAT_BACKEND_FINGERPRINT,
    BACKEND_VERSION as COMBAT_BACKEND_VERSION,
    RULES_FINGERPRINT as COMBAT_RULES_FINGERPRINT,
    RULES_VERSION as COMBAT_RULES_VERSION,
    CombatV0Backend,
    scenario_initial_deck_definition_ids,
)
from game.content.reduced_v0 import (
    CONTENT_FINGERPRINT,
    CONTENT_VERSION,
    MAP_TEMPLATES,
    REWARD_TABLES,
    SAFE_EVENT_DEFINITIONS,
    SCENARIO_REFERENCES,
    resolve_scenario_reference,
)
from game.contracts.headless_v0 import (
    CONTRACT_FINGERPRINT,
    ActionRequest,
    BackendCapabilities,
    BackendManifest,
    ComponentEvidence,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    EvidenceLabel,
    HeadlessBinding,
    MAX_PUBLIC_COUNTER,
    NodeKind,
    PublicEvent,
    PublicEventKind,
    PublicObservation,
    PublicReferenceKind,
    PublicScope,
    RoomKind,
    RunOutcome,
    Transition,
    TransitionReason,
    TransitionResult,
    TypedCandidate,
    UnsupportedReasonCode,
    canonical_json,
)
from game.engine.headless_state import (
    COMBAT_LAUNCH_STREAM,
    WORLD_STATE_FINGERPRINT,
    AutomaticTransition,
    PendingDecision,
    TerminalResult,
    WorldState,
)
from game.engine.random_service import GameRandomService
from game.engine.map_rules import (
    BACKEND_FINGERPRINT as MAP_BACKEND_FINGERPRINT,
    MAP_RULES_VERSION,
    RULES_FINGERPRINT as MAP_RULES_FINGERPRINT,
    MapRules,
)
from game.engine.reward_rules import (
    REWARD_RULES_FINGERPRINT,
    REWARD_RULES_VERSION,
    RewardRules,
)
from game.engine.room_rules import (
    ROOM_DECISION_KIND,
    ROOM_RULES_FINGERPRINT,
    ROOM_RULES_VERSION,
    RoomRuleError,
    UnsupportedRoomContentError,
    apply_room_candidate,
    open_room,
    room_candidates,
    room_public_observation,
)
from game.engine.snapshots import (
    PRIVATE_SNAPSHOT_SCHEMA,
    PRIVATE_SNAPSHOT_VERSION,
    PrivateWorldSnapshot,
    WorldSnapshotCodec,
)


BACKEND_ID = "reduced_headless"
BACKEND_VERSION = "reduced_headless_v1"
RULES_VERSION = "reduced_headless_rules_v1"
SNAPSHOT_VERSION = "reduced_headless_snapshot_v1"
MAP_CONTINUATION_KIND = "resume_map"

_MAP_TEMPLATE_IDS = frozenset(item.template_id for item in MAP_TEMPLATES)
_REWARD_TABLE_IDS = frozenset(item.table_id for item in REWARD_TABLES)
_SAFE_EVENT_IDS = frozenset(item.event_id for item in SAFE_EVENT_DEFINITIONS)
_MAP_TEMPLATES_BY_ID = {item.template_id: item for item in MAP_TEMPLATES}
_REWARD_TABLES_BY_ID = {item.table_id: item for item in REWARD_TABLES}
_SAFE_EVENTS_BY_ID = {item.event_id: item for item in SAFE_EVENT_DEFINITIONS}
_SETTING_FIELDS = frozenset(
    {
        "combat_settings",
        "event_id",
        "initial_gold",
        "initial_hp",
        "map_template_id",
        "reward_table_id",
    }
)
_COMBAT_SETTING_FIELDS = frozenset(
    {
        "cards_per_turn",
        "enemy_max_hp",
        "energy_per_turn",
        "hp_loss_penalty_scale",
        "hp_loss_penalty_scale_ratio",
        "incoming_damage_shaping_scale",
        "incoming_damage_shaping_scale_ratio",
        "record_history",
        "record_trajectory",
    }
)


class ReducedRunBackendError(ValueError):
    """Raised for invalid configuration, lifecycle, or snapshot data."""


def _canonical_hash(domain: str, value: Any) -> str:
    return sha256(domain.encode("ascii") + b"\0" + canonical_json(value).encode()).hexdigest()


_COMBAT_MANIFEST = CombatV0Backend().manifest()
_COMBAT_EVIDENCE = {item.component: item for item in _COMBAT_MANIFEST.evidence}

RULES_FINGERPRINT = _canonical_hash(
    "reduced_headless.rules.v1",
    {
        "combat_backend_fingerprint": COMBAT_BACKEND_FINGERPRINT,
        "combat_projection_fingerprint": _COMBAT_EVIDENCE["projection"].fingerprint,
        "combat_rules_fingerprint": COMBAT_RULES_FINGERPRINT,
        "content_fingerprint": CONTENT_FINGERPRINT,
        "map_backend_fingerprint": MAP_BACKEND_FINGERPRINT,
        "map_rules_fingerprint": MAP_RULES_FINGERPRINT,
        "reward_rules_fingerprint": REWARD_RULES_FINGERPRINT,
        "room_rules_fingerprint": ROOM_RULES_FINGERPRINT,
        "world_state_fingerprint": WORLD_STATE_FINGERPRINT,
        "lifecycle": (
            "combat",
            "reward",
            "map",
            "room",
            "combat",
            "reward",
            "route_complete",
        ),
        "route_completion": {
            "public_structural_outcome": RunOutcome.VICTORY.value,
            "non_policy_terminal_reason": "route_complete",
        },
        "combat_child_binding": (
            "active_actionable_nonterminal_child",
            "accepted_history_equals_outer_sequence_minus_entry_sequence",
            "launch_matches_config_and_named_world_rng_history",
        ),
        "configuration_liveness": "all_declared_required_and_selectable_gold_deltas_preflighted",
        "phase_ownership": "exact_pending_queue_child_terminal_unsupported_partition_v1",
        "reset_epoch": "active_generation_plus_instance_high_water_v1",
        "version": RULES_VERSION,
    },
)

SNAPSHOT_FINGERPRINT = _canonical_hash(
    "reduced_headless.snapshot_schema.v1",
    {
        "private_world_schema": PRIVATE_SNAPSHOT_SCHEMA,
        "private_world_version": PRIVATE_SNAPSHOT_VERSION,
        "snapshot_version": SNAPSHOT_VERSION,
        "fields": (
            "backend_fingerprint",
            "combat_snapshot",
            "combat_entry_sequence",
            "config",
            "content_fingerprint",
            "contract_fingerprint",
            "current_decision_hash",
            "decision_sequence",
            "descriptor_hash",
            "last_public_events",
            "outer_run_id",
            "phase",
            "private_world_snapshot",
            "public_scope",
            "reset_generation",
            "rules_fingerprint",
            "snapshot_fingerprint",
            "snapshot_version",
            "status",
            "terminal_reason",
            "unsupported_reason",
        ),
    },
)

BACKEND_FINGERPRINT = _canonical_hash(
    "reduced_headless.backend.v1",
    {
        "backend_id": BACKEND_ID,
        "backend_version": BACKEND_VERSION,
        "content_fingerprint": CONTENT_FINGERPRINT,
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "rules_fingerprint": RULES_FINGERPRINT,
        "snapshot_fingerprint": SNAPSHOT_FINGERPRINT,
    },
)


def _manifest() -> BackendManifest:
    projection = _COMBAT_EVIDENCE["projection"]
    return BackendManifest(
        backend_id=BACKEND_ID,
        backend_version=BACKEND_VERSION,
        backend_fingerprint=BACKEND_FINGERPRINT,
        content_version=CONTENT_VERSION,
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_version=RULES_VERSION,
        rules_fingerprint=RULES_FINGERPRINT,
        capabilities=BackendCapabilities(
            deterministic_reset=True,
            counterfactual_stepping=True,
            fixture_playback=False,
            snapshot_restore=True,
            live_truth=False,
            legacy_shaped_reward_diagnostics=False,
        ),
        supported_phases=(
            DecisionPhase.COMBAT,
            DecisionPhase.MAP,
            DecisionPhase.REWARD,
            DecisionPhase.ROOM,
        ),
        unsupported_phases=(),
        evidence=(
            ComponentEvidence(
                "combat_backend",
                EvidenceLabel.COMBAT_V0,
                COMBAT_BACKEND_VERSION,
                COMBAT_BACKEND_FINGERPRINT,
            ),
            ComponentEvidence(
                "combat_projection",
                EvidenceLabel.COMBAT_V0,
                projection.version,
                projection.fingerprint,
            ),
            ComponentEvidence(
                "combat_rules",
                EvidenceLabel.COMBAT_V0,
                COMBAT_RULES_VERSION,
                COMBAT_RULES_FINGERPRINT,
            ),
            ComponentEvidence(
                "composer",
                EvidenceLabel.STRUCTURAL_FIXTURE,
                BACKEND_VERSION,
                BACKEND_FINGERPRINT,
            ),
            ComponentEvidence(
                "content",
                EvidenceLabel.STRUCTURAL_FIXTURE,
                CONTENT_VERSION,
                CONTENT_FINGERPRINT,
            ),
            ComponentEvidence(
                "map",
                EvidenceLabel.STRUCTURAL_FIXTURE,
                MAP_RULES_VERSION,
                MAP_RULES_FINGERPRINT,
            ),
            ComponentEvidence(
                "reward",
                EvidenceLabel.STRUCTURAL_FIXTURE,
                REWARD_RULES_VERSION,
                REWARD_RULES_FINGERPRINT,
            ),
            ComponentEvidence(
                "room",
                EvidenceLabel.STRUCTURAL_FIXTURE,
                ROOM_RULES_VERSION,
                ROOM_RULES_FINGERPRINT,
            ),
            ComponentEvidence(
                "snapshot",
                EvidenceLabel.STRUCTURAL_FIXTURE,
                SNAPSHOT_VERSION,
                SNAPSHOT_FINGERPRINT,
            ),
            ComponentEvidence(
                "state",
                EvidenceLabel.STRUCTURAL_FIXTURE,
                "reduced_world_state_v0",
                WORLD_STATE_FINGERPRINT,
            ),
        ),
    )


_BACKEND_MANIFEST = _manifest()


def _json_safe_copy(value: Any, path: str = "backend_settings") -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ReducedRunBackendError(f"{path} keys must be strings.")
            if any(0xD800 <= ord(character) <= 0xDFFF for character in key):
                raise ReducedRunBackendError(f"{path} contains noncanonical text.")
            result[key] = _json_safe_copy(item, f"{path}.{key}")
        return result
    if isinstance(value, list):
        return [_json_safe_copy(item, f"{path}[]") for item in value]
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise ReducedRunBackendError(f"{path} contains noncanonical text.")
        return value
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ReducedRunBackendError(
        f"{path} must contain only JSON-safe strings, integers, booleans, null, arrays, and objects."
    )


@dataclass(frozen=True, slots=True)
class HeadlessRunConfig:
    """Spawn-safe, policy-independent descriptor for one reduced run."""

    scenario_id: str
    content_fingerprint: str
    game_seed: int
    backend_settings: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or self.scenario_id not in SCENARIO_REFERENCES:
            raise ReducedRunBackendError("scenario_id is not declared by reduced content.")
        if self.content_fingerprint != CONTENT_FINGERPRINT:
            raise ReducedRunBackendError("content_fingerprint must exactly match reduced content.")
        if not isinstance(self.game_seed, int) or isinstance(self.game_seed, bool):
            raise ReducedRunBackendError("game_seed must be an integer, not a boolean.")
        if not isinstance(self.backend_settings, Mapping):
            raise ReducedRunBackendError("backend_settings must be a JSON object.")
        settings = _json_safe_copy(self.backend_settings)
        _validate_backend_settings(settings, self.scenario_id)
        object.__setattr__(self, "backend_settings", settings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "content_fingerprint": self.content_fingerprint,
            "game_seed": self.game_seed,
            "backend_settings": deepcopy(dict(self.backend_settings)),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HeadlessRunConfig":
        if not isinstance(value, Mapping):
            raise ReducedRunBackendError("Run configuration must be an object.")
        expected = {
            "scenario_id",
            "content_fingerprint",
            "game_seed",
            "backend_settings",
        }
        if set(value) != expected:
            raise ReducedRunBackendError("Run configuration fields must be exact.")
        return cls(
            scenario_id=value["scenario_id"],
            content_fingerprint=value["content_fingerprint"],
            game_seed=value["game_seed"],
            backend_settings=value["backend_settings"],
        )


def _validate_backend_settings(settings: Mapping[str, Any], scenario_id: str) -> None:
    unknown = set(settings) - _SETTING_FIELDS
    if unknown:
        raise ReducedRunBackendError(f"Unknown backend setting(s): {sorted(unknown)!r}.")
    if "map_template_id" in settings and settings["map_template_id"] not in _MAP_TEMPLATE_IDS:
        raise ReducedRunBackendError("map_template_id is not declared by reduced content.")
    if "reward_table_id" in settings and settings["reward_table_id"] not in _REWARD_TABLE_IDS:
        raise ReducedRunBackendError("reward_table_id is not declared by reduced content.")
    if "event_id" in settings and settings["event_id"] not in _SAFE_EVENT_IDS:
        raise ReducedRunBackendError("event_id is not declared by reduced content.")
    scenario = resolve_scenario_reference(scenario_id)
    initial_hp = settings.get("initial_hp", scenario.player_max_hp)
    if (
        not isinstance(initial_hp, int)
        or isinstance(initial_hp, bool)
        or not 1 <= initial_hp <= scenario.player_max_hp
    ):
        raise ReducedRunBackendError("initial_hp must be between one and scenario max HP.")
    initial_gold = settings.get("initial_gold", 0)
    if (
        not isinstance(initial_gold, int)
        or isinstance(initial_gold, bool)
        or not 0 <= initial_gold <= MAX_PUBLIC_COUNTER
    ):
        raise ReducedRunBackendError("initial_gold must be a bounded nonnegative integer.")
    combat = settings.get("combat_settings", {})
    if not isinstance(combat, Mapping):
        raise ReducedRunBackendError("combat_settings must be an object.")
    unknown_combat = set(combat) - _COMBAT_SETTING_FIELDS
    if unknown_combat:
        raise ReducedRunBackendError(
            f"Unknown combat setting(s): {sorted(unknown_combat)!r}."
        )
    for first, second in (
        ("record_history", "record_trajectory"),
        ("hp_loss_penalty_scale", "hp_loss_penalty_scale_ratio"),
        ("incoming_damage_shaping_scale", "incoming_damage_shaping_scale_ratio"),
    ):
        if first in combat and second in combat:
            raise ReducedRunBackendError(f"combat_settings cannot contain both {first} and {second}.")
    for name in ("cards_per_turn", "enemy_max_hp", "energy_per_turn"):
        if name in combat and (
            not isinstance(combat[name], int) or isinstance(combat[name], bool) or combat[name] < 1
        ):
            raise ReducedRunBackendError(f"combat_settings.{name} must be a positive integer.")
    for name in ("hp_loss_penalty_scale", "incoming_damage_shaping_scale"):
        if name in combat and (
            not isinstance(combat[name], int) or isinstance(combat[name], bool) or combat[name] < 0
        ):
            raise ReducedRunBackendError(f"combat_settings.{name} must be nonnegative integer.")
    for name in ("record_history", "record_trajectory"):
        if name in combat and not isinstance(combat[name], bool):
            raise ReducedRunBackendError(f"combat_settings.{name} must be boolean.")
    for name in ("hp_loss_penalty_scale_ratio", "incoming_damage_shaping_scale_ratio"):
        if name not in combat:
            continue
        ratio = combat[name]
        if (
            not isinstance(ratio, list)
            or len(ratio) != 2
            or any(not isinstance(item, int) or isinstance(item, bool) for item in ratio)
            or ratio[0] < 0
            or ratio[1] <= 0
        ):
            raise ReducedRunBackendError(f"combat_settings.{name} is not a canonical ratio.")
    if scenario.encounter != "simple" and "enemy_max_hp" in combat:
        if combat["enemy_max_hp"] != scenario.enemy_max_hp:
            raise ReducedRunBackendError(
                "combat_settings.enemy_max_hp is configurable only for the simple scenario."
            )
    _validate_route_liveness(settings)


def _validate_route_liveness(settings: Mapping[str, Any]) -> None:
    """Reject configurations whose declared route can deterministically deadlock."""

    template_id = settings.get("map_template_id", "two_combat_rest")
    reward_table_id = settings.get("reward_table_id", "combat_reward_basic")
    event_id = settings.get("event_id", "quiet_cache")
    initial_gold = settings.get("initial_gold", 0)
    template = _MAP_TEMPLATES_BY_ID[template_id]
    reward_table = _REWARD_TABLES_BY_ID[reward_table_id]
    combat_count = sum(node.kind == NodeKind.COMBAT.value for node in template.nodes)
    maximum_gold = initial_gold + combat_count * reward_table.gold_amount
    if any(node.kind == NodeKind.EVENT.value for node in template.nodes):
        event = _SAFE_EVENTS_BY_ID[event_id]
        if event.effect_kind == "gain_gold":
            maximum_gold += event.amount
    if maximum_gold > MAX_PUBLIC_COUNTER:
        raise ReducedRunBackendError(
            "backend_settings can exceed the public gold bound on a declared route."
        )


def _resolved_settings(config: HeadlessRunConfig) -> dict[str, Any]:
    scenario = resolve_scenario_reference(config.scenario_id)
    supplied = deepcopy(dict(config.backend_settings))
    return {
        "combat_settings": supplied.get("combat_settings", {}),
        "event_id": supplied.get("event_id", "quiet_cache"),
        "initial_gold": supplied.get("initial_gold", 0),
        "initial_hp": supplied.get("initial_hp", scenario.player_max_hp),
        "map_template_id": supplied.get("map_template_id", "two_combat_rest"),
        "reward_table_id": supplied.get("reward_table_id", "combat_reward_basic"),
    }


def _scope(decision_ordinal: int = 0) -> PublicScope:
    return PublicScope(
        history_ordinal=0,
        decision_ordinal=decision_ordinal,
        reveal_ordinals={kind.value: 0 for kind in PublicReferenceKind},
    )


def _next_scope(scope: PublicScope) -> PublicScope:
    return PublicScope(
        history_ordinal=scope.history_ordinal,
        decision_ordinal=min(scope.decision_ordinal + 1, MAX_PUBLIC_COUNTER),
        reveal_ordinals=dict(scope.reveal_ordinals),
    )


def _renumber_events(events: Sequence[PublicEvent]) -> tuple[PublicEvent, ...]:
    return tuple(
        PublicEvent(index, event.event_type, event.phase, dict(event.data))
        for index, event in enumerate(events)
    )


def _outer_run_id(config: HeadlessRunConfig, generation: int) -> str:
    digest = _canonical_hash(
        "reduced_headless.outer_run.v0",
        {"config": config.to_dict(), "reset_generation": generation},
    )
    return f"run.h3.{digest[:32]}"


def _terminal_observation(world: WorldState, scope: PublicScope) -> PublicObservation:
    assert world.terminal_result is not None
    return PublicObservation(
        DecisionPhase.TERMINAL,
        {
            "outcome": world.terminal_result.outcome.value,
            "player": {
                "deck_size": len(world.master_deck),
                "gold": world.gold,
                "hp": world.current_hp,
                "max_hp": world.max_hp,
            },
        },
        scope,
    )


class ReducedRunBackend:
    """Resettable composer over the closed reduced structural route."""

    def __init__(self) -> None:
        self._config: HeadlessRunConfig | None = None
        self._settings: dict[str, Any] | None = None
        self._reset_generation = -1
        self._generation_high_water = -1
        self._outer_run_id: str | None = None
        self._outer_sequence = 0
        self._combat_entry_sequence: int | None = None
        self._world: WorldState | None = None
        self._codec = WorldSnapshotCodec(CONTENT_FINGERPRINT, RULES_FINGERPRINT)
        self._map_rules: MapRules | None = None
        self._reward_rules = RewardRules()
        self._combat: CombatV0Backend | None = None
        self._last_public_events: tuple[PublicEvent, ...] = ()
        self._boundary_scope: PublicScope | None = None
        self._terminal_reason: str | None = None
        self._unsupported_reason: str | None = None
        self._decision: DecisionState | None = None

    @property
    def terminal_reason(self) -> str | None:
        """Return the non-policy stop reason for a terminal boundary."""
        return self._terminal_reason

    @property
    def unsupported_reason(self) -> str | None:
        """Return the normalized non-policy unsupported detail, if any."""
        return self._unsupported_reason

    @property
    def rng_stream_counters(self) -> dict[str, int]:
        if self._world is None:
            raise RuntimeError("Backend is not initialized.")
        return self._world.rng_stream_counters()

    @property
    def combat_launch_count(self) -> int:
        return self.rng_stream_counters["combat_launch"]

    def manifest(self) -> BackendManifest:
        return _BACKEND_MANIFEST

    def reset(self, configuration: HeadlessRunConfig | Mapping[str, Any]) -> DecisionState:
        config = (
            HeadlessRunConfig.from_dict(configuration.to_dict())
            if isinstance(configuration, HeadlessRunConfig)
            else HeadlessRunConfig.from_dict(configuration)
        )
        # Resolve the reduced-content reference before consulting the legacy
        # scenario deck adapter.  This rejects broad scenario IDs pre-mutation.
        scenario = resolve_scenario_reference(config.scenario_id)
        deck = scenario_initial_deck_definition_ids(config.scenario_id)
        settings = _resolved_settings(config)
        generation = self._generation_high_water + 1
        outer_run = _outer_run_id(config, generation)

        world = WorldState.create(
            seed=config.game_seed,
            current_hp=settings["initial_hp"],
            max_hp=scenario.player_max_hp,
            gold=settings["initial_gold"],
            deck_definition_ids=deck,
            map_node_definitions=(),
            content_fingerprint=CONTENT_FINGERPRINT,
            rules_fingerprint=RULES_FINGERPRINT,
        )
        map_rules = MapRules(
            settings["map_template_id"],
            world_rules_fingerprint=RULES_FINGERPRINT,
        )
        initial_map = map_rules.reset(world)
        if len(initial_map.candidates) != 1:
            raise ReducedRunBackendError("Reduced map must have one unique start node.")
        start = map_rules.choose_node(
            world,
            ActionRequest(HeadlessBinding.for_candidate(initial_map, initial_map.candidates[0].candidate_id)),
        )
        if (
            start.result is not TransitionResult.ACCEPTED
            or dict(start.public_events[0].data) != {"node_kind": NodeKind.COMBAT.value}
        ):
            raise ReducedRunBackendError("Reduced map start must enter combat.")
        _suspend_map(world, DecisionPhase.COMBAT)
        launch = world.create_combat_launch(
            config.scenario_id,
            combat_settings=settings["combat_settings"],
        )
        combat = CombatV0Backend()
        combat.reset(launch)

        candidate = ReducedRunBackend()
        candidate._config = config
        candidate._settings = settings
        candidate._reset_generation = generation
        candidate._generation_high_water = generation
        candidate._outer_run_id = outer_run
        candidate._outer_sequence = 0
        candidate._combat_entry_sequence = 0
        candidate._world = world
        candidate._map_rules = map_rules
        candidate._combat = combat
        candidate._last_public_events = ()
        candidate._boundary_scope = combat.observe().observation.public_scope
        candidate._validate_private_boundary()
        candidate._decision = candidate._project_current()
        self._install_from(candidate)
        return self.observe()

    def observe(self) -> DecisionState:
        if self._decision is None:
            raise RuntimeError("Backend is not initialized. Call reset() or restore().")
        return self._decision

    def apply(self, action: ActionRequest) -> Transition:
        if not isinstance(action, ActionRequest):
            raise TypeError("action must be an ActionRequest.")
        current = self.observe()
        binding = action.binding
        if (
            binding.run_id != current.run_id
            or binding.decision_sequence != current.decision_sequence
            or binding.decision_hash != current.decision_hash
        ):
            return Transition(
                TransitionResult.STALE,
                TransitionReason.STALE_BINDING,
                binding,
                current.public_events,
                current,
            )
        candidate = next(
            (item for item in current.candidates if item.candidate_id == binding.candidate_id),
            None,
        )
        if candidate is None:
            return Transition(
                TransitionResult.REJECTED,
                TransitionReason.INVALID_CANDIDATE,
                binding,
                current.public_events,
                current,
            )

        preimage = self._transaction_preimage()
        try:
            events = self._dispatch(candidate)
            self._outer_sequence += 1
            self._last_public_events = _renumber_events(events)
            self._validate_private_boundary()
            self._decision = self._project_current()
        except Exception:
            self._restore_transaction_preimage(preimage)
            current = self.observe()
            return Transition(
                TransitionResult.REJECTED,
                TransitionReason.REJECTED_BY_RULES,
                binding,
                current.public_events,
                current,
            )
        return Transition(
            TransitionResult.ACCEPTED,
            TransitionReason.ACCEPTED,
            binding,
            self._decision.public_events,
            self._decision,
        )

    def snapshot(self) -> dict[str, Any]:
        current = self.observe()
        assert self._world is not None and self._config is not None
        combat_snapshot = None if self._combat is None else self._combat.snapshot()
        descriptor = {
            "backend_fingerprint": BACKEND_FINGERPRINT,
            "combat_snapshot": combat_snapshot,
            "combat_entry_sequence": self._combat_entry_sequence,
            "config": self._config.to_dict(),
            "content_fingerprint": CONTENT_FINGERPRINT,
            "contract_fingerprint": CONTRACT_FINGERPRINT,
            "current_decision_hash": current.decision_hash,
            "decision_sequence": self._outer_sequence,
            "last_public_events": [event.to_dict() for event in self._last_public_events],
            "outer_run_id": self._outer_run_id,
            "phase": current.phase.value,
            "private_world_snapshot": self._codec.capture(self._world).to_dict(),
            "public_scope": current.observation.public_scope.to_dict(),
            "reset_generation": self._reset_generation,
            "rules_fingerprint": RULES_FINGERPRINT,
            "snapshot_fingerprint": SNAPSHOT_FINGERPRINT,
            "snapshot_version": SNAPSHOT_VERSION,
            "status": current.status.value,
            "terminal_reason": self._terminal_reason,
            "unsupported_reason": self._unsupported_reason,
        }
        return {
            **descriptor,
            "descriptor_hash": _canonical_hash(
                "reduced_headless.snapshot_descriptor.v1", descriptor
            ),
        }

    def restore(self, snapshot: Mapping[str, Any]) -> DecisionState:
        candidate = self._parse_snapshot(snapshot)
        high_water = max(self._generation_high_water, candidate._reset_generation)
        self._install_from(candidate)
        self._generation_high_water = high_water
        return self.observe()

    def close(self) -> None:
        if self._combat is not None:
            self._combat.close()
        self._config = None
        self._settings = None
        self._outer_run_id = None
        self._outer_sequence = 0
        self._combat_entry_sequence = None
        self._world = None
        self._map_rules = None
        self._combat = None
        self._last_public_events = ()
        self._boundary_scope = None
        self._terminal_reason = None
        self._unsupported_reason = None
        self._decision = None

    def _dispatch(self, candidate: TypedCandidate) -> tuple[PublicEvent, ...]:
        assert self._world is not None
        phase = self.observe().phase
        if phase is DecisionPhase.COMBAT:
            return self._apply_combat(candidate)
        if phase is DecisionPhase.REWARD:
            return self._apply_reward(candidate)
        if phase is DecisionPhase.MAP:
            return self._apply_map(candidate)
        if phase is DecisionPhase.ROOM:
            return self._apply_room(candidate)
        raise ReducedRunBackendError("The current boundary is not actionable.")

    @staticmethod
    def _exact_child_candidate(child: DecisionState, candidate: TypedCandidate) -> TypedCandidate:
        exact = [item for item in child.candidates if item == candidate]
        if len(exact) != 1:
            raise ReducedRunBackendError("Outer candidate does not exactly match child provenance.")
        return exact[0]

    def _apply_combat(self, candidate: TypedCandidate) -> tuple[PublicEvent, ...]:
        assert self._combat is not None and self._world is not None
        child = self._combat.observe()
        exact = self._exact_child_candidate(child, candidate)
        transition = self._combat.apply(
            ActionRequest(HeadlessBinding.for_candidate(child, exact.candidate_id))
        )
        if transition.result is not TransitionResult.ACCEPTED:
            raise ReducedRunBackendError("Authenticated combat candidate was not accepted.")
        events = transition.public_events
        resolution = self._combat.get_resolution()
        if resolution is None:
            self._boundary_scope = transition.next_decision.observation.public_scope
            return events
        launch = self._combat.launch_spec
        assert launch is not None
        self._world.apply_combat_resolution(launch, resolution)
        self._combat.close()
        self._combat = None
        self._combat_entry_sequence = None
        self._boundary_scope = _next_scope(self.observe().observation.public_scope)
        if resolution.outcome.value == "defeat":
            self._world.pending_decision = None
            self._world.automatic_queue = ()
            self._world.phase = DecisionPhase.TERMINAL
            self._world.terminal_result = TerminalResult(RunOutcome.DEFEAT, "defeat")
            self._terminal_reason = "defeat"
            return _renumber_events(
                (*events, PublicEvent(0, PublicEventKind.RUN_TERMINATED, DecisionPhase.TERMINAL, {"outcome": RunOutcome.DEFEAT.value}))
            )
        self._world.phase = DecisionPhase.REWARD
        self._world.pending_decision = None
        reward = self._reward_rules.begin(
            self._world,
            reward_table_id=self._settings["reward_table_id"],
            decision_sequence=0,
            public_scope=_scope(),
        )
        self._boundary_scope = reward.observation.public_scope
        return events

    def _apply_reward(self, candidate: TypedCandidate) -> tuple[PublicEvent, ...]:
        assert self._world is not None
        child = self._reward_rules.decision(self._world)
        exact = self._exact_child_candidate(child, candidate)
        transition = self._reward_rules.apply(
            self._world,
            ActionRequest(HeadlessBinding.for_candidate(child, exact.candidate_id)),
        )
        if transition.result is not TransitionResult.ACCEPTED:
            raise ReducedRunBackendError("Authenticated reward candidate was not accepted.")
        if transition.next_decision.status is DecisionStatus.WAITING:
            _resume_map(self._world)
            assert self._map_rules is not None
            mapped = self._map_rules.decision(self._world)
            self._boundary_scope = mapped.observation.public_scope
        else:
            self._boundary_scope = transition.next_decision.observation.public_scope
        return transition.public_events

    def _apply_map(self, candidate: TypedCandidate) -> tuple[PublicEvent, ...]:
        assert self._world is not None and self._map_rules is not None
        child = self._map_rules.decision(self._world)
        exact = self._exact_child_candidate(child, candidate)
        transition = self._map_rules.choose_node(
            self._world,
            ActionRequest(HeadlessBinding.for_candidate(child, exact.candidate_id)),
        )
        if transition.result is not TransitionResult.ACCEPTED:
            raise ReducedRunBackendError("Authenticated map candidate was not accepted.")
        events = transition.public_events
        node_kind = NodeKind(events[0].data["node_kind"])
        self._boundary_scope = transition.next_decision.observation.public_scope
        if node_kind is NodeKind.COMBAT:
            _suspend_map(self._world, DecisionPhase.COMBAT)
            launch = self._world.create_combat_launch(
                self._config.scenario_id,
                combat_settings=self._settings["combat_settings"],
            )
            combat = CombatV0Backend()
            combat.reset(launch)
            self._combat = combat
            self._combat_entry_sequence = self._outer_sequence + 1
            self._boundary_scope = combat.observe().observation.public_scope
        elif node_kind in (NodeKind.REST, NodeKind.EVENT):
            room_kind = RoomKind(node_kind.value)
            _suspend_map(self._world, DecisionPhase.ROOM)
            try:
                open_room(
                    self._world,
                    room_kind,
                    decision_sequence=0,
                    public_scope=_scope(),
                    event_id=(self._settings["event_id"] if room_kind is RoomKind.EVENT else None),
                )
            except (UnsupportedRoomContentError, RoomRuleError) as error:
                if not self._is_runtime_unavailable_room(room_kind, error):
                    raise
                self._world.pending_decision = None
                self._world.automatic_queue = ()
                self._world.phase = DecisionPhase.UNSUPPORTED
                self._unsupported_reason = "room_unavailable"
                self._boundary_scope = _next_scope(child.observation.public_scope)
                return events
            self._boundary_scope = _scope()
        elif node_kind is NodeKind.TERMINAL:
            # MapRules owns the structural terminal outcome.  H3 supplies the
            # distinct non-policy stop reason without relabelling it as a
            # target-game win.
            self._terminal_reason = "route_complete"
            self._world.pending_decision = None
            self._boundary_scope = _next_scope(child.observation.public_scope)
            events = _renumber_events(
                (*events, PublicEvent(0, PublicEventKind.RUN_TERMINATED, DecisionPhase.TERMINAL, {"outcome": RunOutcome.VICTORY.value}))
            )
        else:
            raise ReducedRunBackendError("Unsupported map node kind.")
        return events

    def _is_runtime_unavailable_room(
        self,
        room_kind: RoomKind,
        error: RoomRuleError,
    ) -> bool:
        """Recognize only the bounded accepted-producer unavailable case."""

        assert self._world is not None and self._settings is not None
        if isinstance(error, UnsupportedRoomContentError):
            return True
        return (
            type(error) is RoomRuleError
            and str(error) == "Healing event has no contract-valid effect at full HP."
            and room_kind is RoomKind.EVENT
            and self._settings["event_id"] == "cool_spring"
            and self._world.current_hp == self._world.max_hp
        )

    def _apply_room(self, candidate: TypedCandidate) -> tuple[PublicEvent, ...]:
        assert self._world is not None and self._boundary_scope is not None
        legal = room_candidates(self._world, self._boundary_scope)
        exact = [item for item in legal if item == candidate]
        if len(exact) != 1:
            raise ReducedRunBackendError("Outer room candidate does not exactly match room state.")
        transition = apply_room_candidate(self._world, self._boundary_scope, exact[0])
        if transition.completed:
            _resume_map(self._world)
            assert self._map_rules is not None
            mapped = self._map_rules.decision(self._world)
            self._boundary_scope = mapped.observation.public_scope
        else:
            pending = self._world.pending_decision
            assert pending is not None
            self._boundary_scope = PublicScope.from_dict(pending.private_context["public_scope"])
        return transition.public_events

    def _project_current(self) -> DecisionState:
        assert self._world is not None and self._outer_run_id is not None
        if self._world.phase is DecisionPhase.COMBAT:
            assert self._combat is not None
            child = self._combat.observe()
            observation, candidates, status, phase = (
                child.observation,
                child.candidates,
                child.status,
                child.phase,
            )
        elif self._world.phase is DecisionPhase.REWARD:
            child = self._reward_rules.decision(self._world)
            if child.status is DecisionStatus.WAITING:
                raise ReducedRunBackendError("Reward WAITING cannot be externally projected.")
            observation, candidates, status, phase = (
                child.observation,
                child.candidates,
                child.status,
                child.phase,
            )
        elif self._world.phase is DecisionPhase.MAP:
            assert self._map_rules is not None
            child = self._map_rules.decision(self._world)
            observation, candidates, status, phase = (
                child.observation,
                child.candidates,
                child.status,
                child.phase,
            )
        elif self._world.phase is DecisionPhase.ROOM:
            assert self._boundary_scope is not None
            observation = room_public_observation(self._world, self._boundary_scope)
            candidates = room_candidates(self._world, self._boundary_scope)
            status, phase = DecisionStatus.ACTIONABLE, DecisionPhase.ROOM
        elif self._world.phase is DecisionPhase.TERMINAL:
            assert self._boundary_scope is not None
            observation = _terminal_observation(self._world, self._boundary_scope)
            candidates = ()
            status, phase = DecisionStatus.TERMINAL, DecisionPhase.TERMINAL
        elif self._world.phase is DecisionPhase.UNSUPPORTED:
            assert self._boundary_scope is not None and self._unsupported_reason is not None
            observation = PublicObservation(
                DecisionPhase.UNSUPPORTED,
                {"reason_code": UnsupportedReasonCode.UNSUPPORTED_CONTENT.value},
                self._boundary_scope,
            )
            candidates = ()
            status, phase = DecisionStatus.UNSUPPORTED, DecisionPhase.UNSUPPORTED
        else:
            raise ReducedRunBackendError("World phase is outside the reduced backend.")
        self._boundary_scope = observation.public_scope
        return DecisionState.create(
            backend_id=BACKEND_ID,
            backend_version=BACKEND_VERSION,
            backend_fingerprint=BACKEND_FINGERPRINT,
            content_version=CONTENT_VERSION,
            content_fingerprint=CONTENT_FINGERPRINT,
            rules_version=RULES_VERSION,
            rules_fingerprint=RULES_FINGERPRINT,
            run_id=self._outer_run_id,
            decision_sequence=self._outer_sequence,
            status=status,
            phase=phase,
            observation=observation,
            candidates=candidates,
            public_events=self._last_public_events,
        )

    def _validate_private_boundary(self) -> None:
        assert self._world is not None and self._config is not None and self._settings is not None
        self._world.validate()
        phase = self._world.phase
        self._validate_world_config_rng_provenance()

        if phase is DecisionPhase.TERMINAL:
            if self._terminal_reason not in {"defeat", "route_complete"} or self._unsupported_reason is not None:
                raise ReducedRunBackendError("Terminal boundary has inconsistent stop reasons.")
        elif phase is DecisionPhase.UNSUPPORTED:
            if self._unsupported_reason != "room_unavailable" or self._terminal_reason is not None:
                raise ReducedRunBackendError("Unsupported boundary has inconsistent stop reasons.")
        elif self._terminal_reason is not None or self._unsupported_reason is not None:
            raise ReducedRunBackendError("Actionable boundary cannot retain a stop reason.")

        if phase in (DecisionPhase.COMBAT, DecisionPhase.REWARD, DecisionPhase.ROOM):
            _map_continuation(self._world)
            self._validate_parked_map_continuation()
        elif self._world.automatic_queue:
            raise ReducedRunBackendError("Map/terminal/unsupported boundaries cannot retain a continuation queue.")
        if phase is DecisionPhase.COMBAT:
            if (
                self._world.pending_decision is not None
                or self._world.terminal_result is not None
                or self._combat is None
                or self._combat_entry_sequence is None
            ):
                raise ReducedRunBackendError("Combat boundary has inconsistent child state.")
            launch = self._combat.launch_spec
            if launch is None:
                raise ReducedRunBackendError("Combat boundary has no launch spec.")
            self._world.validate_combat_launch(launch)
            child = self._combat.observe()
            if (
                child.phase is not DecisionPhase.COMBAT
                or child.status is not DecisionStatus.ACTIONABLE
                or not child.candidates
                or self._combat.get_resolution() is not None
            ):
                raise ReducedRunBackendError("Combat child is not an actionable nonterminal boundary.")
            expected_history_count = self._outer_sequence - self._combat_entry_sequence
            if (
                expected_history_count < 0
                or len(self._combat.accepted_action_history) != expected_history_count
                or child.decision_sequence != expected_history_count
            ):
                raise ReducedRunBackendError("Combat child progress does not match the outer sequence.")
            child_manifest = self._combat.manifest()
            if (
                child_manifest.backend_fingerprint != COMBAT_BACKEND_FINGERPRINT
                or child_manifest.rules_fingerprint != COMBAT_RULES_FINGERPRINT
                or child_manifest.content_fingerprint != CONTENT_FINGERPRINT
            ):
                raise ReducedRunBackendError("Combat child provenance is incompatible.")
        elif self._combat is not None or self._combat_entry_sequence is not None or self._world.active_combat_launch_key is not None:
            raise ReducedRunBackendError("Noncombat boundary cannot retain combat state.")
        if phase is DecisionPhase.REWARD:
            if self._world.terminal_result is not None or self._world.pending_decision is None:
                raise ReducedRunBackendError("Reward boundary has inconsistent private ownership.")
            decision = self._reward_rules.decision(self._world)
            if decision.status is not DecisionStatus.ACTIONABLE or not decision.candidates:
                raise ReducedRunBackendError("Reward boundary must be actionable; WAITING joins automatically.")
        elif phase is DecisionPhase.MAP:
            if (
                self._world.terminal_result is not None
                or self._world.pending_decision is None
                or self._world.pending_decision.decision_kind != "map_choose_node"
            ):
                raise ReducedRunBackendError("Map boundary has no exact pending map decision.")
            assert self._map_rules is not None
            decision = self._map_rules.decision(self._world)
            if decision.status is not DecisionStatus.ACTIONABLE or not decision.candidates:
                raise ReducedRunBackendError("Map boundary must be actionable.")
        elif phase is DecisionPhase.ROOM:
            if (
                self._world.terminal_result is not None
                or self._world.pending_decision is None
                or self._world.pending_decision.decision_kind != ROOM_DECISION_KIND
            ):
                raise ReducedRunBackendError("Room boundary has no exact pending room decision.")
            assert self._boundary_scope is not None
            if not room_candidates(self._world, self._boundary_scope):
                raise ReducedRunBackendError("Room boundary must be actionable.")
        elif phase is DecisionPhase.TERMINAL:
            if (
                self._world.pending_decision is not None
                or self._world.terminal_result is None
            ):
                raise ReducedRunBackendError("Terminal boundary has no supported stop reason.")
            expected_persistent_reason = {
                "defeat": "defeat",
                "route_complete": "map_complete",
            }[self._terminal_reason]
            expected_outcome = {
                "defeat": RunOutcome.DEFEAT,
                "route_complete": RunOutcome.VICTORY,
            }[self._terminal_reason]
            if (
                self._world.terminal_result.reason != expected_persistent_reason
                or self._world.terminal_result.outcome is not expected_outcome
            ):
                raise ReducedRunBackendError("Terminal reason disagrees with persistent state.")
        elif phase is DecisionPhase.UNSUPPORTED:
            if self._world.pending_decision is not None or self._world.terminal_result is not None:
                raise ReducedRunBackendError("Unsupported boundary retains hidden phase state.")

    def _validate_world_config_rng_provenance(self) -> None:
        """Bind world identity and every combat launch to config and named RNG history."""

        assert self._world is not None and self._config is not None and self._settings is not None
        if self._world.rng.seed != self._config.game_seed:
            raise ReducedRunBackendError("World RNG seed does not match the exact run config.")
        if self._settings != _resolved_settings(self._config):
            raise ReducedRunBackendError("Resolved backend settings changed after configuration.")

        nodes = {node.instance_id: node for node in self._world.map_nodes}
        try:
            launch_count = sum(
                nodes[node_id].node_kind is NodeKind.COMBAT
                for node_id in self._world.node_history
            )
        except KeyError as error:
            raise ReducedRunBackendError("Map history cannot bind combat launch provenance.") from error
        if self._world.rng_stream_counters()["combat_launch"] != launch_count:
            raise ReducedRunBackendError("Combat launch count does not match visited combat nodes.")

        replay_rng = GameRandomService(self._config.game_seed)
        launch_seeds = [
            replay_rng.randint(COMBAT_LAUNCH_STREAM, 0, (1 << 63) - 1)
            for _ in range(launch_count)
        ]
        actual_stream = self._world.rng.snapshot()["streams"].get(COMBAT_LAUNCH_STREAM)
        expected_stream = replay_rng.snapshot()["streams"].get(COMBAT_LAUNCH_STREAM)
        if actual_stream != expected_stream:
            raise ReducedRunBackendError("Combat launch RNG state does not match its named history.")

        if self._world.phase is DecisionPhase.COMBAT:
            if not launch_seeds or self._combat is None or self._combat.launch_spec is None:
                raise ReducedRunBackendError("Active combat cannot bind its launch RNG draw.")
            launch = self._combat.launch_spec
            if (
                launch.combat_seed != launch_seeds[-1]
                or launch.scenario_id != self._config.scenario_id
                or launch.to_dict()["combat_settings"] != self._settings["combat_settings"]
            ):
                raise ReducedRunBackendError("Combat launch does not match RNG/config provenance.")

    def _validate_parked_map_continuation(self) -> None:
        """Replay-validate the parked pending map decision without mutating live state."""

        assert self._world is not None and self._map_rules is not None
        pending = _map_continuation(self._world)
        temporary = WorldState.from_private_dict(self._world.to_private_dict())
        temporary.pending_decision = pending
        temporary.automatic_queue = ()
        temporary.active_combat_launch_key = None
        temporary.phase = DecisionPhase.MAP
        temporary.terminal_result = None
        temporary.validate()
        self._map_rules.decision(temporary)

    def _transaction_preimage(self) -> dict[str, Any]:
        assert self._world is not None
        return {
            "world": self._world.to_private_dict(),
            "combat": None if self._combat is None else self._combat.snapshot(),
            "combat_entry_sequence": self._combat_entry_sequence,
            "last_public_events": self._last_public_events,
            "boundary_scope": self._boundary_scope,
            "terminal_reason": self._terminal_reason,
            "unsupported_reason": self._unsupported_reason,
            "outer_sequence": self._outer_sequence,
            "decision": self._decision,
        }

    def _restore_transaction_preimage(self, preimage: Mapping[str, Any]) -> None:
        self._world = WorldState.from_private_dict(preimage["world"])
        combat_snapshot = preimage["combat"]
        if combat_snapshot is None:
            self._combat = None
        else:
            combat = CombatV0Backend()
            combat.restore(combat_snapshot)
            self._combat = combat
        self._combat_entry_sequence = preimage["combat_entry_sequence"]
        self._last_public_events = preimage["last_public_events"]
        self._boundary_scope = preimage["boundary_scope"]
        self._terminal_reason = preimage["terminal_reason"]
        self._unsupported_reason = preimage["unsupported_reason"]
        self._outer_sequence = preimage["outer_sequence"]
        self._decision = preimage["decision"]

    def _parse_snapshot(self, snapshot: Mapping[str, Any]) -> "ReducedRunBackend":
        if not isinstance(snapshot, Mapping):
            raise ReducedRunBackendError("Snapshot must be an object.")
        expected = {
            "backend_fingerprint",
            "combat_snapshot",
            "combat_entry_sequence",
            "config",
            "content_fingerprint",
            "contract_fingerprint",
            "current_decision_hash",
            "decision_sequence",
            "descriptor_hash",
            "last_public_events",
            "outer_run_id",
            "phase",
            "private_world_snapshot",
            "public_scope",
            "reset_generation",
            "rules_fingerprint",
            "snapshot_fingerprint",
            "snapshot_version",
            "status",
            "terminal_reason",
            "unsupported_reason",
        }
        if set(snapshot) != expected:
            raise ReducedRunBackendError("Snapshot fields do not match the H3 schema.")
        descriptor = {key: snapshot[key] for key in expected if key != "descriptor_hash"}
        identities = {
            "backend_fingerprint": BACKEND_FINGERPRINT,
            "content_fingerprint": CONTENT_FINGERPRINT,
            "contract_fingerprint": CONTRACT_FINGERPRINT,
            "rules_fingerprint": RULES_FINGERPRINT,
            "snapshot_fingerprint": SNAPSHOT_FINGERPRINT,
            "snapshot_version": SNAPSHOT_VERSION,
        }
        if any(snapshot[name] != value for name, value in identities.items()):
            raise ReducedRunBackendError("Snapshot provenance is incompatible.")
        if snapshot["descriptor_hash"] != _canonical_hash(
            "reduced_headless.snapshot_descriptor.v1", descriptor
        ):
            raise ReducedRunBackendError("Snapshot descriptor hash is invalid.")
        config_payload = snapshot["config"]
        world_payload = snapshot["private_world_snapshot"]
        scope_payload = snapshot["public_scope"]
        events_payload = snapshot["last_public_events"]
        if not all(isinstance(item, Mapping) for item in (config_payload, world_payload, scope_payload)):
            raise ReducedRunBackendError("Snapshot object payload has the wrong type.")
        if not isinstance(events_payload, list) or not all(isinstance(item, Mapping) for item in events_payload):
            raise ReducedRunBackendError("Snapshot events have the wrong type.")
        config = HeadlessRunConfig.from_dict(config_payload)
        generation = snapshot["reset_generation"]
        sequence = snapshot["decision_sequence"]
        combat_entry_sequence = snapshot["combat_entry_sequence"]
        if (
            not isinstance(generation, int)
            or isinstance(generation, bool)
            or generation < 0
            or not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or sequence < 0
        ):
            raise ReducedRunBackendError("Snapshot generation and sequence must be nonnegative integers.")
        if combat_entry_sequence is not None and (
            not isinstance(combat_entry_sequence, int)
            or isinstance(combat_entry_sequence, bool)
            or not 0 <= combat_entry_sequence <= sequence
        ):
            raise ReducedRunBackendError("Snapshot combat entry sequence is invalid.")
        if snapshot["outer_run_id"] != _outer_run_id(config, generation):
            raise ReducedRunBackendError("Snapshot outer run identity is invalid.")
        try:
            phase = DecisionPhase(snapshot["phase"])
            status = DecisionStatus(snapshot["status"])
            scope = PublicScope.from_dict(scope_payload)
            events = tuple(PublicEvent.from_dict(item) for item in events_payload)
            world_snapshot = PrivateWorldSnapshot.from_dict(world_payload)
            world = self._codec.restore(world_snapshot)
        except (ValueError, TypeError) as error:
            raise ReducedRunBackendError("Snapshot payload is invalid.") from error
        settings = _resolved_settings(config)
        map_rules = MapRules(settings["map_template_id"], world_rules_fingerprint=RULES_FINGERPRINT)
        combat_payload = snapshot["combat_snapshot"]
        combat = None
        if combat_payload is not None:
            if not isinstance(combat_payload, Mapping):
                raise ReducedRunBackendError("Combat snapshot must be null or an object.")
            combat = CombatV0Backend()
            combat.restore(combat_payload)
        candidate = ReducedRunBackend()
        candidate._config = config
        candidate._settings = settings
        candidate._reset_generation = generation
        candidate._generation_high_water = generation
        candidate._outer_run_id = snapshot["outer_run_id"]
        candidate._outer_sequence = sequence
        candidate._combat_entry_sequence = combat_entry_sequence
        candidate._world = world
        candidate._map_rules = map_rules
        candidate._combat = combat
        candidate._last_public_events = events
        candidate._boundary_scope = scope
        candidate._terminal_reason = snapshot["terminal_reason"]
        candidate._unsupported_reason = snapshot["unsupported_reason"]
        try:
            candidate._validate_private_boundary()
            candidate._decision = candidate._project_current()
        except (ValueError, TypeError, RuntimeError) as error:
            raise ReducedRunBackendError("Snapshot private boundary is inconsistent.") from error
        if (
            candidate._decision.phase is not phase
            or candidate._decision.status is not status
            or candidate._decision.decision_hash != snapshot["current_decision_hash"]
            or candidate._decision.observation.public_scope != scope
        ):
            raise ReducedRunBackendError("Snapshot does not reconstruct its exact public boundary.")
        return candidate

    def _install_from(self, other: "ReducedRunBackend") -> None:
        for descriptor in fields(ReducedRunBackendState):
            setattr(self, descriptor.name, getattr(other, descriptor.name))


@dataclass(slots=True)
class ReducedRunBackendState:
    """Internal field list used only for atomic backend installation."""

    _config: Any = None
    _settings: Any = None
    _reset_generation: Any = None
    _generation_high_water: Any = None
    _outer_run_id: Any = None
    _outer_sequence: Any = None
    _combat_entry_sequence: Any = None
    _world: Any = None
    _codec: Any = None
    _map_rules: Any = None
    _reward_rules: Any = None
    _combat: Any = None
    _last_public_events: Any = None
    _boundary_scope: Any = None
    _terminal_reason: Any = None
    _unsupported_reason: Any = None
    _decision: Any = None


def _suspend_map(world: WorldState, target_phase: DecisionPhase) -> None:
    if world.phase is not DecisionPhase.MAP or world.pending_decision is None:
        raise ReducedRunBackendError("Map continuation can only suspend from a map decision.")
    if world.pending_decision.decision_kind != "map_choose_node" or world.automatic_queue:
        raise ReducedRunBackendError("Map continuation is not uniquely owned.")
    world.automatic_queue = (
        AutomaticTransition(
            MAP_CONTINUATION_KIND,
            {"pending_decision": world.pending_decision.to_dict()},
        ),
    )
    world.pending_decision = None
    world.phase = target_phase
    world.validate()


def _map_continuation(world: WorldState) -> PendingDecision:
    if len(world.automatic_queue) != 1:
        raise ReducedRunBackendError("Non-map phase requires exactly one map continuation.")
    transition = world.automatic_queue[0]
    if transition.transition_kind != MAP_CONTINUATION_KIND:
        raise ReducedRunBackendError("Automatic transition is not the map continuation.")
    payload = transition.private_payload
    if set(payload) != {"pending_decision"} or not isinstance(payload["pending_decision"], Mapping):
        raise ReducedRunBackendError("Map continuation payload fields are invalid.")
    pending = PendingDecision.from_dict(payload["pending_decision"])
    if pending.decision_kind != "map_choose_node":
        raise ReducedRunBackendError("Map continuation does not contain a map decision.")
    return pending


def _resume_map(world: WorldState) -> None:
    pending = _map_continuation(world)
    if world.pending_decision is not None:
        # Reward WAITING is a completed child session; room proceed clears its
        # own pending state.  No other pending value is safe to overwrite.
        if not world.pending_decision.decision_kind.startswith("reward_p."):
            raise ReducedRunBackendError("Completed child did not release its pending state.")
    world.pending_decision = pending
    world.automatic_queue = ()
    world.phase = DecisionPhase.MAP
    world.terminal_result = None
    world.validate()


def create_reduced_run_backend() -> ReducedRunBackend:
    """Return a fresh backend through a top-level spawn/pickle-safe callable."""

    return ReducedRunBackend()


__all__ = [
    "BACKEND_FINGERPRINT",
    "BACKEND_ID",
    "BACKEND_VERSION",
    "HeadlessRunConfig",
    "RULES_FINGERPRINT",
    "RULES_VERSION",
    "ReducedRunBackend",
    "ReducedRunBackendError",
    "SNAPSHOT_FINGERPRINT",
    "SNAPSHOT_VERSION",
    "create_reduced_run_backend",
]
