"""Combat-only ``headless_v0`` backend over the legacy :class:`CombatEnv`.

The backend is a composition layer.  Persistent identity and combat handoffs
remain owned by ``headless_state``; public projection and candidate decoding
remain owned by their accepted adapters; and combat rules remain owned by the
legacy simulator.  Exact recovery is intentionally expressed as replay from a
validated launch plus accepted decision-scoped candidate history.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from game.backends.headless.combat_candidates import (
    CombatCandidateMapping,
    InvalidCombatCandidateError,
    StaleCombatCandidateError,
    decode_combat_action_request,
    finalize_combat_candidate_mapping,
    generate_combat_candidates,
)
from game.backends.headless.combat_projection import (
    CARD_DEFINITION_IDS,
    COMBAT_PROJECTION_VERSION,
    ENEMY_DEFINITION_IDS,
    project_combat_observation,
)
from game.backends.headless.scenarios import (
    SCENARIO_SCHEMA,
    CombatScenario,
    scenario_from_id,
)
from game.content.card_upgrades import (
    BASE_CARD_PROFILE,
    STRIKE_UPGRADE_PROFILE,
    STRIKE_UPGRADE_CONTENT_FINGERPRINT,
    validate_card_profile,
)
from game.content.reduced_v0 import (
    CONTENT_FINGERPRINT,
    CONTENT_VERSION,
    REWARDABLE_CARD_DEFINITION_IDS,
    SUPPORTED_CARD_DEFINITIONS,
    materialize_card_definition,
)
from game.contracts.headless_v0 import (
    ActionRequest,
    BackendCapabilities,
    BackendManifest,
    CombatEndTurnCandidate,
    CombatOutcome,
    CombatPlayCardCandidate,
    ComponentEvidence,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    EvidenceLabel,
    PublicEvent,
    PublicEventKind,
    PublicObservation,
    PublicReferenceKind,
    PublicScope,
    RunOutcome,
    Transition,
    TransitionReason,
    TransitionResult,
)
from game.engine.headless_state import (
    CombatLaunchSpec,
    CombatResolution,
    PersistentCardInstance,
)
from game.simulation.card import StrikeCard
from game.simulation.env_factory import CombatEnvFactory


BACKEND_ID = "combat_v0"
BACKEND_VERSION = "combat_v0_backend_v1"
RULES_VERSION = "legacy_combat_v0"
SNAPSHOT_VERSION = "combat_v0_replay_snapshot_v1"
STANDALONE_SEED_NORMALIZATION = "python_integer_modulo_2_to_63_v1"
_COMBAT_SEED_MODULUS = 1 << 63

_CARD_DEFINITIONS = {
    definition.definition_id: definition for definition in SUPPORTED_CARD_DEFINITIONS
}
_LEGACY_CARD_DEFINITION_IDS = {
    legacy_name: definition_id
    for legacy_name, definition_id in CARD_DEFINITION_IDS.items()
}
_SUPPORTED_SETTING_KEYS = frozenset(
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


class CombatV0BackendError(ValueError):
    """Raised when a combat backend configuration or snapshot is invalid."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _fingerprint(domain: str, value: Any) -> str:
    return sha256(f"{domain}\0{_canonical_json(value)}".encode("utf-8")).hexdigest()


RULES_FINGERPRINT = _fingerprint(
    "combat_v0_backend.rules.v1",
    {
        "candidate_adapter": "decision_bound_combat_candidates_v1",
        "card_definitions": sorted(CARD_DEFINITION_IDS.items()),
        "enemy_definitions": sorted(ENEMY_DEFINITION_IDS.items()),
        "projection": COMBAT_PROJECTION_VERSION,
        "rules_version": RULES_VERSION,
        "scenario_schema": SCENARIO_SCHEMA,
    },
)
BACKEND_FINGERPRINT = _fingerprint(
    "combat_v0_backend.schema.v1",
    {
        "backend_id": BACKEND_ID,
        "backend_version": BACKEND_VERSION,
        "content_fingerprint": CONTENT_FINGERPRINT,
        "operations": (
            "reset",
            "observe",
            "apply",
            "snapshot",
            "restore",
            "manifest",
            "close",
        ),
        "recovery": "launch_plus_accepted_candidate_history",
        "rules_fingerprint": RULES_FINGERPRINT,
        "snapshot_version": SNAPSHOT_VERSION,
        "standalone_seed_normalization": {
            "modulus": _COMBAT_SEED_MODULUS,
            "rule": STANDALONE_SEED_NORMALIZATION,
        },
        "supported_settings": sorted(_SUPPORTED_SETTING_KEYS),
    },
)


