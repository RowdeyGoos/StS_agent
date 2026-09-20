"""Relic modifications to generated card offers, persisted before any choice."""

from game.headless.relics.run_rules import has, owned, modify_new_card
from game.headless.enchantments.base import can_enchant, enchant, record


def extend_pool(state, cards, pool, *, card_reward=True, custom_pool=False, no_pool_changes=False, card_kind=None):
    result = list(pool)
    native = getattr(state.rng, "native", False)
    if no_pool_changes or native and (not card_reward or custom_pool):
        return result
    if (card_reward and not custom_pool and not no_pool_changes and has(state, 'prismatic_gem')
            and result and not all(cards.definition(n).pool == 'colorless' for n in result)):
        rarities = {cards.definition(n).rarity for n in result}
        result += [d.definition_id for d in cards.definitions if d.pool in ('ironclad','silent','regent','necrobinder','defect') and d.rarity in rarities and d.definition_id not in result and (card_kind in (None,'any') or d.levels[0].kind == card_kind)]
    if has(state, "dingy_rug"):
        rarities = {cards.definition(name).rarity for name in result}
        result += [
            d.definition_id
            for d in sorted(cards.definitions, key=lambda d: d.definition_id)
            if d.pool == "colorless" and d.rarity in rarities and d.definition_id not in result
            and (card_kind in (None, "any") or d.levels[0].kind == card_kind)
        ]
    return result


def decorate(state, cards, offers, *, upgrade_all=False, card_reward=True, upgraded=(), modifiers=None, indexed=False, upgraded_indices=(), only=None):
    instances = [cards.create(name) for name in offers]
    from game.headless.relics.run_rules import counter
    if modifiers is not None:
        validate_modifiers(cards, offers, modifiers, indexed=isinstance(modifiers, list))
        from game.headless.enchantments.base import restore
        for index, card in enumerate(instances):
            saved = modifiers[index] if isinstance(modifiers, list) else modifiers[card.definition.definition_id]
            card.upgrade_level = saved['upgrade_level']
            card.enchantment = restore(saved['enchantment'])

    for index, card in enumerate(instances):
        if (index in upgraded_indices or card.definition.definition_id in upgraded) and len(card.definition.levels)>1:
            card.upgrade()
    if upgrade_all:
        for card in instances:
            if card.upgrade_level + 1 < len(card.definition.levels):
                card.upgrade()
    for relic in tuple(state.relics):
        if relic.data.get("_melted") or only is not None and relic.instance_id != only:
            continue
        if relic.definition_id == "silver_crucible" and card_reward and relic.counter < 3:
            if only is None:
                counter(state, relic, relic.counter + 1)
            for card in instances:
                if card.upgrade_level + 1 < len(card.definition.levels):
                    card.upgrade()
        elif relic.definition_id == "silken_tress" and card_reward and not relic.counter:
            if only is None:
                counter(state, relic, 1)
            for card in instances:
                if can_enchant(card, "glam"):
                    enchant(card, "glam", 1)
        elif relic.definition_id == "wing_charm":
            eligible = [c for c in instances if can_enchant(c, "swift")]
            if eligible:
                enchant(state.rng.choice("relic.reward_enchantment", eligible), "swift", 1)
        for card in instances:
            modify_new_card(state, card, only=relic.instance_id)
    if only is None and has(state, "glitter"):
        for card in instances:
            if can_enchant(card, "glam"):
                enchant(card, "glam", 1)
    values = [{"upgrade_level": c.upgrade_level, "enchantment": record(c)} for c in instances]
    return values if indexed else dict(zip(offers, values))


def active_power_options(state):
    return sum(r.definition_id == "lasting_candy" and not r.counter and not r.data.get("_melted")
               for r in state.relics)


