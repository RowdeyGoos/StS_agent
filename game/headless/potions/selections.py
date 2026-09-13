"""Potion choice eligibility and snapshot semantics, without callback objects."""

from game.headless.core.choices import begin

# pile, operation, cost flag, optional, select all eligible
SETTINGS = {
    "ashwater": ("hand", "exhaust", "", True, True),
    "gamblers_brew": ("hand", "discard_redraw", "", True, True),
    "droplet_of_precognition": ("draw_pile", "move", "", False, False),
    "liquid_memories": ("discard_pile", "move", "free_this_turn", False, False),
    "touch_of_insanity": ("hand", "free_combat", "", False, False),
    **{
        k: ("offered", "move", "free_this_turn", True, False)
        for k in ("attack_potion", "skill_potion", "power_potion", "colorless_potion")
    },
}


def eligible(p, kind):
    cards = list(getattr(p.deck, SETTINGS[kind][0]))
    if kind == "touch_of_insanity":
        from game.headless.powers.ironclad import local_cost

        cards = [c for c in cards if not c.spec.x_cost and (local_cost(c) > 0 or p.card_cost(c) > 0)]
    return cards


def select(p, source, kind):
    _, op, free, optional, all_cards = SETTINGS[kind]
    cards = eligible(p, kind)
    maximum = len(cards) if all_cards else 1
    begin(p, source, cards, operation=op, free=free, minimum=0 if optional else 1, maximum=maximum)


def validate(r, p, s, kind):
    if kind not in SETTINGS:
        raise ValueError("Potion does not own this choice.")
    _, op, free, optional, all_cards = SETTINGS[kind]
    cards = eligible(p, kind)
    ids = [c.instance_id for c in cards]
    maximum = len(ids) if all_cards else min(1, len(ids))
    if (
        s["candidates"] != ids
        or s["operation"] != op
        or s["free"] != free
        or s["destination"] != "hand"
        or s["maximum"] != maximum
        or s["minimum"] != (0 if optional else maximum)
    ):
        raise ValueError("Potion choice differs from its definition.")
