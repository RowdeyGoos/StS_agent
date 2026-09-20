"""Relic effects at room entry and the explicit player-side turn boundaries."""

from game.headless.core.resolution import push
from game.headless.relics.combat import has, memory, increment, heal
from game.headless.powers.ironclad import apply_power
from game.headless.powers.colorless import area


def upgrade(card):
    if card.upgrade_level + 1 < len(card.definition.levels):
        card.upgrade()


def enter_combat(p):
    from game.headless.relics.base import RELICS

    for relic in p.rules.relics:
        name = relic["definition_id"]
        if relic.get("data", {}).get("_melted"):
            continue
        from game.headless.relics.ancient_combat import enter
        enter(p, relic)
        strength = RELICS[name].combat_strength
        if name == "vajra":
            strength += 1
        elif name == "girya":
            strength += relic["counter"]
        elif name == "sling_of_courage" and p.rules.room_kind == "elite":
            strength += 2
        if strength:
            p.gain_strength(strength)
        if name == "oddly_smooth_stone":
            apply_power(p, "dexterity", 1)
        elif name == "gorget":
            apply_power(p, "plating", 4)
        elif name == "bronze_scales":
            memory(p, relic)["thorns"] = 3
            apply_power(p, "thorns", 3)
        elif name == "ember_tea" and relic["counter"] < 5:
            relic["counter"] += 1
            p.gain_strength(2)
        elif name == "tea_of_discourtesy" and not relic["counter"]:
            relic["counter"] = 1
            from game.headless.cards.colorless_effects import catalog

            for _ in range(2):
                card = catalog(p).create("dazed")
                p.deck._ensure_identity(card)
                p.deck.draw_pile.insert(p.deck.rng.randint(0, len(p.deck.draw_pile)), card)
        elif name == "petrified_toad" and p.rules.potion_slots and not has(p, "sozu"):
            p.rules.potions_generated.append("potion_shaped_rock")
            p.rules.potion_slots -= 1
        elif name == "fake_anchor":
            p.gain_block(4)
        elif name == "fake_snecko_eye":
            apply_power(p, "confused", 1)
        elif name == "anchor":
            p.gain_block(10)
        elif name == "stone_cracker" and p.rules.room_kind == "boss":
            cards = [c for c in p.deck.draw_pile if c.upgrade_level + 1 < len(c.definition.levels)]
            p.deck.selection_rng.shuffle(cards)
            for card in cards[:2]:
                upgrade(card)
    from game.headless.relics.damage import hp_changed, potions_changed

    hp_changed(p)
    potions_changed(p)


def start_turn(p, draw_count):
    r = p.rules
    previous_attacks = r.attacks_started
    previous_plays = p.cards_played_this_turn
    r.round_number += 1
    for relic in r.relics:
        name, m = relic["definition_id"], memory(p, relic)
        if relic.get("data", {}).get("_melted"):
            continue
        from game.headless.relics.ancient_combat import start_turn as ancient_start
        draw_count = ancient_start(p, relic, draw_count)
        from game.headless.relics.event_content import start_turn as event_start
        draw_count = event_start(p, relic, draw_count)
        if name in ("kunai", "kusarigama", "ornamental_fan", "shuriken", "rainbow_ring"):
            m["turn_attacks"] = 0
        if name in ("letter_opener", "rainbow_ring"):
            m["turn_skills"] = 0
        if name == "rainbow_ring":
            m["turn_powers"] = 0
            m["rainbow_triggered"] = False
        if name == "beating_remnant":
            m["turn_damage"] = 0
        if name == "demon_tongue":
            m["demon_triggered"] = False
        if name == "art_of_war" and r.round_number > 1 and previous_attacks == 0:
            p.gain_energy(1)
        elif name == "pocketwatch" and r.round_number > 1 and previous_plays <= 3:
            draw_count += 3
        elif name == "booming_conch" and r.round_number == 1 and r.room_kind == "elite":
            draw_count += 2
        elif name == "bag_of_preparation" and r.round_number == 1:
            draw_count += 2
        elif name == "happy_flower" and increment(relic, 3):
            p.gain_energy(1)
        elif name == "venerable_tea_set" and relic["counter"]:
            p.gain_energy(2)
            relic["counter"] = 0
        elif name == "bread":
            p.energy = max(0, p.energy - 2) if r.round_number == 1 else p.energy + 1
        elif name in ("lantern", "very_hot_cocoa") and r.round_number == 1:
            p.gain_energy(1 if name == "lantern" else 4)
        elif name == "candelabra" and r.round_number == 2:
            p.gain_energy(2)
        elif name == "chandelier" and r.round_number == 3:
            p.gain_energy(3)
        elif name == "horn_cleat" and r.round_number == 2:
            p.gain_block(14)
        elif name == "captains_wheel" and r.round_number == 3:
            p.gain_block(18)
        elif name == "sparkling_rouge" and r.round_number == 3:
            p.gain_strength(1)
            apply_power(p, "dexterity", 1)
        elif name in ("bag_of_marbles", "red_mask") and r.round_number == 1:
            for enemy in tuple(p.combat_enemies or ()):
                if enemy.is_alive:
                    enemy.apply_status("vulnerable" if name == "bag_of_marbles" else "weak", 1)
        if name == "self_forming_clay":
            p.gain_block(m.pop("next_block", 0))
    return draw_count