def _manifest() -> BackendManifest:
    projection_fingerprint = _fingerprint(
        "combat_v0_backend.projection.v1",
        {
            "card_definitions": sorted(CARD_DEFINITION_IDS.items()),
            "enemy_definitions": sorted(ENEMY_DEFINITION_IDS.items()),
            "version": COMBAT_PROJECTION_VERSION,
        },
    )
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
            legacy_shaped_reward_diagnostics=True,
        ),
        supported_phases=(DecisionPhase.COMBAT,),
        unsupported_phases=(
            DecisionPhase.MAP,
            DecisionPhase.REWARD,
            DecisionPhase.ROOM,
        ),
        evidence=(
            ComponentEvidence(
                "backend", EvidenceLabel.COMBAT_V0, BACKEND_VERSION, BACKEND_FINGERPRINT
            ),
            ComponentEvidence(
                "content",
                EvidenceLabel.STRUCTURAL_FIXTURE,
                CONTENT_VERSION,
                CONTENT_FINGERPRINT,
            ),
            ComponentEvidence(
                "projection",
                EvidenceLabel.COMBAT_V0,
                COMBAT_PROJECTION_VERSION,
                projection_fingerprint,
            ),
            ComponentEvidence(
                "rules", EvidenceLabel.COMBAT_V0, RULES_VERSION, RULES_FINGERPRINT
            ),
        ),
    )


_BACKEND_MANIFEST = _manifest()


