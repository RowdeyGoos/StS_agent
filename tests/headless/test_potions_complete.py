"""Pinned potion outcomes, acquisition boundaries and exact private continuation."""

import json
from copy import deepcopy
from pathlib import Path
from dataclasses import asdict
import pytest

from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion, add_relic
from game.headless.run.actions import ChooseNode, UsePotion, DiscardPotion
from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection, PlayCard, EndTurn
from game.headless.potions.base import POTIONS
from game.headless.potions.pools import ORDINARY_POTIONS, generate


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other = RunEngine()
    other.restore(saved(run))
    assert saved(other) == saved(run)
    assert other.legal_actions() == run.legal_actions()
    return other


def setup(name, *, cards=None, relics=()):
    run = RunEngine.ironclad_slice(seed=17)
    if cards:
        from game.headless.run.deck import add_card

        run.state.deck.clear()
        for card in cards:
            add_card(run.state, run.cards.definition(card))
    for relic in relics:
        add_relic(run.state, relic, cards=run.cards)
    item = add_potion(run.state, name)
    run.apply(ChooseNode("fight_1"))
    run.combat.enemies[0].hp = run.combat.enemies[0].max_hp = 1000
    return run, item


def use(run, item):
    action = next(
        a for a in run.legal_actions() if isinstance(a, UsePotion) and a.instance_id == item.instance_id
    )
    run.apply(action)


def settle(run):
    for _ in range(100):
        clone(run)
        if run.combat is None:
            return
        p = run.combat.player
        if p.pending_play is None and p.rules.selection is None:
            return
        actions = run.legal_actions()
        action = next((a for a in actions if isinstance(a, ConfirmCombatSelection)), actions[0])
        other = clone(run)
        run.apply(action)
        other.apply(action)
        assert saved(other) == saved(run)
    pytest.fail("Potion continuation did not settle")


def test_scope_matches_independent_pinned_inventory():
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/headless_potion_scope.json").read_text())
    assert len(POTIONS) == 51
    assert len(ORDINARY_POTIONS) == 48
    for row in fixture["potions"]:
        actual = asdict(POTIONS[row["definition_id"]])
        assert {k: actual[k] for k in row} == row
    assert {k for k, d in POTIONS.items() if not d.in_combat_generation} == {
        "fairy_in_a_bottle",
        "fruit_juice",
        "regen_potion",
    }


@pytest.mark.parametrize("name", [k for k, d in POTIONS.items() if d.usage != "automatic"])
def test_every_manual_potion_consumes_once_and_restores(name):
    run, item = setup(name)
    p = run.combat.player
    p.hp = 30
    if name == "liquid_memories":
        p.deck.discard_pile.extend(p.hand[:2])
        del p.hand[:2]
    clone(run)
    use(run, item)
    assert all(v is None or v.instance_id != item.instance_id for v in run.state.potions)
    settle(run)
    assert not run.combat.player.rules.potion_uses
    assert not run.combat.player.rules.tasks


@pytest.mark.parametrize(
    "name,field,amount",
    [("strength_potion", "strength", 2), ("energy_potion", "energy", 2), ("block_potion", "block", 12)],
)
def test_direct_resources(name, field, amount):
    run, item = setup(name)
    p = run.combat.player
    before = getattr(p, field)
    use(run, item)
    assert getattr(p, field) == before + amount


def test_fortifier_triples_existing_block_without_dexterity():
    run, item = setup("fortifier")
    p = run.combat.player
    p.block = 8
    p.rules.powers["dexterity"] = 10
    use(run, item)
    assert p.block == 24


def test_shrink_and_vulnerable_are_targeted_and_artifact_blocks_them():
    run, item = setup("beetle_juice")
    e = run.combat.enemies[0]
    e.statuses.add("artifact", 1)
    use(run, item)
    assert not e.statuses.get("shrink")
    assert not e.statuses.get("artifact")


