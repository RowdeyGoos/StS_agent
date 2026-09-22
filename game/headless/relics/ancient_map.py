"""Ancient map modifications and their owned combat-entry context."""

from game.headless.relics.run_rules import owned


def update(engine):
    state, graph = engine.state, engine.graph
    if graph is None:
        return
    compass = owned(state, 'golden_compass')
    if compass and 'act' not in compass.data:
        from game.headless.map.golden_path import generate
        if any(graph.node(n).row != 0 for n in state.visited_nodes):
            raise ValueError('Golden Compass must be acquired at the Ancient before entering this act map.')
        root = next((n for n in graph.nodes if n.row == 0), None)
        from dataclasses import replace
        engine.graph = graph = replace(generate(act_index=state.act_index, ancient=None if root is None else root.event_id), replaced_generation=graph.generation)
        compass.data['act'] = state.act_index + 1
        from game.headless.run.spoils_map import retarget
        retarget(state, graph)
    coat = owned(state, 'fur_coat')
    if coat and coat.data.get('act', state.act_index + 1) == state.act_index + 1:
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
            coat.data.update(act=state.act_index + 1, coordinates=[[n.row,n.column] for n in eligible[:7]])


def coat_active(engine):
    coat = owned(engine.state, 'fur_coat')
    if coat is None or engine.graph is None or engine.state.current_node_id is None:
        return False
    node = engine.graph.node(engine.state.current_node_id)
    return [node.row,node.column] in coat.data.get('coordinates', [])


def validate(state, graph):
    from game.headless.map.golden_path import PROFILE
    current_act = state.act_index + 1
    compass = owned(state, 'golden_compass')
    if graph and graph.generation == PROFILE and (compass is None or compass.data.get('act') != current_act):
        raise ValueError('Golden map has no Ancient owner.')
    if compass and compass.data.get('act') == current_act and (graph is None or graph.generation != PROFILE):
        raise ValueError('Golden Compass requires its transformed map.')
    for name in ('golden_compass', 'fur_coat'):
        relic = owned(state, name)
        if relic is None or graph is None:
            continue
        act = relic.data.get('act')
        if type(act) is not int or not 1 <= act <= current_act:
            raise ValueError('Ancient map relic has no act owner.')
        owner = graph if act == current_act else state.completed_acts[act - 1].graph if len(state.completed_acts) >= act else None
        if owner is None:
            raise ValueError('Ancient map relic has no historical map.')
        if name == 'golden_compass' and owner.generation != PROFILE:
            raise ValueError('Golden Compass history lost its transformed map.')
        if name == 'fur_coat':
            eligible = [[n.row, n.column] for n in owner.nodes if n.kind in ('combat', 'elite')]
            marked = relic.data.get('coordinates')
            if not isinstance(marked, list) or len(marked) != min(7, len(eligible)) or any(c not in eligible for c in marked):
                raise ValueError('Fur Coat marks differ from its owning map.')
