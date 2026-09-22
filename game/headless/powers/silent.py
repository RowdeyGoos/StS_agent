"""Silent power hooks and resumable poison, draw and turn reactions."""

from game.headless.core.resolution import push, find

NAMES = frozenset(('accuracy', 'accelerant', 'afterimage', 'anticipate', 'blur', 'burst',
    'corrosive_wave', 'envenom', 'fan_of_knives', 'free_skill', 'infinite_blades',
    'master_planner', 'noxious_fumes', 'outbreak', 'phantom_blades', 'serpent_form',
    'shadow_step', 'shadowmeld', 'speedster', 'tools_of_the_trade', 'tracking',
    'well_laid_plans', 'draw_next_turn', 'double_damage', 'wraith_form'))
SINGLE = frozenset(('fan_of_knives', 'master_planner'))


def is_sly(card):
    return card.spec.sly


def can_play(p, card):
    return card.definition.definition_id != 'grand_finale' or not p.deck.draw_pile


def apply(p, key, amount):
    r = p.rules
    if key == "wraith_form" and p.statuses.get("artifact"):
        p.statuses.decrement("artifact")
        return
    if key == 'tracking' and key not in r.powers:
        amount += 1
    r.powers[key] = 1 if key in SINGLE else r.powers.get(key, 0) + amount
    if key == 'outbreak':
        r.auxiliaries.setdefault(key, 0)
    if key in ('phantom_blades', 'fan_of_knives'):
        for card in p.deck.all_cards():
            entered(p, card)


def entered(p, card, *, is_clone=False):
    if card.definition.definition_id == 'shiv':
        if p.rules.powers.get('phantom_blades'):
            card.combat_state.retain_this_combat = True
        if p.rules.powers.get('fan_of_knives'):
            card.combat_state.all_enemies = True
    elif not is_clone and card.definition.definition_id == 'pinpoint':
        card.combat_state.turn_cost_change = -p.rules.skills_finished


def before_play(p, card):
    r = p.rules
    r.plays[card.instance_id]['silent_before'] = {
        'afterimage': r.powers.get('afterimage', 0),
        'serpent_form': r.powers.get('serpent_form', 0),
        'strangle': [e.statuses.get('strangle') for e in p.combat_enemies or ()],
    }
    if card.spec.kind in ('skill', 'block'):
        if r.powers.get('free_skill'):
            r.powers['free_skill'] -= 1



def after_card(p, card):
    if card.spec.kind in ("skill", "block"):
        for other in p.deck.all_cards():
            if other.definition.definition_id == "pinpoint" and other not in p.deck.offered:
                other.combat_state.turn_cost_change -= 1


def after_play(p, card):
    if card.spec.kind in ('skill', 'block'):
        p.rules.skills_finished += 1
    if card.definition.definition_id == 'shiv':
        p.rules.shivs_finished += 1


def after_card_power(p, card, key):
    r = p.rules
    captured = r.plays[card.instance_id].get('silent_before', {})
    if key == 'afterimage' and captured.get(key):
        p.gain_block(captured[key])
    elif key == 'serpent_form' and captured.get(key):
        living = [e for e in p.combat_enemies if e.is_alive]
        if living:
            p.deck.target_rng.choice(living).take_damage(captured[key], is_attack=False)
    elif key == 'master_planner' and card.spec.kind in ('skill', 'block'):
        card.combat_state.sly_this_combat = True


def after_enemies(p, card):
    captured = p.rules.plays[card.instance_id].get('silent_before', {}).get('strangle', [])
    push(p, *[['silent_strangle', i, amount] for i, amount in enumerate(captured) if amount])


def damage_bonus(p, card):
    if card is None:
        return 0
    bonus = 1 if card.enchantment is not None and card.enchantment.definition_id == 'inky' else 0
    if card.definition.definition_id == 'shiv':
        bonus += p.rules.powers.get('accuracy', 0)
        if not p.rules.shivs_finished:
            bonus += p.rules.powers.get('phantom_blades', 0)
    return bonus


def damage_multiplier(p, enemy):
    multiplier = 2 if p.rules.powers.get('double_damage') and p.current_card is not None else 1
    if enemy.statuses.get('weak'):
        multiplier *= p.rules.powers.get('tracking', 1)
    return multiplier


def poison(p, enemy, amount):
    if amount <= 0 or not enemy.is_alive or p.combat_is_ending:
        return
    enemy.apply_status('poison', amount, source=p)


def after_poison(p):
    r = p.rules
    if r.powers.get('outbreak'):
        r.auxiliaries['outbreak'] += 1
        if r.auxiliaries['outbreak'] >= 3:
            push(p, ['silent_area_damage', r.powers['outbreak']], ['silent_outbreak_reset'])


