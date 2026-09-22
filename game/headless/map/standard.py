"""Shared native A0 standard maps with region-owned sizes and RNG domains."""

from collections import deque
from math import log, pi, sin, sqrt

from game.headless.map.graph import MapGraph, MapNode

BASE_PROFILE = "overgrowth_a0_base_restricted_v1"
PROFILE = "overgrowth_a0_pruned_restricted_v2"
UNDERDOCKS_BASE_PROFILE = "underdocks_a0_base_restricted_v1"
UNDERDOCKS_PROFILE = "underdocks_a0_pruned_restricted_v1"
HIVE_BASE_PROFILE = "hive_a0_base_v1"
HIVE_PROFILE = "hive_a0_pruned_v1"
GLORY_BASE_PROFILE = "glory_a0_base_v1"
GLORY_PROFILE = "glory_a0_pruned_v1"
BASE_PROFILES = (BASE_PROFILE, UNDERDOCKS_BASE_PROFILE, HIVE_BASE_PROFILE, GLORY_BASE_PROFILE)
SPOILS_PROFILE = "hive_a0_spoils_v1"
PRUNED_PROFILES = (PROFILE, UNDERDOCKS_PROFILE, HIVE_PROFILE, GLORY_PROFILE, SPOILS_PROFILE)


def profile_for(act, *, base=False):
    if act == 'glory':
        return GLORY_BASE_PROFILE if base else GLORY_PROFILE
    if act == 'hive':
        return HIVE_BASE_PROFILE if base else HIVE_PROFILE
    if act not in ('overgrowth', 'underdocks'):
        raise ValueError('Unsupported Act 1 location.')
    return (BASE_PROFILE if base else PROFILE) if act == 'overgrowth' else (UNDERDOCKS_BASE_PROFILE if base else UNDERDOCKS_PROFILE)


def ancients_for(act):
    from game.headless.generation.room_pools import REGION_POOLS, SHARED_ANCIENTS
    return (*REGION_POOLS[act][4], *SHARED_ANCIENTS) if act in ('hive', 'glory') else ()


class OrderedPoints(dict):
    """Insertion-ordered adjacency; only construction adds, pruning removes."""
    def __init__(self, points=()):
        super().__init__((p, None) for p in points)
    def add(self, point): self[point] = None
    def discard(self, point): self.pop(point, None)


ROWS = 15
WIDTH = 7


def _gaussian_count(rng, mean, low, high, stream="act1.map"):
    if getattr(rng,"native",False):
        return rng.stream(stream).gaussian_int(mean,1,low,high)
    # Native NextGaussianInt: rounded Box–Muller, rejection rather than clamping.
    for _ in range(10000):
        u = 1 - rng.random(stream)
        v = 1 - rng.random(stream)
        value = round(mean + sqrt(-2 * log(u)) * sin(2 * pi * v))
        if low <= value <= high:
            return value
    raise RuntimeError("Map count sampling exceeded its bound.")


