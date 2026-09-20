"""Doom and Necrobinder powers at the shared combat lifecycle boundaries."""

from game.headless.core.resolution import push, move_out
from game.headless.core import osty

NAMES = frozenset(('forbidden_grimoire', 'borrowed_time', 'calcify', 'call_of_the_void', 'countdown',
    'danse_macabre', 'demesne', 'devour_life', 'friendship', 'haunt', 'lethality',
    'necro_mastery', 'neurosurge', 'pagestorm', 'reaper_form', 'sentry_mode',
    'shroud', 'sleight_of_flesh', 'spirit_of_ash', 'summon_next_turn', 'veilpiercer', 'intangible'))
ENEMY_DEBUFFS = ('doom', 'debilitate', 'enfeebling_touch', 'hang', 'oblivion', 'sic_em')
TEMP_STRENGTH = ('mangle', 'dark_shackles', 'crush_under', 'dying_star', 'monarchs_gaze_strength_down', 'enfeebling_touch')


def apply(p, key, amount):
    p.rules.powers[key] = p.rules.powers.get(key, 0) + amount
    if key == 'summon_next_turn':
        p.rules.auxiliaries.setdefault(key, 0)


def copied_debuffs(enemy):
    keys = ('weak', 'vulnerable', 'frail', 'slow', 'constrict', 'tangled', 'ringing',
            'shrink', 'demise', 'poison', 'strangle', 'conqueror', *ENEMY_DEBUFFS, *TEMP_STRENGTH)
    values = {k: enemy.statuses.get(k) for k in dict.fromkeys(keys) if enemy.statuses.get(k)}
    # Temporary wrappers carry a separate negative Strength power in native.
    strength = enemy.strength - sum(enemy.statuses.get(k) for k in TEMP_STRENGTH)
    if strength < 0:
        values['strength'] = strength
    return values


def before_play(p, card):
    r = p.rules
    r.plays[card.instance_id]['nec_banshees'] = []
    r.plays[card.instance_id]['nec_before'] = {str(i): e.statuses.get('oblivion') for i, e in enumerate(p.combat_enemies or ()) if e.is_alive and e.statuses.get('oblivion')}
    r.plays[card.instance_id]['nec_first_attack'] = card.spec.kind == 'attack' and r.attacks_started == 1
    for key, amount in tuple(r.powers.items()):
        if key == 'danse_macabre' and (r.plays[card.instance_id]['x'] if card.spec.x_cost else p.card_cost(card)) >= 2:
            p.gain_block(amount)
        elif key == 'spirit_of_ash' and card.spec.ethereal:
            p.gain_block(amount)
        elif key == 'veilpiercer' and amount and card.spec.ethereal:
            r.powers[key] -= 1


def after_card_power(p, card, key):
    amount = p.rules.powers.get(key, 0)
    if card.definition.definition_id != 'soul' or not amount:
        return
    if key == 'devour_life':
        osty.summon(p, amount)
    elif key == 'haunt':
        living = [i for i, e in enumerate(p.combat_enemies) if e.is_alive]
        if living:
            push(p, ['nec_enemy_loss', p.deck.target_rng.choice(living), amount, True, key])


def after_enemies(p, card):
    captured = p.rules.plays[card.instance_id]['nec_before']
    push(p, *[['status', int(slot), 'doom', amount] for slot, amount in captured.items()])


