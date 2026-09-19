"""Immutable map topology, shared by authored and generated routes."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MapNode:
    node_id: str
    kind: str
    next_node_ids: tuple[str, ...]
    encounter_id: str | None = None
    event_id: str | None = None
    row: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True)
class MapGraph:
    nodes: tuple[MapNode, ...]
    start_id: str
    entry_node_ids: tuple[str, ...] = ()
    generation: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "entry_node_ids", tuple(self.entry_node_ids))
        ids = {node.node_id for node in self.nodes}
        if len(ids) != len(self.nodes) or self.start_id not in ids:
            raise ValueError("Invalid map identities.")
        entries = self.entry_node_ids or (self.start_id,)
        if not set(entries) <= ids or len(set(entries)) != len(entries) or self.start_id != entries[0]:
            raise ValueError("Invalid map entrances.")
        for node in self.nodes:
            if node.event_id is not None and (node.kind != "event" or not isinstance(node.event_id, str) or not node.event_id or node.encounter_id is not None):
                raise ValueError("Event identity requires an event-only node.")
            if not set(node.next_node_ids) <= ids or len(set(node.next_node_ids)) != len(node.next_node_ids):
                raise ValueError("Invalid map edges.")
        def visit(node_id, active, visited):
            if node_id in active:
                raise ValueError("Map must be acyclic.")
            if node_id in visited:
                return
            node = self.node(node_id)
            for target in node.next_node_ids:
                visit(target, active | {node_id}, visited)
            visited.add(node_id)
        visited = set()
        for entry in entries:
            visit(entry, set(), visited)
        if visited != ids:
            raise ValueError("Map contains unreachable nodes.")
        if self.generation is not None:
            from game.headless.map.overgrowth import validate_generated_map
            from game.headless.map.golden_path import PROFILE, validate
            validate(self) if self.generation == PROFILE else validate_generated_map(self)

    def node(self, node_id: str) -> MapNode:
        try:
            return next(node for node in self.nodes if node.node_id == node_id)
        except StopIteration as error:
            raise ValueError("Unknown map node.") from error

    def available_nodes(self, current_node_id: str | None) -> tuple[str, ...]:
        return (self.entry_node_ids or (self.start_id,)) if current_node_id is None else self.node(current_node_id).next_node_ids
