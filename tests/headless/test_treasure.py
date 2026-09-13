"""Chest rewards, skip/depletion, fallback ownership and exact continuation."""

from copy import deepcopy
import json

import pytest

from game.cli.headless_play import play_slice
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.actions import ChooseNode, OpenChest, ClaimTreasureRelic, LeaveTreasure
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic, remove_relic
from game.headless.run.state import RunPhase
from game.headless.run import treasure
from game.headless.treasure.catalog import ORDINARY_CHEST


def chest_run(seed=2, *, enter=True):
    graph = MapGraph(tuple(MapNode(f"chest{i}", "treasure", (f"chest{i+1}",)) for i in range(4)) +
                     (MapNode("chest4", "treasure", ("fight",)),
                      MapNode("fight", "combat", (), "overgrowth_nibbit")), "chest0")
    run = RunEngine(seed=seed, gold=99, hp=50, graph=graph)
    if enter:
        run.apply(ChooseNode("chest0"))
    return run


def snap(run):
    return json.loads(json.dumps(run.snapshot()))


def step(run, action):
    clone = RunEngine()
    clone.restore(snap(run))
    assert clone.legal_actions() == run.legal_actions()
    clone.apply(action)
    result = run.apply(action)
    assert snap(run) == snap(clone)
    return result


def claim(run):
    return ClaimTreasureRelic(run.state.pending["treasure_id"])


def reject(run, action):
    before = snap(run)
    with pytest.raises(ValueError): run.apply(action)
    assert snap(run) == before


def test_relic_draw_on_entry_and_gold_only_on_open_once():
    run = chest_run()
    assert run.state.gold == 99 and run.state.hp == 50
    assert run.state.rng.request_count("treasure.relic") == 1
    assert run.state.rng.request_count("treasure.gold") == 0
    assert run.state.pending["relic_id"] == run.state.treasure_relics_drawn[-1]
    reject(run, claim(run))
    gold = step(run, OpenChest())
    assert 42 <= gold <= 52
    assert run.state.gold == 99 + gold
    assert run.state.rng.request_count("treasure.gold") == 1
    reject(run, OpenChest())
    step(run, LeaveTreasure())
    assert run.state.phase is RunPhase.ROUTE and run.state.gold == 99 + gold
    assert not run.state.relics  # Skipping the relic does not undo opening gold.


def test_skip_unopened_consumes_offer_but_no_gold_or_item():
    run = chest_run()
    skipped = run.state.pending["relic_id"]
    rng = run.state.rng.snapshot()
    step(run, LeaveTreasure())
    assert run.state.rng.snapshot() == rng
    assert run.state.gold == 99 and not run.state.relics
    step(run, ChooseNode("chest1"))
    assert run.state.pending["relic_id"] != skipped
    assert skipped in run.state.treasure_relics_drawn


@pytest.mark.parametrize("relic_id,amount", [("strawberry",7), ("pear",10), ("mango",14)])
def test_pickup_heals_and_increases_max_hp_exactly_once(relic_id,amount):
    run = chest_run(enter=False)
    for name in ORDINARY_CHEST.relic_pool:
        if name != relic_id: add_relic(run.state, name)
    step(run, ChooseNode("chest0"))
    assert run.state.pending["relic_id"] == relic_id
    before_hp, before_max = run.state.hp, run.state.max_hp
    step(run, OpenChest())
    action = claim(run)
    result = step(run, action)
    assert run.state.hp == before_hp + amount and run.state.max_hp == before_max + amount
    assert result.definition_id == relic_id
    assert run.state.pending["claimed_instance_id"] == result.instance_id
    reject(run, action)
    reject(run, OpenChest())
    step(run, LeaveTreasure())
    assert run.state.hp == before_hp + amount


def test_exhausted_pool_falls_back_to_repeatable_circlet_instances():
    run = chest_run(enter=False)
    for name in ORDINARY_CHEST.relic_pool: add_relic(run.state, name)
    hp, maximum = run.state.hp, run.state.max_hp
    previous_claim = None
    ids = []
    for index in range(2):
        step(run, ChooseNode(f"chest{index}"))
        assert run.state.pending["relic_id"] == "circlet"
        assert run.state.rng.request_count("treasure.relic") == 0
        step(run, OpenChest())
        if previous_claim is not None: reject(run, previous_claim)
        previous_claim = claim(run)
        ids.append(step(run, previous_claim).instance_id)
        step(run, LeaveTreasure())
    assert len(set(ids)) == 2
    assert len([r for r in run.state.relics if r.definition_id == "circlet"]) == 2
    assert (run.state.hp,run.state.max_hp) == (hp,maximum)
    first = remove_relic(run.state, ids[0])
    assert first.instance_id == ids[0]
    assert any(r.instance_id == ids[1] for r in run.state.relics)
    restored = RunEngine(); restored.restore(snap(run))
    assert snap(restored) == snap(run)


def test_three_declined_offers_deplete_pool_then_fallback():
    run = chest_run()
    offered = []
    for index in range(3):
        if index: step(run, ChooseNode(f"chest{index}"))
        offered.append(run.state.pending["relic_id"])
        step(run, OpenChest())
        step(run, LeaveTreasure())
    assert set(offered) == set(ORDINARY_CHEST.relic_pool)
    step(run, ChooseNode("chest3"))
    assert run.state.pending["relic_id"] == "circlet"
    assert not run.state.relics
    step(run, OpenChest()); step(run, claim(run))
    assert [r.definition_id for r in run.state.relics] == ["circlet"]


