"""Serializable acquisition choices layered over the room that granted a relic."""

from copy import deepcopy
from game.headless.run.actions import ChooseRelicCard, ConfirmRelicSelection, ChooseRelicReward, DiscardPotion
from game.headless.relics.run_rules import has

SELECTIONS = {
    "dollys_mirror": ("clone", 1, 1, "", 0),
    "gnarled_hammer": ("enchant", 0, 3, "sharp", 3),
    "kifuda": ("enchant", 0, 3, "adroit", 3),
    "punch_dagger": ("enchant", 1, 1, "momentum", 5),
    "royal_stamp": ("enchant", 1, 1, "royally_approved", 1),
    "new_leaf": ("transform", 1, 1, "", 0),
    "pomander": ("upgrade", 1, 1, "", 0),
    "precise_scissors": ("remove", 1, 1, "", 0),
    "precarious_shears": ("remove", 2, 2, "", 0),
}


def begin(state, relic, cards):
    from game.headless.cards.catalog import DEFAULT_CARDS

    cards = cards or DEFAULT_CARDS
    name = relic.definition_id
    if name in SELECTIONS:
        operation, minimum, maximum, enchantment, amount = SELECTIONS[name]
        eligible = [
            c
            for c in state.deck
            if (operation != "clone" or c.spec.kind != "quest")
            and (operation not in ("remove", "transform") or not c.spec.eternal)
        ]
        if operation == "upgrade":
            eligible = [c for c in eligible if c.upgrade_level + 1 < len(c.definition.levels)]
        elif operation == "enchant":
            from game.headless.enchantments.base import can_enchant

            eligible = [c for c in eligible if can_enchant(c, enchantment)]
        if not eligible:
            if name == "precarious_shears":
                from game.headless.relics.run_rules import damage

                damage(state, 16)
            return
        maximum = min(maximum, len(eligible))
        state.relic_work.append(
            dict(
                source=relic.instance_id,
                kind="select",
                operation=operation,
                candidates=[c.instance_id for c in eligible],
                selected=[],
                minimum=min(minimum, maximum),
                maximum=maximum,
                enchantment=enchantment,
                amount=amount,
            )
        )
    elif name in ("cauldron", "orrery", "lost_coffer", "lead_paperweight"):
        if name == "cauldron":
            for _ in range(5):
                potion_reward(state, relic.instance_id)
        else:
            for _ in range(5 if name == "orrery" else 1):
                card_reward(
                    state,
                    cards,
                    relic.instance_id,
                    colorless=name == "lead_paperweight",
                    count=2 if name == "lead_paperweight" else 3,
                    is_card_reward=name != "lead_paperweight",
                )
            if name == "lost_coffer":
                potion_reward(state, relic.instance_id)
    else:
        from game.headless.relics.neow import begin as neow_begin

        neow_begin(state, relic, cards)


def card_reward(state, cards, source, *, colorless=False, count=3, rarity=None, is_card_reward=True):
    family = "colorless" if colorless else "ironclad"
    pool = [
        d
        for d in sorted(cards.definitions, key=lambda d: d.definition_id)
        if d.pool == family
        and d.rarity in ("common", "uncommon", "rare")
        and (rarity is None or d.rarity == rarity)
    ]
    state.rng.shuffle("relic.card_reward", pool)
    from game.headless.relics.rewards import decorate

    definitions = [d.definition_id for d in pool[:count]]
    modifiers = decorate(state, cards, definitions, card_reward=is_card_reward)
    offers = [{"definition_id": name, **modifiers[name]} for name in definitions]
    if offers:
        state.relic_work.append(dict(source=source, kind="card_reward", offers=offers))


def potion_reward(state, source):
    pool = state.config.reward_potions if state.config is not None else ("fire_potion", "block_potion")
    state.relic_work.append(
        dict(source=source, kind="potion_reward", offers=[state.rng.choice("relic.potion_reward", pool)])
    )


def legal_actions(state):
    work = state.relic_work[0]
    if work["kind"] == "select":
        selected = work["selected"]
        actions = [
            ChooseRelicCard(i) for i in work["candidates"] if i in selected or len(selected) < work["maximum"]
        ]
        if len(selected) >= work["minimum"]:
            actions.append(ConfirmRelicSelection())
        return tuple(actions)
    actions = [] if work.get("mandatory") or work["kind"] == "bundle" else [ChooseRelicReward(None)]
    if work["kind"] != "potion_reward" or None in state.potions:
        actions += [ChooseRelicReward(i) for i in range(len(work["offers"]))]
    if work["kind"] == "potion_reward":
        actions += [DiscardPotion(p.instance_id) for p in state.potions if p is not None]
    return tuple(actions)


