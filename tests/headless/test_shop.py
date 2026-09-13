"""Merchant transactions, exact deck removal and owned JSON continuation."""

import json
from copy import deepcopy

import pytest

from game.cli.headless_play import play_slice
from game.headless.cards.catalog import CardCatalog, DEFAULT_CARDS
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.actions import (
    ChooseNode, BuyShopItem, BeginShopRemoval, ChooseShopRemoval, LeaveShop, DiscardPotion,
)
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion, add_relic
from game.headless.run.shop import begin, removal_price
from game.headless.run.state import RunPhase
from game.headless.shops.catalog import price


def merchant(*, gold=1000, seed=2, card_ids=None):
    graph = MapGraph((MapNode("shop1", "shop", ("shop2",)),
                      MapNode("shop2", "shop", ("fight",)),
                      MapNode("fight", "combat", (), "overgrowth_nibbit")), "shop1")
    run = RunEngine(seed=seed, gold=gold, card_ids=card_ids, graph=graph)
    run.apply(ChooseNode("shop1"))
    return run


def snapshot(run):
    return json.loads(json.dumps(run.snapshot()))


def apply_restored(run, action):
    clone = RunEngine()
    clone.restore(snapshot(run))
    assert clone.legal_actions() == run.legal_actions()
    clone.apply(action)
    result = run.apply(action)
    assert snapshot(clone) == snapshot(run)
    return result


def offer(run, kind):
    return next(o for o in run.state.pending["offers"] if o["kind"] == kind)


def reject_unchanged(run, action):
    before = snapshot(run)
    with pytest.raises(ValueError):
        run.apply(action)
    assert snapshot(run) == before


def test_stock_prices_are_seeded_and_reads_do_not_consume_rng():
    a, b = merchant(), merchant()
    assert snapshot(a) == snapshot(b)
    assert len(a.state.pending["offers"]) == 6
    assert sum(o["on_sale"] for o in a.state.pending["offers"]) == 1
    rng = a.state.rng.snapshot()
    for _ in range(5):
        a.legal_actions()
        snapshot(a)
    assert a.state.rng.snapshot() == rng
    assert set(a.state.rng.stream_names) == {"shop.stock", "shop.prices"}
    b.state.rng.randint("reward.cards", 0, 100)
    apply_restored(a, LeaveShop())
    b.apply(LeaveShop())
    apply_restored(a, ChooseNode("shop2"))
    b.apply(ChooseNode("shop2"))
    assert a.state.pending == b.state.pending


@pytest.mark.parametrize("base,scale,sale,expected", [(50,9500,False,48), (50,10500,False,52),
    (75,10000,True,37), (75,10500,True,39), (175,8500,False,149), (275,11500,False,316)])
def test_source_price_rounding_then_integer_sale(base, scale, sale, expected):
    assert price(base, scale, sale) == expected


@pytest.mark.parametrize("kind", ["card", "relic", "potion"])
def test_purchase_affordability_boundary_acquisition_and_sold_out(kind):
    run = merchant()
    item = offer(run, kind)
    action = BuyShopItem(item["offer_id"])
    run.state.gold = item["price"] - 1
    reject_unchanged(run, action)
    run.state.gold += 1
    hp = run.state.hp
    result = apply_restored(run, action)
    assert run.state.gold == 0
    assert item["sold"]
    if kind == "card":
        assert result in run.state.deck and result.upgrade_level == 0
        assert result.definition.definition_id == item["definition_id"]
    elif kind == "relic":
        assert result in run.state.relics
        assert run.state.hp - hp == {"strawberry":7, "pear":10, "mango":14}[item["definition_id"]]
        assert run.state.hp == run.state.max_hp
    else:
        assert result in run.state.potions
    run.state.gold = 1000
    reject_unchanged(run, action)


