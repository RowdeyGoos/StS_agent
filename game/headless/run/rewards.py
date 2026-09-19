"""Reduced reward game rules, callable without a protocol adapter."""

from game.headless.run.deck import add_card
from game.headless.run.state import RunPhase
from game.headless.run.inventory import add_potion, add_relic
from game.headless.encounters.catalog import ENCOUNTERS


def _begin_reward(state, cards, *, gold: int, card_ids, offer_count: int = 3, decorate_cards=True, native_kind="combat") -> None:
    state.require_between_rooms()
    if type(gold) is not int or gold < 0 or type(offer_count) is not int or offer_count <= 0:
        raise ValueError("Invalid reward parameters.")
    from game.headless.relics.rewards import extend_pool, decorate
    pool = extend_pool(state, cards, card_ids)
    if len(pool) != len(set(pool)) or not pool:
        raise ValueError("Reward cards must be a nonempty distinct pool.")
    for card_id in pool:
        cards.definition(card_id)
    upgraded=[]
    if getattr(state.rng, "native", False):
        from game.headless.generation.odds import card_offers
        pool, upgraded = card_offers(state, cards, pool, offer_count, kind=native_kind)
    else:
        state.rng.shuffle("reward_offer", pool)
    state.pending = {"kind": "reward", "gold": gold, "gold_claimed": False,
                     "offers": pool[:offer_count], "card_resolved": False,
                     "card_modifiers": decorate(state, cards, pool[:offer_count], upgraded=upgraded) if decorate_cards else {}}
    state.phase = RunPhase.REWARD
    return upgraded


def claim_gold(state) -> int:
    reward = _reward(state)
    if reward["gold_claimed"]:
        raise ValueError("Gold reward was already claimed.")
    from game.headless.relics.run_rules import gain_gold
    gain_gold(state, reward["gold"])
    reward["gold_claimed"] = True
    return reward["gold"]


def choose_card(state, cards, definition_id: str | None):
    reward = _reward(state)
    if reward["card_resolved"] or (definition_id is not None and definition_id not in reward["offers"]):
        raise ValueError("Card reward choice is unavailable.")
    card = None if definition_id is None else acquire_card(state, cards, definition_id, reward["card_modifiers"])
    reward["card_resolved"] = True
    return card


def finish_reward(state) -> None:
    reward = _reward(state)
    if not reward["gold_claimed"] or not reward["card_resolved"]:
        raise ValueError("Resolve rewards before proceeding.")
    state.pending = None
    state.phase = RunPhase.ROUTE


def _reward(state):
    if state.phase is not RunPhase.REWARD or not state.pending or state.pending.get("kind") != "reward":
        raise ValueError("No reward is active.")
    return state.pending


def eligible_relics(state):
    owned = {r.definition_id for r in state.relics}
    pool = tuple(r for r in state.config.reward_relics if r not in owned)
    return pool or ((state.config.relic_fallback,) if state.config.relic_fallback else ())


