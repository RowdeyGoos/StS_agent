"""Ancient acquisitions expressed as owned data and shared deck mutations."""

from copy import deepcopy

SELECTIONS = {
    'astrolabe': ('astrolabe', 3, 3, '', 0),
    'beautiful_bracelet': ('enchant', 3, 3, 'swift', 3),
    'biiig_hug': ('remove', 4, 4, '', 0),
    'claws': ('maul', 0, 6, '', 0),
    'electric_shrymp': ('enchant', 1, 1, 'imbued', 1),
    'empty_cage': ('remove', 2, 2, '', 0),
    'paels_growth': ('enchant', 1, 1, 'clone', 4),
    'paels_tooth': ('store', 5, 5, '', 0),
    'preserved_fog': ('remove', 3, 3, '', 0),
    'tri_boomerang': ('enchant', 3, 3, 'instinct', 1),
    'yummy_cookie': ('upgrade', 4, 4, '', 0),
}


def upgrade_random(state, count):
    candidates = [c for c in state.deck if c.upgrade_level + 1 < len(c.definition.levels)]
    from game.headless.core.native_shuffle import sort_cards
    if getattr(state.rng, 'native', False):
        sort_cards(candidates)
    state.rng.shuffle('niche', candidates)
    for card in candidates[:count]:
        card.upgrade()


def replace_preserving(state, original, definition):
    from game.headless.cards.base import Card
    from game.headless.enchantments.base import can_enchant
    result = Card(definition, instance_id=state.allocate_card_id(),
                  upgrade_level=min(original.upgrade_level, len(definition.levels) - 1))
    if original.enchantment and can_enchant(result, original.enchantment.definition_id):
        result.enchantment = deepcopy(original.enchantment)
    state.deck.remove(original)
    state.deck.append(result)
    from game.headless.relics.run_rules import card_added
    card_added(state, result)
    return result


def begin(state, relic, cards):
    from game.headless.run.deck import add_card, transform_card
    from game.headless.run.inventory import add_relic, remove_relic, add_potion
    from game.headless.relics.run_rules import max_hp, counter
    from game.headless.relics.pickup import card_reward, relic_reward
    from game.headless.enchantments.base import can_enchant, enchant
    name, source = relic.definition_id, relic.instance_id
    grants = {'blood_soaked_rose': ('enthralled', 1), 'paels_horn': ('relax', 2),
              'jewelry_box': ('apotheosis', 1), 'storybook': ('brightest_flame', 1),
              'tanxs_whistle': ('whistle', 1)}
    if name in grants:
        definition, count = grants[name]
        for _ in range(count):
            add_card(state, cards.definition(definition))
    elif name == 'alchemical_coffer':
        from game.headless.potions.pools import generate_many
        state.potions.extend([None] * 4)
        state.potion_capacity += 4
        potions = generate_many(state.config.reward_potions if state.config else ('fire_potion','block_potion'), state.rng, 4, stream='combat_potion_generation')
        for index, potion in enumerate(potions, len(state.potions) - 4):
            add_potion(state, potion, slot=index)
    elif name == 'archaic_tooth':
        mapping = {'bash': 'break', 'neutralize': 'suppress', 'unleash': 'protector',
                   'falling_star': 'meteor_shower', 'dualcast': 'quadcast'}
        original = next((c for c in state.deck if c.definition.definition_id in mapping), None)
        if original:
            replace_preserving(state, original, cards.definition(mapping[original.definition.definition_id]))
    elif name == 'distinguished_cape':
        max_hp(state, -9)
        if state.hp:
            for _ in range(3):
                add_card(state, cards.definition('apparition'))
    elif name == 'dusty_tome':
        choices = [d for d in cards.definitions if d.pool == 'ironclad' and d.rarity == 'ancient' and d.definition_id != 'break']
        chosen = cards.definition(relic.data['card']) if 'card' in relic.data else state.rng.choice('rewards', choices)
        relic.data['card'] = chosen.definition_id
        add_card(state, chosen, upgrade_level=1)
    elif name == 'calling_bell':
        add_card(state, cards.definition('curse_of_the_bell'))
        for rarity in ('common', 'uncommon', 'rare'):
            relic_reward(state, source, rarity=rarity)
    elif name == 'toy_box':
        for _ in range(4):
            relic_reward(state, source)
    elif name == 'glass_eye':
        for rarity in ('common', 'common', 'uncommon', 'uncommon', 'rare'):
            card_reward(state, cards, source, rarity=rarity, is_card_reward=True)
    elif name in ('nutritious_soup', 'paels_claw'):
        enchantment = 'tezcataras_ember' if name == 'nutritious_soup' else 'goopy'
        for card in state.deck:
            eligible = card.definition.strike and card.definition.rarity == 'basic' if name == 'nutritious_soup' else card.definition.defend
            if eligible and can_enchant(card, enchantment):
                enchant(card, enchantment)
    elif name == 'pandoras_box':
        from game.headless.events.transformation import replacement_pool
        from game.headless.cards.pools import REWARD_CARDS
        for card in tuple(state.deck):
            if not card.spec.eternal and card.definition.rarity == 'basic' and (card.definition.strike or card.definition.defend):
                transform_card(state, cards, card.instance_id, replacement_pool(card.definition.definition_id, REWARD_CARDS), stream='niche')
    elif name == 'sand_castle':
        upgrade_random(state, 6)
    elif name == 'sea_glass':
        family = relic.data.setdefault('family', 'ironclad')
        offers = []
        for rarity in ('common', 'uncommon', 'rare'):
            card_reward(state, cards, source, rarity=rarity, count=5, is_card_reward=False, family=family, no_pool_changes=True)
            offers.extend(state.relic_work.pop()['offers'])
        state.relic_work.append(dict(source=source, kind='card_grid', offers=offers, selected=[]))
    elif name == 'sere_talon':
        from game.headless.cards.curses import MODIFIER_CURSES
        choices = sorted(MODIFIER_CURSES)
        for _ in range(2):
            chosen = state.rng.choice('niche', choices)
            choices.remove(chosen)
            add_card(state, cards.definition(chosen))
        for _ in range(3):
            add_card(state, cards.definition('wish'))
    elif name == 'touch_of_orobas':
        from game.headless.relics.base import RELICS
        starter = next((r for r in state.relics if RELICS[r.definition_id].rarity == 'starter'), None)
        if starter:
            index = state.relics.index(starter)
            remove_relic(state, starter.instance_id)
            replacement = add_relic(state, 'black_blood' if starter.definition_id == 'burning_blood' else 'circlet', cards=cards)
            state.relics.remove(replacement)
            state.relics.insert(index, replacement)
    elif name == 'pumpkin_candle':
        counter(state, relic, relic.counter + 5)
    else:
        return False
    return True


