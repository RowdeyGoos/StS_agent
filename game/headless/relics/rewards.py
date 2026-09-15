"""Relic modifications to generated card offers, persisted before any choice."""

from game.headless.relics.run_rules import has, owned, modify_new_card
from game.headless.enchantments.base import can_enchant, enchant, record


def extend_pool(state, cards, pool, *, card_reward=True, custom_pool=False, no_pool_changes=False, card_kind=None):
    result = list(pool)
    native = getattr(state.rng, "native", False)
    if native and (not card_reward or custom_pool or no_pool_changes):
        return result
    if has(state, "dingy_rug"):
        rarities = {cards.definition(name).rarity for name in result}
        result += [
            d.definition_id
            for d in sorted(cards.definitions, key=lambda d: d.definition_id)
            if d.pool == "colorless" and d.rarity in rarities and d.definition_id not in result
            and (card_kind in (None, "any") or d.levels[0].kind == card_kind)
        ]
    return result


def decorate(state, cards, offers, *, upgrade_all=False, card_reward=True, upgraded=()):
    instances = [cards.create(name) for name in offers]
    from game.headless.relics.run_rules import counter

    for card in instances:
        if card.definition.definition_id in upgraded and len(card.definition.levels)>1:
            card.upgrade()
    if upgrade_all:
        for card in instances:
            if card.upgrade_level + 1 < len(card.definition.levels):
                card.upgrade()
    for relic in tuple(state.relics):
        if relic.definition_id == "silver_crucible" and card_reward and relic.counter < 3:
            counter(state, relic, relic.counter + 1)
            for card in instances:
                if card.upgrade_level + 1 < len(card.definition.levels):
                    card.upgrade()
        elif relic.definition_id == "silken_tress" and card_reward and not relic.counter:
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
    return {
        c.definition.definition_id: {"upgrade_level": c.upgrade_level, "enchantment": record(c)}
        for c in instances
    }


def add_power_option(state, cards, offers, pool, *, kind="combat"):
    if not has(state, "lasting_candy") or owned(state, "lasting_candy").counter:
        return []
    powers = [name for name in pool if cards.definition(name).levels[0].kind == "power"]
    choices = [name for name in powers if name not in offers]
    if not choices and powers and getattr(state.rng, "native", False):
        # Native retries without the blacklist. Definition-ID reward decisions
        # cannot yet distinguish independently modified duplicate options.
        raise ValueError("Lasting Candy duplicate-power fallback requires instance-based reward choices.")
    if choices:
        if getattr(state.rng, "native", False):
            from game.headless.generation.odds import card_offers
            # Native creates one custom-pool reward with Source.Other: base odds,
            # no further pool/options hooks, but a normal upgrade roll.
            extra, upgraded = card_offers(state, cards, choices, 1, kind=kind, mode="base")
            offers.extend(extra)
            return upgraded
        offers.append(state.rng.choice("relic.power_reward", choices))
    return []


def extra_rewards(state, cards, encounter, *, undamaged=False):
    from game.headless.cards.pools import RARE_CARDS

    result = []
    kind = encounter.room_kind if encounter is not None else "combat"
    for relic in state.relics:
        name = relic.definition_id
        if (name == "prayer_wheel" and kind == "combat") or (name == "white_star" and kind == "elite"):
            pool = extend_pool(
                state, cards, RARE_CARDS if name == "white_star" else state.config.reward_cards
            )
            upgraded=[]
            if getattr(state.rng, "native", False):
                from game.headless.generation.odds import card_offers
                offers,upgraded=card_offers(state,cards,pool,kind="boss" if name=="white_star" else kind)
                upgraded.extend(add_power_option(state,cards,offers,pool,kind="boss" if name=="white_star" else kind))
            else:
                state.rng.shuffle("reward_offer", pool)
                offers = pool[:3]
            result.append(
                {
                    "source": relic.instance_id,
                    "kind": "card",
                    "offers": offers,
                    "modifiers": decorate(
                        state, cards, offers, upgrade_all=undamaged and has(state, "lava_lamp"), upgraded=upgraded
                    ),
                    "resolved": False,
                }
            )
        elif name == "lava_rock" and kind == "boss" and not relic.counter:
            from game.headless.relics.run_rules import counter
            from game.headless.relics.base import RELICS

            blocked = {r.definition_id for r in state.relics}
            if state.pending.get("relic"):
                blocked.add(state.pending["relic"])
            for _ in range(2):
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
            counter(state, relic, 1)
    return result


def validate_modifiers(cards, offers, modifiers):
    if not isinstance(modifiers, dict) or set(modifiers) != set(offers):
        raise ValueError("Reward modifiers differ from their offers.")
    from game.headless.enchantments.base import restore, validate

    for name, data in modifiers.items():
        if not isinstance(data, dict) or set(data) != {"upgrade_level", "enchantment"}:
            raise ValueError("Invalid card reward modifier fields.")
        card = cards.create(name, upgrade_level=data["upgrade_level"])
        card.enchantment = restore(data["enchantment"])
        validate(card, permanent=True)


def validate_extra(state, cards, rewards, *, hunt_rewards_earned=0):
    if not isinstance(rewards, list):
        raise ValueError("Invalid extra rewards.")
    earned = hunt_rewards_earned
    if type(earned) is not int or earned < 0:
        raise ValueError("Invalid earned Hunt reward count.")
    owners = {r.instance_id: r.definition_id for r in state.relics}
    sources = []
    hunt_index = 0
    for reward in rewards:
        if not isinstance(reward, dict) or set(reward) != {
            "source",
            "kind",
            "offers",
            "modifiers",
            "resolved",
        }:
            raise ValueError("Invalid extra reward fields.")
        if reward["source"] == f"the_hunt:{hunt_index}":
            cards.definition("the_hunt")
            owners[reward["source"]] = "the_hunt"
            hunt_index += 1
        if (
            owners.get(reward["source"]) not in ("prayer_wheel", "white_star", "lava_rock", "the_hunt")
            or type(reward["resolved"]) is not bool
        ):
            raise ValueError("Unowned extra reward.")
        if owners[reward["source"]] == "lava_rock":
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
            or len(reward["offers"]) not in ((3, 4) if has(state,"lasting_candy") and owned(state,"lasting_candy").counter == 0 else (3,))
            or len(set(reward["offers"])) != len(reward["offers"])
        ):
            raise ValueError("Invalid extra card offers.")
        sources.append(reward["source"])
        validate_modifiers(cards, reward["offers"], reward["modifiers"])
    if hunt_index != earned:
        raise ValueError("Hunt rewards differ from the earned count.")
    if any(sources.count(i) != (2 if owners[i] == "lava_rock" else 1) for i in sources):
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
            upgraded.extend(add_power_option(state, cards, offers, pool, kind=kind))
        else:
            offers = list(pool)
            state.rng.shuffle("reward_offer", offers)
            offers = offers[:3]
        result.append(dict(source=f"the_hunt:{index}", kind="card", offers=offers,
            modifiers=decorate(state, cards, offers, upgrade_all=undamaged and has(state, "lava_lamp"), upgraded=upgraded), resolved=False))
    return result
