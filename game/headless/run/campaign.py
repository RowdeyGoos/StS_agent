"""Owned act journeys and the explicit transition into the next generated region."""
from copy import copy, deepcopy
from dataclasses import dataclass, replace

from game.headless.map.graph import MapGraph
from game.headless.encounters.progression import EncounterProgression, native_ids
from game.headless.events.progression import EventProgression
from game.headless.run.unknown_rooms import UnknownRooms, room_node


@dataclass
class CompletedAct:
    act: str
    graph: MapGraph
    visited_nodes: list[str]
    encounter_progression: EncounterProgression
    event_progression: EventProgression
    unknown_rooms: UnknownRooms
    event_pool: tuple[str, ...]


def view(state, record, index):
    """Read historical navigation through the same queue and room validators."""
    result = copy(state)
    result.config = replace(state.config, act=record.act, event_pool=record.event_pool)
    result.act_index = index
    result.completed_acts = state.completed_acts[:index]
    for key in ('visited_nodes', 'encounter_progression', 'event_progression', 'unknown_rooms'):
        setattr(result, key, getattr(record, key))
    result.current_node_id = record.visited_nodes[-1] if record.visited_nodes else None
    return result


def journeys(state, graph):
    return [(view(state, record, i), record.graph) for i, record in enumerate(state.completed_acts)] + [(state, graph)]


def validate(state):
    if not isinstance(state.completed_acts, list):
        raise ValueError('Invalid completed act history.')
    config = state.config
    if state.completed_acts and (config is None or not config.campaign):
        raise ValueError('Completed journeys require a declared campaign.')
    if config is None or not config.campaign:
        return
    if state.act_index != len(state.completed_acts) or state.act_index >= len(config.campaign) or config.act != config.campaign[state.act_index]:
        raise ValueError('Current act differs from completed campaign history.')
    for i, record in enumerate(state.completed_acts):
        if not isinstance(record, CompletedAct) or record.act != config.campaign[i] or not isinstance(record.graph, MapGraph):
            raise ValueError('Invalid completed act owner.')
        old = view(state, record, i)
        from game.headless.map.standard import profile_for
        from game.headless.map.golden_path import PROFILE as GOLDEN
        if record.graph.generation not in (profile_for(record.act), GOLDEN):
            raise ValueError('Completed act map differs from its region.')
        if not isinstance(record.visited_nodes, list) or not record.visited_nodes or len(set(record.visited_nodes)) != len(record.visited_nodes):
            raise ValueError('Invalid completed act path.')
        if not isinstance(record.encounter_progression, EncounterProgression) or record.encounter_progression.act != record.act:
            raise ValueError('Invalid completed encounter queues.')
        record.encounter_progression.validate(record.graph, record.visited_nodes,
            room_kinds={n: room_node(old, record.graph, n).kind for n in record.visited_nodes})
        last = room_node(old, record.graph, record.visited_nodes[-1])
        if last.kind != 'boss' or record.encounter_progression.assignments.get(last.node_id) != record.encounter_progression.boss:
            raise ValueError('Completed act requires its visited, assigned boss.')
        if not isinstance(record.unknown_rooms, UnknownRooms) or not isinstance(record.event_progression, EventProgression):
            raise ValueError('Completed act is missing room history.')
        record.unknown_rooms.validate(old, record.graph)
        record.event_progression.validate(old, record.graph)


def can_continue(engine):
    from game.headless.run.state import RunPhase
    s = engine.state
    return (s.phase is RunPhase.ACT_COMPLETE and s.config is not None and bool(s.config.campaign)
            and s.act_index + 1 < len(s.config.campaign) and not s.relic_work
            and s.pending is None and s.hp > 0 and engine.combat is None
            and engine.graph is not None and s.encounter_progression is not None)


def advance(engine):
    from game.headless.run.state import RunPhase
    from game.headless.map.standard import generate_map
    from game.headless.events.progression import HIVE_PROFILE
    from game.headless.generation.room_pools import REGION_POOLS, SHARED_EVENTS
    if not can_continue(engine):
        raise ValueError('No completed generated act is ready to continue.')
    state, graph = engine.state, engine.graph
    # Construction uses an independent owner; a failed map/queue build changes nothing.
    trial = deepcopy(state)
    trial.completed_acts.append(CompletedAct(state.config.act, graph, list(state.visited_nodes),
        deepcopy(state.encounter_progression), deepcopy(state.event_progression), deepcopy(state.unknown_rooms), state.config.event_pool))
    trial.act_index += 1
    act = trial.config.campaign[trial.act_index]
    trial.config = replace(trial.config, act=act, event_pool=(*REGION_POOLS[act][3], *SHARED_EVENTS))
    trial.current_node_id, trial.visited_nodes = None, []
    trial.phase, trial.act_completion, trial.pending = RunPhase.ROUTE, None, None
    trial.unknown_rooms = UnknownRooms()
    if trial.initialization is not None:
        initial = trial.initialization['acts'][trial.act_index]
        ids = native_ids(act)
        trial.encounter_progression = EncounterProgression([ids[n] for n in initial['normal']],
            [ids[n] for n in initial['elites']], ids[initial['boss']], act=act)
        trial.event_progression = EventProgression(list(initial['events']), profile=HIVE_PROFILE)
        ancient = initial['ancient']
    else:
        trial.encounter_progression = EncounterProgression.generate(trial.rng, act=act)
        trial.event_progression = EventProgression.generate(trial.rng, trial.config.event_pool, act=act)
        ancient = trial.rng.choice('act2.ancient', REGION_POOLS[act][4])
    next_graph = generate_map(trial.rng, event_pool=trial.config.event_pool, act=act, ancient=ancient)
    from game.headless.run import spoils_map
    next_graph = spoils_map.generate(trial, next_graph)
    spoils_map.validate(trial, next_graph)
    trial.validate()
    engine.state, engine.graph = trial, next_graph
    return next_graph
