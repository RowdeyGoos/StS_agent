"""Public-only leaf continuations, bounded bootstraps and teacher identity."""
from dataclasses import asdict
import hashlib
import json
from types import SimpleNamespace

import pytest

from game.agent.search import SearchConfig, SearchPolicy
from game.agent.search.model import observation_key
from game.agent.headless import HeadlessAdapter
from .test_search import UniformPolicy, fixture


def test_disabled_rollouts_keep_historical_teacher_identity():
    config = SearchConfig(simulations=8)
    old = asdict(config)
    old.pop('leaf_rollout_steps')
    old.pop('q_scale')
    old.pop('final_selection')
    identity = 'sts_combat_search_v1:' + hashlib.sha256(
        json.dumps([UniformPolicy.identity, old], sort_keys=True).encode()).hexdigest()
    assert SearchPolicy(UniformPolicy(), config).identity == identity
    assert SearchPolicy(UniformPolicy(), SearchConfig(simulations=8, leaf_rollout_steps=2)).identity != identity


def test_leaf_continuation_reaches_settled_lethal_and_preserves_actual_game():
    # Vantom's initial Slippery caps each of the first hits at one damage.
    run, adapter = fixture(('strike', 'strike', 'defend'), enemy_hp=2)
    before = run.snapshot()
    result = SearchPolicy(UniformPolicy(), SearchConfig(simulations=16, max_depth=1,
        leaf_rollout_steps=4, time_limit=20)).choose(adapter.observe().decision)
    assert result.reason is None and result.cutoff is None
    assert result.leaf_work['steps'] > 0 and result.leaf_work['terminals'] > 0
    assert max(result.values.values()) == pytest.approx(1 + .1 * 46 / 80)
    assert run.snapshot() == before
    assert result.simulations == 16
    assert sum(result.probabilities.values()) == pytest.approx(1)


def test_rollout_choices_do_not_see_actual_hidden_order_or_rng():
    run, adapter = fixture(('strike', 'defend') * 5)
    first = adapter.observe().decision
    run.combat.player.deck.draw_pile.reverse()
    run.combat.rng.random()
    run.combat.player.deck.target_rng.random()
    second = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    assert observation_key(first) == observation_key(second)
    config = SearchConfig(simulations=8, max_depth=2, leaf_rollout_steps=3, time_limit=20, seed=12)
    a, b = [SearchPolicy(UniformPolicy(), config).choose(s) for s in (first, second)]
    assert (a.action_ref, a.probabilities, a.values, a.visits, a.leaf_work) == (
        b.action_ref, b.probabilities, b.values, b.visits, b.leaf_work)


def test_nonterminal_rollout_limit_uses_final_public_critic(monkeypatch):
    policy = SearchPolicy(UniformPolicy(), SearchConfig(leaf_rollout_steps=1))
    nodes = [SimpleNamespace(keys=['initial'], priors=[1.], value=.2),
             SimpleNamespace(keys=['successor'], priors=[1.], value=.8)]
    observed = []
    world = SimpleNamespace(timings=dict(transition=0., projection=0.), terminal_value=None)
    def step(public, key):
        assert public == 'public-before' and key == 'initial'
        observed.append(key)
        return 'public-after'
    world.step = step
    monkeypatch.setattr(policy, '_node', lambda public, timings, prepared=None: (nodes[1], []) if public == 'public-after' else None)
    work = dict(steps=0, terminals=0, bootstraps=0, time_bootstraps=0)
    value = policy._leaf_value(world, 'public-before', nodes[0], dict(transition=0., projection=0.), work, float('inf'))
    assert value == .8 and observed == ['initial']
    assert work == dict(steps=1, terminals=0, bootstraps=1, time_bootstraps=0)
    observed.clear()
    value = policy._leaf_value(world, 'public-before', nodes[0], {}, work, 0.)
    assert value == .2 and observed == [] and work['time_bootstraps'] == 1


@pytest.mark.parametrize('steps', [-1, True, 513, 1.5])
def test_rollout_budget_validation(steps):
    with pytest.raises(ValueError, match='rollout'):
        SearchConfig(leaf_rollout_steps=steps)


def test_tree_diagnostics_separate_exact_terminals_from_critic_bootstraps():
    _, adapter = fixture(('strike', 'strike', 'defend'), enemy_hp=2)
    result = SearchPolicy(UniformPolicy(), SearchConfig(simulations=24, max_depth=3,
        leaf_rollout_steps=4, time_limit=20)).choose(adapter.observe().decision)
    assert result.reason is None and result.cutoff is None
    work = result.tree_work
    assert sum(work['depth_histogram'].values()) == result.simulations
    assert all(1 <= int(depth) <= 3 for depth in work['depth_histogram'])
    assert work['terminals'] + result.leaf_work['terminals'] + result.leaf_work['bootstraps'] == 24
    assert work['expansions'] <= 24
    rounds = work['root_rounds']
    assert rounds[0]['simulations_before'] == 0
    assert rounds[-1]['simulations_after'] == 24
    for before, after in zip(rounds, rounds[1:]):
        assert before['simulations_after'] == after['simulations_before']
        assert set(after['ranked']) <= set(before['ranked'])
    assert all(set(r['ranked']) == set(r['visits']) for r in rounds)
    assert result.action_ref == rounds[-1]['ranked'][0]
    assert result.to_dict()['tree_work'] == work


def test_forced_action_has_no_simulated_tree_work():
    _, adapter = fixture(('wound',))
    result = SearchPolicy(UniformPolicy(), SearchConfig()).choose(adapter.observe().decision)
    assert result.reason == 'forced_action'
    assert result.tree_work == dict(depth_histogram={}, expansions=0, terminals=0, root_rounds=[])
