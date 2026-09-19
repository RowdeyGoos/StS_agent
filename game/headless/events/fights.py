"""Combat pages and post-combat rewards for the solo event encounters."""
from game.headless.events.roster import selection

ENCOUNTERS={'battleworn_dummy':tuple(f'battleworn_dummy_{i}' for i in range(1,4)),
            'punch_off':('punch_off_event',),'the_lantern_key':('mysterious_knight_event',),'fake_merchant':('fake_merchant_event',)}
FAKES=('fake_anchor','fake_blood_vial','fake_happy_flower','fake_lees_waffle','fake_mango','fake_orichalcum','fake_snecko_eye','fake_strike_dummy','fake_venerable_tea_set')


def page(name,page_name,state,cards,rng,previous):
    if name=='battleworn_dummy':
        if page_name=='initial': return {'options':['setting_1','setting_2','setting_3']}
        return {'options':['proceed'], 'setting':previous[0]['choice'], 'timed_out':state.event_combats[-1].timed_out}
    if name=='punch_off':
        return {'options':['nab','i_can_take_them'],'gold':rng.randint('event.variables',91,98)} if page_name=='initial' else {'options':['fight']}
    if name=='the_lantern_key':
        return {'options':['return_the_key','keep_the_key']} if page_name=='initial' else {'options':['fight']}
    if page_name=='initial':
        stock=list(FAKES);rng.shuffle('event.fake_merchant',stock);stock=stock[:6]
        from game.headless.core.native_rng import single
        prices={n:round(single(single(50)*single(single(.85)+single(rng.random('shop.prices')*single(single(1.15)-single(.85)))))) for n in stock}
    else:
        stock=list(previous[-1]['context']['stock'])
        prices=dict(previous[-1]['context']['prices'])
        bought=previous[-1]['choice']
        if bought in stock: stock.remove(bought)
    potion=next((p.instance_id for p in state.potions if p is not None and p.definition_id=='foul_potion'),None)
    return {'options':([n for n in stock if state.gold>=prices[n]]+(['throw_foul_potion'] if potion else [])+['leave']), 'stock':stock,'potion':potion,'prices':prices}


def branch(name,page_name,option,c):
    if name=='battleworn_dummy':
        if page_name=='initial': return (('combat',f'battleworn_dummy_{option[-1]}'),),'result'
        if c['timed_out']: return (),None
        return {'setting_1': (('event_potion','any','rewards'),), 'setting_2': (('random_upgrades',2,'event.upgrade'),), 'setting_3': (('relic','random'),)}[c['setting']],None
    if name=='punch_off':
        if option=='nab': return (('card','injury'),('relic_reward','random')),None
        if option=='i_can_take_them': return (),'fight'
        return (('combat','punch_off_event'),('relic_reward','random'),('factory_potion',)),None
    if name=='the_lantern_key':
        if option=='return_the_key': return (('gold',100),),None
        if option=='keep_the_key': return (),'fight'
        return (('combat','mysterious_knight_event'),('special_card_reward','lantern_key')),None
    if option=='leave': return (),None
    if option=='throw_foul_potion':
        return (('discard_potion',c['potion']),('combat','fake_merchant_event'),('relic_reward','fake_merchants_rug'),*(('relic_reward',n) for n in c['stock'])),None
    return (('spend',c['prices'][option]),('relic',option),('merchant_purchase',)),'shop'