def apply(state, cards, action):
    before = deepcopy(state)
    try:
        return _apply(state, cards, action)
    except Exception:
        state.__dict__.clear()
        state.__dict__.update(before.__dict__)
        raise


def _apply(state, cards, action):
    if action not in legal_actions(state):
        raise ValueError("Unavailable relic acquisition choice.")
    work = state.relic_work[0]
    if isinstance(action, DiscardPotion):
        from game.headless.run.inventory import discard_potion

        return discard_potion(state, action.instance_id)
    if isinstance(action, ChooseRelicCard):
        selected = work["selected"]
        (
            selected.remove(action.instance_id)
            if action.instance_id in selected
            else selected.append(action.instance_id)
        )
        return
    state.relic_work.pop(0)
    if isinstance(action, ConfirmRelicSelection):
        from game.headless.run.deck import find_card, add_card, remove_card, transform_card
        from game.headless.cards.pools import REWARD_CARDS, COLORLESS_CARDS
        from game.headless.enchantments.base import enchant

        for identity in work["selected"]:
            card = find_card(state, identity)
            operation = work["operation"]
            if operation == "upgrade":
                card.upgrade()
            elif operation == "remove":
                remove_card(state, identity)
            elif operation == "clone":
                clone = add_card(state, card.definition, upgrade_level=card.upgrade_level)
                if card.enchantment is not None:
                    clone.enchantment = deepcopy(card.enchantment)
            elif operation == "transform":
                from game.headless.events.transformation import replacement_pool

                transform_card(
                    state, cards, identity, replacement_pool(card.definition.definition_id, REWARD_CARDS)
                )
            elif operation == "enchant":
                enchant(card, work["enchantment"], work["amount"])
        source = next(r for r in state.relics if r.instance_id == work["source"])
        if source.definition_id == "precarious_shears":
            from game.headless.relics.run_rules import damage

            damage(state, 16)
            if state.hp == 0:
                from game.headless.run.state import RunPhase

                state.phase = RunPhase.DEFEAT
                state.pending = None
                state.relic_work.clear()
        return
    if action.index is None:
        return
    offer = work["offers"][action.index]
    if work["kind"] == "card_reward":
        from game.headless.run.deck import add_card
        from game.headless.enchantments.base import restore

        card = add_card(state, cards.definition(offer["definition_id"]), upgrade_level=offer["upgrade_level"])
        if offer["enchantment"] is not None:
            card.enchantment = restore(offer["enchantment"])
        return card
    if work["kind"] == "relic_reward":
        from game.headless.run.inventory import add_relic

        remaining, state.relic_work = state.relic_work, []
        result = add_relic(state, offer, cards=cards)
        state.relic_work.extend(remaining)
        return result
    if work["kind"] == "bundle":
        from game.headless.run.deck import add_card

        return [add_card(state, cards.definition(n)) for n in offer]
    if work["kind"] == "potion_reward":
        from game.headless.run.inventory import add_potion

        return add_potion(state, offer)


