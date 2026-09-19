"""A combat card can carry only one affliction; first application owns it."""

NAMES = ('smog', 'tainted', 'galvanized', 'hexed', 'bound')


def afflict(card, name):
    if name not in NAMES:
        raise ValueError('Unknown card affliction.')
    state = card.combat_state
    if any(getattr(state, field) for field in NAMES):
        return False
    setattr(state, name, True)
    return True
