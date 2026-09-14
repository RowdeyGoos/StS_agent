"""Ironclad power hooks at explicit play, damage, exhaust and turn boundaries."""

from game.headless.core.resolution import push, drain

POWER_NAMES = frozenset(
    (
        "aggression",
        "barricade",
        "colossus",
        "corruption",
        "crimson_mantle",
        "cruelty",
        "dark_embrace",
        "demon_form",
        "feel_no_pain",
        "flame_barrier",
        "free_attack",
        "hellraiser",
        "inferno",
        "juggernaut",
        "juggling",
        "no_draw",
        "no_energy_gain",
        "one_two_punch",
        "plating",
        "pyre",
        "rage",
        "rupture",
        "setup_strike",
        "stampede",
        "unmovable",
        "vicious",
    )
)
SINGLE = frozenset(("barricade", "corruption", "hellraiser", "no_draw", "no_energy_gain"))


def apply_power(p, name, amount, target=None):
    if target is not None:
        if not target.is_alive:
            return
        if name == "strength":
            target.strength += amount
        elif name == "mangle":
            target.apply_status("mangle", amount)
        else:
            target.apply_status(name, amount, source=p)
        return
    if name == "strength":
        p.gain_strength(amount)
        return
    from game.headless.powers import colorless

    if name in colorless.NAMES:
        colorless.apply(p, name, amount)
        return
    from game.headless.potions.powers import NAMES as POTION_POWERS
    if name in POTION_POWERS:
        p.rules.powers[name] = p.rules.powers.get(name, 0) + amount
        return
    if name not in POWER_NAMES:
        raise ValueError(f"Unknown player power: {name}")
    r = p.rules
    r.powers[name] = 1 if name in SINGLE else r.powers.get(name, 0) + amount
    if name in ("crimson_mantle", "inferno"):
        r.auxiliaries[name] = r.auxiliaries.get(name, 0) + 1
    if name == "setup_strike":
        p.gain_strength(amount)


def card_cost(p, card):
    if card.spec.x_cost:
        return (
            0
            if (card.combat_state.free_this_turn or card.combat_state.free_until_played or card.combat_state.free_this_combat)
            or (card.spec.kind == "attack" and p.rules.powers.get("free_attack"))
            or (card.spec.kind == "skill" and p.rules.powers.get("corruption"))
            else p.energy
        )
    if card.cost < 0:
        return card.cost
    if card.spec.kind in ("skill", "block") and p.rules.powers.get("corruption"):
        return 0
    if card.spec.kind == "attack" and p.rules.powers.get("free_attack"):
        return 0
    return max(0, local_cost(card, clamp=False) + (p.statuses.get("tangled") if card.spec.kind == "attack" else 0))


def local_cost(card, *, clamp=True):
    """Local cost layers, before combat-wide powers such as Corruption."""
    v = card.combat_state
    if card.cost < 0:
        return card.cost
    if v.free_this_turn or ((v.free_until_played or v.free_this_combat) and v.turn_cost_override is None):
        return 0
    value = card.cost if v.combat_cost_override is None else v.combat_cost_override
    if v.turn_cost_override is not None:
        value = v.turn_cost_override
    value += v.cost_change + v.combat_cost_change
    if v.turn_cost_override is not None:
        value -= v.override_turn_baseline + v.override_combat_baseline
    elif v.combat_cost_override is not None:
        value -= v.combat_override_baseline
    return max(0, value) if clamp else value


def after_exhaust(p, card):
    r = p.rules
    r.exhausted_this_turn += 1
    tasks = []
    for name, amount in r.powers.items():
        if name == "feel_no_pain":
            tasks.append(["block", amount, False])
        elif name == "dark_embrace":
            if r.auxiliaries.get("exhaust_ethereal"):
                r.ethereal_draws += amount
            else:
                tasks.append(["draw", amount, False])
    if card.definition.definition_id == "drum_of_battle":
        p.gain_energy((3 if card.upgraded else 2) * (1 + card.combat_state.replay_count))
    from game.headless.relics.combat import tasks as relic_tasks
    tasks += relic_tasks(p, "exhaust_ethereal" if r.auxiliaries.get("exhaust_ethereal") else "exhaust", card.instance_id)
    push(p, *tasks)
    if not p._resolving:
        drain(p)


def block_multiplier(p, powered=True):
    if not powered:
        return 1
    before = p.rules.auxiliaries.get("block_gains", 0)
    if p.current_card is not None:
        context = p.rules.plays.get(p.current_card.instance_id)
        if context is not None:
            before -= context.get("blocks_gained", 0)
    return 2 if before < p.rules.powers.get("unmovable", 0) else 1


def record_block(p, powered):
    if powered:
        p.rules.auxiliaries["block_gains"] = p.rules.auxiliaries.get("block_gains", 0) + 1
        if p.current_card is not None:
            context = p.rules.plays.get(p.current_card.instance_id)
            if context is not None:
                context["blocks_gained"] = context.get("blocks_gained", 0) + 1


def after_block(p):
    amount = p.rules.powers.get("juggernaut", 0)
    living = [e for e in p.combat_enemies or () if e.is_alive]
    if amount and living and p.is_alive:
        p.deck.target_rng.choice(living).take_damage(amount, is_attack=False)


