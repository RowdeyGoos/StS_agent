"""Native event choices, lethal boundaries and exact owned continuation."""

from copy import deepcopy
import json

import pytest

from game.cli.headless_play import play_slice
from game.headless.events.jungle_maze import JungleMazeAdventure
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.actions import ChooseNode, ChooseEventOption, LeaveEvent
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase


def maze(*, hp=50, seed=2, enter=True):
    graph = MapGraph((MapNode("maze1", "event", ("maze2",), event_id="jungle_maze_adventure"),
                      MapNode("maze2", "event", ("fight",), event_id="jungle_maze_adventure"),
                      MapNode("fight", "combat", (), "overgrowth_nibbit")), "maze1")
    run = RunEngine(hp=hp, seed=seed, gold=0, graph=graph)
    if enter: run.apply(ChooseNode("maze1"))
    return run


def snap(run):
    return json.loads(json.dumps(run.snapshot()))


def step(run, action):
    clone = RunEngine(); clone.restore(snap(run))
    assert clone.legal_actions() == run.legal_actions()
    clone.apply(action)
    result = run.apply(action)
    assert snap(run) == snap(clone)
    return result


def choose(run, option):
    return ChooseEventOption(run.state.pending["event_instance_id"], option)


def leave(run):
    return LeaveEvent(run.state.pending["event_instance_id"])


def reject(run, action):
    before = snap(run)
    with pytest.raises(ValueError): run.apply(action)
    assert snap(run) == before


@pytest.mark.parametrize("hp", [1,17,18,19,80])
def test_join_forces_is_available_without_gold_or_hp_cost(hp):
    run = maze(hp=hp)
    assert {a.option_id for a in run.legal_actions()} == {"solo_quest", "join_forces"}
    reward = run.state.pending["data"]["join_gold"]
    assert 35 <= reward <= 64
    reject(run, leave(run))  # Native has two choices, not a free initial departure.
    step(run, choose(run, "join_forces"))
    assert run.state.hp == hp and run.state.gold == reward
    assert run.state.pending["stage"] == "resolved"
    assert run.legal_actions() == (leave(run),)
    step(run, leave(run))
    assert run.state.phase is RunPhase.ROUTE


@pytest.mark.parametrize("hp,remaining", [(1,0),(17,0),(18,0),(19,1),(80,62)])
def test_solo_damage_then_gold_and_exact_lethal_boundary(hp,remaining):
    run = maze(hp=hp)
    reward = run.state.pending["data"]["solo_gold"]
    assert 135 <= reward <= 164
    action = choose(run,"solo_quest")
    step(run, action)
    assert run.state.hp == remaining
    # Native sequence grants gold after awaiting damage, even on lethal choices.
    assert run.state.gold == reward
    assert run.state.pending["data"]["choice"] == "solo_quest"
    reject(run, action)
    if remaining == 0:
        assert run.state.phase is RunPhase.DEFEAT
        assert run.legal_actions() == ()
        reject(run, leave(run))
        reject(run, ChooseNode("maze2"))
    else:
        step(run, leave(run))
        assert run.state.phase is RunPhase.ROUTE


def test_once_only_rewards_stale_event_ids_and_next_combat_persistence():
    run = maze()
    first_choice = choose(run,"solo_quest"); first_leave = leave(run)
    reward = run.state.pending["data"]["solo_gold"]
    step(run,first_choice)
    reject(run,choose(run,"join_forces"))
    step(run,first_leave)
    step(run,ChooseNode("maze2"))
    reject(run,first_choice)
    reject(run,first_leave)
    reward += run.state.pending["data"]["join_gold"]
    step(run,choose(run,"join_forces")); step(run,leave(run))
    step(run,ChooseNode("fight"))
    assert run.state.gold == reward
    assert run.combat.player.hp == 32
    assert run.state.next_event_id == 2


def test_seeded_offers_read_only_restore_and_stream_isolation():
    a,b = maze(),maze(enter=False)
    b.state.rng.randint("shop.stock",0,10)
    b.state.rng.randint("treasure.gold",42,52)
    b.apply(ChooseNode("maze1"))
    assert a.state.pending == b.state.pending
    assert a.state.rng.request_count("event.jungle_maze") == 2
    before = snap(a)
    for _ in range(5): a.legal_actions(); snap(a)
    assert snap(a) == before
    step(a,choose(a,"join_forces"))
    assert a.state.rng.request_count("event.jungle_maze") == 2