def after_card(p, card):
    r = p.rules
    for identity in r.plays[card.instance_id]['nec_banshees']:
        other = next((c for c in p.deck.all_cards() if c.instance_id == identity), None)
        if other is not None:
            other.combat_state.combat_cost_change -= 2
    if r.plays[card.instance_id]['energy_value'] >= 2:
        for other in tuple(p.deck.discard_pile):
            if other.definition.definition_id == 'right_hand_hand':
                move_out(p, other)
                (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(other)


def entered(p, card, *, is_clone=False):
    if card.definition.definition_id == 'banshees_cry' and not is_clone:
        card.combat_state.combat_cost_change -= 2 * p.rules.ethereal_plays
    if card.definition.definition_id == 'flatten' and p.rules.osty_attacks_turn:
        v = card.combat_state
        v.turn_cost_override = 0
        from game.headless.core.card_costs import mark_setter
        mark_setter(v, 'turn')
        v.turn_cost_until_played = False
        v.override_turn_baseline = v.turn_cost_change
        v.override_combat_baseline = v.combat_cost_change


def after_draw(p, card):
    if card.spec.ethereal and p.rules.powers.get('pagestorm'):
        push(p, ['draw', p.rules.powers['pagestorm'], False])


def start_turn(p, draw_count):
    r = p.rules
    r.osty_attacks_turn = r.drawn_turn = 0
    r.doom_applied_turn = False
    r.fetch_plays.clear()
    if 'summon_next_turn' in r.powers:
        r.auxiliaries['summon_next_turn'] = int(r.powers['summon_next_turn'] > 0)
    return draw_count + r.powers.get('demesne', 0)


def after_status(p, enemy, name, amount, *, temporary_copy=False):
    tasks = []
    if name == 'doom' and amount:
        p.rules.doom_applied_turn = True
    for key, value in p.rules.powers.items():
        if key == 'shroud' and name == 'doom':
            tasks.append(['block', value, False])
        elif key == 'sleight_of_flesh' and amount and (name not in TEMP_STRENGTH or not temporary_copy):
            tasks.append(['nec_enemy_loss', p.combat_enemies.index(enemy), value, False, key])
    push(p, *tasks)


def after_death(p):
    for card in p.deck.all_cards():
        if card not in p.deck.offered and card.definition.definition_id == 'melancholy':
            card.combat_state.combat_cost_change -= 1


def damage_multiplier(p, card):
    if card is not None and p.rules.plays.get(card.instance_id, {}).get('nec_first_attack'):
        return 100 + p.rules.powers.get('lethality', 0), 100
    return 1, 1


def doom_tasks(p, *, source='enemy_end'):
    slots = [i for i, e in enumerate(p.combat_enemies) if e.is_alive and e.hp <= e.statuses.get('doom')]
    from game.headless.relics.combat import has
    return ([['nec_doom_kill', i, source] for i in slots]
            + ([['nec_doom_after', slots, source]] if slots and has(p, 'book_repair_knife') else []))


def end_player(p):
    p.rules.powers.pop('borrowed_time', None)
    for e in p.combat_enemies:
        e.statuses.decrement('oblivion', e.statuses.get('oblivion'))


def execute(p, op, args):
    r = p.rules
    if op == 'nec_enemy_loss':
        e = p.combat_enemies[args[0]]
        if e.is_alive:
            e.take_unblockable_damage(args[1]) if args[2] else e.take_damage(args[1], is_attack=False)
    elif op == 'nec_summon':
        osty.summon(p, args[0])
    elif op == 'nec_kill_osty':
        osty.kill(p)
    elif op == 'nec_doom_kill':
        e = p.combat_enemies[args[0]]
        if e.is_alive:
            previous = e.hp
            e.hp = 0
            e._after_damage(previous, False)
    elif op == 'nec_doom_after':
        from game.headless.relics.combat import has, heal
        if has(p, 'book_repair_knife'):
            from game.headless.monsters.hive_elites import DecimillipedeSegment
            # Native asks the remaining powers after the complete kill batch.
            # Illusion itself does not suppress AfterDiedToDoom's Fatal count.
            victims = [p.combat_enemies[i] for i in args[0]]
            heal(p, 3 * sum(not e.statuses.get('minion') and
                           (not isinstance(e, DecimillipedeSegment) or e.allows_fatal) for e in victims))
    elif op == 'nec_player_doom':
        if p.is_alive and p.hp <= p.statuses.get('doom'):
            p.hp = 0
            from game.headless.potions.combat import prevent_death as fairy
            from game.headless.relics.damage import prevent_death
            fairy(p)
            prevent_death(p)
            if not p.is_alive:
                from game.headless.core.orbs import clear
                clear(p)
                if r.osty is not None:
                    r.osty['hp'] = 0
    elif op == 'nec_side_start':
        key = args[0]
        if key == 'countdown':
            living = [i for i, e in enumerate(p.combat_enemies) if e.is_alive]
            if living:
                push(p, ['status', p.deck.target_rng.choice(living), 'doom', r.powers[key]])
        elif key == 'neurosurge':
            if p.statuses.get('artifact'):
                p.statuses.decrement('artifact')
            else:
                p.apply_status('doom', r.powers[key])
                r.doom_applied_turn = True
                if r.powers.get('shroud'):
                    p.gain_block(r.powers['shroud'])
    elif op == 'nec_start':
        if r.auxiliaries.get('summon_next_turn'):
            amount = r.powers.pop('summon_next_turn')
            r.auxiliaries.pop('summon_next_turn')
            osty.summon(p, amount)
    elif op == 'nec_before_draw':
        from game.headless.cards.colorless_effects import create, catalog, pool
        from game.headless.generation.combat import select_cards
        key = args[0]
        for _ in range(r.powers.get(key, 0)):
            if key == 'sentry_mode':
                create(p, catalog(p).definition('sweeping_gaze'))
            elif key == 'call_of_the_void':
                selected = select_cards(pool(p, 'ironclad'), p.deck.generation_rng, 1, distinct=True)
                for definition in selected:
                    c = create(p, definition, destination='offered')
                    c.combat_state.ethereal_this_combat = True
                    move_out(p, c)
                    (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(c)
                    from game.headless.core.piles import after_generated_entry
                    after_generated_entry(p, c)
    else:
        raise ValueError(f'Unknown Necrobinder task: {op}')


def finished_history(p, card):
    if card.definition.definition_id == 'fetch' and card.instance_id not in p.rules.fetch_plays:
        p.rules.fetch_plays.append(card.instance_id)
    if card.spec.ethereal:
        p.rules.ethereal_plays += 1
        p.rules.plays[card.instance_id]['nec_banshees'] = [c.instance_id for c in p.deck.all_cards() if c not in p.deck.offered and c.definition.definition_id == 'banshees_cry']


def lose_strength(p, amount, target=None):
    from game.headless.relics.damage import debuff_amount
    target = p if target is None else target
    amount = debuff_amount(p, p.current_card, amount)
    if target.statuses.get('artifact'):
        target.statuses.decrement('artifact')
    elif amount:
        target.strength -= amount
        if target is not p:
            after_status(p, target, 'strength', amount)