def generate_map(rng, *, event_pool, act="overgrowth", profile=None, ancient=None, ascension=0, second_boss=False):
    from game.headless.core.ascension import validate
    validate(ascension)
    elite_count = 8 if ascension >= 1 else 5
    rows = {"hive": 14, "glory": 13}.get(act, 15)
    prefix = {"hive": "act2", "glory": "act3"}.get(act, "act1")
    stream = "spoils_map" if profile == SPOILS_PROFILE else prefix + ".map"
    profile = profile or profile_for(act)
    from game.headless.events.catalog import EVENTS
    if not event_pool or len(set(event_pool)) != len(event_pool) or any(e not in EVENTS for e in event_pool):
        raise ValueError("Generated maps require an explicit supported event pool.")
    if profile not in (profile_for(act, base=True), profile_for(act), *( (SPOILS_PROFILE,) if act == "hive" else () )):
        raise ValueError("Unsupported generated map profile.")
    unknown_kind = "event" if profile in BASE_PROFILES else "unknown"
    rest_count = rng.randint(stream, 5, 6) if act == "glory" else _gaussian_count(rng, 6 if act == "hive" else 7, 6, 7, stream)
    event_count = _gaussian_count(rng, 12, 10, 14, stream) - int(act in ("hive", "glory"))
    native = getattr(rng, "native", False)
    points = OrderedPoints if native else set
    edges = {}
    starts = []
    if profile == SPOILS_PROFILE:
        from game.headless.map.spoils import hourglass_paths
        edges, starts = hourglass_paths(rng, stream, rows, points)
    else:
        for path in range(7):
            columns = list(range(WIDTH))
            if path == 1 and not native:
                columns.remove(starts[0][1])
            current = (1, rng.choice(stream, columns))
            while native and path == 1 and current in starts:
                current = (1, rng.choice(stream, columns))
            if current not in starts:
                starts.append(current)
            edges.setdefault(current, points())
            for row in range(2, rows + 1):
                offsets = [-1, 0, 1]
                rng.shuffle(stream, offsets)
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
    kinds = {point: ("combat" if point[0] == 1 else "treasure" if point[0] == rows - 6 else
                     "rest" if point[0] == rows else None) for point in edges}

    def valid(kind, point):
        row = point[0]
        if row < 6 and kind in ("rest", "elite") or row >= rows - 2 and kind == "rest":
            return False
        if kind in ("rest", "elite", "shop", "treasure") and any(
                kinds[p] == kind for p in parents[point] | edges[point]):
            return False
        siblings = {child for parent in parents[point] for child in edges[parent]} - {point}
        return not any(kinds[s] == kind for s in siblings)

    queue = deque(["rest"] * rest_count + ["shop"] * 3 + ["elite"] * elite_count + [unknown_kind] * event_count)
    for _ in range(3):
        unassigned = sorted((p for p, kind in kinds.items() if kind is None), key=(lambda p:(p[1],p[0])) if native else None)
        rng.shuffle(stream, unassigned)
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
    if profile in PRUNED_PROFILES:
        from game.headless.map.pruning import prune_and_repair
        root, boss = (0, 3), (rows + 1, 3)
        edges[root], parents[root], kinds[root] = points(sorted(starts)), points(), "ancient"
        for point in starts:
            parents[point].add(root)
        edges[boss], parents[boss], kinds[boss] = points(), points(), "boss"
        for point in tuple(edges):
            if point[0] == rows:
                edges[point].add(boss)
                parents[boss].add(point)
        prune_and_repair(edges, parents, kinds, root, rng,
                         {"rest": rest_count, "unknown": event_count, "shop": 3, "elite": elite_count}, valid, stream=stream)
        if native and profile != SPOILS_PROFILE:
            from game.headless.map.postprocessing import reposition
            edges, parents, kinds = reposition(edges, parents, kinds)
        starts = sorted(edges.pop(root))
        del edges[boss], kinds[root], kinds[boss]
    def identity(point):
        return f"{prefix}.{point[0]}.{point[1]}"
    nodes = []
    for point in sorted(edges):
        kind = kinds[point] or "combat"
        children = tuple(identity(p) for p in sorted(edges[point])) if point[0] < rows else (prefix + ".boss",)
        event_id = rng.choice(prefix + ".map.events", event_pool) if kind == "event" else None
        nodes.append(MapNode(identity(point), kind, children, event_id=event_id, row=point[0], column=point[1]))
    nodes.append(MapNode(prefix + ".boss", "boss", (prefix + ".boss2",) if second_boss else (), row=rows + 1, column=3))
    if second_boss:
        if act != "glory":
            raise ValueError("Second boss belongs to Glory.")
        nodes.append(MapNode(prefix + ".boss2", "boss", (), row=rows + 2, column=3))
    entries = tuple(identity(p) for p in sorted(starts))
    if ancient is not None:
        if ancient not in ancients_for(act):
            raise ValueError('Unsupported generated Ancient room.')
        root = prefix + '.ancient'
        nodes.insert(0, MapNode(root, 'event', entries, event_id=ancient, row=0, column=3))
        entries = (root,)
    return MapGraph(tuple(nodes), entries[0], entries, profile)


