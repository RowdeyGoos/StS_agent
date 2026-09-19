"""Shared-phase dispatch preserves power application order across card families."""

from game.headless.core.resolution import push


def before_draw_tasks(p):
    tasks = [['before_draw_power', key] for key in p.rules.powers
             if key in ('hello_world', 'infinite_blades', 'spectrum_shift', 'foregone_conclusion', 'call_of_the_void', 'sentry_mode', 'creative_ai') or key.startswith('nightmare:')]
    return tasks


def execute(p, op, args):
    if op == 'before_draw_power':
        key = args[0]
        if key == 'hello_world':
            from game.headless.cards.colorless_effects import create, pool
            from game.headless.generation.combat import select_cards
            options = [d for d in pool(p) if d.rarity == 'common']
            for definition in select_cards(options, p.deck.generation_rng, p.rules.powers[key], distinct=True):
                create(p, definition)
        elif key == 'creative_ai':
            push(p, ['def_before_draw', p.rules.powers.get(key, 0)])
        elif key in ('call_of_the_void', 'sentry_mode'):
            from game.headless.powers.necrobinder import execute as nec
            nec(p, 'nec_before_draw', [key])
        elif key in ('spectrum_shift', 'foregone_conclusion'):
            from game.headless.powers.regent import execute as regent
            regent(p, 'regent_before_draw', [key])
        else:
            from game.headless.powers.silent import before_draw_power
            before_draw_power(p, key)
    elif op == 'side_start_powers':
        tasks = []
        for key in p.rules.powers:
            if key in ('blur', 'shadow_step', 'noxious_fumes'):
                tasks.append(['silent_side_start', key])
            elif key in ('coolant', 'feral'):
                tasks.append(['def_side_start', key])
            elif key in ('countdown', 'neurosurge'):
                tasks.append(['nec_side_start', key])
            elif key in ('furnace', 'reflect'):
                tasks.append(['regent_side_start', key])
        push(p, *tasks)
    else:
        raise ValueError('Unknown shared turn phase.')


def register_before_side_end(p, key):
    order = p.rules.before_side_end_order
    if key not in order:
        order.append(key)


def before_side_end_tasks(p):
    active = {'player_doom': bool(p.statuses.get('doom')), 'hailstorm': bool(p.rules.powers.get('hailstorm'))}
    order = p.rules.before_side_end_order + [k for k in active if k not in p.rules.before_side_end_order]
    return [['nec_player_doom'] if k == 'player_doom' else ['def_early_end', k] for k in order if active[k]]
