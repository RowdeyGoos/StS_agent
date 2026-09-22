"""Resolve immutable monster difficulty data using its combat-owned level."""
from dataclasses import replace
from game.headless.monsters.ascension_values import VALUES, HP
from game.headless.monsters.ascension_moves import MOVES


def value(enemy, name, default):
    row = VALUES.get(type(enemy).__name__, {}).get(name)
    return row[2] if row is not None and enemy.ascension >= row[0] else default


def initial_hp(enemy, low, high):
    return HP.get(type(enemy).__name__, (low, high)) if enemy.ascension >= 8 else (low, high)


def scale_intent(enemy, template):
    fields = MOVES.get(type(enemy).__name__, {}).get(template.move_name, ())
    changes = {}
    for field, prop in fields:
        threshold, low, high = VALUES[type(enemy).__name__][prop]
        if enemy.ascension >= threshold:
            # Keep phase/vigor increases in authored templates before Strength.
            if field == 'discard_cards':
                changes[field] = template.discard_cards + (template.discard_cards[0],) * (high - low)
            else:
                changes[field] = getattr(template, field) + high - low
    return replace(template, **changes) if changes else template
