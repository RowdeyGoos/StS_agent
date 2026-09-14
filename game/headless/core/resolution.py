"""Explicit resumable card work. Tasks contain values and owned card IDs only."""

from game.headless.core.selection import HandChoice, PendingCardPlay


def push(player, *tasks):
    player.rules.tasks[0:0] = [list(t) for t in tasks]


def find(player, identity):
    return next((c for c in player.deck.all_cards() if c.instance_id == identity), None)


def move_out(player, card):
    for name in ("hand", "draw_pile", "discard_pile", "exhaust_pile", "in_play", "powers", "offered"):
        pile = getattr(player.deck, name)
        if card in pile:
            pile.remove(card)
            return


def start_play(player, card, target=None, *, auto=False, force_exhaust=False):
    if player.combat_is_ending:
        return
    from game.headless.cards.curses import can_play
    if not can_play(player, card, auto=auto):
        if auto:
            move_out(player, card)
            player.deck.exhaust_card(card) if force_exhaust or card.exhausts else player.deck.discard_card(card)
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
    repeats = 1 + card.combat_state.replay_count
    if rules.powers.get("duplication"):
        repeats += 1
        rules.powers["duplication"] -= 1
    if card.enchantment is not None and card.enchantment.definition_id == "glam" and not card.enchantment.triggered:
        repeats += 1
    if card.spec.kind == "attack" and rules.powers.get("one_two_punch"):
        repeats += 1
        rules.powers["one_two_punch"] -= 1
    rules.plays[card.instance_id] = {
        "target": target_slot,
        "auto": auto,
        "force_exhaust": force_exhaust,
        "x": x + (2 if card.spec.x_cost and any(r["definition_id"] == "chemical_x" for r in rules.relics) else 0),
        "energy_value": 0 if auto else (x if card.spec.x_cost else cost),
        "remaining": repeats,
        "rupture": 0,
        "effect_index": -1,
        "stage": "effects",
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
    frame = rules.plays[card.instance_id]
    if (
        frame["destination"] == "discard_pile"
        and card.spec.kind in ("attack", "skill", "block")
        and rules.attacks_started + rules.skills_started < rules.powers.get("nostalgia", 0)
    ):
        frame["destination"] = "draw_pile"
    push(player, ["iteration", card.instance_id])


def drain(player):
    if player._resolving:
        return
    player._resolving = True
    try:
        while player.rules.tasks and player.pending_play is None and player.rules.selection is None:
            task = player.rules.tasks.pop(0)
            execute(player, task)
    finally:
        player._resolving = False


def execute(p, task):
    from game.headless.powers import ironclad as hooks
    from game.headless.cards import special
    from game.headless.powers import colorless
    from game.headless.core import choices

    op, *args = task
    r = p.rules
    if op == "iteration":
        (identity,) = args
        card = find(p, identity)
        if not p.combat_is_ending:
            r.plays[identity]["stage"] = "effects"
            r.plays[identity].pop("blocks_gained", None)
            p.cards_played_this_turn += 1
            if card.spec.kind == "attack":
                r.attacks_started += 1
                if r.powers.get("calamity"):
                    r.plays[identity]["calamity"] = r.powers["calamity"]
                if r.powers.get("free_attack"):
                    r.powers["free_attack"] -= 1
                for other in p.deck.all_cards():
                    if other.definition.definition_id == "stomp" and other not in p.deck.offered:
                        other.combat_state.cost_change -= 1
            if card.spec.kind in ("skill", "block"):
                r.skills_started += 1
            from game.headless.relics.plays import before_play
            before_play(p, card)
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
        context["stage"] = "enchantment"
        push(p, ["after_enchantment", identity])
        if card.enchantment is not None and p.is_alive:
            from game.headless.enchantments.base import ENCHANTMENTS

            ENCHANTMENTS[card.enchantment.definition_id].on_play(card.enchantment, p)
    elif op == "after_enchantment":
        (identity,) = args
        r.plays[identity]["stage"] = "hooks"
        push(p, ["repeat", identity])
        hooks.after_play(p, find(p, identity))

    elif op == "repeat":
        (identity,) = args
        context = r.plays[identity]
        context["remaining"] -= 1
        push(p, ["iteration" if context["remaining"] and not p.combat_is_ending else "finish", identity])
    elif op == "finish":
        (identity,) = args
        card = find(p, identity)
        card.combat_state.free_until_played = False
        card.combat_state.turn_cost_override = None
        context = r.plays.pop(identity)
        p.deck.in_play.remove(card)
        if context["destination"] == "powers":
            p.deck.powers.append(card)
        elif context["destination"] == "exhaust_pile":
            p.deck.exhaust_card(card)
        elif context["destination"] == "draw_pile":
            p.deck.draw_pile.append(card)
        else:
            p.deck.discard_card(card)
        from game.headless.relics.plays import hand_emptied
        hand_emptied(p)
    elif op == "shuffle_choice":
        from game.headless.core.piles import choose_after_shuffle
        choose_after_shuffle(p)
    elif op == "draw":
        count, hand_draw = args
        if count <= 0 or p.combat_is_ending or (r.powers.get("no_draw") and not hand_draw):
            return
        if not colorless.ensure_draw(p, task):
            return
        drawn = p.deck.draw(1)
        if not drawn:
            return
        card = drawn[0]
        push(p, ["after_draw_card", card.instance_id], ["after_draw"], ["draw", count - 1, hand_draw])
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
        if not colorless.ensure_draw(p, task, hand=False):
            return
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
        identity, slot, all_enemies, expression, factor, max_hp, vigor = args
        if p.combat_is_ending:
            return
        card = find(p, identity)
        targets = tuple(p.combat_enemies) if all_enemies else (p.combat_enemies[slot],)
        for target in targets:
            if not target.is_alive or p.combat_is_ending:
                continue
            from game.headless.cards.operations import Attack

            amount = Attack(expression=expression, factor=factor).damage(card, p, target) + vigor
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
        if not colorless.ensure_draw(p, task):
            return
        drawn = p.deck.draw(1)
        if drawn:
            continuation = [["pillage"]] if drawn[0].spec.kind == "attack" else []
            push(p, ["after_draw"], *continuation)
            if r.powers.get("hellraiser") and drawn[0].definition.strike:
                push(p, ["autoplay", drawn[0].instance_id, False])
    elif op == "generate":
        count, attacks_only, upgraded, free, distinct = args
        special.generate(p, count, attacks_only, upgraded, free, distinct)
    elif op == "stampede":
        (count,) = args
        if count and not p.combat_is_ending:
            choices = [c for c in p.hand if c.spec.kind == "attack" and (c.cost >= 0 or c.spec.x_cost)]
            if choices:
                card = p.deck.rng.choice(choices)
                push(p, ["autoplay", card.instance_id, False], ["stampede", count - 1])
    elif op == "discard_hand":
        from game.headless.relics.combat import has
        from game.headless.cards.curses import END_HAND_CURSES
        r.end_turn_hand_size = len(p.hand)
        r.end_hand_remaining = [c.instance_id for c in p.hand if c.spec.end_turn_damage or c.definition.definition_id in END_HAND_CURSES]
        ethereal = [c.instance_id for c in p.hand if c.instance_id not in r.end_hand_remaining and (c.spec.ethereal or (has(p, "ghost_seed") and (c.definition.strike or c.definition.defend)))]
        push(p, *[["ethereal", i] for i in ethereal], *[["end_hand_card", i] for i in r.end_hand_remaining], ["discard_remaining"])
    elif op == "end_hand_card":
        from game.headless.cards.curses import end_in_hand
        if not r.end_hand_remaining or r.end_hand_remaining.pop(0) != args[0]:
            raise ValueError("Invalid end-of-hand continuation.")
        card = find(p, args[0])
        if card is not None:
            end_in_hand(p, card)
    elif op == "ethereal":
        (identity,) = args
        card = find(p, identity)
        if card in p.hand and not p.combat_is_ending:
            p.hand.remove(card)
            r.auxiliaries["exhaust_ethereal"] = 1
            p.deck.exhaust_card(card)
            r.auxiliaries.pop("exhaust_ethereal", None)
    elif op == "discard_remaining":
        for card in tuple(p.hand):
            from game.headless.relics.combat import has
            if not card.spec.retain and not r.powers.get("retain_hand") and not (r.round_number == 1 and has(p, "ringing_triangle")):
                p.hand.remove(card)
                p.deck.discard_card(card)
        from game.headless.relics.combat import tasks as relic_tasks
        push(p, *[["end_power", name] for name in r.powers], *relic_tasks(p, "after_end"), ["cleanup_turn"])
    elif op == "cleanup_turn":
        for card in p.deck.all_cards():
            card.combat_state.free_this_turn = False
            card.combat_state.free_until_played = False
            card.combat_state.turn_cost_override = None
    elif op == "end_power":
        hooks.after_player_end(p, args[0])
        colorless.after_end(p, args[0])
    elif op == "start_powers":
        push(p, *[["start_power", key] for key in r.powers])
    elif op == "after_card_power":
        hooks.after_card_power(p, find(p, args[0]), args[1])
    elif op == "after_card_enchantment":
        card = find(p, args[0])
        if card.enchantment is not None and card.enchantment.definition_id == "glam":
            card.enchantment.triggered = True
    elif op == "after_card_enemies":
        for enemy in tuple(p.combat_enemies or ()):
            if enemy.is_alive:
                enemy.after_player_card(p)
    elif op == "mayhem":
        push(p, ["autoplay_draw", r.powers.get("mayhem", 0), False])
    elif op == "start_power":
        colorless.start_power(p, args[0])
    elif op == "early_end":
        colorless.early_end(p, args[0])
    elif op == "after_draw_card":
        from game.headless.enchantments.base import after_draw
        card = find(p, args[0])
        if card is not None:
            after_draw(card, p.deck)
    elif op == "after_draw":
        colorless.after_draw(p)
    elif op == "energy":
        p.gain_energy(args[0])
    elif op == "selected":
        choices.resolve(p, *args)
    elif op == "catastrophe":
        count = args[0]
        if count > 0 and p.deck.draw_pile and not p.combat_is_ending:
            available = [c for c in p.deck.draw_pile if c.cost >= 0 or c.spec.x_cost]
            available = available or list(p.deck.draw_pile)
            from game.headless.core.native_rng import NativeRng
            if isinstance(p.deck.rng, NativeRng):
                from game.headless.core.native_shuffle import stable_shuffle
                # Native CardPile enumerates from the top.
                available.reverse()
                stable_shuffle(available, p.deck.rng)
            else:
                p.deck.rng.shuffle(available)
            push(p, ["autoplay", available[0].instance_id, False], ["catastrophe", count - 1])
    elif op == "random_hit":
        from game.headless.cards.colorless_effects import hit

        living = [e for e in p.combat_enemies if e.is_alive]
        if living and not p.combat_is_ending:
            hit(p, find(p, args[0]), p.deck.target_rng.choice(living), extra=args[1])
    elif op == "gigantification_begin":
        from game.headless.potions.powers import begin_attack
        begin_attack(p, find(p, args[0]), queue_end=False)
    elif op == "gigantification_end":
        from game.headless.potions.powers import end_attack
        end_attack(p, args[0])
    elif op == "potion_effect":
        from game.headless.potions.combat import effect
        effect(p, *args)
    elif op == "potion_finish":
        from game.headless.potions.combat import finish
        finish(p, *args)
    elif op == "potion_status":
        _, slot, key, amount = args
        if not p.combat_is_ending and p.combat_enemies[slot].is_alive:
            p.combat_enemies[slot].apply_status(key, amount, source=p)
    elif op == "relic_damage":
        from game.headless.relics.damage import damage_hook
        damage_hook(p, *args)
    elif op == "relic_hook":
        from game.headless.relics.combat import execute as relic_execute
        relic_execute(p, *args)
    else:
        raise ValueError(f"Unknown combat work: {op}")