def after_hp_loss(p, amount):
    r = p.rules
    r.hp_loss_events += 1
    if not r.player_side:
        return
    r.hp_lost_this_turn += amount
    if not p.is_alive:
        return
    strength = r.powers.get("rupture", 0)
    if p.current_card is not None:
        r.plays[p.current_card.instance_id]["rupture"] += strength
    else:
        p.gain_strength(strength)
    inferno = r.powers.get("inferno", 0)
    if inferno:
        for enemy in tuple(p.combat_enemies or ()):
            if enemy.is_alive:
                enemy.take_damage(inferno, is_attack=False)


def after_play(p, card):
    r = p.rules
    context = r.plays[card.instance_id]
    p.gain_strength(context["rupture"])
    context["rupture"] = 0
    if card.spec.kind == "attack":
        r.attacks_finished += 1
    r.plays_finished += 1
    from game.headless.relics.combat import tasks as relic_tasks
    push(
        p,
        *[["after_card_power", card.instance_id, key] for key in r.powers],
        *relic_tasks(p, "after_play", card.instance_id),
        ["after_card_enchantment", card.instance_id],
        ["after_card_enemies", card.instance_id],
    )


def after_card_power(p, card, key):
    r = p.rules
    if key == "rage" and card.spec.kind == "attack" and not p.combat_is_ending:
        p.gain_block(r.powers[key])
    elif (
        key == "juggling"
        and card.spec.kind == "attack"
        and r.attacks_finished == 3
        and not p.combat_is_ending
    ):
        from game.headless.cards.special import clone_to

        for _ in range(r.powers[key]):
            clone_to(p, card, "hand")
    else:
        from game.headless.powers.colorless import after_card_power

        after_card_power(p, card, key)


def start_turn(p, draw_count):
    r = p.rules
    from game.headless.relics.combat import has, tasks as relic_tasks
    from game.headless.relics.turns import start_turn as relic_start
    if r.round_number and not r.powers.get("barricade"):
        p.block = min(10, p.block) if has(p, "sturdy_clamp") else 0
    if r.round_number:
        from game.headless.cards.event_effects import after_block_cleared
        after_block_cleared(p)
    p.energy = (p.energy if r.round_number and has(p, "ice_cream") else 0) + p.energy_per_turn + r.powers.get("pyre", 0)
    from game.headless.potions.powers import start_turn as potion_start
    draw_count = potion_start(p, draw_count)
    draw_count = relic_start(p, draw_count)
    if r.round_number == 1:
        draw_count = min(10, max(draw_count, sum(c.spec.innate for c in p.deck.draw_pile)))
    p.cards_played_this_turn = 0
    r.player_side = True
    r.turn_ending = False
    r.attacks_started = r.attacks_finished = r.skills_started = r.hp_lost_this_turn = (
        r.exhausted_this_turn
    ) = 0
    r.auxiliaries["block_gains"] = 0
    for card in p.deck.all_cards():
        card.combat_state.cost_change = 0
        card.combat_state.free_this_turn = False
        card.combat_state.turn_cost_override = None
    count = r.powers.get("aggression", 0)
    if count:
        cards = [c for c in p.deck.discard_pile if c.spec.kind == "attack"]
        p.deck.selection_rng.shuffle(cards)
        for card in cards[:count]:
            if len(p.hand) < 10:
                p.deck.discard_pile.remove(card)
                p.hand.append(card)
            if card.upgrade_level + 1 < len(card.definition.levels):
                card.upgrade()
    p.gain_strength(r.powers.get("demon_form", 0))
    from game.headless.powers.colorless import before_draw

    before_draw(p)
    push(p, *relic_tasks(p, "before_draw"), ["draw", draw_count, True], ["start_powers"], *relic_tasks(p, "after_draw"), *relic_tasks(p, "after_side_start"), ["mayhem"])
    drain(p)
    if p.pending_play is not None or r.selection is not None:
        # Native setup may pause while AfterSideTurnStart still completes.
        from game.headless.relics.combat import execute as execute_relic
        ready = [t for t in r.tasks if t[0] == "relic_hook" and t[2] == "after_side_start"]
        for task in ready:
            r.tasks.remove(task)
            execute_relic(p, *task[1:])


def end_turn(p):
    r = p.rules
    r.turn_ending = True
    from game.headless.relics.combat import tasks as relic_tasks, memory
    for relic in r.relics:
        if relic["definition_id"] == "orichalcum":
            memory(p, relic)["orichalcum_ready"] = p.block == 0
    tasks = [["block", r.powers["plating"], False]] if r.powers.get("plating") else []
    tasks += [["early_end", key] for key in r.powers]
    tasks += [
        ["autoplay", c.instance_id, False]
        for c in tuple(p.deck.exhaust_pile)
        if c.definition.definition_id == "howl_from_beyond"
    ]
    tasks += relic_tasks(p, "before_end")
    tasks += [["stampede", r.powers.get("stampede", 0)], ["discard_hand"]]
    push(p, *tasks)
    drain(p)


def after_player_end(p, name):
    from game.headless.potions.powers import after_end
    after_end(p, name)
    r = p.rules
    if name == "dark_embrace":
        push(p, ["draw", r.ethereal_draws, False])
        r.ethereal_draws = 0
    if name == "setup_strike":
        p.strength -= r.powers.get(name, 0)
    if name in ("rage", "one_two_punch", "setup_strike", "no_draw", "no_energy_gain"):
        r.powers.pop(name, None)


def after_enemy_end(p):
    r = p.rules
    r.powers.pop("flame_barrier", None)
    for name in ("plating", "colossus", "no_block"):
        if r.powers.get(name):
            r.powers[name] -= 1
