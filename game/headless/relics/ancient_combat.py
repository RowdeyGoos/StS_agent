"""Ancient combat hooks, using owned relic memory and explicit continuations."""

from game.headless.relics.combat import has, owned, memory
from game.headless.core.resolution import push

ENERGY = frozenset(('blessed_antler', 'blood_soaked_rose', 'ectoplasm', 'philosophers_stone',
                    'prismatic_gem', 'sozu', 'spiked_gauntlets',
                    'velvet_choker', 'whispering_earring'))
from game.headless.relics.ancient_content import MEMORY


def start_turn(p, relic, count):
    name, m = relic['definition_id'], memory(p, relic)
    if name in ENERGY or name == 'paels_flesh' and p.rules.round_number >= 3 or name == 'pumpkin_candle' and relic['counter'] > 0:
        p.gain_energy(1)
    if name in ('fiddle', 'snecko_eye'):
        count += 2
    elif name == 'paels_blood':
        count += 1
    for key, kind in MEMORY.get(name, {}).items():
        if key.startswith('turn_'):
            m[key] = False if kind == 'bool' else 0
    if name == 'diamond_diadem':
        m['protected'] = False
    if name == 'music_box':
        m.pop('triggering_card', None)
    return count


def enter(p, relic):
    name = relic['definition_id']
    if name == 'snecko_eye':
        from game.headless.powers.ironclad import apply_power
        apply_power(p, 'confused', 1)
    elif name == 'philosophers_stone':
        for enemy in p.combat_enemies or ():
            enemy.strength += 1
    elif name == 'delicate_frond':
        from game.headless.potions.pools import generate
        for _ in range(p.rules.potion_slots):
            potion = generate(p.rules.potion_pool, p.deck.potion_rng)
            if has(p, 'sozu'):
                break
            p.rules.potions_generated.append(potion)
            p.rules.potion_slots -= 1


def generate_random_draw(p, name):
    from game.headless.cards.colorless_effects import catalog
    card = catalog(p).create(name)
    p.deck._ensure_identity(card)
    # Native InsertRandomly enumerates from top, this pile pops from the end.
    index = p.deck.rng.randrange(len(p.deck.draw_pile) + 1)
    p.deck.draw_pile.insert(len(p.deck.draw_pile) - index, card)
    from game.headless.core.piles import after_generated_entry
    after_generated_entry(p, card)


def hook(p, relic, event, identity):
    name, m, turn = relic['definition_id'], memory(p, relic), p.rules.round_number
    from game.headless.core.resolution import find
    card = find(p, identity)
    if event == 'after_play':
        frame = p.rules.plays[identity]
        if name in ('diamond_diadem', 'velvet_choker'):
            m['turn_plays'] = m.get('turn_plays', 0) + 1
        if name in ('brilliant_scarf', 'paels_eye') and not frame['auto']:
            m['turn_manual'] = m.get('turn_manual', 0) + 1
        if name == 'iron_club':
            relic['counter'] += 1
            if relic['counter'] % 4 == 0 and not p.combat_is_ending:
                push(p, ['draw', 1, False])
        if name == 'paels_legion' and m.get('triggering_card') == identity:
            m['cooldown'] = 2
            m.pop('triggering_card')
        if name == 'music_box' and m.get('triggering_card') == identity:
            m['turn_used'] = True
            m.pop('triggering_card')
            if not p.combat_is_ending:
                from game.headless.cards.special import clone_to
                clone = clone_to(p, card, 'hand')
                clone.combat_state.ethereal_this_combat = True
        return
    if p.combat_is_ending:
        return
    if event == 'before_draw':
        if name == 'blessed_antler' and turn == 1:
            for _ in range(3):
                generate_random_draw(p, 'dazed')
        elif name == 'radiant_pearl' and turn == 1:
            from game.headless.cards.colorless_effects import create, catalog
            create(p, catalog(p).definition('luminesce'))
        elif name == 'jeweled_mask' and turn == 1:
            from game.headless.core.choices import resolve
            choices = [c for c in reversed(p.deck.draw_pile) if c.spec.kind == 'power']
            if choices:
                card = p.deck.selection_rng.choice(choices)
                resolve(p, card.instance_id, 'move', 'hand', 'free_this_turn')
        elif name == 'toasty_mittens':
            push(p, ['ancient_mittens', relic['instance_id']])
    elif event == 'after_side_start':
        if name == 'sai':
            p.gain_block(7)
        elif name == 'seal_of_gold':
            if p.rules.gold_available + p.rules.gold_gained - p.rules.gold_lost >= 5:
                p.gain_energy(1)
                p.rules.gold_lost += 5
        elif name == 'paels_legion':
            m['cooldown'] = max(0, m.get('cooldown', 0) - 1)
        elif name == 'paels_tears' and m.pop('stored', False):
            p.gain_energy(2)
        elif name == 'crossbow':
            offer(p, relic)
    elif event == 'after_draw' and name == 'choices_paradox' and turn == 1:
        offer(p, relic)
    elif event == 'before_end':
        if name == 'diamond_diadem':
            m['protected'] = m.get('turn_plays', 0) <= 2
        elif name == 'paels_tears':
            m['stored'] = p.energy > 0
    elif event == 'shuffle' and name == 'biiig_hug':
        generate_random_draw(p, 'soot')


