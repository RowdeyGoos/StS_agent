"""Encounter-owned reward outcomes, captured before combat state is released."""


def capture(encounter_id, enemies):
    if encounter_id == 'hive_thieving_hopper':
        from game.headless.monsters.hive_hopper import ThievingHopper
        hopper = next(e for e in enemies if isinstance(e, ThievingHopper))
        return dict(stolen=int(bool(hopper.stolen_id)), escaped=hopper.escaped, returned=hopper.loot_returned, card=hopper.stolen_id)
    if encounter_id != 'underdocks_gremlin_merc':
        return None
    from game.headless.monsters.underdocks_summons import GremlinMerc, FatGremlin
    merc = next(e for e in enemies if isinstance(e, GremlinMerc))
    fat = next((e for e in enemies if isinstance(e, FatGremlin)), None)
    return dict(stolen=merc.stolen_gold, escaped=bool(fat and fat.escaped),
                returned=bool(fat and fat.loot_returned))


def validate(encounter_id, record, cards):
    if record is None:
        if encounter_id in ('underdocks_gremlin_merc', 'hive_thieving_hopper'):
            raise ValueError('Merc rewards require their stolen-loot outcome.')
        return
    if encounter_id == 'hive_thieving_hopper':
        if not isinstance(record, dict) or set(record) != {'stolen', 'escaped', 'returned', 'card'}:
            raise ValueError('Invalid Hopper loot fields.')
        if record['card'] is not None:
            from game.headless.core.snapshots import restore_card
            from game.headless.core.card_state import CardState
            card = restore_card(record['card'], cards)
            if card.combat_state != CardState():
                raise ValueError('Stolen reward retains combat modifiers.')
        if record['stolen'] != int(record['card'] is not None):
            raise ValueError('Hopper loot marker differs from its card.')
        record = {k: v for k, v in record.items() if k != 'card'}
        encounter_id = 'underdocks_gremlin_merc'
    if (encounter_id != 'underdocks_gremlin_merc' or not isinstance(record, dict)
            or set(record) != {'stolen', 'escaped', 'returned'}
            or type(record['stolen']) is not int or record['stolen'] < 0
            or type(record['escaped']) is not bool or type(record['returned']) is not bool
            or record['escaped'] == record['returned']):
        raise ValueError('Invalid stolen-loot outcome.')


def gold_range(low, high, record):
    if record is None or 'card' in record or not record['escaped']:
        return low, high
    if record['stolen']:
        return 0, 0
    return round(low / 2), round(high / 2)


def returned_gold(record):
    return record['stolen'] if record is not None and record['returned'] and 'card' not in record else 0


def validate_rewards(state, rewards):
    record = (state.pending or {}).get('encounter_loot')
    amount = returned_gold(record)
    matches = [r for r in rewards if isinstance(r, dict) and r.get('source') == 'stolen_gold']
    if len(matches) != int(amount > 0):
        raise ValueError('Stolen gold reward count differs from outcome.')
    if matches:
        reward = matches[0]
        if reward['kind'] != 'gold' or reward['offers'] != ['stolen_gold'] or reward['modifiers'] != {'gold': amount} or type(reward['resolved']) is not bool:
            raise ValueError('Stolen gold reward differs from outcome.')
