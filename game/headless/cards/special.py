"""Less common Ironclad effects, composed with the shared resolution queue."""

from copy import deepcopy
from game.headless.core.resolution import push, move_out


def clone_to(p, card, pile):
    clone = deepcopy(card)
    clone.instance_id = None
    # A new instance has no completed-play history of its own.
    clone.combat_state.return_next_turn = False
    p.deck._ensure_identity(clone)
    if pile == "hand" and len(p.hand) >= 10:
        pile = "discard_pile"
    getattr(p.deck, pile).append(clone)
    return clone


def generate(p, count, attacks_only, upgraded, free):
    if p.combat_is_ending:
        return
    from game.headless.cards.catalog import DEFAULT_CARDS

    catalog = p.catalog or DEFAULT_CARDS
    pool = [
        d
        for d in catalog.definitions
        if d.pool == "ironclad"
        and d.rarity in ("common", "uncommon", "rare")
        and d.generate_in_combat
        and (not attacks_only or d.levels[0].kind == "attack")
    ]
    pool.sort(key=lambda definition: definition.definition_id)
    if not pool:
        raise ValueError("No eligible Ironclad generation content.")
    # A dedicated owned stream, separate from shuffle/selection and target draws.
    for _ in range(count):
        definition = p.deck.generation_rng.choice(pool)
        card = catalog.create(definition.definition_id, upgrade_level=int(upgraded))
        card.combat_state.free_this_turn = free
        if definition.definition_id == "stomp":
            card.combat_state.cost_change = -p.rules.attacks_finished
        p.deck._ensure_identity(card)
        (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(card)


def apply_operation(operation, card, p, target, amount):
    if p.combat_is_ending:
        return
    r = p.rules
    if operation == "random_discard_to_hand":
        choices = list(p.deck.discard_pile)
        p.deck.selection_rng.shuffle(choices)
        for chosen in choices[:amount]:
            move_out(p, chosen)
            (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(chosen)
    elif operation == "clone":
        clone_to(p, card, "discard_pile")
    elif operation == "hp_loss":
        p.lose_hp(amount)
    elif operation == "energy":
        p.gain_energy(amount)
    elif operation == "heal":
        from game.headless.relics.combat import heal
        heal(p, amount)
    elif operation == "energy_from_attacks":
        p.gain_energy(sum(c.spec.kind == "attack" for c in p.hand))
    elif operation == "energy_if_exhausted":
        if r.exhausted_this_turn:
            p.gain_energy(amount)
    elif operation == "evil_eye":
        push(p, *[["block", card.spec.block_gain, True] for _ in range(2 if r.exhausted_this_turn else 1)])
    elif operation == "random_exhaust":
        if p.hand:
            push(p, ["exhaust", p.deck.selection_rng.choice(p.hand).instance_id])
    elif operation == "dominate":
        p.gain_strength(target.statuses.get("vulnerable") if target.is_alive else 0)
    elif operation == "double_vulnerable":
        if target.is_alive:
            target.apply_status("vulnerable", target.statuses.get("vulnerable"), source=p)
    elif operation == "area_vulnerable":
        push(
            p,
            *[
                ["status", i, "vulnerable", amount]
                for i, enemy in enumerate(p.combat_enemies)
                if enemy.is_alive
            ],
        )
    elif operation == "pillage":
        push(p, ["pillage"])
    elif operation == "rampage":
        card.combat_state.extra_damage += amount
    elif operation == "thrash":
        choices = [c for c in p.hand if c.spec.kind == "attack"]
        if choices:
            other = p.deck.selection_rng.choice(choices)
            from game.headless.cards.operations import Attack
            from game.headless.powers.status import modify_attack_damage_for_statuses

            effect = next((e for e in other.definition.effects if isinstance(e, Attack)), None)
            damage = (
                effect.damage(other, p, None)
                if effect
                else (
                    p.block
                    if other.spec.damage_equals_player_block
                    else other.spec.base_damage + other.combat_state.extra_damage
                )
            )
            card.combat_state.extra_damage += modify_attack_damage_for_statuses(
                damage, {}, p.statuses, p.strength
            )
            push(p, ["exhaust", other.instance_id])
    elif operation in ("second_wind", "fiend_fire", "stoke"):
        hand = [c for c in p.hand if operation != "second_wind" or c.spec.kind != "attack"]
        tasks = []
        for other in hand:
            tasks.append(["exhaust", other.instance_id])
            if operation == "second_wind":
                tasks.append(["block", card.spec.block_gain, True])
        if operation == "fiend_fire":
            tasks.append(["gigantification_begin", card.instance_id])
            vigor = r.powers.pop("vigor", 0)
            tasks += [
                ["attack", card.instance_id, p.combat_enemies.index(target), False, "base", 0, 0, vigor]
                for _ in hand
            ]
            tasks.append(["gigantification_end", card.instance_id])
        elif operation == "stoke":
            tasks.append(["generate", len(hand), False, card.upgraded, False])
        push(p, *tasks)
    elif operation == "infernal_blade":
        push(p, ["generate", 1, True, False, True])
    elif operation == "havoc":
        push(p, ["autoplay_draw", 1, True])
    elif operation == "cascade":
        push(p, ["autoplay_draw", r.plays[card.instance_id]["x"] + int(card.upgraded), False])
    elif operation == "primal_force":
        from game.headless.cards.catalog import DEFAULT_CARDS

        catalog = p.catalog or DEFAULT_CARDS
        definition = catalog.definition("giant_rock")
        for i, other in enumerate(p.hand):
            if other.spec.kind == "attack":
                replacement = catalog.create(definition.definition_id, upgrade_level=int(card.upgraded))
                p.deck._ensure_identity(replacement)
                p.hand[i] = replacement
    else:
        raise ValueError(f"Unknown card operation: {operation}")