def before_play(p, card):
    relic = owned(p, 'music_box')
    if relic and card.spec.kind == 'attack':
        m = memory(p, relic)
        if not m.get('turn_used') and 'triggering_card' not in m:
            m['triggering_card'] = card.instance_id


def scarf_free(p, card):
    relic = owned(p, 'brilliant_scarf')
    return bool(relic and memory(p, relic).get('turn_manual', 0) == 4 and card in (*p.hand, *p.deck.in_play))


def before_end(p):
    relic = owned(p, 'paels_eye')
    if relic:
        m = memory(p, relic)
        if not m.get('used') and not m.get('turn_manual') and not (p.rules.round_number == 1 and has(p, 'whispering_earring')):
            m['extra_turn'] = True
            return [['exhaust', c.instance_id] for c in p.hand]
    return []


def extra_turn(p):
    relic = owned(p, 'paels_eye')
    if relic and memory(p, relic).pop('extra_turn', False):
        memory(p, relic)['used'] = True
        return True
    return False


def preplay(p):
    if p.rules.round_number != 1:
        from game.headless.relics.event_content import history_preplay
        history_preplay(p)
        return
    # Native hooks visit hand, then top-first draw, discard, exhaust and play.
    ordered = (*p.hand, *reversed(p.deck.draw_pile), *p.deck.discard_pile, *p.deck.exhaust_pile, *p.deck.in_play)
    tasks = [['autoplay', c.instance_id, False] for c in ordered if c.enchantment and c.enchantment.definition_id == 'imbued']
    relic = owned(p, 'whispering_earring')
    if relic:
        tasks.append(['ancient_earring', relic['instance_id'], 0])
    push(p, *tasks)


def execute(p, op, args):
    if op == 'ancient_preplay':
        preplay(p)
        return
    relic = next(r for r in p.rules.relics if r['instance_id'] == args[0])
    if p.combat_is_ending:
        return
    if op == 'ancient_mittens':
        from game.headless.powers.colorless import ensure_draw
        # Refill may emit selectable hooks before the exhaust can continue.
        if p.deck.discard_pile and not ensure_draw(p, [op, *args], hand=False):
            return
        choices = list(reversed(p.deck.draw_pile))
        card = next((c for c in choices if not c.spec.innate), None) if p.rules.round_number == 1 else None
        card = card or next(iter(choices), None)
        push(p, *([['exhaust', card.instance_id]] if card else []), ['ancient_strength', relic['instance_id']])
    elif op == 'ancient_strength':
        p.gain_strength(1)
    elif op == 'ancient_earring':
        if (args[1] >= 13 or p.rules.round_number != 1 or p.rules.turn_ending or p.rules.regent_end_requested
                or p.statuses.get('ringing') and p.cards_played_this_turn):
            memory(p, relic)['active'] = False
            return
        from game.headless.cards.curses import can_play
        card = next((c for c in p.hand if can_play(p, c) and (c.cost >= 0 or c.spec.x_cost) and p.card_cost(c) <= p.energy and p.star_cost(c) <= p.rules.stars), None)
        if card is None:
            memory(p, relic)['active'] = False
            return
        memory(p, relic)['active'] = True
        from game.headless.core.resolution import start_play
        target = next((e for e in p.combat_enemies if e.is_alive), None) if card.spec.uses_target else None
        push(p, ['ancient_earring', relic['instance_id'], args[1] + 1])
        start_play(p, card, target, auto=True, spend_resources=True)


def offer(p, relic):
    name = relic["definition_id"]
    from game.headless.cards.colorless_effects import create, pool
    from game.headless.generation.combat import select_cards
    from game.headless.core.choices import begin
    definitions = select_cards(pool(p, kind='attack' if name == 'crossbow' else None), p.deck.generation_rng, 1 if name == 'crossbow' else 5, distinct=True)
    offers = [create(p, d, destination='offered') for d in definitions]
    if name == 'crossbow':
        from game.headless.core.choices import resolve
        resolve(p, offers[0].instance_id, 'move', 'hand', 'free_this_turn')
    else:
        for offer in offers:
            offer.combat_state.retain_this_combat = True
        begin(p, relic['instance_id'], offers)
