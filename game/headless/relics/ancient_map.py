"""Ancient map modifications and their owned combat-entry context."""

from game.headless.relics.run_rules import owned


def update(engine):
    state, graph = engine.state, engine.graph
    if graph is None:
        return
    compass = owned(state, 'golden_compass')
    if compass and 'act' not in compass.data:
        from game.headless.map.golden_path import generate
        if state.visited_nodes:
            raise ValueError('Golden Compass must be acquired at the Ancient before entering this act map.')
        engine.graph = graph = generate()
        compass.data['act'] = 1
    coat = owned(state, 'fur_coat')
    if coat:
        eligible = sorted([n for n in graph.nodes if n.kind in ('combat','elite')], key=lambda n: (n.column if n.column is not None else -1, n.row if n.row is not None else -1))
        coordinates = [[n.row, n.column] for n in eligible]
        if 'coordinates' not in coat.data or any(c not in coordinates for c in coat.data['coordinates']):
            if getattr(state.rng, 'native', False):
                from game.headless.core.native_rng import NativeRng, deterministic_hash
                rng = NativeRng((state.rng.root_seed + deterministic_hash('FUR_COAT')) & 0xffffffff)
                rng.shuffle(eligible)
            else:
                from game.headless.core.rng import GameRandomService
                GameRandomService(state.seed).shuffle('relic:FUR_COAT', eligible)
            coat.data.update(act=1, coordinates=[[n.row,n.column] for n in eligible[:7]])


def coat_active(engine):
    coat = owned(engine.state, 'fur_coat')
    if coat is None or engine.graph is None or engine.state.current_node_id is None:
        return False
    node = engine.graph.node(engine.state.current_node_id)
    return [node.row,node.column] in coat.data.get('coordinates', [])


def validate(state, graph):
    compass = owned(state, 'golden_compass')
    from game.headless.map.golden_path import PROFILE
    if graph and graph.generation == PROFILE and (compass is None or compass.data.get('act') != 1):
        raise ValueError('Golden map has no Ancient owner.')
    if compass and compass.data.get('act') == 1 and (graph is None or graph.generation != PROFILE):
        raise ValueError('Golden Compass requires its transformed map.')
    coat = owned(state, 'fur_coat')
    if coat and graph:
        eligible = [[n.row,n.column] for n in graph.nodes if n.kind in ('combat','elite')]
        marked = coat.data.get('coordinates')
        if coat.data.get('act') != 1 or not isinstance(marked,list) or len(marked) != min(7,len(eligible)) or any(c not in eligible for c in marked):
            raise ValueError('Fur Coat marks differ from its map.')
