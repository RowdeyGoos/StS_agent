"""Deterministic structural reward rules for the reduced headless run.

This module implements only the declared gold and card reward tables from
``reduced_content_v0``.  It is deliberately not a target-game reward model.
Reward-session continuation lives in ``WorldState.pending_decision`` so the
existing private snapshot codec captures it without extending the state schema.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from game.content.reduced_v0 import (
    CONTENT_VERSION,
    REWARD_TABLES,
    REWARDABLE_CARD_DEFINITION_IDS,
    RewardTable,
)
from game.contracts.headless_v0 import (
    ActionRequest,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    PublicEvent,
    PublicEventKind,
    PublicObservation,
    PublicReferenceKind,
    PublicScope,
    RewardChooseCardCandidate,
    RewardClaimGoldCandidate,
    RewardKind,
    RewardOpenCardRewardCandidate,
    RewardProceedCandidate,
    RewardSkipCardCandidate,
    Transition,
    TransitionReason,
    TransitionResult,
    TypedCandidate,
    reward_offer_reference,
    reward_reference,
)
from game.engine.headless_state import REWARD_OFFER_STREAM, PendingDecision, WorldState


REWARD_RULES_VERSION = "reduced_reward_rules_v0"
REWARD_RULES_EVIDENCE = "structural_fixture"
_RULE_DESCRIPTOR = {
    "evidence": REWARD_RULES_EVIDENCE,
    "offer_draw_order": "one_reward_offer_stream_shuffle_of_declared_table_cards_on_open",
    "reward_tables": "reduced_content_v0",
    "version": REWARD_RULES_VERSION,
}
REWARD_RULES_FINGERPRINT = sha256(
    json.dumps(_RULE_DESCRIPTOR, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

_PENDING_KIND = "reward_choice"
_PROCEEDED_KIND = "reward_proceeded"
_CONTEXT_FIELDS = frozenset(
    {
        "card_claimed",
        "card_opened",
        "gold_claimed",
        "offers",
        "public_events",
        "public_scope",
        "reward_table_id",
    }
)
_TABLES_BY_ID = {table.table_id: table for table in REWARD_TABLES}


class RewardRuleError(ValueError):
    """Raised when reward rules receive incompatible private state or inputs."""


@dataclass(frozen=True, slots=True)
class RewardRules:
    """Build and apply the supported reduced reward decision sequence.

    A card reward consumes exactly one request from ``reward_offer`` when it is
    opened: a shuffle of the selected table's complete declared card list.  No
    reward action touches ``combat_launch`` or ``event_effect``.
    """

    backend_id: str = "reduced_headless"
    backend_version: str = "reduced_headless_v0"
    backend_fingerprint: str = REWARD_RULES_FINGERPRINT
    content_version: str = CONTENT_VERSION
    rules_version: str = REWARD_RULES_VERSION

    def begin(
        self,
        world: WorldState,
        *,
        reward_table_id: str,
        decision_sequence: int,
        public_scope: PublicScope,
    ) -> DecisionState:
        """Start one declared reward screen without consuming world RNG."""

        self._validate_world_for_begin(world)
        table = self._table(reward_table_id)
        if not isinstance(decision_sequence, int) or isinstance(decision_sequence, bool):
            raise RewardRuleError("decision_sequence must be an integer.")
        if decision_sequence < 0:
            raise RewardRuleError("decision_sequence must be non-negative.")
        if not isinstance(public_scope, PublicScope):
            raise RewardRuleError("public_scope must be a PublicScope.")

        context = self._context(
            reward_table_id=table.table_id,
            gold_claimed=False,
            card_opened=False,
            card_claimed=False,
            offers=(),
            public_scope=public_scope,
            public_events=(),
        )
        pending = PendingDecision(_PENDING_KIND, decision_sequence, context)
        world.pending_decision = pending
        world.validate()
        return self.decision(world)

    def decision(self, world: WorldState) -> DecisionState:
        """Project the current private reward session into its typed decision."""

        world.validate()
        pending, context = self._session(world)
        scope = PublicScope.from_dict(context["public_scope"])
        events = self._events(context["public_events"])
        proceeded = pending.decision_kind == _PROCEEDED_KIND
        observation = PublicObservation(
            phase=DecisionPhase.REWARD,
            data=self._observation_data(world, context, scope, proceeded=proceeded),
            public_scope=scope,
        )
        candidates = () if proceeded else self._candidates(context, scope)
        status = DecisionStatus.WAITING if proceeded else DecisionStatus.ACTIONABLE
        return DecisionState.create(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            backend_fingerprint=self.backend_fingerprint,
            content_version=self.content_version,
            content_fingerprint=world.content_fingerprint,
            rules_version=self.rules_version,
            rules_fingerprint=world.rules_fingerprint,
            run_id=world.run_id,
            decision_sequence=pending.sequence,
            status=status,
            phase=DecisionPhase.REWARD,
            observation=observation,
            candidates=candidates,
            public_events=events,
        )

    def apply(self, world: WorldState, request: ActionRequest) -> Transition:
        """Apply one bound reward candidate, preserving atomic rejection.

        Rejections and stale actions rebuild the authoritative current decision
        without changing the world.  Accepted actions advance only this
        reward-session sequence and retain their one public event for snapshot
        continuation.
        """

        if not isinstance(request, ActionRequest):
            raise TypeError("request must be an ActionRequest.")
        current = self.decision(world)
        binding = request.binding
        if (
            binding.run_id != current.run_id
            or binding.decision_sequence != current.decision_sequence
            or binding.decision_hash != current.decision_hash
        ):
            return Transition(
                result=TransitionResult.STALE,
                reason=TransitionReason.STALE_BINDING,
                binding=binding,
                public_events=current.public_events,
                next_decision=current,
            )

        candidate = next(
            (item for item in current.candidates if item.candidate_id == binding.candidate_id),
            None,
        )
        if candidate is None:
            return Transition(
                result=TransitionResult.REJECTED,
                reason=TransitionReason.INVALID_CANDIDATE,
                binding=binding,
                public_events=current.public_events,
                next_decision=current,
            )

        pending, context = self._session(world)
        next_context, event = self._accepted_update(world, context, candidate)
        next_scope = self._next_scope(PublicScope.from_dict(context["public_scope"]))
        next_context["public_scope"] = next_scope.to_dict()
        next_context["public_events"] = [event.to_dict()]
        next_kind = _PROCEEDED_KIND if isinstance(candidate, RewardProceedCandidate) else _PENDING_KIND
        next_pending = PendingDecision(next_kind, pending.sequence + 1, next_context)

        # All validation and, for an open, the sole RNG operation have completed
        # above.  The final state assignment cannot introduce a new allocation.
        world.pending_decision = next_pending
        world.validate()
        next_decision = self.decision(world)
        return Transition(
            result=TransitionResult.ACCEPTED,
            reason=TransitionReason.ACCEPTED,
            binding=binding,
            public_events=next_decision.public_events,
            next_decision=next_decision,
        )

    def _accepted_update(
        self,
        world: WorldState,
        context: Mapping[str, Any],
        candidate: TypedCandidate,
    ) -> tuple[dict[str, Any], PublicEvent]:
        next_context = self._copy_context(context)
        if isinstance(candidate, RewardClaimGoldCandidate):
            if next_context["gold_claimed"]:
                raise RewardRuleError("Gold reward is already claimed.")
            table = self._table(next_context["reward_table_id"])
            if candidate.amount != table.gold_amount:
                raise RewardRuleError("Gold candidate amount does not match its reward table.")
            next_context["gold_claimed"] = True
            world.gold += table.gold_amount
            event = PublicEvent(
                sequence=0,
                event_type=PublicEventKind.REWARD_GOLD_CLAIMED,
                phase=DecisionPhase.REWARD,
                data={"amount": table.gold_amount},
            )
        elif isinstance(candidate, RewardOpenCardRewardCandidate):
            if next_context["card_opened"] or next_context["card_claimed"]:
                raise RewardRuleError("Card reward cannot be opened again.")
            table = self._table(next_context["reward_table_id"])
            offers = list(table.card_definition_ids)
            # Frozen reward draw order: exactly one successful shuffle request,
            # only after every validation above has completed.
            world.rng.shuffle(REWARD_OFFER_STREAM, offers)
            next_context["card_opened"] = True
            next_context["offers"] = offers
            event = PublicEvent(
                sequence=0,
                event_type=PublicEventKind.REWARD_CARD_OPENED,
                phase=DecisionPhase.REWARD,
                data={"offer_count": len(offers)},
            )
        elif isinstance(candidate, RewardChooseCardCandidate):
            if not next_context["card_opened"] or next_context["card_claimed"]:
                raise RewardRuleError("Card reward is not currently selectable.")
            scope = PublicScope.from_dict(next_context["public_scope"])
            card_definition_id = self._offered_definition(context, scope, candidate)
            if card_definition_id not in REWARDABLE_CARD_DEFINITION_IDS:
                raise RewardRuleError("Reward offers must be persistent card definitions.")
            world.add_card(card_definition_id)
            next_context["card_claimed"] = True
            event = PublicEvent(
                sequence=0,
                event_type=PublicEventKind.REWARD_CARD_CHOSEN,
                phase=DecisionPhase.REWARD,
                data={"card_definition_id": card_definition_id, "upgraded": False},
            )
        elif isinstance(candidate, RewardSkipCardCandidate):
            if not next_context["card_opened"] or next_context["card_claimed"]:
                raise RewardRuleError("Card reward is not currently skippable.")
            next_context["card_claimed"] = True
            event = PublicEvent(
                sequence=0,
                event_type=PublicEventKind.REWARD_CARD_SKIPPED,
                phase=DecisionPhase.REWARD,
                data={},
            )
        elif isinstance(candidate, RewardProceedCandidate):
            if not next_context["gold_claimed"] or not next_context["card_claimed"]:
                raise RewardRuleError("Reward screen cannot proceed before every reward resolves.")
            event = PublicEvent(
                sequence=0,
                event_type=PublicEventKind.REWARD_PROCEEDED,
                phase=DecisionPhase.REWARD,
                data={},
            )
        else:
            raise RewardRuleError("Candidate does not belong to the reward rules.")
        return next_context, event

    @staticmethod
    def _next_scope(scope: PublicScope) -> PublicScope:
        return PublicScope(
            history_ordinal=scope.history_ordinal,
            decision_ordinal=scope.decision_ordinal + 1,
            reveal_ordinals=dict(scope.reveal_ordinals),
        )

    def _observation_data(
        self,
        world: WorldState,
        context: Mapping[str, Any],
        scope: PublicScope,
        *,
        proceeded: bool,
    ) -> dict[str, Any]:
        table = self._table(context["reward_table_id"])
        gold_ref = reward_reference(scope, RewardKind.GOLD, 0)
        card_ref = reward_reference(scope, RewardKind.CARD, 1)
        offers = [
            {
                "offer_ref": reward_offer_reference(scope, card_ref, definition_id, index),
                "card_definition_id": definition_id,
                "upgraded": False,
            }
            for index, definition_id in enumerate(context["offers"])
        ]
        can_proceed = bool(context["gold_claimed"] and context["card_claimed"])
        return {
            "can_proceed": can_proceed and not proceeded,
            "player": {
                "deck_size": len(world.master_deck),
                "gold": world.gold,
                "hp": world.current_hp,
                "max_hp": world.max_hp,
            },
            "rewards": [
                {
                    "amount": table.gold_amount,
                    "can_skip": False,
                    "claimed": context["gold_claimed"],
                    "kind": RewardKind.GOLD.value,
                    "offers": [],
                    "opened": False,
                    "reward_ref": gold_ref,
                },
                {
                    "amount": 0,
                    "can_skip": context["card_opened"] and not context["card_claimed"],
                    "claimed": context["card_claimed"],
                    "kind": RewardKind.CARD.value,
                    "offers": offers,
                    "opened": context["card_opened"],
                    "reward_ref": card_ref,
                },
            ],
        }

    def _candidates(
        self,
        context: Mapping[str, Any],
        scope: PublicScope,
    ) -> tuple[TypedCandidate, ...]:
        table = self._table(context["reward_table_id"])
        decision_scope = scope.decision_scope
        gold_ref = reward_reference(scope, RewardKind.GOLD, 0)
        card_ref = reward_reference(scope, RewardKind.CARD, 1)
        candidates: list[TypedCandidate] = []
        if not context["gold_claimed"]:
            candidates.append(RewardClaimGoldCandidate(decision_scope, gold_ref, table.gold_amount))
        if not context["card_opened"]:
            candidates.append(RewardOpenCardRewardCandidate(decision_scope, card_ref))
        elif not context["card_claimed"]:
            candidates.extend(
                RewardChooseCardCandidate(
                    decision_scope,
                    card_ref,
                    reward_offer_reference(scope, card_ref, definition_id, index),
                    definition_id,
                )
                for index, definition_id in enumerate(context["offers"])
            )
            candidates.append(RewardSkipCardCandidate(decision_scope, card_ref))
        if context["gold_claimed"] and context["card_claimed"]:
            candidates.append(RewardProceedCandidate(decision_scope))
        return tuple(candidates)

    def _offered_definition(
        self,
        context: Mapping[str, Any],
        scope: PublicScope,
        candidate: RewardChooseCardCandidate,
    ) -> str:
        card_ref = reward_reference(scope, RewardKind.CARD, 1)
        for index, definition_id in enumerate(context["offers"]):
            if (
                candidate.card_definition_id == definition_id
                and candidate.offer_ref
                == reward_offer_reference(scope, card_ref, definition_id, index)
            ):
                return definition_id
        raise RewardRuleError("Card candidate does not match an offered card.")

    def _session(self, world: WorldState) -> tuple[PendingDecision, dict[str, Any]]:
        if world.phase is not DecisionPhase.REWARD:
            raise RewardRuleError("Reward rules require the reward phase.")
        pending = world.pending_decision
        if pending is None or pending.decision_kind not in {_PENDING_KIND, _PROCEEDED_KIND}:
            raise RewardRuleError("World has no active reward session.")
        context = self._copy_context(pending.private_context)
        self._table(context["reward_table_id"])
        if pending.decision_kind == _PROCEEDED_KIND and not (
            context["gold_claimed"] and context["card_claimed"]
        ):
            raise RewardRuleError("Proceeded reward session is incomplete.")
        return pending, context

    def _validate_world_for_begin(self, world: WorldState) -> None:
        if not isinstance(world, WorldState):
            raise TypeError("world must be a WorldState.")
        world.validate()
        if world.phase is not DecisionPhase.REWARD:
            raise RewardRuleError("Reward rules can only begin in the reward phase.")
        if world.pending_decision is not None:
            raise RewardRuleError("World already has a pending decision.")
        if world.active_combat_launch_key is not None:
            raise RewardRuleError("Reward rules cannot begin during an active combat launch.")

    @staticmethod
    def _table(reward_table_id: Any) -> RewardTable:
        if not isinstance(reward_table_id, str):
            raise RewardRuleError("reward_table_id must be a string.")
        try:
            return _TABLES_BY_ID[reward_table_id]
        except KeyError as error:
            raise RewardRuleError("Unknown declared reward table.") from error

    @staticmethod
    def _context(
        *,
        reward_table_id: str,
        gold_claimed: bool,
        card_opened: bool,
        card_claimed: bool,
        offers: tuple[str, ...],
        public_scope: PublicScope,
        public_events: tuple[PublicEvent, ...],
    ) -> dict[str, Any]:
        return {
            "card_claimed": card_claimed,
            "card_opened": card_opened,
            "gold_claimed": gold_claimed,
            "offers": list(offers),
            "public_events": [event.to_dict() for event in public_events],
            "public_scope": public_scope.to_dict(),
            "reward_table_id": reward_table_id,
        }

    def _copy_context(self, value: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(value, Mapping) or set(value) != _CONTEXT_FIELDS:
            raise RewardRuleError("Reward session context has an incompatible schema.")
        reward_table_id = value["reward_table_id"]
        self._table(reward_table_id)
        flags = ("gold_claimed", "card_opened", "card_claimed")
        if any(not isinstance(value[name], bool) for name in flags):
            raise RewardRuleError("Reward session flags must be booleans.")
        if value["card_claimed"] and not value["card_opened"]:
            raise RewardRuleError("A card reward cannot resolve before it opens.")
        offers = value["offers"]
        if not isinstance(offers, (tuple, list)) or any(
            not isinstance(item, str) for item in offers
        ):
            raise RewardRuleError("Reward session offers must be a string sequence.")
        if not set(offers) <= REWARDABLE_CARD_DEFINITION_IDS:
            raise RewardRuleError("Reward session contains an unsupported card offer.")
        table = self._table(reward_table_id)
        if value["card_opened"]:
            if len(offers) != len(table.card_definition_ids) or set(offers) != set(
                table.card_definition_ids
            ):
                raise RewardRuleError("Opened reward offers do not match their declared table.")
        elif offers:
            raise RewardRuleError("Unopened card rewards cannot expose offers.")
        scope = value["public_scope"]
        if not isinstance(scope, Mapping):
            raise RewardRuleError("Reward session public_scope must be an object.")
        PublicScope.from_dict(scope)
        raw_events = value["public_events"]
        if not isinstance(raw_events, (tuple, list)):
            raise RewardRuleError("Reward session public_events must be a sequence.")
        events = self._events(raw_events)
        if len(events) > 1 or any(event.phase is not DecisionPhase.REWARD for event in events):
            raise RewardRuleError("Reward session contains invalid public events.")
        return {
            "card_claimed": value["card_claimed"],
            "card_opened": value["card_opened"],
            "gold_claimed": value["gold_claimed"],
            "offers": list(offers),
            "public_events": [dict(item) for item in raw_events],
            "public_scope": dict(scope),
            "reward_table_id": reward_table_id,
        }

    @staticmethod
    def _events(raw_events: Any) -> tuple[PublicEvent, ...]:
        if not isinstance(raw_events, (tuple, list)):
            raise RewardRuleError("Reward session public_events must be a sequence.")
        events: list[PublicEvent] = []
        for value in raw_events:
            if not isinstance(value, Mapping):
                raise RewardRuleError("Reward session event must be an object.")
            events.append(PublicEvent.from_dict(value))
        return tuple(events)
