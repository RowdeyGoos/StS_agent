"""Pinned source hook order plus independent native shuffle vectors.

These are Python command/restore regressions, not native full-turn executions.
"""

from copy import deepcopy

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.cards.colorless_effects import create
from game.headless.cards.special import clone_to
from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection, PlayCard
from game.headless.core.choices import resolve
from game.headless.core.deck import Deck
from game.headless.core.native_rng import NativeRng
from game.headless.core.piles import choose_after_shuffle, stratagem_cards
from game.headless.powers.ironclad import apply_power
from game.headless.run.actions import UsePotion
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion, add_relic
from tests.headless.test_native_combat_rng import VECTORS, cards_for
from tests.headless.test_potions_complete import saved, clone


def combat(cards, *, relics=(), draw=0):
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(), card_ids=cards)
    for relic in relics:
        add_relic(run.state, relic, cards=run.cards)
    run.start_combat(encounter_id="overgrowth_cubex", cards_per_turn=draw)
    return run


@pytest.mark.parametrize(
    "row", [r for r in VECTORS["shuffles"] if r["stable"]], ids=lambda r: f"{r['seed']}-{r['size']}"
)
def test_bottled_merge_matches_native_stable_shuffle_physical_copy_vectors(row):
    cards, rng = cards_for(row), NativeRng(row["seed"])
    deck = Deck([], rng)
    # Native input recipe: discard, current draw top-first, then hand at bottom.
    a, b = len(cards) // 3, 2 * len(cards) // 3
    deck.discard_pile = cards[:a]
    deck.draw_pile = list(reversed(cards[a:b]))
    deck.hand = cards[b:]
    exhausted = DEFAULT_CARDS.create("strike", instance_id="exhausted")
    deck.exhaust_pile = [exhausted]
    deck.shuffle_piles(include_hand=True)
    assert [int(c.instance_id) for c in reversed(deck.draw_pile)] == row["order"]
    assert rng.counter == row["counter"] and rng.next_double() == row["suffix"]
    assert not deck.hand and not deck.discard_pile and deck.exhaust_pile == [exhausted]


@pytest.mark.parametrize("trigger", ["potion", "refill"])
def test_stratagem_precedes_unpowered_abacus_then_resumes_real_draw_with_restore(trigger):
    run = combat(["finesse"] + ["strike", "defend", "bash"] * 3, relics=("the_abacus",))
    p = run.combat.player
    assert p.block == 0  # Initial shuffle has no AfterShuffle.
    finesse = next(c for c in p.deck.draw_pile if c.definition.definition_id == "finesse")
    p.deck.draw_pile.remove(finesse)
    p.hand.append(finesse)
    p.deck.discard_pile = p.deck.draw_pile
    p.deck.draw_pile = []
    apply_power(p, "stratagem", 1)
    apply_power(p, "automation", 2)
    apply_power(p, "dexterity", 9)
    p.apply_status("frail", 2)
    if trigger == "potion":
        item = add_potion(run.state, "bottled_potential")
        # Inventory was added after combat construction; sync its owned mirror.
        from dataclasses import asdict

        p.rules.potions = [None if x is None else asdict(x) for x in run.state.potions]
        run.apply(UsePotion(item.instance_id))
        expected_hand = 6
    else:
        run.apply(PlayCard(finesse.instance_id))
        expected_hand = 2
    assert p.rules.selection["source"] == "stratagem"
    block_before = p.block
    assert block_before == (0 if trigger == "potion" else 9)
    assert p.rules.tasks[0][0] == "relic_hook"
    other = clone(run)
    chosen = p.rules.selection["candidates"][0]
    for action in (ChooseCombatCard(chosen), ConfirmCombatSelection()):
        run.apply(action)
        other.apply(action)
        assert saved(run) == saved(other)
    assert len(p.hand) == expected_hand
    # Stratagem is an Add, not Draw. Automation does not trigger on the selection.
    assert p.block == block_before + 6
    automation = next(k for k in p.rules.auxiliaries if k.startswith("automation"))
    assert p.rules.auxiliaries[automation] == (5 if trigger == "potion" else 9)
    assert p.rules.selection is None and not p.rules.tasks


