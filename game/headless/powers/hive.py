"""Player-facing Hive rules and serializable monster choices."""
NAMES = frozenset(('tender', 'tainted', 'disintegration', 'mind_rot', 'sloth', 'waste_away', 'surrounded'))


def debuff(p, name, amount):
    if p.statuses.get('artifact'):
        p.statuses.decrement('artifact')
        return
    p.rules.powers[name] = p.rules.powers.get(name, 0) + amount
    if name == 'tender':
        p.rules.auxiliaries.setdefault(name, 0)


def generate(p, name, pile, count, *, random_position=False):
    from game.headless.cards.colorless_effects import catalog
    from game.headless.core.piles import after_generated_entry
    from game.headless.core.native_rng import NativeRng
    for _ in range(count):
        card = catalog(p).create(name)
        p.deck._ensure_identity(card)
        destination = 'discard_pile' if pile == 'hand' and len(p.hand) >= 10 else pile
        cards = getattr(p.deck, destination)
        if random_position:
            position = p.deck.rng.randrange(len(cards) + 1)
            if destination == 'draw_pile' and isinstance(p.deck.rng, NativeRng):
                position = len(cards) - position
            cards.insert(position, card)
        else:
            cards.append(card)
        after_generated_entry(p, card)


def after_entry(p, card):
    if card.spec.kind in ('skill', 'block') and not card.combat_state.smog and any(e.is_alive and getattr(e, 'vital_spark', 0) for e in p.combat_enemies or ()):
        from game.headless.core.afflictions import afflict
        afflict(card, 'tainted')


def before_target(p, target):
    from game.headless.monsters.hive_bosses import CrabArm
    if p.rules.powers.get('surrounded') and isinstance(target, CrabArm):
        p.rules.auxiliaries['surrounded'] = target.SIDE


def damage_multiplier(p, source):
    from game.headless.monsters.hive_bosses import CrabArm
    if p.rules.powers.get('surrounded') and isinstance(source, CrabArm) and source.SIDE != p.rules.auxiliaries['surrounded']:
        return 3, 2
    return 1, 1


def after_card(p, card):
    if p.rules.powers.get('tender'):
        from game.headless.powers.underdocks import stat_loss
        p.rules.auxiliaries['tender'] += 1
        if p.is_alive and not p.combat_is_ending:
            stat_loss(p, 'strength', 1)
            stat_loss(p, 'dexterity', 1)


def after_end(p, name):
    if name == 'tender':
        count = p.rules.auxiliaries.get('tender', 0)
        if count and p.is_alive and not p.combat_is_ending:
            from game.headless.powers.ironclad import apply_power
            apply_power(p, 'strength', count)
            apply_power(p, 'dexterity', count)
        p.rules.auxiliaries['tender'] = 0


def player_end(p):
    if p.rules.powers.get('disintegration'):
        p.take_damage(p.rules.powers['disintegration'], is_attack=False)


def enemy_start(p):
    from game.headless.monsters.hive_bosses import TheInsatiable
    for enemy in p.combat_enemies:
        if isinstance(enemy, TheInsatiable) and enemy.is_alive and enemy.sandpit and p.is_alive:
            enemy.sandpit -= 1
            if enemy.sandpit == 0:
                # Native forced kill bypasses HP-loss prevention and resurrection.
                p.hp = 0
                from game.headless.core.orbs import clear
                clear(p)
                if p.rules.osty is not None:
                    p.rules.osty['hp'] = 0


def choose_knowledge(p, card):
    from game.headless.monsters.hive_bosses import KnowledgeDemon
    enemy = next(e for e in p.combat_enemies if isinstance(e, KnowledgeDemon) and e.choice_pending)
    name = card.definition.definition_id
    amount = 6 + enemy.curses_chosen if name == 'disintegration' else 3 if name == 'sloth' else 1
    debuff(p, name, amount)
    enemy.curses_chosen += 1
    enemy.choice_pending = False
    p.deck.offered.remove(card)


def validate_choice(r, p, s, *, deferred=False):
    from game.headless.monsters.hive_bosses import KnowledgeDemon
    progress = r.enemy_turn
    if deferred or progress is None or progress['move'] is None or progress['move']['stage'] != 'advance':
        raise ValueError('Knowledge choice requires its paused enemy move.')
    from game.headless.core.enemy_turn import current_slot
    slot = current_slot(progress)
    enemy = p.combat_enemies[slot]
    if (not isinstance(enemy, KnowledgeDemon) or not enemy.choice_pending or not 0 <= enemy.curses_chosen < 3
            or s['source'] != f"monster.{slot}" or s['destination'] != 'hand' or s['free'] != ''
            or s['minimum'] != 1 or s['maximum'] != 1 or 'whitelist' in s
            or s['candidates'] != [c.instance_id for c in p.deck.offered]
            or [c.definition.definition_id for c in p.deck.offered] != ['disintegration', enemy.CURSES[enemy.curses_chosen]]):
        raise ValueError('Invalid Knowledge Demon offers.')
