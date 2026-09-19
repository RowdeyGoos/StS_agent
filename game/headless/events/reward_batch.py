"""Populate custom rewards before claims, retaining only offers and decisions."""
from game.headless.relics.base import RELICS
from game.headless.potions.base import POTIONS


def prepare(state, cards, descriptors):
    from game.headless.potions.pools import ORDINARY_POTIONS, generate
    from game.headless.events.operations import pull_relic
    from game.headless.generation.odds import card_offers
    from game.headless.relics.rewards import decorate, extend_pool
    # Crystal Sphere creates its explicit potions while constructing rewards;
    # the remaining factories run in the subsequent population pass.
    potions = {i: state.rng.choice(d[2], [n for n in ORDINARY_POTIONS if d[1] == 'any' or POTIONS[n].rarity == d[1]])
               for i,d in enumerate(descriptors) if d[0]=='potion' and d[1]!='factory'}
    result=[]
    reserved=[]
    for i,d in enumerate(descriptors):
        kind=d[0]; modifiers={}
        if kind=='relic': offers=[pull_relic(state,stream=d[2],exclude=reserved) if d[1]=='random' else d[1]]
        elif kind=='potion': offers=[potions[i] if i in potions else generate(ORDINARY_POTIONS,state.rng,stream=d[2])]
        elif kind=='gold': offers=['gold'];modifiers={'gold':d[1]}
        elif kind=='special_card': offers=[d[1]]
        elif kind=='card':
            flags=d[5] if len(d)>5 else {}
            pool=[c.definition_id for c in cards.definitions if c.pool==d[1] and c.rarity in (('common','uncommon','rare') if d[2]=='any' else (d[2],))]
            pool=extend_pool(state,cards,pool,card_reward=True,no_pool_changes=not flags.get('pool_changes',True))
            offers,upgraded=card_offers(state,cards,pool,d[3],mode='base',uniform=d[2]!='any',stream=d[4],upgrade_roll=flags.get('upgrade',True))
            modifiers=decorate(state,cards,offers,upgraded=upgraded)
        else: raise ValueError('Unsupported custom reward.')
        if kind=='relic': reserved.extend(offers)
        result.append(dict(kind=kind,offers=offers,modifiers=modifiers,resolved=False))
    return result


def options(batch, state=None):
    result=[]
    reserved=[]
    for i,row in enumerate(batch):
        if row['resolved']: continue
        if row['kind'] != 'potion' or state is None or None in state.potions:
            result.extend(f'reward_{i}_{j}' for j in range(len(row['offers'])))
        result.append(f'skip_{i}')
    return tuple(result)


def claim(state,cards,row,name):
    if row['resolved'] or name is not None and name not in row['offers']:
        raise ValueError('Custom reward is unavailable.')
    if name is not None:
        from game.headless.run.inventory import add_relic,add_potion
        from game.headless.run.rewards import acquire_card
        from game.headless.run.deck import add_card
        from game.headless.relics.run_rules import gain_gold
        if row['kind']=='relic': add_relic(state,name,cards=cards)
        elif row['kind']=='potion': add_potion(state,name)
        elif row['kind']=='gold': gain_gold(state,row['modifiers']['gold'])
        elif row['kind']=='special_card': add_card(state,cards.definition(name))
        elif row['kind']=='card': acquire_card(state,cards,name,row['modifiers'])
    row['resolved']=True


def choose(state,cards,batch,option):
    if option not in options(batch,state): raise ValueError('Unavailable custom reward.')
    parts=option.split('_');row=batch[int(parts[1])]
    claim(state,cards,row,None if parts[0]=='skip' else row['offers'][int(parts[2])])


def validate(batch, descriptors, cards, state=None):
    from game.headless.relics.rewards import validate_modifiers
    if not isinstance(batch,list) or len(batch)!=len(descriptors):
        raise ValueError('Custom reward batch differs from event.')
    for row,d in zip(batch,descriptors):
        if (not isinstance(row,dict) or set(row)-{'rerolled'}!={'kind','offers','modifiers','resolved'}
                or row['kind']!=d[0] or type(row['resolved']) is not bool
                or not isinstance(row['offers'],list) or not row['offers']
                or len(row['offers'])!=len(set(row['offers']))):
            raise ValueError('Invalid custom reward.')
        if 'rerolled' in row:
            from game.headless.relics.reward_alternatives import validate_marker
            if state is None or row['kind']!='card': raise ValueError('Invalid custom reroll.')
            validate_marker(state,row)
        kind=d[0];offers=row['offers']
        if kind=='card':
            if len(offers)>d[3] or any(cards.definition(n).rarity not in (('common','uncommon','rare') if d[2]=='any' else (d[2],)) for n in offers):
                raise ValueError('Invalid custom card pool.')
            validate_modifiers(cards,offers,row['modifiers'])
        else:
            if len(offers)!=1: raise ValueError('Invalid custom item count.')
            n=offers[0]
            if (kind=='relic' and (n not in RELICS or d[1]!='random' and n!=d[1])
                    or kind=='potion' and (n not in POTIONS or d[1] not in ('any','factory') and POTIONS[n].rarity!=d[1])
                    or kind=='special_card' and n!=d[1]
                    or kind=='gold' and (offers!=['gold'] or row['modifiers']!={'gold':d[1]})):
                raise ValueError('Custom reward differs from content.')
            if kind!='gold' and row['modifiers']: raise ValueError('Unexpected item modifiers.')