def test_stratagem_sort_is_stable_by_rarity_id_and_quest_last():
    run = combat(["spoils_map", "bash", "strike", "anger", "anger"])
    p = run.combat.player
    cards = {c.instance_id: c for c in p.deck.draw_pile}
    ordered = [cards[i] for i in sorted(cards)]
    p.deck.draw_pile = list(reversed(ordered))
    ordered[3].upgrade()  # Upgrade is not a selector sort key.
    result = stratagem_cards(p)
    assert [c.definition.definition_id for c in result] == ["bash", "strike", "anger", "anger", "spoils_map"]
    assert result[2:4] == ordered[3:5]
    apply_power(p, "stratagem", 1)
    choose_after_shuffle(p)
    clone(run)
    record = saved(run)
    record["combat"]["player"]["rules"]["selection"]["candidates"].reverse()
    with pytest.raises(ValueError):
        RunEngine().restore(record)


def test_stratagem_automatic_all_preserves_top_first_order():
    run = combat(["strike", "bash", "anger"])
    p = run.combat.player
    top_first = list(reversed(p.deck.draw_pile))
    apply_power(p, "stratagem", 9)
    choose_after_shuffle(p)
    assert p.hand == top_first and p.rules.selection is None


@pytest.mark.parametrize("innate_count,expected", [(1, 7), (6, 7), (8, 8), (12, 10)])
def test_innate_draw_count_applies_after_bag_and_uses_repeated_move_to_top(innate_count, expected):
    run = RunEngine(
        seed=2,
        rng_profile="native",
        config=RunConfig(),
        card_ids=["aggression"] * innate_count + ["strike"] * 10,
    )
    for card in run.state.deck[:innate_count]:
        card.upgrade()
    add_relic(run.state, "bag_of_preparation", cards=run.cards)
    add_relic(run.state, "the_abacus", cards=run.cards)
    run.start_combat(encounter_id="overgrowth_cubex")
    p = run.combat.player
    assert len(p.hand) == expected
    # Independently compose native opening recipe from original master-deck order.
    original = [c.instance_id for c in run.state.deck]
    rng = NativeRng(p.deck.rng.seed)
    rng.shuffle(original)
    innate_ids = {c.instance_id for c in run.state.deck[:innate_count]}
    native = list(reversed([i for i in original if i in innate_ids])) + [
        i for i in original if i not in innate_ids
    ]
    assert [c.instance_id for c in p.hand] == native[:expected]
    assert p.block == 0
    clone(run)


@pytest.mark.parametrize("destination", ["hand", "draw_pile", "discard_pile"])
def test_stomp_entry_counts_finished_attacks_once_preserving_free_flags_and_clones(destination):
    run = combat(["strike"] * 3, draw=3)
    p = run.combat.player
    p.energy = 10
    for card in list(p.hand)[:2]:
        run.apply(PlayCard(card.instance_id, 0))
    stomp = create(p, DEFAULT_CARDS.definition("stomp"), destination="offered")
    assert stomp.combat_state.cost_change == 0
    resolve(p, stomp.instance_id, "move", destination, "free_until_played")
    assert stomp.combat_state.cost_change == -2
    assert stomp.combat_state.free_until_played
    copied = clone_to(p, stomp, "discard_pile")
    assert copied.combat_state.cost_change == -2
    resolve(p, stomp.instance_id, "move", "discard_pile", "")
    assert stomp.combat_state.cost_change == -2
    clone(run)


def test_offered_stomp_does_not_listen_to_attacks_but_direct_entry_does():
    run = combat(["strike"] * 3, draw=3)
    p = run.combat.player
    offered = create(p, DEFAULT_CARDS.definition("stomp"), destination="offered")
    entered = create(p, DEFAULT_CARDS.definition("stomp"))
    run.apply(PlayCard(p.hand[0].instance_id, 0))
    assert offered.combat_state.cost_change == 0
    assert entered.combat_state.cost_change == -1
    late = create(p, DEFAULT_CARDS.definition("stomp"), destination="discard_pile")
    assert late.combat_state.cost_change == -1