def test_multiple_purchases_and_full_potion_slot_recovery():
    run = merchant()
    for _ in range(3):
        add_potion(run.state, "block_potion")
    potion = offer(run, "potion")
    reject_unchanged(run, BuyShopItem(potion["offer_id"]))
    discarded = run.state.potions[1]
    apply_restored(run, DiscardPotion(discarded.instance_id))
    bought = apply_restored(run, BuyShopItem(potion["offer_id"]))
    assert run.state.potions[1] == bought
    assert bought.instance_id != discarded.instance_id
    card = offer(run, "card")
    apply_restored(run, BuyShopItem(card["offer_id"]))
    assert sum(o["sold"] for o in run.state.pending["offers"]) == 2


def test_owned_relics_are_excluded_and_empty_pool_omits_slot():
    run = RunEngine(gold=1000)
    for name in ("strawberry", "pear", "mango"):
        add_relic(run.state, name)
    begin(run.state, run.cards)
    assert not any(o["kind"] == "relic" for o in run.state.pending["offers"])
    apply_restored(run, LeaveShop())


def test_duplicate_relic_purchase_rejects_before_spending_or_allocating():
    run = merchant()
    item = offer(run, "relic")
    add_relic(run.state, item["definition_id"])
    reject_unchanged(run, BuyShopItem(item["offer_id"]))


def test_removal_cancel_is_free_and_selection_locks_other_commands():
    run = merchant(gold=75)
    add_potion(run.state, "fire_potion")
    before = snapshot(run)
    apply_restored(run, BeginShopRemoval())
    assert run.state.gold == 75 and run.state.shop_removals_used == 0
    assert all(isinstance(a, ChooseShopRemoval) for a in run.legal_actions())
    reject_unchanged(run, LeaveShop())
    reject_unchanged(run, DiscardPotion(run.state.potions[0].instance_id))
    reject_unchanged(run, ChooseShopRemoval("unknown"))
    apply_restored(run, ChooseShopRemoval(None))
    assert snapshot(run) == before


def test_removal_exact_instance_once_per_shop_and_cost_escalation():
    run = merchant(gold=300, card_ids=("strike", "strike", "defend"))
    keep, remove, _ = run.state.deck
    remove.upgrade()
    apply_restored(run, BeginShopRemoval())
    apply_restored(run, ChooseShopRemoval(remove.instance_id))
    assert run.state.deck[0] is keep and remove not in run.state.deck
    assert run.state.gold == 225 and run.state.shop_removals_used == 1
    reject_unchanged(run, BeginShopRemoval())
    apply_restored(run, LeaveShop())
    apply_restored(run, ChooseNode("shop2"))
    assert removal_price(run.state) == 100
    apply_restored(run, BeginShopRemoval())
    apply_restored(run, ChooseShopRemoval(keep.instance_id))
    assert run.state.gold == 125 and run.state.shop_removals_used == 2
    assert removal_price(run.state) == 125


def test_removal_affordability_empty_deck_and_last_card():
    run = merchant(gold=74, card_ids=("strike",))
    reject_unchanged(run, BeginShopRemoval())
    run.state.gold = 75
    apply_restored(run, BeginShopRemoval())
    apply_restored(run, ChooseShopRemoval(run.state.deck[0].instance_id))
    assert not run.state.deck and run.state.gold == 0
    empty = merchant(gold=100, card_ids=())
    reject_unchanged(empty, BeginShopRemoval())
    apply_restored(empty, LeaveShop())


def test_purchased_card_removal_and_stale_offer_ids_across_shops():
    run = merchant()
    item = offer(run, "card")
    card = apply_restored(run, BuyShopItem(item["offer_id"]))
    apply_restored(run, BeginShopRemoval())
    assert ChooseShopRemoval(card.instance_id) in run.legal_actions()
    apply_restored(run, ChooseShopRemoval(card.instance_id))
    apply_restored(run, LeaveShop())
    apply_restored(run, ChooseNode("shop2"))
    reject_unchanged(run, BuyShopItem(item["offer_id"]))
    assert len({c.instance_id for c in run.state.deck}) == len(run.state.deck)


