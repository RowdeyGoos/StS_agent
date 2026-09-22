"""Solo Ancient offers. Relic acquisition owns all nested pickup effects."""
from game.headless.characters import character, ancient_cards, STARTER_UPGRADES
from game.headless.enchantments.base import can_enchant

NAMES=('darv','nonupeipe','orobas','pael','tanx','tezcatara','vakuu')


def page(name,state,rng):
    def choose(pool): return rng.choice('event.ancient',pool)
    def shuffled(pool):
        pool=list(pool);rng.shuffle('event.ancient',pool);return pool
    c={}
    if name=='darv':
        sets=[['astrolabe'],['black_star'],['calling_bell'],['empty_cage'],['pandoras_box'],['runic_pyramid'],['snecko_eye']]
        if state.act_index==1: sets.append(['ectoplasm','sozu'])
        elif state.act_index==2: sets.append(['philosophers_stone','velvet_choker'])
        pool=shuffled([choose(s) for s in sets])
        c['options']=pool[:2]+['dusty_tome'] if rng.randint('event.ancient',0,1)==0 else pool[:3]
        if 'dusty_tome' in c['options']:
            from game.headless.cards.catalog import DEFAULT_CARDS
            choices=[d.definition_id for d in ancient_cards(character(state), DEFAULT_CARDS)]
            c['tome_card']=rng.choice('rewards',choices)
    elif name=='nonupeipe':
        pool=['blessed_antler','brilliant_scarf','delicate_frond','diamond_diadem','fur_coat','glitter','jewelry_box','looming_fruit','signet_ring']
        if sum(can_enchant(card,'swift') for card in state.deck)>=4: pool.append('beautiful_bracelet')
        c['options']=shuffled(pool)[:3]
    elif name=='tanx':
        pool=['claws','crossbow','iron_club','meat_cleaver','sai','spiked_gauntlets','tanxs_whistle','throwing_axe','war_hammer']
        if sum(can_enchant(card,'instinct') for card in state.deck)>=3: pool.append('tri_boomerang')
        c['options']=shuffled(pool)[:3]
    elif name=='pael':
        first=choose(['paels_flesh','paels_horn','paels_tears'])
        pool=['paels_wing']
        if sum(can_enchant(card,'goopy') for card in state.deck)>=3: pool.append('paels_claw')
        if sum(not card.spec.eternal for card in state.deck)>=5: pool.append('paels_tooth')
        second=choose(pool+pool+['paels_growth'])
        pool=['paels_eye','paels_blood']
        from game.headless.events.eligibility import entry_conditions
        if not entry_conditions(state)['event_pet']: pool.append('paels_legion')
        c['options']=[first,second,choose(pool)]
    elif name=='tezcatara':
        pool=['very_hot_cocoa','yummy_cookie']
        if any(card.definition.strike and card.definition.rarity=='basic' for card in state.deck): pool.append('nutritious_soup')
        c['options']=[choose(pool),choose(['biiig_hug','storybook','toasty_mittens']),choose(['golden_compass','pumpkin_candle','toy_box','seal_of_gold'])]
    elif name=='vakuu':
        c['options']=[shuffled(pool)[0] for pool in (['blood_soaked_rose','whispering_earring','fiddle'],['preserved_fog','sere_talon','distinguished_cape'],['choices_paradox','music_box','lords_parasol','jeweled_mask'])]
    elif name=='orobas':
        c['family']=choose([c for c in ('ironclad','silent','regent','necrobinder','defect') if c != character(state)])
        extra='prismatic_gem' if rng.random('event.ancient')<0.3333333 else 'sea_glass'
        options=[choose(['electric_shrymp','glass_eye','sand_castle',extra]),choose(['alchemical_coffer','driftwood','radiant_pearl'])]
        pool=[]
        if any(r.definition_id in ('burning_blood','ring_of_the_snake','divine_right','bound_phylactery','cracked_core') for r in state.relics): pool.append('touch_of_orobas')
        if any(c.definition.definition_id in ('bash','neutralize','unleash','falling_star','dualcast') for c in state.deck): pool.append('archaic_tooth')
        third=choose(pool or [None])
        if third is not None: options.append(third)
        c['options']=options
    else: raise ValueError('Unknown Ancient.')
    return c


def branch(name,option,context):
    if option=='dusty_tome': return (('dusty_tome',context['tome_card']),),None
    if option=='sea_glass': return (('sea_glass',context['family']),),None
    return (('relic',option),),None