def selected(state, cards, work, card):
    from game.headless.run.deck import transform_card, remove_card
    if work['operation'] == 'astrolabe':
        from game.headless.events.transformation import replacement_pool
        from game.headless.cards.pools import REWARD_CARDS
        result = transform_card(state, cards, card.instance_id, replacement_pool(card.definition.definition_id, REWARD_CARDS), stream='niche')
        if result.upgrade_level + 1 < len(result.definition.levels):
            result.upgrade()
    elif work['operation'] == 'maul':
        replace_preserving(state, card, cards.definition('maul'))
    elif work['operation'] == 'store':
        from game.headless.core.snapshots import card_record
        relic = next(r for r in state.relics if r.instance_id == work['source'])
        relic.data.setdefault('cards', []).append(card_record(card))
        remove_card(state, card.instance_id)
    else:
        raise ValueError('Unknown ancient deck selection.')


def apply_grid(state, cards, action):
    from game.headless.run.actions import ChooseRelicReward
    work = state.relic_work[0]
    if isinstance(action, ChooseRelicReward):
        selected = work['selected']
        selected.remove(action.index) if action.index in selected else selected.append(action.index)
        return
    from game.headless.run.deck import add_card
    from game.headless.enchantments.base import restore
    state.relic_work.pop(0)
    for index in work['selected']:
        offer = work['offers'][index]
        add_card(state, cards.definition(offer['definition_id']), upgrade_level=offer['upgrade_level'],
                 enchantment=restore(offer['enchantment']))


def validate_grid(state, cards, work, name):
    from game.headless.relics.rewards import validate_modifiers
    if (name != 'sea_glass' or set(work) != {'kind','source','offers','selected'}
            or not isinstance(work['offers'], list) or len(work['offers']) != 15
            or not isinstance(work['selected'], list)
            or any(type(i) is not int or not 0 <= i < 15 for i in work['selected'])
            or len(set(work['selected'])) != len(work['selected'])):
        raise ValueError('Invalid Sea Glass selection.')
    family = next(r for r in state.relics if r.instance_id == work['source']).data['family']
    for index, offer in enumerate(work['offers']):
        if not isinstance(offer, dict) or set(offer) != {'definition_id','upgrade_level','enchantment'}:
            raise ValueError('Invalid Sea Glass card.')
        definition = cards.definition(offer['definition_id'])
        if definition.pool != family or definition.rarity != ('common','uncommon','rare')[index // 5]:
            raise ValueError('Sea Glass card differs from its pool.')
        validate_modifiers(cards, [definition.definition_id], {definition.definition_id: {k:v for k,v in offer.items() if k != 'definition_id'}})
    if len({o['definition_id'] for o in work['offers']}) != 15:
        raise ValueError('Repeated Sea Glass offer.')