def add_power_option(state, cards, offers, pool, *, kind="combat", upgraded_indices=None):
    powers = [name for name in pool if cards.definition(name).levels[0].kind == "power"]
    upgrades = []
    for _ in range(active_power_options(state)):
        choices = [name for name in powers if name not in offers] or powers
        if not choices:
            continue
        if getattr(state.rng, "native", False):
            from game.headless.generation.odds import card_offers
            # Native creates one custom-pool reward with Source.Other: base odds,
            # no further pool/options hooks, but a normal upgrade roll.
            extra, upgraded = card_offers(state, cards, choices, 1, kind=kind, mode="base")
            if extra and extra[0] in upgraded and upgraded_indices is not None:
                upgraded_indices.append(len(offers))
            offers.extend(extra)
            upgrades.extend(upgraded)
        else:
            offers.append(state.rng.choice("relic.power_reward", choices))
    return upgrades



def combat_modifiers(state, cards, offers, pool, *, upgraded=(), kind="combat", upgrade_all=False):
    """One modifier per offer position, including independently generated duplicates."""
    indices = [i for i, name in enumerate(offers) if name in upgraded]
    add_power_option(state, cards, offers, pool, kind=kind, upgraded_indices=indices)
    return decorate(state, cards, offers, indexed=True, upgraded_indices=indices, upgrade_all=upgrade_all)


def extra_rewards(state, cards, encounter, *, undamaged=False, final_boss=False):
    from game.headless.cards.pools import RARE_CARDS

    result = []
    kind = encounter.room_kind if encounter is not None else "combat"
    for relic in state.relics:
        if relic.data.get("_melted"):
            continue
        name = relic.definition_id
        if final_boss and name != "wongos_mystery_ticket":
            continue
        if (name == "prayer_wheel" and kind == "combat") or (name == "white_star" and kind == "elite"):
            pool = extend_pool(
                state, cards, RARE_CARDS if name == "white_star" else state.config.reward_cards
            )
            upgraded=[]
            if getattr(state.rng, "native", False):
                from game.headless.generation.odds import card_offers
                offers,upgraded=card_offers(state,cards,pool,kind="boss" if name=="white_star" else kind)
            else:
                state.rng.shuffle("reward_offer", pool)
                offers = pool[:3]
            result.append(
                {
                    "source": relic.instance_id,
                    "kind": "card",
                    "offers": offers,
                    "modifiers": combat_modifiers(
                        state, cards, offers, pool, kind="boss" if name == "white_star" else kind,
                        upgrade_all=undamaged and has(state, "lava_lamp"), upgraded=upgraded
                    ),
                    "resolved": False,
                }
            )
        elif (name == "lava_rock" and kind == "boss" and not relic.counter) or (name == "black_star" and kind == "elite") or (name == "wongos_mystery_ticket" and relic.counter == 5):
            from game.headless.relics.run_rules import counter
            from game.headless.relics.base import RELICS

            blocked = {r.definition_id for r in state.relics}
            if state.pending.get("relic"):
                blocked.add(state.pending["relic"])
            for _ in range(2 if name == "lava_rock" else 3 if name == "wongos_mystery_ticket" else 1):
                pool = [
                    n
                    for n, d in RELICS.items()
                    if d.rarity in ("common", "uncommon", "rare") and n not in blocked
                ]
                if getattr(state.rng,"native",False):
                    from game.headless.generation.relics import pull
                    chosen=pull(state,blacklist=blocked)
                else:
                    chosen = state.rng.choice("relic.lava_rock", pool) if pool else "circlet"
                blocked.add(chosen)
                result.append(
                    {
                        "source": relic.instance_id,
                        "kind": "relic",
                        "offers": [chosen],
                        "modifiers": {},
                        "resolved": False,
                    }
                )
            if name in ("lava_rock", "wongos_mystery_ticket"):
                counter(state, relic, 1 if name == "lava_rock" else 6)
    return result



