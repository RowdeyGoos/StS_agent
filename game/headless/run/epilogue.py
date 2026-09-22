"""The Architect is an owned post-map event, after final boss completion."""
from copy import deepcopy


def complete_campaign(state):
    return (state.config is not None and len(state.config.campaign) == 3
            and state.config.campaign[-1] == 'glory' and state.act_index == 2)


def validate(state):
    from game.headless.run.state import RunPhase
    identity = state.epilogue_event_id
    if identity is None:
        if state.config is not None and state.config.campaign and (state.phase is RunPhase.VICTORY
                or state.pending is not None and state.pending.get('definition_id') == 'the_architect'):
            raise ValueError('Campaign ending has no Architect owner.')
        return
    if (type(identity) is not int or identity < 0 or identity != state.next_event_id - 1
            or not complete_campaign(state) or len(state.completed_acts) != 2
            or state.act_completion is None or state.act_completion.act != 3
            or state.phase not in (RunPhase.ROOM, RunPhase.VICTORY)
            or state.active_encounter_id is not None or state.relic_work or state.hp <= 0):
        raise ValueError('Invalid Architect epilogue ownership.')
    if state.phase is RunPhase.ROOM:
        p = state.pending
        if (not isinstance(p, dict) or p.get('kind') != 'scripted_event'
                or p.get('definition_id') != 'the_architect' or p.get('event_instance_id') != identity):
            raise ValueError('Epilogue requires its Architect event.')
    elif state.pending is not None:
        raise ValueError('Completed epilogue cannot retain a pending event.')


def begin(engine):
    from game.headless.run.state import RunPhase
    from game.headless.run.events import begin as begin_event
    from game.headless.relics.run_rules import entered_room
    from game.headless.events.checkpoint import refresh
    trial = deepcopy(engine.state)
    if not complete_campaign(trial) or trial.phase is not RunPhase.ACT_COMPLETE or trial.epilogue_event_id is not None:
        raise ValueError('Final act is not ready for the Architect.')
    trial.epilogue_event_id = trial.next_event_id
    trial.phase = RunPhase.ROUTE
    begin_event(trial, 'the_architect', cards=engine.cards)
    if getattr(trial.rng, 'native', False):
        # EventRoom builds the Architect's fixed-HP presentation creature.
        # Native CreateCreature samples even a singleton HP range.
        trial.rng.choice('niche', (9999,))
    # Native EnterRoom invokes room-entry relics but never EnterMapCoord here:
    # no extra floor, map travel, encounter roll, or Ancient heal.
    entered_room(trial, 'event')
    refresh(trial)
    trial.validate()
    engine.state = trial
