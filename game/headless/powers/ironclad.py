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
        p.strength += amount
        return
    from game.headless.powers import colorless

    if name in colorless.NAMES:
        colorless.apply(p, name, amount)
        return
    if name not in POWER_NAMES:
        raise ValueError(f"Unknown player power: {name}")
    r = p.rules
    r.powers[name] = 1 if name in SINGLE else r.powers.get(name, 0) + amount
    if name in ("crimson_mantle", "inferno"):
        r.auxiliaries[name] = r.auxiliaries.get(name, 0) + 1
    if name == "setup_strike":
        p.strength += amount


def card_cost(p, card):
    if card.spec.x_cost:
        return (
            0
            if (card.combat_state.free_this_turn or card.combat_state.free_until_played)
            or (card.spec.kind == "attack" and p.rules.powers.get("free_attack"))
            or (card.spec.kind == "skill" and p.rules.powers.get("corruption"))
            else p.energy
        )
    if card.cost < 0:
        return card.cost
    if card.combat_state.free_this_turn or card.combat_state.free_until_played:
        return 0
    if card.spec.kind in ("skill", "block") and p.rules.powers.get("corruption"):
        return 0
    if card.spec.kind == "attack" and p.rules.powers.get("free_attack"):
        return 0
    return max(
        0,
        card.cost
        + card.combat_state.cost_change
        + (p.statuses.get("tangled") if card.spec.kind == "attack" else 0),
    )


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
    push(p, *tasks)
    if not p._resolving:
        drain(p)


def block_multiplier(p, powered=True):
    if not powered:
        return 1
    before = p.rules.auxiliaries.get("block_gains", 0)
    if p.deck.in_play:
        context = p.rules.plays.get(p.deck.in_play[-1].instance_id)
        if context is not None:
            before -= context.get("blocks_gained", 0)
    return 2 if before < p.rules.powers.get("unmovable", 0) else 1


def record_block(p, powered):
    if powered:
        p.rules.auxiliaries["block_gains"] = p.rules.auxiliaries.get("block_gains", 0) + 1
        if p.deck.in_play:
            context = p.rules.plays.get(p.deck.in_play[-1].instance_id)
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
    if p.deck.in_play and p.deck.in_play[-1].instance_id in r.plays:
        r.plays[p.deck.in_play[-1].instance_id]["rupture"] += strength
    else:
        p.strength += strength
    inferno = r.powers.get("inferno", 0)
    if inferno:
        for enemy in tuple(p.combat_enemies or ()):
            if enemy.is_alive:
                enemy.take_damage(inferno, is_attack=False)


def after_play(p, card):
    r = p.rules
    context = r.plays[card.instance_id]
    p.strength += context["rupture"]
    context["rupture"] = 0
    if card.spec.kind == "attack":
        r.attacks_finished += 1
    r.plays_finished += 1
    push(
        p,
        *[["after_card_power", card.instance_id, key] for key in r.powers],
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
    if not r.powers.get("barricade"):
        p.block = 0
    p.energy = p.energy_per_turn + r.powers.get("pyre", 0)
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
    p.strength += r.powers.get("demon_form", 0)
    from game.headless.powers.colorless import before_draw

    before_draw(p)
    push(p, ["draw", draw_count, True], ["start_powers"], ["mayhem"])
    drain(p)


def end_turn(p):
    r = p.rules
    r.turn_ending = True
    tasks = [["block", r.powers["plating"], False]] if r.powers.get("plating") else []
    tasks += [["early_end", key] for key in r.powers]
    tasks += [
        ["autoplay", c.instance_id, False]
        for c in tuple(p.deck.exhaust_pile)
        if c.definition.definition_id == "howl_from_beyond"
    ]
    tasks += [["stampede", r.powers.get("stampede", 0)], ["discard_hand"]]
    push(p, *tasks)
    drain(p)


def after_player_end(p, name):
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
