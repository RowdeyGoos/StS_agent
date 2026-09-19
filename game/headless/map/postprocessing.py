"""Deterministic native map coordinate layout after topology/pruning.

Node identities remain internal until publication. Root and boss are outside the
native grid; their coordinates stay fixed while connected grid points move.
"""


def reposition(edges, parents, kinds):
    locations = {point: point for point in edges}
    grid = {point: point for point in edges if kinds[point] not in ('ancient', 'boss')}
    rows = max((row for row, _ in grid), default=0)

    def move(point, column):
        row, old = locations[point]
        del grid[(row, old)]
        grid[(row, column)] = point
        locations[point] = (row, column)

    # CenterGrid shifts only when two complete edge columns are empty on one side.
    columns = {col for row, col in grid}
    left = not columns.intersection((0, 1))
    right = not columns.intersection((5, 6))
    shift = -1 if left and not right else 1 if right and not left else 0
    if shift:
        for point in sorted(grid.values(), key=lambda p: (p[0], -p[1] if shift > 0 else p[1])):
            move(point, locations[point][1] + shift)

    for row in range(1, rows + 1):
        row_nodes = [grid[(row, col)] for col in range(7) if (row, col) in grid]
        changed = True
        while changed:
            changed = False
            for point in row_nodes:
                column = locations[point][1]
                allowed = set(range(7))
                for neighbor in (*parents[point], *edges[point]):
                    other = locations[neighbor][1]
                    allowed.intersection_update((other - 1, other, other + 1))

                def gap(candidate):
                    return min(
                        (abs(candidate - locations[n][1]) for n in row_nodes if n != point),
                        default=2147483647,
                    )

                best, best_gap = column, gap(column)
                for candidate in sorted(allowed):
                    if candidate != column and (row, candidate) not in grid and gap(candidate) > best_gap:
                        best, best_gap = candidate, gap(candidate)
                if best != column:
                    move(point, best)
                    changed = True

    for row in range(1, rows + 1):
        for column in range(7):
            point = grid.get((row, column))
            if point is None or len(parents[point]) != 1 or len(edges[point]) != 1:
                continue
            before = locations[next(iter(parents[point]))][1]
            after = locations[next(iter(edges[point]))][1]
            target = (
                column + 1
                if column < min(before, after)
                else column - 1 if column > max(before, after) else column
            )
            if 0 <= target < 7 and target != column and (row, target) not in grid:
                move(point, target)

    adjacency = type(next(iter(edges.values())))
    return (
        {locations[p]: adjacency(locations[c] for c in children) for p, children in edges.items()},
        {locations[p]: adjacency(locations[a] for a in ancestors) for p, ancestors in parents.items()},
        {locations[p]: kind for p, kind in kinds.items()},
    )
