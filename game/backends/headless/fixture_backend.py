"""Deterministic playback of the synthetic ``headless_v0`` fixture corpus.

This backend deliberately has no rules engine.  A fixture names a recorded
route, and the only actions it accepts are the candidates recorded at its
current cursor.  It is useful for contract and runtime tests, not for
counterfactual evaluation or claims about a live game.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from game.contracts.headless_v0 import (
    ACTION_PHASES,
    ActionRequest,
    BackendCapabilities,
    BackendManifest,
    CombatEndTurnCandidate,
    CombatPlayCardCandidate,
    ComponentEvidence,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    EvidenceLabel,
    HeadlessBinding,
    MapChooseNodeCandidate,
    NodeKind,
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
    RoomEffectKind,
    RoomEventOptionCandidate,
    RoomKind,
    RoomOptionKind,
    RoomProceedCandidate,
    RoomRestHealCandidate,
    Transition,
    TransitionReason,
    TransitionResult,
    canonical_json,
    combat_card_reference,
    combat_enemy_reference,
    map_node_reference,
    reward_offer_reference,
    reward_reference,
    room_option_reference,
)


FIXTURE_SCHEMA = "headless_v0_fixture_v1"
CORPUS_SCHEMA = "headless_v0_fixture_corpus_v1"
BACKEND_ID = "headless.fixture"
BACKEND_VERSION = "v1"
_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "headless_v0"


@dataclass(frozen=True, slots=True)
class FixtureCursor:
    """Private, serializable position in one immutable fixture route."""

    fixture_id: str
    cursor: int


class FixtureBackend:
    """Play one of the checked-in synthetic routes without inventing rules."""

    def __init__(self, fixture_root: str | Path | None = None) -> None:
        self._root = Path(fixture_root) if fixture_root is not None else _ROOT
        self._corpus, self._fixtures, self._corpus_fingerprint = self._load_corpus()
        self._backend_fingerprint = _digest(
            {"backend": BACKEND_ID, "version": BACKEND_VERSION, "corpus": self._corpus_fingerprint}
        )
        self._cursor: FixtureCursor | None = None

    def reset(self, configuration: str | Mapping[str, Any]) -> DecisionState:
        """Select a named fixture and return its initial recorded decision."""
        fixture_id = _fixture_id(configuration)
        if fixture_id not in self._fixtures:
            raise ValueError(f"Unknown fixture_id: {fixture_id!r}.")
        self._cursor = FixtureCursor(fixture_id, 0)
        return self.observe()

    def observe(self) -> DecisionState:
        """Return the authoritative decision at the current playback cursor."""
        cursor = self._require_cursor()
        return self._decision(cursor.fixture_id, cursor.cursor)

    def apply(self, request: ActionRequest) -> Transition:
        """Accept exactly a recorded candidate, otherwise return a safe refusal."""
        if not isinstance(request, ActionRequest):
            raise TypeError("request must be an ActionRequest.")
        current = self.observe()
        binding = request.binding
        if not _matches(binding, current):
            return Transition(
                TransitionResult.STALE,
                TransitionReason.STALE_BINDING,
                binding,
                current.public_events,
                current,
            )
        routes = self._fixtures[self._require_cursor().fixture_id]["steps"][
            self._require_cursor().cursor
        ].get("routes", {})
        # A route records one advertised candidate shape.  Its canonical ID is
        # re-derived from the current public decision, never stored as a
        # durable fixture identifier.
        if binding.candidate_id not in {candidate.candidate_id for candidate in current.candidates}:
            return Transition(
                TransitionResult.REJECTED,
                TransitionReason.INVALID_CANDIDATE,
                binding,
                current.public_events,
                current,
            )
        self._cursor = FixtureCursor(self._require_cursor().fixture_id, routes["recorded"])
        next_decision = self.observe()
        return Transition(
            TransitionResult.ACCEPTED,
            TransitionReason.ACCEPTED,
            binding,
            next_decision.public_events,
            next_decision,
        )

    def snapshot(self) -> FixtureCursor:
        return self._require_cursor()

    def restore(self, snapshot: FixtureCursor) -> DecisionState:
        if not isinstance(snapshot, FixtureCursor):
            raise TypeError("snapshot must be a FixtureCursor.")
        fixture = self._fixtures.get(snapshot.fixture_id)
        if fixture is None or not 0 <= snapshot.cursor < len(fixture["steps"]):
            raise ValueError("Snapshot does not identify a corpus cursor.")
        self._cursor = snapshot
        return self.observe()

    def manifest(self) -> BackendManifest:
        return BackendManifest(
            backend_id=BACKEND_ID,
            backend_version=BACKEND_VERSION,
            backend_fingerprint=self._backend_fingerprint,
            content_version="synthetic-fixture-v1",
            content_fingerprint=self._corpus_fingerprint,
            rules_version="recorded-routes-only-v1",
            rules_fingerprint=_digest({"rules": "recorded-routes-only-v1"}),
            capabilities=BackendCapabilities(True, False, True, True, False, False),
            supported_phases=tuple(sorted(ACTION_PHASES, key=lambda phase: phase.value)),
            unsupported_phases=(),
            evidence=(
                ComponentEvidence("fixture_corpus", EvidenceLabel.STRUCTURAL_FIXTURE, "v1", self._corpus_fingerprint),
                ComponentEvidence("fixture_playback", EvidenceLabel.STRUCTURAL_FIXTURE, "v1", self._backend_fingerprint),
            ),
        )

    def close(self) -> None:
        self._cursor = None

    def _load_corpus(self) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
        corpus_path = self._root / "manifest.json"
        corpus = _read_canonical_json(corpus_path)
        if corpus.get("schema") != CORPUS_SCHEMA or not isinstance(corpus.get("fixtures"), dict):
            raise ValueError("Fixture corpus manifest has an unsupported schema.")
        fixtures: dict[str, dict[str, Any]] = {}
        for fixture_id, expected_hash in corpus["fixtures"].items():
            if not isinstance(fixture_id, str) or not isinstance(expected_hash, str):
                raise ValueError("Fixture manifest entries must be strings.")
            raw = _read_canonical_json(self._root / f"{fixture_id}.json")
            if raw.get("schema") != FIXTURE_SCHEMA or raw.get("fixture_id") != fixture_id:
                raise ValueError(f"Fixture {fixture_id!r} has an invalid identity.")
            if _digest(raw) != expected_hash:
                raise ValueError(f"Fixture {fixture_id!r} does not match its frozen hash.")
            _validate_fixture(raw)
            fixtures[fixture_id] = raw
        return corpus, fixtures, _digest(corpus)

    def _decision(self, fixture_id: str, cursor: int) -> DecisionState:
        step = self._fixtures[fixture_id]["steps"][cursor]
        scope = _scope(cursor)
        phase = DecisionPhase(step["phase"])
        status = DecisionStatus(step["status"])
        observation = _observation(phase, scope, step.get("room_kind"), step.get("action"))
        candidates = () if status is not DecisionStatus.ACTIONABLE else (_candidate(step["action"], scope),)
        events = () if cursor == 0 else (_event_for(self._fixtures[fixture_id]["steps"][cursor - 1]["action"], phase),)
        return DecisionState.create(
            backend_id=BACKEND_ID,
            backend_version=BACKEND_VERSION,
            backend_fingerprint=self._backend_fingerprint,
            content_version="synthetic-fixture-v1",
            content_fingerprint=self._corpus_fingerprint,
            rules_version="recorded-routes-only-v1",
            rules_fingerprint=_digest({"rules": "recorded-routes-only-v1"}),
            run_id=f"fixture.{fixture_id}",
            decision_sequence=cursor,
            status=status,
            phase=phase,
            observation=observation,
            candidates=candidates,
            public_events=events,
        )

    def _require_cursor(self) -> FixtureCursor:
        if self._cursor is None:
            raise RuntimeError("reset must be called before observing or stepping.")
        return self._cursor


def _fixture_id(configuration: str | Mapping[str, Any]) -> str:
    if isinstance(configuration, str):
        return configuration
    if isinstance(configuration, Mapping) and set(configuration) == {"fixture_id"} and isinstance(configuration["fixture_id"], str):
        return configuration["fixture_id"]
    raise ValueError("Fixture reset configuration must be a fixture ID or {'fixture_id': ID}.")


def _matches(binding: HeadlessBinding, decision: DecisionState) -> bool:
    return (binding.run_id, binding.decision_sequence, binding.decision_hash) == (decision.run_id, decision.decision_sequence, decision.decision_hash)


def _digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _read_canonical_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Fixture file is not JSON: {path}") from exc
    # Source-control text files conventionally end in one newline.  The frozen
    # digest is nevertheless over the contract's newline-free canonical bytes.
    source = raw[:-1] if raw.endswith(b"\n") else raw
    if not isinstance(value, dict) or source != canonical_json(value).encode("utf-8"):
        raise ValueError(f"Fixture file is not canonical JSON: {path}")
    return value


def _validate_fixture(fixture: dict[str, Any]) -> None:
    steps = fixture.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Fixture must contain a non-empty steps array.")
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or set(step) - {"action", "phase", "room_kind", "routes", "status"}:
            raise ValueError("Fixture step has unsupported fields.")
        status, phase = step.get("status"), step.get("phase")
        if status not in {item.value for item in DecisionStatus} or phase not in {item.value for item in DecisionPhase}:
            raise ValueError("Fixture step has an invalid status or phase.")
        if status == DecisionStatus.ACTIONABLE.value:
            if not isinstance(step.get("action"), str) or not isinstance(step.get("routes"), dict):
                raise ValueError("Actionable fixture steps require action and routes.")
            if len(step["routes"]) != 1 or not all(target == index + 1 for target in step["routes"].values()):
                raise ValueError("Fixture routes must advance exactly one recorded cursor.")
        elif index != len(steps) - 1 or "action" in step or "routes" in step:
            raise ValueError("Only a final non-actionable step may end a fixture.")


def _scope(cursor: int) -> PublicScope:
    return PublicScope(cursor, cursor, {kind.value: 0 for kind in PublicReferenceKind})


def _player() -> dict[str, int]:
    return {"hp": 61, "max_hp": 80, "gold": 99, "deck_size": 10}


def _observation(
    phase: DecisionPhase,
    scope: PublicScope,
    room_kind: str | None,
    action: str | None,
) -> PublicObservation:
    enemy = combat_enemy_reference(scope, "jaw_worm", 0)
    card = combat_card_reference(scope, "strike", 0)
    gold = reward_reference(scope, RewardKind.GOLD, 0)
    reward = reward_reference(scope, RewardKind.CARD, 1)
    offer = reward_offer_reference(scope, reward, "strike", 0)
    node = map_node_reference(scope, NodeKind.REST, 0)
    kind = RoomKind(room_kind or "rest")
    option_kind = RoomOptionKind.REST_HEAL if kind is RoomKind.REST else RoomOptionKind.EVENT_OPTION
    option = room_option_reference(scope, kind, option_kind, 0)
    if phase is DecisionPhase.COMBAT:
        return PublicObservation(phase, {"turn": 1, "player": {"hp": 61, "max_hp": 80, "block": 0, "energy": 3, "energy_per_turn": 3, "strength": 0, "statuses": {"vulnerable": 0, "shrink": 0}}, "enemies": [{"enemy_ref": enemy, "enemy_definition_id": "jaw_worm", "hp": 37, "max_hp": 40, "block": 0, "strength": 0, "statuses": {"vulnerable": 0, "shrink": 0}, "intent": {"kind": "attack", "attack_damage": 11, "attack_count": 1, "block_gain": 0, "strength_gain": 0, "status_kind": "none", "status_stacks": 0, "slimed_added": 0}, "alive": True}], "hand": [{"card_ref": card, "card_definition_id": "strike", "cost": 1, "upgraded": False}], "draw_pile_size": 4, "discard_pile_size": 0, "exhaust_pile_size": 0, "terminal": False, "outcome": "ongoing"}, scope)
    if phase is DecisionPhase.REWARD:
        opened = action in {"reward.choose_card", "reward.skip_card"}
        offers = [{"offer_ref": offer, "card_definition_id": "strike", "upgraded": False}] if opened else []
        return PublicObservation(phase, {"player": _player(), "rewards": [{"reward_ref": gold, "kind": "gold", "claimed": False, "opened": False, "amount": 25, "offers": [], "can_skip": False}, {"reward_ref": reward, "kind": "card", "claimed": False, "opened": opened, "amount": 0, "offers": offers, "can_skip": opened}], "can_proceed": True}, scope)
    if phase is DecisionPhase.MAP:
        return PublicObservation(phase, {"player": _player(), "current_node_ref": None, "nodes": [{"node_ref": node, "kind": "rest", "available": True, "visited": False}], "edges": [], "visited_node_refs": []}, scope)
    if phase is DecisionPhase.ROOM:
        effect = "heal" if kind is RoomKind.REST else "gain_gold"
        return PublicObservation(phase, {"player": _player(), "room_kind": kind.value, "options": [{"option_ref": option, "kind": option_kind.value, "effect": effect, "amount": 18, "enabled": True}], "can_proceed": True}, scope)
    if phase is DecisionPhase.TERMINAL:
        return PublicObservation(phase, {"outcome": "victory", "player": _player()}, scope)
    return PublicObservation(phase, {"reason_code": "unsupported_phase"}, scope)


def _candidate(action: str, scope: PublicScope):
    decision_scope = scope.decision_scope
    card = combat_card_reference(scope, "strike", 0)
    enemy = combat_enemy_reference(scope, "jaw_worm", 0)
    gold = reward_reference(scope, RewardKind.GOLD, 0)
    reward = reward_reference(scope, RewardKind.CARD, 1)
    offer = reward_offer_reference(scope, reward, "strike", 0)
    node = map_node_reference(scope, NodeKind.REST, 0)
    rest = room_option_reference(scope, RoomKind.REST, RoomOptionKind.REST_HEAL, 0)
    event = room_option_reference(scope, RoomKind.EVENT, RoomOptionKind.EVENT_OPTION, 0)
    candidates = {"combat.play_card": CombatPlayCardCandidate(decision_scope, card, enemy), "combat.end_turn": CombatEndTurnCandidate(decision_scope), "reward.claim_gold": RewardClaimGoldCandidate(decision_scope, gold, 25), "reward.open_card_reward": RewardOpenCardRewardCandidate(decision_scope, reward), "reward.choose_card": RewardChooseCardCandidate(decision_scope, reward, offer, "strike"), "reward.skip_card": RewardSkipCardCandidate(decision_scope, reward), "reward.proceed": RewardProceedCandidate(decision_scope), "map.choose_node": MapChooseNodeCandidate(decision_scope, node), "room.rest_heal": RoomRestHealCandidate(decision_scope, rest, 18), "room.event_option": RoomEventOptionCandidate(decision_scope, event), "room.proceed": RoomProceedCandidate(decision_scope)}
    try:
        return candidates[action]
    except KeyError as exc:
        raise ValueError(f"Unsupported recorded action: {action!r}.") from exc


def _event_for(action: str, next_phase: DecisionPhase) -> PublicEvent:
    del next_phase
    records = {
        "combat.play_card": (PublicEventKind.COMBAT_CARD_PLAYED, DecisionPhase.COMBAT, {"card_definition_id": "strike", "target_enemy_definition_id": "jaw_worm"}),
        "combat.end_turn": (PublicEventKind.COMBAT_TURN_ENDED, DecisionPhase.COMBAT, {}),
        "reward.claim_gold": (PublicEventKind.REWARD_GOLD_CLAIMED, DecisionPhase.REWARD, {"amount": 25}),
        "reward.open_card_reward": (PublicEventKind.REWARD_CARD_OPENED, DecisionPhase.REWARD, {"offer_count": 1}),
        "reward.choose_card": (PublicEventKind.REWARD_CARD_CHOSEN, DecisionPhase.REWARD, {"card_definition_id": "strike", "upgraded": False}),
        "reward.skip_card": (PublicEventKind.REWARD_CARD_SKIPPED, DecisionPhase.REWARD, {}),
        "reward.proceed": (PublicEventKind.REWARD_PROCEEDED, DecisionPhase.REWARD, {}),
        "map.choose_node": (PublicEventKind.MAP_NODE_CHOSEN, DecisionPhase.MAP, {"node_kind": "rest"}),
        "room.rest_heal": (PublicEventKind.ROOM_REST_HEALED, DecisionPhase.ROOM, {"amount": 18}),
        "room.event_option": (PublicEventKind.ROOM_EVENT_OPTION_CHOSEN, DecisionPhase.ROOM, {"amount": 18, "effect": "gain_gold"}),
        "room.proceed": (PublicEventKind.ROOM_PROCEEDED, DecisionPhase.ROOM, {}),
    }
    event_type, phase, data = records[action]
    return PublicEvent(0, event_type, phase, data)