def test_gigantification_covers_whole_multihit_command_then_expires():
    run, item = setup("gigantification_potion", cards=["sword_boomerang", "strike", "defend"])
    use(run, item)
    p, e = run.combat.player, run.combat.enemies[0]
    boomerang = next(c for c in p.hand if c.definition.definition_id == "sword_boomerang")
    run.apply(PlayCard(boomerang.instance_id, None))
    assert e.hp == 1000 - 3 * 3 * 3
    assert not p.rules.powers["gigantification"]
    clone(run)


def test_duplicator_repeats_next_card_and_not_the_next_one():
    run, item = setup("duplicator", cards=["strike", "strike", "defend"])
    use(run, item)
    p, e = run.combat.player, run.combat.enemies[0]
    run.apply(PlayCard(next(c.instance_id for c in p.hand if c.definition.definition_id == "strike"), 0))
    assert e.hp == 988
    run.apply(PlayCard(next(c.instance_id for c in p.hand if c.definition.definition_id == "strike"), 0))
    assert e.hp == 982


def test_fairy_precedes_tail_consumes_one_and_runs_potion_hooks():
    run, item = setup("fairy_in_a_bottle", relics=["lizard_tail", "reptile_trinket", "belt_buckle"])
    p = run.combat.player
    assert not any(isinstance(a, UsePotion) for a in run.legal_actions())
    p.hp = 1
    p.lose_hp(99)
    run.combat.resolve_external_effect()
    run.sync_combat_loot()
    assert p.hp == 24
    assert all(v is None for v in run.state.potions)
    assert next(r for r in p.rules.relics if r["definition_id"] == "lizard_tail")["counter"] == 0
    assert p.strength == 3
    assert p.rules.powers["dexterity"] == 2
    clone(run)
    p.lose_hp(99)
    run.combat.resolve_external_effect()
    run.sync_combat_loot()
    assert p.hp == 40


def test_buffer_protects_self_damage_but_not_spent_on_zero_loss():
    run, item = setup("lucky_tonic", relics=["tungsten_rod"])
    p = run.combat.player
    use(run, item)
    p.lose_hp(1)
    assert p.rules.powers["buffer"] == 1
    p.lose_hp(10)
    assert p.hp == 80 and not p.rules.powers["buffer"]
    p.lose_hp(10)
    assert p.hp == 71


@pytest.mark.parametrize("name,amount", [("blood_potion", 16), ("fruit_juice", 5)])
def test_anytime_potions_between_rooms(name, amount):
    run = RunEngine.ironclad_slice()
    run.state.hp = 20
    item = add_potion(run.state, name)
    use(run, item)
    assert run.state.hp == 20 + amount
    assert run.state.max_hp == 80 + (5 if name == "fruit_juice" else 0)
    clone(run)


def test_fairy_outside_combat():
    run = RunEngine.ironclad_slice()
    item = add_potion(run.state, "fairy_in_a_bottle")
    from game.headless.relics.run_rules import damage

    damage(run.state, 100)
    assert run.state.hp == 24 and run.state.potions[0] is None
    clone(run)


def test_entropic_brew_fills_its_own_slot_and_can_generate_fairy_in_combat():
    run, item = setup("entropic_brew")
    run.combat.player.rules.potion_pool = ["fairy_in_a_bottle"]
    use(run, item)
    assert [p.definition_id for p in run.state.potions] == ["fairy_in_a_bottle"] * 3


@pytest.mark.parametrize("name,key,amount", [("clarity", "clarity", 3), ("radiant_tincture", "radiance", 3)])
def test_delayed_power_lasts_three_future_turns(name, key, amount):
    run, item = setup(name, cards=["defend"] * 10)
    use(run, item)
    p = run.combat.player
    assert p.rules.powers[key] == amount
    for remaining in (2, 1, 0):
        run.apply(EndTurn())
        assert p.rules.powers[key] == remaining
        assert p.energy == (4 if key == "radiance" else 3)
        assert len(p.hand) == (6 if key == "clarity" else 5)
        clone(run)


def test_soldiers_stew_modifies_existing_strikes_only():
    run, item = setup("soldiers_stew", cards=["strike", "twin_strike", "defend"])
    use(run, item)
    for card in run.combat.player.deck.all_cards():
        assert card.combat_state.replay_count == int(card.definition.strike)


