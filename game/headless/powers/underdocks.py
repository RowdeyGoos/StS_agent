"""Player-facing rules applied by Underdocks monsters."""


def stat_loss(player, name, amount):
    if player.statuses.get('artifact'):
        player.statuses.decrement('artifact')
        return
    if name == 'strength':
        player.strength -= amount
    else:
        player.rules.powers[name] = player.rules.powers.get(name, 0) - amount


def apply_smoggy(player):
    if player.statuses.get('artifact'):
        player.statuses.decrement('artifact')
        return
    player.rules.powers['smoggy'] = 1


def after_card(player, card):
    if player.rules.powers.get('smoggy') and card.spec.kind in ('skill', 'block'):
        player.rules.auxiliaries['smoggy.ready'] = 1
        for candidate in player.deck.all_cards():
            if candidate.spec.kind in ('skill', 'block'):
                candidate.combat_state.smog = True


def after_entry(player, card):
    if player.rules.powers.get('smoggy') and player.rules.auxiliaries.get('smoggy.ready') and card.spec.kind in ('skill', 'block'):
        card.combat_state.smog = True
