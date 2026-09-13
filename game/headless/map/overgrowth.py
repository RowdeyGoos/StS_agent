"""Pinned A0 base topology with explicitly restricted event substitution.

Seven paths, rows 1–15 and boss row 16. Native pruning/visual postprocessing,
unknown-room rolls and the row-zero Ancient are not implemented by this profile.
"""

from collections import deque
from math import log, pi, sin, sqrt

from game.headless.map.graph import MapGraph, MapNode

PROFILE = "overgrowth_a0_base_restricted_v1"
ROWS = 15
WIDTH = 7


def _gaussian_count(rng, mean, low, high):
    # Native NextGaussianInt: rounded Box–Muller, rejection rather than clamping.
    for _ in range(10000):
        u = 1 - rng.random("act1.map")
        v = 1 - rng.random("act1.map")
        value = round(mean + sqrt(-2 * log(u)) * sin(2 * pi * v))
        if low <= value <= high:
            return value
    raise RuntimeError("Map count sampling exceeded its bound.")


def generate_overgrowth_map(rng, *, event_pool):
    from game.headless.events.catalog import EVENTS
    if not event_pool or len(set(event_pool)) != len(event_pool) or any(e not in EVENTS for e in event_pool):
        raise ValueError("Generated maps require an explicit supported event pool.")
    rest_count = _gaussian_count(rng, 7, 6, 7)
    event_count = _gaussian_count(rng, 12, 10, 14)
    edges = {}
    starts = []
    for path in range(7):
        columns = list(range(WIDTH))
        if path == 1:
            columns.remove(starts[0][1])
        current = (1, rng.choice("act1.map", columns))
        if current not in starts:
            starts.append(current)
        edges.setdefault(current, set())
        for row in range(2, ROWS + 1):
            offsets = [-1, 0, 1]
            rng.shuffle("act1.map", offsets)
            for offset in offsets:
                col = min(WIDTH - 1, max(0, current[1] + offset))
                # Opposing diagonals between adjacent columns cannot cross.
                if (row, current[1]) not in edges.get((row - 1, col), ()) or col == current[1]:
                    target = (row, col)
                    break
            else:
                raise RuntimeError("No noncrossing map continuation.")
            edges[current].add(target)
            edges.setdefault(target, set())
            current = target
    parents = {point: set() for point in edges}
    for point, children in edges.items():
        for child in children:
            parents[child].add(point)
    kinds = {point: ("combat" if point[0] == 1 else "treasure" if point[0] == 9 else
                     "rest" if point[0] == 15 else None) for point in edges}

    def valid(kind, point):
        row = point[0]
        if row < 6 and kind in ("rest", "elite") or row >= 13 and kind == "rest":
            return False
        if kind in ("rest", "elite", "shop", "treasure") and any(
                kinds[p] == kind for p in parents[point] | edges[point]):
            return False
        siblings = {child for parent in parents[point] for child in edges[parent]} - {point}
        return not any(kinds[s] == kind for s in siblings)

    queue = deque(["rest"] * rest_count + ["shop"] * 3 + ["elite"] * 5 + ["event"] * event_count)
    for _ in range(3):
        unassigned = sorted(p for p, kind in kinds.items() if kind is None)
        rng.shuffle("act1.map", unassigned)
        for point in unassigned:
            for _ in range(len(queue)):
                kind = queue.popleft()
                if valid(kind, point):
                    kinds[point] = kind
                    break
                queue.append(kind)
        if not queue:
            break
    # Native generation also fills unassigned points with ordinary combat.
    def identity(point):
        return f"act1.{point[0]}.{point[1]}"
    nodes = []
    for point in sorted(edges):
        kind = kinds[point] or "combat"
        children = tuple(identity(p) for p in sorted(edges[point])) if point[0] < ROWS else ("act1.boss",)
        event_id = rng.choice("act1.map.events", event_pool) if kind == "event" else None
        nodes.append(MapNode(identity(point), kind, children, event_id=event_id, row=point[0], column=point[1]))
    nodes.append(MapNode("act1.boss", "boss", (), row=16, column=3))
    entries = tuple(identity(p) for p in sorted(starts))
    return MapGraph(tuple(nodes), entries[0], entries, PROFILE)


def validate_generated_map(graph):
    """Reject malformed private layouts without regenerating or consuming RNG."""
    if graph.generation != PROFILE:
        raise ValueError("Unsupported generated map profile.")
    points = {}
    for node in graph.nodes:
        if (type(node.row) is not int or not 1 <= node.row <= 16 or type(node.column) is not int
                or not 0 <= node.column < WIDTH or (node.row, node.column) in points):
            raise ValueError("Invalid generated map coordinates.")
        points[node.row, node.column] = node
        expected_id = "act1.boss" if node.row == 16 else f"act1.{node.row}.{node.column}"
        if node.node_id != expected_id:
            raise ValueError("Generated map identity differs from its coordinates.")
        if node.kind not in ("combat", "elite", "boss", "rest", "treasure", "shop", "event") or node.encounter_id is not None:
            raise ValueError("Generated maps use run-owned encounter queues.")
        if node.kind == "event" and node.event_id is None:
            raise ValueError("Restricted generated event requires its definition.")
        required = {1: "combat", 9: "treasure", 15: "rest", 16: "boss"}.get(node.row)
        if required and node.kind != required or not required and node.kind in ("treasure", "boss"):
            raise ValueError("Invalid fixed map row.")
        if node.row < 6 and node.kind in ("rest", "elite") or node.row in (13, 14) and node.kind == "rest":
            raise ValueError("Invalid early/late room placement.")
    bosses = [n for n in graph.nodes if n.kind == "boss"]
    if len(bosses) != 1 or bosses[0].next_node_ids or bosses[0].column != 3:
        raise ValueError("Generated map requires one final boss.")
    entries = tuple(n.node_id for n in sorted(graph.nodes, key=lambda n: n.column) if n.row == 1)
    if graph.entry_node_ids != entries or len(entries) < 2:
        raise ValueError("Generated map entrances differ from its first row.")
    for node in graph.nodes:
        if node.row < 16 and not node.next_node_ids:
            raise ValueError("Generated path ends before its boss.")
        if node.row not in (1, 9, 15, 16) and node.kind in ("rest", "elite", "shop", "event"):
            siblings = {child for parent in graph.nodes if node.node_id in parent.next_node_ids
                        for child in parent.next_node_ids} - {node.node_id}
            if any(graph.node(sibling).kind == node.kind for sibling in siblings):
                raise ValueError("Sibling choices duplicate a restricted room type.")
        for target_id in node.next_node_ids:
            target = graph.node(target_id)
            if target.row != node.row + 1 or node.row < 15 and abs(target.column - node.column) > 1:
                raise ValueError("Invalid generated map edge.")
            if node.kind == target.kind and node.kind in ("rest", "elite", "shop", "treasure"):
                raise ValueError("Consecutive restricted room types.")
            opposite = points.get((node.row, target.column))
            if node.row < 15 and node.column != target.column and opposite and any(
                    graph.node(c).column == node.column for c in opposite.next_node_ids):
                raise ValueError("Generated paths cross.")
