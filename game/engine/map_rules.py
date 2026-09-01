"""Deterministic reduced map rules for the structural headless fixture."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from game.content.reduced_v0 import (
    CONTENT_FINGERPRINT,
    CONTENT_VERSION,
    MAP_TEMPLATES,
    MapTemplate,
)
from game.contracts.headless_v0 import (
    ActionRequest,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    HeadlessBinding,
    MAX_PUBLIC_COUNTER,
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
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
if len(_TEMPLATES_BY_ID) != len(MAP_TEMPLATES):
    raise RuntimeError("Reduced map content contains duplicate template IDs.")


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
    world_rules_fingerprint: str = RULES_FINGERPRINT

    def __post_init__(self) -> None:
        if (
            not isinstance(self.world_rules_fingerprint, str)
            or _SHA256_PATTERN.fullmatch(self.world_rules_fingerprint) is None
        ):
            raise MapRuleError("Expected world rules fingerprint must be canonical SHA-256.")

    def _resolved(self, world: WorldState | None = None) -> MapTemplate:
        configured = None if self.template is None else _template(self.template)
        if world is None:
            return _template(None) if configured is None else configured
        if world.pending_decision is None:
            raise MapRuleError("Map state requires a pending decision identity.")
        context = world.pending_decision.private_context
        if set(context) != {"public_events", "template_id"}:
            raise MapRuleError("Persisted map context fields must be exact.")
        template_id = context["template_id"]
        if not isinstance(template_id, str):
            raise MapRuleError("Persisted map template ID is invalid.")
        persisted = _template(template_id)
        if configured is not None and configured is not persisted:
            raise MapRuleError("Configured map template conflicts with persisted state.")
        return persisted

    def _validate_base_world(self, world: WorldState) -> None:
        try:
            world.validate()
        except ValueError as error:
            raise MapRuleError("World state is invalid at the map boundary.") from error
        if world.content_fingerprint != CONTENT_FINGERPRINT:
            raise MapRuleError("World content fingerprint is not reduced_content_v0.")
        if world.rules_fingerprint != self.world_rules_fingerprint:
            raise MapRuleError("World rules fingerprint does not match configured provenance.")

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
        context = world.pending_decision.private_context
        if set(context) != {"public_events", "template_id"}:
            raise MapRuleError("Persisted map context fields must be exact.")
        raw_events = context["public_events"]
        if not isinstance(raw_events, (list, tuple)) or not all(
            isinstance(item, Mapping) for item in raw_events
        ):
            raise MapRuleError("Persisted map events are invalid.")
        try:
            return tuple(PublicEvent.from_dict(item) for item in raw_events)
        except ValueError as error:
            raise MapRuleError("Persisted map events are invalid.") from error

    @staticmethod
    def _longest_moves_to_terminal(template: MapTemplate, node_id: str) -> int:
        by_id = {node.node_id: node for node in template.nodes}
        node = by_id[node_id]
        if node.kind == NodeKind.TERMINAL.value:
            return 0
        return 1 + max(
            MapRules._longest_moves_to_terminal(template, target_id)
            for target_id in node.next_node_ids
        )

    def _validate_session(self, world: WorldState) -> MapTemplate:
        """Validate all snapshot-backed map invariants before public use."""
        self._validate_base_world(world)
        if world.phase not in (DecisionPhase.MAP, DecisionPhase.TERMINAL):
            raise MapRuleError("Map session must be in the map phase or exact terminal phase.")
        pending = world.pending_decision
        if pending is None or pending.decision_kind != "map_choose_node":
            raise MapRuleError("Map session has the wrong pending decision kind.")
        template = self._resolved(world)
        by_definition = self._node_map(world)
        by_instance = {node.instance_id: node for node in world.map_nodes}

        if len(set(world.node_history)) != len(world.node_history):
            raise MapRuleError("Map history cannot visit a node more than once.")
        try:
            history = [by_instance[node_id] for node_id in world.node_history]
        except KeyError as error:
            raise MapRuleError("Map history references an undeclared node.") from error
        if not history:
            if world.current_node_id is not None:
                raise MapRuleError("An empty map history cannot have a current node.")
        else:
            if world.current_node_id != history[-1].instance_id:
                raise MapRuleError("Current map node must equal the history tail.")
            if history[0].definition_id != "start":
                raise MapRuleError("Map history must begin at start.")
            for source, target in zip(history, history[1:]):
                if target.definition_id not in by_definition[source.definition_id].next_node_ids:
                    raise MapRuleError("Map history contains an impossible edge.")

        terminal_visited = bool(history) and history[-1].node_kind is NodeKind.TERMINAL
        if terminal_visited:
            if (
                world.phase is not DecisionPhase.TERMINAL
                or world.terminal_result is None
                or world.terminal_result.outcome is not RunOutcome.VICTORY
                or world.terminal_result.reason != "map_complete"
            ):
                raise MapRuleError("Visited map terminal has inconsistent terminal state.")
        elif world.phase is not DecisionPhase.MAP or world.terminal_result is not None:
            raise MapRuleError("Map terminal state requires visiting the declared terminal.")

        events = self._current_events(world)
        if not history:
            if events:
                raise MapRuleError("Initial map state cannot contain public events.")
        else:
            if len(events) != 1:
                raise MapRuleError("A traversed map boundary requires exactly one event.")
            event = events[0]
            if (
                event.sequence != 0
                or event.event_type is not PublicEventKind.MAP_NODE_CHOSEN
                or event.phase is not DecisionPhase.MAP
                or dict(event.data) != {"node_kind": history[-1].node_kind.value}
            ):
                raise MapRuleError("Persisted map event does not match the current node.")

        if world.phase is DecisionPhase.MAP:
            next_ids = self._next_ids(world)
            required_moves = max(
                1 + self._longest_moves_to_terminal(template, node_id)
                for node_id in next_ids
            )
            if pending.sequence + required_moves > MAX_PUBLIC_COUNTER:
                raise MapRuleError("Map decision sequence cannot complete within public scope.")
        elif pending.sequence > MAX_PUBLIC_COUNTER:
            raise MapRuleError("Terminal map decision sequence exceeds public scope.")
        return template

    def reset(self, world: WorldState) -> DecisionState:
        """Install a closed registered map with a monotone new decision identity."""
        if world.phase in (DecisionPhase.MAP, DecisionPhase.TERMINAL):
            self._validate_session(world)
        else:
            self._validate_base_world(world)
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
        if len(world.map_nodes) != len(by_id):
            raise MapRuleError("World map nodes do not match declared reduced content.")
        actual_by_id: dict[str, Any] = {}
        for node in world.map_nodes:
            if node.definition_id in actual_by_id:
                raise MapRuleError("World map nodes contain a duplicate definition ID.")
            declared = by_id.get(node.definition_id)
            if declared is None or node.node_kind is not NodeKind(declared.kind):
                raise MapRuleError("World map node kind or identity is not declared.")
            actual_by_id[node.definition_id] = node
        if set(actual_by_id) != set(by_id):
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
        self._validate_session(world)
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
        self._validate_session(world)
        scope = self._scope(world)
        events = self._current_events(world)
        if world.phase is DecisionPhase.TERMINAL:
            if world.terminal_result is None:
                raise MapRuleError("Terminal map state requires a terminal result.")
            return DecisionState.create(
                backend_id=BACKEND_ID,
                backend_version=BACKEND_VERSION,
                backend_fingerprint=BACKEND_FINGERPRINT,
                content_version=CONTENT_VERSION,
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
            content_version=CONTENT_VERSION,
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
                before.public_events,
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
                before.public_events,
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
