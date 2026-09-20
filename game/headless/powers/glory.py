"""Glory card hooks keep afflictions, temporary upgrades and draw history owned."""


from game.headless.core.afflictions import afflict


def after_entry(player, card, *, generated=True):
    from game.headless.monsters.glory_normal import GlobeHead
    from game.headless.monsters.glory_bosses import Aeonglass
    for enemy in player.combat_enemies or ():
        if not enemy.is_alive: continue
        if getattr(enemy, 'hex_active', False): afflict(card, 'hexed')
        if isinstance(enemy, GlobeHead) and card.spec.kind == 'power': afflict(card, 'galvanized')
        if generated and isinstance(enemy, Aeonglass) and card.definition.definition_id == 'wither':
            card.combat_state.wither_level += enemy.wither_upgrades


def binding_owner(player):
    return next((e for e in player.combat_enemies or () if getattr(e, 'binding', False)), None)


def after_draw(player, card):
    owner = binding_owner(player)
    if owner is not None and player.rules.player_side and owner.bound_draws < 3 and afflict(card, 'bound'):
        owner.bound_draws += 1


def before_play(player, card):
    owner = binding_owner(player)
    if owner is not None and card.combat_state.bound and not card.combat_state.is_dupe:
        owner.bound_played = True


def can_play(player, card):
    owner = binding_owner(player)
    return not (card.combat_state.bound and owner is not None and owner.bound_played)


def clear_bound(player):
    owner = binding_owner(player)
    if owner is not None: owner.bound_played = False
    for card in player.deck.all_cards(): card.combat_state.bound = False


def validate(player):
    owner = binding_owner(player)
    if player.rules.powers.get('chains_of_binding', 0) != (3 if owner is not None else 0):
        raise ValueError('Unowned Chains of Binding power.')
    dampen = any(getattr(e, 'dampen_active', False) for e in player.combat_enemies)
    hexed = any(getattr(e, 'hex_active', False) for e in player.combat_enemies)
    wither_limit = sum(getattr(e, 'wither_upgrades', 0) for e in player.combat_enemies)
    for card in player.deck.all_cards():
        state = card.combat_state
        if state.bound and (owner is None or not owner.bound_draws) or state.hexed and not hexed or state.dampened_levels and not dampen:
            raise ValueError('Unowned Glory card effect.')
        if state.wither_level > wither_limit: raise ValueError('Wither upgrade exceeds its source history.')
        if state.wither_level and card.definition.definition_id != 'wither': raise ValueError('Wither upgrade belongs to another card.')
        if state.dampened_levels >= len(card.definition.levels): raise ValueError('Invalid saved Dampen upgrade level.')
        if sum(bool(getattr(state, n)) for n in ('smog', 'tainted', 'galvanized', 'hexed', 'bound')) > 1: raise ValueError('Conflicting Glory afflictions.')