def test_potion_selection_holds_post_use_hook_until_confirmation():
    run, item = setup("ashwater", relics=["reptile_trinket"])
    use(run, item)
    p = run.combat.player
    assert p.rules.selection is not None and p.strength == 0
    assert not any(isinstance(a, (UsePotion, DiscardPotion)) for a in run.legal_actions())
    clone(run)
    run.apply(ConfirmCombatSelection())
    assert p.strength == 3


def test_generated_route_uses_all_ordinary_potions():
    run = RunEngine.ironclad_act1(seed=0)
    assert run.state.config.reward_potions == ORDINARY_POTIONS
    clone(run)


@pytest.mark.parametrize(
    "event",
    [
        "jungle_maze_adventure",
        "aroma_of_chaos",
        "tablet_of_truth",
        "morphic_grove",
        "whispering_hollow",
        "wellspring",
        "slippery_bridge",
        "sunken_statue",
        "dense_vegetation",
        "sapphire_seed",
        "byrdonis_nest",
    ],
)
@pytest.mark.parametrize("name", ["blood_potion", "fruit_juice", "entropic_brew"])
def test_anytime_potions_preserve_event_continuation(event, name):
    from game.headless.run import events
    from game.headless.run.actions import ChooseEventOption, ChooseEventCard, LeaveEvent
    from game.headless.run.config import RunConfig

    run = RunEngine(seed=5, hp=30, gold=100, config=RunConfig())
    item = add_potion(run.state, name)
    events.begin(run.state, event, cards=run.cards)
    use(run, item)
    clone(run)
    for _ in range(30):
        actions = run.legal_actions()
        if any(isinstance(a, LeaveEvent) for a in actions):
            before = [None if p is None else asdict(p) for p in run.state.potions]
            second = add_potion(run.state, name) if None in run.state.potions else None
            if second:
                from game.headless.events.potion_context import record

                record(run.state, before)
            if second:
                use(run, second)
                clone(run)
            return
        if event == "slippery_bridge":
            action = next(
                a for a in actions if isinstance(a, ChooseEventOption) and a.option_id.startswith("overcome_")
            )
        else:
            action = next(a for a in actions if isinstance(a, (ChooseEventOption, ChooseEventCard)))
        run.apply(action)
        clone(run)
        if run.combat or run.state.hp == 0:
            return
    pytest.fail("Event did not settle")


def test_fairy_revival_during_event_damage_restores():
    from game.headless.run import events
    from game.headless.run.actions import ChooseEventOption

    run = RunEngine(seed=5, hp=1, gold=100)
    add_potion(run.state, "fairy_in_a_bottle")
    events.begin(run.state, "whispering_hollow", cards=run.cards)
    run.apply(ChooseEventOption(run.state.pending["event_instance_id"], "hug"))
    settle_actions = run.legal_actions()
    run.apply(settle_actions[0])
    assert run.state.hp == 24
    clone(run)


def test_snecko_replaces_earlier_local_costs_but_later_changes_apply():
    run, item = setup("snecko_oil", cards=["stomp", "defend", "bash"])
    p = run.combat.player
    card = next(c for c in p.hand if c.definition.definition_id == "stomp")
    card.combat_state.cost_change = -2
    card.combat_state.combat_cost_change = -3
    card.combat_state.free_this_turn = True
    before = p.deck.generation_rng.getstate()
    use(run, item)
    value = card.combat_state.turn_cost_override
    assert p.card_cost(card) == value
    assert p.deck.generation_rng.getstate() == before
    card.combat_state.cost_change -= 1
    assert p.card_cost(card) == max(0, value - 1)
    clone(run)
    run.apply(EndTurn())
    assert card.combat_state.turn_cost_override is None


def test_touch_of_insanity_free_combat_survives_turns_not_master_deck():
    run, item = setup("touch_of_insanity", cards=["bash", "defend", "strike"])
    use(run, item)
    p = run.combat.player
    card = next(c for c in p.hand if c.definition.definition_id == "bash")
    run.apply(ChooseCombatCard(card.instance_id))
    run.apply(ConfirmCombatSelection())
    assert p.card_cost(card) == 0
    run.apply(EndTurn())
    assert p.card_cost(card) == 0
    assert not any(c.combat_state.free_this_combat for c in run.state.deck)
    clone(run)