def validate_generated_map(graph):
    """Reject malformed private layouts without regenerating or consuming RNG."""
    if graph.generation not in (*BASE_PROFILES, *PRUNED_PROFILES):
        raise ValueError("Unsupported generated map profile.")
    hive = graph.generation in (HIVE_PROFILE, HIVE_BASE_PROFILE, SPOILS_PROFILE)
    glory = graph.generation in (GLORY_PROFILE, GLORY_BASE_PROFILE)
    rows, prefix = (13, 'act3') if glory else (14, 'act2') if hive else (15, 'act1')
    root = next((n for n in graph.nodes if n.row == 0), None)
    if root is not None and (not (hive or glory) or root.node_id != prefix + '.ancient' or root.kind != 'event'
            or root.column != 3 or root.event_id not in ancients_for('glory' if glory else 'hive')):
        raise ValueError('Invalid generated Ancient root.')
    double = any(n.node_id == prefix + ".boss2" for n in graph.nodes)
    if double and not glory:
        raise ValueError("Second boss belongs to Glory.")
    points = {}
    for node in graph.nodes:
        if (type(node.row) is not int or not (0 if root else 1) <= node.row <= rows + 1 + int(double) or type(node.column) is not int
                or not 0 <= node.column < WIDTH or (node.row, node.column) in points):
            raise ValueError("Invalid generated map coordinates.")
        points[node.row, node.column] = node
        expected_id = prefix + ".boss2" if node.row == rows + 2 else prefix + ".ancient" if node.row == 0 else prefix + ".boss" if node.row == rows + 1 else f"{prefix}.{node.row}.{node.column}"
        if node.node_id != expected_id:
            raise ValueError("Generated map identity differs from its coordinates.")
        if node is root:
            continue
        extra_kind = "event" if graph.generation in BASE_PROFILES else "unknown"
        if node.kind not in ("combat", "elite", "boss", "rest", "treasure", "shop", extra_kind) or node.encounter_id is not None:
            raise ValueError("Generated maps use run-owned encounter queues.")
        if node.kind == "event" and node.event_id is None:
            raise ValueError("Restricted generated event requires its definition.")
        if node.kind == "unknown" and node.event_id is not None:
            raise ValueError("Unknown map points cannot contain an eventual event.")
        required = {1: "combat", rows - 6: "treasure", rows: "rest", rows + 1: "boss", rows + 2: "boss"}.get(node.row)
        if required and node.kind != required or not required and node.kind in ("treasure", "boss"):
            raise ValueError("Invalid fixed map row.")
        if node.row < 6 and node.kind in ("rest", "elite") or node.row in (rows - 2, rows - 1) and node.kind == "rest":
            raise ValueError("Invalid early/late room placement.")
    if graph.generation == SPOILS_PROFILE and [(n.row, n.column) for n in graph.nodes if n.kind == "treasure"] != [(8, 3)]:
        raise ValueError("Spoils map requires its central treasure.")
    bosses = [n for n in graph.nodes if n.kind == "boss"]
    if (len(bosses) != 1 + int(double) or bosses[-1].next_node_ids or any(n.column != 3 for n in bosses)
            or double and bosses[0].next_node_ids != (prefix + ".boss2",)):
        raise ValueError("Invalid generated boss sequence.")
    entries = tuple(n.node_id for n in sorted(graph.nodes, key=lambda n: n.column) if n.row == 1)
    if (root.next_node_ids if root else graph.entry_node_ids) != entries or len(entries) < (2 if graph.generation in BASE_PROFILES else 1):
        raise ValueError("Generated map entrances differ from its first row.")
    if root and graph.entry_node_ids != (root.node_id,):
        raise ValueError('Ancient must precede ordinary map entrances.')
    for node in graph.nodes:
        if node is root:
            continue
        if node.row < rows + 1 and not node.next_node_ids:
            raise ValueError("Generated path ends before its boss.")
        if node.row not in (1, rows - 6, rows, rows + 1) and node.kind in ("rest", "elite", "shop", "event", "unknown"):
            siblings = {child for parent in graph.nodes if node.node_id in parent.next_node_ids
                        for child in parent.next_node_ids} - {node.node_id}
            if any(graph.node(sibling).kind == node.kind for sibling in siblings):
                raise ValueError("Sibling choices duplicate a restricted room type.")
        for target_id in node.next_node_ids:
            target = graph.node(target_id)
            if target.row != node.row + 1 or node.row < rows and abs(target.column - node.column) > 1:
                raise ValueError("Invalid generated map edge.")
            if node.kind == target.kind and node.kind in ("rest", "elite", "shop", "treasure"):
                raise ValueError("Consecutive restricted room types.")
            opposite = points.get((node.row, target.column))
            if node.row < rows and node.column != target.column and opposite and any(
                    graph.node(c).column == node.column for c in opposite.next_node_ids):
                raise ValueError("Generated paths cross.")
