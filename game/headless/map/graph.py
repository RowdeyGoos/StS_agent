"""Map navigation over authored nodes; procedural generation is separate work."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MapNode:
    node_id: str
    kind: str
    next_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MapGraph:
    nodes: tuple[MapNode, ...]
    start_id: str

    def __post_init__(self):
        object.__setattr__(self, "nodes", tuple(self.nodes))
        ids = {node.node_id for node in self.nodes}
        if len(ids) != len(self.nodes) or self.start_id not in ids:
            raise ValueError("Invalid map identities.")
        for node in self.nodes:
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
        visit(self.start_id, set(), visited)
        if visited != ids:
            raise ValueError("Map contains unreachable nodes.")

    def node(self, node_id: str) -> MapNode:
        try:
            return next(node for node in self.nodes if node.node_id == node_id)
        except StopIteration as error:
            raise ValueError("Unknown map node.") from error

    def available_nodes(self, current_node_id: str | None) -> tuple[str, ...]:
        return (self.start_id,) if current_node_id is None else self.node(current_node_id).next_node_ids