def test_bottled_potential_merges_all_nonexhausted_piles():
    run, item = setup("bottled_potential", cards=["defend"] * 8)
    p = run.combat.player
    p.deck.discard_pile.extend(p.hand[:2])
    del p.hand[:2]
    ids = {c.instance_id for c in p.deck.all_cards()}
    use(run, item)
    assert not p.deck.discard_pile and len(p.hand) == 5 and len(p.deck.draw_pile) == 3
    assert {c.instance_id for c in p.deck.all_cards()} == ids
    clone(run)


def test_thorns_kill_attacker_before_later_hits_but_current_hit_lands():
    run, item = setup("liquid_bronze")
    p, e = run.combat.player, run.combat.enemies[0]
    use(run, item)
    e.hp = 3
    p.take_damage(10, source=e)
    assert p.hp == 70 and e.hp == 0


def test_regen_and_temporary_stats_expire_at_player_end():
    run, item = setup("regen_potion")
    p = run.combat.player
    p.hp = 30
    use(run, item)
    run.apply(EndTurn())
    assert p.rules.powers["regen"] == 4
    run2, item2 = setup("flex_potion")
    use(run2, item2)
    assert run2.combat.player.strength == 5
    run2.apply(EndTurn())
    assert run2.combat.player.strength == 0


def test_demise_bypasses_block_after_enemy_turn():
    run, item = setup("powdered_demise")
    e = run.combat.enemies[0]
    use(run, item)
    e.block = 50
    from game.headless.powers.lifecycle import after_owner_side_turn_end

    after_owner_side_turn_end(e)
    assert e.hp == 991 and e.block == 50


@pytest.mark.parametrize(
    "name",
    ["ashwater", "gamblers_brew", "distilled_chaos", "glowwater_potion", "bottled_potential", "snecko_oil"],
)
def test_nested_draw_choices_preserve_potion_post_use_work(name):
    run, item = setup(
        name,
        cards=["armaments", "defend", "strike", "defend", "strike", "defend", "defend"],
        relics=["reptile_trinket"],
    )
    p = run.combat.player
    p.rules.powers["stratagem"] = 1
    p.rules.powers["dark_embrace"] = 1
    p.deck.discard_pile.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    if name == "distilled_chaos":
        from game.headless.core.resolution import move_out

        card = next(c for c in p.deck.all_cards() if c.definition.definition_id == "armaments")
        move_out(p, card)
        p.deck.draw_pile.append(card)
    use(run, item)
    if name in ("ashwater", "gamblers_brew") and p.rules.selection:
        run.apply(ChooseCombatCard(p.rules.selection["candidates"][0]))
        run.apply(ConfirmCombatSelection())
    settle(run)
    assert p.strength == 3


@pytest.mark.parametrize("corruption", ["effect", "finish", "source", "identity", "target"])
def test_corrupt_pending_potion_rejected_atomically(corruption):
    run, item = setup("ashwater")
    use(run, item)
    bad = saved(run)
    rules = bad["combat"]["player"]["rules"]
    if corruption == "effect":
        rules["potion_uses"][item.instance_id]["effect_index"] = 8
    elif corruption == "finish":
        rules["tasks"] = [t for t in rules["tasks"] if t[0] != "potion_finish"]
    elif corruption == "source":
        rules["selection"]["source"] = "run.item.99999"
    elif corruption == "identity":
        rules["potion_uses"]["run.item.99999"] = rules["potion_uses"].pop(item.instance_id)
    elif corruption == "target":
        rules["potion_uses"][item.instance_id]["target"] = 0
    before = saved(run)
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before


