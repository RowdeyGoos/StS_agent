"""Deterministic reduced map rules for the structural headless fixture."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from game.content.reduced_v0 import MAP_TEMPLATES, MapTemplate
from game.contracts.headless_v0 import (
    ActionRequest,
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
    json.dumps(
        [template.to_dict() for template in MAP_TEMPLATES],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
).hexdigest()
_TEMPLATES_BY_ID = {template.template_id: template for template in MAP_TEMPLATES}


class MapRuleError(ValueError):
    """Raised when private map state or closed reduced content is invalid."""


def _validate_closed_template(template: MapTemplate) -> None:
    """Validate the intentionally small, terminating map-DAG subset."""
    by_id = {node.node_id: node for node in template.nodes}
    terminals = [node for node in template.nodes if node.kind == NodeKind.TERMINAL.value]
    if len(terminals) != 1 or terminals[0].next_node_ids:
        raise MapRuleError("Reduced map content requires one leaf terminal node.")

    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node_id: str) -> None:
        if node_id in visiting:
            raise MapRuleError("Reduced map content must be acyclic.")
        if node_id in visited:
            return
        visiting.add(node_id)
        node = by_id[node_id]
        if not node.next_node_ids and node.kind != NodeKind.TERMINAL.value:
            raise MapRuleError("Reduced map content cannot have a nonterminal leaf.")
        for target_id in node.next_node_ids:
            walk(target_id)
        visiting.remove(node_id)
        visited.add(node_id)

    walk("start")
    if visited != set(by_id):
        raise MapRuleError("Reduced map content cannot contain unreachable nodes.")


for _registered_template in MAP_TEMPLATES:
    _validate_closed_template(_registered_template)


def _template(value: MapTemplate | str | None) -> MapTemplate:
    if value is None:
        return MAP_TEMPLATES[0]
    if isinstance(value, MapTemplate):
        registered = _TEMPLATES_BY_ID.get(value.template_id)
        if registered is not value:
            raise MapRuleError("Map template must be an exact registered content object.")
        return registered
    registered = _TEMPLATES_BY_ID.get(value)
    if registered is None:
        raise MapRuleError(f"Unknown reduced map template: {value!r}.")
    return registered


@dataclass(slots=True)
class MapRules:
    """Traverse one declared map while WorldState owns persistent identity."""

    template: MapTemplate | str | None = None

    def _resolved(self, world: WorldState | None = None) -> MapTemplate:
        if self.template is not None:
            return _template(self.template)
        if world is not None and world.pending_decision is not None:
            template_id = world.pending_decision.private_context.get("template_id")
            if template_id is not None:
                if not isinstance(template_id, str):
                    raise MapRuleError("Persisted map template ID is invalid.")
                return _template(template_id)
        return _template(None)

    @staticmethod
    def _restore_private(world: WorldState, payload: Mapping[str, Any]) -> None:
        restored = WorldState.from_private_dict(payload)
        for name in world.__dataclass_fields__:
            setattr(world, name, getattr(restored, name))

    @staticmethod
    def _next_sequence(world: WorldState) -> int:
        return 0 if world.pending_decision is None else world.pending_decision.sequence + 1

    @staticmethod
    def _pending_context(template_id: str, events: tuple[PublicEvent, ...]) -> dict[str, Any]:
        return {
            "public_events": [event.to_dict() for event in events],
            "template_id": template_id,
        }

    def _current_events(self, world: WorldState) -> tuple[PublicEvent, ...]:
        if world.pending_decision is None:
            raise MapRuleError("Map state requires a pending decision identity.")
        raw_events = world.pending_decision.private_context.get("public_events", [])
        if not isinstance(raw_events, (list, tuple)) or not all(
            isinstance(item, Mapping) for item in raw_events
        ):
            raise MapRuleError("Persisted map events are invalid.")
        try:
            return tuple(PublicEvent.from_dict(item) for item in raw_events)
        except ValueError as error:
            raise MapRuleError("Persisted map events are invalid.") from error

    def reset(self, world: WorldState) -> DecisionState:
        """Install a closed registered map with a monotone new decision identity."""
        template = self._resolved()
        _validate_closed_template(template)
        definitions = tuple((node.node_id, NodeKind(node.kind)) for node in template.nodes)
        original = world.to_private_dict()
        try:
            sequence = self._next_sequence(world)
            world.map_nodes = ()
            world.current_node_id = None
            world.node_history = ()
            world.terminal_result = None
            world.phase = DecisionPhase.MAP
            world.pending_decision = PendingDecision(
                "map_choose_node",
                sequence,
                self._pending_context(template.template_id, ()),
            )
            for definition_id, kind in definitions:
                world.add_map_node(definition_id, kind)
            world.validate()
            return self.decision(world)
        except Exception:
            self._restore_private(world, original)
            raise

    def _node_map(self, world: WorldState) -> dict[str, Any]:
        template = self._resolved(world)
        by_id = {node.node_id: node for node in template.nodes}
        installed = {node.definition_id for node in world.map_nodes}
        if installed != set(by_id):
            raise MapRuleError("World map nodes do not match declared reduced content.")
        return by_id

    def _scope(self, world: WorldState) -> PublicScope:
        if world.pending_decision is None:
            raise MapRuleError("Map state requires a pending decision identity.")
        return PublicScope(
            0,
            world.pending_decision.sequence,
            {kind.value: 0 for kind in PublicReferenceKind},
        )

    @staticmethod
    def _ordered(world: WorldState) -> tuple[Any, ...]:
        return tuple(
            sorted(world.map_nodes, key=lambda node: (node.definition_id, node.node_kind.value))
        )

    def _next_ids(self, world: WorldState) -> tuple[str, ...]:
        current = next(
            (node for node in world.map_nodes if node.instance_id == world.current_node_id),
            None,
        )
        if current is None:
            if world.current_node_id is not None:
                raise MapRuleError("Current map node is unknown.")
            return ("start",)
        return self._node_map(world)[current.definition_id].next_node_ids

    def visible_graph(self, world: WorldState) -> dict[str, Any]:
        if world.phase is not DecisionPhase.MAP:
            raise MapRuleError("Visible map graphs require the map phase.")
        scope = self._scope(world)
        nodes = self._ordered(world)
        refs = {
            node.instance_id: map_node_reference(scope, node.node_kind, index)
            for index, node in enumerate(nodes)
        }
        reachable = set(self._next_ids(world))
        visited = set(world.node_history)
        data_nodes = [
            {
                "available": node.definition_id in reachable,
                "kind": node.node_kind.value,
                "node_ref": refs[node.instance_id],
                "visited": node.instance_id in visited,
            }
            for node in nodes
        ]
        by_def = {node.definition_id: node for node in nodes}
        edges = [
            {
                "source_node_ref": refs[source.instance_id],
                "target_node_ref": refs[by_def[target_id].instance_id],
            }
            for source in nodes
            for target_id in self._node_map(world)[source.definition_id].next_node_ids
        ]
        edges.sort(key=lambda edge: (edge["source_node_ref"], edge["target_node_ref"]))
        current = next(
            (refs[node.instance_id] for node in nodes if node.instance_id == world.current_node_id),
            None,
        )
        return {
            "current_node_ref": current,
            "edges": edges,
            "nodes": data_nodes,
            "player": {
                "deck_size": len(world.master_deck),
                "gold": world.gold,
                "hp": world.current_hp,
                "max_hp": world.max_hp,
            },
            "visited_node_refs": [
                refs[node.instance_id] for node in nodes if node.instance_id in visited
            ],
        }

    def decision(self, world: WorldState) -> DecisionState:
        if world.phase not in (DecisionPhase.MAP, DecisionPhase.TERMINAL):
            raise MapRuleError("Map rules can only produce decisions in the map phase.")
        scope = self._scope(world)
        events = self._current_events(world)
        if world.phase is DecisionPhase.TERMINAL:
            if world.terminal_result is None:
                raise MapRuleError("Terminal map state requires a terminal result.")
            return DecisionState.create(
                backend_id=BACKEND_ID,
                backend_version=BACKEND_VERSION,
                backend_fingerprint=BACKEND_FINGERPRINT,
                content_version="reduced_content_v0",
                content_fingerprint=world.content_fingerprint,
                rules_version=MAP_RULES_VERSION,
                rules_fingerprint=RULES_FINGERPRINT,
                run_id=world.run_id,
                decision_sequence=scope.decision_ordinal,
                status=DecisionStatus.TERMINAL,
                phase=DecisionPhase.TERMINAL,
                observation=PublicObservation(
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
                ),
                public_events=events,
            )
        graph = self.visible_graph(world)
        candidates = tuple(
            MapChooseNodeCandidate(scope.decision_scope, node["node_ref"])
            for node in graph["nodes"]
            if node["available"]
        )
        return DecisionState.create(
            backend_id=BACKEND_ID,
            backend_version=BACKEND_VERSION,
            backend_fingerprint=BACKEND_FINGERPRINT,
            content_version="reduced_content_v0",
            content_fingerprint=world.content_fingerprint,
            rules_version=MAP_RULES_VERSION,
            rules_fingerprint=RULES_FINGERPRINT,
            run_id=world.run_id,
            decision_sequence=scope.decision_ordinal,
            status=DecisionStatus.ACTIONABLE,
            phase=DecisionPhase.MAP,
            observation=PublicObservation(DecisionPhase.MAP, graph, scope),
            candidates=candidates,
            public_events=events,
        )

    def choose_node(
        self,
        world: WorldState,
        request: ActionRequest | HeadlessBinding,
    ) -> Transition:
        """Apply one fully bound map choice, atomically including projection work."""
        if isinstance(request, ActionRequest):
            binding = request.binding
        elif isinstance(request, HeadlessBinding):
            binding = request
        else:
            raise TypeError("Map choices require an ActionRequest or HeadlessBinding.")

        before = self.decision(world)
        if (
            binding.run_id != before.run_id
            or binding.decision_sequence != before.decision_sequence
            or binding.decision_hash != before.decision_hash
        ):
            return Transition(
                TransitionResult.STALE,
                TransitionReason.STALE_BINDING,
                binding,
                (),
                before,
            )
        selected = next(
            (item for item in before.candidates if item.candidate_id == binding.candidate_id),
            None,
        )
        if selected is None:
            return Transition(
                TransitionResult.REJECTED,
                TransitionReason.INVALID_CANDIDATE,
                binding,
                (),
                before,
            )

        original = world.to_private_dict()
        try:
            node = self._node_by_ref(world, selected.node_ref)
            event = PublicEvent(
                0,
                PublicEventKind.MAP_NODE_CHOSEN,
                DecisionPhase.MAP,
                {"node_kind": node.node_kind.value},
            )
            world.current_node_id = node.instance_id
            world.node_history = (*world.node_history, node.instance_id)
            world.pending_decision = PendingDecision(
                "map_choose_node",
                before.decision_sequence + 1,
                self._pending_context(self._resolved(world).template_id, (event,)),
            )
            if node.node_kind is NodeKind.TERMINAL:
                world.phase = DecisionPhase.TERMINAL
                world.terminal_result = TerminalResult(RunOutcome.VICTORY, "map_complete")
            world.validate()
            after = self.decision(world)
            return Transition(
                TransitionResult.ACCEPTED,
                TransitionReason.ACCEPTED,
                binding,
                after.public_events,
                after,
            )
        except Exception:
            self._restore_private(world, original)
            raise

    def _node_by_ref(self, world: WorldState, reference: str) -> Any:
        scope = self._scope(world)
        for index, node in enumerate(self._ordered(world)):
            if map_node_reference(scope, node.node_kind, index) == reference:
                return node
        raise MapRuleError("Unknown map node reference.")


__all__ = [
    "BACKEND_FINGERPRINT",
    "MAP_RULES_VERSION",
    "RULES_FINGERPRINT",
    "MapRuleError",
    "MapRules",
]
