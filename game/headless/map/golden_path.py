"""Pinned solo Golden Compass topology (Ancient root excluded from navigation)."""

from game.headless.map.graph import MapGraph, MapNode

PROFILE = 'golden_path_solo_v1'
KINDS = ('combat','unknown','combat','rest','combat','rest','unknown','treasure',
         'unknown','treasure','unknown','shop','elite','rest','elite','rest','boss')


def nodes():
    return tuple(MapNode('act1.boss' if row == 17 else f'act1.{row}.3', kind,
                        () if row == 17 else ('act1.boss' if row == 16 else f'act1.{row+1}.3',),
                        row=row, column=3) for row,kind in enumerate(KINDS, 1))


def generate():
    return MapGraph(nodes(), 'act1.1.3', ('act1.1.3',), PROFILE)


def validate(graph):
    if graph.nodes != nodes() or graph.start_id != 'act1.1.3' or graph.entry_node_ids != ('act1.1.3',):
        raise ValueError('Invalid Golden Compass map.')
