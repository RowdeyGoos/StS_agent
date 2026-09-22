"""Card-play, exhaust and shuffle relic hooks, each resumable in owned order."""

from game.headless.core.resolution import push, find
from game.headless.relics.combat import has, memory, increment
from game.headless.powers.ironclad import apply_power
from game.headless.powers.colorless import area


def random_damage(p, amount):
    living = [e for e in p.combat_enemies or () if e.is_alive]
    if living and not p.combat_is_ending:
        p.deck.target_rng.choice(living).take_damage(amount, is_attack=False)


def before_play(p, card):
    from game.headless.relics.ancient_combat import before_play as ancient_before
    ancient_before(p, card)
    frame = p.rules.plays[card.instance_id]
    for relic in p.rules.relics:
        if relic.get("data", {}).get("_melted"):
            continue
        name, m = relic["definition_id"], memory(p, relic)
        if name == "pen_nib" and card.spec.kind == "attack":
            if increment(relic, 10):
                m["attack_to_double"] = card.instance_id
        elif name == "intimidating_helmet" and frame["energy_value"] >= 2:
            p.gain_block(4)


def hook(p, relic, event, identity):
    from game.headless.relics.ancient_combat import hook as ancient_hook
    ancient_hook(p, relic, event, identity)
    name, m = relic["definition_id"], memory(p, relic)
    card = find(p, identity)
    if event == "after_play":
        if name == "pen_nib" and m.get("attack_to_double") == identity:
            m.pop("attack_to_double")
        if name in ("vambrace", "unsettling_lamp") and m.get("triggering_card") == identity:
            m["used"] = True
        if p.combat_is_ending:
            return
        kind = card.spec.kind
        if kind == "block":
            kind = "skill"
        key = {"attack": "turn_attacks", "skill": "turn_skills", "power": "turn_powers"}.get(kind)
        if key and key in m:
            m[key] = m.get(key, 0) + 1
        if kind == "attack":
            third = m.get("turn_attacks", 1) % 3 == 0
            if name == "nunchaku" and increment(relic, 10):
                p.gain_energy(1)
            elif third and name == "shuriken":
                p.gain_strength(1)
            elif third and name == "kunai":
                apply_power(p, "dexterity", 1)
            elif third and name == "ornamental_fan":
                p.gain_block(4)
            elif third and name == "kusarigama":
                random_damage(p, 6)
        elif kind == "skill":
            if name == "tuning_fork" and increment(relic, 10):
                p.gain_block(7)
            elif name == "letter_opener" and m["turn_skills"] % 3 == 0:
                area(p, 5)
        elif kind == "power":
            if name == "game_piece":
                push(p, ["draw", 1, False])
            elif name == "permafrost" and not m.get("used"):
                m["used"] = True
                p.gain_block(7)
            elif name == "mummified_hand":
                from game.headless.powers.ironclad import card_cost

                cards = [c for c in p.hand if c.cost >= 0 and card_cost(p, c) > 0]
                if cards:
                    p.deck.selection_rng.choice(cards).combat_state.free_this_turn = True
        if (
            name == "rainbow_ring"
            and not m.get("rainbow_triggered")
            and all(m.get(k, 0) for k in ("turn_attacks", "turn_skills", "turn_powers"))
        ):
            m["rainbow_triggered"] = True
            p.gain_strength(1)
            apply_power(p, "dexterity", 1)
        elif name == "razor_tooth" and kind in ("attack", "skill"):
            from game.headless.relics.turns import upgrade

            upgrade(card)
    elif event in ("exhaust", "exhaust_ethereal") and not p.combat_is_ending:
        if name == "charons_ashes":
            area(p, 3)
        elif name == "burning_sticks" and card.spec.kind in ("skill", "block") and not m.get("used"):
            m["used"] = True
            from game.headless.cards.special import clone_to

            clone_to(p, card, "hand")
        elif name == "joss_paper":
            if event == "exhaust_ethereal":
                m["ethereal_exhausts"] = m.get("ethereal_exhausts", 0) + 1
            elif increment(relic, 5):
                push(p, ["draw", 1, False])
    elif event == "shuffle" and name == "the_abacus" and not p.combat_is_ending:
        p.gain_block(6)


def hand_emptied(p):
    if not p.hand and p.rules.player_side and not p.rules.turn_ending:
        # The empty-hand event is captured once. Each native Top listener draws
        # even when an earlier listener has already filled the hand.
        push(p, *[["draw", 1, False] for relic in p.rules.relics
                  if relic["definition_id"] == "unceasing_top"
                  and not relic.get("data", {}).get("_melted")])
