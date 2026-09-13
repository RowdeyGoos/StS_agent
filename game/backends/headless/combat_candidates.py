"""Decision-scoped typed candidates for the legacy :class:`CombatEnv`.

This adapter intentionally delegates legality to ``CombatEnv.get_legal_actions``.
It translates each current legal tuple action into the accepted ``headless_v0``
combat candidate subset, while retaining the exact legacy tuple only in an
immutable, one-decision mapping used for decoding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Sequence

from game.backends.headless.combat_projection import (
    CARD_DEFINITION_IDS,
    ENEMY_DEFINITION_IDS,
)
from game.content.card_upgrades import (
    BASE_CARD_PROFILE,
    projected_card_name,
    validate_card_profile,
)
from game.contracts.headless_v0 import (
    ActionRequest,
    CombatEndTurnCandidate,
    CombatPlayCardCandidate,
    ContractValidationError,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    HeadlessBinding,
    PublicScope,
    combat_card_reference,
    combat_enemy_reference,
)
from game.simulation.actions import CombatAction, validate_action
from game.simulation.card import get_card_spec
from game.simulation.core import CombatEnv


class CombatCandidateError(ValueError):
    """Raised when a legacy combat action cannot be represented safely."""


class StaleCombatCandidateError(CombatCandidateError):
    """Raised when a request or candidate mapping is for another decision."""


class InvalidCombatCandidateError(CombatCandidateError):
    """Raised when a request does not name one advertised combat candidate."""


@dataclass(frozen=True, slots=True)
class _CombatDecisionIdentity:
    """Private control-plane identity for one authoritative decision."""

    run_id: str
    decision_sequence: int
    decision_hash: str

    @classmethod
    def from_decision(cls, decision: DecisionState) -> "_CombatDecisionIdentity":
        return cls(
            run_id=decision.run_id,
            decision_sequence=decision.decision_sequence,
            decision_hash=decision.decision_hash,
        )


@dataclass(frozen=True, slots=True)
class CombatCandidateMapping:
    """Immutable candidate-to-tuple mapping whose lifetime is one decision."""

    decision_scope: str
    candidates: Sequence[CombatEndTurnCandidate | CombatPlayCardCandidate]
    _actions_by_candidate_id: Mapping[str, CombatAction] = field(repr=False)
    _decision_identity: _CombatDecisionIdentity | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        candidates = tuple(self.candidates)
        if any(
            type(candidate) not in (CombatEndTurnCandidate, CombatPlayCardCandidate)
            for candidate in candidates
        ):
            raise CombatCandidateError("Combat mappings require exact combat candidate types.")
        candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
        if not candidates:
            raise CombatCandidateError("An actionable combat mapping requires candidates.")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise CombatCandidateError("Combat candidates must have distinct candidate IDs.")
        if any(candidate.decision_scope != self.decision_scope for candidate in candidates):
            raise CombatCandidateError("Combat candidates must share one decision scope.")
        if not isinstance(self._actions_by_candidate_id, Mapping):
            raise CombatCandidateError("Combat candidate actions must be a mapping.")
        if set(self._actions_by_candidate_id) != set(candidate_ids):
            raise CombatCandidateError(
                "Combat candidate actions must cover exactly the advertised candidates."
            )
        actions = dict(self._actions_by_candidate_id)
        try:
            for action in actions.values():
                validate_action(action)
        except ValueError as error:
            raise CombatCandidateError("Combat candidate action is not a legacy tuple.") from error
        if len(set(actions.values())) != len(actions):
            raise CombatCandidateError("Each legacy legal action must occur exactly once.")
        if self._decision_identity is not None and not isinstance(
            self._decision_identity,
            _CombatDecisionIdentity,
        ):
            raise CombatCandidateError("Combat decision identity has the wrong type.")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "_actions_by_candidate_id", MappingProxyType(actions))

    def action_for(self, candidate_id: str) -> CombatAction:
        """Return the exact current tuple action for an advertised candidate ID."""

        try:
            return self._actions_by_candidate_id[candidate_id]
        except KeyError as error:
            raise InvalidCombatCandidateError(
                "Candidate ID is not advertised by this combat decision."
            ) from error


def generate_combat_candidates(
    environment: CombatEnv,
    public_scope: PublicScope,
    *,
    card_profile: str = BASE_CARD_PROFILE,
) -> CombatCandidateMapping:
    """Translate every current legal ``CombatEnv`` action exactly once.

    Candidate ordering is canonical candidate-ID ordering, not the environment's
    incidental legal-action list order.  The retained tuple action is needed
    only to call the legacy environment and expires with the returned mapping.
    """

    validate_card_profile(card_profile)
    if not isinstance(environment, CombatEnv):
        raise TypeError("environment must be a CombatEnv.")
    if not isinstance(public_scope, PublicScope):
        raise TypeError("public_scope must be a PublicScope.")

    legal_actions = tuple(environment.get_legal_actions())
    if not legal_actions:
        raise CombatCandidateError("Cannot generate candidates without legal combat actions.")

    candidates_by_id: dict[
        str, CombatEndTurnCandidate | CombatPlayCardCandidate
    ] = {}
    actions_by_candidate_id: dict[str, CombatAction] = {}
    for action in legal_actions:
        candidate = _candidate_for_action(environment, public_scope, action, card_profile)
        if candidate.candidate_id in candidates_by_id:
            raise CombatCandidateError(
                "Distinct legacy legal actions mapped to one combat candidate."
            )
        candidates_by_id[candidate.candidate_id] = candidate
        actions_by_candidate_id[candidate.candidate_id] = action

    candidates = tuple(
        candidates_by_id[candidate_id] for candidate_id in sorted(candidates_by_id)
    )
    return CombatCandidateMapping(
        decision_scope=public_scope.decision_scope,
        candidates=candidates,
        _actions_by_candidate_id=actions_by_candidate_id,
    )


def finalize_combat_candidate_mapping(
    decision: DecisionState,
    mapping: CombatCandidateMapping,
) -> CombatCandidateMapping:
    """Bind an unbound candidate mapping to one authoritative decision.

    Candidate generation must precede ``DecisionState.create`` because the
    candidates participate in its hash.  Finalization supplies the resulting
    private run/sequence/hash identity once and prevents cross-run reuse even
    when a public scope and candidate IDs happen to be identical.
    """

    _validate_mapping_contents_for_decision(decision, mapping)
    if mapping._decision_identity is not None:
        raise StaleCombatCandidateError("Combat candidate mapping is already finalized.")
    return CombatCandidateMapping(
        decision_scope=mapping.decision_scope,
        candidates=mapping.candidates,
        _actions_by_candidate_id=mapping._actions_by_candidate_id,
        _decision_identity=_CombatDecisionIdentity.from_decision(decision),
    )


def bind_combat_candidate(
    decision: DecisionState,
    mapping: CombatCandidateMapping,
    candidate_id: str,
) -> ActionRequest:
    """Bind an advertised mapped candidate to exactly ``decision``."""

    _validate_mapping_for_decision(decision, mapping)
    mapping.action_for(candidate_id)
    try:
        binding = HeadlessBinding.for_candidate(decision, candidate_id)
    except ContractValidationError as error:
        raise InvalidCombatCandidateError(str(error)) from error
    return ActionRequest(binding)


def decode_combat_action_request(
    decision: DecisionState,
    mapping: CombatCandidateMapping,
    request: ActionRequest,
) -> CombatAction:
    """Validate a bound request and recover its one legacy tuple action.

    A stale run/sequence/hash is distinguished from a syntactically valid but
    unadvertised candidate ID.  The function never trusts an ID alone.
    """

    _validate_mapping_for_decision(decision, mapping)
    if not isinstance(request, ActionRequest):
        raise TypeError("request must be an ActionRequest.")

    binding = request.binding
    if (
        binding.run_id != decision.run_id
        or binding.decision_sequence != decision.decision_sequence
        or binding.decision_hash != decision.decision_hash
    ):
        raise StaleCombatCandidateError(
            "Combat action request does not bind to the current decision."
        )
    return mapping.action_for(binding.candidate_id)


def _candidate_for_action(
    environment: CombatEnv,
    public_scope: PublicScope,
    action: CombatAction,
    card_profile: str,
) -> CombatEndTurnCandidate | CombatPlayCardCandidate:
    if action == ("end_turn",):
        return CombatEndTurnCandidate(public_scope.decision_scope)
    if action[0] != "play":
        raise CombatCandidateError(f"Unsupported legacy combat action: {action!r}.")

    hand_index = action[1]
    try:
        card = environment.player.hand[hand_index]  # type: ignore[union-attr]
    except (AttributeError, IndexError) as error:
        raise CombatCandidateError("Legal play action has no current hand card.") from error
    card_ref = combat_card_reference(
        public_scope,
        _definition_id(
            CARD_DEFINITION_IDS, projected_card_name(card.name, card_profile)[0], "card"
        ),
        hand_index,
    )

    card_spec = get_card_spec(card.name)
    if not card_spec.uses_target:
        return CombatPlayCardCandidate(public_scope.decision_scope, card_ref)

    target_index = _target_index_for_action(environment, action)
    try:
        target = environment.enemies[target_index]  # type: ignore[index, union-attr]
    except (AttributeError, IndexError) as error:
        raise CombatCandidateError("Legal targeted play has no current enemy target.") from error
    return CombatPlayCardCandidate(
        public_scope.decision_scope,
        card_ref,
        combat_enemy_reference(
            public_scope,
            _definition_id(ENEMY_DEFINITION_IDS, target.name, "enemy"),
            target_index,
        ),
    )


def _target_index_for_action(environment: CombatEnv, action: CombatAction) -> int:
    if len(action) == 3:
        return action[2]
    enemies = environment.enemies
    if enemies is None:
        raise CombatCandidateError("Combat environment is not ready.")
    living_indices = tuple(index for index, enemy in enumerate(enemies) if enemy.is_alive)
    if len(living_indices) != 1:
        raise CombatCandidateError(
            "Targeted two-item legacy action requires exactly one living enemy."
        )
    return living_indices[0]


def _definition_id(
    definitions: Mapping[str, str],
    legacy_name: object,
    kind: str,
) -> str:
    if not isinstance(legacy_name, str):
        raise CombatCandidateError(f"Legacy combat {kind} name must be a string.")
    try:
        return definitions[legacy_name]
    except KeyError as error:
        raise CombatCandidateError(
            f"Legacy combat {kind} is absent from the closed projection registry: "
            f"{legacy_name!r}."
        ) from error


def _validate_mapping_for_decision(
    decision: DecisionState,
    mapping: CombatCandidateMapping,
) -> None:
    _validate_mapping_contents_for_decision(decision, mapping)
    identity = mapping._decision_identity
    if identity is None:
        raise StaleCombatCandidateError("Combat candidate mapping is not finalized.")
    if identity != _CombatDecisionIdentity.from_decision(decision):
        raise StaleCombatCandidateError(
            "Combat candidate mapping does not bind to the current decision."
        )


def _validate_mapping_contents_for_decision(
    decision: DecisionState,
    mapping: CombatCandidateMapping,
) -> None:
    if not isinstance(decision, DecisionState):
        raise TypeError("decision must be a DecisionState.")
    if not isinstance(mapping, CombatCandidateMapping):
        raise TypeError("mapping must be a CombatCandidateMapping.")
    if (
        decision.status is not DecisionStatus.ACTIONABLE
        or decision.phase is not DecisionPhase.COMBAT
    ):
        raise StaleCombatCandidateError("Combat candidates require an actionable combat decision.")
    if mapping.decision_scope != decision.observation.public_scope.decision_scope:
        raise StaleCombatCandidateError("Combat candidate mapping has another decision scope.")
    advertised_ids = {candidate.candidate_id for candidate in decision.candidates}
    mapping_ids = {candidate.candidate_id for candidate in mapping.candidates}
    if mapping_ids != advertised_ids:
        raise StaleCombatCandidateError(
            "Combat candidate mapping does not match the decision's advertised candidates."
        )
