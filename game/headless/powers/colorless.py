"""Colorless power hooks; independent instances retain their own counters."""

from game.headless.core.resolution import push, move_out
from game.headless.core.choices import begin

INSTANCED = frozenset(("automation", "panache", "rolling_boulder", "the_bomb"))
NAMES = INSTANCED | frozenset(
    (
        "calamity",
        "entropy",
        "fasten",
        "mayhem",
        "no_block",
        "nostalgia",
        "prep_time",
        "retain_hand",
        "stratagem",
        "the_gambit",
        "dexterity",
        "vigor",
        "block_next_turn",
    )
)


def name(key):
    return key.split(":")[0]


def apply(p, key, amount):
    r = p.rules
    if key in INSTANCED:
        identity = f"{key}:{r.power_sequence}"
        r.power_sequence += 1
        r.powers[identity] = amount
        if key in ("automation", "panache", "the_bomb"):
            r.auxiliaries[identity] = {"automation": 10, "panache": 5, "the_bomb": 3}[key]
        if key == "panache":
            r.auxiliaries[identity + ".ready"] = 0
    else:
        r.powers[key] = r.powers.get(key, 0) + amount


def area(p, amount):
    for enemy in tuple(p.combat_enemies or ()):
        if enemy.is_alive and not p.combat_is_ending:
            enemy.take_damage(amount, is_attack=False)


def after_draw(p):
    for key in tuple(p.rules.powers):
        if name(key) == "automation":
            p.rules.auxiliaries[key] -= 1
            if not p.rules.auxiliaries[key]:
                p.rules.auxiliaries[key] = 10
                p.gain_energy(p.rules.powers[key])


def after_card_power(p, card, key):
    r = p.rules
    if name(key) == "panache":
        if not r.auxiliaries[key + ".ready"]:
            r.auxiliaries[key + ".ready"] = 1
            return
        r.auxiliaries[key] -= 1
        if not r.auxiliaries[key]:
            r.auxiliaries[key] = 5
            area(p, r.powers[key])
    elif key == "calamity":
        amount = r.plays[card.instance_id].pop("calamity", 0)
        if amount:
            push(p, ["generate", amount, True, False, False])


def before_draw(p):
    r = p.rules
    amount = r.powers.pop("block_next_turn", 0)
    if amount:
        p.gain_block(amount)
    if r.powers.get("prep_time"):
        apply(p, "vigor", r.powers["prep_time"])
    for card in tuple(p.deck.all_cards()):
        if card.combat_state.return_next_turn:
            card.combat_state.return_next_turn = False
            if card not in p.hand:
                move_out(p, card)
                (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(card)


def start_power(p, key):
    r = p.rules
    if p.combat_is_ending or key not in r.powers:
        return
    if name(key) == "rolling_boulder":
        area(p, r.powers[key])
        r.powers[key] += 5
    elif key == "entropy":
        begin(p, key, tuple(p.hand), operation="transform", minimum=r.powers[key], maximum=r.powers[key])
    elif key in ("crimson_mantle", "inferno"):
        from game.headless.powers.ironclad import after_hp_loss

        damage = min(p.hp, r.auxiliaries.get(key, 0))
        p.hp -= damage
        if damage:
            after_hp_loss(p, damage)
        if key == "crimson_mantle" and not p.combat_is_ending:
            p.gain_block(r.powers[key])


def early_end(p, key):
    r = p.rules
    if name(key) == "the_bomb" and not p.combat_is_ending:
        r.auxiliaries[key] -= 1
        if not r.auxiliaries[key]:
            amount = r.powers.pop(key)
            r.auxiliaries.pop(key)
            area(p, amount)


def after_end(p, key):
    if name(key) == "panache":
        p.rules.auxiliaries[key] = 5
    if key == "retain_hand":
        p.rules.powers[key] -= 1
        if not p.rules.powers[key]:
            p.rules.powers.pop(key)


def ensure_draw(p, continuation, *, hand=True):
    """Suspend the draw that caused a shuffle until Stratagem finishes."""
    if hand and len(p.hand) >= 10:
        return False
    if not p.deck.draw_pile and p.deck.discard_pile:
        p.deck._refill_draw_pile()
        if p.rules.powers.get("stratagem"):
            push(p, continuation)
            count = p.rules.powers["stratagem"]
            begin(p, "stratagem", tuple(p.deck.draw_pile), minimum=count, maximum=count)
            return False
    return bool(p.deck.draw_pile)
