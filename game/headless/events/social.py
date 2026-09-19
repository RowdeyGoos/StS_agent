"""Repeated visits, conversations and offered trades; no UI callbacks."""
from game.headless.events.roster import selection
from game.headless.events.operations import pull_relic

DOLLS = ('daughter_of_the_wind','mr_struggles','bing_bong')


PICKUP_RELICS = frozenset(('alchemical_coffer', 'astrolabe', 'big_mushroom', 'blood_soaked_rose', 'byrdpip', 'calling_bell', 'cauldron', 'distinguished_cape', 'dollys_mirror', 'electric_shrymp', 'empty_cage', 'fake_lees_waffle', 'fake_mango', 'fragrant_mushroom', 'gnarled_hammer', 'golden_compass', 'golden_pearl', 'hefty_tablet', 'jewelry_box', 'kaleidoscope', 'kifuda', 'lees_waffle', 'looming_fruit', 'lost_coffer', 'mango', 'neows_talisman', 'neows_torment', 'new_leaf', 'nutritious_oyster', 'old_coin', 'orrery', 'paels_tooth', 'pandoras_box', 'pear', 'phial_holster', 'potion_belt', 'precarious_shears', 'precise_scissors', 'punch_dagger', 'royal_stamp', 'sand_castle', 'sea_glass', 'sere_talon', 'strawberry', 'toy_box', 'war_paint', 'whetstone', 'yummy_cookie'))


def tradable(state):
    from game.headless.relics.base import RELICS
    used_limits = {'lizard_tail':1, 'winged_boots':3}
    return [r for r in state.relics
            if RELICS[r.definition_id].rarity not in ('starter','event','ancient')
            and r.definition_id not in PICKUP_RELICS and not RELICS[r.definition_id].adds_pet
            and not r.data.get('_melted')
            and r.counter < used_limits.get(r.definition_id, 10**9)]


def page(name, page_name, state, cards, rng, previous):
    c = {'options': []}
    if name == 'abyssal_baths':
        c['options'] = ['immerse','abstain'] if page_name == 'initial' else ['linger','exit_baths']
        c['damage'] = len(previous) + 3
    elif name == 'colossal_flower':
        depth = len(previous)
        c.update(depth=depth, options=[('extract_current_prize_1','extract_current_prize_2','extract_instead')[depth], ('reach_deeper_1','reach_deeper_2','pollinous_core')[depth]])
    elif name == 'round_tea_party':
        c['options'] = ['enjoy_tea','pick_fight'] if page_name == 'initial' else ['continue_fight']
        c['heal'] = state.max_hp
    elif name == 'doll_room':
        if page_name == 'initial': c['options'] = ['random','take_some_time','examine']
        else:
            pool = sorted(DOLLS)
            rng.shuffle('event.dolls',pool)
            c['options'] = pool[:2 if previous[0]['choice']=='take_some_time' else 3]
    elif name == 'trial':
        if page_name == 'initial': c['options'] = ['accept','reject']
        elif page_name == 'reject': c['options'] = ['accept','double_down']
        elif page_name == 'confirm_abandon': c['options'] = ['cancel','confirm']
        else:
            c.update(options=['guilty','innocent'], accused=rng.choice('event.trial',['merchant','noble','nondescript']))
    elif name == 'colorful_philosophers':
        pool=['necrobinder','regent','silent','defect']
        while len(pool)>3: pool.remove(rng.choice('event.philosophers',pool))
        c['options'] = pool
    elif name == 'ranwid_the_elder':
        potions=[p for p in state.potions if p is not None]
        relics=tradable(state)
        c.update(potion=rng.choice('event.ranwid',potions).instance_id if potions else None,
                 relic=rng.choice('event.ranwid',relics).instance_id if relics else None)
        c['options'] = (['potion'] if c['potion'] else []) + ['gold'] + (['relic'] if c['relic'] else [])
    elif name == 'relic_trader':
        owned=sorted(tradable(state),key=lambda r:r.definition_id.upper())
        rng.shuffle('event.trader',owned)
        c['owned']=[r.instance_id for r in owned[:3]]
        c['new']=[pull_relic(state) for _ in range(3)] if owned else []
        c['options'] = ['top','middle','bottom'][:len(c['owned'])] or ['proceed']
    elif name == 'welcome_to_wongos':
        c['featured'] = pull_relic(state,rarity='rare',merchant=True)
        c['options']=[n for n,cost in (('bargain',100),('featured',200),('mystery',300)) if state.gold>=cost]+['leave']
    else:
        raise ValueError(f'Unknown event page: {name}/{page_name}.')
    return c


def branch(name, page_name, option, c):
    if name == 'abyssal_baths':
        if option in ('immerse','linger'): return (('max_hp',2),('damage',c['damage'])), 'baths'
        return ((('heal',10),) if option=='abstain' else ()), None
    if name == 'colossal_flower':
        depth=c['depth']
        if option.startswith('extract'): return (('gold',(35,75,135)[depth]),),None
        return ((('damage',5+depth),('relic','pollinous_core')),None) if depth==2 else ((('damage',5+depth),),'depth')
    if name == 'round_tea_party':
        if option=='enjoy_tea': return (('relic','royal_poison'),('heal',c['heal'])),None
        if option=='pick_fight': return (), 'fight'
        if option=='continue_fight': return (('damage',11),('relic','random')),None
    if name == 'doll_room':
        if page_name != 'initial': return (('relic',option),),None
        if option=='random': return (('random_relic',*DOLLS),),None
        return (('damage',5 if option=='take_some_time' else 15),),'dolls'
    if name == 'trial':
        if option=='accept': return (),'accused'
        if option in ('reject','cancel'): return (),'reject'
        if option=='double_down': return (),'confirm_abandon'
        if option=='confirm': return (('abandon',),),None
        rewards={
            ('merchant','guilty'): (('card','regret'),('relic','random'),('relic','random')),
            ('merchant','innocent'): (('card','shame'),selection('upgrade',2)),
            ('noble','guilty'): (('heal',10),),
            ('noble','innocent'): (('card','regret'),('gold',300)),
            ('nondescript','guilty'): (('card','doubt'),('rewards',[['card','ironclad','any',3,'rewards',{'upgrade':False}]]*2)),
            ('nondescript','innocent'): (('card','doubt'),selection('transform',2)),
        }
        return rewards[(c['accused'],option)],None
    if name == 'colorful_philosophers':
        return (('rewards',[['card',option,rarity,3,'rewards',{'pool_changes':False}] for rarity in ('common','uncommon','rare')]),),None
    if name == 'ranwid_the_elder':
        return {'potion': (('discard_potion',c['potion']),('relic','random')),
                'gold': (('spend',100),('relic','random')),
                'relic': (('remove_relic',c['relic']),('relic','random'),('relic','random'))}[option],None
    if name == 'relic_trader':
        if option=='proceed': return (),None
        i=('top','middle','bottom').index(option)
        return (('remove_relic',c['owned'][i]),('relic',c['new'][i])),None
    if name == 'welcome_to_wongos':
        if option=='leave': return (('downgrade_random',),),None
        return {'bargain': (('spend',100),('pull_relic','common',True),('wongo_points',32)),
                'featured': (('spend',200),('relic',c['featured']),('wongo_points',16)),
                'mystery': (('spend',300),('relic','wongos_mystery_ticket'),('wongo_points',8))}[option],None
    raise ValueError('Unknown event branch.')
