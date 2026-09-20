"""Relic damage/resource modifiers, separate from card damage expressions."""

from game.headless.relics.combat import has, memory, heal, owned
from game.headless.core.resolution import push


def strength_gain(p, amount):
    relic = owned(p, "ruined_helmet")
    if relic is not None and amount > 0 and not memory(p, relic).get("used"):
        memory(p, relic)["used"] = True
        amount *= 2
    return amount


def hp_changed(p):
    relic = owned(p, "red_skull")
    if relic is None or not p.is_alive:
        return
    m = memory(p, relic)
    active = p.hp * 2 <= p.max_hp
    if active != m.get("strength_applied", False):
        m["strength_applied"] = active
        p.gain_strength(3) if active else setattr(p, "strength", p.strength - 3)


def potions_changed(p):
    relic = owned(p, "belt_buckle")
    if relic is None:
        return
    m = memory(p, relic)
    active = p.rules.potion_slots == p.rules.potion_capacity
    if active != m.get("dexterity_applied", False):
        m["dexterity_applied"] = active
        # Native PowerCmd ignores applications after combat starts ending.
        if not p.combat_is_ending:
            p.rules.powers["dexterity"] = p.rules.powers.get("dexterity", 0) + (2 if active else -2)


def hp_loss_amount(p, amount):
    for relic in p.rules.relics:
        if relic.get("data", {}).get("_melted"):
            continue
        name = relic["definition_id"]
        if name == "tungsten_rod":
            amount = max(0, amount - 1)
        elif name == "beating_remnant":
            amount = min(amount, max(0, 20 - memory(p, relic).get("turn_damage", 0)))
    return amount


def prevent_death(p):
    if p.hp > 0:
        return
    # Native ShouldDieLate picks the first listener that can prevent death.
    # A used earlier instance must not hide a fresh Tail from a shared refill.
    for relic in p.rules.relics:
        if (relic["definition_id"] == "lizard_tail" and not relic["counter"]
                and not relic.get("data", {}).get("_melted")):
            relic["counter"] = 1
            p.hp = max(1, p.max_hp // 2)
            return


def after_damage(p, amount, *, unblockable=False, attack=False, source=None):
    hp_changed(p)
    if not p.is_alive:
        return
    source_slot = (
        p.combat_enemies.index(source) if source is not None and source in (p.combat_enemies or ()) else None
    )
    push(
        p,
        *[
            ["relic_damage", r["instance_id"], amount, unblockable, attack, source_slot]
            for r in p.rules.relics if not r.get("data", {}).get("_melted")
        ],
    )


def damage_hook(p, identity, amount, unblockable, attack, source_slot):
    relic = next(r for r in p.rules.relics if r["instance_id"] == identity)
    name, m = relic["definition_id"], memory(p, relic)
    if not p.is_alive:
        return
    if not amount:
        return
    if name == "beating_remnant":
        m["turn_damage"] = m.get("turn_damage", 0) + amount
    elif name == "centennial_puzzle" and not m.get("used"):
        m["used"] = True
        push(p, ["draw", 3, False])
    elif name == "self_forming_clay":
        m["next_block"] = m.get("next_block", 0) + 3
    elif name == "demon_tongue" and p.rules.player_side and not m.get("demon_triggered"):
        m["demon_triggered"] = True
        heal(p, amount)
    elif name == "lava_lamp" and not unblockable:
        m["damaged"] = True


def attack_bonus(p, card):
    if card is None:
        return 0
    enchantment = card.enchantment
    extra = (
        (enchantment.amount if enchantment.definition_id == "sharp" or enchantment.definition_id == "vigorous" and not enchantment.triggered else enchantment.extra_damage)
        if enchantment is not None
        else 0
    )
    extra += 3 if enchantment is not None and enchantment.definition_id == "tezcataras_ember" else 0
    for relic in p.rules.relics:
        if relic.get("data", {}).get("_melted"):
            continue
        name = relic["definition_id"]
        if card.definition.strike and name in ("strike_dummy", "fake_strike_dummy"):
            extra += 3 if name == "strike_dummy" else 1
        elif name == "miniature_cannon" and card.upgraded:
            extra += 3
        elif name == "mystic_lighter" and card.enchantment is not None:
            extra += 9
    return extra


def attack_multiplier(p, card):
    result = 2 if card and card.enchantment and card.enchantment.definition_id == "instinct" else 1
    if card and card.enchantment and card.enchantment.definition_id == "corrupted":
        result *= 1.5
    for relic in p.rules.relics:
        if (relic["definition_id"] == "pen_nib" and not relic.get("data", {}).get("_melted")
                and card is not None and memory(p, relic).get("attack_to_double") == card.instance_id):
            result *= 2
    return result


def block_multiplier(p, gain):
    card = p.current_card
    if card is None or gain <= 0:
        return 1
    result = 1
    for relic in p.rules.relics:
        name = relic["definition_id"]
        if name not in ('vambrace', 'paels_legion') or relic.get("data", {}).get("_melted"):
            continue
        m = memory(p, relic)
        unavailable = m.get('used') if name == 'vambrace' else m.get('cooldown', 0) > 0
        if not unavailable and (name == 'paels_legion' or m.get('triggering_card', card.instance_id) == card.instance_id):
            m.setdefault('triggering_card', card.instance_id)
            result *= 2
    return result


def debuff_amount(p, card, amount):
    if card is None or amount <= 0:
        return amount
    for relic in p.rules.relics:
        if relic["definition_id"] != "unsettling_lamp" or relic.get("data", {}).get("_melted"):
            continue
        m = memory(p, relic)
        if m.get("used"):
            continue
        m.setdefault("triggering_card", card.instance_id)
        if m["triggering_card"] == card.instance_id:
            amount *= 2
    return amount