def validate_combat_offers(state, cards, offers):
    if len(offers) <= 3 and len(set(offers)) == len(offers):
        return
    # The factory samples without replacement; every position appended by a
    # Candy is a Power, whether it repeats an earlier definition or is distinct.
    if (not 3 < len(offers) <= 3 + active_power_options(state)
            or len(set(offers[:3])) != 3
            or any(cards.definition(name).levels[0].kind != "power" for name in offers[3:])):
        raise ValueError("Duplicated reward lacks its Lasting Candy offer.")


def validate_modifiers(cards, offers, modifiers, *, indexed=False):
    if indexed:
        if not isinstance(modifiers, list) or len(modifiers) != len(offers):
            raise ValueError("Reward modifiers differ from their offer positions.")
    elif not isinstance(modifiers, dict) or set(modifiers) != set(offers):
        raise ValueError("Reward modifiers differ from their offers.")
    from game.headless.enchantments.base import restore, validate

    for name, data in (zip(offers, modifiers) if indexed else modifiers.items()):
        if not isinstance(data, dict) or set(data) != {"upgrade_level", "enchantment"}:
            raise ValueError("Invalid card reward modifier fields.")
        card = cards.create(name, upgrade_level=data["upgrade_level"])
        card.enchantment = restore(data["enchantment"])
        validate(card, permanent=True)


def validate_extra(state, cards, rewards, *, hunt_rewards_earned=0, royalties_earned=0):
    if not isinstance(rewards, list):
        raise ValueError("Invalid extra rewards.")
    earned = hunt_rewards_earned
    if type(earned) is not int or earned < 0:
        raise ValueError("Invalid earned Hunt reward count.")
    if type(royalties_earned) is not int or royalties_earned < 0:
        raise ValueError("Invalid earned Royalties reward.")
    royalties_count = 0
    owners = {r.instance_id: r.definition_id for r in state.relics}
    sources = []
    hunt_index = 0
    from game.headless.run.event_combat import validate_extra_rewards
    validate_extra_rewards(state,cards,rewards)
    from game.headless.encounters.loot import validate_rewards
    validate_rewards(state, rewards)
    from game.headless.encounters.theft import validate_rewards as validate_theft
    validate_theft(state, rewards)
    for reward in rewards:
        if not isinstance(reward, dict) or set(reward) - {"rerolled"} != {
            "source",
            "kind",
            "offers",
            "modifiers",
            "resolved",
        }:
            raise ValueError("Invalid extra reward fields.")
        from game.headless.relics.reward_alternatives import validate_marker
        validate_marker(state, reward)
        if "rerolled" in reward and reward["kind"] != "card":
            raise ValueError("Non-card reroll marker.")
        if isinstance(reward["source"],str) and reward["source"].startswith("event:"):
            continue
        if str(reward["source"]).startswith("forbidden_grimoire:"):
            from game.headless.run.removal_rewards import validate
            validate(state)
            continue
        if reward["source"] in ("stolen_gold", "stolen_card"):
            continue
        if reward["source"] == "royalties":
            cards.definition("royalties")
            if not royalties_earned or reward["kind"] != "gold" or reward["offers"] != ["royalties"] or reward["modifiers"] != {"gold": royalties_earned} or type(reward["resolved"]) is not bool:
                raise ValueError("Invalid Royalties reward.")
            royalties_count += 1
            continue
        if reward["source"] == f"the_hunt:{hunt_index}":
            cards.definition("the_hunt")
            owners[reward["source"]] = "the_hunt"
            hunt_index += 1
        if (
            owners.get(reward["source"]) not in ("prayer_wheel", "white_star", "lava_rock", "black_star", "the_hunt", "wongos_mystery_ticket")
            or type(reward["resolved"]) is not bool
        ):
            raise ValueError("Unowned extra reward.")
        if owners[reward["source"]] in ("lava_rock", "black_star", "wongos_mystery_ticket"):
            from game.headless.relics.base import RELICS

            if (
                reward["kind"] != "relic"
                or reward["modifiers"]
                or not isinstance(reward["offers"], list)
                or len(reward["offers"]) != 1
                or reward["offers"][0] not in RELICS
            ):
                raise ValueError("Invalid Lava Rock reward.")
            sources.append(reward["source"])
            continue
        if (
            reward["kind"] != "card"
            or not isinstance(reward["offers"], list)
            or len(reward["offers"]) not in range(3, 4 + active_power_options(state))
        ):
            raise ValueError("Invalid extra card offers.")
        sources.append(reward["source"])
        validate_combat_offers(state, cards, reward["offers"])
        validate_modifiers(cards, reward["offers"], reward["modifiers"], indexed=True)
    if royalties_count != int(royalties_earned > 0):
        raise ValueError("Royalties reward differs from earned gold.")
    if hunt_index != earned:
        raise ValueError("Hunt rewards differ from the earned count.")
    if any(sources.count(i) != (2 if owners[i] == "lava_rock" else 3 if owners[i] == "wongos_mystery_ticket" else 1) for i in sources):
        raise ValueError("Duplicated relic reward source.")


