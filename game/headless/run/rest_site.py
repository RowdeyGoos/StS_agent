"""Ordinary rest healing and cancelable single-card smithing."""

from game.headless.run.deck import upgrade_card
from game.headless.run.state import RunPhase
from game.headless.relics.run_rules import has, owned, counter, max_hp


def begin_rest_site(state) -> None:
    state.require_room_entry("rest")
    if state.pending is None:
        from game.headless.relics.run_rules import entered_room
        entered_room(state, "rest")
    state.pending = {"kind": "rest_site", "stage": "options", "used": []}
    state.phase = RunPhase.ROOM


def eligible_upgrades(state) -> tuple[str, ...]:
    return tuple(c.instance_id for c in state.deck if c.upgrade_level + 1 < len(c.definition.levels))


def _pending(state, stage):
    if state.phase is not RunPhase.ROOM or not state.pending or state.pending.get("kind") != "rest_site" or (state.pending.get("stage") != stage and not (stage == "options" and state.pending.get("stage") == "hatched" and has(state, "miniature_tent"))):
        raise ValueError("Rest-site action is unavailable.")
    return state.pending


def heal_amount(state) -> int:
    return min(state.max_hp * 3 // 10 + (15 if has(state, "regal_pillow") else 0), state.max_hp - state.hp)


def heal(state) -> int:
    pending = _pending(state, "options")
    if "rest" in pending["used"]:
        raise ValueError("Rest was already used here.")
    amount = heal_amount(state)
    state.hp += amount
    complete(state, "rest")
    if has(state, "stone_humidifier"):
        max_hp(state, 5)
    if has(state, "tiny_mailbox"):
        from game.headless.relics.pickup import potion_reward
        potion_reward(state, owned(state, "tiny_mailbox").instance_id)
    return amount


def begin_smith(state) -> None:
    pending = _pending(state, "options")
    if "smith" in pending["used"]:
        raise ValueError("Smithing was already used here.")
    choices = eligible_upgrades(state)
    if not choices:
        raise ValueError("No supported card can be upgraded.")
    state.pending = {"kind": "rest_site", "stage": "smith", "used": pending["used"], "eligible": list(choices)}


def choose_upgrade(state, instance_id: str | None):
    pending = _pending(state, "smith")
    if instance_id is None:
        state.pending = {"kind": "rest_site", "stage": "options", "used": pending["used"]}
        return None
    if instance_id not in pending["eligible"] or instance_id not in eligible_upgrades(state):
        raise ValueError("Card is not eligible for this upgrade choice.")
    card = upgrade_card(state, instance_id)
    complete(state, "smith")
    return card


def leave(state) -> None:
    if state.pending and state.pending.get("stage") == "options" and has(state, "miniature_tent") and state.pending["used"]:
        _pending(state, "options")
    else:
        _pending(state, "hatched" if state.pending and state.pending.get("stage") == "hatched" else "resolved")
    state.pending = None
    state.phase = RunPhase.ROUTE


def complete(state, option):
    used = [*state.pending["used"], option]
    state.pending = {"kind": "rest_site", "stage": "options" if has(state, "miniature_tent") else "resolved", "used": used}


def lift(state):
    pending = _pending(state, "options")
    relic = owned(state, "girya")
    if relic is None or relic.counter >= 3 or "lift" in pending["used"]:
        raise ValueError("Lifting is unavailable.")
    counter(state, relic, relic.counter + 1)
    complete(state, "lift")


def dig(state):
    pending = _pending(state, "options")
    relic = owned(state, "shovel")
    if relic is None or "dig" in pending["used"]:
        raise ValueError("Digging is unavailable.")
    from game.headless.relics.pickup import relic_reward
    relic_reward(state, relic.instance_id)
    complete(state, "dig")


ANCIENT_OPTIONS = {'cook': 'meat_cleaver', 'clone': 'paels_growth', 'kindle': 'pumpkin_candle'}


def ancient_actions(state):
    from game.headless.run.actions import UseRestRelic, ChooseCookCard, ConfirmCook
    pending = state.pending
    if pending['stage'] == 'cook':
        selected = pending['selected']
        actions = [ChooseCookCard(None)]
        actions += [ChooseCookCard(i) for i in pending['eligible'] if i in selected or len(selected) < 2]
        if len(selected) == 2:
            actions.append(ConfirmCook())
        return actions
    if pending['stage'] not in ('options', 'hatched') or pending['stage'] == 'hatched' and not has(state, 'miniature_tent'):
        return []
    return [UseRestRelic(option) for option, name in ANCIENT_OPTIONS.items()
            if has(state, name) and option not in pending['used']
            and (option != 'cook' or sum(not c.spec.eternal for c in state.deck) >= 2)]


def use_ancient(state, cards, option):
    pending = _pending(state, 'options')
    if option not in ANCIENT_OPTIONS or not has(state, ANCIENT_OPTIONS[option]) or option in pending['used']:
        raise ValueError('Ancient rest action is unavailable.')
    if option == 'cook':
        eligible = [c.instance_id for c in state.deck if not c.spec.eternal]
        if len(eligible) < 2:
            raise ValueError('Cooking needs two removable cards.')
        pending.update(stage='cook', eligible=eligible, selected=[])
        return
    if option == 'kindle':
        relic = owned(state, 'pumpkin_candle')
        counter(state, relic, relic.counter + 5)
    elif option == 'clone':
        from game.headless.run.deck import add_card
        from copy import deepcopy
        for card in tuple(state.deck):
            if card.enchantment and card.enchantment.definition_id == 'clone':
                clone = add_card(state, card.definition, upgrade_level=card.upgrade_level)
                clone.enchantment = deepcopy(card.enchantment)
                clone.permanent_damage, clone.permanent_block = card.permanent_damage, card.permanent_block
    complete(state, option)


def cook_choice(state, action):
    from game.headless.run.actions import ChooseCookCard
    pending = _pending(state, 'cook')
    if isinstance(action, ChooseCookCard):
        if action.instance_id is None:
            state.pending = dict(kind='rest_site', stage='options', used=pending['used'])
            return
        selected = pending['selected']
        if action.instance_id not in pending['eligible'] or action.instance_id not in selected and len(selected) == 2:
            raise ValueError('Invalid cooking card.')
        selected.remove(action.instance_id) if action.instance_id in selected else selected.append(action.instance_id)
        return
    if len(pending['selected']) != 2:
        raise ValueError('Cooking requires exactly two cards.')
    from game.headless.run.deck import remove_card
    for identity in pending['selected']:
        remove_card(state, identity)
    max_hp(state, 9)
    complete(state, 'cook')


def validate_cook(state):
    pending = state.pending
    if (not has(state, 'meat_cleaver') or 'cook' in pending['used']
            or set(pending) != {'kind','stage','used','eligible','selected'}
            or pending['eligible'] != [c.instance_id for c in state.deck if not c.spec.eternal]
            or len(pending['eligible']) < 2 or not isinstance(pending['selected'], list)
            or len(pending['selected']) > 2 or len(set(pending['selected'])) != len(pending['selected'])
            or not set(pending['selected']) <= set(pending['eligible'])):
        raise ValueError('Invalid cooking selection.')
