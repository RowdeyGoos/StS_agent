"""Defect resources and powers at the existing ordered combat hook boundaries."""

from game.headless.core.resolution import push, find
from game.headless.core import orbs

TEMP_FOCUS = ('focused_strike', 'hotfix', 'synchronize')
NAMES = frozenset(('focus', *TEMP_FOCUS, 'consuming_shadow', 'coolant', 'creative_ai',
    'echo_form', 'feral', 'hailstorm', 'defect_iteration', 'lightning_rod', 'loop',
    'machine_learning', 'signal_boost', 'smokestack', 'spinner', 'storm', 'subroutine',
    'thunder', 'trash_to_treasure', 'free_power', 'biased_cognition'))


def focus(p, amount):
    if amount < 0 and p.statuses.get('artifact'):
        p.statuses.decrement('artifact')
    else:
        p.rules.powers['focus'] = p.rules.powers.get('focus', 0) + amount


def apply(p, key, amount):
    if not amount:
        return
    r = p.rules
    if key == "biased_cognition" and p.statuses.get("artifact"):
        p.statuses.decrement("artifact")
        return
    if key == 'focus':
        focus(p, amount)
        return
    first_application = key not in r.powers
    if key == 'hailstorm' and first_application:
        from game.headless.powers.turns import register_before_side_end
        if p.statuses.get('doom'):
            register_before_side_end(p, 'player_doom')
        register_before_side_end(p, 'hailstorm')
    r.powers[key] = r.powers.get(key, 0) + amount
    if key in TEMP_FOCUS:
        focus(p, amount)
    if key == 'feral' and first_application:
        r.auxiliaries[key] = r.zero_attacks_turn


def prepare_play(p, card, frame):
    r = p.rules
    if r.series_turn < r.powers.get('echo_form', 0):
        frame['remaining'] += 1
    if card.spec.kind == 'power' and r.powers.get('signal_boost'):
        frame['remaining'] += 1
        r.powers['signal_boost'] -= 1
    frame['def_feral'] = (card.spec.kind == 'attack' and frame['energy_value'] == 0
                          and r.auxiliaries.get('feral', 0) < r.powers.get('feral', 0))
    if frame['def_feral']:
        frame['destination'] = 'hand'
        r.auxiliaries['feral'] += 1
    r.series_turn += 1
    if not frame['auto']:
        r.energy_spent_turn += frame['energy_value']


def before_play(p, card):
    r = p.rules
    frame = r.plays[card.instance_id]
    frame['def_before'] = {key: r.powers.get(key, 0) for key in ('storm', 'subroutine')} if card.spec.kind == 'power' else {}
    if card.spec.kind == 'power' and r.powers.get('free_power'):
        r.powers['free_power'] -= 1
    if card.spec.kind == 'attack' and frame['energy_value'] == 0:
        r.zero_attacks_turn += 1


def after_card_power(p, card, key):
    amount = p.rules.plays[card.instance_id]['def_before'].get(key, 0)
    if key == 'storm' and amount:
        push(p, *[['orb_channel', 'lightning'] for _ in range(amount)])
    elif key == 'subroutine' and amount:
        p.gain_energy(amount)


def start_turn(p, draw_count):
    r = p.rules
    r.finished_plays_turn = r.series_turn = r.energy_spent_turn = r.zero_attacks_turn = r.status_draws_turn = 0
    return draw_count + r.powers.get('machine_learning', 0)


def draw_record(p, card):
    if card.spec.kind == 'status':
        p.rules.status_draws_turn += 1


def generate_power(p, *, free=False):
    from game.headless.cards.colorless_effects import catalog, pool
    from game.headless.generation.combat import select_cards
    from game.headless.core.piles import after_generated_entry
    for definition in select_cards(pool(p, 'ironclad', 'power'), p.deck.generation_rng, 1, distinct=True):
        card = catalog(p).create(definition.definition_id)
        p.deck._ensure_identity(card)
        card.combat_state.free_this_turn = free
        (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(card)
        after_generated_entry(p, card)


def generated_status(p, card):
    tasks = []
    for key in p.rules.powers:
        if key in ('arsenal', 'pillar_of_creation', 'smokestack', 'trash_to_treasure'):
            tasks.append(['def_generated', key, card.instance_id])
    # Card listeners follow powers; only the actual owner-created status event enters here.
    tasks.extend(['def_rocket', c.instance_id] for c in p.deck.all_cards()
                 if c not in p.deck.offered and c.definition.definition_id == 'rocket_punch')
    push(p, *tasks)


def execute(p, op, args):
    r = p.rules
    if op == 'def_energy_reset':
        key = args[0]
        amount = r.powers.get(key, 0)
        if amount:
            if key == 'lightning_rod':
                push(p, ['orb_channel', 'lightning'], ['def_decrement', key])
            elif key == 'spinner':
                push(p, *[['orb_channel', 'glass'] for _ in range(amount)])
    elif op == 'def_decrement':
        r.powers[args[0]] -= 1
    elif op == 'def_before_draw':
        if args[0] > 0:
            push(p, ['def_generate_power'], ['def_before_draw', args[0] - 1])
    elif op == 'def_generate_power':
        generate_power(p)
    elif op == 'def_side_start' and args[0] == 'biased_cognition':
        focus(p, -r.powers.get('biased_cognition', 0))
    elif op == 'def_side_start':
        key = args[0]
        if key == 'coolant':
            p.gain_block(orbs.distinct(p) * r.powers.get(key, 0))
        elif key == 'feral':
            r.auxiliaries[key] = 0
    elif op == 'def_start_power':
        if args[0] == 'loop':
            push(p, *[['orb_front_passive'] for _ in range(r.powers.get('loop', 0))])
    elif op == 'def_early_end':
        if args[0] == 'hailstorm' and orbs.count(p, 'frost'):
            push(p, *[['def_damage', i, r.powers['hailstorm']] for i, e in enumerate(p.combat_enemies) if e.is_alive])
    elif op == 'def_end_power':
        key = args[0]
        if key in TEMP_FOCUS and r.powers.get(key):
            focus(p, -r.powers.pop(key))
        elif key == 'consuming_shadow':
            push(p, *[['orb_evoke', True, True] for _ in range(r.powers.get(key, 0))])
    elif op == 'def_generated':
        key, identity = args
        amount = r.powers.get(key, 0)
        if key == 'arsenal':
            p.gain_strength(amount)
        elif key == 'pillar_of_creation':
            p.gain_block(amount)
        elif key == 'smokestack':
            push(p, *[['def_damage', i, amount] for i, e in enumerate(p.combat_enemies) if e.is_alive])
        elif key == 'trash_to_treasure':
            push(p, *[['orb_channel', 'random'] for _ in range(amount)])
    elif op == 'def_rocket':
        card = find(p, args[0])
        if card is not None:
            from game.headless.core.card_costs import until_played
            until_played(card, 0)
    elif op == 'def_damage':
        if p.combat_enemies[args[0]].is_alive:
            p.combat_enemies[args[0]].take_damage(args[1], is_attack=False)
    else:
        raise ValueError(f'Unknown Defect hook: {op}')
