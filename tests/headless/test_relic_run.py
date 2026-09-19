"""Run relic effects, nested acquisition and exact JSON continuation."""

import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest
from game.headless.cards.catalog import CardCatalog, DEFAULT_CARDS, IRONCLAD_CARDS
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.inventory import add_relic
from game.headless.run.actions import (
    ChooseRelicReward,
    ChooseExtraReward,
    ChooseEventOption,
    LeaveEvent,
    Lift,
    Rest,
    Dig,
    LeaveRest,
    BuyShopItem,
)
from game.headless.relics.base import RELICS
from game.headless.relics.pools import ORDINARY_RELICS, SHOP_RELICS
from game.cli.headless_play import choose_demo_action


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def step(run, action):
    clone = RunEngine(cards=run.cards)
    clone.restore(saved(run))
    assert clone.legal_actions() == run.legal_actions()
    a = run.apply(action)
    clone.apply(action)
    assert saved(run) == saved(clone)
    return a


def settle(run):
    for _ in range(100):
        if not run.state.relic_work:
            return
        step(run, choose_demo_action(run))
    pytest.fail("Unfinished relic acquisition.")


def run_with(*relics, **kwargs):
    r = RunEngine(
        config=RunConfig(reward_relics=ORDINARY_RELICS, shop_relics=SHOP_RELICS, relic_fallback="circlet"),
        **kwargs,
    )
    for relic in relics:
        add_relic(r.state, relic, cards=r.cards)
        settle(r)
    return r


def test_catalog_matches_independently_audited_solo_scope():
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/headless_relic_scope.json").read_text())
    names = [
        n
        for k in (
            "shared",
            "ironclad",
            "neow",
            "overgrowth_event_and_evolution",
            "shared_act1_event",
            "fallback",
        )
        for n in fixture[k]
    ]
    converted = {re.sub(r"(?<!^)(?=[A-Z])", "_", n).lower() for n in names}
    assert len(converted) == fixture["definition_count"] == 161
    ancients = json.loads((Path(__file__).parents[1] / "fixtures/headless_ancient_scope.json").read_text())
    events = json.loads((Path(__file__).parents[1] / "fixtures/headless_solo_event_scope.json").read_text())
    assert set(RELICS) == converted | set(ancients["solo"]) | set(events["event_relics"]) | {"black_blood"}


@pytest.mark.parametrize("name", sorted(RELICS))
def test_each_available_relic_pickup_and_all_choices_roundtrip(name):
    r = run_with(name, seed=7, hp=50, gold=99)
    clone = RunEngine()
    clone.restore(saved(r))
    assert saved(clone) == saved(r)
    assert any(x.definition_id == name for x in r.state.relics)


def test_missing_foreign_pool_dependency_is_explicit_and_atomic():
    r = run_with(cards=IRONCLAD_CARDS)
    before = saved(r)
    with pytest.raises(ValueError, match="card pools"):
        r.obtain_relic("kaleidoscope")
    assert saved(r) == before


def test_kaleidoscope_uses_distinct_foreign_families_in_each_set():
    catalog = DEFAULT_CARDS
    r = RunEngine(cards=catalog)
    add_relic(r.state, "kaleidoscope", cards=catalog)
    assert len(r.state.relic_work) == 2
    assert all(
        len({catalog.definition(x["definition_id"]).pool for x in w["offers"]}) == 3
        for w in r.state.relic_work
    )
    settle(r)
    assert len([c for c in r.state.deck if c.definition.pool in ("silent", "regent", "necrobinder", "defect")]) == 2


def test_acquisition_blocks_room_entry_and_corrupt_automatic_work():
    r = RunEngine()
    r.obtain_relic("dollys_mirror")
    before = saved(r)
    with pytest.raises(ValueError):
        r.start_combat()
    assert saved(r) == before
    r = RunEngine()
    r.obtain_relic("hefty_tablet")
    bad = saved(r)
    bad["state"]["relic_work"][-1]["values"] = ["not_a_card"]
    with pytest.raises(ValueError):
        RunEngine().restore(bad)


def test_eggs_fresnel_and_card_acquisition_resources():
    from game.headless.run.deck import add_card

    r = run_with(
        "molten_egg", "toxic_egg", "fresnel_lens", "lucky_fysh", "dragon_fruit", "book_of_five_rings", hp=20
    )
    for _ in range(5):
        c = add_card(r.state, DEFAULT_CARDS.definition("defend"))
    assert c.upgrade_level == 1 and c.enchantment.definition_id == "nimble"
    assert (r.state.gold, r.state.max_hp, r.state.hp) == (75, 85, 45)
    assert next(x for x in r.state.relics if x.definition_id == "book_of_five_rings").counter == 0


