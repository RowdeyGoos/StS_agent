"""Transfer an event into ordinary combat/rewards, retaining its own history."""

from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.events.catalog import EVENTS
from game.headless.events.combat import EventCombatRecord, EventCombatRequest


def start(engine, request):
    from game.headless.run.state import RunPhase
    from game.headless.run.events import validate_event
    state, pending = engine.state, engine.state.pending
    if (not isinstance(request, EventCombatRequest) or state.phase is not RunPhase.ROOM
            or pending is None or pending.get("kind") != "scripted_event"
            or state.config is None):
        raise ValueError("Event combat requires an owned event and declared reward pools.")
    validate_event(state, engine.graph, cards=engine.cards)
    definition = EVENTS[pending["definition_id"]]
    encounter = ENCOUNTERS.get(request.encounter_id)
    if (pending["stage"] != "fight" or getattr(definition, "combat_encounter_id", None) != request.encounter_id
            or encounter is None or encounter.event_id != definition.definition_id):
        raise ValueError("Event combat does not match its content definition.")
    # Construction uses isolated RNG; no event, navigation or history changes on failure.
    rng, combat = engine._prepare_combat(encounter_factory=encounter)
    record = EventCombatRecord(pending["event_instance_id"], definition.definition_id,
                               state.current_node_id, request.encounter_id, state.combats_completed + 1)
    state.rng, state.pending, state.phase = rng, None, RunPhase.COMBAT
    state.active_encounter_id = request.encounter_id
    state.event_combats.append(record)
    engine.combat = combat
    engine.sync_combat_loot()
    if combat.done:
        engine.finish_combat()
    return combat


def finish(state, encounter_id, *, won):
    if not state.event_combats:
        return
    record = state.event_combats[-1]
    if record.outcome is None:
        if record.encounter_id != encounter_id or record.combat_number != state.combats_completed:
            raise ValueError("Finished combat differs from its event owner.")
        record.outcome = "victory" if won else "defeat"


def leave_rewards(state, encounter_id):
    if state.event_combats:
        record = state.event_combats[-1]
        if record.outcome == "victory" and not record.rewards_left:
            if record.encounter_id != encounter_id:
                raise ValueError("Rewards differ from their event combat.")
            record.rewards_left = True


def validate(state, graph):
    from game.headless.run.state import RunPhase
    from game.headless.run.unknown_rooms import room_node
    if not isinstance(state.event_combats, list) or state.event_combats and state.config is None:
        raise ValueError("Invalid event combat history.")
    previous_number, previous_event, previous_node = 0, -1, -1
    active = None
    for index, record in enumerate(state.event_combats):
        if (not isinstance(record, EventCombatRecord)
                or type(record.event_instance_id) is not int or not previous_event < record.event_instance_id < state.next_event_id
                or type(record.combat_number) is not int or not previous_number < record.combat_number <= state.combats_completed + (state.phase is RunPhase.COMBAT)
                or type(record.rewards_left) is not bool
                or record.outcome not in (None, "victory", "defeat")
                or not isinstance(record.definition_id, str) or record.definition_id not in EVENTS
                or not isinstance(record.encounter_id, str) or record.encounter_id not in ENCOUNTERS
                or getattr(EVENTS[record.definition_id], "combat_encounter_id", None) != record.encounter_id
                or ENCOUNTERS[record.encounter_id].event_id != record.definition_id):
            raise ValueError("Invalid event combat record.")
        previous_number, previous_event = record.combat_number, record.event_instance_id
        if graph is None:
            if record.node_id is not None:
                raise ValueError("Event combat node has no map.")
        else:
            if not isinstance(record.node_id, str) or record.node_id not in state.visited_nodes:
                raise ValueError("Event combat requires a visited event node.")
            node = room_node(state, graph, record.node_id)
            position = state.visited_nodes.index(record.node_id)
            if node.kind != "event" or node.event_id != record.definition_id or position <= previous_node:
                raise ValueError("Event combat differs from its map origin.")
            previous_node = position
        if record.rewards_left:
            if record.outcome != "victory" or record.combat_number > state.combats_completed:
                raise ValueError("Only completed victory rewards can be left.")
            continue
        active = record
        if index != len(state.event_combats)-1 or record.node_id != state.current_node_id:
            raise ValueError("Unfinished event combat must own the current room.")
        if record.outcome is None:
            if (state.phase is not RunPhase.COMBAT or state.active_encounter_id != record.encounter_id
                    or record.combat_number != state.combats_completed + 1 or state.pending is not None):
                raise ValueError("Event combat has no matching active fight.")
        elif record.outcome == "victory":
            if (state.phase is not RunPhase.REWARD or record.combat_number != state.combats_completed
                    or state.pending is None or state.pending.get("encounter_id") != record.encounter_id
                    or state.pending.get("combat_reward") is not True):
                raise ValueError("Event victory has no matching rewards.")
        elif state.phase is not RunPhase.DEFEAT or record.combat_number != state.combats_completed or state.pending is not None:
            raise ValueError("Event defeat has no terminal owner.")
    if (state.pending is not None and state.pending.get("kind") == "scripted_event"
            and previous_event >= state.pending.get("event_instance_id", -1)):
        raise ValueError("Prior event combat collides with the current event identity.")
    encounter_id = state.active_encounter_id
    if state.phase is RunPhase.REWARD and state.pending is not None:
        encounter_id = state.pending.get("encounter_id")
    if encounter_id in ENCOUNTERS and ENCOUNTERS[encounter_id].event_id is not None:
        if active is None or active.encounter_id != encounter_id:
            raise ValueError("Event encounter has no event owner.")


def encounter_at_current_room(state):
    """Resolve the active/reward child without consuming a map encounter queue."""
    if state.event_combats:
        record = state.event_combats[-1]
        if not record.rewards_left and record.node_id == state.current_node_id:
            return record.encounter_id
    return None
