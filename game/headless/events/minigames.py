"""Crystal Sphere's board and Endless Conveyor's weighted dishes."""
from copy import deepcopy
from game.headless.events.roster import selection

ITEMS=(('relic',4,4),('potion_common',1,3),('potion_common',1,3),('potion_rare',2,2),
       ('card_common',2,2),('card_uncommon',2,2),('card_rare',2,2),('curse',2,2),
       *(('gold_small',1,1),)*5,*(('gold_big',2,1),)*2)


def crystal_board(rng):
    clear = {(x, y) for x in range(11) for y in range(11)
             if min(x, 10 - x) + min(y, 10 - y) <= 2}
    occupied = set()
    items = []
    # Native retries keep earlier placements and subscribe to every item again.
    for _ in range(10):
        placed = True
        for kind, width, height in ITEMS:
            candidates = [
                (x, y) for x in range(12 - width) for y in range(12 - height)
                if all((i, j) not in clear | occupied
                       for i in range(x, x + width) for j in range(y, y + height))
            ] if placed else []
            cells = []
            if candidates:
                x, y = rng.choice('event.crystal', candidates)
                cells = [[i, j] for i in range(x, x + width) for j in range(y, y + height)]
                occupied.update(map(tuple, cells))
            else:
                placed = False
            items.append({'kind': kind, 'cells': cells, 'subscriptions': 0})
        for item in items:
            item['subscriptions'] += 1
        if placed:
            break
    return dict(clear=[list(v) for v in sorted(clear)], items=items, revealed=[])


def cleared(context, option):
    board = deepcopy(context['board'])
    tool, x, y = option.split('_')
    x, y = int(x), int(y)
    offsets = ((-1, 0), (1, 0), (0, -1), (0, 1),
               (-1, -1), (-1, 1), (1, -1), (1, 1), (0, 0))
    points = [(x, y)] if tool == 'small' else [
        (x + dx, y + dy) for dx, dy in offsets if 0 <= x + dx < 11 and 0 <= y + dy < 11
    ]
    revealed = []
    for point in points:
        if list(point) in board['clear']:
            continue
        board['clear'].append(list(point))
        for index, item in enumerate(board['items']):
            if (list(point) in item['cells'] and index not in board['revealed']
                    and all(cell in board['clear'] for cell in item['cells'])):
                board['revealed'].extend([index] * item['subscriptions'])
                # Curse acquisition runs once, independently of reward subscribers.
                revealed.append(item['kind'])
    board['clear'].sort()
    return board, revealed


def page(name,page_name,state,cards,rng,previous):
    if name=='crystal_sphere':
        if page_name=='initial': return {'options':['uncover_future','payment_plan'],'price':rng.randint('event.variables',51,99)}
        if len(previous)==1:
            board=crystal_board(rng);remaining=6 if previous[0]['choice']=='payment_plan' else 3
        else:
            board,_=cleared(previous[-1]['context'],previous[-1]['choice']);remaining=previous[-1]['context']['remaining']-1
        return {'options':[f'{tool}_{x}_{y}' for tool in ('big','small') for x in range(11) for y in range(11) if [x,y] not in board['clear']],'board':board,'remaining':remaining}
    count=len(previous)+1
    last=previous[-1]['context']['dish'] if previous else None
    if count%5==0: dish='seapunk_salad'
    else:
        weights=[('caviar',6),('spicy_snappy',3),('jelly_liver',3),('fried_eel',3)]
        if None in state.potions: weights.append(('suspicious_condiment',3))
        if state.hp<state.max_hp: weights.append(('clam_roll',6))
        if count>1: weights.append(('golden_fysh',1))
        weights=[(n,w) for n,w in weights if n!=last]
        from game.headless.core.native_rng import single
        roll=single(rng.random('event.conveyor')*sum(w for _,w in weights));total=0
        dish=weights[-1][0]
        for n,w in weights:
            total+=w
            if roll<total: dish=n;break
    return {'options':([dish] if state.gold>=40 else [])+(['observe_chef'] if not previous else ['leave']), 'dish':dish}


def branch(name,page_name,option,c):
    if name=='endless_conveyor':
        if option=='leave': return (),None
        if option=='observe_chef': return (('upgrade_one_random',),),None
        cost=() if option=='golden_fysh' else (('spend',40),)
        effects={'caviar': (('max_hp',4),), 'spicy_snappy': (('upgrade_one_random',),),
                 'jelly_liver': (selection('transform'),), 'fried_eel': (('generated_card','colorless',False),),
                 'suspicious_condiment': (('event_potion','any','rewards'),), 'clam_roll': (('heal',10),),
                 'golden_fysh': (('gold',75),), 'seapunk_salad': (('card','feeding_frenzy'),)}
        return cost+effects[option],'belt'
    if page_name=='initial':
        return ((('spend',c['price']),) if option=='uncover_future' else (('card','debt'),)),'sphere'
    board,revealed=cleared(c,option)
    ops=[('card','doubt') for kind in revealed if kind=='curse']
    if c['remaining']>1: return tuple(ops),'sphere'
    rewards=[]
    for i in board['revealed']:
        kind=board['items'][i]['kind']
        if kind=='relic': rewards.append(['relic','random','event.crystal'])
        elif kind.startswith('potion_'): rewards.append(['potion',kind[7:],'event.crystal'])
        elif kind.startswith('card_'): rewards.append(['card','ironclad',kind[5:],3,'event.crystal'])
        elif kind.startswith('gold_'): rewards.append(['gold',30 if kind=='gold_big' else 10])
    if rewards: ops.append(('rewards',rewards))
    return tuple(ops),None