def _begin_combat_rewards(state, cards, *, encounter_id=None, undamaged=False, extra_cards=0, royalties=0, encounter_loot=None) -> None:
    """A0 encounter amounts with explicitly restricted, project-sampled pools.

    Draw once on entry. Reading choices and restoring a pending reward never
    rerolls it. Named Python streams do not reproduce native seeds/draw order.
    """
    state.require_between_rooms()
    if type(royalties) is not int or royalties < 0:
        raise ValueError("Invalid earned Royalties gold.")
    if type(extra_cards) is not int or extra_cards < 0:
        raise ValueError("Invalid earned card reward count.")
    if state.config is None:
        raise ValueError("Combat rewards require declared content pools.")
    encounter = None if encounter_id is None else ENCOUNTERS[encounter_id]
    relic_pool = eligible_relics(state) if encounter is not None and encounter.gives_relic else ()
    if encounter is not None and encounter.gives_relic and not relic_pool:
        raise ValueError("Restricted relic pool exhausted.")
    from game.headless.encounters import loot
    loot.validate(encounter_id, encounter_loot, cards)
    if encounter is not None and encounter.room_kind == 'boss' and encounter.act == 3:
        from game.headless.relics.rewards import extra_rewards
        state.pending = dict(kind='reward', gold=0, gold_claimed=True, offers=[], card_resolved=True,
            card_modifiers={}, combat_reward=True, encounter_id=encounter_id,
            potion=None, potion_claimed=False, relic=None, relic_claimed=False, relic_instance_id=None,
            extra_rewards=[], hunt_rewards_earned=0, royalties_earned=0)
        state.pending['extra_rewards'] = extra_rewards(state, cards, encounter, final_boss=True)
        state.phase = RunPhase.REWARD
        return
    low, high = (10, 20) if encounter is None else encounter.gold_range
    low, high = loot.gold_range(low, high, encounter_loot)
    from game.headless.relics.run_rules import has
    kind = encounter.room_kind if encounter is not None else "combat"
    if getattr(state.rng, "native", False):
        from game.headless.generation.odds import potion_drop
        dropped = potion_drop(state, kind, forced=has(state, "white_beast_statue"))
    else:
        dropped = state.rng.randint("potion_drop", 0, 99) < state.potion_drop_chance
        dropped = dropped or has(state, "white_beast_statue")
        state.potion_drop_chance = max(0, min(100, state.potion_drop_chance + (-10 if dropped else 10)))
    gold = (state.rng.randint("reward_gold", low, high) if high else 0) + (15 if has(state, "amethyst_aubergine") else 0)
    from game.headless.potions.pools import generate
    potion = generate(state.config.reward_potions, state.rng, stream="reward_potion") if dropped else None
    pool = state.config.boss_reward_cards if encounter is not None and encounter.room_kind == "boss" else state.config.reward_cards
    upgraded = begin_reward(state, cards, gold=gold, card_ids=pool, decorate_cards=False, native_kind=kind)
    from game.headless.relics.rewards import add_power_option, decorate, extra_rewards, extend_pool
    upgraded.extend(add_power_option(state, cards, state.pending["offers"], extend_pool(state, cards, pool), kind=kind))
    state.pending["card_modifiers"] = decorate(state, cards, state.pending["offers"], upgrade_all=undamaged and has(state, "lava_lamp"), upgraded=upgraded)
    if relic_pool and getattr(state.rng,"native",False):
        from game.headless.generation.relics import pull
        relic=pull(state,allowed=state.config.reward_relics)
    else:
        relic = state.rng.choice("reward_relic", relic_pool) if relic_pool else None
    state.pending["relic"] = relic
    returned = loot.returned_gold(encounter_loot)
    if returned:
        # Initial room rewards populate before relic-added reward batches.
        state.rng.randint('reward_gold', returned, returned)
    state.pending.update(combat_reward=True, hunt_rewards_earned=extra_cards, royalties_earned=royalties, encounter_id=encounter_id, potion=potion,
                         potion_claimed=False, relic=relic, relic_claimed=False, relic_instance_id=None, extra_rewards=extra_rewards(state, cards, encounter, undamaged=undamaged))
    if encounter_loot is not None:
        state.pending['encounter_loot'] = dict(encounter_loot)
        if not high and not gold:
            state.pending['gold_claimed'] = True
        if returned:
            state.pending['extra_rewards'].append(dict(source='stolen_gold', kind='gold', offers=['stolen_gold'], modifiers={'gold': returned}, resolved=False))
    from game.headless.encounters.theft import rewards as theft_rewards
    state.pending["extra_rewards"].extend(theft_rewards(encounter_loot))
    from game.headless.run.event_combat import extra_rewards as event_rewards
    state.pending["extra_rewards"].extend(event_rewards(state,cards,encounter_id))
    if royalties:
        state.pending["extra_rewards"].append(dict(source="royalties", kind="gold", offers=["royalties"], modifiers={"gold": royalties}, resolved=False))
    if extra_cards:
        from game.headless.relics.rewards import hunt_rewards
        state.pending["extra_rewards"].extend(hunt_rewards(state, cards, kind, extra_cards, undamaged=undamaged))


