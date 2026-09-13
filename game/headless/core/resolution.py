"""Explicit resumable card work. Tasks contain values and owned card IDs only."""

from game.headless.core.selection import HandChoice, PendingCardPlay


def push(player, *tasks):
    player.rules.tasks[0:0] = [list(t) for t in tasks]


def find(player, identity):
    return next((c for c in player.deck.all_cards() if c.instance_id == identity), None)


def move_out(player, card):
    for name in ("hand", "draw_pile", "discard_pile", "exhaust_pile", "in_play", "powers"):
        pile = getattr(player.deck, name)
        if card in pile:
            pile.remove(card)
            return


def start_play(player, card, target=None, *, auto=False, force_exhaust=False):
    if player.combat_is_ending:
        return
    if card.cost < 0 and not card.spec.x_cost:
        if auto:
            move_out(player, card)
            if force_exhaust or card.exhausts:
                player.deck.exhaust_card(card)
            else:
                player.deck.discard_card(card)
        return
    if card in player.deck.in_play:
        return
    if card.spec.uses_target:
        if target is not None and player.combat_enemies is not None and target not in player.combat_enemies:
            raise ValueError("Target is outside the owning combat.")
        if target is None and player.combat_enemies is None:
            raise ValueError("An isolated targeted play requires an enemy.")
        if target is None or not target.is_alive:
            living = [e for e in player.combat_enemies or () if e.is_alive]
            if not living:
                return
            target = player.deck.target_rng.choice(living)
    else:
        target = None
    if target is not None and player.combat_enemies is None:
        player.combat_enemies = [target]
    # Legacy isolated fixtures can insert raw card objects directly into piles.
    for owned in player.deck.all_cards():
        player.deck._ensure_identity(owned)
    player.deck._ensure_identity(card)
    target_slot = None if target is None else player.combat_enemies.index(target)
    cost = player.card_cost(card)
    x = player.energy if card.spec.x_cost else 0
    if not auto:
        player.energy -= cost
    move_out(player, card)
    player.deck.in_play.append(card)
    rules = player.rules
    repeats = 1
    if card.spec.kind == "attack" and rules.powers.get("one_two_punch"):
        repeats += 1
        rules.powers["one_two_punch"] -= 1
    rules.plays[card.instance_id] = {
        "target": target_slot,
        "auto": auto,
        "force_exhaust": force_exhaust,
        "x": x,
        "remaining": repeats,
        "rupture": 0,
        "effect_index": -1,
        "destination": (
            "powers"
            if card.spec.kind == "power"
            else (
                "exhaust_pile"
                if force_exhaust
                or card.exhausts
                or (rules.powers.get("corruption") and card.spec.kind in ("skill", "block"))
                else "discard_pile"
            )
        ),
    }
    push(player, ["iteration", card.instance_id])


def drain(player):
    if player._resolving:
        return
    player._resolving = True
    try:
        while player.rules.tasks and player.pending_play is None:
            task = player.rules.tasks.pop(0)
            execute(player, task)
    finally:
        player._resolving = False


