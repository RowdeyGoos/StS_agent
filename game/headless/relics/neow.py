"""Solo Neow pickup rules and explicit dependent-content eligibility."""

from game.headless.relics.run_rules import max_hp

NEOW_RELICS = (
    "arcane_scroll",
    "booming_conch",
    "cursed_pearl",
    "fishing_rod",
    "golden_pearl",
    "hefty_tablet",
    "kaleidoscope",
    "large_capsule",
    "lava_rock",
    "lead_paperweight",
    "leafy_poultice",
    "lost_coffer",
    "neows_bones",
    "neows_talisman",
    "neows_torment",
    "new_leaf",
    "nutritious_oyster",
    "phial_holster",
    "pomander",
    "precarious_shears",
    "precise_scissors",
    "scroll_boxes",
    "silken_tress",
    "silver_crucible",
    "small_capsule",
    "stone_humidifier",
    "winged_boots",
)


def available(name, cards):
    if name == "kaleidoscope":
        from game.headless.generation.foreign import complete
        return complete(cards)
    if name == "scroll_boxes":
        return all(
            sum(
                d.pool == "ironclad" and d.rarity == rarity
                for d in sorted(cards.definitions, key=lambda d: d.definition_id)
            )
            >= count
            for rarity, count in (("common", 4), ("uncommon", 2))
        )
    return True


def effect(state, source, operation, values):
    state.relic_work.append(dict(source=source, kind="effect", operation=operation, values=values))


def begin(state, relic, cards):
    from game.headless.relics.pickup import card_reward, relic_reward
    from game.headless.run.deck import add_card, transform_card
    from game.headless.cards.pools import REWARD_CARDS

    name, source = relic.definition_id, relic.instance_id
    if name == "arcane_scroll":
        pool = [
            d
            for d in sorted(cards.definitions, key=lambda d: d.definition_id)
            if d.pool == "ironclad" and d.rarity == "rare"
        ]
        if getattr(state.rng,"native",False):
            from game.headless.core.content_order import IRONCLADCARDPOOL
            rank={n:i for i,n in enumerate(IRONCLADCARDPOOL)}
            pool.sort(key=lambda d:rank[d.definition_id])
        add_card(state, state.rng.choice("relic.rare_card", pool))
    elif name == "cursed_pearl":
        add_card(state, cards.definition("greed"))
        from game.headless.relics.run_rules import gain_gold

        gain_gold(state, 333)
    elif name == "hefty_tablet":
        card_reward(state, cards, source, rarity="rare", is_card_reward=False)
        effect(state, source, "cards", ["injury"])
    elif name == "large_capsule":
        for _ in range(2):
            relic_reward(state, source, automatic=True)
        effect(state, source, "cards", ["strike", "defend"])
    elif name == "small_capsule":
        relic_reward(state, source)
    elif name == "leafy_poultice":
        max_hp(state, -12)
        if not state.hp:
            return
        for tag in ("strike", "defend"):
            card = next(
                (c for c in state.deck if c.definition.rarity == "basic" and getattr(c.definition, tag)), None
            )
            if card is not None:
                transform_card(state, cards, card.instance_id, REWARD_CARDS, stream="card.transform")
    elif name == "neows_talisman":
        for tag in ("strike", "defend"):
            card = next(
                (
                    c
                    for c in reversed(state.deck)
                    if c.definition.rarity == "basic" and getattr(c.definition, tag)
                ),
                None,
            )
            if card is not None and card.upgrade_level + 1 < len(card.definition.levels):
                card.upgrade()
    elif name == "neows_torment":
        add_card(state, cards.definition("neows_fury"))
    elif name == "phial_holster":
        state.potions.append(None)
        state.potion_capacity += 1
        from game.headless.run.inventory import add_potion

        pool = state.config.reward_potions if state.config is not None else ("fire_potion", "block_potion")
        from game.headless.potions.pools import generate_many
        generated = generate_many(pool, state.rng, 2, stream="relic.potion_generation")
        for potion in generated:
            if None in state.potions:
                add_potion(state, potion)
    elif name == "silken_tress":
        state.gold = 0
    elif name == "scroll_boxes":
        commons = [
            d.definition_id
            for d in sorted(cards.definitions, key=lambda d: d.definition_id)
            if d.pool == "ironclad" and d.rarity == "common"
        ]
        uncommons = [
            d.definition_id
            for d in sorted(cards.definitions, key=lambda d: d.definition_id)
            if d.pool == "ironclad" and d.rarity == "uncommon"
        ]
        if getattr(state.rng,"native",False):
            from game.headless.generation.odds import card_offers
            commons,_=card_offers(state,cards,commons,4,uniform=True,upgrade_roll=False)
            uncommons,_=card_offers(state,cards,uncommons,2,uniform=True,upgrade_roll=False)
        else:
            state.rng.shuffle("relic.bundles", commons)
            state.rng.shuffle("relic.bundles", uncommons)
        bundles = [[*commons[i * 2 : i * 2 + 2], uncommons[i]] for i in range(2)]
        state.relic_work.append(dict(source=source, kind="bundle", offers=bundles))
    elif name == "neows_bones":
        from game.headless.run.ancient import CURSES,POSITIVES
        order=(*CURSES,*POSITIVES,"lava_rock","neows_talisman","nutritious_oyster","pomander","small_capsule","stone_humidifier") if getattr(state.rng,"native",False) else NEOW_RELICS
        pool = [
            n
            for n in order
            if n != name and n not in {r.definition_id for r in state.relics} and available(n, cards)
        ]
        state.rng.shuffle("relic.neow_rewards", pool)
        for definition in pool[:2]:
            state.relic_work.append(
                dict(source=source, kind="relic_reward", offers=[definition], mandatory=True)
            )
        effect(state, source, "curse", [])
    elif name == "kaleidoscope":
        from game.headless.generation.foreign import kaleidoscope
        kaleidoscope(state, cards, source)


def drain(state, cards):
    """Execute deterministic acquisition work until the next player decision."""
    while state.relic_work and state.relic_work[0]["kind"] == "effect":
        work = state.relic_work.pop(0)
        if work["operation"] == "curse":
            from game.headless.cards.curses import MODIFIER_CURSES
            from game.headless.run.deck import add_card
            name = state.rng.choice("relic.curse", MODIFIER_CURSES)
            if state.hp:
                add_card(state, cards.definition(name))
        elif work["operation"] == "cards":
            from game.headless.run.deck import add_card

            for name in work["values"]:
                add_card(state, cards.definition(name))
        elif work["operation"] == "relic":
            from game.headless.run.inventory import add_relic

            remaining, state.relic_work = state.relic_work, []
            add_relic(state, work["values"][0], cards=cards)
            state.relic_work.extend(remaining)
        else:
            raise ValueError("Unknown automatic relic acquisition.")