def hook(p, relic, event, identity):
    from game.headless.relics.ancient_combat import hook as ancient_hook
    ancient_hook(p, relic, event, identity)
    name, m, turn = relic["definition_id"], memory(p, relic), p.rules.round_number
    if p.combat_is_ending:
        return
    if event == "before_draw" and turn == 1 and name == "toolbox":
        from game.headless.relics.choices import offer

        offer(p, relic, colorless=True)
    elif event == "after_side_start":
        if name == "booming_conch" and turn == 1 and p.rules.room_kind == "elite":
            p.gain_energy(1)
        elif name == "bone_tea" and turn == 1 and not relic["counter"]:
            relic["counter"] = 1
            for card in p.hand:
                upgrade(card)
        elif name == "akabeko" and turn == 1:
            apply_power(p, "vigor", 8)
        elif name == "brimstone":
            p.gain_strength(2)
            for enemy in p.combat_enemies or ():
                if enemy.is_alive:
                    enemy.strength += 1
    elif event == "after_draw":
        if name == "mercury_hourglass":
            area(p, 3)
        elif name == "pendulum" and turn % 3 == 0:
            push(p, ["draw", 1, False])
        elif turn == 1:
            if name == "blood_vial":
                heal(p, 2)
            elif name == "festive_popper":
                area(p, 9)
            elif name == "bellows":
                for card in p.hand:
                    upgrade(card)
            elif name == "gambling_chip":
                from game.headless.core.choices import begin

                begin(
                    p,
                    relic["instance_id"],
                    tuple(p.hand),
                    operation="discard_redraw",
                    minimum=0,
                    maximum=len(p.hand),
                )
            elif name == "vexing_puzzlebox":
                from game.headless.cards.colorless_effects import pool, create

                card = create(p, p.deck.generation_rng.choice(pool(p)))
                card.combat_state.combat_cost_change = -max(0, card.cost)
    elif event == "before_end":
        if name == "orichalcum" and m.pop("orichalcum_ready", False):
            p.gain_block(6)
        elif name == "cloak_clasp":
            p.gain_block(len(p.hand))
        elif name == "ripple_basin" and not p.rules.attacks_started:
            p.gain_block(4)
        elif name == "screaming_flagon" and not p.hand:
            area(p, 20)
        elif name == "stone_calendar" and turn == 7:
            area(p, 52)
    elif event == "after_end":
        if name == "reptile_trinket":
            p.strength -= m.pop("temporary_strength", 0)
        elif name == "parrying_shield" and p.block >= 10:
            from game.headless.relics.plays import random_damage

            random_damage(p, 6)
        elif name == "joss_paper":
            count = m.pop("ethereal_exhausts", 0) + relic["counter"]
            relic["counter"] = count % 5
            push(p, ["draw", count // 5, False])