def execute(p, task):
    from game.headless.powers import ironclad as hooks
    from game.headless.cards import special

    op, *args = task
    r = p.rules
    if op == "iteration":
        (identity,) = args
        card = find(p, identity)
        if not p.combat_is_ending:
            r.plays[identity].pop("blocks_gained", None)
            p.cards_played_this_turn += 1
            if card.spec.kind == "attack":
                r.attacks_started += 1
                if r.powers.get("free_attack"):
                    r.powers["free_attack"] -= 1
                for other in p.deck.all_cards():
                    if other.definition.definition_id == "stomp":
                        other.combat_state.cost_change -= 1
            push(
                p,
                *[["effect", identity, i] for i in range(len(card.definition.effects))],
                ["after_play", identity],
            )
        else:
            push(p, ["finish", identity])
    elif op == "effect":
        identity, index = args
        if p.combat_is_ending:
            return
        card = find(p, identity)
        context = r.plays[identity]
        target = None if context["target"] is None else p.combat_enemies[context["target"]]
        context["effect_index"] = index
        result = card.definition.effects[index].apply(card, p, target)
        if isinstance(result, HandChoice):
            p.pending_play = PendingCardPlay(index, context["target"])
    elif op == "after_play":
        (identity,) = args
        card = find(p, identity)
        context = r.plays[identity]
        push(p, ["repeat", identity])
        if card.enchantment is not None and p.is_alive:
            from game.headless.enchantments.base import ENCHANTMENTS

            ENCHANTMENTS[card.enchantment.definition_id].on_play(card.enchantment, p)
        hooks.after_play(p, card)
        for enemy in tuple(p.combat_enemies or ()):
            if enemy.is_alive:
                enemy.after_player_card(p)
    elif op == "repeat":
        (identity,) = args
        context = r.plays[identity]
        context["remaining"] -= 1
        push(p, ["iteration" if context["remaining"] and not p.combat_is_ending else "finish", identity])
    elif op == "finish":
        (identity,) = args
        card = find(p, identity)
        context = r.plays.pop(identity)
        p.deck.in_play.remove(card)
        if context["destination"] == "powers":
            p.deck.powers.append(card)
        elif context["destination"] == "exhaust_pile":
            p.deck.exhaust_card(card)
        else:
            p.deck.discard_card(card)
    elif op == "draw":
        count, hand_draw = args
        if count <= 0 or p.combat_is_ending or (r.powers.get("no_draw") and not hand_draw):
            return
        drawn = p.deck.draw(1)
        if not drawn:
            return
        push(p, ["draw", count - 1, hand_draw])
        card = drawn[0]
        if r.powers.get("hellraiser") and card.definition.strike:
            push(p, ["autoplay", card.instance_id, False])
    elif op == "autoplay":
        identity, force_exhaust = args
        card = find(p, identity)
        if card is not None:
            start_play(p, card, auto=True, force_exhaust=force_exhaust)
    elif op == "autoplay_draw":
        count, force_exhaust = args
        if count <= 0 or p.combat_is_ending:
            return
        if not p.deck.draw_pile:
            p.deck._refill_draw_pile()
        if p.deck.draw_pile:
            push(
                p,
                ["autoplay", p.deck.draw_pile[-1].instance_id, force_exhaust],
                ["autoplay_draw", count - 1, force_exhaust],
            )
    elif op == "exhaust":
        (identity,) = args
        card = find(p, identity)
        if card is not None and card not in p.deck.exhaust_pile and not p.combat_is_ending:
            move_out(p, card)
            p.deck.exhaust_card(card)
    elif op == "block":
        amount, powered = args
        if not p.combat_is_ending:
            p.gain_block(amount, powered=powered)
    elif op == "attack":
        identity, slot, all_enemies, expression, factor, max_hp = args
        if p.combat_is_ending:
            return
        card = find(p, identity)
        targets = tuple(p.combat_enemies) if all_enemies else (p.combat_enemies[slot],)
        for target in targets:
            if not target.is_alive or p.combat_is_ending:
                continue
            from game.headless.cards.operations import Attack

            amount = Attack(expression=expression, factor=factor).damage(card, p, target)
            fatal = not target.statuses.get("minion") and not target.statuses.get("illusion")
            target.take_damage(amount, attacker_statuses=p.statuses, attacker_strength=p.strength)
            if max_hp and fatal and not target.is_alive and p.is_alive:
                p.max_hp += max_hp
                p.hp += max_hp
                r.max_hp_gained += max_hp
    elif op == "status":
        slot, name, amount = args
        if not p.combat_is_ending and p.combat_enemies[slot].is_alive:
            hooks.apply_power(p, name, amount, p.combat_enemies[slot])
    elif op == "pillage":
        if p.combat_is_ending or r.powers.get("no_draw"):
            return
        drawn = p.deck.draw(1)
        if drawn:
            if drawn[0].spec.kind == "attack":
                push(p, ["pillage"])
            if r.powers.get("hellraiser") and drawn[0].definition.strike:
                push(p, ["autoplay", drawn[0].instance_id, False])
    elif op == "generate":
        count, attacks_only, upgraded, free = args
        special.generate(p, count, attacks_only, upgraded, free)
    elif op == "stampede":
        (count,) = args
        if count and not p.combat_is_ending:
            choices = [c for c in p.hand if c.spec.kind == "attack" and (c.cost >= 0 or c.spec.x_cost)]
            if choices:
                card = p.deck.rng.choice(choices)
                push(p, ["autoplay", card.instance_id, False], ["stampede", count - 1])
    elif op == "discard_hand":
        for card in tuple(p.hand):
            if p.combat_is_ending:
                break
            if card.spec.end_turn_damage:
                p.take_damage(card.spec.end_turn_damage, is_attack=False)
        ethereal = [c.instance_id for c in p.hand if c.spec.ethereal]
        push(p, *[["ethereal", i] for i in ethereal], ["discard_remaining"])
    elif op == "ethereal":
        (identity,) = args
        card = find(p, identity)
        if card in p.hand and not p.combat_is_ending:
            p.hand.remove(card)
            r.auxiliaries["exhaust_ethereal"] = 1
            p.deck.exhaust_card(card)
            r.auxiliaries.pop("exhaust_ethereal", None)
    elif op == "discard_remaining":
        p.deck.discard_hand()
        push(p, *[["end_power", name] for name in r.powers])
    elif op == "end_power":
        hooks.after_player_end(p, args[0])
    elif op == "start_powers":
        hooks.after_start(p)
    else:
        raise ValueError(f"Unknown combat work: {op}")