def _manifest_for_profile(card_profile: str) -> BackendManifest:
    validate_card_profile(card_profile)
    if card_profile == BASE_CARD_PROFILE:
        return _BACKEND_MANIFEST
    version = f"{BACKEND_VERSION}_{card_profile}"
    rules_version = f"{RULES_VERSION}_{card_profile}"
    rules_fingerprint = _fingerprint(
        "combat_v0_backend.upgrade_rules.v1",
        {
            "base_rules": RULES_FINGERPRINT,
            "content": STRIKE_UPGRADE_CONTENT_FINGERPRINT,
            "profile": card_profile,
        },
    )
    backend_fingerprint = _fingerprint(
        "combat_v0_backend.upgrade_backend.v1",
        {
            "base_backend": BACKEND_FINGERPRINT,
            "rules": rules_fingerprint,
            "version": version,
        },
    )
    projection_version = f"{COMBAT_PROJECTION_VERSION}_{card_profile}"
    projection_fingerprint = _fingerprint(
        "combat_v0_backend.upgrade_projection.v1",
        {
            "base_projection": _BACKEND_MANIFEST.evidence[2].fingerprint,
            "version": projection_version,
            "variants": [["Strike+", "strike", True, 1]],
        },
    )
    return replace(
        _BACKEND_MANIFEST,
        backend_version=version,
        backend_fingerprint=backend_fingerprint,
        content_version=card_profile,
        content_fingerprint=STRIKE_UPGRADE_CONTENT_FINGERPRINT,
        rules_version=rules_version,
        rules_fingerprint=rules_fingerprint,
        evidence=(
            ComponentEvidence("backend", EvidenceLabel.COMBAT_V0, version, backend_fingerprint),
            ComponentEvidence(
                "content", EvidenceLabel.STRUCTURAL_FIXTURE,
                card_profile, STRIKE_UPGRADE_CONTENT_FINGERPRINT,
            ),
            ComponentEvidence(
                "projection", EvidenceLabel.COMBAT_V0,
                projection_version, projection_fingerprint,
            ),
            ComponentEvidence(
                "rules", EvidenceLabel.COMBAT_V0, rules_version, rules_fingerprint,
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class _BuiltState:
    environment: Any
    decision: DecisionState
    mapping: CombatCandidateMapping | None
    resolution: CombatResolution | None
    public_events: tuple[PublicEvent, ...]
    legacy_diagnostics: Mapping[str, Any] | None


class CombatV0Backend:
    """A deterministic, combat-only implementation of ``headless_v0``."""

    def __init__(self, *, card_profile: str = BASE_CARD_PROFILE) -> None:
        self._manifest = _manifest_for_profile(card_profile)
        self._card_profile = card_profile
        self._launch: CombatLaunchSpec | None = None
        self._accepted_candidate_ids: tuple[str, ...] = ()
        self._environment: Any = None
        self._decision: DecisionState | None = None
        self._mapping: CombatCandidateMapping | None = None
        self._resolution: CombatResolution | None = None
        self._last_public_events: tuple[PublicEvent, ...] = ()
        self._legacy_diagnostics: Mapping[str, Any] | None = None

    @property
    def launch_spec(self) -> CombatLaunchSpec | None:
        """Return the immutable active launch, if reset has completed."""
        return self._launch

    @property
    def resolution(self) -> CombatResolution | None:
        """Return the validated terminal handoff, or ``None`` while ongoing."""
        return self._resolution

    @property
    def accepted_action_history(self) -> tuple[str, ...]:
        """Return the private replay history of accepted candidate IDs."""
        return self._accepted_candidate_ids

    @property
    def last_legacy_diagnostics(self) -> Mapping[str, Any] | None:
        """Return explicitly adapter-labelled legacy shaped-reward diagnostics."""
        if self._legacy_diagnostics is None:
            return None
        return deepcopy(dict(self._legacy_diagnostics))

    def get_resolution(self) -> CombatResolution | None:
        """Method form of :attr:`resolution` for composer integrations."""
        return self._resolution

    def manifest(self) -> BackendManifest:
        return self._manifest

    def reset(
        self,
        configuration: CombatScenario | CombatLaunchSpec | Mapping[str, Any] | str | None,
    ) -> DecisionState:
        """Start from a standalone scenario or a composer-issued launch."""
        launch = _configuration_to_launch(configuration, card_profile=self._card_profile)
        built = self._rebuild(launch, ())
        self._install(launch, (), built)
        return built.decision

    def observe(self) -> DecisionState:
        if self._decision is None:
            raise RuntimeError("Combat backend is not initialized. Call reset() or restore().")
        return self._decision

    def apply(self, action: ActionRequest) -> Transition:
        if not isinstance(action, ActionRequest):
            raise TypeError("action must be an ActionRequest.")
        current = self.observe()
        mapping = self._mapping
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
        if mapping is None:
            return Transition(
                TransitionResult.REJECTED,
                TransitionReason.INVALID_CANDIDATE,
                binding,
                current.public_events,
                current,
            )

        try:
            legacy_action = decode_combat_action_request(current, mapping, action)
        except InvalidCombatCandidateError:
            return Transition(
                TransitionResult.REJECTED,
                TransitionReason.INVALID_CANDIDATE,
                binding,
                current.public_events,
                current,
            )
        except StaleCombatCandidateError:
            return Transition(
                TransitionResult.STALE,
                TransitionReason.STALE_BINDING,
                binding,
                current.public_events,
                current,
            )

        candidate = next(
            candidate
            for candidate in current.candidates
            if candidate.candidate_id == binding.candidate_id
        )
        events = _events_for_candidate(current, candidate)
        try:
            _observation, reward, done, info = self._environment.step(legacy_action)
        except (RuntimeError, ValueError):
            # The mapped action was legal when advertised.  Rebuild from the
            # authoritative replay descriptor before returning a rules rejection
            # so an exceptional legacy step can never leak partial mutation.
            assert self._launch is not None
            rebuilt = self._rebuild(self._launch, self._accepted_candidate_ids)
            self._install(self._launch, self._accepted_candidate_ids, rebuilt)
            current = self.observe()
            return Transition(
                TransitionResult.REJECTED,
                TransitionReason.REJECTED_BY_RULES,
                binding,
                current.public_events,
                current,
            )

        if done:
            outcome = _environment_outcome(self._environment)
            events += (
                PublicEvent(
                    len(events),
                    PublicEventKind.COMBAT_RESOLVED,
                    DecisionPhase.COMBAT,
                    {"outcome": outcome.value},
                ),
            )
        history = self._accepted_candidate_ids + (binding.candidate_id,)
        diagnostics = {
            "evidence": EvidenceLabel.COMBAT_V0.value,
            "legacy_shaped_reward": reward,
            "legacy_info": dict(info),
        }
        next_state = self._build_current_state(
            self._environment,
            self._launch,
            history,
            events,
            diagnostics,
        )
        self._install(self._launch, history, next_state)
        return Transition(
            TransitionResult.ACCEPTED,
            TransitionReason.ACCEPTED,
            binding,
            events,
            next_state.decision,
        )

    def snapshot(self) -> dict[str, Any]:
        """Return the exact private replay descriptor for this decision."""
        if self._launch is None or self._decision is None:
            raise RuntimeError("Combat backend is not initialized.")
        descriptor = {
            "accepted_candidate_ids": list(self._accepted_candidate_ids),
            "backend_fingerprint": self._manifest.backend_fingerprint,
            "launch": self._launch.to_dict(),
            "snapshot_version": SNAPSHOT_VERSION,
        }
        return {
            **descriptor,
            "descriptor_hash": _fingerprint(
                "combat_v0_backend.snapshot_descriptor.v1", descriptor
            ),
        }

    def restore(self, snapshot: Mapping[str, Any]) -> DecisionState:
        """Atomically restore and verify exact continuation by deterministic replay."""
        launch, history = _parse_snapshot(snapshot, card_profile=self._card_profile)
        built = self._rebuild(launch, history)
        self._install(launch, history, built)
        return built.decision

    def close(self) -> None:
        self._launch = None
        self._accepted_candidate_ids = ()
        self._environment = None
        self._decision = None
        self._mapping = None
        self._resolution = None
        self._last_public_events = ()
        self._legacy_diagnostics = None

    def _rebuild(
        self,
        launch: CombatLaunchSpec,
        history: Sequence[str],
    ) -> _BuiltState:
        environment = _build_environment(launch, card_profile=self._card_profile)
        events: tuple[PublicEvent, ...] = ()
        diagnostics: Mapping[str, Any] | None = None
        consumed: list[str] = []
        for sequence, candidate_id in enumerate(history):
            if environment.done:
                raise CombatV0BackendError("Replay history continues after terminal combat.")
            scope = _public_scope(sequence)
            mapping = generate_combat_candidates(environment, scope, card_profile=self._card_profile)
            try:
                legacy_action = mapping.action_for(candidate_id)
            except InvalidCombatCandidateError as error:
                raise CombatV0BackendError(
                    "Replay history contains a candidate unavailable at its decision."
                ) from error
            candidate = next(
                item for item in mapping.candidates if item.candidate_id == candidate_id
            )
            observation = project_combat_observation(
                environment.get_observation(), scope, card_profile=self._card_profile
            )
            decision = DecisionState.create(
                **_decision_identity(launch.run_id, sequence, self._manifest),
                status=DecisionStatus.ACTIONABLE,
                phase=DecisionPhase.COMBAT,
                observation=observation,
                candidates=mapping.candidates,
                public_events=events,
            )
            # Finalization proves the same decision-scoped identity used during
            # live apply even though replay already recovered the tuple above.
            finalize_combat_candidate_mapping(decision, mapping)
            events = _events_for_candidate(decision, candidate)
            _next, reward, done, info = environment.step(legacy_action)
            if done:
                outcome = _environment_outcome(environment)
                events += (
                    PublicEvent(
                        len(events),
                        PublicEventKind.COMBAT_RESOLVED,
                        DecisionPhase.COMBAT,
                        {"outcome": outcome.value},
                    ),
                )
            diagnostics = {
                "evidence": EvidenceLabel.COMBAT_V0.value,
                "legacy_shaped_reward": reward,
                "legacy_info": dict(info),
            }
            consumed.append(candidate_id)
        if tuple(consumed) != tuple(history):
            raise CombatV0BackendError("Replay history was not consumed exactly.")
        return self._build_current_state(
            environment,
            launch,
            tuple(history),
            events,
            diagnostics,
        )

    def _build_current_state(
        self,
        environment: Any,
        launch: CombatLaunchSpec | None,
        history: Sequence[str],
        events: tuple[PublicEvent, ...],
        diagnostics: Mapping[str, Any] | None,
    ) -> _BuiltState:
        assert launch is not None
        sequence = len(history)
        scope = _public_scope(sequence)
        if environment.done:
            outcome = _environment_outcome(environment)
            assert environment.player is not None
            observation = PublicObservation(
                DecisionPhase.TERMINAL,
                {
                    "outcome": (
                        RunOutcome.VICTORY.value
                        if outcome is CombatOutcome.VICTORY
                        else RunOutcome.DEFEAT.value
                    ),
                    "player": {
                        "deck_size": len(launch.ordered_deck),
                        "gold": 0,
                        "hp": environment.player.hp,
                        "max_hp": environment.player.max_hp,
                    },
                },
                scope,
            )
            decision = DecisionState.create(
                **_decision_identity(launch.run_id, sequence, self._manifest),
                status=DecisionStatus.TERMINAL,
                phase=DecisionPhase.TERMINAL,
                observation=observation,
                public_events=events,
            )
            replay_reference = "replay.combat." + _fingerprint(
                "combat_v0_backend.replay.v1",
                {
                    "accepted_candidate_ids": list(history),
                    "launch": launch.to_dict(),
                    **(
                        {"backend_fingerprint": self._manifest.backend_fingerprint}
                        if self._card_profile != BASE_CARD_PROFILE else {}
                    ),
                },
            )
            resolution = CombatResolution(
                run_id=launch.run_id,
                launch_key=launch.semantic_key(),
                outcome=outcome,
                final_hp=environment.player.hp,
                replay_reference=replay_reference,
            )
            return _BuiltState(
                environment, decision, None, resolution, events, diagnostics
            )

        mapping = generate_combat_candidates(environment, scope, card_profile=self._card_profile)
        observation = project_combat_observation(
            environment.get_observation(), scope, card_profile=self._card_profile
        )
        decision = DecisionState.create(
            **_decision_identity(launch.run_id, sequence, self._manifest),
            status=DecisionStatus.ACTIONABLE,
            phase=DecisionPhase.COMBAT,
            observation=observation,
            candidates=mapping.candidates,
            public_events=events,
        )
        finalized = finalize_combat_candidate_mapping(decision, mapping)
        return _BuiltState(environment, decision, finalized, None, events, diagnostics)

    def _install(
        self,
        launch: CombatLaunchSpec | None,
        history: Sequence[str],
        built: _BuiltState,
    ) -> None:
        self._launch = launch
        self._accepted_candidate_ids = tuple(history)
        self._environment = built.environment
        self._decision = built.decision
        self._mapping = built.mapping
        self._resolution = built.resolution
        self._last_public_events = built.public_events
        self._legacy_diagnostics = built.legacy_diagnostics


def _decision_identity(
    run_id: str, sequence: int, manifest: BackendManifest = _BACKEND_MANIFEST,
) -> dict[str, Any]:
    return {
        **{name: getattr(manifest, name) for name in (
            "backend_id", "backend_version", "backend_fingerprint",
            "content_version", "content_fingerprint", "rules_version", "rules_fingerprint",
        )},
        "run_id": run_id,
        "decision_sequence": sequence,
    }


def _public_scope(decision_ordinal: int) -> PublicScope:
    reveals = {kind.value: 0 for kind in PublicReferenceKind}
    reveals[PublicReferenceKind.CARD.value] = decision_ordinal
    return PublicScope(
        history_ordinal=0,
        decision_ordinal=decision_ordinal,
        reveal_ordinals=reveals,
    )


def _configuration_to_launch(
    configuration: CombatScenario | CombatLaunchSpec | Mapping[str, Any] | str | None,
    *, card_profile: str = BASE_CARD_PROFILE,
) -> CombatLaunchSpec:
    if configuration is None:
        configuration = scenario_from_id("simple__starter")
    elif isinstance(configuration, str):
        configuration = scenario_from_id(configuration)
    elif isinstance(configuration, Mapping):
        if configuration.get("schema") == SCENARIO_SCHEMA:
            configuration = CombatScenario.from_dict(configuration)
        elif "handoff_version" in configuration:
            configuration = CombatLaunchSpec.from_dict(configuration)
        else:
            raise CombatV0BackendError(
                "Configuration mapping must be a strict scenario or combat launch."
            )
    if isinstance(configuration, CombatLaunchSpec):
        _validate_launch(configuration, card_profile=card_profile)
        return configuration
    if not isinstance(configuration, CombatScenario):
        raise TypeError("configuration must be a scenario or CombatLaunchSpec.")
    return _standalone_launch(configuration)


def scenario_initial_deck_definition_ids(scenario_id: str) -> tuple[str, ...]:
    """Return the ordered persistent deck definitions for a registered scenario."""

    return _scenario_deck_definition_ids(scenario_from_id(scenario_id))


def _scenario_deck_definition_ids(scenario: CombatScenario) -> tuple[str, ...]:
    source_cards = scenario.build().deck_factory()
    definition_ids: list[str] = []
    for card in source_cards:
        try:
            definition_ids.append(_LEGACY_CARD_DEFINITION_IDS[card.name])
        except KeyError as error:
            raise CombatV0BackendError(
                f"Standalone scenario deck contains unsupported card {card.name!r}."
            ) from error
    return tuple(definition_ids)


def _standalone_launch(scenario: CombatScenario) -> CombatLaunchSpec:
    definition_ids = _scenario_deck_definition_ids(scenario)
    scenario_payload = scenario.to_dict()
    namespace = _fingerprint("combat_v0_backend.standalone.v1", scenario_payload)
    launch = CombatLaunchSpec(
        run_id=f"run.combat.{namespace[:32]}",
        scenario_id=scenario.scenario_id,
        combat_seed=_normalize_standalone_seed(scenario.seed),
        current_hp=scenario.player_max_hp,
        max_hp=scenario.player_max_hp,
        combat_settings={
            "cards_per_turn": scenario.cards_per_turn,
            "enemy_max_hp": scenario.enemy_max_hp,
            "hp_loss_penalty_scale_ratio": list(
                scenario.hp_loss_penalty_scale.as_integer_ratio()
            ),
            "incoming_damage_shaping_scale_ratio": list(
                scenario.incoming_damage_shaping_scale.as_integer_ratio()
            ),
            "record_trajectory": scenario.record_trajectory,
        },
        ordered_deck=tuple(
            PersistentCardInstance(
                f"card.combat.{namespace[:16]}.{index:08d}", definition_id
            )
            for index, definition_id in enumerate(definition_ids)
        ),
    )
    _validate_launch(launch)
    return launch


def _normalize_standalone_seed(seed: int) -> int:
    """Map H0's full integer domain into the launch seam's 63-bit domain.

    Seeds are congruent for combat RNG exactly when they are equal modulo
    ``2**63``.  The standalone run identity still hashes the original H0
    scenario descriptor, so distinct source seeds do not collapse control
    identity even when they intentionally select the same combat RNG stream.
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise CombatV0BackendError("Standalone scenario seed must be an integer.")
    return seed % _COMBAT_SEED_MODULUS


def _validate_launch(
    launch: CombatLaunchSpec, *, card_profile: str = BASE_CARD_PROFILE,
) -> None:
    validate_card_profile(card_profile)
    if not isinstance(launch, CombatLaunchSpec):
        raise TypeError("launch must be a CombatLaunchSpec.")
    scenario_from_id(launch.scenario_id)
    unknown = set(launch.combat_settings) - _SUPPORTED_SETTING_KEYS
    if unknown:
        raise CombatV0BackendError(f"Unsupported combat settings: {sorted(unknown)!r}.")
    if any(
        card.upgraded and not (
            card_profile == STRIKE_UPGRADE_PROFILE and card.definition_id == "strike"
        )
        for card in launch.ordered_deck
    ):
        raise CombatV0BackendError("This card profile cannot materialize these upgraded cards.")
    for card in launch.ordered_deck:
        if card.definition_id not in REWARDABLE_CARD_DEFINITION_IDS:
            raise CombatV0BackendError(
                f"Unsupported persistent card definition: {card.definition_id!r}."
            )


def _build_environment(
    launch: CombatLaunchSpec, *, card_profile: str = BASE_CARD_PROFILE,
) -> Any:
    _validate_launch(launch, card_profile=card_profile)
    scenario = scenario_from_id(launch.scenario_id)
    settings = dict(launch.combat_settings)
    record_trajectory = _setting_bool(
        settings,
        "record_trajectory",
        alias="record_history",
        default=scenario.record_trajectory,
    )
    enemy_max_hp = _setting_int(
        settings, "enemy_max_hp", scenario.enemy_max_hp, minimum=1
    )
    if scenario.encounter != "simple" and enemy_max_hp != scenario.enemy_max_hp:
        raise CombatV0BackendError(
            "combat_settings.enemy_max_hp is configurable only for the simple encounter."
        )
    factory = CombatEnvFactory(
        encounter_set=scenario.encounter,
        enemy_hp=enemy_max_hp,
        player_hp=launch.max_hp,
        cards_per_turn=_setting_int(
            settings, "cards_per_turn", scenario.cards_per_turn, minimum=1
        ),
        hp_loss_penalty_scale=_setting_scale(
            settings,
            "hp_loss_penalty_scale",
            "hp_loss_penalty_scale_ratio",
            scenario.hp_loss_penalty_scale,
        ),
        incoming_damage_shaping_scale=_setting_scale(
            settings,
            "incoming_damage_shaping_scale",
            "incoming_damage_shaping_scale_ratio",
            scenario.incoming_damage_shaping_scale,
        ),
        record_trajectory=record_trajectory,
        # The ordered launch deck replaces this preset immediately below.
        deck=scenario.deck,
    )
    environment = factory()
    if card_profile == STRIKE_UPGRADE_PROFILE:
        vocabulary = dict(environment.encoder.card_name_to_id)
        vocabulary["Strike+"] = max(vocabulary.values()) + 1
        environment.encoder = replace(environment.encoder, card_name_to_id=vocabulary)

    def materialize_launch_deck() -> list[Any]:
        cards = []
        for instance in launch.ordered_deck:
            card = (
                StrikeCard(upgraded=True) if instance.upgraded else
                materialize_card_definition(_CARD_DEFINITIONS[instance.definition_id])
            )
            # Private identity follows the object through draw, play and reshuffle.
            # Public references continue to come exclusively from public scope.
            if card_profile == STRIKE_UPGRADE_PROFILE:
                card.persistent_instance_id = instance.instance_id
            cards.append(card)
        return cards

    environment.deck_factory = materialize_launch_deck
    environment.energy_per_turn = _setting_int(
        settings, "energy_per_turn", environment.energy_per_turn, minimum=1
    )
    environment.reset(seed=launch.combat_seed)
    assert environment.player is not None
    environment.player.hp = launch.current_hp
    environment.last_observation = environment.get_observation()
    return environment


def _setting_int(
    settings: Mapping[str, Any], name: str, default: int, *, minimum: int
) -> int:
    value = settings.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise CombatV0BackendError(f"combat_settings.{name} is invalid.")
    return value


def _setting_bool(
    settings: Mapping[str, Any], name: str, *, alias: str, default: bool
) -> bool:
    if name in settings and alias in settings:
        raise CombatV0BackendError(f"combat_settings cannot contain both {name} and {alias}.")
    value = settings.get(name, settings.get(alias, default))
    if not isinstance(value, bool):
        raise CombatV0BackendError(f"combat_settings.{name} is invalid.")
    return value


def _setting_scale(
    settings: Mapping[str, Any], name: str, ratio_name: str, default: float
) -> float:
    if name in settings and ratio_name in settings:
        raise CombatV0BackendError(
            f"combat_settings cannot contain both {name} and {ratio_name}."
        )
    if ratio_name in settings:
        ratio = settings[ratio_name]
        if (
            not isinstance(ratio, (list, tuple))
            or len(ratio) != 2
            or any(not isinstance(item, int) or isinstance(item, bool) for item in ratio)
            or ratio[1] <= 0
            or ratio[0] < 0
        ):
            raise CombatV0BackendError(f"combat_settings.{ratio_name} is invalid.")
        return ratio[0] / ratio[1]
    if name not in settings:
        return float(default)
    value = settings[name]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CombatV0BackendError(f"combat_settings.{name} is invalid.")
    return float(value)


def _events_for_candidate(
    decision: DecisionState,
    candidate: CombatEndTurnCandidate | CombatPlayCardCandidate,
) -> tuple[PublicEvent, ...]:
    if isinstance(candidate, CombatEndTurnCandidate):
        return (
            PublicEvent(
                0,
                PublicEventKind.COMBAT_TURN_ENDED,
                DecisionPhase.COMBAT,
                {},
            ),
        )
    hand = decision.observation.data["hand"]
    enemies = decision.observation.data["enemies"]
    card_definition_id = next(
        card["card_definition_id"]
        for card in hand
        if card["card_ref"] == candidate.card_ref
    )
    target_definition_id = None
    if candidate.target_ref is not None:
        target_definition_id = next(
            enemy["enemy_definition_id"]
            for enemy in enemies
            if enemy["enemy_ref"] == candidate.target_ref
        )
    return (
        PublicEvent(
            0,
            PublicEventKind.COMBAT_CARD_PLAYED,
            DecisionPhase.COMBAT,
            {
                "card_definition_id": card_definition_id,
                "target_enemy_definition_id": target_definition_id,
            },
        ),
    )


def _environment_outcome(environment: Any) -> CombatOutcome:
    if not environment.done:
        return CombatOutcome.ONGOING
    if environment.winner == "player":
        return CombatOutcome.VICTORY
    if environment.winner == "enemy":
        return CombatOutcome.DEFEAT
    raise CombatV0BackendError("Terminal CombatEnv has no supported winner.")


def _parse_snapshot(
    snapshot: Mapping[str, Any],
    *, card_profile: str = BASE_CARD_PROFILE,
) -> tuple[CombatLaunchSpec, tuple[str, ...]]:
    if not isinstance(snapshot, Mapping):
        raise CombatV0BackendError("Snapshot must be an object.")
    expected = {
        "accepted_candidate_ids",
        "backend_fingerprint",
        "descriptor_hash",
        "launch",
        "snapshot_version",
    }
    if set(snapshot) != expected:
        raise CombatV0BackendError("Snapshot fields do not match the replay schema.")
    descriptor = {key: snapshot[key] for key in expected if key != "descriptor_hash"}
    if snapshot["snapshot_version"] != SNAPSHOT_VERSION:
        raise CombatV0BackendError("Snapshot version is incompatible.")
    if snapshot["backend_fingerprint"] != _manifest_for_profile(card_profile).backend_fingerprint:
        raise CombatV0BackendError("Snapshot backend fingerprint is incompatible.")
    if snapshot["descriptor_hash"] != _fingerprint(
        "combat_v0_backend.snapshot_descriptor.v1", descriptor
    ):
        raise CombatV0BackendError("Snapshot replay descriptor hash is invalid.")
    launch_payload = snapshot["launch"]
    history_payload = snapshot["accepted_candidate_ids"]
    if not isinstance(launch_payload, Mapping):
        raise CombatV0BackendError("Snapshot launch must be an object.")
    if not isinstance(history_payload, list) or not all(
        isinstance(candidate_id, str) for candidate_id in history_payload
    ):
        raise CombatV0BackendError("Snapshot history must be an array of candidate IDs.")
    try:
        launch = CombatLaunchSpec.from_dict(launch_payload)
    except ValueError as error:
        raise CombatV0BackendError("Snapshot launch is invalid.") from error
    _validate_launch(launch, card_profile=card_profile)
    return launch, tuple(history_payload)
