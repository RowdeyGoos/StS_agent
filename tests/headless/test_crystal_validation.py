"""Crystal Sphere restores validate structure and the chosen history directly."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from game.headless.events.crystal_validation import validate_context
from tests.headless.test_all_solo_events import start, choose, saved


def options(board):
    return [f'{tool}_{x}_{y}' for tool in ('big', 'small')
            for x in range(11) for y in range(11) if [x, y] not in board['clear']]


@pytest.fixture
def sphere():
    run = start('crystal_sphere')
    choose(run, 'payment_plan')
    choose(run, 'big_5_5')
    return run


@pytest.mark.parametrize('corruption', [
    'unknown_tool', 'cleared_target', 'missing_option', 'bool_coordinate',
    'shape', 'kind', 'subscriptions', 'revealed', 'remaining', 'history',
])
def test_corrupt_crystal_restore_is_atomic(sphere, corruption):
    before = saved(sphere)
    bad = deepcopy(before)
    data = bad['state']['pending']['data']
    context = data['pages'][-1]['context']
    board = context['board']
    if corruption == 'unknown_tool':
        context['options'][0] = context['options'][0].replace('big', 'unknown')
    elif corruption == 'cleared_target':
        context['options'].append('small_0_0')
    elif corruption == 'missing_option':
        context['options'].pop()
    elif corruption == 'bool_coordinate':
        board['clear'][0][0] = False
    elif corruption == 'shape':
        board['items'][0]['cells'].pop()
    elif corruption == 'kind':
        board['items'][0]['kind'] = 'unknown'
    elif corruption == 'subscriptions':
        board['items'][0]['subscriptions'] += 1
    elif corruption == 'revealed':
        board['revealed'].append(len(board['items']))
    elif corruption == 'remaining':
        context['remaining'] = 0
    else:
        occupied = {tuple(cell) for item in board['items'] for cell in item['cells']}
        cell = next([x, y] for x in range(11) for y in range(11)
                    if [x, y] not in board['clear'] and (x, y) not in occupied)
        board['clear'].append(cell)
        board['clear'].sort()
        context['options'] = options(board)
        validate_context('sphere', context)
    # Reach semantic validation rather than only the continuation hash guard.
    data['checkpoint']['continuation'] = sha256(json.dumps(
        {key: value for key, value in data.items() if key != 'checkpoint'},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    with pytest.raises(ValueError, match='Crystal Sphere'):
        sphere.restore(bad)
    assert saved(sphere) == before


def test_context_validation_does_not_simulate_offered_clicks(sphere, monkeypatch):
    from game.headless.events import minigames
    context = saved(sphere)['state']['pending']['data']['pages'][-1]['context']
    before = deepcopy(context)
    monkeypatch.setattr(minigames, 'cleared', lambda *args: pytest.fail('Offered click executed'))
    validate_context('sphere', context)
    assert context == before


def test_retained_retry_placements_and_multiple_reveal_subscriptions(monkeypatch):
    from game.headless.events import minigames
    from game.headless.core.rng import GameRandomService
    monkeypatch.setattr(minigames, 'ITEMS', (('gold_small', 1, 1), ('relic', 20, 20)))
    board = minigames.crystal_board(GameRandomService(7))
    context = dict(board=board, remaining=6, options=options(board))
    validate_context('sphere', context)
    x, y = board['items'][0]['cells'][0]
    board, _ = minigames.cleared(context, f'small_{x}_{y}')
    assert board['revealed'] == [0] * 10
    context = dict(board=board, remaining=5, options=options(board))
    validate_context('sphere', context)
    board['revealed'].pop()
    with pytest.raises(ValueError, match='revealed'):
        validate_context('sphere', context)