def hunt_rewards(state, cards, kind, count, *, undamaged=False):
    """Populate the room's owed Fatal rewards only at the post-combat boundary."""
    if type(count) is not int or count < 0:
        raise ValueError("Invalid owed card reward count.")
    result = []
    pool = extend_pool(state, cards, state.config.boss_reward_cards if kind == "boss" else state.config.reward_cards)
    for index in range(count):
        upgraded = []
        if getattr(state.rng, "native", False):
            from game.headless.generation.odds import card_offers
            offers, upgraded = card_offers(state, cards, pool, kind=kind)
        else:
            offers = list(pool)
            state.rng.shuffle("reward_offer", offers)
            offers = offers[:3]
        result.append(dict(source=f"the_hunt:{index}", kind="card", offers=offers,
            modifiers=combat_modifiers(state, cards, offers, pool, kind=kind, upgrade_all=undamaged and has(state, "lava_lamp"), upgraded=upgraded), resolved=False))
    return result


def relic_obtained(state, cards, relic):
    """Refresh subscribed offers before pickup work, using only the new relic.

    Native CardReward.OnRelicObtained calls AfterModifyingRewards, not the
    AfterModifyingCardRewardOptions hook that consumes Crucible/Tress uses.
    Fresh Candy has not seen a triggering combat. Explicit/manual card grids
    (including Kaleidoscope) do not subscribe to relic acquisition.
    """
    if relic.definition_id not in ('molten_egg', 'toxic_egg', 'frozen_egg',
                                   'wing_charm', 'silver_crucible', 'silken_tress', 'fresnel_lens'):
        return

    def refresh(offers, modifiers):
        return decorate(state, cards, offers, modifiers=modifiers,
                        indexed=isinstance(modifiers, list), only=relic.instance_id)

    pending = state.pending or {}
    if pending.get('kind') == 'reward':
        if not pending['card_resolved']:
            pending['card_modifiers'] = refresh(pending['offers'], pending['card_modifiers'])
        for row in pending.get('extra_rewards', []):
            if row['kind'] == 'card' and not row['resolved']:
                row['modifiers'] = refresh(row['offers'], row['modifiers'])
    elif pending.get('kind') == 'scripted_event' and pending.get('stage') == 'event_rewards':
        for row in pending['data']['active']['rewards']:
            if row['kind'] == 'card' and not row['resolved']:
                row['modifiers'] = refresh(row['offers'], row['modifiers'])

    owners = {r.instance_id: r.definition_id for r in state.relics}
    for work in state.relic_work:
        if work['kind'] != 'card_reward' or owners.get(work['source']) not in (
                'orrery', 'lost_coffer', 'glass_eye', 'dream_catcher'):
            continue
        names = [o['definition_id'] for o in work['offers']]
        modifiers = [{k: v for k, v in o.items() if k != 'definition_id'} for o in work['offers']]
        work['offers'] = [dict(definition_id=n, **m) for n, m in zip(names, refresh(names, modifiers))]
