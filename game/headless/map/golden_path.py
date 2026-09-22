"""Pinned solo Golden Compass topology, with an explicit root in later acts."""

from game.headless.map.graph import MapGraph, MapNode

PROFILE = 'golden_path_solo_v1'
KINDS = ('combat','unknown','combat','rest','combat','rest','unknown','treasure',
         'unknown','treasure','unknown','shop','elite','rest','elite','rest','boss')


def nodes(prefix="act1"):
    return tuple(MapNode(prefix + '.boss' if row == 17 else f'{prefix}.{row}.3', kind,
                        () if row == 17 else (prefix + '.boss' if row == 16 else f'{prefix}.{row+1}.3',),
                        row=row, column=3) for row,kind in enumerate(KINDS, 1))


def generate(*, act_index=0, ancient=None):
    prefix = f'act{act_index + 1}'
    route = nodes(prefix)
    entries = (prefix + '.1.3',)
    if ancient is not None:
        root = MapNode(prefix + '.ancient', 'event', entries, event_id=ancient, row=0, column=3)
        route, entries = (root, *route), (root.node_id,)
    return MapGraph(route, entries[0], entries, PROFILE)


def validate(graph):
    prefix = graph.nodes[0].node_id.split('.')[0]
    if prefix not in ('act1', 'act2', 'act3'):
        raise ValueError('Invalid Golden Compass act.')
    root = next((n for n in graph.nodes if n.row == 0), None)
    expected = nodes(prefix)
    entries = (prefix + '.1.3',)
    if root:
        from game.headless.map.standard import ancients_for
        if (prefix not in ('act2', 'act3') or root != MapNode(prefix + '.ancient', 'event', entries,
                event_id=root.event_id, row=0, column=3) or root.event_id not in ancients_for('hive' if prefix == 'act2' else 'glory')):
            raise ValueError('Invalid Golden Compass Ancient.')
        expected, entries = (root, *expected), (root.node_id,)
    if graph.nodes != expected or graph.start_id != entries[0] or graph.entry_node_ids != entries:
        raise ValueError('Invalid Golden Compass map.')
