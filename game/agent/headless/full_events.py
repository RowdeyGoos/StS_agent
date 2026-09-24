"""Current visible event page, offers and selections; no future page plans."""
from .full_projection import node
from .full_cards import card_node
from .errors import UnsupportedProfile

# Explicit visible scalar fields, shared by page mechanics. Checkpoints, original
# deck records, RNG captures, receipt queues and unchosen results are excluded.
VISIBLE = ('price', 'remaining', 'dish', 'damage', 'depth', 'heal', 'accused',
           'setting', 'timed_out', 'kind', 'second', 'gold', 'breathing_cost',
           'small_gold', 'large_gold', 'small', 'large', 'solo_gold', 'join_gold', 'count')
STAGES = frozenset(('options', 'page', 'select_card', 'resolved', 'fight',
                    'event_rewards', 'card_rewards', 'potion_rewards',
                    'relic_reward', 'gold_reward', 'special_card_reward'))


def project_event(projection):
    p = projection
    pending = p.state.pending
    name, stage, data = pending['definition_id'], pending['stage'], pending['data']
    if stage not in STAGES:
        raise UnsupportedProfile('event_stage:' + stage)
    values, children, links = {'stage': stage}, [], []
    page = data['pages'][-1] if data.get('pages') else None
    context = page['context'] if page is not None else data.get('variables', data)
    if page:
        values['page'] = page['name']
    if data.get('choice') is not None:
        values['choice'] = data['choice']
    for key in VISIBLE:
        if key in context:
            values[key] = context[key]
    # Public selected trade costs, rather than the raw allocated item identities.
    for key, refs in (('potion', p.potion_refs), ('relic', p.relic_refs)):
        if context.get(key) in refs:
            links.append((key, (refs[context[key]],)))
    if name == 'darv' and 'dusty_tome' in context.get('options', ()):
        children.append(p.offer_card(context['tome_card'], ('dusty_tome', p.serial), {'upgrade_level': 1}))
    if name == 'orobas' and 'sea_glass' in context.get('options', ()):
        values['sea_glass_family'] = context['family']
    if name == 'slippery_bridge' and stage == 'options':
        links.append(('offered_card', (p.card_refs[data['offers'][-1]],)))
        values['damage'] = 3 + len(data['offers']) - 1
    if name == 'tablet_of_truth':
        count = data['count']
        values['next_max_hp_cost'] = (3, 6, 12, 24)[count] if count < 4 else p.state.max_hp - 1
    if name == 'the_future_of_potions':
        for i, trade in enumerate(context.get('trades', ())):
            targets = (p.potion_refs[trade['instance_id']],) if trade['instance_id'] in p.potion_refs else ()
            children.append(node('trade', index=i, rarity=trade['rarity'], card_kind=trade['kind'], links=(('potion', targets),)))
    if name == 'relic_trader' and stage in ('options', 'page'):
        for i, (owned, offered) in enumerate(zip(context['owned'], context['new'])):
            child = p.item('relic', offered, ('event_trade', p.serial, i, offered))
            children.append(node('trade', index=i, children=(child,), links=(('owned', (p.relic_refs[owned],)),)))
    if name == 'welcome_to_wongos':
        children.append(p.item('relic', context['featured'], ('featured', p.serial, context['featured'])))
    if name == 'fake_merchant' and 'stock' in context:
        for i, relic in enumerate(context['stock']):
            children.append(p.item('relic', relic, ('fake_shop', p.serial, i, relic), price=context['prices'][relic]))
    if name == 'war_historian_repy':
        links.append(('keys', (p.card_refs[i] for i in context.get('keys', ()) if i in p.card_refs)))
    if name == 'crystal_sphere' and 'board' in context:
        board = context['board']
        clear = {tuple(cell) for cell in board['clear']}
        # Only uncovered squares can reveal a fragment of an item. Neither its
        # hidden extent nor other placements/subscription counts are public.
        for x, y in sorted(clear):
            fragment = next((item['kind'] for item in board['items'] if [x, y] in item['cells']), 'empty')
            children.append(node('cell', fragment, ref=p.ref('cell', (p.serial, x, y)), x=x, y=y))
        revealed = sorted(set(board['revealed']))
        children.extend(node('revealed_item', board['items'][i]['kind']) for i in revealed)
    active = data.get('active') or {}
    if stage == 'select_card':
        selected = active.get('selected', data.get('selected', ())) or ()
        selected = [selected] if isinstance(selected, str) else selected
        # Step selections apply one card immediately. Preserve descriptions of
        # already selected cards only from their explicitly public pre-choice deck.
        selected_refs = []
        originals = active.get('originals', data.get('originals', ()))
        for identity in selected:
            ref = p.card_refs.get(identity)
            if ref is None:
                from game.headless.core.snapshots import restore_card
                original = next((v for v in originals if v['instance_id'] == identity), None)
                if original is None:
                    raise UnsupportedProfile('selected_card_description')
                ref = p.ref('card', ('deck', identity))
                children.append(card_node(restore_card(original, p.engine.cards), ref))
            selected_refs.append(ref)
        count = active.get('count', 2 if name == 'morphic_grove' else 1)
        values.update(minimum=count, maximum=count, selected_count=len(selected), manual_confirmation=False, cancelable=False)
        links += [('options', (p.card_refs[i] for i in data['eligible'])), ('selected', selected_refs)]
        if active:
            # This is the already chosen operation, never the plan for an
            # unchosen page. Its selection instruction is visible now.
            from game.headless.events.catalog import EVENTS
            operation = EVENTS[name].plan(data)[data['cursor']]
            values['operation'] = operation[1]
            values['modifier'] = operation[3]
            values['amount'] = operation[4]
    elif stage == 'event_rewards':
        p.modal = True
        for i, reward in enumerate(active['rewards']):
            children.append(p.reward(reward['kind'], reward['offers'], reward['modifiers'], i, resolved=reward['resolved']))
    elif stage == 'card_rewards':
        children.append(p.reward('card', active['offers'], active['modifiers'], -1))
        links.append(('selected', (p.reward_cards[-1, i] for i in active['selected'])))
        values.update(minimum=0 if active['optional'] else active['count'], maximum=active['count'],
                      selected_count=len(active['selected']), manual_confirmation=False)
    elif stage == 'potion_rewards':
        if active:
            children.append(p.reward('potion', [active['definition_id']], {}, 'potion'))
        else:
            for i, reward in enumerate(data['rewards']):
                children.append(p.reward('potion', [reward['definition_id']], {}, i, resolved=reward['claimed_id'] is not None))
    elif stage in ('relic_reward', 'gold_reward', 'special_card_reward'):
        kind = stage.removesuffix('_reward')
        children.append(p.reward(kind, [active['value']], {'gold': active['value']} if kind == 'gold' else {}, -1))
    return node('event', name, children=children, links=links, **values)
