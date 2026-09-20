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
    if (pending["stage"] != "fight" or request.encounter_id not in (getattr(definition, "combat_encounter_id", None), *getattr(definition, "combat_encounter_ids", ()))
            or encounter is None or encounter.event_id != definition.definition_id):
        raise ValueError("Event combat does not match its content definition.")
    # Construction uses isolated RNG; no event, navigation or history changes on failure.
    rng, combat = engine._prepare_combat(encounter_factory=encounter)
    record = EventCombatRecord(pending["event_instance_id"], definition.definition_id,
                               state.current_node_id, request.encounter_id, state.combats_completed + 1)
    if hasattr(definition, "open_page"):
        from copy import deepcopy
        record.continuation = deepcopy(pending)
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


def validate(state, graph, *, cards=None):
    from game.headless.cards.catalog import DEFAULT_CARDS
    cards = cards or DEFAULT_CARDS
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
                or type(record.timed_out) is not bool or type(record.resumed) is not bool
                or record.timed_out and (record.definition_id != "battleworn_dummy" or record.outcome != "victory")
                or record.continuation is not None and record.resumed != record.rewards_left
                or record.resumed and (not record.rewards_left or record.outcome != "victory" or record.continuation is None)
                or record.outcome not in (None, "victory", "defeat")
                or not isinstance(record.definition_id, str) or record.definition_id not in EVENTS
                or not isinstance(record.encounter_id, str) or record.encounter_id not in ENCOUNTERS
                or record.encounter_id not in (getattr(EVENTS[record.definition_id], "combat_encounter_id", None), *getattr(EVENTS[record.definition_id], "combat_encounter_ids", ()))
                or ENCOUNTERS[record.encounter_id].event_id != record.definition_id):
            raise ValueError("Invalid event combat record.")
        validate_continuation(state, record, cards)
        previous_number, previous_event = record.combat_number, record.event_instance_id
        if graph is None:
            if record.node_id is not None:
                raise ValueError("Event combat node has no map.")
        else:
            from game.headless.run.campaign import journeys
            owners = journeys(state, graph)
            visited = [n for owner, _ in owners for n in owner.visited_nodes]
            if not isinstance(record.node_id, str) or record.node_id not in visited:
                raise ValueError("Event combat requires a visited event node.")
            owner, layout = next((o, g) for o, g in owners if record.node_id in o.visited_nodes)
            node = room_node(owner, layout, record.node_id)
            position = visited.index(record.node_id)
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
            and previous_event >= state.pending.get("event_instance_id", -1)
            and not (state.event_combats and state.event_combats[-1].continuation is not None and state.event_combats[-1].rewards_left and previous_event == state.pending.get("event_instance_id"))):
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


def resume(state, cards):
    if not state.event_combats:
        return False
    record = state.event_combats[-1]
    if record.continuation is None or record.outcome != 'victory' or record.resumed or record.combat_number != state.combats_completed or record.node_id != state.current_node_id:
        return False
    if record.definition_id != 'battleworn_dummy':
        record.rewards_left = True
        record.resumed = True
        return True
    from copy import deepcopy
    from game.headless.run.state import RunPhase
    from game.headless.events.steps import complete, drain
    from game.headless.events.checkpoint import refresh
    state.pending = deepcopy(record.continuation)
    state.phase = RunPhase.ROOM
    data = state.pending['data']
    operation = EVENTS[record.definition_id].plan(data)[data['cursor']]
    if operation != ['combat', record.encounter_id]:
        raise ValueError('Combat continuation differs from its event.')
    complete(data, operation, {'timed_out': record.timed_out})
    record.rewards_left = True
    record.resumed = True
    drain(state, cards)
    # Native Resume finishes the event and immediately grants its outcome;
    # the result description is not a second player decision.
    if state.pending and state.pending['stage'] == 'page':
        EVENTS[record.definition_id].choose(state, state.pending, 'proceed', cards=cards)
    refresh(state)
    return True


def validate_continuation(state, record, cards):
    definition = EVENTS[record.definition_id]
    if not hasattr(definition, 'open_page'):
        if record.continuation is not None or record.resumed or record.timed_out:
            raise ValueError('Unexpected event continuation.')
        return
    from copy import deepcopy
    from game.headless.cards.catalog import DEFAULT_CARDS
    from game.headless.core.snapshots import restore_card
    from game.headless.relics.base import RelicInstance
    from game.headless.potions.base import PotionInstance
    pending = record.continuation
    if (not isinstance(pending, dict) or pending.get('kind') != 'scripted_event'
            or pending.get('definition_id') != record.definition_id
            or pending.get('event_instance_id') != record.event_instance_id
            or pending.get('stage') != 'fight'):
        raise ValueError('Invalid suspended event combat owner.')
    data = pending.get('data')
    if not isinstance(data, dict) or not isinstance(data.get('checkpoint'), dict):
        raise ValueError('Missing suspended event state.')
    checkpoint = data['checkpoint']
    trial = deepcopy(state)
    for key in ('hp','max_hp','gold','next_card_id','next_item_id','potion_capacity','act_index','wongo_points','freed_repy'):
        setattr(trial, key, checkpoint[key])
    trial.deck = [restore_card(c, cards) for c in checkpoint['deck']]
    trial.relics = [RelicInstance(**r) for r in checkpoint['relics']]
    trial.potions = [PotionInstance(**p) if p else None for p in checkpoint['potions']]
    trial.relic_work = []
    definition.validate(pending, state=trial, cards=cards)
    if data['active'] != {'encounter_id': record.encounter_id}:
        raise ValueError('Suspended event requests a different encounter.')


def reward_descriptors(record):
    if record.continuation is None or record.definition_id == 'battleworn_dummy':
        return []
    data=record.continuation['data']
    ops=EVENTS[record.definition_id].plan(data)[data['cursor']+1:]
    result=[]
    for op in ops:
        if op[0]=='relic_reward': result.append(['relic',op[1],'rewards'])
        elif op[0]=='factory_potion': result.append(['potion','factory','rewards'])
        elif op[0]=='special_card_reward': result.append(['special_card',op[1]])
        else: raise ValueError('Unsupported post-combat event reward.')
    return result


def extra_rewards(state,cards,encounter_id):
    if not state.event_combats: return []
    record=state.event_combats[-1]
    if record.encounter_id != encounter_id or record.outcome != 'victory' or record.rewards_left: return []
    from game.headless.events.reward_batch import prepare
    return [dict(row, source=f'event:{record.event_instance_id}:{i}')
            for i,row in enumerate(prepare(state,cards,reward_descriptors(record)))]


def validate_extra_rewards(state,cards,rewards):
    rows=[r for r in rewards if isinstance(r,dict) and isinstance(r.get('source'),str) and r['source'].startswith('event:')]
    record=state.event_combats[-1] if state.event_combats else None
    descriptors=reward_descriptors(record) if record and record.outcome=='victory' and not record.rewards_left else []
    if [r['source'] for r in rows] != [f'event:{record.event_instance_id}:{i}' for i in range(len(descriptors))]:
        raise ValueError('Event reward sources differ from completed encounter.')
    from game.headless.events.reward_batch import validate
    validate([{k:v for k,v in r.items() if k!='source'} for r in rows],descriptors,cards)
