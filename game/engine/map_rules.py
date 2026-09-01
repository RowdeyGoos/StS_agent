"""Deterministic reduced map rules for the structural headless fixture."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping

from game.content.reduced_v0 import MAP_TEMPLATES, MapTemplate
from game.contracts.headless_v0 import (
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    HeadlessBinding,
    MapChooseNodeCandidate,
    NodeKind,
    PublicEvent,
    PublicEventKind,
    PublicObservation,
    PublicReferenceKind,
    PublicScope,
    RunOutcome,
    Transition,
    TransitionReason,
    TransitionResult,
    map_node_reference,
)
from game.engine.headless_state import PendingDecision, TerminalResult, WorldState


MAP_RULES_VERSION = "reduced_map_rules_v0"
BACKEND_ID = "reduced_map_rules"
BACKEND_VERSION = "reduced_map_rules_v0"
BACKEND_FINGERPRINT = sha256(BACKEND_VERSION.encode()).hexdigest()
RULES_FINGERPRINT = sha256(
    json.dumps([template.to_dict() for template in MAP_TEMPLATES], sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


class MapRuleError(ValueError):
    """Raised when a map template or map operation is invalid."""


def _template(value: MapTemplate | str | None) -> MapTemplate:
    if value is None:
        return MAP_TEMPLATES[0]
    if isinstance(value, MapTemplate):
        return value
    for item in MAP_TEMPLATES:
        if item.template_id == value:
            return item
    raise MapRuleError(f"Unknown reduced map template: {value!r}.")


@dataclass(slots=True)
class MapRules:
    """Own the explicit DAG projection while persistent state owns identities."""

    template: MapTemplate | str | None = None
    _bindings: dict[str, HeadlessBinding] = field(default_factory=dict, init=False, repr=False)

    def _resolved(self) -> MapTemplate:
        return _template(self.template)

    def reset(self, world: WorldState) -> DecisionState:
        """Install only nodes reachable from ``start`` and expose the first choice."""
        template = self._resolved()
        reachable: list[str] = []
        by_id = {node.node_id: node for node in template.nodes}
        pending = ["start"]
        while pending:
            node_id = pending.pop(0)
            if node_id in reachable:
                continue
            node = by_id[node_id]
            reachable.append(node_id)
            pending.extend(node.next_node_ids)
        # Validate all content before changing the world, then consume IDs through
        # the sole allocator.  Existing map state is intentionally replaced.
        definitions = tuple((node_id, NodeKind(by_id[node_id].kind)) for node_id in reachable)
        original = world.to_private_dict()
        try:
            world.map_nodes = ()
            world.current_node_id = None
            world.node_history = ()
            world.terminal_result = None
            world.phase = DecisionPhase.MAP
            world.pending_decision = PendingDecision("map_choose_node", 0, {"template_id": template.template_id})
            for definition_id, kind in definitions:
                world.add_map_node(definition_id, kind)
            world.validate()
        except Exception:
            self._restore_private(world, original)
            raise
        return self.decision(world)

    @staticmethod
    def _restore_private(world: WorldState, payload: Mapping[str, Any]) -> None:
        restored = WorldState.from_private_dict(payload)
        for name in world.__dataclass_fields__:
            setattr(world, name, getattr(restored, name))

    def _node_map(self, world: WorldState) -> dict[str, Any]:
        template = self._resolved()
        installed = {item.definition_id for item in world.map_nodes}
        return {node.node_id: node for node in template.nodes if node.node_id in installed}

    def _scope(self, world: WorldState) -> PublicScope:
        sequence = world.pending_decision.sequence if world.pending_decision else 0
        return PublicScope(0, sequence, {kind.value: 0 for kind in PublicReferenceKind})

    def _ordered(self, world: WorldState) -> tuple[Any, ...]:
        return tuple(sorted(world.map_nodes, key=lambda node: (node.definition_id, node.node_kind.value)))

    def visible_graph(self, world: WorldState) -> dict[str, Any]:
        scope = self._scope(world)
        nodes = self._ordered(world)
        refs = {node.instance_id: map_node_reference(scope, node.node_kind, index) for index, node in enumerate(nodes)}
        visited = set(world.node_history)
        data_nodes = [
            {"available": node.definition_id == "start" or (world.current_node_id is not None and node.definition_id in self._next_ids(world)),
             "kind": node.node_kind.value, "node_ref": refs[node.instance_id], "visited": node.instance_id in visited}
            for node in nodes
        ]
        edges = []
        by_def = {node.definition_id: node for node in nodes}
        for source in nodes:
            for target_id in self._node_map(world)[source.definition_id].next_node_ids:
                edges.append({"source_node_ref": refs[source.instance_id], "target_node_ref": refs[by_def[target_id].instance_id]})
        edges.sort(key=lambda edge: (edge["source_node_ref"], edge["target_node_ref"]))
        current = next((refs[node.instance_id] for node in nodes if node.instance_id == world.current_node_id), None)
        return {"current_node_ref": current, "edges": edges, "nodes": data_nodes,
                "player": {"deck_size": len(world.master_deck), "gold": world.gold, "hp": world.current_hp, "max_hp": world.max_hp},
                "visited_node_refs": [refs[node.instance_id] for node in nodes if node.instance_id in visited]}

    def _next_ids(self, world: WorldState) -> tuple[str, ...]:
        current = next((node for node in world.map_nodes if node.instance_id == world.current_node_id), None)
        if current is None:
            return ("start",)
        return self._node_map(world)[current.definition_id].next_node_ids

    def decision(self, world: WorldState) -> DecisionState:
        scope = self._scope(world)
        if world.phase is DecisionPhase.TERMINAL:
            return DecisionState.create(backend_id=BACKEND_ID, backend_version=BACKEND_VERSION, backend_fingerprint=BACKEND_FINGERPRINT,
                content_version="reduced_content_v0", content_fingerprint=world.content_fingerprint, rules_version=MAP_RULES_VERSION,
                rules_fingerprint=RULES_FINGERPRINT, run_id=world.run_id, decision_sequence=scope.decision_ordinal,
                status=DecisionStatus.TERMINAL, phase=DecisionPhase.TERMINAL,
                observation=PublicObservation(DecisionPhase.TERMINAL, {"outcome": RunOutcome.VICTORY.value, "player": {"deck_size": len(world.master_deck), "gold": world.gold, "hp": world.current_hp, "max_hp": world.max_hp}}, scope))
        candidates = []
        nodes = self._ordered(world)
        for index, node in enumerate(nodes):
            if node.definition_id in self._next_ids(world):
                candidates.append(MapChooseNodeCandidate(scope.decision_scope, map_node_reference(scope, node.node_kind, index)))
        result = DecisionState.create(backend_id=BACKEND_ID, backend_version=BACKEND_VERSION, backend_fingerprint=BACKEND_FINGERPRINT,
            content_version="reduced_content_v0", content_fingerprint=world.content_fingerprint, rules_version=MAP_RULES_VERSION,
            rules_fingerprint=RULES_FINGERPRINT, run_id=world.run_id, decision_sequence=scope.decision_ordinal,
            status=DecisionStatus.ACTIONABLE, phase=DecisionPhase.MAP, observation=PublicObservation(DecisionPhase.MAP, self.visible_graph(world), scope), candidates=candidates)
        for item in result.candidates:
            self._bindings[item.candidate_id] = HeadlessBinding.for_candidate(result, item.candidate_id)
        return result

    def choose_node(self, world: WorldState, candidate: MapChooseNodeCandidate | str | HeadlessBinding) -> Transition:
        before = self.decision(world)
        if isinstance(candidate, HeadlessBinding):
            binding = candidate
        elif isinstance(candidate, MapChooseNodeCandidate):
            binding = self._bindings.get(candidate.candidate_id)
            if binding is None:
                binding = HeadlessBinding.for_candidate(before, candidate.candidate_id)
        else:
            # A well-formed but unadvertised candidate is rejected with an
            # authoritative binding; malformed IDs still fail closed.
            binding = HeadlessBinding(before.run_id, before.decision_sequence, before.decision_hash, candidate)
        if (binding.run_id != before.run_id or binding.decision_hash != before.decision_hash
                or binding.decision_sequence != before.decision_sequence):
            return Transition(TransitionResult.STALE, TransitionReason.STALE_BINDING, binding, (), before)
        selected = next((item for item in before.candidates if item.candidate_id == binding.candidate_id), None)
        if selected is None:
            return Transition(TransitionResult.REJECTED, TransitionReason.INVALID_CANDIDATE, binding, (), before)
        node = self._node_by_ref(world, selected.node_ref)
        world.current_node_id = node.instance_id
        world.node_history = (*world.node_history, node.instance_id)
        event = PublicEvent(0, PublicEventKind.MAP_NODE_CHOSEN, DecisionPhase.MAP, {"node_kind": node.node_kind.value})
        if node.node_kind is NodeKind.TERMINAL:
            world.pending_decision = PendingDecision("map_choose_node", before.decision_sequence + 1, {"template_id": self._resolved().template_id})
            world.phase = DecisionPhase.TERMINAL
            world.terminal_result = TerminalResult(RunOutcome.VICTORY, "map_complete")
        else:
            world.pending_decision = PendingDecision("map_choose_node", before.decision_sequence + 1, {"template_id": self._resolved().template_id})
        after = self.decision(world)
        after = DecisionState.create(backend_id=after.backend_id, backend_version=after.backend_version, backend_fingerprint=after.backend_fingerprint,
            content_version=after.content_version, content_fingerprint=after.content_fingerprint, rules_version=after.rules_version,
            rules_fingerprint=after.rules_fingerprint, run_id=after.run_id, decision_sequence=after.decision_sequence,
            status=after.status, phase=after.phase, observation=after.observation, candidates=after.candidates, public_events=(event,))
        return Transition(TransitionResult.ACCEPTED, TransitionReason.ACCEPTED, binding, (event,), after)

    def _node_by_ref(self, world: WorldState, reference: str) -> Any:
        scope = self._scope(world)
        for index, node in enumerate(self._ordered(world)):
            if map_node_reference(scope, node.node_kind, index) == reference:
                return node
        raise MapRuleError("Unknown map node reference.")


__all__ = ["BACKEND_FINGERPRINT", "MAP_RULES_VERSION", "RULES_FINGERPRINT", "MapRuleError", "MapRules"]
