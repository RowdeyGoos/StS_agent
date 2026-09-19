"""Native duplicate-segment pruning and special-room count repair.

Operates on the generator's owned coordinate graph, before immutable publication.
The temporary Ancient/root point participates in comparison, not game choices.
"""

from types import MappingProxyType

TYPE_NUMBER = MappingProxyType({"unknown": 1, "shop": 2, "treasure": 3, "rest": 4,
                                "combat": 5, "elite": 6, "boss": 7, "ancient": 8})


def matching_segments(edges, parents, kinds, root, *, native_order=False):
    def paths(point):
        if kinds[point] == "boss":
            yield (point,)
        else:
            for child in (edges[point] if native_order else sorted(edges[point])):
                for suffix in paths(child):
                    yield (point, *suffix)

    groups = {}
    for path in paths(root):
        for i, start in enumerate(path[:-1]):
            if len(edges[start]) <= 1 and start[0] != 0:
                continue
            for j in range(i + 2, len(path)):
                end = path[j]
                if len(parents[end]) < 2:
                    continue
                segment = path[i:j + 1]
                prefix = "0" if start[0] == 0 else f"{start[1]},{start[0]}"
                key = f"{prefix}-{end[1]},{end[0]}-" + ",".join(str(TYPE_NUMBER[kinds[p]]) for p in segment)
                group = groups.setdefault(key, [])
                # Endpoints may coincide; sharing an interior point disqualifies
                # the alternative. Identical segments from longer paths dedupe here.
                if not any(any(a == b for a, b in zip(segment[1:-1], prior[1:-1])) for prior in group):
                    group.append(segment)
    return [group for key, group in sorted(groups.items()) if len(group) > 1]


def _unlink(edges, parents, parent, child):
    edges[parent].discard(child)
    parents[child].discard(parent)


def _prune_segment(edges, parents, kinds, segment):
    removed = False
    for index, point in enumerate(segment[:-1]):
        if point not in edges:
            return True
        if len(edges[point]) > 1 or len(parents[point]) > 1:
            continue
        if any(len(edges[p]) == 1 and kinds[p] not in ("ancient", "boss") for p in parents[point]):
            continue
        if any(len(edges.get(p, ())) > 1 and len(parents.get(p, ())) == 1 for p in segment[index:]):
            continue
        if len(parents[segment[-1]]) == 1:
            return False
        if any(c not in segment and len(parents[c]) == 1 for c in edges[point]):
            continue
        for child in tuple(edges[point]):
            _unlink(edges, parents, point, child)
        for parent in tuple(parents[point]):
            _unlink(edges, parents, parent, point)
        del edges[point], parents[point], kinds[point]
        removed = True
    return removed


def _break_segment(edges, parents, segment):
    changed = False
    for point, child in zip(segment, segment[1:]):
        if len(edges.get(point, ())) >= 2 and child in edges[point] and len(parents[child]) != 1:
            _unlink(edges, parents, point, child)
            changed = True
    return changed


def prune_duplicates(edges, parents, kinds, root, rng, *, stream="act1.map"):
    for _ in range(51):
        changed = False
        for group in matching_segments(edges, parents, kinds, root, native_order=getattr(rng, "native", False)):
            rng.shuffle(stream, group)
            removed_count = 0
            for segment in group:
                if removed_count == len(group) - 1:
                    break
                removed_count += _prune_segment(edges, parents, kinds, segment)
            if removed_count or any(_break_segment(edges, parents, segment) for segment in group):
                changed = True
                break
        if not changed:
            return
    raise RuntimeError("Map pruning exceeded the native 50-change bound.")


def prune_and_repair(edges, parents, kinds, root, rng, counts, valid, *, stream="act1.map"):
    """At most three prune/repair rounds, matching the pinned native boundary."""
    for _ in range(3):
        prune_duplicates(edges, parents, kinds, root, rng, stream=stream)
        repaired = False
        for kind in ("shop", "elite", "rest", "unknown"):
            missing = counts[kind] - sum(k == kind for k in kinds.values())
            if missing <= 0:
                continue
            candidates = sorted((p for p, k in kinds.items() if k == "combat" and p[0] != 1), key=(lambda p:(p[1],p[0])) if getattr(rng,"native",False) else None)
            rng.shuffle(stream, candidates)
            for point in candidates:
                if not missing:
                    break
                if valid(kind, point):
                    kinds[point] = kind
                    missing -= 1
                    repaired = True
        if not repaired:
            return
