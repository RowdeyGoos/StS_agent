"""Exclusive potions reuse the existing summon, forge and orb commands."""
from game.headless.core.resolution import push


def apply(p, op, amount=0):
    from game.headless.cards.colorless_effects import create, catalog, pool
    if op == 'cunning':
        # Native generated-entry hooks see the base Shivs, then they upgrade.
        cards = [create(p, catalog(p).definition('shiv')) for _ in range(3)]
        for card in cards:
            card.upgrade()
    elif op == 'colorless':
        from game.headless.generation.combat import select_cards
        for definition in select_cards(pool(p, 'colorless'), p.deck.generation_rng, amount, distinct=True):
            create(p, definition, upgraded=True)
    elif op == 'stars':
        from game.headless.powers.regent import gain_stars
        gain_stars(p, amount)
    elif op == 'forge':
        from game.headless.cards.regent_effects import forge
        forge(p, amount)
    elif op == 'souls':
        from game.headless.cards.necrobinder_effects import souls
        souls(p, amount, destination='hand')
    elif op == 'summon':
        from game.headless.core.osty import summon
        summon(p, amount)
    elif op == 'slots':
        from game.headless.core.orbs import add_slots
        add_slots(p, amount)
    elif op == 'darkness':
        push(p, *[['orb_channel', 'dark'] for _ in range(p.rules.orb_slots)])
    else:
        raise ValueError('Unknown character potion effect.')
