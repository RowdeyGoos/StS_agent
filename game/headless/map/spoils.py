"""Spoils Map's native hourglass paths; point assignment is shared with standard maps."""


def hourglass_paths(rng, stream, rows, points):
    edges, starts = {}, []
    treasure = rows - 6
    def clamp(value, low=0, high=6): return min(high, max(low, value))
    def crossing(current, col):
        return col != current[1] and (current[0] + 1, current[1]) in edges.get((current[0], col), ())
    for path in range(7):
        current = (1, rng.randint(stream, 0, 6))
        while path == 1 and current in starts:
            current = (1, rng.randint(stream, 0, 6))
        if current not in starts: starts.append(current)
        edges.setdefault(current, points())
        for row in range(2, rows + 1):
            width = min(3, abs(row - treasure), min(3, max(0, rows - row) + 1))
            low, high = 3 - width, 3 + width
            distance = treasure - current[0]
            offsets = [-1, 0, 1]
            if 0 < distance <= 3:
                direction = (3 > current[1]) - (3 < current[1])
                offsets = [direction, 0, -direction] if direction else [0, -1, 1]
            else:
                rng.shuffle(stream, offsets)
            target = None
            for offset in offsets:
                col = clamp(current[1] + offset)
                candidate = (row, col)
                if not low <= col <= high or crossing(current, col): continue
                parent_count = sum(candidate in children for children in edges.values())
                if (candidate in edges[current] or parent_count < 3) and (len(edges[current]) < 3 or candidate in edges[current]):
                    target = candidate
                    break
            if target is None:
                col = clamp(3, low, high)
                if abs(col - current[1]) > 1:
                    col = clamp(current[1] + ((col > current[1]) - (col < current[1])), low, high)
                if crossing(current, col): col = clamp(current[1], low, high)
                if abs(col - current[1]) > 1: raise RuntimeError('Invalid Spoils map continuation.')
                target = (row, col)
            edges[current].add(target)
            edges.setdefault(target, points())
            current = target
    return edges, starts
