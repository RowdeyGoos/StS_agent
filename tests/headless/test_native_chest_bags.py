"""Shared chest offers and player offers have different depletion ownership."""
from copy import deepcopy

import pytest

from game.headless.generation import relics
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.actions import ChooseNode, OpenChest, ClaimTreasureRelic, LeaveTreasure
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from tests.headless.test_act2_run import clone, saved, step


@pytest.mark.parametrize('claim', [False, True])
def test_chest_offer_preserves_player_copy_until_pickup_and_json_resume(claim):
    graph = MapGraph((MapNode('chest', 'treasure', ('fight',)),
                      MapNode('fight', 'combat', (), 'overgrowth_nibbit')), 'chest')
    run = RunEngine(seed=2, graph=graph, config=RunConfig(), rng_profile='native')
    rarity = relics.roll(deepcopy(run.state.rng), 'treasure_room_relics')
    # Authored bags isolate skip/pickup semantics while preserving native rolls.
    name = {'common': 'strawberry', 'uncommon': 'pear', 'rare': 'mango'}[rarity]
    for owner in ('shared', 'player'):
        run.state.relic_bags[owner][rarity] = [name]
    player_before = deepcopy(run.state.relic_bags['player'])
    step(run, ChooseNode('chest'))
    assert run.state.pending['relic_id'] == name
    assert run.state.relic_bags['player'] == player_before
    assert name not in run.state.relic_bags['shared'][rarity]
    if claim:
        step(run, OpenChest())
        step(run, ClaimTreasureRelic(run.state.pending['treasure_id']))
        assert any(r.definition_id == name for r in run.state.relics)
    step(run, LeaveTreasure())
    restored = clone(run)
    expected = 'circlet' if claim else name
    for candidate in (run, restored):
        assert relics.pull(candidate.state, rarity=rarity, allowed=(name,)) == expected
    assert saved(run) == saved(restored)


def test_invalid_owner_rejects_before_rng_or_bag_mutation():
    run = RunEngine(seed=2, rng_profile='native')
    before = saved(run)
    with pytest.raises(ValueError, match='owner'):
        relics.pull(run.state, owner='other')
    assert saved(run) == before


def test_shared_pull_purges_only_shared_bag_and_keeps_caller_exclusions(monkeypatch):
    run = RunEngine(seed=2, rng_profile='native')
    for owner in ('shared', 'player'):
        run.state.relic_bags[owner]['common'] = ['anchor', 'strawberry', 'bag_of_preparation']
    player_before = deepcopy(run.state.relic_bags['player'])
    monkeypatch.setattr('game.headless.relics.eligibility.allowed_in_run',
                        lambda state, name: name != 'anchor')
    assert relics.pull(run.state, rarity='common', owner='shared', blacklist=('strawberry',)) == 'bag_of_preparation'
    assert run.state.relic_bags['shared']['common'] == ['strawberry']
    assert run.state.relic_bags['player'] == player_before
