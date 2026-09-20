"""Earned card-removal rewards use existing extra-reward commands and run IDs."""


def add(state, count):
    if not count:
        return
    state.pending['grimoire_rewards_earned'] = count
    for index in range(count):
        state.pending['extra_rewards'].append(dict(source=f'forbidden_grimoire:{index}',
            kind='remove', offers=[], modifiers={}, resolved=False))


def options(state):
    return [c.instance_id for c in state.deck if not c.spec.eternal]


def claim(state, row, identity):
    if identity is not None and identity not in options(state):
        raise ValueError('Card-removal reward requires an owned removable card.')
    if identity is not None:
        from game.headless.run.deck import remove_card
        remove_card(state, identity)
    row['resolved'] = True


def validate(state):
    pending = state.pending or {}
    count = pending.get('grimoire_rewards_earned', 0)
    if type(count) is not int or count < 0:
        raise ValueError('Invalid earned Grimoire rewards.')
    rows = [r for r in pending.get('extra_rewards', []) if str(r.get('source', '')).startswith('forbidden_grimoire:')]
    if len(rows) != count:
        raise ValueError('Removal rewards differ from earned count.')
    for index, row in enumerate(rows):
        if (row['source'] != f'forbidden_grimoire:{index}' or row['kind'] != 'remove'
                or row['offers'] != [] or row['modifiers'] != {} or type(row['resolved']) is not bool):
            raise ValueError('Invalid owned removal reward.')
