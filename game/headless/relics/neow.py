"""Solo Neow pickup rules and explicit dependent-content eligibility."""
from game.headless.characters import character, potion_pool as character_potions

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


def available(name, cards, family="ironclad"):
    if name == "kaleidoscope":
        from game.headless.generation.foreign import complete
        return complete(cards, family)
    if name == "scroll_boxes":
        return all(
            sum(
                d.pool == family and d.rarity == rarity
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
            if d.pool == character(state) and d.rarity == "rare"
        ]
        if getattr(state.rng,"native",False):
            from game.headless.characters import card_order
            IRONCLADCARDPOOL = card_order(character(state))
            rank={n:i for i,n in enumerate(IRONCLADCARDPOOL)}
            pool.sort(key=lambda d:rank[d.definition_id])
        from game.headless.relics.rewards import decorate
        from game.headless.enchantments.base import restore
        chosen = state.rng.choice("relic.rare_card", pool)
        modifier = decorate(state, cards, [chosen.definition_id], card_reward=False)[chosen.definition_id]
        add_card(state, chosen, upgrade_level=modifier["upgrade_level"],
                 enchantment=restore(modifier["enchantment"]))
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
        effect(state, source, "cards", ["strike", "defend"] if character(state) == "ironclad" else ["strike_" + character(state), "defend_" + character(state)])
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
                transform_card(state, cards, card.instance_id, state.config.reward_cards if state.config else REWARD_CARDS, stream="card.transform")
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
        generated = generate_many(pool, state.rng, 2, stream="combat_potion_generation" if getattr(state.rng, "native", False) else "relic.potion_generation")
        for potion in generated:
            if None in state.potions:
                add_potion(state, potion)
    elif name == "silken_tress":
        state.gold = 0
    elif name == "scroll_boxes":
        commons = [
            d.definition_id
            for d in sorted(cards.definitions, key=lambda d: d.definition_id)
            if d.pool == character(state) and d.rarity == "common"
        ]
        uncommons = [
            d.definition_id
            for d in sorted(cards.definitions, key=lambda d: d.definition_id)
            if d.pool == character(state) and d.rarity == "uncommon"
        ]
        if getattr(state.rng,"native",False):
            from game.headless.generation.odds import card_offers
            # Native generates each complete bundle before the next: C, C, U.
            # Drawing all commons first changes both bundles for the same seed.
            bundles = []
            used = []
            for _ in range(2):
                if character(state) == "defect" and state.rng.randint("rewards", 0, 99) < 1:
                    bundles.append(["claw"] * 3)
                    continue
                common, _ = card_offers(state, cards, commons, 2, uniform=True,
                                        upgrade_roll=False, blacklist=used)
                uncommon, _ = card_offers(state, cards, uncommons, 1, uniform=True,
                                          upgrade_roll=False, blacklist=used)
                bundle = [*common, *uncommon]
                bundles.append(bundle)
                used.extend(bundle)
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
            if n != name and n not in {r.definition_id for r in state.relics} and available(n, cards, character(state))
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

            add_relic(state, work["values"][0], cards=cards, prioritize_pickup=True)
        else:
            raise ValueError("Unknown automatic relic acquisition.")