def test_rng_isolation_read_only_inspection_and_gold_endpoints():
    outcomes = set()
    for seed in range(40):
        a, b = chest_run(seed), chest_run(seed)
        before = snap(a)
        for _ in range(3): a.legal_actions(); snap(a)
        assert snap(a) == before
        b.state.rng.randint("shop.prices", 1, 9)
        b.state.rng.randint("reward_gold", 1, 9)
        outcomes.add(step(a, OpenChest()))
        b.apply(OpenChest())
        assert a.state.pending == b.state.pending
    assert min(outcomes) == 42 and max(outcomes) == 52


def test_treasure_pickup_reaches_next_combat_and_remains_owned():
    run = chest_run()
    step(run, OpenChest()); relic = step(run, claim(run)); step(run, LeaveTreasure())
    maximum = run.state.max_hp
    for i in range(1,5):
        step(run, ChooseNode(f"chest{i}")); step(run, LeaveTreasure())
    step(run, ChooseNode("fight"))
    assert run.combat.player.max_hp == maximum
    assert relic in run.state.relics
    assert run.state.hp == 50 + maximum - 80


def test_failed_entry_rolls_back_rng_cursor_and_pool(monkeypatch):
    run = chest_run(enter=False)
    before = snap(run)
    monkeypatch.setattr(treasure, "RELICS", {})
    with pytest.raises(ValueError): run.apply(ChooseNode("chest0"))
    assert snap(run) == before


@pytest.mark.parametrize("field,value", [("stage","bogus"), ("definition_id","unknown"),
    ("treasure_id",True), ("treasure_id",9), ("relic_id","burning_blood"),
    ("relic_id","circlet"), ("gold",42), ("claimed_instance_id","run.item.0"), ("extra",0)])
def test_malformed_closed_chest_restore_is_atomic(field,value):
    run = chest_run(); before = snap(run); broken = deepcopy(before)
    broken["state"]["pending"][field] = value
    with pytest.raises(ValueError): run.restore(broken)
    assert snap(run) == before


@pytest.mark.parametrize("mutation", ["wrong_room", "counter", "counter_bool", "missing_pool", "duplicate_pool",
    "unknown_pool", "pool_over_counter", "gold_bool", "gold_low", "gold_high", "missing_gold", "fake_claim", "schema", "catalog"])
def test_malformed_open_chest_restore_is_atomic(mutation):
    run = chest_run(); run.apply(OpenChest()); before = snap(run); broken = deepcopy(before)
    state = broken["state"]; pending = state["pending"]
    if mutation == "wrong_room": broken["graph"]["nodes"][0]["kind"] = "rest"
    elif mutation == "counter": state["next_treasure_id"] = -1
    elif mutation == "counter_bool": state["next_treasure_id"] = True
    elif mutation == "missing_pool": state["treasure_relics_drawn"] = []
    elif mutation == "duplicate_pool": state["treasure_relics_drawn"] *= 2
    elif mutation == "unknown_pool": state["treasure_relics_drawn"] = ["circlet"]
    elif mutation == "pool_over_counter": state["treasure_relics_drawn"] = list(ORDINARY_CHEST.relic_pool)
    elif mutation == "gold_bool": pending["gold"] = True
    elif mutation == "gold_low": pending["gold"] = 41
    elif mutation == "gold_high": pending["gold"] = 53
    elif mutation == "missing_gold": pending["gold"] = None
    elif mutation == "fake_claim": pending["stage"] = "claimed"
    elif mutation == "schema": broken["schema"] = "headless_run_state_v5"
    elif mutation == "catalog": broken["treasure"]["gold_range"][0] += 1
    with pytest.raises(ValueError): run.restore(broken)
    assert snap(run) == before


def test_claim_snapshot_binds_exact_instance_and_nonstackable_duplicates_reject():
    run = chest_run(); run.apply(OpenChest()); run.apply(claim(run))
    before = snap(run); broken = deepcopy(before)
    broken["state"]["pending"]["claimed_instance_id"] = "run.item.99"
    with pytest.raises(ValueError): run.restore(broken)
    assert snap(run) == before
    with pytest.raises(ValueError): add_relic(run.state, run.state.pending["relic_id"])
    assert snap(run) == before
    broken = deepcopy(before)
    duplicate = deepcopy(broken["state"]["relics"][0]); duplicate["instance_id"] = "run.item.1"
    broken["state"]["relics"].append(duplicate); broken["state"]["next_item_id"] = 2
    with pytest.raises(ValueError): run.restore(broken)
    assert snap(run) == before


@pytest.mark.parametrize("path", ["left", "right"])
def test_authored_act1_route_visits_chest_and_restores_every_decision(path):
    run, trace = play_slice(seed=2, route="overgrowth-act1", path=path, rest_choice="rest", verify_restore=True)
    assert "treasure" in run.state.visited_nodes
    assert sum(t["action"] == "OpenChest" for t in trace) == 1
    assert sum(t["action"] == "ClaimTreasureRelic" for t in trace) == 1
    assert run.state.phase in (RunPhase.DEFEAT, RunPhase.ACT_COMPLETE)
    assert run.state.next_treasure_id == 1