def test_full_hand_blocks_refill_hooks_and_rng_but_explicit_empty_shuffle_fires_hooks():
    from game.headless.core.resolution import push, drain
    from game.headless.core.piles import shuffle

    run = combat(["strike"] * 12, relics=("the_abacus",), draw=10)
    p = run.combat.player
    p.deck.discard_pile = p.deck.draw_pile
    p.deck.draw_pile = []
    before = saved(run)
    push(p, ["draw", 2, False])
    drain(p)
    assert saved(run) == before
    p.deck.exhaust_pile += p.hand + p.deck.discard_pile
    p.hand.clear()
    p.deck.discard_pile.clear()
    rng = p.deck.rng.getstate()
    shuffle(p, include_hand=True)
    drain(p)
    assert p.block == 6 and p.deck.rng.getstate() == rng


def test_queued_shuffle_choice_restores_and_rejects_foreign_power_and_arguments():
    from game.headless.core.choices import begin
    from game.headless.core.resolution import push

    run = combat(["strike", "bash", "defend"])
    p = run.combat.player
    apply_power(p, "stratagem", 1)
    begin(p, "stratagem", stratagem_cards(p))
    push(p, ["shuffle_choice"])
    clone(run)
    snapshot = saved(run)
    for change in ("argument", "power"):
        altered = deepcopy(snapshot)
        rules = altered["combat"]["player"]["rules"]
        if change == "argument":
            rules["tasks"][0].append(1)
        else:
            rules["powers"].pop("stratagem")
            rules["selection"] = None
        with pytest.raises(ValueError):
            RunEngine().restore(altered)


def test_generated_stomp_offer_and_selection_restore_through_actual_attack_potion():
    run = RunEngine(seed=13, rng_profile="native", config=RunConfig(), card_ids=["strike"] * 3)
    item = add_potion(run.state, "attack_potion")
    run.start_combat(encounter_id="overgrowth_cubex")
    p = run.combat.player
    run.apply(PlayCard(p.hand[0].instance_id, 0))
    # Seed 13's owned generation stream offers Stomp first.
    run.apply(UsePotion(item.instance_id))
    stomp = p.deck.offered[0]
    assert stomp.definition.definition_id == "stomp"
    assert stomp.combat_state.cost_change == 0
    other = clone(run)
    for action in (ChooseCombatCard(stomp.instance_id), ConfirmCombatSelection()):
        run.apply(action)
        other.apply(action)
        assert saved(run) == saved(other)
    assert stomp in p.hand and stomp.combat_state.cost_change == -1
    assert p.card_cost(stomp) == 0 and stomp.combat_state.turn_cost_until_played


@pytest.mark.parametrize("corruption", ["negative", "boolean_count", "non_boolean_flag", "arity", "old_combat", "old_run"])
def test_post_shuffle_draw_restore_rejects_malformed_or_ambiguous_old_state_atomically(corruption):
    run = combat(["finesse", "strike", "defend", "bash"], relics=("the_abacus",))
    p = run.combat.player
    finesse = next(c for c in p.deck.draw_pile if c.definition.definition_id == "finesse")
    p.deck.draw_pile.remove(finesse)
    p.hand.append(finesse)
    p.deck.discard_pile, p.deck.draw_pile = p.deck.draw_pile, []
    apply_power(p, "stratagem", 1)
    run.apply(PlayCard(finesse.instance_id))
    original = saved(run)
    restored = clone(run)
    assert saved(restored) == original
    altered = deepcopy(original)
    task = next(t for t in altered["combat"]["player"]["rules"]["tasks"] if t[0] == "draw_after_shuffle")
    if corruption == "negative":
        task[1] = -1
    elif corruption == "boolean_count":
        task[1] = True
    elif corruption == "non_boolean_flag":
        task[2] = 1
    elif corruption == "arity":
        task.append(False)
    elif corruption == "old_combat":
        altered["combat"]["schema"] = "headless_combat_state_v30"
    else:
        altered["schema"] = "headless_run_state_v46"
    with pytest.raises(ValueError):
        restored.restore(altered)
    assert saved(restored) == original
