"""Actual native factory sequences plus card/potion continuation regressions."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS, CardCatalog
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.native_rng import NativeRng
from game.headless.generation.combat import card_pool, select_cards
from game.headless.powers.ironclad import apply_power
from game.headless.run.actions import UsePotion
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion
from game.headless.potions.pools import ORDINARY_POTIONS

VECTORS = json.loads(
    (Path(__file__).parents[1] / "fixtures/headless_native_combat_generation_vectors.json").read_text()
)


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other = RunEngine(cards=run.cards, card_ids=[])
    other.restore(saved(run))
    assert saved(other) == saved(run)
    return other


def ids(cards):
    return [c.definition.definition_id for c in cards]


def options(mode, family, kind):
    result = card_pool(DEFAULT_CARDS, family, kind.lower() or None)
    if mode == "jack_of_all_trades":
        result = [d for d in result if d.definition_id != mode]
    if mode == "jackpot":
        result = [d for d in result if d.levels[0].cost == 0 and not d.levels[0].x_cost]
    return result


@pytest.mark.parametrize("row", VECTORS["poolRows"], ids=lambda r: r["name"])
def test_eligible_pools_match_actual_native_filter(row):
    assert [d.definition_id for d in card_pool(DEFAULT_CARDS, row["name"])] == row["eligible"]
    native = {d["id"]: d for d in row["cards"]}
    for d in card_pool(DEFAULT_CARDS, row["name"]):
        record = native[d.definition_id]
        assert record["kind"].lower() == ("skill" if d.levels[0].kind == "block" else d.levels[0].kind)
        assert record["canGenerate"] == d.generate_in_combat
        assert record["costsX"] == d.levels[0].x_cost
        assert record["cost"] == (0 if d.levels[0].x_cost else d.levels[0].cost)


@pytest.mark.parametrize("row", VECTORS["generationRows"], ids=lambda r: f"{r['seed']}-{r['mode']}")
def test_factory_sequences_match_cards_consumption_and_suffix(row):
    rng = NativeRng(row["seed"])
    for call in row["calls"]:
        eligible = options(row["mode"], call["family"], call["kind"])
        assert [d.definition_id for d in eligible] == call["eligible"]
        selected = select_cards(eligible, rng, call["count"], distinct=call["distinct"])
        assert [d.definition_id for d in selected] == call["selected"]
        assert call["upgrades"] == [0] * len(selected)
        assert rng.counter == call["counter"]
        restored = NativeRng()
        restored.setstate(json.loads(json.dumps(rng.getstate())))
        assert restored.next_double() == deepcopy(rng).next_double()
    assert rng.counter == row["counter"] and rng.next_double() == row["suffix"]


@pytest.mark.parametrize("row", VECTORS["boundaries"])
def test_empty_singleton_duplicate_and_oversized_factory_requests(row):
    rng = NativeRng(42)
    options = [DEFAULT_CARDS.definition(n) for n in row["inputs"]]
    generated = select_cards(options, rng, row["count"], distinct=row["distinct"])
    assert [d.definition_id for d in generated] == row["selected"]
    assert rng.counter == row["counter"] and rng.next_double() == row["suffix"]


RUN_ROWS = [row for row in VECTORS["generationRows"] if row["seed"] == VECTORS["combatSeed"]]


@pytest.mark.parametrize("row", RUN_ROWS, ids=lambda r: r["mode"])
@pytest.mark.parametrize("upgraded", [False, True])
def test_actual_card_and_potion_callers_match_factory_vectors_and_restore(row, upgraded):
    mode = row["mode"]
    potion = mode.endswith("_potion") or mode == "orobic_acid"
    names = [] if potion else (["strike"] if mode == "calamity" else [mode])
    if mode == "stoke":
        names += ["wound"] * 3
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(), card_ids=names)
    if upgraded and not potion:
        run.state.deck[0].upgrade()
    item = add_potion(run.state, mode) if potion else None
    run.start_combat(encounter_id="overgrowth_cubex", cards_per_turn=10)
    if mode == "calamity":
        apply_power(run.combat.player, "calamity", 3)
    if mode == "jack_of_all_trades" and not upgraded:
        # The retained native batch uses the upgraded count of two.
        run.combat.player.hand[0].upgrade()
    before = saved(run)
    run.legal_actions()
    with pytest.raises(ValueError):
        run.apply(ChooseCombatCard("unallocated"))
    assert saved(run) == before
    initial_ids = {c.instance_id for c in run.combat.player.deck.all_cards()}
    copy = clone(run)
    for current in [run, copy]:
        if potion:
            current.apply(UsePotion(item.instance_id))
        else:
            card = next(
                c
                for c in current.combat.player.hand
                if c.definition.definition_id == ("strike" if mode == "calamity" else mode)
            )
            current.apply(PlayCard(card.instance_id, 0 if card.spec.uses_target else None))
    assert saved(run) == saved(copy)
    p = run.combat.player
    generated = [c for c in p.deck.all_cards() if c.instance_id not in initial_ids]
    expected = [name for call in row["calls"] for name in call["selected"]]
    assert ids(generated) == expected
    expected_upgrade = int(upgraded and mode in ("stoke", "jackpot"))
    assert [c.upgrade_level for c in generated] == [expected_upgrade] * len(expected)
    assert p.deck.generation_rng.counter == row["counter"]
    assert deepcopy(p.deck.generation_rng).next_double() == row["suffix"]
    # Other random domains and noncombat rarity odds do not move.
    old_rng = before["state"]["rng"]["streams"]
    for name, stream in run.state.rng.snapshot()["streams"].items():
        if name != "combat_card_generation":
            assert stream == old_rng[name]
    assert saved(run)["state"]["generation_odds"] == before["state"]["generation_odds"]
    clone(run)
    if p.rules.selection:
        pending = saved(run)
        for choose in (False, True):
            run.restore(pending)
            if choose:
                run.apply(ChooseCombatCard(run.combat.player.deck.offered[0].instance_id))
            copy = clone(run)
            run.apply(ConfirmCombatSelection())
            copy.apply(ConfirmCombatSelection())
            assert saved(run) == saved(copy)
            assert not run.combat.player.deck.offered
            if choose:
                selected = run.combat.player.hand[-1]
                assert selected.definition.definition_id == expected[0]
                assert (
                    selected.combat_state.free_until_played
                    if mode == "discovery"
                    else selected.combat_state.free_this_turn
                )
            assert deepcopy(run.combat.player.deck.generation_rng).next_double() == row["suffix"]


def test_skill_pool_includes_shrug_it_off_without_basic_defend():
    pool = [d.definition_id for d in card_pool(DEFAULT_CARDS, kind="skill")]
    assert "shrug_it_off" in pool and "defend" not in pool


def test_native_infernal_blade_singleton_does_not_consume_a_draw():
    catalog = CardCatalog([DEFAULT_CARDS.definition(n) for n in ("infernal_blade", "anger")])
    run = RunEngine(seed=2, rng_profile="native", cards=catalog, card_ids=["infernal_blade"])
    run.start_combat()
    run.apply(PlayCard(run.combat.player.hand[0].instance_id))
    assert ids(run.combat.player.hand) == ["anger"]
    assert run.combat.player.deck.generation_rng.counter == 0
    clone(run)


def test_orobic_acid_full_hand_keeps_all_generated_instances_and_draws():
    row = next(r for r in RUN_ROWS if r["mode"] == "orobic_acid")
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(), card_ids=["wound"] * 10)
    item = add_potion(run.state, "orobic_acid")
    run.start_combat(encounter_id="overgrowth_cubex", cards_per_turn=10)
    copy = clone(run)
    for current in (run, copy):
        current.apply(UsePotion(item.instance_id))
    assert saved(run) == saved(copy)
    p = run.combat.player
    assert len(p.hand) == 10
    assert ids(p.deck.discard_pile) == [name for call in row["calls"] for name in call["selected"]]
    assert all(c.combat_state.free_this_turn for c in p.deck.discard_pile)
    assert len({c.instance_id for c in p.deck.all_cards()}) == 13
    assert p.deck.generation_rng.counter == row["counter"]
    clone(run)


def test_queued_distinct_generation_restores_and_rejects_malformed_flags():
    # Explicit continuation fixture: generation waiting behind an optional choice.
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(), card_ids=["discovery"])
    run.start_combat(encounter_id="overgrowth_cubex")
    run.apply(PlayCard(run.combat.player.hand[0].instance_id))
    run.combat.player.rules.tasks.insert(0, ["generate", 1, True, False, True, True])
    before = saved(run)
    for replacement in (["generate", 1, True, False, True], ["generate", 1, True, False, True, 1]):
        bad = deepcopy(before)
        bad["combat"]["player"]["rules"]["tasks"][0] = replacement
        with pytest.raises(ValueError):
            run.restore(bad)
        assert saved(run) == before
    copy = clone(run)
    expected = deepcopy(run.combat.player.deck.generation_rng)
    definitions = select_cards(card_pool(DEFAULT_CARDS, kind="attack"), expected, 1, distinct=True)
    for current in (run, copy):
        current.apply(ConfirmCombatSelection())
    assert saved(run) == saved(copy)
    assert ids(run.combat.player.hand) == [d.definition_id for d in definitions]
    assert run.combat.player.deck.generation_rng.getstate() == expected.getstate()


@pytest.mark.parametrize("row", VECTORS["potionRows"])
def test_actual_native_potion_factory_repeated_calls_preserve_eligibility_and_rng(row):
    from game.headless.potions.pools import generate, ORDINARY_POTIONS

    rng = NativeRng(row["seed"])
    selected = [generate(ORDINARY_POTIONS, rng, in_combat=row["inCombat"]) for _ in range(3)]
    assert selected == row["selected"]
    assert rng.counter == row["counter"] and rng.next_double() == row["suffix"]


@pytest.mark.parametrize("full", [False, True])
def test_alchemize_consumes_native_potion_factory_even_when_inventory_is_full(full):
    row = next(r for r in VECTORS["potionRows"] if r["seed"] == VECTORS["potionSeed"] and r["inCombat"])
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(reward_potions=ORDINARY_POTIONS), card_ids=["alchemize"] * 3)
    if full:
        for _ in range(3):
            add_potion(run.state, "fire_potion")
    run.start_combat(encounter_id="overgrowth_cubex")
    before_card_rng = run.combat.player.deck.generation_rng.getstate()
    for _ in range(3):
        copy = clone(run)
        action = PlayCard(run.combat.player.hand[0].instance_id)
        run.apply(action)
        copy.apply(action)
        assert saved(run) == saved(copy)
    assert [p.definition_id for p in run.state.potions] == (["fire_potion"] * 3 if full else row["selected"])
    rng = run.combat.player.deck.potion_rng
    assert rng.counter == row["counter"] and deepcopy(rng).next_double() == row["suffix"]
    assert run.combat.player.deck.generation_rng.getstate() == before_card_rng
    clone(run)


def test_entropic_brew_uses_repeated_out_of_combat_factory_and_restores():
    row = next(r for r in VECTORS["potionRows"] if r["seed"] == VECTORS["potionSeed"] and not r["inCombat"])
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(reward_potions=ORDINARY_POTIONS), card_ids=[])
    item = add_potion(run.state, "entropic_brew")
    run.start_combat(encounter_id="overgrowth_cubex")
    copy = clone(run)
    for current in (run, copy):
        current.apply(UsePotion(item.instance_id))
    assert saved(run) == saved(copy)
    assert [p.definition_id for p in run.state.potions] == row["selected"]
    rng = run.combat.player.deck.potion_rng
    assert rng.counter == row["counter"] and deepcopy(rng).next_double() == row["suffix"]
    clone(run)
