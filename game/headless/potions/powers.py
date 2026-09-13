"""Potion-granted powers at existing resource and turn boundaries."""

NAMES = frozenset(
    (
        "clarity",
        "radiance",
        "thorns",
        "buffer",
        "ritual",
        "regen",
        "gigantification",
        "duplication",
        "temporary_strength",
        "temporary_dexterity",
    )
)


def start_turn(p, draw_count):
    r = p.rules
    if r.powers.get("clarity"):
        draw_count += 1
        r.powers["clarity"] -= 1
    if r.powers.get("radiance"):
        p.gain_energy(1)
        r.powers["radiance"] -= 1
    return draw_count


def after_end(p, key):
    r = p.rules
    amount = r.powers.get(key, 0)
    if key == "ritual" and p.is_alive:
        p.gain_strength(amount)
    elif key == "regen" and amount:
        from game.headless.relics.combat import heal

        heal(p, amount)
        r.powers[key] -= 1
    elif key == "temporary_strength":
        p.strength -= r.powers.pop(key, 0)
    elif key == "temporary_dexterity":
        r.powers["dexterity"] = r.powers.get("dexterity", 0) - r.powers.pop(key, 0)
    elif key == "duplication":
        r.powers.pop(key, None)


def begin_attack(p, card, *, queue_end=True):
    """Capture one attack command, keeping all of its hits under one multiplier."""
    r = p.rules
    if (
        card.spec.kind != "attack"
        or not r.powers.get("gigantification")
        or any(frame.get("gigantification") for frame in r.plays.values())
    ):
        return
    r.plays[card.instance_id]["gigantification"] = True
    from game.headless.core.resolution import push

    if queue_end:
        push(p, ["gigantification_end", card.instance_id])


def end_attack(p, identity):
    if p.rules.plays[identity].pop("gigantification", False):
        p.rules.powers["gigantification"] -= 1


def attack_multiplier(p, card):
    return 3 if card is not None and p.rules.plays.get(card.instance_id, {}).get("gigantification") else 1
