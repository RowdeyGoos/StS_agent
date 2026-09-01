"""Deterministic structural reward rules for the reduced headless run.

This module implements only the declared gold and card reward tables from
``reduced_content_v0``.  It is deliberately not a target-game reward model.
Reward-session continuation lives in ``WorldState.pending_decision`` so the
existing private snapshot codec captures it without extending the state schema.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from hashlib import sha256
import json
from typing import Any

from game.content.reduced_v0 import (
    CONTENT_FINGERPRINT,
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
    MAX_COLLECTION_SIZE,
    MAX_PUBLIC_COUNTER,
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
from game.engine.headless_state import (
    REWARD_OFFER_STREAM,
    PendingDecision,
    PersistentCardInstance,
    StableIdAllocator,
    WorldState,
    canonical_private_json,
)
from game.engine.random_service import GameRandomService


REWARD_RULES_VERSION = "reduced_reward_rules_v3"
REWARD_RULES_EVIDENCE = "structural_fixture"
REWARD_CONTEXT_VERSION = "reduced_reward_context_v3"
_RULE_DESCRIPTOR = {
    "context_version": REWARD_CONTEXT_VERSION,
    "evidence": REWARD_RULES_EVIDENCE,
    "origin_commitment": "pending_kind_prefix_plus_55_hex_sha256_v2_with_action_history",
    "offer_draw_order": "one_reward_offer_stream_shuffle_of_declared_table_cards_on_open",
    "reward_tables": "reduced_content_v0",
    "version": REWARD_RULES_VERSION,
}
REWARD_RULES_FINGERPRINT = sha256(
    json.dumps(_RULE_DESCRIPTOR, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

_PENDING_KIND_PREFIX = "reward_c."
_PROCEEDED_KIND_PREFIX = "reward_p."
_ORIGIN_COMMITMENT_HEX_LENGTH = 55
_CONTEXT_FIELDS = frozenset(
    {
        "accepted_actions",
        "card_claimed",
        "card_opened",
        "card_resolution",
        "chosen_card_definition_id",
        "context_version",
        "gold_claimed",
        "offers",
        "opening_allocator",
        "opening_deck",
        "opening_gold",
        "opening_public_scope",
        "opening_rng",
        "opening_sequence",
        "public_events",
        "public_scope",
        "reward_table_id",
    }
)
_TABLES_BY_ID = {table.table_id: table for table in REWARD_TABLES}
_CARD_RESOLUTIONS = frozenset({"unopened", "pending", "chosen", "skipped"})


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

    def __post_init__(self) -> None:
        if self.content_version != CONTENT_VERSION:
            raise RewardRuleError("Reward rules require the fixed reduced content version.")

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
        self._validate_reduced_content_provenance(world)
        table = self._table(reward_table_id)
        if not isinstance(decision_sequence, int) or isinstance(decision_sequence, bool):
            raise RewardRuleError("decision_sequence must be an integer.")
        if decision_sequence < 0:
            raise RewardRuleError("decision_sequence must be non-negative.")
        if not isinstance(public_scope, PublicScope):
            raise RewardRuleError("public_scope must be a PublicScope.")
        self._assert_begin_is_projectable(world, table, public_scope)

        before = world.to_private_dict()
        try:
            context = self._context(
                world=world,
                reward_table_id=table.table_id,
                gold_claimed=False,
                card_opened=False,
                card_claimed=False,
                opening_sequence=decision_sequence,
                offers=(),
                public_scope=public_scope,
                public_events=(),
            )
            pending = PendingDecision(
                self._committed_pending_kind(world, context, proceeded=False),
                decision_sequence,
                context,
            )
            world.pending_decision = pending
            world.validate()
            return self.decision(world)
        except Exception:
            self._restore_world(world, before)
            raise

    def decision(self, world: WorldState) -> DecisionState:
        """Project the current private reward session into its typed decision."""

        world.validate()
        self._validate_reduced_content_provenance(world)
        pending, context, proceeded = self._session(world)
        scope = PublicScope.from_dict(context["public_scope"])
        events = self._events(context["public_events"])
        if not proceeded:
            self._assert_session_is_completable(world, context, scope)
        observation = PublicObservation(
            phase=DecisionPhase.REWARD,
            data=self._observation_data(world, context, scope, proceeded=proceeded),
            public_scope=scope,
        )
        candidates = () if proceeded else self._candidates(world, context, scope)
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

        before = world.to_private_dict()
        try:
            pending, context, _ = self._session(world)
            next_context, event = self._accepted_update(world, context, candidate)
            next_scope = self._next_scope(PublicScope.from_dict(context["public_scope"]))
            next_context["public_scope"] = next_scope.to_dict()
            next_context["public_events"] = [event.to_dict()]
            next_kind = self._committed_pending_kind(
                world,
                next_context,
                proceeded=isinstance(candidate, RewardProceedCandidate),
            )
            next_pending = PendingDecision(next_kind, pending.sequence + 1, next_context)

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
        except Exception:
            self._restore_world(world, before)
            raise

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
            action_entry = "claim_gold"
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
            next_context["card_resolution"] = "pending"
            next_context["offers"] = offers
            action_entry = "open_card_reward"
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
            next_context["card_resolution"] = "chosen"
            next_context["chosen_card_definition_id"] = card_definition_id
            action_entry = f"choose_card:{card_definition_id}"
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
            next_context["card_resolution"] = "skipped"
            action_entry = "skip_card"
            event = PublicEvent(
                sequence=0,
                event_type=PublicEventKind.REWARD_CARD_SKIPPED,
                phase=DecisionPhase.REWARD,
                data={},
            )
        elif isinstance(candidate, RewardProceedCandidate):
            if not next_context["gold_claimed"] or not next_context["card_claimed"]:
                raise RewardRuleError("Reward screen cannot proceed before every reward resolves.")
            action_entry = "proceed"
            event = PublicEvent(
                sequence=0,
                event_type=PublicEventKind.REWARD_PROCEEDED,
                phase=DecisionPhase.REWARD,
                data={},
            )
        else:
            raise RewardRuleError("Candidate does not belong to the reward rules.")
        next_context["accepted_actions"].append(action_entry)
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
        world: WorldState,
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
            if (
                world.identity_allocator.can_allocate_card_id()
                and len(world.master_deck) < MAX_COLLECTION_SIZE
            ):
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

    def _session(
        self,
        world: WorldState,
    ) -> tuple[PendingDecision, dict[str, Any], bool]:
        if world.phase is not DecisionPhase.REWARD:
            raise RewardRuleError("Reward rules require the reward phase.")
        pending = world.pending_decision
        if pending is None:
            raise RewardRuleError("World has no active reward session.")
        context = self._copy_context(pending.private_context)
        self._table(context["reward_table_id"])
        proceeded = self._validate_pending_commitment(world, pending, context)
        action_history = self._validate_action_history(context, proceeded=proceeded)
        self._validate_origin_progress(
            pending,
            context,
            proceeded=proceeded,
            action_history=action_history,
        )
        self._validate_persistent_session(world, context)
        if proceeded and not (
            context["gold_claimed"] and context["card_claimed"]
        ):
            raise RewardRuleError("Proceeded reward session is incomplete.")
        self._validate_last_event(context, action_history=action_history)
        return pending, context, proceeded

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
    def _remaining_actions(context: Mapping[str, Any]) -> int:
        """Return the shortest remaining supported path through this reward screen."""

        claim_gold = 0 if context["gold_claimed"] else 1
        if context["card_claimed"]:
            resolve_card = 0
        elif context["card_opened"]:
            resolve_card = 1
        else:
            resolve_card = 2  # Open, then choose or skip.
        return claim_gold + resolve_card + 1  # The final proceed is always required.

    def _assert_begin_is_projectable(
        self,
        world: WorldState,
        table: RewardTable,
        public_scope: PublicScope,
    ) -> None:
        if world.gold > MAX_PUBLIC_COUNTER:
            raise RewardRuleError("Current gold exceeds the public reward bound.")
        if world.gold + table.gold_amount > MAX_PUBLIC_COUNTER:
            raise RewardRuleError("Declared gold reward exceeds the public reward bound.")
        # Four accepted transitions are required from an unopened screen:
        # claim, open, choose-or-skip, and proceed.  ``decision_sequence`` is
        # contract-nonnegative but intentionally has no finite upper bound.
        if public_scope.decision_ordinal + 4 > MAX_PUBLIC_COUNTER:
            raise RewardRuleError("Reward session cannot complete within the public scope budget.")

    def _assert_session_is_completable(
        self,
        world: WorldState,
        context: Mapping[str, Any],
        scope: PublicScope,
    ) -> None:
        table = self._table(context["reward_table_id"])
        if world.gold > MAX_PUBLIC_COUNTER:
            raise RewardRuleError("Current gold exceeds the public reward bound.")
        if (
            not context["gold_claimed"]
            and world.gold + table.gold_amount > MAX_PUBLIC_COUNTER
        ):
            raise RewardRuleError("Unclaimed gold reward exceeds the public reward bound.")
        if scope.decision_ordinal + self._remaining_actions(context) > MAX_PUBLIC_COUNTER:
            raise RewardRuleError("Reward session cannot complete within the public scope budget.")

    @staticmethod
    def _validate_reduced_content_provenance(world: WorldState) -> None:
        if world.content_fingerprint != CONTENT_FINGERPRINT:
            raise RewardRuleError("Reward rules require the fixed reduced content fingerprint.")

    def _validate_last_event(
        self,
        context: Mapping[str, Any],
        *,
        action_history: tuple[str, ...],
    ) -> None:
        events = self._events(context["public_events"])
        if not action_history:
            if events:
                raise RewardRuleError("Initial reward session cannot contain a public event.")
            return
        if len(events) != 1:
            raise RewardRuleError("Reward session must retain exactly one last public event.")

        table = self._table(context["reward_table_id"])
        last_action = action_history[-1]
        if last_action == "claim_gold":
            expected = PublicEvent(
                0,
                PublicEventKind.REWARD_GOLD_CLAIMED,
                DecisionPhase.REWARD,
                {"amount": table.gold_amount},
            )
        elif last_action == "open_card_reward":
            expected = PublicEvent(
                0,
                PublicEventKind.REWARD_CARD_OPENED,
                DecisionPhase.REWARD,
                {"offer_count": len(table.card_definition_ids)},
            )
        elif last_action.startswith("choose_card:"):
            expected = PublicEvent(
                0,
                PublicEventKind.REWARD_CARD_CHOSEN,
                DecisionPhase.REWARD,
                {
                    "card_definition_id": last_action.split(":", 1)[1],
                    "upgraded": False,
                },
            )
        elif last_action == "skip_card":
            expected = PublicEvent(
                0,
                PublicEventKind.REWARD_CARD_SKIPPED,
                DecisionPhase.REWARD,
                {},
            )
        elif last_action == "proceed":
            expected = PublicEvent(
                0,
                PublicEventKind.REWARD_PROCEEDED,
                DecisionPhase.REWARD,
                {},
            )
        else:
            raise RewardRuleError("Reward action history has an unsupported last action.")
        if events[0] != expected:
            raise RewardRuleError("Reward receipt does not match the actual last accepted action.")

    def _validate_persistent_session(
        self,
        world: WorldState,
        context: Mapping[str, Any],
    ) -> None:
        """Validate the complete reward trajectory against its opening baseline."""

        table = self._table(context["reward_table_id"])
        expected_gold = context["opening_gold"] + (
            table.gold_amount if context["gold_claimed"] else 0
        )
        if world.gold != expected_gold:
            raise RewardRuleError("Persistent gold does not match the reward opening baseline.")

        opening_rng = GameRandomService(0)
        opening_rng.restore(self._mutable_private(context["opening_rng"]))
        expected_offers: list[str] = []
        if context["card_opened"]:
            expected_offers = list(table.card_definition_ids)
            opening_rng.shuffle(REWARD_OFFER_STREAM, expected_offers)
        if list(context["offers"]) != expected_offers:
            raise RewardRuleError("Card offers do not match the deterministic opening draw.")
        if world.rng.snapshot() != opening_rng.snapshot():
            raise RewardRuleError("World RNG does not match the reward opening baseline.")

        opening_allocator = StableIdAllocator.from_dict(
            self._mutable_private(context["opening_allocator"])
        )
        opening_deck = tuple(
            PersistentCardInstance.from_dict(self._mutable_private(item))
            for item in context["opening_deck"]
        )
        if opening_allocator.run_id != world.run_id:
            raise RewardRuleError("Reward opening allocator belongs to another run.")
        opening_ids = [card.instance_id for card in opening_deck]
        if len(set(opening_ids)) != len(opening_ids):
            raise RewardRuleError("Reward opening deck contains duplicate card identities.")
        try:
            for card_id in opening_ids:
                opening_allocator.validate_card_id(card_id)
        except ValueError as error:
            raise RewardRuleError("Reward opening deck does not match its allocator.") from error

        resolution = context["card_resolution"]
        chosen_definition = context["chosen_card_definition_id"]
        expected_allocator = opening_allocator
        expected_deck = opening_deck
        if resolution == "unopened":
            if context["card_opened"] or context["card_claimed"] or chosen_definition is not None:
                raise RewardRuleError("Unopened card metadata is contradictory.")
        elif resolution == "pending":
            if not context["card_opened"] or context["card_claimed"] or chosen_definition is not None:
                raise RewardRuleError("Pending card metadata is contradictory.")
        elif resolution == "chosen":
            if (
                not context["card_opened"]
                or not context["card_claimed"]
                or chosen_definition not in expected_offers
            ):
                raise RewardRuleError("Chosen card metadata is contradictory.")
            instance_id = expected_allocator.allocate_card_id()
            expected_deck += (
                PersistentCardInstance(instance_id, chosen_definition, False),
            )
        elif resolution == "skipped":
            if (
                not context["card_opened"]
                or not context["card_claimed"]
                or chosen_definition is not None
            ):
                raise RewardRuleError("Skipped card metadata is contradictory.")

        if world.master_deck != expected_deck:
            raise RewardRuleError("Persistent deck does not match the reward opening baseline.")
        if world.identity_allocator.to_dict() != expected_allocator.to_dict():
            raise RewardRuleError("Card allocator does not match the reward opening baseline.")

    @staticmethod
    def _origin_commitment(world: WorldState, context: Mapping[str, Any]) -> str:
        # This in-object commitment detects localized edits against the
        # existing pending decision.  A coordinated replacement of the whole
        # PendingDecision, including a recomputed digest, remains outside the
        # reward-rule trust boundary.
        basis = {
            "accepted_actions": context["accepted_actions"],
            "context_version": context["context_version"],
            "opening_allocator": context["opening_allocator"],
            "opening_deck": context["opening_deck"],
            "opening_gold": context["opening_gold"],
            "opening_public_scope": context["opening_public_scope"],
            "opening_rng": context["opening_rng"],
            "opening_sequence": context["opening_sequence"],
            "reward_table_id": context["reward_table_id"],
            "rules_version": REWARD_RULES_VERSION,
            "run_id": world.run_id,
        }
        payload = (
            "reduced_reward_pending.v2\0" + canonical_private_json(basis)
        ).encode("utf-8")
        return sha256(payload).hexdigest()[:_ORIGIN_COMMITMENT_HEX_LENGTH]

    def _committed_pending_kind(
        self,
        world: WorldState,
        context: Mapping[str, Any],
        *,
        proceeded: bool,
    ) -> str:
        prefix = _PROCEEDED_KIND_PREFIX if proceeded else _PENDING_KIND_PREFIX
        return prefix + self._origin_commitment(world, context)

    def _validate_pending_commitment(
        self,
        world: WorldState,
        pending: PendingDecision,
        context: Mapping[str, Any],
    ) -> bool:
        if pending.decision_kind.startswith(_PENDING_KIND_PREFIX):
            proceeded = False
            digest = pending.decision_kind[len(_PENDING_KIND_PREFIX) :]
        elif pending.decision_kind.startswith(_PROCEEDED_KIND_PREFIX):
            proceeded = True
            digest = pending.decision_kind[len(_PROCEEDED_KIND_PREFIX) :]
        else:
            raise RewardRuleError("Reward pending kind has an invalid commitment prefix.")
        expected = self._origin_commitment(world, context)
        if len(digest) != _ORIGIN_COMMITMENT_HEX_LENGTH or digest != expected:
            raise RewardRuleError("Reward pending kind has an invalid opening commitment.")
        return proceeded

    @staticmethod
    def _accepted_action_count(
        context: Mapping[str, Any],
        *,
        proceeded: bool,
    ) -> int:
        count = 1 if context["gold_claimed"] else 0
        resolution = context["card_resolution"]
        if resolution == "pending":
            count += 1
        elif resolution in {"chosen", "skipped"}:
            count += 2
        if proceeded:
            count += 1
        return count

    @staticmethod
    def _validate_action_history(
        context: Mapping[str, Any],
        *,
        proceeded: bool,
    ) -> tuple[str, ...]:
        history = tuple(context["accepted_actions"])
        normalized: list[str] = []
        chosen_definition: str | None = None
        for action in history:
            if action in {"claim_gold", "open_card_reward", "skip_card", "proceed"}:
                normalized.append(action)
            elif action.startswith("choose_card:"):
                definition = action.split(":", 1)[1]
                if definition not in REWARDABLE_CARD_DEFINITION_IDS:
                    raise RewardRuleError("Reward action history has an invalid chosen card.")
                normalized.append("choose_card")
                chosen_definition = definition
            else:
                raise RewardRuleError("Reward action history contains an invalid action.")

        complete_orders = (
            ("claim_gold", "open_card_reward", "choose_card", "proceed"),
            ("claim_gold", "open_card_reward", "skip_card", "proceed"),
            ("open_card_reward", "claim_gold", "choose_card", "proceed"),
            ("open_card_reward", "claim_gold", "skip_card", "proceed"),
            ("open_card_reward", "choose_card", "claim_gold", "proceed"),
            ("open_card_reward", "skip_card", "claim_gold", "proceed"),
        )
        normalized_tuple = tuple(normalized)
        if not any(
            normalized_tuple == order[: len(normalized_tuple)]
            for order in complete_orders
        ):
            raise RewardRuleError("Reward action history is not a legal ordering prefix.")
        if proceeded != (bool(normalized_tuple) and normalized_tuple[-1] == "proceed"):
            raise RewardRuleError("Reward pending prefix contradicts its action history.")
        if context["card_resolution"] == "chosen":
            if chosen_definition != context["chosen_card_definition_id"]:
                raise RewardRuleError("Chosen card metadata contradicts action history.")
        elif chosen_definition is not None:
            raise RewardRuleError("Non-chosen card state contains a choose action.")
        return history

    def _validate_origin_progress(
        self,
        pending: PendingDecision,
        context: Mapping[str, Any],
        *,
        proceeded: bool,
        action_history: tuple[str, ...],
    ) -> None:
        opening_scope = PublicScope.from_dict(context["opening_public_scope"])
        current_scope = PublicScope.from_dict(context["public_scope"])
        action_count = self._accepted_action_count(context, proceeded=proceeded)
        if len(action_history) != action_count:
            raise RewardRuleError("Reward action history does not match derived progress.")
        if pending.sequence != context["opening_sequence"] + action_count:
            raise RewardRuleError("Reward sequence does not match its immutable opening origin.")
        if current_scope.history_ordinal != opening_scope.history_ordinal:
            raise RewardRuleError("Reward history scope changed after opening.")
        if dict(current_scope.reveal_ordinals) != dict(opening_scope.reveal_ordinals):
            raise RewardRuleError("Reward reveal scopes changed after opening.")
        if current_scope.decision_ordinal != opening_scope.decision_ordinal + action_count:
            raise RewardRuleError("Reward decision scope does not match its opening origin.")

    @staticmethod
    def _restore_world(world: WorldState, snapshot: Mapping[str, Any]) -> None:
        """Restore a pre-mutation private snapshot into the original object.

        The state kernel deliberately owns the snapshot schema.  Rehydrating
        through it restores all persistent fields, the sole ID allocator, and
        every RNG stream/counter rather than trying to reverse individual
        writes made by a partially failed reward action.
        """

        restored = WorldState.from_private_dict(snapshot)
        for descriptor in fields(WorldState):
            setattr(world, descriptor.name, getattr(restored, descriptor.name))

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
        world: WorldState,
        reward_table_id: str,
        gold_claimed: bool,
        card_opened: bool,
        card_claimed: bool,
        opening_sequence: int,
        offers: tuple[str, ...],
        public_scope: PublicScope,
        public_events: tuple[PublicEvent, ...],
    ) -> dict[str, Any]:
        return {
            "accepted_actions": [],
            "card_claimed": card_claimed,
            "card_opened": card_opened,
            "card_resolution": "unopened",
            "chosen_card_definition_id": None,
            "context_version": REWARD_CONTEXT_VERSION,
            "gold_claimed": gold_claimed,
            "offers": list(offers),
            "opening_allocator": world.identity_allocator.to_dict(),
            "opening_deck": [card.to_dict() for card in world.master_deck],
            "opening_gold": world.gold,
            "opening_public_scope": public_scope.to_dict(),
            "opening_rng": world.rng.snapshot(),
            "opening_sequence": opening_sequence,
            "public_events": [event.to_dict() for event in public_events],
            "public_scope": public_scope.to_dict(),
            "reward_table_id": reward_table_id,
        }

    def _copy_context(self, value: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(value, Mapping) or set(value) != _CONTEXT_FIELDS:
            raise RewardRuleError("Reward session context has an incompatible schema.")
        if value["context_version"] != REWARD_CONTEXT_VERSION:
            raise RewardRuleError("Reward session context version is incompatible.")
        accepted_actions = value["accepted_actions"]
        if not isinstance(accepted_actions, (tuple, list)) or any(
            not isinstance(action, str) for action in accepted_actions
        ):
            raise RewardRuleError("Reward session accepted-action history is invalid.")
        reward_table_id = value["reward_table_id"]
        self._table(reward_table_id)
        flags = ("gold_claimed", "card_opened", "card_claimed")
        if any(not isinstance(value[name], bool) for name in flags):
            raise RewardRuleError("Reward session flags must be booleans.")
        if value["card_claimed"] and not value["card_opened"]:
            raise RewardRuleError("A card reward cannot resolve before it opens.")
        resolution = value["card_resolution"]
        if not isinstance(resolution, str) or resolution not in _CARD_RESOLUTIONS:
            raise RewardRuleError("Reward session card resolution is invalid.")
        chosen_definition = value["chosen_card_definition_id"]
        if chosen_definition is not None and (
            not isinstance(chosen_definition, str)
            or chosen_definition not in REWARDABLE_CARD_DEFINITION_IDS
        ):
            raise RewardRuleError("Reward session chosen card definition is invalid.")
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
        opening_gold = value["opening_gold"]
        if (
            not isinstance(opening_gold, int)
            or isinstance(opening_gold, bool)
            or not 0 <= opening_gold <= MAX_PUBLIC_COUNTER
        ):
            raise RewardRuleError("Reward session opening gold is invalid.")
        opening_deck = value["opening_deck"]
        if not isinstance(opening_deck, (tuple, list)) or not opening_deck or any(
            not isinstance(item, Mapping) for item in opening_deck
        ):
            raise RewardRuleError("Reward session opening deck is invalid.")
        opening_allocator = value["opening_allocator"]
        opening_rng = value["opening_rng"]
        opening_scope = value["opening_public_scope"]
        opening_sequence = value["opening_sequence"]
        if (
            not isinstance(opening_allocator, Mapping)
            or not isinstance(opening_rng, Mapping)
            or not isinstance(opening_scope, Mapping)
        ):
            raise RewardRuleError("Reward session opening state is invalid.")
        if (
            not isinstance(opening_sequence, int)
            or isinstance(opening_sequence, bool)
            or opening_sequence < 0
        ):
            raise RewardRuleError("Reward session opening sequence is invalid.")
        try:
            StableIdAllocator.from_dict(self._mutable_private(opening_allocator))
            tuple(
                PersistentCardInstance.from_dict(self._mutable_private(item))
                for item in opening_deck
            )
            opening_random = GameRandomService(0)
            opening_random.restore(self._mutable_private(opening_rng))
            PublicScope.from_dict(self._mutable_private(opening_scope))
        except (TypeError, ValueError) as error:
            raise RewardRuleError("Reward session opening state is invalid.") from error
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
            key: self._mutable_private(value[key])
            for key in sorted(_CONTEXT_FIELDS)
        }

    @staticmethod
    def _mutable_private(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                key: RewardRules._mutable_private(item)
                for key, item in value.items()
            }
        if isinstance(value, (tuple, list)):
            return [RewardRules._mutable_private(item) for item in value]
        return value

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