def validate(state, cards):
    if not isinstance(state.relic_work, list):
        raise ValueError("Invalid relic acquisition work.")
    if state.relic_work and state.relic_work[0].get("kind") == "effect":
        raise ValueError("Snapshot contains undrained automatic acquisition.")
    owners = {r.instance_id: r.definition_id for r in state.relics}
    for work in state.relic_work:
        if not isinstance(work, dict) or work.get("source") not in owners:
            raise ValueError("Unowned relic acquisition.")
        if work.get("kind") == "select":
            if set(work) != {
                "source",
                "kind",
                "operation",
                "candidates",
                "selected",
                "minimum",
                "maximum",
                "enchantment",
                "amount",
            }:
                raise ValueError("Invalid relic selection fields.")
            name = owners[work["source"]]
            expected = SELECTIONS.get(name)
            if expected is None or (work["operation"], work["enchantment"], work["amount"]) != (
                expected[0],
                expected[3],
                expected[4],
            ):
                raise ValueError("Relic choice differs from its source.")
            candidates, selected = work["candidates"], work["selected"]
            if any(
                not isinstance(v, list) or any(not isinstance(x, str) for x in v) or len(v) != len(set(v))
                for v in (candidates, selected)
            ):
                raise ValueError("Invalid relic choice identities.")
            if not set(selected) <= set(candidates) <= {c.instance_id for c in state.deck}:
                raise ValueError("Relic selection references a foreign card.")
            from game.headless.enchantments.base import can_enchant

            for card in state.deck:
                if card.instance_id in candidates and (
                    (work["operation"] in ("remove", "transform") and card.spec.eternal)
                    or (
                        work["operation"] == "upgrade"
                        and card.upgrade_level + 1 >= len(card.definition.levels)
                    )
                    or (work["operation"] == "enchant" and not can_enchant(card, work["enchantment"]))
                    or (work["operation"] == "clone" and card.spec.kind == "quest")
                ):
                    raise ValueError("Relic choice includes an ineligible card.")
            if (work["minimum"], work["maximum"]) != (
                min(expected[1], len(candidates)),
                min(expected[2], len(candidates)),
            ) or len(selected) > work["maximum"]:
                raise ValueError("Invalid relic choice bounds.")
        elif work.get("kind") in ("card_reward", "potion_reward", "relic_reward", "bundle"):
            if (
                set(work) not in ({"source", "kind", "offers"}, {"source", "kind", "offers", "mandatory"})
                or not isinstance(work["offers"], list)
                or not work["offers"]
            ):
                raise ValueError("Invalid relic reward.")
            name = owners[work["source"]]
            sources = {
                "card_reward": {"orrery", "lost_coffer", "lead_paperweight", "hefty_tablet", "kaleidoscope"},
                "potion_reward": {"cauldron", "lost_coffer", "tiny_mailbox"},
                "relic_reward": {"small_capsule", "neows_bones", "shovel"},
                "bundle": {"scroll_boxes"},
            }
            if name == "neows_bones" and work.get("mandatory") is not True:
                raise ValueError("Neow relic rewards cannot be skipped.")
            if name not in sources[work["kind"]] or (
                "mandatory" in work and (work["mandatory"] is not True or name != "neows_bones")
            ):
                raise ValueError("Relic reward kind differs from its source.")
            from game.headless.potions.base import POTIONS

            for offer in work["offers"]:
                if work["kind"] == "bundle":
                    if not isinstance(offer, list) or len(offer) != 3:
                        raise ValueError("Invalid relic bundle.")
                    for name in offer:
                        cards.definition(name)
                elif work["kind"] == "relic_reward":
                    from game.headless.relics.base import RELICS

                    if not isinstance(offer, str) or offer not in RELICS:
                        raise ValueError("Invalid relic reward definition.")
                elif work["kind"] == "potion_reward":
                    if not isinstance(offer, str) or offer not in POTIONS:
                        raise ValueError("Invalid relic potion offer.")
                else:
                    if not isinstance(offer, dict) or set(offer) != {
                        "definition_id",
                        "upgrade_level",
                        "enchantment",
                    }:
                        raise ValueError("Invalid relic card offer.")
                    card = cards.create(offer["definition_id"], upgrade_level=offer["upgrade_level"])
                    from game.headless.enchantments.base import restore, validate as validate_enchantment

                    card.enchantment = restore(offer["enchantment"])
                    validate_enchantment(card, permanent=True)
        elif work.get("kind") == "effect":
            if (
                set(work) != {"source", "kind", "operation", "values"}
                or work["operation"] not in ("cards", "relic")
                or not isinstance(work["values"], list)
                or any(not isinstance(v, str) for v in work["values"])
            ):
                raise ValueError("Invalid automatic relic acquisition.")
            name = owners[work["source"]]
            if work["operation"] == "cards":
                for value in work["values"]:
                    cards.definition(value)
                valid = (
                    (name == "hefty_tablet" and work["values"] == ["injury"])
                    or (name == "large_capsule" and work["values"] == ["strike", "defend"])
                    or (
                        name == "neows_bones"
                        and len(work["values"]) == 1
                        and work["values"][0] in ("clumsy", "injury")
                    )
                )
            else:
                from game.headless.relics.base import RELICS

                valid = (
                    name == "large_capsule"
                    and len(work["values"]) == 1
                    and work["values"][0] in RELICS
                    and (
                        RELICS[work["values"][0]].rarity in ("common", "uncommon", "rare")
                        or work["values"][0] == "circlet"
                    )
                )
            if not valid:
                raise ValueError("Automatic acquisition differs from its source.")
        else:
            raise ValueError("Unknown relic acquisition work.")


def relic_reward(state, source, *, automatic=False):
    from game.headless.relics.base import RELICS

    unavailable = {r.definition_id for r in state.relics}
    unavailable.update(x for w in state.relic_work if w["kind"] == "relic_reward" for x in w["offers"])
    unavailable.update(
        x
        for w in state.relic_work
        if w["kind"] == "effect" and w["operation"] == "relic"
        for x in w["values"]
    )
    pool = [
        name
        for name, definition in RELICS.items()
        if definition.rarity in ("common", "uncommon", "rare") and name not in unavailable
    ]
    name = state.rng.choice("relic.reward", pool) if pool else "circlet"
    if automatic:
        from game.headless.relics.neow import effect

        effect(state, source, "relic", [name])
    else:
        state.relic_work.append(dict(source=source, kind="relic_reward", offers=[name]))