def area_damage(p, amount):
    push(p, *[['silent_damage', i, amount] for i, e in enumerate(p.combat_enemies) if e.is_alive])


def enemy_side_tasks(p):
    # Capture the participant slots before side-start reactions can spawn enemies.
    return [['silent_poison_begin', i] for i, e in enumerate(p.combat_enemies) if e.is_alive and e.statuses.get('poison')]


def before_draw_power(p, key):
    from game.headless.core.snapshots import restore_card
    from game.headless.cards.special import clone_to
    from game.headless.cards.colorless_effects import catalog
    from game.headless.cards.silent_effects import shivs
    r = p.rules
    if key == 'infinite_blades' and r.powers.get(key):
        shivs(p, r.powers[key])
    elif key in r.nightmares:
        card = restore_card(r.nightmares.pop(key), catalog(p))
        for _ in range(r.powers.pop(key)):
            clone_to(p, card, 'hand')


def start_power(p, key):
    from game.headless.cards.silent_effects import shivs, choose
    r = p.rules
    amount = r.powers.get(key, 0)
    if not amount or p.combat_is_ending:
        return
    if key == 'tools_of_the_trade':
        choose(p, key, 'discard', amount)


def end_turn(p, key):
    r = p.rules
    if key == 'anticipate':
        r.powers['dexterity'] = r.powers.get('dexterity', 0) - r.powers.get(key, 0)
    if key == 'double_damage' and r.powers.get(key):
        r.powers[key] -= 1
    if key == 'corrosive_wave':
        from game.headless.core.draw_hooks import remove_power
        remove_power(p, key)
    elif key in ('anticipate', 'burst', 'shadowmeld'):
        r.powers.pop(key, None)


def selected(p, card, operation):
    if operation == 'hand_trick':
        card.combat_state.sly_this_turn = True
    elif operation == 'nightmare':
        from game.headless.core.snapshots import card_record
        key = f"nightmare:{p.rules.power_sequence}"
        p.rules.power_sequence += 1
        p.rules.powers[key] = 3
        p.rules.nightmares[key] = card_record(card)
    elif operation == 'well_laid_plans':
        card.combat_state.retain_this_turn = True
    else:
        raise ValueError('Unknown Silent selection.')


def execute(p, op, args):
    r = p.rules
    if op == 'silent_side_start_all':
        push(p, *[['silent_side_start', key] for key in r.powers if key in ('blur', 'shadow_step', 'noxious_fumes')])
    elif op == 'silent_side_start':
        key = args[0]
        amount = r.powers.get(key, 0)
        if key == 'wraith_form' and amount:
            from game.headless.powers.underdocks import stat_loss
            stat_loss(p, 'dexterity', amount)
        elif key == 'blur' and amount:
            r.powers[key] -= 1
        elif key == 'shadow_step' and amount:
            apply(p, 'double_damage', r.powers.pop(key))
        elif key == 'noxious_fumes' and amount:
            push(p, *[['status', i, 'poison', amount] for i, e in enumerate(p.combat_enemies) if e.is_alive])
    elif op == 'silent_area_damage':
        area_damage(p, args[0])
    elif op == 'silent_damage':
        enemy = p.combat_enemies[args[0]]
        if enemy.is_alive:
            enemy.take_damage(args[1], is_attack=False)
    elif op == 'silent_strangle':
        enemy = p.combat_enemies[args[0]]
        if enemy.is_alive:
            enemy.take_unblockable_damage(args[1])
    elif op == 'silent_outbreak_reset':
        r.auxiliaries['outbreak'] %= 3
    elif op == 'silent_poison_begin':
        e = p.combat_enemies[args[0]]
        count = min(e.statuses.get('poison'), 1 + r.powers.get('accelerant', 0))
        push(p, *[['silent_poison_tick', args[0]] for _ in range(count)])
    elif op == 'silent_poison_tick':
        e = p.combat_enemies[args[0]]
        if e.is_alive and e.statuses.get('poison'):
            push(p, ['silent_poison_decrement', args[0]])
            e.take_unblockable_damage(e.statuses.get('poison'))
    elif op == 'silent_poison_decrement':
        e = p.combat_enemies[args[0]]
        if e.is_alive:
            e.statuses.decrement('poison')
    elif op == 'silent_retain':
        from game.headless.cards.silent_effects import choose
        from game.headless.relics.combat import has
        if not r.powers.get('retain_hand') and not (r.round_number == 1 and has(p, 'ringing_triangle')):
            choose(p, 'well_laid_plans', 'well_laid_plans', r.powers.get('well_laid_plans', 0), optional=True)
    else:
        raise ValueError(f'Unknown Silent task: {op}')
