"""Shared-phase dispatch preserves power application order across card families."""

from game.headless.core.resolution import push


def before_draw_tasks(p):
    tasks = [['before_draw_power', key] for key in p.rules.powers
             if key in ('infinite_blades', 'spectrum_shift', 'foregone_conclusion', 'call_of_the_void', 'sentry_mode') or key.startswith('nightmare:')]
    return tasks


def execute(p, op, args):
    if op == 'before_draw_power':
        key = args[0]
        if key in ('call_of_the_void', 'sentry_mode'):
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
            elif key in ('countdown', 'neurosurge'):
                tasks.append(['nec_side_start', key])
            elif key in ('furnace', 'reflect'):
                tasks.append(['regent_side_start', key])
        push(p, *tasks)
    else:
        raise ValueError('Unknown shared turn phase.')