def test_shop_changes_reach_next_combat_without_reapplying_pickups():
    run = merchant()
    purchased = apply_restored(run, BuyShopItem(offer(run, "card")["offer_id"]))
    apply_restored(run, BuyShopItem(offer(run, "relic")["offer_id"]))
    removed = run.state.deck[0]
    apply_restored(run, BeginShopRemoval())
    apply_restored(run, ChooseShopRemoval(removed.instance_id))
    apply_restored(run, LeaveShop())
    apply_restored(run, ChooseNode("shop2"))
    apply_restored(run, LeaveShop())
    apply_restored(run, ChooseNode("fight"))
    player = run.combat.player
    combat_cards = [*player.hand, *player.deck.draw_pile, *player.deck.discard_pile]
    assert purchased.instance_id in {c.instance_id for c in combat_cards}
    assert removed.instance_id not in {c.instance_id for c in combat_cards}
    assert player.max_hp == run.state.max_hp


@pytest.mark.parametrize("field,value", [("shop_id",True), ("shop_id",99), ("catalog_id","future"),
    ("stage","callback"), ("removal_used",1), ("removal_used",True), ("removals_on_entry",-1),
    ("offers",[]), ("eligible",[])])
def test_malformed_shop_restore_is_atomic(field,value):
    run = merchant()
    original = snapshot(run)
    broken = deepcopy(original)
    broken["state"]["pending"][field] = value
    with pytest.raises(ValueError):
        run.restore(broken)
    assert snapshot(run) == original


@pytest.mark.parametrize("field,value", [("slot",True), ("slot",90), ("definition_id","unknown"),
    ("offer_id","shop.100.offer.0"), ("kind","event"), ("price",-1), ("price",True),
    ("price",999), ("sold",1), ("on_sale",1)])
def test_malformed_offer_restore_is_atomic(field,value):
    run = merchant()
    original = snapshot(run)
    broken = deepcopy(original)
    broken["state"]["pending"]["offers"][0][field] = value
    with pytest.raises(ValueError):
        run.restore(broken)
    assert snapshot(run) == original


@pytest.mark.parametrize("mutation", ["duplicate", "missing_slot", "missing_relic", "wrong_room", "selection", "counter", "schema", "catalog"])
def test_restore_rejects_inconsistent_continuations(mutation):
    run = merchant()
    if mutation == "selection":
        run.apply(BeginShopRemoval())
    original = snapshot(run)
    broken = deepcopy(original)
    state, pending = broken["state"], broken["state"]["pending"]
    if mutation == "duplicate": pending["offers"][1] = deepcopy(pending["offers"][0])
    elif mutation == "missing_slot": pending["offers"].pop(0)
    elif mutation == "missing_relic": pending["offers"].pop(3)
    elif mutation == "wrong_room": broken["graph"]["nodes"][0]["kind"] = "rest"
    elif mutation == "selection": pending["eligible"].pop()
    elif mutation == "counter": state["shop_removals_used"] = state["next_shop_id"] + 1
    elif mutation == "schema": broken["schema"] = "headless_run_state_v4"
    elif mutation == "catalog": broken["shops"]["slots"][0]["items"][0][1] += 1
    with pytest.raises(ValueError): run.restore(broken)
    assert snapshot(run) == original


def test_failed_shop_construction_rolls_back_map_rng_and_allocators():
    run = merchant()
    run.apply(LeaveShop())
    run.cards = CardCatalog((DEFAULT_CARDS.definition("strike"), DEFAULT_CARDS.definition("defend"), DEFAULT_CARDS.definition("bash")))
    before = snapshot(run)
    with pytest.raises(ValueError): run.apply(ChooseNode("shop2"))
    assert snapshot(run) == before


def test_optional_act1_shop_route_and_demo_restore():
    run, trace = play_slice(seed=2, route="overgrowth-act1", verify_restore=True)
    assert any(t["action"] == "BuyShopItem" for t in trace)
    assert any(t["action"] == "ChooseShopRemoval" for t in trace)
    assert "merchant" in run.state.visited_nodes
    # The example policy is not a claim that this deck reliably beats the boss.
    assert run.state.phase in (RunPhase.ACT_COMPLETE, RunPhase.DEFEAT)
    graph = run.graph
    assert "boss_camp" in graph.node("mawler").next_node_ids
    assert graph.node("merchant").next_node_ids == ("boss_camp",)
