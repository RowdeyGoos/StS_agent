"""Validate saved Crystal Sphere structure without playing every possible click."""

from collections import Counter


def initial_clear():
    return {(x, y) for x in range(11) for y in range(11)
            if min(x, 10 - x) + min(y, 10 - y) <= 2}


def _cells(value):
    if (not isinstance(value, list)
            or any(not isinstance(p, list) or len(p) != 2
                   or any(type(n) is not int or not 0 <= n < 11 for n in p) for p in value)):
        raise ValueError('Invalid Crystal Sphere coordinates.')
    cells = set(map(tuple, value))
    if len(cells) != len(value):
        raise ValueError('Duplicate Crystal Sphere coordinates.')
    return cells


def validate_context(page, context):
    from game.headless.events.minigames import ITEMS

    if page == 'initial':
        if (set(context) != {'options', 'price'}
                or context['options'] != ['uncover_future', 'payment_plan']
                or type(context['price']) is not int or not 51 <= context['price'] <= 99):
            raise ValueError('Invalid Crystal Sphere entry.')
        return
    if (page != 'sphere' or set(context) != {'options', 'board', 'remaining'}
            or type(context['remaining']) is not int or not 1 <= context['remaining'] <= 6):
        raise ValueError('Invalid Crystal Sphere page.')
    board = context['board']
    if not isinstance(board, dict) or set(board) != {'clear', 'items', 'revealed'}:
        raise ValueError('Invalid Crystal Sphere board.')
    clear = _cells(board['clear'])
    if not initial_clear() <= clear or board['clear'] != [list(p) for p in sorted(clear)]:
        raise ValueError('Invalid Crystal Sphere clear cells.')
    items = board['items']
    if (not isinstance(items, list) or not items or len(items) % len(ITEMS)
            or len(items) > 10 * len(ITEMS)):
        raise ValueError('Invalid Crystal Sphere placement attempts.')
    attempts = len(items) // len(ITEMS)
    occupied = initial_clear()
    revealed = Counter()
    failed = False
    for index, item in enumerate(items):
        if index % len(ITEMS) == 0:
            if index and not failed:
                raise ValueError('Crystal Sphere retried a successful placement.')
            failed = False
        kind, width, height = ITEMS[index % len(ITEMS)]
        subscriptions = attempts - index // len(ITEMS)
        if (not isinstance(item, dict) or set(item) != {'kind', 'cells', 'subscriptions'}
                or item['kind'] != kind or type(item['subscriptions']) is not int
                or item['subscriptions'] != subscriptions):
            raise ValueError('Invalid Crystal Sphere item.')
        cells = _cells(item['cells'])
        if not cells:
            failed = True
            continue
        x, y = min(a for a, _ in cells), min(b for _, b in cells)
        rectangle = [[a, b] for a in range(x, x + width) for b in range(y, y + height)]
        if failed or item['cells'] != rectangle or occupied & cells:
            raise ValueError('Invalid Crystal Sphere item placement.')
        occupied.update(cells)
        if cells <= clear:
            revealed[index] = subscriptions
    if failed and attempts != 10:
        raise ValueError('Crystal Sphere placement stopped before its last attempt.')
    if (not isinstance(board['revealed'], list)
            or any(type(i) is not int for i in board['revealed'])
            or Counter(board['revealed']) != revealed):
        raise ValueError('Invalid Crystal Sphere revealed items.')
    options = [f'{tool}_{x}_{y}' for tool in ('big', 'small')
               for x in range(11) for y in range(11) if (x, y) not in clear]
    if context['options'] != options:
        raise ValueError('Invalid Crystal Sphere options.')


def validate_history(pages):
    """Check actual chosen transitions once, including clear order and subscriptions."""
    from game.headless.events.minigames import cleared

    for index, page in enumerate(pages[1:], 1):
        context = page['context']
        previous = pages[index - 1]
        if index == 1:
            remaining = 6 if previous['choice'] == 'payment_plan' else 3
            if context['board']['clear'] != [list(p) for p in sorted(initial_clear())]:
                raise ValueError('Crystal Sphere started with revealed cells.')
        else:
            remaining = previous['context']['remaining'] - 1
            expected, _ = cleared(previous['context'], previous['choice'])
            if context['board'] != expected:
                raise ValueError('Crystal Sphere board differs from its chosen history.')
        if context['remaining'] != remaining:
            raise ValueError('Crystal Sphere tools differ from its chosen history.')