def test_full_pool_merchant_prices_and_restore():
    from game.headless.run import shop
    from game.headless.potions.pools import COSTS
    from game.headless.run.config import RunConfig

    run = RunEngine(seed=4, config=RunConfig(reward_potions=ORDINARY_POTIONS))
    shop.begin(run.state, run.cards)
    offers = [o for o in run.state.pending["offers"] if o["kind"] == "potion"]
    assert len(offers) == 2
    for offer in offers:
        assert offer["definition_id"] in ORDINARY_POTIONS
        base = COSTS[POTIONS[offer["definition_id"]].rarity]
        assert round(base * 0.95) <= offer["price"] <= round(base * 1.05)
    clone(run)


def test_potion_finish_cannot_precede_nested_autoplay():
    run, item = setup(
        "distilled_chaos", cards=["discovery", "strike", "strike", "defend"], relics=["reptile_trinket"]
    )
    p = run.combat.player
    from game.headless.core.resolution import move_out

    card = next(c for c in p.deck.all_cards() if c.definition.definition_id == "discovery")
    move_out(p, card)
    p.deck.draw_pile.append(card)
    use(run, item)
    assert p.rules.selection
    bad = saved(run)
    tasks = bad["combat"]["player"]["rules"]["tasks"]
    finish = next(t for t in tasks if t[0] == "potion_finish")
    tasks.remove(finish)
    tasks.insert(0, finish)
    with pytest.raises(ValueError):
        run.restore(bad)
    settle(run)


def test_touch_excludes_x_and_locally_free_cards_but_allows_corruption_discount():
    run, item = setup("touch_of_insanity", cards=["whirlwind", "strike", "shrug_it_off", "bash"])
    p = run.combat.player
    strike = next(c for c in p.hand if c.definition.definition_id == "strike")
    strike.combat_state.free_this_turn = True
    p.rules.powers["corruption"] = 1
    use(run, item)
    names = {c.definition.definition_id for c in p.hand if c.instance_id in p.rules.selection["candidates"]}
    assert names == {"shrug_it_off", "bash"}
    clone(run)


def test_local_cost_clamps_after_global_tangled():
    run, item = setup("touch_of_insanity", cards=["stomp", "strike"])
    p = run.combat.player
    stomp = next(c for c in p.hand if c.definition.definition_id == "stomp")
    stomp.combat_state.cost_change = -5
    p.statuses.add("tangled", 1)
    assert p.card_cost(stomp) == 0
    stomp.combat_state.free_this_combat = True
    assert p.card_cost(stomp) == 1


def test_event_potion_history_cannot_restore_the_consumed_bottle():
    from game.headless.run import events

    run = RunEngine(seed=5)
    item = add_potion(run.state, "fruit_juice")
    events.begin(run.state, "jungle_maze_adventure", cards=run.cards)
    use(run, item)
    bad = saved(run)
    pending = bad["state"]["pending"]
    change = pending["potion_changes"][0]
    change["after"] = deepcopy(change["before"])
    bad["state"]["potions"] = deepcopy(change["before"])
    with pytest.raises(ValueError):
        run.restore(bad)


def test_beetle_shrink_decrements_after_each_of_four_enemy_turns():
    run, item = setup("beetle_juice", cards=["defend"] * 5)
    use(run, item)
    e = run.combat.enemies[0]
    for remaining in (3, 2, 1, 0):
        run.apply(EndTurn())
        assert e.statuses.get("shrink") == remaining
        clone(run)


def test_demise_counts_as_a_debuff_for_rend():
    run, item = setup("powdered_demise", cards=["rend", "defend"])
    use(run, item)
    p, e = run.combat.player, run.combat.enemies[0]
    card = next(c for c in p.hand if c.definition.definition_id == "rend")
    before = e.hp
    run.apply(PlayCard(card.instance_id, 0))
    assert before - e.hp == card.spec.base_damage + 5


@pytest.mark.parametrize("strength,bonus", [(0, 5), (10, 0)])
def test_shackling_counts_actual_negative_strength_for_rend(strength, bonus):
    run, item = setup("shackling_potion", cards=["rend", "defend"])
    p, e = run.combat.player, run.combat.enemies[0]
    e.strength = strength
    use(run, item)
    card = next(c for c in p.hand if c.definition.definition_id == "rend")
    run.apply(PlayCard(card.instance_id, 0))
    assert e.hp == 1000 - card.spec.base_damage - bonus