def test_all_sampled_amounts_fit_native_truncated_bands():
    solos,joins = set(),set()
    for seed in range(200):
        data = maze(seed=seed).state.pending["data"]
        solos.add(data["solo_gold"]); joins.add(data["join_gold"])
    assert solos == set(range(135,165))
    assert joins == set(range(35,65))


@pytest.mark.parametrize("mutation", ["unknown", "missing", "wrong_kind", "conflicting_encounter"])
def test_map_event_identity_is_explicit(mutation):
    run = maze(enter=False)
    if mutation in ("unknown","missing"):
        identifier = "not_implemented" if mutation == "unknown" else None
        run.graph = MapGraph((MapNode("maze1","event",(),event_id=identifier),),"maze1")
        before = snap(run)
        with pytest.raises(ValueError): run.apply(ChooseNode("maze1"))
        assert snap(run) == before
    else:
        node = MapNode("bad", "rest" if mutation == "wrong_kind" else "event", (),
                       encounter_id="overgrowth_nibbit" if mutation == "conflicting_encounter" else None,
                       event_id="jungle_maze_adventure")
        with pytest.raises(ValueError): MapGraph((node,),"bad")


def test_entry_generation_failure_is_atomic(monkeypatch):
    run = maze(enter=False); before = snap(run)
    def fail(self,rng):
        rng.randint("event.jungle_maze",0,100)
        raise ValueError("Failed content generation")
    monkeypatch.setattr(JungleMazeAdventure,"generate",fail)
    with pytest.raises(ValueError): run.apply(ChooseNode("maze1"))
    assert snap(run) == before


@pytest.mark.parametrize("field,value", [("stage","missing"),("stage","resolved"),("definition_id","unknown"),
    ("event_instance_id",True),("event_instance_id",-1),("event_instance_id",3),("data",{}),("extra",0)])
def test_malformed_pending_restore_is_atomic(field,value):
    run = maze(); before = snap(run); broken = deepcopy(before)
    broken["state"]["pending"][field] = value
    with pytest.raises(ValueError): run.restore(broken)
    assert snap(run) == before


@pytest.mark.parametrize("field,value", [("solo_gold",134),("solo_gold",165),("solo_gold",True),
    ("join_gold",34),("join_gold",65),("join_gold",None),("choice","join_forces"),("extra",0)])
def test_malformed_event_variables_restore_is_atomic(field,value):
    run = maze(); before = snap(run); broken = deepcopy(before)
    broken["state"]["pending"]["data"][field] = value
    with pytest.raises(ValueError): run.restore(broken)
    assert snap(run) == before


@pytest.mark.parametrize("mutation", ["missing_counter","negative_counter","boolean_counter","wrong_room", "unknown_map_event", "catalog", "schema", "dead_join", "dead_unresolved"])
def test_invalid_event_context_restore_is_atomic(mutation):
    run = maze(); before = snap(run); broken = deepcopy(before)
    state = broken["state"]
    if mutation == "missing_counter": del state["next_event_id"]
    elif mutation == "negative_counter": state["next_event_id"] = -1
    elif mutation == "boolean_counter": state["next_event_id"] = True
    elif mutation == "wrong_room": broken["graph"]["nodes"][0]["kind"] = "rest"
    elif mutation == "unknown_map_event": broken["graph"]["nodes"][1]["event_id"] = "unknown"
    elif mutation == "catalog": broken["events"][0]["solo_damage"] = 17
    elif mutation == "schema": broken["schema"] = "headless_run_state_v6"
    elif mutation.startswith("dead"):
        state["hp"] = 0; state["phase"] = "defeat"
        if mutation == "dead_join":
            state["pending"]["stage"] = "resolved";state["pending"]["data"]["choice"] = "join_forces"
    with pytest.raises(ValueError): run.restore(broken)
    assert snap(run) == before


@pytest.mark.parametrize("path", ["left","right"])
def test_event_route_restores_through_every_decision(path):
    run,trace = play_slice(seed=2,route="overgrowth-act1",path=path,rest_choice="rest",verify_restore=True)
    assert "jungle_maze" in run.state.visited_nodes
    choices = [t for t in trace if t["action"] == "ChooseEventOption"]
    assert len(choices) == 1 and choices[0]["option_id"] == "join_forces"
    assert run.state.phase in (RunPhase.ACT_COMPLETE,RunPhase.DEFEAT)