def claim_potion(state):
    reward = _reward(state)
    if not reward.get("combat_reward") or reward["potion"] is None or reward["potion_claimed"]:
        raise ValueError("Potion reward is unavailable.")
    potion = add_potion(state, reward["potion"])
    reward["potion_claimed"] = True
    return potion


def leave_combat_rewards(state, *, cards=None) -> None:
    reward = _reward(state)
    if not reward.get("combat_reward"):
        raise ValueError("No combat rewards are active.")
    # Combat rewards may be left unclaimed; they are then forfeited.
    encounter_id = reward["encounter_id"]
    from game.headless.run.event_combat import leave_rewards
    leave_rewards(state, encounter_id)
    state.pending = None
    if encounter_id is not None and ENCOUNTERS[encounter_id].room_kind == "boss":
        from game.headless.run.state import ActCompletion
        state.act_completion = ActCompletion(ENCOUNTERS[encounter_id].act, encounter_id)
        state.phase = RunPhase.ACT_COMPLETE
    else:
        state.phase = RunPhase.ROUTE
        from game.headless.run.event_combat import resume
        from game.headless.cards.catalog import DEFAULT_CARDS
        resume(state, cards or DEFAULT_CARDS)


def claim_relic(state, *, cards=None):
    reward = _reward(state)
    if not reward.get("combat_reward") or reward["relic"] is None or reward["relic_claimed"]:
        raise ValueError("Relic reward is unavailable.")
    relic = add_relic(state, reward["relic"], cards=cards)
    reward["relic_claimed"] = True
    reward["relic_instance_id"] = relic.instance_id
    return relic


def acquire_card(state, cards, name, modifiers):
    from game.headless.enchantments.base import restore
    modifier = modifiers[name]
    card = add_card(state, cards.definition(name), upgrade_level=modifier['upgrade_level'],
                    enchantment=restore(modifier['enchantment']))
    return card


def choose_extra(state, cards, index, name):
    reward = _reward(state)['extra_rewards'][index]
    if reward['resolved'] or name is not None and name not in reward['offers']:
        raise ValueError('Extra reward is unavailable.')
    result = None
    if reward['source'] == 'stolen_card':
        from game.headless.encounters.theft import claim
        return claim(state, cards, reward, name)
    if reward['source'].startswith('event:'):
        from game.headless.events.reward_batch import claim
        return claim(state,cards,reward,name)
    if name is not None:
        if reward['kind'] == 'gold':
            from game.headless.relics.run_rules import gain_gold
            gain_gold(state, reward["modifiers"]["gold"])
            result = reward["modifiers"]["gold"]
        else:
            result = add_relic(state, name, cards=cards) if reward['kind'] == 'relic' else acquire_card(state, cards, name, reward['modifiers'])
    reward['resolved'] = True
    return result


def begin_reward(state, cards, **kwargs):
    if not getattr(state.rng,"native",False):return _begin_reward(state,cards,**kwargs)
    from copy import deepcopy
    trial=deepcopy(state);result=_begin_reward(trial,cards,**kwargs)
    state.__dict__.clear();state.__dict__.update(trial.__dict__)
    return result


def begin_combat_rewards(state,cards,**kwargs):
    if not getattr(state.rng,"native",False):return _begin_combat_rewards(state,cards,**kwargs)
    from copy import deepcopy
    trial=deepcopy(state);result=_begin_combat_rewards(trial,cards,**kwargs)
    state.__dict__.clear();state.__dict__.update(trial.__dict__)
    return result
