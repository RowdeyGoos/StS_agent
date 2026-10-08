"""Isolate experimental selection changes from allocation and public sampling."""
from dataclasses import asdict, replace
import hashlib
import json

import pytest

from game.agent.search import SearchConfig, SearchPolicy
from game.agent.headless import HeadlessAdapter
from .test_search import UniformPolicy, card_action, fixture


class SkewedPolicy(UniformPolicy):
    def probabilities(self, decision):
        strike = card_action(decision, 'strike').ref
        return {a.ref: .001 if a.ref == strike else .999 for a in decision.candidates}, .5


def test_final_choice_only_can_take_exact_win_without_changing_search_targets_or_work():
    run, adapter = fixture(('strike', 'wound'), hp=1, enemy_hp=1)
    before, public = run.snapshot(), adapter.observe().decision
    config = SearchConfig(simulations=24, time_limit=30)
    original = SearchPolicy(SkewedPolicy(), config).choose(public)
    final_only = SearchPolicy(SkewedPolicy(), replace(config, final_selection='max_value')).choose(public)
    scaled = SearchPolicy(SkewedPolicy(), replace(config, q_scale=1.)).choose(public)
    strike = card_action(public, 'strike').ref
    assert original.action_ref != strike
    assert final_only.action_ref == scaled.action_ref == strike
    assert final_only.values == original.values
    assert final_only.visits == original.visits
    assert final_only.probabilities == original.probabilities
    assert final_only.tree_work == original.tree_work
    assert scaled.probabilities[strike] > original.probabilities[strike]
    assert original.values[strike] == pytest.approx(1 + .1 * 7 / 80)
    assert run.snapshot() == before


@pytest.mark.parametrize('simulations', [1, 7, 24, 25])
def test_max_value_uses_visited_final_round_contenders_only(simulations):
    _, adapter = fixture()
    config = SearchConfig(simulations=simulations, time_limit=30, max_depth=2, leaf_rollout_steps=2)
    public = adapter.observe().decision
    a = SearchPolicy(UniformPolicy(), config).choose(public)
    b = SearchPolicy(UniformPolicy(), replace(config, final_selection='max_value')).choose(public)
    assert not a.reason and not b.reason and not b.cutoff
    assert (a.values, a.visits, a.probabilities, a.tree_work) == (b.values, b.visits, b.probabilities, b.tree_work)
    finalists = [ref for ref in b.tree_work['root_rounds'][-1]['ranked'] if b.visits[ref]]
    assert b.action_ref in finalists
    assert b.values[b.action_ref] == max(b.values[ref] for ref in finalists)
    evidence = b.tree_work['root_evidence']
    for ref, row in evidence.items():
        assert sum(row[k] for k in ('tree_terminals', 'leaf_terminals', 'critic_bootstraps')) == b.visits[ref]
        if b.visits[ref]:
            assert row['value_sum_squares'] / b.visits[ref] >= b.values[ref] ** 2 - 1e-9
    assert sum(row['tree_terminals'] for row in evidence.values()) == b.tree_work['terminals']
    assert sum(row['leaf_terminals'] for row in evidence.values()) == b.leaf_work['terminals']
    assert sum(row['critic_bootstraps'] for row in evidence.values()) == b.leaf_work['bootstraps']


@pytest.mark.parametrize('settings', [dict(q_scale=1.), dict(final_selection='max_value')])
def test_selection_variants_preserve_hidden_state_and_rng_boundary(settings):
    run, adapter = fixture(('strike', 'defend') * 5)
    first = adapter.observe().decision
    run.combat.player.deck.draw_pile.reverse()
    run.combat.rng.random()
    run.combat.player.deck.target_rng.random()
    second = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    config = SearchConfig(simulations=8, max_depth=2, leaf_rollout_steps=2, time_limit=30,
                          seed=21, exploration=True, **settings)
    a, b = [SearchPolicy(UniformPolicy(), config).choose(d) for d in (first, second)]
    assert (a.action_ref, a.probabilities, a.visits, a.values, a.tree_work) == (
        b.action_ref, b.probabilities, b.visits, b.values, b.tree_work)


def test_default_teacher_identity_matches_before_selection_options():
    for leaf in (0, 4):
        config = SearchConfig(leaf_rollout_steps=leaf)
        old = asdict(config)
        del old['q_scale'], old['final_selection']
        if not leaf:
            del old['leaf_rollout_steps']
        expected = 'sts_combat_search_v1:' + hashlib.sha256(
            json.dumps([UniformPolicy.identity, old], sort_keys=True).encode()).hexdigest()
        assert SearchPolicy(UniformPolicy(), config).identity == expected
        assert SearchPolicy(UniformPolicy(), replace(config, q_scale=1.)).identity != expected
        assert SearchPolicy(UniformPolicy(), replace(config, final_selection='max_value')).identity != expected


