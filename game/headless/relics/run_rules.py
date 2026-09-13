"""Shared run mutations used by relics and every card/gold acquisition source."""

from dataclasses import replace


def owned(state, name):
    return next((r for r in state.relics if r.definition_id == name), None)


def has(state, name):
    return owned(state, name) is not None


def counter(state, relic, value):
    replacement = replace(relic, counter=value)
    state.relics[state.relics.index(relic)] = replacement
    return replacement


def heal(state, amount):
    if state.hp > 0:
        state.hp = min(state.max_hp, state.hp + max(0, amount))


def max_hp(state, amount):
    target = state.max_hp + amount
    if amount < 0 and state.hp > target:
        damage(state, state.hp - target)
    state.max_hp = max(1, target)
    state.hp = min(state.max_hp, state.hp + max(0, amount)) if state.hp > 0 else 0


def gain_gold(state, amount):
    amount = max(0, amount)
    if has(state, "bowler_hat"):
        amount = amount * 5 // 4
    state.gold += amount
    if amount and has(state, "dragon_fruit"):
        max_hp(state, 1)
    return amount


def modify_new_card(state, card, *, only=None):
    eggs = {"attack": "molten_egg", "skill": "toxic_egg", "block": "toxic_egg", "power": "frozen_egg"}
    for relic in state.relics:
        if only is not None and relic.instance_id != only:
            continue
        if relic.definition_id == eggs.get(card.spec.kind) and card.upgrade_level + 1 < len(
            card.definition.levels
        ):
            card.upgrade()
        if relic.definition_id == "fresnel_lens":
            from game.headless.enchantments.base import can_enchant, enchant

            if can_enchant(card, "nimble"):
                enchant(card, "nimble", 2)
    return card


def card_added(state, card):
    modify_new_card(state, card)
    after_card_added(state)


def after_card_added(state):
    for relic in tuple(state.relics):
        if relic.definition_id == "book_of_five_rings":
            value = (relic.counter + 1) % 5
            counter(state, relic, value)
            if value == 0:
                heal(state, 20)
        elif relic.definition_id == "lucky_fysh":
            gain_gold(state, 15)


def entered_room(state, kind, *, unknown=False):
    for relic in tuple(state.relics):
        name = relic.definition_id
        if name == "meal_ticket" and kind == "shop":
            heal(state, 15)
        elif name == "eternal_feather" and kind == "rest":
            heal(state, 3 * (len(state.deck) // 5))
        elif name == "pantograph" and kind == "boss":
            heal(state, 25)
        elif name == "planisphere" and unknown:
            heal(state, 5)
        elif name == "venerable_tea_set" and kind == "rest":
            counter(state, relic, 1)


def victory(state, *, room_kind="combat"):
    # Early victory healing precedes ordinary Burning Blood irrespective of inventory order.
    if has(state, "meat_on_the_bone") and state.hp * 2 <= state.max_hp:
        heal(state, 12)
    for relic in tuple(state.relics):
        if relic.definition_id == "lasting_candy":
            counter(state, relic, (relic.counter + 1) % 2)
        elif relic.definition_id == "fishing_rod" and room_kind == "combat":
            value = (relic.counter + 1) % 3
            counter(state, relic, value)
            if value == 0:
                eligible = [c for c in state.deck if c.upgrade_level + 1 < len(c.definition.levels)]
                if eligible:
                    state.rng.choice("relic.fishing_upgrade", eligible).upgrade()
        elif relic.definition_id == "chosen_cheese":
            max_hp(state, 1)


def pickup(state, relic, cards):
    name = relic.definition_id
    if name == "lees_waffle":
        heal(state, state.max_hp)
    elif name == "potion_belt":
        state.potions.extend([None, None])
        state.potion_capacity += 2
    elif name in ("war_paint", "whetstone"):
        kinds = ("attack",) if name == "whetstone" else ("skill", "block")
        choices = [
            c for c in state.deck if c.spec.kind in kinds and c.upgrade_level + 1 < len(c.definition.levels)
        ]
        state.rng.shuffle("relic.pickup", choices)
        for card in choices[:2]:
            card.upgrade()
    else:
        from game.headless.relics.pickup import begin

        begin(state, relic, cards)


def damage(state, amount):
    if has(state, "tungsten_rod"):
        amount = max(0, amount - 1)
    previous = state.hp
    state.hp = max(0, state.hp - amount)
    from game.headless.potions.use import prevent_death
    prevent_death(state)
    tail = owned(state, "lizard_tail")
    if not state.hp and tail is not None and not tail.counter:
        counter(state, tail, 1)
        state.hp = max(1, state.max_hp // 2)
    return max(0, previous - state.hp)


def rest_rewards(state):
    if has(state, "stone_humidifier"):
        max_hp(state, 5)
    if has(state, "tiny_mailbox"):
        from game.headless.relics.pickup import potion_reward

        potion_reward(state, owned(state, "tiny_mailbox").instance_id)
