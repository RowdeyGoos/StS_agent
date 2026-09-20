"""Explicit resumable card work. Tasks contain values and owned card IDs only."""

from game.headless.core.selection import HandChoice, PendingCardPlay


def requires_receipt(op):
    return op in ('exhaust', 'nec_summon', 'nec_enemy_loss') or op.startswith(('orb_', 'def_', 'hive_'))


def push(player, *tasks):
    r = player.rules
    for task in tasks:
        if requires_receipt(task[0]):
            # Capture an emitted event separately from its executable queue entry.
            # Its receipt survives suspended death hooks and is consumed once.
            r.pending_events.append(dict(context=r.active_hook, task=list(task)))
    r.tasks[0:0] = [list(t) for t in tasks]


def find(player, identity):
    return next((c for c in player.deck.all_cards() if c.instance_id == identity), None)


def move_out(player, card):
    for name in ("hand", "draw_pile", "discard_pile", "exhaust_pile", "in_play", "powers", "offered"):
        pile = getattr(player.deck, name)
        if card in pile:
            pile.remove(card)
            return


def start_play(player, card, target=None, *, auto=False, force_exhaust=False, spend_resources=False, from_reservation=False):
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
    if card in player.deck.in_play and not from_reservation:
        return
    if card.spec.uses_target:
        if target is not None and player.combat_enemies is not None and target not in player.combat_enemies:
            raise ValueError("Target is outside the owning combat.")
        if target is None and player.combat_enemies is None:
            raise ValueError("An isolated targeted play requires an enemy.")
        if target is None or not target.is_alive:
            living = [e for e in player.combat_enemies or () if e.is_alive]
            if not living:
                if auto:
                    move_out(player, card)
                    if force_exhaust or card.exhausts:
                        player.deck.exhaust_card(card)
                    else:
                        player.deck.discard_card(card)
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
    star_value = player.rules.stars if card.spec.star_x else 0
    stars_spent = 0 if auto and not spend_resources else player.star_cost(card)
    if not auto or spend_resources:
        player.energy -= cost
    move_out(player, card)
    player.deck.in_play.append(card)
    rules = player.rules
    repeats = 1 + card.combat_state.replay_count
    from game.headless.relics.combat import owned, memory
    axe = owned(player, "throwing_axe")
    if axe and not memory(player, axe).get("used"):
        memory(player, axe)["used"] = True
        repeats += 1
    if rules.powers.get("duplication"):
        repeats += 1
        rules.powers["duplication"] -= 1
    if card.enchantment is not None and card.enchantment.definition_id == "spiral":
        repeats += 1
    if card.enchantment is not None and card.enchantment.definition_id == "glam" and not card.enchantment.triggered:
        repeats += 1
    if card.spec.kind == "attack" and rules.powers.get("one_two_punch"):
        repeats += 1
        rules.powers["one_two_punch"] -= 1
    if card.spec.kind in ("skill", "block") and rules.powers.get("burst"):
        repeats += 1
        rules.powers["burst"] -= 1
    rules.plays[card.instance_id] = {
        "context": rules.active_hook,
        "target": target_slot,
        "auto": auto,
        "force_exhaust": force_exhaust,
        "x": x + (2 if card.spec.x_cost and any(r["definition_id"] == "chemical_x" and not r.get("data", {}).get("_melted") for r in rules.relics) else 0),
        "energy_value": 0 if auto and not spend_resources else cost,
        "star_value": star_value + (2 if card.spec.star_x and any(r["definition_id"] == "chemical_x" and not r.get("data", {}).get("_melted") for r in rules.relics) else 0),
        "stars_spent": stars_spent,
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
    if frame["destination"] == "discard_pile" and rules.powers.get("rebound", 0):
        frame["destination"] = "draw_pile"
        rules.powers["rebound"] -= 1
    from game.headless.powers.defect import prepare_play
    prepare_play(player, card, frame)
    push(player, ["iteration", card.instance_id])
    if not auto or spend_resources:
        from game.headless.powers.regent import spend
        spend(player, cost, stars_spent)


def drain(player):
    if player._resolving:
        return
    from game.headless.core.hook_scheduler import run

    player._resolving = True
    try:
        run(player, execute)
    finally:
        player._resolving = False


def execute(p, task):
    from game.headless.powers import ironclad as hooks
    from game.headless.cards import special
    from game.headless.powers import colorless
    from game.headless.core import choices

    op, *args = task
    r = p.rules
    if requires_receipt(op):
        r.pending_events.remove(dict(context=r.active_hook, task=task))
    if op.startswith("ancient_"):
        from game.headless.relics.ancient_combat import execute as ancient_execute
        ancient_execute(p, op, args)
    elif op == "iteration":
        (identity,) = args
        card = find(p, identity)
        if not p.combat_is_ending:
            r.plays[identity]["stage"] = "effects"
            r.plays[identity].pop("blocks_gained", None)
            from game.headless.powers.hive import before_target
            target_slot = r.plays[identity]["target"]
            before_target(p, None if target_slot is None else p.combat_enemies[target_slot])
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
                if r.powers.get('smoggy'):
                    r.auxiliaries['smoggy.ready'] = 1
            from game.headless.relics.plays import before_play
            before_play(p, card)
            from game.headless.powers.silent import before_play as silent_before_play
            silent_before_play(p, card)
            from game.headless.powers.regent import before_play as regent_before_play
            regent_before_play(p, card)
            from game.headless.powers.necrobinder import before_play as nec_before_play
            nec_before_play(p, card)
            from game.headless.powers.defect import before_play as def_before_play
            def_before_play(p, card)
            from game.headless.powers.glory import before_play as glory_before_play
            glory_before_play(p, card)
            push(
                p,
                *[["effect", identity, i] for i in range(len(card.definition.effects))],
                ["after_play", identity],
            )
        else:
            push(p, ["finish", identity])
    elif op in ('begin_card_attack', 'end_card_attack'):
        frame = r.plays[args[0]]
        if op == 'begin_card_attack':
            frame['enemy_attack'] = {}
        else:
            for enemy in tuple(p.combat_enemies or ()):
                enemy.after_card_attack(frame)
            frame.pop('enemy_attack', None)
    elif op == 'monster_death':
        enemy = p.combat_enemies[args[0]]
        if enemy.hp != 0 or not enemy.death_pending:
            raise ValueError('Unowned monster death continuation.')
        enemy.resolve_death(p)
    elif op == "effect":
        identity, index = args
        card = find(p, identity)
        if p.combat_is_ending and not getattr(card.definition.effects[index], 'resolves_after_combat_end', False):
            return
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
        card.combat_state.played_cost_override = None
        card.combat_state.played_cost_baselines = [0, 0, 0]
        if card.combat_state.turn_cost_until_played:
            card.combat_state.turn_cost_override = None
        context = r.plays.pop(identity)
        p.deck.in_play.remove(card)
        if card.combat_state.is_dupe:
            pass  # Native duplicate plays disappear without discard/exhaust hooks.
        elif context["destination"] == "powers":
            p.deck.powers.append(card)
        elif context["destination"] == "exhaust_pile":
            p.deck.exhaust_card(card)
        elif context["destination"] == "hand":
            (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(card)
        elif context["destination"] == "draw_pile":
            p.deck.draw_pile.append(card)
        else:
            p.deck.discard_card(card)
        from game.headless.relics.plays import hand_emptied
        hand_emptied(p)
        if r.regent_end_requested and not r.plays and not r.turn_ending:
            r.regent_end_requested = False
            hooks.end_turn(p)
    elif op == "shuffle_choice":
        from game.headless.core.piles import choose_after_shuffle
        choose_after_shuffle(p)
    elif op == "hand_draw":
        count = args[0]
        if r.round_number == 1:
            imbued = [c for c in reversed(p.deck.draw_pile) if c.enchantment and c.enchantment.definition_id == 'imbued']
            innate = [c for c in reversed(p.deck.draw_pile) if c.spec.innate and c not in imbued]
            p.deck.draw_pile = list(reversed(imbued)) + [c for c in p.deck.draw_pile if c not in imbued and c not in innate] + innate
            count = min(10, max(count, len(innate)))
        push(p, ['draw', count, True])
    elif op in ("draw", "draw_after_shuffle"):
        count, hand_draw = args
        from game.headless.relics.combat import has
        if count <= 0 or p.combat_is_ending or (not hand_draw and (r.powers.get("no_draw") or r.player_side and has(p, "fiddle"))):
            return
        if op == "draw":
            if not colorless.ensure_draw(p, ["draw_after_shuffle", count, hand_draw]):
                return
        elif not p.deck.draw_pile or len(p.hand) >= 10:
            # Native Draw shuffles once per iteration. A deferred AfterShuffle
            # choice may consume its last card; resuming cannot refill again.
            return
        drawn = p.deck.draw(1)
        if not drawn:
            return
        card = drawn[0]
        r.drawn_combat += 1
        from game.headless.powers.defect import draw_record
        draw_record(p, card)
        if not hand_draw:
            r.drawn_turn += 1
        push(p, ["after_draw"], ["silent_draw_hook", hand_draw, card.instance_id], ["after_draw_card", card.instance_id], ["draw", count - 1, hand_draw])
        if r.powers.get("hellraiser") and card.definition.strike:
            push(p, ["autoplay", card.instance_id, False])
    elif op == "autoplay":
        identity, force_exhaust = args
        card = find(p, identity)
        if card is not None:
            start_play(p, card, auto=True, force_exhaust=force_exhaust)
    elif op == "autoplay_draw":
        from game.headless.core.autoplay import begin
        begin(p, *args)
    elif op in ("autoplay_collect", "autoplay_take", "autoplay_next"):
        from game.headless.core.autoplay import execute as autoplay_execute
        autoplay_execute(p, op, args[0])
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
        if all_enemies:
            push(p, *[["attack", identity, i, False, expression, factor, max_hp, vigor]
                      for i, enemy in enumerate(p.combat_enemies) if enemy.is_alive])
            return
        targets = (p.combat_enemies[slot],)
        for target in targets:
            if not target.is_alive or p.combat_is_ending:
                continue
            from game.headless.cards.operations import Attack

            amount = Attack(expression=expression, factor=factor).damage(card, p, target) + vigor
            fatal = target.allows_fatal
            hp_before = target.hp
            damage = target.take_damage(amount, attacker_statuses=p.statuses, attacker_strength=p.strength)
            if "echo_kills" in r.plays[identity] and damage >= hp_before:
                r.plays[identity]["echo_kills"] += 1
            if max_hp and fatal and not target.is_alive and p.is_alive:
                p.max_hp += max_hp
                p.hp += max_hp
                r.max_hp_gained += max_hp
    elif op == "status":
        slot, name, amount = args
        if not p.combat_is_ending and p.combat_enemies[slot].is_alive:
            hooks.apply_power(p, name, amount, p.combat_enemies[slot])
    elif op in ("pillage", "pillage_after_shuffle"):
        from game.headless.relics.combat import has
        if p.combat_is_ending:
            return
        if op == "pillage":
            if r.powers.get("no_draw") or r.player_side and has(p, "fiddle"):
                return
            if not colorless.ensure_draw(p, ["pillage_after_shuffle"]):
                return
        elif not p.deck.draw_pile or len(p.hand) >= 10:
            # Resume the one native Draw already awaiting its shuffle. A live
            # choice can consume the last card; do not refill again here.
            return
        drawn = p.deck.draw(1)
        if drawn:
            r.drawn_combat += 1
            from game.headless.powers.defect import draw_record
            draw_record(p, drawn[0])
            r.drawn_turn += 1
            continuation = [["pillage"]] if drawn[0].spec.kind == "attack" else []
            push(p, ["after_draw"], ["silent_draw_hook", False, drawn[0].instance_id], ["after_draw_card", drawn[0].instance_id], *continuation)
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
        r.end_hand_remaining = [c.instance_id for c in p.hand if c.spec.end_turn_damage or c.spec.end_turn_hp_loss or c.definition.definition_id in END_HAND_CURSES]
        ethereal = [c.instance_id for c in p.hand if c.instance_id not in r.end_hand_remaining and (c.spec.ethereal or (has(p, "ghost_seed") and (c.definition.strike or c.definition.defend)))]
        push(p, *[["ethereal", i] for i in ethereal], *[["end_hand_card", i] for i in r.end_hand_remaining], *([["silent_retain"]] if r.powers.get("well_laid_plans") else []), ["discard_remaining"])
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
            if not has(p, "runic_pyramid") and not card.spec.retain and not r.powers.get("retain_hand") and not (r.round_number == 1 and has(p, "ringing_triangle")):
                p.hand.remove(card)
                p.deck.discard_card(card)
        from game.headless.relics.combat import tasks as relic_tasks
        push(p, *[["end_power", name] for name in r.powers], *relic_tasks(p, "after_end"), ["hive_player_end"], ["cleanup_turn"])
    elif op == "hive_player_end":
        from game.headless.powers.hive import player_end
        player_end(p)
    elif op == "hive_enemy_start":
        from game.headless.powers.hive import enemy_start
        enemy_start(p)
    elif op == "cleanup_turn":
        r.auxiliaries.pop('smoggy.ready', None)
        for card in p.deck.all_cards():
            card.combat_state.smog = False
            card.combat_state.free_this_turn = False
            card.combat_state.star_free_this_turn = False
            card.combat_state.turn_cost_change = 0
            card.combat_state.played_cost_baselines[1] = 0
            card.combat_state.sly_this_turn = False
            card.combat_state.retain_this_turn = False
            card.combat_state.free_until_played = False
            card.combat_state.turn_cost_override = None
    elif op == "end_power":
        hooks.after_player_end(p, args[0])
        colorless.after_end(p, args[0])
        from game.headless.powers.defect import execute as defect_execute
        defect_execute(p, "def_end_power", args)
    elif op in ("before_draw_power", "side_start_powers"):
        from game.headless.powers.turns import execute as turn_execute
        turn_execute(p, op, args)
    elif op == "start_powers":
        push(p, *[["start_power", key] for key in r.powers])
    elif op == "after_card_power":
        hooks.after_card_power(p, find(p, args[0]), args[1])
    elif op == "after_card_enchantment":
        card = find(p, args[0])
        from game.headless.powers.silent import after_card
        after_card(p, card)
        from game.headless.powers.regent import after_card as regent_after_card
        regent_after_card(p, card)
        from game.headless.powers.necrobinder import after_card as nec_after_card
        nec_after_card(p, card)
        if card.enchantment is not None and card.enchantment.definition_id in ("glam", "vigorous"):
            card.enchantment.triggered = True
        if card.enchantment is not None and card.enchantment.definition_id == "goopy" and p.is_alive:
            card.enchantment.amount += 1
    elif op == "after_card_enemies":
        from game.headless.powers.underdocks import after_card as underdocks_after_card
        underdocks_after_card(p, find(p, args[0]))
        from game.headless.powers.hive import after_card as hive_after_card
        hive_after_card(p, find(p, args[0]))
        from game.headless.powers.necrobinder import after_enemies as nec_after_enemies
        nec_after_enemies(p, find(p, args[0]))
        from game.headless.powers.silent import after_enemies
        after_enemies(p, find(p, args[0]))
        for enemy in tuple(p.combat_enemies or ()):
            if enemy.is_alive:
                enemy.after_player_card(p)
    elif op == "mayhem":
        push(p, ["autoplay_draw", r.powers.get("mayhem", 0), False])
    elif op == "start_power":
        colorless.start_power(p, args[0])
        from game.headless.powers.defect import execute as defect_execute
        defect_execute(p, "def_start_power", args)
        from game.headless.powers.silent import start_power
        start_power(p, args[0])
        if args[0] == "tyranny":
            push(p, ["regent_start_power"])
    elif op == "glory_bound_clear":
        from game.headless.powers.glory import clear_bound
        clear_bound(p)
    elif op == "begin_end_hooks":
        hooks.begin_end_hooks(p)
    elif op == "early_end":
        colorless.early_end(p, args[0])
    elif op == "after_draw_card":
        from game.headless.enchantments.base import after_draw
        card = find(p, args[0])
        if card is not None:
            if r.powers.get("confused") and card.cost >= 0 and not card.spec.x_cost:
                from game.headless.enchantments.base import randomize_cost
                randomize_cost(card, p.deck)
            after_draw(card, p.deck)
            from game.headless.powers.regent import after_draw as regent_after_draw
            regent_after_draw(p, card)
            from game.headless.powers.glory import after_draw as glory_after_draw
            glory_after_draw(p, card)
            if card.definition.definition_id == "void":
                p.energy = max(0, p.energy - 1)
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
    elif op == "spawn_wrigglers":
        p.combat_enemies[args[0]].spawn_children(p)
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
    elif op.startswith("orb_"):
        from game.headless.core.orbs import execute as orb_execute
        orb_execute(p, op, args)
    elif op.startswith("def_"):
        from game.headless.cards.defect_effects import execute as defect_execute
        defect_execute(p, op, args)
    elif op.startswith("osty_"):
        from game.headless.cards.osty_effects import execute as osty_execute
        osty_execute(p, op, args)
    elif op.startswith("nec_"):
        from game.headless.cards.necrobinder_effects import execute as nec_execute
        nec_execute(p, op, args)
    elif op.startswith("regent_"):
        from game.headless.cards.regent_effects import execute as regent_execute
        regent_execute(p, op, args)
    elif op.startswith("silent_"):
        from game.headless.cards.silent_effects import execute as silent_execute
        silent_execute(p, op, args)
    else:
        raise ValueError(f"Unknown combat work: {op}")
