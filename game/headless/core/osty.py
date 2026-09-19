"""The player's owned pet; dead Osty retains identity until combat ends."""

from game.headless.core.resolution import push


def alive(p):
    return p.rules.osty is not None and p.rules.osty['hp'] > 0


def summon(p, amount):
    if amount <= 0 or p.combat_is_ending:
        return
    r = p.rules
    if r.osty is None:
        r.osty = {'hp': amount, 'max_hp': amount}
    elif alive(p):
        r.osty['max_hp'] += amount
        r.osty['hp'] += amount
    else:
        r.osty.update(hp=amount, max_hp=amount)


def heal(p, amount):
    if alive(p):
        p.rules.osty['hp'] = min(p.rules.osty['max_hp'], p.rules.osty['hp'] + amount)


def lose_hp(p, amount):
    if not alive(p):
        return 0
    actual = min(amount, p.rules.osty['hp'])
    p.rules.osty['hp'] -= actual
    if actual and p.rules.powers.get('necro_mastery'):
        push(p, *[['nec_enemy_loss', i, actual * p.rules.powers['necro_mastery'], True, 'necro_mastery']
                  for i, e in enumerate(p.combat_enemies) if e.is_alive])
    if actual and not alive(p):
        from game.headless.powers.necrobinder import after_death
        after_death(p)
    return actual


def take_damage(p, amount):
    """Unpowered damage addressed to Osty uses shared Block, with no overflow."""
    if not alive(p):
        return 0
    blocked = min(p.block, amount)
    p.block -= blocked
    return lose_hp(p, amount - blocked)


def kill(p):
    if alive(p):
        lose_hp(p, p.rules.osty['hp'])


def after_attack(p):
    p.rules.osty_attacks_turn += 1
    for card in p.deck.all_cards():
        if card not in p.deck.offered and card.definition.definition_id == 'flatten':
            v = card.combat_state
            v.turn_cost_override = 0
            from game.headless.core.card_costs import mark_setter
            mark_setter(v, 'turn')
            v.turn_cost_until_played = False
            v.override_turn_baseline = v.turn_cost_change
            v.override_combat_baseline = v.combat_cost_change