def test_final_choice_does_not_resurrect_eliminated_highest_q():
    class ExtremePrior(UniformPolicy):
        def probabilities(self, public):
            strike = card_action(public, 'strike').ref
            return {a.ref: 1e-12 if a.ref == strike else (1 - 1e-12) / (len(public.candidates) - 1)
                    for a in public.candidates}, .5
    _, adapter = fixture(('strike', 'defend', 'defend'), enemy_hp=1)
    public = adapter.observe().decision
    result = SearchPolicy(ExtremePrior(), SearchConfig(simulations=24, max_depth=1,
        time_limit=30, final_selection='max_value')).choose(public)
    strike = card_action(public, 'strike').ref
    assert result.visits[strike] > 0
    assert result.values[strike] == max(result.values.values())
    assert strike not in result.tree_work['root_rounds'][-1]['ranked']
    assert result.action_ref != strike


@pytest.mark.parametrize('completed', [0, 1])
def test_final_choice_handles_zero_and_partial_time_budget(monkeypatch, completed):
    import game.agent.search.policy as module
    _, adapter = fixture(('strike', 'defend'), enemy_hp=1)
    public = adapter.observe().decision
    planner = SearchPolicy(UniformPolicy(), SearchConfig(simulations=8, time_limit=.5,
                                                        final_selection='max_value'))
    clock = [0.]
    monkeypatch.setattr(module.time, 'perf_counter', lambda: clock[0])
    if completed:
        sample = module.PublicCombatModel.sample
        def wrapped_sample(self, seed):
            value = sample(self, seed)
            clock[0] = 1.
            return value
        monkeypatch.setattr(module.PublicCombatModel, 'sample', wrapped_sample)
    else:
        node = planner._node
        def wrapped_node(decision, timings):
            value = node(decision, timings)
            clock[0] = 1.
            return value
        monkeypatch.setattr(planner, '_node', wrapped_node)
    result = planner.choose(public)
    assert result.simulations == completed
    assert result.cutoff == 'search_time_budget'
    if completed:
        assert result.reason is None and result.visits[result.action_ref] == 1
    else:
        assert result.reason == 'no_completed_simulation'
        assert result.probabilities == UniformPolicy().probabilities(public)[0]


@pytest.mark.parametrize('change', [dict(q_scale=0), dict(q_scale=True), dict(q_scale=float('nan')),
                                  dict(q_scale=101), dict(final_selection='argmax_target')])
def test_selection_config_rejects_undefined_variants(change):
    with pytest.raises(ValueError):
        SearchConfig(**change)


def test_cli_exposes_selection_variants():
    from argparse import ArgumentParser
    from game.cli.search_args import add_search_arguments, search_config
    parser = ArgumentParser()
    add_search_arguments(parser)
    config = search_config(parser.parse_args(['--search', '--search-q-scale', '1', '--search-final-selection', 'max_value']))
    assert config.q_scale == 1. and config.final_selection == 'max_value'


@pytest.mark.parametrize('settings', [dict(q_scale=1.), dict(final_selection='max_value')])
def test_direct_belief_diagnostics_are_independent_of_actual_hidden_state(settings):
    from game.agent.training.scenarios import Scenario
    from .test_belief import actual
    start = Scenario('overgrowth_vantom', 'controlled').planning_start()
    run, adapter = actual(start, seed=15)
    first = adapter.observe().decision
    run.combat.player.deck.draw_pile.reverse()
    run.combat.rng.random()
    run.combat.player.deck.target_rng.random()
    second = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    snapshot = run.snapshot()
    config = SearchConfig(model_version='direct_belief_v1', simulations=8, max_depth=2,
                          leaf_rollout_steps=2, time_limit=30, belief_particles=2, seed=19, **settings)
    results = []
    for public in (first, second):
        planner = SearchPolicy(UniformPolicy(), config)
        planner.begin_combat(start, public)
        results.append(planner.choose(public))
    a, b = results
    assert a.reason is None and b.reason is None
    assert (a.action_ref, a.probabilities, a.values, a.visits, a.tree_work) == (
        b.action_ref, b.probabilities, b.values, b.visits, b.tree_work)
    assert run.snapshot() == snapshot
