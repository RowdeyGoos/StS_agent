"""Automatic operations for the extended event roster."""
from game.headless.characters import character, potion_pool as character_potions
from copy import deepcopy
from game.headless.core.snapshots import card_record


def stable_shuffle(rng, stream, values):
    values.sort(key=lambda c: (c.definition.definition_id.upper(),c.upgrade_level))
    rng.shuffle(stream, values)
    return values


def pull_relic(state, *, rarity=None, merchant=False, stream="rewards", exclude=()):
    from game.headless.generation.relics import pull
    from game.headless.relics.base import RELICS
    from game.headless.relics.eligibility import SHOP_EXCLUDED
    pool = [n for n,d in RELICS.items() if n not in exclude and d.rarity in ('common','uncommon','rare') and (not merchant or n not in SHOP_EXCLUDED)]
    if state.relic_bags is not None:
        return pull(state,rarity=rarity,allowed=pool,stream=stream)
    pool = [n for n in pool if (rarity is None or RELICS[n].rarity == rarity) and n not in {r.definition_id for r in state.relics}]
    return state.rng.choice(stream,pool) if pool else 'circlet'


def execute(state, cards, operation):
    from game.headless.run.deck import add_card
    op,*args = operation
    if op == 'merchant_purchase':
        from game.headless.relics.run_rules import owned, counter
        bank = owned(state, 'maw_bank')
        if bank: counter(state,bank,1)
        return None
    if op == 'mad_science':
        card = cards.create('mad_science', instance_id=state.allocate_card_id())
        card.event_data = dict(kind=args[0], rider=args[1])
        state.deck.append(card)
        from game.headless.relics.run_rules import card_added
        card_added(state, card)
        return card_record(card)
    if op == 'random_card':
        return card_record(add_card(state,cards.definition(state.rng.choice('event.card',args))))
    if op == 'remove_exact':
        from game.headless.run.deck import remove_card
        return card_record(remove_card(state,args[0]))
    if op == 'freed_repy':
        state.freed_repy = True
        return None
    if op == 'win_run':
        if state.config is not None and state.config.campaign and state.epilogue_event_id is None:
            raise ValueError('Campaign victory requires its completed Architect epilogue.')
        from game.headless.run.state import RunPhase
        state.phase = RunPhase.VICTORY
        state.pending = None
        return None
    if op == 'dusty_tome':
        from game.headless.run.inventory import add_relic
        from dataclasses import asdict
        return asdict(add_relic(state, 'dusty_tome', cards=cards, tome_card=args[0]))
    if op == 'sea_glass':
        from game.headless.run.inventory import add_relic
        from dataclasses import asdict
        return asdict(add_relic(state, 'sea_glass', cards=cards, card_pool=args[0]))
    if op == 'wongo_points':
        from game.headless.run.inventory import add_relic
        if state.wongo_points % 2000 + args[0] >= 2000:
            add_relic(state,'wongo_customer_appreciation_badge',cards=cards)
        state.wongo_points += args[0]
        return state.wongo_points
    if op == 'random_relic':
        from game.headless.run.inventory import add_relic
        from dataclasses import asdict
        return asdict(add_relic(state,state.rng.choice('event.fixed_relic_pool',args),cards=cards,allow_dead=True))
    if op == 'abandon':
        state.hp = 0
        return None
    if op == 'random_upgrades':
        pool = [c for c in state.deck if c.upgrade_level + 1 < len(c.definition.levels)]
        stable_shuffle(state.rng,args[1],pool)
        for c in pool[:args[0]]: c.upgrade()
        return [card_record(c) for c in pool[:args[0]]]
    if op == 'upgrade_one_random':
        pool=[c for c in state.deck if c.upgrade_level+1<len(c.definition.levels)]
        if not pool: return None
        card=state.rng.choice('event.upgrade',pool);card.upgrade();return card_record(card)
    if op == 'reflections':
        result=[]
        for count,upgrade in ((2,False),(4,True)):
            pool=[c for c in state.deck if c.upgrade_level + 1 < len(c.definition.levels)] if upgrade else [c for c in state.deck if c.upgrade_level > 0]
            for _ in range(min(count,len(pool))):
                card=state.rng.choice('event.reflections',pool);pool.remove(card)
                card.upgrade_level += 1 if upgrade else -1
                result.append(card_record(card))
        return result
    if op == 'clone_deck':
        from game.headless.relics.run_rules import card_added
        result=[]
        for original in list(state.deck):
            card=deepcopy(original); card.instance_id=state.allocate_card_id()
            state.deck.append(card);card_added(state,card);result.append(card_record(card))
        return result
    if op == 'rng_int':
        return state.rng.randint('event.cosmetic',0,args[0]-1)
    if op == 'remove_relic':
        from game.headless.run.inventory import remove_relic
        from dataclasses import asdict
        return asdict(remove_relic(state,args[0]))
    if op == 'generated_card':
        from game.headless.generation.odds import card_offers
        from game.headless.relics.rewards import extend_pool, decorate
        from game.headless.run.rewards import acquire_card
        kind,no_modify=args
        pool=[d.definition_id for d in cards.definitions if d.pool==('colorless' if kind=='colorless' else character(state)) and d.rarity in ('common','uncommon','rare') and (kind=='colorless' or (d.levels[0].kind=='power' if kind=='power' else d.levels[0].cost==0 and not d.levels[0].x_cost))]
        if not no_modify: pool=extend_pool(state,cards,pool,card_reward=False,card_kind='power')
        offers,upgraded=card_offers(state,cards,pool,1,mode='base',upgrade_roll=False)
        modifiers=decorate(state,cards,offers,upgraded=upgraded,card_reward=False)
        return card_record(acquire_card(state,cards,offers[0],modifiers))
    if op == 'downgrade_random':
        pool=[c for c in state.deck if c.upgrade_level>0]
        if pool:
            card=state.rng.choice('event.downgrade',pool);card.upgrade_level-=1
            return card_record(card)
        return None
    if op == 'pull_relic':
        from game.headless.run.inventory import add_relic
        from dataclasses import asdict
        return asdict(add_relic(state,pull_relic(state,rarity=args[0],merchant=args[1]),cards=cards,allow_dead=True))
    raise ValueError(f'Unknown event operation: {op}.')
