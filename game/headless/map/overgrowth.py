"""Pinned A0 topology; selectable base fixture or pruned unknown-room map."""

from collections import deque
from math import log, pi, sin, sqrt

from game.headless.map.graph import MapGraph, MapNode

BASE_PROFILE = "overgrowth_a0_base_restricted_v1"
PROFILE = "overgrowth_a0_pruned_restricted_v2"
class OrderedPoints(dict):
    """Insertion-ordered adjacency; only construction adds, pruning removes."""
    def __init__(self, points=()):
        super().__init__((p, None) for p in points)
    def add(self, point): self[point] = None
    def discard(self, point): self.pop(point, None)


ROWS = 15
WIDTH = 7


def _gaussian_count(rng, mean, low, high):
    if getattr(rng,"native",False):
        return rng.stream("act1.map").gaussian_int(mean,1,low,high)
    # Native NextGaussianInt: rounded Box–Muller, rejection rather than clamping.
    for _ in range(10000):
        u = 1 - rng.random("act1.map")
        v = 1 - rng.random("act1.map")
        value = round(mean + sqrt(-2 * log(u)) * sin(2 * pi * v))
        if low <= value <= high:
            return value
    raise RuntimeError("Map count sampling exceeded its bound.")


def generate_overgrowth_map(rng, *, event_pool, profile=PROFILE):
    from game.headless.events.catalog import EVENTS
    if not event_pool or len(set(event_pool)) != len(event_pool) or any(e not in EVENTS for e in event_pool):
        raise ValueError("Generated maps require an explicit supported event pool.")
    if profile not in (BASE_PROFILE, PROFILE):
        raise ValueError("Unsupported generated map profile.")
    unknown_kind = "event" if profile == BASE_PROFILE else "unknown"
    rest_count = _gaussian_count(rng, 7, 6, 7)
    event_count = _gaussian_count(rng, 12, 10, 14)
    native = getattr(rng, "native", False)
    points = OrderedPoints if native else set
    edges = {}
    starts = []
    for path in range(7):
        columns = list(range(WIDTH))
        if path == 1 and not native:
            columns.remove(starts[0][1])
        current = (1, rng.choice("act1.map", columns))
        while native and path == 1 and current in starts:
            current = (1, rng.choice("act1.map", columns))
        if current not in starts:
            starts.append(current)
        edges.setdefault(current, points())
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
            edges.setdefault(target, points())
            current = target
    parents = {point: points() for point in edges}
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

    queue = deque(["rest"] * rest_count + ["shop"] * 3 + ["elite"] * 5 + [unknown_kind] * event_count)
    for _ in range(3):
        unassigned = sorted((p for p, kind in kinds.items() if kind is None), key=(lambda p:(p[1],p[0])) if native else None)
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
    kinds.update((point, kind or "combat") for point, kind in kinds.items())
    if profile == PROFILE:
        from game.headless.map.pruning import prune_and_repair
        root, boss = (0, 3), (16, 3)
        edges[root], parents[root], kinds[root] = points(sorted(starts)), points(), "ancient"
        for point in starts:
            parents[point].add(root)
        edges[boss], parents[boss], kinds[boss] = points(), points(), "boss"
        for point in tuple(edges):
            if point[0] == ROWS:
                edges[point].add(boss)
                parents[boss].add(point)
        prune_and_repair(edges, parents, kinds, root, rng,
                         {"rest": rest_count, "unknown": event_count, "shop": 3, "elite": 5}, valid)
        if native:
            from game.headless.map.postprocessing import reposition
            edges, parents, kinds = reposition(edges, parents, kinds)
        starts = sorted(edges.pop(root))
        del edges[boss], kinds[root], kinds[boss]
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
    return MapGraph(tuple(nodes), entries[0], entries, profile)


def validate_generated_map(graph):
    """Reject malformed private layouts without regenerating or consuming RNG."""
    if graph.generation not in (BASE_PROFILE, PROFILE):
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
        extra_kind = "event" if graph.generation == BASE_PROFILE else "unknown"
        if node.kind not in ("combat", "elite", "boss", "rest", "treasure", "shop", extra_kind) or node.encounter_id is not None:
            raise ValueError("Generated maps use run-owned encounter queues.")
        if node.kind == "event" and node.event_id is None:
            raise ValueError("Restricted generated event requires its definition.")
        if node.kind == "unknown" and node.event_id is not None:
            raise ValueError("Unknown map points cannot contain an eventual event.")
        required = {1: "combat", 9: "treasure", 15: "rest", 16: "boss"}.get(node.row)
        if required and node.kind != required or not required and node.kind in ("treasure", "boss"):
            raise ValueError("Invalid fixed map row.")
        if node.row < 6 and node.kind in ("rest", "elite") or node.row in (13, 14) and node.kind == "rest":
            raise ValueError("Invalid early/late room placement.")
    bosses = [n for n in graph.nodes if n.kind == "boss"]
    if len(bosses) != 1 or bosses[0].next_node_ids or bosses[0].column != 3:
        raise ValueError("Generated map requires one final boss.")
    entries = tuple(n.node_id for n in sorted(graph.nodes, key=lambda n: n.column) if n.row == 1)
    if graph.entry_node_ids != entries or len(entries) < (2 if graph.generation == BASE_PROFILE else 1):
        raise ValueError("Generated map entrances differ from its first row.")
    for node in graph.nodes:
        if node.row < 16 and not node.next_node_ids:
            raise ValueError("Generated path ends before its boss.")
        if node.row not in (1, 9, 15, 16) and node.kind in ("rest", "elite", "shop", "event", "unknown"):
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
