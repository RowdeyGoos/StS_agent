"""Actual pinned room/map generator vectors and initialization ownership cases."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from game.headless.core.native_service import NativeRandomService
from game.headless.generation.initialization import generate, extend_queue
from game.headless.generation.relics import populate
from game.headless.run.engine import RunEngine
from game.headless.run.ancient import PROFILE as NEOW
from game.headless.events.progression import NATIVE_PROFILE

VECTORS = json.loads(
    (Path(__file__).parents[1] / "fixtures/headless_native_initialization_vectors.json").read_text()
)
KINDS = dict(
    Monster="combat",
    Elite="elite",
    Unknown="unknown",
    RestSite="rest",
    Treasure="treasure",
    Shop="shop",
    Boss="boss",
)


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


@pytest.mark.parametrize("row", VECTORS["rows"], ids=lambda r: r["seed"])
def test_native_initialization_and_complete_map_match_actual_assembly(row):
    rng = NativeRandomService(row["seed"])
    populate(rng)
    assert rng.request_count("up_front") == row["afterBags"]
    initial = generate(rng)
    assert initial["subsets"] == row["subsets"]
    assert initial["acts"] == row["acts"]
    assert rng.request_count("up_front") == row["upFrontCounter"]
    assert rng.double("up_front") == row["upFrontSuffix"]
    run = RunEngine.ironclad_act1(seed=row["seed"], ancient_profile=NEOW)
    graph = run.graph
    actual = [
        dict(
            coord=[n.row, n.column],
            kind=n.kind,
            children=sorted([[graph.node(i).row, graph.node(i).column] for i in n.next_node_ids]),
        )
        for n in graph.nodes
    ]
    expected = [dict(n, kind=KINDS[n["kind"]]) for n in row["map"]["nodes"]]
    assert actual == expected
    assert [[graph.node(i).row, graph.node(i).column] for i in graph.entry_node_ids] == row["map"]["starts"]
    assert run.state.rng.request_count("act1.map") == row["map"]["counter"]
    assert deepcopy(run.state.rng).double("act1.map") == row["map"]["suffix"]
    assert run.state.rng.request_count("up_front") == row["upFrontCounter"]
    assert run.state.rng.request_count("act1.encounters") == run.state.rng.request_count("act1.events") == 0
    assert run.state.event_progression.profile == NATIVE_PROFILE
    assert len(run.state.event_progression.queue) == 31
    before = saved(run)
    for _ in range(3):
        run.legal_actions()
    assert saved(run) == before
    clone = RunEngine()
    clone.restore(before)
    assert clone.legal_actions() == run.legal_actions() and saved(clone) == before


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda s: s["state"].__setitem__("initialization", None),
        lambda s: s["state"]["initialization"].__setitem__("profile", "unknown"),
        lambda s: s["state"]["initialization"]["acts"][1]["normal"].reverse(),
        lambda s: s["state"]["initialization"]["acts"][0]["events"].reverse(),
        lambda s: s["state"]["encounter_progression"]["normal_queue"].reverse(),
        lambda s: s["state"]["event_progression"]["queue"].reverse(),
        lambda s: s["state"]["rng"]["streams"].pop("up_front"),
        lambda s: s.__setitem__("schema", "headless_run_state_v23"),
    ],
)
def test_corrupt_or_missing_initialization_rejects_atomically(corrupt):
    run = RunEngine.ironclad_act1(seed=2)
    before = saved(run)
    bad = deepcopy(before)
    corrupt(bad)
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before


def test_encounter_predicate_rejections_consume_draws_and_empty_predicate_falls_back():
    class Rolls:
        def __init__(self, rolls):
            self.rolls = iter(rolls)
            self.calls = 0

        def double(self, name):
            assert name == "up_front"
            self.calls += 1
            return next(self.rolls)

    # Native GrabBag retries A twice instead of reducing the candidate list to B.
    rng = Rolls([0.1, 0.2, 0.9])
    queue = ["A"]
    extend_queue(rng, queue, ("A", "B"), 1)
    assert queue == ["A", "B"] and rng.calls == 3
    rng = Rolls([0.5])
    queue = ["A"]
    extend_queue(rng, queue, ("A",), 1)
    assert queue == ["A", "A"] and rng.calls == 1


def test_later_act_events_stay_in_queue_but_are_skipped_before_room_construction():
    from game.headless.events.eligibility import entry_conditions

    run = RunEngine.ironclad_act1(seed=2)
    queue = run.state.event_progression
    blocked = next(n for n in queue.queue if n in ("fake_merchant", "crystal_sphere"))
    queue.cursor = queue.queue.index(blocked)
    result = queue.pull("synthetic-event", conditions=entry_conditions(run.state))
    assert result in run.state.config.event_pool
    assert queue.cursor > queue.queue.index(blocked) + 1


def test_fixture_profile_keeps_its_independent_streams_and_no_native_record():
    run = RunEngine.ironclad_act1(seed=2, rng_profile="fixture")
    assert run.state.initialization is None
    assert run.state.rng.request_count("act1.events") == 1
    assert len(run.state.event_progression.queue) == 21
    clone = RunEngine()
    clone.restore(saved(run))
    assert saved(clone) == saved(run)


def test_full_pass_fallback_can_now_resolve_later_act_content():
    from game.headless.events.progression import EventProgression
    queue=EventProgression(['fake_merchant'],profile=NATIVE_PROFILE)
    assert queue.pull('synthetic-event',conditions={'gold':0,'transformable_cards':0}) == 'fake_merchant'
    assert queue.cursor == 2 and queue.assignments == {'synthetic-event':'fake_merchant'}
