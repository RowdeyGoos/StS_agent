"""Transfer Hopper's exact permanent card between deck, theft and reward owners."""
from game.headless.core.card_state import CardState
from game.headless.core.snapshots import card_record, restore_card


def synchronize(state, player):
    held = {c.instance_id for c in state.stolen_cards}
    for enemy in player.combat_enemies:
        identity = getattr(enemy, 'stolen_id', '')
        if identity and identity not in held:
            card = next((c for c in state.deck if c.instance_id == identity), None)
            if card is None:
                raise ValueError('Stolen combat card has no permanent owner.')
            state.deck.remove(card)
            state.stolen_cards.append(card)
            held.add(identity)


def finish(state, record):
    if record is not None and 'card' in record:
        card = next((c for c in state.stolen_cards if c.instance_id == record['card']), None)
        if bool(card) != bool(record['card']):
            raise ValueError('Stolen card differs from combat outcome.')
        record['card'] = None if card is None else card_record(card)
    state.stolen_cards.clear()


def rewards(record):
    if record is None or not record.get('card') or not record['returned']:
        return []
    card = record['card']
    return [dict(source='stolen_card', kind='stolen_card', offers=[card['instance_id']], modifiers={'card': card}, resolved=False)]


def claim(state, cards, reward, identity):
    result = None
    if identity is not None:
        result = restore_card(reward['modifiers']['card'], cards)
        if any(c.instance_id == result.instance_id for c in state.deck):
            raise ValueError('Returned card already belongs to the deck.')
        state.deck.append(result)
        from game.headless.relics.run_rules import card_added
        card_added(state, result)
    reward['resolved'] = True
    return result


def validate_rewards(state, rows):
    record = (state.pending or {}).get('encounter_loot')
    expected = rewards(record)
    actual = [r for r in rows if isinstance(r, dict) and r.get('source') == 'stolen_card']
    if len(expected) != len(actual):
        raise ValueError('Stolen-card reward count differs from outcome.')
    for a, b in zip(actual, expected):
        if type(a.get('resolved')) is not bool or {**a, 'resolved': False} != b:
            raise ValueError('Stolen-card reward differs from its owner.')
        if not a['resolved'] and any(c.instance_id == a['offers'][0] for c in state.deck):
            raise ValueError('Unclaimed stolen card is already in the deck.')


def validate_run(state, combat):
    if combat is None:
        if state.stolen_cards:
            raise ValueError('Permanent stolen cards require an active combat owner.')
        return
    ids = [getattr(e, 'stolen_id', '') for e in combat.enemies if getattr(e, 'stolen_id', '')]
    if sorted(ids) != sorted(c.instance_id for c in state.stolen_cards):
        raise ValueError('Stolen permanent cards differ from combat ownership.')
    for card in state.stolen_cards:
        stolen = next(c for c in combat.player.deck.sequestered if c.instance_id == card.instance_id)
        if stolen.definition != card.definition:
            raise ValueError('Stolen card definition differs from its permanent version.')


def validate_combat(player):
    held = [getattr(e, 'stolen_id', '') for e in player.combat_enemies if getattr(e, 'stolen_id', '')]
    cards = player.deck.sequestered
    if (len(set(held)) != len(held) or sorted(held) != sorted(c.instance_id for c in cards)
            or not set(held) <= player.deck.original_ids):
        raise ValueError('Unowned sequestered combat card.')
