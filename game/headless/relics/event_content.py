"""Relics obtainable only from the extended solo event roster."""
NAMES = ('pollinous_core','forgotten_soul','big_mushroom','fragrant_mushroom','lost_wisp','royal_poison',
 'daughter_of_the_wind','mr_struggles','bing_bong','wongos_mystery_ticket','wongo_customer_appreciation_badge',
 'darkstone_periapt','dream_catcher','hand_drill','maw_bank','the_boot','fake_anchor','fake_blood_vial',
 'fake_happy_flower','fake_lees_waffle','fake_mango','fake_orichalcum','fake_snecko_eye','fake_strike_dummy',
 'fake_venerable_tea_set','fake_merchants_rug','history_course')


def definitions(cls):
    result={n:cls(n,rarity='event') for n in NAMES}
    for n,count in (('pollinous_core',3),('fake_happy_flower',4),('fake_venerable_tea_set',1),('maw_bank',1),('wongos_mystery_ticket',6)):
        result[n]=cls(n,rarity='event',counter_limit=count)
    result['big_mushroom']=cls('big_mushroom',rarity='event',pickup_max_hp=20)
    result['fake_mango']=cls('fake_mango',rarity='event',pickup_max_hp=3)
    return result


def pickup(state,relic,cards):
    from game.headless.relics.run_rules import damage,heal
    if relic.definition_id=='fragrant_mushroom':
        damage(state,15)
        from game.headless.relics.ancient_pickups import upgrade_random
        upgrade_random(state,2)
    elif relic.definition_id=='fake_lees_waffle': heal(state,state.max_hp//10)


def start_turn(p,relic,draw_count):
    from game.headless.relics.combat import increment
    name=relic['definition_id']
    if name=='big_mushroom' and p.rules.round_number==1: draw_count-=2
    elif name=='pollinous_core' and increment(relic,4): draw_count+=2
    elif name=='fake_venerable_tea_set' and relic['counter']:
        p.gain_energy(1);relic['counter']=0
    return max(0,draw_count)


def hook(p,relic,event,identity):
    from game.headless.relics.combat import memory,increment,heal
    from game.headless.core.resolution import find,push
    from game.headless.powers.colorless import area
    name=relic['definition_id']; m=memory(p,relic)
    if event=='after_play':
        card=find(p,identity)
        if name=='daughter_of_the_wind' and card.spec.kind=='attack': p.gain_block(1)
        elif name=='lost_wisp' and card.spec.kind=='power': area(p,8)
        elif name=='history_course' and card.spec.kind in ('attack','skill','block') and not card.combat_state.is_dupe:
            m.update(last_card=identity,last_turn=p.rules.round_number)
    elif event in ('exhaust','exhaust_ethereal') and name=='forgotten_soul':
        from game.headless.relics.plays import random_damage
        random_damage(p,1)
    elif event=='after_side_start' and name=='fake_happy_flower' and increment(relic,5): p.gain_energy(1)
    elif event=='after_draw':
        if name=='royal_poison' and p.rules.round_number==1: p.lose_hp(4)
        elif name=='fake_blood_vial' and p.rules.round_number==1: heal(p,1)
        elif name=='mr_struggles': area(p,p.rules.round_number)
    elif event=='before_end' and name=='fake_orichalcum' and m.pop('orichalcum_ready',False): p.gain_block(3)


def history_preplay(p):
    from copy import deepcopy
    from game.headless.relics.combat import owned, memory
    from game.headless.core.resolution import find, push
    relic = owned(p, 'history_course')
    if not relic:
        return
    m = memory(p, relic)
    if m.get('last_turn') != p.rules.round_number - 1:
        return
    original = find(p, m['last_card'])
    if original is None:
        return
    card = deepcopy(original)
    card.instance_id = None
    card.combat_state.is_dupe = True
    p.deck._ensure_identity(card)
    p.deck.offered.append(card)
    push(p, ['autoplay', card.instance_id, False])
