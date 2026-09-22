"""Driftwood and Pael's Wing decisions on actual card reward objects."""
from game.headless.characters import character, potion_pool as character_potions

from game.headless.relics.run_rules import has, owned, counter
from game.headless.run.actions import RerollCardReward, SacrificeCardReward


def contexts(state):
    if state.relic_work:
        work = state.relic_work[0]
        source = next(r for r in state.relics if r.instance_id == work['source'])
        if work['kind'] == 'card_reward' and source.definition_id in ('orrery','lost_coffer','glass_eye','kaleidoscope','dream_catcher'):
            return [(-1, 'relic', work)]
        return []
    pending = state.pending or {}
    if pending.get('kind') == 'reward':
        result = [] if pending['card_resolved'] else [(-1, 'main', pending)]
        return result + [(i, 'extra', r) for i,r in enumerate(pending.get('extra_rewards', [])) if r['kind'] == 'card' and not r['resolved']]
    if pending.get('kind') == 'scripted_event' and pending.get('stage') == 'event_rewards':
        return [(i,'batch',r) for i,r in enumerate(pending['data']['active']['rewards']) if r['kind']=='card' and not r['resolved']]
    if pending.get('kind') == 'scripted_event' and pending.get('stage') == 'card_rewards':
        data = pending.get('data', {})
        active = data.get('active', {})
        if active.get('optional') and not active.get('selected'):
            return [(-1, 'event', active)]
    return []


def actions(state):
    result = []
    for index, kind, reward in contexts(state):
        if has(state, 'driftwood') and not reward.get('rerolled'):
            result.append(RerollCardReward(index))
        if has(state, 'paels_wing'):
            result.append(SacrificeCardReward(index))
    return result


def apply(state, cards, action):
    from copy import deepcopy
    before = deepcopy(state)
    try:
        _apply(state, cards, action)
    except Exception:
        state.__dict__.clear()
        state.__dict__.update(before.__dict__)
        raise


def _apply(state, cards, action):
    if action not in actions(state):
        raise ValueError('Card reward alternative is unavailable.')
    _, kind, reward = next(c for c in contexts(state) if c[0] == action.index)
    if isinstance(action, RerollCardReward):
        reroll(state, cards, kind, reward)
        reward['rerolled'] = True
        return
    # Complete the reward before obtaining a relic that can open nested choices.
    if kind == 'main':
        reward['card_resolved'] = True
    elif kind in ('extra','batch'):
        reward['resolved'] = True
        if kind == 'batch' and all(r['resolved'] for r in state.pending['data']['active']['rewards']):
            from game.headless.events.steps import complete
            from game.headless.events.catalog import EVENTS
            data=state.pending['data']
            complete(data,EVENTS[state.pending['definition_id']].plan(data)[data['cursor']],data['active']['rewards'])
    elif kind == 'relic':
        state.relic_work.pop(0)
    else:
        from game.headless.events.steps import complete
        from game.headless.events.catalog import EVENTS
        data = state.pending['data']
        complete(data, EVENTS[state.pending['definition_id']].plan(data)[data['cursor']], [])
    wing = owned(state, 'paels_wing')
    wing = counter(state, wing, wing.counter + 1)
    if wing.counter % 2 == 0:
        from game.headless.generation.relics import pull
        from game.headless.relics.base import RELICS
        from game.headless.run.inventory import add_relic
        if getattr(state.rng, 'native', False):
            name = pull(state)
        else:
            pool = [n for n,d in RELICS.items() if d.rarity in ('common','uncommon','rare') and not any(r.definition_id == n for r in state.relics)]
            name = state.rng.choice('relic.reward', pool) if pool else 'circlet'
        add_relic(state, name, cards=cards, prioritize_pickup=True)


def reroll(state, cards, kind, reward):
    from game.headless.relics.rewards import extend_pool, decorate, combat_modifiers
    from game.headless.cards.pools import REWARD_CARDS
    room_kind, mode, uniform, upgrade, count = 'combat', 'base', False, True, 3
    rarity, family, card_kind, upgrade_all = None, character(state), None, False
    stream='rewards'
    no_pool_changes=False
    pool = list(state.config.reward_cards if state.config else REWARD_CARDS)
    if kind in ('main','extra'):
        from game.headless.encounters.catalog import ENCOUNTERS
        encounter = state.pending.get('encounter_id')
        room_kind = ENCOUNTERS[encounter].room_kind if encounter else 'combat'
        mode = 'changing'
        if kind == 'extra':
            source = next((r for r in state.relics if r.instance_id == reward['source']), None)
            if source and source.definition_id == 'white_star':
                rarity, room_kind = 'rare', 'boss'
        if room_kind == 'boss' and state.config:
            pool = list(state.config.boss_reward_cards)
    elif kind == 'batch':
        from game.headless.events.catalog import EVENTS
        data=state.pending['data']
        index=data['active']['rewards'].index(reward)
        descriptor=EVENTS[state.pending['definition_id']].plan(data)[data['cursor']][1][index]
        _,family,rarity,count,stream,*extra=descriptor
        flags=extra[0] if extra else {}
        rarity=None if rarity=='any' else rarity
        uniform,upgrade=rarity is not None,flags.get('upgrade',True)
        no_pool_changes=not flags.get('pool_changes',True)
    elif kind == 'relic':
        source = next(r for r in state.relics if r.instance_id == reward['source'])
        if source.definition_id == 'kaleidoscope':
            raise ValueError('Pinned Kaleidoscope has an empty native reroll pool.')
        if source.definition_id in ('glass_eye', 'hefty_tablet'):
            rarity = cards.definition(reward['offers'][0]['definition_id']).rarity
            uniform, upgrade = True, False
    else:
        from game.headless.events.catalog import EVENTS
        data = state.pending['data']
        op = EVENTS[state.pending['definition_id']].plan(data)[data['cursor']]
        _, family, rarity, card_kind, count, _, _, upgrade_all = op
        rarity = None if rarity == 'any' else rarity
        uniform, upgrade = rarity is not None, False
    if kind in ('relic','event','batch') or rarity:
        pool = [d.definition_id for d in cards.definitions if d.pool == family and d.rarity in ((rarity,) if rarity else ('common','uncommon','rare')) and (card_kind in (None,'any') or d.levels[0].kind == card_kind)]
    pool = extend_pool(state, cards, pool, card_kind=card_kind, no_pool_changes=no_pool_changes)
    upgraded = []
    if getattr(state.rng,'native',False):
        from game.headless.generation.odds import card_offers
        offers, upgraded = card_offers(state, cards, pool, count, kind=room_kind, mode=mode, uniform=uniform, upgrade_roll=upgrade,stream=stream)
    else:
        state.rng.shuffle('reward_offer', pool)
        offers = pool[:count]
    modifiers = (combat_modifiers(state, cards, offers, pool, kind=room_kind, upgraded=upgraded, upgrade_all=upgrade_all)
                 if kind in ("main", "extra") else decorate(state, cards, offers, upgraded=upgraded, upgrade_all=upgrade_all))
    if kind == 'relic':
        reward['offers'] = [dict(definition_id=n, **modifiers[n]) for n in offers]
    else:
        reward['offers'] = offers
        reward['card_modifiers' if kind == 'main' else 'modifiers'] = modifiers


def validate_marker(state, reward):
    if 'rerolled' in reward and (reward['rerolled'] is not True or not any(r.definition_id == 'driftwood' for r in state.relics)):
        raise ValueError('Unowned card reward reroll.')
