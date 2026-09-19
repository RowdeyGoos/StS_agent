"""Stars, Forge-related powers, and Regent card lifecycle hooks."""

from game.headless.core.resolution import push, move_out

INSTANCED = frozenset(('orbit', 'monologue'))
NAMES = frozenset(('arsenal', 'black_hole', 'child_of_the_stars', 'foregone_conclusion',
    'furnace', 'genesis', 'monarchs_gaze', 'monologue', 'orbit', 'pale_blue_dot',
    'parry', 'pillar_of_creation', 'reflect', 'royalties', 'seeking_edge',
    'spectrum_shift', 'energy_next_turn', 'star_next_turn', 'sword_sage', 'tyranny', 'void_form'))


def apply(p, key, amount):
    r = p.rules
    if key in INSTANCED:
        key = f'{key}:{r.power_sequence}'
        r.power_sequence += 1
        r.powers[key] = amount
        r.auxiliaries[key] = 0
    else:
        r.powers[key] = 1 if key == 'seeking_edge' else r.powers.get(key, 0) + amount
    if key == 'void_form':
        r.auxiliaries[key] = 999999999
    if key == 'sword_sage':
        for card in p.deck.all_cards():
            if card.definition.definition_id == 'sovereign_blade' and card not in p.deck.offered:
                card.combat_state.replay_count += amount
    if key == 'seeking_edge':
        for card in p.deck.all_cards():
            entered(p, card, is_clone=True)


def free(p):
    return p.rules.auxiliaries.get('void_form', 999999999) < p.rules.powers.get('void_form', 0)


def star_cost(p, card):
    if card.spec.star_x:
        return p.rules.stars
    if card.combat_state.star_free_this_turn:
        return 0
    return 0 if free(p) else max(0, card.spec.star_cost)


def gain_stars(p, amount):
    if amount < 0:
        raise ValueError('Stars gain cannot be negative.')
    if not amount or p.combat_is_ending:
        return
    r = p.rules
    r.stars += amount
    r.stars_gained_turn += amount
    if r.powers.get('black_hole'):
        from game.headless.powers.silent import area_damage
        area_damage(p, r.powers['black_hole'])


def spend(p, energy, stars):
    r = p.rules
    for key, amount in tuple(r.powers.items()):
        if key.startswith('orbit:') and energy:
            before = r.auxiliaries[key]
            r.auxiliaries[key] += energy
            p.gain_energy(amount * (r.auxiliaries[key] // 4 - before // 4))
    r.stars -= stars
    if stars and r.powers.get('child_of_the_stars'):
        p.gain_block(stars * r.powers['child_of_the_stars'])


def entered(p, card, *, is_clone=False):
    if card.definition.definition_id == "sovereign_blade" and not is_clone:
        card.combat_state.replay_count += p.rules.powers.get("sword_sage", 0)
    if card.definition.definition_id == 'sovereign_blade' and p.rules.powers.get('seeking_edge'):
        card.combat_state.all_enemies = True


def generated(p):
    for key, amount in tuple(p.rules.powers.items()):
        if key == 'arsenal':
            p.gain_strength(amount)
        elif key == 'pillar_of_creation':
            p.gain_block(amount)


def before_play(p, card):
    r = p.rules
    r.plays[card.instance_id]['regent_before'] = {key: amount for key, amount in r.powers.items() if key.startswith('monologue:')}


def after_card_power(p, card, key):
    from game.headless.cards.regent_effects import is_colorless
    r = p.rules
    frame = r.plays[card.instance_id]
    if key == 'black_hole' and frame['stars_spent'] and frame['remaining'] == 1:
        from game.headless.powers.silent import area_damage
        area_damage(p, r.powers[key])
    elif key.startswith('monologue:'):
        amount = frame['regent_before'].get(key, 0)
        if amount:
            p.gain_strength(amount)
            r.auxiliaries[key] += amount
    elif key == 'void_form' and not frame['auto'] and frame['remaining'] == 1:
        r.auxiliaries[key] += 1


def after_card(p, card):
    r = p.rules
    r.round_plays += 1
    if card.spec.kind in ('skill', 'block') and r.skills_finished % 3 == 0:
        for other in tuple(p.deck.all_cards()):
            if other.definition.definition_id == 'make_it_so' and other not in p.hand and other not in p.deck.in_play and other not in p.deck.offered:
                move_out(p, other)
                (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(other)


def after_draw(p, card):
    if card.definition.definition_id == 'kingly_kick':
        card.combat_state.combat_cost_change -= 1
    elif card.definition.definition_id == 'kingly_punch':
        card.combat_state.extra_damage += 6 if card.upgraded else 4


def start_turn(p, draw_count):
    r = p.rules
    if r.round_plays >= 5:
        draw_count += r.powers.get('pale_blue_dot', 0)
    draw_count += r.powers.get('tyranny', 0)
    r.round_plays = r.stars_gained_turn = 0
    r.regent_hits.clear()
    if 'void_form' in r.powers:
        r.auxiliaries['void_form'] = 0
    return draw_count


def setup_tasks(p):
    tasks = []
    for key in p.rules.powers:
        if key in ('genesis', 'energy_next_turn', 'star_next_turn'):
            tasks.append(['regent_energy_reset', key])
    return tasks


def end_turn(p, key):
    if key.startswith('monologue:'):
        p.strength -= p.rules.auxiliaries.pop(key, 0)
        p.rules.powers.pop(key, None)


def execute(p, op, args):
    from game.headless.cards.regent_effects import forge, colorless
    from game.headless.core.choices import begin
    r = p.rules
    if op == 'regent_energy_reset':
        key = args[0]
        if key == 'energy_next_turn':
            p.gain_energy(r.powers.get(key, 0))
        else:
            gain_stars(p, r.powers.get(key, 0))
        if key in ('star_next_turn', 'energy_next_turn'):
            r.powers.pop(key, None)
    elif op == 'regent_before_draw':
        key = args[0]
        amount = r.powers.get(key, 0)
        if key == 'spectrum_shift':
            colorless(p, amount)
        elif amount:
            from game.headless.powers.colorless import ensure_draw
            if not ensure_draw(p, [op, *args], hand=False):
                return
            from game.headless.core.piles import stratagem_cards
            begin(p, key, stratagem_cards(p), operation='regent_foregone_conclusion', minimum=amount, maximum=amount)
            push(p, ['regent_remove', key])
    elif op == 'regent_remove':
        r.powers.pop(args[0], None)
    elif op == 'regent_side_start_all':
        push(p, *[['regent_side_start', key] for key in r.powers if key in ('furnace', 'reflect')])
    elif op == 'regent_side_start':
        key = args[0]
        if key == 'furnace':
            forge(p, r.powers.get(key, 0))
        elif r.powers.get(key):
            r.powers[key] -= 1
    elif op == 'regent_start_power':
        if r.powers.get('tyranny'):
            begin(p, 'tyranny', list(p.hand), operation='regent_tyranny', minimum=r.powers['tyranny'], maximum=r.powers['tyranny'])
    elif op == 'regent_preplay':
        push(p, *[['autoplay', c.instance_id, False] for c in tuple(p.deck.exhaust_pile) if c.definition.definition_id == 'bombardment'])
    elif op == 'regent_end_card':
        if p.deck.draw_pile and p.deck.draw_pile[-1].instance_id == args[0]:
            push(p, ['autoplay', args[0], False])
    else:
        raise ValueError(f'Unknown Regent task: {op}')
