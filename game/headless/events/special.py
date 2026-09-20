"""Tinker Time, recovered legacy content, Lantern Key follow-up and epilogue."""
from game.headless.events.roster import selection
from game.headless.cards.extended_events import RIDERS

TRASH_RELICS=('darkstone_periapt','dream_catcher','hand_drill','maw_bank','the_boot')
TRASH_CARDS=('caltrops','clash','distraction','dual_wield','entrench','hello_world','outmaneuver','rebound','rip_and_tear','stack')


def page(name,page_name,state,cards,rng,previous):
    if name=='trash_heap': return {'options':['dive_in','grab']}
    if name=='the_architect':
        if getattr(rng, 'native', False):
            # The declared fresh-history ending selects its sole dialogue.
            # Dialogue text/animation are omitted; preserve the owned RNG draw.
            rng.choice('event.variables', (0,))
        return {'options':['proceed']}
    if name=='war_historian_repy':
        keys=[c.instance_id for c in state.deck if c.definition.definition_id=='lantern_key']
        options=['unlock_cage','unlock_chest'] if not previous else ([o for o in ('unlock_cage','unlock_chest') if o!=previous[0]['choice']] if keys else ['proceed'])
        return {'options':options,'keys':keys,'second':bool(previous)}
    if page_name=='initial': return {'options':['choose_card_type']}
    if page_name=='type':
        pool=list(RIDERS);rng.shuffle('event.tinker',pool)
        return {'options':pool[:2]}
    kind=previous[-1]['choice'];pool=list(RIDERS[kind]);rng.shuffle('event.tinker',pool)
    return {'options':pool[:2],'kind':kind}


def branch(name,page_name,option,c):
    if name=='trash_heap':
        return ((('damage',8),('random_relic',*TRASH_RELICS)) if option=='dive_in' else (('gold',100),('random_card',*TRASH_CARDS))),None
    if name=='the_architect': return (('win_run',),),None
    if name=='war_historian_repy':
        if option=='proceed': return (),None
        keys=c['keys'] if c['second'] else c['keys'][:1]
        operations=[('remove_exact',i) for i in keys]
        if option=='unlock_cage': operations += [('freed_repy',),('relic','history_course')]
        else: operations += [('rewards',[['potion','factory','rewards']]*2+[['relic','random','rewards']]*2)]
        return tuple(operations),None if c['second'] else 'second'
    if page_name=='initial': return (),'type'
    if page_name=='type': return (),'rider'
    return (('mad_science',c['kind'],option),),None
