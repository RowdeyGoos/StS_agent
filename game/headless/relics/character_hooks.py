"""Character relics at shared combat boundaries, with owned counters and tasks."""
from game.headless.core.resolution import push, find
from game.headless.relics.combat import has, memory, heal
from game.headless.powers.ironclad import local_cost


def enter(p, relic):
    name = relic['definition_id']
    if name == 'divine_right':
        from game.headless.powers.regent import gain_stars
        gain_stars(p, 3)
    elif name == 'data_disk':
        from game.headless.powers.ironclad import apply_power
        apply_power(p, 'focus', 1)
    elif name in ('bound_phylactery', 'phylactery_unbound'):
        from game.headless.core.osty import summon
        summon(p, 1 if name == 'bound_phylactery' else 5)


def start(p, relic, draw):
    name, turn = relic['definition_id'], p.rules.round_number
    if name in ('ring_of_the_snake', 'ring_of_the_drake') and turn <= (1 if name == 'ring_of_the_snake' else 3):
        draw += 2
    elif name == 'bound_phylactery' and turn > 1:
        from game.headless.core.osty import summon
        summon(p, 1)
    elif name == 'emotion_chip':
        m = memory(p, relic)
        m['previous_damage'] = m.pop('damaged', False)
    elif name == 'mini_regent':
        memory(p, relic)['used'] = False
    return draw


def hook(p, relic, event, identity):
    name, turn = relic['definition_id'], p.rules.round_number
    m = memory(p, relic)
    if p.combat_is_ending:
        return
    if event == 'before_draw':
        if name == 'ninja_scroll' and turn == 1:
            from game.headless.cards.silent_effects import shivs
            shivs(p, 3)
        elif name == 'funerary_mask' and turn == 1:
            from game.headless.cards.necrobinder_effects import souls
            souls(p, 3)
    elif event == 'before_side_start':
        if name == 'cracked_core':
            push(p, ['orb_channel', 'lightning'])
        elif name == 'power_cell':
            from game.headless.core.native_shuffle import stable_shuffle
            cards = [c for c in reversed(p.deck.draw_pile) if not c.spec.x_cost and local_cost(c) == 0]
            stable_shuffle(cards, p.deck.selection_rng)
            for card in cards[:2]:
                p.deck.draw_pile.remove(card)
                (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(card)
        elif name == 'twisted_funnel':
            for enemy in p.combat_enemies:
                if enemy.is_alive:
                    enemy.apply_status('poison', 4, source=p)
    elif event == 'after_side_start':
        if name == 'phylactery_unbound':
            from game.headless.core.osty import summon
            summon(p, 2)
        elif turn == 1:
            if name == 'divine_destiny':
                from game.headless.powers.regent import gain_stars
                gain_stars(p, 6)
            elif name == 'fencing_manual':
                from game.headless.cards.regent_effects import forge
                forge(p, 10)
            elif name == 'orange_dough':
                from game.headless.cards.regent_effects import colorless
                colorless(p, 2)
            elif name == 'big_hat':
                from game.headless.cards.colorless_effects import pool, create
                from game.headless.generation.combat import select_cards
                choices = [d for d in pool(p) if d.levels[0].ethereal]
                for definition in select_cards(choices, p.deck.generation_rng, 2, distinct=True):
                    create(p, definition)
            elif name == 'runic_capacitor':
                from game.headless.core.orbs import add_slots
                add_slots(p, 3)
            elif name in ('symbiotic_virus', 'infused_core'):
                push(p, *[['orb_channel', 'dark' if name == 'symbiotic_virus' else 'lightning']
                           for _ in range(1 if name == 'symbiotic_virus' else 3)])
    elif event == 'after_draw' and name == 'emotion_chip' and m.pop('previous_damage', False):
        push(p, *[['orb_trigger', i, 'passive', None] for i in tuple(p.rules.orb_order)])
    elif event == 'after_play':
        card = find(p, identity)
        if name == 'helical_dart' and card.definition.definition_id == 'shiv':
            from game.headless.powers.ironclad import apply_power
            apply_power(p, 'dexterity', 1)
            apply_power(p, 'helical_dart', 1)
        elif name == 'ivory_tile' and p.rules.plays[identity]['energy_value'] >= 3:
            p.gain_energy(1)
    elif event == 'discard' and p.rules.player_side:
        if name == 'tingsha':
            from game.headless.relics.plays import random_damage
            random_damage(p, 3)
        elif name == 'tough_bandages':
            p.gain_block(3)
    elif event == 'after_end':
        if name == 'lunar_pastry':
            from game.headless.powers.regent import gain_stars
            gain_stars(p, 1)
    elif event == 'after_flush' and name == 'bookmark':
        choices = [c for c in p.hand if not c.spec.x_cost and local_cost(c) > 0]
        if choices:
            card = p.deck.selection_rng.choice(choices)
            card.combat_state.until_played_discount += 1


def spent(p, stars):
    if not stars:
        return
    from game.headless.powers.ironclad import apply_power
    for relic in p.rules.relics:
        if relic.get('data', {}).get('_melted'):
            continue
        name = relic['definition_id']
        if name == 'galactic_dust':
            total = relic['counter'] + stars
            relic['counter'] = total % 10
            if total >= 10 and not p.combat_is_ending:
                p.gain_block(10 * (total // 10))
        elif name == 'mini_regent' and not p.combat_is_ending and not memory(p, relic).get('used'):
            memory(p, relic)['used'] = True
            apply_power(p, 'strength', 1)


def generated(p):
    if has(p, 'regalite') and not p.combat_is_ending:
        p.gain_block(2)


def channeled(p):
    for relic in p.rules.relics:
        if relic['definition_id'] == 'metronome' and not relic.get('data', {}).get('_melted'):
            m = memory(p, relic)
            m['count'] = m.get('count', 0) + 1
            if m['count'] == 7:
                from game.headless.powers.colorless import area
                area(p, 30)