def test_rest_combinations_lift_dig_tent_and_rewards():
    from game.headless.run.rest_site import begin_rest_site

    r = run_with(
        "miniature_tent", "girya", "shovel", "regal_pillow", "stone_humidifier", "tiny_mailbox", hp=10
    )
    begin_rest_site(r.state)
    step(r, Lift())
    step(r, Rest())
    settle(r)
    assert (r.state.max_hp, r.state.hp) == (85, 54)
    assert Rest() not in r.legal_actions() and Lift() not in r.legal_actions()
    step(r, Dig())
    settle(r)
    step(r, LeaveRest())


def test_membership_and_courier_capture_price_and_fresh_restock_identity():
    from game.headless.run.shop import begin

    r = run_with("membership_card", "the_courier", gold=1000)
    begin(r.state, r.cards)
    offer = next(o for o in r.state.pending["offers"] if o["kind"] == "card")
    identity, paid = offer["offer_id"], offer["price"]
    assert paid == int(offer["base_price"] * 0.4)
    step(r, BuyShopItem(identity))
    assert r.state.gold == 1000 - paid
    assert not any(o["offer_id"] == identity for o in r.state.pending["offers"])
    assert any(o["generation"] == 1 for o in r.state.pending["offers"])


def test_lava_rock_first_boss_adds_two_owned_distinct_relic_rewards_once():
    from game.headless.run.rewards import begin_combat_rewards
    from game.headless.encounters.catalog import ENCOUNTERS

    boss = next(k for k, v in ENCOUNTERS.items() if v.room_kind == "boss")
    r = run_with("lava_rock")
    begin_combat_rewards(r.state, r.cards, encounter_id=boss)
    extra = r.state.pending["extra_rewards"]
    assert len(extra) == 2 and len({w["offers"][0] for w in extra}) == 2
    for i in range(2):
        step(r, ChooseExtraReward(i, extra[i]["offers"][0]))
        settle(r)
    assert next(x for x in r.state.relics if x.definition_id == "lava_rock").counter == 1


def test_silver_crucible_does_not_consume_rewards_on_hefty_tablet():
    r = run_with("silver_crucible")
    r.obtain_relic("hefty_tablet")
    assert r.state.relics[0].counter == 0
    settle(r)
    from game.headless.run.rewards import begin_reward

    begin_reward(r.state, r.cards, gold=0, card_ids=("strike", "defend", "bash"))
    assert r.state.relics[0].counter == 1
    assert all(v["upgrade_level"] == 1 for v in r.state.pending["card_modifiers"].values())


def test_shears_empty_deck_still_loses_hp():
    r = RunEngine(card_ids=())
    r.obtain_relic("precarious_shears")
    assert r.state.hp == 64


@pytest.mark.parametrize("name", ("leafy_poultice", "precarious_shears"))
def test_lethal_pickup_has_a_valid_terminal_snapshot(name):
    r = RunEngine(max_hp=10, hp=10, card_ids=())
    r.obtain_relic(name)
    assert r.state.hp == 0 and not r.legal_actions()
    clone = RunEngine()
    clone.restore(saved(r))
    assert saved(clone) == saved(r)


@pytest.mark.parametrize(
    "event",
    (
        "dense_vegetation",
        "sunken_statue",
        "whispering_hollow",
        "morphic_grove",
        "byrdonis_nest",
        "wellspring",
        "slippery_bridge",
        "aroma_of_chaos",
        "jungle_maze_adventure",
        "sapphire_seed",
        "tablet_of_truth",
    ),
)
def test_scripted_event_options_accept_relic_resource_effects(event):
    from game.headless.run.events import begin

    r = run_with(
        "tungsten_rod",
        "lizard_tail",
        "bowler_hat",
        "dragon_fruit",
        "lucky_fysh",
        "book_of_five_rings",
        "toxic_egg",
        "molten_egg",
        "fresnel_lens",
        hp=20,
        gold=200,
    )
    book = next(x for x in r.state.relics if x.definition_id == "book_of_five_rings")
    r.state.relics[r.state.relics.index(book)] = replace(book, counter=4)
    begin(r.state, event, cards=r.cards)
    for option in r.legal_actions():
        if not isinstance(option, ChooseEventOption):
            continue
        trial = RunEngine()
        trial.restore(saved(r))
        step(trial, option)
        for _ in range(12):
            if not trial.legal_actions() or any(isinstance(a, LeaveEvent) for a in trial.legal_actions()):
                break
            step(trial, choose_demo_action(trial))
        clone = RunEngine()
        clone.restore(saved(trial))
        assert saved(clone) == saved(trial)


def test_opening_relic_victory_enters_rewards_without_a_player_action():
    from game.headless.monsters.overgrowth import SimpleEnemy
    from game.headless.run.state import RunPhase

    r = run_with("festive_popper", "mercury_hourglass")
    combat = r.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=10))
    assert combat.done and combat.winner == "player"
    assert r.combat is None and r.state.phase is RunPhase.REWARD
    clone = RunEngine()
    clone.restore(saved(r))
    assert clone.legal_actions() == r.legal_actions()
