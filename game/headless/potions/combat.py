"""Potion effects execute through the same resumable work queue as cards."""

from game.headless.potions.base import POTIONS
from game.headless.core.resolution import push, drain


def start(p, potion, target):
    from game.headless.powers.hive import before_target
    before_target(p, None if target is None else p.combat_enemies[target])
    r = p.rules
    identity = potion.instance_id
    r.potion_uses[identity] = dict(definition_id=potion.definition_id, target=target, effect_index=-1)
    push(
        p,
        *[["potion_effect", identity, i] for i in range(len(POTIONS[potion.definition_id].effects))],
        ["potion_finish", identity],
    )
    drain(p)


def after_use(p):
    from game.headless.relics.combat import owned, memory
    from game.headless.relics.plays import hand_emptied

    relic = owned(p, "reptile_trinket")
    if relic is not None and not p.combat_is_ending:
        p.gain_strength(3)
        m = memory(p, relic)
        m["temporary_strength"] = m.get("temporary_strength", 0) + 3
    hand_emptied(p)


def finish(p, identity):
    p.rules.potion_uses.pop(identity)
    after_use(p)


def effect(p, identity, index):
    from game.headless.powers.ironclad import apply_power
    from game.headless.relics.combat import heal, has
    from game.headless.cards.colorless_effects import pool, create
    from game.headless.generation.combat import select_cards
    from game.headless.core.choices import begin
    from game.headless.potions.selections import select

    r = p.rules
    frame = r.potion_uses[identity]
    frame["effect_index"] = index
    if p.combat_is_ending:
        return
    op, *args = POTIONS[frame["definition_id"]].effects[index]
    target = None if frame["target"] is None else p.combat_enemies[frame["target"]]
    if op == "damage":
        if target.is_alive:
            target.take_damage(args[0], is_attack=False)
    elif op in ("area", "damage_all_creatures"):
        if op == "damage_all_creatures":
            p.take_damage(args[0], is_attack=False)
        for enemy in tuple(p.combat_enemies):
            if enemy.is_alive:
                enemy.take_damage(args[0], is_attack=False)
    elif op in ("status", "all_status"):
        targets = [target] if op == "status" else list(p.combat_enemies)
        # One task per recipient preserves on-application draw/choice order.
        push(
            p,
            *[
                ["potion_status", identity, p.combat_enemies.index(e), args[0], args[1]]
                for e in targets
                if e.is_alive
            ],
        )
    elif op == "block":
        p.gain_block(args[0])
    elif op == "fortify":
        p.gain_block(p.block * 2)
    elif op == "power":
        apply_power(p, *args)
    elif op == "temporary":
        name, amount = args
        apply_power(p, name, amount)
        apply_power(p, "temporary_" + name, amount)
    elif op == "energy":
        p.gain_energy(args[0])
    elif op in ("draw", "autoplay"):
        push(p, ["draw" if op == "draw" else "autoplay_draw", args[0], False])
    elif op == "heal_percent":
        heal(p, p.max_hp * args[0] // 100)
    elif op == "max_hp":
        p.max_hp += args[0]
        r.max_hp_gained += args[0]
        heal(p, args[0])
    elif op == "fill":
        from game.headless.potions.pools import generate

        while r.potion_slots:
            # Entropic Brew deliberately uses the OUT-of-combat factory even in combat.
            potion = generate(r.potion_pool, p.deck.potion_rng)
            from game.headless.relics.combat import has
            if has(p, "sozu"):
                break
            r.potions_generated.append(potion)
            r.potion_slots -= 1
    elif op == "upgrade_hand":
        for card in p.hand:
            if card.upgrade_level + 1 < len(card.definition.levels):
                card.upgrade()
    elif op == "replay_strikes":
        for card in p.deck.all_cards():
            if card.definition.strike:
                card.combat_state.replay_count += 1
    elif op == "select":
        select(p, identity, args[0])
    elif op == "offer":
        family, kind = ("colorless", None) if args[0] == "colorless" else ("ironclad", args[0])
        options = pool(p, family, kind)
        offered = [
            create(p, d, destination="offered")
            for d in select_cards(options, p.deck.generation_rng, 3, distinct=True)
        ]
        begin(p, identity, offered, minimum=0, free="free_this_turn")
    elif op == "generate_types":
        for kind in ("attack", "skill", "power"):
            options = pool(p, "ironclad", kind)
            for definition in select_cards(options, p.deck.generation_rng, 1, distinct=True):
                create(p, definition).combat_state.free_this_turn = True
    elif op == "shuffle_hand":
        from game.headless.core.piles import shuffle
        shuffle(p, include_hand=True)
    elif op == "random_costs":
        for card in p.hand:
            if card.cost >= 0 and not card.spec.x_cost:
                v = card.combat_state
                v.turn_cost_override = p.deck.energy_rng.randrange(4)
                from game.headless.core.card_costs import mark_setter
                mark_setter(v, 'turn')
                v.turn_cost_until_played = True
                v.override_turn_baseline = v.cost_change + v.turn_cost_change
                v.override_combat_baseline = v.combat_cost_change
                v.free_this_turn = False
    elif op == "exhaust_hand":
        push(p, *[["exhaust", c.instance_id] for c in tuple(p.hand)])
    else:
        raise ValueError(f"Unsupported potion operation {op}")


def prevent_death(p):
    if p.hp > 0:
        return
    for index, item in enumerate(p.rules.potions):
        if item is not None and item["definition_id"] == "fairy_in_a_bottle":
            p.rules.potions[index] = None
            p.rules.potion_slots += 1
            from game.headless.relics.damage import potions_changed, hp_changed

            potions_changed(p)
            p.hp = max(1, p.max_hp * 30 // 100)
            hp_changed(p)
            after_use(p)
            return
