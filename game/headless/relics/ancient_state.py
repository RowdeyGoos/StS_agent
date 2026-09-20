"""Persistent Ancient state, lifecycle effects and continuation validation."""

from copy import deepcopy


def validate_data(name, values):
    if not isinstance(values, dict):
        raise ValueError('Invalid persistent relic data.')
    data = dict(values)
    for flag in ('_wax', '_melted'):
        if flag in data and data.pop(flag) is not True:
            raise ValueError('Invalid wax relic flag.')
    if values.get('_melted') and not values.get('_wax'):
        raise ValueError('Only wax relics may melt.')
    if name == 'paels_tooth' and 'cards' in data:
        from game.headless.core.snapshots import restore_card
        from game.headless.core.card_state import CardState
        from dataclasses import asdict
        records = data.pop('cards')
        if not isinstance(records, list) or len(records) > 5:
            raise ValueError('Invalid stored cards.')
        identities = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError('Invalid stored card.')
            card = restore_card(record)
            if card.spec.eternal or card.upgrade_level + 1 >= len(card.definition.levels) or record['combat_state'] != asdict(CardState()):
                raise ValueError('Ineligible stored card.')
            identities.append(card.instance_id)
        if len(set(identities)) != len(identities):
            raise ValueError('Repeated stored card.')
    if name == 'dusty_tome' and 'card' in data:
        from game.headless.cards.catalog import DEFAULT_CARDS
        card = DEFAULT_CARDS.definition(data.pop('card'))
        if card.pool != 'ironclad' or card.rarity != 'ancient' or card.definition_id == 'break':
            raise ValueError('Invalid Dusty Tome card.')
    if name == 'sea_glass' and 'family' in data:
        if data.pop('family') not in ('ironclad', 'silent', 'regent', 'necrobinder', 'defect'):
            raise ValueError('Invalid Sea Glass family.')
    if name in ("fur_coat", "golden_compass") and "act" in data:
        if type(data["act"]) is not int or data.pop("act") not in (1, 2, 3):
            raise ValueError("Invalid Ancient act ownership.")
    if name == "fur_coat" and "coordinates" in data:
        coordinates = data.pop("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) > 7 or any(not isinstance(c, list) or len(c) != 2 or any(type(v) is not int or v < 0 for v in c) for c in coordinates) or len({tuple(c) for c in coordinates}) != len(coordinates):
            raise ValueError("Invalid Fur Coat coordinates.")
    return data


def validate_task(rules, op, args):
    if op == 'ancient_preplay':
        if not rules.player_side:
            raise ValueError('Ancient setup outside the player turn.')
        return
    expected = 'whispering_earring' if op == 'ancient_earring' else 'toasty_mittens'
    relic = next((r for r in rules.relics if r['instance_id'] == args[0]), None)
    if relic is None or relic['definition_id'] != expected or relic['data'].get('_melted'):
        raise ValueError('Unowned Ancient continuation.')
    if op == 'ancient_earring' and (type(args[1]) is not int or not 0 <= args[1] <= 13 or rules.round_number != 1):
        raise ValueError('Invalid Whispering Earring continuation.')


def auto_select(p):
    from game.headless.relics.combat import owned, memory
    relic = owned(p, 'whispering_earring')
    if not relic or not memory(p, relic).get('active'):
        return False
    if p.rules.selection is not None:
        from game.headless.core.choices import confirm
        s = p.rules.selection
        s['selected'] = s['candidates'][:s['maximum']]
        confirm(p)
    elif p.pending_play is not None:
        card = p.current_card
        effect = card.definition.effects[p.pending_play.effect_index]
        options = effect.eligible(p)
        p.pending_play = None
        if options:
            effect.resolve(p, options[0])
    else:
        return False
    return True


def sync_cards(state, p):
    combat = {c.instance_id:c for c in p.deck.all_cards()}
    for card in state.deck:
        version = combat.get(card.instance_id)
        if card.enchantment and card.enchantment.definition_id == 'goopy' and version and version.enchantment and version.enchantment.definition_id == 'goopy':
            card.enchantment.amount = version.enchantment.amount


def after_combat(state, cards, *, elite=False, relics=None):
    from game.headless.relics.run_rules import counter
    from game.headless.run.deck import add_card
    listeners = tuple(r for r in state.relics if not r.data.get('_melted')) if relics is None else relics
    for relic in listeners:
        name = relic.definition_id
        if name == 'pumpkin_candle':
            counter(state, relic, max(0, relic.counter - 1))
        elif name == 'paels_tooth' and state.hp and relic.data.get('cards'):
            from game.headless.core.snapshots import restore_card
            record = state.rng.choice('rewards', relic.data['cards'])
            saved = restore_card(record, cards)
            saved.upgrade()
            card = add_card(state, saved.definition, upgrade_level=saved.upgrade_level)
            card.enchantment = deepcopy(saved.enchantment)
            card.permanent_damage, card.permanent_block = saved.permanent_damage, saved.permanent_block
            relic.data['cards'].remove(record)
        elif name == 'toy_box':
            counter(state, relic, relic.counter + 1)
            if (relic.counter + 1) % 3 == 0:
                wax = next((r for r in state.relics if r.data.get('_wax') and not r.data.get('_melted')), None)
                if wax:
                    wax.data['_melted'] = True
